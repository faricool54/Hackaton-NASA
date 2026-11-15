from __future__ import annotations

import json
import math
import os
from dataclasses import dataclass, field
from pathlib import Path

from errante import settings as core


def has_real_fields(root: Path) -> bool:
    """True if <root>/manifest.json lists at least one field (a systems-only manifest doesn't count)."""
    try:
        manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
        return bool(manifest.get("fields"))
    except (OSError, ValueError):
        return False


@dataclass
class Settings:
    data_dir: Path
    cors_origins: list[str] = field(default_factory=lambda: ["*"])
    live_cache_dir: Path = field(default_factory=lambda: core.CACHE_DIR / "api")
    live_timeout_s: float = 30
    live_cache_ttl_s: float = 300
    live_max_concurrent: int = 2
    live_cache_entries: int = 128
    enable_jobs: bool = False
    web_dir: Path | None = None
    jobs_dir: Path = field(default_factory=lambda: core.CACHE_DIR / "jobs")
    # GET /api/object (catalog context): None = derived from live_timeout_s (see ObjectService)
    object_deadline_s: float | None = None
    object_service_timeout_s: float | None = None
    object_max_concurrent: int = 4
    context_cache_dir: Path = field(default_factory=lambda: core.CACHE_DIR / "context")

    def __post_init__(self) -> None:
        self.data_dir = Path(self.data_dir).resolve()
        if self.web_dir is not None:
            self.web_dir = Path(self.web_dir).resolve()
        self.live_cache_dir = Path(self.live_cache_dir).resolve()
        self.jobs_dir = Path(self.jobs_dir).resolve()
        self.context_cache_dir = Path(self.context_cache_dir).resolve()
        if self.live_cache_dir.is_relative_to(self.data_dir):
            raise ValueError("API cache must be outside the public data directory")
        if self.context_cache_dir.is_relative_to(self.data_dir):
            raise ValueError("Catalog context cache must be outside the public data directory")
        if self.enable_jobs and self.jobs_dir.is_relative_to(self.data_dir):
            raise ValueError("Job state must be outside the public data directory")
        self.cors_origins = [origin.strip() for origin in self.cors_origins if origin.strip()]
        for value in (self.live_timeout_s, self.live_cache_ttl_s):
            if not math.isfinite(value) or value <= 0:
                raise ValueError("Live timeout and cache TTL must be finite and positive")
        if self.live_max_concurrent < 1 or self.live_cache_entries < 1 or self.object_max_concurrent < 1:
            raise ValueError("Live concurrency and cache capacity must be positive")
        for value in (self.object_deadline_s, self.object_service_timeout_s):
            if value is not None and (not math.isfinite(value) or value <= 0):
                raise ValueError("Object context deadline and service timeout must be finite and positive")

    @classmethod
    def from_env(cls) -> Settings:
        """ERRANTE_DATA_DIR wins; else real products if they have fields; else the synthetic demo."""
        enabled = os.environ.get("ERRANTE_ENABLE_JOBS", "").lower() in ("1", "true", "yes")
        if os.environ.get("ERRANTE_DATA_DIR"):
            data_dir = Path(os.environ["ERRANTE_DATA_DIR"]).resolve()
        elif enabled or has_real_fields(core.PRODUCTS_DIR):
            data_dir = core.PRODUCTS_DIR
        else:
            data_dir = core.DEMO_DIR
        origins = os.environ.get("ERRANTE_CORS_ORIGINS", "*").split(",")
        return cls(
            data_dir=data_dir,
            cors_origins=origins,
            live_cache_dir=Path(os.environ.get("ERRANTE_API_CACHE_DIR", core.CACHE_DIR / "api")),
            live_timeout_s=float(os.environ.get("ERRANTE_API_TIMEOUT_S", "30")),
            live_cache_ttl_s=float(os.environ.get("ERRANTE_API_CACHE_TTL_S", "300")),
            live_max_concurrent=int(os.environ.get("ERRANTE_API_MAX_CONCURRENT", "2")),
            live_cache_entries=int(os.environ.get("ERRANTE_API_CACHE_ENTRIES", "128")),
            enable_jobs=enabled,
            web_dir=Path(os.environ["ERRANTE_WEB_DIR"]) if os.environ.get("ERRANTE_WEB_DIR") else None,
            jobs_dir=Path(os.environ.get("ERRANTE_JOBS_DIR", core.CACHE_DIR / "jobs")),
            object_deadline_s=_optional_float("ERRANTE_OBJECT_DEADLINE_S"),
            object_service_timeout_s=_optional_float("ERRANTE_OBJECT_SERVICE_TIMEOUT_S"),
            object_max_concurrent=int(os.environ.get("ERRANTE_OBJECT_MAX_CONCURRENT", "4")),
            context_cache_dir=Path(os.environ.get("ERRANTE_CONTEXT_CACHE_DIR", core.CACHE_DIR / "context")),
        )


def _optional_float(name: str) -> float | None:
    value = os.environ.get(name, "").strip()
    return float(value) if value else None
