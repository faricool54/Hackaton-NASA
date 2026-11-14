"""Job engine top-level: wiring supervisor + service into the FastAPI app.

Usage (programmatic, E4):

    from errante_api.jobs.engine import JobEngine

    engine = JobEngine.from_env()
    engine.start()       # idempotent; raises if already started
    ...
    engine.stop()

The engine is started/stopped via FastAPI lifespan events in main.py.
It can also be run standalone (without FastAPI) for local testing:

    python -m errante_api.jobs.engine --enqueue 269.4463 4.7665
    python -m errante_api.jobs.engine --status <job_id>
    python -m errante_api.jobs.engine --list
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

from .repository import JobRepository
from .service import JobService
from .supervisor import Supervisor
from .types import JobRequest

log = logging.getLogger(__name__)

_DEFAULT_JOBS_DIR = Path(os.environ.get("ERRANTE_JOBS_DIR", "data/cache/jobs"))
_DEFAULT_PRODUCTS_DIR = Path(os.environ.get("ERRANTE_PRODUCTS_DIR", "data/products"))


class JobEngine:
    """Owns the repository, service and supervisor; single instance per process."""

    def __init__(self, jobs_dir: Path, products_dir: Path) -> None:
        self._jobs_dir = jobs_dir.resolve()
        self._products_dir = products_dir.resolve()
        db_path = self._jobs_dir / "jobs.db"
        self._repo = JobRepository(db_path)
        self._service = JobService(self._repo)
        self._supervisor = Supervisor(
            repo=self._repo,
            jobs_dir=self._jobs_dir,
            products_dir=self._products_dir,
        )
        self._started = False

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    @classmethod
    def from_env(cls) -> JobEngine:
        """Build from environment variables (or repo defaults)."""
        from errante import settings as core

        jobs_dir = Path(os.environ.get("ERRANTE_JOBS_DIR", str(core.CACHE_DIR / "jobs")))
        products_dir = Path(os.environ.get("ERRANTE_PRODUCTS_DIR", str(core.PRODUCTS_DIR)))
        return cls(jobs_dir=jobs_dir, products_dir=products_dir)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Start the supervisor.  Idempotent: no-op if already running."""
        if self._started and self._supervisor.is_running:
            return
        self._supervisor.start()
        self._started = True
        log.info("job engine started (jobs_dir=%s)", self._jobs_dir)

    def stop(self, timeout: float = 15.0) -> None:
        self._supervisor.stop(timeout=timeout)
        self._started = False

    @property
    def service(self) -> JobService:
        return self._service

    @property
    def is_running(self) -> bool:
        return self._supervisor.is_running


# ------------------------------------------------------------------
# Standalone CLI tool (E4: internal enqueue/query without HTTP)
# ------------------------------------------------------------------


def _cli() -> None:
    import argparse
    import json
    import sys

    parser = argparse.ArgumentParser(
        prog="python -m errante_api.jobs.engine",
        description="Internal job engine CLI (WS4-5 development tool)",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    enq = sub.add_parser("enqueue", help="Submit a build job")
    enq.add_argument("ra", type=float)
    enq.add_argument("dec", type=float)
    enq.add_argument("--size-deg", type=float, default=0.25)
    enq.add_argument("--max-frames", type=int, default=40)

    sub.add_parser("list", help="List recent jobs")

    status_p = sub.add_parser("status", help="Query a specific job")
    status_p.add_argument("job_id")

    args = parser.parse_args()
    engine = JobEngine.from_env()

    if args.cmd == "enqueue":
        try:
            req = JobRequest.create(
                ra=args.ra,
                dec=args.dec,
                size_deg=args.size_deg,
                max_frames=args.max_frames,
            )
        except Exception as exc:
            print(f"Invalid request: {exc}", file=sys.stderr)
            sys.exit(1)
        job, created = engine.service.submit(req)
        action = "created" if created else "reused"
        print(json.dumps({"id": job.id, "status": job.status.value, "action": action}, indent=2))

    elif args.cmd == "list":
        jobs = engine.service.list_jobs(limit=20)
        for j in jobs:
            print(f"{j.id[:12]}  {j.status.value:20s}  {j.stage:12s}  {j.created_at.isoformat()[:19]}")

    elif args.cmd == "status":
        try:
            job = engine.service.get(args.job_id)
        except Exception as exc:
            print(f"Not found: {exc}", file=sys.stderr)
            sys.exit(1)
        print(
            json.dumps(
                {
                    "id": job.id,
                    "status": job.status.value,
                    "stage": job.stage,
                    "attempt": job.attempt,
                    "result_field_id": job.result_field_id,
                    "error_detail": job.error_detail,
                    "created_at": job.created_at.isoformat(),
                    "updated_at": job.updated_at.isoformat(),
                },
                indent=2,
            )
        )


if __name__ == "__main__":
    _cli()
