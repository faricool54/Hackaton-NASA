import pytest
from fastapi.testclient import TestClient

from errante import settings as core
from errante_api.main import create_app
from errante_api.settings import Settings


@pytest.fixture(scope="module")
def client():
    return TestClient(create_app(Settings(data_dir=core.DEMO_DIR)))


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
    assert r.json()["synthetic"] is True


def test_manifest_and_field_roundtrip(client):
    manifest = client.get("/api/manifest").json()
    assert manifest["fields"]
    fid = manifest["fields"][0]["id"]
    field = client.get(f"/api/fields/{fid}").json()
    assert field["id"] == fid and field["frames"]
    img = client.get(f"/data/fields/{fid}/{field['frames'][0]['image']}")
    assert img.status_code == 200 and img.headers["content-type"] == "image/png"
    assert client.get(f"/api/fields/{fid}/candidates").json()["field_id"] == fid
    assert client.get(f"/api/fields/{fid}/known").json()["field_id"] == fid


def test_unknown_field_is_404(client):
    assert client.get("/api/fields/nope").status_code == 404


def test_live_endpoints_report_not_implemented_cleanly(client):
    r = client.get("/api/search", params={"ra": 10, "dec": 10})
    assert r.status_code in (200, 501, 502, 504)
