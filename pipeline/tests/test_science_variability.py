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


def test_wing_method_measures_a_saturated_star_relative_brightness():
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
                )
            )
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


def synthetic_lc(period=250.0, amp=0.5, n_det=2, seed=3) -> LightCurve:
    """Points of a sinusoid sampled in three seasons with per-bin offsets already removed (relative magnitudes)."""
    rng = np.random.default_rng(seed)
    pts, b = [], 0
    for det in range(1, n_det + 1):
        for lam_bin in range(6):
            t = np.concatenate(
                [rng.uniform(60800, 60880, 8), rng.uniform(61000, 61080, 8), rng.uniform(61220, 61300, 8)]
            )
            m = amp / det * np.sin(2 * math.pi * t / period + det) + rng.normal(0, 0.03, t.size)  # semi-amplitude
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
                        flux_err=0.03,
                        bin=b,
                        rel_mag=float(mi),
                        rel_mag_err=0.03,
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
    assert v.period_note(p).startswith("Period 2")


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
    # 6 visits, a monotonic brightening: the forced estimate is printed as NOT a period
    assert "No significant period" in text and "  period " not in text
