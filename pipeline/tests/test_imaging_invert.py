"""WS2-8: inverting the published 8-bit display mapping (imaging/invert.py)."""

import inspect

import numpy as np
import pytest

from errante.imaging import invert, render
from errante.models import Stretch

GREYS = np.arange(256, dtype=np.uint8)


def test_softening_matches_the_renderer_default():
    assert inspect.signature(render.to_uint8).parameters["softening"].default == invert.SOFTENING


@pytest.mark.parametrize("method", ["asinh", "linear", "log"])
@pytest.mark.parametrize("highlight", [None, 60.0])
def test_every_grey_level_round_trips_through_to_uint8(method, highlight):
    stretch = Stretch(vmin=-0.2, vmax=7.0, method=method)
    values = invert.grey_to_value(GREYS.astype(float), stretch, highlight)
    assert np.array_equal(render.to_uint8(values, stretch, highlight=highlight), GREYS)


@pytest.mark.parametrize("highlight", [None, 25.0])
def test_the_truth_lies_inside_its_grey_level_whose_width_is_the_step(highlight):
    stretch = Stretch(vmin=0.0, vmax=5.0)
    truth = np.geomspace(0.01, 30.0, 400).reshape(20, 20)
    grey = render.to_uint8(truth, stretch, highlight=highlight)
    dec = invert.decode(grey, stretch, highlight)
    inside = ~dec.high_clip & ~dec.low_clip
    lower = invert.grey_to_value(grey - 0.5, stretch, highlight)
    upper = invert.grey_to_value(grey + 0.5, stretch, highlight)
    assert inside.sum() >= 80 and dec.high_clip.any()
    assert np.all(((truth >= lower - 1e-9) & (truth <= upper + 1e-9))[inside])
    assert np.all(truth[dec.high_clip] >= lower[dec.high_clip] - 1e-9)  # white = a lower bound
    assert np.allclose(dec.step[inside], (upper - lower)[inside])


def test_clipped_pixels_are_flagged_and_hold_the_clip_bound():
    stretch = Stretch(vmin=1.0, vmax=5.0)
    grey = render.to_uint8(np.array([[-3.0, 1.0, 3.0, 50.0]]), stretch)
    dec = invert.decode(grey, stretch)
    assert dec.low_clip.tolist() == [[True, True, False, False]]
    assert dec.high_clip.tolist() == [[False, False, False, True]]
    assert dec.values[0, 0] == pytest.approx(1.0) and dec.values[0, 3] == pytest.approx(5.0)


def test_with_a_roll_off_white_means_at_least_the_roll_off_top():
    stretch = Stretch(vmin=0.0, vmax=5.0)
    grey = render.to_uint8(np.array([[6.0, 80.0]]), stretch, highlight=40.0)
    dec = invert.decode(grey, stretch, 40.0)
    assert grey[0, 0] < 255 and dec.values[0, 0] == pytest.approx(6.0, rel=0.04)
    assert dec.high_clip[0, 1] and dec.values[0, 1] == pytest.approx(40.0)


def test_transparent_pixels_decode_to_nan_and_are_never_clipped():
    stretch = Stretch(vmin=0.0, vmax=1.0)
    grey = np.array([[0, 255]], dtype=np.uint8)
    dec = invert.decode(grey, stretch, nodata=np.array([[True, True]]))
    assert np.isnan(dec.values).all() and not dec.low_clip.any() and not dec.high_clip.any()


def test_bad_inputs_raise():
    with pytest.raises(ValueError, match="vmax > vmin"):
        invert.grey_to_value(10.0, Stretch(vmin=1.0, vmax=1.0))
    with pytest.raises(ValueError, match="2-D"):
        invert.decode(np.zeros((2, 2, 2), np.uint8), Stretch(vmin=0.0, vmax=1.0))
    with pytest.raises(ValueError, match="nodata mask shape"):
        invert.decode(np.zeros((2, 2), np.uint8), Stretch(vmin=0.0, vmax=1.0), nodata=np.zeros((3, 3), bool))
