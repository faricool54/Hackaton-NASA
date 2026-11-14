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
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass

import numpy as np

MIN_STAR_SNR = 20.0  # star peak / per-pixel noise
MIN_STARS = 5
APERTURE_HALF = 2  # 5x5 px aperture; SPHEREx PSF FWHM ~1.2 px
ISOLATION_HALF = 3  # a star must be the maximum of its 7x7 neighbourhood


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


def find_stars(
    img: np.ndarray,
    sigma: float,
    min_snr: float = MIN_STAR_SNR,
    exclude: tuple[float, float, float] | None = None,
) -> list[tuple[int, int]]:
    """(x, y) of isolated local maxima with peak >= ``min_snr`` x ``sigma`` (sky-free ``img``).

    Stars too close to the edge, with a non-finite aperture, or inside the
    circle ``exclude = (x, y, radius)`` (the target) are skipped.
    """
    ny, nx = img.shape
    h = max(APERTURE_HALF, ISOLATION_HALF)
    out = []
    finite = np.isfinite(img)
    cand = np.argwhere(finite & (np.nan_to_num(img) >= min_snr * sigma))
    for y, x in cand:
        if not (h <= x < nx - h and h <= y < ny - h):
            continue
        if exclude is not None and np.hypot(x - exclude[0], y - exclude[1]) < exclude[2]:
            continue
        hood = img[y - ISOLATION_HALF : y + ISOLATION_HALF + 1, x - ISOLATION_HALF : x + ISOLATION_HALF + 1]
        if not np.isfinite(hood).all() or img[y, x] < np.max(hood):
            continue
        out.append((int(x), int(y)))
    return out


def aperture_flux(img: np.ndarray, x: int, y: int, half: int = APERTURE_HALF) -> float:
    """Sum of a (2*half+1)^2 box (sky already removed); NaN if any pixel is missing."""
    box = img[y - half : y + half + 1, x - half : x + half + 1]
    return float(box.sum()) if np.isfinite(box).all() else float("nan")


def star_flux_scale(
    late: np.ndarray,
    early: np.ndarray,
    sigma_early: float,
    exclude: tuple[float, float, float] | None = None,
    min_stars: int = MIN_STARS,
) -> StarScale:
    """``s`` with ``late ~ s * early``: sigma-clipped median of per-star aperture ratios.

    Both images must be sky-free. Stars are found on ``early``; ``exclude``
    removes the target. Fewer than ``min_stars`` usable stars -> s = 1, fitted=False.
    """
    ratios = []
    for x, y in find_stars(early, sigma_early, exclude=exclude):
        fe, fl = aperture_flux(early, x, y), aperture_flux(late, x, y)
        if np.isfinite(fe) and np.isfinite(fl) and fe > 0 and fl > 0:
            ratios.append(fl / fe)
    r = np.asarray(ratios)
    for _ in range(3):  # sigma-clip variables, blends and movers among the field stars
        if r.size < min_stars:
            break
        med = np.median(r)
        mad = 1.4826 * np.median(np.abs(r - med)) or 1e-9
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
