"""WS2-2: frames of one detector share their contrast, so the blink does not pulse."""

import numpy as np
import pytest

from errante.imaging.render import field_stretches


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


def test_lengths_must_match():
    with pytest.raises(ValueError):
        field_stretches([np.zeros((2, 2))], [1, 2])
