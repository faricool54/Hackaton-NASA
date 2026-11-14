"""The temporal viewer must remain usable without automatic analysis."""

from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from errante.build import FieldConfig, build_field
from errante.cli import main
from errante.data import cutouts, fits_io, irsa
from errante.detect import linking, scoring, sources
from errante.imaging import reproject
from errante.models import FrameRef, SearchResult, SkyCoord
from errante.products import ProductStore
from errante.science import known_objects


@pytest.fixture
def archive(monkeypatch):
    cfg = FieldConfig(id="test-field", name="Test field", ra=150, dec=11, size_deg=0.01)
    refs = [FrameRef(obs_id="OBS1", detector=2, mjd=61000, release="dr1")]
    result = SearchResult(center=SkyCoord(ra=150, dec=11), radius_deg=0, frames=refs)
    monkeypatch.setattr(irsa, "search_frames", lambda *a, **kw: result)
    monkeypatch.setattr(cutouts, "fetch_cutouts", lambda *a, **kw: [Path("OBS1.fits")])
    image = SimpleNamespace(obs_id="OBS1", detector=2, mjd=61000, date_obs=datetime.now(UTC).isoformat())
    monkeypatch.setattr(fits_io, "read_spherex", lambda path: image)

    def project(image, grid):
        shape = (grid.height_px, grid.width_px)
        return np.ones(shape), np.zeros(shape, dtype=bool)

    monkeypatch.setattr(reproject, "reproject_to_grid", project)
    return cfg, result


def test_basic_build_publishes_images_without_calling_analysis(archive, monkeypatch, tmp_path):
    cfg, _ = archive

    def forbidden(*args, **kwargs):
        pytest.fail("The basic image build must not call automatic analysis")

    monkeypatch.setattr(sources, "find_sources", forbidden)
    monkeypatch.setattr(known_objects, "objects_in_frame", forbidden)
    field = build_field(cfg, tmp_path)
    store = ProductStore(tmp_path)
    assert store.read_manifest().fields[0].n_frames == 1
    assert (store.field_dir(cfg.id) / field.frames[0].image).exists()
    assert store.read_candidates(cfg.id).candidates == []
    assert store.read_known(cfg.id).objects == []
    assert "were not run" in store.read_field(cfg.id).provenance.notes[0]


def test_analysis_failure_preserves_the_viewable_field(archive, monkeypatch, tmp_path):
    cfg, _ = archive

    def unavailable(*args, **kwargs):
        raise NotImplementedError("Detection is not available")

    monkeypatch.setattr(sources, "find_sources", unavailable)
    with pytest.raises(NotImplementedError, match="Detection"):
        build_field(cfg, tmp_path, analyze=True)
    store = ProductStore(tmp_path)
    field = store.read_field(cfg.id)
    assert store.read_manifest().fields[0].id == cfg.id
    assert (store.field_dir(cfg.id) / field.frames[0].image).exists()
    assert "has not completed" in field.provenance.notes[0]


def test_successful_analysis_records_that_it_ran(archive, monkeypatch, tmp_path):
    cfg, _ = archive
    monkeypatch.setattr(sources, "find_sources", lambda *a: [])
    monkeypatch.setattr(linking, "link_tracks", lambda *a: [])
    monkeypatch.setattr(scoring, "score_tracks", lambda *a: [])
    monkeypatch.setattr(known_objects, "objects_in_frame", lambda *a: [])
    monkeypatch.setattr(known_objects, "crossmatch", lambda candidates, known: candidates)
    build_field(cfg, tmp_path, analyze=True)
    assert "completed" in ProductStore(tmp_path).read_field(cfg.id).provenance.notes[0]


def test_no_coverage_does_not_publish_a_field(archive, monkeypatch, tmp_path):
    cfg, result = archive
    result.frames = []

    def forbidden(*args, **kwargs):
        pytest.fail("No-coverage searches must not attempt downloads")

    monkeypatch.setattr(cutouts, "fetch_cutouts", forbidden)
    with pytest.raises(ValueError, match="No usable SPHEREx frames"):
        build_field(cfg, tmp_path)
    assert not ProductStore(tmp_path).manifest_path.exists()


@pytest.mark.parametrize("analyze", [False, True])
def test_cli_build_analysis_is_opt_in(monkeypatch, tmp_path, analyze):
    from errante import build

    calls = []
    monkeypatch.setattr(build, "build_field", lambda cfg, out, **kw: calls.append(kw["analyze"]))
    args = ["build", "barnards-star", "--out", str(tmp_path)]
    assert main(args + (["--analyze"] if analyze else [])) == 0
    assert calls == [analyze]
