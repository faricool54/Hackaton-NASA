"""WS2: frames are spread over seasons x detectors, and a real-WCS build blinks on one grid."""

from pathlib import Path

import numpy as np
import pytest
from test_imaging_reproject import DEC0, PIXEL_DEG, RA0, fake_image

from errante.build import FieldConfig, build_field, season_index, select_frames
from errante.data import cutouts, fits_io, irsa
from errante.models import FrameRef, SearchResult, SkyCoord
from errante.products import ProductStore

SEASON_STARTS = (60903.0, 61110.0, 61269.0)  # Barnard's Star seasons (docs/DATA.md §3.0)


def ref(obs: str, det: int, mjd: float, release="dr1", wl=None) -> FrameRef:
    return FrameRef(obs_id=obs, detector=det, mjd=mjd, release=release, wavelength_um=wl,
                    irsa_uri=f"ibe/data/spherex/{release}/level2/{obs}D{det}.fits")  # fmt: skip


def archive_like(n_per_group=20, detectors=(1, 2, 3, 4, 5, 6)) -> list[FrameRef]:
    out = []
    for s, start in enumerate(SEASON_STARTS):
        for det in detectors:
            for i in range(n_per_group):
                out.append(ref(f"S{s}_{det}_{i:02d}", det, start + i * 1.5))
    return sorted(out, key=lambda r: r.mjd)  # what a TAP ORDER BY time returns


def groups_of(refs):
    seasons = season_index([r.mjd for r in refs])
    return {(s, r.detector) for s, r in zip(seasons, refs, strict=True)}


def test_season_index_splits_on_gaps_longer_than_30_days():
    assert season_index([61110.0, 60903.0, 60925.0, 61269.0, 60904.0, 60950.0]) == [1, 0, 0, 2, 0, 0]
    assert season_index([60903.0, 60940.0]) == [0, 1]  # 37-day gap
    assert season_index([]) == []


def test_old_first_n_by_time_was_one_season_new_selection_covers_all():
    refs = archive_like()
    assert len(groups_of(refs[:40])) == 6  # the old cut: 6 detectors, 1 season
    picked = select_frames(refs, 40)
    assert len(picked) == 40
    assert groups_of(picked) == {(s, d) for s in range(3) for d in range(1, 7)}
    counts = {}
    for s, r in zip(season_index([r.mjd for r in picked]), picked, strict=True):
        counts[(s, r.detector)] = counts.get((s, r.detector), 0) + 1
    assert set(counts.values()) <= {2, 3}  # round-robin: balanced
    assert [r.mjd for r in picked] == sorted(r.mjd for r in picked)


def test_small_budget_keeps_whole_detectors_across_seasons():
    refs = archive_like(n_per_group=3, detectors=(1, 2, 3))
    refs += [ref("LONE", 4, 60905.0)]  # D4 seen in one season only
    picked = select_frames(refs, 6)
    dets = {r.detector for r in picked}
    assert len(picked) == 6 and 4 not in dets
    # every picked detector spans >30 days -> passes the batch validation of WS4
    for d in dets:
        mjds = [r.mjd for r in picked if r.detector == d]
        assert max(mjds) - min(mjds) > 30


def test_duplicate_exposures_keep_the_final_release():
    refs = [ref("A", 1, 60903.0, "qr3"), ref("A", 1, 60903.0, "dr1"), ref("B", 1, 61110.0, "qr3")]
    picked = select_frames(refs, 10)
    assert [(r.obs_id, r.release) for r in picked] == [("A", "dr1"), ("B", "qr3")]


def test_wavelength_matching_picks_the_same_colour_every_season():
    refs = [
        ref("s0_blue", 1, 60903.0, wl=0.80), ref("s0_red", 1, 60904.0, wl=1.05),
        ref("s1_red", 1, 61110.0, wl=1.04), ref("s1_mid", 1, 61111.0, wl=0.92),
        ref("s2_red", 1, 61269.0, wl=1.06), ref("s2_blue", 1, 61270.0, wl=0.79),
    ]  # fmt: skip
    picked = select_frames(refs, 3)
    assert [r.obs_id for r in picked] == ["s0_red", "s1_red", "s2_red"]


def test_empty_inputs():
    assert select_frames([], 40) == []
    assert select_frames(archive_like(1), 0) == []


@pytest.fixture
def real_wcs_archive(monkeypatch):
    """Two seasons of detector 1 + one frame that misses the field; images have real (rotated, SIP) WCS."""
    star = (RA0 + 4 * PIXEL_DEG, DEC0 - 3 * PIXEL_DEG, 80.0)
    images = {
        "OBS_A": fake_image(stars=(star,), obs_id="2025W35_1A_0001_1", mjd=60903.2, rotation_deg=10, zodi_level=3),
        "OBS_B": fake_image(stars=(star,), obs_id="2026W12_2B_0042_3", mjd=61110.4, rotation_deg=-75, zodi_level=4),
        "OBS_C": fake_image(obs_id="2026W12_2B_0043_1", mjd=61112.0, ra=RA0 + 2.0),  # 2 deg away
    }
    refs = [ref(k, 1, img.mjd) for k, img in images.items()]
    monkeypatch.setattr(irsa, "search_frames", lambda *a, **kw: SearchResult(
        center=SkyCoord(ra=RA0, dec=DEC0), radius_deg=0, frames=refs))  # fmt: skip
    monkeypatch.setattr(cutouts, "fetch_cutouts", lambda frames, *a, **kw: [Path(f"{f.obs_id}.fits") for f in frames])
    monkeypatch.setattr(fits_io, "read_spherex", lambda path: images[Path(path).stem])
    return FieldConfig(id="wcs-field", name="WCS field", ra=RA0, dec=DEC0, size_deg=0.05), star


def test_build_reprojects_real_wcs_frames_onto_one_grid(real_wcs_archive, tmp_path):
    cfg, star = real_wcs_archive
    field = build_field(cfg, tmp_path)
    store = ProductStore(tmp_path)
    fdir = store.field_dir(cfg.id)

    assert [f.id for f in field.frames] == ["2025W35_1A_0001_1D1", "2026W12_2B_0042_3D1"]
    assert any("Skipped 1" in n and "outside the cutout" in n for n in field.provenance.notes)
    assert (fdir / "thumb.png").exists()
    assert store.read_manifest().fields[0].thumbnail == "thumb.png"
    a, b = (f.stretch for f in field.frames)
    assert a.vmax - a.vmin == pytest.approx(b.vmax - b.vmin)  # same detector -> same contrast

    from PIL import Image

    from errante.imaging.grid import sky_to_png_xy

    ex, ey = (int(round(float(v))) for v in sky_to_png_xy(field.grid, star[0], star[1]))
    for fr in field.frames:
        png = np.asarray(Image.open(fdir / fr.image))
        assert png.shape == (field.grid.height_px, field.grid.width_px)
        peak = np.unravel_index(np.argmax(png), png.shape)
        assert abs(peak[0] - ey) <= 1 and abs(peak[1] - ex) <= 1  # same star, same pixel, both epochs
