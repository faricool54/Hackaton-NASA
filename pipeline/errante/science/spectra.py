"""Coarse spectrum of a candidate from its detections (WS3, P1).

Each SPHEREx frame samples a different wavelength at a given sky position, so
the detections of one mover across frames form a low-resolution 0.75-5 um
spectrum. That is SPHEREx's superpower and a great UI feature:
  asteroids  -> reflected sunlight (rises toward ~1-2.5 um, 3 um hydration band)
  cold brown dwarfs -> very red, strong CH4 absorption ~3.3 um, bright ~4-5 um
  stars -> Rayleigh-Jeans tail (falls with wavelength)
"""

from __future__ import annotations

from ..models import Candidate, SpectrumPoint

MJY_PER_MJY_SR_PER_PIXEL = (6.15 / 206264.806) ** 2 * 1e9  # MJy/sr * px -> mJy (6.15" px)


def candidate_spectrum(candidate: Candidate, wavelengths: dict[str, tuple[float, float]]) -> list[SpectrumPoint]:
    """Build spectrum points from detections. ``wavelengths[frame_id] = (um, bw_um)``
    at the detection position (``data.fits_io.wavelength_at``).

    TODO(WS3): aperture photometry on the frame (not the PNG!), MJy/sr -> mJy
    with the pixel solid angle (header OMEGA_MEDIAN [arcsec^2] is more exact than
    6.15^2), errors from VARIANCE; mark flagged points.
    """
    raise NotImplementedError("WS3: candidate_spectrum")


def color_class(points: list[SpectrumPoint]) -> str:
    """'star-like' | 'neutral' | 'red' | 'very-red' from 1-2 um vs 4-5 um flux ratio.

    TODO(WS3): simple ratio with thresholds tuned on known stars/asteroids; always
    return it with a caveat note in the UI.
    """
    raise NotImplementedError("WS3: color_class")
