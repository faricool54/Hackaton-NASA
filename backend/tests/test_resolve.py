"""Tests for GET /api/resolve-name (WS4).

All Sesame HTTP calls are mocked — no network required.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from errante import settings as core
from errante_api.main import create_app
from errante_api.routes.resolve import _resolve_cached
from errante_api.settings import Settings

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def clear_lru_cache():
    """Clear the in-memory LRU cache between tests."""
    _resolve_cached.cache_clear()
    yield
    _resolve_cached.cache_clear()


@pytest.fixture(scope="module")
def client():
    return TestClient(create_app(Settings(data_dir=core.DEMO_DIR)))


# ---------------------------------------------------------------------------
# Sesame XML samples
# ---------------------------------------------------------------------------

_SESAME_BARNARD = """\
<?xml version="1.0" encoding="UTF-8"?>
<Sesame>
  <Resolver name="S=Simbad">
    <oname>NAME Barnard's star</oname>
    <jpos>269.4520 4.6933</jpos>
    <otype>V*</otype>
  </Resolver>
</Sesame>
"""

_SESAME_NOT_FOUND = """\
<?xml version="1.0" encoding="UTF-8"?>
<Sesame>
</Sesame>
"""

_SESAME_BROWN_DWARF = """\
<?xml version="1.0" encoding="UTF-8"?>
<Sesame>
  <Resolver name="S=Simbad">
    <oname>WISE J085510.83-071442.5</oname>
    <jpos>133.7951 -7.2451</jpos>
    <otype>BD*</otype>
  </Resolver>
</Sesame>
"""


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _mock_response(text: str, status_code: int = 200):
    mock = MagicMock()
    mock.status_code = status_code
    mock.text = text
    return mock


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_resolve_star(client):
    with patch("errante_api.routes.resolve.httpx.get") as mock_get:
        mock_get.return_value = _mock_response(_SESAME_BARNARD)
        r = client.get("/api/resolve-name", params={"name": "Barnard's star"})

    assert r.status_code == 200
    data = r.json()
    assert abs(data["ra"] - 269.4520) < 0.01
    assert abs(data["dec"] - 4.6933) < 0.01
    assert data["object_type"] == "star"
    assert data["source"] == "sesame/cfa"
    assert "Barnard" in data["resolved_name"]


def test_resolve_brown_dwarf(client):
    with patch("errante_api.routes.resolve.httpx.get") as mock_get:
        mock_get.return_value = _mock_response(_SESAME_BROWN_DWARF)
        r = client.get("/api/resolve-name", params={"name": "WISE 0855"})

    assert r.status_code == 200
    data = r.json()
    assert data["object_type"] == "brown_dwarf"


def test_resolve_name_not_found_returns_404(client):
    with patch("errante_api.routes.resolve.httpx.get") as mock_get:
        mock_get.return_value = _mock_response(_SESAME_NOT_FOUND)
        r = client.get("/api/resolve-name", params={"name": "XYZZY_NONEXISTENT_OBJECT"})

    assert r.status_code == 404


def test_resolve_upstream_404_returns_404(client):
    with patch("errante_api.routes.resolve.httpx.get") as mock_get:
        mock_get.return_value = _mock_response("", status_code=404)
        r = client.get("/api/resolve-name", params={"name": "foo"})

    assert r.status_code == 404


def test_resolve_upstream_500_returns_502(client):
    with patch("errante_api.routes.resolve.httpx.get") as mock_get:
        mock_get.return_value = _mock_response("", status_code=500)
        r = client.get("/api/resolve-name", params={"name": "foo"})

    assert r.status_code == 502


def test_resolve_timeout_returns_502(client):
    import httpx as _httpx

    with patch("errante_api.routes.resolve.httpx.get") as mock_get:
        mock_get.side_effect = _httpx.TimeoutException("timed out")
        r = client.get("/api/resolve-name", params={"name": "foo"})

    assert r.status_code == 502


def test_resolve_network_error_returns_502(client):
    import httpx as _httpx

    with patch("errante_api.routes.resolve.httpx.get") as mock_get:
        mock_get.side_effect = _httpx.ConnectError("connection refused")
        r = client.get("/api/resolve-name", params={"name": "foo"})

    assert r.status_code == 502


def test_resolve_missing_name_param(client):
    r = client.get("/api/resolve-name")
    assert r.status_code == 422  # FastAPI validation error


def test_resolve_caches_second_call(client):
    """The same name must only hit the network once."""
    with patch("errante_api.routes.resolve.httpx.get") as mock_get:
        mock_get.return_value = _mock_response(_SESAME_BARNARD)
        client.get("/api/resolve-name", params={"name": "cache_test_name"})
        client.get("/api/resolve-name", params={"name": "cache_test_name"})

    assert mock_get.call_count == 1


def test_resolve_name_in_autodoc(client):
    r = client.get("/openapi.json")
    assert "/api/resolve-name" in r.text
