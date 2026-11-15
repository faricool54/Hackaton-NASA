"""WS2: the AI-usage record (submission rule S08) stays machine-readable, honest and free of personal data."""

import json
import re
from datetime import date, datetime
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
RECORD = ROOT / "pipeline" / "errante" / "imaging" / "ai-usage.json"
PRODUCTS = ROOT / "data" / "products" / "fields"

# Keys and value types of backend/ai-usage.json (WS4's per-workstream record), which this record mirrors.
SHARED_KEYS: dict[str, type] = {
    "updated_on": str,
    "tool": str,
    "scope": str,
    "affected_paths": list,
    "generated_media": list,
    "real_target_validation": bool,
    "human_review": str,
    "repository_disclosure": str,
    "integration_validation": dict,
    "cache_revision": str,
}
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


def test_record_mirrors_the_backend_record_keys(record: dict) -> None:
    for key, kind in SHARED_KEYS.items():
        assert isinstance(record.get(key), kind), key
    assert list(record)[: len(SHARED_KEYS)] == list(SHARED_KEYS)
    date.fromisoformat(record["updated_on"])
    assert (ROOT / record["repository_disclosure"]).is_file()


def test_record_has_no_email_addresses() -> None:
    assert EMAIL.search(RECORD.read_text(encoding="utf-8")) is None


def test_record_claims_no_generated_media_and_no_line_by_line_review(record: dict) -> None:
    assert record["generated_media"] == []
    assert record["nasa_branding_generated"] is False
    assert record["line_by_line_human_review"] is False
    assert record["rendered_products"]["ai_generated_imagery"] is False
    assert record["integration_validation"]["scientific_R05_validation"] is False


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


def test_rendered_products_are_the_published_real_fields(record: dict) -> None:
    published = sorted(p.parent.name for p in PRODUCTS.glob("*/field.json"))
    assert record["rendered_products"]["fields"] == published
    for field_id in published:
        field = json.loads((PRODUCTS / field_id / "field.json").read_text(encoding="utf-8"))
        assert field["provenance"]["synthetic"] is False, field_id
