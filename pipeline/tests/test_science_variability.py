"""WS3-9 light curves (errante.science.variability) on synthetic SPHEREx-like stamps (offline).

The stamps carry a TAN WCS, a Gaussian PSF (plus a broad halo for the wing method), VARIANCE and FLAGS, so the code
runs exactly as on WS1 point stamps. The real-data reproductions (RW Aur, R Dra) are network tests in
test_science_validation_network.py.
"""

import json
import math
import types
import warnings

import numpy as np
import pytest
from astropy.io import fits
from astropy.io.fits.verify import VerifyWarning
from astropy.wcs import WCS

from errante.data.fits_io import SpherexImage
from errante.imaging.flags import FLAG_BITS
from errante.science import variability as v
from errante.science.variability import (
    Exposure,
    LightCurve,
    LightCurvePoint,
    estimate_period,
    light_curve_from_exposures,
    matched_pairs,
    wavelength_bins,
)

RA0, DEC0 = 150.0, 20.0
PIX_DEG = 6.15 / 3600.0
BOX = 81
COMPS = [(-22.0, -16.0, 40.0), (21.0, -18.0, 35.0), (-19.0, 20.0, 45.0), (23.0, 17.0, 30.0), (2.0, -25.0, 38.0)]
OVERFLOW = 1 << FLAG_BITS["OVERFLOW"]
NOISE = 0.02


def offset_sky(dx: float, dy: float) -> tuple[float, float]:
    """Sky position dx, dy pixels from the target (x = column grows to the WEST here: RA decreases)."""
    return RA0 - dx * PIX_DEG / math.cos(math.radians(DEC0)), DEC0 + dy * PIX_DEG


def stamp(
    target_amp: float,
    *,
    mjd: float,
    detector: int = 1,
    lam: float = 0.75,
    obs_id: str = "2025W36_1A_0001_1",
    saturate: bool = False,
    halo: float = 0.0,
    shift: tuple[float, float] = (0.0, 0.0),
    seed: int = 0,
    comps=COMPS,
    box: int = BOX,
) -> Exposure:
    """A box x box stamp centred near the target; ``shift`` moves the pointing (the target lands off-centre)."""
    c = (box - 1) / 2
    w = WCS(naxis=2)
    w.wcs.ctype = ["RA---TAN", "DEC--TAN"]
    w.wcs.crval = [RA0, DEC0]
    w.wcs.crpix = [c + 1 + shift[0], c + 1 + shift[1]]
    w.wcs.cdelt = [-PIX_DEG, PIX_DEG]
    yy, xx = np.mgrid[0:box, 0:box]
    rng = np.random.default_rng(seed)
    data = 0.3 + rng.normal(0, NOISE, (box, box))
    flags = np.zeros((box, box), np.int32)
    sources = [(0.0, 0.0, target_amp)] + [(dx, dy, a) for dx, dy, a in comps]
    for k, (dx, dy, amp) in enumerate(sources):
        sra, sdec = offset_sky(dx, dy)
        x, y = (float(t) for t in w.all_world2pix(sra, sdec, 0))
        r2 = (xx - x) ** 2 + (yy - y) ** 2
        data += amp * np.exp(-r2 / (2 * 1.2**2))
        if k == 0 and halo:
            data += halo * amp * np.exp(-r2 / (2 * 14.0**2))
        if k == 0 and saturate:
            core = r2 <= 2.0**2
            flags[core] |= OVERFLOW
            data[core] = 50.0  # clipped core: its value means nothing
    header = fits.Header()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", VerifyWarning)
        header["OMEGA_MEDIAN"] = 37.9  # a HIERARCH card, as in the real headers
    img = SpherexImage(
        data=data.astype(np.float32),
        flags=flags,
        variance=np.full((box, box), NOISE**2, np.float32),
        zodi=None,
        wcs=w,
        header=header,
        obs_id=obs_id,
        detector=detector,
        mjd=mjd,
        date_obs="",
    )
    img.wavelength_at = lambda ra, dec, lam=lam: (lam * (1 + 0.002 * (dec - DEC0) / PIX_DEG), 0.02)
    return Exposure(img, f"{obs_id}D{detector}", "dr1", lam, 0.02)


SEASONS = {0: 60920.0, 1: 61105.0, 2: 61290.0}
BRIGHTNESS = {0: 1.0, 1: 1.6, 2: 2.5}  # S0 -> S2: -2.5 log10(2.5) = -0.995 mag


def season_exposures(**kw):
    """Three seasons x two visits x three wavelengths on D1, a spectrum falling with lambda (bins needed)."""
    out, k = [], 0
    for s, t0 in SEASONS.items():
        for visit in range(2):
            for lam in (0.75, 0.80, 0.85):
                amp = 20.0 * BRIGHTNESS[s] * (0.75 / lam) ** 3
                shift = ((k % 5) - 2.0, (k % 3) - 1.0)
                out.append(
                    stamp(
                        amp,
                        mjd=t0 + 3 * visit + lam / 10,
                        lam=lam,
                        obs_id=f"S{s}V{visit}_{lam}",
                        shift=shift,
                        seed=k,
                        **kw,
                    )
                )
                k += 1
    return out


def test_wavelength_bins_are_greedy_and_narrow():
    assert wavelength_bins([0.75, 0.7549, 0.76, 0.80, 0.801]) == [0, 0, 1, 2, 2]
    assert wavelength_bins([1.0, 1.0, 1.0]) == [0, 0, 0]
    with pytest.raises(ValueError):
        wavelength_bins([1.0], 0.0)


def test_aperture_light_curve_recovers_season_changes_at_matched_wavelength():
    lc = light_curve_from_exposures(season_exposures(), RA0, DEC0, method="aperture")
    assert len(lc.used()) == 18 and not lc.excluded
    assert len(lc.bins) == 3 and {b.n_points for b in lc.bins} == {6}
    for b in lc.bins:  # within a bin, S2 - S0 = -0.995 mag whatever the wavelength
        m = {p.season: p.rel_mag for p in lc.points if p.bin == b.index}
        assert m[2] - m[0] == pytest.approx(-2.5 * math.log10(2.5), abs=0.01)
        assert m[1] - m[0] == pytest.approx(-2.5 * math.log10(1.6), abs=0.01)
    pairs = [p for p in matched_pairs(lc) if p["season_a"] == 0 and p["season_b"] == 2]
    assert len(pairs) == 12  # 3 wavelengths x 2 x 2 visits
    for p in pairs:
        assert p["delta_mag"] == pytest.approx(-0.995, abs=0.01)
        assert abs(p["ensemble_mag"]) < 0.01 and p["n_ensemble"] >= 3
        assert p["delta_mag_err"] < 0.01
    # the comparison stars are the control: constant, same frames, own wavelength
    assert len(lc.comparisons) >= 3
    assert lc.control[1]["robust_sigma_mag"] < 0.01
    assert lc.summary[1]["scatter_over_control"] > 10
    assert all(p.zero_point_mag is not None and abs(p.zero_point_mag) < 0.01 for p in lc.used())
    assert lc.period is None  # 18 points: no automatic period


def test_two_exposure_bins_remain_pairs_but_do_not_claim_ten_independent_scatter_points():
    # One visit in two seasons: each of the three wavelength bins has only two exposures.
    exposures = [e for e in season_exposures() if str(e.image.obs_id).startswith(("S0V0_", "S2V0_"))]
    assert len(exposures) == 6
    lc = light_curve_from_exposures(exposures, RA0, DEC0, method="aperture")
    assert len(lc.used()) == 6 and len(matched_pairs(lc)) == 3
    assert lc.summary[1]["n"] == 0 and lc.summary[1]["scatter_over_control"] is None
    assert any("only one independent difference" in note for note in lc.notes)


def test_flux_is_in_mjy_and_dates_are_iso():
    exp = season_exposures()[:6]
    lc = light_curve_from_exposures(exp, RA0, DEC0, method="aperture", n_comparison=0, min_bin_span_days=0)
    p = lc.points[0]
    truth = 2 * math.pi * 1.2**2 * 20.0 * (1 - math.exp(-(3.0**2) / (2 * 1.2**2)))  # MJy/sr * px within r = 3
    assert p.flux == pytest.approx(truth * 37.9 * (math.pi / 648000) ** 2 * 1e9, rel=0.02)
    assert p.date.startswith("2025-09-") and p.date.endswith("Z")
    assert "No comparison star" in " ".join(lc.notes)


def test_saturated_exposures_are_excluded_and_counted():
    exps = season_exposures()
    exps += [
        stamp(400.0, mjd=61291.0, lam=0.75, obs_id="SAT1", saturate=True),
        stamp(400.0, mjd=60921.0, lam=0.80, obs_id="SAT2", saturate=True),
    ]
    lc = light_curve_from_exposures(exps, RA0, DEC0, method="aperture")
    assert lc.excluded["saturated"] == 2
    sat = [p for p in lc.points if p.excluded == "saturated"]
    assert {p.frame_id for p in sat} == {"SAT1D1", "SAT2D1"} and all(p.rel_mag is None for p in sat)
    assert "saturated" in " ".join(lc.notes)
    assert not any(n.startswith("Saturated exposures by season") for n in lc.notes)  # 1/7, 0/6, 1/7: no censoring
    assert all(p["frame_a"] not in ("SAT1D1", "SAT2D1") for p in matched_pairs(lc))


def test_lone_and_short_bins_are_dropped_and_listed():
    exps = season_exposures()
    exps.append(stamp(10.0, mjd=60925.0, lam=0.95, obs_id="LONE"))  # alone at 0.95 um
    exps += [stamp(10.0, mjd=60930.0, lam=1.05, obs_id="SHORTA"), stamp(10.0, mjd=60935.0, lam=1.05, obs_id="SHORTB")]
    lc = light_curve_from_exposures(exps, RA0, DEC0, method="aperture")
    why = {p.frame_id: p.excluded for p in lc.points}
    assert why["LONED1"] == "lone_bin"
    assert why["SHORTAD1"] == why["SHORTBD1"] == "short_bin"  # 5 d < 30 d: no time information
    lc0 = light_curve_from_exposures(exps, RA0, DEC0, method="aperture", min_bin_span_days=0)
    assert {p.frame_id: p.excluded for p in lc0.points}["SHORTAD1"] is None


def test_target_off_the_stamp_or_without_flags_is_excluded():
    exps = season_exposures()[:6]
    bad = stamp(20.0, mjd=60950.0, lam=0.75, obs_id="NOFLAGS")
    bad.image.flags = None  # FLAGS not read: unknown, NOT clean
    far = stamp(20.0, mjd=60951.0, lam=0.75, obs_id="FAR", shift=(60.0, 0.0))  # target 60 px off the 81 px stamp
    lc = light_curve_from_exposures([*exps, bad, far], RA0, DEC0, method="aperture", min_bin_span_days=0)
    why = {p.frame_id: p.excluded for p in lc.points}
    assert why["NOFLAGSD1"] == "no_flags" and why["FARD1"] == "edge"


WING_COMPS = [(36.0, 22.0, 40.0), (-35.0, -20.0, 35.0), (-30.0, 30.0, 45.0)]  # >= 30 px: off the target's halo


def wing_exposures(comps=COMPS):
    """A saturated star with a halo on D4, three seasons x two wavelengths, 111 px stamps (``COMPS`` are all closer
    than the 30 px the wing method needs: no comparison; ``WING_COMPS`` are far enough)."""
    exps = []
    for s, t0 in SEASONS.items():
        for lam in (2.5, 2.6):
            amp = 300.0 * BRIGHTNESS[s]
            exps.append(
                stamp(
                    amp,
                    mjd=t0 + lam,
                    detector=4,
                    lam=lam,
                    obs_id=f"W{s}_{lam}",
                    saturate=True,
                    halo=0.01,
                    box=111,
                    seed=s,
                    comps=comps,
                )
            )
    return exps


def test_wing_method_measures_a_saturated_star_relative_brightness():
    exps = wing_exposures()
    lc = light_curve_from_exposures(exps, RA0, DEC0, method="wing")
    assert lc.unit.startswith("MJy/sr")
    assert all("saturated_core" in p.flags for p in lc.points)
    assert len(lc.used()) == 6
    for b in lc.bins:
        m = {p.season: p.rel_mag for p in lc.points if p.bin == b.index}
        assert m[2] - m[0] == pytest.approx(-0.995, abs=0.03)
    # the aperture method on the same stamps excludes all of them (OVERFLOW in the aperture)
    ap = light_curve_from_exposures(exps, RA0, DEC0, method="aperture")
    assert ap.excluded == {"saturated": 6} and not ap.used()


def test_wing_measure_flags_a_clipped_annulus():
    e = stamp(300.0, mjd=60900.0, lam=2.5, halo=0.01, box=111, shift=(50.0, 0.0))  # target 5 px from the edge
    pl = v.photometry.planes(e.image)
    x, y = v.sky_to_pixel(e.image, RA0, DEC0)
    flux, err, flags = v.wing_measure(pl, float(x[0]), float(y[0]))
    assert "edge" in flags and math.isnan(flux)


def synthetic_lc(period=250.0, amp=0.5, n_det=2, seed=3, trend=0.0, err=0.03) -> LightCurve:
    """Points of a sinusoid sampled in three seasons with per-bin offsets already removed (relative magnitudes).
    ``trend``: mag added linearly over the 500 d baseline; ``err``: the stated error (the noise is 0.03 mag)."""
    rng = np.random.default_rng(seed)
    pts, b = [], 0
    for det in range(1, n_det + 1):
        for lam_bin in range(6):
            t = np.concatenate(
                [rng.uniform(60800, 60880, 8), rng.uniform(61000, 61080, 8), rng.uniform(61220, 61300, 8)]
            )
            m = amp / det * np.sin(2 * math.pi * t / period + det) + rng.normal(0, 0.03, t.size)  # semi-amplitude
            m += trend * (t - 60800) / 500
            m -= m.mean()
            for ti, mi in zip(t, m, strict=True):
                pts.append(
                    LightCurvePoint(
                        frame_id=f"f{len(pts)}",
                        obs_id="x",
                        detector=det,
                        release="dr1",
                        mjd=float(ti),
                        date="",
                        season=0,
                        wavelength_um=1.0 + 0.01 * lam_bin,
                        bandwidth_um=0.02,
                        flux=1.0,
                        flux_err=err,
                        bin=b,
                        rel_mag=float(mi),
                        rel_mag_err=err,
                    )  # fmt: skip
                )
            b += 1
    return LightCurve(0, 0, "wing", "", 0.01, 30, pts, [], [], {}, {}, {})


def test_period_estimate_recovers_a_sinusoid_with_seasonal_gaps():
    lc = synthetic_lc()
    p = estimate_period(lc, n_bootstrap=30)
    assert p.period_days == pytest.approx(250.0, rel=0.03)
    assert p.peaks[0][0] == pytest.approx(p.period_days)
    assert len(p.peaks) >= 2  # aliases listed
    assert p.amplitude_mag[1] == pytest.approx(1.0, abs=0.05)  # peak-to-peak
    assert p.amplitude_mag[2] == pytest.approx(0.5, abs=0.05)
    assert p.period_err_formal_days is not None and p.period_err_formal_days < 10
    lo, hi = p.bootstrap_95_days
    assert lo <= p.period_days <= hi
    assert "aliases" in p.caveat
    assert all(f < 0.05 for f in p.floor_mag.values())  # the noise is 0.03 mag: no extra floor needed
    assert p.significant is True and p.false_alarm <= 0.01 and p.n_permutations == 100
    assert p.untested_reason is None and p.caveat == v.PERIOD_CAVEAT  # 2 cycles, far from the grid ends: tested
    note = v.period_note(p)
    assert note.startswith("Significant time-correlated variability; best period 2") and "not a confirmed" in note
    assert set(p.amplitude_err_mag) == {1, 2} and all(0 < e < 0.05 for e in p.amplitude_err_mag.values())
    assert f"D1 {p.amplitude_mag[1]:.2f}±{p.amplitude_err_mag[1]:.2f}" in note


@pytest.mark.parametrize("seed", [1, 2, 3])
def test_noise_gives_a_best_period_but_not_a_significant_one(seed):
    """Review finding (2026-11-15): pure noise (0.03 mag) gave P = 37.1 / 32.1 / 40.7 d with formal errors of
    0.1-0.2 d and nothing said they were not significant."""
    p = estimate_period(synthetic_lc(amp=0.0, seed=seed))
    assert p.period_days > 0 and p.significant is False and p.false_alarm > 0.05
    assert v.period_note(p).startswith("No significant period")
    untested = estimate_period(synthetic_lc(amp=0.0, seed=seed), n_permutations=0)
    assert untested.significant is None and untested.false_alarm is None and "NOT tested" in v.period_note(untested)


def test_light_curve_to_dict_is_strict_json():
    lc = light_curve_from_exposures(season_exposures(), RA0, DEC0, method="aperture")
    lc.period = estimate_period(synthetic_lc())
    d = lc.to_dict()
    text = json.dumps(d, allow_nan=False)
    back = json.loads(text)
    assert back["method"] == "aperture" and back["unit"].startswith("mJy")
    assert set(back["summary"]) == {"1"} and back["comparisons"][0]["id"] == "C1"
    assert len(back["points"]) == 18 and back["period"]["period_days"] > 0


def test_invalid_arguments():
    with pytest.raises(ValueError):
        light_curve_from_exposures([], RA0, DEC0, method="psf")
    with pytest.raises(ValueError):
        v.light_curve(RA0, DEC0, method="wing", box_px=61)  # the 55 px background annulus needs 111 px


def test_light_curve_reads_point_stamps(monkeypatch):
    exps = season_exposures()
    samples = [
        types.SimpleNamespace(
            obs_id=e.image.obs_id,
            detector=e.image.detector,
            release="dr1",
            wavelength_um=e.wavelength_um,
            bandwidth_um=0.02,
            exp=e,
        )
        for e in exps
    ]
    asked = {}

    def fake_series(ra, dec, **kw):
        asked.update(kw)
        return types.SimpleNamespace(
            samples=samples,
            failures=[],
            search={"service": "fake", "n_found": len(samples)},
            timings={"frames": len(samples), "timed_out": 0},
        )

    import errante.data.point as point

    monkeypatch.setattr(point, "point_series", fake_series)
    monkeypatch.setattr(point, "to_spherex_image", lambda s: s.exp.image)
    lc = v.light_curve(RA0, DEC0, detectors=[1], deadline_s=20.0)
    assert asked["box_px"] == 81 and asked["planes"] == ("IMAGE", "VARIANCE", "FLAGS") and asked["deadline_s"] == 20.0
    assert asked["detectors"] == [1]
    assert len(lc.used()) == 18 and lc.search["service"] == "fake" and lc.timings["box_px"] == 81
    lcw = v.light_curve(RA0, DEC0, method="wing")
    assert asked["box_px"] == 111 and asked["planes"] == ("IMAGE", "FLAGS")
    assert lcw.method == "wing"


def fake_point(monkeypatch, exps):
    samples = [
        types.SimpleNamespace(
            obs_id=e.image.obs_id,
            detector=e.image.detector,
            release="dr1",
            wavelength_um=e.wavelength_um,
            bandwidth_um=0.02,
            exp=e,
        )
        for e in exps
    ]
    asked = {}

    def fake_series(ra, dec, **kw):
        asked.update(kw)
        failures = [(types.SimpleNamespace(obs_id="2025W01_1A_0001_1", detector=1), "NoOverlap: off the array")]
        return types.SimpleNamespace(samples=samples, failures=failures, search={}, timings={"timed_out": 0})

    import errante.data.point as point

    monkeypatch.setattr(point, "point_series", fake_series)
    monkeypatch.setattr(point, "to_spherex_image", lambda s: s.exp.image)
    return asked


def test_cli_lightcurve_json_and_summary(monkeypatch, capsys, tmp_path):
    from errante.cli import main

    asked = fake_point(monkeypatch, season_exposures())
    out = tmp_path / "lc.json"
    assert main(["lightcurve", "--ra", str(RA0), "--dec", str(DEC0), "--deep", "--json", "--out", str(out)]) == 0
    assert asked["collections"] == "spherex_dr1,spherex_qr3,spherex_dr1_deep,spherex_qr3_deep"
    doc = json.loads(capsys.readouterr().out)
    assert doc == json.loads(out.read_text())
    assert len(doc["matched_pairs"]) == 36 and doc["failures"][0]["frame_id"] == "2025W01_1A_0001_1D1"
    # the wing method on unsaturated 81 px stamps: the 55 px background annulus is not there -> nothing usable
    assert main(["lightcurve", "--ra", str(RA0), "--dec", str(DEC0), "--method", "wing", "--detector", "1"]) == 4
    text = capsys.readouterr().out
    assert "method wing" in text and "D1:" in text
    assert main(["lightcurve", "--ra", str(RA0), "--dec", str(DEC0), "--period"]) == 0
    text = capsys.readouterr().out
    assert "matched pairs" in text and "caveat" in text
    # 6 visits, a monotonic brightening: the forced estimate is printed as NOT a period (and not even tested: its
    # best period is the 800 d grid edge, < 1.5 cycles of the 373 d baseline)
    assert "NOT tested for significance" in text and "fewer than 1.5 cycles" in text and "  period " not in text


# --- WS3 review of the published light curves (docs/SCIENCE.md, LC7 and LC23-LC30) -------------------------------


def test_a_trend_is_not_tested_as_a_period(monkeypatch):
    """LC7: on R Dra's sampling a 0.6 mag linear trend peaked at the 800 d grid edge and beat every visit permutation
    (false alarm 1/101, 'significant'): time-correlated variability, not a period."""
    lc = synthetic_lc(amp=0.0, trend=0.6)
    p = estimate_period(lc)
    assert p.period_days == pytest.approx(800.0, rel=0.01)
    assert p.significant is None and p.false_alarm is None and p.n_permutations == 0  # the test is not even run
    assert "edge of the 20-800 d search range" in p.untested_reason and "fewer than 1.5 cycles" in p.untested_reason
    assert p.caveat.startswith("Not tested for significance: best period at the edge")
    assert p.caveat.endswith(v.PERIOD_CAVEAT) and "does not by itself establish a period" in p.caveat
    note = v.period_note(p)
    assert note.startswith("Best sinusoid 800.0 d, NOT tested for significance") and "consistent with a trend" in note
    # without the guard the same trend passes the permutation test: what 'significant' alone would have claimed
    monkeypatch.setattr(v, "_period_guard", lambda *a: None)
    unguarded = estimate_period(lc)
    assert unguarded.significant is True and unguarded.false_alarm == pytest.approx(1 / 101)


def test_period_guard_checks_both_grid_ends_and_the_cycles_covered():
    short = estimate_period(synthetic_lc(period=20.0))  # a real 20 d signal sits on the grid's short end
    assert short.period_days == pytest.approx(20.0, rel=0.01) and short.significant is None
    assert short.untested_reason == "best period at the edge of the 20-800 d search range"
    long = estimate_period(synthetic_lc(period=400.0))  # 1.25 cycles over the ~500 d baseline
    assert long.period_days == pytest.approx(400.0, rel=0.05) and long.significant is None
    assert long.n_permutations == 0 and long.untested_reason.startswith("it covers fewer than 1.5 cycles")
    assert "edge" not in long.untested_reason
    capped = estimate_period(synthetic_lc(), period_range_days=(20.0, 250.0))  # 249.4 d: one step from 250 d
    assert capped.significant is None and "edge of the 20-250 d search range" in capped.untested_reason
    untested = estimate_period(synthetic_lc(), n_permutations=0)  # no permutations asked: untested, no reason
    assert untested.significant is None and untested.untested_reason is None
    assert "NOT tested for significance (no permutations run)" in v.period_note(untested)


def test_a_period_of_one_and_a_half_to_two_cycles_is_tested():
    """MIN_PERIOD_CYCLES is 1.5, not the review's 2 (measured reasons in its comment): R Dra's catalog period
    (245.6-247.2 d) covers 1.73 cycles of the product's 426 d baseline, and no strong trend-like signal peaked at
    1.5-2 cycles on its sampling. A real 300 d sinusoid over ~500 d (1.67 cycles) is tested and significant."""
    p = estimate_period(synthetic_lc(period=300.0))
    assert p.period_days == pytest.approx(300.0, rel=0.05) and 1.5 < p.baseline_days / p.period_days < 2.0
    assert p.untested_reason is None and p.n_permutations == 100 and p.significant is True
    assert "a weak trend can still pass" in p.caveat


def test_cli_prints_the_false_alarm_as_counts(monkeypatch, capsys):
    """The CLI's period line used to print 'false-alarm 0.010' for 1/101 (LC8): the same counts as the notes now."""
    from errante.cli import main

    lc = synthetic_lc()
    lc.period = estimate_period(lc)
    assert lc.period.significant is True
    monkeypatch.setattr(v, "light_curve", lambda *a, **k: lc)
    assert main(["lightcurve", "--ra", "0", "--dec", "0"]) == 0
    text = capsys.readouterr().out
    line = next(x for x in text.splitlines() if x.startswith("  period "))
    assert (
        "false-alarm 1/101 (0 of 100 permutations reached the peak; the smallest value 100 permutations can give)"
        in (line)
    )
    assert "0.010" not in line


def period_arrays(lc):
    """The arrays estimate_period fits (used points with an error, t from the first point, bin labels)."""
    used = [p for p in lc.used() if p.rel_mag_err]
    t = np.array([p.mjd for p in used])
    y = np.array([p.rel_mag for p in used])
    sig = np.array([p.rel_mag_err for p in used])
    bins = np.unique([p.bin for p in used], return_inverse=True)[1]
    return t - t.min(), y, sig, bins, np.array([p.detector for p in used])


def test_floors_and_amplitude_errors_refer_to_the_reported_period():
    """LC27: the floors were evaluated at the statistical-only best period (239 d for R Dra), not the reported 259 d.
    LC29: amplitude_mag had no uncertainty; it now comes from the fit covariance (in the period note)."""
    lc = synthetic_lc(err=0.01)  # 0.03 mag noise with 0.01 mag errors: floors of ~0.03 mag are needed
    p = estimate_period(lc)
    assert p.significant is True and all(0.02 < f < 0.04 for f in p.floor_mag.values())
    t, y, sig, bins, dets = period_arrays(lc)
    f = 1.0 / p.period_days
    assert p.floor_mag == pytest.approx(v._floors(t, y, sig, bins, dets, f), abs=1e-3)
    # amplitude and error = the full weighted least squares (bin offsets + a sinusoid per detector) at that period
    w = 1.0 / (sig**2 + np.array([p.floor_mag[int(d)] for d in dets]) ** 2)
    nb = int(bins.max()) + 1
    x = np.zeros((t.size, nb + 4))
    x[np.arange(t.size), bins] = 1.0
    for j, d in enumerate((1, 2)):
        m = dets == d
        x[m, nb + 2 * j], x[m, nb + 2 * j + 1] = np.sin(2 * math.pi * f * t[m]), np.cos(2 * math.pi * f * t[m])
    cov = np.linalg.inv(x.T @ (x * w[:, None]))
    beta = cov @ (x.T @ (w * y))
    for j, d in enumerate((1, 2)):
        pq = beta[nb + 2 * j : nb + 2 * j + 2]
        g = pq / np.hypot(*pq)
        c = cov[nb + 2 * j : nb + 2 * j + 2, nb + 2 * j : nb + 2 * j + 2]
        assert p.amplitude_mag[d] == pytest.approx(2 * np.hypot(*pq), rel=1e-6)
        assert p.amplitude_err_mag[d] == pytest.approx(2 * math.sqrt(g @ c @ g), rel=1e-6)
    assert f"D2 {p.amplitude_mag[2]:.2f}±{p.amplitude_err_mag[2]:.2f}" in v.period_note(p)


def test_period_note_reads_the_false_alarm_as_counts():
    """LC8/LC29: (1 + k) / (1 + n) = 1/101 when 0 of 100 permutations reached the peak: the smallest value 100
    permutations can give, neither a measured 1 % nor an upper bound (the true probability can be higher)."""

    def pe(fap, n, significant):
        return v.PeriodEstimate(
            259.1, 1826.0, 6.2, None, [(259.1, 1826.0)], {1: 1.21}, {1: 0.35}, 450, 425.9, (20.0, 800.0),
            false_alarm=fap, n_permutations=n, significant=significant, amplitude_err_mag={1: 0.39},
        )  # fmt: skip

    smallest = v.period_note(pe(1 / 101, 100, True))
    assert (
        "probability 1/101 (0 of 100 permutations reached the peak; the smallest value 100 permutations can give)"
        in (smallest)
    )
    assert "<=" not in smallest and "D1 1.21±0.39" in smallest  # not written as an upper bound
    assert "candidate period" in smallest and "not a confirmed one" in smallest
    two = v.period_note(pe(3 / 101, 100, False))
    assert two.startswith("No significant period") and "is matched by shuffled visit epochs" in two
    assert "0.030 (2 of 100 permutations reached the peak)" in two and "needs at least" not in two
    assert "1/1000 (0 of 999 permutations reached the peak" in v.period_note(pe(1 / 1000, 999, True))
    # fewer than 99 permutations can never reach 1 %: unbeaten, the note must not say shuffled epochs matched it
    few = v.period_note(pe(1 / 51, 50, False))
    assert few.startswith("No significant period: 50 visit permutations cannot reach") and "1/51" in few
    assert "at least 99 are needed" in few and "none of them reached the peak" in few and "matched by" not in few
    beaten = v.period_note(pe(3 / 51, 50, False))
    assert "is matched by shuffled visit epochs" in beaten and "2 of 50 permutations" in beaten
    assert "which needs at least 99 permutations" in beaten
    assert v.false_alarm_text(pe(None, 0, None)) == "not tested"
    assert (
        "means time-correlated variability" in v.PERIOD_CAVEAT and "conditional on the chosen peak" in v.PERIOD_CAVEAT
    )


def test_wing_has_no_scatter_over_control():
    """LC24: wing scatter over the aperture comparisons' scatter is not a defined ratio."""
    lc = light_curve_from_exposures(wing_exposures(WING_COMPS), RA0, DEC0, method="wing")
    assert len(lc.comparisons) == 3 and lc.control[4]["robust_sigma_mag"] is not None
    assert lc.summary[4]["scatter_over_control"] is None
    assert any(n.startswith("scatter_over_control is not given for wing photometry") for n in lc.notes)
    # the comparisons' aperture pairs are not the floor of wing pairs (R Dra D1: floor_mag 0.35 against 0.030 mag)
    pair = next(n for n in lc.notes if n.startswith("Comparison-star matched-pair scatter"))
    assert "their own aperture pairs" in pair and "NOT the floor of the target's wing pairs" in pair
    assert "empirical floor" not in pair
    ap = light_curve_from_exposures(season_exposures(), RA0, DEC0, method="aperture")
    assert ap.summary[1]["scatter_over_control"] > 10 and not any("not given for wing" in n for n in ap.notes)
    pair = next(n for n in ap.notes if n.startswith("Comparison-star matched-pair scatter"))
    assert "the empirical floor for the target's matched-wavelength pairs" in pair and "NOT" not in pair


def lone_and_short_exposures():
    exps = season_exposures()
    exps.append(stamp(10.0, mjd=60925.0, lam=0.95, obs_id="LONE"))  # alone at 0.95 um
    exps += [stamp(10.0, mjd=60930.0, lam=1.05, obs_id="SHORTA"), stamp(10.0, mjd=60935.0, lam=1.05, obs_id="SHORTB")]
    return exps


def test_control_counts_comparison_exclusions_and_notes_the_pair_floor():
    """LC25: control[det].excluded was always {} (R Dra: ~36 % of the comparison measurements are excluded).
    LC26: the floor for a matched pair is the comparisons' own matched-pair scatter, not the per-point control."""
    lc = light_curve_from_exposures(lone_and_short_exposures(), RA0, DEC0, method="aperture")
    n = len(lc.comparisons)
    assert n >= 3
    assert lc.control[1]["excluded"] == {"lone_bin": n, "short_bin": 2 * n}  # every comparison, in the same frames
    assert sum(lc.control[1]["excluded"].values()) == sum(w is not None for c in lc.comparisons for w in c.excluded)
    pairs = v.comparison_pair_scatter(lc)
    # per star: 3 wavelengths x (15 pairs of 6 epochs - 3 within a season) >= 30 d apart; LONE/SHORT give none
    assert pairs[1]["n"] == 36 * n and pairs[1]["robust_sigma_mag"] < 0.02
    note = next(x for x in lc.notes if x.startswith("Comparison-star matched-pair scatter"))
    assert f"D1 {pairs[1]['robust_sigma_mag']:.3f} mag ({36 * n} pairs)" in note and "< 1.0%" in note
    assert v.comparison_pair_scatter(lc, min_dt_days=1000.0) == {}
    half = light_curve_from_exposures(season_exposures(), RA0, DEC0, lambda_bin_frac=0.005)  # the contract's minimum
    assert "< 0.5%" in next(x for x in half.notes if x.startswith("Comparison-star matched-pair scatter"))


def lc_point(fid: str, mjd: float, lam: float, flux: float) -> LightCurvePoint:
    return LightCurvePoint(fid, fid, 1, "dr1", mjd, v.mjd_to_iso(mjd), 0, lam, 0.01, flux, 0.01)


def comparison(cid: str, lam_b: float, flux_b: float) -> v.ComparisonStar:
    """A comparison at 2.0 um and flux 1 in frame A, ``lam_b``/``flux_b`` in frame B."""
    return v.ComparisonStar(
        cid, 0.0, 0.0, 2, ["A", "B"], [1, 1], [2.0, lam_b], [1.0, flux_b], [0.01, 0.01], [None, None], [None, None]
    )


def test_pair_ensemble_uses_only_wavelength_matched_comparisons():
    """LC28: a comparison sits elsewhere on the linear variable filter, so the target's wavelength match is not its
    match (median 0.5-0.9 %, up to 2.3 % on the real products): only comparisons matched themselves count."""
    pts = [lc_point("A", 61000.0, 1.000, 1.0), lc_point("B", 61100.0, 1.005, 0.5)]  # 0.5 % apart: a matched pair
    matched, off = comparison("C1", 2.004, 1.1), comparison("C2", 2.05, 3.0)  # 0.2 % and 2.5 % apart
    lc = LightCurve(0, 0, "aperture", "", 0.01, 30, pts, [], [matched, off], {}, {}, {})
    (pair,) = matched_pairs(lc)
    assert pair["delta_mag"] == pytest.approx(2.5 * math.log10(2.0))
    assert pair["n_ensemble"] == 1 and pair["ensemble_mag"] == pytest.approx(-2.5 * math.log10(1.1))
    assert pair["delta_mag_corrected"] == pytest.approx(pair["delta_mag"] - pair["ensemble_mag"])
    assert matched_pairs(lc, max_frac=0.03)[0]["n_ensemble"] == 2  # a looser match takes both
    lc.comparisons = [off]
    (pair,) = matched_pairs(lc)
    assert pair["n_ensemble"] == 0 and pair["ensemble_mag"] is None and pair["delta_mag_corrected"] is None


def saturated_in_one_season():
    """Season exposures plus 4 saturated ones in S2: saturated S0 0/6, S1 0/6, S2 4/10."""
    sat = [stamp(400.0, mjd=61291.0 + k, lam=0.75, obs_id=f"SAT{k}", saturate=True) for k in range(4)]
    return season_exposures() + sat


def test_saturation_changing_with_season_gets_a_censoring_note():
    """RW Aur saturates in 7/19, 14/19 and 16/18 exposures by season: the bright states are preferentially excluded,
    and the notes did not say so."""
    lc = light_curve_from_exposures(saturated_in_one_season(), RA0, DEC0, method="aperture")
    assert lc.excluded["saturated"] == 4
    note = next(n for n in lc.notes if n.startswith("Saturated exposures by season"))
    assert "S0 0/6, S1 0/6, S2 4/10" in note and "bright states may be preferentially excluded" in note


def as_contract(lc: LightCurve):
    """What WS4's adapter publishes (backend/errante_api/lightcurve_build.py calculate()), validated by the contract
    model (extra='forbid': a new key anywhere fails)."""
    from errante.models import LightCurveData

    native = lc.to_dict()
    for key in ("search", "timings"):
        native.pop(key, None)
    native["unit"] = "mJy" if lc.method == "aperture" else "MJy/sr"
    native["relative_only"] = lc.method == "wing"
    native["matched_pairs"] = matched_pairs(lc, max_frac=lc.lambda_bin_frac)
    native["failures"] = []
    return LightCurveData.model_validate(native)


def test_light_curves_still_validate_against_the_contract():
    forced = light_curve_from_exposures(lone_and_short_exposures(), RA0, DEC0, method="aperture", period=True)
    assert forced.period.significant is None and forced.period.untested_reason  # a trend: untested
    assert not set(v.PERIOD_PRIVATE_FIELDS) & set(forced.to_dict()["period"])
    data = as_contract(forced)
    assert data.period.significant is None and data.period.n_permutations == 0 and data.period.false_alarm is None
    assert data.period.caveat.startswith("Not tested") and data.control[1].excluded["lone_bin"] == len(data.comparisons)
    assert data.matched_pairs and all(p.n_ensemble >= 3 for p in data.matched_pairs)
    for pe in (estimate_period(synthetic_lc()), estimate_period(synthetic_lc(amp=0.0, seed=1))):
        forced.period = pe  # a significant and a non-significant tested period
        assert as_contract(forced).period.significant is pe.significant
    wing = as_contract(light_curve_from_exposures(wing_exposures(WING_COMPS), RA0, DEC0, method="wing"))
    assert wing.relative_only and wing.summary[4].scatter_over_control is None and wing.control[4].n_stars == 3
    sat = as_contract(light_curve_from_exposures(saturated_in_one_season(), RA0, DEC0, method="aperture"))
    assert any(n.startswith("Saturated exposures by season") for n in sat.notes)
    assert any(n.startswith("Comparison-star matched-pair scatter") for n in sat.notes)


def _two_per_bin(exps, method):
    """The same exposures reduced to the first and last of each wavelength bin (two-exposure bins only)."""
    full = light_curve_from_exposures(exps, RA0, DEC0, method=method)
    keep = set()
    for b in full.bins:
        pts = sorted((p for p in full.points if p.bin == b.index), key=lambda p: p.mjd)
        keep |= {pts[0].frame_id, pts[-1].frame_id}
    return [e for e in exps if e.frame_id in keep]


def test_two_exposure_bins_note_and_control_follow_lc24():
    """LC24 follow-up (#102 review): the control uses the same >= 3-point rule as the summary, and the pair-floor
    advice is only given for aperture photometry with comparison stars (wing pairs have their own floor)."""
    exps = _two_per_bin(season_exposures(), "aperture")
    lc = light_curve_from_exposures(exps, RA0, DEC0, method="aperture")
    assert {b.n_points for b in lc.bins} == {2} and lc.comparisons
    note = next(n for n in lc.notes if "two-exposure" in n)
    assert "comparison-star control uses the same rule" in note and "aperture-pair noise floor" in note
    assert lc.summary[1]["n"] == 0 and lc.control[1]["n"] == 0 and lc.summary[1]["scatter_over_control"] is None
    alone = light_curve_from_exposures(exps, RA0, DEC0, method="aperture", n_comparison=0)
    assert "aperture-pair noise floor" not in next(n for n in alone.notes if "two-exposure" in n)
    wing = light_curve_from_exposures(_two_per_bin(wing_exposures(WING_COMPS), "wing"), RA0, DEC0, method="wing")
    note = next(n for n in wing.notes if "two-exposure" in n)
    assert "aperture-pair noise floor" not in note
    assert any("NOT the floor of the target's wing pairs" in n for n in wing.notes)
