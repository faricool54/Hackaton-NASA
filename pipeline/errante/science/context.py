"""Object context for a clicked sky position or a name (WS3-10, C05; data card + inputs of the 3D model).

What the panel shows next to the SPHEREx video and spectrum: who the object is and what OTHER catalogs measured
about it. Every value carries its catalog, URL and retrieval time; nothing is filled from memory. SPHEREx itself
does not measure distances, radii or masses: those come from Gaia DR3 (ESA) and are labelled as such.

Sources (all verified live on 2026-11-15, see ``docs/SCIENCE.md`` §3.1 and the fixtures in
``pipeline/tests/fixtures/ws3/context/``):

- **Sesame at CfA** (``-oxpI`` XML): SIMBAD main id, object type, spectral type, J2000 position, proper motion,
  parallax, RV and identifiers (the Gaia DR3 cross-id among them). CDS Strasbourg is degraded: only the CfA mirror
  is used. Gotcha: ``GJ 699`` resolves only through "VizieR (local)" to an old position 8.6' from Barnard's Star,
  with no proper motion: such answers are flagged.
- **Gaia DR3 at the ESA archive TAP**: ``gaiadr3.gaia_source`` (astrometry, photometry, RUWE, DSC quasar/galaxy
  probabilities), ``gaiadr3.astrophysical_parameters`` (GSP-Phot Teff, ESP-UCD Teff +/- its uncertainty, FLAME
  radius/luminosity/mass), ``external.gaiaedr3_distance`` (Bailer-Jones et al. 2021) and
  ``gaiadr3.vari_long_period_variable``. Candidates are matched AFTER propagating each one from its 2016.0 position
  to the requested epoch: high proper-motion stars are up to ~100" away from their 2016 position at SPHEREx epochs.
  On a click, a source >= 2.5 mag brighter than the nearest one inside the radius is adopted (it dominates the
  SPHEREx pixel). Fallback: VizieR CfA ``I/355/gaiadr3`` (astrometry, GSP-Phot only).
- **AAVSO VSX** (VizieR CfA ``B/vsx/vsx``): variability type, range and period.
- **NASA Exoplanet Archive** ``pscomppars`` (confirmed planets only; one composite row per planet), matched by Gaia
  DR3 id, then host name, then position. A planet of a neighbour (eps Ind A b next to eps Ind B) is never attached.
- **2MASS** (``II/246/out``) and **AllWISE** (``II/328/allwise``) magnitudes via VizieR CfA: context photometry of
  OTHER missions, never shown as SPHEREx.

Honesty rules of :func:`derive_parameters`: an ambiguous or distant match leaves every identity-dependent value
(Gaia, SIMBAD reached through the Gaia id, VSX matched by position, 2MASS/AllWISE) unverified; objects SIMBAD types
as extragalactic get no stellar parameters; a Bailer-Jones distance with parallax S/N < 1 is not shown (it would be
the Galactic prior) and is unverified below S/N 5; a service that did not answer is reported as unreachable, never
as 'not catalogued'.

Responses are cached as raw text under ``CACHE_DIR/context`` (TTL ``ERRANTE_CONTEXT_CACHE_TTL_S``); an expired
entry is still served, flagged ``stale``, when the service fails. ``offline=True`` only replays the cache (tests).
"""

from __future__ import annotations

import csv
import hashlib
import html
import io
import json
import math
import os
import re
import threading
import time
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import quote, urlencode, urlsplit

from .. import settings
from ..models import (
    ContextMagnitude,
    ContextService,
    Fact,
    NearbyPlanetHost,
    ObjectContextResponse,
    ObjectIdentity,
    ObjectPlanet,
    ObjectPosition,
    ObjectQuery,
    ObjectVariability,
)

# --- services (verified live 2026-11-15) -------------------------------------------------------------------
SESAME_URL = "https://vizier.cfa.harvard.edu/viz-bin/nph-sesame/-oxpI/"
VIZIER_TSV = "https://vizier.cfa.harvard.edu/viz-bin/asu-tsv"
GAIA_TAP_SYNC = "https://gea.esac.esa.int/tap-server/tap/sync"
EXOPLANET_TAP_SYNC = "https://exoplanetarchive.ipac.caltech.edu/TAP/sync"

CONTEXT_CACHE_TTL_S = float(os.environ.get("ERRANTE_CONTEXT_CACHE_TTL_S", str(7 * 86400)))
CONTEXT_TIMEOUT_S = float(os.environ.get("ERRANTE_CONTEXT_TIMEOUT_S", "25"))
# A host that did not accept a connection within the timeout is skipped for this long (per process): on 2026-11-15
# the ESA Gaia TAP stopped accepting connections and every lookup paid a full connect timeout before the VizieR
# fallback. Skipped calls are reported as errors (unknown, not negative), so the stale cache / fallbacks still apply.
CONTEXT_HOST_BACKOFF_S = float(os.environ.get("ERRANTE_CONTEXT_HOST_BACKOFF_S", "120"))
# Only hosts with a fallback are skipped. The CfA host serves Sesame (the only name resolver), the VizieR Gaia
# fallback, VSX, 2MASS and AllWISE: skipping it after one dropped connection made every name lookup fail for 120 s
# (review 2026-11-15). Hosts without a fallback pay their own transport timeout, bounded by the API deadline.
BACKOFF_HOSTS = frozenset({urlsplit(GAIA_TAP_SYNC).netloc})
_DOWN_HOSTS: dict[str, tuple[float, str]] = {}
_DOWN_LOCK = threading.Lock()


def _host_down(host: str) -> str | None:
    with _DOWN_LOCK:
        entry = _DOWN_HOSTS.get(host)
        if entry is None:
            return None
        age = time.monotonic() - entry[0]
        if age >= CONTEXT_HOST_BACKOFF_S:
            _DOWN_HOSTS.pop(host, None)
            return None
    return f"skipped: {host} did not accept a connection {age:.0f} s ago ({entry[1]}); retried after {CONTEXT_HOST_BACKOFF_S:.0f} s"


def _mark_down(host: str, why: str) -> None:
    with _DOWN_LOCK:
        _DOWN_HOSTS[host] = (time.monotonic(), why)


def _mark_up(host: str) -> None:
    with _DOWN_LOCK:
        _DOWN_HOSTS.pop(host, None)


# --- epochs and matching -------------------------------------------------------------------------------------
J2000_MJD = 51544.5
GAIA_DR3_EPOCH_MJD = 57388.5  # J2016.0, ref_epoch of every Gaia DR3 source
# AllWISE positions refer to each source's mean epoch (2010-2011, not published per row in II/328): we propagate to
# this nominal epoch and widen the match radius by half a year of proper motion.
ALLWISE_NOMINAL_EPOCH_MJD = 55400.0  # 2010.56
ALLWISE_EPOCH_SLACK_YR = 0.5
# Same value as imaging.photometry.SPHEREX_ERA_MJD (2025-11, middle of DR1 + QR3); a test keeps them equal.
DEFAULT_EPOCH_MJD = 61000.0
# One click on the map: ~1.3 SPHEREx pixels (6.15"), about one PSF FWHM (~7.5").
DEFAULT_RADIUS_ARCSEC = 8.0
# Barnard's Star, the largest proper motion in Gaia DR3, has 10393 mas/yr (ESA archive, 2026-11-15).
MAX_PM_MASYR = 10500.0
# Sources faster than this are searched in the wide cone; slower ones can only be inside radius + HIGH_PM * |dt|.
HIGH_PM_MASYR = 100.0
GAIA_MAX_ROWS = 2000
# A name lookup only accepts a Gaia source whose proper motion agrees with SIMBAD's (WISE 0855 is not in Gaia, but
# a G = 16.3 field star passes within a few arcsec of it at SPHEREx epochs).
PM_AGREEMENT_MASYR = 25.0
PM_AGREEMENT_FRACTION = 0.1
SESAME_GAIA_WARN_ARCSEC = 1.0
VSX_MATCH_ARCSEC = 5.0
TWOMASS_MATCH_ARCSEC = 3.0
ALLWISE_MATCH_ARCSEC = 3.0
PLANET_POSITION_MATCH_ARCSEC = 5.0
PLANET_NEIGHBOUR_ARCSEC = 600.0
RUWE_WARN = 1.4
GSPSPEC_DISAGREE_K = 500.0
# A neighbour inside the radius makes a positional match ambiguous unless it is this much fainter in G (x10 flux).
# On a click, a source this much BRIGHTER than the nearest one dominates the SPHEREx pixel and is adopted instead.
AMBIGUITY_DMAG = 2.5
# Parallax S/N: from PLX_SNR_MEASURED a distance counts as measured (verified); below PLX_SNR_MIN a Bailer-Jones
# distance is essentially its Galactic prior and is not shown.
PLX_SNR_MEASURED = 5.0
PLX_SNR_MIN = 1.0
# Gaia DR3 DSC-Combmod probability from which a source is flagged as a likely quasar or galaxy (caveat, not hidden).
DSC_EXTRAGALACTIC_PROB = 0.5
# SIMBAD object types under G (galaxies, AGN, QSO), ClG, GrG, PaG, IG, PCG, SCG and lensed galaxies/quasars, read
# from SIMBAD's otypedef table (TAP, CfA mirror, 2026-11-15). Sesame returns these codes (3C 273 'BLL', M87 'AGN').
EXTRAGALACTIC_OTYPES = frozenset(
    "G GiC BiC GiG GiP H2G EmG SBG bCG LSB AGN QSO Bla BLL LIN rG SyG Sy1 Sy2 ClG GrG CGG PaG IG PCG SCG LeG LeQ".split()
)
EXTRAGALACTIC_CANDIDATE_OTYPES = frozenset("G? AG? Q? Bz? BL? C?G Gr? PCG? SC?".split())

# Nominal band centres [um] (2MASS isophotal; WISE band names). Context only.
TWOMASS_BANDS = (("J", "Jmag", "e_Jmag", 1.235), ("H", "Hmag", "e_Hmag", 1.662), ("Ks", "Kmag", "e_Kmag", 2.159))
WISE_BANDS = (
    ("W1", "W1mag", "e_W1mag", 3.4),
    ("W2", "W2mag", "e_W2mag", 4.6),
    ("W3", "W3mag", "e_W3mag", 12.0),
    ("W4", "W4mag", "e_W4mag", 22.0),
)
# A few SIMBAD object types (the raw code is always kept).
OTYPE_LABELS = {
    "*": "star",
    "BY*": "BY Dra variable",
    "BD*": "brown dwarf",
    "TT*": "T Tauri star",
    "Mi*": "Mira variable",
    "PM*": "high proper-motion star",
    "V*": "variable star",
    "LP*": "long-period variable",
    "**": "double or multiple star",
    "LM*": "low-mass star",
}


class ContextError(RuntimeError):
    """No position to work with: the name was not found, or Sesame could not be reached for a name lookup.

    ``not_found`` is True only when Sesame answered that it does not know the name (an API maps it to 404); False
    when Sesame could not be reached or its answer was unreadable.
    """

    def __init__(self, message: str, *, not_found: bool = False):
        super().__init__(message)
        self.not_found = not_found


# Error note of a response that an offline replay does not have (see to_response(replay_deadline_s=...)).
OFFLINE_MISS = "offline: response not recorded"
CONTEXT_NOTE = (
    "Catalog context from other missions/surveys (SIMBAD, Gaia DR3, AAVSO VSX, NASA Exoplanet Archive, "
    "2MASS, AllWISE): not SPHEREx measurements. 'unknown' = not measured or not found."
)


# --- HTTP with a raw-text disk cache ------------------------------------------------------------------------


@dataclass
class Provenance:
    service: str
    catalog: str
    url: str
    retrieved_utc: str | None = None
    status: str = "ok"  # ok | no_match | error | skipped
    cached: bool = False
    stale: bool = False
    note: str | None = None


@dataclass
class _Reply:
    service: str
    url: str
    ok: bool
    text: str = ""
    retrieved_utc: str | None = None
    cached: bool = False
    stale: bool = False
    error: str | None = None


def _now_utc() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _full_url(url: str, params: dict | None) -> str:
    return f"{url}?{urlencode(params)}" if params else url


class _Http:
    def __init__(self, cache_dir: Path, *, use_cache: bool, offline: bool, ttl_s: float, timeout_s: float):
        self.cache_dir = cache_dir
        self.use_cache = use_cache or offline
        self.offline = offline
        self.ttl_s = ttl_s
        self.timeout_s = timeout_s

    def _path(self, service: str, url: str, params: dict | None) -> Path:
        key = json.dumps([url, sorted((params or {}).items())], ensure_ascii=True)
        return self.cache_dir / f"{service}-{hashlib.sha256(key.encode()).hexdigest()[:16]}.json"

    def get(self, service: str, url: str, params: dict | None = None, require: str | None = None) -> _Reply:
        """GET with the disk cache. ``require``: a substring a valid answer must contain (else: error, not cached)."""
        full = _full_url(url, params)
        path = self._path(service, url, params)
        entry = None
        if self.use_cache and path.is_file():
            try:
                entry = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                entry = None
        if entry is not None:
            age = _age_s(entry.get("retrieved_utc"))
            if self.offline or (age is not None and age <= self.ttl_s):
                return _Reply(service, full, True, entry["text"], entry.get("retrieved_utc"), cached=True)
        if self.offline:
            return _Reply(service, full, False, error=OFFLINE_MISS)
        for attempt in range(2):
            text, error, retry = self._fetch(url, params, require)
            if error is None or not retry or attempt:
                break
        if error is None:
            stamp = _now_utc()
            if self.use_cache:
                try:
                    path.parent.mkdir(parents=True, exist_ok=True)
                    doc = {"service": service, "url": url, "params": params, "retrieved_utc": stamp, "text": text}
                    path.write_text(json.dumps(doc, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
                except OSError:
                    pass
            return _Reply(service, full, True, text, stamp)
        if entry is not None:  # expired but better than nothing; flagged stale
            return _Reply(service, full, True, entry["text"], entry.get("retrieved_utc"), True, True, error)
        return _Reply(service, full, False, error=error)

    def _fetch(self, url: str, params: dict | None, require: str | None) -> tuple[str, str | None, bool]:
        """(text, error or None, worth retrying once)."""
        host = urlsplit(url).netloc
        backoff = host in BACKOFF_HOSTS
        down = _host_down(host) if backoff else None
        if down is not None:
            return "", down, False
        try:
            import requests

            r = requests.get(url, params=params, timeout=self.timeout_s, headers={"User-Agent": "errante/0.1"})
        except Exception as e:  # noqa: BLE001 - any transport failure is a service error, reported in provenance
            if backoff and type(e).__name__ == "ConnectTimeout":
                _mark_down(host, type(e).__name__)
            return "", f"{type(e).__name__}: {e}", "timeout" not in type(e).__name__.lower()
        _mark_up(host)
        text = r.text
        if r.status_code >= 400:
            return text, f"HTTP {r.status_code}: {_short(text)}", r.status_code >= 500
        if 'QUERY_STATUS" value="ERROR"' in text:
            return text, f"query error: {_short(text)}", False
        if require is not None and require not in text:
            # VizieR CfA sometimes answers 200 with an empty RESOURCE (no '#Table') for a cone that has rows
            # (seen twice on 2026-11-15); a genuinely empty result still carries the '#Table' header.
            return text, f"answer without {require!r} (transient empty answer)", True
        return text, None, False


def _age_s(stamp: str | None) -> float | None:
    if not stamp:
        return None
    try:
        when = datetime.strptime(stamp, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
    except ValueError:
        return None
    return (datetime.now(UTC) - when).total_seconds()


def _short(text: str, n: int = 200) -> str:
    text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", text or "")).strip()
    return text[:n]


def _prov(reply: _Reply, catalog: str, status: str | None = None, note: str | None = None) -> Provenance:
    if not reply.ok:
        status, note = "error", reply.error
    elif reply.stale:
        note = f"stale cache served: {reply.error}" + (f"; {note}" if note else "")
    return Provenance(
        reply.service, catalog, reply.url, reply.retrieved_utc, status or "ok", reply.cached, reply.stale, note
    )


# --- astrometry ----------------------------------------------------------------------------------------------


def propagate(ra: float, dec: float, pm_ra: float | None, pm_dec: float | None, dt_yr: float) -> tuple[float, float]:
    """Linear space motion on the sphere: pm_ra includes cos(dec) [mas/yr]; no parallax, no perspective term.

    Ignoring the perspective acceleration costs 0.16" for Barnard's Star from J2000 to 2016 (validation record).
    """
    if pm_ra is None or pm_dec is None or dt_yr == 0:
        return ra % 360.0, dec
    a, d = math.radians(ra), math.radians(dec)
    p = (math.cos(d) * math.cos(a), math.cos(d) * math.sin(a), math.sin(d))
    e_ra = (-math.sin(a), math.cos(a), 0.0)
    e_dec = (-math.sin(d) * math.cos(a), -math.sin(d) * math.sin(a), math.cos(d))
    k = math.radians(1.0 / 3.6e6) * dt_yr
    v = [p[i] + k * (pm_ra * e_ra[i] + pm_dec * e_dec[i]) for i in range(3)]
    norm = math.sqrt(sum(c * c for c in v))
    x, y, z = (c / norm for c in v)
    return math.degrees(math.atan2(y, x)) % 360.0, math.degrees(math.asin(max(-1.0, min(1.0, z))))


def separation_arcsec(ra1: float, dec1: float, ra2: float, dec2: float) -> float:
    a1, d1, a2, d2 = map(math.radians, (ra1, dec1, ra2, dec2))
    h = math.sin((d2 - d1) / 2) ** 2 + math.cos(d1) * math.cos(d2) * math.sin((a2 - a1) / 2) ** 2
    return math.degrees(2 * math.asin(min(1.0, math.sqrt(h)))) * 3600.0


def _years(mjd_to: float, mjd_from: float) -> float:
    return (mjd_to - mjd_from) / 365.25


@dataclass
class Track:
    """Where the object is at any epoch: reference position + proper motion (None = assumed static)."""

    ra: float
    dec: float
    epoch_mjd: float
    pm_ra: float | None = None
    pm_dec: float | None = None
    source: str = ""

    @property
    def pm_total(self) -> float:
        return math.hypot(self.pm_ra, self.pm_dec) if self.pm_ra is not None and self.pm_dec is not None else 0.0

    def at(self, mjd: float) -> tuple[float, float]:
        return propagate(self.ra, self.dec, self.pm_ra, self.pm_dec, _years(mjd, self.epoch_mjd))

    def min_sep(self, ra: float, dec: float, mjd_from: float, mjd_to: float, steps: int = 17) -> float:
        """Smallest separation between (ra, dec) and the track between two epochs (positions of unknown epoch)."""
        if self.pm_total == 0.0:
            return separation_arcsec(*self.at(mjd_from), ra, dec)
        return min(
            separation_arcsec(*self.at(mjd_from + (mjd_to - mjd_from) * i / (steps - 1)), ra, dec) for i in range(steps)
        )


# --- result types --------------------------------------------------------------------------------------------


@dataclass
class SesameInfo:
    query: str
    resolver: str
    main_id: str | None
    object_type: str | None
    spectral_type: str | None
    ra_j2000: float
    dec_j2000: float
    ref_pos: str | None = None
    pm_ra: float | None = None
    pm_dec: float | None = None
    pm_ref: str | None = None
    plx_mas: float | None = None
    plx_err_mas: float | None = None
    plx_ref: str | None = None
    rv_kms: float | None = None
    rv_ref: str | None = None
    aliases: list[str] = field(default_factory=list)

    @property
    def is_simbad(self) -> bool:
        return "simbad" in self.resolver.lower()

    @property
    def gaia_dr3_id(self) -> int | None:
        for alias in self.aliases:
            m = re.fullmatch(r"Gaia DR3 (\d+)", alias.strip())
            if m:
                return int(m.group(1))
        return None


@dataclass
class GaiaSource:
    source_id: int
    ra: float  # ICRS at ref_epoch (2016.0)
    dec: float
    ref_epoch: float = 2016.0
    pmra: float | None = None
    pmra_error: float | None = None
    pmdec: float | None = None
    pmdec_error: float | None = None
    parallax: float | None = None
    parallax_error: float | None = None
    phot_g_mean_mag: float | None = None
    phot_bp_mean_mag: float | None = None
    phot_rp_mean_mag: float | None = None
    ruwe: float | None = None
    radial_velocity: float | None = None
    radial_velocity_error: float | None = None
    phot_variable_flag: str | None = None
    # propagated to the requested epoch
    ra_epoch: float | None = None
    dec_epoch: float | None = None
    sep_arcsec: float | None = None
    # astrophysical parameters (gaiadr3.astrophysical_parameters); lower/upper = 16th/84th percentiles
    teff_gspphot: float | None = None
    teff_gspphot_lower: float | None = None
    teff_gspphot_upper: float | None = None
    teff_gspspec: float | None = None
    teff_espucd: float | None = None
    teff_espucd_uncertainty: float | None = None
    radius_flame: float | None = None
    radius_flame_lower: float | None = None
    radius_flame_upper: float | None = None
    lum_flame: float | None = None
    lum_flame_lower: float | None = None
    lum_flame_upper: float | None = None
    mass_flame: float | None = None
    mass_flame_lower: float | None = None
    mass_flame_upper: float | None = None
    flags_flame: str | None = None
    distance_gspphot: float | None = None
    distance_gspphot_lower: float | None = None
    distance_gspphot_upper: float | None = None
    # Bailer-Jones et al. (2021), external.gaiaedr3_distance; lo/hi = 16th/84th percentiles
    r_med_geo: float | None = None
    r_lo_geo: float | None = None
    r_hi_geo: float | None = None
    r_med_photogeo: float | None = None
    r_lo_photogeo: float | None = None
    r_hi_photogeo: float | None = None
    # gaiadr3.vari_long_period_variable
    lpv_frequency: float | None = None  # 1/d
    lpv_frequency_error: float | None = None
    lpv_amplitude: float | None = None  # G mag
    # gaiadr3.gaia_source DSC-Combmod class probabilities (3C 273: quasar 0.85; M87 core: galaxy 0.999)
    classprob_dsc_combmod_quasar: float | None = None
    classprob_dsc_combmod_galaxy: float | None = None
    details_from: str | None = None  # where the astrophysical parameters came from (None = not retrieved)

    @property
    def pm_total(self) -> float | None:
        return math.hypot(self.pmra, self.pmdec) if self.pmra is not None and self.pmdec is not None else None


@dataclass
class GaiaMatch:
    catalog: str
    # simbad_crossid | nearest_after_propagation | brightest_within_radius (click: dominates the pixel) | None
    method: str | None
    source: GaiaSource | None
    radius_arcsec: float
    n_within_radius: int = 0
    ambiguous: bool = False  # another source of similar brightness inside the radius
    loose: bool = False  # positional (click) match farther than half the radius: may be another object
    candidates: list[dict] = field(default_factory=list)  # nearest few after propagation
    rejected: list[dict] = field(default_factory=list)  # within radius but proper motion disagrees with SIMBAD


@dataclass
class VariableStar:
    name: str
    oid: int | None
    var_type: str | None
    mag_max: float | None
    mag_min: float | None
    min_is_amplitude: bool
    passband: str | None
    period_d: float | None
    epoch_hjd: float | None
    spectral_type: str | None
    sep_arcsec: float
    url: str | None = None


@dataclass
class Planet:
    name: str
    letter: str | None
    hostname: str
    match: str  # gaia_dr3_id | hostname | position
    period_d: float | None = None
    semi_major_axis_au: float | None = None
    radius_earth: float | None = None
    radius_calculated: bool = False  # True = estimated by the archive (mass-radius relation), not measured
    mass_earth: float | None = None
    mass_kind: str | None = None  # pl_bmassprov: Mass | Msini (minimum mass) | M-R relationship ...
    eccentricity: float | None = None
    inclination_deg: float | None = None
    discovery_year: int | None = None
    discovery_method: str | None = None
    discovery_facility: str | None = None
    reference: str | None = None
    controversial: bool = False


@dataclass
class CatalogMagnitude:
    mission: str  # 2MASS | WISE: never SPHEREx
    catalog: str
    designation: str
    band: str
    wavelength_um: float  # nominal band centre
    mag: float | None
    mag_err: float | None
    system: str = "Vega"
    quality: str | None = None  # 2MASS Qflg / AllWISE qph character for this band
    contamination: str | None = None  # AllWISE ccf character (0 = clean)
    upper_limit: bool = False  # True: the source is fainter than `mag`
    epoch_mjd: float | None = None
    sep_arcsec: float | None = None
    # matched along an ambiguous or distant Gaia identification: may belong to a neighbouring source
    identity_uncertain: bool = False


@dataclass
class PhysicalParameter:
    key: str
    label: str
    value: float | str | None  # None = unknown
    unit: str | None = None
    lower: float | None = None
    upper: float | None = None
    method: str | None = None
    source: str | None = None
    caveats: list[str] = field(default_factory=list)
    verified: bool = False

    def to_fact(self) -> Fact:
        if self.value is None:
            text = "unknown"
        elif isinstance(self.value, str):
            text = self.value
        else:
            text = _fmt(self.value, self.key)
            if self.lower is not None and self.upper is not None:
                for extra in range(4):  # add digits until the interval is visible (1.828 (1.8280-1.8282))
                    lo, hi = _fmt(self.lower, self.key, extra), _fmt(self.upper, self.key, extra)
                    if lo != hi:
                        break
                text += f" ({lo}-{hi})"
        parts = [p for p in (self.source, self.method) if p]
        if self.caveats:
            parts.append("Caveat: " + " ".join(self.caveats))
        return Fact(
            label=self.label,
            value=text,
            unit=self.unit if self.value is not None else None,
            source=" | ".join(parts) or None,
            verified=bool(self.verified and self.value is not None),
        )


@dataclass
class ObjectContext:
    query: dict
    epoch_mjd: float
    ra: float | None  # adopted position at epoch_mjd
    dec: float | None
    position_source: str
    display_name: str | None = None
    main_id: str | None = None
    object_type: str | None = None
    object_type_label: str | None = None
    spectral_type: str | None = None
    sesame: SesameInfo | None = None
    sesame_gaia_sep_arcsec: float | None = None
    gaia: GaiaMatch | None = None
    # the Gaia match is ambiguous or distant: identity-dependent values are not verified (see warnings)
    identity_uncertain: bool = False
    variability: VariableStar | None = None
    planets: list[Planet] = field(default_factory=list)
    nearby_planet_hosts: list[dict] = field(default_factory=list)
    photometry: list[CatalogMagnitude] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    provenance: list[Provenance] = field(default_factory=list)

    def parameters(self) -> list[PhysicalParameter]:
        return derive_parameters(self)

    def to_dict(self) -> dict:
        """Strict JSON (NaN/inf -> None): the context, the numeric parameters and the contract Facts."""
        doc = asdict(self)
        doc["parameters"] = [asdict(p) for p in self.parameters()]
        doc["facts"] = [f.model_dump() for f in physical_parameters(self)]
        doc["note"] = CONTEXT_NOTE
        return _finite(doc)


def _finite(value):
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, dict):
        return {k: _finite(v) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [_finite(v) for v in value]
    return value


# --- parsing helpers ---------------------------------------------------------------------------------------


def _num(text) -> float | None:
    if text is None:
        return None
    text = str(text).strip()
    if not text or text.lower() in {"nan", "null", "none"}:
        return None
    try:
        v = float(text)
    except ValueError:
        return None
    return v if math.isfinite(v) else None


def _int(text) -> int | None:
    v = _num(text)
    return int(v) if v is not None else None


def _str(text) -> str | None:
    if text is None:
        return None
    text = str(text).strip()
    return text or None


def _read_csv(text: str) -> list[dict]:
    return [dict(row) for row in csv.DictReader(io.StringIO(text))]


def _read_vizier_tsv(text: str) -> list[dict]:
    """VizieR asu-tsv: '#' comments, header, units line, dashes line, rows until a blank line."""
    lines = [ln for ln in text.splitlines() if not ln.startswith("#")]
    while lines and not lines[0].strip():
        lines.pop(0)
    if len(lines) < 3:
        return []
    header = lines[0].split("\t")
    rows = []
    for ln in lines[3:]:
        if not ln.strip():
            break
        cells = ln.split("\t")
        rows.append({h.strip(): (cells[i].strip() if i < len(cells) else "") for i, h in enumerate(header)})
    return rows


def parse_sesame(text: str, query: str) -> SesameInfo | None:
    """First resolver of a Sesame -oxp(I) answer with a position; None when the name is not found."""
    body = text[: text.rfind("</Sesame>") + len("</Sesame>")] if "</Sesame>" in text else text
    try:
        root = ET.fromstring(body)
    except ET.ParseError as e:
        raise ValueError(f"unreadable Sesame answer: {e}") from e
    for res in root.iter("Resolver"):
        ra, dec = _num(res.findtext("jradeg")), _num(res.findtext("jdedeg"))
        if ra is None or dec is None:
            continue
        pm = res.find("pm")
        plx = res.find("plx")
        vel = res.find("Vel")
        return SesameInfo(
            query=query,
            resolver=res.get("name", ""),
            main_id=_str(res.findtext("oname")),
            object_type=_str(res.findtext("otype")),
            spectral_type=_str(res.findtext("spType")),
            ra_j2000=ra,
            dec_j2000=dec,
            ref_pos=_str(res.findtext("refPos")),
            pm_ra=_num(pm.findtext("pmRA")) if pm is not None else None,
            pm_dec=_num(pm.findtext("pmDE")) if pm is not None else None,
            pm_ref=_str(pm.findtext("r")) if pm is not None else None,
            plx_mas=_num(plx.findtext("v")) if plx is not None else None,
            plx_err_mas=_num(plx.findtext("e")) if plx is not None else None,
            plx_ref=_str(plx.findtext("r")) if plx is not None else None,
            rv_kms=_num(vel.findtext("v")) if vel is not None else None,
            rv_ref=_str(vel.findtext("r")) if vel is not None else None,
            aliases=[a.text.strip() for a in res.findall("alias") if a.text and a.text.strip()],
        )
    return None


def display_name(main_id: str | None) -> str | None:
    """SIMBAD main id without its catalogue prefix: 'NAME Barnard's star' -> "Barnard's star", 'V* R Dra' -> 'R Dra'."""
    if not main_id:
        return None
    name = re.sub(r"^(NAME|\*\*|\*|V\*)\s+", "", main_id.strip())
    return re.sub(r"^\{Name\}\s*", "", name)


def _norm_name(name: str | None) -> str:
    return re.sub(r"[^a-z0-9]", "", display_name(name or "").lower()) if name else ""


# --- Sesame ----------------------------------------------------------------------------------------------------

SESAME_CATALOG = "SIMBAD via Sesame (CfA mirror, vizier.cfa.harvard.edu)"


def _sesame(http: _Http, name: str, resolvers: str = "SNV") -> tuple[SesameInfo | None, Provenance]:
    reply = http.get("sesame", SESAME_URL + resolvers + "?" + quote(name, safe=""), require="</Sesame>")
    if not reply.ok:
        return None, _prov(reply, SESAME_CATALOG)
    try:
        info = parse_sesame(reply.text, name)
    except ValueError as e:
        return None, Provenance(
            "sesame", SESAME_CATALOG, reply.url, reply.retrieved_utc, "error", reply.cached, note=str(e)
        )
    if info is None:
        return None, _prov(reply, SESAME_CATALOG, "no_match", f"name not found: {name!r}")
    return info, _prov(reply, SESAME_CATALOG if info.is_simbad else f"Sesame resolver '{info.resolver}' (CfA)")


# --- Gaia DR3 --------------------------------------------------------------------------------------------------

GAIA_ESA_CATALOG = "Gaia DR3 gaiadr3.gaia_source (ESA Gaia archive TAP)"
GAIA_ESA_DETAILS = (
    "Gaia DR3 astrophysical_parameters + external.gaiaedr3_distance + vari_long_period_variable (ESA Gaia archive TAP)"
)
GAIA_VIZIER_CATALOG = "Gaia DR3 I/355/gaiadr3 (VizieR CfA; fallback, no FLAME/Bailer-Jones/LPV)"

_GAIA_COLUMNS = (
    "source_id, ra, dec, ref_epoch, pmra, pmra_error, pmdec, pmdec_error, parallax, parallax_error, "
    "phot_g_mean_mag, phot_bp_mean_mag, phot_rp_mean_mag, ruwe, radial_velocity, radial_velocity_error, "
    "phot_variable_flag"
)
_AP_COLUMNS = (
    "teff_gspphot", "teff_gspphot_lower", "teff_gspphot_upper", "teff_gspspec", "teff_espucd",
    "teff_espucd_uncertainty", "radius_flame", "radius_flame_lower", "radius_flame_upper", "lum_flame", "lum_flame_lower", "lum_flame_upper",
    "mass_flame", "mass_flame_lower", "mass_flame_upper", "flags_flame",
    "distance_gspphot", "distance_gspphot_lower", "distance_gspphot_upper",
)  # fmt: skip
_BJ_COLUMNS = ("r_med_geo", "r_lo_geo", "r_hi_geo", "r_med_photogeo", "r_lo_photogeo", "r_hi_photogeo")
_DSC_COLUMNS = ("classprob_dsc_combmod_quasar", "classprob_dsc_combmod_galaxy")


def _cone_radii(radius_arcsec: float, epoch_mjd: float) -> tuple[float, float]:
    """(wide, narrow) cone radii [deg] around the epoch position, in the 2016.0 frame of Gaia positions."""
    dt = abs(_years(epoch_mjd, GAIA_DR3_EPOCH_MJD))
    return (radius_arcsec + MAX_PM_MASYR / 1000.0 * dt + 1.0) / 3600.0, (
        radius_arcsec + HIGH_PM_MASYR / 1000.0 * dt + 1.0
    ) / 3600.0


def _tap(query: str) -> dict:
    return {"REQUEST": "doQuery", "LANG": "ADQL", "FORMAT": "csv", "QUERY": " ".join(query.split())}


def _gaia_row(row: dict) -> GaiaSource:
    g = GaiaSource(source_id=int(row["source_id"]), ra=float(row["ra"]), dec=float(row["dec"]))
    for name in _GAIA_COLUMNS.split(", ")[3:]:
        if name == "phot_variable_flag":
            g.phot_variable_flag = _str(row.get(name))
        else:
            setattr(g, name, _num(row.get(name)))
    return g


def gaia_cone_esa(http: _Http, ra: float, dec: float, radius_arcsec: float, epoch_mjd: float):
    wide, narrow = _cone_radii(radius_arcsec, epoch_mjd)
    q = f"""SELECT TOP {GAIA_MAX_ROWS} {_GAIA_COLUMNS} FROM gaiadr3.gaia_source
        WHERE 1 = CONTAINS(POINT('ICRS', ra, dec), CIRCLE('ICRS', {ra:.7f}, {dec:.7f}, {wide:.7f}))
        AND (pm >= {HIGH_PM_MASYR:.1f} OR DISTANCE(POINT('ICRS', ra, dec), POINT('ICRS', {ra:.7f}, {dec:.7f}))
        <= {narrow:.7f})"""
    reply = http.get("gaia-esa", GAIA_TAP_SYNC, _tap(q), require="source_id")
    if not reply.ok:
        return None, _prov(reply, GAIA_ESA_CATALOG)
    try:
        rows = [_gaia_row(r) for r in _read_csv(reply.text)]
    except (KeyError, ValueError) as e:
        return None, Provenance("gaia-esa", GAIA_ESA_CATALOG, reply.url, reply.retrieved_utc, "error", note=str(e))
    return rows, _prov(reply, GAIA_ESA_CATALOG, "ok" if rows else "no_match")


def gaia_by_id_esa(http: _Http, source_id: int):
    q = f"SELECT {_GAIA_COLUMNS} FROM gaiadr3.gaia_source WHERE source_id = {int(source_id)}"
    reply = http.get("gaia-esa", GAIA_TAP_SYNC, _tap(q), require="source_id")
    if not reply.ok:
        return None, _prov(reply, GAIA_ESA_CATALOG)
    rows = [_gaia_row(r) for r in _read_csv(reply.text)]
    return (rows[0] if rows else None), _prov(reply, GAIA_ESA_CATALOG, "ok" if rows else "no_match")


def gaia_details_esa(http: _Http, source: GaiaSource) -> Provenance:
    """Fill astrophysical parameters, Bailer-Jones distances, DSC class and the LPV period of ONE source (in place)."""
    cols = ", ".join(
        [f"ap.{c}" for c in _AP_COLUMNS] + [f"d.{c}" for c in _BJ_COLUMNS] + [f"g.{c}" for c in _DSC_COLUMNS]
    )
    q = f"""SELECT g.source_id, {cols}, lpv.frequency, lpv.frequency_error, lpv.amplitude
        FROM gaiadr3.gaia_source AS g
        LEFT OUTER JOIN gaiadr3.astrophysical_parameters AS ap ON ap.source_id = g.source_id
        LEFT OUTER JOIN external.gaiaedr3_distance AS d ON d.source_id = g.source_id
        LEFT OUTER JOIN gaiadr3.vari_long_period_variable AS lpv ON lpv.source_id = g.source_id
        WHERE g.source_id = {int(source.source_id)}"""
    reply = http.get("gaia-esa", GAIA_TAP_SYNC, _tap(q), require="source_id")
    if not reply.ok:
        return _prov(reply, GAIA_ESA_DETAILS)
    rows = _read_csv(reply.text)
    if not rows:
        return _prov(reply, GAIA_ESA_DETAILS, "no_match")
    row = rows[0]
    for c in _AP_COLUMNS + _BJ_COLUMNS + _DSC_COLUMNS:
        setattr(source, c, _str(row.get(c)) if c == "flags_flame" else _num(row.get(c)))
    source.lpv_frequency = _num(row.get("frequency"))
    source.lpv_frequency_error = _num(row.get("frequency_error"))
    source.lpv_amplitude = _num(row.get("amplitude"))
    source.details_from = GAIA_ESA_DETAILS
    return _prov(reply, GAIA_ESA_DETAILS)


_VIZIER_GAIA_OUT = (
    "Source,RA_ICRS,DE_ICRS,Plx,e_Plx,pmRA,e_pmRA,pmDE,e_pmDE,PM,RUWE,Gmag,BPmag,RPmag,RV,e_RV,VarFlag,"
    "Teff,b_Teff,B_Teff,Dist,b_Dist,B_Dist"
)


def _vizier_gaia_row(row: dict) -> GaiaSource:
    return GaiaSource(
        source_id=int(row["Source"]),
        ra=float(row["RA_ICRS"]),
        dec=float(row["DE_ICRS"]),
        pmra=_num(row.get("pmRA")),
        pmra_error=_num(row.get("e_pmRA")),
        pmdec=_num(row.get("pmDE")),
        pmdec_error=_num(row.get("e_pmDE")),
        parallax=_num(row.get("Plx")),
        parallax_error=_num(row.get("e_Plx")),
        phot_g_mean_mag=_num(row.get("Gmag")),
        phot_bp_mean_mag=_num(row.get("BPmag")),
        phot_rp_mean_mag=_num(row.get("RPmag")),
        ruwe=_num(row.get("RUWE")),
        radial_velocity=_num(row.get("RV")),
        radial_velocity_error=_num(row.get("e_RV")),
        phot_variable_flag=_str(row.get("VarFlag")),
        # I/355/gaiadr3 Teff/Dist are GSP-Phot (checked against the ESA archive for Barnard's Star, 2026-11-15)
        teff_gspphot=_num(row.get("Teff")),
        teff_gspphot_lower=_num(row.get("b_Teff")),
        teff_gspphot_upper=_num(row.get("B_Teff")),
        distance_gspphot=_num(row.get("Dist")),
        distance_gspphot_lower=_num(row.get("b_Dist")),
        distance_gspphot_upper=_num(row.get("B_Dist")),
        details_from=GAIA_VIZIER_CATALOG,
    )


def gaia_cone_vizier(http: _Http, ra: float, dec: float, radius_arcsec: float, epoch_mjd: float):
    """Same candidates as gaia_cone_esa from VizieR CfA: narrow cone (all) + wide cone with PM >= HIGH_PM."""
    wide, narrow = _cone_radii(radius_arcsec, epoch_mjd)
    rows: dict[int, GaiaSource] = {}
    provs = []
    for rs, extra in ((narrow, {}), (wide, {"PM": f">={HIGH_PM_MASYR:.0f}"})):
        params = {
            "-source": "I/355/gaiadr3",
            "-c": f"{ra:.7f} {dec:+.7f}",
            "-c.rs": f"{rs * 3600.0:.3f}",
            "-out": _VIZIER_GAIA_OUT,
            "-out.max": str(GAIA_MAX_ROWS),
            **extra,
        }
        reply = http.get("gaia-vizier", VIZIER_TSV, params, require="#Table")
        provs.append(_prov(reply, GAIA_VIZIER_CATALOG))
        if not reply.ok:
            return None, provs
        for r in _read_vizier_tsv(reply.text):
            if r.get("Source"):
                g = _vizier_gaia_row(r)
                rows[g.source_id] = g
    return list(rows.values()), provs


def _match_gaia(
    sources: list[GaiaSource],
    ra: float,
    dec: float,
    radius_arcsec: float,
    epoch_mjd: float,
    expected_pm: tuple[float, float] | None,
) -> tuple[list[GaiaSource], list[GaiaSource], list[GaiaSource]]:
    """Propagate every candidate to the epoch; return (all sorted by separation, accepted in radius, rejected)."""
    dt = _years(epoch_mjd, GAIA_DR3_EPOCH_MJD)
    for g in sources:
        g.ra_epoch, g.dec_epoch = propagate(g.ra, g.dec, g.pmra, g.pmdec, dt)
        g.sep_arcsec = separation_arcsec(ra, dec, g.ra_epoch, g.dec_epoch)
    ordered = sorted(sources, key=lambda g: g.sep_arcsec)
    inside = [g for g in ordered if g.sep_arcsec <= radius_arcsec]
    if expected_pm is None:
        return ordered, inside, []
    ok, bad = [], []
    for g in inside:
        (ok if _pm_agrees(g, expected_pm) else bad).append(g)
    return ordered, ok, bad


def _pm_agrees(g: GaiaSource, expected: tuple[float, float]) -> bool:
    if g.pmra is None or g.pmdec is None:
        return math.hypot(*expected) < PM_AGREEMENT_MASYR  # a 2-parameter source can only be a slow one
    tol = max(PM_AGREEMENT_MASYR, PM_AGREEMENT_FRACTION * math.hypot(*expected))
    return math.hypot(g.pmra - expected[0], g.pmdec - expected[1]) <= tol


def _gmag(g: GaiaSource) -> float:
    return g.phot_g_mean_mag if g.phot_g_mean_mag is not None else math.inf


def _candidate_summary(g: GaiaSource) -> dict:
    return {
        "source_id": g.source_id,
        "sep_arcsec": g.sep_arcsec,
        "phot_g_mean_mag": g.phot_g_mean_mag,
        "pmra": g.pmra,
        "pmdec": g.pmdec,
        "parallax": g.parallax,
        "ruwe": g.ruwe,
    }


# --- VSX, 2MASS, AllWISE, exoplanets -------------------------------------------------------------------------

VSX_CATALOG = "AAVSO VSX B/vsx/vsx (VizieR CfA)"
TWOMASS_CATALOG = "2MASS All-Sky PSC II/246/out (VizieR CfA)"
ALLWISE_CATALOG = "AllWISE II/328/allwise (VizieR CfA)"
EXOPLANET_CATALOG = "NASA Exoplanet Archive pscomppars (confirmed planets, TAP)"


def _vizier_cone(http: _Http, service: str, source: str, ra: float, dec: float, rs_arcsec: float, out: str):
    params = {
        "-source": source,
        "-c": f"{ra:.7f} {dec:+.7f}",
        "-c.rs": f"{rs_arcsec:.3f}",
        "-out": out,
        "-out.max": "200",
    }
    return http.get(service, VIZIER_TSV, params, require="#Table")


def _vsx(http: _Http, track: Track, radius_arcsec: float) -> tuple[VariableStar | None, Provenance]:
    # VSX positions are J2000 (equinox and, for most entries, epoch): search along the 2000-2016 track.
    match = VSX_MATCH_ARCSEC if track.pm_ra is not None else max(VSX_MATCH_ARCSEC, radius_arcsec)
    span = track.pm_total / 1000.0 * abs(_years(GAIA_DR3_EPOCH_MJD, J2000_MJD))
    ra0, dec0 = track.at(J2000_MJD)
    out = "OID,Name,V,Type,max,n_max,f_min,min,n_min,Period,Epoch,Sp,RAJ2000,DEJ2000"
    reply = _vizier_cone(http, "vsx", "B/vsx/vsx", ra0, dec0, match + span, out)
    if not reply.ok:
        return None, _prov(reply, VSX_CATALOG)
    best = None
    for r in _read_vizier_tsv(reply.text):
        rra, rdec = _num(r.get("RAJ2000")), _num(r.get("DEJ2000"))
        if rra is None or rdec is None:
            continue
        sep = track.min_sep(rra, rdec, J2000_MJD, GAIA_DR3_EPOCH_MJD)
        if sep <= match and (best is None or sep < best[0]):
            best = (sep, r)
    if best is None:
        return None, _prov(reply, VSX_CATALOG, "no_match", f'no VSX entry within {match:.1f}" of the track')
    sep, r = best
    oid = _int(r.get("OID"))
    var = VariableStar(
        name=r.get("Name", "").strip(),
        oid=oid,
        var_type=_str(r.get("Type")),
        mag_max=_num(r.get("max")),
        mag_min=_num(r.get("min")),
        min_is_amplitude=(r.get("f_min", "").strip() == "Y"),
        passband=_str(r.get("n_max")),
        period_d=_num(r.get("Period")),
        epoch_hjd=_num(r.get("Epoch")),
        spectral_type=_str(r.get("Sp")),
        sep_arcsec=sep,
        url=f"https://www.aavso.org/vsx/index.php?view=detail.top&oid={oid}" if oid else None,
    )
    return var, _prov(reply, VSX_CATALOG)


def _twomass(http: _Http, track: Track, radius_arcsec: float) -> tuple[list[CatalogMagnitude], Provenance]:
    # 2MASS observed 1997-2001; each row has its own JD, so we propagate to it exactly.
    match = TWOMASS_MATCH_ARCSEC if track.pm_ra is not None else max(TWOMASS_MATCH_ARCSEC, radius_arcsec)
    ra0, dec0 = track.at(J2000_MJD)
    out = "2MASS,RAJ2000,DEJ2000,Jmag,e_Jmag,Hmag,e_Hmag,Kmag,e_Kmag,Qflg,Rflg,Bflg,Cflg,JD"
    reply = _vizier_cone(http, "2mass", "II/246/out", ra0, dec0, match + track.pm_total / 1000.0 * 3.0, out)
    if not reply.ok:
        return [], _prov(reply, TWOMASS_CATALOG)
    best = None
    for r in _read_vizier_tsv(reply.text):
        rra, rdec, jd = _num(r.get("RAJ2000")), _num(r.get("DEJ2000")), _num(r.get("JD"))
        if rra is None or rdec is None:
            continue
        mjd = jd - 2400000.5 if jd is not None else J2000_MJD
        sep = separation_arcsec(*track.at(mjd), rra, rdec)
        if sep <= match and (best is None or sep < best[0]):
            best = (sep, mjd, r)
    if best is None:
        return [], _prov(reply, TWOMASS_CATALOG, "no_match", f'no 2MASS source within {match:.1f}"')
    sep, mjd, r = best
    qflg = r.get("Qflg", "")
    mags = []
    for i, (band, col, ecol, lam) in enumerate(TWOMASS_BANDS):
        q = qflg[i] if i < len(qflg) else None
        mags.append(
            CatalogMagnitude(
                mission="2MASS",
                catalog=TWOMASS_CATALOG,
                designation=f"2MASS J{r.get('2MASS', '').strip()}",
                band=band,
                wavelength_um=lam,
                mag=_num(r.get(col)),
                mag_err=_num(r.get(ecol)),
                quality=q,
                upper_limit=(q == "U"),
                epoch_mjd=mjd,
                sep_arcsec=sep,
            )
        )
    return mags, _prov(reply, TWOMASS_CATALOG)


def _allwise(http: _Http, track: Track, radius_arcsec: float) -> tuple[list[CatalogMagnitude], Provenance]:
    slack = track.pm_total / 1000.0 * ALLWISE_EPOCH_SLACK_YR
    match = (ALLWISE_MATCH_ARCSEC if track.pm_ra is not None else max(ALLWISE_MATCH_ARCSEC, radius_arcsec)) + slack
    ra0, dec0 = track.at(ALLWISE_NOMINAL_EPOCH_MJD)
    out = "AllWISE,RAJ2000,DEJ2000,W1mag,e_W1mag,W2mag,e_W2mag,W3mag,e_W3mag,W4mag,e_W4mag,ccf,ex,qph"
    reply = _vizier_cone(http, "allwise", "II/328/allwise", ra0, dec0, match, out)
    if not reply.ok:
        return [], _prov(reply, ALLWISE_CATALOG)
    best = None
    for r in _read_vizier_tsv(reply.text):
        rra, rdec = _num(r.get("RAJ2000")), _num(r.get("DEJ2000"))
        if rra is None or rdec is None:
            continue
        sep = separation_arcsec(ra0, dec0, rra, rdec)
        if sep <= match and (best is None or sep < best[0]):
            best = (sep, r)
    if best is None:
        return [], _prov(reply, ALLWISE_CATALOG, "no_match", f'no AllWISE source within {match:.1f}"')
    sep, r = best
    qph, ccf = r.get("qph", ""), r.get("ccf", "")
    mags = []
    for i, (band, col, ecol, lam) in enumerate(WISE_BANDS):
        q = qph[i] if i < len(qph) else None
        mags.append(
            CatalogMagnitude(
                mission="WISE",
                catalog=ALLWISE_CATALOG,
                designation=f"AllWISE {r.get('AllWISE', '').strip()}",
                band=band,
                wavelength_um=lam,
                mag=_num(r.get(col)),
                mag_err=_num(r.get(ecol)),
                quality=q,
                contamination=ccf[i] if i < len(ccf) else None,
                upper_limit=(q == "U"),
                epoch_mjd=ALLWISE_NOMINAL_EPOCH_MJD,
                sep_arcsec=sep,
            )
        )
    return mags, _prov(reply, ALLWISE_CATALOG, note="AllWISE epoch is nominal (2010.56): see match radius")


_PLANET_COLUMNS = (
    "pl_name,pl_letter,hostname,ra,dec,gaia_dr3_id,pl_orbper,pl_orbsmax,pl_rade,pl_rade_reflink,pl_bmasse,"
    "pl_bmassprov,pl_orbeccen,pl_orbincl,disc_year,discoverymethod,disc_facility,disc_refname,pl_controv_flag"
)


def _ra_box(ra: float, half_ra: float) -> str:
    lo, hi = ra - half_ra, ra + half_ra
    if half_ra >= 180.0:
        # every RA (near a pole). Not a literal '1=1': the archive's Cloudflare WAF answers that with HTTP 403
        # (seen on 2026-11-15), while 'ra >= 0' returns 200.
        return "ra >= 0"
    if lo < 0:
        return f"(ra >= {lo + 360.0:.6f} OR ra <= {hi:.6f})"
    if hi >= 360.0:
        return f"(ra >= {lo:.6f} OR ra <= {hi - 360.0:.6f})"
    return f"ra BETWEEN {lo:.6f} AND {hi:.6f}"


def _planets(
    http: _Http, track: Track, gaia_id: int | None, names: list[str], radius_arcsec: float
) -> tuple[list[Planet], list[dict], Provenance]:
    # generic contains(point...) ADQL answered 403 on 2026-11-14: plain ra/dec BETWEEN box instead.
    half = PLANET_NEIGHBOUR_ARCSEC + track.pm_total / 1000.0 * abs(_years(GAIA_DR3_EPOCH_MJD, J2000_MJD))
    ra0, dec0 = track.at((J2000_MJD + GAIA_DR3_EPOCH_MJD) / 2)
    cosd = math.cos(math.radians(min(89.0, abs(dec0))))
    half_ra = (half / 3600.0) / cosd if abs(dec0) + half / 3600.0 < 89.5 else 180.0
    dlo, dhi = max(-90.0, dec0 - half / 3600.0), min(90.0, dec0 + half / 3600.0)
    q = f"select {_PLANET_COLUMNS} from pscomppars where {_ra_box(ra0, half_ra)} and dec between {dlo:.6f} and {dhi:.6f}"
    reply = http.get("exoplanets", EXOPLANET_TAP_SYNC, {"query": q, "format": "csv"}, require="pl_name")
    if not reply.ok:
        return [], [], _prov(reply, EXOPLANET_CATALOG)
    keys = {_norm_name(n) for n in names if n}
    match_pos = (
        PLANET_POSITION_MATCH_ARCSEC if track.pm_ra is not None else max(PLANET_POSITION_MATCH_ARCSEC, radius_arcsec)
    )
    # Neighbour hosts: separation at ONE epoch. pscomppars positions are Gaia-era (eps Ind A: 2.4" from its Gaia
    # DR3 2016.0 position), so the object is taken at 2016.0; the minimum over the 2000-2016 track would mix epochs
    # and shrink a common-proper-motion pair (eps Ind A-B: ~405", not ~344").
    ra16, dec16 = track.at(GAIA_DR3_EPOCH_MJD)
    planets, others = [], {}
    for r in _read_csv(reply.text):
        rra, rdec = _num(r.get("ra")), _num(r.get("dec"))
        if rra is None or rdec is None:
            continue
        sep = track.min_sep(rra, rdec, J2000_MJD, GAIA_DR3_EPOCH_MJD)
        rid = re.fullmatch(r"\s*Gaia DR3 (\d+)\s*", r.get("gaia_dr3_id") or "")
        how = None
        if gaia_id is not None and rid and int(rid.group(1)) == gaia_id:
            how = "gaia_dr3_id"
        elif keys and _norm_name(r.get("hostname")) in keys:
            how = "hostname"
        elif not rid and sep <= match_pos:  # a host with a different Gaia id is another star
            how = "position"
        if how is None:
            sep16 = separation_arcsec(ra16, dec16, rra, rdec)
            if sep16 <= PLANET_NEIGHBOUR_ARCSEC:
                host = r.get("hostname", "")
                entry = others.setdefault(host, {"hostname": host, "sep_arcsec": sep16, "planets": []})
                entry["planets"].append(r.get("pl_name"))
            continue
        planets.append(
            Planet(
                name=r.get("pl_name", ""),
                letter=_str(r.get("pl_letter")),
                hostname=r.get("hostname", ""),
                match=how,
                period_d=_num(r.get("pl_orbper")),
                semi_major_axis_au=_num(r.get("pl_orbsmax")),
                radius_earth=_num(r.get("pl_rade")),
                radius_calculated="CALCULATED_VALUE" in (r.get("pl_rade_reflink") or ""),
                mass_earth=_num(r.get("pl_bmasse")),
                mass_kind=_str(r.get("pl_bmassprov")),
                eccentricity=_num(r.get("pl_orbeccen")),
                inclination_deg=_num(r.get("pl_orbincl")),
                discovery_year=_int(r.get("disc_year")),
                discovery_method=_str(r.get("discoverymethod")),
                discovery_facility=_str(r.get("disc_facility")),
                reference=_str(html.unescape(_short(r.get("disc_refname") or ""))),
                controversial=(r.get("pl_controv_flag", "").strip() == "1"),
            )
        )
    planets.sort(key=lambda p: (p.period_d is None, p.period_d or 0.0, p.name))
    hosts = sorted(others.values(), key=lambda h: h["sep_arcsec"])
    status = "ok" if planets else "no_match"
    return planets, hosts, _prov(reply, EXOPLANET_CATALOG, status)


# --- main entry point ------------------------------------------------------------------------------------------


def object_context(
    ra: float | None = None,
    dec: float | None = None,
    *,
    name: str | None = None,
    epoch_mjd: float | None = None,
    radius_arcsec: float = DEFAULT_RADIUS_ARCSEC,
    use_cache: bool = True,
    cache_dir: Path | str | None = None,
    offline: bool = False,
    timeout_s: float = CONTEXT_TIMEOUT_S,
) -> ObjectContext:
    """Catalog context of a clicked position (ra, dec at ``epoch_mjd``) OR of a name.

    ``epoch_mjd`` is the epoch of the clicked position and of the reported one (default: the SPHEREx-era epoch
    used by the photometry, MJD 61000). Raises ``ContextError`` only when a name cannot be resolved; every other
    service failure is reported in ``provenance`` (status ``error``) and the rest of the context still comes back.
    """
    if (name is None) == (ra is None or dec is None):
        raise ValueError("give either ra and dec, or name")
    if not (radius_arcsec > 0 and math.isfinite(radius_arcsec)):
        raise ValueError("radius_arcsec must be a positive number")
    if ra is not None and not (math.isfinite(ra) and math.isfinite(dec) and -90.0 <= dec <= 90.0):
        raise ValueError("invalid ra/dec")
    epoch = float(epoch_mjd) if epoch_mjd is not None else DEFAULT_EPOCH_MJD
    http = _Http(
        Path(cache_dir) if cache_dir is not None else settings.CACHE_DIR / "context",
        use_cache=use_cache,
        offline=offline,
        ttl_s=CONTEXT_CACHE_TTL_S,
        timeout_s=timeout_s,
    )
    query = {"ra": ra, "dec": dec, "name": name, "epoch_mjd": epoch, "radius_arcsec": radius_arcsec}
    warnings: list[str] = []
    provenance: list[Provenance] = []

    # 1) where to look
    sesame = None
    if name is not None:
        sesame, prov = _sesame(http, name.strip())
        provenance.append(prov)
        if sesame is None:
            raise ContextError(
                f"could not resolve {name!r}: {prov.note or prov.status}", not_found=prov.status == "no_match"
            )
        if not sesame.is_simbad:
            warnings.append(
                f"Sesame resolved {name!r} via '{sesame.resolver}', not SIMBAD, without a proper motion: the position "
                "may be from an old epoch (known case: 'GJ 699' lands 8.6' from Barnard's Star). Prefer a SIMBAD "
                "name or a Gaia DR3 id."
            )
        elif sesame.pm_ra is None:
            warnings.append("SIMBAD gives no proper motion: the object is treated as static.")
        qtrack = Track(sesame.ra_j2000, sesame.dec_j2000, J2000_MJD, sesame.pm_ra, sesame.pm_dec, "Sesame")
        qra, qdec = qtrack.at(epoch)
        expected_pm = (sesame.pm_ra, sesame.pm_dec) if sesame.pm_ra is not None and sesame.pm_dec is not None else None
    else:
        qra, qdec = float(ra) % 360.0, float(dec)
        expected_pm = None

    # 2) Gaia DR3 counterpart, matched after propagation to the epoch
    gaia = _gaia_match(http, qra, qdec, radius_arcsec, epoch, sesame, expected_pm, warnings, provenance)
    src = gaia.source if gaia else None

    # 3) the object's track for the other catalogs
    if src is not None and src.pmra is not None:
        track = Track(src.ra, src.dec, GAIA_DR3_EPOCH_MJD, src.pmra, src.pmdec, "Gaia DR3")
    elif sesame is not None and expected_pm is not None:
        track = qtrack
    else:
        track = Track(qra, qdec, epoch, None, None, "click" if name is None else "Sesame (static)")
        if gaia is not None and src is None and name is None:
            warnings.append(
                "No Gaia DR3 source here: proper motion unknown, the other catalogs are searched as for a static "
                "source (a fast object absent from Gaia, like WISE 0855, is only found by name)."
            )

    # 4) everything else in parallel
    with ThreadPoolExecutor(max_workers=6) as pool:
        f_details = pool.submit(gaia_details_esa, http, src) if src and src.details_from is None else None
        f_simbad = (
            pool.submit(_sesame, http, f"Gaia DR3 {src.source_id}", "S") if src is not None and sesame is None else None
        )
        f_vsx = pool.submit(_vsx, http, track, radius_arcsec)
        f_2mass = pool.submit(_twomass, http, track, radius_arcsec)
        f_wise = pool.submit(_allwise, http, track, radius_arcsec)
        simbad_by_id = None
        if f_simbad is not None:
            simbad_by_id, prov = f_simbad.result()
            provenance.append(prov)
        ses = sesame or simbad_by_id
        names = ([ses.main_id, *ses.aliases] if ses else []) + ([name] if name else [])
        f_planets = pool.submit(_planets, http, track, src.source_id if src else None, names, radius_arcsec)
        if f_details is not None:
            prov = f_details.result()
            provenance.append(prov)
            if prov.status != "ok":
                warnings.append("Gaia DR3 astrophysical parameters / distances could not be retrieved.")
        variability, prov = f_vsx.result()
        provenance.append(prov)
        mags2, prov = f_2mass.result()
        provenance.append(prov)
        magsw, prov = f_wise.result()
        provenance.append(prov)
        planets, hosts, prov = f_planets.result()
        provenance.append(prov)

    sesame_used = sesame or simbad_by_id
    ctx = ObjectContext(
        query=query,
        epoch_mjd=epoch,
        ra=None,
        dec=None,
        position_source="",
        sesame=sesame_used,
        gaia=gaia,
        variability=variability,
        planets=planets,
        nearby_planet_hosts=hosts,
        photometry=mags2 + magsw,
        warnings=warnings,
        provenance=provenance,
    )
    ctx.ra, ctx.dec = track.at(epoch)
    ctx.position_source = {
        "Gaia DR3": "Gaia DR3 propagated to the epoch",
        "Sesame": "SIMBAD (Sesame) J2000 propagated to the epoch",
    }.get(track.source, "query position (static)")
    if sesame_used is not None:
        ctx.main_id = sesame_used.main_id
        ctx.display_name = display_name(sesame_used.main_id)
        ctx.object_type = sesame_used.object_type
        ctx.object_type_label = OTYPE_LABELS.get(sesame_used.object_type or "")
        ctx.spectral_type = sesame_used.spectral_type
    elif src is not None:
        ctx.display_name = f"Gaia DR3 {src.source_id}"
    if sesame_used is not None and src is not None and sesame_used.is_simbad:
        s_ra, s_dec = Track(
            sesame_used.ra_j2000, sesame_used.dec_j2000, J2000_MJD, sesame_used.pm_ra, sesame_used.pm_dec
        ).at(GAIA_DR3_EPOCH_MJD)
        ctx.sesame_gaia_sep_arcsec = separation_arcsec(s_ra, s_dec, src.ra, src.dec)
        if ctx.sesame_gaia_sep_arcsec > SESAME_GAIA_WARN_ARCSEC:
            warnings.append(
                f'SIMBAD position propagated to 2016.0 is {ctx.sesame_gaia_sep_arcsec:.2f}" from Gaia DR3 '
                f"{src.source_id}: check the identification."
            )
    if hosts:
        listed = ", ".join(f'{h["hostname"]} (~{h["sep_arcsec"]:.0f}" at 2016.0)' for h in hosts[:3])
        warnings.append(f"Confirmed planet host(s) nearby but NOT this object: {listed}.")
    ctx.identity_uncertain = bool(gaia is not None and (gaia.ambiguous or gaia.loose))
    for m in ctx.photometry:
        m.identity_uncertain = ctx.identity_uncertain
    exgal, exgal_firm = _extragalactic(ctx, src)
    if exgal is not None:
        warnings.append(f"{exgal}: Gaia's stellar parameters {'are not shown' if exgal_firm else 'may not apply'}.")
    # A service that did not answer is not a catalog negative: say so (Gaia failures are reported above).
    for service, (label, what) in _SERVICE_WHAT.items():
        failed = next((p for p in provenance if p.service == service and p.status == "error"), None)
        if failed is not None:
            warnings.append(f"{label} could not be reached ({failed.note}): {what} unknown, not a negative result.")
    return ctx


_SERVICE_WHAT = {
    "sesame": ("SIMBAD (Sesame CfA)", "SIMBAD identity and spectral type"),
    "vsx": ("AAVSO VSX", "catalogued variability"),
    "exoplanets": ("NASA Exoplanet Archive", "confirmed planets"),
    "2mass": ("2MASS (VizieR CfA)", "2MASS photometry"),
    "allwise": ("AllWISE (VizieR CfA)", "WISE photometry"),
}


def _gaia_match(
    http: _Http,
    ra: float,
    dec: float,
    radius_arcsec: float,
    epoch: float,
    sesame: SesameInfo | None,
    expected_pm: tuple[float, float] | None,
    warnings: list[str],
    provenance: list[Provenance],
) -> GaiaMatch | None:
    sources, prov = gaia_cone_esa(http, ra, dec, radius_arcsec, epoch)
    provenance.append(prov)
    catalog = GAIA_ESA_CATALOG
    if sources is None:
        sources, provs = gaia_cone_vizier(http, ra, dec, radius_arcsec, epoch)
        provenance.extend(provs)
        catalog = GAIA_VIZIER_CATALOG
        if sources is None:
            warnings.append("Gaia DR3 unreachable (ESA archive and VizieR CfA): no Gaia identification.")
            return None
        warnings.append("ESA Gaia archive unreachable: Gaia DR3 from VizieR CfA (no FLAME, Bailer-Jones or LPV).")
    ordered, accepted, rejected = _match_gaia(sources, ra, dec, radius_arcsec, epoch, expected_pm)
    match = GaiaMatch(
        catalog=catalog,
        method=None,
        source=None,
        radius_arcsec=radius_arcsec,
        n_within_radius=len(accepted),
        candidates=[_candidate_summary(g) for g in ordered[:5]],
        rejected=[_candidate_summary(g) for g in rejected],
    )
    crossid = sesame.gaia_dr3_id if sesame is not None else None
    chosen = None
    if sesame is not None and not sesame.is_simbad:
        # e.g. 'GJ 699' -> VizieR (local), an old position 8.6' from Barnard's Star: nearest source would be a stranger
        warnings.append("Name not resolved by SIMBAD: no automatic Gaia DR3 identification (candidates listed).")
        return match
    if crossid is not None:
        chosen = next((g for g in sources if g.source_id == crossid), None)
        if chosen is None and catalog == GAIA_ESA_CATALOG:
            chosen, prov = gaia_by_id_esa(http, crossid)
            provenance.append(prov)
            if chosen is not None:
                _match_gaia([chosen], ra, dec, radius_arcsec, epoch, None)
        if chosen is not None:
            match.method = "simbad_crossid"
            if chosen.sep_arcsec is not None and chosen.sep_arcsec > radius_arcsec:
                warnings.append(
                    f"SIMBAD's Gaia DR3 cross-id {crossid} is {chosen.sep_arcsec:.1f}\" from the SIMBAD position at "
                    "the epoch (outside the match radius)."
                )
        else:
            warnings.append(f"SIMBAD lists Gaia DR3 {crossid}, but it could not be retrieved.")
    if chosen is None and accepted:
        chosen = accepted[0]
        match.method = "nearest_after_propagation"
        dominant = min((g for g in accepted if g.phot_g_mean_mag is not None), key=_gmag, default=None)
        if (
            sesame is None
            and dominant is not None
            and chosen.phot_g_mean_mag is not None
            and dominant.phot_g_mean_mag <= chosen.phot_g_mean_mag - AMBIGUITY_DMAG
        ):
            # A click: both sit in the same SPHEREx pixel (6.15") and the brighter one dominates what was clicked
            # (5.5" from R Dra, G = 6.4, the nearest source is a G = 19.4 star at 1.7").
            warnings.append(
                f"Adopted Gaia DR3 {dominant.source_id} (G = {dominant.phot_g_mean_mag:.2f}, "
                f'{dominant.sep_arcsec:.1f}" away), which dominates the SPHEREx pixel, instead of the nearest source '
                f'Gaia DR3 {chosen.source_id} (G = {chosen.phot_g_mean_mag:.2f}, {chosen.sep_arcsec:.1f}" away).'
            )
            chosen = dominant
            match.method = "brightest_within_radius"
    match.source = chosen
    # Neighbours that matter: inside the radius and not >= AMBIGUITY_DMAG fainter than the match (a G = 20.9 star
    # 2" from Barnard's Star, G = 8.2, does not make the click ambiguous; RW Aur A next to RW Aur B does).
    rivals = [
        g
        for g in accepted
        if chosen is not None
        and g.source_id != chosen.source_id
        and (
            g.phot_g_mean_mag is None
            or chosen.phot_g_mean_mag is None
            or g.phot_g_mean_mag <= chosen.phot_g_mean_mag + AMBIGUITY_DMAG
        )
    ]
    if rivals:
        match.ambiguous = match.method != "simbad_crossid"
        brightest = min(
            (
                g
                for g in rivals
                if g.phot_g_mean_mag is not None
                and chosen.phot_g_mean_mag is not None
                and g.phot_g_mean_mag < chosen.phot_g_mean_mag
            ),
            key=_gmag,
            default=None,
        )
        text = (
            f'{len(rivals)} other Gaia DR3 source(s) of similar brightness within {radius_arcsec:.1f}" at the epoch'
            + (
                f", including a BRIGHTER one (Gaia DR3 {brightest.source_id}, G = {brightest.phot_g_mean_mag:.2f}, "
                f'{brightest.sep_arcsec:.1f}" away)'
                if brightest is not None
                else ""
            )
            + (": the identification is ambiguous." if match.ambiguous else "; SIMBAD's cross-id was used.")
        )
        warnings.append(text)
    if chosen is None and sesame is not None:
        warnings.append("No Gaia DR3 counterpart with a compatible proper motion within the match radius.")
        for g in rejected:
            warnings.append(
                f'Gaia DR3 {g.source_id} (G = {g.phot_g_mean_mag}) is {g.sep_arcsec:.1f}" away at the epoch but its '
                "proper motion disagrees with SIMBAD's: a different object, not used."
            )
    if (
        chosen is not None
        and sesame is None
        and chosen.sep_arcsec is not None
        and chosen.sep_arcsec > 0.5 * radius_arcsec
    ):
        match.loose = True
        warnings.append(
            f'The adopted Gaia DR3 source is {chosen.sep_arcsec:.1f}" from the clicked position: it may not be the '
            "object you clicked (sources absent from Gaia, such as cold brown dwarfs, cannot be matched by position)."
        )
    if chosen is not None and chosen.ruwe is not None and chosen.ruwe > RUWE_WARN:
        warnings.append(
            f"Gaia DR3 {chosen.source_id} has RUWE {chosen.ruwe:.2f} > {RUWE_WARN}: its astrometric solution may be "
            "perturbed (e.g. an unresolved companion)."
        )
    return match


# --- physical parameters (inputs of the 3D model and the data card) -----------------------------------------


def _fmt(v: float, key: str, extra: int = 0) -> str:
    if key == "teff":
        return f"{v:.{extra}f}"
    if key == "variability_period":
        return f"{v:.{4 + extra}g}" if v < 10 else f"{v:.{1 + extra}f}"
    if key == "distance":
        return f"{v:.{4 + extra}g}" if v < 100 else f"{v:.{extra}f}"
    return f"{v:.{3 + extra}g}"


def _gaia_ok(ctx: ObjectContext) -> GaiaSource | None:
    return ctx.gaia.source if ctx.gaia is not None and ctx.gaia.source is not None else None


def _stamp(ctx: ObjectContext, service: str) -> str:
    for p in ctx.provenance:
        if p.service == service and p.status == "ok" and p.retrieved_utc:
            return f", retrieved {p.retrieved_utc[:10]}"
    return ""


def _is_cool_dwarf(ctx: ObjectContext, teff: float | None) -> bool:
    sp = (ctx.spectral_type or "").strip()
    return (teff is not None and teff < 4000.0) or bool(re.match(r"^(sd)?[MLTY]", sp))


def _failed(ctx: ObjectContext, service: str) -> bool:
    """True when that service did not answer (provenance status 'error'): a gap, never a catalog negative."""
    return any(p.service == service and p.status == "error" for p in ctx.provenance)


UNREACHABLE = "could not be reached (see provenance): unknown, not a negative result."


def _plx_snr(g: GaiaSource | None) -> float | None:
    if g is None or g.parallax is None or not g.parallax_error or g.parallax_error <= 0:
        return None
    return g.parallax / g.parallax_error


def _extragalactic(ctx: ObjectContext, g: GaiaSource | None) -> tuple[str | None, bool]:
    """(reason, firm). Firm = SIMBAD types it as a galaxy/AGN/QSO; a SIMBAD candidate type or Gaia's DSC is not."""
    otype = (ctx.object_type or "").strip()
    if otype in EXTRAGALACTIC_OTYPES:
        return f"SIMBAD object type '{otype}' (extragalactic)", True
    if otype in EXTRAGALACTIC_CANDIDATE_OTYPES:
        return f"SIMBAD object type '{otype}' (extragalactic candidate)", False
    if g is not None:
        probs = [
            (kind, p)
            for kind, p in (("quasar", g.classprob_dsc_combmod_quasar), ("galaxy", g.classprob_dsc_combmod_galaxy))
            if p is not None and p >= DSC_EXTRAGALACTIC_PROB
        ]
        if probs:
            kind, p = max(probs, key=lambda kp: kp[1])
            return f"Gaia DR3 DSC classifies it as a likely {kind} (probability {p:.2f})", False
    return None, False


def _names(ctx: ObjectContext) -> set[str]:
    names = [ctx.query.get("name"), ctx.main_id, *(ctx.sesame.aliases if ctx.sesame else [])]
    return {_norm_name(n) for n in names if n}


def derive_parameters(ctx: ObjectContext) -> list[PhysicalParameter]:
    """Teff, radius, luminosity, mass, distance, spectral type, variability type/period: measured or 'unknown'.

    ``verified`` needs a secure identification: an ambiguous or distant Gaia match leaves Gaia values, SIMBAD values
    found through that match and VSX entries matched by position unverified, with the reason in the caveats.
    Stellar parameters are not shown for objects SIMBAD types as extragalactic, and a Bailer-Jones distance is not
    shown when the parallax is not significant (it would be the Galactic prior). A service that did not answer is
    reported as such, never as 'not catalogued'.
    """
    g = _gaia_ok(ctx)
    amb = ctx.gaia is not None and (ctx.gaia.ambiguous or ctx.gaia.loose)
    by_name = ctx.query.get("name") is not None
    common: list[str] = []
    if ctx.gaia is not None and ctx.gaia.ambiguous:
        common.append("Ambiguous Gaia match (several sources within the radius): not verified.")
    if ctx.gaia is not None and ctx.gaia.loose and g is not None:
        common.append(f'Adopted Gaia source is {g.sep_arcsec:.1f}" from the click: identity not verified.')
    if g is not None and g.ruwe is not None and g.ruwe > RUWE_WARN:
        common.append(f"RUWE {g.ruwe:.2f} > {RUWE_WARN}: possibly an unresolved multiple system.")
    if g is not None and re.search(r"\+\s*(sd)?[OBAFGKMLTYW]", ctx.spectral_type or ""):  # 'T1V+T6V'; not 'M6+e'
        common.append(
            f"SIMBAD's spectral type ({ctx.spectral_type}) is composite: the Gaia value may describe a blend or "
            "a single component."
        )
    exgal, exgal_firm = _extragalactic(ctx, g)
    if exgal is not None and not exgal_firm:
        common.append(f"{exgal}: Gaia's stellar parameters assume a star and may not apply.")
    trusted = not amb and exgal is None  # Gaia-derived stellar values can be marked verified
    ident_caveat = "Found through an ambiguous or distant Gaia match: may describe a neighbouring source."

    def gaia_src(table: str) -> str | None:
        if g is None:
            return None
        if ctx.gaia.catalog == GAIA_VIZIER_CATALOG:
            return f"Gaia DR3 {g.source_id}, I/355/gaiadr3 (VizieR CfA fallback{_stamp(ctx, 'gaia-vizier')})"
        return f"Gaia DR3 {g.source_id}, {table} (ESA Gaia archive{_stamp(ctx, 'gaia-esa')})"

    ap_src = gaia_src("gaiadr3.astrophysical_parameters")
    if ctx.gaia is None:
        no_gaia = "Gaia DR3 (ESA archive and VizieR CfA) " + UNREACHABLE
    elif g is None and ctx.sesame is not None and not ctx.sesame.is_simbad:
        no_gaia = "No automatic Gaia DR3 identification (name not resolved by SIMBAD; candidates listed)."
    elif g is None:
        no_gaia = "No Gaia DR3 counterpart."
    else:
        no_gaia = None
    no_details = "Gaia DR3 astrophysical parameters / distances " + UNREACHABLE
    star_only = (
        f"{exgal}: Gaia DR3 stellar parameters (GSP-Phot, FLAME) and Galactic-prior distances assume a Milky Way "
        "star; not shown."
        if exgal_firm
        else None
    )
    out: list[PhysicalParameter] = []

    # Teff
    teff = PhysicalParameter("teff", "Effective temperature", None, "K")
    if star_only:
        teff.method = star_only
    elif g is not None and g.teff_gspphot is not None:
        teff.value, teff.lower, teff.upper = g.teff_gspphot, g.teff_gspphot_lower, g.teff_gspphot_upper
        teff.method = "GSP-Phot (BP/RP spectra + parallax), 16th-84th percentiles"
        teff.source = ap_src
        teff.verified = trusted
        if _is_cool_dwarf(ctx, g.teff_gspphot):
            teff.caveats.append(
                "GSP-Phot temperatures of M dwarfs and cooler objects are unreliable (see the Gaia DR3 "
                "astrophysical-parameters documentation): indicative only."
            )
        if g.teff_gspspec is not None and abs(g.teff_gspspec - g.teff_gspphot) > GSPSPEC_DISAGREE_K:
            teff.caveats.append(f"Gaia GSP-Spec gives {g.teff_gspspec:.0f} K: the two Gaia estimates disagree.")
    elif g is not None and g.teff_espucd is not None:
        unc = g.teff_espucd_uncertainty
        teff.value, teff.source, teff.verified = g.teff_espucd, ap_src, trusted
        if unc:
            teff.lower, teff.upper = g.teff_espucd - unc, g.teff_espucd + unc
            teff.method = (
                f"ESP-UCD (ultracool dwarfs, from the Gaia RP spectrum), +/- {unc:.0f} K (teff_espucd_uncertainty); "
                "no GSP-Phot value"
            )
        else:
            teff.method = "ESP-UCD (ultracool dwarfs, from the Gaia RP spectrum); no GSP-Phot value"
            teff.caveats.append("Gaia DR3 gives no ESP-UCD uncertainty for this source.")
    elif no_gaia:
        teff.method = no_gaia
    elif g.details_from is None:
        teff.method = no_details
    else:
        teff.method = "Gaia DR3 has no temperature for this source."
    teff.caveats += common if teff.value is not None else []
    out.append(teff)

    # FLAME radius / luminosity / mass
    for key, label, attr, unit in (
        ("radius", "Radius", "radius_flame", "R_sun"),
        ("luminosity", "Luminosity", "lum_flame", "L_sun"),
        ("mass", "Mass", "mass_flame", "M_sun"),
    ):
        p = PhysicalParameter(key, label, None, unit)
        v = getattr(g, attr) if g is not None else None
        if star_only:
            p.method = star_only
        elif v is not None:
            p.value, p.lower, p.upper = v, getattr(g, f"{attr}_lower"), getattr(g, f"{attr}_upper")
            p.method = "Gaia DR3 FLAME (from GSP-Phot parameters, G photometry and the Gaia distance), 16th-84th pct"
            p.source = ap_src
            p.verified = trusted
            p.caveats.append("FLAME assumes a single star and inherits the GSP-Phot temperature.")
            if _is_cool_dwarf(ctx, g.teff_gspphot):
                p.caveats.append("For M dwarfs the GSP-Phot input is unreliable: indicative only.")
            p.caveats += common
        elif no_gaia:
            p.method = no_gaia
        elif g.details_from is None:
            p.method = no_details
        elif g.details_from == GAIA_VIZIER_CATALOG:
            p.method = "FLAME not available from the VizieR fallback (ESA Gaia archive unreachable)."
        else:
            p.method = f"Gaia DR3 FLAME gives no {label.lower()} for this source."
        out.append(p)

    # distance
    dist = PhysicalParameter("distance", "Distance", None, "pc")
    ses = ctx.sesame
    snr = _plx_snr(g)
    if star_only:
        dist.method = star_only
    elif g is not None and g.r_med_geo is not None and snr is not None and snr >= PLX_SNR_MIN:
        dist.value, dist.lower, dist.upper = g.r_med_geo, g.r_lo_geo, g.r_hi_geo
        dist.method = "Bailer-Jones et al. (2021) geometric distance from the Gaia parallax, 16th-84th percentiles"
        dist.source = gaia_src("external.gaiaedr3_distance")
        dist.verified = trusted and snr >= PLX_SNR_MEASURED
        if snr < PLX_SNR_MEASURED:
            dist.caveats.append(
                f"Gaia parallax S/N = {snr:.1f} < {PLX_SNR_MEASURED:.0f}: the distance leans on the Bailer-Jones "
                "Galactic prior."
            )
        dist.caveats += common
    elif g is not None and snr is not None and snr >= PLX_SNR_MEASURED:
        dist.value = 1000.0 / g.parallax
        dist.lower, dist.upper = 1000.0 / (g.parallax + g.parallax_error), 1000.0 / (g.parallax - g.parallax_error)
        dist.method = f"1/parallax (Gaia DR3 parallax {g.parallax:.3f} +/- {g.parallax_error:.3f} mas)"
        dist.source = gaia_src("gaiadr3.gaia_source")
        dist.verified = trusted
        dist.caveats += common
    elif ses is not None and ses.plx_mas and ses.plx_err_mas and ses.plx_mas / ses.plx_err_mas >= PLX_SNR_MEASURED:
        dist.value = 1000.0 / ses.plx_mas
        dist.lower = 1000.0 / (ses.plx_mas + ses.plx_err_mas)
        dist.upper = 1000.0 / (ses.plx_mas - ses.plx_err_mas)
        dist.method = f"1/parallax (SIMBAD parallax {ses.plx_mas} +/- {ses.plx_err_mas} mas, ref {ses.plx_ref})"
        dist.source = SESAME_CATALOG + _stamp(ctx, "sesame")
        dist.verified = by_name or not amb
        if not dist.verified:
            dist.caveats.append(ident_caveat)
    elif g is not None and g.r_med_geo is not None and snr is not None:
        dist.method = (
            f"Gaia DR3 parallax {g.parallax:.3f} +/- {g.parallax_error:.3f} mas (S/N {snr:.1f}) is not significant: "
            "the Bailer-Jones distance would be its Galactic prior alone; not shown."
        )
    elif ctx.gaia is None:
        dist.method = no_gaia
    elif g is not None and g.details_from is None:
        dist.method = no_details
    else:
        dist.method = "No parallax with S/N >= 5 (SPHEREx does not measure distances)."
    out.append(dist)

    # spectral type (SIMBAD only: Gaia ESP-HS classes are not spectral types)
    sp = PhysicalParameter("spectral_type", "Spectral type", None)
    if ctx.spectral_type:
        sp.value, sp.source = ctx.spectral_type, SESAME_CATALOG + _stamp(ctx, "sesame")
        # by name SIMBAD IS the object; on a click SIMBAD is reached through the Gaia match
        sp.verified = by_name or not amb
        if not sp.verified:
            sp.caveats.append(ident_caveat)
    elif _failed(ctx, "sesame"):
        sp.method = "SIMBAD (Sesame CfA) " + UNREACHABLE
    elif ses is not None:
        sp.method = (
            "SIMBAD gives no spectral type." if ses.is_simbad else "Name not resolved by SIMBAD: no spectral type."
        )
    elif ctx.gaia is None:
        sp.method = "No SIMBAD lookup: Gaia DR3 could not be reached (see provenance)."
    elif g is None:
        sp.method = "No SIMBAD lookup: no Gaia DR3 source here to identify."
    else:
        sp.method = f"No SIMBAD entry for Gaia DR3 {g.source_id}."
    out.append(sp)

    # variability
    var = ctx.variability
    vsx_down = _failed(ctx, "vsx")
    # VSX is matched by position along the adopted track: by name, a VSX entry with the object's own name is
    # still that object even if the Gaia match is ambiguous (RW Aur); otherwise it needs a secure identification.
    vsx_ok = not amb or (by_name and var is not None and _norm_name(var.name) in _names(ctx))
    vt = PhysicalParameter("variability_type", "Variability type", None)
    vp = PhysicalParameter("variability_period", "Variability period", None, "days")
    vsx_src = f"AAVSO VSX {var.name} (B/vsx, VizieR CfA{_stamp(ctx, 'vsx')})" if var else None
    if var is not None and var.var_type:
        rng = ""
        if var.mag_max is not None and var.mag_min is not None:
            band = f" {var.passband}" if var.passband else ""
            rng = (
                f" ({band.strip()} amplitude {var.mag_min})"
                if var.min_is_amplitude
                else f" ({band.strip()} {var.mag_max}-{var.mag_min})"
            )
        vt.value, vt.source, vt.verified = f"{var.var_type}{rng}", vsx_src, vsx_ok
        if not vsx_ok:
            vt.caveats.append(ident_caveat)
    elif vsx_down:
        vt.method = "AAVSO VSX " + UNREACHABLE
    else:
        vt.method = "No AAVSO VSX entry matched (not catalogued as variable; this does not prove it is constant)."
    lpv_p = lpv_e = None
    if g is not None and g.lpv_frequency:
        lpv_p = 1.0 / g.lpv_frequency
        lpv_e = g.lpv_frequency_error / g.lpv_frequency**2 if g.lpv_frequency_error else None
    if var is not None and var.period_d:
        vp.value, vp.source, vp.verified = var.period_d, vsx_src, vsx_ok
        if not vsx_ok:
            vp.caveats.append(ident_caveat)
        if var.var_type and "ROT" in var.var_type.upper():
            vp.caveats.append("VSX type includes ROT: a rotation period, not a pulsation.")
        if lpv_p is not None:
            vp.caveats.append(
                f"Gaia DR3 long-period-variable period: {lpv_p:.1f}" + (f" +/- {lpv_e:.1f}" if lpv_e else "") + " d."
            )
    elif lpv_p is not None:
        vp.value, vp.source, vp.verified = lpv_p, gaia_src("gaiadr3.vari_long_period_variable"), not amb
        if lpv_e:
            vp.lower, vp.upper = lpv_p - lpv_e, lpv_p + lpv_e
        if amb:
            vp.caveats += common
        if vsx_down:
            vp.caveats.append("AAVSO VSX could not be reached: its period was not checked.")
    else:
        vsx_why = "AAVSO VSX could not be reached" if vsx_down else "no period in AAVSO VSX"
        if no_gaia:
            gaia_why = "no Gaia DR3 source" if ctx.gaia is not None else "Gaia DR3 could not be reached"
        elif g.details_from is None:
            gaia_why = "Gaia DR3 long-period-variable table could not be retrieved"
        elif g.details_from == GAIA_VIZIER_CATALOG:
            gaia_why = "Gaia DR3 long-period variables not available from the VizieR fallback"
        else:
            gaia_why = "not a Gaia DR3 long-period variable"
        gap = vsx_down or ctx.gaia is None or (g is not None and g.details_from is None)
        vp.method = f"{vsx_why[0].upper()}{vsx_why[1:]}; {gaia_why}" + (
            " (see provenance): unknown, not a negative result." if gap else "."
        )
    out += [vt, vp]
    return out


def physical_parameters(ctx: ObjectContext) -> list[Fact]:
    """The parameters as contract ``Fact``s (label, value, unit, source, verified); 'unknown' when not measured."""
    return [p.to_fact() for p in derive_parameters(ctx)]


# --- contract adapter (GET /api/object, models.ObjectContextResponse) ---------------------------------------------


def identity_match(ctx: ObjectContext) -> str:
    """Contract ``ObjectMatch``: how secure the identity is (see models.ObjectMatch)."""
    gaia = ctx.gaia
    if gaia is not None and gaia.ambiguous:
        return "ambiguous"
    if gaia is not None and gaia.loose:
        return "loose"
    if ctx.query.get("name") is not None:
        return "name" if ctx.sesame is not None and ctx.sesame.is_simbad else "none"
    if gaia is None:
        return "unavailable"
    return "matched" if gaia.source is not None else "none"


def _finite_or_none(v: float | None) -> float | None:
    return v if v is not None and math.isfinite(v) else None


def to_response(
    ctx: ObjectContext, *, built_at: datetime | None = None, replay_deadline_s: float | None = None
) -> ObjectContextResponse:
    """The context as the API contract (``models.ObjectContextResponse``): the backend does no science.

    ``replay_deadline_s``: this context was REPLAYED offline from the disk cache after an API stopped waiting for
    the live lookup at that deadline. Responses not recorded yet are then reported as unanswered within the
    deadline (unknown, not negative), cache entries older than the TTL are flagged stale and the result is partial.
    """
    match = identity_match(ctx)
    by_name = ctx.query.get("name") is not None
    ses = ctx.sesame
    src = ctx.gaia.source if ctx.gaia is not None else None
    # no secure identity at all: values matched by position may belong to anything in the radius
    uncertain = bool(ctx.identity_uncertain or match == "unavailable" or (by_name and match == "none"))
    pending = None
    if replay_deadline_s is not None:
        pending = f"no answer within the {replay_deadline_s:.0f} s API deadline (lookup still running; retry later)"

    def unanswered(text: str | None) -> str | None:
        return text.replace(OFFLINE_MISS, pending) if text and pending else text

    def stamp(service: str) -> str:
        return _stamp(ctx, service).replace(", retrieved", "; retrieved")

    provenance = []
    for p in ctx.provenance:
        stale = p.stale
        if pending is not None and p.status != "error" and (_age_s(p.retrieved_utc) or 0.0) > CONTEXT_CACHE_TTL_S:
            stale = True  # an offline replay does not apply the TTL
        note = unanswered(p.note)
        provenance.append(
            ContextService(
                service=p.service,
                catalog=p.catalog,
                url=p.url or None,
                status=p.status if p.status in ("ok", "no_match", "error", "skipped") else "error",
                retrieved_utc=p.retrieved_utc,
                cached=p.cached,
                stale=stale,
                note=note[:300] if note else None,
            )
        )
    warnings = [unanswered(w) or "" for w in ctx.warnings]
    partial = any(p.status == "error" for p in provenance)
    if pending is not None and partial:
        warnings.insert(
            0,
            f"Partial result: the catalog lookup did not finish within {replay_deadline_s:.0f} s. Services marked "
            "'error' had not answered yet: their values are unknown, not negative. Retry for the full context.",
        )
    var = ctx.variability
    return ObjectContextResponse(
        query=ObjectQuery(
            ra=ctx.query["ra"] % 360.0 if ctx.query.get("ra") is not None else None,
            dec=ctx.query.get("dec"),
            name=ctx.query.get("name"),
            epoch_mjd=ctx.query.get("epoch_mjd", ctx.epoch_mjd),
            radius_arcsec=ctx.query.get("radius_arcsec", DEFAULT_RADIUS_ARCSEC),
        ),
        position=(
            ObjectPosition(ra=ctx.ra % 360.0, dec=ctx.dec, epoch_mjd=ctx.epoch_mjd, source=ctx.position_source)
            if ctx.ra is not None and ctx.dec is not None
            else None
        ),
        identity=ObjectIdentity(
            display_name=ctx.display_name,
            main_id=ctx.main_id,
            object_type=ctx.object_type,
            object_type_label=ctx.object_type_label,
            spectral_type=ctx.spectral_type,
            resolver=(SESAME_CATALOG if ses.is_simbad else f"Sesame resolver '{ses.resolver}' (CfA)") if ses else None,
            gaia_source_id=str(src.source_id) if src is not None else None,
            gaia_method=ctx.gaia.method if src is not None else None,
            match=match,
            identity_uncertain=uncertain,
            separation_arcsec=_finite_or_none(src.sep_arcsec) if src is not None else None,
            n_gaia_within_radius=ctx.gaia.n_within_radius if ctx.gaia is not None else None,
        ),
        facts=physical_parameters(ctx),
        variability=(
            ObjectVariability(
                name=var.name,
                var_type=var.var_type,
                period_days=var.period_d if var.period_d and var.period_d > 0 else None,
                mag_max=var.mag_max,
                mag_min=var.mag_min,
                min_is_amplitude=var.min_is_amplitude,
                passband=var.passband,
                separation_arcsec=_finite_or_none(var.sep_arcsec),
                url=var.url,
                source=VSX_CATALOG + stamp("vsx"),
            )
            if var is not None
            else None
        ),
        planets=[
            ObjectPlanet(
                name=p.name,
                hostname=p.hostname,
                match=p.match,
                period_days=p.period_d,
                semi_major_axis_au=p.semi_major_axis_au,
                radius_earth=p.radius_earth,
                radius_calculated=p.radius_calculated,
                mass_earth=p.mass_earth,
                mass_kind=p.mass_kind,
                eccentricity=p.eccentricity,
                inclination_deg=p.inclination_deg,
                discovery_year=p.discovery_year,
                discovery_method=p.discovery_method,
                discovery_facility=p.discovery_facility,
                reference=p.reference,
                controversial=p.controversial,
                source=EXOPLANET_CATALOG + stamp("exoplanets"),
            )
            for p in ctx.planets
        ],
        nearby_planet_hosts=[
            NearbyPlanetHost(
                hostname=h["hostname"], separation_arcsec=h["sep_arcsec"], planets=[n for n in h["planets"] if n]
            )
            for h in ctx.nearby_planet_hosts
        ],
        photometry=[
            ContextMagnitude(
                mission=m.mission,
                catalog=m.catalog,
                designation=m.designation,
                band=m.band,
                wavelength_um=m.wavelength_um,
                mag=m.mag,
                mag_err=m.mag_err if m.mag_err is None or m.mag_err >= 0 else None,
                system=m.system,
                quality=m.quality,
                contamination=m.contamination,
                upper_limit=m.upper_limit,
                epoch_mjd=m.epoch_mjd,
                separation_arcsec=_finite_or_none(m.sep_arcsec),
                identity_uncertain=m.identity_uncertain or uncertain,
            )
            for m in ctx.photometry
        ],
        warnings=warnings,
        provenance=provenance,
        partial=partial,
        built_at=built_at or datetime.now(UTC),
        note=CONTEXT_NOTE,
    )
