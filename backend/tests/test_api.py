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


def test_systems_roundtrip(client):
    manifest = client.get("/api/manifest").json()
    assert manifest["systems"], "demo data should include 3D systems"
    sid = manifest["systems"][0]["id"]
    system = client.get(f"/api/systems/{sid}").json()
    assert system["id"] == sid and system["bodies"]
    assert client.get("/api/systems/nope").status_code == 404


def test_systems_only_products_do_not_hide_the_demo(tmp_path, monkeypatch):
    """`errante systems` writes a manifest with zero fields: the backend must keep serving the demo."""
    from errante.products import ProductStore
    from errante.systems.build import write_systems
    from errante.systems.catalog import curated_systems

    store = ProductStore(tmp_path)
    write_systems(store, curated_systems())
    store.rebuild_manifest()
    monkeypatch.delenv("ERRANTE_DATA_DIR", raising=False)
    monkeypatch.setattr(core, "PRODUCTS_DIR", tmp_path)
    assert Settings.from_env().data_dir == core.DEMO_DIR
