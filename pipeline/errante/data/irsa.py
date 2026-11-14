"""Find SPHEREx Level-2 frames covering a sky position: IRSA SIA2, TAP fallback (WS1, P0).

Verified live on 2026-11-14 (docs/DATA.md §3.0):

* SIA2 (1-4 s): ``https://irsa.ipac.caltech.edu/SIA?COLLECTION=spherex_dr1&COLLECTION=spherex_qr3
  &POS=CIRCLE+<ra>+<dec>+<r>&RESPONSEFORMAT=VOTABLE``. Ask for **VOTable**: the CSV output is broken
  (``cloud_access`` is unquoted JSON). Rows carry ``access_url``, ``cloud_access`` (JSON with
  ``aws.bucket_name/key/region``), ``t_min``/``t_max`` [MJD], ``energy_bandpassname`` ('SPHEREx-D<n>')
  and ``obs_collection``. ``TIME`` and ``MAXREC`` work. A collection that does not exist returns an
  EMPTY VOTable with no error, so collection names come from ``settings.IRSA_COLLECTIONS``.
  Each exposure covers a point with ONE dichroic pair (D1/D4, D2/D5 or D3/D6), so one obs_id gives
  at most 2 rows at a position.
* Deep-field collections (opt-in) use the same S3 layout: ``spherex_dr1_deep`` keys start with
  ``dr1/level2/`` and ``spherex_qr3_deep`` keys with ``qr3/level2/``, so ``release`` maps cleanly;
  only ``ArchiveRow.collection`` tells wide and deep apart.
* TAP (8-19 s) is the fallback: ``spherex.artifact`` JOIN ``spherex.plane`` (+ ``spherex.observation``
  for the collection) with ``CONTAINS(POINT, p.poly)``.
* Pipeline versions (``l2b-v27-2026-NNN``) change per week AND detector: never build paths by hand,
  use the key/URI returned by the archive.

Timeouts surface as ``requests.Timeout`` in the ``__cause__`` chain of :class:`SearchError` (the
backend maps that to HTTP 504 and any other failure to 502).
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import logging
import math
import re
import time
import uuid
import warnings
from dataclasses import dataclass, field
from pathlib import Path

import requests

from .. import settings
from ..models import FrameRef, SearchResult, SkyCoord
from . import s3

log = logging.getLogger(__name__)

MIN_RADIUS_DEG = 1.0 / 3600.0
"""Smallest search radius: a point search is a 1 arcsec circle."""
IRSA_DATA_PREFIX = "ibe/data/spherex/"
"""Relative IRSA path of every SPHEREx file; the S3 key is the rest of the path."""
CACHE_FORMAT = 1
"""Bump when the cached JSON layout or the row parsing changes (old entries are then ignored)."""

_MJD_FLOOR, _MJD_CEIL = 0.0, 100000.0  # open TIME bounds sent to SIA/TAP
_RELEASES = ("dr1", "qr2", "qr3")  # contract Release literal, minus 'synthetic'
# Same (obs_id, detector) in several releases: the data release (reprocessed, definitive)
# beats quick releases; among those, the newest quick release wins.
_RELEASE_RANK = {"dr1": 3, "qr3": 2, "qr2": 1}
_BAND_RE = re.compile(r"D([1-6])\s*$")
_VERSION_RE = re.compile(r"v(\d+)-(\d{4})-(\d+)")

ADQL_FRAMES_AT_POSITION = """
SELECT a.uri, p.planeid, p.time_bounds_lower, p.time_bounds_upper, p.energy_bandpassname, o.collection
FROM spherex.artifact a
JOIN spherex.plane p ON a.planeid = p.planeid
JOIN spherex.observation o ON p.obsid = o.obsid
WHERE 1 = {region}
{collection_clause}
{time_clause}
{band_clause}
ORDER BY p.time_bounds_lower
"""


class SearchError(RuntimeError):
    """The archive search failed. ``__cause__`` keeps the last transport error (e.g. ``requests.Timeout``).

    ``failures`` lists the underlying error of every service tried, in order (SIA, then TAP).
    """

    def __init__(self, message: str, failures: list[BaseException] | None = None):
        super().__init__(message)
        self.failures = list(failures or [])

    @property
    def is_outage(self) -> bool:
        """True when every service failed at the transport level (5xx/429, timeout, connection)."""
        return bool(self.failures) and all(_is_transport_failure(e) for e in self.failures)


def _is_transport_failure(err: BaseException) -> bool:
    if isinstance(err, (requests.Timeout, requests.ConnectionError, TimeoutError)):
        return True
    response = getattr(err, "response", None)
    return isinstance(err, requests.HTTPError) and response is not None and response.status_code >= 429


@dataclass(frozen=True)
class ArchiveRow:
    """One archive frame plus provenance the contract does not carry."""

    ref: FrameRef
    collection: str
    pipeline_version: str


@dataclass
class SearchReport:
    """``search_frames`` result plus how it was obtained (for the CLI and logs)."""

    result: SearchResult
    rows: list[ArchiveRow]
    service: str  # 'sia' or 'tap' (the service that produced the data, even when read from cache)
    from_cache: bool
    elapsed_s: float
    collections: tuple[str, ...]
    overflow: bool = False
    n_duplicates: int = 0
    errors: list[str] = field(default_factory=list)
    stale: bool = False  # True when IRSA failed and an expired cache entry was served instead


@dataclass(frozen=True)
class _CacheEntry:
    rows: list[ArchiveRow]
    service: str
    overflow: bool
    n_duplicates: int
    age_s: float


# --------------------------------------------------------------------------- public API


def search_frames(
    ra: float,
    dec: float,
    radius_deg: float = 0.0,
    detectors: list[int] | None = None,
    mjd_min: float | None = None,
    mjd_max: float | None = None,
    *,
    collections: list[str] | tuple[str, ...] | None = None,
    use_cache: bool = True,
) -> SearchResult:
    """All SPHEREx L2 frames whose footprint touches a circle of ``radius_deg`` around (ra, dec).

    ``radius_deg=0`` is a point search (1 arcsec circle). ``detectors`` keeps only those detectors;
    ``mjd_min``/``mjd_max`` keep frames whose exposure overlaps that interval. Frames are deduplicated
    by (obs_id, detector), preferring DR1 over quick releases, and sorted by mid-exposure MJD.
    ``collections`` defaults to ``settings.IRSA_COLLECTIONS`` (env ``ERRANTE_COLLECTIONS``).
    """
    return search_frames_report(
        ra, dec, radius_deg, detectors, mjd_min, mjd_max, collections=collections, use_cache=use_cache
    ).result


def search_frames_report(
    ra: float,
    dec: float,
    radius_deg: float = 0.0,
    detectors: list[int] | None = None,
    mjd_min: float | None = None,
    mjd_max: float | None = None,
    *,
    collections: list[str] | tuple[str, ...] | None = None,
    use_cache: bool = True,
) -> SearchReport:
    """Same as :func:`search_frames` but also says which service answered, cache use and timing."""
    t0 = time.monotonic()
    ra, dec, radius, dets = _validate(ra, dec, radius_deg, detectors, mjd_min, mjd_max)
    cols = normalize_collections(collections)
    key = cache_key(ra, dec, radius, mjd_min, mjd_max, cols)

    use_cache = use_cache and settings.QUERY_CACHE_TTL_S > 0
    cached = _cache_read(key) if use_cache else None
    errors: list[str] = []
    stale = False
    if cached is not None and cached.age_s <= settings.QUERY_CACHE_TTL_S:
        rows, service, overflow, n_dup = cached.rows, cached.service, cached.overflow, cached.n_duplicates
        from_cache = True
    else:
        try:
            raw, service, overflow, errors = _query_archive(ra, dec, radius, mjd_min, mjd_max, cols)
        except SearchError as e:
            if cached is None:
                raise
            # IRSA is down: an expired answer beats no answer (new weeks may be missing).
            log.warning("IRSA unavailable; using a %.1f h old cached search (%s)", cached.age_s / 3600, e)
            rows, service, overflow, n_dup = cached.rows, cached.service, cached.overflow, cached.n_duplicates
            from_cache, stale, errors = True, True, [str(e)]
        else:
            rows, n_dup = dedupe_rows(raw)
            from_cache = False
            if use_cache and rows:  # an empty answer is suspicious (all-sky survey): do not pin it for a day
                _cache_write(key, rows, service, overflow, n_dup)

    if dets is not None:
        rows = [r for r in rows if r.ref.detector in dets]
    result = SearchResult(center=SkyCoord(ra=ra, dec=dec), radius_deg=radius, frames=[r.ref for r in rows])
    elapsed = time.monotonic() - t0
    log.info(
        "search_frames(%.5f, %.5f, r=%.5g): %d frames via %s%s in %.2f s",
        ra,
        dec,
        radius,
        len(rows),
        service,
        " (stale cache)" if stale else " (cache)" if from_cache else "",
        elapsed,
    )
    return SearchReport(
        result=result,
        rows=rows,
        service=service,
        from_cache=from_cache,
        elapsed_s=elapsed,
        collections=cols,
        overflow=overflow,
        n_duplicates=n_dup,
        errors=errors,
        stale=stale,
    )


def normalize_collections(collections: list[str] | tuple[str, ...] | str | None) -> tuple[str, ...]:
    """Sorted, de-duplicated collection names (default: ``settings.IRSA_COLLECTIONS``)."""
    if collections is None:
        collections = settings.IRSA_COLLECTIONS
    if isinstance(collections, str):
        collections = collections.split(",")
    cols = tuple(sorted({c.strip() for c in collections if c and c.strip()}))
    if not cols:
        raise ValueError("At least one IRSA collection is required")
    for c in cols:
        if not re.fullmatch(r"[A-Za-z0-9_]+", c):
            raise ValueError(f"Invalid collection name: {c!r}")
    return cols


def build_query(
    ra: float,
    dec: float,
    detector: int | None = None,
    *,
    radius_deg: float = 0.0,
    mjd_min: float | None = None,
    mjd_max: float | None = None,
    collections: list[str] | tuple[str, ...] | None = None,
) -> str:
    """ADQL for the TAP fallback (``ADQL_FRAMES_AT_POSITION``)."""
    if radius_deg > MIN_RADIUS_DEG:
        region = f"INTERSECTS(CIRCLE('ICRS', {ra:.8f}, {dec:.8f}, {radius_deg:.9g}), p.poly)"
    else:
        region = f"CONTAINS(POINT('ICRS', {ra:.8f}, {dec:.8f}), p.poly)"
    collection_clause = ""
    if collections:
        names = ", ".join(f"'{c}'" for c in normalize_collections(collections))
        collection_clause = f"AND o.collection IN ({names})"
    time_clause = ""
    if mjd_min is not None or mjd_max is not None:
        lo = _MJD_FLOOR if mjd_min is None else float(mjd_min)
        hi = _MJD_CEIL if mjd_max is None else float(mjd_max)
        time_clause = f"AND p.time_bounds_upper >= {lo:.8f} AND p.time_bounds_lower <= {hi:.8f}"
    band_clause = f"AND p.energy_bandpassname = 'SPHEREx-D{int(detector)}'" if detector else ""
    return ADQL_FRAMES_AT_POSITION.format(
        region=region, collection_clause=collection_clause, time_clause=time_clause, band_clause=band_clause
    )


def sia_params(
    ra: float,
    dec: float,
    radius_deg: float,
    mjd_min: float | None,
    mjd_max: float | None,
    collections: tuple[str, ...],
) -> list[tuple[str, str]]:
    """SIA2 query parameters (``COLLECTION`` repeated once per collection)."""
    params = [("COLLECTION", c) for c in collections]
    params += [
        ("POS", f"CIRCLE {ra:.8f} {dec:.8f} {max(radius_deg, MIN_RADIUS_DEG):.9g}"),
        ("RESPONSEFORMAT", "VOTABLE"),
        ("MAXREC", str(settings.SIA_MAXREC)),
    ]
    if mjd_min is not None or mjd_max is not None:
        lo = _MJD_FLOOR if mjd_min is None else float(mjd_min)
        hi = _MJD_CEIL if mjd_max is None else float(mjd_max)
        params.append(("TIME", f"{lo:.8f} {hi:.8f}"))
    return params


def dedupe_rows(rows: list[ArchiveRow]) -> tuple[list[ArchiveRow], int]:
    """Keep one row per (obs_id, detector), preferring DR1 then newer pipeline versions; sort by MJD."""
    best: dict[tuple[str, int], ArchiveRow] = {}
    for row in rows:
        k = (row.ref.obs_id, row.ref.detector)
        if k not in best or _preference(row) > _preference(best[k]):
            best[k] = row
    out = sorted(best.values(), key=lambda r: (r.ref.mjd, r.ref.detector, r.ref.obs_id))
    return out, len(rows) - len(out)


# --------------------------------------------------------------------------- parsing


def parse_sia_votable(content: bytes) -> tuple[list[ArchiveRow], bool]:
    """Rows of an SIA2 VOTable response and whether it overflowed ``MAXREC``."""
    from astropy.io.votable import parse as parse_votable

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        vot = parse_votable(io.BytesIO(content), verify="ignore")
    status, message = "OK", ""
    for info in vot.iter_info():
        if info.name == "QUERY_STATUS":
            status = (info.value or "").upper()
            message = (info.content or "").strip()
    if status == "ERROR":
        raise SearchError(f"SIA returned an error: {message or 'no message'}")
    # IRSA sends a type="meta" RESOURCE (service self-description) before the type="results" one.
    tables = [t for r in vot.resources if r.type == "results" for t in r.tables] or list(vot.iter_tables())
    if not tables:
        return [], status == "OVERFLOW"
    # IRSA FIELDs have ID="col_<n>" and the record array is keyed by ID: map FIELD names by position.
    # (Reading the raw array is ~100x faster than Table.to_table() + row iteration on 20k-row deep fields.)
    vt = tables[0]
    arr = vt.array
    by_name = {f.name.lower(): dtype_name for f, dtype_name in zip(vt.fields, arr.dtype.names, strict=True)}
    if "access_url" not in by_name and "cloud_access" not in by_name:
        raise SearchError(f"SIA response has no access_url/cloud_access columns: {sorted(by_name)}")

    def column(name: str) -> list:
        key = by_name.get(name)
        return [None] * len(arr) if key is None else [_plain(v) for v in arr[key].tolist()]

    rows: list[ArchiveRow] = []
    for cloud, access_url, t_lo, t_hi, band, collection in zip(
        column("cloud_access"),
        column("access_url"),
        column("t_min"),
        column("t_max"),
        column("energy_bandpassname"),
        column("obs_collection"),
        strict=True,
    ):
        key = _key_from_cloud_access(cloud)
        irsa_uri = _irsa_uri(access_url) if access_url else None
        if key is None and irsa_uri:
            key = s3.irsa_uri_to_s3_key(irsa_uri)
        row = _make_row(key, irsa_uri, t_lo, t_hi, band, collection or "")
        if row is not None:
            rows.append(row)
    if status == "OVERFLOW":
        log.warning("SIA result truncated at MAXREC (QUERY_STATUS=OVERFLOW, %d rows)", len(rows))
    return rows, status == "OVERFLOW"


def parse_tap_csv(text: str) -> list[ArchiveRow]:
    """Rows of a TAP CSV response to :func:`build_query`."""
    if text.lstrip().startswith("<"):  # TAP reports errors as a VOTable
        m = re.search(r"<INFO[^>]*QUERY_STATUS[^>]*>(.*?)</INFO>", text, re.S)
        raise SearchError(f"TAP returned an error: {(m.group(1).strip() if m else text[:300])}")
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames or "uri" not in reader.fieldnames:
        raise SearchError(f"TAP response has no 'uri' column: {reader.fieldnames}")
    rows: list[ArchiveRow] = []
    for rec in reader:
        uri = (rec.get("uri") or "").strip()
        if not uri:
            continue
        irsa_uri = _irsa_uri(uri)
        row = _make_row(
            s3.irsa_uri_to_s3_key(irsa_uri),
            irsa_uri,
            _float_or_none(rec.get("time_bounds_lower")),
            _float_or_none(rec.get("time_bounds_upper")),
            rec.get("energy_bandpassname"),
            (rec.get("collection") or "").strip(),
        )
        if row is not None:
            rows.append(row)
    return rows


# --------------------------------------------------------------------------- services


def _query_archive(
    ra: float,
    dec: float,
    radius: float,
    mjd_min: float | None,
    mjd_max: float | None,
    cols: tuple[str, ...],
) -> tuple[list[ArchiveRow], str, bool, list[str]]:
    errors: list[str] = []
    try:
        rows, overflow = _search_sia(ra, dec, radius, mjd_min, mjd_max, cols)
        return rows, "sia", overflow, errors
    except Exception as e:  # any SIA failure (HTTP, timeout, parse) falls back to TAP
        sia_err = e
        log.warning("SIA search failed (%s); falling back to TAP", _describe(sia_err))
        errors.append(f"sia: {_describe(sia_err)}")
    try:
        rows = _search_tap(ra, dec, radius, mjd_min, mjd_max, cols)
    except Exception as tap_err:
        errors.append(f"tap: {_describe(tap_err)}")
        raise SearchError(f"IRSA frame search failed ({'; '.join(errors)})", [sia_err, tap_err]) from tap_err
    return rows, "tap", False, errors


def _search_sia(
    ra: float, dec: float, radius: float, mjd_min: float | None, mjd_max: float | None, cols: tuple[str, ...]
) -> tuple[list[ArchiveRow], bool]:
    params = sia_params(ra, dec, radius, mjd_min, mjd_max, cols)
    t0 = time.monotonic()
    resp = _fetch("GET", settings.IRSA_SIA, params=params, timeout=settings.SIA_TIMEOUT_S)
    rows, overflow = parse_sia_votable(resp.content)
    log.info("SIA: %d rows, %.0f KB in %.2f s", len(rows), len(resp.content) / 1024, time.monotonic() - t0)
    return rows, overflow


def _search_tap(
    ra: float, dec: float, radius: float, mjd_min: float | None, mjd_max: float | None, cols: tuple[str, ...]
) -> list[ArchiveRow]:
    query = build_query(ra, dec, radius_deg=radius, mjd_min=mjd_min, mjd_max=mjd_max, collections=cols)
    data = {"REQUEST": "doQuery", "LANG": "ADQL", "FORMAT": "csv", "QUERY": query}
    t0 = time.monotonic()
    resp = _fetch("POST", settings.IRSA_TAP_SYNC, data=data, timeout=settings.TAP_TIMEOUT_S)
    rows = parse_tap_csv(resp.text)
    log.info("TAP: %d rows in %.2f s", len(rows), time.monotonic() - t0)
    return rows


def _http(method: str, url: str, *, params=None, data=None, timeout: float) -> requests.Response:
    """One HTTP attempt (tests replace this)."""
    return requests.request(method, url, params=params, data=data, timeout=timeout)


def _fetch(method: str, url: str, *, params=None, data=None, timeout: float) -> requests.Response:
    """HTTP with retries and exponential backoff on 5xx/429, connection errors and timeouts.

    4xx is raised at once. A timeout is retried once at most (each one already cost ``timeout``
    seconds). The last transport error is re-raised as is, so ``requests.Timeout`` survives.
    """
    attempts = max(1, settings.SEARCH_ATTEMPTS)
    timeouts = 0
    last: Exception | None = None
    for attempt in range(attempts):
        if attempt:
            delay = settings.SEARCH_BACKOFF_S * 2 ** (attempt - 1)
            retry_after = getattr(getattr(last, "response", None), "headers", {}).get("Retry-After", "")
            if retry_after.isdigit():
                delay = max(delay, min(float(retry_after), 10.0))
            log.info("Retry %d/%d of %s in %.1f s after %s", attempt + 1, attempts, url, delay, _describe(last))
            time.sleep(delay)
        try:
            resp = _http(method, url, params=params, data=data, timeout=timeout)
        except requests.Timeout as e:  # also ConnectTimeout
            last = e
            timeouts += 1
            if timeouts > 1:
                break
            continue
        except requests.ConnectionError as e:
            last = e
            continue
        if resp.status_code >= 500 or resp.status_code == 429:
            last = requests.HTTPError(f"HTTP {resp.status_code} from {url}", response=resp)
            continue
        resp.raise_for_status()
        return resp
    assert last is not None
    raise last


# --------------------------------------------------------------------------- cache


def cache_key(
    ra: float,
    dec: float,
    radius: float,
    mjd_min: float | None,
    mjd_max: float | None,
    collections: tuple[str, ...],
) -> str:
    """Stable key of a search (detectors are filtered after the cache, so they are not part of it)."""
    ident = {
        "format": CACHE_FORMAT,
        "ra": round(ra, 7),
        "dec": round(dec, 7),
        "radius": round(radius, 9),
        "mjd_min": None if mjd_min is None else round(float(mjd_min), 6),
        "mjd_max": None if mjd_max is None else round(float(mjd_max), 6),
        "collections": list(collections),
    }
    return hashlib.sha256(json.dumps(ident, sort_keys=True).encode()).hexdigest()[:32]


def cache_file(key: str) -> Path:
    return settings.CACHE_DIR / "queries" / f"search_{key}.json"


def _cache_read(key: str) -> _CacheEntry | None:
    """The cached search for ``key`` whatever its age (the caller applies the TTL), or None."""
    path = cache_file(key)
    if not path.exists():
        return None
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
        if doc.get("format") != CACHE_FORMAT:
            return None
        rows = [
            ArchiveRow(FrameRef.model_validate(r["frame"]), r["collection"], r["pipeline_version"]) for r in doc["rows"]
        ]
        return _CacheEntry(
            rows=rows,
            service=str(doc["service"]),
            overflow=bool(doc["overflow"]),
            n_duplicates=int(doc["n_duplicates"]),
            age_s=max(0.0, time.time() - float(doc["created"])),
        )
    except (OSError, ValueError, KeyError, TypeError) as e:
        log.warning("Ignoring unreadable search cache %s: %s", path, e)
        return None


def _cache_write(key: str, rows: list[ArchiveRow], service: str, overflow: bool, n_dup: int) -> None:
    path = cache_file(key)
    doc = {
        "format": CACHE_FORMAT,
        "created": time.time(),
        "service": service,
        "overflow": overflow,
        "n_duplicates": n_dup,
        "rows": [
            {"collection": r.collection, "pipeline_version": r.pipeline_version, "frame": r.ref.model_dump()}
            for r in rows
        ],
    }
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(f"{path.name}.{uuid.uuid4().hex}.part")  # unique: backend threads may race
        tmp.write_text(json.dumps(doc, separators=(",", ":")), encoding="utf-8")
        tmp.replace(path)
    except OSError as e:  # a read-only cache must not break the search
        log.warning("Could not write search cache %s: %s", path, e)


# --------------------------------------------------------------------------- helpers


def _validate(
    ra: float,
    dec: float,
    radius_deg: float,
    detectors: list[int] | None,
    mjd_min: float | None,
    mjd_max: float | None,
) -> tuple[float, float, float, frozenset[int] | None]:
    ra, dec, radius_deg = float(ra), float(dec), float(radius_deg)
    if not (math.isfinite(ra) and math.isfinite(dec) and -90.0 <= dec <= 90.0):
        raise ValueError(f"Invalid position ra={ra}, dec={dec}")
    if not math.isfinite(radius_deg) or radius_deg < 0 or radius_deg > 10:
        raise ValueError(f"radius_deg must be within [0, 10], got {radius_deg}")
    for v in (mjd_min, mjd_max):
        if v is not None and not math.isfinite(float(v)):
            raise ValueError(f"Invalid MJD bound {v}")
    if mjd_min is not None and mjd_max is not None and float(mjd_min) > float(mjd_max):
        raise ValueError(f"mjd_min ({mjd_min}) > mjd_max ({mjd_max})")
    dets = None
    if detectors:
        dets = frozenset(int(d) for d in detectors)
        if not dets <= set(range(1, 7)):
            raise ValueError(f"Detectors must be 1-6, got {sorted(dets)}")
    return ra % 360.0, dec, max(radius_deg, MIN_RADIUS_DEG), dets


def _make_row(
    key: str | None,
    irsa_uri: str | None,
    t_lo: float | None,
    t_hi: float | None,
    bandpass: str | None,
    collection: str,
) -> ArchiveRow | None:
    if not key:
        return None
    try:
        parsed = s3.parse_key(key)
    except ValueError:
        log.debug("Skipping non-level2 archive row: %s", key)
        return None
    if parsed.release not in _RELEASES:
        log.warning("Skipping frame from unknown release prefix %r: %s", parsed.release, key)
        return None
    times = [t for t in (t_lo, t_hi) if t is not None and math.isfinite(t)]
    if not times:
        log.warning("Skipping frame without exposure time: %s", key)
        return None
    if bandpass:
        m = _BAND_RE.search(str(bandpass))
        if m and int(m.group(1)) != parsed.detector:
            log.warning("Detector mismatch %s vs file name %s; trusting the file name", bandpass, key)
    ref = FrameRef(
        obs_id=parsed.obs_id,
        detector=parsed.detector,
        mjd=sum(times) / len(times),
        release=parsed.release,
        irsa_uri=irsa_uri or f"{IRSA_DATA_PREFIX}{key}",
        s3_key=key,
        wavelength_um=None,
    )
    return ArchiveRow(ref=ref, collection=collection, pipeline_version=parsed.pipeline_version)


def _key_from_cloud_access(value) -> str | None:
    if not value:
        return None
    try:
        key = json.loads(value)["aws"]["key"]
    except (ValueError, KeyError, TypeError):
        return None
    return key.lstrip("/") if isinstance(key, str) and key else None


def _irsa_uri(url_or_uri: str) -> str:
    """'https://irsa.ipac.caltech.edu/ibe/data/spherex/x' or '/ibe/...' -> 'ibe/data/spherex/x'."""
    uri = str(url_or_uri).strip()
    if uri.startswith(settings.IRSA_BASE):
        uri = uri[len(settings.IRSA_BASE) :]
    elif "://" in uri and IRSA_DATA_PREFIX in uri:
        uri = uri[uri.index(IRSA_DATA_PREFIX) :]
    return uri.split("?", 1)[0].lstrip("/")


def _plain(value):
    """VOTable cell -> None / str / float."""
    import numpy as np

    if value is None or value is np.ma.masked:
        return None
    if isinstance(value, bytes):
        value = value.decode("utf-8", "replace")
    if isinstance(value, str):
        return value.strip() or None
    if isinstance(value, np.generic):
        value = value.item()
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def _float_or_none(value) -> float | None:
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


def _preference(row: ArchiveRow) -> tuple[int, tuple[int, ...]]:
    m = _VERSION_RE.search(row.pipeline_version)
    version = tuple(int(g) for g in m.groups()) if m else (0,)
    return _RELEASE_RANK.get(row.ref.release, 0), version


def _describe(err: BaseException) -> str:
    return f"{type(err).__name__}: {err}"
