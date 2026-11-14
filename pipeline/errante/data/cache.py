"""Tiny disk cache for downloads and query results (WS1).

Everything lives under settings.CACHE_DIR (git-ignored). Keyed by SHA-256 of
the URL so re-running a build never re-downloads.
"""

from __future__ import annotations

import hashlib
import time
from pathlib import Path

import requests

from .. import settings


def cache_path(url: str, suffix: str = "") -> Path:
    h = hashlib.sha256(url.encode()).hexdigest()[:24]
    return settings.CACHE_DIR / h[:2] / f"{h}{suffix}"


def cached_download(url: str, suffix: str = ".fits", retries: int = 3, timeout: float | None = None) -> Path:
    """GET ``url`` into the cache (atomic write) and return the local path."""
    dest = cache_path(url, suffix)
    if dest.exists() and dest.stat().st_size > 0:
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    last: Exception | None = None
    for attempt in range(retries):
        try:
            with requests.get(url, stream=True, timeout=timeout or settings.HTTP_TIMEOUT_S) as r:
                r.raise_for_status()
                tmp = dest.with_suffix(dest.suffix + ".part")
                with open(tmp, "wb") as fh:
                    for chunk in r.iter_content(1 << 20):
                        fh.write(chunk)
                tmp.replace(dest)
                return dest
        except requests.HTTPError as e:  # 4xx won't fix itself
            if e.response is not None and e.response.status_code < 500:
                raise
            last = e
        except (requests.ConnectionError, requests.Timeout) as e:
            last = e
        time.sleep(2**attempt)
    raise RuntimeError(f"Download failed after {retries} attempts: {url}") from last
