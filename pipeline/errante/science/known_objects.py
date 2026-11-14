"""Which known solar-system objects are in a frame? (WS3, P0)

Services (no account needed; verify reachability from your network):
  JPL SB Identification  https://ssd-api.jpl.nasa.gov/sb_ident.api
     docs: https://ssd-api.jpl.nasa.gov/doc/sb_ident.html
     Takes an observer location + time + field of view; supports SPACECRAFT
     observers via a heliocentric/geocentric position vector -> pass SPHEREx's
     position from the header (X_SC, Y_SC, Z_SC [km, geocentric]).
  JPL Horizons API       https://ssd.jpl.nasa.gov/api/horizons.api
     ephemeris of ONE named object (e.g. Makemake '136472') at many times.
  IMCCE SkyBoT           https://ssp.imcce.fr/webservices/skybot/api/conesearch.php
     cone search at an epoch (JD), JSON, CORS-enabled (browser can call it).
SPHEREx is in low-Earth orbit (~7000 km from Earth's center): that offset is
~10" at 1 AU (1.5 px!), ~3" at 3 AU, ~0.2" at 40 AU. Geocentric ('500') is OK
for TNOs; for asteroids use the spacecraft position from the header.
"""

from __future__ import annotations

from ..models import Candidate, KnownMatch, KnownObject


def objects_in_frame(ra: float, dec: float, radius_deg: float, mjd: float) -> list[KnownObject]:
    """Known objects (with predicted position) inside a cone at one epoch.

    TODO(WS3): SkyBoT conesearch (simplest) or JPL SBIdent; cache by (ra,dec,mjd).
    Return positions only for this mjd; the caller merges per frame.
    """
    raise NotImplementedError("WS3: objects_in_frame")


def ephemeris(designation: str, mjds: list[float]) -> list[tuple[float, float, float]]:
    """(mjd, ra, dec) for a named object from JPL Horizons (observer '500@399').

    TODO(WS3): Horizons API with EPHEM_TYPE=OBSERVER, TLIST of JDs, CSV output.
    Used to build showcase fields around known movers (e.g. Makemake, an asteroid).
    """
    raise NotImplementedError("WS3: ephemeris")


def crossmatch(candidates: list[Candidate], known: list[KnownObject], max_sep_arcsec: float = 15.0) -> list[Candidate]:
    """Set ``known_match`` + status='known' when a candidate track matches a known object.

    TODO(WS3): compare per-frame positions (same frame_id); median separation.
    2-3 SPHEREx pixels (12-18") is a reasonable tolerance for ephemeris + centroid error.
    """
    raise NotImplementedError("WS3: crossmatch")


__all__ = ["objects_in_frame", "ephemeris", "crossmatch", "KnownMatch"]
