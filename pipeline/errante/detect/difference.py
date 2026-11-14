"""Remove the static sky so only things that changed remain (WS2).

Caveat: SPHEREx is a *spectral* survey. The same star has a different
brightness in every frame because each frame samples a different wavelength
(linear variable filter). Compare frames of the SAME detector and similar
wavelength, or normalise on field stars, or work on positions only. The
season-level version for display lives in ``imaging.compare``.

The flux scale between two images is fitted on FIELD STARS, one aperture
ratio per star, never on raw pixels: on a real Barnard's Star field half of
the bright pixels belonged to the target's own halo, so a pixel median
followed the target and cancelled its real changes.

Each star is measured above its LOCAL sky (median of a ring around it): on
the R Draconis field the saturated target's halo still adds a pedestal and a
gradient 25-30 px away, which a global sky level leaves in the aperture
(D2 S4-S0, same 13-px target circle: s = 0.46 with the global sky, 0.99
with a local ring sky; stars 40-70 px from the target give 1.03).
"""

from __future__ import annotations

import math
import warnings
from dataclasses import dataclass
from functools import lru_cache

import numpy as np

MIN_STAR_SNR = 20.0  # star peak / per-pixel noise
MIN_STARS = 5
APERTURE_HALF = 2  # 5x5 px aperture; SPHEREx PSF FWHM ~1.2 px
ISOLATION_HALF = 3  # a star must be the maximum of its 7x7 neighbourhood
SKY_ANNULUS = (4.0, 7.0)  # px: inner/outer radius of the local sky ring around each star
MIN_SKY_FRACTION = 0.5  # of the ring pixels must hold valid data (inside the image, finite)
# The clip never gets tighter than this relative scatter: with a handful of stars that agree to 0.1%, a
# 3-MAD clip repeated 3 times dropped good stars until fewer than MIN_STARS were left.
MIN_RATIO_SCATTER = 0.02


@dataclass(frozen=True)
class StarScale:
    scale: float
    n_stars: int
    fitted: bool


def static_sky(stack: np.ndarray, bad: np.ndarray | None = None) -> np.ndarray:
    """Per-pixel robust median of a (n_frames, h, w) stack -> (h, w) template.

    Pixels flagged in ``bad`` (same shape as ``stack``) are ignored; a pixel
    with no usable frame is NaN. Group frames by detector first: different
    detectors see different wavelengths.
    """
    stack = np.asarray(stack, dtype=np.float64)
    if stack.ndim != 3:
        raise ValueError("stack must be (n_frames, h, w)")
    values = np.where(bad, np.nan, stack) if bad is not None else stack
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)  # all-NaN pixels -> NaN
        return np.nanmedian(values, axis=0)


def _sky_free(img: np.ndarray) -> np.ndarray:
    img = np.asarray(img, dtype=np.float64)
    finite = img[np.isfinite(img)]
    return img - (np.median(finite) if finite.size else 0.0)


@lru_cache(maxsize=8)
def _ring_offsets(r_in: float, r_out: float) -> tuple[np.ndarray, np.ndarray]:
    k = math.ceil(r_out)
    dy, dx = np.mgrid[-k : k + 1, -k : k + 1]
    d = np.hypot(dx, dy)
    ring = (d >= r_in) & (d <= r_out)
    return dy[ring], dx[ring]


def local_sky(img: np.ndarray, x: int, y: int, radii: tuple[float, float] = SKY_ANNULUS) -> float:
    """Median of the ring ``radii`` (px) around (x, y); NaN if under ``MIN_SKY_FRACTION`` of it is usable.

    Pixels off the image or not finite (saturated cores, no data) are left out.
    A median ignores the few ring pixels covered by a neighbouring star.
    """
    dy, dx = _ring_offsets(float(radii[0]), float(radii[1]))
    ys, xs = y + dy, x + dx
    ny, nx = img.shape
    inside = (ys >= 0) & (ys < ny) & (xs >= 0) & (xs < nx)
    values = img[ys[inside], xs[inside]]
    values = values[np.isfinite(values)]
    if values.size == 0 or values.size < MIN_SKY_FRACTION * dy.size:
        return float("nan")
    return float(np.median(values))


def find_stars(
    img: np.ndarray,
    sigma: float,
    min_snr: float = MIN_STAR_SNR,
    exclude: tuple[float, float, float] | None = None,
    sky_annulus: tuple[float, float] | None = SKY_ANNULUS,
) -> list[tuple[int, int]]:
    """(x, y) of isolated local maxima whose peak is >= ``min_snr`` x ``sigma`` above the sky.

    The sky is the local ring median (``sky_annulus``; None = ``img`` is
    already sky-free). Stars too close to the edge, with a non-finite 7x7
    neighbourhood or local sky, or inside the circle ``exclude = (x, y,
    radius)`` (the target) are skipped.
    """
    img = np.asarray(img, dtype=np.float64)
    ny, nx = img.shape
    h = max(APERTURE_HALF, ISOLATION_HALF)
    size = 2 * ISOLATION_HALF + 1
    if ny < size or nx < size:
        return []
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)  # all-NaN windows
        hood_max = np.lib.stride_tricks.sliding_window_view(img, (size, size)).max(axis=(-2, -1))
    peak = np.full(img.shape, False)
    centre = img[ISOLATION_HALF : ny - ISOLATION_HALF, ISOLATION_HALF : nx - ISOLATION_HALF]
    with np.errstate(invalid="ignore"):  # NaN in a window -> not a star
        peak[ISOLATION_HALF : ny - ISOLATION_HALF, ISOLATION_HALF : nx - ISOLATION_HALF] = centre >= hood_max
    out = []
    for y, x in np.argwhere(peak):
        if not (h <= x < nx - h and h <= y < ny - h):
            continue
        if exclude is not None and np.hypot(x - exclude[0], y - exclude[1]) < exclude[2]:
            continue
        sky = 0.0 if sky_annulus is None else local_sky(img, int(x), int(y), sky_annulus)
        if not math.isfinite(sky) or img[y, x] - sky < min_snr * sigma:
            continue
        out.append((int(x), int(y)))
    return out


def aperture_flux(
    img: np.ndarray,
    x: int,
    y: int,
    half: int = APERTURE_HALF,
    sky_annulus: tuple[float, float] | None = SKY_ANNULUS,
) -> float:
    """Sum of a (2*half+1)^2 box minus the local sky (``sky_annulus``; None = ``img`` is already sky-free).

    NaN if any box pixel is missing or off the image, or the local sky cannot be measured.
    """
    ny, nx = img.shape
    if not (half <= x < nx - half and half <= y < ny - half):
        return float("nan")
    box = img[y - half : y + half + 1, x - half : x + half + 1]
    if not np.isfinite(box).all():
        return float("nan")
    sky = 0.0 if sky_annulus is None else local_sky(img, x, y, sky_annulus)
    return float(box.sum() - box.size * sky)


def star_flux_scale(
    late: np.ndarray,
    early: np.ndarray,
    sigma_early: float,
    exclude: tuple[float, float, float] | None = None,
    min_stars: int = MIN_STARS,
    sky_annulus: tuple[float, float] | None = SKY_ANNULUS,
) -> StarScale:
    """``s`` with ``late ~ s * early``: sigma-clipped median of per-star aperture ratios.

    Each star is measured above its local sky in both images (``sky_annulus``;
    None = both images are already sky-free). Stars are found on ``early``;
    ``exclude`` removes the target. Fewer than ``min_stars`` usable stars -> s = 1, fitted=False.
    """
    ratios = []
    for x, y in find_stars(early, sigma_early, exclude=exclude, sky_annulus=sky_annulus):
        fe = aperture_flux(early, x, y, sky_annulus=sky_annulus)
        fl = aperture_flux(late, x, y, sky_annulus=sky_annulus)
        if np.isfinite(fe) and np.isfinite(fl) and fe > 0 and fl > 0:
            ratios.append(fl / fe)
    r = np.asarray(ratios)
    for _ in range(3):  # sigma-clip variables, blends and movers among the field stars
        if r.size < min_stars:
            break
        med = np.median(r)
        mad = max(1.4826 * np.median(np.abs(r - med)), MIN_RATIO_SCATTER * abs(med), 1e-9)
        keep = np.abs(r - med) <= 3 * mad
        if keep.all():
            break
        r = r[keep]
    if r.size < min_stars:
        return StarScale(1.0, int(r.size), False)
    return StarScale(float(np.median(r)), int(r.size), True)


def fit_scale(frame: np.ndarray, template: np.ndarray, noise: float | None = None) -> float:
    """Robust ``s`` with ``frame ~ s * template`` from field stars (sky removed from both).

    ``noise`` is the per-pixel sigma of ``template``; estimated from it when None.
    Returns 1.0 when fewer than ``MIN_STARS`` stars qualify.
    """
    t = _sky_free(template)
    f = _sky_free(frame)
    if noise is None:
        finite = t[np.isfinite(t)]
        noise = float(1.4826 * np.median(np.abs(finite))) if finite.size else 1.0
    return star_flux_scale(f, t, noise or 1e-6).scale


def residuals(frame: np.ndarray, template: np.ndarray, scale: float | None = None) -> np.ndarray:
    """``frame - scale * template`` (sky removed from both); ``scale`` fitted on stars when None."""
    s = fit_scale(frame, template) if scale is None else scale
    return _sky_free(frame) - s * _sky_free(template)
