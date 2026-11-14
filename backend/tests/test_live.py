"""Offline archive-boundary regressions; no test may call IRSA/JPL."""

import threading

import pytest
import requests
from fastapi.testclient import TestClient

from errante import settings as core
from errante.models import SearchResult, SkyCoord
from errante_api.main import create_app
from errante_api.settings import Settings


@pytest.fixture
def config(tmp_path):
    return Settings(data_dir=core.DEMO_DIR, live_cache_dir=tmp_path / "cache")


def result(ra=10, dec=20):
    return SearchResult(center=SkyCoord(ra=ra, dec=dec), radius_deg=0, frames=[])


def test_success_cache_survives_restart_and_normalizes_detectors(config, monkeypatch):
    calls = []

    def search(ra, dec, detectors):
        calls.append((ra, dec, detectors))
        return result(ra, dec)

    monkeypatch.setattr("errante.data.irsa.search_frames", search)
    with TestClient(create_app(config)) as client:
        a = client.get("/api/search?ra=10&dec=20&detector=2&detector=1&detector=2")
        b = client.get("/api/search?ra=10&dec=20&detector=1&detector=2")
        assert a.status_code == b.status_code == 200
        assert a.json() == b.json()
    with TestClient(create_app(config)) as client:
        assert client.get("/api/search?ra=10&dec=20&detector=1&detector=2").json() == a.json()
        assert client.get("/api/search?ra=11&dec=20&detector=1").status_code == 200
    assert calls == [(10, 20, [1, 2]), (11, 20, [1])]


def test_expired_and_corrupt_disk_cache_are_refetched(config, monkeypatch):
    import json

    calls = []
    monkeypatch.setattr("errante.data.irsa.search_frames", lambda *a, **k: calls.append(1) or result())
    for iteration in range(3):
        with TestClient(create_app(config)) as client:
            assert client.get("/api/search?ra=10&dec=20").status_code == 200
        path = next(config.live_cache_dir.glob("*.json"))
        if iteration == 0:
            entry = json.loads(path.read_text())
            entry["created_at"] = 0
            path.write_text(json.dumps(entry))
        else:
            path.write_text('{"value": "broken')
    assert len(calls) == 3


def test_memory_cache_expires_without_restart(config, monkeypatch):
    from types import SimpleNamespace

    clock = [1000.0]
    calls = []
    monkeypatch.setattr("errante_api.live_service.time", SimpleNamespace(time=lambda: clock[0]))
    monkeypatch.setattr("errante.data.irsa.search_frames", lambda *a, **k: calls.append(1) or result())
    with TestClient(create_app(config)) as client:
        assert client.get("/api/search?ra=10&dec=20").status_code == 200
        clock[0] += config.live_cache_ttl_s + 1
        assert client.get("/api/search?ra=10&dec=20").status_code == 200
    assert len(calls) == 2


def test_nonfinite_upstream_data_does_not_poison_cache(config, monkeypatch):
    invalid = result().model_dump()
    invalid["frames"] = [{"obs_id": "test", "detector": 1, "mjd": float("nan"), "release": "dr1"}]
    monkeypatch.setattr("errante.data.irsa.search_frames", lambda *a, **k: invalid)
    with TestClient(create_app(config)) as client:
        assert client.get("/api/search?ra=10&dec=20").status_code == 502
        monkeypatch.setattr("errante.data.irsa.search_frames", lambda *a, **k: result())
        assert client.get("/api/search?ra=10&dec=20").status_code == 200


@pytest.mark.parametrize(
    ("failure", "status"),
    [
        (NotImplementedError("private path"), 501),
        (requests.Timeout("secret URL"), 504),
        (requests.ConnectionError("private URL"), 502),
        (ValueError("malformed upstream data"), 502),
    ],
)
def test_archive_failures_are_sanitized_and_not_cached(config, monkeypatch, failure, status):
    def fail(*args, **kwargs):
        raise failure

    monkeypatch.setattr("errante.data.irsa.search_frames", fail)
    with TestClient(create_app(config)) as client:
        response = client.get("/api/search?ra=10&dec=20", headers={"Origin": "https://web.example"})
        assert response.status_code == status
        assert response.headers["access-control-allow-origin"] == "*"
        assert "private" not in response.text and "secret" not in response.text
        monkeypatch.setattr("errante.data.irsa.search_frames", lambda *a, **k: result())
        assert client.get("/api/search?ra=10&dec=20").status_code == 200
    assert len(list(config.live_cache_dir.glob("*.json"))) == 1


def test_deadline_does_not_release_capacity_while_thread_is_running(config, monkeypatch):
    gate = threading.Event()
    started = threading.Event()
    config.live_timeout_s = 0.05
    config.live_max_concurrent = 1

    def slow(*args, **kwargs):
        started.set()
        assert gate.wait(timeout=5)
        return result()

    monkeypatch.setattr("errante.data.irsa.search_frames", slow)
    try:
        with TestClient(create_app(config)) as client:
            assert client.get("/api/search?ra=10&dec=20").status_code == 504
            assert started.is_set()
            response = client.get("/api/search?ra=11&dec=20")
            assert response.status_code == 503
            assert response.headers["retry-after"] == "2"
            assert client.get("/api/health").status_code == 200
    finally:
        gate.set()


def test_invalid_upstream_response_is_502(config, monkeypatch):
    monkeypatch.setattr("errante.data.irsa.search_frames", lambda *a, **k: {"not": "SearchResult"})
    with TestClient(create_app(config)) as client:
        assert client.get("/api/search?ra=10&dec=20").status_code == 502


def test_cache_disk_failure_keeps_valid_response(config, monkeypatch):
    # A file where the cache directory should be makes mkdir fail.
    config.live_cache_dir.write_text("not a directory")
    monkeypatch.setattr("errante.data.irsa.search_frames", lambda *a, **k: result())
    with TestClient(create_app(config)) as client:
        assert client.get("/api/search?ra=10&dec=20").status_code == 200


def test_disk_and_memory_cache_capacity_is_bounded(config, monkeypatch):
    config.live_cache_entries = 2
    monkeypatch.setattr("errante.data.irsa.search_frames", lambda ra, dec, **k: result(ra, dec))
    app = create_app(config)
    with TestClient(app) as client:
        for ra in (10, 11, 12, 13):
            assert client.get(f"/api/search?ra={ra}&dec=20").status_code == 200
        assert len(app.state.live._memory) == 2
    assert len(list(config.live_cache_dir.glob("*.json"))) == 2


def test_known_objects_cache_includes_epoch_and_radius(config, monkeypatch):
    calls = []
    monkeypatch.setattr("errante.science.known_objects.objects_in_frame", lambda *a: calls.append(a) or [])
    with TestClient(create_app(config)) as client:
        for mjd, radius in [(61000, 0.25), (61000, 0.25), (61001, 0.25), (61001, 0.5)]:
            response = client.get(f"/api/known-objects?ra=10&dec=20&mjd={mjd}&radius_deg={radius}")
            assert response.status_code == 200 and response.json() == []
    assert len(calls) == 3


@pytest.mark.parametrize(
    "query",
    ["ra=360&dec=0", "ra=0&dec=91", "ra=nan&dec=0", "ra=0&dec=inf", "ra=0&dec=0&detector=0", "ra=0&dec=0&detector=7"],
)
def test_bad_search_inputs_never_call_archive(config, monkeypatch, query):
    def unexpected(*a, **k):
        pytest.fail("Invalid input reached the archive")

    monkeypatch.setattr("errante.data.irsa.search_frames", unexpected)
    with TestClient(create_app(config)) as client:
        assert client.get(f"/api/search?{query}").status_code == 422


def test_settings_strip_cors_and_read_limits(monkeypatch, tmp_path):
    monkeypatch.setenv("ERRANTE_DATA_DIR", str(tmp_path / "products"))
    monkeypatch.setenv("ERRANTE_API_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setenv("ERRANTE_CORS_ORIGINS", " https://one.example, ,https://two.example ")
    monkeypatch.setenv("ERRANTE_API_TIMEOUT_S", "12")
    settings = Settings.from_env()
    assert settings.cors_origins == ["https://one.example", "https://two.example"]
    assert settings.live_timeout_s == 12
    with pytest.raises(ValueError, match="outside"):
        Settings(data_dir=tmp_path, live_cache_dir=tmp_path / "private")
    with pytest.raises(ValueError, match="positive"):
        Settings(data_dir=tmp_path / "products", live_timeout_s=float("nan"))


@pytest.mark.parametrize(
    "path",
    [
        "fields/..%5C..%5Csecret",
        "fields/C%3Asecret",
        "systems/..%5Csecret",
        "fields/..%5Csecret/candidates",
        "fields/..%5Csecret/known",
    ],
)
def test_product_ids_reject_windows_traversal(config, path):
    with TestClient(create_app(config)) as client:
        assert client.get(f"/api/{path}").status_code == 422
        assert "C:\\" not in client.get("/api/health").json()["data_dir"]


def test_corrupt_product_is_clear_503(config, tmp_path):
    config.data_dir = tmp_path / "products"
    directory = config.data_dir / "fields" / "broken"
    directory.mkdir(parents=True)
    (directory / "field.json").write_text("invalid JSON")
    with TestClient(create_app(config)) as client:
        assert client.get("/api/fields/broken").status_code == 503
        assert client.get("/api/health").json()["status"] == "no-data"


def test_product_symlink_cannot_read_outside_root(config, tmp_path):
    config.data_dir = tmp_path / "products"
    directory = config.data_dir / "fields" / "escape"
    directory.mkdir(parents=True)
    source = core.DEMO_DIR / "fields" / "demo-ecliptic" / "field.json"
    try:
        (directory / "field.json").symlink_to(source)
    except OSError:
        pytest.skip("Symlink privilege unavailable")
    with TestClient(create_app(config)) as client:
        assert client.get("/api/fields/escape").status_code == 404
