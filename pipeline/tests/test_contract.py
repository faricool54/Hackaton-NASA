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
    ComparisonImage,
    ComparisonRequest,
    Composite,
    CompositeChannel,
    JobStatusResponse,
    JobSubmitRequest,
    LightCurveData,
    LightCurveParameters,
    LightCurvePeriod,
    LightCurveProduct,
    SkyField,
    SpectralMeasurement,
    SpectrumRequest,
    SpectrumResponse,
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


@pytest.mark.parametrize(
    "extra",
    [
        {"mjd_min": 60000},
        {"ra": 360},
        {"dec": float("nan")},
        {"max_frames": 61},
        {"aperture_px": 4},
        {"field_id": "../secret"},
        {"source": "l2_exposures", "aperture_px": 2},
        {"source": "l2_exposures", "mjd_min": 60001, "mjd_max": 60000},
    ],
)
def test_spectrum_selection_is_bounded_and_source_aware(extra):
    with pytest.raises(ValueError):
        SpectrumRequest.model_validate({"ra": 10, "dec": 0, **extra})


def test_spectrum_does_not_invent_errors_or_drop_negative_flux():
    point = SpectralMeasurement(id="p1", detector=1, wavelength_um=1.0, flux=-0.2, usable=True)
    response = SpectrumResponse(
        center={"ra": 10, "dec": 0},
        source="dr1_cube",
        unit="MJy/sr",
        static_coadd=True,
        points=[point],
        built_at="2026-11-15T02:00:00Z",
        aperture_px=0,
        background_subtracted=False,
    )
    assert response.points[0].flux_err is None
    assert response.points[0].flux == -0.2
    with pytest.raises(ValueError):
        SpectrumResponse.model_validate({**response.model_dump(), "unit": "mJy"})
    with pytest.raises(ValueError):
        SpectralMeasurement(id="bad", detector=1, wavelength_um=1, flux=float("inf"), usable=True)


@pytest.mark.parametrize(
    "path",
    [
        "../x.png",
        "/x.png",
        "analyses/" + "a" * 64 + "/compare/../x.png",
        "analyses/" + "a" * 64 + "/compare/x.png?token=y",
    ],
)
def test_comparison_images_are_contained(path):
    with pytest.raises(ValueError):
        ComparisonImage(id="one", kind="weighted_mean", detector=1, image=path, frame_ids=["one"], mjd_min=1, mjd_max=2)


def test_comparison_request_rejects_duplicate_frames():
    with pytest.raises(ValueError):
        ComparisonRequest(frame_ids=["a", "a"])


# --- Object card (contract 0.5.0, C05) ---------------------------------------


def _object_response(**changes) -> dict:
    doc = {
        "query": {"ra": None, "dec": None, "name": "Barnard's Star", "epoch_mjd": 61000.0, "radius_arcsec": 8.0},
        "position": {"ra": 269.4462933, "dec": 4.7678814, "epoch_mjd": 61000.0, "source": "Gaia DR3 propagated"},
        "identity": {
            "display_name": "Barnard's star",
            "main_id": "NAME Barnard's star",
            "gaia_source_id": "4472832130942575872",
            "gaia_method": "simbad_crossid",
            "match": "name",
        },
        "facts": [{"label": "Mass", "value": "unknown", "unit": None, "source": "Gaia DR3 FLAME", "verified": False}],
        "photometry": [
            {
                "mission": "2MASS",
                "catalog": "2MASS All-Sky PSC II/246/out (VizieR CfA)",
                "designation": "2MASS J17574849+0441405",
                "band": "J",
                "wavelength_um": 1.235,
                "mag": 5.244,
            }
        ],
        "provenance": [
            {"service": "vsx", "catalog": "AAVSO VSX", "status": "error", "note": "ReadTimeout"},
            {"service": "sesame", "catalog": "SIMBAD", "status": "ok", "retrieved_utc": "2026-11-15T03:44:16Z"},
        ],
        "partial": True,
        "built_at": "2026-11-15T12:00:00Z",
        "note": "Catalog context from other missions/surveys: not SPHEREx measurements.",
    }
    doc.update(changes)
    return doc


def test_object_context_round_trip_matches_published_schema():
    from errante.models import ObjectContextResponse

    model = ObjectContextResponse.model_validate(_object_response())
    data = model.model_dump(mode="json")
    jsonschema.validate(data, json.loads((SCHEMA_DIR / "ObjectContextResponse.schema.json").read_text()))
    assert data["photometry"][0]["other_mission"] is True and data["synthetic"] is False
    assert data["schema_version"] == SCHEMA_VERSION and data["identity"]["gaia_source_id"] == "4472832130942575872"
    assert data["facts"][0]["value"] == "unknown" and data["provenance"][0]["status"] == "error"


@pytest.mark.parametrize(
    "query",
    [
        {"ra": 10.0, "dec": 20.0, "name": "x"},  # both
        {"ra": None, "dec": None, "name": None},  # neither
        {"ra": 10.0, "dec": None, "name": None},  # half a position
        {"ra": 360.0, "dec": 0.0, "name": None},
        {"ra": float("nan"), "dec": 0.0, "name": None},
    ],
)
def test_object_query_needs_a_name_or_a_full_position(query):
    from errante.models import ObjectQuery

    with pytest.raises(ValueError):
        ObjectQuery.model_validate({**query, "epoch_mjd": 61000.0, "radius_arcsec": 8.0})


@pytest.mark.parametrize(
    "path, value",
    [
        (("identity", "gaia_source_id"), 4472832130942575872),  # a JS number would lose the last digits
        (("identity", "match"), "probable"),
        (("photometry", 0, "other_mission"), False),  # context photometry is never SPHEREx
        (("photometry", 0, "mission"), "SPHEREx"),
        (("provenance", 0, "status"), "timeout"),
        (("synthetic",), True),
    ],
)
def test_object_context_rejects_values_that_would_mislead_the_card(path, value):
    from errante.models import ObjectContextResponse

    doc = _object_response()
    target = doc
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    with pytest.raises(ValueError):
        ObjectContextResponse.model_validate(doc)


# Public light-curve proposal (explicit test data).


def example_product():
    return {
        "id": "a" * 64,
        "target_id": "example",
        "target_name": "Explicit test double",
        "built_at": "2026-11-15T12:00:00Z",
        "status": "ready",
        "parameters": {"ra": 10, "dec": 0, "max_frames": 2},
        "curve": {
            "ra": 10,
            "dec": 0,
            "method": "aperture",
            "unit": "mJy",
            "relative_only": False,
            "lambda_bin_frac": 0.01,
            "min_bin_span_days": 30,
            "points": [
                {
                    "frame_id": "one",
                    "obs_id": "one",
                    "detector": 1,
                    "release": "dr1",
                    "mjd": 60000,
                    "date": "2023-02-25T00:00:00Z",
                    "season": 0,
                    "wavelength_um": 0.75,
                    "flux": 1,
                    "flux_err": None,
                    "bin": 0,
                    "rel_mag": -0.1,
                    "rel_mag_err": None,
                }
            ],
            "bins": [
                {
                    "index": 0,
                    "detector": 1,
                    "lambda_min_um": 0.75,
                    "lambda_max_um": 0.75,
                    "n_points": 1,
                    "mjd_min": 60000,
                    "mjd_max": 60000,
                    "mean_mag": 0,
                }
            ],
            "comparisons": [],
            "control": {},
            "summary": {},
            "excluded": {},
        },
        "provenance": {
            "pipeline_version": "test",
            "processing_fingerprint": "b" * 64,
            "collections": ["spherex_dr1", "spherex_qr3"],
            "n_selected": 1,
            "sources": [{"frame_id": "one", "source_uri": "https://example.invalid/one.fits"}],
        },
    }


def test_negative_relative_magnitude_and_missing_uncertainty_are_preserved():
    result = LightCurveProduct.model_validate(example_product())
    assert result.curve.points[0].rel_mag == -0.1
    assert result.curve.points[0].rel_mag_err is None
    assert LightCurveProduct.model_validate_json(result.model_dump_json()) == result


@pytest.mark.parametrize(
    "change",
    [
        {"mjd_min": 60001, "mjd_max": 60000},
        {"max_frames": 2501},
        {"ra": float("nan")},
        {"detectors": [1, 1]},
        {"collections": ["synthetic"]},
        {"period_range_days": [0, 10]},
    ],
)
def test_bounded_offline_calculation(change):
    with pytest.raises(ValueError):
        LightCurveParameters.model_validate({"ra": 10, "dec": 0, **change})


def test_wing_units_cannot_be_presented_as_aperture_flux():
    doc = example_product()["curve"]
    with pytest.raises(ValueError):
        LightCurveData.model_validate({**doc, "method": "wing"})
    assert LightCurveData.model_validate({**doc, "method": "wing", "unit": "MJy/sr", "relative_only": True})


def test_ready_cannot_hide_empty_or_excluded_measurements():
    doc = example_product()
    doc["curve"]["points"][0]["excluded"] = "saturated"
    with pytest.raises(ValueError):
        LightCurveProduct.model_validate(doc)
    doc["curve"]["points"][0]["rel_mag"] = None
    with pytest.raises(ValueError):
        LightCurveProduct.model_validate(doc)
    doc["status"] = "no_usable_points"
    assert LightCurveProduct.model_validate(doc).curve.points[0].excluded == "saturated"


def test_broken_provenance_or_binning_is_rejected():
    doc = example_product()
    doc["provenance"]["sources"] = []
    with pytest.raises(ValueError):
        LightCurveProduct.model_validate(doc)
    doc = example_product()
    doc["curve"]["bins"][0]["detector"] = 2
    with pytest.raises(ValueError):
        LightCurveProduct.model_validate(doc)


@pytest.mark.parametrize(
    "tested,probability,significant,valid",
    [
        (0, None, None, True),
        (0, None, True, False),
        (100, 0.2, True, False),
        (100, 0.0099, True, True),
        (100, 0.2, False, True),
    ],
)
def test_period_candidate_is_distinct_from_a_significant_period(tested, probability, significant, valid):
    doc = {
        "period_days": 260,
        "delta_chi2": 100,
        "peaks": [[260, 100]],
        "amplitude_mag": {1: 1},
        "floor_mag": {1: 0.1},
        "n_points": 40,
        "baseline_days": 400,
        "period_range_days": [20, 800],
        "n_permutations": tested,
        "false_alarm": probability,
        "significant": significant,
        "caveat": "Candidate sinusoid; inspect the aliases and independent data.",
    }
    if valid:
        assert LightCurvePeriod.model_validate(doc).significant is significant
    else:
        with pytest.raises(ValueError):
            LightCurvePeriod.model_validate(doc)
