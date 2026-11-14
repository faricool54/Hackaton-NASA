"""Paths and external endpoints. Override any of them with environment variables."""

from __future__ import annotations

import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def _env_path(name: str, default: Path) -> Path:
    return Path(os.environ[name]).resolve() if os.environ.get(name) else default


# Where built products go (manifest.json + fields/<id>/...). Served by backend & frontend.
PRODUCTS_DIR = _env_path("ERRANTE_PRODUCTS_DIR", REPO_ROOT / "data" / "products")
# Synthetic demo products (committed, so the frontend works with no Python at all).
DEMO_DIR = _env_path("ERRANTE_DEMO_DIR", REPO_ROOT / "data" / "demo")
# Downloaded FITS/cutouts and query results. Never committed.
CACHE_DIR = _env_path("ERRANTE_CACHE_DIR", REPO_ROOT / "data" / "cache")

# --- SPHEREx archive (verified 2026-11-14, see docs/DATA.md) ---------------
S3_BUCKET = "nasa-irsa-spherex"
S3_HTTPS = f"https://{S3_BUCKET}.s3.us-east-1.amazonaws.com"
IRSA_BASE = "https://irsa.ipac.caltech.edu"
IRSA_TAP_SYNC = f"{IRSA_BASE}/TAP/sync"
IRSA_SIA = f"{IRSA_BASE}/SIA"


def _env_list(name: str, default: str) -> tuple[str, ...]:
    raw = os.environ.get(name) or default
    return tuple(item.strip() for item in raw.split(",") if item.strip())


# --- Frame search: errante.data.irsa.search_frames (verified 2026-11-14) ----
# SIA2/ObsCore collections searched by default. A misspelled collection returns an
# EMPTY result with no error, so only list names verified live (docs/DATA.md §3.0).
# Deep-field collections (spherex_dr1_deep, spherex_qr3_deep) are opt-in: near the
# ecliptic poles they return thousands of frames.
IRSA_COLLECTIONS = _env_list("ERRANTE_COLLECTIONS", "spherex_dr1,spherex_qr3")
IRSA_DEEP_COLLECTIONS = ("spherex_dr1_deep", "spherex_qr3_deep")
SIA_MAXREC = int(os.environ.get("ERRANTE_SIA_MAXREC", "50000"))
SIA_TIMEOUT_S = float(os.environ.get("ERRANTE_SIA_TIMEOUT_S", "30"))
TAP_TIMEOUT_S = float(os.environ.get("ERRANTE_TAP_TIMEOUT_S", "60"))
# Attempts per service on 5xx / connection errors (a timeout is retried once at most).
# IRSA answered ~50% of SIA requests with a fast (< 1 s) 502 on 2026-11-14, so retry a few times.
SEARCH_ATTEMPTS = int(os.environ.get("ERRANTE_SEARCH_ATTEMPTS", "4"))
SEARCH_BACKOFF_S = float(os.environ.get("ERRANTE_SEARCH_BACKOFF_S", "1"))
# Wall-clock budget of one search (SIA retries + TAP fallback): SIA gets at most half, TAP the rest.
# Without it a dead IRSA held a backend worker ~2-3 min. 0 disables it. The backend does NOT lower it
# to its own ERRANTE_API_TIMEOUT_S (30 s): a search with nothing to fall back on can still answer
# HTTP 504 while its worker runs on (TODO(WS4): keep ERRANTE_SEARCH_DEADLINE_S < ERRANTE_API_TIMEOUT_S).
SEARCH_DEADLINE_S = float(os.environ.get("ERRANTE_SEARCH_DEADLINE_S", "60"))
# Budget when the search can fall back on something (an expired cached answer, or a committed search
# snapshot covering the position): IRSA gets at most this long, so the fallback still reaches an API
# client before ERRANTE_API_TIMEOUT_S (30 s). 0 disables the cap (then SEARCH_DEADLINE_S alone).
SEARCH_FALLBACK_DEADLINE_S = float(os.environ.get("ERRANTE_SEARCH_FALLBACK_DEADLINE_S", "20"))
# Search results are cached as JSON in CACHE_DIR/queries/; 0 disables the cache. An expired
# entry is still served (flagged stale) when both SIA and TAP fail.
QUERY_CACHE_TTL_S = float(os.environ.get("ERRANTE_QUERY_CACHE_TTL_S", "86400"))

# --- Solar-system / catalog services (WS3) ----------------------------------
JPL_SBIDENT = "https://ssd-api.jpl.nasa.gov/sb_ident.api"
JPL_HORIZONS = "https://ssd.jpl.nasa.gov/api/horizons.api"
SKYBOT_CONESEARCH = "https://ssp.imcce.fr/webservices/skybot/api/conesearch.php"

HTTP_TIMEOUT_S = float(os.environ.get("ERRANTE_HTTP_TIMEOUT_S", "120"))
# IRSA throttles concurrent requests; keep this small (docs/DATA.md §Límites).
MAX_PARALLEL_DOWNLOADS = int(os.environ.get("ERRANTE_MAX_PARALLEL", "6"))
