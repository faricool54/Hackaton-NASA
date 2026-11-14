"""WS2-1: reproject_to_grid puts sources where the grid says they are (north up, east left)."""

import numpy as np
import pytest
from astropy.io import fits
from astropy.wcs import WCS, Sip

from errante.data.fits_io import SpherexImage
from errante.imaging.flags import FLAG_BITS
from errante.imaging.grid import make_grid, sky_to_png_xy
from errante.imaging.reproject import bilinear_sample, fill_saturated, reproject_to_grid

RA0, DEC0 = 269.45, 4.77
PIXEL_DEG = 6.15 / 3600


def fake_wcs(shape=(50, 70), rotation_deg=30.0, ra=RA0, dec=DEC0, sip=True) -> WCS:
    """Detector-like WCS: rotated (not north-up), TAN-SIP, centred on (ra, dec)."""
    ny, nx = shape
    w = WCS(naxis=2)
    w.wcs.ctype = ["RA---TAN-SIP", "DEC--TAN-SIP"] if sip else ["RA---TAN", "DEC--TAN"]
    w.wcs.crval = [ra, dec]
    w.wcs.crpix = [(nx + 1) / 2, (ny + 1) / 2]
    t = np.deg2rad(rotation_deg)
    w.wcs.cd = PIXEL_DEG * np.array([[-np.cos(t), np.sin(t)], [np.sin(t), np.cos(t)]])
    if sip:
        a = np.zeros((3, 3))
        b = np.zeros((3, 3))
        a[2, 0] = 4e-5  # mild distortion: ~0.1 px at the cutout edge
        b[0, 2] = -3e-5
        w.sip = Sip(a, b, None, None, w.wcs.crpix)
    w.pixel_shape = (nx, ny)
    return w


def fake_image(
    stars=((RA0, DEC0, 100.0),),
    shape=(50, 70),
    rotation_deg=30.0,
    zodi_level=5.0,
    flags=None,
    obs_id="2025W35_1A_0001_1",
    detector=1,
    mjd=60910.0,
    ra=RA0,
    dec=DEC0,
    sigma_px=1.0,
) -> SpherexImage:
    """SPHEREx-like cutout in FITS orientation with Gaussian stars at known sky positions."""
    w = fake_wcs(shape, rotation_deg, ra, dec)
    yy, xx = np.mgrid[0 : shape[0], 0 : shape[1]]
    data = np.full(shape, zodi_level, dtype=np.float32)
    for sra, sdec, amp in stars:
        x, y = w.all_world2pix(sra, sdec, 0)
        data += (amp * np.exp(-((xx - x) ** 2 + (yy - y) ** 2) / (2 * sigma_px**2))).astype(np.float32)
    return SpherexImage(
        data=data,
        flags=np.zeros(shape, dtype=np.int32) if flags is None else flags,
        variance=np.ones(shape, dtype=np.float32),
        zodi=np.full(shape, zodi_level, dtype=np.float32),
        wcs=w,
        header=fits.Header(),
        obs_id=obs_id,
        detector=detector,
        mjd=mjd,
        date_obs="2025-08-31T12:00:00",
    )


def centroid(img: np.ndarray, x: float, y: float, half: int = 4) -> tuple[float, float]:
    x0, y0 = int(round(x)), int(round(y))
    win = np.nan_to_num(img[y0 - half : y0 + half + 1, x0 - half : x0 + half + 1])
    win = np.clip(win, 0, None)
    yy, xx = np.mgrid[y0 - half : y0 + half + 1, x0 - half : x0 + half + 1]
    return float((win * xx).sum() / win.sum()), float((win * yy).sum() / win.sum())


def test_stars_land_where_the_grid_predicts_within_0_3_px():
    offset = 13 * PIXEL_DEG  # 13 px from the centre: well inside the 70x50 px cutout
    stars = (
        (RA0, DEC0, 100.0),
        (RA0 + offset / np.cos(np.deg2rad(DEC0)), DEC0, 80.0),  # east of centre
        (RA0, DEC0 + offset, 60.0),  # north of centre
    )
    img = fake_image(stars=stars)
    grid = make_grid(RA0, DEC0, 0.06)
    data, bad = reproject_to_grid(img, grid)
    assert data.shape == (grid.height_px, grid.width_px) == bad.shape
    for sra, sdec, _ in stars:
        ex, ey = sky_to_png_xy(grid, sra, sdec)
        cx, cy = centroid(data, float(ex), float(ey))
        assert cx == pytest.approx(float(ex), abs=0.3)
        assert cy == pytest.approx(float(ey), abs=0.3)
    # PNG orientation: the east star is LEFT of centre, the north star is ABOVE it.
    cx0, cy0 = sky_to_png_xy(grid, RA0, DEC0)
    east_x, _ = sky_to_png_xy(grid, *stars[1][:2])
    _, north_y = sky_to_png_xy(grid, *stars[2][:2])
    assert east_x < cx0 and north_y < cy0


def test_zodi_is_subtracted_and_units_kept():
    img = fake_image(stars=(), zodi_level=7.5)
    grid = make_grid(RA0, DEC0, 0.04)
    data, _ = reproject_to_grid(img, grid)
    assert np.nanmax(np.abs(data)) < 1e-4
    raw, _ = reproject_to_grid(img, grid, subtract_zodi=False)
    assert np.nanmedian(raw) == pytest.approx(7.5, abs=1e-4)


def test_outside_the_cutout_is_nan_and_bad():
    img = fake_image(shape=(30, 40))
    grid = make_grid(RA0, DEC0, 0.2)  # much bigger than the cutout
    data, bad = reproject_to_grid(img, grid)
    assert np.isnan(data[0, 0]) and bad[0, 0]
    assert np.isnan(data[-1, -1]) and bad[-1, -1]
    finite = np.isfinite(data)
    assert 0.0 < finite.mean() < 0.5
    assert np.array_equal(bad[finite], np.zeros(finite.sum(), dtype=bool))


def test_bad_flags_are_masked_but_source_is_not_and_data_is_kept():
    shape = (50, 70)
    flags = np.full(shape, 1 << FLAG_BITS["SOURCE"], dtype=np.int32)
    w = fake_wcs(shape)
    hx, hy = (int(round(float(v))) for v in w.all_world2pix(RA0, DEC0, 0))
    flags[hy, hx] |= 1 << FLAG_BITS["HOT"]
    img = fake_image(flags=flags)
    grid = make_grid(RA0, DEC0, 0.05)  # fully inside the rotated cutout
    data, bad = reproject_to_grid(img, grid)
    ex, ey = (int(round(float(v))) for v in sky_to_png_xy(grid, RA0, DEC0))
    assert bad[ey - 1 : ey + 2, ex - 1 : ex + 2].any()  # the HOT pixel lands near the star
    assert bad.mean() < 0.01  # SOURCE everywhere does not make the frame bad
    assert np.isfinite(data[ey, ex]) and data[ey, ex] > 10  # flagged pixels stay visible


def test_saturated_nan_core_is_shown_bright_but_stays_bad():
    """Real DR1 Barnard's Star cutouts have a NaN core flagged OVERFLOW (2026-11-14)."""
    shape = (50, 70)
    img = fake_image(shape=shape)
    x, y = (int(round(float(v))) for v in img.wcs.all_world2pix(RA0, DEC0, 0))
    img.data[y, x - 1 : x + 1] = np.nan  # 2-pixel saturated core, as in the real file
    img.flags[y, x - 1 : x + 1] = 1 << FLAG_BITS["OVERFLOW"]
    grid = make_grid(RA0, DEC0, 0.05)
    data, bad = reproject_to_grid(img, grid)
    ex, ey = (int(round(float(v))) for v in sky_to_png_xy(grid, RA0, DEC0))
    core = data[ey - 1 : ey + 2, ex - 1 : ex + 2]
    assert np.isfinite(core).all() and core.max() > 50  # bright, not a black hole
    assert bad[ey - 1 : ey + 2, ex - 1 : ex + 2].any()
    holes, _ = reproject_to_grid(img, grid, fill_saturated_cores=False)
    assert np.isnan(holes[ey - 1 : ey + 2, ex - 1 : ex + 2]).any()


def test_fill_saturated_only_touches_flagged_nans():
    px = np.array([[1.0, 2.0, 3.0], [4.0, np.nan, 6.0], [7.0, 8.0, np.nan]])
    sat = np.array([[0, 0, 0], [0, 1, 0], [0, 0, 0]], dtype=bool)
    out = fill_saturated(px, sat)
    assert out[1, 1] == 8.0  # brightest finite neighbour
    assert np.isnan(out[2, 2])  # NaN but not saturated: untouched
    assert np.isnan(px[1, 1])  # input not modified


def test_bilinear_ignores_a_nan_neighbour_with_little_weight():
    img = np.array([[1.0, 2.0], [3.0, np.nan]])
    vals = bilinear_sample(img, np.array([0.0, 0.25, 0.9]), np.array([0.0, 0.0, 0.9]))
    assert vals[0] == pytest.approx(1.0)
    assert vals[1] == pytest.approx(1.25)
    assert np.isnan(vals[2])  # mostly the NaN corner
    outside = bilinear_sample(img, np.array([-0.6, 1.6]), np.array([0.0, 0.0]))
    assert np.isnan(outside).all()
