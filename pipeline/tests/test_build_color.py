"""WS2: build_field writes false-color season composites (Field.composites) after choosing the final frames."""

import json

import numpy as np
from PIL import Image
from test_build_robust import SEASON_0, SEASON_1, config, frame, install_archive, note

from errante import build
from errante.build import build_field
from errante.cli import main
from errante.imaging import color
from errante.models import SkyField
from errante.products import ProductStore

# Per season: D1 0.95 (blue), D2 1.25 (J), D3 1.68 (H, published) and D3 2.17 (Ks, pool only), D6 4.70 (red).
WAVELENGTHS = [("d1", 1, 0.95), ("j2", 2, 1.25), ("h3", 3, 1.68), ("k3", 3, 2.17), ("r6", 6, 4.70)]


def archive(monkeypatch):
    frames = [
        frame(f"{tag}_{s}", start + 0.1 * i, det=det, lam=lam, seed=10 * s + i)
        for s, start in enumerate((SEASON_0, SEASON_1))
        for i, (tag, det, lam) in enumerate(WAVELENGTHS)
    ]
    return install_archive(monkeypatch, frames)


def test_build_writes_detector_and_jhk_composites_from_final_frames_and_pool(monkeypatch, tmp_path):
    _, fetched = archive(monkeypatch)
    # 8 published frames = one per (season, detector); the pool (10) also holds the Ks exposures.
    field = build_field(config(max_frames=8), tmp_path)

    published = {f.id for f in field.frames}
    assert len(fetched) == 10 and len(published) == 8
    assert {"k3_0D3", "k3_1D3"}.isdisjoint(published)  # D3 shows the H exposures (same colour every season)
    by_id = {c.id: c for c in field.composites}
    assert sorted(by_id) == ["detectors_S0", "detectors_S1", "jhk_S0", "jhk_S1"]

    det = by_id["detectors_S1"]
    assert [ch.detector for ch in det.channels] == [6, 3, 1]
    assert [ch.frame_ids for ch in det.channels] == [["r6_1D6"], ["h3_1D3"], ["d1_1D1"]]
    assert all(set(ch.frame_ids) <= published for ch in det.channels)

    jhk = by_id["jhk_S0"]
    assert [ch.frame_ids for ch in jhk.channels] == [["k3_0D3"], ["h3_0D3"], ["j2_0D2"]]
    assert [ch.wavelength_um for ch in jhk.channels] == [2.17, 1.68, 1.25]

    fdir = ProductStore(tmp_path).field_dir("t-field")
    for comp in field.composites:
        with Image.open(fdir / comp.image) as png:
            assert png.mode in ("RGB", "RGBA") and png.size == (field.grid.width_px, field.grid.height_px)
    assert note(field, "False-color composites: ").count("(infrared, not true color)") == 1

    stored = SkyField.model_validate_json((fdir / "field.json").read_text(encoding="utf-8"))
    assert stored.composites == field.composites
    assert main(["validate", "--dir", str(tmp_path)]) == 0


def test_composites_use_the_variance_plane_on_the_grid(monkeypatch, tmp_path):
    archive(monkeypatch)
    seen = []
    real = color.write_composites

    def spy(field_dir, final, pool):
        seen.extend(final)
        return real(field_dir, final, pool)

    monkeypatch.setattr(color, "write_composites", spy)
    build_field(config(max_frames=8), tmp_path)
    assert seen and all(f.variance is not None and f.variance.shape == f.data.shape for f in seen)
    assert all(f.wavelength_um is not None for f in seen)


def test_a_composite_failure_does_not_block_the_published_field(monkeypatch, tmp_path):
    archive(monkeypatch)

    def broken(*args, **kwargs):
        raise RuntimeError("colour went wrong")

    monkeypatch.setattr(color, "write_composites", broken)
    field = build_field(config(max_frames=8), tmp_path)
    assert len(field.frames) == 8 and field.composites == []
    assert note(field, "False-color composites: ") == (
        "False-color composites: not built (RuntimeError: colour went wrong)."
    )
    assert ProductStore(tmp_path).read_field("t-field").frames


def test_a_field_without_the_needed_detectors_has_no_composites_and_says_why(monkeypatch, tmp_path):
    frames = [frame(f"o{s}", start, det=2, lam=1.4, seed=s) for s, start in enumerate((SEASON_0, SEASON_1))]
    install_archive(monkeypatch, frames)
    field = build_field(config(max_frames=4), tmp_path)
    assert field.composites == []
    text = note(field, "False-color composites: ")
    assert text.startswith("False-color composites: none built") and "detectors S0" in text and "jhk S1" in text


def test_rebuild_with_fewer_seasons_removes_stale_composite_pngs(monkeypatch, tmp_path):
    archive(monkeypatch)
    build_field(config(max_frames=8), tmp_path)
    fdir = ProductStore(tmp_path).field_dir("t-field")
    assert (fdir / "color" / "detectors_S1.png").exists()

    only_season_0 = [frame(f"{tag}_0", SEASON_0 + 0.1 * i, det=det, lam=lam, seed=i)
                     for i, (tag, det, lam) in enumerate(WAVELENGTHS)]  # fmt: skip
    install_archive(monkeypatch, only_season_0)
    monkeypatch.setattr(build, "load_field_configs", lambda: {"t-field": config(max_frames=8)})
    assert main(["build", "t-field", "--out", str(tmp_path)]) == 0
    stored = json.loads((fdir / "field.json").read_text(encoding="utf-8"))
    assert [c["id"] for c in stored["composites"]] == ["detectors_S0", "jhk_S0"]
    assert sorted(p.name for p in (fdir / "color").iterdir()) == ["detectors_S0.png", "jhk_S0.png"]
    assert np.isfinite(stored["composites"][0]["mjd_min"])
