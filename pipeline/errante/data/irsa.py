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
backend maps that to HTTP 504 and any other failure to 502). When one service timed out and the
other failed differently (e.g. SIA timeout, TAP 502), the timeout is the cause, so callers see 504.

A whole search is bounded by ``settings.SEARCH_DEADLINE_S`` (a supervised build job gets
``settings.JOB_SEARCH_DEADLINE_S`` instead, see settings.py). Within it :func:`_query_archive` asks SIA, SIA
again, then alternates TAP / SIA (a timeout switches service at once), with a short exponential backoff
(``SEARCH_BACKOFF_S`` x 1, 2, 4, 8, at most 4 s, plus up to 25 % jitter) after fast failures. Only HTTP 429/5xx,
connection errors and timeouts are retried; a 4xx or an answer that does not parse drops that service for the
search. Each service gets at most ``SEARCH_ATTEMPTS`` attempts and two timeouts. An SIA attempt may hold half of
the time left but at least 10 s, or all of a shorter remainder (:func:`sia_budget`), so a hung SIA still leaves TAP
its turn; no attempt starts without at least ``_MIN_ATTEMPT_S`` left and no attempt's timeout outlives the
deadline. 2026-11-15: IRSA answered SIA/TAP with intermittent fast 502s and hangs, and one try per service failed
every map-click build (docs/DATA.md §3.4).
When the search has a fallback in hand (an expired cache entry or a covering snapshot, see below) the
budget is capped at ``settings.SEARCH_FALLBACK_DEADLINE_S`` (20 s), so the fallback still answers before
the backend gives up on the request (ERRANTE_API_TIMEOUT_S, 30 s -> HTTP 504).
TAP runs one query at a time per process (module lock), as IRSA asks.

Results truncated at MAXREC (SIA ``QUERY_STATUS=OVERFLOW``) are flagged and never cached, so raising
``ERRANTE_SIA_MAXREC`` takes effect on the next search.

When SIA and TAP both fail and there is no cached answer (not even an expired one), a committed
**search snapshot** (``data/index/search/<field-id>.json``, written by ``errante snapshot-search``)
answers searches that fall inside its disk: a real SIA answer around a showcase field, replayed
offline with each frame's footprint (``s_region``), the collections and the detector/MJD filters.
It is flagged (``service='snapshot'``, ``stale=True``, a warning with the query date) and never used
while IRSA answers. See :func:`find_snapshot` and :func:`fetch_snapshot`.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import logging
import math
import os
import random
import re
import threading
import time
import uuid
import warnings
from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, datetime
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
# Matches 'l2b-v27-2026-228' and the rarer 'l2b_retry-v27-2026-230' (seen once at Barnard's Star).
_VERSION_RE = re.compile(r"v(\d+)-(\d{4})-(\d+)")
_SIA_SHARE = 0.5  # fraction of the search budget that SIA may use before TAP gets the rest (see sia_budget)
_SIA_MIN_S = 10.0  # ... but never less (or the whole budget when shorter): SIA's slowest answer seen was 9.3 s
_MIN_ATTEMPT_S = 2.0  # do not start an HTTP attempt with less time than this left
_BACKOFF_MAX_S = 4.0  # longest pause between two search attempts (before jitter)
_MAX_TIMEOUTS = 2  # a service that hung twice is not asked again in the same search
_SERVICES = ("sia", "tap")
_TAP_LOCK = threading.Lock()  # IRSA asks for one TAP query at a time (backend threads + CLI share it)
# Collections that exist in SIA2/ObsCore (verified live 2026-11-14; qr2 is no longer indexed).
_VERIFIED_COLLECTIONS = frozenset({"spherex_dr1", "spherex_dr1_deep", "spherex_qr3", "spherex_qr3_deep"})

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
    """The archive search failed. ``__cause__`` is the first timeout if any attempt timed out, else the last error.

    ``failures`` lists the error of every failed attempt, in order (the attempt history: SIA, SIA, TAP, ...); the
    message names each one (``sia 2/4: HTTPError: HTTP 502 ...``).
    """

    def __init__(self, message: str, failures: list[BaseException] | None = None):
        super().__init__(message)
        self.failures = list(failures or [])

    @property
    def is_outage(self) -> bool:
        """True when every service failed at the transport level (5xx/429, timeout, connection)."""
        return bool(self.failures) and all(_is_transport_failure(e) for e in self.failures)


def _is_timeout(err: BaseException) -> bool:
    return isinstance(err, (requests.Timeout, TimeoutError))


def _is_retryable(err: BaseException) -> bool:
    """Worth asking again: a timeout, a connection error, HTTP 429 or 5xx. Not a 4xx, not an answer that did not parse."""
    if _is_timeout(err) or isinstance(err, requests.ConnectionError):
        return True
    status = getattr(getattr(err, "response", None), "status_code", None)
    return isinstance(err, requests.HTTPError) and status is not None and (status == 429 or status >= 500)


def _is_transport_failure(err: BaseException) -> bool:
    if _is_timeout(err) or isinstance(err, requests.ConnectionError):
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
    # 'sia' or 'tap' (the service that produced the data, even when read from cache), or 'snapshot'
    # when IRSA was down and a committed search snapshot answered (then stale=True; see warnings).
    service: str
    from_cache: bool
    elapsed_s: float
    collections: tuple[str, ...]
    overflow: bool = False
    n_duplicates: int = 0
    # Why the answer is a fallback: the failed SIA attempts when TAP answered, or the SearchError when a stale
    # cache entry / snapshot answered. Empty when SIA answered, even after retries (the answer is complete).
    errors: list[str] = field(default_factory=list)
    # Every failed attempt before the answer ("sia 1/4: HTTPError: HTTP 502 ..."), for logs and the CLI only; a
    # search answered on a retry is not partial (backend/errante_api/lightcurve_build.py reads ``errors``).
    retries: list[str] = field(default_factory=list)
    # True when IRSA failed and an older answer was served instead: an expired cache entry (``service`` is
    # the service that produced it) or a committed search snapshot (``service == 'snapshot'``).
    stale: bool = False
    warnings: list[str] = field(default_factory=list)  # e.g. unknown collection names (IRSA ignores them)


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
    use_snapshot: bool | None = None,
    deadline_s: float | None = None,
) -> SearchReport:
    """Same as :func:`search_frames` but also says which service answered, cache use and timing.

    ``use_snapshot`` (default: same as ``use_cache``) allows the committed search snapshots as a last
    resort, only after SIA and TAP both failed and no cached answer exists (see :func:`find_snapshot`).
    With such a fallback in hand IRSA gets ``settings.SEARCH_FALLBACK_DEADLINE_S`` at most
    (:func:`search_budget`).

    ``deadline_s`` (optional) caps further the seconds this call may spend asking IRSA, for a caller with a
    wall-clock budget of its own (``point.point_series(deadline_s=...)``). Like every budget here, no attempt
    starts with less than ``_MIN_ATTEMPT_S`` (2 s) left: with less, IRSA is not asked and a fresh cached
    answer, an expired one or a snapshot answers, else :class:`SearchError` (``requests.Timeout`` cause).
    SIA may use all of a budget up to 10 s and half of a longer one (:func:`sia_budget`), so under ~20 s TAP
    (8-19 s) has little or no time left: a hung SIA then ends in that timeout, not in a TAP answer.
    """
    if deadline_s is not None and math.isnan(deadline_s):
        raise ValueError("deadline_s must be a number of seconds (or None)")
    t0 = time.monotonic()
    allow_snapshot = use_cache if use_snapshot is None else use_snapshot
    ra, dec, radius, dets = _validate(ra, dec, radius_deg, detectors, mjd_min, mjd_max)
    cols = normalize_collections(collections)
    warn = [
        f"unknown IRSA collection {c!r}: IRSA returns no rows for it without an error"
        for c in cols
        if c not in known_collections()
    ]
    for w in warn:
        log.warning(w)
    key = cache_key(ra, dec, radius, mjd_min, mjd_max, cols)

    use_cache = use_cache and settings.QUERY_CACHE_TTL_S > 0
    cached = _cache_read(key) if use_cache else None
    errors: list[str] = []
    retries: list[str] = []
    stale = False
    # A truncated (overflow) entry is never served as fresh: MAXREC may have been raised since.
    if cached is not None and cached.age_s <= settings.QUERY_CACHE_TTL_S and not cached.overflow:
        rows, service, overflow, n_dup = cached.rows, cached.service, cached.overflow, cached.n_duplicates
        from_cache = True
    else:
        # Fallbacks are known before IRSA is asked: with one in hand the search gets a shorter budget, so
        # the fallback still reaches a caller that stops waiting (the backend answers 504 after 30 s).
        snap = find_snapshot(ra, dec, radius, cols) if cached is None and allow_snapshot else None
        budget = search_budget(fallback=cached is not None or snap is not None)
        deadline = t0 + budget if budget > 0 else None
        if deadline_s is not None:  # the caller's own budget (0 or less: IRSA is not asked)
            cap = t0 + max(0.0, float(deadline_s))
            deadline = cap if deadline is None else min(deadline, cap)
        try:
            raw, service, overflow, errors, retries = _query_archive(ra, dec, radius, mjd_min, mjd_max, cols, deadline)
        except SearchError as e:
            if cached is not None:
                # IRSA is down: an expired answer beats no answer (new weeks may be missing).
                log.warning("IRSA unavailable; using a %.1f h old cached search (%s)", cached.age_s / 3600, e)
                rows, service, overflow, n_dup = cached.rows, cached.service, cached.overflow, cached.n_duplicates
            else:
                # Nothing cached: last resort, a committed snapshot whose disk holds this search.
                if snap is None:
                    raise
                rows, n_dup = snap.replay(ra, dec, radius, mjd_min, mjd_max, cols)
                service, overflow = "snapshot", False
                warn.append(snapshot_warning(snap))
                log.warning("%s (%s)", warn[-1], e)
            from_cache, stale, errors = True, True, [str(e)]
        else:
            rows, n_dup = dedupe_rows(raw)
            from_cache = False
            # Not cached: an empty answer (suspicious for an all-sky survey) and a truncated one
            # (the cache key has no MAXREC, and a bigger MAXREC must reach IRSA).
            if use_cache and rows and not overflow:
                _cache_write(key, rows, service, overflow, n_dup)
            if not rows:
                log.warning("No SPHEREx frames at (%.5f, %.5f) in %s", ra, dec, ", ".join(cols))

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
        retries=retries,
        stale=stale,
        warnings=warn,
    )


def search_budget(*, fallback: bool) -> float:
    """Seconds one search may spend on IRSA (0 = unbounded).

    ``settings.SEARCH_DEADLINE_S``, capped at ``settings.SEARCH_FALLBACK_DEADLINE_S`` when an expired cache
    entry or a committed snapshot can answer instead (``fallback=True``). A value of 0 switches either off.
    """
    limits = [settings.SEARCH_DEADLINE_S] + ([settings.SEARCH_FALLBACK_DEADLINE_S] if fallback else [])
    limits = [s for s in limits if s > 0]
    return min(limits) if limits else 0.0


def sia_budget(total_s: float) -> float:
    """Seconds SIA may use out of a search budget of ``total_s``: half of it (TAP, 8-19 s, gets the rest), but
    at least ``_SIA_MIN_S`` (10 s), or all of a shorter budget.

    SIA answers in 1-4 s (2.6-9.3 s on the afternoon of 2026-11-14, docs/DATA.md §3.0) and TAP in 8-19 s: on a
    short budget (a caller's ``deadline_s``) half of it made searches that SIA would have answered fail with a
    timeout, and the half kept for TAP was too short for TAP anyway (review 2026-11-15). TAP still gets every
    second that SIA leaves when SIA fails fast (an HTTP error)."""
    total_s = max(0.0, float(total_s))
    return max(total_s * _SIA_SHARE, min(total_s, _SIA_MIN_S))


def known_collections() -> frozenset[str]:
    """Collection names verified live (2026-11-14) plus whatever the settings configure."""
    return frozenset(settings.IRSA_COLLECTIONS) | frozenset(settings.IRSA_DEEP_COLLECTIONS) | _VERIFIED_COLLECTIONS


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
    """ADQL for the TAP fallback (``ADQL_FRAMES_AT_POSITION``).

    The column goes FIRST in INTERSECTS: IRSA TAP rejects ``INTERSECTS(CIRCLE(...), p.poly)`` at once with
    "Invalid or unsupported ADQL query string" (live 2026-11-14 19:25-19:44 and 20:05 UTC).
    ``INTERSECTS(p.poly, CIRCLE(...))`` is not rejected at parse time, but no answer has been seen end to end:
    it hung or got a 502 while the TAP spherex tables were down (2026-11-14 19:16-20:07 UTC). Unverified.
    """
    if radius_deg > MIN_RADIUS_DEG:
        region = f"INTERSECTS(p.poly, CIRCLE('ICRS', {ra:.8f}, {dec:.8f}, {radius_deg:.9g}))"
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


@dataclass(frozen=True)
class _Attempt:
    service: str  # 'sia' or 'tap'
    number: int  # 1-based attempt number of that service
    error: BaseException
    seconds: float


def _next_service(history: list[_Attempt], usable: set[str]) -> str | None:
    """SIA first and, after a fast SIA failure, SIA once more (it answers in 1-4 s, TAP in 8-19 s); then alternate.
    A timeout switches to the other service at once. With one usable service left, that one."""
    if not usable:
        return None
    if not history:
        want = "sia"
    elif len(history) == 1 and history[0].service == "sia" and not _is_timeout(history[0].error):
        want = "sia"
    else:
        want = "tap" if history[-1].service == "sia" else "sia"
    return want if want in usable else next(s for s in _SERVICES if s in usable)


def _backoff(n_failed: int, last: BaseException) -> float:
    """Pause before the next attempt: ``SEARCH_BACKOFF_S`` x 1, 2, 4, ... (at most ``_BACKOFF_MAX_S``) + up to 25 %
    jitter, and at least a ``Retry-After`` of up to 10 s. None after a timeout: that attempt already waited."""
    if _is_timeout(last):
        return 0.0
    base = min(settings.SEARCH_BACKOFF_S * 2 ** (n_failed - 1), _BACKOFF_MAX_S)
    delay = base + random.uniform(0.0, base / 4)
    retry_after = str(getattr(getattr(last, "response", None), "headers", {}).get("Retry-After", ""))
    if retry_after.isdigit():
        delay = max(delay, min(float(retry_after), 10.0))
    return delay


def _attempt_timeout(service: str, remaining: float | None) -> float:
    """Timeout of the next attempt: the service's own (SIA_TIMEOUT_S / TAP_TIMEOUT_S) capped by the time left; an SIA
    attempt by :func:`sia_budget` of it, so a hung SIA still leaves TAP (8-19 s) its turn."""
    limit = settings.SIA_TIMEOUT_S if service == "sia" else settings.TAP_TIMEOUT_S
    if remaining is None:
        return limit
    return min(limit, sia_budget(remaining) if service == "sia" else remaining)


def _query_archive(
    ra: float,
    dec: float,
    radius: float,
    mjd_min: float | None,
    mjd_max: float | None,
    cols: tuple[str, ...],
    deadline: float | None = None,
) -> tuple[list[ArchiveRow], str, bool, list[str], list[str]]:
    """Ask SIA and TAP until one answers, the attempts run out or ``deadline`` (``time.monotonic()``) comes.

    Returns (rows, service, overflow, errors, retries). ``retries`` describes every failed attempt before the
    answer; ``errors`` only the failed SIA attempts when the answer came from TAP (a real fallback), so a search
    that SIA answered on a retry is complete, not partial. Raises :class:`SearchError` with the whole attempt
    history when nothing answered.
    """
    t0 = time.monotonic()
    max_tries = max(1, settings.SEARCH_ATTEMPTS)
    tries = dict.fromkeys(_SERVICES, 0)
    timeouts = dict.fromkeys(_SERVICES, 0)
    usable = set(_SERVICES)
    history: list[_Attempt] = []
    errors: list[str] = []
    stopped = ""
    while True:
        service = _next_service(history, usable)
        delay = _backoff(len(history), history[-1].error) if history and service else 0.0
        now = time.monotonic()
        if service is not None and deadline is not None and now + delay + _MIN_ATTEMPT_S > deadline:
            stopped = f"{max(0.0, deadline - now):.1f} s left of the search budget"
            service = None
        if history:
            last = history[-1]
            if service:
                left = "" if deadline is None else f", {deadline - now:.1f} s left"
                plan = f"retrying {service.upper()} ({tries[service] + 1}/{max_tries}) in {delay:.1f} s{left}"
            else:
                plan = f"giving up ({stopped or 'no attempts left'})"
            log.warning(
                "%s attempt %d/%d failed after %.1f s: %s; %s",
                last.service.upper(),
                last.number,
                max_tries,
                last.seconds,
                _describe(last.error),
                plan,
            )
        if service is None:
            break
        if delay:
            time.sleep(delay)
        start = time.monotonic()
        timeout = _attempt_timeout(service, None if deadline is None else deadline - start)
        tries[service] += 1
        search = _search_sia if service == "sia" else _search_tap
        try:
            rows, overflow = search(ra, dec, radius, mjd_min, mjd_max, cols, start + timeout)
        except Exception as e:  # any failure (HTTP, timeout, parse) is recorded; only transport ones are retried
            history.append(_Attempt(service, tries[service], e, time.monotonic() - start))
            errors.append(f"{service} {tries[service]}/{max_tries}: {_describe(e)}")
            if _is_timeout(e):
                timeouts[service] += 1
            if not _is_retryable(e) or tries[service] >= max_tries or timeouts[service] >= _MAX_TIMEOUTS:
                usable.discard(service)
            continue
        if history:
            log.info(
                "%s answered on attempt %d/%d after %d failed attempt(s), %.1f s in all",
                service.upper(),
                tries[service],
                max_tries,
                len(history),
                time.monotonic() - t0,
            )
        fallback = [e for a, e in zip(history, errors, strict=True) if a.service == "sia"] if service == "tap" else []
        return rows, service, overflow, fallback, errors
    if not history:
        err = requests.Timeout(f"search deadline reached before querying IRSA ({stopped})")
        raise SearchError(f"IRSA frame search failed ({_describe(err)})", [err]) from err
    failures = [a.error for a in history]
    # A real timeout anywhere wins the cause chain (backend: 504), else the last error (502).
    cause = next((f for f in failures if _is_timeout(f)), failures[-1])
    detail = "; ".join(errors) + (f"; stopped: {stopped}" if stopped else "")
    elapsed = time.monotonic() - t0
    raise SearchError(
        f"IRSA frame search failed after {len(history)} attempt(s) in {elapsed:.1f} s ({detail})", failures
    ) from cause


def _search_sia(
    ra: float,
    dec: float,
    radius: float,
    mjd_min: float | None,
    mjd_max: float | None,
    cols: tuple[str, ...],
    deadline: float | None = None,
) -> tuple[list[ArchiveRow], bool]:
    """ONE SIA2 request (timeout ``SIA_TIMEOUT_S``, capped by ``deadline``); retries are :func:`_query_archive`'s."""
    params = sia_params(ra, dec, radius, mjd_min, mjd_max, cols)
    t0 = time.monotonic()
    resp = _request_once("GET", settings.IRSA_SIA, params=params, timeout=settings.SIA_TIMEOUT_S, deadline=deadline)
    rows, overflow = parse_sia_votable(resp.content)
    log.info("SIA: %d rows, %.0f KB in %.2f s", len(rows), len(resp.content) / 1024, time.monotonic() - t0)
    return rows, overflow


def _search_tap(
    ra: float,
    dec: float,
    radius: float,
    mjd_min: float | None,
    mjd_max: float | None,
    cols: tuple[str, ...],
    deadline: float | None = None,
) -> tuple[list[ArchiveRow], bool]:
    """ONE TAP sync query (timeout ``TAP_TIMEOUT_S``, capped by ``deadline``); returns (rows, overflow).

    Overflow = as many rows as MAXREC (TAP CSV has no status). Retries are :func:`_query_archive`'s."""
    query = build_query(ra, dec, radius_deg=radius, mjd_min=mjd_min, mjd_max=mjd_max, collections=cols)
    maxrec = settings.SIA_MAXREC
    data = {"REQUEST": "doQuery", "LANG": "ADQL", "FORMAT": "csv", "MAXREC": str(maxrec), "QUERY": query}
    t0 = time.monotonic()
    wait = -1 if deadline is None else max(0.0, deadline - t0 - _MIN_ATTEMPT_S)
    if not _TAP_LOCK.acquire(timeout=wait):
        raise requests.Timeout(f"waited {wait:.0f} s for another TAP query to finish")
    try:
        resp = _request_once(
            "POST", settings.IRSA_TAP_SYNC, data=data, timeout=settings.TAP_TIMEOUT_S, deadline=deadline
        )
    finally:
        _TAP_LOCK.release()
    rows = parse_tap_csv(resp.text)
    overflow = len(rows) >= maxrec
    if overflow:
        log.warning("TAP result has MAXREC=%d rows: probably truncated", maxrec)
    log.info("TAP: %d rows in %.2f s", len(rows), time.monotonic() - t0)
    return rows, overflow


def _request_once(
    method: str, url: str, *, params=None, data=None, timeout: float, deadline: float | None = None
) -> requests.Response:
    """One HTTP attempt whose timeout never outlives ``deadline``. Any HTTP status >= 400 raises
    ``requests.HTTPError`` (with ``.response``), so the caller can tell 5xx/429 (retried) from 4xx (not)."""
    if deadline is not None:
        timeout = min(timeout, deadline - time.monotonic())
        if timeout <= 0:
            raise requests.Timeout(f"search deadline reached before querying {url}")
    resp = _http(method, url, params=params, data=data, timeout=timeout)
    if resp.status_code >= 400:
        raise requests.HTTPError(f"HTTP {resp.status_code} from {url}", response=resp)
    return resp


def _http(method: str, url: str, *, params=None, data=None, timeout: float) -> requests.Response:
    """One HTTP attempt (tests replace this)."""
    return requests.request(method, url, params=params, data=data, timeout=timeout)


def _fetch(
    method: str, url: str, *, params=None, data=None, timeout: float, deadline: float | None = None
) -> requests.Response:
    """HTTP with retries and exponential backoff on 5xx/429, connection errors and timeouts.

    4xx is raised at once. A timeout is retried once at most (each one already cost ``timeout``
    seconds). The last transport error is re-raised as is, so ``requests.Timeout`` survives.
    ``deadline`` (a ``time.monotonic()`` value) caps every attempt's timeout and stops retrying when
    less than ``_MIN_ATTEMPT_S`` would be left; with no attempt made at all it raises ``requests.Timeout``.
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
            if deadline is not None and time.monotonic() + delay + _MIN_ATTEMPT_S > deadline:
                log.info("No time left to retry %s after %s", url, _describe(last))
                break
            log.info("Retry %d/%d of %s in %.1f s after %s", attempt + 1, attempts, url, delay, _describe(last))
            time.sleep(delay)
        attempt_timeout = timeout
        if deadline is not None:
            remaining = deadline - time.monotonic()
            if remaining < _MIN_ATTEMPT_S:
                break
            attempt_timeout = min(timeout, remaining)
        try:
            resp = _http(method, url, params=params, data=data, timeout=attempt_timeout)
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
    if last is None:
        raise requests.Timeout(f"search deadline reached before querying {url}")
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
        if not isinstance(doc, dict):
            raise ValueError(f"expected a JSON object, got {type(doc).__name__}")
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
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as e:
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
    ra %= 360.0
    if ra >= 360.0:  # float rounding: -1e-17 % 360.0 == 360.0, which SkyCoord rejects
        ra = 0.0
    return ra, dec, max(radius_deg, MIN_RADIUS_DEG), dets


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


# --------------------------------------------------------------------------- search snapshots (IRSA outage)

SNAPSHOT_KIND = "errante.search_snapshot"
SNAPSHOT_FORMAT = 1
"""Bump when the snapshot layout changes (files with another format are ignored, with a warning)."""
SNAPSHOT_COLUMNS = ("s3_key", "t_min", "t_max", "collection", "footprint")
SNAPSHOT_RADIUS_DEG = 0.1
"""Default snapshot disk: searches whose circle lies inside it are answered exactly from the footprints.
0.1 deg holds the 0.15 deg field box's inner circle and the J2000 (name-resolver) positions of the
high-proper-motion targets (Barnard's Star: 0.076 deg from its fields.toml centre)."""
SNAPSHOT_TILE_RADIUS_DEG = 0.055
"""Largest single SIA circle used to build a snapshot. 2026-11-14 (Barnard's Star): SIA answered circles of
0.001-0.085 deg in 3-5 s but hung on 0.1 deg (60 s and 300 s timeouts) and 0.25 deg, so wider disks are tiled."""
DEFAULT_SNAPSHOT_DIR = settings.REPO_ROOT / "data" / "index" / "search"
_SNAPSHOT_OFF = {"0", "off", "no", "none", "false"}
_SNAPSHOT_LOCK = threading.Lock()


def _snapshot_dir_from_env() -> Path | None:
    raw = os.environ.get("ERRANTE_SEARCH_SNAPSHOTS", "").strip()
    if raw.lower() in _SNAPSHOT_OFF:
        return None
    return Path(raw).resolve() if raw else DEFAULT_SNAPSHOT_DIR


SNAPSHOT_DIR: Path | None = _snapshot_dir_from_env()
"""Where the committed snapshots live (env ``ERRANTE_SEARCH_SNAPSHOTS``: a directory, or ``0`` to disable).
``None`` disables the snapshot fallback (offline tests and live checks set it)."""


@dataclass(frozen=True)
class SnapshotRow:
    """One snapshot frame: the ArchiveRow plus what an offline replay needs."""

    row: ArchiveRow
    t_min: float
    t_max: float
    footprint: tuple[float, ...]  # ra1, dec1, ra2, dec2, ... [deg]; great-circle edges, not closed


@dataclass(frozen=True)
class SearchSnapshot:
    """A committed IRSA answer around a showcase field (``data/index/search/<field-id>.json``)."""

    path: Path
    field_id: str
    name: str
    ra: float
    dec: float
    radius_deg: float
    collections: tuple[str, ...]
    service: str  # service that produced the snapshot ('sia')
    queried_utc: str
    rows: tuple[SnapshotRow, ...]

    def covers(self, ra: float, dec: float, radius_deg: float, collections: tuple[str, ...] | list[str]) -> bool:
        """True when the search circle lies inside the snapshot disk and every collection was snapshotted."""
        if not set(collections) <= set(self.collections):
            return False
        return angular_separation_deg(self.ra, self.dec, ra, dec) + radius_deg <= self.radius_deg + 1e-9

    def frames(
        self,
        ra: float,
        dec: float,
        radius_deg: float,
        mjd_min: float | None = None,
        mjd_max: float | None = None,
        collections: tuple[str, ...] | list[str] | None = None,
    ) -> list[ArchiveRow]:
        """Replay a search offline: footprint touches the circle and the exposure overlaps [mjd_min, mjd_max]."""
        return self.replay(ra, dec, radius_deg, mjd_min, mjd_max, collections)[0]

    def replay(
        self,
        ra: float,
        dec: float,
        radius_deg: float,
        mjd_min: float | None = None,
        mjd_max: float | None = None,
        collections: tuple[str, ...] | list[str] | None = None,
    ) -> tuple[list[ArchiveRow], int]:
        """:meth:`frames` plus the number of (obs_id, detector) duplicates dropped.

        The snapshot keeps every collection's row; like :func:`search_frames` the replay keeps one row per
        (obs_id, detector) (DR1 wins) AFTER the collection filter, so a search of one collection still sees
        that collection's rows, as live SIA does.
        """
        wanted = set(self.collections if collections is None else collections)
        lo = -math.inf if mjd_min is None else float(mjd_min)
        hi = math.inf if mjd_max is None else float(mjd_max)
        hits = [
            s.row
            for s in self.rows
            if s.row.collection in wanted
            and s.t_max >= lo
            and s.t_min <= hi
            and footprint_hits(s.footprint, ra, dec, radius_deg)
        ]
        return dedupe_rows(hits)


_SNAPSHOT_MEMO: dict[Path, tuple[tuple[int, int], SearchSnapshot | None]] = {}
_SNAPSHOT_DIRS_WARNED: set[Path] = set()  # missing snapshot directories already logged


def snapshot_path(field_id: str, directory: Path | None = None) -> Path:
    """``<directory>/<field-id>.json`` (default directory: ``SNAPSHOT_DIR`` or ``DEFAULT_SNAPSHOT_DIR``)."""
    if not re.fullmatch(r"[a-z0-9][a-z0-9_-]*", field_id):
        raise ValueError(f"Invalid field id for a snapshot file name: {field_id!r}")
    return (directory or SNAPSHOT_DIR or DEFAULT_SNAPSHOT_DIR) / f"{field_id}.json"


def snapshot_warning(snap: SearchSnapshot) -> str:
    return (
        f"IRSA unavailable: frames come from the committed search snapshot '{snap.field_id}' "
        f"({snap.service.upper()} answer of {snap.queried_utc}); frames published after that date are missing"
    )


def load_snapshot(path: Path) -> SearchSnapshot:
    """Read and validate one snapshot file (``ValueError`` when it is not a usable snapshot)."""
    try:
        doc = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise ValueError(f"unreadable snapshot {path}: {e}") from e
    if not isinstance(doc, dict) or doc.get("kind") != SNAPSHOT_KIND:
        raise ValueError(f"{path} is not a search snapshot")
    if doc.get("format") != SNAPSHOT_FORMAT:
        raise ValueError(f"{path}: snapshot format {doc.get('format')!r}, expected {SNAPSHOT_FORMAT}")
    if tuple(doc.get("columns", ())) != SNAPSHOT_COLUMNS:
        raise ValueError(f"{path}: columns {doc.get('columns')!r}, expected {list(SNAPSHOT_COLUMNS)}")
    try:
        listed = list(doc["collections"])
        cols = normalize_collections(listed)
        rows = []
        for rec in doc["rows"]:
            key, t_min, t_max, ci, footprint = rec
            if not (isinstance(ci, int) and 0 <= ci < len(listed)):
                raise ValueError(f"bad collection index in row {key}")
            row = _make_row(key, None, t_min, t_max, None, listed[ci])
            if row is None:
                raise ValueError(f"bad row {key}")
            fp = tuple(float(v) for v in footprint)
            if len(fp) < 6 or len(fp) % 2 or not all(math.isfinite(v) for v in fp):
                raise ValueError(f"bad footprint in row {key}")
            t_lo = row.ref.mjd if t_min is None else float(t_min)
            t_hi = row.ref.mjd if t_max is None else float(t_max)
            rows.append(SnapshotRow(row, t_lo, t_hi, fp))
        ra, dec = float(doc["center"]["ra"]), float(doc["center"]["dec"])
        radius = float(doc["radius_deg"])
        if not (0.0 <= ra < 360.0 and -90.0 <= dec <= 90.0 and 0.0 < radius <= 10.0):
            raise ValueError(f"bad centre/radius ({ra}, {dec}, {radius})")
        prov = doc["provenance"]
        return SearchSnapshot(
            path=Path(path),
            field_id=str(doc["field_id"]),
            name=str(doc.get("name", "")),
            ra=ra,
            dec=dec,
            radius_deg=radius,
            collections=cols,
            service=str(prov["service"]),
            queried_utc=str(prov["queried_utc"]),
            rows=tuple(rows),
        )
    except (KeyError, TypeError, ValueError, IndexError) as e:
        raise ValueError(f"invalid snapshot {path}: {e}") from e


def list_snapshots(directory: Path | None = None) -> list[SearchSnapshot]:
    """Every valid snapshot in ``directory`` (default ``SNAPSHOT_DIR``); invalid files are skipped with a warning.

    Parsed files are memoized by (mtime, size), so a long-running backend reads each file once.
    """
    directory = directory or SNAPSHOT_DIR
    if directory is None:  # switched off (ERRANTE_SEARCH_SNAPSHOTS=0, tests, live checks)
        return []
    if not directory.is_dir():
        # A deploy that does not ship data/index/search, or a non-editable install (REPO_ROOT elsewhere).
        with _SNAPSHOT_LOCK:
            first = directory not in _SNAPSHOT_DIRS_WARNED
            _SNAPSHOT_DIRS_WARNED.add(directory)
        if first:
            log.warning(
                "Search snapshot directory %s does not exist: the IRSA-outage fallback is off "
                "(ship data/index/search or set ERRANTE_SEARCH_SNAPSHOTS to its path; 0 silences this)",
                directory,
            )
        return []
    out: list[SearchSnapshot] = []
    for path in sorted(directory.glob("*.json")):
        try:
            st = path.stat()
        except OSError:
            continue
        stamp = (st.st_mtime_ns, st.st_size)
        with _SNAPSHOT_LOCK:
            memo = _SNAPSHOT_MEMO.get(path)
        if memo is not None and memo[0] == stamp:
            snap = memo[1]
        else:
            try:
                snap = load_snapshot(path)
            except ValueError as e:
                log.warning("Ignoring search snapshot: %s", e)
                snap = None
            with _SNAPSHOT_LOCK:
                _SNAPSHOT_MEMO[path] = (stamp, snap)
        if snap is not None:
            out.append(snap)
    return out


def find_snapshot(
    ra: float,
    dec: float,
    radius_deg: float,
    collections: tuple[str, ...] | list[str],
    directory: Path | None = None,
) -> SearchSnapshot | None:
    """The snapshot whose disk holds this search (closest centre first), or None. Never raises."""
    try:
        hits = [s for s in list_snapshots(directory) if s.covers(ra, dec, radius_deg, collections)]
    except Exception as e:  # a broken snapshot directory must not hide the IRSA error
        log.warning("Search snapshots unavailable: %s", _describe(e))
        return None
    if not hits:
        return None
    return min(hits, key=lambda s: (angular_separation_deg(s.ra, s.dec, ra, dec), s.field_id))


def fetch_snapshot(
    field_id: str,
    ra: float,
    dec: float,
    *,
    name: str = "",
    radius_deg: float = SNAPSHOT_RADIUS_DEG,
    collections: list[str] | tuple[str, ...] | str | None = None,
    rounds: int = 6,
    pause_s: float = 20.0,
    tile_radius_deg: float = SNAPSHOT_TILE_RADIUS_DEG,
) -> dict:
    """Query SIA live around a field and return a snapshot document (write it with :func:`write_snapshot`).

    SIA only: its ``s_region`` footprints make the offline replay exact. A disk wider than
    ``tile_radius_deg`` is covered by several SIA circles (:func:`snapshot_tiles`; IRSA hung on single
    circles of 0.1 deg), merged, and cut back to the frames whose footprint touches the disk. Each of
    ``rounds`` rounds already retries 5xx like any search, with ``pause_s`` between rounds. A truncated
    answer (MAXREC) raises :class:`SearchError`. The point search at the centre is also run live and
    compared with the replay of the snapshot (``provenance.point_check``).
    """
    snapshot_path(field_id)  # validates the id
    ra, dec, radius, _ = _validate(ra, dec, radius_deg, None, None, None)
    cols = normalize_collections(collections)
    tiles = snapshot_tiles(ra, dec, radius, tile_radius_deg)
    tile_radius = radius if len(tiles) == 1 else tile_radius_deg
    queries: list[dict] = []
    by_key: dict[str, ArchiveRow] = {}
    extra: dict[str, tuple[float | None, float | None, tuple[float, ...] | None]] = {}
    for t_ra, t_dec in tiles:
        params = sia_params(t_ra, t_dec, tile_radius, None, None, cols)
        content, queried, elapsed = _sia_patiently(params, rounds, pause_s)
        raw, overflow = parse_sia_votable(content)
        if overflow:
            raise SearchError(f"SIA answer truncated at MAXREC={settings.SIA_MAXREC}: not writing a partial snapshot")
        extra.update(_sia_snapshot_columns(content))
        by_key.update((r.ref.s3_key or "", r) for r in raw)
        queries.append(
            {
                "pos": dict(params)["POS"],
                "queried_utc": queried,
                "elapsed_s": round(elapsed, 2),
                "response_bytes": len(content),
                "rows": len(raw),
            }
        )
    # Every file is kept, also when one (obs_id, detector) is in two collections: the replay deduplicates
    # after its collection filter (SearchSnapshot.replay), so a one-collection search stays exact.
    kept = sorted(by_key.values(), key=lambda r: (r.ref.mjd, r.ref.detector, r.ref.obs_id, r.collection))
    records: list[list] = []
    used: list[ArchiveRow] = []
    n_no_footprint = n_outside = 0
    for r in kept:
        key = r.ref.s3_key or ""
        t_min, t_max, footprint = extra.get(key, (None, None, None))
        if r.ref.irsa_uri != f"{IRSA_DATA_PREFIX}{key}":
            raise SearchError(f"irsa_uri {r.ref.irsa_uri!r} is not '{IRSA_DATA_PREFIX}' + key: the snapshot would lie")
        if r.collection not in cols:
            raise SearchError(f"SIA returned collection {r.collection!r} outside the query {cols}")
        if footprint is None:
            n_no_footprint += 1
            continue
        if not footprint_hits(footprint, ra, dec, radius):  # reached by a tile beyond the disk only
            n_outside += 1
            continue
        records.append([key, t_min, t_max, cols.index(r.collection), list(footprint)])
        used.append(r)
    if n_no_footprint:
        log.warning("%d frames without a usable s_region left out of the snapshot", n_no_footprint)
    mjds = [r.ref.mjd for r in used]
    doc = {
        "kind": SNAPSHOT_KIND,
        "format": SNAPSHOT_FORMAT,
        "field_id": field_id,
        "name": name,
        "center": {"ra": round(ra, 8), "dec": round(dec, 8)},
        "radius_deg": radius,
        "collections": list(cols),
        "provenance": {
            "service": "sia",
            "url": settings.IRSA_SIA,
            "params": {"COLLECTION": list(cols), "RESPONSEFORMAT": "VOTABLE", "MAXREC": settings.SIA_MAXREC},
            "queries": queries,
            "queried_utc": queries[0]["queried_utc"],
            "elapsed_s": round(sum(q["elapsed_s"] for q in queries), 2),
            "rows_returned": sum(q["rows"] for q in queries),
            "distinct_files": len(by_key),
            "duplicate_rows": len(used) - len(dedupe_rows(used)[0]),
            "rows_without_footprint": n_no_footprint,
            "rows_outside_disk": n_outside,
            "rows": len(records),
            "rows_by_collection": dict(sorted(Counter(r.collection for r in used).items())),
            "rows_by_detector": {f"D{d}": n for d, n in sorted(Counter(r.ref.detector for r in used).items())},
            "mjd_range": [round(min(mjds), 6), round(max(mjds), 6)] if mjds else None,
            "point_check": None,
            "generator": "errante snapshot-search (errante.data.irsa.fetch_snapshot)",
            "use": (
                "Real IRSA SIA answer, one row per file (duplicate_rows: same obs_id + detector in two "
                "collections; a replay keeps one per (obs_id, detector) after its collection filter, DR1 first, "
                "like search_frames). Read only when SIA and TAP both fail and no cached search exists, for "
                "searches inside this disk; flagged service='snapshot', stale=True. Frames published after "
                "queried_utc are missing."
            ),
        },
        "columns": list(SNAPSHOT_COLUMNS),
        "column_notes": {
            "s3_key": "key in s3://nasa-irsa-spherex/; irsa_uri = 'ibe/data/spherex/' + key; obs_id, detector, "
            "release and pipeline version are parsed from it (errante.data.s3.parse_key)",
            "t_min": "exposure start [MJD] (SIA t_min)",
            "t_max": "exposure end [MJD] (SIA t_max); FrameRef.mjd = (t_min + t_max) / 2",
            "collection": "index into 'collections'",
            "footprint": "SIA s_region polygon: ra1, dec1, ra2, dec2, ... [deg ICRS, 6 decimals], closing "
            "vertex dropped; edges are great circles",
        },
        "rows": records,
    }
    doc["provenance"]["point_check"] = _point_check(records, ra, dec, cols, rounds, pause_s)
    return doc


def write_snapshot(doc: dict, path: Path) -> Path:
    """Write a snapshot document as JSON with one row per line (small, readable diffs); returns ``path``."""
    path = Path(path)
    head = {k: v for k, v in doc.items() if k != "rows"}
    text = json.dumps(head, indent=2, ensure_ascii=False)
    body = ",\n".join("    " + json.dumps(r, separators=(",", ":"), ensure_ascii=False) for r in doc["rows"])
    text = text[:-1].rstrip() + ',\n  "rows": [\n' + body + ("\n" if body else "") + "  ]\n}\n"
    json.loads(text)  # never write a file the loader cannot parse
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.{uuid.uuid4().hex}.part")
    tmp.write_text(text, encoding="utf-8", newline="\n")
    tmp.replace(path)
    return path


def snapshot_tiles(
    ra: float, dec: float, radius_deg: float, tile_radius_deg: float = SNAPSHOT_TILE_RADIUS_DEG
) -> list[tuple[float, float]]:
    """Centres of SIA circles of ``tile_radius_deg`` that together cover the disk of ``radius_deg``.

    Hexagonal lattice with spacing sqrt(3) * tile radius (every point of the plane is within one tile
    radius of a node), keeping the nodes whose circle reaches the disk: 7 tiles for 0.1 / 0.055 deg.
    Offsets are laid out in the tangent plane and moved onto the sphere along great circles.
    """
    if radius_deg <= tile_radius_deg:
        return [(ra, dec)]
    step = math.sqrt(3.0) * tile_radius_deg
    n = math.ceil((radius_deg + tile_radius_deg) / step) + 1
    nodes = []
    for j in range(-n, n + 1):
        for i in range(-n, n + 1):
            x, y = step * (i + j / 2.0), step * j * math.sqrt(3.0) / 2.0
            if math.hypot(x, y) <= radius_deg + tile_radius_deg:
                nodes.append((math.hypot(x, y), math.atan2(x, y)))
    out = []
    d0, a0 = math.radians(dec), math.radians(ra)
    for dist, bearing in sorted(nodes):
        delta = math.radians(dist)
        d = math.asin(math.sin(d0) * math.cos(delta) + math.cos(d0) * math.sin(delta) * math.cos(bearing))
        a = a0 + math.atan2(
            math.sin(bearing) * math.sin(delta) * math.cos(d0), math.cos(delta) - math.sin(d0) * math.sin(d)
        )
        out.append((round(math.degrees(a) % 360.0, 8), round(math.degrees(d), 8)))
    return out


def angular_separation_deg(ra1: float, dec1: float, ra2: float, dec2: float) -> float:
    """Great-circle distance [deg] (Vincenty formula: accurate at all separations)."""
    r1, d1, r2, d2 = (math.radians(v) for v in (ra1, dec1, ra2, dec2))
    dra = r2 - r1
    num = math.hypot(
        math.cos(d2) * math.sin(dra), math.cos(d1) * math.sin(d2) - math.sin(d1) * math.cos(d2) * math.cos(dra)
    )
    den = math.sin(d1) * math.sin(d2) + math.cos(d1) * math.cos(d2) * math.cos(dra)
    return math.degrees(math.atan2(num, den))


def footprint_hits(footprint: tuple[float, ...] | list[float], ra: float, dec: float, radius_deg: float = 0.0) -> bool:
    """True when a sky polygon (ra1, dec1, ra2, dec2, ...; great-circle edges) touches a circle around (ra, dec).

    Exact on the sphere: the gnomonic projection about (ra, dec) maps great circles to straight lines,
    and the angular distance to a projected point p is atan(|p|), so "inside, or an edge closer than the
    radius" is decided in the plane. Polygons reaching more than ~84 deg from the centre never match.
    """
    d0 = math.radians(dec)
    sin_d0, cos_d0 = math.sin(d0), math.cos(d0)
    pts: list[tuple[float, float]] = []
    for i in range(0, len(footprint) - 1, 2):
        d = math.radians(footprint[i + 1])
        dra = math.radians(footprint[i] - ra)
        cos_c = sin_d0 * math.sin(d) + cos_d0 * math.cos(d) * math.cos(dra)
        if cos_c < 0.1:
            return False
        x = math.cos(d) * math.sin(dra) / cos_c
        y = (cos_d0 * math.sin(d) - sin_d0 * math.cos(d) * math.cos(dra)) / cos_c
        pts.append((x, y))
    if len(pts) < 3:
        return False
    inside = False
    nearest2 = math.inf
    for (x1, y1), (x2, y2) in zip(pts, pts[1:] + pts[:1], strict=True):
        if (y1 > 0) != (y2 > 0) and x1 - y1 * (x2 - x1) / (y2 - y1) > 0:
            inside = not inside
        dx, dy = x2 - x1, y2 - y1
        length2 = dx * dx + dy * dy
        t = 0.0 if length2 == 0 else min(1.0, max(0.0, -(x1 * dx + y1 * dy) / length2))
        px, py = x1 + t * dx, y1 + t * dy
        nearest2 = min(nearest2, px * px + py * py)
    return inside or math.degrees(math.atan(math.sqrt(nearest2))) <= radius_deg


def parse_s_region(text) -> tuple[float, ...] | None:
    """'POLYGON ICRS ra1 dec1 ... ra1 dec1' -> (ra1, dec1, ...) rounded to 6 decimals, or None."""
    if not text:
        return None
    tokens = str(text).replace("(", " ").replace(")", " ").replace(",", " ").split()
    if not tokens or tokens[0].upper() != "POLYGON":
        return None
    nums: list[float] = []
    for tok in tokens[1:]:
        try:
            nums.append(float(tok))
        except ValueError:
            if nums:  # a word after the coordinates: not a simple polygon
                return None
    if len(nums) % 2 or not all(math.isfinite(v) for v in nums):
        return None
    if len(nums) >= 8 and nums[:2] == nums[-2:]:
        nums = nums[:-2]  # closing vertex
    if len(nums) < 6:
        return None
    return tuple(round(v, 6) for v in nums)


def _utc_now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _sia_patiently(params: list[tuple[str, str]], rounds: int, pause_s: float) -> tuple[bytes, str, float]:
    """(content, UTC start, seconds) of an SIA query, retried for ``rounds`` rounds on transport failures."""
    last: Exception | None = None
    for attempt in range(max(1, rounds)):
        if attempt:
            log.info("SIA round %d/%d in %.0f s after %s", attempt + 1, rounds, pause_s, _describe(last))
            time.sleep(pause_s)
        started, t0 = _utc_now(), time.monotonic()
        try:
            resp = _fetch("GET", settings.IRSA_SIA, params=params, timeout=settings.SIA_TIMEOUT_S)
        except requests.RequestException as e:
            if not _is_transport_failure(e):
                raise SearchError(f"SIA failed: {_describe(e)}", [e]) from e
            last = e
            continue
        return resp.content, started, time.monotonic() - t0
    raise SearchError(f"SIA unavailable after {max(1, rounds)} rounds: {_describe(last)}", [last]) from last


def _sia_snapshot_columns(content: bytes) -> dict[str, tuple[float | None, float | None, tuple[float, ...] | None]]:
    """S3 key -> (t_min, t_max, footprint) from an SIA2 VOTable: the columns ArchiveRow does not keep."""
    from astropy.io.votable import parse as parse_votable

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        vot = parse_votable(io.BytesIO(content), verify="ignore")
    tables = [t for r in vot.resources if r.type == "results" for t in r.tables] or list(vot.iter_tables())
    if not tables:
        return {}
    vt = tables[0]
    arr = vt.array
    by_name = {f.name.lower(): dtype_name for f, dtype_name in zip(vt.fields, arr.dtype.names, strict=True)}

    def column(name: str) -> list:
        key = by_name.get(name)
        return [None] * len(arr) if key is None else [_plain(v) for v in arr[key].tolist()]

    out: dict[str, tuple[float | None, float | None, tuple[float, ...] | None]] = {}
    for cloud, access_url, t_lo, t_hi, region in zip(
        column("cloud_access"), column("access_url"), column("t_min"), column("t_max"), column("s_region"), strict=True
    ):
        key = _key_from_cloud_access(cloud)
        if key is None and access_url:
            key = s3.irsa_uri_to_s3_key(_irsa_uri(access_url))
        if key:
            out[key] = (_float_or_none(t_lo), _float_or_none(t_hi), parse_s_region(region))
    return out


def _point_check(
    records: list[list], ra: float, dec: float, cols: tuple[str, ...], rounds: int, pause_s: float
) -> dict:
    """Live point search at the centre vs the offline replay of the snapshot rows: same (obs_id, detector) set?"""
    replay = set()
    for key, _t_min, _t_max, _ci, footprint in records:
        if footprint_hits(footprint, ra, dec, MIN_RADIUS_DEG):
            parsed = s3.parse_key(key)
            replay.add((parsed.obs_id, parsed.detector))
    try:
        content, queried, _ = _sia_patiently(sia_params(ra, dec, MIN_RADIUS_DEG, None, None, cols), rounds, pause_s)
        rows, overflow = parse_sia_votable(content)
    except SearchError as e:
        return {"radius_deg": MIN_RADIUS_DEG, "error": str(e), "rows_replayed": len(replay)}
    live = {(r.ref.obs_id, r.ref.detector) for r in dedupe_rows(rows)[0]}
    return {
        "radius_deg": MIN_RADIUS_DEG,
        "queried_utc": queried,
        "rows_live": len(live),
        "rows_replayed": len(replay),
        "overflow": overflow,
        "only_live": [f"{o}D{d}" for o, d in sorted(live - replay)][:20],
        "only_replayed": [f"{o}D{d}" for o, d in sorted(replay - live)][:20],
    }
