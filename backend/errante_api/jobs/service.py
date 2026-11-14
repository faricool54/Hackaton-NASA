"""Job admission, deduplication and query service (E1).

The service is the only entry point for submitting and querying jobs.
The supervisor uses it to claim work; callers use it to submit and poll.
"""

from __future__ import annotations

from .errors import DuplicateActive, InvalidRequest  # noqa: F401 (re-exported for callers)
from .repository import JobRepository, _new_id
from .types import Job, JobRequest, JobStatus


class JobService:
    """High-level job operations layered over ``JobRepository``."""

    def __init__(self, repo: JobRepository) -> None:
        self._repo = repo

    # ------------------------------------------------------------------
    # Submission
    # ------------------------------------------------------------------

    def submit(self, request: JobRequest) -> tuple[Job, bool]:
        """Submit a build request.

        Returns ``(job, created)`` where ``created=False`` means an identical
        active job already existed and was returned instead.

        Raises:
            QueueFull: if the queue is full and no reusable job exists.
            InvalidRequest: if the request parameters are invalid (should have
                been validated by ``JobRequest.create`` already).
        """
        from errante import __version__
        from errante.models import SCHEMA_VERSION

        # Attach pipeline/schema version to the request for cache-key stability
        if not request.pipeline_version or not request.schema_version:
            request = JobRequest(
                ra=request.ra,
                dec=request.dec,
                size_deg=request.size_deg,
                detectors=request.detectors,
                mjd_min=request.mjd_min,
                mjd_max=request.mjd_max,
                max_frames=request.max_frames,
                pipeline_version=request.pipeline_version or __version__,
                schema_version=request.schema_version or SCHEMA_VERSION,
            )

        cache_key = request.cache_key()

        # Reutilisation: return a ready job if it's still fresh
        reusable = self._repo.find_reusable(cache_key)
        if reusable is not None:
            return reusable, False

        try:
            job = self._repo.enqueue(
                job_id=_new_id(),
                cache_key=cache_key,
                params=request.to_dict(),
            )
            return job, True
        except DuplicateActive as exc:
            # Another concurrent submission beat us to it; return theirs
            existing = self._repo.get(exc.existing_job_id)
            return existing, False

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def get(self, job_id: str) -> Job:
        return self._repo.get(job_id)

    def list_jobs(self, status: str | None = None, limit: int = 50) -> list[Job]:
        return self._repo.list_jobs(status=status, limit=limit)

    def status_summary(self) -> dict[str, int]:
        """Count of jobs by status (useful for health/metrics)."""
        counts: dict[str, int] = {s.value: 0 for s in JobStatus}
        for job in self._repo.list_jobs(limit=1000):
            counts[job.status.value] = counts.get(job.status.value, 0) + 1
        return counts
