"""WS2: honesty rules of the false-color composites (noisy channels, mixed detectors, curated caveats, units)."""

import numpy as np
import pytest
from test_imaging_color import S0, S1, by_id, gf, jhk_pool, season_frames, sky

from errante.imaging import color
from errante.imaging.color import RELATIVE_NOTE, color_balance, composite_rgb, plan_composites, write_composites
from errante.imaging.compare import GridFrame

M = 64  # a grid big enough for blank-sky apertures around the target circle
CENTRE = ((M - 1) / 2, (M - 1) / 2)
STARS = [(8, 8, 40.0), (55, 8, 25.0), (8, 55, 35.0), (55, 55, 60.0), (31, 8, 30.0), (8, 31, 45.0), (55, 31, 50.0)]


def frames(red_noise=0.5, red_target=0.0, seed=0):
    """D6 / D3 / D1 of one season; red is as noisy as ``red_noise`` and holds a target of ``red_target`` at the centre."""
    target = [(*CENTRE, red_target)] if red_target else []
    red = sky(scale=0.2, noise=red_noise, seed=seed + 1, stars=STARS, n=M, extra=target)
    return [
        gf("r", 6, S0, 4.7, red, var=red_noise**2),
        gf("g", 3, S0, 2.0, sky(scale=1.0, noise=0.05, seed=seed + 2, stars=STARS, n=M)),
        gf("b", 1, S0, 0.9, sky(scale=3.0, noise=0.1, seed=seed + 3, stars=STARS, n=M), var=0.01),
    ]


def balanced(fs):
    plan = plan_composites(fs, pool=fs)
    return plan.composites[0], color_balance(plan.composites)


def red_dominant(rgb, mask):
    r, g, b = (rgb[..., c].astype(int) for c in range(3))
    return ((r >= 64) & (r - np.maximum(g, b) >= 40) & mask).sum()


def far_from_stars(shape):
    yy, xx = np.indices(shape)
    far = np.hypot(xx - CENTRE[0], yy - CENTRE[1]) > 6
    for x, y, _ in STARS:
        far &= np.hypot(xx - x, yy - y) > 4
    return far


# --- 1. a noisy channel's speckle goes black ---------------------------------------------------------------------


def test_a_noisy_channel_gets_its_black_point_at_sky_plus_two_pixel_sigmas():
    comp, balance = balanced(frames(red_noise=0.5))
    assert balance.noise[(comp.id, "red")] > color.NOISY_FRACTION
    red = comp.channels[0].stack.data.astype(np.float64)
    vmin = balance.stretches[(comp.id, "red")].vmin
    # the pixel noise of pure white noise (0.5), measured on the coadd
    assert vmin == pytest.approx(np.median(red) + color.NOISY_BLACK_SIGMAS * 0.5, abs=0.1)


def test_raising_the_black_point_turns_red_speckle_black():
    comp, balance = balanced(frames(red_noise=0.5))
    rgb = composite_rgb(comp, balance.stretches)
    far = far_from_stars(rgb.shape[:2])
    old = dict(balance.stretches)  # the previous rule: black point ~0.3 sigma below the sky
    base_red = old[(comp.id, "red")]
    sigma = 0.5
    old[(comp.id, "red")] = base_red.model_copy(update={"vmin": np.median(comp.channels[0].stack.data) - 0.3 * sigma})
    before = red_dominant(composite_rgb(comp, old), far)
    after = red_dominant(rgb, far)
    assert before > 0.15 * far.sum()  # most of the sky was red speckle
    assert after < 0.03 * far.sum()  # only the > 2 sigma tail is left (2.3 % of pure noise)


def test_only_the_noisy_channel_changes():
    noisy_comp, noisy = balanced(frames(red_noise=0.5))
    quiet_comp, quiet = balanced(frames(red_noise=0.02))
    assert quiet.target_snr == {} and not any("noisy" in n for n in quiet.notes[quiet_comp.id])
    for c in ("green", "blue"):
        assert noisy.stretches[(noisy_comp.id, c)] == quiet.stretches[(quiet_comp.id, c)]
    assert noisy.stretches[(noisy_comp.id, "red")].vmax == pytest.approx(
        quiet.stretches[(quiet_comp.id, "red")].vmax, rel=0.05
    )


def test_the_white_point_stays_above_a_raised_black_point():
    stretch = color.Stretch(vmin=-1.0, vmax=1.0)
    raised = color._speckle_black_point(stretch, sky=0.0, sigma=2.0)
    assert raised.vmin == 4.0 and raised.vmax == 6.0  # pushed one sigma above the black point
    assert color._speckle_black_point(stretch, sky=0.0, sigma=0.1).vmax == 1.0  # normally kept


def test_an_undetected_target_in_a_noisy_channel_is_said_not_to_be_visible():
    comp, balance = balanced(frames(red_noise=0.5, red_target=0.0))
    snr = balance.target_snr[(comp.id, "red")]
    assert snr is not None and snr < color.TARGET_MIN_SNR
    notes = [n for n in balance.notes[comp.id] if n.startswith("The target is not detected")]
    assert notes == [
        f"The target is not detected in the red channel (D6 aperture S/N {snr:.1f} at the field centre, below 3): "
        "it cannot be seen in this single-season D6 coadd, and red specks near the centre are noise."
    ]


def test_a_detected_target_in_a_noisy_channel_gets_no_such_note_and_stays_red():
    comp, balance = balanced(frames(red_noise=0.5, red_target=10.0))
    assert balance.target_snr[(comp.id, "red")] > 10
    assert not any(n.startswith("The target is not detected") for n in balance.notes[comp.id])
    assert any("noisy" in n for n in balance.notes[comp.id])  # the channel is still noisy
    r, g, b = composite_rgb(comp, balance.stretches)[32, 32, :3].astype(int)
    assert r > 150 and r > 2 * max(g, b)


def test_a_target_core_without_data_is_not_called_undetected():
    fs = frames(red_noise=0.5)
    core = np.zeros((M, M), bool)
    core[30:34, 30:34] = True  # saturated core: bad in the only red frame
    fs[0] = GridFrame("r", 6, S0, fs[0].data, core, fs[0].variance, 4.7)
    comp, balance = balanced(fs)
    assert balance.target_snr[(comp.id, "red")] is None
    assert not any(n.startswith("The target is not detected") for n in balance.notes[comp.id])


# --- 2. seasons with different detectors -------------------------------------------------------------------------


def test_detector_composites_say_when_seasons_use_different_detectors():
    final = season_frames(S0) + season_frames(S1, dets=(1, 4, 5), prefix="b") + season_frames(S1 + 200, prefix="c")
    plan = plan_composites(final, pool=[*final, *jhk_pool(S0)])
    comps = by_id(plan)
    expected = (
        "Seasons use different detectors (red/green/blue = S0, S2: D6/D3/D1; S1: D5/D4/D1): colour differences "
        "between them can be instrumental (other wavelengths), so they are not evidence of a colour change of the object."
    )
    for cid in ("detectors_S0", "detectors_S1", "detectors_S2"):
        assert expected in comps[cid].notes, cid
        assert comps[cid].notes[-1] == RELATIVE_NOTE  # the balance notes still go before the closing note
    assert expected not in comps["jhk_S0"].notes


def test_seasons_with_the_same_detectors_get_no_mixed_detector_note(tmp_path):
    final = season_frames(S0) + season_frames(S1, prefix="b")
    comps, _ = write_composites(tmp_path, final, final)
    assert comps and not any("different detectors" in n for c in comps for n in c.notes)


def test_the_mixed_detector_note_reaches_the_contract_before_the_closing_note(tmp_path):
    final = season_frames(S0) + season_frames(S1, dets=(2, 3, 6), prefix="b")
    comps, _ = write_composites(tmp_path, final, final)
    for c in comps:
        i = next(i for i, n in enumerate(c.notes) if n.startswith("Seasons use different detectors"))
        assert c.notes[-1] == RELATIVE_NOTE and i < len(c.notes) - 1
        assert "S0: D6/D3/D1; S1: D6/D3/D2" in c.notes[i]


# --- 3. curated caveats follow their exposures -------------------------------------------------------------------


def test_a_curated_caveat_goes_to_every_composite_that_uses_its_exposure_and_only_there():
    flagged = "2025W40_1A_0559_1D6"
    assert flagged in color.CURATED_FRAME_CAVEATS
    s1 = [gf(flagged, 6, S1, 4.5), gf("2025W44_2B_0494_1D6", 6, S1 + 20, 4.5), *season_frames(S1, (1, 3), "b")]
    final = season_frames(S0) + s1
    comps = by_id(plan_composites(final, pool=final))
    caveat = color.CURATED_FRAME_CAVEATS[flagged]
    assert caveat.startswith("Curated caveat (checked by eye")
    assert comps["detectors_S1"].notes.count(caveat) == 1  # two flagged exposures, one caveat
    assert caveat not in comps["detectors_S0"].notes
    assert comps["detectors_S1"].notes[-1] == RELATIVE_NOTE


# --- 4. units ----------------------------------------------------------------------------------------------------


def test_user_visible_wavelengths_are_written_in_micrometres(tmp_path):
    final = season_frames(S0) + season_frames(S1, prefix="b")
    pool = [*final, *jhk_pool(S0, k=(2.27,)), *jhk_pool(S1, h=(2.0,), prefix="q")]  # S0 Ks fallback, S1 skipped
    comps, note = write_composites(tmp_path, final, pool)
    texts = [note, *(n for c in comps for n in c.notes)]
    assert not any(" um" in t for t in texts)
    assert "Full range: red = D6 4.70 µm" in " ".join(comps[0].notes)
    assert any("red (Ks 2.17 µm) uses the nearest exposure, 2.270 µm (0.100 µm away)" in t for t in texts)
    assert "no exposure within 0.12 µm of green (H 1.65 µm)" in note
    assert "within 0.06 µm of J 1.25 / H 1.65 / Ks 2.17 µm" in note
