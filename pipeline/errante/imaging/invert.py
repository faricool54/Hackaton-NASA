"""WS2-8: undo the 8-bit display mapping of ``render.to_uint8`` to approximate MJy/sr from a published PNG.

A published frame PNG keeps only 256 grey levels of ``IMAGE - ZODI`` under the frame's ``Stretch`` (asinh with
softening 0.1) and, on detectors with a highlight roll-off, a logarithmic compression of the values above
``Stretch.vmax`` into the top ``1 - HIGHLIGHT_KNEE`` of the grey range (white = the roll-off top). Inverting
that mapping gives each pixel back at the centre of its grey level. What it cannot give back:

- grey 0 is everything below about ``vmin`` and grey 255 everything above about ``vmax`` (or the roll-off
  top; exactly: above the middle of the last grey level): those pixels are CLIPPED and their value is only a
  bound;
- inside a level the value is unknown to +- half a step; ``Decoded.step`` is that step in MJy/sr per pixel
  (fine near the sky, ~1 % of the stretch range near white, ~6 % of the value in the roll-off);
- saturated cores and detector defects were filled from their neighbours for display (build notes): the PNG
  does not say which pixels those are.

It is a display-level reading of the products, not photometry: fluxes and errors come from the FITS.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from ..models import Stretch
from .render import HIGHLIGHT_KNEE

SOFTENING = 0.1  # render.to_uint8 default (the build never changes it)
GREY_MAX = 255
LOG_SCALE = 1000.0  # render.to_uint8 'log' method: log1p(1000 y) / log1p(1000)


@dataclass(frozen=True)
class Decoded:
    """One PNG frame back in MJy/sr (approximately): see the module docstring for what is lost."""

    values: np.ndarray  # float64, value at the centre of each grey level; NaN where the PNG has no data
    step: np.ndarray  # MJy/sr spanned by each pixel's grey level (one-sided at 0 and 255)
    low_clip: np.ndarray  # grey 0 with data: value <= Stretch.vmin
    high_clip: np.ndarray  # grey 255 with data: value >= Stretch.vmax (or >= the roll-off top)


def _unit_to_x(u: np.ndarray, method: str, softening: float) -> np.ndarray:
    """Inverse of the display curve on [0, 1] -> stretch fraction x = (value - vmin) / (vmax - vmin)."""
    if method == "asinh":
        return softening * np.sinh(u * np.arcsinh(1.0 / softening))
    if method == "log":
        return np.expm1(u * np.log1p(LOG_SCALE)) / LOG_SCALE
    return u  # linear, and zscale (to_uint8 maps it linearly)


def grey_to_value(
    grey: np.ndarray | float, stretch: Stretch, highlight: float | None = None, softening: float = SOFTENING
) -> np.ndarray:
    """MJy/sr of (possibly fractional) grey levels under ``stretch``; the inverse of ``render.to_uint8``.

    ``highlight``: the roll-off top used when the PNG was written (None = no roll-off). Grey is clamped to
    [0, 255], so 0 and 255 give the clip bounds.
    """
    if stretch.vmax <= stretch.vmin:
        raise ValueError(f"stretch must have vmax > vmin, got {stretch.vmin}..{stretch.vmax}")
    y = np.clip(np.asarray(grey, dtype=np.float64) / GREY_MAX, 0.0, 1.0)
    width = stretch.vmax - stretch.vmin
    if highlight is None or highlight <= stretch.vmax:
        x = _unit_to_x(y, stretch.method, softening)
    else:
        top = (highlight - stretch.vmin) / width
        below = _unit_to_x(np.minimum(y / HIGHLIGHT_KNEE, 1.0), stretch.method, softening)
        above = top ** ((y - HIGHLIGHT_KNEE) / (1.0 - HIGHLIGHT_KNEE))
        x = np.where(y <= HIGHLIGHT_KNEE, below, above)
    return stretch.vmin + x * width


def decode(
    grey: np.ndarray, stretch: Stretch, highlight: float | None = None, nodata: np.ndarray | None = None
) -> Decoded:
    """``grey`` (uint8 frame PNG) -> values, grey-level steps and clip masks. ``nodata``: transparent pixels."""
    g = np.asarray(grey)
    if g.ndim != 2:
        raise ValueError(f"expected a 2-D grey image, got shape {g.shape}")
    missing = np.zeros(g.shape, bool) if nodata is None else np.asarray(nodata, dtype=bool)
    if missing.shape != g.shape:
        raise ValueError(f"nodata mask shape {missing.shape} != image shape {g.shape}")
    gf = g.astype(np.float64)
    values = grey_to_value(gf, stretch, highlight)
    step = grey_to_value(gf + 0.5, stretch, highlight) - grey_to_value(gf - 0.5, stretch, highlight)
    values = np.where(missing, np.nan, values)
    return Decoded(
        values=values,
        step=np.where(missing, np.nan, step),
        low_clip=(g == 0) & ~missing,
        high_clip=(g == GREY_MAX) & ~missing,
    )
