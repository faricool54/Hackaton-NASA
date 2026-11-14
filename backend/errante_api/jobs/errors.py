"""Domain errors for the job engine."""

from __future__ import annotations


class JobEngineError(Exception):
    """Base class for all job-engine errors."""


class InvalidRequest(JobEngineError):
    """The caller supplied invalid parameters."""


class QueueFull(JobEngineError):
    """The job queue is at capacity; the caller should retry later."""


class JobNotFound(JobEngineError):
    """No job with the given ID exists in the repository."""


class DuplicateActive(JobEngineError):
    """A job with the same cache key is already active; returns its ID."""

    def __init__(self, existing_job_id: str) -> None:
        super().__init__(f"duplicate active job: {existing_job_id}")
        self.existing_job_id = existing_job_id


class PublicationError(JobEngineError):
    """Something went wrong while publishing the product."""


class ReconciliationRequired(JobEngineError):
    """The repository has unresolved in-progress records; must reconcile before claiming."""
