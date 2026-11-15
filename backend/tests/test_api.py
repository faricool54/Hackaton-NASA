import pytest
from fastapi.testclient import TestClient

from errante import settings as core
from errante_api.main import create_app
from errante_api.settings import Settings


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    config = Settings(data_dir=core.DEMO_DIR, live_cache_dir=tmp_path_factory.mktemp("api-cache"))
    with TestClient(create_app(config)) as client:
        yield client


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


def test_showcase_hides_job_fields_without_changing_the_persisted_catalog(tmp_path):
    import shutil

    from errante.products import ProductStore

    products = tmp_path / "products"
    shutil.copytree(core.DEMO_DIR, products)
    store = ProductStore(products)
    original = store.read_manifest()
    visible = original.fields[0].model_copy(update={"synthetic": False})
    job = visible.model_copy(update={"id": "job-smoke-test", "synthetic": True})
    # Isolate the showcase flag from the synthetic systems in the demo fixture.
    manifest = original.model_copy(update={"fields": [job, visible], "systems": [], "synthetic": True})
    store.manifest_path.write_text(manifest.model_dump_json(), encoding="utf-8")
    before = store.manifest_path.read_bytes()
    config = Settings(data_dir=products, live_cache_dir=tmp_path / "cache")
    with TestClient(create_app(config)) as api:
        showcase = api.get("/api/manifest").json()
        assert [field["id"] for field in showcase["fields"]] == [visible.id]
        assert showcase["synthetic"] is False
        complete = api.get("/api/manifest", params={"include_jobs": True}).json()
        assert [field["id"] for field in complete["fields"]] == [job.id, visible.id]
        assert complete["synthetic"] is True
        assert api.get("/api/manifest", params={"include_jobs": "invalid"}).status_code == 422
    assert store.manifest_path.read_bytes() == before


def test_live_endpoints_report_not_implemented_cleanly(client, monkeypatch):
    def unavailable(*args, **kwargs):
        raise NotImplementedError("test stub")

    monkeypatch.setattr("errante.data.irsa.search_frames", unavailable)
    r = client.get("/api/search", params={"ra": 10, "dec": 10})
    assert r.status_code == 501


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
