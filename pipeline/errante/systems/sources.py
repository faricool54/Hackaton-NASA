"""Where real 3D-model parameters come from (WS7). All stubs for now.

Rule (AGENTS.md #5): never invent values. Each fetcher returns the parameters
it found *and* the source, so ``catalog`` can mark facts ``verified=True``.
Network functions import their HTTP/astro libraries inside the function and
their tests are marked ``@pytest.mark.network``.
"""

from __future__ import annotations

from ..models import Orbit


def exoplanet_archive_system(hostname: str) -> dict:
    """Host star + planets from the NASA Exoplanet Archive (TAP, table ``pscomppars``).

    TODO(WS7): query https://exoplanetarchive.ipac.caltech.edu/TAP/sync with
    ``select pl_name, pl_orbper, pl_orbsmax, pl_orbeccen, pl_orbincl, pl_bmasse,
    pl_rade, st_teff, st_rad, st_mass, st_spectype, sy_dist from pscomppars
    where hostname = '<hostname>'``. Return a dict with ``star`` and ``planets``
    plus the archive URL used as ``source``. Hosts to cover first: "Barnard's star"
    (check the exact hostname string in the archive), "eps Ind A".
    """
    raise NotImplementedError("WS7: exoplanet_archive_system")


def sbdb_orbit(designation: str) -> Orbit:
    """Heliocentric osculating elements of an asteroid/comet/TNO from JPL SBDB.

    TODO(WS7): GET https://ssd-api.jpl.nasa.gov/sbdb.api?sstr=<designation> →
    ``orbit.elements`` (a, e, i, om, w, ma, epoch). Convert to ``Orbit`` with
    ``parent="sun"``, ``epoch_mjd = JD - 2400000.5``, period from ``per`` (days).
    Also return H, diameter, albedo and rotation period when present (``phys_par``).
    """
    raise NotImplementedError("WS7: sbdb_orbit")


def simbad_star(name: str) -> dict:
    """Position, parallax, proper motion, RV, spectral type and Teff from SIMBAD / Gaia DR3.

    TODO(WS7): astroquery.simbad with votable fields ``plx_value, pmra, pmdec,
    rvz_radvel, sp_type``; Teff from Gaia DR3 ``astrophysical_parameters`` when
    available. Feeds ``SpaceMotion`` and the star body facts.
    """
    raise NotImplementedError("WS7: simbad_star")


def shape_model(designation: str) -> str | None:
    """URL of a 3D shape model (glTF/OBJ) for an asteroid, if one exists.

    TODO(WS7, P2): look at NASA 3D Resources (https://science.nasa.gov/3d-resources/)
    and DAMIT (lightcurve-inversion shapes). Convert OBJ → glTF offline and keep
    files small (< 1 MB). Return None when there is no shape model: the UI then
    draws a procedural body and says so.
    """
    raise NotImplementedError("WS7: shape_model")
