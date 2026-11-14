"""Job admission, deduplication and query service (E1).

The service is the only entry point for submitting and querying jobs.
The supervisor uses it to claim work; callers use it to submit and poll.
"""

from __future__ import annotations

import os
import shutil
from dataclasses import replace
from pathlib import Path

from .errors import DuplicateActive, InvalidRequest, QueueFull  # noqa: F401 (re-exported for callers)
from .repository import JobRepository, _new_id
from .types import Job, JobRequest, JobStatus


class JobService:
    """High-level job operations layered over ``JobRepository``."""

    def __init__(self, repo: JobRepository, products_dir: Path | None = None) -> None:
        self._repo = repo
        self._products_dir = products_dir
        self._max_bytes = int(os.environ.get("ERRANTE_JOBS_MAX_BYTES", str(2 * 1024**3)))
        if self._max_bytes <= 0:
            raise ValueError("ERRANTE_JOBS_MAX_BYTES must be positive")

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
            request = replace(
                request,
                pipeline_version=request.pipeline_version or __version__,
                schema_version=request.schema_version or SCHEMA_VERSION,
            )

        cache_key = request.cache_key()

        # Reutilisation: return a ready job if it's still fresh
        reusable = self._repo.find_reusable(cache_key)
        if reusable is not None and self._products_dir is not None:
            from ..publication import validate_product

            try:
                validate_product(self._products_dir, reusable.result_field_id or "")
            except (OSError, ValueError):
                self._repo.invalidate_ready(reusable.id)
                reusable = None
        if reusable is not None:
            return reusable, False

        # Repeated active work needs no new disk or queue capacity.
        active = self._repo.find_active(cache_key)
        if active is not None:
            return active, False
        if self._products_dir is not None:
            from .process import tree_bytes

            private = self._repo.db_path.parent
            usage = tree_bytes(private) + tree_bytes(self._products_dir)
            if usage >= self._max_bytes or shutil.disk_usage(private).free < 128 * 1024**2:
                raise QueueFull("Build storage budget is exhausted")

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
        job = self._repo.get(job_id)
        if job.status == JobStatus.ready and self._products_dir is not None:
            from ..publication import validate_product

            try:
                validate_product(self._products_dir, job.result_field_id or "")
            except (OSError, ValueError):
                self._repo.invalidate_ready(job.id)
                return self._repo.get(job_id)
        return job

    def list_jobs(self, status: str | None = None, limit: int = 50) -> list[Job]:
        return self._repo.list_jobs(status=status, limit=limit)

    def status_summary(self) -> dict[str, int]:
        """Count of jobs by status (useful for health/metrics)."""
        counts: dict[str, int] = {s.value: 0 for s in JobStatus}
        for job in self._repo.list_jobs(limit=1000):
            counts[job.status.value] = counts.get(job.status.value, 0) + 1
        return counts
