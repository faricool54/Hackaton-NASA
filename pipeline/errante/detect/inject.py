"""Injection-recovery: plant fake movers in REAL frames to measure limits (WS2, P1).

This is what makes the project scientifically honest: "we can recover objects
brighter than X mJy moving faster than Y"/h with Z % efficiency". Judges love it.
Injected candidates must carry status='injected' and never be shown as real.
"""

from __future__ import annotations

import numpy as np


def inject_mover(
    frames: list[np.ndarray],
    mjds: list[float],
    x0: float,
    y0: float,
    rate_px_per_day: tuple[float, float],
    flux: float,
    fwhm_px: float = 1.2,
) -> list[np.ndarray]:
    """Return copies of ``frames`` with a Gaussian PSF moving linearly.

    TODO(WS2): reuse ``errante.synthetic.add_gaussian`` (already implemented);
    then a ``recovery_grid(flux_values, rate_values)`` that runs the detector and
    reports the efficiency table (export as JSON for a 'Limits' page in the UI).
    """
    raise NotImplementedError("WS2: inject_mover")
