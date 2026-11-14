"""Batch orchestration tested with explicit pipeline doubles, never network data."""

import json
import subprocess
from types import SimpleNamespace

import pytest
from PIL import Image

from errante import settings
from errante.models import CandidateList, KnownObjectList
from errante.products import ProductStore
from errante_api import batch


def write_test_field(root, field_id):
    # Artificial test data only; not an observation or validation of a real target.
    demo = ProductStore(settings.DEMO_DIR)
    field = demo.read_field(demo.read_manifest().fields[0].id).model_copy(deep=True)
    field.id = field_id
    field.provenance.synthetic = False
    field.frames = field.frames[:2]
    store = ProductStore(root)
    for i, frame in enumerate(field.frames):
        frame.detector = 1
        frame.mjd = 61000 + 100 * i
        frame.source_uri = "test-double-only"
        path = store.field_dir(field_id) / frame.image
        path.parent.mkdir(parents=True, exist_ok=True)
        Image.new("L", (field.grid.width_px, field.grid.height_px)).save(path)
    store.write_field(field)
    store.write_candidates(CandidateList(field_id=field_id, candidates=[]))
    store.write_known(KnownObjectList(field_id=field_id, objects=[]))
    return field


def fake_build(command, **kwargs):
    from pathlib import Path

    assert "--analyze" not in command
    assert kwargs["timeout"] > 0
    write_test_field(Path(command[-1]), command[-3])
    return SimpleNamespace(returncode=0)


def test_batch_publishes_only_validated_fields_and_preserves_other_products(tmp_path, monkeypatch):
    monkeypatch.setattr(batch.subprocess, "run", fake_build)
    store = ProductStore(tmp_path / "products")
    write_test_field(store.root, "existing")
    report = batch.build_fields(store.root, targets=batch.TARGETS[:2])
    assert [f["status"] for f in report["fields"]] == ["ready", "ready"]
    assert {f.id for f in store.read_manifest().fields} == {"existing", *batch.TARGETS[:2]}
    assert not (store.root / ".build.lock").exists()


def test_failure_or_timeout_continues_and_preserves_old_field(tmp_path, monkeypatch):
    out = tmp_path / "products"
    write_test_field(out, batch.TARGETS[0])
    original = (out / "fields" / batch.TARGETS[0] / "field.json").read_bytes()

    def child(command, **kwargs):
        if command[-3] == batch.TARGETS[0]:
            return SimpleNamespace(returncode=3)
        raise subprocess.TimeoutExpired(command, kwargs["timeout"])

    monkeypatch.setattr(batch.subprocess, "run", child)
    report = batch.build_fields(out, targets=batch.TARGETS[:2])
    assert [f["error"] for f in report["fields"]] == ["pipeline_not_ready", "timeout"]
    assert (out / "fields" / batch.TARGETS[0] / "field.json").read_bytes() == original


def test_invalid_new_field_does_not_replace_old_field(tmp_path, monkeypatch):
    out = tmp_path / "products"
    write_test_field(out, batch.TARGETS[0])
    original = (out / "fields" / batch.TARGETS[0] / "field.json").read_bytes()

    def child(command, **kwargs):
        from pathlib import Path

        root = Path(command[-1])
        field = write_test_field(root, command[-3])
        field.frames[1].mjd = field.frames[0].mjd
        ProductStore(root).write_field(field)
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(batch.subprocess, "run", child)
    report = batch.build_fields(out, targets=batch.TARGETS[:1])
    assert report["fields"][0]["status"] == "failed"
    assert (out / "fields" / batch.TARGETS[0] / "field.json").read_bytes() == original


def test_manifest_failure_rolls_back_existing_field(tmp_path, monkeypatch):
    out = tmp_path / "products"
    old = write_test_field(out, batch.TARGETS[0])
    old.description = "previous product"
    ProductStore(out).write_field(old)
    monkeypatch.setattr(batch.subprocess, "run", fake_build)

    def broken(*args):
        raise OSError("disk unavailable")

    monkeypatch.setattr(batch.AtomicProductStore, "rebuild_manifest", broken)
    assert batch.build_fields(out, targets=batch.TARGETS[:1])["fields"][0]["status"] == "failed"
    assert ProductStore(out).read_field(batch.TARGETS[0]).description == "previous product"


def test_cli_nonzero_on_missing_pipeline_and_lock_is_respected(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(batch.subprocess, "run", lambda *a, **k: SimpleNamespace(returncode=3))
    assert batch.main(["--out", str(tmp_path), "--field", batch.TARGETS[0]]) == 1
    assert json.loads(capsys.readouterr().out)["fields"][0]["error"] == "pipeline_not_ready"
    (tmp_path / ".build.lock").touch()
    assert batch.main(["--out", str(tmp_path)]) == 2
    assert (tmp_path / ".build.lock").exists()
    with pytest.raises(ValueError):
        batch.build_fields(tmp_path, targets=["../outside"])


def test_failed_restore_retains_previous_product_for_recovery(tmp_path, monkeypatch):
    from pathlib import Path

    out = tmp_path / "products"
    old = write_test_field(out, batch.TARGETS[0])
    old.description = "retain this product"
    ProductStore(out).write_field(old)
    monkeypatch.setattr(batch.subprocess, "run", fake_build)
    original_replace = batch.os.replace

    def replace(source, destination):
        if Path(source).name == "previous":
            raise OSError("restore blocked")
        return original_replace(source, destination)

    def broken(*args):
        raise OSError("manifest write failed")

    monkeypatch.setattr(batch.os, "replace", replace)
    monkeypatch.setattr(batch.AtomicProductStore, "rebuild_manifest", broken)
    item = batch.build_fields(out, targets=batch.TARGETS[:1])["fields"][0]
    assert item["status"] == "failed"
    preserved = Path(item["recovery_dir"]) / "previous" / "field.json"
    assert json.loads(preserved.read_text())["description"] == "retain this product"
