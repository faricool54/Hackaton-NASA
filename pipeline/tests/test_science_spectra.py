"""WS3-5 spectrum at a chosen position (errante.science.spectra), offline.

WS2's forced photometry (imaging.photometry) is tested by WS2; here its output (ForcedFlux) is synthetic, so the
season grouping, the variability check, the unit conversions and the reference comparisons are tested alone.
Real-data checks (eps Ind B against 2MASS/AllWISE and the DR1 cube, WISE 0855 against AllWISE W2) are network
tests in test_science_validation_network.py.
"""

import json
import math
from dataclasses import replace
from datetime import datetime
from pathlib import Path

import pytest

from errante.imaging import photometry
from errante.imaging.photometry import ForcedFlux, SpectrumResult
from errante.models import Candidate, Detection, SkyCoord
from errante.science import spectra
from errante.science.spectra import (
    REFERENCE_BANDS,
    band_average,
    candidate_spectrum,
    compare_with_cube,
    compare_with_photometry,
    from_spectrum_result,
    mag_to_mjy,
)

CUBE = Path(__file__).parent / "fixtures" / "ws1" / "cube_spectra"
SEASON_MJD = (60920.0, 61105.0, 61290.0)


def ff(i, *, mjd, lam, flux, det=1, err=None, flags=(), release="dr1"):
    return ForcedFlux(
        frame_id=f"F{i:03d}D{det}",
        obs_id=f"F{i:03d}",
        detector=det,
        mjd=mjd,
        release=release,
        ra=10.0,
        dec=20.0,
        x=5.0,
        y=5.0,
        wavelength_um=lam,
        bandwidth_um=0.02 * lam if lam else None,
        flux_mjy=flux,
        flux_err_mjy=0.01 * flux if err is None and flux else err,
        sky_mjy_sr=0.1,
        aperture_correction=1.1,
        flags=tuple(flags),
    )


def star(brightness=(1.0, 1.0, 1.0), *, lams=(0.75, 0.80, 0.85, 1.2, 1.6), saturate_from=None):
    """A star falling as lambda^-2, observed at the same wavelengths in three seasons."""
    pts, i = [], 0
    for s, t0 in enumerate(SEASON_MJD):
        for k, lam in enumerate(lams):
            flags = ("saturated",) if saturate_from is not None and k >= saturate_from else ()
            pts.append(ff(i, mjd=t0 + k * 0.5, lam=lam, flux=10.0 * brightness[s] * (1 / lam) ** 2, flags=flags))
            i += 1
    return SpectrumResult(10.0, 20.0, pts, [], ["15 SPHEREx exposures cover this position."])


def test_seasons_dates_and_contract_points():
    spec = from_spectrum_result(star())
    assert [s.n_points for s in spec.seasons] == [5, 5, 5]
    assert {s.season for s in spec.samples} == {0, 1, 2}
    first = spec.samples[0]
    assert first.date == "2025-09-02T00:00:00Z" and datetime.fromisoformat(first.date[:-1])
    pts = spec.spectrum_points()
    assert len(pts) == 15 and all(p.flux_mjy > 0 for p in pts)
    assert [p.wavelength_um for p in pts] == sorted(p.wavelength_um for p in pts)
    assert set(spec.by_season()) == {0, 1, 2} and len(spec.by_season()[1]) == 5
    assert spec.variable is False and not spec.warnings
    assert any("agree" in n for n in spec.notes)


def test_a_variable_source_gets_a_warning_not_a_mixed_spectrum():
    spec = from_spectrum_result(star(brightness=(1.0, 1.0, 2.5)))
    assert spec.variable is True
    assert len(spec.warnings) == 1 and "separately" in spec.warnings[0] and "S0->S2" in spec.warnings[0]
    s02 = [p for p in spec.season_pairs if (p["season_a"], p["season_b"]) == (0, 2)]
    assert len(s02) == 5 and all(p["delta_mag"] == pytest.approx(-0.995, abs=1e-3) for p in s02)


def test_single_outlier_pairs_do_not_make_a_constant_source_variable():
    res = star(lams=(0.75, 0.80, 0.85, 1.2, 1.6, 2.0, 2.4))
    res.points[-1] = ff(99, mjd=res.points[-1].mjd, lam=2.4, flux=res.points[-1].flux_mjy * 1.5)  # one glitch
    spec = from_spectrum_result(res)
    assert spec.variable is False and any(p["delta_mag"] < -0.4 for p in spec.season_pairs)


def test_variability_in_one_detector_is_not_outvoted_by_the_others():
    """A young star (RW Aur) changes ~1 mag at 0.75 um and little in the infrared: D1 must not be pooled with the many
    constant infrared pairs (review finding, 2026-11-15: the pooled median said 'constant', no warning)."""
    pts, i = [], 0
    for s, t0 in enumerate((60920.0, 61290.0)):
        for k, lam in enumerate((0.75, 0.78, 0.81, 0.84, 0.87)):  # D1: 1 mag brighter in S1, 5 matched pairs
            pts.append(ff(i, mjd=t0 + 0.1 * k, lam=lam, flux=100.0 * (2.512 if s else 1.0), det=1))
            i += 1
        for det, lam0, step in ((3, 1.7, 0.04), (4, 2.5, 0.08), (6, 4.4, 0.06)):  # constant, 4 pairs each
            for k in range(4):
                pts.append(ff(i, mjd=t0 + 1 + 0.01 * k, lam=lam0 + step * k, flux=300.0, det=det))
                i += 1
    spec = from_spectrum_result(SpectrumResult(1.0, 2.0, pts, [], []))
    assert len(spec.season_pairs) == 17
    assert spec.variable is True
    assert len(spec.warnings) == 1 and "S0->S1 D1 median dm -1.00 (5 pairs)" in spec.warnings[0]
    assert not any("D3" in w or "D4" in w or "D6" in w for w in spec.warnings)
    assert not any("agree" in n for n in spec.notes)
    # the same source without the D1 change: constant, and the note names the detectors it covers
    const = [
        ff(j, mjd=p.mjd, lam=p.wavelength_um, flux=100.0, det=p.detector) if p.detector == 1 else p
        for j, p in enumerate(pts)
    ]
    spec = from_spectrum_result(SpectrumResult(1.0, 2.0, const, [], []))
    assert spec.variable is False and not spec.warnings
    assert any("detector tested (D1, D3, D4, D6)" in n for n in spec.notes)


def test_one_detector_with_an_inconsistent_or_single_pair_is_not_called_constant():
    def two_seasons(d1_flux_s1):
        pts = []
        for s, t0 in enumerate((60920.0, 61290.0)):
            for k, lam in enumerate((1.7, 1.74, 1.78)):  # D3 constant
                pts.append(ff(10 * s + k, mjd=t0 + k, lam=lam, flux=50.0, det=3))
            for k, lam in enumerate((0.75, 0.80)[: len(d1_flux_s1)]):
                pts.append(ff(10 * s + 5 + k, mjd=t0 + 5 + k, lam=lam, flux=d1_flux_s1[k] if s else 50.0, det=1))
        return from_spectrum_result(SpectrumResult(1.0, 2.0, pts, [], []))

    # D1: two pairs, one unchanged and one 0.75 mag brighter: the median (mean of two) is -0.38 but not a majority
    spec = two_seasons((50.0, 100.0))
    assert spec.variable is None and any("S0->S1 D1 median dm -0.38 (2 pairs)" in w for w in spec.warnings)
    # D1: a single pair 1 mag brighter: not testable, never "constant" (the D3 pairs agree)
    spec = two_seasons((125.6,))
    assert spec.variable is None and any("S0->S1 D1 a single pair, dm -1.00" in w for w in spec.warnings)
    # D1 in both seasons but at wavelengths that do not match: named as not tested
    pts = [ff(0, mjd=60920.0, lam=0.75, flux=5.0), ff(1, mjd=61290.0, lam=0.90, flux=5.0)]
    pts += [ff(2 + k, mjd=60920.0 + 370 * (k % 2), lam=1.7, flux=50.0, det=3) for k in range(2)]
    spec = from_spectrum_result(SpectrumResult(1.0, 2.0, pts, [], []))
    assert spec.variable is False and any("no matched pair with SNR >= 10): D1." in n for n in spec.notes)


def test_untestable_multi_season_spectrum_is_warned():
    pts = [ff(0, mjd=60920.0, lam=0.75, flux=5.0), ff(1, mjd=61290.0, lam=0.90, flux=5.0)]
    spec = from_spectrum_result(SpectrumResult(1.0, 2.0, pts, [], []))
    assert spec.variable is None and spec.season_pairs == []
    assert any("no same-detector pair" in w for w in spec.warnings)
    single = from_spectrum_result(SpectrumResult(1.0, 2.0, pts[:1], [], []))
    assert single.variable is None and not single.warnings
    one_pair = [ff(0, mjd=60920.0, lam=0.75, flux=5.0), ff(1, mjd=61290.0, lam=0.751, flux=12.5)]  # 1 mag, once
    spec = from_spectrum_result(SpectrumResult(1.0, 2.0, one_pair, [], []))
    assert spec.variable is None and any("a single pair" in w for w in spec.warnings)


def test_saturated_exposures_are_lower_limits_outside_the_spectrum():
    spec = from_spectrum_result(star(saturate_from=2))  # 9 of 15 saturated
    sat = [s for s in spec.samples if s.saturated]
    assert len(sat) == 9 and not any(s.usable for s in sat)
    assert len(spec.spectrum_points()) == 6
    assert any("saturates in 9 of 15" in w for w in spec.warnings)
    assert spec.seasons[0].n_saturated == 3


def test_fluxes_without_aperture_correction_are_said():
    res = star()
    raw = [replace(p, aperture_correction=None, flags=("no_aperture_correction",)) for p in res.points]
    spec = from_spectrum_result(SpectrumResult(10.0, 20.0, raw, [], []))  # WISE 0855 D5/D6: no field star at all
    assert any("No aperture correction" in n and "all 15 usable" in n for n in spec.notes) and not spec.warnings
    mixed = from_spectrum_result(SpectrumResult(10.0, 20.0, raw[:5] + res.points[5:], [], []))
    assert any("5 of 15 usable points have no aperture correction" in w for w in mixed.warnings)
    assert not any("aperture correction" in n for n in from_spectrum_result(res).notes)


def test_to_dict_is_strict_json():
    res = star()
    res.points.append(ff(50, mjd=61000.0, lam=None, flux=None, flags=("no_wavelength", "no_sky")))
    res.points.append(ff(51, mjd=61001.0, lam=2.0, flux=5.0, err=float("nan")))
    res.failures.append(("X1D1", "TimeoutError: slow"))
    spec = from_spectrum_result(res, pm=(100.0, -50.0, 51544.5))
    text = json.dumps(spec.to_dict(), allow_nan=False)
    back = json.loads(text)
    assert back["proper_motion"] == {"pm_ra_masyr": 100.0, "pm_dec_masyr": -50.0, "epoch_mjd": 51544.5}
    assert back["failures"] == [{"frame_id": "X1D1", "reason": "TimeoutError: slow"}]
    by_id = {s["frame_id"]: s for s in back["samples"]}
    assert len(by_id) == 17
    assert by_id["F050D1"]["flux_mjy"] is None and by_id["F050D1"]["usable"] is False
    assert by_id["F051D1"]["flux_err_mjy"] is None  # NaN -> null
    assert by_id["F050D1"]["flags"] == ["no_wavelength", "no_sky"]


def test_noisy_pairs_make_variability_untestable_not_absent():
    pts, i = [], 0
    for s, t0 in enumerate(SEASON_MJD):
        for k, lam in enumerate((4.2, 4.4, 4.6)):
            flux = 0.5 * (1.0 + 0.2 * ((s + k) % 3 - 1))  # +-20 % between seasons, SNR 10: |dm| > 0.15 but < 5 sigma
            pts.append(ff(i, mjd=t0 + k, lam=lam, flux=flux, det=6, err=flux / 10.0))
            i += 1
    spec = from_spectrum_result(SpectrumResult(1.0, 2.0, pts, [], []))
    assert spec.variable is None
    assert any("not testable" in w for w in spec.warnings)
    faint = [ff(j, mjd=SEASON_MJD[j % 3], lam=4.4, flux=0.1, det=6, err=0.05) for j in range(6)]  # SNR 2
    assert from_spectrum_result(SpectrumResult(1.0, 2.0, faint, [], [])).season_pairs == []


def test_zero_points_and_magnitude_conversion():
    # WISE 0855 AllWISE W2 = 13.704 -> 0.567 mJy (docs/validation/wise-0855.md)
    f, e = mag_to_mjy(13.704, "WISE_W2", 0.033)
    assert f == pytest.approx(0.5667, abs=1e-4) and e == pytest.approx(f * 0.033 / 1.0857, rel=1e-3)
    assert mag_to_mjy(0.0, "2MASS_Ks")[0] == pytest.approx(666.7e3)
    assert mag_to_mjy(0.0, "2MASS_J")[0] == pytest.approx(1594e3)
    assert REFERENCE_BANDS["2MASS_H"].window_um == pytest.approx((1.5365, 1.7875))
    assert all(b.source for b in REFERENCE_BANDS.values())


def test_band_average_and_photometry_comparison():
    pts = [ff(i, mjd=60920.0 + i, lam=1.16 + 0.01 * i, flux=20.0) for i in range(15)]  # 1.16-1.30 um, flat
    spec = from_spectrum_result(SpectrumResult(1.0, 2.0, pts, [], []))
    avg = band_average(spec, "2MASS_J")
    assert avg["n"] == 15 and avg["mean_mjy"] == pytest.approx(20.0) and 0.8 < avg["coverage"] <= 1.0
    assert band_average(spec, "WISE_W2") is None
    mag = -2.5 * math.log10(20.0 / 1594e3)
    out = compare_with_photometry(spec, {"2MASS_J": (mag, 0.02), "WISE_W2": 10.0})
    assert out[0]["ratio"] == pytest.approx(1.0) and out[0]["zero_point_jy"] == 1594.0
    assert out[1]["spherex"] is None and out[1]["ratio"] is None


def test_cube_shape_comparison_on_the_real_eps_ind_b_fixture():
    cube = json.loads((CUBE / "eps-indi-b_ap2.json").read_text())
    pts = []
    for k, (lam, f, ok) in enumerate(zip(cube["wavelength_um"], cube["flux"], cube["valid"], strict=True)):
        if ok:  # a fake SPHEREx spectrum with the cube's shape: 50 mJy per MJy/sr, plus an offset
            pts.append(ff(k, mjd=61000.0, lam=lam, flux=50.0 * f + 3.0, det=cube["detector"][k]))
    spec = from_spectrum_result(SpectrumResult(1.0, 2.0, pts, [], []))
    r = compare_with_cube(spec, cube)
    assert r["n_planes"] == 100 and r["pearson_r"] == pytest.approx(1.0, abs=1e-6)
    assert r["slope"] == pytest.approx(1 / 50.0, rel=1e-4) and r["cube_unit"] == "MJy/sr"
    flat = from_spectrum_result(SpectrumResult(1.0, 2.0, pts[:3], [], []))
    assert compare_with_cube(flat, cube)["pearson_r"] is None


def test_candidate_spectrum_uses_measured_fluxes_only():
    def det(fid, flux):
        return Detection(frame_id=fid, mjd=60900.0, position=SkyCoord(ra=10.0, dec=20.0), x=1.0, y=1.0, flux_mjy=flux)

    cand = Candidate(
        id="c1",
        field_id="f",
        kind="moving",
        status="unconfirmed",
        score=0.5,
        detections=[det("A", 2.0), det("B", None), det("C", 1.5), det("D", 3.0)],
    )
    pts = candidate_spectrum(cand, {"A": (1.6, 0.04), "B": (1.2, 0.03), "C": (0.9, 0.02)})  # D: no wavelength
    assert [(p.frame_id, p.wavelength_um, p.flux_mjy) for p in pts] == [("C", 0.9, 1.5), ("A", 1.6, 2.0)]


def test_candidate_spectrum_from_images_uses_one_aperture_correction():
    """Review finding (2026-11-15): measure() per frame corrected the frame with field stars and left the star-poor
    one uncorrected (r = 2 px only): the same source differed by 38 % between two frames of one spectrum."""
    from test_science_variability import COMPS, DEC0, RA0, stamp

    with_stars = stamp(20.0, mjd=60900.0, lam=1.0, obs_id="A", comps=COMPS)
    no_stars = stamp(20.0, mjd=60901.0, lam=1.0, obs_id="B", comps=[])
    alone = stamp(20.0, mjd=60902.0, lam=2.5, detector=4, obs_id="C", comps=[])
    frames = (with_stars, no_stars, alone)
    dets = [
        Detection(frame_id=e.frame_id, mjd=e.mjd, position=SkyCoord(ra=RA0, dec=DEC0), x=40.0, y=40.0) for e in frames
    ]
    dets.append(Detection(frame_id="X", mjd=60903.0, position=SkyCoord(ra=RA0, dec=DEC0), x=1.0, y=1.0, flux_mjy=9.0))
    cand = Candidate(id="c", field_id="f", kind="moving", status="unconfirmed", score=0.5, detections=dets)
    images = {e.frame_id: e.image for e in frames}
    pts = candidate_spectrum(cand, {"X": (1.2, 0.02)}, images=images)
    by_id = {p.frame_id: p.flux_mjy for p in pts}
    assert set(by_id) == {"AD1", "BD1", "CD4"}  # X has no image: its flux of unknown aperture is not mixed in
    assert by_id["AD1"] == pytest.approx(by_id["BD1"], rel=0.02)  # one correction for D1 (was a ratio of 1.38)
    assert by_id["CD4"] == pytest.approx(by_id["AD1"], rel=0.02)  # D4 has no star: the all-detector fit
    # no field star in any image: no correction can be measured, and nothing uncorrected is returned
    bare = {e.frame_id: e.image for e in (no_stars, alone)}
    assert candidate_spectrum(cand, {}, images=bare) == []


def test_position_spectrum_calls_ws2_photometry(monkeypatch):
    seen = {}

    def fake(ra, dec, **kw):
        seen.update(kw, ra=ra, dec=dec)
        return star()

    monkeypatch.setattr(photometry, "spectrum_at", fake)
    pm = (3981.977, -2466.832, 51544.5)
    spec = spectra.position_spectrum(331.04, -56.78, pm=pm, detectors=[5, 6], max_frames=40)
    assert seen["pm"] == pm and seen["detectors"] == [5, 6] and seen["max_frames"] == 40
    assert spec.proper_motion["pm_ra_masyr"] == 3981.977 and len(spec.samples) == 15


def test_color_class_is_not_implemented():
    with pytest.raises(NotImplementedError):
        spectra.color_class([])


def test_cli_position_spectrum(monkeypatch, capsys):
    from errante.cli import main

    seen = {}

    def fake(ra, dec, **kw):
        seen.update(kw)
        return star(brightness=(1.0, 1.0, 2.5))

    monkeypatch.setattr(photometry, "spectrum_at", fake)
    argv = ["position-spectrum", "--ra", "331.04", "--dec", "-56.78", "--pm-ra", "3981.977", "--pm-dec", "-2466.832"]
    assert main([*argv, "--json"]) == 0
    doc = json.loads(capsys.readouterr().out)
    assert seen["pm"] == (3981.977, -2466.832, 51544.5)
    assert doc["variable"] is True and len(doc["seasons"]) == 3
    assert main(argv) == 0
    text = capsys.readouterr().out
    assert "season 2: 2026-09-" in text and "WARNING: The flux changed between seasons" in text
    monkeypatch.setattr(photometry, "spectrum_at", lambda ra, dec, **kw: SpectrumResult(ra, dec, [], [], []))
    assert main(argv) == 4
