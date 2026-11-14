"""Reproject a SPHEREx image/cutout onto the field grid (WS2, P0).

SPHEREx images come in the detector's native orientation with TAN-SIP
distortion; cutouts can be non-square and NaN-padded at detector edges.

Implementation note: this is the same pixel-to-pixel mapping that
``reproject.reproject_interp`` performs (output pixel -> sky through the grid
WCS -> input pixel through the full SIP WCS -> bilinear interpolation), written
with numpy + astropy only. The CI environment and ``dev.py setup`` do not
install the heavy ``science`` extra, so this keeps the function (and its tests)
available everywhere, with identical results in the backend container.
"""

from __future__ import annotations

import warnings

import numpy as np

from ..data.fits_io import SpherexImage
from ..models import Grid
from .flags import DEFAULT_BAD, bad_pixel_mask
from .grid import grid_wcs
from .render import fits_to_png_orientation

# A bilinear sample is kept only if at least this much of its interpolation
# weight comes from finite input pixels (NaN-padded cutout edges).
MIN_FINITE_WEIGHT = 0.5
# A grid pixel is bad when at least this much of its interpolation weight comes
# from bad input pixels (nearest-neighbour alone can skip an isolated bad pixel
# on a rotated detector, although its value still leaks into the image).
BAD_WEIGHT = 0.2


def _input_pixel_coords(image: SpherexImage, grid: Grid) -> tuple[np.ndarray, np.ndarray]:
    """0-based input (x, y) of every grid pixel centre, FITS orientation (row 0 = south)."""
    h, w = grid.height_px, grid.width_px
    yo, xo = np.mgrid[0:h, 0:w]
    ra, dec = grid_wcs(grid).all_pix2world(xo.ravel(), yo.ravel(), 0)
    # quiet=True: SIP inversion may not converge far outside the cutout; those
    # pixels are outside anyway and become NaN below.
    xi, yi = image.wcs.all_world2pix(ra, dec, 0, quiet=True)
    return np.asarray(xi, dtype=float), np.asarray(yi, dtype=float)


def _inside(x: np.ndarray, y: np.ndarray, shape: tuple[int, int]) -> np.ndarray:
    ny, nx = shape
    with np.errstate(invalid="ignore"):
        return np.isfinite(x) & np.isfinite(y) & (x >= -0.5) & (x <= nx - 0.5) & (y >= -0.5) & (y <= ny - 0.5)


def bilinear_sample(img: np.ndarray, x: np.ndarray, y: np.ndarray, *, variance: bool = False) -> np.ndarray:
    """Sample ``img`` at 0-based (x, y); NaN outside the array or where mostly NaN.

    ``variance=True`` treats ``img`` as a variance map and returns the variance
    of the interpolated value, sum(w^2 var) / (sum w)^2.
    """
    ny, nx = img.shape
    out = np.full(x.shape, np.nan, dtype=np.float64)
    ok = _inside(x, y, img.shape)
    if not ok.any():
        return out
    xs = np.clip(x[ok], 0.0, nx - 1.0)
    ys = np.clip(y[ok], 0.0, ny - 1.0)
    x0 = np.minimum(np.floor(xs).astype(np.intp), max(nx - 2, 0))
    y0 = np.minimum(np.floor(ys).astype(np.intp), max(ny - 2, 0))
    x1 = np.minimum(x0 + 1, nx - 1)
    y1 = np.minimum(y0 + 1, ny - 1)
    fx = xs - x0
    fy = ys - y0
    total = np.zeros(xs.shape)
    weight = np.zeros(xs.shape)
    for yy, xx, wgt in (
        (y0, x0, (1 - fx) * (1 - fy)),
        (y0, x1, fx * (1 - fy)),
        (y1, x0, (1 - fx) * fy),
        (y1, x1, fx * fy),
    ):
        v = img[yy, xx].astype(np.float64)
        finite = np.isfinite(v)
        total += np.where(finite, v, 0.0) * (wgt**2 if variance else wgt)
        weight += np.where(finite, wgt, 0.0)
    with np.errstate(invalid="ignore", divide="ignore"):
        value = total / weight**2 if variance else total / weight
        out[ok] = np.where(weight >= MIN_FINITE_WEIGHT, value, np.nan)
    return out


def nearest_sample(img: np.ndarray, x: np.ndarray, y: np.ndarray, fill) -> np.ndarray:
    """Nearest-neighbour sample (for masks); ``fill`` outside the array."""
    ny, nx = img.shape
    out = np.full(x.shape, fill, dtype=img.dtype)
    ok = _inside(x, y, img.shape)
    xi = np.clip(np.floor(x[ok] + 0.5).astype(np.intp), 0, nx - 1)
    yi = np.clip(np.floor(y[ok] + 0.5).astype(np.intp), 0, ny - 1)
    out[ok] = img[yi, xi]
    return out


def _neighbours(img: np.ndarray) -> np.ndarray:
    """(8, ny, nx) stack of the 8-connected neighbours of every pixel (NaN outside)."""
    ny, nx = img.shape
    padded = np.pad(img, 1, constant_values=np.nan)
    return np.stack(
        [padded[1 + dy : 1 + dy + ny, 1 + dx : 1 + dx + nx] for dy in (-1, 0, 1) for dx in (-1, 0, 1) if dy or dx]
    )


def display_defects(flags: np.ndarray) -> np.ndarray:
    """Detector defects that are never sky signal: repaired for display, kept in the bad mask.

    On real DR1/QR3 Barnard cutouts (2026-11-14) single pixels flagged NONFUNC,
    PERSIST or SUR_ERROR reach hundreds to thousands of MJy/sr with sky-level
    neighbours (no PSF wings), change position between epochs, and in the
    blink look like 1-2 px movers. TRANSIENT/OUTLIER are NOT included: they can
    mark a real moving object (tasks/WS2). SUR_ERROR next to a saturated core
    (with OVERFLOW) is left alone: it belongs to the star.
    """
    defects = bad_pixel_mask(flags, ("NONFUNC", "HOT", "COLD", "PERSIST"))
    ramp = bad_pixel_mask(flags, ("SUR_ERROR",)) & ~bad_pixel_mask(flags, ("OVERFLOW",))
    return defects | ramp


def repair_for_display(
    pixels: np.ndarray, saturated: np.ndarray, defects: np.ndarray | None = None, max_iter: int = 10
) -> np.ndarray:
    """Copy of ``pixels`` with saturated NaN cores and detector defects filled from their neighbours.

    - Saturated NaN pixels (OVERFLOW) touching another saturated pixel form the
      core of a bright star (SPHEREx sets it to NaN; e.g. Barnard's Star,
      K = 4.5): they take the BRIGHTEST finite neighbour, a lower bound of the
      true value, so the star does not render with a black hole.
    - Isolated saturated NaN pixels (dead pixels also carry OVERFLOW in real
      files) and ``defects`` take the MEDIAN of their finite neighbours, a
      neutral value that does not create bright specks.
    Display only: callers keep these pixels in the bad mask. Larger holes are
    filled from the outside in, up to ``max_iter`` rings.
    """
    out = np.array(pixels, dtype=np.float64, copy=True)
    sat = saturated & np.isnan(out)
    core = sat & (np.nan_to_num(_neighbours(sat.astype(float)), nan=0.0).max(axis=0) > 0)
    todo = sat.copy()
    if defects is not None:
        todo |= defects
        out[defects & ~sat] = np.nan
    for _ in range(max_iter):
        if not todo.any():
            break
        nb = _neighbours(out)
        has = np.isfinite(nb).any(axis=0) & todo
        if not has.any():
            break
        brightest = np.max(np.where(np.isfinite(nb[:, has]), nb[:, has], -np.inf), axis=0)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            typical = np.nanmedian(nb[:, has], axis=0)
        out[has] = np.where(core[has], brightest, typical)
        todo &= ~has
    return out


def reproject_to_grid(
    image: SpherexImage,
    grid: Grid,
    *,
    subtract_zodi: bool = True,
    bad_flags: tuple[str, ...] = DEFAULT_BAD,
    repair_display: bool = True,
) -> tuple[np.ndarray, np.ndarray]:
    """Return (data, bad_mask) on ``grid`` in PNG orientation (row 0 = north).

    - ``data`` keeps MJy/sr. By default the zodiacal model (ZODI HDU) is
      subtracted first (``IMAGE - ZODI``), so the sky level is comparable
      between epochs. Grid pixels outside the cutout are NaN. Saturated NaN
      cores and detector defects are repaired for display (``repair_for_display``).
    - ``bad_mask`` is True where the value cannot be trusted: outside the
      cutout, NaN, or a ``bad_flags`` bit (or a pixel repaired for display,
      whatever ``bad_flags`` says) in the nearest input pixel or carrying at
      least ``BAD_WEIGHT`` of the interpolation weight.
      Other flagged pixels are NOT blanked in ``data`` (display them; report
      the fraction). SOURCE/TRANSIENT/OUTLIER are not in ``DEFAULT_BAD`` on purpose.
    """
    xi, yi = _input_pixel_coords(image, grid)
    shape = (grid.height_px, grid.width_px)
    pixels = np.asarray(image.data_minus_zodi if subtract_zodi else image.data)
    flags = None if image.flags is None else np.asarray(image.flags)
    repaired = None
    if repair_display and flags is not None:
        saturated = bad_pixel_mask(flags, ("OVERFLOW",)) & np.isnan(pixels)
        defects = display_defects(flags)
        repaired = saturated | defects
        pixels = repair_for_display(pixels, saturated, defects)
    data = bilinear_sample(pixels, xi, yi).reshape(shape)

    bad = ~np.isfinite(data)
    if flags is not None:
        flagged = bad_pixel_mask(flags, bad_flags)
        if repaired is not None:
            flagged = flagged | repaired
        share = np.nan_to_num(bilinear_sample(flagged.astype(np.float64), xi, yi), nan=1.0)
        bad |= (nearest_sample(flagged, xi, yi, fill=True) | (share >= BAD_WEIGHT)).reshape(shape)

    return fits_to_png_orientation(data.astype(np.float32)), fits_to_png_orientation(bad)


def reproject_variance(image: SpherexImage, grid: Grid) -> np.ndarray | None:
    """VARIANCE plane on ``grid`` (PNG orientation), (MJy/sr)^2; None if the file has none.

    It is the variance of each interpolated grid value (same bilinear weights as
    the data: sum(w^2 var) / (sum w)^2). Interpolation averages up to four
    pixels, so it is up to 4x smaller than the native per-pixel variance;
    neighbouring grid pixels are correlated.
    """
    if image.variance is None:
        return None
    xi, yi = _input_pixel_coords(image, grid)
    var = bilinear_sample(np.asarray(image.variance, dtype=np.float64), xi, yi, variance=True)
    return fits_to_png_orientation(var.reshape(grid.height_px, grid.width_px).astype(np.float32))
