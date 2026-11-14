"""Pixels of each frame around a position (WS1): S3 Range patches first, IRSA IBE cutouts as fallback.

:func:`fetch_cutouts` is what ``build.py`` calls. For every frame it returns a small multi-extension FITS
(IMAGE/FLAGS/VARIANCE/ZODI/WCS-WAVE) that ``fits_io.read_spherex`` opens, or ``None`` if that frame could
not be fetched, so one bad frame never aborts a field:

  1. :mod:`errante.data.s3range` reads only the rows of the box from the public S3 bucket (HTTP Range):
     ~0.4-0.7 s and ~1.4 MB per 5' frame, bit-identical to an IBE cutout (verified live on D1-D6, dr1/qr3);
  2. if that fails for any reason other than "no overlap", the frame is asked to IRSA IBE instead
     (``?center=<ra>,<dec>&size=<s>arcmin`` on the file URL), which also returns the EPSF table.

``ERRANTE_PIXEL_SOURCE=ibe`` skips step 1 (e.g. if S3 is unreachable from a deploy host).

Verified live (2026-11-14, docs/DATA.md §3.0):
  * every cutout carries the WHOLE EPSF table: ~4 MB minimum even for a 5' box,
    4-15 s each; FLAGS comes back as a plain int32 image (not compressed);
  * box: n = round(size / pixel_scale) pixels per axis, first pixel
    ceil(x_center - n/2) (0-based), clipped to the detector (non-square at edges);
    CRPIXn of the primary WCS and of the alternates 'A' and 'W' are shifted by the
    offset; no LTV1/LTV2 keywords are written;
  * no overlap with the detector -> HTTP 422 ("Arrays do not overlap.");
  * transient HTTP 502/503 ("Server busy", Retry-After: 5) under load, and bodies cut
    mid-transfer (requests' ChunkedEncodingError): retry;
  * orientation is the native detector one (NOT north-up) -> reproject (WS2);
  * IRSA throttles parallel requests: keep <= settings.MAX_PARALLEL_DOWNLOADS threads.
"""

from __future__ import annotations

import logging
import os
import shutil
import threading
import time
import uuid
from collections.abc import Callable, Iterator
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from pathlib import Path

import requests

from .. import settings
from ..models import FrameRef
from . import cache

log = logging.getLogger(__name__)

IBE_PREFIX = "ibe/data/spherex/"
PIXEL_SOURCE = os.environ.get("ERRANTE_PIXEL_SOURCE", "s3").strip().lower()
"""'s3' (default): S3 Range patch, IBE cutout as per-frame fallback. 'ibe': IBE cutouts only."""
CUTOUT_RETRIES = 5
"""Attempts per cutout; ``cache.cached_download`` backs off 1, 2, 4, 8 s between them."""
BODY_RETRIES = 3
"""Attempts when the connection breaks mid-body (``cache.cached_download`` only retries
5xx and connection/timeout errors; a cut body surfaces as ChunkedEncodingError)."""
TRANSIENT_BODY_ERRORS = (requests.exceptions.ChunkedEncodingError, requests.exceptions.ContentDecodingError)
"""Raised by requests while reading a body the server cut short: transient, worth a retry."""


class KeyedLocks:
    """One lock per key, created on demand and dropped once nobody holds or waits on it.

    Used to run at most one fetch per URL / cache file at a time inside this process
    (duplicate frames in a batch, or a live request racing a build).
    """

    def __init__(self) -> None:
        self._guard = threading.Lock()
        self._locks: dict[object, list] = {}  # key -> [lock, holders + waiters]

    @contextmanager
    def hold(self, key: object) -> Iterator[None]:
        with self._guard:
            entry = self._locks.get(key)
            if entry is None:
                entry = self._locks[key] = [threading.Lock(), 0]
            entry[1] += 1
        try:
            with entry[0]:
                yield
        finally:
            with self._guard:
                entry[1] -= 1
                if entry[1] == 0:
                    del self._locks[key]


_url_locks = KeyedLocks()


class NoOverlap(ValueError):
    """The requested box does not overlap the detector (IBE answers HTTP 422)."""


def frame_irsa_uri(frame: FrameRef) -> str:
    """Relative IBE path of a frame ('ibe/data/spherex/<release>/level2/...')."""
    if frame.irsa_uri:
        return frame.irsa_uri
    if frame.s3_key:  # S3 key = IBE uri minus 'ibe/data/spherex/' (docs/DATA.md §3.0)
        return IBE_PREFIX + frame.s3_key.lstrip("/")
    raise ValueError(f"FrameRef {frame.obs_id}D{frame.detector} has neither irsa_uri nor s3_key")


def cutout_url(irsa_uri: str, ra: float, dec: float, size_arcmin: float) -> str:
    base = irsa_uri if irsa_uri.startswith("http") else f"{settings.IRSA_BASE}/{irsa_uri.lstrip('/')}"
    return f"{base}?center={ra:.7f},{dec:.7f}&size={size_arcmin:g}arcmin"


def _download(url: str, what: str) -> Path:
    """``cache.cached_download`` plus retries for bodies cut mid-transfer; 422 -> NoOverlap."""
    for attempt in range(BODY_RETRIES):
        try:
            return cache.cached_download(url, suffix=".fits", retries=CUTOUT_RETRIES)
        except requests.HTTPError as e:
            if e.response is not None and e.response.status_code == 422:
                raise NoOverlap(f"no overlap with {what}") from e
            raise
        except TRANSIENT_BODY_ERRORS as e:
            if attempt == BODY_RETRIES - 1:
                raise RuntimeError(f"IBE download kept breaking mid-transfer ({BODY_RETRIES} attempts): {url}") from e
            time.sleep(2**attempt)
    raise AssertionError("unreachable")


def _copy_atomic(src: Path, dest: Path) -> None:
    """Copy via a unique temp file + os.replace, so a partial copy is never left as ``dest``."""
    tmp = dest.with_name(f"{dest.name}.{uuid.uuid4().hex[:8]}.part")
    try:
        shutil.copyfile(src, tmp)
        os.replace(tmp, dest)
    except OSError:
        if not dest.exists():  # e.g. another process copied the same cutout and holds it open (Windows)
            raise
    finally:
        try:
            tmp.unlink(missing_ok=True)
        except OSError:
            pass


def fetch_cutout(frame: FrameRef, ra: float, dec: float, size_arcmin: float, out_dir: Path | None = None) -> Path:
    """Download one IBE cutout (cached in settings.CACHE_DIR) and return the local FITS path.

    Raises :class:`NoOverlap` on HTTP 422, ``requests.HTTPError`` on other 4xx and
    ``RuntimeError`` once the retries for 5xx/timeouts/cut bodies are exhausted. With
    ``out_dir`` the cached file is also copied there under a readable name. Concurrent
    calls for the same cutout download it once (``cache.cached_download`` writes a fixed
    ``.part`` name per URL, so two downloads of one URL must never overlap).
    """
    url = cutout_url(frame_irsa_uri(frame), ra, dec, size_arcmin)
    with _url_locks.hold(url):
        path = _download(url, f"{frame.obs_id}D{frame.detector} at ({ra}, {dec})")
        with open(path, "rb") as fh:
            magic = fh.read(9)
        if magic != b"SIMPLE  =":
            path.unlink(missing_ok=True)  # an HTML error page with status 200 must not poison the cache
            raise RuntimeError(f"IBE returned something that is not FITS for {url}")
        if out_dir is None:
            return path
        out_dir.mkdir(parents=True, exist_ok=True)
        stem = Path(frame_irsa_uri(frame)).stem
        dest = out_dir / f"{stem}_{ra:.5f}_{dec:+.5f}_{size_arcmin:g}am.fits"
        if not dest.exists():
            _copy_atomic(path, dest)
        return dest


def fetch_aligned(
    fetch_one: Callable[[FrameRef], Path], frames: list[FrameRef], max_workers: int
) -> tuple[list[Path | None], list[tuple[FrameRef, str]]]:
    """Run ``fetch_one`` over ``frames`` in a thread pool, never aborting on one failure.

    Returns (paths, failures): ``paths`` is aligned 1:1 with ``frames`` (``None`` where the frame failed) and
    ``failures`` lists (frame, "<ExceptionType>: <message>") in input order.
    """
    if not frames:
        return [], []
    paths: list[Path | None] = []
    failures: list[tuple[FrameRef, str]] = []
    with ThreadPoolExecutor(max_workers=max(1, min(max_workers, len(frames)))) as pool:
        futures = [pool.submit(fetch_one, f) for f in frames]
        for frame, fut in zip(frames, futures, strict=True):
            try:
                paths.append(fut.result())
            except Exception as e:  # noqa: BLE001  (reported to the caller, never swallowed)
                paths.append(None)
                failures.append((frame, f"{type(e).__name__}: {e}"))
    return paths, failures


def fetch_report(
    fetch_one: Callable[[FrameRef], Path], frames: list[FrameRef], max_workers: int
) -> tuple[list[tuple[FrameRef, Path]], list[tuple[FrameRef, str]]]:
    """Like :func:`fetch_aligned` but returns ([(frame, path)], [(frame, reason)]), both in input order."""
    paths, failures = fetch_aligned(fetch_one, frames, max_workers)
    return [(f, p) for f, p in zip(frames, paths, strict=True) if p is not None], failures


def fetch_cutouts_report(
    frames: list[FrameRef], ra: float, dec: float, size_arcmin: float, max_workers: int | None = None
) -> tuple[list[tuple[FrameRef, Path]], list[tuple[FrameRef, str]]]:
    """Fetch every cutout; return ([(frame, path)], [(frame, reason)]) without raising (for WS2)."""
    return fetch_report(
        lambda f: fetch_cutout(f, ra, dec, size_arcmin),
        frames,
        max_workers or settings.MAX_PARALLEL_DOWNLOADS,
    )


_ibe_slots = threading.BoundedSemaphore(max(1, settings.MAX_PARALLEL_DOWNLOADS))
"""IRSA throttles parallel requests: IBE fallbacks share these slots even inside the wider S3 pool."""


def fetch_frame(frame: FrameRef, ra: float, dec: float, size_arcmin: float) -> Path:
    """Best available pixels of one frame: S3 Range patch, else IBE cutout. Raises if both fail.

    :class:`NoOverlap` is raised as is (IBE would answer 422 for the same box). Any other S3 failure
    (network, missing key, unexpected layout) falls back to IBE; if that fails too the error names both.
    """
    if PIXEL_SOURCE == "ibe":
        with _ibe_slots:
            return fetch_cutout(frame, ra, dec, size_arcmin)
    from . import s3range  # lazy: s3range imports helpers from this module

    try:
        return s3range.fetch_patch(frame, ra, dec, size_arcmin)
    except NoOverlap:
        raise
    except Exception as s3_error:  # noqa: BLE001  (falls back, and is reported if the fallback fails too)
        log.info("S3 patch failed for %sD%s (%s); trying IBE", frame.obs_id, frame.detector, s3_error)
        try:
            with _ibe_slots:
                return fetch_cutout(frame, ra, dec, size_arcmin)
        except NoOverlap:
            raise
        except Exception as ibe_error:
            raise RuntimeError(
                f"S3: {type(s3_error).__name__}: {s3_error}; IBE: {type(ibe_error).__name__}: {ibe_error}"
            ) from ibe_error


def fetch_frames_report(
    frames: list[FrameRef], ra: float, dec: float, size_arcmin: float, max_workers: int | None = None
) -> tuple[list[Path | None], list[tuple[FrameRef, str]]]:
    """:func:`fetch_frame` for every frame in parallel: (paths aligned with ``frames``, [(frame, reason)])."""
    if PIXEL_SOURCE == "ibe":
        workers = max_workers or settings.MAX_PARALLEL_DOWNLOADS
    else:
        from .s3range import MAX_PARALLEL_S3

        workers = max_workers or MAX_PARALLEL_S3
    return fetch_aligned(lambda f: fetch_frame(f, ra, dec, size_arcmin), frames, workers)


def fetch_cutouts(frames: list[FrameRef], ra: float, dec: float, size_arcmin: float) -> list[Path | None]:
    """Pixels of every frame around (ra, dec): one path per frame, in order, ``None`` where it failed.

    This is the entry point of ``build.py``: the caller skips (and may replace) the ``None`` frames, so one
    missing or unreachable frame never aborts a field. Each failure is logged with its reason; use
    :func:`fetch_frames_report` to get the reasons programmatically.
    """
    paths, failures = fetch_frames_report(frames, ra, dec, size_arcmin)
    for frame, reason in failures:
        log.warning("no pixels for %sD%s: %s", frame.obs_id, frame.detector, reason)
    if failures:
        log.warning("fetch_cutouts: %d of %d frames failed", len(failures), len(frames))
    return paths
