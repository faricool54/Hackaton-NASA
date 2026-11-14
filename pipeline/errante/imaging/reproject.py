"""Reproject a SPHEREx image/cutout onto the field grid (WS2, P0).

SPHEREx images come in the detector's native orientation with TAN-SIP
distortion; cutouts can be non-square and NaN-padded at detector edges.
"""

from __future__ import annotations

import numpy as np

from ..data.fits_io import SpherexImage
from ..models import Grid


def reproject_to_grid(image: SpherexImage, grid: Grid) -> tuple[np.ndarray, np.ndarray]:
    """Return (data, bad_mask) on ``grid`` in PNG orientation (row 0 = north).

    TODO(WS2):
      - use ``reproject.reproject_interp`` (extra 'science') with the full SIP WCS
        of ``image`` -> ``imaging.grid.grid_wcs(grid)``; flux-conserving is not
        needed for display, but keep MJy/sr units.
      - reproject the bad-pixel mask with nearest-neighbour (``imaging.flags``).
      - pixels outside the cutout -> NaN, and report the valid fraction.
      - flip to PNG orientation with ``imaging.render.fits_to_png_orientation``.
    """
    raise NotImplementedError("WS2: reproject_to_grid")
