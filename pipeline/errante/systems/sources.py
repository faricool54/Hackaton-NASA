"""Where real 3D-model parameters come from (WS7).

Rule (AGENTS.md #5): never invent values. Each fetcher returns the parameters
it found *and* the exact query URL, so ``catalog`` can cite it and mark facts
``verified=True`` only for values checked against that source.

The catalog itself stores the checked values (the site must not depend on a
live archive); these fetchers are how they were checked, and the ``network``
tests in ``tests/test_systems.py`` re-run that check.

HTTP uses the standard library on purpose: ``urllib`` trusts the operating
system's certificate store, which also works on machines where an HTTPS proxy
or antivirus breaks the ``certifi`` bundle used by ``requests``.
"""

from __future__ import annotations

import html
import json
import os
import re
import urllib.parse
import urllib.request

from .. import __version__
from ..models import Orbit

EXOPLANET_ARCHIVE_TAP = "https://exoplanetarchive.ipac.caltech.edu/TAP/sync"
# SIMBAD's CfA mirror: CDS Strasbourg has been degraded since 2026-11-09 (CLAUDE.md).
SIMBAD_TAP = os.environ.get("ERRANTE_SIMBAD_TAP", "https://simbad.cfa.harvard.edu/simbad/sim-tap/sync")
GAIA_TAP = "https://gea.esac.esa.int/tap-server/tap/sync"
TIMEOUT_S = 60.0


def adql_str(value: str) -> str:
    """Quote a string literal for ADQL (single quotes doubled)."""
    return "'" + value.replace("'", "''") + "'"


def _get_json(url: str, params: dict[str, str]) -> tuple[object, str]:
    full = f"{url}?{urllib.parse.urlencode(params)}"
    request = urllib.request.Request(full, headers={"User-Agent": f"errante/{__version__} (NASA Space Apps 2026)"})
    with urllib.request.urlopen(request, timeout=TIMEOUT_S) as response:  # noqa: S310 (fixed https endpoints)
        return json.loads(response.read().decode("utf-8")), full


def tap_rows(service: str, adql: str) -> tuple[list[dict], str]:
    """Run a synchronous ADQL query; return (rows as dicts, exact query URL).

    The Exoplanet Archive takes ``query``/``format`` and answers a list of
    objects; SIMBAD and the Gaia archive speak standard TAP and answer
    ``{"metadata": [...], "data": [[...]]}``.
    """
    if service == EXOPLANET_ARCHIVE_TAP:
        payload, url = _get_json(service, {"query": adql, "format": "json"})
        if not isinstance(payload, list):
            raise ValueError(f"unexpected Exoplanet Archive answer for {url}")
        return payload, url
    payload, url = _get_json(service, {"REQUEST": "doQuery", "LANG": "ADQL", "FORMAT": "json", "QUERY": adql})
    if not isinstance(payload, dict) or "data" not in payload:
        raise ValueError(f"unexpected TAP answer for {url}")
    names = [column["name"] for column in payload["metadata"]]
    return [dict(zip(names, row, strict=True)) for row in payload["data"]], url


# pscomppars mixes solutions per column; each *_reflink names the paper behind that column.
PLANET_COLUMNS = (
    "pl_name, pl_letter, pl_orbper, pl_orbpererr1, pl_orbpererr2, pl_orbper_reflink, pl_orbsmax, pl_orbsmax_reflink, "
    "pl_orbeccen, pl_orbeccen_reflink, pl_orbincl, pl_bmasse, pl_bmassj, pl_bmassprov, pl_bmasse_reflink, "
    "pl_rade, pl_eqt, disc_refname"
)
STAR_COLUMNS = (
    "hostname, st_teff, st_teff_reflink, st_rad, st_rad_reflink, st_mass, st_mass_reflink, st_spectype, "
    "sy_dist, sy_plx, sy_pmra, sy_pmdec"
)


def exoplanet_archive_system(hostname: str) -> dict:
    """Host star + planets from the NASA Exoplanet Archive (TAP, table ``pscomppars``).

    ``hostname`` must be the archive's exact string, e.g. ``"Barnard's star"`` or
    ``"eps Ind A"``. ``pscomppars`` holds one row per planet with the archive's
    preferred value for each column (the reference is in ``pl_refname``).
    Returns ``{"hostname", "star": {...}, "planets": [...], "source": url}``.
    """
    adql = (
        f"select {STAR_COLUMNS}, {PLANET_COLUMNS} from pscomppars "
        f"where hostname = {adql_str(hostname)} order by pl_orbper"
    )
    rows, url = tap_rows(EXOPLANET_ARCHIVE_TAP, adql)
    if not rows:
        raise LookupError(f"no planets for hostname {hostname!r} in pscomppars ({url})")
    star_keys = [c.strip() for c in STAR_COLUMNS.split(",")]
    planet_keys = [c.strip() for c in PLANET_COLUMNS.split(",")]
    return {
        "hostname": hostname,
        "star": _clean_refs({k: rows[0].get(k) for k in star_keys}),
        "planets": [_clean_refs({k: row.get(k) for k in planet_keys}) for row in rows],
        "source": url,
    }


_HREF = re.compile(r"href=['\"]?([^'\" >]+)")
_TAG = re.compile(r"<[^>]+>")


def _clean_refs(row: dict) -> dict:
    """The archive returns references as HTML links: keep the text, add ``<key>_url``."""
    out = dict(row)
    for key, value in row.items():
        if isinstance(value, str) and "<a " in value:
            href = _HREF.search(value)
            out[key] = html.unescape(_TAG.sub("", value)).strip()
            out[f"{key}_url"] = href.group(1) if href else None
    return out


def simbad_star(identifier: str) -> dict:
    """Position, parallax, proper motion, RV and spectral type from SIMBAD (TAP).

    ``identifier`` is any SIMBAD identifier (``"GJ 699"``, ``"* eps Ind B"``,
    ``"V* R Dra"``). Values come from the ``basic`` table, with the bibcode of
    the reference SIMBAD adopted for each one. Positions are ICRS at J2000.
    """
    adql = (
        "SELECT b.main_id, b.ra, b.dec, b.plx_value, b.plx_err, b.pmra, b.pmdec, b.rvz_radvel, b.sp_type, "
        "b.coo_bibcode, b.plx_bibcode, b.pm_bibcode, b.rvz_bibcode, b.sp_bibcode "
        "FROM basic AS b JOIN ident AS i ON i.oidref = b.oid "
        f"WHERE i.id = {adql_str(identifier)}"
    )
    rows, url = tap_rows(SIMBAD_TAP, adql)
    if not rows:
        raise LookupError(f"SIMBAD does not know {identifier!r} ({url})")
    row = rows[0]
    return {
        "main_id": row["main_id"],
        "ra": row["ra"],
        "dec": row["dec"],
        "parallax_mas": row["plx_value"],
        "parallax_err_mas": row["plx_err"],
        "pm_ra_cosdec_mas_yr": row["pmra"],
        "pm_dec_mas_yr": row["pmdec"],
        "radial_velocity_km_s": row["rvz_radvel"],
        "spectral_type": row["sp_type"],
        "bibcodes": {k: row[f"{k}_bibcode"] for k in ("coo", "plx", "pm", "rvz", "sp")},
        "source": url,
    }


def gaia_dr3_source(source_id: int) -> dict:
    """Astrometry (epoch J2016.0), RV and GSP-Phot Teff of one Gaia DR3 source."""
    adql = (
        "SELECT source_id, ref_epoch, ra, dec, parallax, parallax_error, pmra, pmdec, radial_velocity, "
        "phot_g_mean_mag, teff_gspphot FROM gaiadr3.gaia_source "
        f"WHERE source_id = {int(source_id)}"
    )
    rows, url = tap_rows(GAIA_TAP, adql)
    if not rows:
        raise LookupError(f"Gaia DR3 source {source_id} not found ({url})")
    return {**rows[0], "source": url}


def sbdb_orbit(designation: str) -> Orbit:
    """Heliocentric osculating elements of an asteroid/comet/TNO from JPL SBDB.

    TODO(WS7-3): GET https://ssd-api.jpl.nasa.gov/sbdb.api?sstr=<designation> →
    ``orbit.elements`` (a, e, i, om, w, ma, epoch). Convert to ``Orbit`` with
    ``parent="sun"``, ``epoch_mjd = JD - 2400000.5``, period from ``per`` (days).
    Also return H, diameter, albedo and rotation period when present (``phys_par``).
    """
    raise NotImplementedError("WS7: sbdb_orbit")


def shape_model(designation: str) -> str | None:
    """URL of a 3D shape model (glTF/OBJ) for an asteroid, if one exists.

    TODO(WS7-6, P2): look at NASA 3D Resources (https://science.nasa.gov/3d-resources/)
    and DAMIT (lightcurve-inversion shapes). Convert OBJ → glTF offline and keep
    files small (< 1 MB). Return None when there is no shape model: the UI then
    draws a procedural body and says so.
    """
    raise NotImplementedError("WS7: shape_model")
