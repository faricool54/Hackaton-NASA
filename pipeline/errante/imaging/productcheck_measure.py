"""WS2-8: display-level measurements on decoded PNG frames (centroids, white plateaus, aperture sums).

The inputs are ``invert.decode`` values (approximate MJy/sr): clipped (white) pixels are bounds, not values,
so the flux-weighted centroid refuses a box that holds one, and aperture sums that include one are lower
bounds. Windows are sized to the SPHEREx PSF (FWHM ~1.2-2 px on the 6.15"/px grid).
"""

from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass

import numpy as np

from ..detect.difference import local_sky

MAD_TO_SIGMA = 1.4826
CENTROID_HALF = 2  # 5x5 px box: the PSF core plus its first wing
CENTROID_ITERATIONS = 5  # the box is recentred on each estimate
CENTROID_SKY = (4.0, 7.0)  # px, local sky ring of the centroid (as detect.difference / imaging.register)
APERTURE_RADIUS = 3.0  # px, the r = 3 px aperture of docs/validation/rw-aurigae.md
APERTURE_SKY = (5.0, 8.0)  # px, sky ring outside the r = 3 px aperture
PLATEAU_SEARCH = 3.0  # px: a white plateau counts as the target's if one of its pixels is this close


@dataclass(frozen=True)
class Centroid:
    """Flux-weighted centroid in PNG pixels; ``status`` says why x/y are None."""

    x: float | None
    y: float | None
    status: str  # ok | clipped | no_data | faint | off_image
    peak_snr: float | None = None


@dataclass(frozen=True)
class Plateau:
    """The connected white (grey 255) region at the target: its centroid and size."""

    x: float
    y: float
    area: int
    touches_edge: bool


@dataclass(frozen=True)
class Aperture:
    """Sum of (value - local sky) in a disc; a lower bound when it holds clipped pixels."""

    total: float  # MJy/sr x px
    sigma: float  # from the sky scatter and the grey-level quantisation
    n_pixels: int
    n_clipped: int
    sky: float
    peak: float  # brightest disc pixel above the sky [MJy/sr]
    peak_grey: int
    flat_top: int  # pixels of the 3x3 around the peak sharing its (non-white) grey: a display-filled core?

    @property
    def lower_bound(self) -> bool:
        return self.n_clipped > 0


def robust_sigma(values: np.ndarray) -> float:
    v = np.asarray(values, dtype=np.float64)
    v = v[np.isfinite(v)]
    if v.size == 0:
        return float("nan")
    return float(MAD_TO_SIGMA * np.median(np.abs(v - np.median(v))))


def disc(shape: tuple[int, int], x: float, y: float, radius: float) -> np.ndarray:
    yy, xx = np.indices(shape)
    return np.hypot(xx - x, yy - y) <= radius


def frame_noise(values: np.ndarray, clipped: np.ndarray, exclude: tuple[float, float, float]) -> float:
    """Robust pixel scatter of a decoded frame outside the circle ``exclude = (x, y, r)`` and its white pixels."""
    keep = ~disc(values.shape, *exclude) & ~clipped & np.isfinite(values)
    return robust_sigma(values[keep])


def masked(values: np.ndarray, clipped: np.ndarray) -> np.ndarray:
    """Values with clipped pixels set to NaN (they are bounds, not measurements)."""
    return np.where(clipped, np.nan, values)


def flux_centroid(
    values: np.ndarray, clipped: np.ndarray, x0: float, y0: float, sigma: float, min_snr: float
) -> Centroid:
    """Flux-weighted centroid above the local sky in a recentred 5x5 box, starting at (x0, y0).

    Refuses (status) a box that leaves the image, holds no-data or clipped (white) pixels, or whose brightest
    pixel is under ``min_snr`` x ``sigma`` above the local sky.
    """
    if not math.isfinite(sigma):
        return Centroid(None, None, "no_data")  # no usable sky to judge the detection
    img = masked(values, clipped)
    ny, nx = img.shape
    h = CENTROID_HALF
    dy, dx = np.mgrid[-h : h + 1, -h : h + 1]
    cx, cy, snr = float(x0), float(y0), None
    for _ in range(CENTROID_ITERATIONS):
        ix, iy = int(round(cx)), int(round(cy))
        if not (h <= ix < nx - h and h <= iy < ny - h):
            return Centroid(None, None, "off_image")
        if clipped[iy - h : iy + h + 1, ix - h : ix + h + 1].any():
            return Centroid(None, None, "clipped")
        box = img[iy - h : iy + h + 1, ix - h : ix + h + 1]
        sky = local_sky(img, ix, iy, CENTROID_SKY)
        if not np.isfinite(box).all() or not math.isfinite(sky):
            return Centroid(None, None, "no_data")
        w = np.clip(box - sky, 0.0, None)
        snr = float(w.max()) / sigma if sigma > 0 else float("inf")
        if snr < min_snr or float(w.sum()) <= 0:
            return Centroid(None, None, "faint", snr)
        cx, cy = ix + float((w * dx).sum() / w.sum()), iy + float((w * dy).sum() / w.sum())
    return Centroid(cx, cy, "ok", snr)


def plateau(clipped: np.ndarray, x0: float, y0: float, search: float = PLATEAU_SEARCH) -> Plateau | None:
    """The 4-connected white region with a pixel within ``search`` px of (x0, y0) (the nearest such pixel)."""
    near = disc(clipped.shape, x0, y0, search) & clipped
    if not near.any():
        return None
    ys, xs = np.nonzero(near)
    k = int(np.argmin(np.hypot(xs - x0, ys - y0)))
    seen = np.zeros(clipped.shape, bool)
    queue = deque([(int(ys[k]), int(xs[k]))])
    seen[ys[k], xs[k]] = True
    ny, nx = clipped.shape
    while queue:
        y, x = queue.popleft()
        for yy, xx in ((y - 1, x), (y + 1, x), (y, x - 1), (y, x + 1)):
            if 0 <= yy < ny and 0 <= xx < nx and clipped[yy, xx] and not seen[yy, xx]:
                seen[yy, xx] = True
                queue.append((yy, xx))
    py, px = np.nonzero(seen)
    edge = bool(py.min() == 0 or px.min() == 0 or py.max() == ny - 1 or px.max() == nx - 1)
    return Plateau(float(px.mean()), float(py.mean()), int(seen.sum()), edge)


def _flat_top(grey: np.ndarray, inside: np.ndarray) -> tuple[int, int]:
    """(peak grey in ``inside``, pixels of the 3x3 around it with the same grey; 0 when the peak is white)."""
    g = np.where(inside, grey.astype(int), -1)
    iy, ix = np.unravel_index(int(np.argmax(g)), g.shape)
    peak = int(g[iy, ix])
    if peak >= 255:
        return peak, 0
    hood = g[max(iy - 1, 0) : iy + 2, max(ix - 1, 0) : ix + 2]
    return peak, int((hood == peak).sum())


def aperture(
    values: np.ndarray,
    step: np.ndarray,
    clipped: np.ndarray,
    grey: np.ndarray,
    x: float,
    y: float,
    sigma: float,
    radius: float = APERTURE_RADIUS,
) -> Aperture | None:
    """Disc sum of (value - local sky) around (x, y); None when the disc has no-data pixels or no sky."""
    inside = disc(values.shape, x, y, radius)
    v = values[inside]
    if not np.isfinite(v).all():
        return None
    sky = local_sky(masked(values, clipped), int(round(x)), int(round(y)), APERTURE_SKY)
    if not math.isfinite(sky):
        return None
    quant = step[inside]
    var = v.size * sigma**2 + float(np.nansum(quant**2)) / 12.0
    peak_grey, flat = _flat_top(grey, inside)
    return Aperture(
        total=float((v - sky).sum()),
        sigma=float(math.sqrt(var)),
        n_pixels=int(v.size),
        n_clipped=int(clipped[inside].sum()),
        sky=float(sky),
        peak=float(v.max() - sky),
        peak_grey=peak_grey,
        flat_top=flat,
    )


def rolloff_top_index(white_counts: list[int], peaks: list[float], cap: float) -> int | None:
    """Index of the one frame of a roll-off detector whose single white target pixel IS the roll-off top.

    ``render.target_highlights`` sets a detector's roll-off top to its brightest unflagged target peak
    (unless capped at ``cap`` x the median peak), so exactly one frame's peak maps to white. When only one
    frame has white target pixels, it has exactly one, and its peak is not above the cap, that pixel is the
    top itself: a value (to one grey level, ~6 %), not a lower bound. INFERRED from the renderer's rule: a
    flagged core pixel brighter than the top would look the same in the PNG.
    """
    white = [i for i, n in enumerate(white_counts) if n > 0]
    if len(white) != 1 or white_counts[white[0]] != 1 or not peaks:
        return None
    return white[0] if peaks[white[0]] <= cap * float(np.median(peaks)) else None
