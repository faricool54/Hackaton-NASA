"""SQLite persistence layer for the job engine.

Design rules (from INTERNAL_ENGINE_PLAN.md §4):
- Short transactions; connections opened per operation and closed immediately.
- Foreign keys and journal mode (default, single writer).
- ``PRAGMA user_version`` carries the internal schema version.
- No transaction held open during network, process, PNG validation or file copy.
- Busy timeout so concurrent requests queue instead of immediately erroring.
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from collections.abc import Generator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

from .errors import DuplicateActive, JobNotFound, QueueFull
from .types import Attempt, Job, JobStatus

# Increment this when the schema changes in a non-additive way.
_SCHEMA_VERSION = 1

# How long to wait (ms) before giving up on a write lock.
_BUSY_TIMEOUT_MS = 5_000

_MAX_QUEUE = 8  # max jobs in queued + running state together
_MAX_ACTIVE = 1  # max running jobs


def _iso(dt: datetime) -> str:
    return dt.isoformat()


def _from_iso(s: str) -> datetime:
    return datetime.fromisoformat(s)


def _now() -> datetime:
    return datetime.now(UTC)


@contextmanager
def _connect(db_path: Path) -> Generator[sqlite3.Connection, None, None]:
    con = sqlite3.connect(str(db_path), timeout=_BUSY_TIMEOUT_MS / 1000)
    con.row_factory = sqlite3.Row
    try:
        con.execute("PRAGMA foreign_keys = ON")
        yield con
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()


class JobRepository:
    """All database operations for the job engine.

    Thread-safe: each public method opens its own connection.  Do not share a
    connection across method calls.
    """

    def __init__(self, db_path: Path) -> None:
        self._db = db_path
        self._db.parent.mkdir(parents=True, exist_ok=True)
        self._migrate()

    @property
    def db_path(self) -> Path:
        return self._db

    # ------------------------------------------------------------------
    # Schema migration
    # ------------------------------------------------------------------

    def _migrate(self) -> None:
        with _connect(self._db) as con:
            version = con.execute("PRAGMA user_version").fetchone()[0]
            if version == 0:
                self._create_schema(con)
                con.execute(f"PRAGMA user_version = {_SCHEMA_VERSION}")
            elif version > _SCHEMA_VERSION:
                raise RuntimeError(
                    f"Database schema version {version} is newer than the engine "
                    f"knows ({_SCHEMA_VERSION}). Upgrade the backend."
                )
            # version == _SCHEMA_VERSION: nothing to do

    def _create_schema(self, con: sqlite3.Connection) -> None:
        con.executescript(
            """
            CREATE TABLE IF NOT EXISTS jobs (
                id              TEXT PRIMARY KEY,
                cache_key       TEXT NOT NULL,
                params          TEXT NOT NULL,     -- JSON
                status          TEXT NOT NULL,
                stage           TEXT NOT NULL DEFAULT 'queued',
                created_at      TEXT NOT NULL,
                updated_at      TEXT NOT NULL,
                attempt         INTEGER NOT NULL DEFAULT 0,
                result_field_id TEXT,
                error_detail    TEXT,
                reuse_until     TEXT
            );

            CREATE UNIQUE INDEX IF NOT EXISTS idx_jobs_cache_key_active
                ON jobs (cache_key)
                WHERE status IN ('queued', 'running', 'publishing');

            CREATE INDEX IF NOT EXISTS idx_jobs_status
                ON jobs (status);

            CREATE TABLE IF NOT EXISTS attempts (
                id            TEXT PRIMARY KEY,
                job_id        TEXT NOT NULL REFERENCES jobs(id),
                generation    INTEGER NOT NULL,
                started_at    TEXT NOT NULL,
                deadline_at   TEXT NOT NULL,
                heartbeat_at  TEXT,
                pid           INTEGER,
                staging_dir   TEXT,
                result_path   TEXT,
                finished_at   TEXT
            );

            CREATE TABLE IF NOT EXISTS publications (
                id          TEXT PRIMARY KEY,
                job_id      TEXT NOT NULL REFERENCES jobs(id),
                attempt_id  TEXT NOT NULL REFERENCES attempts(id),
                field_id    TEXT NOT NULL,
                stage       TEXT NOT NULL DEFAULT 'started',
                file_hashes TEXT,           -- JSON {rel_path: sha256}
                staging_dir TEXT,
                created_at  TEXT NOT NULL,
                finished_at TEXT
            );

            CREATE TABLE IF NOT EXISTS events (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id      TEXT NOT NULL REFERENCES jobs(id),
                ts          TEXT NOT NULL,
                from_status TEXT,
                to_status   TEXT,
                reason      TEXT
            );
            """
        )

    # ------------------------------------------------------------------
    # Job admission
    # ------------------------------------------------------------------

    def enqueue(self, job_id: str, cache_key: str, params: dict) -> Job:
        """Insert a new job in queued state.

        Raises:
            DuplicateActive: if an active job with the same cache_key exists.
            QueueFull: if the queue is already at capacity.
        """
        now = _now()
        with _connect(self._db) as con:
            con.execute("BEGIN IMMEDIATE")
            dup = con.execute(
                "SELECT id FROM jobs WHERE cache_key=? AND status IN ('queued','running','publishing')",
                (cache_key,),
            ).fetchone()
            if dup:
                raise DuplicateActive(dup["id"])
            # Check active count (queued + running + publishing)
            active_count = con.execute(
                "SELECT COUNT(*) FROM jobs WHERE status IN ('queued','running','publishing')"
            ).fetchone()[0]
            if active_count >= _MAX_QUEUE:
                raise QueueFull(f"Queue is full ({active_count}/{_MAX_QUEUE} active jobs)")

            con.execute(
                """
                INSERT INTO jobs
                    (id, cache_key, params, status, stage, created_at, updated_at)
                VALUES (?, ?, ?, 'queued', 'queued', ?, ?)
                """,
                (job_id, cache_key, json.dumps(params), _iso(now), _iso(now)),
            )
            con.execute(
                "INSERT INTO events (job_id, ts, from_status, to_status, reason) VALUES (?, ?, NULL, 'queued', 'enqueued')",
                (job_id, _iso(now)),
            )
        return self.get(job_id)

    # ------------------------------------------------------------------
    # Claiming a job for execution
    # ------------------------------------------------------------------

    def claim_next(self, attempt_id: str, generation: int, deadline_at: datetime) -> tuple[Job, Attempt] | None:
        """Atomically claim the oldest queued job.

        Returns (Job, Attempt) or None if no queued jobs exist or the running
        slot is already occupied.
        """
        now = _now()
        with _connect(self._db) as con:
            con.execute("BEGIN IMMEDIATE")
            # Only allow _MAX_ACTIVE concurrent runs
            running = con.execute("SELECT COUNT(*) FROM jobs WHERE status IN ('running','publishing')").fetchone()[0]
            if running >= _MAX_ACTIVE:
                return None

            row = con.execute("SELECT * FROM jobs WHERE status = 'queued' ORDER BY created_at LIMIT 1").fetchone()
            if row is None:
                return None

            job_id = row["id"]
            new_attempt = row["attempt"] + 1

            con.execute(
                """
                UPDATE jobs SET status='running', stage='build', updated_at=?, attempt=?
                WHERE id=? AND status='queued'
                """,
                (_iso(now), new_attempt, job_id),
            )
            con.execute(
                """
                INSERT INTO attempts
                    (id, job_id, generation, started_at, deadline_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (attempt_id, job_id, generation, _iso(now), _iso(deadline_at)),
            )
            con.execute(
                "INSERT INTO events (job_id, ts, from_status, to_status, reason) VALUES (?, ?, 'queued', 'running', 'claimed')",
                (job_id, _iso(now)),
            )

        job = self.get(job_id)
        attempt = self.get_attempt(attempt_id)
        return job, attempt

    # ------------------------------------------------------------------
    # Attempt lifecycle
    # ------------------------------------------------------------------

    def record_pid(self, attempt_id: str, pid: int, staging_dir: str) -> None:
        with _connect(self._db) as con:
            con.execute(
                "UPDATE attempts SET pid=?, staging_dir=? WHERE id=?",
                (pid, staging_dir, attempt_id),
            )

    def heartbeat(self, attempt_id: str) -> None:
        with _connect(self._db) as con:
            con.execute(
                "UPDATE attempts SET heartbeat_at=? WHERE id=?",
                (_iso(_now()), attempt_id),
            )

    def record_result_path(self, attempt_id: str, result_path: str) -> None:
        with _connect(self._db) as con:
            con.execute(
                "UPDATE attempts SET result_path=? WHERE id=?",
                (result_path, attempt_id),
            )

    def finish_attempt(self, attempt_id: str) -> None:
        with _connect(self._db) as con:
            con.execute(
                "UPDATE attempts SET finished_at=? WHERE id=?",
                (_iso(_now()), attempt_id),
            )

    # ------------------------------------------------------------------
    # Job state transitions
    # ------------------------------------------------------------------

    def mark_publishing(self, job_id: str, attempt_id: str, field_id: str, staging_dir: str) -> None:
        now = _now()
        pub_id = _new_id()
        with _connect(self._db) as con:
            con.execute(
                "UPDATE jobs SET status='publishing', stage='publish', updated_at=? WHERE id=?",
                (_iso(now), job_id),
            )
            con.execute(
                """
                INSERT INTO publications (id, job_id, attempt_id, field_id, stage, staging_dir, created_at)
                VALUES (?, ?, ?, ?, 'started', ?, ?)
                """,
                (pub_id, job_id, attempt_id, field_id, staging_dir, _iso(now)),
            )
            con.execute(
                "INSERT INTO events (job_id, ts, from_status, to_status, reason) VALUES (?, ?, 'running', 'publishing', 'validate_ok')",
                (job_id, _iso(now)),
            )

    def mark_ready(self, job_id: str, field_id: str, reuse_ttl_seconds: int = 900) -> None:
        from datetime import timedelta

        now = _now()
        reuse_until = now + timedelta(seconds=reuse_ttl_seconds)
        with _connect(self._db) as con:
            con.execute(
                """
                UPDATE jobs
                SET status='ready', stage='publish', updated_at=?, result_field_id=?, reuse_until=?
                WHERE id=?
                """,
                (_iso(now), field_id, _iso(reuse_until), job_id),
            )
            con.execute(
                """
                UPDATE publications SET stage='done', finished_at=?
                WHERE job_id=? AND stage != 'done'
                """,
                (_iso(now), job_id),
            )
            con.execute(
                "INSERT INTO events (job_id, ts, from_status, to_status, reason) VALUES (?, ?, 'publishing', 'ready', 'published')",
                (job_id, _iso(now)),
            )

    def mark_failed(self, job_id: str, status: str, detail: str, from_status: str = "running") -> None:
        now = _now()
        with _connect(self._db) as con:
            con.execute(
                "UPDATE jobs SET status=?, stage='failed', updated_at=?, error_detail=? WHERE id=?",
                (status, _iso(now), detail[:4096], job_id),
            )
            con.execute(
                "INSERT INTO events (job_id, ts, from_status, to_status, reason) VALUES (?, ?, ?, ?, ?)",
                (job_id, _iso(now), from_status, status, detail[:256]),
            )

    def update_stage(self, job_id: str, stage: str) -> None:
        with _connect(self._db) as con:
            con.execute(
                "UPDATE jobs SET stage=?, updated_at=? WHERE id=?",
                (stage, _iso(_now()), job_id),
            )

    def latest_attempt(self, job_id: str) -> Attempt | None:
        with _connect(self._db) as con:
            row = con.execute("SELECT * FROM attempts WHERE job_id=? ORDER BY rowid DESC LIMIT 1", (job_id,)).fetchone()
        return _row_to_attempt(row) if row else None

    def owns_attempt(self, job_id: str, attempt_id: str, generation: int) -> bool:
        attempt = self.latest_attempt(job_id)
        return bool(
            attempt
            and attempt.id == attempt_id
            and attempt.generation == generation
            and self.get(job_id).status in (JobStatus.running, JobStatus.publishing)
        )

    def publication(self, job_id: str) -> dict | None:
        with _connect(self._db) as con:
            row = con.execute(
                "SELECT * FROM publications WHERE job_id=? ORDER BY rowid DESC LIMIT 1", (job_id,)
            ).fetchone()
        return dict(row) if row else None

    def record_publication_hashes(self, job_id: str, fingerprint: dict[str, str]) -> None:
        with _connect(self._db) as con:
            con.execute(
                "UPDATE publications SET file_hashes=?,stage='prepared' WHERE job_id=? AND stage!='done'",
                (json.dumps(fingerprint, sort_keys=True), job_id),
            )

    def inflight(self) -> list[Job]:
        with _connect(self._db) as con:
            rows = con.execute("SELECT * FROM jobs WHERE status IN ('running','publishing')").fetchall()
        return [_row_to_job(row) for row in rows]

    def invalidate_ready(self, job_id: str) -> None:
        with _connect(self._db) as con:
            con.execute(
                "UPDATE jobs SET status='failed',stage='failed',reuse_until=NULL,error_detail='Published artifact unavailable',updated_at=? WHERE id=? AND status='ready'",
                (_iso(_now()), job_id),
            )

    # ------------------------------------------------------------------
    # Reutilisation
    # ------------------------------------------------------------------

    def find_reusable(self, cache_key: str) -> Job | None:
        """Return a ready job whose reuse window is still valid, or None."""
        now = _iso(_now())
        with _connect(self._db) as con:
            row = con.execute(
                """
                SELECT * FROM jobs
                WHERE cache_key=? AND status='ready'
                  AND reuse_until IS NOT NULL AND reuse_until > ?
                ORDER BY updated_at DESC LIMIT 1
                """,
                (cache_key, now),
            ).fetchone()
        return _row_to_job(row) if row else None

    def find_active(self, cache_key: str) -> Job | None:
        with _connect(self._db) as con:
            row = con.execute(
                "SELECT * FROM jobs WHERE cache_key=? AND status IN ('queued','running','publishing')", (cache_key,)
            ).fetchone()
        return _row_to_job(row) if row else None

    # ------------------------------------------------------------------
    # Reconciliation: resolve stale running/publishing records on startup
    # ------------------------------------------------------------------

    def reconcile_interrupted(self) -> list[str]:
        """Mark any jobs stuck in running/publishing as failed (interrupted).

        Called once on supervisor startup, before claiming new work.
        Returns the IDs of jobs that were reconciled.
        """
        now = _now()
        with _connect(self._db) as con:
            rows = con.execute("SELECT id, status FROM jobs WHERE status IN ('running', 'publishing')").fetchall()
            ids = []
            for row in rows:
                job_id = row["id"]
                from_status = row["status"]
                con.execute(
                    "UPDATE jobs SET status='failed', stage='interrupted', updated_at=?, error_detail=? WHERE id=?",
                    (_iso(now), "interrupted on supervisor startup", job_id),
                )
                con.execute(
                    "INSERT INTO events (job_id, ts, from_status, to_status, reason) VALUES (?, ?, ?, 'failed', 'interrupted_on_startup')",
                    (job_id, _iso(now), from_status),
                )
                ids.append(job_id)
        return ids

    # ------------------------------------------------------------------
    # Read operations
    # ------------------------------------------------------------------

    def get(self, job_id: str) -> Job:
        with _connect(self._db) as con:
            row = con.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
        if row is None:
            raise JobNotFound(job_id)
        return _row_to_job(row)

    def get_attempt(self, attempt_id: str) -> Attempt:
        with _connect(self._db) as con:
            row = con.execute("SELECT * FROM attempts WHERE id=?", (attempt_id,)).fetchone()
        if row is None:
            raise JobNotFound(f"attempt:{attempt_id}")
        return _row_to_attempt(row)

    def list_jobs(self, status: str | None = None, limit: int = 50) -> list[Job]:
        with _connect(self._db) as con:
            if status:
                rows = con.execute(
                    "SELECT * FROM jobs WHERE status=? ORDER BY created_at DESC LIMIT ?",
                    (status, limit),
                ).fetchall()
            else:
                rows = con.execute("SELECT * FROM jobs ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
        return [_row_to_job(r) for r in rows]


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _new_id() -> str:
    return uuid.uuid4().hex


def _row_to_job(row: sqlite3.Row) -> Job:
    return Job(
        id=row["id"],
        cache_key=row["cache_key"],
        params=json.loads(row["params"]),
        status=JobStatus(row["status"]),
        stage=row["stage"],
        created_at=_from_iso(row["created_at"]),
        updated_at=_from_iso(row["updated_at"]),
        attempt=row["attempt"],
        result_field_id=row["result_field_id"],
        error_detail=row["error_detail"],
        reuse_until=_from_iso(row["reuse_until"]) if row["reuse_until"] else None,
    )


def _row_to_attempt(row: sqlite3.Row) -> Attempt:
    return Attempt(
        id=row["id"],
        job_id=row["job_id"],
        generation=row["generation"],
        started_at=_from_iso(row["started_at"]),
        deadline_at=_from_iso(row["deadline_at"]),
        heartbeat_at=_from_iso(row["heartbeat_at"]) if row["heartbeat_at"] else None,
        pid=row["pid"],
        staging_dir=row["staging_dir"],
        result_path=row["result_path"],
        finished_at=_from_iso(row["finished_at"]) if row["finished_at"] else None,
    )
