"""Tests for POST /api/jobs and GET /api/jobs/{id} (WS4-5).

All tests use a mock JobEngine injected via app.state so no real
supervisor threads or SQLite databases are needed.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from errante import settings as core
from errante_api.jobs.errors import JobNotFound, QueueFull
from errante_api.jobs.types import Job, JobStatus
from errante_api.main import create_app
from errante_api.settings import Settings

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_NOW = datetime(2026, 11, 14, 12, 0, 0, tzinfo=UTC)


def _make_job(
    status: JobStatus = JobStatus.queued,
    stage: str = "queued",
    result_field_id: str | None = None,
    error_detail: str | None = None,
    job_id: str = "abc123",
) -> Job:
    return Job(
        id=job_id,
        cache_key="k",
        params={},
        status=status,
        stage=stage,
        created_at=_NOW,
        updated_at=_NOW,
        result_field_id=result_field_id,
        error_detail=error_detail,
    )


def _make_engine(job: Job, created: bool = True) -> MagicMock:
    engine = MagicMock()
    engine.service.submit.return_value = (job, created)
    engine.service.get.return_value = job
    return engine


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def client_no_engine(tmp_path):
    """Client with job engine disabled (app.state.job_engine = None)."""
    config = Settings(data_dir=core.DEMO_DIR, live_cache_dir=tmp_path / "cache")
    app = create_app(config)
    app.state.job_engine = None
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def client_with_engine(tmp_path):
    """Factory fixture — call it with a mock engine to get a TestClient."""

    def _factory(engine: MagicMock) -> TestClient:
        config = Settings(data_dir=core.DEMO_DIR, live_cache_dir=tmp_path / "cache")
        app = create_app(config)
        app.state.job_engine = engine
        return TestClient(app)

    return _factory


# ---------------------------------------------------------------------------
# POST /api/jobs — engine disabled
# ---------------------------------------------------------------------------


def test_submit_without_engine_returns_503(client_no_engine):
    r = client_no_engine.post("/api/jobs", json={"ra": 269.4463, "dec": 4.7665})
    assert r.status_code == 503
    assert "ERRANTE_ENABLE_JOBS" in r.json()["detail"]


# ---------------------------------------------------------------------------
# POST /api/jobs — validation errors
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "body,fragment",
    [
        ({"ra": -1, "dec": 0}, "ra"),
        ({"ra": 360, "dec": 0}, "ra"),
        ({"ra": 0, "dec": 91}, "dec"),
        ({"ra": 0, "dec": -91}, "dec"),
        ({"ra": 0, "dec": 0, "size_deg": 0.001}, "size_deg"),
        ({"ra": 0, "dec": 0, "size_deg": 1.0}, "size_deg"),
        ({"ra": 0, "dec": 0, "max_frames": 1}, "max_frames"),
        ({"ra": 0, "dec": 0, "detectors": [0]}, "detector"),
        ({"ra": 0, "dec": 0, "detectors": [7]}, "detector"),
    ],
)
def test_submit_invalid_params_returns_422(client_with_engine, body, fragment):
    engine = _make_engine(_make_job())
    client = client_with_engine(engine)
    r = client.post("/api/jobs", json={"ra": 0.0, "dec": 0.0, **body})
    assert r.status_code == 422
    assert any(fragment in str(error["loc"][-2:]).lower() for error in r.json()["detail"])
    engine.service.submit.assert_not_called()


# ---------------------------------------------------------------------------
# POST /api/jobs — happy paths
# ---------------------------------------------------------------------------


def test_submit_queued_job_returns_202(client_with_engine):
    job = _make_job(status=JobStatus.queued, stage="queued")
    client = client_with_engine(_make_engine(job))
    r = client.post("/api/jobs", json={"ra": 269.4463, "dec": 4.7665})
    assert r.status_code == 202
    data = r.json()
    assert data["id"] == "abc123"
    assert data["status"] == "queued"
    assert data["result_field_id"] is None


def test_submit_reuses_existing_job(client_with_engine):
    job = _make_job(status=JobStatus.running, stage="build")
    client = client_with_engine(_make_engine(job, created=False))
    r = client.post("/api/jobs", json={"ra": 269.4463, "dec": 4.7665})
    assert r.status_code == 202
    assert r.json()["status"] == "running"


def test_submit_ready_job_returns_field_id(client_with_engine):
    job = _make_job(status=JobStatus.ready, stage="publish", result_field_id="barnards-star")
    client = client_with_engine(_make_engine(job))
    r = client.post("/api/jobs", json={"ra": 269.4463, "dec": 4.7665})
    assert r.status_code == 202
    data = r.json()
    assert data["status"] == "ready"
    assert data["result_field_id"] == "barnards-star"


def test_submit_failed_job_returns_error_detail(client_with_engine):
    job = _make_job(status=JobStatus.failed, stage="build", error_detail="cutout download failed")
    client = client_with_engine(_make_engine(job))
    r = client.post("/api/jobs", json={"ra": 269.4463, "dec": 4.7665})
    assert r.status_code == 202
    data = r.json()
    assert data["status"] == "failed"
    assert "build failed" in data["error_detail"]
    assert "cutout download failed" not in data["error_detail"]


def test_submit_no_coverage(client_with_engine):
    job = _make_job(status=JobStatus.no_coverage, stage="build")
    client = client_with_engine(_make_engine(job))
    r = client.post("/api/jobs", json={"ra": 0.0, "dec": 0.0})
    assert r.status_code == 202
    assert r.json()["status"] == "no_coverage"


def test_submit_publishing_collapses_to_running(client_with_engine):
    """The internal 'publishing' status must be hidden from callers."""
    job = _make_job(status=JobStatus.publishing, stage="publish")
    client = client_with_engine(_make_engine(job))
    r = client.post("/api/jobs", json={"ra": 0.0, "dec": 0.0})
    assert r.status_code == 202
    assert r.json()["status"] == "running"


def test_submit_queue_full_returns_429(client_with_engine):
    engine = MagicMock()
    engine.service.submit.side_effect = QueueFull("queue full")
    client = client_with_engine(engine)
    r = client.post("/api/jobs", json={"ra": 0.0, "dec": 0.0})
    assert r.status_code == 429


def test_submit_all_params_accepted(client_with_engine):
    job = _make_job(status=JobStatus.queued)
    client = client_with_engine(_make_engine(job))
    r = client.post(
        "/api/jobs",
        json={
            "ra": 331.0964,
            "dec": -56.8006,
            "size_deg": 0.1,
            "detectors": [1, 3],
            "mjd_min": 60000.0,
            "mjd_max": 61000.0,
            "max_frames": 20,
        },
    )
    assert r.status_code == 202


# ---------------------------------------------------------------------------
# GET /api/jobs/{id} — engine disabled
# ---------------------------------------------------------------------------


def test_poll_without_engine_returns_503(client_no_engine):
    r = client_no_engine.get("/api/jobs/abc123")
    assert r.status_code == 503


# ---------------------------------------------------------------------------
# GET /api/jobs/{id} — happy paths
# ---------------------------------------------------------------------------


def test_poll_known_job_returns_200(client_with_engine):
    job = _make_job(status=JobStatus.running, stage="build")
    client = client_with_engine(_make_engine(job))
    r = client.get("/api/jobs/abc123")
    assert r.status_code == 200
    assert r.json()["status"] == "running"


def test_poll_unknown_job_returns_404(client_with_engine):
    engine = MagicMock()
    engine.service.get.side_effect = JobNotFound("not found")
    client = client_with_engine(engine)
    r = client.get("/api/jobs/doesnotexist")
    assert r.status_code == 404


def test_poll_ready_job_has_field_id(client_with_engine):
    job = _make_job(status=JobStatus.ready, result_field_id="barnards-star")
    client = client_with_engine(_make_engine(job))
    r = client.get("/api/jobs/abc123")
    assert r.status_code == 200
    assert r.json()["result_field_id"] == "barnards-star"


# ---------------------------------------------------------------------------
# OpenAPI presence
# ---------------------------------------------------------------------------


def test_jobs_endpoints_in_openapi(client_with_engine):
    client = client_with_engine(_make_engine(_make_job()))
    schema = client.get("/openapi.json").json()
    paths = schema["paths"]
    assert "/api/jobs" in paths
    assert "/api/jobs/{job_id}" in paths
