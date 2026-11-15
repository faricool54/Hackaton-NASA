"""Exclusive build supervision, bounded resources and verifiable recovery."""

from __future__ import annotations

import json
import logging
import os
import secrets
import shutil
import subprocess
import sys
import threading
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

import psutil

from ..locking import FileLock
from ..publication import AtomicProductStore, atomic_bytes, field_path, hashes, publication_lock, validate_product
from .process import collect_log, kill_tree, stop_saved_child, tree_bytes
from .publication import publish_job
from .repository import JobRepository, _new_id
from .types import ChildResult, JobRequest, JobStatus, _build_context

log = logging.getLogger(__name__)
_POLL_INTERVAL_S = 2.0
_DEADLINE_S = 900
_LOG_MAX_BYTES = 5 * 1024 * 1024


class Supervisor:
    def __init__(self, repo: JobRepository, jobs_dir: Path, products_dir: Path, *, builder=None):
        self._repo = repo
        self._jobs_dir = jobs_dir.resolve()
        self._products_dir = products_dir.resolve()
        self._builder = builder
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._lock = FileLock(self._jobs_dir / "supervisor.lock", timeout=0)
        self._generation = 0
        self._max_bytes = int(os.environ.get("ERRANTE_JOB_MAX_BYTES", str(768 * 1024**2)))
        if self._max_bytes <= 0:
            raise ValueError("ERRANTE_JOB_MAX_BYTES must be positive")

    def start(self):
        try:
            self._lock.acquire()
        except BlockingIOError as error:
            raise RuntimeError("Another supervisor is already running") from error
        try:
            self._generation = secrets.randbits(63)
            self._stop_event.clear()
            self._recover()
            self._thread = threading.Thread(target=self._loop, name="errante-supervisor", daemon=True)
            self._thread.start()
        except BaseException:
            self._lock.release()
            raise

    def stop(self, timeout=15.0):
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout)
        if self.is_running:
            raise RuntimeError("Supervisor has not stopped; its lock remains held")
        self._lock.release()

    @property
    def is_running(self):
        return self._thread is not None and self._thread.is_alive()

    def _loop(self):
        try:
            while not self._stop_event.is_set():
                try:
                    self._recover()
                    self._tick()
                    self._cleanup()
                except Exception:
                    log.exception("Supervisor tick failed")
                self._stop_event.wait(_POLL_INTERVAL_S)
        finally:
            self._lock.release()

    def _recover(self):
        for job in self._repo.inflight():
            attempt = self._repo.latest_attempt(job.id)
            if attempt is not None:
                stop_saved_child(attempt.pid, self._jobs_dir / "staging" / attempt.id / "request.json")
                self._repo.finish_attempt(attempt.id)
            record = self._repo.publication(job.id)
            if job.status != JobStatus.publishing or not record or not record["file_hashes"]:
                self._repo.mark_failed(job.id, "failed", "interrupted before a verified publication")
                continue
            field_id = record["field_id"]
            root = self._products_dir
            expected_hashes = json.loads(record["file_hashes"])
            try:
                validate_product(root, field_id)
                found = hashes(root, field_id)
                if found != expected_hashes:
                    raise ValueError("Published files do not match the attempt receipt")
            except (ValueError, OSError):
                stage = Path(record["staging_dir"]).resolve()
                if not stage.is_relative_to(self._jobs_dir / "staging"):
                    raise RuntimeError("Unowned recovery staging path") from None
                if field_path(root, field_id).exists():
                    with publication_lock(root):
                        quarantine = root.parent / f".errante-recovery-{_new_id()}"
                        quarantine.mkdir()
                        os.replace(field_path(root, field_id), quarantine / field_id)
                        AtomicProductStore(root).rebuild_manifest()
                try:
                    validate_product(stage / "products", field_id)
                    if hashes(stage / "products", field_id) != expected_hashes:
                        raise ValueError("Recovery staging does not match the publication receipt")
                except (ValueError, OSError):
                    self._repo.mark_failed(job.id, "failed", "verified recovery staging is unavailable")
                    continue
                try:
                    publish_job(staging_dir=stage, field_id=field_id, products_dir=root, repo=self._repo, job_id=job.id)
                except Exception:
                    self._repo.mark_failed(job.id, "failed", "interrupted publication could not be recovered")
                    continue
            else:
                with publication_lock(root):
                    AtomicProductStore(root).rebuild_manifest()
            self._repo.mark_ready(job.id, field_id)

    def _tick(self):
        attempt_id = _new_id()
        claimed = self._repo.claim_next(
            attempt_id, self._generation, datetime.now(UTC) + timedelta(seconds=_DEADLINE_S)
        )
        if claimed is None:
            return
        job, attempt = claimed
        stage = self._jobs_dir / "staging" / attempt_id
        stage.mkdir(parents=True)
        request_path, result_path = stage / "request.json", stage / "result.json"
        field_id = _field_id_for_job(job.id, attempt_id)
        request = JobRequest.from_dict(job.params)
        current = _build_context()
        if any(request.build_context.get(key) != current[key] for key in ("build_revision", "processing")):
            self._repo.finish_attempt(attempt_id)
            self._repo.mark_failed(job.id, "failed", "Processing changed while this request was queued; submit again")
            return
        atomic_bytes(
            request_path,
            json.dumps({"request": request.to_dict(), "staging_dir": str(stage), "field_id": field_id}).encode(),
        )
        self._repo.record_result_path(attempt_id, str(result_path))
        proc = None
        try:
            proc = self._launch_child(request_path, result_path, stage, attempt_id)
            if proc is not None:
                self._repo.record_pid(attempt_id, proc.pid, str(stage))
                deadline = time.monotonic() + _DEADLINE_S
                while proc.poll() is None:
                    reason = (
                        "interrupted by shutdown"
                        if self._stop_event.is_set()
                        else "timeout"
                        if time.monotonic() >= deadline
                        else "job disk budget exceeded"
                        if tree_bytes(stage) > self._max_bytes
                        else None
                    )
                    if reason:
                        kill_tree(proc)
                        proc.wait(timeout=5)
                        raise RuntimeError(reason)
                    self._repo.heartbeat(attempt_id)
                    self._stop_event.wait(0.2)
            result = _read_child_result(result_path)
            if proc is not None and proc.returncode != 0 and result.success:
                raise RuntimeError("Child exited unsuccessfully after writing its result")
            if not self._repo.owns_attempt(job.id, attempt_id, self._generation):
                return
            if not result.success:
                status = result.status if result.status in ("failed", "no_coverage", "pipeline_not_ready") else "failed"
                self._repo.mark_failed(job.id, status, result.error or "build failed")
                return
            if result.field_id != field_id:
                raise ValueError("Child returned the wrong field identity")
            field = validate_product(stage / "products", field_id)
            if (field.center.ra, field.center.dec, field.size_deg) != (request.ra, request.dec, request.size_deg):
                raise ValueError("Child product does not match requested coordinates/FOV")
            if len(field.frames) > request.max_frames:
                raise ValueError("Child exceeded the frame budget")
        except Exception as error:
            log.exception("Build failed for %s", job.id)
            if proc is not None and proc.poll() is None:
                kill_tree(proc)
                proc.wait(timeout=5)
            if self._repo.owns_attempt(job.id, attempt_id, self._generation):
                self._repo.mark_failed(job.id, "failed", str(error))
            return
        finally:
            if proc is not None:
                proc._output_thread.join(timeout=5)
            self._repo.finish_attempt(attempt_id)

        if not self._repo.owns_attempt(job.id, attempt_id, self._generation):
            return
        self._repo.mark_publishing(job.id, attempt_id, field_id, str(stage))
        try:
            publish_job(
                staging_dir=stage, field_id=field_id, products_dir=self._products_dir, repo=self._repo, job_id=job.id
            )
        except Exception as error:
            log.exception("Publication failed for %s", job.id)
            self._repo.mark_failed(job.id, "failed", f"publication error: {error}", from_status="publishing")
            return
        self._repo.mark_ready(job.id, field_id)

    def _launch_child(self, request_path, result_path, staging_dir, attempt_id):
        if self._builder is not None:
            self._builder(request_path, result_path)
            return None
        request = json.loads(request_path.read_text())["request"]
        env = {
            **os.environ,
            "ERRANTE_CACHE_DIR": str(staging_dir / "cache"),
            "ERRANTE_JOB_SUPERVISED": "1",
            "ERRANTE_JOB_OWNER_PID": str(os.getpid()),
            "ERRANTE_JOB_OWNER_CREATED": str(psutil.Process().create_time()),
            "ERRANTE_COLLECTIONS": ",".join(request["build_context"]["collections"]),
        }
        kwargs = (
            {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP}
            if sys.platform == "win32"
            else {"start_new_session": True}
        )
        proc = subprocess.Popen(
            [sys.executable, "-m", "errante_api.jobs.child", str(request_path), str(result_path)],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            shell=False,
            env=env,
            **kwargs,
        )
        proc._output_thread = collect_log(proc, staging_dir / "child.log", _LOG_MAX_BYTES)
        return proc

    def _cleanup(self):
        staging = self._jobs_dir / "staging"
        if not staging.exists():
            return
        for path in staging.iterdir():
            if path.is_symlink() or not path.is_dir() or path.parent.resolve() != staging.resolve():
                continue
            try:
                attempt = self._repo.get_attempt(path.name)
                job = self._repo.get(attempt.job_id)
            except Exception:
                continue
            if attempt.finished_at is None or job.status in (JobStatus.running, JobStatus.publishing):
                continue
            for name in ("cache", "products"):
                child = path / name
                if child.exists() and not child.is_symlink() and child.resolve().is_relative_to(staging.resolve()):
                    shutil.rmtree(child)
            if (datetime.now(UTC) - attempt.finished_at).total_seconds() > 86400:
                shutil.rmtree(path)


def _field_id_for_job(job_id, attempt_id=None):
    return f"job-{job_id}-{attempt_id}" if attempt_id is not None else f"job-{job_id[:12]}"


def _read_child_result(path):
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(doc.get("success"), bool):
            raise ValueError("Invalid success flag")
        return ChildResult(**doc)
    except Exception as error:
        return ChildResult(success=False, error=f"Cannot read child result: {error}")
