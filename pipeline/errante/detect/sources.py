"""Point-source detection on one reprojected frame (WS2, P0)."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class Source:
    frame_id: str
    mjd: float
    x: float  # PNG convention (models.py)
    y: float
    flux: float  # MJy/sr summed in aperture (convert to mJy in science/)
    snr: float
    flags: int = 0


def find_sources(
    data: np.ndarray,
    bad: np.ndarray | None,
    frame_id: str,
    mjd: float,
    fwhm_px: float = 1.2,
    threshold_sigma: float = 5.0,
) -> list[Source]:
    """Detect point sources.

    TODO(WS2): photutils ``DAOStarFinder``/``find_peaks`` on background-subtracted
    data (``photutils.background.Background2D`` or sigma-clipped median), mask
    ``bad``; SNR from the VARIANCE plane if available. SPHEREx PSF FWHM is
    ~5-7.5" (~1-1.2 px): sources are barely resolved, use small apertures.
    """
    raise NotImplementedError("WS2: find_sources")
