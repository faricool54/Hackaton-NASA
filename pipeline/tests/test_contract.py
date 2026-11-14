"""The committed demo data and schema must always match the contract."""

import json
from pathlib import Path

import jsonschema
import pytest

from errante import settings
from errante.cli import main
from errante.models import ALL_MODELS, SCHEMA_VERSION, JobStatusResponse, JobSubmitRequest, SkyField
from errante.products import ProductStore

SCHEMA_DIR = settings.REPO_ROOT / "shared" / "schema"


def test_schema_is_up_to_date():
    assert main(["schema", "--check", "--out", str(SCHEMA_DIR)]) == 0


def test_frontend_contract_version_matches_pipeline():
    types = (settings.REPO_ROOT / "frontend/src/api/types.ts").read_text(encoding="utf-8")
    assert f"export const SCHEMA_VERSION = '{SCHEMA_VERSION}';" in types


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


@pytest.mark.parametrize(
    "changes",
    [
        {"ra": 360},
        {"ra": float("nan")},
        {"dec": -91},
        {"size_deg": 1},
        {"detectors": [7]},
        {"max_frames": 1},
        {"max_frames": 2.5},
        {"mjd_min": float("inf")},
        {"mjd_min": 60001, "mjd_max": 60000},
    ],
)
def test_job_request_rejects_unbounded_or_invalid_builds(changes):
    with pytest.raises(ValueError):
        JobSubmitRequest.model_validate({"ra": 269.45, "dec": 4.77, **changes})


def test_job_wire_examples_match_published_schemas():
    request = JobSubmitRequest(ra=269.45, dec=4.77)
    assert request.max_frames == 40
    examples = {
        "JobSubmitRequest": request.model_dump(mode="json"),
        "JobStatusResponse": JobStatusResponse(
            id="job-id",
            status="ready",
            stage="ready",
            result_field_id="real-field",
            created_at="2026-11-14T20:00:00Z",
            updated_at="2026-11-14T20:01:00Z",
        ).model_dump(mode="json"),
    }
    for name, data in examples.items():
        jsonschema.validate(data, json.loads((SCHEMA_DIR / f"{name}.schema.json").read_text()))
    with pytest.raises(ValueError):
        JobStatusResponse.model_validate({**examples["JobStatusResponse"], "status": "publishing"})
