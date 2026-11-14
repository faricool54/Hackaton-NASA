"""Link per-frame detections into straight-line tracks (WS2, P0).

Over hours-to-days a solar-system object moves ~linearly on the sky. Typical
rates near opposition (science/motion.py: opposition_rate_arcsec_per_hour):
main belt (2-3 AU) ~25-40"/h (4-6 px/h); Kuiper belt (40 AU) ~3"/h (0.5 px/h);
a Planet-Nine-like body (400-800 AU) ~0.2-0.4"/h (~1 px/day).
Across 6-month survey passes the motion is NOT linear (parallax): link within
one visit window first, then use science/ for cross-pass association.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .sources import Source


@dataclass
class Track:
    sources: list[Source]
    rate_px_per_day: tuple[float, float]  # (dx/dt, dy/dt) in PNG convention
    residual_rms_px: float
    meta: dict = field(default_factory=dict)


def link_tracks(
    sources: list[Source],
    min_detections: int = 3,
    max_rate_px_per_day: float = 200.0,
    tolerance_px: float = 1.0,
) -> list[Track]:
    """Find sets of sources (one per frame, distinct mjd) that fit x(t), y(t) linear.

    TODO(WS2): simple and robust first: for each pair of sources in the first and
    last frame within ``max_rate``, predict positions in middle frames, collect
    matches within ``tolerance_px``, keep tracks with >= min_detections. Remove
    sources that match a static star (present at the same x,y in most frames).
    Later: Hough transform / shift-and-stack for faint slow movers.
    """
    raise NotImplementedError("WS2: link_tracks")
