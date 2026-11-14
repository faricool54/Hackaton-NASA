"""Live endpoints that call external archives (WS4 wires them, WS1/WS3 implement the logic).

Rules: cache aggressively (in-memory LRU or disk via errante.data.cache), set
timeouts, and return a clear 502/504 JSON error when IRSA/JPL are slow or down,
never hang the UI. The static frontend works without these.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query, Request
from pydantic import Field, TypeAdapter

from errante.models import KnownObject, SearchResult

router = APIRouter(tags=["live"])
Detector = Annotated[int, Field(ge=1, le=6)]
search_adapter = TypeAdapter(SearchResult)
known_adapter = TypeAdapter(list[KnownObject])


@router.get("/search", response_model=SearchResult)
async def search(
    request: Request,
    ra: float = Query(ge=0, lt=360, allow_inf_nan=False),
    dec: float = Query(ge=-90, le=90, allow_inf_nan=False),
    detector: list[Detector] | None = Query(default=None, max_length=6),
) -> SearchResult:
    """SPHEREx frames covering a position (calls errante.data.irsa.search_frames)."""
    from errante.data.irsa import search_frames

    detectors = sorted(set(detector)) if detector else None
    return await request.app.state.live.call(
        "search",
        {"ra": ra, "dec": dec, "detectors": detectors},
        lambda: search_frames(ra, dec, detectors=detectors),
        search_adapter,
    )


@router.get("/known-objects", response_model=list[KnownObject])
async def known_objects(
    request: Request,
    ra: float = Query(ge=0, lt=360, allow_inf_nan=False),
    dec: float = Query(ge=-90, le=90, allow_inf_nan=False),
    mjd: float = Query(allow_inf_nan=False),
    radius_deg: float = Query(default=0.25, gt=0, le=5, allow_inf_nan=False),
) -> list[KnownObject]:
    """Known solar-system objects in a cone at an epoch (errante.science.known_objects)."""
    from errante.science.known_objects import objects_in_frame

    return await request.app.state.live.call(
        "known-objects",
        {"ra": ra, "dec": dec, "mjd": mjd, "radius_deg": radius_deg},
        lambda: objects_in_frame(ra, dec, radius_deg, mjd),
        known_adapter,
    )
