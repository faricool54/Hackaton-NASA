"""Remove the static sky so only things that changed remain (WS2, P0).

Caveat: SPHEREx is a *spectral* survey. The same star has a different
brightness in every frame because each frame samples a different wavelength
(linear variable filter). Compare frames of the SAME detector and similar
wavelength, or normalise per star, or work on positions only.
"""

from __future__ import annotations

import numpy as np


def static_sky(stack: np.ndarray, bad: np.ndarray | None = None) -> np.ndarray:
    """Per-pixel robust median of a (n_frames, h, w) stack -> (h, w) template.

    TODO(WS2): nan-median over frames where ``bad`` is False; with few frames
    (<4) a min/median mix works better. Group by detector first.
    """
    raise NotImplementedError("WS2: static_sky")


def residuals(frame: np.ndarray, template: np.ndarray, scale: float | None = None) -> np.ndarray:
    """frame - scale*template; fit ``scale`` on stars if None (wavelength-dependent flux).

    TODO(WS2): also export residual PNGs as an optional UI layer ("difference").
    """
    raise NotImplementedError("WS2: residuals")
