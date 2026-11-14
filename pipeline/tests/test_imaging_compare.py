"""WS2-7: season coadds and flux-matched differences show movers as dipoles and cancel static stars."""

import json
from datetime import UTC, datetime

import numpy as np
import pytest
from PIL import Image

from errante.detect.difference import fit_scale, residuals, static_sky
from errante.imaging.compare import (
    GridFrame,
    build_comparisons,
    coadd,
    compare_field,
    difference,
    diverging_rgba,
    flux_scale,
)
from errante.imaging.grid import make_grid
from errante.models import Frame, Provenance, SkyCoord, SkyField

N = 48
STARS = [(10, 12, 40.0), (30, 8, 25.0), (38, 36, 60.0), (14, 34, 30.0), (24, 24, 50.0), (6, 40, 35.0)]


def scene(stars=STARS, scale=1.0, sky=0.0, noise=0.05, seed=0, extra=()):
    """Gaussian stars (x, y, amp) on a N x N grid, PNG orientation, MJy/sr-like units."""
    rng = np.random.default_rng(seed)
    yy, xx = np.mgrid[0:N, 0:N]
    img = sky + noise * rng.standard_normal((N, N))
    for x, y, amp in [*stars, *extra]:
        img += scale * amp * np.exp(-((xx - x) ** 2 + (yy - y) ** 2) / (2 * 1.0**2))
    return img.astype(np.float32)


def frame(fid, det, mjd, data, var=0.0025, bad=None):
    return GridFrame(
        fid, det, mjd, data, np.zeros(data.shape, bool) if bad is None else bad, np.full(data.shape, var, np.float32)
    )


def test_coadd_weights_by_inverse_variance_and_skips_bad_pixels():
    a = np.full((4, 4), 1.0, np.float32)
    b = np.full((4, 4), 3.0, np.float32)
    a[0, 0] = 100.0  # star-free frames: sky = the constant, removed
    bad = np.zeros((4, 4), bool)
    bad[1, 1] = True
    c = coadd([frame("a", 2, 1.0, a, var=1.0), frame("b", 2, 2.0, b, var=3.0, bad=bad)])
    assert c.data[0, 0] == pytest.approx((99.0 * 1 + 0.0 / 3) / (1 + 1 / 3))
    assert c.variance[2, 2] == pytest.approx(1 / (1 + 1 / 3))
    assert c.coverage[1, 1] == 1 and c.coverage[2, 2] == 2
    assert c.variance[1, 1] == pytest.approx(1.0)  # only frame a there


def test_coadd_refuses_mixed_detectors():
    with pytest.raises(ValueError, match="single detector"):
        coadd([frame("a", 1, 1.0, scene()), frame("b", 4, 1.0, scene())])


def test_flux_scale_cancels_the_wavelength_change_of_static_stars():
    early = coadd([frame("e", 3, 60900.0, scene(seed=1))])
    late = coadd([frame("l", 3, 61270.0, scene(scale=0.6, seed=2))])  # same stars, other wavelength
    s, n = flux_scale(late, early)
    assert s == pytest.approx(0.6, rel=0.02) and n >= 20
    d = difference(late, early)
    assert np.nanmax(np.abs(d.data)) < 1.0  # stars of amplitude 15-36 cancel to the noise level


def test_a_moving_star_becomes_a_dipole_and_a_variable_a_monopole():
    early = coadd([frame("e", 1, 60900.0, scene(seed=3, extra=[(20, 30, 80.0), (40, 20, 40.0)]))])
    late = coadd(
        [frame("l", 1, 61270.0, scene(scale=0.8, seed=4, extra=[(20, 29, 0.8 * 80.0), (40, 20, 0.8 * 80.0)]))]
    )  # mover went 1 px north (smaller y); the star at (40, 20) doubled its flux
    d = difference(late, early)
    assert d.data[29, 20] > 10 and d.data[31, 20] < -10  # dipole: + where it is now, - where it was
    assert d.data[20, 40] > 10 and d.data[20, 40] > 5 * abs(d.data[20, 38])  # brightening: same-sign peak
    assert d.variance[0, 0] == pytest.approx(0.0025 + d.scale**2 * 0.0025)


def test_build_comparisons_pairs_seasons_within_each_detector_only():
    frames = [
        frame(f"{det}_{s}", det, mjd, scene(seed=10 * det + s))
        for det in (1, 4)
        for s, mjd in enumerate((60908.0, 61116.0, 61270.0))
    ]
    season = {60908.0: 0, 61116.0: 1, 61270.0: 2}
    coadds, diffs = build_comparisons(frames, season.get)
    assert [c.id for c in coadds] == ["D1_S0", "D1_S1", "D1_S2", "D4_S0", "D4_S1", "D4_S2"]
    assert [d.id for d in diffs] == ["D1_S1-S0", "D1_S2-S0", "D1_S2-S1", "D4_S1-S0", "D4_S2-S0", "D4_S2-S1"]


def test_diverging_colours_and_transparent_no_data():
    rgba = diverging_rgba(np.array([[0.0, 5.0, -5.0, np.nan]]), limit=5.0)
    zero, pos, neg, nodata = rgba[0]
    assert tuple(zero[:3]) == (0, 0, 0) and zero[3] == 255
    assert pos[0] > pos[2] and pos[0] == 255  # orange: brighter now
    assert neg[2] > neg[0] and neg[2] == 255  # cyan: brighter before
    assert nodata[3] == 255 and nodata[0] == nodata[1] == nodata[2] >= 70  # grey checker, not "no change"


def _field(frames_meta):
    grid = make_grid(150.0, 11.0, N * 6.15 / 3600)
    return SkyField(
        id="cmp-field",
        name="Compare",
        center=SkyCoord(ra=150.0, dec=11.0),
        size_deg=N * 6.15 / 3600,
        grid=grid,
        frames=[
            Frame(
                id=f"{o}D{d}",
                obs_id=o,
                detector=d,
                mjd=m,
                date_obs=datetime(2026, 1, 1, tzinfo=UTC),
                release="dr1",
                image=f"frames/{o}D{d}.png",
                source_uri=f"ibe/{o}",
            )  # fmt: skip
            for o, d, m in frames_meta
        ],
        provenance=Provenance(pipeline_version="t", built_at=datetime.now(UTC), synthetic=False),
    )


def test_compare_field_writes_coadds_differences_and_provisional_metadata(tmp_path):
    meta_in = [("A", 2, 60908.0), ("B", 2, 60910.0), ("C", 2, 61116.0), ("D", 5, 60908.0), ("E", 5, 61116.0)]
    fld = _field(meta_in)

    def load(refs):
        return [frame(f"{r.obs_id}D{r.detector}", r.detector, r.mjd, scene(seed=i)) for i, r in enumerate(refs)]

    meta = compare_field(fld, tmp_path, load)
    assert [c["id"] for c in meta["coadds"]] == ["D2_S0", "D2_S1", "D5_S0", "D5_S1"]
    assert meta["coadds"][0]["frame_ids"] == ["AD2", "BD2"]
    assert [d["id"] for d in meta["differences"]] == ["D2_S1-S0", "D5_S1-S0"]
    assert "not part of the data contract" in meta["format"]
    assert json.loads((tmp_path / "compare" / "compare.json").read_text())["field_id"] == "cmp-field"
    png = Image.open(tmp_path / meta["differences"][0]["image"])
    assert png.mode == "RGBA" and png.size == (N, N)  # same shape as the coadded grid data
    assert (tmp_path / meta["coadds"][0]["image"]).exists()


def test_compare_field_needs_at_least_one_loaded_frame(tmp_path):
    with pytest.raises(ValueError, match="could be loaded"):
        compare_field(_field([("A", 1, 60908.0)]), tmp_path, lambda refs: [None for _ in refs])


def test_detect_static_sky_and_residuals():
    stack = np.stack([scene(seed=s) for s in range(5)])
    bad = np.zeros(stack.shape, bool)
    stack[2, 24, 24] = 1e6  # cosmic ray in one frame
    bad[0] = True  # a whole frame flagged
    template = static_sky(stack, bad)
    assert template[24, 24] == pytest.approx(scene()[24, 24], abs=0.3)
    with pytest.raises(ValueError):
        static_sky(stack[0])
    frame_ = scene(scale=0.7, seed=9, extra=[(20, 30, 50.0)])  # new source + wavelength change
    assert fit_scale(frame_, template) == pytest.approx(0.7, rel=0.03)
    res = residuals(frame_, template)
    assert res[30, 20] > 30 and abs(res[24, 24]) < 1.0  # new source (0.7 x 50) survives, stars cancel
