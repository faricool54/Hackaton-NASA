import numpy as np
import pytest

from errante.data.s3 import parse_key
from errante.imaging.flags import FLAG_BITS, bad_pixel_mask, bitmask
from errante.imaging.grid import make_grid, png_xy_to_sky, sky_to_png_xy
from errante.science.motion import (
    distance_from_opposition_rate,
    motion_from_detections,
    opposition_rate_arcsec_per_hour,
)


def test_grid_roundtrip_and_orientation():
    g = make_grid(150.0, 11.0, 0.25)
    cx, cy = (g.width_px - 1) / 2, (g.height_px - 1) / 2
    ra, dec = png_xy_to_sky(g, cx, cy)
    assert ra == pytest.approx(150.0, abs=1e-6) and dec == pytest.approx(11.0, abs=1e-6)
    # north is up: smaller y -> larger dec ; east is left: smaller x -> larger ra
    _, dec_top = png_xy_to_sky(g, cx, 0)
    ra_left, _ = png_xy_to_sky(g, 0, cy)
    assert dec_top > 11.0 and ra_left > 150.0
    x, y = sky_to_png_xy(g, 150.01, 11.02)
    ra2, dec2 = png_xy_to_sky(g, x, y)
    assert ra2 == pytest.approx(150.01, abs=1e-7) and dec2 == pytest.approx(11.02, abs=1e-7)


def test_opposition_rate_known_values():
    assert opposition_rate_arcsec_per_hour(40) == pytest.approx(3.2, abs=0.1)
    assert opposition_rate_arcsec_per_hour(500) == pytest.approx(0.28, abs=0.02)
    assert distance_from_opposition_rate(3.2).au_median == pytest.approx(40, rel=0.03)


def test_motion_from_detections_pure_north():
    mjd = [0.0, 1 / 24, 2 / 24]
    dec = [10.0, 10.0 + 10 / 3600, 10.0 + 20 / 3600]  # 10"/h north
    m = motion_from_detections(mjd, [100.0] * 3, dec)
    assert m.rate_arcsec_per_hour == pytest.approx(10, rel=1e-3)
    assert m.position_angle_deg == pytest.approx(0, abs=1e-3)


def test_flags_source_bit_is_not_bad():
    flags = np.array([1 << FLAG_BITS["SOURCE"], 1 << FLAG_BITS["HOT"], 0])
    assert bad_pixel_mask(flags).tolist() == [False, True, False]
    assert bitmask(["SOURCE"]) == 2097152


def test_parse_s3_key():
    k = parse_key("dr1/level2/2025W19_2B/l2b-v27-2026-198/1/level2_2025W19_2B_0007_1D1_spx_l2b-v27-2026-198.fits")
    assert (k.release, k.week, k.obs_id, k.detector) == ("dr1", "2025W19_2B", "2025W19_2B_0007_1", 1)
    assert k.url.startswith("https://nasa-irsa-spherex.s3")
