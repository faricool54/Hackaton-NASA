"""Common north-up TAN grid for a field (implemented; WS2 owns changes).

Every frame of a field is reprojected onto the same grid so the browser can
blink PNGs pixel-on-pixel and draw overlays with plain x/y.
"""

from __future__ import annotations

import numpy as np
from astropy.wcs import WCS

from ..models import Grid, SkyCoord

SPHEREX_PIXEL_SCALE_ARCSEC = 6.15  # native SPHEREx pixel (docs/DATA.md)


def make_grid(ra: float, dec: float, size_deg: float, pixel_scale_arcsec: float = SPHEREX_PIXEL_SCALE_ARCSEC) -> Grid:
    n = int(np.ceil(size_deg * 3600.0 / pixel_scale_arcsec))
    n += n % 2  # even size -> center falls between pixels, symmetric
    cdelt = pixel_scale_arcsec / 3600.0
    wcs = {
        "CTYPE1": "RA---TAN",
        "CTYPE2": "DEC--TAN",
        "CRVAL1": float(ra),
        "CRVAL2": float(dec),
        "CRPIX1": n / 2 + 0.5,
        "CRPIX2": n / 2 + 0.5,
        "CDELT1": -cdelt,  # east left
        "CDELT2": cdelt,  # north up (in FITS, y up)
        "CUNIT1": "deg",
        "CUNIT2": "deg",
        "NAXIS1": n,
        "NAXIS2": n,
    }
    return Grid(
        center=SkyCoord(ra=ra % 360, dec=dec),
        width_px=n,
        height_px=n,
        pixel_scale_arcsec=pixel_scale_arcsec,
        wcs=wcs,
    )


def grid_wcs(grid: Grid) -> WCS:
    hdr = {k: v for k, v in grid.wcs.items() if not k.startswith("NAXIS")}
    w = WCS(naxis=2)
    w.wcs.ctype = [hdr["CTYPE1"], hdr["CTYPE2"]]
    w.wcs.crval = [hdr["CRVAL1"], hdr["CRVAL2"]]
    w.wcs.crpix = [hdr["CRPIX1"], hdr["CRPIX2"]]
    w.wcs.cdelt = [hdr["CDELT1"], hdr["CDELT2"]]
    w.wcs.cunit = [hdr.get("CUNIT1", "deg"), hdr.get("CUNIT2", "deg")]
    w.pixel_shape = (grid.width_px, grid.height_px)
    return w


def sky_to_png_xy(grid: Grid, ra, dec):
    """ICRS deg -> PNG-convention pixel (top-left origin, y down). Works on arrays."""
    x0, y0 = grid_wcs(grid).all_world2pix(ra, dec, 0)  # 0-based FITS (y up)
    return x0, (grid.height_px - 1) - y0


def png_xy_to_sky(grid: Grid, x, y):
    """PNG-convention pixel -> ICRS deg (ra, dec). Works on arrays."""
    y0 = (grid.height_px - 1) - np.asarray(y, dtype=float)
    ra, dec = grid_wcs(grid).all_pix2world(x, y0, 0)
    return np.mod(ra, 360.0), dec
