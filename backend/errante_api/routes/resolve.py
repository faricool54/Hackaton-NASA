"""Name-resolution proxy endpoint (WS4).

GET /api/resolve-name?name=<text>

Calls Sesame/CfA (vizier.cfa.harvard.edu) to resolve an arbitrary name or
coordinate string and returns RA/Dec + object type. Avoids CORS issues for
the browser and caches results in memory.

Returns:
    200  { ra, dec, object_type, resolved_name, source }
    404  when Sesame cannot find the name
    502  when Sesame is unreachable or returns an unexpected response
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from functools import lru_cache
from typing import Literal

import httpx
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

router = APIRouter(tags=["live"])

# ObjectType values from the contract (models.py / types.ts)
ObjectType = Literal[
    "asteroid",
    "comet",
    "tno",
    "dwarf_planet",
    "planet",
    "star",
    "brown_dwarf",
    "unknown",
]

# Map Sesame/SIMBAD otype codes → contract ObjectType.
# SIMBAD otype reference: https://simbad.cds.unistra.fr/guide/otypes.htx
_OTYPE_MAP: dict[str, ObjectType] = {
    # Stars
    "*": "star",
    "Star": "star",
    "V*": "star",  # variable star
    "V": "star",
    "RG*": "star",  # red giant
    "Mi*": "star",  # Mira-type variable
    "Pe*": "star",  # peculiar star
    "BY*": "star",  # BY Dra variable
    "RS*": "star",
    "Or*": "star",  # T Tauri / pre-main-sequence
    "TT*": "star",
    "FU*": "star",
    "Al*": "star",  # eclipsing binary
    "EB*": "star",
    "SB*": "star",  # spectroscopic binary
    "LP*": "star",  # long-period variable
    "HB*": "star",  # horizontal branch
    "RR*": "star",
    "Ce*": "star",  # Cepheid
    "LPV": "star",
    # Brown dwarfs
    "BD*": "brown_dwarf",
    "BrownD": "brown_dwarf",
    "bd*": "brown_dwarf",
    # Planets and solar-system bodies
    "Pl": "planet",
    "Planet": "planet",
    # Comets
    "Com": "comet",
    "Comet": "comet",
    # Asteroids
    "Ast": "asteroid",
    "Asteroid": "asteroid",
    "MiP": "asteroid",  # minor planet
    # TNOs / KBOs
    "TNO": "tno",
    "KBO": "tno",
    # Dwarf planets (also often listed as TNO/KBO in SIMBAD)
    "DwP": "dwarf_planet",
}


def _parse_sesame_xml(xml_text: str) -> tuple[float, float, str, ObjectType]:
    """Parse Sesame XML response.

    Returns (ra_deg, dec_deg, resolved_name, object_type).
    Raises ValueError when the object is not found or the XML cannot be parsed.
    """
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        raise ValueError(f"Could not parse Sesame XML: {exc}") from exc

    # Sesame wraps results in <Resolver> elements; use the first successful one.
    resolver = root.find(".//Resolver")
    if resolver is None:
        raise ValueError("No Resolver element in Sesame response")

    jpos = resolver.findtext("jpos")
    if not jpos:
        raise ValueError("Sesame returned no position (jpos missing)")

    # jpos format: "HH MM SS.ss +DD MM SS.s" or decimal degrees separated by space
    parts = jpos.strip().split()
    if len(parts) == 2:
        ra_deg = float(parts[0])
        dec_deg = float(parts[1])
    elif len(parts) == 6:
        # Sexagesimal RA + Dec
        ra_h, ra_m, ra_s = float(parts[0]), float(parts[1]), float(parts[2])
        ra_deg = 15.0 * (ra_h + ra_m / 60.0 + ra_s / 3600.0)
        sign = -1.0 if parts[3].startswith("-") else 1.0
        dec_d = abs(float(parts[3]))
        dec_m, dec_s = float(parts[4]), float(parts[5])
        dec_deg = sign * (dec_d + dec_m / 60.0 + dec_s / 3600.0)
    else:
        raise ValueError(f"Unexpected jpos format: {jpos!r}")

    # Try to extract canonical name
    resolved_name = resolver.findtext("oname") or resolver.findtext("name") or ""

    # Map otype → ObjectType
    otype_raw = resolver.findtext("otype") or ""
    # SIMBAD otype may carry trailing qualifiers like "V*|RG*"; take the first token
    otype_key = re.split(r"[|/\s]", otype_raw.strip())[0] if otype_raw.strip() else ""
    object_type: ObjectType = _OTYPE_MAP.get(otype_key, "unknown")

    return ra_deg, dec_deg, resolved_name, object_type


@lru_cache(maxsize=200)
def _resolve_cached(name: str) -> dict:
    """Cached Sesame lookup.  Returns the response dict or raises HTTPException."""
    url = f"https://vizier.cfa.harvard.edu/viz-bin/nph-sesame/-oxp/SNV?{name}"
    try:
        response = httpx.get(url, timeout=5.0)
    except httpx.TimeoutException as exc:
        raise HTTPException(status_code=502, detail="Sesame timed out") from exc
    except httpx.RequestError as exc:
        raise HTTPException(status_code=502, detail=f"Sesame unreachable: {exc}") from exc

    if response.status_code == 200:
        try:
            ra, dec, resolved_name, object_type = _parse_sesame_xml(response.text)
        except ValueError as exc:
            # Sesame returned 200 but with an empty / not-found response
            raise HTTPException(
                status_code=404,
                detail=f"Name not found in Sesame: {exc}",
            ) from exc
        return {
            "ra": ra,
            "dec": dec,
            "object_type": object_type,
            "resolved_name": resolved_name or name,
            "source": "sesame/cfa",
        }

    if response.status_code == 404:
        raise HTTPException(status_code=404, detail=f"Name not found: {name!r}")

    raise HTTPException(
        status_code=502,
        detail=f"Sesame returned unexpected status {response.status_code}",
    )


class ResolvedRegion(BaseModel):
    ra: float
    dec: float
    object_type: str
    resolved_name: str
    source: str


@router.get("/resolve-name", response_model=ResolvedRegion)
def resolve_name(
    name: str = Query(min_length=1, description="Object name or coordinate string"),
) -> ResolvedRegion:
    """Resolve a name via Sesame/CfA and return RA/Dec + object type.

    Proxies the request so the browser avoids CORS issues.
    Results are cached in memory (LRU, 200 entries).

    - **200** – name resolved successfully.
    - **404** – name not found in Sesame.
    - **502** – Sesame is unreachable or returned an unexpected response.
    """
    result = _resolve_cached(name.strip())
    return ResolvedRegion(**result)
