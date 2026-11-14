"""WS2-2: frames of one detector share their contrast, so the blink does not pulse."""

import numpy as np
import pytest
from PIL import Image

from errante.imaging.render import field_stretches, save_png


def sky(level: float, noise: float, seed: int, star: float = 0.0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    img = level + noise * rng.standard_normal((60, 60))
    img[30, 30] += star
    return img


def width(s) -> float:
    return s.vmax - s.vmin


def test_same_detector_gets_same_width_anchored_at_each_sky_level():
    a, b = sky(1.0, 0.1, 1, star=50), sky(1.6, 0.1, 2, star=50)
    sa, sb = field_stretches([a, b], [3, 3])
    assert width(sa) == pytest.approx(width(sb))
    assert sb.vmin - sa.vmin == pytest.approx(0.6, abs=0.03)  # follows the sky offset
    assert sa.unit == "MJy/sr" and sa.method == "asinh"


def test_a_brighter_epoch_still_looks_brighter():
    faint, bright = sky(1.0, 0.1, 3, star=20), sky(1.0, 0.1, 4, star=60)
    sf, sb = field_stretches([faint, bright], [5, 5])
    assert width(sf) == pytest.approx(width(sb))
    # same mapping -> the star value sits higher in the bright epoch's range
    assert (bright[30, 30] - sb.vmin) / width(sb) > (faint[30, 30] - sf.vmin) / width(sf)


def test_detectors_are_stretched_independently_and_empty_frames_do_not_crash():
    quiet, noisy = sky(0.5, 0.05, 5), sky(0.5, 0.5, 6)
    empty = np.full((60, 60), np.nan)
    sq, sn, se = field_stretches([quiet, noisy, empty], [1, 4, 4])
    assert width(sn) > 5 * width(sq)
    assert (se.vmin, se.vmax) == (0.0, 1.0)


def test_bad_pixels_do_not_set_the_contrast():
    """Real case: Barnard's filled saturated core pushed every other star to near black."""
    a = sky(1.0, 0.1, 7)
    a[18:24, 18:24] = 5000.0  # filled core (36 px > the top 0.5 %), flagged bad
    a[40, 40] += 20.0  # a normal star
    bad = np.zeros_like(a, dtype=bool)
    bad[18:24, 18:24] = True
    (with_mask,) = field_stretches([a], [1], [bad])
    (without,) = field_stretches([a], [1])
    assert with_mask.vmax < 100 < without.vmax
    assert (a[40, 40] - with_mask.vmin) / width(with_mask) > 0.2  # the star is clearly visible


def test_no_data_is_transparent_not_black(tmp_path):
    img = sky(1.0, 0.1, 8)
    img[:10] = np.nan  # strip outside the cutout
    (s,) = field_stretches([img], [2])
    save_png(img, tmp_path / "a.png", s)
    png = Image.open(tmp_path / "a.png")
    assert png.mode == "LA"
    alpha = np.asarray(png)[..., 1]
    assert (alpha[:10] == 0).all() and (alpha[10:] == 255).all()
    save_png(sky(1.0, 0.1, 9), tmp_path / "b.png", s)
    assert Image.open(tmp_path / "b.png").mode == "L"  # complete frames stay plain grey


def test_lengths_must_match():
    with pytest.raises(ValueError):
        field_stretches([np.zeros((2, 2))], [1, 2])
