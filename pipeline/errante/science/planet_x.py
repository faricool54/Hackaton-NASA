"""Planet X / Planet Nine context for the UI and field selection (WS3, P1).

Honest framing (docs/SCIENCE.md): a Planet-Nine-like body (~400-800 AU,
V ~ 21-25) is most likely BELOW what single SPHEREx exposures can detect. The
project's value is a public tool that shows how such a search works and finds
real moving objects (asteroids, TNOs, nearby brown dwarfs), plus measured
detection limits that say how far from Planet X we are. Never claim a discovery.
"""

from __future__ import annotations

from ..models import SkyCoord


def planet_nine_search_region() -> list[SkyCoord]:
    """Polygon of the predicted Planet Nine region for the sky map overlay.

    TODO(WS3): take it from Brown & Batygin (2021, AJ 162, 219) and/or the
    later updates; cite the source in the UI. Do not invent coordinates.
    """
    raise NotImplementedError("WS3: planet_nine_search_region")


def detectability(r_au: float, diameter_km: float, albedo: float = 0.3) -> dict:
    """Expected V mag, rate ("/h) and SPHEREx detectability for a hypothetical body.

    TODO(WS3): H from diameter+albedo, V ≈ H + 5 log10(r·Δ) (opposition), rate from
    ``science.motion.opposition_rate_arcsec_per_hour``; compare with the limits
    measured by ``detect.inject``. Powers an interactive "what could SPHEREx see?"
    widget in the frontend.
    """
    raise NotImplementedError("WS3: detectability")
