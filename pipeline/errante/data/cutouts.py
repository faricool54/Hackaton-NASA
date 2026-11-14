"""Server-side cutouts from IRSA IBE (WS1): the fallback path for pixels.

The fast path is :mod:`errante.data.s3range` (HTTP Range reads on the public S3
bucket). This module asks IRSA to cut the file instead: append
``?center=<ra>,<dec>&size=<s>arcmin`` to the IBE file URL and get a multi-extension
FITS with the same HDUs (IMAGE/FLAGS/VARIANCE/ZODI/EPSF/WCS-WAVE).

Verified live (2026-11-14, docs/DATA.md §3.0):
  * every cutout carries the WHOLE EPSF table: ~4 MB minimum even for a 5' box,
    4-15 s each; FLAGS comes back as a plain int32 image (not compressed);
  * box: n = round(size / pixel_scale) pixels per axis, first pixel
    ceil(x_center - n/2) (0-based), clipped to the detector (non-square at edges);
    CRPIXn of the primary WCS and of the alternates 'A' and 'W' are shifted by the
    offset; no LTV1/LTV2 keywords are written;
  * no overlap with the detector -> HTTP 422 ("Arrays do not overlap.");
  * transient HTTP 502/503 ("Server busy", Retry-After: 5) under load: retry;
  * orientation is the native detector one (NOT north-up) -> reproject (WS2);
  * IRSA throttles parallel requests: keep <= settings.MAX_PARALLEL_DOWNLOADS threads.
"""

from __future__ import annotations

import shutil
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests

from .. import settings
from ..models import FrameRef
from . import cache

IBE_PREFIX = "ibe/data/spherex/"
CUTOUT_RETRIES = 5
"""Attempts per cutout; ``cache.cached_download`` backs off 1, 2, 4, 8 s between them."""


class NoOverlap(ValueError):
    """The requested box does not overlap the detector (IBE answers HTTP 422)."""


class FetchError(RuntimeError):
    """Some frames failed. Carries what succeeded and what did not, in input order.

    ``results``: list of (FrameRef, Path) that worked; ``failures``: list of (FrameRef, reason).
    """

    def __init__(self, results: list[tuple[FrameRef, Path]], failures: list[tuple[FrameRef, str]]):
        self.results = results
        self.failures = failures
        first = failures[0][1] if failures else ""
        super().__init__(f"{len(failures)} of {len(results) + len(failures)} frames failed (first: {first})")


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


def fetch_cutout(frame: FrameRef, ra: float, dec: float, size_arcmin: float, out_dir: Path | None = None) -> Path:
    """Download one IBE cutout (cached in settings.CACHE_DIR) and return the local FITS path.

    Raises :class:`NoOverlap` on HTTP 422, ``requests.HTTPError`` on other 4xx and
    ``RuntimeError`` once the retries for 5xx/timeouts are exhausted. With ``out_dir``
    the cached file is also copied there under a readable name.
    """
    url = cutout_url(frame_irsa_uri(frame), ra, dec, size_arcmin)
    try:
        path = cache.cached_download(url, suffix=".fits", retries=CUTOUT_RETRIES)
    except requests.HTTPError as e:
        if e.response is not None and e.response.status_code == 422:
            raise NoOverlap(f"no overlap with {frame.obs_id}D{frame.detector} at ({ra}, {dec})") from e
        raise
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
        shutil.copyfile(path, dest)
    return dest


def fetch_report(
    fetch_one: Callable[[FrameRef], Path], frames: list[FrameRef], max_workers: int
) -> tuple[list[tuple[FrameRef, Path]], list[tuple[FrameRef, str]]]:
    """Run ``fetch_one`` over ``frames`` in a thread pool, never aborting on one failure.

    Returns (results, failures), both in input order; every frame lands in exactly one list.
    """
    if not frames:
        return [], []
    with ThreadPoolExecutor(max_workers=max(1, min(max_workers, len(frames)))) as pool:
        futures = [pool.submit(fetch_one, f) for f in frames]
        results: list[tuple[FrameRef, Path]] = []
        failures: list[tuple[FrameRef, str]] = []
        for frame, fut in zip(frames, futures, strict=True):
            try:
                results.append((frame, fut.result()))
            except Exception as e:  # noqa: BLE001  (reported to the caller, never swallowed)
                failures.append((frame, f"{type(e).__name__}: {e}"))
    return results, failures


def fetch_cutouts_report(
    frames: list[FrameRef], ra: float, dec: float, size_arcmin: float, max_workers: int | None = None
) -> tuple[list[tuple[FrameRef, Path]], list[tuple[FrameRef, str]]]:
    """Fetch every cutout; return ([(frame, path)], [(frame, reason)]) without raising (for WS2)."""
    return fetch_report(
        lambda f: fetch_cutout(f, ra, dec, size_arcmin),
        frames,
        max_workers or settings.MAX_PARALLEL_DOWNLOADS,
    )


def fetch_cutouts(frames: list[FrameRef], ra: float, dec: float, size_arcmin: float) -> list[Path]:
    """Parallel :func:`fetch_cutout`; returns paths aligned 1:1 with ``frames``.

    If any frame fails, raises :class:`FetchError` with the partial results and the
    failures, so the caller can never zip misaligned ``frames`` and ``paths``.
    """
    results, failures = fetch_cutouts_report(frames, ra, dec, size_arcmin)
    if failures:
        raise FetchError(results, failures)
    return [p for _, p in results]
