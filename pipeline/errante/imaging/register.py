"""WS2: per-frame registration check — find frames whose archive WCS puts the sky at the wrong place.

Every frame reaches the common grid through its own WCS. If that WCS is wrong, every star of the frame lands
at a shifted position and the blink shows a false jump of the whole field. This happens in the archive: in
2026W38_1A_0162_3D6 (RW Aurigae field) four Gaia stars sit 1.21-1.36 px off in x although the header says
``FINAST = 0`` and ``ASTRONETSOLVED = True`` (docs/validation/rw-aurigae.md).

The check needs no catalog; it uses the frames of the field itself (all detectors: a correct WCS puts a star
at the same grid position at every wavelength):

1. Each frame is made sky-free and divided by its noise; the field stars are found on the per-pixel median
   of those signal-to-noise images, outside the target circle (the target may move, vary or saturate).
2. A coarse integer shift per frame (cross-correlation with the median, up to ``MAX_LAG_PX``) catches gross
   WCS errors, so a star is never looked for in empty sky.
3. Each star's centroid is measured in every frame where it stands ``FRAME_STAR_SNR`` sigmas above its local
   sky; its consensus position is the median of those centroids, so a few bad frames cannot move it.
4. A frame's registration error is the median over its stars of (centroid - consensus).

Safety: a frame whose offset is uncertain (``MAX_ERROR_PX``: few or disagreeing stars) is not checked rather than judged,
and if more than ``MAX_REJECT_FRACTION`` of the checked frames would be rejected the consensus itself is
suspect, so nothing is rejected and the report says it is inconsistent.
"""

from __future__ import annotations

import math
import warnings
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Protocol

import numpy as np

from ..detect.difference import find_stars, local_sky
from .compare import target_exclusion

MAX_OFFSET_PX = 0.5  # a frame whose stars are further than this from their consensus position is misregistered
MIN_FRAMES = 3  # frames in which a star must be measured to have a consensus position
MIN_STARS = 3  # stars measured in a frame to judge it
STAR_SNR = 15.0  # field star peak on the median S/N image, in robust sigmas of that image
FRAME_STAR_SNR = 5.0  # a star counts in a frame only if its peak is this many frame sigmas above its local sky
MAX_STARS = 25  # brightest field stars used
CENTROID_HALF = 2  # 5x5 px centroid box (SPHEREx PSF FWHM ~1.2 px)
CENTROID_ITERATIONS = 3  # the box is recentred on each estimate
MAX_LAG_PX = 20  # coarse search radius for gross WCS errors
CORRELATION_CLIP = (3.0, 30.0)  # S/N pixels used in the cross-correlation (noise out, bright stars capped)
# A frame is judged only if the uncertainty of its offset (standard error of the median of its star offsets,
# 1.2533 x robust scatter / sqrt(n), worst axis) is at most this: a few faint, disagreeing stars (e.g. 3 stars
# in a D6 frame of eps Indi B, 0.38 px with scatter 0.44 px) are "not checked" rather than near the threshold.
MAX_ERROR_PX = 0.15
MAX_REJECT_FRACTION = 1 / 3  # rejecting more of the checked frames than this means the consensus is suspect
MAD_TO_SIGMA = 1.4826


class _GridFrame(Protocol):
    frame_id: str
    detector: int
    data: np.ndarray
    bad: np.ndarray


@dataclass(frozen=True)
class Registration:
    """Registration error of one frame on the grid, relative to the consensus of the field's frames [px]."""

    dx: float  # +x = towards the right of the PNG (west)
    dy: float  # +y = towards the bottom of the PNG (south)
    n_stars: int
    scatter: float  # robust sigma of the per-star offsets around their median (worst axis)

    @property
    def offset(self) -> float:
        return math.hypot(self.dx, self.dy)


@dataclass(frozen=True)
class Report:
    """Per frame: its Registration, or None when it could not be checked."""

    frames: dict[str, Registration | None] = field(default_factory=dict)
    inconsistent: bool = False  # the check would have rejected too many frames; nothing was rejected

    def misregistered(self, max_offset: float = MAX_OFFSET_PX) -> dict[str, Registration]:
        if self.inconsistent:
            return {}
        return {fid: r for fid, r in self.frames.items() if r is not None and r.offset > max_offset}


def _robust_sigma(values: np.ndarray) -> float:
    values = values[np.isfinite(values)]
    if values.size == 0:
        return float("nan")
    return float(MAD_TO_SIGMA * np.median(np.abs(values - np.median(values))))


def _sky_free(f: _GridFrame) -> np.ndarray:
    """float32 frame data minus its median; bad pixels (saturated cores, repaired defects) and no data = NaN."""
    data = np.asarray(f.data, dtype=np.float32)
    bad = np.asarray(f.bad, dtype=bool) if f.bad is not None else np.zeros(data.shape, bool)
    out = np.where(bad | ~np.isfinite(data), np.float32(np.nan), data)
    finite = out[np.isfinite(out)]
    return out - np.float32(np.median(finite)) if finite.size else out


def _nanmedian(stack: np.ndarray) -> np.ndarray:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)  # all-NaN pixels -> NaN
        return np.nanmedian(stack, axis=0)


def _outside(shape: tuple[int, int], circle: tuple[float, float, float]) -> np.ndarray:
    yy, xx = np.indices(shape)
    return np.hypot(xx - circle[0], yy - circle[1]) >= circle[2]


def centroid(img: np.ndarray, x: float, y: float, sigma: float | None = None) -> tuple[float, float] | None:
    """Flux-weighted centroid (x, y) above the local sky in a 5x5 box recentred from (x, y); None if not measurable.

    Not measurable: the box leaves the image or holds a NaN (bad pixel, no data), the local sky ring is
    unusable, there is no flux above the sky, or (with ``sigma``, the frame's pixel noise) the brightest
    box pixel is less than ``FRAME_STAR_SNR`` x ``sigma`` above the sky — no star there.
    """
    ny, nx = img.shape
    h = CENTROID_HALF
    dy, dx = np.mgrid[-h : h + 1, -h : h + 1]
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
        if total <= 0 or (sigma is not None and float(w.max()) < FRAME_STAR_SNR * sigma):
            return None
        cx, cy = ix + float((w * dx).sum()) / total, iy + float((w * dy).sum()) / total
    return cx, cy


def coarse_lag(snr: np.ndarray, reference: np.ndarray, max_lag: int = MAX_LAG_PX) -> tuple[int, int]:
    """Integer (dx, dy) that best aligns ``reference`` onto ``snr`` (both S/N images, target masked to NaN).

    Cross-correlation of the clipped star pixels (``CORRELATION_CLIP``) by FFT with zero padding, searched
    within ``max_lag`` px. (0, 0) when the images hold no star pixels.
    """

    def stars_only(img: np.ndarray) -> np.ndarray:
        img = np.nan_to_num(img, nan=0.0)
        return np.where(img > CORRELATION_CLIP[0], np.minimum(img, CORRELATION_CLIP[1]), 0.0)

    a, b = stars_only(snr), stars_only(reference)
    if not a.any() or not b.any():
        return 0, 0
    ny, nx = a.shape
    shape = (ny + max_lag, nx + max_lag)
    corr = np.fft.irfft2(np.fft.rfft2(a, shape) * np.conj(np.fft.rfft2(b, shape)), shape)
    lags = np.arange(-max_lag, max_lag + 1)
    window = corr[np.ix_(lags % shape[0], lags % shape[1])]
    iy, ix = np.unravel_index(int(np.argmax(window)), window.shape)
    return int(lags[ix]), int(lags[iy])


def _measure(img: np.ndarray, sigma: float, stars: list[tuple[int, int]], lag: tuple[int, int]) -> np.ndarray:
    out = np.full((len(stars), 2), np.nan)
    for k, (x, y) in enumerate(stars):
        c = centroid(img, x + lag[0], y + lag[1], sigma)
        if c is not None:
            out[k] = c
    return out


def registrations(frames: Sequence[_GridFrame]) -> Report:
    """Registration error of every frame against the consensus of all ``frames`` (one grid, any detectors).

    A frame is None (not checked) when fewer than ``MIN_STARS`` field stars with a consensus position are
    measurable in it, or when its offset is too uncertain (``MAX_ERROR_PX``).
    """
    frames = list(frames)
    if len(frames) < MIN_FRAMES:
        return Report({f.frame_id: None for f in frames})
    sky_free = np.stack([_sky_free(f) for f in frames])  # float32 (n, ny, nx)
    shape = sky_free.shape[1:]
    rough = np.array([_robust_sigma(img) for img in sky_free])
    with np.errstate(invalid="ignore", divide="ignore"):
        exclude = target_exclusion(_nanmedian(sky_free / rough[:, None, None]))
    outside = _outside(shape, exclude)
    sigma = np.array([_robust_sigma(img[outside]) for img in sky_free])  # the target halo inflates `rough`
    usable = np.isfinite(sigma) & (sigma > 0)
    with np.errstate(invalid="ignore", divide="ignore"):
        snr = sky_free / np.where(usable, sigma, np.nan)[:, None, None]
    reference = _nanmedian(snr[usable]) if usable.any() else np.full(shape, np.nan)
    ref_sigma = _robust_sigma(reference[outside])
    stars: list[tuple[int, int]] = []
    if math.isfinite(ref_sigma) and ref_sigma > 0:
        stars = find_stars(reference, ref_sigma, min_snr=STAR_SNR, exclude=exclude)
        stars.sort(key=lambda s: -reference[s[1], s[0]])
        stars = stars[:MAX_STARS]

    masked_reference = np.where(outside, reference, np.nan)
    centroids = np.full((len(frames), len(stars), 2), np.nan)
    for i in range(len(frames)):
        if not usable[i] or not stars:
            continue
        at_zero = _measure(sky_free[i], float(sigma[i]), stars, (0, 0))
        lag = coarse_lag(np.where(outside, snr[i], np.nan), masked_reference)
        if lag != (0, 0):  # keep the gross shift only if it finds more stars than no shift
            shifted = _measure(sky_free[i], float(sigma[i]), stars, lag)
            if np.isfinite(shifted[:, 0]).sum() > np.isfinite(at_zero[:, 0]).sum():
                at_zero = shifted
        centroids[i] = at_zero

    measured = np.isfinite(centroids[..., 0])
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        consensus = np.nanmedian(centroids, axis=0)  # (n_stars, 2)
    enough = measured.sum(axis=0) >= MIN_FRAMES
    out: dict[str, Registration | None] = {}
    for i, f in enumerate(frames):
        use = measured[i] & enough
        if use.sum() < MIN_STARS:
            out[f.frame_id] = None
            continue
        d = centroids[i, use] - consensus[use]
        med = np.median(d, axis=0)
        scatter = max(_robust_sigma(d[:, 0] - med[0]), _robust_sigma(d[:, 1] - med[1]))
        error = 1.2533 * scatter / math.sqrt(int(use.sum()))
        out[f.frame_id] = (
            None if error > MAX_ERROR_PX else Registration(float(med[0]), float(med[1]), int(use.sum()), scatter)
        )
    checked = [r for r in out.values() if r is not None]
    n_bad = sum(r.offset > MAX_OFFSET_PX for r in checked)
    return Report(out, inconsistent=bool(checked) and n_bad > MAX_REJECT_FRACTION * len(checked))
