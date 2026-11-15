"""GET /api/object (contract 0.5.0, C05). No test may call SIMBAD, Gaia, VizieR or the Exoplanet Archive.

Two kinds of tests: the WS3 lookup mocked (bounds, cache, errors, deadline), and the real WS3 code replaying the
responses recorded live on 2026-11-15 in pipeline/tests/fixtures/ws3/context/ (offline, network forbidden).
"""

from __future__ import annotations

import json
import shutil
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import pytest
import requests
from fastapi.testclient import TestClient

from errante import settings as core
from errante.models import ObjectContextResponse
from errante.science import context as C
from errante_api.main import create_app
from errante_api.object_service import deadlines
from errante_api.settings import Settings

FIXTURES = core.REPO_ROOT / "pipeline" / "tests" / "fixtures" / "ws3" / "context"
REAL_LOOKUP = C.object_context


@pytest.fixture
def config(tmp_path):
    return Settings(
        data_dir=core.DEMO_DIR, live_cache_dir=tmp_path / "api-cache", context_cache_dir=tmp_path / "context"
    )


@pytest.fixture
def no_network(monkeypatch):
    def refuse(*args, **kwargs):
        raise AssertionError("tests must not reach external services")

    monkeypatch.setattr(requests, "get", refuse)


def replayed(*args, **kwargs) -> C.ObjectContext:
    """The real WS3 lookup over the recorded fixtures (offline)."""
    kwargs.update(cache_dir=FIXTURES, offline=True)
    return REAL_LOOKUP(*args, **kwargs)


class Recorder:
    def __init__(self, result=replayed):
        self.calls: list[dict] = []
        self.result = result

    def __call__(self, ra=None, dec=None, **kwargs):
        self.calls.append({"ra": ra, "dec": dec, **kwargs})
        return self.result(ra, dec, **kwargs)

    @property
    def live_calls(self):
        return [c for c in self.calls if not c.get("offline")]


# --- validation -------------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "query",
    [
        "",
        "?ra=10",
        "?dec=10",
        "?name=Vega&ra=10&dec=20",
        "?name=Vega&ra=10",
        "?name=%20%20",
        "?ra=360&dec=0",
        "?ra=-1&dec=0",
        "?ra=10&dec=91",
        "?ra=nan&dec=0",
        "?ra=10&dec=inf",
        "?ra=10&dec=20&radius_arcsec=0",
        "?ra=10&dec=20&radius_arcsec=12.5",  # > ~2 SPHEREx pixels: the pixel-dominance rule would not hold
        "?ra=10&dec=20&radius_arcsec=60",
        "?ra=10&dec=20&epoch_mjd=1",
        "?name=" + "x" * 201,
    ],
)
def test_invalid_queries_are_rejected_before_any_lookup(config, monkeypatch, query):
    lookup = Recorder()
    monkeypatch.setattr(C, "object_context", lookup)
    with TestClient(create_app(config)) as client:
        response = client.get("/api/object" + query)
    assert response.status_code == 422, response.text
    assert lookup.calls == []


# --- mocked WS3 lookup ------------------------------------------------------------------------------------------


def test_lookup_gets_bounded_timeouts_cache_dir_and_defaults(config, monkeypatch):
    lookup = Recorder()
    monkeypatch.setattr(C, "object_context", lookup)
    with TestClient(create_app(config)) as client:
        response = client.get("/api/object", params={"ra": 200.0, "dec": 40.1})
    assert response.status_code == 200
    (call,) = lookup.calls
    deadline, replay, service = deadlines(config)
    assert deadline + replay < config.live_timeout_s and 0 < service <= deadline
    assert call["timeout_s"] == service and call["cache_dir"] == config.context_cache_dir
    assert call["epoch_mjd"] == C.DEFAULT_EPOCH_MJD and call["radius_arcsec"] == C.DEFAULT_RADIUS_ARCSEC
    assert call["name"] is None and not call["offline"]


def test_the_largest_accepted_radius_reaches_the_lookup(config, monkeypatch):
    lookup = Recorder()
    monkeypatch.setattr(C, "object_context", lookup)
    with TestClient(create_app(config)) as client:
        response = client.get("/api/object", params={"ra": 200.0, "dec": 40.1, "radius_arcsec": 12})
    assert response.status_code == 200 and response.json()["query"]["radius_arcsec"] == 12.0
    assert [c["radius_arcsec"] for c in lookup.calls] == [12.0]


def test_results_are_cached_and_concurrent_requests_share_one_lookup(config, monkeypatch):
    gate = threading.Event()

    def slow(*args, **kwargs):
        assert gate.wait(timeout=5)
        return replayed(*args, **kwargs)

    lookup = Recorder(slow)
    monkeypatch.setattr(C, "object_context", lookup)
    with TestClient(create_app(config)) as client:
        with ThreadPoolExecutor(3) as pool:
            futures = [pool.submit(client.get, "/api/object", params={"name": "R Dra"}) for _ in range(3)]
            time.sleep(0.3)
            gate.set()
            answers = [f.result() for f in futures]
        assert [a.status_code for a in answers] == [200, 200, 200]
        assert client.get("/api/object", params={"name": "R Dra"}).json() == answers[0].json()
    with TestClient(create_app(config)) as client:  # the disk cache survives a restart
        assert client.get("/api/object", params={"name": "R Dra"}).status_code == 200
    assert len(lookup.calls) == 1
    assert len(list((config.live_cache_dir / "object-context").glob("*.json"))) == 1


@pytest.mark.parametrize(
    ("error", "status", "hidden"),
    [
        (C.ContextError("could not resolve 'zz': name not found: 'zz'", not_found=True), 404, None),
        (C.ContextError("could not resolve 'zz': ConnectionError: secret-host", not_found=False), 502, "secret"),
        (RuntimeError("private path C:/x"), 502, "private"),
    ],
)
def test_lookup_failures_map_to_documented_statuses_and_are_not_cached(config, monkeypatch, error, status, hidden):
    def fail(*args, **kwargs):
        raise error

    monkeypatch.setattr(C, "object_context", fail)
    with TestClient(create_app(config)) as client:
        response = client.get("/api/object", params={"name": "zz"})
        assert response.status_code == status, response.text
        assert isinstance(response.json()["detail"], str)
        if hidden:
            assert hidden not in response.text
        monkeypatch.setattr(C, "object_context", Recorder())
        assert client.get("/api/object", params={"name": "R Dra"}).status_code == 200
    assert len(list((config.live_cache_dir / "object-context").glob("*.json"))) == 1


def test_partial_results_are_returned_but_never_served_from_the_api_cache(config, monkeypatch, tmp_path):
    # Every service down: the WS3 lookup still answers, with provenance errors.
    def down(*args, **kwargs):
        kwargs.update(cache_dir=tmp_path / "empty", offline=True)
        return REAL_LOOKUP(*args, **kwargs)

    lookup = Recorder(down)
    monkeypatch.setattr(C, "object_context", lookup)
    with TestClient(create_app(config)) as client:
        for _ in range(2):
            doc = client.get("/api/object", params={"ra": 269.44623, "dec": 4.7687}).json()
            assert doc["partial"] and doc["identity"]["match"] == "unavailable"
            assert all(f["value"] == "unknown" for f in doc["facts"])
    assert len(lookup.calls) == 2  # retried, not cached


def test_deadline_returns_a_partial_replay_and_the_finished_lookup_fills_the_cache(config, monkeypatch, tmp_path):
    config.live_timeout_s = 3.0  # deadline 2.4 s
    gate = threading.Event()
    config.context_cache_dir.mkdir(parents=True)
    for f in FIXTURES.glob("sesame-*.json"):  # Sesame answered quickly; Gaia, VSX, ... had not yet
        shutil.copy(f, config.context_cache_dir / f.name)

    def slow(ra, dec, **kwargs):
        if kwargs.get("offline"):
            return REAL_LOOKUP(ra, dec, **kwargs)  # replay of the partial disk cache
        assert gate.wait(timeout=10)
        return replayed(ra, dec, **{k: v for k, v in kwargs.items() if k not in ("cache_dir", "offline")})

    lookup = Recorder(slow)
    monkeypatch.setattr(C, "object_context", lookup)
    try:
        with TestClient(create_app(config)) as client:
            started = time.monotonic()
            response = client.get("/api/object", params={"name": "Barnard's Star"})
            elapsed = time.monotonic() - started
            assert response.status_code == 200 and elapsed < config.live_timeout_s
            doc = response.json()
            assert doc["partial"] and doc["warnings"][0].startswith("Partial result")
            assert doc["identity"]["match"] == "name" and doc["identity"]["display_name"] == "Barnard's star"
            assert C.OFFLINE_MISS not in response.text and "API deadline" in response.text
            assert {p["status"] for p in doc["provenance"] if p["service"] != "sesame"} == {"error"}
            gate.set()  # the background lookup finishes and caches the full context
            for _ in range(50):
                if list((config.live_cache_dir / "object-context").glob("*.json")):
                    break
                time.sleep(0.1)
            full = client.get("/api/object", params={"name": "Barnard's Star"}).json()
            assert not full["partial"] and len(full["planets"]) == 4
    finally:
        gate.set()
    assert len(lookup.live_calls) == 1


def test_deadline_before_the_name_resolved_is_a_504(config, monkeypatch):
    config.live_timeout_s = 2.0
    gate = threading.Event()

    def slow(ra, dec, **kwargs):
        if kwargs.get("offline"):
            return REAL_LOOKUP(ra, dec, **kwargs)  # nothing recorded: ContextError(not_found=False)
        assert gate.wait(timeout=10)
        return replayed(ra, dec, **kwargs)

    monkeypatch.setattr(C, "object_context", Recorder(slow))
    try:
        with TestClient(create_app(config)) as client:
            response = client.get("/api/object", params={"name": "Barnard's Star"})
            assert response.status_code == 504 and "could not be resolved" in response.json()["detail"]
    finally:
        gate.set()


def test_capacity_is_bounded(config, monkeypatch):
    config.object_max_concurrent = 1
    config.live_timeout_s = 2.0
    gate = threading.Event()

    def slow(ra, dec, **kwargs):
        if kwargs.get("offline"):
            return REAL_LOOKUP(ra, dec, **kwargs)
        assert gate.wait(timeout=10)
        return replayed(ra, dec, **kwargs)

    monkeypatch.setattr(C, "object_context", Recorder(slow))
    try:
        with TestClient(create_app(config)) as client:
            first = client.get("/api/object", params={"ra": 200.0, "dec": 40.1})
            assert first.status_code == 200 and first.json()["partial"]  # deadline: replay of an empty cache
            busy = client.get("/api/object", params={"ra": 201.0, "dec": 40.1})
            assert busy.status_code == 503 and busy.headers["retry-after"] == "2"
    finally:
        gate.set()


def test_settings_keep_the_context_cache_private_and_bounds_finite(tmp_path):
    with pytest.raises(ValueError):
        Settings(data_dir=tmp_path, live_cache_dir=tmp_path.parent / "x", context_cache_dir=tmp_path / "context")
    with pytest.raises(ValueError):
        Settings(data_dir=tmp_path / "public", object_deadline_s=float("inf"))
    with pytest.raises(ValueError):
        Settings(data_dir=tmp_path / "public", object_max_concurrent=0)
    too_long = Settings(data_dir=tmp_path / "public", live_timeout_s=30, object_deadline_s=45)
    assert deadlines(too_long)[0] == 25.0  # clamped below the API timeout


# --- real WS3 code over the recorded fixtures (offline) ---------------------------------------------------------


@pytest.fixture
def recorded(config, monkeypatch, no_network):
    shutil.copytree(FIXTURES, config.context_cache_dir)

    def offline(*args, **kwargs):
        kwargs["offline"] = True  # replay only: never refresh an expired recording from the network
        return REAL_LOOKUP(*args, **kwargs)

    monkeypatch.setattr(C, "object_context", offline)
    with TestClient(create_app(config)) as client:
        yield client


def test_recorded_barnard_by_name(recorded):
    response = recorded.get("/api/object", params={"name": "Barnard's Star"})
    assert response.status_code == 200
    doc = ObjectContextResponse.model_validate(response.json())
    assert doc.identity.match == "name" and doc.identity.display_name == "Barnard's star"
    assert doc.identity.gaia_source_id == "4472832130942575872" and doc.identity.spectral_type == "M4V"
    assert response.json()["identity"]["gaia_source_id"] == "4472832130942575872"  # string on the wire
    facts = {f.label: f for f in doc.facts}
    assert facts["Distance"].value.startswith("1.828") and facts["Distance"].verified
    assert facts["Mass"].value == "unknown" and not facts["Mass"].verified
    assert len(doc.planets) == 4 and doc.variability.name == "V2500 Oph"
    assert doc.photometry and all(m.other_mission and m.mission in ("2MASS", "WISE") for m in doc.photometry)
    assert not doc.partial and "not SPHEREx" in doc.note
    assert all(p.status in ("ok", "no_match") for p in doc.provenance)


def test_recorded_click_at_the_eps_indi_b_field_centre(recorded):
    response = recorded.get("/api/object", params={"ra": 331.09665, "dec": -56.80066})
    assert response.status_code == 200
    doc = response.json()
    assert doc["identity"]["match"] == "matched" and doc["identity"]["display_name"] == "eps Ind B"
    assert doc["identity"]["gaia_source_id"] == "6412596012146801152"
    assert doc["planets"] == [] and [h["hostname"] for h in doc["nearby_planet_hosts"]] == ["eps Ind A"]
    assert doc["query"] == {
        "ra": 331.09665,
        "dec": -56.80066,
        "name": None,
        "epoch_mjd": C.DEFAULT_EPOCH_MJD,
        "radius_arcsec": C.DEFAULT_RADIUS_ARCSEC,
    }


def test_recorded_empty_sky_is_a_200_with_nothing_catalogued(recorded):
    response = recorded.get("/api/object", params={"ra": 200.0, "dec": 40.1})
    assert response.status_code == 200
    doc = response.json()
    assert doc["identity"]["match"] == "none" and doc["identity"]["display_name"] is None
    assert all(f["value"] == "unknown" and not f["verified"] for f in doc["facts"])
    assert doc["photometry"] == [] and doc["planets"] == [] and doc["variability"] is None
    assert not doc["partial"]
    json.dumps(doc, allow_nan=False)
