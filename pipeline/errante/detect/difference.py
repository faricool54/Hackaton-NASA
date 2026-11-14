"""Remove the static sky so only things that changed remain (WS2).

Caveat: SPHEREx is a *spectral* survey. The same star has a different
brightness in every frame because each frame samples a different wavelength
(linear variable filter). Compare frames of the SAME detector and similar
wavelength, or normalise per star, or work on positions only. The
season-level, flux-matched version for display lives in ``imaging.compare``.
"""

from __future__ import annotations

import warnings

import numpy as np

MIN_SCALE_SNR = 20.0
MIN_SCALE_PIXELS = 20


def static_sky(stack: np.ndarray, bad: np.ndarray | None = None) -> np.ndarray:
    """Per-pixel robust median of a (n_frames, h, w) stack -> (h, w) template.

    Pixels flagged in ``bad`` (same shape as ``stack``) are ignored; a pixel
    with no usable frame is NaN. Group frames by detector first: different
    detectors see different wavelengths.
    """
    stack = np.asarray(stack, dtype=np.float64)
    if stack.ndim != 3:
        raise ValueError("stack must be (n_frames, h, w)")
    values = np.where(bad, np.nan, stack) if bad is not None else stack
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)  # all-NaN pixels -> NaN
        return np.nanmedian(values, axis=0)


def fit_scale(frame: np.ndarray, template: np.ndarray, noise: float | None = None) -> float:
    """Robust ``s`` with ``frame ~ s * template`` on bright pixels of both (field stars).

    ``noise`` is the per-pixel sigma of ``template``; estimated from it when None.
    Returns 1.0 when fewer than ``MIN_SCALE_PIXELS`` pixels are bright enough.
    """
    ok = np.isfinite(frame) & np.isfinite(template)
    if not ok.any():
        return 1.0
    t = template[ok]
    f = frame[ok]
    t0 = t - np.median(t)
    sigma = noise or float(1.4826 * np.median(np.abs(t0))) or 1e-6
    use = (t0 / sigma >= MIN_SCALE_SNR) & (f > 0) & (t > 0)
    if use.sum() < MIN_SCALE_PIXELS:
        return 1.0
    return float(np.median(f[use] / t[use]))


def residuals(frame: np.ndarray, template: np.ndarray, scale: float | None = None) -> np.ndarray:
    """``frame - scale * template``; ``scale`` is fitted on stars when None (wavelength-dependent flux)."""
    s = fit_scale(frame, template) if scale is None else scale
    return np.asarray(frame, dtype=np.float64) - s * np.asarray(template, dtype=np.float64)
