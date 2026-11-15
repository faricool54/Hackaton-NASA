"""Descriptive SPHEREx colours and conditional blackbody colour temperatures (WS3, V18).

Fit F_nu, not F_lambda: mJy is a flux density per Hz. The model is a scaled Planck B_nu
evaluated at each channel centre (Astropy physical_models.BlackBody documentation).
This is NOT a stellar-atmosphere fit or an effective temperature measurement. Extinction,
disks, molecular absorption, blends and variability can all invalidate this approximation.
Only background-subtracted, quality-screened source fluxes belong here, never a raw cube poke.
"""

from __future__ import annotations

import math
from collections import Counter
from collections.abc import Sequence
from dataclasses import asdict, dataclass, field

import numpy as np

from ..models import SpectrumPoint

PLANCK_SOURCE = "https://docs.astropy.org/en/stable/modeling/physical_models.html#blackbody"
HC_OVER_K_UM_K = 14387.768775039337  # exact SI h*c/k_B, expressed in micrometre kelvin
MIN_CHANNELS = 6
MIN_SPAN = 2.0
FRACTIONAL_FLOOR = 0.05  # declared modelling allowance, NOT a measured instrument calibration
CHANNEL_FRAC = 0.025  # approximate broad SPHEREx channel width; prevents repeated-frame pseudo-precision
TEMPERATURE_BOUNDS_K = (300.0, 20000.0)
TEMPERATURE_FLOOR_FRACTION = 0.10  # declared modelling allowance, not calibrated confidence
CAUTION = (
    "Blackbody colour temperature, not stellar effective temperature or a physical 3D reconstruction. "
    "No extinction, disk, atmosphere/molecular-band or blend model; channel centres approximate bandpasses. "
    "Ranges rescale profile delta-chi2 by max(1, reduced chi2) and include an assumed +/-10% temperature "
    "modelling floor; they are not calibrated confidence intervals or total astrophysical uncertainties."
)


@dataclass
class TemperatureEstimate:
    status: str = "insufficient_data"
    temperature_k: float | None = None
    lower_k: float | None = None
    upper_k: float | None = None
    scale_mjy_at_2um: float | None = None
    reduced_chi2: float | None = None
    n_points: int = 0
    n_channels: int = 0
    wavelength_range_um: tuple[float, float] | None = None
    excluded: dict[str, int] = field(default_factory=dict)
    frame_ids: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=lambda: [CAUTION])
    model_source: str = PLANCK_SOURCE
    temperature_floor_fraction: float = TEMPERATURE_FLOOR_FRACTION

    def to_dict(self) -> dict:
        return asdict(self)


def _valid_points(points: Sequence[SpectrumPoint]) -> tuple[list[SpectrumPoint], dict[str, int]]:
    valid, excluded = [], Counter()
    for p in points:
        # WCS-WAVE centres straddle nominal detector edges (real epsilon Indi B: 0.74996 um).
        if not (math.isfinite(p.wavelength_um) and 0.74 <= p.wavelength_um <= 5.05):
            excluded["outside_spherex_wavelength"] += 1
        elif not math.isfinite(p.flux_mjy) or p.flux_mjy <= 0:
            excluded["nonpositive_or_missing_flux"] += 1
        elif p.flux_err_mjy is None or not math.isfinite(p.flux_err_mjy) or p.flux_err_mjy <= 0:
            excluded["missing_uncertainty"] += 1
        elif p.flux_mjy / p.flux_err_mjy < 3:
            excluded["low_snr"] += 1
        else:
            valid.append(p)
    return valid, dict(excluded)


def _channels(points: Sequence[SpectrumPoint]) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Group near-repeated wavelengths; a 5% floor cannot be averaged down with repeated exposures."""
    groups: list[list[SpectrumPoint]] = []
    for p in sorted(points, key=lambda p: p.wavelength_um):
        if not groups or p.wavelength_um / groups[-1][0].wavelength_um > 1 + CHANNEL_FRAC:
            groups.append([])
        groups[-1].append(p)
    rows = []
    for group in groups:
        lam = np.array([p.wavelength_um for p in group])
        flux = np.array([p.flux_mjy for p in group])
        err = np.array([p.flux_err_mjy for p in group])
        w = 1 / err**2
        mean = float(np.average(flux, weights=w))
        # Retain the dispersion of repeat measurements as an allowance, not the error of their mean.
        scatter = float(np.sqrt(np.average((flux - mean) ** 2, weights=w)))
        sigma = math.sqrt(1 / w.sum() + (FRACTIONAL_FLOOR * mean) ** 2 + scatter**2)
        rows.append((float(np.average(lam, weights=w)), mean, sigma))
    return tuple(np.asarray(rows, float).T)


def planck_fnu_shape(wavelength_um, temperature_k):
    """B_nu(lambda, T) / B_nu(2 um, T), dimensionless; wavelength in um, temperature in K."""
    lam = np.asarray(wavelength_um, float)
    temp = np.asarray(temperature_k, float)
    return (2 / lam) ** 3 * np.expm1(HC_OVER_K_UM_K / (2 * temp)) / np.expm1(HC_OVER_K_UM_K / (lam * temp))


def estimate_temperature(points: Sequence[SpectrumPoint]) -> TemperatureEstimate:
    """Weighted one-component B_nu fit with a profiled positive scale and explicit rejection gates.

    Caller guarantees quality-screened, background-subtracted mJy source fluxes from one epoch/season.
    Unknown errors, low S/N and non-detections cannot be converted into confident temperatures. At least
    six independent-ish wavelength groups and a factor-two spectral span are required. No fitting of
    only a narrow Rayleigh-Jeans tail, censored SED or a poor single-blackbody match is reported as a result.
    """
    use, excluded = _valid_points(points)
    result = TemperatureEstimate(n_points=len(use), excluded=excluded, frame_ids=[p.frame_id for p in use])
    result.notes.append(
        f"F_nu in mJy; repeated wavelengths grouped within {CHANNEL_FRAC:.1%}. "
        f"A {FRACTIONAL_FLOOR:.0%} per-channel modelling floor is assumed, not an instrument calibration."
    )
    if not use:
        result.notes.append("No positive source fluxes with finite positive uncertainties and S/N >= 3.")
        return result
    lam, flux, err = _channels(use)
    result.n_channels = len(lam)
    result.wavelength_range_um = float(lam.min()), float(lam.max())
    if len(lam) < MIN_CHANNELS or lam.max() / lam.min() < MIN_SPAN:
        result.notes.append("Need >= 6 wavelength groups and >= 2x wavelength span; no extrapolated temperature.")
        return result
    if sum(excluded.values()) > len(points) * 0.2:
        result.status = "censored_spectrum"
        result.notes.append("More than 20% of supplied points lack usable flux/error; detection-selected fit withheld.")
        return result
    temperatures = np.geomspace(*TEMPERATURE_BOUNDS_K, 4097)
    model = planck_fnu_shape(lam[None, :], temperatures[:, None])
    w = 1 / err**2
    scale = (model @ (flux * w)) / (model**2 @ w)
    chi2 = np.sum(((flux - model * scale[:, None]) / err) ** 2, axis=1)
    best = int(np.argmin(chi2))
    result.reduced_chi2 = float(chi2[best] / (len(lam) - 2))
    if result.reduced_chi2 > 5:
        result.status = "poor_fit"
        result.notes.append("Single blackbody rejected: reduced chi-square > 5, including the declared floor.")
        return result
    threshold = chi2[best] + max(1.0, result.reduced_chi2)
    inside = np.flatnonzero(chi2 <= threshold)
    lo, hi = int(inside[0]), int(inside[-1])
    # A closed interval is essential: a best fit near a grid boundary is not a measurement.
    if lo == 0 or hi == len(temperatures) - 1:
        result.status = "unconstrained"
        result.notes.append("Temperature interval reaches the 300-20000 K search boundary; no finite result reported.")
        return result
    lower = float(np.interp(threshold, chi2[lo - 1 : lo + 1][::-1], temperatures[lo - 1 : lo + 1][::-1]))
    upper = float(np.interp(threshold, chi2[hi : hi + 2], temperatures[hi : hi + 2]))
    lower = min(lower, float(temperatures[best] * (1 - TEMPERATURE_FLOOR_FRACTION)))
    upper = max(upper, float(temperatures[best] * (1 + TEMPERATURE_FLOOR_FRACTION)))
    if lower <= TEMPERATURE_BOUNDS_K[0] or upper >= TEMPERATURE_BOUNDS_K[1]:
        result.status = "unconstrained"
        result.notes.append(
            "The modelling-floor range reaches a temperature search boundary; no finite result reported."
        )
        return result
    if (upper - lower) / temperatures[best] > 0.5:
        result.status = "unconstrained"
        result.notes.append(
            "Conditional interval exceeds 50% of the fitted temperature; shape is insufficiently constraining."
        )
        return result
    result.status = "ok"
    result.temperature_k = float(temperatures[best])
    result.lower_k, result.upper_k = lower, upper
    result.scale_mjy_at_2um = float(scale[best])
    return result


def color_class(points: Sequence[SpectrumPoint]) -> str:
    """Descriptive F_nu colour, NOT an object/spectral-type classifier or visible RGB.

    Median 4-5 um / 1-2 um source flux: <0.25 blue, <=1 neutral, <4 red, else very-red.
    These are declared display categories (flat F_nu has ratio 1), not empirically calibrated
    class boundaries. Require three wavelength groups spanning each window; otherwise 'unknown'.
    """
    use, excluded = _valid_points(points)
    if not use or sum(excluded.values()) > len(points) * 0.2:
        return "unknown"
    lam, flux, _ = _channels(use)
    short_lam, long_lam = lam[(lam >= 1) & (lam <= 2)], lam[(lam >= 4) & (lam <= 5)]
    short, long = flux[(lam >= 1) & (lam <= 2)], flux[(lam >= 4) & (lam <= 5)]
    if len(short) < 3 or len(long) < 3:
        return "unknown"
    if short_lam.min() > 1.2 or short_lam.max() < 1.8 or long_lam.min() > 4.2 or long_lam.max() < 4.8:
        return "unknown"
    ratio = float(np.median(long) / np.median(short))
    return "blue" if ratio < 0.25 else "neutral" if ratio <= 1 else "red" if ratio < 4 else "very-red"
