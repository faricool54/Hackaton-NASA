"""Turn a float image (MJy/sr) into an 8-bit PNG for the browser (WS2).

Basic version implemented so the demo works. Ideas for WS2: per-field common
stretch (so blinking doesn't flicker in brightness), zscale, colormaps,
WebP output, difference images (frame - median stack) as an extra layer.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image

from ..models import Stretch


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
    """``img`` must already be in PNG orientation (row 0 = north/top)."""
    stretch = stretch or compute_stretch(img)
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(to_uint8(img, stretch), mode="L").save(path, optimize=True)
    return stretch


def fits_to_png_orientation(img_fits_yup: np.ndarray) -> np.ndarray:
    """FITS arrays have row 0 at the bottom (south); PNG wants it at the top."""
    return np.flipud(img_fits_yup)
