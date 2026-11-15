"""WS2: the AI-usage record (submission rule S08) stays machine-readable, honest and free of personal data."""

import json
import re
from datetime import date, datetime
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
RECORD = ROOT / "pipeline" / "errante" / "imaging" / "ai-usage.json"
# WS4's per-workstream record: this record mirrors its keys and value types.
BACKEND_RECORD = ROOT / "backend" / "ai-usage.json"
PRODUCTS = ROOT / "data" / "products" / "fields"
OFFICIAL_TARGETS = ("barnards-star", "eps-indi-b", "r-draconis", "rw-aurigae", "wise-0855")
PR_KEYS = ("number", "title", "merged_at", "ai_generated", "humans")
EMAIL = re.compile(r"[\w.+-]+@[\w-]+(\.[\w-]+)+")
# Paths WS2 owns: they must exist. Other workstreams may rename theirs, so only their form is checked.
WS2_PREFIXES = (
    "pipeline/errante/imaging/",
    "pipeline/errante/detect/",
    "pipeline/errante/build.py",
    "pipeline/tests/test_imaging_",
    "pipeline/tests/test_build_",
    "data/products/",
    "tasks/WS2-",
)


@pytest.fixture(scope="module")
def record() -> dict:
    return json.loads(RECORD.read_text(encoding="utf-8"))


def _assert_mirrors(mine: dict, theirs: dict, where: str = "") -> None:
    """Every key of `theirs` is in `mine` with a value of the same JSON type, recursively for objects."""
    for key, value in theirs.items():
        assert key in mine, f"missing {where}{key}"
        kind, expected = type(mine[key]).__name__, type(value).__name__
        assert kind == expected, f"{where}{key}: {kind} instead of {expected}"
        if isinstance(value, dict):
            _assert_mirrors(mine[key], value, f"{where}{key}.")


def test_record_mirrors_the_backend_record_keys(record: dict) -> None:
    backend = json.loads(BACKEND_RECORD.read_text(encoding="utf-8"))
    assert backend
    _assert_mirrors(record, backend)
    date.fromisoformat(record["updated_on"])
    assert (ROOT / record["repository_disclosure"]).is_file()


def test_record_has_no_email_addresses() -> None:
    assert EMAIL.search(RECORD.read_text(encoding="utf-8")) is None


def test_record_claims_no_generated_media_review_or_validation(record: dict) -> None:
    assert record["generated_media"] == []
    assert record["nasa_branding_generated"] is False
    assert record["line_by_line_human_review"] is False
    assert record["rendered_products"]["ai_generated_imagery"] is False
    assert record["integration_validation"]["scientific_R05_validation"] is False
    assert record["real_target_validation"] is False
    assert record["real_target_validation_basis"]


def test_pull_requests_are_unique_and_complete(record: dict) -> None:
    prs = record["pull_requests"]
    numbers = [pr["number"] for pr in prs]
    assert numbers == sorted(set(numbers))
    for pr in prs:
        assert all(pr.get(key) for key in PR_KEYS), pr.get("number")
        datetime.fromisoformat(pr["merged_at"].replace("Z", "+00:00"))


def test_affected_paths_are_repo_relative_and_ws2_paths_exist(record: dict) -> None:
    for path in record["affected_paths"]:
        assert "\\" not in path and ".." not in path.split("/") and not path.startswith("/"), path
        if path.startswith(WS2_PREFIXES):
            assert (ROOT / path).exists(), path


def test_rendered_products_are_real_published_fields_with_the_official_targets(record: dict) -> None:
    listed = record["rendered_products"]["fields"]
    assert len(listed) == len(set(listed))
    assert set(OFFICIAL_TARGETS) <= set(listed)
    for field_id in listed:
        path = PRODUCTS / field_id / "field.json"
        assert path.is_file(), field_id
        provenance = json.loads(path.read_text(encoding="utf-8"))["provenance"]
        assert provenance["synthetic"] is False, field_id
        # The record says display-only repairs are disclosed in each field's notes.
        assert any("for display only" in note for note in provenance["notes"]), field_id
