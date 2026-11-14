"""Server-side cutouts from IRSA (WS1, P0).

Instead of downloading 66 MB files, append ``?center=<ra>,<dec>&size=<s>`` to an
IRSA file URL and get a small multi-extension FITS with the same HDUs
(IMAGE/FLAGS/VARIANCE/ZODI/PSF/WCS-WAVE). Documented behaviour (verify!):
  center: degrees by default (units deg|rad|px)
  size:   degrees by default (px|arcsec|arcmin|deg|rad), e.g. size=5arcmin
  cutout partially off the detector -> clipped (may be non-square, NaN edges)
  no overlap -> HTTP 500; bad params -> HTTP 400
  ~1-15 s per cutout; IRSA throttles parallel requests (use <= 6-8 threads)
  orientation is the native detector one (NOT north-up) -> reproject (WS2)
"""

from __future__ import annotations

from pathlib import Path

from .. import settings
from ..models import FrameRef


def cutout_url(irsa_uri: str, ra: float, dec: float, size_arcmin: float) -> str:
    base = irsa_uri if irsa_uri.startswith("http") else f"{settings.IRSA_BASE}/{irsa_uri.lstrip('/')}"
    return f"{base}?center={ra:.7f},{dec:.7f}&size={size_arcmin:g}arcmin"


def fetch_cutout(frame: FrameRef, ra: float, dec: float, size_arcmin: float, out_dir: Path | None = None) -> Path:
    """Download one cutout (cached). Returns the local FITS path.

    TODO(WS1): use ``data.cache.cached_download(cutout_url(...))``; retry 3x with
    backoff on 5xx/timeouts; raise a clear error on HTTP 500 (no overlap).
    """
    raise NotImplementedError("WS1: fetch_cutout")


def fetch_cutouts(frames: list[FrameRef], ra: float, dec: float, size_arcmin: float) -> list[Path]:
    """Parallel version (ThreadPoolExecutor(settings.MAX_PARALLEL_DOWNLOADS)).

    TODO(WS1): skip-and-report failures instead of crashing the whole build.
    """
    raise NotImplementedError("WS1: fetch_cutouts")
