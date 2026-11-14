"""The committed demo data and schema must always match the contract."""

import json
from pathlib import Path

import jsonschema
import pytest

from errante import settings
from errante.cli import main
from errante.models import ALL_MODELS, SkyField
from errante.products import ProductStore

SCHEMA_DIR = settings.REPO_ROOT / "shared" / "schema"


def test_schema_is_up_to_date():
    assert main(["schema", "--check", "--out", str(SCHEMA_DIR)]) == 0


@pytest.mark.parametrize("name", list(ALL_MODELS))
def test_schema_files_are_valid_json_schema(name):
    schema = json.loads((SCHEMA_DIR / f"{name}.schema.json").read_text())
    jsonschema.Draft202012Validator.check_schema(schema)


def _validate(path: Path, name: str):
    schema = json.loads((SCHEMA_DIR / f"{name}.schema.json").read_text())
    jsonschema.validate(json.loads(path.read_text()), schema)


def test_committed_demo_matches_json_schema():
    """What the frontend reads (raw JSON) validates against the published schema."""
    store = ProductStore(settings.REPO_ROOT / "data" / "demo")
    _validate(store.manifest_path, "Manifest")
    for fs in store.read_manifest().fields:
        d = store.field_dir(fs.id)
        _validate(d / "field.json", "Field")
        _validate(d / "candidates.json", "CandidateList")
        _validate(d / "known.json", "KnownObjectList")
    for ss in store.read_manifest().systems:
        _validate(store.system_path(ss.id), "SystemModel")


def test_committed_demo_passes_cli_validate():
    assert main(["validate", "--dir", str(settings.REPO_ROOT / "data" / "demo")]) == 0


def test_field_id_must_be_slug():
    store = ProductStore(settings.REPO_ROOT / "data" / "demo")
    data = store.read_field("demo-ecliptic").model_dump()
    SkyField.model_validate(data)  # valid as is
    data["id"] = "Not A Slug"
    with pytest.raises(ValueError, match="id"):
        SkyField.model_validate(data)
