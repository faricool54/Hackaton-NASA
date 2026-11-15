from dataclasses import replace

from errante_api.jobs.types import JobRequest
from errante_api.processing import source_fingerprint


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
