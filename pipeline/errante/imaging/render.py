"""Turn a float image (MJy/sr) into an 8-bit PNG for the browser (WS2).

``field_stretches`` gives every frame of a detector the same contrast so the
blink does not flicker in brightness. Ideas left for WS2: zscale, colormaps,
WebP output, difference images (frame - median stack) as an extra layer.
"""

from __future__ import annotations

from collections.abc import Hashable, Sequence
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image

from ..models import Stretch


@dataclass(frozen=True)
class _SkyStats:
    background: float
    sigma: float
    bright: float  # hi_pct percentile minus background


def _sky_stats(img: np.ndarray, hi_pct: float, bad: np.ndarray | None = None) -> _SkyStats | None:
    usable = np.isfinite(img) if bad is None else np.isfinite(img) & ~bad
    finite = img[usable]
    if finite.size == 0:
        return None
    med = float(np.median(finite))
    sigma = float(1.4826 * np.median(np.abs(finite - med)))
    return _SkyStats(background=med, sigma=sigma, bright=float(np.percentile(finite, hi_pct)) - med)


def field_stretches(
    images: Sequence[np.ndarray],
    groups: Sequence[Hashable],
    bad_masks: Sequence[np.ndarray | None] | None = None,
    sigma_low: float = 2.0,
    sigma_high: float = 40.0,
    hi_pct: float = 99.5,
    group_pct: float = 50.0,
) -> list[Stretch]:
    """One stretch per image with a CONTRAST shared by its group (WS2-2).

    Blinking frames that were each normalised on their own makes the whole
    image pulse in brightness. Here every frame of a group (use the detector:
    each one sees a different wavelength range) gets the same display width,
    taken from the group's typical noise and bright end, anchored at the
    frame's own sky level. Each Stretch stays in true MJy/sr, so a colorbar is
    still correct, and a source that really changes brightness between epochs
    still looks brighter or fainter.

    Pixels in ``bad_masks`` (saturated cores filled for display, detector
    defects) never set the scale: on a real Barnard's Star field the filled
    core alone pushed every other star to near black. The bright end is the
    ``hi_pct`` percentile of usable pixels, and the group takes the median
    (``group_pct``) of its frames so one odd epoch cannot set it for all.
    """
    if len(images) != len(groups) or (bad_masks is not None and len(bad_masks) != len(images)):
        raise ValueError("images, groups and bad_masks must have the same length")
    masks = bad_masks if bad_masks is not None else [None] * len(images)
    stats = [_sky_stats(img, hi_pct, bad) for img, bad in zip(images, masks, strict=True)]
    spans: dict[Hashable, tuple[float, float]] = {}
    for key in dict.fromkeys(groups):
        members = [s for s, g in zip(stats, groups, strict=True) if g == key and s is not None]
        if not members:
            continue
        sigma = float(np.median([s.sigma for s in members])) or 1e-6
        bright = float(np.percentile([s.bright for s in members], group_pct))
        spans[key] = (sigma_low * sigma, max(bright, sigma_high * sigma))
    out = []
    for s, g in zip(stats, groups, strict=True):
        if s is None:
            out.append(Stretch(vmin=0.0, vmax=1.0, method="asinh"))
            continue
        low, high = spans[g]
        out.append(Stretch(vmin=s.background - low, vmax=s.background + high, method="asinh"))
    return out


def compute_stretch(img: np.ndarray, sigma_low: float = 2.0, sigma_high: float = 40.0, hi_pct: float = 99.9) -> Stretch:
    """Robust display range: from just below the sky background to bright stars.

    Percentile-only stretches make the noise fill the whole grey range in sparse
    fields; anchoring on the background median and its robust sigma (MAD) keeps
    the sky dark and point sources visible.
    """
    finite = img[np.isfinite(img)]
    if finite.size == 0:
        return Stretch(vmin=0.0, vmax=1.0)
    med = float(np.median(finite))
    sigma = float(1.4826 * np.median(np.abs(finite - med))) or 1e-6
    vmin = med - sigma_low * sigma
    vmax = max(float(np.percentile(finite, hi_pct)), med + sigma_high * sigma)
    return Stretch(vmin=vmin, vmax=vmax, method="asinh")


def to_uint8(img: np.ndarray, stretch: Stretch, softening: float = 0.1) -> np.ndarray:
    x = (img - stretch.vmin) / (stretch.vmax - stretch.vmin)
    x = np.clip(np.nan_to_num(x, nan=0.0), 0.0, 1.0)
    if stretch.method == "asinh":
        x = np.arcsinh(x / softening) / np.arcsinh(1.0 / softening)
    elif stretch.method == "log":
        x = np.log1p(1000 * x) / np.log1p(1000)
    return (x * 255).round().astype(np.uint8)


def save_png(img: np.ndarray, path: Path, stretch: Stretch | None = None) -> Stretch:
    """``img`` must already be in PNG orientation (row 0 = north/top).

    Grid pixels without data (NaN: outside the cutout) become TRANSPARENT
    (grey + alpha PNG) instead of black, so the viewer can tell missing data
    from dark sky. Images without NaN stay plain 8-bit grey.
    """
    stretch = stretch or compute_stretch(img)
    path.parent.mkdir(parents=True, exist_ok=True)
    grey = to_uint8(img, stretch)
    nodata = ~np.isfinite(img)
    if nodata.any():
        alpha = np.where(nodata, 0, 255).astype(np.uint8)
        Image.fromarray(np.dstack([grey, alpha])).save(path, optimize=True)
    else:
        Image.fromarray(grey).save(path, optimize=True)
    return stretch


def fits_to_png_orientation(img_fits_yup: np.ndarray) -> np.ndarray:
    """FITS arrays have row 0 at the bottom (south); PNG wants it at the top."""
    return np.flipud(img_fits_yup)
