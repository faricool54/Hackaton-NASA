"""Object card endpoint (WS4 over WS3 ``errante.science.context``; contract 0.5.0, C05).

GET /api/object?name=<text>                       catalog context of a named object
GET /api/object?ra=<deg>&dec=<deg>                catalog context of a clicked position
    optional: epoch_mjd (epoch of the position, default the SPHEREx-era MJD 61000), radius_arcsec (default 8,
    at most 12: about two SPHEREx pixels)

200  ObjectContextResponse; ``partial: true`` when a catalog did not answer in time (its values are unknown,
     not negative). A position with nothing catalogued is a 200 with match 'none', not a 404.
404  the NAME is not known to SIMBAD/Sesame (CfA)
422  invalid parameters: give exactly one of name or ra+dec
502  the name resolver could not be reached, or an unexpected failure
503  capacity busy (Retry-After)
504  nothing could be answered within the deadline (only when a name was not resolved in time)
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request

from errante.models import ObjectContextResponse

router = APIRouter(tags=["live"])

# WS3 adopts a much brighter Gaia source inside the radius because it "dominates the SPHEREx pixel" (6.15"): at
# 60" it adopted a star 57.7" away with that wording (review 2026-11-15). Clicks use the 8" default (~1.3 px).
MAX_RADIUS_ARCSEC = 12.0


@router.get("/object", response_model=ObjectContextResponse)
async def object_context(
    request: Request,
    name: str | None = Query(default=None, min_length=1, max_length=200, description="SIMBAD/Sesame name"),
    ra: float | None = Query(default=None, ge=0, lt=360, allow_inf_nan=False, description="ICRS RA [deg]"),
    dec: float | None = Query(default=None, ge=-90, le=90, allow_inf_nan=False, description="ICRS Dec [deg]"),
    epoch_mjd: float | None = Query(
        default=None, ge=15020, le=88070, allow_inf_nan=False, description="Epoch of the position [MJD]"
    ),
    radius_arcsec: float | None = Query(
        default=None, gt=0, le=MAX_RADIUS_ARCSEC, allow_inf_nan=False, description="Match radius [arcsec]"
    ),
) -> ObjectContextResponse:
    """Who is at this position (or who is this name) according to SIMBAD, Gaia DR3, AAVSO VSX, the NASA Exoplanet
    Archive, 2MASS and AllWISE. Catalog context from other missions: never SPHEREx measurements."""
    if name is not None:
        name = name.strip()
        if not name:
            raise HTTPException(422, "Object name must not be blank.")
        if ra is not None or dec is not None:
            raise HTTPException(422, "Give either a name or ra and dec, not both.")
    elif ra is None or dec is None:
        raise HTTPException(422, "Give a name, or both ra and dec.")
    return await request.app.state.objects.describe(
        ra=ra, dec=dec, name=name, epoch_mjd=epoch_mjd, radius_arcsec=radius_arcsec
    )
