"""WS2: per-frame registration check — find frames whose archive WCS puts the sky at the wrong place.

Every frame reaches the common grid through its own WCS. If that WCS is wrong, every star of the frame lands
at a shifted position and the blink shows a false jump of the whole field. This happens in the archive: in
2026W38_1A_0162_3D6 (RW Aurigae field) four Gaia stars sit 1.21-1.36 px off in x although the header says
``FINAST = 0`` and ``ASTRONETSOLVED = True`` (docs/validation/rw-aurigae.md).

The check needs no catalog. Per detector (same PSF, same stars), the field stars are found on the per-pixel
median of the detector's frames; each star's centroid is measured in every frame; the star's consensus
position is the median of those centroids, so one bad frame cannot move it; and a frame's registration error
is the median, over its stars, of (centroid - consensus). The target at the field centre (it may move or
saturate) is left out with the same halo-sized circle as the season comparison.
"""

from __future__ import annotations

import math
import warnings
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

import numpy as np

from ..detect.difference import find_stars, local_sky
from .compare import target_exclusion

MAX_OFFSET_PX = 0.5  # a frame whose stars are further than this from their consensus position is misregistered
MIN_FRAMES = 3  # frames of one detector needed for a consensus a single bad frame cannot pull
MIN_STARS = 3  # stars measured in a frame (and in MIN_FRAMES frames overall) to judge it
STAR_SNR = 15.0  # reference star peak above its local sky, in robust sigmas of the reference
MAX_STARS = 25  # brightest reference stars used
CENTROID_HALF = 2  # 5x5 px centroid box (SPHEREx PSF FWHM ~1.2 px)
CENTROID_ITERATIONS = 2  # recentre the box once, so a 1-2 px shift is not clipped by the box edge
MAD_TO_SIGMA = 1.4826


class _GridFrame(Protocol):
    frame_id: str
    detector: int
    data: np.ndarray
    bad: np.ndarray


@dataclass(frozen=True)
class Registration:
    """Registration error of one frame on the grid, relative to the other frames of its detector [px]."""

    dx: float  # +x = towards the right of the PNG (west)
    dy: float  # +y = towards the bottom of the PNG (south)
    n_stars: int
    scatter: float  # robust sigma of the per-star offsets (both axes pooled)

    @property
    def offset(self) -> float:
        return math.hypot(self.dx, self.dy)


def _robust_sigma(values: np.ndarray) -> float:
    values = values[np.isfinite(values)]
    if values.size == 0:
        return float("nan")
    return float(MAD_TO_SIGMA * np.median(np.abs(values - np.median(values))))


def _usable(f: _GridFrame) -> np.ndarray:
    """Frame data with bad pixels (saturated cores, defects repaired for display only) set to NaN."""
    data = np.asarray(f.data, dtype=np.float64)
    bad = np.asarray(f.bad, dtype=bool) if f.bad is not None else np.zeros(data.shape, bool)
    return np.where(bad | ~np.isfinite(data), np.nan, data)


def centroid(img: np.ndarray, x: int, y: int) -> tuple[float, float] | None:
    """Flux-weighted centroid (x, y) above the local sky in a 5x5 box near (x, y); None if not measurable.

    The box is recentred once on the first estimate. Not measurable: the box leaves the image, holds a NaN
    (bad pixel, no data), the local sky ring is unusable, or no flux is above the sky.
    """
    ny, nx = img.shape
    h = CENTROID_HALF
    cx, cy = float(x), float(y)
    for _ in range(CENTROID_ITERATIONS):
        ix, iy = int(round(cx)), int(round(cy))
        if not (h <= ix < nx - h and h <= iy < ny - h):
            return None
        box = img[iy - h : iy + h + 1, ix - h : ix + h + 1]
        if not np.isfinite(box).all():
            return None
        sky = local_sky(img, ix, iy)
        if not math.isfinite(sky):
            return None
        w = np.clip(box - sky, 0.0, None)
        total = float(w.sum())
        if total <= 0:
            return None
        dy, dx = np.mgrid[-h : h + 1, -h : h + 1]
        cx, cy = ix + float((w * dx).sum()) / total, iy + float((w * dy).sum()) / total
    return cx, cy


def _reference_stars(stack: np.ndarray) -> list[tuple[int, int]]:
    """Brightest isolated field stars on the per-pixel median of ``stack`` (target circle left out)."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)  # all-NaN pixels
        reference = np.nanmedian(stack, axis=0)
    finite = reference[np.isfinite(reference)]
    if finite.size == 0:
        return []
    sky_free = reference - float(np.median(finite))
    sigma = _robust_sigma(sky_free)
    if not math.isfinite(sigma) or sigma <= 0:
        return []
    exclude = target_exclusion(np.where(np.isfinite(sky_free), sky_free, np.nan))
    stars = find_stars(sky_free, sigma, min_snr=STAR_SNR, exclude=exclude)
    stars.sort(key=lambda s: -sky_free[s[1], s[0]])
    return stars[:MAX_STARS]


def _detector_registrations(frames: Sequence[_GridFrame]) -> dict[str, Registration | None]:
    stack = np.stack([_usable(f) for f in frames])
    stars = _reference_stars(stack)
    # centroids[i, k] = (x, y) of star k in frame i, NaN where not measurable
    centroids = np.full((len(frames), len(stars), 2), np.nan)
    for i, img in enumerate(stack):
        for k, (x, y) in enumerate(stars):
            c = centroid(img, x, y)
            if c is not None:
                centroids[i, k] = c
    measured = np.isfinite(centroids[..., 0])
    enough = measured.sum(axis=0) >= MIN_FRAMES  # stars with a trustworthy consensus
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        consensus = np.nanmedian(centroids, axis=0)  # (n_stars, 2)
    out: dict[str, Registration | None] = {}
    for i, f in enumerate(frames):
        use = measured[i] & enough
        if use.sum() < MIN_STARS:
            out[f.frame_id] = None
            continue
        d = centroids[i, use] - consensus[use]
        out[f.frame_id] = Registration(
            float(np.median(d[:, 0])),
            float(np.median(d[:, 1])),
            int(use.sum()),
            _robust_sigma(d.ravel()),
        )
    return out


def registrations(frames: Sequence[_GridFrame]) -> dict[str, Registration | None]:
    """Registration error of every frame, judged against the other frames of the same detector.

    None means not checked: fewer than ``MIN_FRAMES`` frames of that detector, or fewer than ``MIN_STARS``
    field stars measurable in the frame. Frames must share one grid (same shape).
    """
    by_detector: dict[int, list[_GridFrame]] = defaultdict(list)
    for f in frames:
        by_detector[f.detector].append(f)
    out: dict[str, Registration | None] = {}
    for members in by_detector.values():
        if len(members) < MIN_FRAMES:
            out.update({f.frame_id: None for f in members})
        else:
            out.update(_detector_registrations(members))
    return out


def misregistered(
    registered: dict[str, Registration | None], max_offset: float = MAX_OFFSET_PX
) -> dict[str, Registration]:
    """The frames whose registration error exceeds ``max_offset`` px."""
    return {fid: r for fid, r in registered.items() if r is not None and r.offset > max_offset}
