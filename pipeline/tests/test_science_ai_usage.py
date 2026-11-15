"""WS3: the AI-usage record (submission rule S08) stays machine-readable, honest and free of personal data."""

import json
import re
from datetime import date, datetime
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
RECORD = ROOT / "pipeline" / "errante" / "science" / "ai-usage.json"
# WS4's per-workstream record: this record mirrors its keys and value types.
BACKEND_RECORD = ROOT / "backend" / "ai-usage.json"
# rpccp's record of #102 (OpenAI Codex), which changed WS3 files after this work: referenced, never claimed here.
CONTINUUM_RECORD = "pipeline/errante/science/continuum-ai-usage.json"
CONTINUUM_PR = 102
CONTINUUM_ONLY_PATHS = (
    "pipeline/errante/science/continuum.py",
    "pipeline/tests/test_science_continuum.py",
    "pipeline/tests/fixtures/ws3/continuum/",
)
PR_KEYS = ("number", "title", "merged_at", "ai_generated", "humans")
EMAIL = re.compile(r"[\w.+-]+@[\w-]+(\.[\w-]+)+")
# Paths WS3 owns: they must exist. Other workstreams may rename theirs, so only their form is checked.
WS3_PREFIXES = (
    "pipeline/errante/science/",
    "pipeline/errante/config/",
    "pipeline/tests/test_science_",
    "pipeline/tests/fixtures/ws3/",
    "docs/SCIENCE.md",
    "tasks/WS3-",
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
    assert record["workstream"] == "WS3"


def test_record_has_no_email_addresses() -> None:
    assert EMAIL.search(RECORD.read_text(encoding="utf-8")) is None


def test_record_claims_no_generated_media_review_or_validation(record: dict) -> None:
    assert record["generated_media"] == []
    assert record["nasa_branding_generated"] is False
    assert record["line_by_line_human_review"] is False
    assert record["committed_data"]["ai_generated_values"] is False
    assert record["committed_data"]["synthetic"] is False
    assert record["integration_validation"]["scientific_R05_validation"] is False
    assert record["real_target_validation"] is False
    assert record["real_target_validation_basis"]


def test_pull_requests_are_unique_and_complete(record: dict) -> None:
    prs = record["pull_requests"]
    numbers = [pr["number"] for pr in prs]
    assert numbers == sorted(set(numbers))
    for pr in prs:
        assert all(pr.get(key) for key in PR_KEYS), pr.get("number")
        assert isinstance(pr["number"], int) and isinstance(pr["ai_generated"], list), pr["number"]
        datetime.fromisoformat(pr["merged_at"].replace("Z", "+00:00"))


def test_affected_paths_are_repo_relative_and_ws3_paths_exist(record: dict) -> None:
    paths = record["affected_paths"] + record["committed_data"]["paths"]
    for path in paths:
        assert "\\" not in path and ".." not in path.split("/") and not path.startswith("/"), path
        if path.startswith(WS3_PREFIXES):
            assert (ROOT / path).exists(), path
    # The committed data the record describes is listed among the affected paths.
    assert set(record["committed_data"]["paths"]) <= set(record["affected_paths"])


def test_other_developers_work_on_ws3_files_is_referenced_not_claimed(record: dict) -> None:
    assert CONTINUUM_PR not in [pr["number"] for pr in record["pull_requests"]]
    assert (ROOT / CONTINUUM_RECORD).is_file()
    assert CONTINUUM_RECORD not in record["affected_paths"]
    paths = record["affected_paths"] + record["committed_data"]["paths"]
    assert not [p for p in paths if p.startswith(CONTINUUM_ONLY_PATHS)]
    # The record says where that work is recorded, and does not list its tool as one of its own.
    assert CONTINUUM_RECORD in record["related_work_note"] and CONTINUUM_RECORD in record["human_review"]
    assert record["other_ai_tools"] == []
