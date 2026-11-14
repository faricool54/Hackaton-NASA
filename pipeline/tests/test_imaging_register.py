"""WS2: per-frame registration check (imaging/register.py) and its use in build_field."""

import dataclasses
from types import SimpleNamespace

import numpy as np
import pytest
from test_build_robust import install_archive, noisy, note
from test_build_selection import ref
from test_imaging_reproject import DEC0, PIXEL_DEG, RA0, fake_image

from errante.build import FieldConfig, build_field
from errante.imaging import register

SHAPE = (60, 60)
# (x, y, amplitude) of the field stars on the grid; the target sits at the centre and is left out.
FIELD_STARS = [(12.3, 14.6, 300.0), (45.1, 12.2, 250.0), (16.8, 44.4, 280.0), (47.6, 46.9, 260.0), (30.2, 9.7, 220.0),
               (9.5, 30.4, 240.0), (50.3, 29.1, 230.0), (29.4, 51.2, 210.0)]  # fmt: skip


def star_field(seed: int, shift=(0.0, 0.0), target=(29.5, 29.5), noise=1.0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    yy, xx = np.mgrid[0 : SHAPE[0], 0 : SHAPE[1]]
    img = 10.0 + rng.normal(0.0, noise, SHAPE)
    for x, y, amp in [*FIELD_STARS, (*target, 400.0)]:
        if (x, y) != target:
            x, y = x + shift[0], y + shift[1]
        img += amp * np.exp(-((xx - x) ** 2 + (yy - y) ** 2) / (2 * 0.9**2))
    return img


def gframe(fid: str, data: np.ndarray, detector: int = 1, bad: np.ndarray | None = None):
    return SimpleNamespace(
        frame_id=fid, detector=detector, data=data, bad=np.zeros(SHAPE, bool) if bad is None else bad
    )


def test_centroid_finds_a_sub_pixel_star_position():
    img = star_field(0, noise=0.01)
    cx, cy = register.centroid(img, 12, 15)
    assert cx == pytest.approx(12.3, abs=0.05) and cy == pytest.approx(14.6, abs=0.05)


def test_centroid_is_none_when_the_box_holds_a_bad_pixel_or_leaves_the_image():
    img = star_field(0)
    holed = img.copy()
    holed[15, 13] = np.nan
    assert register.centroid(holed, 12, 15) is None
    assert register.centroid(img, 1, 30) is None


def test_a_frame_shifted_like_the_rw_aurigae_wcs_error_is_flagged_and_the_others_are_not():
    frames = [gframe(f"f{i}", star_field(i)) for i in range(5)]
    frames.append(gframe("bad", star_field(9, shift=(-1.3, 0.05))))
    found = register.registrations(frames)
    assert found["bad"].dx == pytest.approx(-1.3, abs=0.15) and found["bad"].n_stars >= register.MIN_STARS
    assert all(found[f"f{i}"].offset < 0.1 for i in range(5))  # one bad frame does not move the consensus
    assert set(register.misregistered(found)) == {"bad"}


def test_a_moving_target_at_the_centre_does_not_count_as_misregistration():
    frames = [gframe(f"f{i}", star_field(i, target=(29.5 + 0.8 * i, 29.5))) for i in range(4)]
    found = register.registrations(frames)
    assert register.misregistered(found) == {}
    assert all(r is not None and r.offset < 0.1 for r in found.values())


def test_frames_are_judged_only_against_their_own_detector_and_need_enough_frames():
    frames = [gframe(f"d1_{i}", star_field(i), detector=1) for i in range(3)]
    frames += [gframe(f"d6_{i}", star_field(10 + i, shift=(1.0 * i, 0.0)), detector=6) for i in range(2)]
    found = register.registrations(frames)
    assert all(found[f"d1_{i}"] is not None for i in range(3))
    assert found["d6_0"] is None and found["d6_1"] is None  # 2 frames: no consensus a bad frame cannot pull


def test_a_frame_without_measurable_field_stars_is_not_checked():
    empty = [gframe(f"e{i}", 10.0 + np.random.default_rng(i).normal(0, 1, SHAPE)) for i in range(4)]
    assert all(r is None for r in register.registrations(empty).values())
    # bad pixels over every field star of one frame: that frame cannot be judged, the others still are
    frames = [gframe(f"f{i}", star_field(i)) for i in range(4)]
    covered = np.zeros(SHAPE, bool)
    for x, y, _ in FIELD_STARS:
        covered[int(round(y)), int(round(x))] = True
    frames[0] = gframe("f0", frames[0].data, bad=covered)
    found = register.registrations(frames)
    assert found["f0"] is None and all(found[f"f{i}"] is not None for i in (1, 2, 3))


# --- build_field integration -----------------------------------------------------------------------------

SIZE_DEG = 0.1  # 60 px grid at 6.15"/px
SKY_STARS = [(RA0 + dx * PIXEL_DEG / np.cos(np.radians(DEC0)), DEC0 + dy * PIXEL_DEG, amp)
             for dx, dy, amp in [(-17, 14, 300.0), (15, 16, 260.0), (-14, -15, 280.0), (16, -17, 250.0),
                                 (0, 20, 220.0), (-20, 1, 240.0), (21, -2, 230.0)]]  # fmt: skip


def sky_frame(obs: str, mjd: float, seed: int, wcs_shift_px: float = 0.0):
    """(FrameRef, image) with field stars; ``wcs_shift_px`` mis-states the WCS like the RW Aur archive file."""
    img = fake_image(stars=((RA0, DEC0, 150.0), *SKY_STARS), shape=(90, 90), rotation_deg=7 * seed, obs_id=obs,
                     mjd=mjd, detector=1)  # fmt: skip
    img = noisy(img, seed)
    if wcs_shift_px:
        w = img.wcs.deepcopy()
        w.wcs.crpix = w.wcs.crpix + np.array([wcs_shift_px, 0.0])
        img = dataclasses.replace(img, wcs=w)
    img.wavelength_at = lambda ra, dec: (1.0, 0.03)
    return ref(obs, 1, mjd), img


def test_build_rejects_a_misregistered_frame_and_says_so(monkeypatch, tmp_path):
    frames = [sky_frame(f"good{i}", 60900.0 + i, seed=i) for i in range(4)]
    frames.append(sky_frame("shifted", 60904.5, seed=5, wcs_shift_px=1.3))
    install_archive(monkeypatch, frames)
    cfg = FieldConfig(id="t-field", name="T", ra=RA0, dec=DEC0, size_deg=SIZE_DEG, max_frames=5)
    field = build_field(cfg, tmp_path)

    assert "shiftedD1" not in {f.id for f in field.frames} and len(field.frames) == 4
    # The 5x5 centroid box slightly underestimates a 1.3 px shift of this broad synthetic PSF (~1.1 px);
    # on the real RW Aurigae frame it measured 1.34 px, matching the Gaia check (-1.21 to -1.36 px).
    skipped = note(field, "Skipped ")
    assert "shiftedD1: misregistered frame: field stars 1." in skipped
    check = note(field, "Registration check: ")
    assert "5 of 5 candidate frame(s) checked" in check
    assert "Rejected 1 misregistered frame(s)" in check and "shiftedD1 (1." in check


def test_build_keeps_every_frame_when_registration_is_consistent(monkeypatch, tmp_path):
    install_archive(monkeypatch, [sky_frame(f"good{i}", 60900.0 + i, seed=i) for i in range(4)])
    cfg = FieldConfig(id="t-field", name="T", ra=RA0, dec=DEC0, size_deg=SIZE_DEG, max_frames=4)
    field = build_field(cfg, tmp_path)
    assert len(field.frames) == 4
    check = note(field, "Registration check: ")
    assert "4 of 4 candidate frame(s) checked" in check and "Rejected" not in check
