"""Supervisor: runs in a dedicated thread, claims jobs and manages child processes.

Design (from INTERNAL_ENGINE_PLAN.md §6):
- One active build at a time (_MAX_ACTIVE = 1 in repository.py).
- Uses a cross-platform process group / Job Object to kill descendants too.
- Deadline enforced with a monotonic clock; UTC timestamps stored for audit.
- Graceful shutdown: stops claiming, waits for the active child, then exits.
- Exclusive start: a file lock prevents a second supervisor from starting on
  the same jobs directory.
"""

from __future__ import annotations

import json
import logging
import os
import sys
import threading
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

from .repository import JobRepository, _new_id
from .types import ChildResult, JobRequest

log = logging.getLogger(__name__)

_POLL_INTERVAL_S = 2.0
_DEADLINE_S = 900
_GRACE_S = 5
_LOG_MAX_BYTES = 5 * 1024 * 1024  # 5 MiB per attempt


class Supervisor:
    """Single-instance supervisor for the job queue.

    Usage::

        sup = Supervisor(repo, jobs_dir, products_dir)
        sup.start()   # starts background thread; raises if already running
        ...
        sup.stop()    # signals and waits
    """

    def __init__(
        self,
        repo: JobRepository,
        jobs_dir: Path,
        products_dir: Path,
        *,
        builder: _BuilderProtocol | None = None,
    ) -> None:
        self._repo = repo
        self._jobs_dir = jobs_dir
        self._products_dir = products_dir
        self._builder = builder  # injectable for tests
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._lock_path = jobs_dir / "supervisor.lock"
        self._lock_fd: int | None = None
        self._generation = 0

    # ------------------------------------------------------------------
    # Public lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Start the supervisor background thread.

        Raises RuntimeError if another supervisor is already running on the
        same jobs directory (detected via a file lock).
        """
        self._acquire_lock()
        self._stop_event.clear()
        self._repo.reconcile_interrupted()
        self._thread = threading.Thread(target=self._loop, name="errante-supervisor", daemon=True)
        self._thread.start()
        log.info("supervisor started (generation=%d)", self._generation)

    def stop(self, timeout: float = 15.0) -> None:
        """Signal the supervisor to stop and wait for the thread."""
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=timeout)
        self._release_lock()
        log.info("supervisor stopped")

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------

    def _loop(self) -> None:
        self._generation += 1
        while not self._stop_event.is_set():
            try:
                self._tick()
            except Exception:
                log.exception("supervisor tick error")
            self._stop_event.wait(timeout=_POLL_INTERVAL_S)

    def _tick(self) -> None:
        from .publication import publish_job

        attempt_id = _new_id()
        deadline_at = datetime.now(UTC) + timedelta(seconds=_DEADLINE_S)

        claimed = self._repo.claim_next(
            attempt_id=attempt_id,
            generation=self._generation,
            deadline_at=deadline_at,
        )
        if claimed is None:
            return

        job, attempt = claimed
        log.info("claimed job %s (attempt %s)", job.id, attempt_id)

        staging_dir = self._jobs_dir / "staging" / attempt_id
        staging_dir.mkdir(parents=True, exist_ok=True)

        request = JobRequest.from_dict(job.params)
        field_id = _field_id_for_job(job.id)
        request_path = staging_dir / "request.json"
        result_path = staging_dir / "result.json"

        request_payload = {
            "request": request.to_dict(),
            "staging_dir": str(staging_dir),
            "field_id": field_id,
        }
        request_path.write_text(json.dumps(request_payload), encoding="utf-8")

        success = False
        child_result: ChildResult | None = None

        try:
            proc = self._launch_child(request_path, result_path, staging_dir, attempt_id)
            if proc is None:
                # injected builder (tests) already wrote result
                child_result = _read_child_result(result_path)
                success = child_result.success
            else:
                self._repo.record_pid(attempt_id, proc.pid, str(staging_dir))

                # Wait with deadline
                mono_deadline = time.monotonic() + _DEADLINE_S
                timed_out = False
                while proc.poll() is None:
                    if time.monotonic() > mono_deadline or self._stop_event.is_set():
                        timed_out = True
                        break
                    self._repo.heartbeat(attempt_id)
                    time.sleep(1.0)

                if timed_out:
                    _kill_tree(proc)
                    proc.wait()
                    self._repo.finish_attempt(attempt_id)
                    self._repo.mark_failed(
                        job.id,
                        "failed" if self._stop_event.is_set() else "failed",
                        "timeout" if not self._stop_event.is_set() else "interrupted by shutdown",
                    )
                    return

                _drain_proc(proc)
                self._repo.finish_attempt(attempt_id)
                child_result = _read_child_result(result_path)
                success = child_result.success

        except Exception as exc:
            log.exception("error managing child for job %s", job.id)
            self._repo.mark_failed(job.id, "failed", str(exc))
            return

        if child_result is None:
            self._repo.mark_failed(job.id, "failed", "no result written by child")
            return

        if not success:
            status = child_result.status or "failed"
            self._repo.mark_failed(job.id, status, child_result.error or "child reported failure")
            return

        # Publish
        try:
            self._repo.mark_publishing(job.id, attempt_id, field_id, str(staging_dir))
            self._repo.update_stage(job.id, "publish")
            published_field_id = publish_job(
                staging_dir=staging_dir,
                field_id=field_id,
                products_dir=self._products_dir,
                repo=self._repo,
                job_id=job.id,
            )
            self._repo.mark_ready(job.id, published_field_id)
            log.info("job %s ready → field %s", job.id, published_field_id)
        except Exception as exc:
            log.exception("publication failed for job %s", job.id)
            self._repo.mark_failed(job.id, "failed", f"publication error: {exc}", from_status="publishing")

    # ------------------------------------------------------------------
    # Child launcher
    # ------------------------------------------------------------------

    def _launch_child(self, request_path: Path, result_path: Path, staging_dir: Path, attempt_id: str):
        """Launch the child process (or use injected builder for tests).

        Returns a Popen object, or None if an injected builder was used.
        """
        if self._builder is not None:
            self._builder(request_path, result_path)
            return None

        import subprocess

        log_path = staging_dir / "child.log"
        log_file = open(log_path, "w", encoding="utf-8")  # noqa: SIM115

        cmd = [
            sys.executable,
            "-m",
            "errante_api.jobs.child",
            str(request_path),
            str(result_path),
        ]

        kwargs: dict = {
            "stdout": log_file,
            "stderr": log_file,
            "shell": False,
        }

        if sys.platform == "win32":
            CREATE_NEW_PROCESS_GROUP = 0x00000200
            kwargs["creationflags"] = CREATE_NEW_PROCESS_GROUP
        else:
            kwargs["start_new_session"] = True

        proc = subprocess.Popen(cmd, **kwargs)
        # Keep log_file open; it will be flushed when proc finishes
        return proc

    # ------------------------------------------------------------------
    # Lock management
    # ------------------------------------------------------------------

    def _acquire_lock(self) -> None:
        self._jobs_dir.mkdir(parents=True, exist_ok=True)
        try:
            if sys.platform == "win32":
                import msvcrt

                fd = os.open(str(self._lock_path), os.O_CREAT | os.O_RDWR)
                try:
                    msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
                except OSError as exc:
                    os.close(fd)
                    raise RuntimeError(
                        f"Another supervisor is already running on {self._jobs_dir}. "
                        "Only one supervisor per jobs directory is allowed."
                    ) from exc
                self._lock_fd = fd
            else:
                import fcntl

                fd = os.open(str(self._lock_path), os.O_CREAT | os.O_RDWR)
                try:
                    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except OSError as exc:
                    os.close(fd)
                    raise RuntimeError(f"Another supervisor is already running on {self._jobs_dir}.") from exc
                self._lock_fd = fd
        except RuntimeError:
            raise
        except Exception as exc:
            log.warning("could not acquire supervisor lock: %s", exc)
            # Non-fatal on platforms where locking is unavailable

    def _release_lock(self) -> None:
        if self._lock_fd is not None:
            try:
                if sys.platform == "win32":
                    import msvcrt

                    msvcrt.locking(self._lock_fd, msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl

                    fcntl.flock(self._lock_fd, fcntl.LOCK_UN)
                os.close(self._lock_fd)
            except Exception:
                pass
            finally:
                self._lock_fd = None


# ------------------------------------------------------------------
# Protocol for injected builders (tests)
# ------------------------------------------------------------------


class _BuilderProtocol:
    """Callable(request_path, result_path) used in tests instead of a child process."""


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _field_id_for_job(job_id: str) -> str:
    """Generate a stable, URL-safe field ID from the job ID."""
    return f"job-{job_id[:12]}"


def _read_child_result(result_path: Path) -> ChildResult:
    try:
        doc = json.loads(result_path.read_text(encoding="utf-8"))
        return ChildResult(
            success=doc.get("success", False),
            field_id=doc.get("field_id"),
            status=doc.get("status", "failed"),
            error=doc.get("error"),
            stage=doc.get("stage"),
        )
    except Exception as exc:
        return ChildResult(success=False, status="failed", error=f"cannot read result: {exc}")


def _kill_tree(proc) -> None:  # type: ignore[no-untyped-def]
    """Terminate the process and its descendants."""
    try:
        if sys.platform == "win32":
            import subprocess

            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                capture_output=True,
            )
        else:
            import signal as sig

            os.killpg(os.getpgid(proc.pid), sig.SIGTERM)
            time.sleep(_GRACE_S)
            if proc.poll() is None:
                os.killpg(os.getpgid(proc.pid), sig.SIGKILL)
    except Exception:
        try:
            proc.terminate()
        except Exception:
            pass


def _drain_proc(proc) -> None:  # type: ignore[no-untyped-def]
    """Ensure stdout/stderr are fully flushed (for file-based redirects)."""
    try:
        if proc.stdout:
            proc.stdout.read()
        if proc.stderr:
            proc.stderr.read()
    except Exception:
        pass
