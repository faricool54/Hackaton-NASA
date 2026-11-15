"""WS2-8: proper motion seen in the PUBLISHED PNGs: target centroids per season x detector and season shifts.

Per frame, two display-level position estimates of the target near its expected grid position:

- ``core``: flux-weighted centroid in a PSF-sized 5x5 box of the decoded values. A box that holds a white
  (clipped) pixel is refused: a saturated or clipped core has no usable flux weights.
- ``plateau``: for those refused frames, the centroid of the connected white region at the target, i.e. an
  isophote at the display limit. It follows the star, but its shape depends on saturation, the display fill
  of NaN cores and the 1-px quantisation: indicative only.

Per (season, detector) the core centroid is measured again on the mean image of the group's frames (more
signal for faint targets), and the plateau estimate is the mean of the frame plateaus. A season shift is
taken per detector (same detector in both seasons, so a detector-specific offset cancels) and averaged over
detectors; its uncertainty is the scatter between detectors / sqrt(n), or with one detector the scatter of
its frames. Optionally each group is corrected by the median field-star offset of its frames measured on
the same PNGs (``registration``). The expected shift is the catalog proper motion from ``fields.toml`` over
the same mean epochs, parallax ignored.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

import numpy as np

from .productcheck_data import Astrometry, LoadedField, PublishedFrame, groups
from .productcheck_measure import Centroid, Plateau, disc, flux_centroid, frame_noise, plateau, rolloff_top_index

MIN_TARGET_SNR = 5.0  # peak above the local sky, in pixel sigmas (imaging.register.FRAME_STAR_SNR)
MAX_TARGET_OFFSET_PX = 1.5  # a centroid further than this from the expected position is another source
NOISE_EXCLUDE_PX = 8.0  # the target's halo is left out of the frame noise
ESTIMATORS = ("core", "plateau")


@dataclass(frozen=True)
class FramePosition:
    frame_id: str
    season: int
    detector: int
    mjd: float
    expected: tuple[float, float]
    core: Centroid
    plateau: Plateau | None
    registration: tuple[float, float] | None  # field-star offset of this frame on the PNGs (dx, dy) [px]
    at_rolloff_top: bool = False  # its one white core pixel is the roll-off top: used as a value


@dataclass(frozen=True)
class GroupPosition:
    season: int
    detector: int
    frame_ids: tuple[str, ...]
    mjd: float  # mean of the frames
    expected: tuple[float, float]
    coadd: Centroid  # core centroid on the mean image of the group
    core_frames: tuple[tuple[float, float], ...]  # per-frame core centroids that succeeded
    plateaus: tuple[tuple[float, float], ...]  # per-frame plateau centroids
    registration: tuple[float, float] | None  # mean field-star offset of the checked frames

    def position(self, estimator: str) -> tuple[float, float] | None:
        if estimator == "core":
            return (self.coadd.x, self.coadd.y) if self.coadd.status == "ok" else None
        return tuple(np.mean(self.plateaus, axis=0)) if self.plateaus else None

    def frame_scatter(self, estimator: str) -> tuple[float, float, int]:
        pts = np.asarray(self.core_frames if estimator == "core" else self.plateaus, dtype=float)
        if len(pts) < 2:
            return float("nan"), float("nan"), len(pts)
        sd = pts.std(axis=0, ddof=1)
        return float(sd[0]), float(sd[1]), len(pts)


@dataclass(frozen=True)
class DetectorShift:
    detector: int
    dx: float
    dy: float
    expected_dx: float | None
    expected_dy: float | None
    dt_days: float


@dataclass(frozen=True)
class SeasonShift:
    estimator: str
    corrected: bool  # registration-corrected
    season_a: int
    season_b: int
    detectors: tuple[DetectorShift, ...]
    dx: float
    dy: float
    sigma_x: float | None
    sigma_y: float | None
    uncertainty_from: str  # detectors | frames | none
    expected_dx: float | None
    expected_dy: float | None

    @property
    def total_px(self) -> float:
        return math.hypot(self.dx, self.dy)

    @property
    def sigma_px(self) -> float | None:
        if self.sigma_x is None or self.sigma_y is None or self.total_px == 0:
            return None
        return math.hypot(self.dx * self.sigma_x, self.dy * self.sigma_y) / self.total_px

    @property
    def expected_px(self) -> float | None:
        if self.expected_dx is None or self.expected_dy is None:
            return None
        return math.hypot(self.expected_dx, self.expected_dy)

    @property
    def residual_px(self) -> float | None:
        if self.expected_dx is None or self.expected_dy is None:
            return None
        return math.hypot(self.dx - self.expected_dx, self.dy - self.expected_dy)

    @property
    def residual_sigma(self) -> float | None:
        """(measured - expected) in units of the per-axis uncertainty, combined in 2-D."""
        if self.expected_dx is None or self.expected_dy is None or not self.sigma_x or not self.sigma_y:
            return None
        return math.hypot((self.dx - self.expected_dx) / self.sigma_x, (self.dy - self.expected_dy) / self.sigma_y)


def position_angle(dx: float, dy: float) -> float:
    """PA (deg, east of north) of a grid shift: PNG +x = west, +y = south."""
    return math.degrees(math.atan2(-dx, -dy)) % 360.0


@dataclass(frozen=True)
class MotionResult:
    target_detectors: tuple[int, ...]
    frames: tuple[FramePosition, ...]
    groups: tuple[GroupPosition, ...]
    shifts: tuple[SeasonShift, ...]
    other_shifts: tuple[SeasonShift, ...] = ()  # same, over the detectors where the target is NOT seen (control)


def _core_peak(f: PublishedFrame, core: np.ndarray) -> float:
    values = f.values[core & np.isfinite(f.values)]
    finite = f.values[np.isfinite(f.values)]
    return float(values.max() - np.median(finite)) if values.size and finite.size else float("nan")


def rolloff_top_masks(loaded: LoadedField, astrometry: Astrometry | None) -> dict[str, np.ndarray]:
    """frame_id -> white mask without the target's roll-off-top pixel, for the frames ``rolloff_top_index`` picks."""
    from .render import MAX_TOP_OVER_MEDIAN, TARGET_RADIUS_PX

    out = {}
    for det in loaded.rolloff:
        frames = [f for f in loaded.frames if f.detector == det]
        cores = [disc(loaded.shape, *loaded.expected_xy(astrometry, f.mjd), TARGET_RADIUS_PX) for f in frames]
        counts = [int((f.clipped & c).sum()) for f, c in zip(frames, cores, strict=True)]
        peaks = [_core_peak(f, c) for f, c in zip(frames, cores, strict=True)]
        k = rolloff_top_index(counts, peaks, MAX_TOP_OVER_MEDIAN)
        if k is not None:
            out[frames[k].frame_id] = frames[k].clipped & ~cores[k]
    return out


def _frame_position(
    loaded: LoadedField,
    f: PublishedFrame,
    astrometry: Astrometry | None,
    reg: tuple[float, float] | None,
    clipped: np.ndarray,
    at_top: bool,
) -> FramePosition:
    ex, ey = loaded.expected_xy(astrometry, f.mjd)
    sigma = frame_noise(f.values, clipped, (ex, ey, NOISE_EXCLUDE_PX))
    core = _on_target(flux_centroid(f.values, clipped, ex, ey, sigma, MIN_TARGET_SNR), ex, ey)
    pl = plateau(clipped, ex, ey) if core.status == "clipped" else None
    return FramePosition(f.frame_id, f.season, f.detector, f.mjd, (ex, ey), core, pl, reg, at_top)


def _on_target(c: Centroid, ex: float, ey: float) -> Centroid:
    if c.status == "ok" and math.hypot(c.x - ex, c.y - ey) > MAX_TARGET_OFFSET_PX:
        return Centroid(None, None, "off_target", c.peak_snr)
    return c


def _mean_image(frames: Sequence[PublishedFrame], masks: Mapping[str, np.ndarray]) -> tuple[np.ndarray, np.ndarray]:
    stack = np.stack([f.values for f in frames])
    clipped = np.any(np.stack([masks[f.frame_id] for f in frames]), axis=0)
    return stack.mean(axis=0), clipped  # NaN where any frame has no data


def _group_position(
    loaded: LoadedField,
    members: list[PublishedFrame],
    positions: dict[str, FramePosition],
    astrometry: Astrometry | None,
    masks: Mapping[str, np.ndarray],
) -> GroupPosition:
    f0 = members[0]
    mjd = float(np.mean([f.mjd for f in members]))
    ex, ey = loaded.expected_xy(astrometry, mjd)
    mean, clipped = _mean_image(members, masks)
    sigma = frame_noise(mean, clipped, (ex, ey, NOISE_EXCLUDE_PX))
    coadd = _on_target(flux_centroid(mean, clipped, ex, ey, sigma, MIN_TARGET_SNR), ex, ey)
    fp = [positions[f.frame_id] for f in members]
    regs = [p.registration for p in fp if p.registration is not None]
    return GroupPosition(
        season=f0.season,
        detector=f0.detector,
        frame_ids=tuple(f.frame_id for f in members),
        mjd=mjd,
        expected=(ex, ey),
        coadd=coadd,
        core_frames=tuple((p.core.x, p.core.y) for p in fp if p.core.status == "ok"),
        plateaus=tuple((p.plateau.x, p.plateau.y) for p in fp if p.plateau is not None),
        registration=tuple(np.mean(regs, axis=0)) if regs else None,
    )


def _detector_shift(
    a: GroupPosition,
    b: GroupPosition,
    estimator: str,
    corrected: bool,
    loaded: LoadedField,
    astrometry: Astrometry | None,
) -> DetectorShift | None:
    pa, pb = a.position(estimator), b.position(estimator)
    if pa is None or pb is None or (corrected and (a.registration is None or b.registration is None)):
        return None
    dx, dy = pb[0] - pa[0], pb[1] - pa[1]
    if corrected:
        dx -= b.registration[0] - a.registration[0]
        dy -= b.registration[1] - a.registration[1]
    if astrometry is None:
        return DetectorShift(a.detector, dx, dy, None, None, b.mjd - a.mjd)
    xa, ya = loaded.expected_xy(astrometry, a.mjd)
    xb, yb = loaded.expected_xy(astrometry, b.mjd)
    return DetectorShift(a.detector, dx, dy, xb - xa, yb - ya, b.mjd - a.mjd)


def _combine(
    per: list[DetectorShift], a: list[GroupPosition], b: list[GroupPosition], estimator: str
) -> tuple[float, float, float | None, float | None, str]:
    """(dx, dy, sigma_x, sigma_y, source): mean over detectors; scatter/sqrt(n), or frame scatter for one."""
    d = np.array([(s.dx, s.dy) for s in per])
    mean = d.mean(axis=0)
    if len(per) >= 2:
        se = d.std(axis=0, ddof=1) / math.sqrt(len(per))
        return float(mean[0]), float(mean[1]), float(se[0]), float(se[1]), "detectors"
    sa, sb = a[0].frame_scatter(estimator), b[0].frame_scatter(estimator)
    if sa[2] >= 2 and sb[2] >= 2:
        sx = math.sqrt(sa[0] ** 2 / sa[2] + sb[0] ** 2 / sb[2])
        sy = math.sqrt(sa[1] ** 2 / sa[2] + sb[1] ** 2 / sb[2])
        return float(mean[0]), float(mean[1]), sx, sy, "frames"
    return float(mean[0]), float(mean[1]), None, None, "none"


def season_shifts(
    loaded: LoadedField, grouped: Sequence[GroupPosition], detectors: Sequence[int], astrometry: Astrometry | None
) -> list[SeasonShift]:
    """Every season pair (a < b) x estimator x (raw, registration-corrected) with >= 1 common detector."""
    by_key = {(g.season, g.detector): g for g in grouped if g.detector in detectors}
    seasons = sorted({s for s, _ in by_key})
    out = []
    for i, sa in enumerate(seasons):
        for sb in seasons[i + 1 :]:
            common = sorted(d for s, d in by_key if s == sa and (sb, d) in by_key)
            for estimator in ESTIMATORS:
                for corrected in (False, True):
                    shift = _pair(loaded, by_key, sa, sb, common, estimator, corrected, astrometry)
                    if shift is not None:
                        out.append(shift)
    return out


def _pair(
    loaded: LoadedField,
    by_key: Mapping[tuple[int, int], GroupPosition],
    sa: int,
    sb: int,
    common: Sequence[int],
    estimator: str,
    corrected: bool,
    astrometry: Astrometry | None,
) -> SeasonShift | None:
    per, ga, gb = [], [], []
    for d in common:
        s = _detector_shift(by_key[(sa, d)], by_key[(sb, d)], estimator, corrected, loaded, astrometry)
        if s is not None:
            per.append(s)
            ga.append(by_key[(sa, d)])
            gb.append(by_key[(sb, d)])
    if not per:
        return None
    dx, dy, sx, sy, source = _combine(per, ga, gb, estimator)
    exp = [(s.expected_dx, s.expected_dy) for s in per if s.expected_dx is not None]
    ex, ey = tuple(np.mean(exp, axis=0)) if exp else (None, None)
    return SeasonShift(estimator, corrected, sa, sb, tuple(per), dx, dy, sx, sy, source, ex, ey)


def analyse_motion(
    loaded: LoadedField,
    astrometry: Astrometry | None,
    registration: Mapping[str, tuple[float, float] | None],
    target_detectors: Sequence[int] | None = None,
) -> MotionResult:
    """Centroids per frame and per (season, detector), and season shifts over ``target_detectors`` (all).

    With ``target_detectors`` a subset, the other detectors get their own shifts (``other_shifts``): a control
    that shows what the source at the target position does where the target itself is not seen.
    """
    tops = rolloff_top_masks(loaded, astrometry)
    masks = {f.frame_id: tops.get(f.frame_id, f.clipped) for f in loaded.frames}
    positions = {
        f.frame_id: _frame_position(
            loaded, f, astrometry, registration.get(f.frame_id), masks[f.frame_id], f.frame_id in tops
        )
        for f in loaded.frames
    }
    grouped = [_group_position(loaded, m, positions, astrometry, masks) for m in groups(loaded.frames).values()]
    present = {f.detector for f in loaded.frames}
    detectors = tuple(sorted(target_detectors or present))
    others = tuple(sorted(present - set(detectors)))
    shifts = season_shifts(loaded, grouped, detectors, astrometry)
    other = season_shifts(loaded, grouped, others, astrometry) if others else []
    ordered = tuple(sorted(positions.values(), key=lambda p: (p.season, p.detector, p.mjd)))
    return MotionResult(detectors, ordered, tuple(grouped), tuple(shifts), tuple(other))
