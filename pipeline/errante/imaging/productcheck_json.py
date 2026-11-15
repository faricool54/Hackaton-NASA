"""WS2-8: JSON-ready records of the product check (``report.json``; ``report.md`` is rendered from them)."""

from __future__ import annotations

import math
from collections.abc import Sequence

import numpy as np

from .productcheck_data import Astrometry, LoadedField
from .productcheck_motion import FramePosition, GroupPosition, MotionResult, SeasonShift, position_angle
from .productcheck_variable import CoreLevel, HypothesisCheck, Pair, VariableResult


def rounded(x: float | None, nd: int = 3) -> float | None:
    """Rounded float for JSON; None for None/NaN/inf."""
    if x is None:
        return None
    x = float(x)
    return round(x, nd) if math.isfinite(x) else None


def _attr(obj: object | None, name: str, nd: int | None = 3):
    """``obj.name`` (rounded when ``nd``), or None when ``obj`` is None."""
    if obj is None:
        return None
    value = getattr(obj, name)
    return rounded(value, nd) if nd is not None else value


def shift_json(s: SeasonShift, scale: float) -> dict:
    exp, sig = s.expected_px, s.sigma_px
    return {
        "estimator": s.estimator,
        "registration_corrected": s.corrected,
        "season_a": s.season_a,
        "season_b": s.season_b,
        "dt_days": rounded(float(np.mean([d.dt_days for d in s.detectors])), 1),
        "detectors": [d.detector for d in s.detectors],
        "per_detector": [{"detector": d.detector, "dx_px": rounded(d.dx), "dy_px": rounded(d.dy)} for d in s.detectors],
        "dx_px": rounded(s.dx),
        "dy_px": rounded(s.dy),
        "shift_px": rounded(s.total_px),
        "sigma_px": rounded(sig),
        "shift_arcsec": rounded(s.total_px * scale, 2),
        "sigma_arcsec": rounded(None if sig is None else sig * scale, 2),
        "pa_deg": rounded(position_angle(s.dx, s.dy), 1),
        "uncertainty_from": s.uncertainty_from,
        "expected_px": rounded(exp),
        "expected_arcsec": rounded(None if exp is None else exp * scale, 2),
        "expected_pa_deg": rounded(None if exp is None else position_angle(s.expected_dx, s.expected_dy), 1),
        "residual_px": rounded(s.residual_px),
        "residual_sigma": rounded(s.residual_sigma, 1),
    }


def headline_shift(shifts: Sequence[dict]) -> dict | None:
    """The reported shift: core estimator if any, raw (uncorrected), longest baseline, most detectors."""
    raw = [s for s in shifts if not s["registration_corrected"]]
    if not raw:
        return None
    best = "core" if any(s["estimator"] == "core" for s in raw) else "plateau"
    pool = [s for s in raw if s["estimator"] == best]
    return max(pool, key=lambda s: (s["dt_days"] or 0.0, len(s["detectors"])))


def _frame_json(p: FramePosition) -> dict:
    reg = p.registration
    return {
        "frame_id": p.frame_id,
        "season": p.season,
        "detector": p.detector,
        "mjd": rounded(p.mjd, 4),
        "expected_x": rounded(p.expected[0]),
        "expected_y": rounded(p.expected[1]),
        "core_status": p.core.status,
        "core_x": rounded(p.core.x),
        "core_y": rounded(p.core.y),
        "peak_snr": rounded(p.core.peak_snr, 1),
        "plateau_x": _attr(p.plateau, "x"),
        "plateau_y": _attr(p.plateau, "y"),
        "plateau_area": _attr(p.plateau, "area", None),
        "registration_dx": None if reg is None else rounded(reg[0]),
        "registration_dy": None if reg is None else rounded(reg[1]),
        "at_rolloff_top": p.at_rolloff_top,
    }


def _group_json(g: GroupPosition) -> dict:
    pl = g.position("plateau")
    return {
        "season": g.season,
        "detector": g.detector,
        "n_frames": len(g.frame_ids),
        "mjd": rounded(g.mjd, 3),
        "expected_x": rounded(g.expected[0]),
        "expected_y": rounded(g.expected[1]),
        "coadd_status": g.coadd.status,
        "coadd_x": rounded(g.coadd.x),
        "coadd_y": rounded(g.coadd.y),
        "coadd_snr": rounded(g.coadd.peak_snr, 1),
        "n_core_frames": len(g.core_frames),
        "n_plateaus": len(g.plateaus),
        "plateau_x": None if pl is None else rounded(pl[0]),
        "plateau_y": None if pl is None else rounded(pl[1]),
    }


def motion_json(m: MotionResult, loaded: LoadedField, astrometry: Astrometry | None, note: str | None) -> dict:
    scale = loaded.field.grid.pixel_scale_arcsec
    on_target = [p for p in m.frames if p.detector in m.target_detectors]
    statuses = [p.core.status for p in on_target]
    shifts = [shift_json(s, scale) for s in m.shifts]
    plx = None if astrometry is None or astrometry.parallax_mas is None else astrometry.parallax_mas / 1000 / scale
    return {
        "target_detectors": list(m.target_detectors),
        "target_detector_note": note,
        "pixel_scale_arcsec": scale,
        "expected_available": astrometry is not None,
        "parallax_amplitude_px": rounded(plx),
        "parallax_max_difference_px": rounded(None if plx is None else 2 * plx),
        "core_status_counts": {s: statuses.count(s) for s in sorted(set(statuses))},
        "plateau_frames": sum(p.plateau is not None for p in on_target),
        "rolloff_top_frames": sorted(p.frame_id for p in on_target if p.at_rolloff_top),
        "frames": [_frame_json(p) for p in m.frames],
        "groups": [_group_json(g) for g in m.groups],
        "shifts": shifts,
        "other_detector_shifts": [shift_json(s, scale) for s in m.other_shifts if not s.corrected],
        "headline": headline_shift(shifts),
    }


def _level_json(c: CoreLevel) -> dict:
    a = c.aperture
    return {
        "frame_id": c.frame_id,
        "season": c.season,
        "detector": c.detector,
        "mjd": rounded(c.mjd, 4),
        "wavelength_um": rounded(c.wavelength_um, 4),
        "status": c.status,
        "aperture": _attr(a, "total", 2),
        "aperture_sigma": _attr(a, "sigma", 2),
        "peak": _attr(a, "peak", 2),
        "peak_grey": _attr(a, "peak_grey", None),
        "n_clipped": _attr(a, "n_clipped", None),
        "core_clipped": c.core_clipped,
        "plateau_area": c.plateau_area,
        "flat_top": _attr(a, "flat_top", None),
        "rolloff": c.rolloff,
        "at_rolloff_top": c.at_rolloff_top,
    }


def _pair_json(p: Pair) -> dict:
    return {
        "detector": p.detector,
        "earlier": p.earlier.frame_id,
        "later": p.later.frame_id,
        "season_a": p.earlier.season,
        "season_b": p.later.season,
        "wavelength_a_um": rounded(p.earlier.wavelength_um, 4),
        "wavelength_b_um": rounded(p.later.wavelength_um, 4),
        "dlambda_pct": rounded(100 * p.dlambda_rel, 2),
        "ratio": rounded(p.ratio),
        "ratio_sigma": rounded(p.ratio_sigma),
        "bound": p.bound,
        "delta_mag": rounded(p.delta_mag),
        "controls_median": _attr(p.controls, "median"),
        "controls_scatter": _attr(p.controls, "scatter"),
        "controls_n": _attr(p.controls, "n", None),
        "relative_ratio": rounded(p.relative_ratio),
        "blink_visible": p.blink_visible,
        "blink_note": p.blink_note,
    }


def _per_detector_json(v: VariableResult, d: int) -> dict:
    lv = [c for c in v.levels if c.detector == d]
    pr = [p for p in v.pairs if p.detector == d]
    return {
        "detector": d,
        "n_frames": len(lv),
        "clipped_core": sum(c.status == "clipped_core" for c in lv),
        "rolloff": any(c.rolloff for c in lv),
        "n_pairs": len(pr),
        "pairs_with_value": sum(p.bound == "value" for p in pr),
        "blink_visible_pairs": sum(p.blink_visible for p in pr),
    }


def _hypothesis_json(h: HypothesisCheck) -> dict:
    return {
        "earlier": h.hypothesis.earlier,
        "later": h.hypothesis.later,
        "expected_ratio": h.hypothesis.ratio,
        "source": h.hypothesis.source,
        "verdict": h.verdict,
        "note": h.note,
        "ratio": _attr(h.pair, "ratio"),
    }


def variable_json(v: VariableResult) -> dict:
    return {
        "levels": [_level_json(c) for c in v.levels],
        "pairs": [_pair_json(p) for p in v.pairs],
        "per_detector": [_per_detector_json(v, d) for d in sorted({c.detector for c in v.levels})],
        "hypotheses": [_hypothesis_json(h) for h in v.hypotheses],
    }


def astrometry_json(a: Astrometry | None) -> dict | None:
    if a is None:
        return None
    return {
        "ra_j2000_deg": a.ra_deg,
        "dec_j2000_deg": a.dec_deg,
        "pm_ra_cosdec_mas_yr": a.pm_ra_cosdec_mas_yr,
        "pm_dec_mas_yr": a.pm_dec_mas_yr,
        "parallax_mas": a.parallax_mas,
        "source": a.source,
        "total_pm_arcsec_yr": rounded(a.total_pm_arcsec_yr, 3),
    }
