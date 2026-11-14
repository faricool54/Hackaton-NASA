"""WS2-7: season coadds and flux-matched differences show movers as dipoles and cancel static stars."""

import json
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pytest
from PIL import Image
from test_imaging_reproject import DEC0, RA0, fake_image

from errante.cli import main
from errante.data import cutouts, fits_io
from errante.detect.difference import aperture_flux, fit_scale, residuals, star_flux_scale, static_sky
from errante.imaging import compare as compare_mod
from errante.imaging.compare import (
    GridFrame,
    build_comparisons,
    coadd,
    compare_field,
    difference,
    difference_limit,
    diverging_rgba,
    flux_scale,
    halo_radius,
    load_from_cutouts,
    target_exclusion,
)
from errante.imaging.grid import make_grid, sky_to_png_xy
from errante.imaging.reproject import reproject_to_grid, reproject_variance
from errante.models import Frame, FrameRef, Provenance, SkyCoord, SkyField
from errante.products import ProductStore

N = 48
# Field stars (x, y, amplitude), all outside the target circle around the centre (23.5, 23.5).
STARS = [
    (6, 6, 40.0), (40, 6, 25.0), (6, 40, 35.0), (40, 40, 60.0), (23, 6, 30.0),
    (6, 23, 45.0), (40, 23, 50.0), (23, 41, 28.0), (12, 32, 33.0), (34, 12, 38.0),
]  # fmt: skip


def scene(stars=STARS, scale=1.0, sky=0.0, noise=0.05, seed=0, extra=(), n=N):
    """Gaussian stars on a n x n grid (PNG orientation), MJy/sr-like units.

    ``scale`` multiplies the field stars only (the wavelength change); ``extra``
    sources (x, y, amp[, sigma]) are added as given.
    """
    rng = np.random.default_rng(seed)
    yy, xx = np.mgrid[0:n, 0:n]
    img = sky + noise * rng.standard_normal((n, n))
    for x, y, amp in stars:
        img += scale * amp * np.exp(-((xx - x) ** 2 + (yy - y) ** 2) / 2.0)
    for x, y, amp, *rest in extra:
        s = rest[0] if rest else 1.0
        img += amp * np.exp(-((xx - x) ** 2 + (yy - y) ** 2) / (2 * s**2))
    return img.astype(np.float32)


def frame(fid, det, mjd, data, var=0.0025, bad=None):
    variance = var if isinstance(var, np.ndarray) else np.full(data.shape, var, np.float32)
    return GridFrame(fid, det, mjd, data, np.zeros(data.shape, bool) if bad is None else bad, variance)


def test_coadd_one_weight_per_frame_and_skips_bad_pixels():
    a = np.full((4, 4), 1.0, np.float32)
    b = np.full((4, 4), 3.0, np.float32)
    a[0, 0] = 100.0  # star-free frames: sky = the constant, removed
    bad = np.zeros((4, 4), bool)
    bad[1, 1] = True
    c = coadd([frame("a", 2, 1.0, a, var=1.0), frame("b", 2, 2.0, b, var=3.0, bad=bad)])
    assert c.data[0, 0] == pytest.approx(99.0 * 1 / (1 + 1 / 3))
    assert c.variance[2, 2] == pytest.approx(1 / (1 + 1 / 3))
    assert c.coverage[1, 1] == 1 and c.coverage[2, 2] == 2
    assert c.variance[1, 1] == pytest.approx(1.0)  # only frame a there


def test_coadd_does_not_bias_bright_stars_with_their_own_poisson_noise():
    """Per-pixel 1/VARIANCE weights favour the frame where a star came out fainter."""
    hi, lo = scene(stars=[(24, 24, 60.0)], seed=1), scene(stars=[(24, 24, 40.0)], seed=2)
    var_hi = (0.01 + 0.5 * np.clip(hi, 0, None)).astype(np.float32)  # background + source Poisson term
    var_lo = (0.01 + 0.5 * np.clip(lo, 0, None)).astype(np.float32)
    c = coadd([frame("hi", 1, 1.0, hi, var_hi), frame("lo", 1, 2.0, lo, var_lo)])
    assert c.data[24, 24] == pytest.approx(50.0, abs=0.5)


def test_coadd_lists_only_frames_that_contributed():
    empty = frame("empty", 3, 1.0, np.full((N, N), np.nan, np.float32))
    c = coadd([frame("ok", 3, 2.0, scene()), empty])
    assert c.frame_ids == ["ok"] and c.skipped == ["empty"]


def test_coadd_refuses_mixed_detectors():
    with pytest.raises(ValueError, match="single detector"):
        coadd([frame("a", 1, 1.0, scene()), frame("b", 4, 1.0, scene())])


def test_flux_scale_cancels_the_wavelength_change_of_static_stars():
    early = coadd([frame("e", 3, 60900.0, scene(seed=1))])
    late = coadd([frame("l", 3, 61270.0, scene(scale=0.6, seed=2))])  # same stars, other wavelength
    s = flux_scale(late, early)
    assert s.fitted and s.n_stars >= 5 and s.scale == pytest.approx(0.6, rel=0.02)
    d = difference(late, early)
    assert np.nanmax(np.abs(d.data)) < 1.0  # stars of amplitude 15-36 cancel to the noise level


def test_a_bright_variable_target_does_not_set_the_scale():
    """Review finding: a pixel-level fit followed the target's halo (s ~ 2 instead of 1)."""
    target = [(23.5, 23.5, 400.0, 1.0), (23.5, 23.5, 40.0, 4.0)]  # core + extended halo
    early = coadd([frame("e", 2, 60900.0, scene(seed=3, extra=target))])
    brighter = [(x, y, 2 * a, s) for x, y, a, s in target]
    late = coadd([frame("l", 2, 61270.0, scene(seed=4, extra=brighter))])  # target doubled, field static
    d = difference(late, early)
    assert d.scale.scale == pytest.approx(1.0, abs=0.03)
    assert d.data[23, 23] > 300  # the brightening survives
    for x, y, _ in STARS:
        assert abs(d.data[y, x]) < 1.0  # static field stars do not look variable


def test_a_star_on_a_local_pedestal_and_gradient_gets_the_right_ratio():
    """Review finding (R Draconis): with a global sky, a halo pedestal under a star biased its ratio."""
    yy, xx = np.mgrid[0:N, 0:N]
    early = scene(seed=1) + 4.0 + 0.15 * xx  # pedestal + gradient (MJy/sr) ...
    late = scene(scale=0.6, seed=2) + 1.0 + 0.12 * yy - 0.05 * xx  # ... that is NOT 0.6 x the early one
    x, y, amp = STARS[9]
    box = amp * sum(np.exp(-(d**2) / 2) for d in range(-2, 3)) ** 2  # the star alone in the 5x5 box
    assert aperture_flux(early, x, y) == pytest.approx(box, rel=0.01)
    assert aperture_flux(early, x, y, sky_annulus=None) > 1.5 * box  # without the local sky
    local = star_flux_scale(late, early, 0.05)
    assert local.fitted and local.n_stars == len(STARS) and local.scale == pytest.approx(0.6, rel=0.01)
    assert abs(star_flux_scale(late, early, 0.05, sky_annulus=None).scale - 0.6) > 0.05


M = 88  # real fields are ~88 x 88 px
C = (M - 1) / 2
FAR_STARS = [(6, 6, 40.0), (81, 6, 30.0), (6, 81, 35.0), (81, 81, 50.0), (75, 12, 45.0), (10, 76, 28.0), (43, 4, 38.0)]
HALO_STARS = [  # 14-21 px from the target: inside its halo
    (43, 29, 30.0), (58, 43, 25.0), (34, 58, 40.0), (30, 33, 35.0), (57, 57, 30.0), (26, 48, 45.0),
    (56, 32, 28.0), (49, 62, 33.0), (36, 24, 26.0), (62, 50, 36.0), (28, 58, 32.0), (52, 26, 30.0),
]  # fmt: skip


def test_a_bright_target_with_a_wide_halo_does_not_bias_the_scale():
    """Review finding (R Draconis): the halo reached 25-30 px but only 13 px were excluded."""
    target = [(C, C, 400.0, 1.0), (C, C, 100.0, 8.0)]  # core + halo (sigma 8 px)
    brighter = [(x, y, 1.6 * a, s) for x, y, a, s in target]  # the target brightens, field stars x 0.7
    early_img = scene(FAR_STARS + HALO_STARS, seed=3, extra=target, n=M)
    late_img = scene(FAR_STARS + HALO_STARS, scale=0.7, seed=4, extra=brighter, n=M)
    for img in (early_img, late_img):
        img[41:47, 41:47] = np.nan  # saturated core
    early = coadd([frame("e", 2, 60900.0, early_img)])
    late = coadd([frame("l", 2, 61270.0, late_img)])
    d = difference(late, early)
    assert 26 <= halo_radius(early.data) <= 30 and d.target_exclude_px == pytest.approx(1.2 * halo_radius(early.data))
    assert d.scale.fitted and d.scale.n_stars == len(FAR_STARS) and d.scale.scale == pytest.approx(0.7, rel=0.02)
    for x, y, _ in FAR_STARS:
        assert abs(d.data[y, x]) < 0.5  # static field stars cancel (peaks 20-35 after scaling)
    assert d.data[40, 47] > 50  # the brightening halo survives
    # the old fit (13-px circle, global sky) and the local sky alone both follow the variable halo
    e, la = early.data.astype(np.float64), late.data.astype(np.float64)
    assert star_flux_scale(la, e, 0.05, exclude=(C, C, 13.2), sky_annulus=None).scale > 0.9
    assert star_flux_scale(la, e, 0.05, exclude=(C, C, 13.2)).scale > 0.75


def test_target_exclusion_follows_the_halo_within_its_limits():
    faint = scene(FAR_STARS + HALO_STARS, seed=5, extra=[(C, C, 30.0)], n=M)
    assert target_exclusion(faint) == (C, C, 8.0)  # point-like target: the 8-px minimum
    wide = scene(seed=6, extra=[(23.5, 23.5, 1000.0, 5.0)])  # 1.2 x its halo radius would pass 45% of the grid
    assert 1.2 * halo_radius(wide) > 0.45 * N and target_exclusion(wide)[2] == pytest.approx(0.45 * N)


def test_a_moving_star_becomes_a_dipole_and_a_variable_a_monopole():
    early = coadd([frame("e", 1, 60900.0, scene(seed=3, extra=[(22, 26, 80.0), (30, 34, 40.0)]))])
    late = coadd([frame("l", 1, 61270.0, scene(scale=0.8, seed=4, extra=[(22, 25, 64.0), (30, 34, 64.0)]))])
    # the mover went 1 px north (smaller y) and kept its colour; the star at (30, 34) brightened
    d = difference(late, early)
    assert d.scale.scale == pytest.approx(0.8, rel=0.03)
    assert d.data[25, 22] > 10 and d.data[27, 22] < -10  # dipole: + where it is now, - where it was
    assert d.data[34, 30] > 10 and d.data[34, 30] > 5 * abs(d.data[34, 27])  # brightening: same-sign peak
    assert d.variance[0, 0] == pytest.approx(0.0025 + d.scale.scale**2 * 0.0025)


def test_too_few_field_stars_falls_back_to_one_with_a_note():
    early = coadd([frame("e", 4, 60900.0, scene(stars=STARS[:2], seed=5))])
    late = coadd([frame("l", 4, 61270.0, scene(stars=STARS[:2], scale=0.5, seed=6))])
    d = difference(late, early)
    assert not d.scale.fitted and d.scale.scale == 1.0
    assert "not fitted" in d.notes[0] and "8-px circle" in d.notes[0]


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


def test_diverging_colours_and_checkered_no_data():
    rgba = diverging_rgba(np.array([[0.0, 5.0, -5.0, np.nan]]), limit=5.0)
    zero, pos, neg, nodata = rgba[0]
    assert tuple(zero[:3]) == (0, 0, 0) and zero[3] == 255
    assert pos[0] > pos[2] and pos[0] == 255  # orange: brighter now
    assert neg[2] > neg[0] and neg[2] == 255  # cyan: brighter before
    assert nodata[3] == 255 and nodata[0] == nodata[1] == nodata[2] >= 70  # grey checker, not "no change"


def test_difference_limit_saturates_the_dipole_not_the_noise():
    early = coadd([frame("e", 1, 60900.0, scene(seed=7, extra=[(22, 26, 80.0)]))])
    late = coadd([frame("l", 1, 61270.0, scene(seed=8, extra=[(22, 25, 80.0)]))])
    d = difference(late, early)
    limit = difference_limit(d)
    assert 10 * 0.05 < limit <= np.nanmax(np.abs(d.data))
    rgba = diverging_rgba(d.data, limit)
    assert rgba[25, 22, 0] > 200 and rgba[0, 0, :3].max() < 60  # bright dipole, dark sky


def _field(frames_meta, built_at=datetime(2026, 11, 14, tzinfo=UTC)):
    size = (N - 0.5) * 6.15 / 3600
    grid = make_grid(RA0, DEC0, size)
    assert grid.width_px == N
    return SkyField(
        id="cmp-field",
        name="Compare",
        center=SkyCoord(ra=RA0, dec=DEC0),
        size_deg=size,
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
        provenance=Provenance(pipeline_version="t", built_at=built_at, synthetic=False),
    )


def _loader(refs):
    return [frame(f"{r.obs_id}D{r.detector}", r.detector, r.mjd, scene(seed=i)) for i, r in enumerate(refs)]


def test_compare_field_writes_products_and_strict_json(tmp_path):
    fld = _field([("A", 2, 60908.0), ("B", 2, 60910.0), ("C", 2, 61116.0), ("D", 5, 60908.0), ("E", 5, 61116.0)])
    (tmp_path / "compare").mkdir()
    (tmp_path / "compare" / "diff_D9_S3-S0.png").write_bytes(b"stale")
    meta = compare_field(fld, tmp_path, _loader)
    assert not (tmp_path / "compare" / "diff_D9_S3-S0.png").exists()  # stale products are removed
    assert [c["id"] for c in meta["coadds"]] == ["D2_S0", "D2_S1", "D5_S0", "D5_S1"]
    assert meta["coadds"][0]["frame_ids"] == ["AD2", "BD2"] and meta["coadds"][0]["n_frames"] == 2
    assert [d["id"] for d in meta["differences"]] == ["D2_S1-S0", "D5_S1-S0"]
    assert meta["differences"][0]["flux_scale_fitted"] is True
    assert meta["differences"][0]["target_exclude_px"] == 8.0  # no halo in these scenes
    assert meta["field_frame_ids"] == [f.id for f in fld.frames]
    assert "not part of the data contract" in meta["format"] and meta["limitations"]

    def no_nan(token):
        raise AssertionError(f"non-standard JSON token {token}")

    on_disk = json.loads((tmp_path / "compare" / "compare.json").read_text(), parse_constant=no_nan)
    assert on_disk["field_id"] == "cmp-field"
    png = Image.open(tmp_path / meta["differences"][0]["image"])
    assert png.mode == "RGBA" and png.size == (N, N)


def test_seasons_without_overlap_are_skipped_not_written_as_nan(tmp_path):
    fld = _field([("A", 2, 60908.0), ("B", 2, 61116.0)])
    left = np.zeros((N, N), bool)
    left[:, N // 2 :] = True

    def load(refs):
        return [
            frame("AD2", 2, refs[0].mjd, np.where(left, np.nan, scene(seed=1)).astype(np.float32)),
            frame("BD2", 2, refs[1].mjd, np.where(~left, np.nan, scene(seed=2)).astype(np.float32)),
        ]

    meta = compare_field(fld, tmp_path, load)
    assert meta["differences"] == [] and meta["skipped"][0]["id"] == "D2_S1-S0"

    def no_nan(token):
        raise AssertionError(f"non-standard JSON token {token}")

    json.loads((tmp_path / "compare" / "compare.json").read_text(), parse_constant=no_nan)


def test_compare_field_needs_at_least_one_loaded_frame(tmp_path):
    with pytest.raises(ValueError, match="could be loaded"):
        compare_field(_field([("A", 1, 60908.0)]), tmp_path, lambda refs: [None for _ in refs])


def test_reproject_variance_lands_on_the_same_pixel_as_the_data():
    img = fake_image(stars=())
    x, y = (int(round(float(v))) for v in img.wcs.all_world2pix(RA0, DEC0, 0))
    img.variance[:] = 0.04
    img.variance[y, x] = 400.0  # one noisy pixel, at the position of a data spike
    img.data[y, x] += 1000.0
    grid = make_grid(RA0, DEC0, 0.05)
    data, _ = reproject_to_grid(img, grid, repair_display=False)
    var = reproject_variance(img, grid)
    assert np.unravel_index(np.nanargmax(var), var.shape) == np.unravel_index(np.nanargmax(data), data.shape)
    ex, ey = (int(round(float(v))) for v in sky_to_png_xy(grid, RA0 + 0.003, DEC0 + 0.003))
    assert 0.04 / 4 - 1e-6 <= var[ey, ex] <= 0.04 + 1e-6  # interpolated value: at most the native variance


def test_load_from_cutouts_uses_the_build_cutout_size_and_keeps_variance(monkeypatch):
    fld = _field([("OBS1", 1, 60908.0), ("OBS2", 1, 61116.0)])
    calls = {}

    def fetch(refs, ra, dec, size_arcmin):
        calls.update(ra=ra, dec=dec, size=size_arcmin, n=len(refs))
        return [Path(f"{r.obs_id}.fits") if r.obs_id == "OBS1" else None for r in refs]

    monkeypatch.setattr(cutouts, "fetch_cutouts", fetch)
    monkeypatch.setattr(fits_io, "read_spherex", lambda path: fake_image(stars=()))
    refs = [
        FrameRef(obs_id=f.obs_id, detector=f.detector, mjd=f.mjd, release="dr1", irsa_uri=f.source_uri)
        for f in fld.frames
    ]
    out = load_from_cutouts(fld)(refs)
    assert calls == {"ra": RA0, "dec": DEC0, "size": pytest.approx(fld.size_deg * 90), "n": 2}
    assert out[1] is None and out[0].frame_id == "OBS1D1" and out[0].variance is not None
    assert out[0].data.shape == (fld.grid.height_px, fld.grid.width_px)


def test_cli_compare_errors_and_success(monkeypatch, tmp_path, capsys):
    assert main(["compare", "missing", "--dir", str(tmp_path)]) == 2
    store = ProductStore(tmp_path)
    store.write_field(_field([("A", 2, 60908.0), ("B", 2, 61116.0)]))
    monkeypatch.setattr(compare_mod, "load_from_cutouts", lambda f: _loader)
    assert main(["compare", "cmp-field", "--dir", str(tmp_path)]) == 0
    assert "1 differences" in capsys.readouterr().out

    def not_ready(f):
        def load(refs):
            raise NotImplementedError("WS1: fetch_cutouts")

        return load

    monkeypatch.setattr(compare_mod, "load_from_cutouts", not_ready)
    assert main(["compare", "cmp-field", "--dir", str(tmp_path)]) == 3


def test_detect_static_sky_honours_bad_and_residuals_fit_on_stars():
    stack = np.stack([scene(seed=s) for s in range(5)])
    clean = static_sky(stack)[10, 10]
    bad = np.zeros(stack.shape, bool)
    stack[:3, 10, 10] = 1e6  # a majority of frames corrupted at one pixel...
    bad[:3, 10, 10] = True  # ...and flagged
    assert static_sky(stack, bad)[10, 10] == pytest.approx(clean, abs=0.2)
    assert static_sky(stack)[10, 10] > 1e5  # ignoring the flags would fail
    bad[:, 20, 20] = True
    assert np.isnan(static_sky(stack, bad)[20, 20])
    with pytest.raises(ValueError):
        static_sky(stack[0])
    template = static_sky(stack)
    frame_ = scene(scale=0.7, sky=5.0, seed=9, extra=[(23, 23, 50.0)])  # pedestal + new source + wavelength
    assert fit_scale(frame_, template) == pytest.approx(0.7, rel=0.03)
    res = residuals(frame_, template)
    assert res[23, 23] > 40 and abs(res[40, 40]) < 1.0  # new source survives, stars and pedestal cancel
