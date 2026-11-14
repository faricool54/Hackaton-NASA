"""Find SPHEREx frames covering a sky position via IRSA TAP / SIA (WS1, P0).

⚠ IRSA was NOT reachable from the environment that generated this skeleton, so
the details below come from IRSA documentation/tutorials and must be verified
on your machine first (docs/DATA.md §IRSA). Table and collection names change
between releases (qr2 -> qr3 -> dr1).

TAP (sync, CSV):  https://irsa.ipac.caltech.edu/TAP/sync?REQUEST=doQuery&LANG=ADQL&FORMAT=csv&QUERY=...
Tables (documented): spherex.plane (planeid, time_bounds_lower [MJD], poly,
energy_bandpassname='SPHEREx-D<n>') and spherex.artifact (uri, planeid).
SIA2: https://irsa.ipac.caltech.edu/SIA?COLLECTION=spherex_qr3&POS=circle+<ra>+<dec>+<r>
Collections documented: spherex_qr2, spherex_qr2_deep, spherex_qr3, spherex_qr3_deep
(TODO(WS1): find the DR1 names).
"""

from __future__ import annotations

from ..models import FrameRef, SearchResult, SkyCoord  # noqa: F401  (for the implementation)

ADQL_FRAMES_AT_POSITION = """
SELECT a.uri, p.planeid, p.time_bounds_lower, p.energy_bandpassname
FROM spherex.artifact a
JOIN spherex.plane p ON a.planeid = p.planeid
WHERE 1 = CONTAINS(POINT('ICRS', {ra}, {dec}), p.poly)
{band_clause}
ORDER BY p.time_bounds_lower
"""


def build_query(ra: float, dec: float, detector: int | None = None) -> str:
    band = f"AND p.energy_bandpassname = 'SPHEREx-D{detector}'" if detector else ""
    return ADQL_FRAMES_AT_POSITION.format(ra=ra, dec=dec, band_clause=band)


def search_frames(
    ra: float,
    dec: float,
    radius_deg: float = 0.0,
    detectors: list[int] | None = None,
    mjd_min: float | None = None,
    mjd_max: float | None = None,
) -> SearchResult:
    """All SPHEREx L2 frames whose footprint contains (ra, dec).

    TODO(WS1):
      - run ``build_query`` against IRSA_TAP_SYNC with ``requests`` (FORMAT=csv)
        or ``astroquery.ipac.irsa.Irsa.query_tap`` (extra 'science');
      - parse uri -> FrameRef (obs_id/detector from the file name, see
        ``data.s3.parse_key``; release from the path);
      - cache results on disk (``data.cache``), queries take 3-20 s;
      - retry on timeouts / 5xx, never run many TAP queries in parallel.
    """
    raise NotImplementedError("WS1: search_frames")
