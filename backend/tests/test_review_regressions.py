"""Integration failures found in the WS4 review: exercise real boundaries offline."""

import json
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta

import psutil
import pytest
from fastapi.testclient import TestClient
from test_jobs_execution import _success_builder
from test_jobs_publication import _write_valid_product

from errante import settings as core
from errante.products import ProductStore
from errante_api.jobs.errors import QueueFull
from errante_api.jobs.process import collect_log, kill_tree
from errante_api.jobs.publication import publish_job
from errante_api.jobs.repository import JobRepository
from errante_api.jobs.service import JobService
from errante_api.jobs.supervisor import Supervisor, _field_id_for_job
from errante_api.jobs.types import JobRequest, JobStatus
from errante_api.main import create_app
from errante_api.publication import AtomicProductStore, hashes, publication_lock, publish_field, validate_product
from errante_api.settings import Settings


def enqueue(repo, ra=10):
    return JobService(repo).submit(JobRequest.create(ra, 0, 0.25))[0]


def test_browser_can_submit_and_open_first_built_field(tmp_path):
    config = Settings(
        data_dir=tmp_path / "new-products",
        live_cache_dir=tmp_path / "cache",
        enable_jobs=True,
        jobs_dir=tmp_path / "jobs",
    )
    with TestClient(create_app(config)) as client:
        client.app.state.job_engine._supervisor._builder = _success_builder
        preflight = client.options(
            "/api/jobs",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type",
            },
        )
        assert preflight.status_code == 200
        response = client.post("/api/jobs", json={"ra": 10, "dec": 0})
        assert response.status_code == 202
        job_id = response.json()["id"]
        deadline = time.monotonic() + 8
        while time.monotonic() < deadline:
            status = client.get("/api/jobs/" + job_id).json()
            if status["status"] not in ("queued", "running"):
                break
            time.sleep(0.05)
        assert status["status"] == "ready", status
        fid = status["result_field_id"]
        field = client.get("/api/fields/" + fid).json()
        assert field["id"] == fid
        assert client.get(f"/data/fields/{fid}/" + field["frames"][0]["image"]).status_code == 200
        assert fid in [f["id"] for f in client.get("/api/manifest").json()["fields"]]


def test_enabled_jobs_select_writable_products_even_without_manifest(tmp_path, monkeypatch):
    monkeypatch.setenv("ERRANTE_ENABLE_JOBS", "1")
    monkeypatch.setattr(core, "PRODUCTS_DIR", tmp_path / "products")
    assert Settings.from_env().data_dir == tmp_path / "products"


def test_concurrent_duplicate_admission_returns_one_job(tmp_path):
    service = JobService(JobRepository(tmp_path / "jobs.db"))
    barrier = threading.Barrier(8)

    def submit(_):
        barrier.wait()
        return service.submit(JobRequest.create(10, 0, 0.25))

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(submit, range(8)))
    assert len({job.id for job, _ in results}) == 1
    assert sum(created for _, created in results) == 1


def test_capacity_and_reuse_are_transactional(tmp_path):
    repo = JobRepository(tmp_path / "jobs.db")
    service = JobService(repo)
    initial = [enqueue(repo, ra) for ra in range(7)]
    gate = threading.Barrier(2)

    def submit(ra):
        gate.wait()
        try:
            return service.submit(JobRequest.create(ra, 0, 0.25))
        except QueueFull:
            return None

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(submit, [20, 30]))
    assert sum(r is not None for r in results) == 1
    assert len(repo.list_jobs()) == 8
    assert service.submit(JobRequest.create(0, 0, 0.25))[0].id == initial[0].id


def test_manifest_failure_is_not_ready_and_preserves_existing(tmp_path, monkeypatch):
    repo = JobRepository(tmp_path / "jobs/jobs.db")
    job = enqueue(repo)
    products = tmp_path / "products"
    _write_valid_product(products, "previous")
    ProductStore(products).rebuild_manifest()
    old = (products / "manifest.json").read_bytes()

    def fail(*a):
        raise OSError("simulated disk failure")

    monkeypatch.setattr(AtomicProductStore, "rebuild_manifest", fail)
    Supervisor(repo, tmp_path / "jobs", products, builder=_success_builder)._tick()
    assert repo.get(job.id).status == JobStatus.failed
    assert (products / "manifest.json").read_bytes() == old
    assert sorted(p.name for p in (products / "fields").iterdir()) == ["previous"]


@pytest.mark.parametrize("installed", [False, True])
def test_recovery_completes_verified_publication_without_rebuilding(tmp_path, installed):
    repo = JobRepository(tmp_path / "jobs/jobs.db")
    job = enqueue(repo)
    _, attempt = repo.claim_next("attempt", 1, datetime.now(UTC) + timedelta(seconds=60))
    field_id = _field_id_for_job(job.id, attempt.id)
    stage = tmp_path / "jobs/staging/attempt"
    products = tmp_path / "products"
    _write_valid_product(stage / "products", field_id)
    repo.mark_publishing(job.id, attempt.id, field_id, str(stage))
    if installed:
        publish_job(staging_dir=stage, field_id=field_id, products_dir=products, repo=repo, job_id=job.id)
        (products / "manifest.json").unlink()
    else:
        repo.record_publication_hashes(job.id, hashes(stage / "products", field_id))
    Supervisor(repo, tmp_path / "jobs", products)._recover()
    assert repo.get(job.id).status == JobStatus.ready
    assert ProductStore(products).read_manifest().fields[0].id == field_id


def test_truncated_png_rejected(tmp_path):
    _write_valid_product(tmp_path, "broken")
    (tmp_path / "fields/broken/frames/f0.png").write_bytes(b"\x89PNG\r\n\x1a\n" + bytes(50))
    with pytest.raises(ValueError, match="valid PNG"):
        validate_product(tmp_path, "broken")


def test_incomplete_private_copy_never_replaces_public_product(tmp_path, monkeypatch):
    stage, public = tmp_path / "stage", tmp_path / "public"
    _write_valid_product(stage, "target")
    _write_valid_product(public, "target")
    old = (public / "fields/target/field.json").read_bytes()

    def copy(source, destination):
        destination.mkdir()
        raise OSError("copy interrupted")

    monkeypatch.setattr("errante_api.publication.shutil.copytree", copy)
    with pytest.raises(OSError):
        publish_field(stage, "target", public, replace=True)
    assert (public / "fields/target/field.json").read_bytes() == old


def test_publication_lock_is_shared_between_processes(tmp_path):
    script = "from pathlib import Path; from errante_api.locking import FileLock; FileLock(Path(__import__('sys').argv[1]),timeout=0).acquire()"
    with publication_lock(tmp_path):
        response = subprocess.run(
            [sys.executable, "-c", script, str(tmp_path / ".publish.lock")], capture_output=True, timeout=10
        )
    assert response.returncode != 0 and b"Lock is busy" in response.stderr


def test_stop_does_not_release_ownership_while_builder_is_alive(tmp_path):
    repo = JobRepository(tmp_path / "jobs/jobs.db")
    enqueue(repo)
    entered, release = threading.Event(), threading.Event()

    def slow(request, result):
        entered.set()
        assert release.wait(5)
        _success_builder(request, result)

    first = Supervisor(repo, tmp_path / "jobs", tmp_path / "products", builder=slow)
    second = Supervisor(repo, tmp_path / "jobs", tmp_path / "products")
    first.start()
    try:
        assert entered.wait(3)
        with pytest.raises(RuntimeError, match="lock remains held"):
            first.stop(timeout=0)
        with pytest.raises(RuntimeError, match="already running"):
            second.start()
    finally:
        release.set()
        first.stop(timeout=5)
    second.start()
    second.stop()


def test_log_limit_drains_output_without_deadlock(tmp_path):
    proc = subprocess.Popen([sys.executable, "-c", "print('x'*100000)"], stdout=subprocess.PIPE)
    thread = collect_log(proc, tmp_path / "child.log", 1024)
    proc.wait(timeout=10)
    thread.join(timeout=5)
    assert not thread.is_alive()
    content = (tmp_path / "child.log").read_bytes()
    assert len(content) <= 1024 and b"truncated" in content


def test_missing_ready_artifact_is_not_reused(tmp_path):
    repo = JobRepository(tmp_path / "jobs.db")
    request = JobRequest.create(10, 0, 0.25)
    service = JobService(repo, tmp_path / "products")
    job, _ = service.submit(request)
    repo.mark_ready(job.id, "missing")
    replacement, created = service.submit(request)
    assert created and replacement.id != job.id
    assert repo.get(job.id).status == JobStatus.failed


def test_context_changes_invalidate_keys_and_ra_does_not_round_out_of_range(monkeypatch):
    request = JobRequest.create(359.9999999, 0, 0.25)
    before = request.cache_key()
    monkeypatch.setattr(core, "IRSA_COLLECTIONS", ["spherex_qr3"])
    assert request.cache_key() == before
    assert JobRequest.create(359.9999999, 0, 0.25).cache_key() != before
    assert request.ra < 360


def test_deadline_cleanup_kills_actual_child_and_descendant():
    script = "import subprocess,sys,time; child=subprocess.Popen([sys.executable,'-c','import time; time.sleep(60)']); print(child.pid,flush=True); time.sleep(60)"
    options = (
        {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP}
        if sys.platform == "win32"
        else {"start_new_session": True}
    )
    proc = subprocess.Popen([sys.executable, "-c", script], stdout=subprocess.PIPE, **options)
    descendant = psutil.Process(int(proc.stdout.readline()))
    try:
        kill_tree(proc, grace=0.2)
        proc.wait(timeout=5)
        assert not descendant.is_running() or descendant.status() == psutil.STATUS_ZOMBIE
    finally:
        if proc.poll() is None:
            proc.kill()
        if descendant.is_running():
            try:
                descendant.kill()
            except psutil.NoSuchProcess:
                pass
        proc.stdout.close()


def test_generic_pipeline_error_is_not_mislabeled_as_no_coverage(tmp_path, monkeypatch):
    from errante.models import FrameRef, SearchResult, SkyCoord
    from errante_api.jobs.child import _run

    request = tmp_path / "request.json"
    result = tmp_path / "result.json"
    request.write_text(
        json.dumps(
            {"request": JobRequest.create(10, 0, 0.25).to_dict(), "staging_dir": str(tmp_path), "field_id": "job-test"}
        )
    )
    coverage = SearchResult(
        center=SkyCoord(ra=10, dec=0),
        radius_deg=0,
        frames=[FrameRef(obs_id="fixture", detector=1, mjd=61000, release="dr1")],
    )
    monkeypatch.setattr("errante.data.irsa.search_frames", lambda *a, **k: coverage)

    def fail(*a, **k):
        raise ValueError("no products: invalid projection")

    monkeypatch.setattr("errante.build.build_field", fail)
    _run(request, result)
    assert json.loads(result.read_text())["status"] == "failed"


def test_no_private_job_directory_can_be_served(tmp_path):
    with pytest.raises(ValueError, match="outside"):
        Settings(
            data_dir=tmp_path, jobs_dir=tmp_path / "jobs", live_cache_dir=tmp_path.parent / "cache", enable_jobs=True
        )


def test_storage_quota_rejects_new_work_but_reuses_active(tmp_path, monkeypatch):
    monkeypatch.setenv("ERRANTE_JOBS_MAX_BYTES", "1")
    repo = JobRepository(tmp_path / "jobs.db")
    first = enqueue(repo)
    service = JobService(repo, tmp_path / "products")
    assert service.submit(JobRequest.create(10, 0, 0.25))[0].id == first.id
    with pytest.raises(QueueFull, match="storage budget"):
        service.submit(JobRequest.create(20, 0, 0.25))


def test_owner_monitor_does_not_block_scientific_imports():
    import os

    environment = {
        **os.environ,
        "ERRANTE_JOB_OWNER_PID": str(os.getpid()),
        "ERRANTE_JOB_OWNER_CREATED": str(psutil.Process().create_time()),
    }
    script = "import threading; from errante_api.jobs.child import _watch_parent; threading.Thread(target=_watch_parent,daemon=True).start(); import numpy; print('imported')"
    result = subprocess.run(
        [sys.executable, "-c", script], stdin=subprocess.DEVNULL, capture_output=True, env=environment, timeout=15
    )
    assert result.returncode == 0 and b"imported" in result.stdout
