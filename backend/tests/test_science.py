"""Offline scientific boundaries: real recorded cube metadata, explicit image/IO test doubles."""

import asyncio
import json
import subprocess
import threading
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
from fastapi.testclient import TestClient
from pydantic import TypeAdapter

from errante import settings as core
from errante.data.cube import CubeSpectrum
from errante.imaging.compare import GridFrame
from errante.models import SpectrumRequest, SpectrumResponse
from errante.products import ProductStore
from errante_api import science_ops
from errante_api.live_service import LiveService
from errante_api.main import create_app
from errante_api.science_service import ScienceService
from errante_api.settings import Settings


def test_real_exposure_interpretation_reaches_existing_notes_without_inventing_a_temperature(monkeypatch):
    record = json.loads((Path(core.__file__).parents[1] / "tests/fixtures/ws3/continuum/eps-indi-b.json").read_bytes())
    data = record["spectrum"]
    measured = SpectrumResponse.model_validate(
        {
            "center": {"ra": data["ra"], "dec": data["dec"]},
            "source": "l2_exposures",
            "unit": "mJy",
            "background_subtracted": True,
            "static_coadd": False,
            "aperture_px": 2,
            "built_at": record["recorded_utc"],
            "points": [
                {
                    "id": p["frame_id"],
                    "frame_id": p["frame_id"],
                    "detector": p["detector"],
                    "release": p["release"],
                    "mjd": p["mjd"],
                    "wavelength_um": p["wavelength_um"],
                    "bandwidth_um": p["bandwidth_um"],
                    "flux": p["flux_mjy"],
                    "flux_err": p["flux_err_mjy"],
                    "usable": p["usable"],
                    "flags": p["flags"],
                    "aperture_correction": p["aperture_correction"],
                }
                for p in data["samples"]
            ],
        }
    )
    monkeypatch.setattr(science_ops, "exposure_spectrum", lambda request, field: measured)
    result = science_ops.spectrum(SpectrumRequest(ra=data["ra"], dec=data["dec"], source="l2_exposures"))
    assert len(result.points) == 40 and sum(p.usable for p in result.points) == 35
    assert any("not stellar effective temperature" in note for note in result.notes)
    assert any("colour temperature unknown (poor_fit)" in note for note in result.notes)
    assert not any("conditional interval" in note for note in result.notes)


@pytest.fixture
def real_field():
    field = ProductStore(core.PRODUCTS_DIR).read_field("barnards-star")
    frames = [f for f in field.frames if f.detector == 2]
    return field.model_copy(update={"frames": [frames[0], frames[-1]], "composites": []})


@pytest.fixture
def cube_recording():
    path = core.REPO_ROOT / "pipeline/tests/fixtures/ws1/cube_spectra/wise-0855_ap2.json"
    return CubeSpectrum.from_dict(json.loads(path.read_text()))


@pytest.fixture
def science_client(tmp_path, real_field, cube_recording, monkeypatch):
    public = tmp_path / "public"
    ProductStore(public).write_field(real_field)
    settings = Settings(data_dir=public, live_cache_dir=tmp_path / "private")
    calls = []
    monkeypatch.setattr("errante.data.cube.cube_spectrum", lambda *a, **kw: cube_recording)

    def loader(field):
        def load(refs):
            shape = (field.grid.height_px, field.grid.width_px)
            # Explicit deterministic image double; no physical result is claimed.
            return [
                GridFrame(f.id, f.detector, f.mjd, np.full(shape, float(i)), np.zeros(shape, bool), np.ones(shape))
                for i, f in enumerate(field.frames)
            ]

        return load

    monkeypatch.setattr("errante.imaging.compare.load_from_cutouts", loader)

    def run(doc, stage):
        calls.append(doc)
        (stage / "output").mkdir()
        if doc["operation"] == "spectrum":
            return science_ops.spectrum(SpectrumRequest.model_validate(doc["request"])).model_dump(mode="json")
        from errante.models import SkyField

        return science_ops.comparisons(SkyField.model_validate(doc["field"]), stage / "output", doc["id"]).model_dump(
            mode="json"
        )

    app = create_app(settings)
    app.state.science._runner = run
    with TestClient(app) as client:
        yield client, app.state.science, calls, real_field, cube_recording, public


def test_cube_preserves_recorded_nulls_flags_and_units(science_client):
    client, _, calls, _, cube, _ = science_client
    body = {"ra": cube.ra, "dec": cube.dec, "aperture_px": 2}
    response = client.post("/api/spectra", json=body)
    assert any("colour temperature unknown (unsupported_product)" in note for note in response.json()["notes"])
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["unit"] == "MJy/sr" and data["static_coadd"]
    assert len(data["points"]) == 102
    assert all(p["flux_err"] is None for p in data["points"])
    assert data["points"][50]["flux"] is None and not data["points"][50]["usable"]
    assert all(p["source_uri"] for p in data["points"])
    assert client.post("/api/spectra", json=body).json() == data
    assert len(calls) == 1


def test_cube_source_is_informational_but_hot_pixel_is_not_usable(cube_recording, monkeypatch):
    from errante.imaging.flags import FLAG_BITS

    cube_recording.flux[:2] = [1.0, -2.0]
    cube_recording.valid[:2] = True
    cube_recording.flags[:2] = [1 << FLAG_BITS["SOURCE"], 1 << FLAG_BITS["HOT"]]
    monkeypatch.setattr("errante.data.cube.cube_spectrum", lambda *a, **kw: cube_recording)
    result = science_ops.cube_spectrum(SpectrumRequest(ra=cube_recording.ra, dec=cube_recording.dec))
    assert result.points[0].usable and "source" in result.points[0].flags
    assert not result.points[1].usable and "hot" in result.points[1].flags
    assert result.points[1].flux == -2.0


def test_comparison_publishes_verified_images_without_modifying_field(science_client):
    client, _, calls, field, _, root = science_client
    before = (root / "fields" / field.id / "field.json").read_bytes()
    response = client.post(f"/api/fields/{field.id}/comparisons", json={"detectors": [2]})
    assert response.status_code == 200, response.text
    data = response.json()
    assert len(data["images"]) == 3
    assert {i["kind"] for i in data["images"]} == {"weighted_mean", "scaled_difference"}
    for image in data["images"]:
        png = client.get("/data/" + image["image"])
        assert png.status_code == 200 and png.content.startswith(b"\x89PNG")
        assert image["frame_ids"]
        assert image["mjd_min"] <= image["mjd_max"]
    assert (root / "fields" / field.id / "field.json").read_bytes() == before
    assert client.post(f"/api/fields/{field.id}/comparisons", json={"detectors": [2]}).json() == data
    assert len(calls) == 1


def test_missing_or_corrupt_analysis_png_is_rebuilt(science_client):
    client, _, calls, field, _, root = science_client
    url = f"/api/fields/{field.id}/comparisons"
    result = client.post(url, json={}).json()
    (root / result["images"][0]["image"]).write_bytes(b"broken")
    again = client.post(url, json={})
    assert again.status_code == 200, again.text
    assert len(calls) == 2
    assert client.get("/data/" + again.json()["images"][0]["image"]).content.startswith(b"\x89PNG")


def test_invalid_selections_and_synthetic_fields_never_launch(science_client):
    client, _, calls, field, _, root = science_client
    url = f"/api/fields/{field.id}/comparisons"
    assert client.post(url, json={"frame_ids": ["unknown", "missing"]}).status_code == 422
    assert client.post(url, json={"detectors": [7]}).status_code == 422
    assert client.post("/api/spectra", json={"ra": 360, "dec": 0}).status_code == 422
    assert client.post("/api/spectra", json={"ra": 0, "dec": 0, "mjd_min": 1}).status_code == 422
    field.provenance.synthetic = True
    ProductStore(root).write_field(field)
    assert client.post(url, json={}).status_code == 409
    assert calls == []


def test_science_worker_errors_are_sanitized(science_client):
    client, service, _, _, cube, _ = science_client

    def fail(*args):
        raise RuntimeError("private path C:/secrets/internal trace")

    service._runner = fail
    result = client.post("/api/spectra", json={"ra": cube.ra, "dec": cube.dec})
    assert result.status_code == 502
    assert "secrets" not in result.text and "trace" not in result.text


def test_outside_field_and_unknown_field_do_not_launch(science_client):
    client, _, calls, field, _, _ = science_client
    assert client.post("/api/spectra", json={"ra": 0, "dec": -70, "field_id": field.id}).status_code == 422
    assert client.post("/api/spectra", json={"ra": 0, "dec": 0, "field_id": "missing"}).status_code == 404
    assert not calls


def test_identical_work_is_shared_and_one_caller_cannot_cancel_it(tmp_path):
    settings = Settings(data_dir=tmp_path / "public", live_cache_dir=tmp_path / "private", live_max_concurrent=1)
    service = LiveService(settings)
    entered, release = threading.Event(), threading.Event()
    calls = []

    def work():
        calls.append(1)
        entered.set()
        release.wait(5)
        return 42

    async def scenario():
        first = asyncio.create_task(service.call("same", {}, work, TypeAdapter(int)))
        while not entered.is_set():
            await asyncio.sleep(0.001)
        second = asyncio.create_task(service.call("same", {}, work, TypeAdapter(int)))
        await asyncio.sleep(0.005)
        first.cancel()
        with pytest.raises(asyncio.CancelledError):
            await first
        release.set()
        assert await second == 42

    try:
        asyncio.run(scenario())
        assert len(calls) == 1
    finally:
        release.set()
        service.close()


@pytest.mark.parametrize("failure", ["deadline", "disk"])
def test_actual_science_child_is_killed_when_budget_is_exceeded(tmp_path, monkeypatch, failure):
    service = ScienceService(Settings(data_dir=tmp_path / "public", live_cache_dir=tmp_path / "private"))
    stage = tmp_path / "stage"
    stage.mkdir()
    real_popen = subprocess.Popen
    children = []

    def launch(args, **kwargs):
        proc = real_popen([args[0], "-c", "import time; time.sleep(60)"], **kwargs)
        children.append(proc)
        return proc

    monkeypatch.setattr("errante_api.science_service.subprocess.Popen", launch)
    if failure == "deadline":
        monkeypatch.setattr("errante_api.science_service._DEADLINE_S", 0.05)
    else:
        monkeypatch.setattr("errante_api.science_service.tree_bytes", lambda _: 513 * 1024**2)
    try:
        with pytest.raises((TimeoutError, OSError)):
            service._run_child({}, stage)
        assert children and children[0].poll() is not None
    finally:
        for proc in children:
            if proc.poll() is None:
                proc.kill()
                proc.wait()
        service.close()


def test_exposure_photometry_preserves_errors_negative_flux_and_bad_quality(monkeypatch):
    from astropy.wcs import WCS

    from errante.imaging.photometry import SATURATED
    from errante.models import FrameRef

    wcs = WCS(naxis=2)
    wcs.wcs.crval = [10, 0]
    wcs.wcs.crpix = [13, 13]
    wcs.wcs.cdelt = [-6.15 / 3600, 6.15 / 3600]
    wcs.wcs.ctype = ["RA---TAN", "DEC--TAN"]
    yy, xx = np.mgrid[:25, :25]
    samples = []
    for i in range(3):
        flags = np.zeros((25, 25), dtype=np.int64)
        if i == 1:
            flags[12, 12] = SATURATED
        img = SimpleNamespace(
            data_minus_zodi=-10 * np.exp(-((xx - 12) ** 2 + (yy - 12) ** 2) / 2),
            data=np.zeros((25, 25)),
            flags=flags if i < 2 else None,
            variance=np.ones((25, 25)),
            header={"OMEGA_MEDIAN": 6.15**2},
            wcs=wcs,
            obs_id=f"test-{i}",
            detector=1,
            mjd=61000 + i,
            source="https://example.invalid/test-double.fits",
            wavelength_at=lambda *a: (1.0, 0.05),
        )
        samples.append(
            SimpleNamespace(
                obs_id=img.obs_id,
                detector=1,
                release="dr1",
                image=img,
                flags=img.flags,
                variance=img.variance,
                zodi=np.zeros((25, 25)),
            )
        )
    lost = FrameRef(obs_id="lost", detector=1, mjd=61003, release="dr1")
    monkeypatch.setattr(
        "errante.data.point.point_series",
        lambda *a, **kw: SimpleNamespace(
            samples=samples, failures=[(lost, "TimeoutError: /private/path")], search={"stale": True}
        ),
    )
    monkeypatch.setattr("errante.data.point.to_spherex_image", lambda sample: sample.image)
    result = science_ops.exposure_spectrum(SpectrumRequest(ra=10, dec=0, source="l2_exposures"), None)
    assert result.unit == "mJy" and not result.static_coadd
    assert result.points[0].flux < 0 and result.points[0].flux_err > 0 and result.points[0].usable
    assert not result.points[1].usable and "saturated" in result.points[1].flags
    assert not result.points[2].usable and "flags_unavailable" in result.points[2].flags
    assert result.stale and result.failures[0].reason == "download_failed"
    assert "private/path" not in result.model_dump_json()


def test_catalog_motion_extracts_at_exposure_position_and_changes_cache_identity(tmp_path, monkeypatch):
    from astropy.wcs import WCS

    from errante.imaging.photometry import propagate

    wcs = WCS(naxis=2)
    wcs.wcs.crval, wcs.wcs.crpix = [10, 0], [13, 13]
    wcs.wcs.cdelt, wcs.wcs.ctype = [-6.15 / 3600, 6.15 / 3600], ["RA---TAN", "DEC--TAN"]
    yy, xx = np.mgrid[:25, :25]
    data = 40 * np.exp(-((xx - 12) ** 2 + (yy - 15) ** 2) / (2 * 0.7**2))
    image = SimpleNamespace(
        data_minus_zodi=data,
        data=data,
        flags=np.zeros((25, 25), dtype=np.int64),
        variance=np.ones((25, 25)),
        header={"OMEGA_MEDIAN": 6.15**2},
        wcs=wcs,
        obs_id="explicit-moving-test",
        detector=1,
        mjd=61365.25,
        source="https://example.invalid/moving-test.fits",
        wavelength_at=lambda *a: (1.0, 0.05),
    )
    sample = SimpleNamespace(
        obs_id=image.obs_id,
        detector=1,
        release="dr1",
        image=image,
        flags=image.flags,
        variance=image.variance,
        zodi=np.zeros((25, 25)),
    )
    calls = []

    def series(ra, dec, **kwargs):
        calls.append((ra, dec, kwargs["box_px"]))
        return SimpleNamespace(samples=[sample], failures=[], search={"n_selected": 1, "n_found": 3})

    monkeypatch.setattr("errante.data.point.point_series", series)
    monkeypatch.setattr("errante.data.point.to_spherex_image", lambda sample: sample.image)
    fixed = SpectrumRequest(ra=10, dec=0, source="l2_exposures")
    moving = SpectrumRequest(
        ra=10,
        dec=0,
        source="l2_exposures",
        proper_motion={"ra_cosdec_masyr": 0, "dec_masyr": 18450, "epoch_mjd": 61000},
    )
    fixed_result = science_ops.exposure_spectrum(fixed, None)
    result = science_ops.exposure_spectrum(moving, None)
    expected = propagate(10, 0, (0, 18450, 61000), image.mjd)
    assert result.points[0].position.dec == pytest.approx(expected[1])
    assert result.points[0].flux > 3 * fixed_result.points[0].flux
    assert result.proper_motion == moving.proper_motion and result.truncated
    assert calls == [(10, 0, 25), (10, 0, 81)]
    service = ScienceService(Settings(data_dir=tmp_path / "public", live_cache_dir=tmp_path / "private"))
    try:
        assert service._identity("spectrum", fixed, None)["id"] != service._identity("spectrum", moving, None)["id"]
    finally:
        service.close()
