"""Offline product boundaries and native WS3 integration on explicitly synthetic stamps."""

import json
import os
import runpy
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from errante import settings as core
from errante.models import LightCurveParameters, LightCurveProduct
from errante_api import lightcurve_build as build
from errante_api.lightcurve_store import LightCurveStore
from errante_api.main import create_app
from errante_api.settings import Settings

BUNDLED = Path(build.__file__).parent / "curated" / "lightcurves"


@pytest.fixture
def product():
    return LightCurveProduct.model_validate_json((BUNDLED / "rw-aurigae.json").read_bytes())


def test_real_bundles_keep_quality_provenance_and_native_period():
    store = LightCurveStore(BUNDLED)
    assert {p.target_id for p in store.index().products} == {"rw-aurigae", "r-draconis"}
    for name in ("rw-aurigae", "r-draconis"):
        p, _, _ = store.read(name)
        assert not p.synthetic and p.status == "ready"
        assert p.provenance.sources and all(s.source_uri.startswith("https://") for s in p.provenance.sources)
        assert any(x.rel_mag is not None for x in p.curve.points)
        assert p.curve.excluded and p.curve.comparisons and p.curve.control
        # A fresh archive rebuild is allowed to be complete; snapshot fallback must remain explicit.
        if p.provenance.stale_search or p.provenance.truncated_search:
            assert p.provenance.partial
    rw, _, _ = store.read("rw-aurigae")
    assert rw.curve.unit == "mJy" and not rw.curve.relative_only and rw.curve.matched_pairs
    assert sum(p.rel_mag is not None for p in rw.curve.points) == 10  # playback and pairs retain all measurements
    assert rw.curve.summary[1].n == 0 and rw.curve.summary[1].scatter_over_control is None
    assert any("only one independent difference" in note for note in rw.curve.notes)
    dra, _, _ = store.read("r-draconis")
    assert dra.curve.unit == "MJy/sr" and dra.curve.relative_only
    assert dra.curve.period.significant and dra.curve.period.false_alarm <= 0.01
    assert len(dra.curve.period.peaks) > 1 and dra.curve.period.bootstrap_95_days
    assert dra.parameters.n_bootstrap == 1000 and dra.parameters.n_permutations == 999
    assert dra.curve.period.n_permutations == 999
    assert any("wide survey only" in n for n in dra.provenance.notes)
    assert any("A+BC is unresolved" in n for n in rw.provenance.notes)


def test_api_reads_offline_and_etag_is_checked_after_validation(tmp_path, monkeypatch, product):
    def forbidden(*args, **kwargs):
        pytest.fail("GET must never compute a light curve or access the archive")

    monkeypatch.setattr(build, "calculate", forbidden)
    monkeypatch.setattr("errante.data.point.point_series", forbidden)
    root = tmp_path / "public"
    path = build.publish(product, root / "lightcurves")
    app = create_app(Settings(data_dir=root, live_cache_dir=tmp_path / "private"))
    with TestClient(app) as client:
        listing = client.get("/api/lightcurves")
        assert listing.status_code == 200
        row = next(p for p in listing.json()["products"] if p["target_id"] == product.target_id)
        assert row["n_used"] == sum(p.rel_mag is not None for p in product.curve.points)
        url = f"/api/lightcurves/{product.target_id}"
        first = client.get(url)
        assert first.status_code == 200 and first.json() == product.model_dump(mode="json")
        etag = first.headers["etag"]
        for offered in (etag, "W/" + etag, '"other", ' + etag, "*"):
            cached = client.get(url, headers={"If-None-Match": offered})
            assert cached.status_code == 304 and not cached.content
        assert client.get(url, headers={"If-None-Match": '"other"'}).status_code == 200
        assert client.get("/api/lightcurves/missing").status_code == 404
        assert client.get("/api/lightcurves/UPPERCASE").status_code == 422
        path.write_text("broken /private/token")
        invalid = client.get(url, headers={"If-None-Match": etag})
        assert invalid.status_code == 503 and "private" not in invalid.text
        schemas = client.get("/openapi.json").json()["components"]["schemas"]
        assert "LightCurveProduct" in schemas and "LightCurveIndex" in schemas


@pytest.mark.parametrize("problem", ["corrupt", "identity", "synthetic", "oversize"])
def test_runtime_invalid_never_falls_back_to_good_bundle(tmp_path, product, monkeypatch, problem):
    path = build.publish(product, tmp_path)
    doc = product.model_dump(mode="json")
    if problem == "identity":
        doc["target_id"] = "other"
    elif problem == "synthetic":
        doc["synthetic"] = True
    path.write_text("broken" if problem == "corrupt" else json.dumps(doc))
    if problem == "oversize":
        monkeypatch.setattr("errante_api.lightcurve_store.MAX_PRODUCT_BYTES", 10)
    with pytest.raises(HTTPException) as caught:
        LightCurveStore(tmp_path).read(product.target_id)
    assert caught.value.status_code == 503


def test_cache_refreshes_same_size_same_mtime_and_missing_file(tmp_path, product):
    path = build.publish(product, tmp_path)
    store = LightCurveStore(tmp_path, tmp_path / "no-bundle")
    first, _, etag = store.read(product.target_id)
    stat = path.stat()
    original = path.read_bytes()
    path.write_bytes(original.replace(b"RW Aurigae", b"RW AURIGAE"))
    os.utime(path, ns=(stat.st_atime_ns, stat.st_mtime_ns))
    updated, _, new_etag = store.read(product.target_id)
    assert first.target_name == "RW Aurigae" and updated.target_name == "RW AURIGAE" and etag != new_etag
    path.unlink()
    with pytest.raises(HTTPException) as caught:
        store.read(product.target_id)
    assert caught.value.status_code == 404


def test_path_boundary_and_index_cap(tmp_path, monkeypatch):
    store = LightCurveStore(tmp_path, tmp_path / "no-bundle")
    with pytest.raises(HTTPException) as caught:
        store.read("../secret")
    assert caught.value.status_code == 404
    monkeypatch.setattr("errante_api.lightcurve_store.MAX_PRODUCTS", 1)
    (tmp_path / "one.json").write_text("{}")
    (tmp_path / "two.json").write_text("{}")
    with pytest.raises(HTTPException) as caught:
        store.index()
    assert caught.value.status_code == 503


def test_failed_atomic_publication_keeps_previous_and_does_not_touch_fields(tmp_path, monkeypatch, product):
    public = tmp_path / "public"
    public.mkdir()
    manifest = public / "manifest.json"
    manifest.write_bytes(b"manifest sentinel")
    path = build.publish(product, public / "lightcurves")
    original = path.read_bytes()

    def fail(*args):
        raise OSError("simulated failed write")

    monkeypatch.setattr(build, "atomic_bytes", fail)
    with pytest.raises(OSError):
        build.publish(product, public / "lightcurves")
    assert path.read_bytes() == original and manifest.read_bytes() == b"manifest sentinel"
    assert not (public / "fields").exists()


@pytest.mark.parametrize("failure", ["deadline", "disk"])
def test_real_child_terminated_and_staging_removed_on_limit(tmp_path, monkeypatch, failure):
    real_popen = subprocess.Popen
    children = []

    def launch(args, **kwargs):
        proc = real_popen([args[0], "-c", "import time; time.sleep(60)"], **kwargs)
        children.append(proc)
        return proc

    monkeypatch.setattr(build.subprocess, "Popen", launch)
    if failure == "disk":
        monkeypatch.setattr(build, "tree_bytes", lambda _: 999999)
    try:
        with pytest.raises((TimeoutError, OSError)):
            build.run_bounded({}, tmp_path, deadline_s=0.05 if failure == "deadline" else 10, max_bytes=10000)
        assert children and children[0].poll() is not None
        assert not list(tmp_path.iterdir())
    finally:
        for proc in children:
            if proc.poll() is None:
                proc.kill()
                proc.wait()


def test_low_disk_rejected_before_child_launch(tmp_path, monkeypatch):
    monkeypatch.setattr(build.shutil, "disk_usage", lambda _: SimpleNamespace(free=0))
    with pytest.raises(OSError, match="free space"):
        build.run_bounded({}, tmp_path)
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize("mismatch", [False, True])
def test_worker_result_is_validated_against_requested_identity(tmp_path, monkeypatch, product, mismatch):
    fixture = tmp_path / "worker-result.json"
    fixture.write_text(product.model_dump_json())
    real_popen = subprocess.Popen

    def launch(args, **kwargs):
        assert kwargs["env"]["ERRANTE_SEARCH_DEADLINE_S"] == "7"
        assert kwargs["env"]["ERRANTE_SEARCH_FALLBACK_DEADLINE_S"] == "7"
        return real_popen(
            [args[0], "-c", "import shutil,sys; shutil.copyfile(sys.argv[1],sys.argv[2])", str(fixture), args[-1]],
            **kwargs,
        )

    monkeypatch.setattr(build.subprocess, "Popen", launch)
    doc = {
        "target_id": "other-target" if mismatch else product.target_id,
        "target_name": product.target_name,
        "parameters": product.parameters.model_dump(mode="json"),
        "processing_fingerprint": product.provenance.processing_fingerprint,
        "archive_deadline_s": 7,
    }
    work = tmp_path / "work"
    if mismatch:
        with pytest.raises(ValueError, match="does not match"):
            build.run_bounded(doc, work, deadline_s=10)
    else:
        assert build.run_bounded(doc, work, deadline_s=10) == product
    assert not list(work.iterdir())


def test_native_empty_result_is_explicit_and_publishable(tmp_path, monkeypatch):
    from errante.science import variability as ws3

    monkeypatch.setattr(
        "errante.data.point.point_series",
        lambda *a, **kw: SimpleNamespace(samples=[], failures=[], search={"n_found": 0}),
    )
    monkeypatch.setattr(ws3, "exposures_from_series", lambda _: ([], []))
    result = build.calculate(
        {
            "target_id": "empty-test",
            "target_name": "Empty synthetic test; never bundled",
            "parameters": {"ra": 10, "dec": 0},
            "archive_deadline_s": 10,
            "processing_fingerprint": "a" * 64,
        }
    )
    assert result.status == "no_usable_points" and result.curve.period is None
    build.publish(result, tmp_path)
    assert LightCurveStore(tmp_path, tmp_path / "no-bundle").index().products[0].n_used == 0


def test_native_ws3_adapter_preserves_controls_pairs_and_sanitizes_failures(tmp_path, monkeypatch):
    # Reuse explicitly synthetic WS3 test stamps; never publish them as real curated data.
    helper = runpy.run_path(str(core.REPO_ROOT / "pipeline/tests/test_science_variability.py"))
    exposures = helper["season_exposures"]()
    for exposure in exposures:
        exposure.image.source = f"https://example.invalid/{exposure.frame_id}.fits"
    from errante.models import FrameRef
    from errante.science import variability as ws3

    calls = []

    def series(*args, **kwargs):
        calls.append(kwargs)
        return SimpleNamespace(
            samples=[None] * len(exposures),
            failures=[(FrameRef(obs_id="lost", detector=1, mjd=61000, release="dr1"), "TimeoutError: /secret")],
            search={"n_found": 30, "n_selected": 19, "stale": True},
            timings={"timed_out": 1},
        )

    monkeypatch.setattr("errante.data.point.point_series", series)
    monkeypatch.setattr(
        ws3, "exposures_from_series", lambda _: (exposures, [{"frame_id": "lost2", "reason": "/secret"}])
    )
    params = LightCurveParameters(ra=helper["RA0"], dec=helper["DEC0"], max_frames=30)
    result = build.calculate(
        {
            "target_id": "test-only",
            "target_name": "Explicit synthetic stamp test; never bundled",
            "parameters": params.model_dump(mode="json"),
            "archive_deadline_s": 10,
            "processing_fingerprint": "a" * 64,
        }
    )
    assert result.status == "ready" and len(result.curve.points) == 18
    assert result.curve.comparisons and result.curve.control and result.curve.matched_pairs
    assert result.curve.period is None and calls[0]["planes"] == ws3.DEFAULT_PLANES["aperture"]
    assert result.provenance.partial and result.provenance.truncated_search and result.provenance.stale_search
    assert [f.reason for f in result.curve.failures] == ["download_failed", "measurement_failed"]
    assert "/secret" not in result.model_dump_json()
    # The known synthetic season change traverses the unchanged WS3 algorithms and typed adapter.
    pairs = [p for p in result.curve.matched_pairs if p.season_a == 0 and p.season_b == 2]
    assert len(pairs) == 12
    assert all(p.delta_mag == pytest.approx(-0.995, abs=0.01) for p in pairs)
    # Keep the 32-worker/provenance adapter tied to WS3's public CLI calculation (LC12).
    expected = ws3.light_curve(
        params.ra, params.dec, max_frames=30, deadline_s=10, period=False, n_permutations=params.n_permutations
    )
    from errante.models import LightCurveData

    native = expected.to_dict()
    native.pop("search")
    native.pop("timings")
    native.update(unit="mJy", relative_only=False, failures=[], matched_pairs=ws3.matched_pairs(expected))
    typed = LightCurveData.model_validate(native)
    for key in ("points", "bins", "comparisons", "control", "summary", "period", "matched_pairs"):
        assert getattr(result.curve, key) == getattr(typed, key), key
    assert any("1 exposures were not read" in note for note in result.provenance.notes)


@pytest.mark.parametrize(
    ("reason", "partial", "public_reason"),
    [
        ("NoOverlap: /secret", False, "no_overlap"),
        ("TimeoutError: /secret", True, "download_failed"),
        ("ValueError: truncated FITS /secret", True, "invalid_pixels"),
    ],
)
def test_partial_selection_distinguishes_footprints_from_missing_data(monkeypatch, reason, partial, public_reason):
    from errante.models import FrameRef
    from errante.science import variability as ws3

    monkeypatch.setattr(
        "errante.data.point.point_series",
        lambda *a, **kw: SimpleNamespace(
            samples=[],
            failures=[(FrameRef(obs_id="missing", detector=1, mjd=61000, release="dr1"), reason)],
            search={"service": "sia", "n_found": 1, "n_selected": 1},
            timings={},
        ),
    )
    monkeypatch.setattr(ws3, "exposures_from_series", lambda _: ([], []))
    result = build.calculate(
        {
            "target_id": "test-only",
            "target_name": "No samples",
            "parameters": {"ra": 10, "dec": 0},
            "archive_deadline_s": 10,
            "processing_fingerprint": "a" * 64,
        }
    )
    assert result.provenance.partial is partial
    assert result.curve.failures[0].reason == public_reason
    assert "/secret" not in result.model_dump_json()


def test_snapshot_notes_keep_actual_query_date_without_publishing_raw_warnings():
    from errante_api.lightcurve_metadata import acquisition_notes

    notes = acquisition_notes(
        {
            "service": "snapshot",
            "from_cache": False,
            "stale": True,
            "warnings": [
                "IRSA unavailable: frames come from the committed search snapshot 'r-draconis' "
                "(SIA answer of 2026-11-14 19:20:30+00:00); frames published after that date are missing",
                "/secret",
            ],
        },
        {},
        box_px=81,
        planes=("IMAGE", "FLAGS"),
        deadline_s=180,
    )
    assert any("2026-11-14T19:20:30+00:00" in note for note in notes)
    assert any("service: snapshot" in note and "stale=True" in note for note in notes)
    assert "/secret" not in " ".join(notes)


def test_preset_warnings_describe_actual_selection_and_brightness_censoring(product):
    from errante_api.lightcurve_metadata import target_notes

    notes = target_notes("rw-aurigae", product.parameters, product.curve)
    assert any("A+BC is unresolved" in n for n in notes)
    assert any(f"{product.curve.excluded['saturated']} saturated" in n and "bright states" in n for n in notes)
    wide = LightCurveParameters(ra=1, dec=0)
    assert any("wide survey only" in n for n in target_notes("r-draconis", wide, product.curve))
    deep = wide.model_copy(update={"collections": ["spherex_dr1_deep"]})
    assert not any("wide survey only" in n for n in target_notes("r-draconis", deep, product.curve))
