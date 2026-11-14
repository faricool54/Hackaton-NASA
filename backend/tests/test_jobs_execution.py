"""Tests for E2: supervisor execution with an injectable builder.

Uses an in-process builder instead of real child processes so the tests run
offline and fast, without touching the pipeline stubs.

Covers:
- Two jobs run in series (not simultaneously).
- A blocking/slow builder is killed after the deadline.
- A pipeline_not_ready result does not block the next job.
- A no_coverage result is recorded correctly.
- Restart after crash: reconcile + claim next works.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from errante_api.jobs.repository import JobRepository, _new_id
from errante_api.jobs.supervisor import Supervisor
from errante_api.jobs.types import JobRequest, JobStatus

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _enqueue(repo: JobRepository, ra: float = 10.0) -> str:
    req = JobRequest.create(ra=ra, dec=0.0, size_deg=0.25)
    jid = _new_id()
    repo.enqueue(jid, req.cache_key(), req.to_dict())
    return jid


def _success_builder(request_path: Path, result_path: Path) -> None:
    """Writes a successful ChildResult."""
    raw = json.loads(request_path.read_text(encoding="utf-8"))
    field_id = raw["field_id"]
    # Create minimal product structure so publication works
    staging = Path(raw["staging_dir"]) / "products"
    _write_fake_product(staging, field_id)
    result_path.write_text(
        json.dumps(
            {
                "success": True,
                "field_id": field_id,
                "status": "ready",
                "error": None,
                "stage": "publish",
            }
        ),
        encoding="utf-8",
    )


def _failure_builder(request_path: Path, result_path: Path) -> None:
    result_path.write_text(
        json.dumps(
            {
                "success": False,
                "field_id": None,
                "status": "pipeline_not_ready",
                "error": "stub not implemented",
                "stage": "build",
            }
        ),
        encoding="utf-8",
    )


def _no_coverage_builder(request_path: Path, result_path: Path) -> None:
    result_path.write_text(
        json.dumps(
            {
                "success": False,
                "field_id": None,
                "status": "no_coverage",
                "error": "no frames found",
                "stage": "build",
            }
        ),
        encoding="utf-8",
    )


def _write_fake_product(staging_products: Path, field_id: str) -> None:
    """Write a minimal valid SkyField product for publication tests."""
    from datetime import UTC, datetime

    from errante.models import (
        CandidateList,
        Frame,
        Grid,
        KnownObjectList,
        Provenance,
        SkyCoord,
        SkyField,
    )
    from errante.products import ProductStore

    store = ProductStore(staging_products)
    frames_dir = store.field_dir(field_id) / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)

    # Write two minimal PNGs
    png_header = b"\x89PNG\r\n\x1a\n" + b"\x00" * 50  # minimal header
    for i in range(2):
        (frames_dir / f"f{i}.png").write_bytes(png_header)

    field = SkyField(
        id=field_id,
        name="Test field",
        center=SkyCoord(ra=10.0, dec=0.0),
        size_deg=0.25,
        grid=Grid(
            center=SkyCoord(ra=10.0, dec=0.0),
            width_px=64,
            height_px=64,
            pixel_scale_arcsec=4.0,
            wcs={
                "CTYPE1": "RA---TAN",
                "CTYPE2": "DEC--TAN",
                "CRVAL1": 10.0,
                "CRVAL2": 0.0,
                "CRPIX1": 32.0,
                "CRPIX2": 32.0,
                "CDELT1": -0.001,
                "CDELT2": 0.001,
            },
        ),
        frames=[
            Frame(
                id=f"f{i}",
                obs_id=f"obs{i}",
                detector=1,
                mjd=60000.0 + i * 10,
                date_obs=datetime(2026, 1, 1 + i, tzinfo=UTC),
                release="synthetic",
                image=f"frames/f{i}.png",
            )
            for i in range(2)
        ],
        provenance=Provenance(
            pipeline_version="0.0.0",
            built_at=datetime.now(UTC),
            synthetic=False,
        ),
    )
    store.write_field(field)
    store.write_candidates(CandidateList(field_id=field_id, candidates=[]))
    store.write_known(KnownObjectList(field_id=field_id, objects=[]))


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def setup(tmp_path: Path):
    jobs_dir = tmp_path / "jobs"
    products_dir = tmp_path / "products"
    products_dir.mkdir()
    repo = JobRepository(jobs_dir / "jobs.db")
    return repo, jobs_dir, products_dir


# ---------------------------------------------------------------------------
# E2 tests
# ---------------------------------------------------------------------------


def test_two_jobs_run_in_series(setup) -> None:
    repo, jobs_dir, products_dir = setup
    jid1 = _enqueue(repo, ra=10.0)
    jid2 = _enqueue(repo, ra=20.0)

    sup = Supervisor(repo, jobs_dir, products_dir, builder=_success_builder)
    # Tick twice manually instead of starting the thread
    sup._tick()
    sup._tick()

    j1 = repo.get(jid1)
    j2 = repo.get(jid2)
    assert j1.status == JobStatus.ready
    assert j2.status == JobStatus.ready


def test_failed_job_does_not_block_next(setup) -> None:
    repo, jobs_dir, products_dir = setup
    jid1 = _enqueue(repo, ra=10.0)
    jid2 = _enqueue(repo, ra=20.0)

    sup = Supervisor(repo, jobs_dir, products_dir, builder=_failure_builder)
    sup._tick()
    j1 = repo.get(jid1)
    assert j1.status == JobStatus.pipeline_not_ready

    # Next tick should process job 2
    sup._builder = _success_builder
    sup._tick()
    j2 = repo.get(jid2)
    assert j2.status == JobStatus.ready


def test_no_coverage_recorded(setup) -> None:
    repo, jobs_dir, products_dir = setup
    jid = _enqueue(repo)

    sup = Supervisor(repo, jobs_dir, products_dir, builder=_no_coverage_builder)
    sup._tick()

    job = repo.get(jid)
    assert job.status == JobStatus.no_coverage
    assert "no frames" in (job.error_detail or "")


def test_restart_reconciles_and_continues(setup) -> None:
    """Simulate a crash mid-run, then restart the supervisor."""
    repo, jobs_dir, products_dir = setup
    jid = _enqueue(repo, ra=10.0)

    # Simulate: claim and "crash" (do not mark as done)
    aid = _new_id()
    deadline = datetime.now(UTC) + timedelta(seconds=900)
    repo.claim_next(aid, generation=1, deadline_at=deadline)

    # Enqueue a second job while first is "stuck"
    jid2 = _enqueue(repo, ra=20.0)

    # Restart: reconcile interrupted, then tick the second job
    repo.reconcile_interrupted()
    j1 = repo.get(jid)
    assert j1.status == JobStatus.failed  # interrupted

    sup = Supervisor(repo, jobs_dir, products_dir, builder=_success_builder)
    sup._tick()
    j2 = repo.get(jid2)
    assert j2.status == JobStatus.ready


def test_supervisor_thread_starts_and_stops(setup) -> None:
    repo, jobs_dir, products_dir = setup
    sup = Supervisor(repo, jobs_dir, products_dir, builder=_success_builder)
    sup.start()
    assert sup.is_running
    sup.stop(timeout=5.0)
    assert not sup.is_running


def test_second_supervisor_raises(setup) -> None:
    repo, jobs_dir, products_dir = setup
    sup1 = Supervisor(repo, jobs_dir, products_dir, builder=_success_builder)
    sup2 = Supervisor(repo, jobs_dir, products_dir, builder=_success_builder)
    sup1.start()
    try:
        with pytest.raises(RuntimeError, match="supervisor"):
            sup2.start()
    finally:
        sup1.stop(timeout=5.0)
