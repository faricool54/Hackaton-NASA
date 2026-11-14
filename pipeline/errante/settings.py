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

# --- Solar-system / catalog services (WS3) ----------------------------------
JPL_SBIDENT = "https://ssd-api.jpl.nasa.gov/sb_ident.api"
JPL_HORIZONS = "https://ssd.jpl.nasa.gov/api/horizons.api"
SKYBOT_CONESEARCH = "https://ssp.imcce.fr/webservices/skybot/api/conesearch.php"

HTTP_TIMEOUT_S = float(os.environ.get("ERRANTE_HTTP_TIMEOUT_S", "120"))
# IRSA throttles concurrent requests; keep this small (docs/DATA.md §Límites).
MAX_PARALLEL_DOWNLOADS = int(os.environ.get("ERRANTE_MAX_PARALLEL", "6"))
