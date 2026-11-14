"""HTTP endpoints for the job engine (WS4-5).

POST /api/jobs            Submit a build request (RA/Dec → field)
GET  /api/jobs/{id}       Poll job status

The job engine must be enabled via ERRANTE_ENABLE_JOBS=1.  When disabled
(default) both endpoints return 503 with a clear message.

Job lifecycle (public subset of JobStatus):
  queued      → accepted, waiting for a worker slot
  running     → pipeline is executing
  ready       → field published; result_field_id is set
  failed      → pipeline error; error_detail is set
  no_coverage → no SPHEREx frames found at the requested position
  pipeline_not_ready → WS1/WS2 stubs not yet implemented

The internal "publishing" state is collapsed to "running" in responses.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, HTTPException, Path, Request
from pydantic import BaseModel, Field

from ..jobs.errors import InvalidRequest, JobNotFound, QueueFull
from ..jobs.types import Job, JobRequest, JobStatus

router = APIRouter(tags=["jobs"])

# Public status values (publishing is an internal transition)
_PUBLIC_STATUS = {
    JobStatus.queued: "queued",
    JobStatus.running: "running",
    JobStatus.publishing: "running",  # collapse to running
    JobStatus.ready: "ready",
    JobStatus.failed: "failed",
    JobStatus.no_coverage: "no_coverage",
    JobStatus.pipeline_not_ready: "pipeline_not_ready",
}

PublicStatus = Literal["queued", "running", "ready", "failed", "no_coverage", "pipeline_not_ready"]


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------


class JobSubmitRequest(BaseModel):
    """Body for POST /api/jobs."""

    ra: float = Field(..., description="Right ascension (ICRS degrees, [0, 360))")
    dec: float = Field(..., description="Declination (ICRS degrees, [-90, 90])")
    size_deg: float = Field(
        default=0.25,
        description="Field side length in degrees ([0.01, 0.5])",
    )
    detectors: list[int] = Field(
        default_factory=list,
        description="SPHEREx detector numbers to include (1–6); empty = all",
    )
    mjd_min: float | None = Field(default=None, description="Earliest frame epoch (MJD)")
    mjd_max: float | None = Field(default=None, description="Latest frame epoch (MJD)")
    max_frames: int = Field(
        default=40,
        description="Maximum number of frames to include ([2, 120])",
    )


class JobStatusResponse(BaseModel):
    """Response for both POST /api/jobs and GET /api/jobs/{id}."""

    id: str
    status: PublicStatus
    stage: str
    created_at: datetime
    updated_at: datetime
    # Set when status == "ready"
    result_field_id: str | None = None
    # Set when status == "failed"
    error_detail: str | None = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _engine(request: Request):
    """Return the JobEngine or raise 503 when not enabled."""
    engine = getattr(request.app.state, "job_engine", None)
    if engine is None:
        raise HTTPException(
            status_code=503,
            detail=("Job engine is disabled. Set ERRANTE_ENABLE_JOBS=1 to enable background builds."),
        )
    return engine


def _job_to_response(job: Job) -> JobStatusResponse:
    return JobStatusResponse(
        id=job.id,
        status=_PUBLIC_STATUS[job.status],  # type: ignore[arg-type]
        stage=job.stage,
        created_at=job.created_at,
        updated_at=job.updated_at,
        result_field_id=job.result_field_id,
        error_detail=(
            "No SPHEREx coverage for these parameters."
            if job.status == JobStatus.no_coverage
            else "The requested pipeline capability is unavailable."
            if job.status == JobStatus.pipeline_not_ready
            else "The build failed. Retry later or change the request."
            if job.error_detail
            else None
        ),
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/jobs", response_model=JobStatusResponse, status_code=202)
def submit_job(body: JobSubmitRequest, request: Request) -> JobStatusResponse:
    """Submit a build request for an arbitrary sky position.

    If an identical job is already active or recently completed, that job is
    returned instead of creating a new one (deduplication by cache key).

    - **202** – job accepted (or existing job returned).
    - **422** – invalid parameters (out-of-range RA/Dec, bad FOV, etc.).
    - **503** – job engine disabled (start the server with ERRANTE_ENABLE_JOBS=1).
    - **429** – queue full; retry after a moment.
    """
    engine = _engine(request)
    try:
        req = JobRequest.create(
            ra=body.ra,
            dec=body.dec,
            size_deg=body.size_deg,
            detectors=body.detectors or None,
            mjd_min=body.mjd_min,
            mjd_max=body.mjd_max,
            max_frames=body.max_frames,
        )
    except InvalidRequest as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    try:
        job, _ = engine.service.submit(req)
    except QueueFull as exc:
        raise HTTPException(
            status_code=429,
            detail=f"Build queue is full: {exc}. Retry after a moment.",
            headers={"Retry-After": "2"},
        ) from exc
    except sqlite3.DatabaseError as exc:
        raise HTTPException(503, "Job storage is temporarily unavailable.", headers={"Retry-After": "2"}) from exc

    return _job_to_response(job)


@router.get("/jobs/{job_id}", response_model=JobStatusResponse)
def get_job(
    job_id: str = Path(min_length=1, description="Job ID returned by POST /api/jobs"),
    request: Request = ...,
) -> JobStatusResponse:
    """Poll the status of a submitted build job.

    - **200** – job found; check ``status`` field.
    - **404** – unknown job ID.
    - **503** – job engine disabled.
    """
    engine = _engine(request)
    try:
        job = engine.service.get(job_id)
    except JobNotFound as exc:
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id!r}") from exc
    except sqlite3.DatabaseError as exc:
        raise HTTPException(503, "Job storage is temporarily unavailable.", headers={"Retry-After": "2"}) from exc

    return _job_to_response(job)
