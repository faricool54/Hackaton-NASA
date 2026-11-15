"""WS2: SNOWBALL flag, star-aware defect repair, highlight roll-off and the thumbnail detector."""

from datetime import UTC, datetime

import numpy as np
import pytest
from astropy.io import fits
from PIL import Image
from test_build_robust import install_archive, noisy, note
from test_build_selection import ref
from test_imaging_reproject import DEC0, PIXEL_DEG, RA0, fake_image

from errante import build
from errante.build import FieldConfig, build_field
from errante.imaging import render
from errante.imaging.flags import DEFAULT_BAD, FLAG_BITS, bad_pixel_mask, bits_from_header
from errante.imaging.grid import make_grid
from errante.imaging.reproject import display_defects, repair_for_display, reproject_to_grid
from errante.models import Frame, Stretch
from errante.products import ProductStore

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


def scene(amp: float = 500.0, plateau: float = 0.0, size: int = 41) -> np.ndarray:
    """Unit-noise sky, an optional flat halo plateau, and a star of peak ``amp`` at the centre."""
    rng = np.random.default_rng(0)
    yy, xx = np.mgrid[0:size, 0:size]
    c = size // 2
    img = rng.normal(0.0, 1.0, (size, size)) + amp * np.exp(-((xx - c) ** 2 + (yy - c) ** 2) / (2 * 0.8**2))
    img[np.hypot(xx - c, yy - c) < 12] += plateau
    return img


def flagged(shape, pixels, name: str = "SUR_ERROR") -> np.ndarray:
    flags = np.zeros(shape, dtype=np.int32)
    for y, x in pixels:
        flags[y, x] = 1 << FLAG_BITS[name]
    return flags


def test_sur_error_on_a_star_core_is_shown_as_recorded_but_stays_bad():
    img = scene()
    flags = flagged(img.shape, [(20, 20)])
    defects = display_defects(flags, img)
    assert not defects[20, 20]  # its neighbours are the star's wings
    fixed = repair_for_display(img, np.zeros_like(defects), defects)
    assert fixed[20, 20] == pytest.approx(img[20, 20])  # was flattened to the wings before
    assert bad_pixel_mask(flags)[20, 20]  # still never used for measurements


def test_isolated_sur_error_is_still_repaired():
    img = scene(amp=0.0)
    img[20, 20] = 800.0
    flags = flagged(img.shape, [(20, 20)])
    assert display_defects(flags, img)[20, 20]
    assert display_defects(flags)[20, 20]  # without pixels the old rule applies


def test_a_cosmic_ray_next_to_a_faint_star_is_repaired():
    img = scene(amp=40.0)
    block = [(20, 22), (20, 23), (21, 22), (21, 23)]  # 2x2 hit beside the star, ~10x its peak
    for y, x in block:
        img[y, x] += 400.0
    defects = display_defects(flagged(img.shape, block), img)
    assert all(defects[y, x] for y, x in block)


def test_a_cosmic_ray_on_a_halo_plateau_is_repaired():
    img = scene(amp=0.0, plateau=6.0)  # a raised halo, no star under the hit
    block = [(25, 25), (25, 26), (26, 25), (26, 26)]
    for y, x in block:
        img[y, x] += 300.0
    defects = display_defects(flagged(img.shape, block), img)
    assert all(defects[y, x] for y, x in block)


def test_other_defects_on_a_star_are_still_repaired():
    img = scene()
    assert display_defects(flagged(img.shape, [(20, 20)], "NONFUNC"), img)[20, 20]


def test_reprojection_keeps_a_star_core_flagged_sur_error():
    shape = (60, 60)
    clean = fake_image(stars=((RA0, DEC0, 500.0),), shape=shape, sigma_px=0.8)
    grid = make_grid(RA0, DEC0, 0.05)
    reference, _ = reproject_to_grid(clean, grid)
    x, y = (int(round(float(v))) for v in clean.wcs.all_world2pix(RA0, DEC0, 0))
    flags = np.zeros(shape, dtype=np.int32)
    flags[y, x] = 1 << FLAG_BITS["SUR_ERROR"]
    data, bad = reproject_to_grid(fake_image(stars=((RA0, DEC0, 500.0),), shape=shape, sigma_px=0.8, flags=flags), grid)
    assert np.nanmax(data) == pytest.approx(np.nanmax(reference), rel=0.02)  # the core is not flattened
    my, mx = np.unravel_index(np.nanargmax(data), data.shape)
    assert bad[my - 1 : my + 2, mx - 1 : mx + 2].any()  # and is still reported as bad


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
    assert rolled[0] == 0 and rolled[2] == 217  # vmax -> 85 % grey
    assert rolled[1] == pytest.approx(0.85 * plain[1], abs=1)  # the field keeps its curve, 15 % dimmer
    assert rolled[2] < rolled[3] < rolled[4] == 255 == rolled[5]  # graded up to the highlight, then white
    assert np.all(np.diff(rolled) >= 0)


def core_target(peak: float, bad_fraction: float = 0.0, shape=(40, 40), seed=0, sky: float = 0.0):
    rng = np.random.default_rng(seed)
    yy, xx = np.indices(shape)
    r = np.hypot(xx - 19.5, yy - 19.5)
    img = sky + rng.normal(0.0, 1.0, shape) + peak * np.exp(-(r**2) / (2 * 1.0**2))
    img += 60.0 * np.exp(-((xx - 6) ** 2 + (yy - 8) ** 2) / 2)  # a field star sets the bright end
    bad = np.zeros(shape, bool)
    core = np.argwhere(r <= render.TARGET_RADIUS_PX)
    for y, x in core[: int(round(bad_fraction * len(core)))]:
        bad[y, x] = True
    return img, bad


def highlights(frames):
    images, bads = [x for x, _ in frames], [b for _, b in frames]
    groups = [1] * len(frames)
    stretches = render.field_stretches(images, groups, bads)
    return render.target_highlights(images, groups, bads, stretches), stretches


def test_a_clean_bright_target_gets_a_roll_off_that_clips_in_no_frame():
    peaks, skies = [600.0, 900.0, 1200.0], [0.0, 3.0, -2.0]
    frames = [core_target(p, seed=i, sky=s) for i, (p, s) in enumerate(zip(peaks, skies, strict=True))]
    tops, stretches = highlights(frames)
    for (img, _), top, s in zip(frames, tops, stretches, strict=True):
        assert top is not None and top > s.vmax
        assert top >= np.max(img[render._core(img.shape)]) - 1e-6  # the brightest core pixel is graded


@pytest.mark.parametrize("bad_fraction", [0.3, 0.7, 1.0])
def test_a_flagged_core_gets_no_roll_off_even_if_its_clean_pixels_are_bright(bad_fraction):
    tops, _ = highlights([core_target(800.0, bad_fraction, seed=i) for i in range(3)])  # RW Aur D2-D6 like
    assert tops == [None] * 3


def test_a_faint_target_gets_no_roll_off():
    tops, _ = highlights([core_target(5.0, seed=i) for i in range(3)])
    assert tops == [None] * 3


def test_one_odd_frame_does_not_trigger_a_roll_off_for_its_detector():
    tops, _ = highlights([core_target(5.0, seed=i) for i in range(4)] + [core_target(900.0, seed=9)])
    assert tops == [None] * 5


def test_the_roll_off_top_ignores_an_outlier_peak():
    tops, stretches = highlights([core_target(300.0, seed=i) for i in range(4)] + [core_target(5000.0, seed=9)])
    assert all(t is not None and t > s.vmax for t, s in zip(tops, stretches, strict=True))
    assert max(tops) < 4.0 * 300.0 + 10.0  # capped near 4 x the median peak, not 5000


def test_target_scores_measure_detection_and_prominence():
    bright, faint = core_target(800.0), core_target(0.0)
    stretches = render.field_stretches([bright[0], faint[0]], [1, 2], [bright[1], faint[1]])
    (snr_b, prom_b), (snr_f, prom_f) = render.target_scores([bright[0], faint[0]], [bright[1], faint[1]], stretches)
    assert snr_b > 100 and prom_b > 1.0
    assert snr_f < build.THUMB_MIN_SNR and prom_f < 1.0


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
        ({1: (50.0, 0.5), 6: (40.0, 30.0)}, 6),  # the target outshines the field in D6 only (RW Aurigae-like)
        ({1: (50.0, 3.0), 6: (40.0, 30.0)}, 6),  # it outshines it in both: the most prominent wins
        ({1: (2.0, 0.1), 6: (3.0, 0.2)}, 1),  # never detected: the season-coverage rule (D1 covers more)
        ({1: (22.0, 0.3), 6: (8.0, 0.2)}, 1),  # detected but never dominant (WISE 0855-like): coverage rule
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


# --- build integration -------------------------------------------------------------------------------------

FIELD = [(dx, dy, 120.0) for dx, dy in [(-17, 14), (15, 16), (-14, -15), (16, -17), (0, 20), (-20, 1), (21, -2)]]


def bright_target_frame(obs: str, mjd: float, seed: int, target: float):
    stars = [(RA0, DEC0, target)] + [
        (RA0 + dx * PIXEL_DEG / np.cos(np.radians(DEC0)), DEC0 + dy * PIXEL_DEG, amp) for dx, dy, amp in FIELD
    ]
    img = noisy(fake_image(stars=stars, shape=(90, 90), rotation_deg=7 * seed, obs_id=obs, mjd=mjd), seed)
    img.wavelength_at = lambda ra, dec: (1.0, 0.03)
    return ref(obs, 1, mjd), img


def test_build_rolls_off_a_bright_clean_target_and_says_how(monkeypatch, tmp_path):
    amps = [1500.0, 2000.0, 2600.0]
    install_archive(monkeypatch, [bright_target_frame(f"t{i}", 60900.0 + i, i, a) for i, a in enumerate(amps)])
    cfg = FieldConfig(id="t-field", name="T", ra=RA0, dec=DEC0, size_deg=0.1, max_frames=3)
    field = build_field(cfg, tmp_path)

    text = note(field, "Pixel values")
    assert "Highlight roll-off" in text and "D1: white = vmax + " in text and "thumb.png is a D1 frame." in text
    fdir = ProductStore(tmp_path).field_dir("t-field")
    cores = []
    for f in sorted(field.frames, key=lambda f: f.mjd):
        with Image.open(fdir / f.image) as png:
            grey = np.asarray(png.convert("L"), dtype=int)
        cores.append(int(grey[render._core(grey.shape)].max()))
    assert 217 < cores[0] < cores[1] < 255  # the target is graded, brighter epochs look brighter
