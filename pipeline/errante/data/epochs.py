"""Group SPHEREx frames in time and pick well-spread epochs (WS1-6, R02/R05).

SPHEREx revisits a point of the sky in *visits* (a few frames within hours, often all six detectors)
and, about every six months, in *seasons* (one survey pass, weeks long). Barnard's Star, verified live
2026-11-14: 358 frames in 3 seasons (MJD ~60903-60949, 61110-61165, 61269-61306).

Taking the first N frames of a time-sorted search puts every frame in the first season, so a
proper-motion star does not move. :func:`select_per_season` picks frames spread over every
season x detector instead (meant to replace the ``max_frames`` cut in ``build.py``; WS2 adopts it).

Every function accepts plain MJDs or objects with an ``mjd`` attribute (``FrameRef``, ``Frame``) and
returns the original items.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from typing import Any, TypeVar

T = TypeVar("T")

VISIT_GAP_HOURS = 6.0
SEASON_GAP_DAYS = 30.0


def mjd_of(item: Any) -> float:
    """MJD of a number or of an object with an ``mjd`` attribute."""
    return float(item.mjd) if hasattr(item, "mjd") else float(item)


def group_by_gap(items: Iterable[T], gap_days: float) -> list[list[T]]:
    """Sort by MJD and split wherever two consecutive items are more than ``gap_days`` apart."""
    if gap_days <= 0:
        raise ValueError(f"gap must be positive, got {gap_days}")
    ordered = sorted(items, key=mjd_of)
    groups: list[list[T]] = []
    last = None
    for item in ordered:
        t = mjd_of(item)
        if last is None or t - last > gap_days:
            groups.append([])
        groups[-1].append(item)
        last = t
    return groups


def group_visits(items: Iterable[T], gap_hours: float = VISIT_GAP_HOURS) -> list[list[T]]:
    """Visits: runs of frames with no gap longer than ``gap_hours``."""
    return group_by_gap(items, gap_hours / 24.0)


def group_seasons(items: Iterable[T], gap_days: float = SEASON_GAP_DAYS) -> list[list[T]]:
    """Seasons (survey passes): runs of frames with no gap longer than ``gap_days``."""
    return group_by_gap(items, gap_days)


def _spread_indices(n: int, k: int) -> list[int]:
    """``k`` distinct indices in ``range(n)`` evenly spread, always including both ends when k >= 2."""
    if k >= n:
        return list(range(n))
    if k == 1:
        return [n // 2]
    return sorted({round(i * (n - 1) / (k - 1)) for i in range(k)})


def _pick_spread(frames: Sequence[T], k: int, visit_gap_hours: float) -> list[T]:
    """Up to ``k`` frames spread over time, at most one per visit until every visit has one."""
    if k <= 0:
        return []
    visits = group_visits(frames, visit_gap_hours)
    if k <= len(visits):
        # One frame per chosen visit: the one closest to the visit's middle.
        return [v[len(v) // 2] for v in (visits[i] for i in _spread_indices(len(visits), k))]
    # More slots than visits: take every visit, then fill round-robin with the remaining frames.
    picked = [v[len(v) // 2] for v in visits]
    rest = [[f for j, f in enumerate(v) if j != len(v) // 2] for v in visits]
    while len(picked) < k and any(rest):
        for r in rest:
            if r and len(picked) < k:
                picked.append(r.pop(len(r) // 2))
    return sorted(picked, key=mjd_of)


def select_per_season(
    frames: Iterable[T],
    per_detector: int = 2,
    *,
    season_gap_days: float = SEASON_GAP_DAYS,
    visit_gap_hours: float = VISIT_GAP_HOURS,
) -> list[T]:
    """Pick up to ``per_detector`` frames for every season x detector, spread over each season.

    Frames need ``mjd`` and ``detector`` attributes (e.g. ``FrameRef``). Within a season and detector
    the picks go to different visits, evenly spaced from the first to the last visit. Returns the
    selection sorted by MJD; a season/detector with fewer frames contributes all of them.
    """
    if per_detector < 1:
        raise ValueError(f"per_detector must be >= 1, got {per_detector}")
    selected: list[T] = []
    for season in group_seasons(frames, season_gap_days):
        by_det: dict[int, list[T]] = {}
        for f in season:
            by_det.setdefault(int(f.detector), []).append(f)
        for det in sorted(by_det):
            selected.extend(_pick_spread(by_det[det], per_detector, visit_gap_hours))
    return sorted(selected, key=lambda f: (mjd_of(f), int(f.detector)))


def season_summary(items: Iterable[T], gap_days: float = SEASON_GAP_DAYS) -> list[dict]:
    """One dict per season: ``{"mjd_min", "mjd_max", "n", "visits"}`` (for CLI/evidence reports)."""
    out = []
    for season in group_seasons(items, gap_days):
        mjds = [mjd_of(x) for x in season]
        out.append({"mjd_min": min(mjds), "mjd_max": max(mjds), "n": len(season), "visits": len(group_visits(season))})
    return out
