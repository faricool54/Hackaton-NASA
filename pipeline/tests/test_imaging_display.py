"""WS2: SNOWBALL flag, star-aware defect repair, highlight roll-off and the thumbnail detector."""

from datetime import UTC, datetime

import numpy as np
import pytest
from astropy.io import fits
from PIL import Image

from errante import build
from errante.imaging import render
from errante.imaging.flags import DEFAULT_BAD, FLAG_BITS, bad_pixel_mask, bits_from_header
from errante.imaging.reproject import display_defects, repair_for_display
from errante.models import Frame, Stretch

# --- SNOWBALL ----------------------------------------------------------------------------------------------


def test_snowball_is_bit_27_and_bad():
    assert FLAG_BITS["SNOWBALL"] == 27 and "SNOWBALL" in DEFAULT_BAD
    flags = np.array([1 << 27, 1 << FLAG_BITS["SOURCE"], 0])
    assert bad_pixel_mask(flags).tolist() == [True, False, False]
    header = fits.Header()
    header["MSKN0027"] = "SNOWBALL"  # as in the dr1 and qr3 FLAGS headers
    assert bits_from_header(header)["SNOWBALL"] == FLAG_BITS["SNOWBALL"]


def test_snowball_pixels_are_repaired_for_display():
    flags = np.zeros((5, 5), dtype=np.int32)
    flags[2, 2] = 1 << FLAG_BITS["SNOWBALL"]
    assert display_defects(flags)[2, 2]


# --- SUR_ERROR on a star -----------------------------------------------------------------------------------


def star_with_flags(core_flag: str, amp: float = 500.0) -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(0)
    yy, xx = np.mgrid[0:31, 0:31]
    img = rng.normal(0.0, 1.0, (31, 31)) + amp * np.exp(-((xx - 15) ** 2 + (yy - 15) ** 2) / (2 * 0.8**2))
    flags = np.zeros((31, 31), dtype=np.int32)
    flags[15, 15] = 1 << FLAG_BITS[core_flag]
    return img, flags


def test_sur_error_on_a_star_is_shown_as_recorded_but_stays_bad():
    img, flags = star_with_flags("SUR_ERROR")
    defects = display_defects(flags, img)
    assert not defects[15, 15]  # neighbours are PSF wings: part of the star
    fixed = repair_for_display(img, np.zeros_like(defects), defects)
    assert fixed[15, 15] == pytest.approx(img[15, 15])  # the core keeps its value (was flattened to the wings)
    assert bad_pixel_mask(flags)[15, 15]  # still never used for measurements


def test_isolated_sur_error_is_still_repaired():
    img, flags = star_with_flags("SUR_ERROR", amp=0.0)  # no star: a lone defect
    img[15, 15] = 800.0
    defects = display_defects(flags, img)
    assert defects[15, 15]
    assert repair_for_display(img, np.zeros_like(defects), defects)[15, 15] < 5.0
    assert display_defects(flags)[15, 15]  # without pixels the old rule applies


def test_other_defects_on_a_star_are_still_repaired():
    img, flags = star_with_flags("NONFUNC")
    assert display_defects(flags, img)[15, 15]  # a non-functional pixel has no valid value anywhere


# --- highlight roll-off ------------------------------------------------------------------------------------

S = Stretch(vmin=0.0, vmax=100.0, method="asinh")


def test_without_highlight_the_mapping_is_unchanged():
    img = np.array([0.0, 50.0, 100.0, 1000.0])
    assert render.to_uint8(img, S).tolist() == render.to_uint8(img, S, highlight=None).tolist()
    assert render.to_uint8(img, S)[-2:].tolist() == [255, 255]  # vmax and above clip to white


def test_highlight_rolls_off_above_vmax_instead_of_clipping():
    img = np.array([0.0, 10.0, 100.0, 300.0, 1000.0, 5000.0])
    plain = render.to_uint8(img, S).astype(int)
    rolled = render.to_uint8(img, S, highlight=1000.0).astype(int)
    assert rolled[0] == 0 and rolled[2] == round(render.HIGHLIGHT_KNEE * 255)
    assert rolled[1] == pytest.approx(render.HIGHLIGHT_KNEE * plain[1], abs=1)  # the field keeps its curve
    assert rolled[2] < rolled[3] < rolled[4] == 255 == rolled[5]  # graded up to the highlight, then white
    assert np.all(np.diff(rolled) >= 0)


def core_target(peak: float, saturated: bool = False, shape=(40, 40), seed=0):
    rng = np.random.default_rng(seed)
    yy, xx = np.indices(shape)
    img = rng.normal(0.0, 1.0, shape) + peak * np.exp(-((xx - 19.5) ** 2 + (yy - 19.5) ** 2) / (2 * 1.0**2))
    img += 60.0 * np.exp(-((xx - 6) ** 2 + (yy - 8) ** 2) / 2)  # a field star sets the bright end
    bad = np.zeros(shape, bool)
    if saturated:
        bad[np.hypot(xx - 19.5, yy - 19.5) <= 2.5] = True
    return img, bad


def test_target_highlights_only_for_an_unsaturated_target_brighter_than_the_field():
    bright = [core_target(800.0, seed=i) for i in range(3)]
    faint = [core_target(5.0, seed=i) for i in range(3)]
    saturated = [core_target(800.0, saturated=True, seed=i) for i in range(3)]
    images = [x for x, _ in bright + faint + saturated]
    bads = [b for _, b in bright + faint + saturated]
    groups = [1] * 3 + [2] * 3 + [3] * 3
    stretches = render.field_stretches(images, groups, bads)
    tops = render.target_highlights(images, groups, bads, stretches)
    assert all(t is not None and t > s.vmax for t, s in zip(tops[:3], stretches[:3], strict=True))
    assert tops[3:] == [None] * 6  # faint target: nothing to roll off; saturated core: lower bounds only


# --- thumbnail ---------------------------------------------------------------------------------------------


def frame(i: int, det: int, mjd: float) -> Frame:
    return Frame(
        id=f"f{i}D{det}",
        obs_id=f"f{i}",
        detector=det,
        mjd=mjd,
        date_obs=datetime(2025, 9, 1, tzinfo=UTC),
        release="dr1",
        image=f"frames/f{i}D{det}.png",
    )


@pytest.mark.parametrize(
    ("scores", "expected"),
    [
        ({1: (50.0, 0.5), 6: (40.0, 30.0)}, 6),  # target outshines the field in D6 (RW Aurigae-like)
        ({1: (2.0, 0.1), 6: (3.0, 0.2)}, 1),  # detected nowhere: the old season-coverage rule (D1 has more)
        ({1: (2.0, 0.1), 6: (8.0, 0.2)}, 6),  # detected only in D6 (WISE 0855-like)
    ],
)
def test_thumbnail_comes_from_the_detector_where_the_target_stands_out(tmp_path, scores, expected):
    frames = [frame(i, 1, 60900.0 + 200 * (i % 3)) for i in range(3)]
    frames += [frame(10 + i, 6, 60900.0 + 200 * i) for i in range(2)]
    for k, f in enumerate(frames):
        (tmp_path / f.image).parent.mkdir(parents=True, exist_ok=True)
        Image.fromarray(np.full((4, 4), k * 40, np.uint8)).save(tmp_path / f.image)
    det = build._write_thumbnail(tmp_path, frames, [scores[f.detector] for f in frames])
    assert det == expected
    middle = sorted((f for f in frames if f.detector == expected), key=lambda f: f.mjd)
    chosen = middle[len(middle) // 2]
    assert (tmp_path / "thumb.png").read_bytes() == (tmp_path / chosen.image).read_bytes()
