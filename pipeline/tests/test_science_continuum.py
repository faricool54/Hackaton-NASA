"""V18: recover conditional colour temperatures, reject inputs that cannot support them.

Synthetic fluxes are generated independently with Astropy's physical model, not the fitting implementation.
These tests validate the algorithm, not the atmosphere or temperature of any real challenge target.
"""

import json
from dataclasses import replace

import astropy.units as u
import numpy as np
import pytest
from astropy.modeling.models import BlackBody

from errante.models import SpectralMeasurement, SpectrumPoint
from errante.science import continuum as c
from errante.science import spectra as s


def source(temperature=4000, scale=10.0, wavelengths=None):
    lam = np.geomspace(0.8, 5.0, 40) if wavelengths is None else np.asarray(wavelengths)
    bb = BlackBody(temperature=temperature * u.K)
    flux = (bb(lam * u.um) / bb(2 * u.um)).value * scale
    return [
        SpectrumPoint(
            frame_id=f"F{i}", wavelength_um=float(wavelength), flux_mjy=float(f), flux_err_mjy=float(f * 0.02)
        )
        for i, (wavelength, f) in enumerate(zip(lam, flux, strict=True))
    ]


@pytest.mark.parametrize("temperature", [1200, 3500, 6000])
def test_recovers_a_scaled_fnu_blackbody_with_closed_interval(temperature):
    fit = c.estimate_temperature(source(temperature))
    assert fit.status == "ok"
    assert fit.temperature_k == pytest.approx(temperature, rel=0.003)
    assert fit.lower_k < temperature < fit.upper_k
    assert fit.scale_mjy_at_2um == pytest.approx(10, rel=0.01)
    assert fit.reduced_chi2 < 0.01 and fit.n_channels >= 30
    assert "not stellar effective temperature" in fit.notes[0]
    json.dumps(fit.to_dict(), allow_nan=False)


def test_temperature_is_independent_of_source_brightness():
    faint, bright = (c.estimate_temperature(source(scale=x)) for x in (0.001, 10000))
    assert faint.temperature_k == bright.temperature_k
    assert faint.lower_k == pytest.approx(bright.lower_k)


def test_repeated_frames_do_not_create_spectral_coverage_or_average_down_the_floor():
    repeated = source(wavelengths=[1.0] * 100 + [2.0] * 100 + [4.0] * 100)
    assert c.estimate_temperature(repeated).status == "insufficient_data"
    few = source()
    many = [p.model_copy(update={"frame_id": f"{p.frame_id}-{i}"}) for p in few for i in range(100)]
    a, b = c.estimate_temperature(few), c.estimate_temperature(many)
    assert a.n_channels == b.n_channels
    assert (b.upper_k - b.lower_k) > 0.8 * (a.upper_k - a.lower_k)


@pytest.mark.parametrize("mode", ["missing_error", "zero_error", "negative", "low_snr", "narrow"])
def test_uninformative_fluxes_do_not_become_temperatures(mode):
    pts = source(wavelengths=np.linspace(4.1, 4.9, 20)) if mode == "narrow" else source()
    updates = {
        "missing_error": {"flux_err_mjy": None},
        "zero_error": {"flux_err_mjy": 0},
        "negative": {"flux_mjy": -1.0},
        "low_snr": {"flux_err_mjy": 1e6},
        "narrow": {},
    }
    fit = c.estimate_temperature([p.model_copy(update=updates[mode]) for p in pts])
    assert fit.temperature_k is None and fit.status == "insufficient_data"


def test_a_detection_selected_sed_is_withheld():
    pts = source()
    pts[:12] = [p.model_copy(update={"flux_mjy": -1}) for p in pts[:12]]
    fit = c.estimate_temperature(pts)
    assert fit.status == "censored_spectrum" and fit.temperature_k is None
    assert c.color_class(pts) == "unknown"


def test_absorption_and_temperature_boundaries_do_not_get_a_physical_value():
    pts = source()
    distorted = [p.model_copy(update={"flux_mjy": p.flux_mjy * (0.25 if i % 2 else 2)}) for i, p in enumerate(pts)]
    fit = c.estimate_temperature(distorted)
    assert fit.status == "poor_fit" and fit.temperature_k is None
    hot = c.estimate_temperature(source(temperature=100000))
    assert hot.temperature_k is None and hot.status in {"unconstrained", "poor_fit"}


@pytest.mark.parametrize("ratio,label", [(0.1, "blue"), (0.5, "neutral"), (1, "neutral"), (2, "red"), (5, "very-red")])
def test_colours_are_declared_fnu_display_categories(ratio, label):
    pts = source(wavelengths=[1.1, 1.4, 1.8, 4.1, 4.5, 4.9])
    pts = [p.model_copy(update={"flux_mjy": 1.0 if p.wavelength_um < 2 else ratio, "flux_err_mjy": 0.01}) for p in pts]
    assert c.color_class(pts) == label
    assert c.color_class(pts[:3]) == "unknown"


def as_spectrum():
    rows, seasons = [], []
    for season, temp in enumerate((3500, 6000)):
        points = source(temp)
        rows.extend(
            s.SpectrumSample(
                p.frame_id,
                p.frame_id,
                1,
                "dr1",
                61000.0 + 100 * season,
                "",
                season,
                p.wavelength_um,
                None,
                p.flux_mjy,
                p.flux_err_mjy,
                False,
                True,
                1.1,
            )
            for p in points
        )
        seasons.append(
            s.SeasonSummary(season, 61000 + 100 * season, 61000 + 100 * season, "", "", 40, 40, 0, [1], 0.8, 5)
        )
    return s.PositionSpectrum(10, 20, None, rows, seasons, [], True)


def test_variable_source_is_interpreted_per_season_never_as_a_pooled_temperature():
    spec = as_spectrum()
    diagnostics = spec.to_dict()["interpretation"]
    assert len(diagnostics) == 2
    assert diagnostics[0]["temperature"]["temperature_k"] == pytest.approx(3500, rel=0.003)
    assert diagnostics[1]["temperature"]["temperature_k"] == pytest.approx(6000, rel=0.003)
    assert "temperature" not in spec.to_dict()  # no global/mixed-epoch temperature


@pytest.mark.parametrize("problem", ["saturated", "uncorrected"])
def test_season_quality_is_checked_before_reporting_temperature_or_colour(problem):
    spec = as_spectrum()
    spec.samples = [
        replace(p, saturated=True, usable=False) if problem == "saturated" else replace(p, aperture_correction=None)
        for p in spec.samples
    ]
    for row in spec.to_dict()["interpretation"]:
        assert row["temperature"]["status"] == "quality_rejected"
        assert row["temperature"]["temperature_k"] is None and row["color_class"] == "unknown"


def test_api_adapter_keeps_cube_unknown_and_exposure_results_per_season():
    points = [
        SpectralMeasurement(
            id=p.frame_id,
            detector=1,
            wavelength_um=p.wavelength_um,
            flux=p.flux_mjy,
            flux_err=p.flux_err_mjy,
            usable=True,
            mjd=61000,
            aperture_correction=1.1,
        )
        for p in source()
    ]
    kw = dict(unit="mJy", background_subtracted=True, static_coadd=False)
    (row,) = s.interpret_measurements(points, **kw)
    assert row["temperature"]["temperature_k"] == pytest.approx(4000, rel=0.003)
    assert "not stellar effective temperature" in s.interpretation_notes([row])[0]
    assert "conditional interval" in s.interpretation_notes([row])[1]
    (cube,) = s.interpret_measurements(points, unit="MJy/sr", background_subtracted=False, static_coadd=True)
    assert cube["temperature"]["status"] == "unsupported_product" and cube["temperature"]["temperature_k"] is None
    assert not any("No positive source fluxes" in note for note in cube["temperature"]["notes"])
    points[0].mjd = None
    assert s.interpret_measurements(points, **kw)[0]["temperature"]["status"] == "unknown_epoch"


def test_systematic_temperature_allowance_cannot_average_down_with_many_channels():
    pts = source(3000)
    rng = np.random.default_rng(7)
    noisy = [p.model_copy(update={"flux_mjy": p.flux_mjy * (1 + rng.normal(0, 0.08))}) for p in pts]
    for fit in (c.estimate_temperature(pts), c.estimate_temperature(noisy)):
        assert fit.status == "ok"
        assert fit.lower_k <= fit.temperature_k * 0.9
        assert fit.upper_k >= fit.temperature_k * 1.1
    assert c.estimate_temperature(noisy).reduced_chi2 > 1


def test_real_detector_edge_has_tolerance_and_colour_windows_need_broad_coverage():
    pts = source(wavelengths=[0.74996, 1.1, 1.4, 1.8, 4.1, 4.5, 4.9])
    assert "outside_spherex_wavelength" not in c.estimate_temperature(pts).excluded
    narrow = source(wavelengths=[1.3, 1.4, 1.5, 4.3, 4.5, 4.7])
    assert c.color_class(narrow) == "unknown"


@pytest.mark.parametrize("n_saturated", [1, 8])
def test_even_a_small_censored_peak_is_not_fitted_as_an_uncensored_sed(n_saturated):
    spec = as_spectrum()
    spec.samples[:n_saturated] = [replace(p, saturated=True, usable=False) for p in spec.samples[:n_saturated]]
    first, second = s.interpret_spectrum(spec)
    assert first["temperature"]["status"] == "quality_rejected" and first["color_class"] == "unknown"
    assert first["temperature"]["temperature_k"] is None
    assert second["temperature"]["status"] == "ok"


def test_replay_real_eps_indi_photometry_does_not_invent_an_effective_temperature():
    from pathlib import Path

    doc = json.loads((Path(__file__).parent / "fixtures/ws3/continuum/eps-indi-b.json").read_bytes())
    spec = s.PositionSpectrum(
        **{
            **doc["spectrum"],
            "samples": [s.SpectrumSample(**p) for p in doc["spectrum"]["samples"]],
            "seasons": [s.SeasonSummary(**p) for p in doc["spectrum"]["seasons"]],
        }
    )
    assert len(spec.samples) == 40 and len(spec.usable()) == 35
    diagnostics = s.interpret_spectrum(spec)
    assert all(d["temperature"]["temperature_k"] is None for d in diagnostics)
    assert {d["temperature"]["status"] for d in diagnostics} >= {"poor_fit", "quality_rejected"}
    assert "snapshot" in doc["method"].lower()
