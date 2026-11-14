"""WS1 cutouts: IBE fallback (422 -> NoOverlap, retries on 5xx, aligned batch results)."""

from __future__ import annotations

import os
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import pytest
import requests
from astropy.io import fits

from errante import settings
from errante.data import cache, cutouts
from errante.data.cutouts import NoOverlap
from errante.models import FrameRef

KEY = "dr1/level2/2025W33_2C/l2b-v27-2026-228/3/level2_2025W33_2C_0321_1D3_spx_l2b-v27-2026-228.fits"
BARNARD = (269.44623, 4.76870)


def _frame(key: str = KEY, **kw) -> FrameRef:
    return FrameRef(obs_id="2025W33_2C_0321_1", detector=3, mjd=60902.9, release="dr1", s3_key=key, **kw)


def _fits_bytes() -> bytes:
    import io

    buf = io.BytesIO()
    fits.HDUList([fits.PrimaryHDU(), fits.ImageHDU(np.zeros((3, 3), np.float32), name="IMAGE")]).writeto(buf)
    return buf.getvalue()


class _Resp:
    def __init__(self, status: int, body: bytes = b""):
        self.status_code, self.body = status, body

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}", response=self)

    def iter_content(self, n):
        yield self.body


@pytest.fixture
def fake_http(monkeypatch, tmp_path):
    """Replace the HTTP GET used by cache.cached_download with a scripted sequence."""
    monkeypatch.setattr(settings, "CACHE_DIR", tmp_path / "cache")
    monkeypatch.setattr(cache.time, "sleep", lambda s: None)
    calls: list[str] = []
    script: list[_Resp] = []

    def get(url, stream, timeout):
        calls.append(url)
        return script.pop(0)

    monkeypatch.setattr(cache.requests, "get", get)
    return script, calls


def test_cutout_url_and_uri_from_s3_key():
    assert cutouts.frame_irsa_uri(_frame()) == "ibe/data/spherex/" + KEY
    assert cutouts.frame_irsa_uri(_frame(irsa_uri="ibe/data/spherex/x.fits")) == "ibe/data/spherex/x.fits"
    url = cutouts.cutout_url(cutouts.frame_irsa_uri(_frame()), *BARNARD, 5.0)
    assert url == f"{settings.IRSA_BASE}/ibe/data/spherex/{KEY}?center=269.4462300,4.7687000&size=5arcmin"
    with pytest.raises(ValueError):
        cutouts.frame_irsa_uri(FrameRef(obs_id="x", detector=1, mjd=1.0, release="dr1"))


def test_422_is_no_overlap(fake_http):
    script, calls = fake_http
    script.append(_Resp(422, b"Arrays do not overlap."))
    with pytest.raises(NoOverlap):
        cutouts.fetch_cutout(_frame(), *BARNARD, 5.0)
    assert len(calls) == 1  # a 4xx is not retried


def test_5xx_is_retried_then_cached(fake_http, tmp_path):
    script, calls = fake_http
    script += [_Resp(503), _Resp(502), _Resp(200, _fits_bytes())]
    path = cutouts.fetch_cutout(_frame(), *BARNARD, 5.0)
    assert len(calls) == 3 and fits.getdata(path, "IMAGE").shape == (3, 3)
    assert cutouts.fetch_cutout(_frame(), *BARNARD, 5.0) == path and len(calls) == 3  # cache hit
    copy = cutouts.fetch_cutout(_frame(), *BARNARD, 5.0, out_dir=tmp_path / "out")
    assert copy.parent == tmp_path / "out" and copy.read_bytes() == path.read_bytes()


def test_5xx_gives_up_after_retries(fake_http):
    script, calls = fake_http
    script += [_Resp(503)] * cutouts.CUTOUT_RETRIES
    with pytest.raises(RuntimeError):
        cutouts.fetch_cutout(_frame(), *BARNARD, 5.0)
    assert len(calls) == cutouts.CUTOUT_RETRIES


def test_non_fits_answer_is_not_cached(fake_http):
    script, _ = fake_http
    script.append(_Resp(200, b"<html>busy</html>"))
    with pytest.raises(RuntimeError, match="not FITS"):
        cutouts.fetch_cutout(_frame(), *BARNARD, 5.0)
    url = cutouts.cutout_url(cutouts.frame_irsa_uri(_frame()), *BARNARD, 5.0)
    assert not cache.cache_path(url, ".fits").exists()


class _CutResp(_Resp):
    """A 200 whose body breaks mid-transfer (what requests raises for an IncompleteRead)."""

    def iter_content(self, n):
        yield self.body[:10]
        raise requests.exceptions.ChunkedEncodingError("Connection broken: IncompleteRead")


def test_body_cut_mid_transfer_is_retried(fake_http, monkeypatch):
    script, calls = fake_http
    monkeypatch.setattr(cutouts.time, "sleep", lambda s: None)
    script += [_CutResp(200, _fits_bytes()), _Resp(200, _fits_bytes())]
    path = cutouts.fetch_cutout(_frame(), *BARNARD, 5.0)
    assert len(calls) == 2 and fits.getdata(path, "IMAGE").shape == (3, 3)
    script += [_CutResp(200, _fits_bytes())] * cutouts.BODY_RETRIES
    with pytest.raises(RuntimeError, match="mid-transfer"):
        cutouts.fetch_cutout(_frame(), *BARNARD, 7.0)


def test_concurrent_requests_for_one_cutout_download_once(fake_http, monkeypatch, tmp_path):
    """Duplicate frames in one batch: one download (cache.cached_download uses a fixed .part
    name per URL, so two concurrent downloads of one URL would write into the same file)."""
    script, calls = fake_http
    body = _fits_bytes()
    scripted_get = cache.requests.get

    def slow_get(url, stream, timeout):
        time.sleep(0.05)  # widen the race window
        return scripted_get(url, stream=stream, timeout=timeout)

    monkeypatch.setattr(cache.requests, "get", slow_get)
    script.append(_Resp(200, body))
    with ThreadPoolExecutor(8) as pool:
        paths = list(
            pool.map(lambda _: cutouts.fetch_cutout(_frame(), *BARNARD, 5.0, out_dir=tmp_path / "o"), range(8))
        )
    assert len(calls) == 1 and len(set(paths)) == 1 and paths[0].read_bytes() == body
    assert not list((tmp_path / "o").glob("*.part"))


def test_batch_is_aligned_and_reports_failures(monkeypatch, tmp_path):
    frames = [_frame(f"dr1/level2/w/v/3/level2_2025W33_2C_000{i}_1D3_spx_v.fits") for i in range(5)]

    def fake_fetch(frame, ra, dec, size_arcmin, out_dir=None):
        i = int(Path(frame.s3_key).stem.split("_")[3])  # level2_2025W33_2C_000<i>_1D3_...
        if i == 1:
            raise NoOverlap("no overlap")
        if i == 3:
            raise RuntimeError("Download failed after 5 attempts")
        return tmp_path / f"{i}.fits"

    monkeypatch.setattr(cutouts, "fetch_cutout", fake_fetch)
    results, failures = cutouts.fetch_cutouts_report(frames, *BARNARD, 5.0)
    assert [(f.s3_key, p.name) for f, p in results] == [(frames[i].s3_key, f"{i}.fits") for i in (0, 2, 4)]
    assert [f.s3_key for f, _ in failures] == [frames[1].s3_key, frames[3].s3_key]
    assert failures[0][1].startswith("NoOverlap") and failures[1][1].startswith("RuntimeError")

    # build.py's contract (WS2): one entry per frame, in order, None where the frame failed; never raises.
    monkeypatch.setattr(cutouts, "PIXEL_SOURCE", "ibe")
    paths = cutouts.fetch_cutouts(frames, *BARNARD, 5.0)
    assert [p.name if p else None for p in paths] == ["0.fits", None, "2.fits", None, "4.fits"]
    ok = [frames[i] for i in (4, 0, 2)]
    assert [p.name for p in cutouts.fetch_cutouts(ok, *BARNARD, 5.0)] == ["4.fits", "0.fits", "2.fits"]
    assert cutouts.fetch_cutouts([], *BARNARD, 5.0) == []


def test_fetch_cutouts_prefers_s3_and_falls_back_to_ibe(monkeypatch, tmp_path):
    from errante.data import s3range

    frames = [_frame(f"dr1/level2/w/v/3/level2_2025W33_2C_000{i}_1D3_spx_v.fits") for i in range(4)]

    def idx(frame):
        return int(Path(frame.s3_key).stem.split("_")[3])

    def fake_patch(frame, ra, dec, size_arcmin):
        i = idx(frame)
        if i == 0:
            return tmp_path / "s3_0.fits"
        if i == 1:
            raise NoOverlap("no overlap")  # IBE would 422 too: not retried there
        raise requests.ConnectionError("S3 unreachable")

    ibe_calls = []

    def fake_ibe(frame, ra, dec, size_arcmin, out_dir=None):
        ibe_calls.append(idx(frame))
        if idx(frame) == 3:
            raise RuntimeError("Download failed after 5 attempts")
        return tmp_path / f"ibe_{idx(frame)}.fits"

    monkeypatch.setattr(cutouts, "PIXEL_SOURCE", "s3")
    monkeypatch.setattr(s3range, "fetch_patch", fake_patch)
    monkeypatch.setattr(cutouts, "fetch_cutout", fake_ibe)
    paths, failures = cutouts.fetch_frames_report(frames, *BARNARD, 5.0)
    assert [p.name if p else None for p in paths] == ["s3_0.fits", None, "ibe_2.fits", None]
    assert sorted(ibe_calls) == [2, 3]
    assert [idx(f) for f, _ in failures] == [1, 3]
    assert failures[0][1].startswith("NoOverlap")
    assert "S3: ConnectionError" in failures[1][1] and "IBE: RuntimeError" in failures[1][1]
    assert cutouts.fetch_cutouts(frames, *BARNARD, 5.0) == paths


@pytest.mark.network
@pytest.mark.skipif(os.environ.get("ERRANTE_NETWORK_TESTS") != "1", reason="set ERRANTE_NETWORK_TESTS=1")
def test_real_cutout_and_422(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "CACHE_DIR", tmp_path)
    path = cutouts.fetch_cutout(_frame(), *BARNARD, 5.0)
    with fits.open(path) as h:
        assert [x.name for x in h] == ["PRIMARY", "IMAGE", "FLAGS", "VARIANCE", "ZODI", "EPSF", "WCS-WAVE"]
        assert h["IMAGE"].data.shape == (49, 49)
    assert path.stat().st_size > 3_500_000  # the whole EPSF table rides along
    with pytest.raises(NoOverlap):  # 30 px off the left edge of the detector (IBE: HTTP 422)
        cutouts.fetch_cutout(_frame(), 266.5516089, 3.7885772, 0.5)
