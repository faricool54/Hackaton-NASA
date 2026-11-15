"""WS2-8: brightness changes seen in the PUBLISHED PNGs of a variable target, per detector at matched wavelength.

Per frame: the target's core on the decoded values (peak and r = 3 px aperture above a local sky ring), how
many of its pixels are white (clipped: the sum is then a LOWER bound) and the size of the white plateau.
SPHEREx measures a different wavelength in every exposure (linear variable filter), so brightness is only
compared between frames of the same detector whose wavelengths at the target agree within
``MATCH_TOLERANCE``. Each pair is checked against the field stars measured the same way in the same two
frames (their median ratio should be ~1). It is a display-level check: the PNGs keep 256 grey levels, the
values come back to +-half a level, and saturated cores were filled for display. Science photometry
(fluxes, errors, flags) comes from the FITS (``imaging/photometry.py``).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace

import numpy as np

from ..detect.difference import MIN_STAR_SNR, find_stars
from .productcheck_data import Astrometry, LoadedField, PublishedFrame
from .productcheck_measure import Aperture, aperture, frame_noise, masked, plateau, robust_sigma, rolloff_top_index

MATCH_TOLERANCE = 0.01  # |dlambda| / lambda for a matched pair (docs/validation/rw-aurigae.md uses < 1 %)
BLINK_MIN_GREY = 10  # peak grey difference a viewer can notice in the blink (~4 % of the grey range)
# Both cores white: the blink can only show the white disc changing size. It also changes with the sub-pixel
# position and the PSF, so only a change of at least this fraction AND this many pixels counts.
BLINK_MIN_DISC_CHANGE = 0.25
BLINK_MIN_DISC_PX = 3
CONTROL_EXCLUDE_PX = 10.0  # field stars this close to the target are not used as controls
MIN_CONTROLS = 3
HYPOTHESIS_TOLERANCE = 0.15  # relative: grey-level quantisation (~6 %/level in the roll-off) + pixel aperture


@dataclass(frozen=True)
class Hypothesis:
    """A brightness ratio stated elsewhere, to confirm or refute on the published PNGs."""

    earlier: str
    later: str
    ratio: float
    source: str


# Ratios to check, from the team's own FITS measurements (not external data).
HYPOTHESES: dict[str, tuple[Hypothesis, ...]] = {
    "rw-aurigae": (
        Hypothesis(
            "2025W36_1A_0233_3D1",
            "2026W37_1A_0234_3D1",
            2.6,
            "docs/validation/rw-aurigae.md: FITS forced photometry r = 3 px, D1 0.7645 -> 0.7712 um, "
            "76.2 -> 197.0 mJy (2.59x)",
        ),
    ),
}


@dataclass(frozen=True)
class CoreLevel:
    frame_id: str
    season: int
    detector: int
    mjd: float
    wavelength_um: float | None
    position: tuple[float, float]
    aperture: Aperture | None
    core_clipped: int  # white pixels within 2.5 px of the target (render.TARGET_RADIUS_PX)
    plateau_area: int  # white pixels connected to the target (0 = none)
    rolloff: bool  # the detector has the build's highlight roll-off (target core unflagged in most frames)
    at_rolloff_top: bool = False  # its single white pixel is the peak that DEFINES the roll-off top (a value)

    @property
    def lower_bound(self) -> bool:
        return self.aperture is not None and self.aperture.lower_bound and not self.at_rolloff_top

    @property
    def status(self) -> str:
        if self.at_rolloff_top:
            return "measured_at_top"
        if self.core_clipped:
            return "clipped_core"
        if self.aperture is None:
            return "no_data"
        return "lower_bound" if self.aperture.lower_bound else "measured"


@dataclass(frozen=True)
class Controls:
    median: float
    scatter: float
    n: int


@dataclass(frozen=True)
class Pair:
    detector: int
    earlier: CoreLevel
    later: CoreLevel
    dlambda_rel: float
    ratio: float | None  # later / earlier aperture sum
    ratio_sigma: float | None
    bound: str  # value | lower | upper | none (a clipped side makes the ratio a bound or undetermined)
    controls: Controls | None
    blink_visible: bool
    blink_note: str

    @property
    def delta_mag(self) -> float | None:
        return None if self.ratio is None or self.ratio <= 0 else -2.5 * math.log10(self.ratio)

    @property
    def relative_ratio(self) -> float | None:
        if self.ratio is None or self.controls is None or self.controls.median <= 0:
            return None
        return self.ratio / self.controls.median


@dataclass(frozen=True)
class HypothesisCheck:
    hypothesis: Hypothesis
    pair: Pair | None
    verdict: str  # confirmed | refuted | undetermined
    note: str


@dataclass(frozen=True)
class VariableResult:
    levels: tuple[CoreLevel, ...]
    pairs: tuple[Pair, ...]
    hypotheses: tuple[HypothesisCheck, ...]


def core_level(loaded: LoadedField, f: PublishedFrame, astrometry: Astrometry | None) -> CoreLevel:
    from .render import TARGET_RADIUS_PX

    x, y = loaded.expected_xy(astrometry, f.mjd)
    sigma = frame_noise(f.values, f.clipped, (x, y, CONTROL_EXCLUDE_PX))
    ap = aperture(f.values, f.decoded.step, f.clipped, f.grey, x, y, sigma)
    yy, xx = np.indices(f.grey.shape)
    core = int((f.clipped & (np.hypot(xx - x, yy - y) <= TARGET_RADIUS_PX)).sum())
    pl = plateau(f.clipped, x, y)
    return CoreLevel(
        f.frame_id,
        f.season,
        f.detector,
        f.mjd,
        f.meta.wavelength_um,
        (x, y),
        ap,
        core,
        0 if pl is None else pl.area,
        f.detector in loaded.rolloff,
    )


def control_ratios(a: PublishedFrame, b: PublishedFrame, target: tuple[float, float]) -> Controls | None:
    """Median and robust scatter of later/earlier r = 3 px sums of unclipped field stars (found on ``a``)."""
    img = masked(a.values, a.clipped)
    sigma = frame_noise(a.values, a.clipped, (*target, CONTROL_EXCLUDE_PX))
    sigma_b = frame_noise(b.values, b.clipped, (*target, CONTROL_EXCLUDE_PX))
    if not (math.isfinite(sigma) and sigma > 0 and math.isfinite(sigma_b)):
        return None
    ratios = []
    for x, y in find_stars(img, sigma, MIN_STAR_SNR, exclude=(*target, CONTROL_EXCLUDE_PX)):
        sa = aperture(a.values, a.decoded.step, a.clipped, a.grey, x, y, sigma)
        sb = aperture(b.values, b.decoded.step, b.clipped, b.grey, x, y, sigma_b)
        if sa is None or sb is None or sa.lower_bound or sb.lower_bound or sa.total <= 0 or sb.total <= 0:
            continue
        ratios.append(sb.total / sa.total)
    if len(ratios) < MIN_CONTROLS:
        return None
    r = np.asarray(ratios)
    return Controls(float(np.median(r)), robust_sigma(r), int(r.size))


def _ratio(a: CoreLevel, b: CoreLevel) -> tuple[float | None, float | None, str]:
    """(later/earlier, sigma, bound); no ratio when either sum is missing or both are lower bounds."""
    if a.aperture is None or b.aperture is None or a.aperture.total <= 0 or b.aperture.total <= 0:
        return None, None, "none"
    if a.lower_bound and b.lower_bound:
        return None, None, "none"  # a ratio of two lower bounds says nothing
    ra, rb = a.aperture, b.aperture
    ratio = rb.total / ra.total
    sigma = ratio * math.hypot(ra.sigma / ra.total, rb.sigma / rb.total)
    bound = {(False, False): "value", (False, True): "lower", (True, False): "upper"}
    return ratio, sigma, bound[(a.lower_bound, b.lower_bound)]


def _blink(a: CoreLevel, b: CoreLevel) -> tuple[bool, str]:
    if a.core_clipped and b.core_clipped and not (a.at_rolloff_top or b.at_rolloff_top):
        change = abs(b.plateau_area - a.plateau_area)
        size = f"white disc {a.plateau_area} -> {b.plateau_area} px"
        if change >= BLINK_MIN_DISC_PX and change >= BLINK_MIN_DISC_CHANGE * max(a.plateau_area, b.plateau_area):
            return True, f"core white in both; only the {size} changes"
        return False, f"core white (clipped) in both; {size}"
    if a.aperture is None or b.aperture is None:
        return False, "no usable pixels at the target in one frame"
    ga, gb = a.aperture.peak_grey, b.aperture.peak_grey
    return abs(gb - ga) >= BLINK_MIN_GREY, f"peak grey {ga} -> {gb}"


def mark_rolloff_tops(levels: list[CoreLevel], rolloff: dict[int, float]) -> list[CoreLevel]:
    """Mark the frame whose white target pixel is AT a detector's roll-off top (``rolloff_top_index``)."""
    from .render import MAX_TOP_OVER_MEDIAN

    out = list(levels)
    for det in rolloff:
        idx = [i for i, c in enumerate(out) if c.detector == det and c.aperture is not None]
        k = rolloff_top_index(
            [out[i].aperture.n_clipped for i in idx], [out[i].aperture.peak for i in idx], MAX_TOP_OVER_MEDIAN
        )
        if k is not None:
            out[idx[k]] = replace(out[idx[k]], at_rolloff_top=True)
    return out


def matched_pairs(loaded: LoadedField, levels: list[CoreLevel]) -> list[Pair]:
    """All cross-season pairs of one detector with |dlambda|/lambda <= MATCH_TOLERANCE (earlier first)."""
    frames = {f.frame_id: f for f in loaded.frames}
    out = []
    ordered = sorted(levels, key=lambda c: (c.detector, c.mjd))
    for i, a in enumerate(ordered):
        for b in ordered[i + 1 :]:
            if b.detector != a.detector or b.season == a.season or not a.wavelength_um or not b.wavelength_um:
                continue
            dl = abs(b.wavelength_um - a.wavelength_um) / a.wavelength_um
            if dl > MATCH_TOLERANCE:
                continue
            ratio, sigma, bound = _ratio(a, b)
            visible, note = _blink(a, b)
            controls = control_ratios(frames[a.frame_id], frames[b.frame_id], a.position)
            out.append(Pair(a.detector, a, b, dl, ratio, sigma, bound, controls, visible, note))
    return out


def check_hypothesis(h: Hypothesis, levels: list[CoreLevel], pairs: list[Pair]) -> HypothesisCheck:
    pair = next((p for p in pairs if p.earlier.frame_id == h.earlier and p.later.frame_id == h.later), None)
    if pair is None:
        known = {c.frame_id for c in levels}
        missing = [fid for fid in (h.earlier, h.later) if fid not in known]
        why = f"frame(s) not published: {', '.join(missing)}" if missing else "not a matched-wavelength pair"
        return HypothesisCheck(h, None, "undetermined", why)
    if pair.ratio is None or pair.bound == "none":
        return HypothesisCheck(h, pair, "undetermined", "the target is clipped (white) in both frames")
    r = pair.ratio
    tol = max(HYPOTHESIS_TOLERANCE * h.ratio, 3 * (pair.ratio_sigma or 0.0))
    c = pair.controls
    stable = c is not None and abs(c.median - 1.0) <= HYPOTHESIS_TOLERANCE
    ctrl = "no field-star control" if c is None else f"field stars {c.median:.3f} +- {c.scatter:.3f} (n={c.n})"
    if pair.bound == "value":
        agrees = abs(r - h.ratio) <= tol
        verdict = "refuted" if not agrees else ("confirmed" if stable else "undetermined")
        return HypothesisCheck(h, pair, verdict, f"ratio {r:.2f} vs {h.ratio:.2f} +- {tol:.2f}; {ctrl}")
    if pair.bound == "lower":
        verdict = "refuted" if r > h.ratio + tol else "undetermined"
        return HypothesisCheck(h, pair, verdict, f"ratio >= {r:.2f} (later frame clipped); {ctrl}")
    verdict = "refuted" if r < h.ratio - tol else "undetermined"
    return HypothesisCheck(h, pair, verdict, f"ratio <= {r:.2f} (earlier frame clipped); {ctrl}")


def analyse_variable(loaded: LoadedField, astrometry: Astrometry | None) -> VariableResult:
    ordered = sorted(loaded.frames, key=lambda f: (f.detector, f.mjd))
    levels = mark_rolloff_tops([core_level(loaded, f, astrometry) for f in ordered], loaded.rolloff)
    pairs = matched_pairs(loaded, levels)
    checks = tuple(check_hypothesis(h, levels, pairs) for h in HYPOTHESES.get(loaded.field.id, ()))
    return VariableResult(tuple(levels), tuple(pairs), checks)
