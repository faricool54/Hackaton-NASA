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


HIGHLIGHT_KNEE = 0.85  # with a highlight roll-off, stretch.vmax maps to this fraction of white
TARGET_RADIUS_PX = 2.5  # the target's core: grid pixels this close to the field centre
# A group gets a roll-off only if its target core holds no flagged pixel in at least half of its frames: a
# flagged core pixel is mostly saturation (OVERFLOW) or a ramp error, i.e. a lower bound that would still clip
# (RW Aurigae D2-D6 have OVERFLOW in the core in 24 of 25 frames, Barnard and R Draconis in all).
MAX_BAD_CORE_FRACTION = 0.0
MAX_TOP_OVER_MEDIAN = 4.0  # roll-off top at most this x the median target peak (RW Aur varies 2.4x in D1)


def to_uint8(img: np.ndarray, stretch: Stretch, softening: float = 0.1, highlight: float | None = None) -> np.ndarray:
    """8-bit grey levels of ``img`` under ``stretch``.

    With ``highlight`` (MJy/sr, above ``stretch.vmax``) values beyond ``vmax`` are not clipped to white: the
    usual curve fills [0, ``HIGHLIGHT_KNEE``] of the grey range and a logarithmic roll-off maps
    (vmax, highlight] onto the rest, so a bright, unsaturated target keeps its brightness changes visible.
    """
    x = np.nan_to_num((img - stretch.vmin) / (stretch.vmax - stretch.vmin), nan=0.0)
    y = np.clip(x, 0.0, 1.0)
    if stretch.method == "asinh":
        y = np.arcsinh(y / softening) / np.arcsinh(1.0 / softening)
    elif stretch.method == "log":
        y = np.log1p(1000 * y) / np.log1p(1000)
    if highlight is not None and highlight > stretch.vmax:
        top = (highlight - stretch.vmin) / (stretch.vmax - stretch.vmin)
        above = x > 1.0
        y = HIGHLIGHT_KNEE * y
        y[above] = HIGHLIGHT_KNEE + (1.0 - HIGHLIGHT_KNEE) * np.log(np.minimum(x[above], top)) / np.log(top)
    return (y * 255).round().astype(np.uint8)


def _core(shape: tuple[int, ...]) -> np.ndarray:
    h, w = shape
    yy, xx = np.indices((h, w))
    return np.hypot(xx - (w - 1) / 2, yy - (h - 1) / 2) <= TARGET_RADIUS_PX


def target_highlights(
    images: Sequence[np.ndarray],
    groups: Sequence[Hashable],
    bad_masks: Sequence[np.ndarray | None],
    stretches: Sequence[Stretch],
    hi_pct: float = 99.5,
) -> list[float | None]:
    """Per image, the top of a highlight roll-off (``to_uint8``) or None.

    A group (detector) gets one when its target (the field centre) is clean — no flagged (bad) core pixel
    in at least half of its frames, see ``MAX_BAD_CORE_FRACTION`` — and the target's brightest
    usable core pixel is above the group's shared bright end in at least half of its frames (one odd frame,
    e.g. a cosmic ray on the core, does not change a detector's look). The top is the largest such peak above
    each frame's own sky, capped at ``MAX_TOP_OVER_MEDIAN`` x the median peak, so the target clips in no
    ordinary frame. Saturated targets (Barnard's Star, R Draconis, RW Aurigae D2-D6) keep the plain stretch:
    their core values are lower bounds and cannot show brightness changes.
    """
    peaks: list[float | None] = []
    fractions: list[float] = []
    backgrounds: list[float | None] = []
    for img, bad in zip(images, bad_masks, strict=True):
        core = _core(img.shape)
        usable = core & np.isfinite(img) & (~bad if bad is not None else True)
        stats = _sky_stats(img, hi_pct, bad)
        backgrounds.append(None if stats is None else stats.background)
        fractions.append(1.0 - usable.sum() / core.sum())
        peaks.append(float(img[usable].max()) - stats.background if usable.any() and stats is not None else None)
    tops: dict[Hashable, float | None] = {}
    for key in dict.fromkeys(groups):
        idx = [i for i, g in enumerate(groups) if g == key]
        measured = [i for i in idx if peaks[i] is not None and backgrounds[i] is not None]
        if not measured or np.median([fractions[i] for i in idx]) > MAX_BAD_CORE_FRACTION:
            tops[key] = None
            continue
        rises = sum(peaks[i] > stretches[i].vmax - backgrounds[i] for i in measured)
        median_peak = float(np.median([peaks[i] for i in measured]))
        top = min(max(peaks[i] for i in measured), MAX_TOP_OVER_MEDIAN * median_peak)
        tops[key] = top if 2 * rises >= len(idx) and top > 0 else None
    return [
        None if tops[g] is None or backgrounds[i] is None else backgrounds[i] + tops[g] for i, g in enumerate(groups)
    ]


def target_scores(
    images: Sequence[np.ndarray], bad_masks: Sequence[np.ndarray | None], stretches: Sequence[Stretch]
) -> list[tuple[float, float]]:
    """Per image, (signal-to-noise, prominence) of the target's core peak above the sky.

    Prominence = peak / the shared bright end of the stretch: > 1 means the target outshines the field's
    bright stars in that image. Saturated cores count with their display fill (a lower bound). (0, 0) for an
    image without a usable sky.
    """
    out = []
    for img, bad, s in zip(images, bad_masks, stretches, strict=True):
        stats = _sky_stats(img, 99.5, bad)
        core = _core(img.shape) & np.isfinite(img)
        if stats is None or not core.any() or stats.sigma <= 0 or s.vmax <= stats.background:
            out.append((0.0, 0.0))
            continue
        peak = float(img[core].max()) - stats.background
        out.append((peak / stats.sigma, peak / (s.vmax - stats.background)))
    return out


def save_png(img: np.ndarray, path: Path, stretch: Stretch | None = None, highlight: float | None = None) -> Stretch:
    """``img`` must already be in PNG orientation (row 0 = north/top).

    Grid pixels without data (NaN: outside the cutout) become TRANSPARENT
    (grey + alpha PNG) instead of black, so the viewer can tell missing data
    from dark sky. Images without NaN stay plain 8-bit grey. ``highlight``: see ``to_uint8``.
    """
    stretch = stretch or compute_stretch(img)
    path.parent.mkdir(parents=True, exist_ok=True)
    grey = to_uint8(img, stretch, highlight=highlight)
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
