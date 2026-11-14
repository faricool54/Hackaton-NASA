"""Internal types for the job engine.  NOT part of the public API contract.

These types are used exclusively within backend/errante_api/jobs/ and are
never added to models.py, shared/schema/, or frontend/src/api/types.ts.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any

# ---------------------------------------------------------------------------
# Job state machine
# ---------------------------------------------------------------------------


class JobStatus(str, Enum):  # noqa: UP042 — StrEnum requires Python 3.11+; keep for compatibility
    queued = "queued"
    running = "running"
    publishing = "publishing"  # internal; not exposed publicly
    ready = "ready"
    failed = "failed"
    no_coverage = "no_coverage"
    pipeline_not_ready = "pipeline_not_ready"


# ---------------------------------------------------------------------------
# Normalised request
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class JobRequest:
    """Validated and normalised build request.

    Coordinates are rounded to 6 decimal places (sub-arcsecond precision) to
    produce a stable cache key without changing the requested region.
    """

    ra: float  # ICRS degrees, [0, 360)
    dec: float  # ICRS degrees, [-90, 90]
    size_deg: float  # field side, [0.01, 0.5]
    detectors: tuple[int, ...] = ()  # sorted unique subset of 1-6; empty = all
    mjd_min: float | None = None
    mjd_max: float | None = None
    max_frames: int = 40
    # Pipeline/product versioning for cache key stability
    pipeline_version: str = ""
    schema_version: str = ""

    # --- construction helpers ------------------------------------------------

    @classmethod
    def create(
        cls,
        ra: float,
        dec: float,
        size_deg: float,
        detectors: list[int] | None = None,
        mjd_min: float | None = None,
        mjd_max: float | None = None,
        max_frames: int = 40,
        pipeline_version: str = "",
        schema_version: str = "",
    ) -> JobRequest:
        from .errors import InvalidRequest

        _check_finite(ra, "ra")
        _check_finite(dec, "dec")
        _check_finite(size_deg, "size_deg")
        if not (0 <= ra < 360):
            raise InvalidRequest(f"ra must be in [0, 360): {ra}")
        if not (-90 <= dec <= 90):
            raise InvalidRequest(f"dec must be in [-90, 90]: {dec}")
        if not (0.01 <= size_deg <= 0.5):
            raise InvalidRequest(f"size_deg must be in [0.01, 0.5]: {size_deg}")
        if not (2 <= max_frames <= 120):
            raise InvalidRequest(f"max_frames must be in [2, 120]: {max_frames}")
        dets: tuple[int, ...] = ()
        if detectors is not None:
            invalid = [d for d in detectors if d not in range(1, 7)]
            if invalid:
                raise InvalidRequest(f"invalid detector numbers: {invalid}")
            dets = tuple(sorted(set(detectors)))
        if mjd_min is not None:
            _check_finite(mjd_min, "mjd_min")
        if mjd_max is not None:
            _check_finite(mjd_max, "mjd_max")
        if mjd_min is not None and mjd_max is not None and mjd_min >= mjd_max:
            raise InvalidRequest("mjd_min must be < mjd_max")
        return cls(
            ra=round(ra, 6),
            dec=round(dec, 6),
            size_deg=round(size_deg, 6),
            detectors=dets,
            mjd_min=mjd_min,
            mjd_max=mjd_max,
            max_frames=max_frames,
            pipeline_version=pipeline_version,
            schema_version=schema_version,
        )

    def cache_key(self) -> str:
        """Stable SHA-256 hex digest over canonical JSON.

        Two requests with the same parameters always produce the same key.
        """
        doc: dict[str, Any] = {
            "ra": self.ra,
            "dec": self.dec,
            "size_deg": self.size_deg,
            "detectors": list(self.detectors),
            "mjd_min": self.mjd_min,
            "mjd_max": self.mjd_max,
            "max_frames": self.max_frames,
            "pipeline_version": self.pipeline_version,
            "schema_version": self.schema_version,
        }
        canonical = json.dumps(doc, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode()).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        return {
            "ra": self.ra,
            "dec": self.dec,
            "size_deg": self.size_deg,
            "detectors": list(self.detectors),
            "mjd_min": self.mjd_min,
            "mjd_max": self.mjd_max,
            "max_frames": self.max_frames,
            "pipeline_version": self.pipeline_version,
            "schema_version": self.schema_version,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> JobRequest:
        return cls(
            ra=d["ra"],
            dec=d["dec"],
            size_deg=d["size_deg"],
            detectors=tuple(d.get("detectors") or []),
            mjd_min=d.get("mjd_min"),
            mjd_max=d.get("mjd_max"),
            max_frames=d.get("max_frames", 40),
            pipeline_version=d.get("pipeline_version", ""),
            schema_version=d.get("schema_version", ""),
        )


# ---------------------------------------------------------------------------
# Job record (as stored in SQLite)
# ---------------------------------------------------------------------------


@dataclass
class Job:
    id: str  # opaque hex token
    cache_key: str
    params: dict[str, Any]  # JSON-serialisable copy of JobRequest
    status: JobStatus
    stage: str  # 'queued'/'build'/'validate'/'publish'
    created_at: datetime
    updated_at: datetime
    attempt: int = 0
    result_field_id: str | None = None
    error_detail: str | None = None
    reuse_until: datetime | None = None


# ---------------------------------------------------------------------------
# Attempt record
# ---------------------------------------------------------------------------


@dataclass
class Attempt:
    id: str  # unique token per attempt
    job_id: str
    generation: int
    started_at: datetime
    deadline_at: datetime
    heartbeat_at: datetime | None = None
    pid: int | None = None
    staging_dir: str | None = None
    result_path: str | None = None
    finished_at: datetime | None = None


# ---------------------------------------------------------------------------
# Child result (written by the child process, read by the supervisor)
# ---------------------------------------------------------------------------


@dataclass
class ChildResult:
    success: bool
    field_id: str | None = None  # set when success=True
    status: str = "failed"  # one of JobStatus values
    error: str | None = None
    stage: str | None = None  # stage at which failure happened


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _check_finite(value: float, name: str) -> None:
    from .errors import InvalidRequest

    if not math.isfinite(value):
        raise InvalidRequest(f"{name} must be finite: {value}")
