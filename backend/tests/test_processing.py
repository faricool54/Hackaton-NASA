from dataclasses import replace

import pytest

from errante.models import SpectrumRequest
from errante_api.jobs.types import JobRequest
from errante_api.processing import source_fingerprint
from errante_api.science_service import ScienceService
from errante_api.settings import Settings


def test_render_or_mask_change_invalidates_identity_and_paths_do_not(tmp_path):
    first, second = tmp_path / "one", tmp_path / "two"
    for root in (first, second):
        (root / "imaging").mkdir(parents=True)
        (root / "build.py").write_text("build = 1")
        (root / "imaging/render.py").write_text("stretch = 1")
        (root / "imaging/flags.py").write_text("mask = 1")
    before = source_fingerprint(first)
    assert before == source_fingerprint(second)
    (second / "imaging/render.py").write_text("stretch = 2")
    assert before != source_fingerprint(second)
    (second / "imaging/render.py").write_text("stretch = 1")
    (second / "imaging/flags.py").write_text("mask = 2")
    assert before != source_fingerprint(second)


def test_previous_processing_is_not_reused_but_saved_context_is_preserved():
    current = JobRequest.create(269.45, 4.77, 0.15)
    old = replace(current, build_context={"build_revision": "wavelength-pool-v3"})
    assert old.cache_key() != current.cache_key()
    assert JobRequest.from_dict(old.to_dict()).cache_key() == old.cache_key()


@pytest.mark.parametrize("relative_path", ["detect/difference.py", "detect/helpers/background.py", "products.py"])
def test_transitive_source_change_invalidates_jobs_and_science(tmp_path, monkeypatch, relative_path):
    source = tmp_path / relative_path
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text("implementation = 1")
    monkeypatch.setattr("errante_api.processing.errante.__file__", str(tmp_path / "__init__.py"))
    saved = JobRequest.create(269.45, 4.77, 0.15)
    old_job_key = saved.cache_key()
    service = ScienceService(Settings(data_dir=tmp_path / "public", live_cache_dir=tmp_path / "private"))
    request = SpectrumRequest(ra=269.45, dec=4.77)
    try:
        old_science_key = service._identity("spectrum", request, None)["id"]
        source.write_text("implementation = 2")
        assert JobRequest.create(269.45, 4.77, 0.15).cache_key() != old_job_key
        assert service._identity("spectrum", request, None)["id"] != old_science_key
        assert saved.cache_key() == old_job_key
        assert JobRequest.from_dict(saved.to_dict()).cache_key() == old_job_key
    finally:
        service.close()


def test_spectral_interpretation_change_invalidates_science_without_discarding_image_jobs(tmp_path, monkeypatch):
    source = tmp_path / "science/continuum.py"
    source.parent.mkdir()
    source.write_text("model = 1")
    monkeypatch.setattr("errante_api.processing.errante.__file__", str(tmp_path / "__init__.py"))
    job_key = JobRequest.create(10, 20, 0.15).cache_key()
    service = ScienceService(Settings(data_dir=tmp_path / "public", live_cache_dir=tmp_path / "private"))
    request = SpectrumRequest(ra=10, dec=20)
    try:
        key = service._identity("spectrum", request, None)["id"]
        source.write_text("model = 2")
        assert service._identity("spectrum", request, None)["id"] != key
        assert JobRequest.create(10, 20, 0.15).cache_key() == job_key
    finally:
        service.close()
