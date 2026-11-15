"""The committed demo data and schema must always match the contract."""

import json
import shutil
from pathlib import Path

import jsonschema
import pytest

from errante import settings
from errante.cli import main
from errante.models import (
    ALL_MODELS,
    SCHEMA_VERSION,
    Composite,
    CompositeChannel,
    JobStatusResponse,
    JobSubmitRequest,
    SkyField,
)
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


# --- False-color composites (contract 0.3.1) --------------------------------

TYPES_TS = settings.REPO_ROOT / "frontend" / "src" / "api" / "types.ts"


def _channel(color: str, detector: int | None, lam: float | None, frame_ids: list[str]) -> dict:
    return {
        "color": color,
        "detector": detector,
        "wavelength_um": lam,
        "wavelength_min_um": None if lam is None else lam - 0.05,
        "wavelength_max_um": None if lam is None else lam + 0.05,
        "frame_ids": frame_ids,
    }


def _composite(**overrides) -> dict:
    data = {
        "id": "detectors_S0",
        "mode": "detectors",
        "season": 0,
        "mjd_min": 60810.1,
        "mjd_max": 60811.4,
        "image": "color/detectors_S0.png",
        "channels": [
            _channel("red", None, 4.1, ["SYN05D2"]),
            _channel("green", 3, 2.0, ["SYN03D2", "SYN04D2"]),
            _channel("blue", 1, 0.9, ["SYN00D2"]),
        ],
        "notes": ["False color: infrared wavelengths mapped to RGB."],
    }
    data.update(overrides)
    return data


def _demo_field_dict() -> dict:
    return json.loads((settings.REPO_ROOT / "data" / "demo" / "fields" / "demo-ecliptic" / "field.json").read_text())


def test_field_without_composites_key_defaults_to_empty_list():
    """Products written before 0.3.1 (no 'composites' key) stay valid and read as []."""
    data = _demo_field_dict()
    data.pop("composites", None)
    field = SkyField.model_validate(data)
    assert field.composites == []
    assert json.loads(field.model_dump_json())["composites"] == []


def test_composite_round_trip_and_json_schema():
    data = _demo_field_dict()
    data["composites"] = [_composite(), _composite(id="jhk_S0", mode="jhk", image="color/jhk_S0.png")]
    field = SkyField.model_validate(data)
    assert [c.id for c in field.composites] == ["detectors_S0", "jhk_S0"]
    assert [ch.color for ch in field.composites[0].channels] == ["red", "green", "blue"]
    assert field.composites[0].channels[0].detector is None  # mixed detectors

    dumped = field.model_dump_json()
    assert SkyField.model_validate_json(dumped) == field
    schema = json.loads((SCHEMA_DIR / "Field.schema.json").read_text())
    jsonschema.validate(json.loads(dumped), schema)


@pytest.mark.parametrize("n_channels", [0, 2, 4])
def test_composite_needs_exactly_three_channels(n_channels):
    channels = [_channel(c, 1, 1.0, ["SYN00D2"]) for c in ("red", "green", "blue", "red")][:n_channels]
    with pytest.raises(ValueError, match="channels"):
        Composite.model_validate(_composite(channels=channels))
    # The published JSON Schema enforces the count too (raw JSON readers, e.g. the frontend tests).
    schema = json.loads((SCHEMA_DIR / "Field.schema.json").read_text())
    data = _demo_field_dict()
    data["composites"] = [_composite(channels=channels)]
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(data, schema)


@pytest.mark.parametrize("colors", [["blue", "green", "red"], ["red", "red", "blue"], ["red", "green", "green"]])
def test_composite_channels_must_be_red_green_blue_in_order(colors):
    channels = [_channel(c, 1, 1.0, ["SYN00D2"]) for c in colors]
    with pytest.raises(ValueError, match="red, green, blue"):
        Composite.model_validate(_composite(channels=channels))


def test_composite_rejects_inverted_ranges_and_bad_values():
    with pytest.raises(ValueError, match="mjd_min"):
        Composite.model_validate(_composite(mjd_min=60812.0, mjd_max=60811.0))
    bad = _channel("red", 4, 3.0, ["SYN05D2"]) | {"wavelength_min_um": 3.5, "wavelength_max_um": 2.5}
    with pytest.raises(ValueError, match="wavelength_min_um"):
        CompositeChannel.model_validate(bad)
    with pytest.raises(ValueError, match="detector"):
        CompositeChannel.model_validate(_channel("red", 7, 3.0, ["SYN05D2"]))
    with pytest.raises(ValueError, match="frame_ids"):
        CompositeChannel.model_validate(_channel("red", 4, 3.0, []))
    with pytest.raises(ValueError, match="season"):
        Composite.model_validate(_composite(season=-1))
    with pytest.raises(ValueError, match="mode"):
        Composite.model_validate(_composite(mode="true_color"))


def test_composite_ids_are_unique_within_a_field():
    data = _demo_field_dict()
    data["composites"] = [_composite(), _composite()]
    with pytest.raises(ValueError, match="detectors_S0"):
        SkyField.model_validate(data)


def test_cli_validate_reports_missing_composite_image(tmp_path):
    root = tmp_path / "products"
    shutil.copytree(settings.REPO_ROOT / "data" / "demo", root)
    store = ProductStore(root)
    field = store.read_field("demo-ecliptic")
    store.write_field(field.model_copy(update={"composites": [Composite.model_validate(_composite())]}))
    assert main(["validate", "--dir", str(root)]) == 1  # color/detectors_S0.png does not exist

    png = store.field_dir("demo-ecliptic") / "color" / "detectors_S0.png"
    png.parent.mkdir(parents=True)
    shutil.copy(store.field_dir("demo-ecliptic") / "thumb.png", png)
    assert main(["validate", "--dir", str(root)]) == 0


def test_frontend_types_declare_the_same_schema_version():
    assert f"export const SCHEMA_VERSION = '{SCHEMA_VERSION}';" in TYPES_TS.read_text(encoding="utf-8")


@pytest.mark.parametrize(
    "image",
    ["../x.png", "/abs.png", "C:/x.png", "color\\x.png", "a/../../b.png", "color//x.png", "color/x.png?y=1", "x.jpg"],
)
def test_composite_image_must_stay_inside_the_field_directory(image):
    from errante.models import Composite, CompositeChannel

    def ch(color):
        return CompositeChannel(
            color=color, frame_ids=["a"], wavelength_um=1.0, wavelength_min_um=0.9, wavelength_max_um=1.1
        )

    with pytest.raises(ValueError):
        Composite(id="detectors_S0", mode="detectors", season=0, mjd_min=1, mjd_max=2, image=image,
                  channels=[ch("red"), ch("green"), ch("blue")])  # fmt: skip


def test_composite_channel_mean_wavelength_must_lie_in_its_range_and_ids_are_slugs():
    from errante.models import Composite, CompositeChannel

    with pytest.raises(ValueError, match="outside"):
        CompositeChannel(color="red", frame_ids=["a"], wavelength_um=2.0, wavelength_min_um=0.9, wavelength_max_um=1.1)
    ch = [CompositeChannel(color=c, frame_ids=["a"]) for c in ("red", "green", "blue")]
    ok = Composite(id="jhk_S1", mode="jhk", season=1, mjd_min=1, mjd_max=2, image="color/jhk_S1.png", channels=ch)
    assert ok.image == "color/jhk_S1.png"
    with pytest.raises(ValueError):
        Composite(id="a/b", mode="jhk", season=1, mjd_min=1, mjd_max=2, image="color/jhk_S1.png", channels=ch)
