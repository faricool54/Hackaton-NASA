"""WS2: false-color season composites (detectors = full range, jhk = 2MASS-like) from grid frames."""

import json

import numpy as np
import pytest
from PIL import Image

from errante import settings
from errante.imaging import color
from errante.imaging.color import (
    COLOR_DIR,
    JHK_FALLBACK_UM,
    JHK_TOLERANCE_UM,
    color_balance,
    composite_rgb,
    plan_composites,
    write_composites,
)
from errante.imaging.compare import GridFrame
from errante.models import Composite, SkyField

N = 40
DEMO_FIELD = settings.REPO_ROOT / "data" / "demo" / "fields" / "demo-ecliptic" / "field.json"
S0, S1 = 60900.0, 61100.0  # two seasons, > 30 days apart
FIELD_STARS = [(6, 6, 40.0), (33, 6, 25.0), (6, 33, 35.0), (33, 33, 60.0), (20, 6, 30.0), (6, 20, 45.0)]


def sky(scale=1.0, noise=0.05, seed=0, extra=(), stars=FIELD_STARS, n=N, level=0.0):
    """Gaussian stars on an n x n grid; ``scale`` multiplies the field stars, ``extra`` (x, y, amp) is added."""
    rng = np.random.default_rng(seed)
    yy, xx = np.mgrid[0:n, 0:n]
    img = level + noise * rng.standard_normal((n, n))
    for x, y, amp in stars:
        img += scale * amp * np.exp(-((xx - x) ** 2 + (yy - y) ** 2) / 2.0)
    for x, y, amp in extra:
        img += amp * np.exp(-((xx - x) ** 2 + (yy - y) ** 2) / 2.0)
    return img.astype(np.float32)


def gf(fid, det, mjd, lam=None, data=None, bad=None, var=0.0025):
    data = sky(seed=sum(map(ord, fid))) if data is None else data
    bad = np.zeros(data.shape, bool) if bad is None else bad
    return GridFrame(fid, det, mjd, data, bad, np.full(data.shape, var, np.float32), lam)


def season_frames(mjd, dets=(1, 3, 6), prefix="a"):
    lam = {1: 0.95, 2: 1.40, 3: 2.00, 4: 3.00, 5: 4.10, 6: 4.70}
    return [gf(f"{prefix}{d}", d, mjd + 0.1 * d, lam[d]) for d in dets]


def by_id(plan):
    return {c.id: c for c in plan.composites}


def detectors_of(composite):
    return [ch.detector for ch in composite.channels]


# --- mode "detectors" (option A, full range) ----------------------------------------------------------------


def test_detector_mode_maps_d6_d3_d1_to_red_green_blue_per_season():
    final = season_frames(S0, prefix="a") + season_frames(S1, prefix="b")
    plan = plan_composites(final, pool=final)
    comps = by_id(plan)
    assert {"detectors_S0", "detectors_S1"} <= set(comps)
    assert detectors_of(comps["detectors_S0"]) == [6, 3, 1]
    assert [ch.frame_ids for ch in comps["detectors_S1"].channels] == [["b6"], ["b3"], ["b1"]]
    assert [ch.color for ch in comps["detectors_S0"].channels] == ["red", "green", "blue"]


def test_detector_mode_falls_back_to_d5_d4_d2_and_says_so():
    final = season_frames(S0, dets=(2, 4, 5))
    comp = by_id(plan_composites(final, pool=final))["detectors_S0"]
    assert detectors_of(comp) == [5, 4, 2]
    joined = " ".join(comp.notes)
    assert "red uses D5" in joined and "green uses D4" in joined and "blue uses D2" in joined


def test_detector_mode_prefers_the_main_detector_over_its_fallback():
    final = season_frames(S0, dets=(1, 2, 3, 4, 5, 6))
    comp = by_id(plan_composites(final, pool=final))["detectors_S0"]
    assert detectors_of(comp) == [6, 3, 1]
    assert not any("uses D" in n for n in comp.notes)


def test_detector_mode_only_uses_final_frames_not_the_pool():
    final = season_frames(S0)
    extra = gf("pool6", 6, S0 + 0.3, 4.75)
    comp = by_id(plan_composites(final, pool=[*final, extra]))["detectors_S0"]
    assert comp.channels[0].frame_ids == ["a6"]


def test_a_season_without_a_red_detector_has_no_detector_composite_and_says_why():
    final = season_frames(S0) + season_frames(S1, dets=(1, 3), prefix="b")
    plan = plan_composites(final, pool=final)
    assert "detectors_S1" not in by_id(plan)
    assert any(s.startswith("detectors S1: ") and "red" in s and "D6" in s and "D5" in s for s in plan.skipped)


def test_frames_without_any_usable_pixel_do_not_make_a_channel():
    dead = gf("dead1", 1, S0, 0.95, bad=np.ones((N, N), bool))
    final = [dead, gf("a2", 2, S0, 1.4), *season_frames(S0, dets=(3, 6))]
    comp = by_id(plan_composites(final, pool=final))["detectors_S0"]
    assert comp.channels[2].detector == 2  # D1 had nothing usable: fallback D2


def test_channel_metadata_has_mean_min_max_wavelength_and_mjd_range():
    final = [gf("x1", 1, S0, 0.90), gf("y1", 1, S0 + 2, 1.00), *season_frames(S0, dets=(3, 6))]
    plan = plan_composites(final, pool=final)
    comp = by_id(plan)["detectors_S0"]
    blue = comp.channels[2]
    assert blue.frame_ids == ["x1", "y1"]
    assert blue.wavelength_um == pytest.approx(0.95)
    assert (blue.wavelength_min_um, blue.wavelength_max_um) == (pytest.approx(0.90), pytest.approx(1.00))
    assert comp.mjd_min == pytest.approx(S0) and comp.mjd_max == pytest.approx(S0 + 2)


def test_channel_mean_wavelength_stays_within_its_range_despite_rounding():
    # np.mean([0.7] * 3) == 0.6999999999999998 < 0.7: the contract would reject the channel (mean outside [min, max])
    final = [gf(f"x{i}", 1, S0 + i, 0.7) for i in range(3)] + season_frames(S0, dets=(3, 6))
    blue = by_id(plan_composites(final, pool=final))["detectors_S0"].channels[2]
    assert blue.wavelength_min_um <= blue.wavelength_um <= blue.wavelength_max_um
    assert blue.wavelength_um == 0.7


# --- mode "jhk" (option B, 2MASS-like) -------------------------------------------------------------------------


def jhk_pool(mjd, j=(1.25,), h=(1.65,), k=(2.17,), prefix="p"):
    frames = []
    for band, lams in (("j", j), ("h", h), ("k", k)):
        for i, lam in enumerate(lams):
            det = 2 if lam < 1.64 else 3
            frames.append(gf(f"{prefix}{band}{i}", det, mjd + 0.01 * len(frames), lam))
    return frames


def test_jhk_coadds_every_pool_exposure_within_the_tolerance():
    final = season_frames(S0)
    t = JHK_TOLERANCE_UM
    pool = jhk_pool(S0, j=(1.25 - t + 0.005, 1.25 + t - 0.005, 1.25 + t + 0.01))
    comp = by_id(plan_composites(final, pool=[*final, *pool]))["jhk_S0"]
    red, green, blue = comp.channels
    assert blue.frame_ids == ["pj0", "pj1"]  # the third J exposure is 0.07 um away
    assert green.frame_ids == ["ph0"] and red.frame_ids == ["pk0"]
    assert blue.detector == 2 and red.detector == 3


def test_jhk_falls_back_to_the_single_nearest_exposure_and_says_so():
    final = season_frames(S0)
    pool = jhk_pool(S0, k=(2.27, 2.26))  # 0.10 / 0.09 um from Ks: outside 0.06, inside 0.12
    comp = by_id(plan_composites(final, pool=[*final, *pool]))["jhk_S0"]
    assert comp.channels[0].frame_ids == ["pk1"]
    assert any("red (Ks" in n and "nearest" in n and "2.260" in n for n in comp.notes)


def test_jhk_skips_the_season_when_a_band_has_nothing_within_the_fallback_and_says_why():
    final = season_frames(S0) + season_frames(S1, prefix="b")
    pool = jhk_pool(S0) + jhk_pool(S1, h=(1.65 + JHK_FALLBACK_UM + 0.01,), prefix="q")
    plan = plan_composites(final, pool=[*final, *pool])
    comps = by_id(plan)
    assert "jhk_S0" in comps and "jhk_S1" not in comps
    assert "detectors_S1" in comps  # the other mode is not affected
    reason = next(s for s in plan.skipped if s.startswith("jhk S1: "))
    assert "green (H 1.65 µm)" in reason and "0.12" in reason


def test_jhk_channel_may_mix_detectors_and_then_has_no_single_detector():
    final = season_frames(S0)
    pool = jhk_pool(S0, h=(1.62, 1.68))  # D2 upper edge and D3 lower edge
    comp = by_id(plan_composites(final, pool=[*final, *pool]))["jhk_S0"]
    green = comp.channels[1]
    assert green.frame_ids == ["ph0", "ph1"] and green.detector is None


def test_jhk_ignores_frames_without_a_known_wavelength():
    final = season_frames(S0)
    pool = jhk_pool(S0) + [gf("unknown", 2, S0, None)]
    comp = by_id(plan_composites(final, pool=[*final, *pool]))["jhk_S0"]
    assert all("unknown" not in ch.frame_ids for ch in comp.channels)


def test_pool_frames_join_the_season_of_the_nearest_final_frame():
    final = season_frames(S0) + season_frames(S1, prefix="b")
    late_pool = jhk_pool(S1 + 25.0, prefix="q")  # after the last final frame, within 30 days
    far_pool = jhk_pool(S1 + 200.0, prefix="z")  # a season with no final frame: not used
    plan = plan_composites(final, pool=[*final, *late_pool, *far_pool])
    comps = by_id(plan)
    assert comps["jhk_S1"].channels[0].frame_ids == ["qk0"]
    assert "jhk_S0" not in comps and "jhk_S2" not in comps
    assert all(c.season in (0, 1) for c in plan.composites)


# --- rendering ---------------------------------------------------------------------------------------------------


def test_stretch_of_a_channel_is_shared_by_every_season_of_its_mode():
    # Season 1 sees every field star 2x brighter (another wavelength): same contrast, brighter picture.
    a = [gf(f"a{d}", d, S0, None, sky(scale=1.0, seed=d)) for d in (1, 3, 6)]
    b = [gf(f"b{d}", d, S1, None, sky(scale=2.0, seed=10 + d, level=3.0)) for d in (1, 3, 6)]
    plan = plan_composites(a + b, pool=a + b)
    stretches = color_balance(plan.composites).stretches
    for c in ("red", "green", "blue"):
        s0, s1 = stretches[("detectors_S0", c)], stretches[("detectors_S1", c)]
        assert s1.vmax - s1.vmin == pytest.approx(s0.vmax - s0.vmin)
    rgb0 = composite_rgb(plan.composites[0], stretches)
    rgb1 = composite_rgb(plan.composites[1], stretches)
    assert rgb1[20, 6, :3].astype(int).sum() > rgb0[20, 6, :3].astype(int).sum()  # star (6, 20) brighter


def red_target_frames(red_target=6.0, stars=FIELD_STARS):
    """Channels differ in overall flux and noise (other wavelengths and detectors); the target at the
    centre (20, 20) shines only in red, like a brown dwarf at 4.5 um."""
    return [
        gf("r", 6, S0, 4.7, sky(scale=0.2, noise=0.02, seed=1, extra=[(20, 20, red_target)], stars=stars)),
        gf("g", 3, S0, 2.0, sky(scale=1.0, noise=0.05, seed=2, stars=stars)),
        gf("b", 1, S0, 0.9, sky(scale=3.0, noise=0.1, seed=3, stars=stars)),
    ]


@pytest.mark.parametrize("red_target", [6.0, 600.0])  # 600: the target alone would set a percentile stretch
def test_field_stars_come_out_neutral_and_a_very_red_object_red(red_target):
    frames = red_target_frames(red_target)
    plan = plan_composites(frames, pool=frames)
    comp = by_id(plan)["detectors_S0"]
    balance = color_balance(plan.composites)
    assert balance.ratios[(comp.id, "red")] == pytest.approx(0.2, rel=0.05)
    assert balance.ratios[(comp.id, "blue")] == pytest.approx(3.0, rel=0.05)
    assert "so typical field stars look white" in balance.notes[comp.id][0]
    assert len(balance.notes[comp.id]) == 1  # no channel is noisy here
    rgb = composite_rgb(comp, balance.stretches).astype(int)
    for x, y, _ in FIELD_STARS:
        r, g, b = rgb[y, x, :3]
        assert max(r, g, b) - min(r, g, b) <= 0.15 * max(r, g, b), (x, y, (r, g, b))
    r, g, b = rgb[20, 20, :3]
    assert r > 150 and g < 0.3 * r and b < 0.3 * r


def test_the_sky_stays_neutral_when_one_channel_is_much_noisier():
    # Like real D6: noise ~7 % of its balanced span (green ~0.1 %). A per-channel 2-sigma black point
    # lifted that channel's whole sky (the purple eps Indi B / WISE 0855 backgrounds).
    frames = red_target_frames()
    frames[0] = gf("r", 6, S0, 4.7, sky(scale=0.2, noise=0.5, seed=1))
    plan = plan_composites(frames, pool=frames)
    comp = plan.composites[0]
    rgb = composite_rgb(comp, color_balance(plan.composites).stretches).astype(int)
    yy, xx = np.mgrid[0:N, 0:N]
    far = np.ones((N, N), bool)
    for x, y, _ in FIELD_STARS:
        far &= np.hypot(xx - x, yy - y) > 4
    r, g, b = (np.median(rgb[..., c][far]) for c in range(3))
    assert r <= g + 8 and abs(b - g) <= 8, (r, g, b)
    balance = color_balance(plan.composites)
    assert balance.noise[(comp.id, "red")] > color.NOISY_FRACTION > balance.noise[(comp.id, "green")]
    noisy = [n for n in balance.notes[comp.id] if "noisy" in n]
    assert noisy == [
        f"The red channel (D6, 1 frame(s)) is noisy here (pixel noise {100 * balance.noise[(comp.id, 'red')]:.0f}% "
        "of its colour-balanced range), so its black point is raised to 2 sigma of that noise above the sky: most "
        "noise specks are black, but faint red light is hidden too (faint field stars look cyan), and isolated red "
        "specks that remain are mostly noise, not red objects."
    ]


def test_a_field_with_too_few_stars_is_not_balanced_and_says_so():
    frames = red_target_frames(stars=FIELD_STARS[:3])
    plan = plan_composites(frames, pool=frames)
    balance = color_balance(plan.composites)
    comp = plan.composites[0]
    assert balance.ratios[(comp.id, "red")] is None and balance.ratios[(comp.id, "blue")] is None
    assert balance.notes[comp.id][0].startswith("Colour balance: not fitted")
    assert composite_rgb(comp, balance.stretches).shape == (N, N, 3)


def test_the_balance_is_shared_by_seasons_with_the_same_detectors_only():
    a = red_target_frames()
    b = [GridFrame(f.frame_id + "b", f.detector, S1, f.data, f.bad, f.variance, f.wavelength_um) for f in a]
    b[0] = GridFrame("r5", 5, S1, a[0].data * 2, a[0].bad, a[0].variance, 4.1)  # fallback D5, twice as bright
    plan = plan_composites([*a, *b], pool=[*a, *b])
    balance = color_balance(plan.composites)
    assert balance.ratios[("detectors_S0", "red")] == pytest.approx(0.2, rel=0.05)
    assert balance.ratios[("detectors_S1", "red")] == pytest.approx(0.4, rel=0.05)
    assert balance.ratios[("detectors_S1", "blue")] == pytest.approx(3.0, rel=0.05)


def test_png_is_rgb_on_the_grid_and_transparent_only_where_no_channel_has_data(tmp_path):
    frames = season_frames(S0)
    comps, _ = write_composites(tmp_path, frames, frames)
    with Image.open(tmp_path / comps[0].image) as png:
        assert png.mode == "RGB" and png.size == (N, N)

    red = sky(seed=5)
    red[:, :10] = np.nan  # red channel has no data in the left 10 columns
    blue_green_gap = np.zeros((N, N), bool)
    blue_green_gap[:5, :] = True  # blue + green have no data in the top 5 rows
    frames = [
        gf("r6", 6, S0, 4.7, red),
        gf("g3", 3, S0, 2.0, np.where(blue_green_gap, np.nan, sky(seed=6)).astype(np.float32)),
        gf("b1", 1, S0, 0.9, np.where(blue_green_gap, np.nan, sky(seed=7)).astype(np.float32)),
    ]
    comps, _ = write_composites(tmp_path, frames, frames)
    with Image.open(tmp_path / comps[0].image) as png:
        assert png.mode == "RGBA" and png.size == (N, N)
        alpha = np.asarray(png)[..., 3]
    nothing = blue_green_gap.copy()
    nothing[:, 10:] = False  # only the top-left corner lacks all three channels
    assert (alpha == 0).sum() == nothing.sum() and (alpha[nothing] == 0).all()
    rgb = np.asarray(Image.open(tmp_path / comps[0].image))[..., :3].astype(int)
    only_some = (np.isnan(red) | blue_green_gap) & ~nothing
    assert only_some.any() and (rgb[only_some].max(axis=1) == rgb[only_some].min(axis=1)).all()  # grey


def test_saturated_core_is_filled_for_display_and_does_not_set_the_stretch():
    core = np.zeros((N, N), bool)
    core[19:22, 19:22] = True

    def saturated(seed, peak):
        img = sky(seed=seed, extra=[(20, 20, peak)])
        img[core] = 5 * peak  # the display-repaired core (brightest neighbour) is finite but bad
        return img

    frames = [gf(f"s{d}", d, S0, None, saturated(d, 2000.0), bad=core) for d in (1, 3, 6)]
    plan = plan_composites(frames, pool=frames)
    comp = plan.composites[0]
    assert np.isnan(comp.channels[0].stack.data[20, 20])  # science coadd: no valid core
    assert np.isfinite(comp.channels[0].display[20, 20])  # display: filled
    stretches = color_balance(plan.composites).stretches
    assert stretches[(comp.id, "red")].vmax < 2000.0  # set by the usable pixels, not the core
    rgb = composite_rgb(comp, stretches)
    assert rgb.shape == (N, N, 3) and rgb[20, 20].min() > 200  # a bright star, not a hole


# --- products and contract ---------------------------------------------------------------------------------------


def test_written_composites_round_trip_through_the_field_contract(tmp_path):
    final = season_frames(S0) + season_frames(S1, prefix="b")
    pool = [*final, *jhk_pool(S0), *jhk_pool(S1, prefix="q")]
    comps, note = write_composites(tmp_path, final, pool)
    assert [c.id for c in comps] == ["detectors_S0", "detectors_S1", "jhk_S0", "jhk_S1"]
    assert all(isinstance(c, Composite) and c.image == f"{COLOR_DIR}/{c.id}.png" for c in comps)
    assert all((tmp_path / c.image).is_file() for c in comps)
    assert note.startswith("False-color composites: ") and "(infrared, not true color)" in note
    assert all(any("not true color" in n for n in c.notes) for c in comps)

    field = json.loads(DEMO_FIELD.read_text(encoding="utf-8"))
    field["composites"] = [json.loads(c.model_dump_json()) for c in comps]
    parsed = SkyField.model_validate_json(json.dumps(field))
    assert parsed.composites == comps
    jhk = parsed.composites[2]
    assert jhk.mode == "jhk" and [ch.frame_ids for ch in jhk.channels] == [["pk0"], ["ph0"], ["pj0"]]


def test_rewriting_removes_composites_that_no_longer_exist(tmp_path):
    final = season_frames(S0) + season_frames(S1, prefix="b")
    write_composites(tmp_path, final, final)
    assert (tmp_path / COLOR_DIR / "detectors_S1.png").exists()
    comps, _ = write_composites(tmp_path, final[:3], final[:3])
    assert [c.id for c in comps] == ["detectors_S0"]
    assert sorted(p.name for p in (tmp_path / COLOR_DIR).iterdir()) == ["detectors_S0.png"]


def test_no_composite_at_all_is_reported_not_raised(tmp_path):
    final = season_frames(S0, dets=(1, 3))
    comps, note = write_composites(tmp_path, final, final)
    assert comps == []
    assert note.startswith("False-color composites: none built") and "detectors S0" in note


def test_module_constants_follow_the_2mass_bands():
    assert color.JHK_BANDS == {"red": ("Ks", 2.17), "green": ("H", 1.65), "blue": ("J", 1.25)}
    assert JHK_TOLERANCE_UM == 0.06 and JHK_FALLBACK_UM == 0.12
    assert color.DETECTOR_CHANNELS == {"red": (6, 5), "green": (3, 4), "blue": (1, 2)}
