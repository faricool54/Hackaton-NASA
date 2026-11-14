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

import numpy as np

from ..data.fits_io import SpherexImage
from ..models import Grid
from .flags import DEFAULT_BAD, bad_pixel_mask
from .grid import grid_wcs
from .render import fits_to_png_orientation

# A bilinear sample is kept only if at least this much of its interpolation
# weight comes from finite input pixels (NaN-padded cutout edges).
MIN_FINITE_WEIGHT = 0.5


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


def bilinear_sample(img: np.ndarray, x: np.ndarray, y: np.ndarray) -> np.ndarray:
    """Sample ``img`` at 0-based (x, y); NaN outside the array or where mostly NaN."""
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
        total += np.where(finite, v, 0.0) * wgt
        weight += np.where(finite, wgt, 0.0)
    with np.errstate(invalid="ignore", divide="ignore"):
        out[ok] = np.where(weight >= MIN_FINITE_WEIGHT, total / weight, np.nan)
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


def fill_saturated(pixels: np.ndarray, saturated: np.ndarray, max_iter: int = 10) -> np.ndarray:
    """Copy of ``pixels`` where NaN ``saturated`` pixels take their brightest finite neighbour.

    SPHEREx sets the saturated core of bright stars to NaN (FLAGS bit OVERFLOW;
    e.g. Barnard's Star, K = 4.5). Left as NaN they render as a black hole in
    the middle of the brightest star of the field. The neighbour maximum is a
    lower bound of the true value, good for display only: the pixel stays in
    the bad mask. Larger cores are filled from the outside in.
    """
    out = np.array(pixels, dtype=np.float64, copy=True)
    todo = saturated & np.isnan(out)
    for _ in range(max_iter):
        if not todo.any():
            break
        padded = np.pad(out, 1, constant_values=np.nan)
        ny, nx = out.shape
        neighbours = np.stack(
            [padded[1 + dy : 1 + dy + ny, 1 + dx : 1 + dx + nx] for dy in (-1, 0, 1) for dx in (-1, 0, 1) if dy or dx]
        )
        has = np.isfinite(neighbours).any(axis=0) & todo
        if not has.any():
            break
        best = np.max(np.where(np.isfinite(neighbours), neighbours, -np.inf), axis=0)
        out[has] = best[has]
        todo &= ~has
    return out


def reproject_to_grid(
    image: SpherexImage,
    grid: Grid,
    *,
    subtract_zodi: bool = True,
    bad_flags: tuple[str, ...] = DEFAULT_BAD,
    fill_saturated_cores: bool = True,
) -> tuple[np.ndarray, np.ndarray]:
    """Return (data, bad_mask) on ``grid`` in PNG orientation (row 0 = north).

    - ``data`` keeps MJy/sr. By default the zodiacal model (ZODI HDU) is
      subtracted first (``IMAGE - ZODI``), so the sky level is comparable
      between epochs. Grid pixels outside the cutout are NaN. Saturated
      (OVERFLOW) NaN cores are filled for display (``fill_saturated``).
    - ``bad_mask`` is True where the value cannot be trusted: outside the
      cutout, NaN, or a ``bad_flags`` bit set in the nearest input pixel.
      Flagged pixels are NOT blanked in ``data`` (display them; report the
      fraction). SOURCE/TRANSIENT/OUTLIER are not in ``DEFAULT_BAD`` on purpose.
    """
    xi, yi = _input_pixel_coords(image, grid)
    shape = (grid.height_px, grid.width_px)
    pixels = np.asarray(image.data_minus_zodi if subtract_zodi else image.data)
    flags = None if image.flags is None else np.asarray(image.flags)
    if fill_saturated_cores and flags is not None:
        pixels = fill_saturated(pixels, bad_pixel_mask(flags, ("OVERFLOW",)))
    data = bilinear_sample(pixels, xi, yi).reshape(shape)

    bad = ~np.isfinite(data)
    if flags is not None:
        flagged = bad_pixel_mask(flags, bad_flags)
        bad |= nearest_sample(flagged, xi, yi, fill=True).reshape(shape)

    return fits_to_png_orientation(data.astype(np.float32)), fits_to_png_orientation(bad)
