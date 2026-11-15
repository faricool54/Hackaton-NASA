"""Full-stack delivery and persistent seed regression tests; never contact archives."""

import shutil

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from errante import settings as core
from errante.models import FrameFlagSummary
from errante.products import ProductStore
from errante_api import comparison_snapshots
from errante_api.bootstrap import seed_products
from errante_api.main import create_app
from errante_api.settings import Settings


def test_real_runtime_seed_is_idempotent_and_preserves_new_products(tmp_path):
    seed = tmp_path / "runtime"
    seed_products(core.PRODUCTS_DIR, seed)
    manifest = ProductStore(seed).read_manifest()
    assert not manifest.synthetic and len(manifest.fields) == 5
    extra = seed / "analyses" / "user-result.json"
    extra.parent.mkdir()
    extra.write_bytes(b"user result")
    original = (seed / "manifest.json").read_bytes()
    seed_products(core.PRODUCTS_DIR, seed)
    assert extra.read_bytes() == b"user result" and (seed / "manifest.json").read_bytes() == original
    (seed / "manifest.json").write_text("broken")
    with pytest.raises(ValueError):
        seed_products(core.PRODUCTS_DIR, seed)
    assert (seed / "manifest.json").read_text() == "broken"


def test_production_seed_rejects_synthetic_and_overlapping_paths(tmp_path):
    with pytest.raises(ValueError, match="real fields"):
        seed_products(core.DEMO_DIR, tmp_path / "runtime")
    with pytest.raises(ValueError, match="separate"):
        seed_products(core.PRODUCTS_DIR, core.PRODUCTS_DIR)


def test_seed_adds_curated_flags_without_replacing_a_different_build(tmp_path):
    source = tmp_path / "source"
    runtime = tmp_path / "runtime"
    seed_products(core.PRODUCTS_DIR, source)
    seed_products(source, runtime)

    source_store, runtime_store = ProductStore(source), ProductStore(runtime)
    barnard = source_store.read_field("barnards-star")
    legacy = runtime_store.read_field("barnards-star")
    frame_id = legacy.frames[0].id
    legacy.frame_flags.pop(frame_id, None)
    runtime_store.write_field(legacy)
    flags = FrameFlagSummary(coverage_fraction=1, fractions={"OVERFLOW": 0.02, "GHOST": 0})
    barnard.frame_flags[frame_id] = flags
    source_store.write_field(barnard)

    replaced = runtime_store.read_field("r-draconis")
    replaced.provenance.built_at = replaced.provenance.built_at.replace(year=2027)
    replaced.frame_flags.clear()
    runtime_store.write_field(replaced)
    replacement_path = runtime_store.field_dir(replaced.id) / "field.json"
    replacement_bytes = replacement_path.read_bytes()

    seed_products(source, runtime)
    assert runtime_store.read_field("barnards-star").frame_flags[frame_id] == flags
    assert replacement_path.read_bytes() == replacement_bytes
    app = create_app(Settings(data_dir=runtime, live_cache_dir=tmp_path / "cache"))
    with TestClient(app) as client:
        assert client.get("/api/fields/barnards-star").json()["frame_flags"][frame_id] == flags.model_dump()
        assert client.get("/api/fields/r-draconis").json()["frame_flags"] == {}


def test_frontend_fallback_preserves_api_data_and_asset_errors(tmp_path):
    web = tmp_path / "web"
    web.mkdir()
    (web / "index.html").write_text("<!doctype html><title>Explicit frontend fixture</title>")
    (web / "assets").mkdir()
    (web / "assets" / "app.js").write_text("console.log('fixture')")
    data = tmp_path / "public"
    seed_products(core.PRODUCTS_DIR, data)
    app = create_app(Settings(data_dir=data, live_cache_dir=tmp_path / "private", web_dir=web))
    with TestClient(app) as client:
        assert client.get("/").status_code == 200
        assert "frontend fixture" in client.get("/fields/barnards-star").text
        assert client.get("/assets/app.js").status_code == 200
        for path in ("/api/unknown", "/api/fields/unknown", "/data/missing", "/assets/missing", "/unknown.js"):
            assert client.get(path).status_code == 404, path
        assert client.get("/api/manifest").json()["synthetic"] is False
        field = client.get("/api/fields/barnards-star").json()
        assert client.get("/data/fields/barnards-star/" + field["frames"][0]["image"]).status_code == 200
        assert client.get("/api/lightcurves/r-draconis").status_code == 200


def test_invalid_frontend_fails_at_startup(tmp_path):
    with pytest.raises(ValueError, match="index.html"):
        create_app(Settings(data_dir=tmp_path / "public", live_cache_dir=tmp_path / "private", web_dir=tmp_path))


def test_interrupted_initial_seed_does_not_publish_manifest(tmp_path, monkeypatch):
    real_copy = shutil.copytree

    def interrupted(*args, **kwargs):
        real_copy(*args, **kwargs)
        raise OSError("simulated interrupted copy")

    monkeypatch.setattr("errante_api.bootstrap.shutil.copytree", interrupted)
    public = tmp_path / "public"
    with pytest.raises(OSError):
        seed_products(core.PRODUCTS_DIR, public)
    assert not (public / "manifest.json").exists()
    monkeypatch.setattr("errante_api.bootstrap.shutil.copytree", real_copy)
    seed_products(core.PRODUCTS_DIR, public)
    assert len(ProductStore(public).read_manifest().fields) == 5


def test_all_real_comparison_snapshots_and_pngs_are_available_offline(tmp_path, monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("A snapshot GET must not download or compute anything")

    monkeypatch.setattr("errante_api.science_ops.comparisons", forbidden)
    app = create_app(Settings(data_dir=core.PRODUCTS_DIR, live_cache_dir=tmp_path / "private"))
    with TestClient(app) as client:
        for field in ProductStore(core.PRODUCTS_DIR).read_manifest().fields:
            response = client.get(f"/api/fields/{field.id}/comparisons")
            assert response.status_code == 200, response.text
            result = response.json()
            assert result["images"] and not result["synthetic"]
            assert any(i["kind"] == "scaled_difference" for i in result["images"])
            png = client.get("/data/" + result["images"][0]["image"])
            assert png.status_code == 200 and png.content.startswith(b"\x89PNG\r\n\x1a\n")


def test_damaged_or_stale_snapshot_does_not_silently_fall_back(tmp_path, monkeypatch):
    import json

    public = tmp_path / "public"
    seed_products(core.PRODUCTS_DIR, public)
    field = ProductStore(public).read_field("barnards-star")
    original = comparison_snapshots.read_snapshot(public, field)
    path = public / "fields" / field.id / "comparisons.json"
    path.write_text("broken /private/path")
    with pytest.raises(HTTPException) as caught:
        comparison_snapshots.read_snapshot(public, field)
    assert caught.value.status_code == 503
    doc = original.model_dump(mode="json")
    doc["field_built_at"] = "2000-01-01T00:00:00Z"
    path.write_text(json.dumps(doc))
    with pytest.raises(HTTPException) as caught:
        comparison_snapshots.read_snapshot(public, field)
    assert caught.value.status_code == 409
    path.unlink()
    monkeypatch.setattr(comparison_snapshots, "BUNDLE", tmp_path / "missing-bundle")
    with pytest.raises(HTTPException) as caught:
        comparison_snapshots.read_snapshot(public, field)
    assert caught.value.status_code == 404


def test_static_export_keeps_manifest_and_contains_typed_products_and_pngs(tmp_path):
    import json
    import runpy

    module = runpy.run_path(str(core.REPO_ROOT / "scripts/export_static_science.py"))
    manifest = tmp_path / "manifest.json"
    manifest.write_bytes(b"sentinel")
    module["export"](tmp_path)
    assert manifest.read_bytes() == b"sentinel"
    products = json.loads((tmp_path / "lightcurves.json").read_text())["products"]
    assert {p["target_id"] for p in products} == {"rw-aurigae", "r-draconis"}
    assert len(list((tmp_path / "fields").glob("*/comparisons.json"))) == 5
    assert len(list((tmp_path / "analyses").glob("*/compare/*.png"))) == 196
