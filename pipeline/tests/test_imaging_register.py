"""WS2: per-frame registration check (imaging/register.py) and its use in build_field."""

import dataclasses
from types import SimpleNamespace

import numpy as np
import pytest
from test_build_robust import SEASON_0, SEASON_1, install_archive, noisy, note
from test_build_selection import ref
from test_imaging_reproject import DEC0, PIXEL_DEG, RA0, fake_image

from errante import build
from errante.build import FieldConfig, build_field
from errante.imaging import color, register

SHAPE = (60, 60)
CENTRE = (29.5, 29.5)
# (x, y, amplitude) of the field stars on the grid; the target sits at the centre and is left out.
FIELD_STARS = [(12.3, 14.6, 300.0), (45.1, 12.2, 250.0), (16.8, 44.4, 280.0), (47.6, 46.9, 260.0), (30.2, 9.7, 220.0),
               (9.5, 30.4, 240.0), (50.3, 29.1, 230.0), (29.4, 51.2, 210.0)]  # fmt: skip


def star_field(seed: int, shift=(0.0, 0.0), target=CENTRE, stars=FIELD_STARS, noise=1.0, psf=0.6) -> np.ndarray:
    rng = np.random.default_rng(seed)
    yy, xx = np.mgrid[0 : SHAPE[0], 0 : SHAPE[1]]
    img = 10.0 + rng.normal(0.0, noise, SHAPE)
    sources = [(x + shift[0], y + shift[1], amp) for x, y, amp in stars] + [(*target, 400.0)]
    for x, y, amp in sources:
        img += amp * np.exp(-((xx - x) ** 2 + (yy - y) ** 2) / (2 * psf**2))
    return img


def gframe(fid: str, data: np.ndarray, detector: int = 1, bad: np.ndarray | None = None):
    return SimpleNamespace(
        frame_id=fid, detector=detector, data=data, bad=np.zeros(SHAPE, bool) if bad is None else bad
    )


def good_frames(n: int, detector: int = 1) -> list:
    return [gframe(f"f{i}", star_field(i), detector) for i in range(n)]


def test_centroid_finds_a_sub_pixel_star_position_and_needs_a_real_star():
    img = star_field(0, noise=0.01)
    cx, cy = register.centroid(img, 12, 15)
    assert cx == pytest.approx(12.3, abs=0.05) and cy == pytest.approx(14.6, abs=0.05)
    assert register.centroid(star_field(0), 22, 22, sigma=1.0) is None  # empty sky: no star above 5 sigma


def test_centroid_is_none_when_the_box_holds_a_bad_pixel_or_leaves_the_image():
    img = star_field(0)
    holed = img.copy()
    holed[15, 13] = np.nan
    assert register.centroid(holed, 12, 15) is None
    assert register.centroid(img, 1, 30) is None


@pytest.mark.parametrize("shift", [(-1.3, 0.05), (0.7, 0.0), (8.0, -3.0), (-15.0, 6.0)])
def test_a_misregistered_frame_is_flagged_from_sub_pixel_to_gross_shifts(shift):
    frames = [*good_frames(5), gframe("bad", star_field(9, shift=shift))]
    report = register.registrations(frames)
    bad = report.frames["bad"]
    assert bad.dx == pytest.approx(shift[0], abs=0.15) and bad.dy == pytest.approx(shift[1], abs=0.15)
    assert all(report.frames[f"f{i}"].offset < 0.1 for i in range(5))  # the bad frame does not move the consensus
    assert set(report.misregistered()) == {"bad"} and not report.inconsistent


def test_a_shift_below_the_threshold_is_kept():
    report = register.registrations([*good_frames(5), gframe("small", star_field(9, shift=(0.3, 0.0)))])
    assert report.frames["small"].offset == pytest.approx(0.3, abs=0.1)
    assert report.misregistered() == {}


def test_frames_of_other_detectors_count_in_the_consensus():
    frames = [
        *good_frames(3, detector=1),
        gframe("d6_ok", star_field(20), 6),
        gframe("d6_bad", star_field(21, (1.2, 0)), 6),
    ]
    report = register.registrations(frames)
    assert report.frames["d6_ok"].offset < 0.1  # only two D6 frames, judged against the D1 frames too
    assert set(report.misregistered()) == {"d6_bad"}


def test_a_split_field_is_reported_inconsistent_and_nothing_is_rejected():
    frames = [*good_frames(2), gframe("b0", star_field(7, (1.3, 0))), gframe("b1", star_field(8, (1.3, 0)))]
    report = register.registrations(frames)
    assert report.inconsistent and report.misregistered() == {}


def test_a_moving_target_at_the_centre_does_not_count_and_is_not_a_field_star():
    frames = [gframe(f"f{i}", star_field(i, target=(29.5 + 0.8 * i, 29.5))) for i in range(4)]
    report = register.registrations(frames)
    assert report.misregistered() == {} and all(r is not None and r.offset < 0.1 for r in report.frames.values())
    # With only two field stars the frames cannot be judged: the target is never used as the third star.
    two = [gframe(f"t{i}", star_field(i, target=(29.5 + 1.5 * i, 29.5), stars=FIELD_STARS[:2])) for i in range(4)]
    assert all(r is None for r in register.registrations(two).frames.values())


def test_too_few_frames_or_no_measurable_field_stars_leave_frames_unchecked():
    assert all(r is None for r in register.registrations(good_frames(2)).frames.values())
    empty = [gframe(f"e{i}", 10.0 + np.random.default_rng(i).normal(0, 1, SHAPE)) for i in range(4)]
    assert all(r is None for r in register.registrations(empty).frames.values())
    frames = good_frames(4)
    covered = np.zeros(SHAPE, bool)
    for x, y, _ in FIELD_STARS:
        covered[int(round(y)), int(round(x))] = True  # a bad pixel in every star box of one frame
    frames[0] = gframe("f0", frames[0].data, bad=covered)
    report = register.registrations(frames)
    assert report.frames["f0"] is None and all(report.frames[f"f{i}"] is not None for i in (1, 2, 3))


# --- build integration ------------------------------------------------------------------------------------


def projected(fid: str, data: np.ndarray, detector: int = 1):
    return SimpleNamespace(frame_id=fid, detector=detector, data=data, bad=np.zeros(SHAPE, bool), ref=None)


def test_later_passes_judge_only_new_and_unchecked_frames_and_count_each_frame_once():
    check = build._RegistrationCheck()
    first = [projected(f"f{i}", star_field(i)) for i in range(2)]
    assert build._drop_misregistered(first, check) == first  # 2 frames: not checkable yet
    assert check.ids("unchecked") == {"f0", "f1"}
    topup = [projected("t0", star_field(5)), projected("t1", star_field(6)), projected("tb", star_field(7, (1.3, 0)))]
    judged = {p.frame_id for p in topup} | check.ids("unchecked")
    kept = build._drop_misregistered(first + topup, check, judged, topup=True)
    assert [p.frame_id for p in kept] == ["f0", "f1", "t0", "t1"]
    assert check.ids("ok") == {"f0", "f1", "t0", "t1"} and check.ids("rejected") == {"tb"}
    assert not check.frames["f0"].topup and check.frames["tb"].topup  # f0 stays a blink candidate
    text = check.note()
    assert "2 of 2 blink candidate frame(s) and 3 of 3 J/H/Ks top-up frame(s) checked" in text
    assert "Rejected 1 misregistered frame(s)" in text and "tb (1." in text and "J/H/Ks top-up)" in text


SIZE_DEG = 0.1  # 60 px grid at 6.15"/px
SKY_STARS = [(RA0 + dx * PIXEL_DEG / np.cos(np.radians(DEC0)), DEC0 + dy * PIXEL_DEG, amp)
             for dx, dy, amp in [(-17, 14, 300.0), (15, 16, 260.0), (-14, -15, 280.0), (16, -17, 250.0),
                                 (0, 20, 220.0), (-20, 1, 240.0), (21, -2, 230.0)]]  # fmt: skip


def sky_frame(obs: str, mjd: float, seed: int, wcs_shift_px: float = 0.0, det: int = 1, lam: float = 1.0):
    """(FrameRef, image) with field stars; ``wcs_shift_px`` mis-states the WCS like the RW Aur archive file."""
    img = fake_image(stars=((RA0, DEC0, 150.0), *SKY_STARS), shape=(90, 90), rotation_deg=7 * seed, obs_id=obs,
                     mjd=mjd, detector=det, sigma_px=0.6)  # fmt: skip
    img = noisy(img, seed)
    if wcs_shift_px:
        w = img.wcs.deepcopy()
        w.wcs.crpix = w.wcs.crpix + np.array([wcs_shift_px, 0.0])
        img = dataclasses.replace(img, wcs=w)
    img.wavelength_at = lambda ra, dec, lam=lam: (lam, 0.03)
    return ref(obs, det, mjd), img


def cfg(max_frames: int) -> FieldConfig:
    return FieldConfig(id="t-field", name="T", ra=RA0, dec=DEC0, size_deg=SIZE_DEG, max_frames=max_frames)


def test_build_rejects_a_misregistered_frame_everywhere_and_says_so(monkeypatch, tmp_path):
    frames = [sky_frame(f"good{i}", 60900.0 + i, seed=i) for i in range(4)]
    frames.append(sky_frame("shifted", 60904.5, seed=5, wcs_shift_px=1.3))
    install_archive(monkeypatch, frames)
    pools = []
    real = color.write_composites
    monkeypatch.setattr(
        color,
        "write_composites",
        lambda d, final, pool: pools.append({f.frame_id for f in pool}) or real(d, final, pool),
    )
    field = build_field(cfg(5), tmp_path)

    assert "shiftedD1" not in {f.id for f in field.frames} and len(field.frames) == 4
    assert pools and "shiftedD1" not in pools[0]  # not in the false-color composites either
    assert "shiftedD1: misregistered frame: field stars 1." in note(field, "Skipped ")
    check = note(field, "Registration check: ")
    assert "5 of 5 blink candidate frame(s) checked" in check
    assert "Rejected 1 misregistered frame(s)" in check and "shiftedD1 (1." in check


def test_a_misregistered_frame_is_replaced_like_any_skipped_frame(monkeypatch, tmp_path):
    frames = [sky_frame(f"good{i}", 60900.0 + i, seed=i) for i in (0, 1, 3, 4, 5)]
    frames.append(sky_frame("shifted", 60902.6, seed=6, wcs_shift_px=1.3))  # season middle: ranked first
    _, fetched = install_archive(monkeypatch, frames)
    field = build_field(cfg(2), tmp_path)  # pool of 4 of the 6 frames
    assert "shifted" in fetched[:4] and len(fetched) == 5  # one replacement downloaded
    assert "shiftedD1" not in {f.id for f in field.frames} and len(field.frames) == 2


def test_build_keeps_every_frame_when_registration_is_consistent(monkeypatch, tmp_path):
    install_archive(monkeypatch, [sky_frame(f"good{i}", 60900.0 + i, seed=i) for i in range(4)])
    field = build_field(cfg(4), tmp_path)
    assert len(field.frames) == 4
    check = note(field, "Registration check: ")
    assert "4 of 4 blink candidate frame(s) checked" in check and "Rejected" not in check


def test_a_misregistered_jhk_topup_frame_stays_out_of_the_composites(monkeypatch, tmp_path):
    """The J exposure of season 0 is only downloaded by the J/H/Ks top-up, and its WCS is off."""
    frames = []
    for s, base in enumerate((SEASON_0, SEASON_1)):
        for k, (tag, det, lam, dt) in enumerate(
            [
                ("D1", 1, 0.9, 1),
                ("D6", 6, 4.7, 1),
                ("D2_mid", 2, 1.45, 1),
                ("D2_J", 2, 1.25, 0),
                ("D2_H", 2, 1.63, 2),
                ("D3_mid", 3, 2.0, 1),
                ("D3_K", 3, 2.17, 2),
            ]  # fmt: skip
        ):
            shift = 1.3 if (s, tag) == (0, "D2_J") else 0.0
            frames.append(sky_frame(f"S{s}_{tag}", base + dt, seed=10 * s + k, det=det, lam=lam, wcs_shift_px=shift))
    _, fetched = install_archive(monkeypatch, frames)
    pools = []
    real = color.write_composites
    monkeypatch.setattr(
        color,
        "write_composites",
        lambda d, final, pool: pools.append({f.frame_id for f in pool}) or real(d, final, pool),
    )
    field = build_field(cfg(4), tmp_path, jhk_topup=True)

    assert "S0_D2_J" in fetched  # downloaded by the top-up...
    assert "S0_D2_JD2" not in pools[0] and "S1_D2_JD2" in pools[0]  # ...but kept out of the composites
    assert sorted(c.season for c in field.composites if c.mode == "jhk") == [1]
    check = note(field, "Registration check: ")
    assert "S0_D2_JD2 (1." in check and "J/H/Ks top-up)" in check
    skipped = [n for n in field.provenance.notes if n.startswith("Skipped ")]
    assert not any("S0_D2_J" in n for n in skipped)  # not a blink candidate, so not in the Skipped list
