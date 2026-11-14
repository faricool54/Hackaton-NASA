"""Live endpoints that call external archives (WS4 wires them, WS1/WS3 implement the logic).

Rules: cache aggressively (in-memory LRU or disk via errante.data.cache), set
timeouts, and return a clear 502/504 JSON error when IRSA/JPL are slow or down,
never hang the UI. The static frontend works without these.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from errante.models import KnownObject, SearchResult

router = APIRouter(tags=["live"])


@router.get("/search", response_model=SearchResult)
def search(
    ra: float = Query(ge=0, lt=360),
    dec: float = Query(ge=-90, le=90),
    detector: list[int] | None = Query(default=None),
) -> SearchResult:
    """SPHEREx frames covering a position (calls errante.data.irsa.search_frames)."""
    from errante.data.irsa import search_frames

    try:
        return search_frames(ra, dec, detectors=detector)
    except NotImplementedError as e:
        raise HTTPException(status_code=501, detail=f"Not implemented yet: {e}") from e


@router.get("/known-objects", response_model=list[KnownObject])
def known_objects(
    ra: float = Query(ge=0, lt=360),
    dec: float = Query(ge=-90, le=90),
    mjd: float = Query(),
    radius_deg: float = Query(default=0.25, gt=0, le=5),
) -> list[KnownObject]:
    """Known solar-system objects in a cone at an epoch (errante.science.known_objects)."""
    from errante.science.known_objects import objects_in_frame

    try:
        return objects_in_frame(ra, dec, radius_deg, mjd)
    except NotImplementedError as e:
        raise HTTPException(status_code=501, detail=f"Not implemented yet: {e}") from e
