"""WS1 s3range: HTTP Range patches from S3, checked offline against a synthetic L2 file.

The synthetic file mirrors the real layout (docs/DATA.md §2): PRIMARY, IMAGE/VARIANCE/ZODI
float32, FLAGS tile-compressed RICE_1 with one tile per row, an EPSF-like table and
WCS-WAVE, with the real DR1 D3 TAN-SIP header (fixtures/ws1). It is served by a fake
Range reader, so nothing touches the network. Live checks are marked ``network``.
"""

from __future__ import annotations

import io
import os
import re
import threading
import time
import warnings
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import numpy as np
import pytest
import requests
from astropy.io import fits
from astropy.wcs import WCS

from errante import settings
from errante.data import fits_io, s3range
from errante.data.cutouts import NoOverlap
from errante.models import FrameRef

FIXTURES = Path(__file__).parent / "fixtures" / "ws1"
REAL_HEADER = FIXTURES / "dr1_D3_image_header.txt"
NX, NY = 300, 200  # non-square on purpose: catches x/y swaps


def _wcs(h: fits.Header) -> WCS:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return WCS(h)


def _image_header() -> fits.Header:
    h = fits.Header.fromtextfile(REAL_HEADER)
    h["NAXIS1"], h["NAXIS2"] = NX, NY
    h["CRPIX1"], h["CRPIX2"] = NX / 2 + 0.5, NY / 2 + 0.5
    return h


def make_l2(seed: int = 0, flags_tile_rows: int = 1) -> tuple[bytes, dict[str, np.ndarray]]:
    """A small L2-like MEF as bytes, plus the original planes."""
    rng = np.random.default_rng(seed)
    img = rng.normal(1.0, 0.1, (NY, NX)).astype(np.float32)
    img[5, 7] = np.nan
    var = rng.uniform(0.01, 0.02, (NY, NX)).astype(np.float32)
    zodi = rng.uniform(0.2, 0.3, (NY, NX)).astype(np.float32)
    flags = (rng.integers(0, 1 << 29, (NY, NX)) & rng.integers(0, 1 << 29, (NY, NX))).astype(np.int32)
    flags[:, :40] = 0  # long runs of zeros, like a real mask
    h = _image_header()
    hdus = [fits.PrimaryHDU(header=fits.Header([("VERSION", "7.0.5")]))]
    hdus.append(fits.ImageHDU(img, header=h, name="IMAGE"))
    hdus.append(
        fits.CompImageHDU(
            flags, header=h.copy(), name="FLAGS", compression_type="RICE_1", tile_shape=(flags_tile_rows, NX)
        )
    )
    hdus.append(fits.ImageHDU(var, header=h.copy(), name="VARIANCE"))
    hdus.append(fits.ImageHDU(zodi, header=h.copy(), name="ZODI"))
    hdus.append(
        fits.BinTableHDU.from_columns(
            [
                fits.Column(name="BINX", format="J", array=np.arange(7)),
                fits.Column(name="EPSF", format="9D", array=rng.normal(size=(7, 9))),
            ],
            name="EPSF",
        )
    )
    values = rng.uniform(1.6, 2.4, (1, 14, 9, 2)).astype(np.float32)
    hdus.append(
        fits.BinTableHDU.from_columns(
            [
                fits.Column(name="X", format="9J", array=np.linspace(1, NX, 9).astype(np.int32)[None]),
                fits.Column(name="Y", format="14J", array=np.linspace(1, NY, 14).astype(np.int32)[None]),
                fits.Column(name="VALUES", format="252E", dim="(2,9,14)", array=values),
            ],
            name="WCS-WAVE",
        )
    )
    buf = io.BytesIO()
    fits.HDUList(hdus).writeto(buf)
    return buf.getvalue(), {"IMAGE": img, "VARIANCE": var, "ZODI": zodi, "FLAGS": flags}


class FakeS3:
    """Serves byte ranges of in-memory objects, like the S3 bucket does (b"" past the end)."""

    def __init__(self, objects: dict[str, bytes]):
        self.objects = objects
        self.calls = 0
        self.bytes = 0

    def __call__(self, key: str, start: int, stop: int) -> bytes:
        self.calls += 1
        data = self.objects[key][start:stop]
        self.bytes += len(data)
        return data


@pytest.fixture
def l2(monkeypatch, tmp_path):
    blob, planes = make_l2()
    key = "dr1/level2/2025W33_2C/l2b-v27-2026-228/3/level2_2025W33_2C_0321_1D3_spx_l2b-v27-2026-228.fits"
    fake = FakeS3({key: blob})
    monkeypatch.setattr(settings, "CACHE_DIR", tmp_path / "cache")
    monkeypatch.setattr(s3range, "read_range", fake)
    return key, blob, planes, fake


def _sky(px: float, py: float) -> tuple[float, float]:
    ra, dec = _wcs(_image_header()).all_pix2world([[px, py]], 0)[0]
    return float(ra), float(dec)


def test_synthetic_file_has_the_real_flags_layout(l2):
    _, blob, _, _ = l2
    with fits.open(io.BytesIO(blob), disable_image_compression=True) as h:
        fh = h["FLAGS"].header
    assert (fh["ZCMPTYPE"], fh["ZTILE1"], fh["ZTILE2"], fh["NAXIS2"]) == ("RICE_1", NX, 1, NY)


def test_directory_matches_astropy_offsets(l2):
    key, blob, _, _ = l2
    d = s3range.hdu_directory(key)
    with fits.open(io.BytesIO(blob)) as h:
        infos = [h.fileinfo(i) for i in range(len(h))]
        names = [hdu.name for hdu in h]
    assert [x.name for x in d.hdus] == names == ["PRIMARY", "IMAGE", "FLAGS", "VARIANCE", "ZODI", "EPSF", "WCS-WAVE"]
    for x, info in zip(d.hdus, infos, strict=True):
        assert (x.header_offset, x.data_offset, x.end - x.data_offset) == (
            info["hdrLoc"],
            info["datLoc"],
            info["datSpan"],
        )
    assert d.wcs_wave == blob[infos[-1]["hdrLoc"] :]
    assert d.hdus[-1].end == len(blob)


def test_directory_is_cached_on_disk(l2, monkeypatch):
    key, _, _, fake = l2
    s3range.hdu_directory(key)
    n = fake.calls
    s3range._mem.clear()  # forget the in-memory copy: must come back from disk

    def boom(*a):
        raise AssertionError("directory should come from the disk cache")

    monkeypatch.setattr(s3range, "read_range", boom)
    d = s3range.hdu_directory(key)
    assert d["IMAGE"].header["NAXIS1"] == NX and fake.calls == n


@pytest.mark.parametrize(
    ("px", "py", "size"),
    [(150.2, 99.7, 2.0), (3.0, 50.0, 3.0), (298.0, 198.0, 4.0), (150.0, 100.0, 60.0), (40.0, 190.0, 1.0)],
)
def test_read_patch_equals_direct_slice(l2, px, py, size):
    key, blob, planes, _ = l2
    ra, dec = _sky(px, py)
    img = s3range.read_patch(key, ra, dec, size)
    x0, x1, y0, y1 = img.extra["bbox"]
    sl = (slice(y0, y1 + 1), slice(x0, x1 + 1))
    assert 0 <= x0 <= px <= x1 < NX or size < 2  # the target is inside its own patch
    np.testing.assert_array_equal(img.data, planes["IMAGE"][sl])
    np.testing.assert_array_equal(img.variance, planes["VARIANCE"][sl])
    np.testing.assert_array_equal(img.zodi, planes["ZODI"][sl])
    assert img.extra["flags"] == "ok"
    np.testing.assert_array_equal(img.flags, planes["FLAGS"][sl])  # RICE rows decompressed exactly
    assert img.data.dtype == np.float32 and img.flags.dtype == np.int32
    # header: like an IRSA cutout, every CRPIX (primary, 'A', 'W') shifts by the offset
    full = _image_header()
    for k, off in (("CRPIX1", x0), ("CRPIX2", y0), ("CRPIX1A", x0), ("CRPIX2A", y0), ("CRPIX1W", x0), ("CRPIX2W", y0)):
        assert img.header[k] == pytest.approx(float(full[k]) - off), k
    assert (img.header["NAXIS1"], img.header["NAXIS2"]) == (x1 - x0 + 1, y1 - y0 + 1)
    assert (img.header["PATCH_X0"], img.header["PATCH_Y0"]) == (x0, y0)
    # same sky position -> same pixel, minus the offset
    pf = _wcs(full).all_world2pix([[ra, dec]], 0)[0]
    pp = img.wcs.all_world2pix([[ra, dec]], 0)[0]
    np.testing.assert_allclose(pp, pf - [x0, y0], atol=1e-6)
    assert img.mjd == pytest.approx(full["MJD-AVG"])  # mid-exposure, not MJD-OBS (start)
    if size < 10:  # a small patch reads a fraction of the file (60' = the whole synthetic detector)
        assert img.extra["bytes"] < len(blob) / 2


def test_box_is_clipped_at_the_edges(l2):
    key, _, _, _ = l2
    img = s3range.read_patch(key, *_sky(0.0, 0.0), 5.0)
    x0, x1, y0, y1 = img.extra["bbox"]
    assert (x0, y0) == (0, 0) and x1 < 40 and y1 < 40 and img.data.shape == (y1 + 1, x1 + 1)


def test_no_overlap(l2):
    key, _, _, _ = l2
    with pytest.raises(NoOverlap):
        s3range.read_patch(key, *_sky(-40.0, 100.0), 1.0)
    with pytest.raises(NoOverlap):
        s3range.read_patch(key, *_sky(NX + 30.0, NY + 30.0), 2.0)
    with pytest.raises(NoOverlap):  # the other side of the sky
        s3range.read_patch(key, 89.0, -4.0, 5.0)


def test_box_rule_matches_real_irsa_cutouts():
    """Boxes of 5 real IBE cutouts of the same DR1 D3 file (2026-11-14), incl. clipped ones."""
    h = fits.Header.fromtextfile(REAL_HEADER)
    measured = [  # (ra, dec, size'), IRSA box (x0, x1, y0, y1) from the CRPIX shift and NAXISn
        (269.44623, 4.76870, 5, (1605, 1653, 254, 302)),
        (269.44623, 4.76870, 7, (1595, 1662, 245, 312)),
        (269.44623, 4.76870, 10, (1581, 1677, 230, 327)),
        (266.6197682, 3.7833895, 5, (0, 34, 976, 1024)),
        (269.9917058, 1.7020960, 5, (2011, 2039, 2006, 2039)),
    ]
    for ra, dec, size, box in measured:
        assert s3range.patch_box(h, ra, dec, size) == box
    with pytest.raises(NoOverlap):  # IBE answered 422 "Arrays do not overlap." here
        s3range.patch_box(h, 266.5516089, 3.7885772, 0.5)


def test_box_ties_break_like_irsa():
    """Centers within ~1e-4 px of a box-edge tie: IBE sees ra/dec as '%.7f' text, so must we.

    Full-precision (ra, dec) of detector pixels (-0.5, -0.5), (2039.5, 2039.5) and (-300, 1000)
    of the same DR1 D3 file, with the boxes IBE cut for them on 2026-11-14. Without rounding
    to 7 decimals the box was off by one pixel in each case.
    """
    h = fits.Header.fromtextfile(REAL_HEADER)
    measured = [
        (266.6965181635169, 5.487312459045988, 5, (0, 24, 0, 23)),
        (269.9986876068837, 1.684944635871196, 5, (2015, 2039, 2016, 2039)),
        (266.0915705279688, 3.8225308122590413, 70, (0, 40, 659, 1341)),
    ]
    for ra, dec, size, box in measured:
        assert s3range.patch_box(h, ra, dec, size) == box, (ra, dec, size)


def test_flags_unavailable_when_tiles_are_not_rows(monkeypatch, tmp_path):
    blob, planes = make_l2(flags_tile_rows=16)
    key = "dr1/level2/x/v/3/level2_2025W01_1A_0001_1D3_spx_v.fits"
    monkeypatch.setattr(settings, "CACHE_DIR", tmp_path / "cache")
    monkeypatch.setattr(s3range, "read_range", FakeS3({key: blob}))
    img = s3range.read_patch(key, *_sky(100.0, 100.0), 2.0)
    assert img.flags is None and img.extra["flags"] == "unavailable" and "ZTILE2" in img.extra["flags_error"]
    x0, x1, y0, y1 = img.extra["bbox"]
    np.testing.assert_array_equal(img.data, planes["IMAGE"][y0 : y1 + 1, x0 : x1 + 1])
    path = s3range.write_patch_fits(img, tmp_path / "p.fits")
    with fits.open(path) as h:
        assert "FLAGS" not in h and h["IMAGE"].header["PATCHFLG"] == "unavailable"
    assert fits_io.read_spherex(path).flags is None  # unknown, never "clean"


def test_write_patch_roundtrip_with_read_spherex(l2, tmp_path):
    key, blob, _, _ = l2
    img = s3range.read_patch(key, *_sky(120.0, 80.0), 3.0)
    path = s3range.write_patch_fits(img, tmp_path / "patch.fits")
    back = fits_io.read_spherex(path)
    np.testing.assert_array_equal(back.data, img.data)
    np.testing.assert_array_equal(back.flags, img.flags)
    np.testing.assert_array_equal(back.variance, img.variance)
    np.testing.assert_array_equal(back.zodi, img.zodi)
    assert (back.obs_id, back.detector) == (img.obs_id, img.detector)
    with fits.open(path) as h:
        assert [x.name for x in h] == ["PRIMARY", "IMAGE", "FLAGS", "VARIANCE", "ZODI", "WCS-WAVE"]
        assert h["FLAGS"].header["CRPIX1"] == img.header["CRPIX1"]
        assert h["WCS-WAVE"].header["TDIM3"] == "(2,9,14)"
    raw = path.read_bytes()
    assert raw.endswith(s3range.hdu_directory(key).wcs_wave)  # copied byte for byte
    assert len(raw) < 150_000  # mostly the 4 copied headers; an IBE cutout is >= ~4 MB (EPSF)


def _frame(key: str) -> FrameRef:
    return FrameRef(obs_id="2025W33_2C_0321_1", detector=3, mjd=60902.9, release="dr1", s3_key=key)


def test_fetch_patches_aligned_cached_and_reports_failures(monkeypatch, tmp_path):
    blob_a, _ = make_l2(seed=1)
    blob_b, _ = make_l2(seed=2)
    ka = "dr1/level2/w/v/3/level2_2025W33_2C_0001_1D3_spx_v.fits"
    kb = "qr3/level2/w/v/3/level2_2026W30_2A_0002_1D3_spx_v.fits"
    fake = FakeS3({ka: blob_a, kb: blob_b})
    monkeypatch.setattr(settings, "CACHE_DIR", tmp_path / "cache")
    monkeypatch.setattr(s3range, "read_range", fake)
    ra, dec = _sky(150.0, 100.0)
    frames = [_frame(kb), FrameRef(obs_id="x", detector=3, mjd=1.0, release="qr3", irsa_uri="ibe/data/spherex/" + ka)]
    paths = s3range.fetch_patches(frames, ra, dec, 2.0)
    assert [p.stem for p in paths] == [Path(kb).stem, Path(ka).stem]  # aligned with the input
    assert paths[0].parent.name == "qr3" and paths[1].parent.name == "dr1"
    assert fits_io.read_spherex(paths[0]).data.shape == fits_io.read_spherex(paths[1]).data.shape
    calls = fake.calls
    assert s3range.fetch_patches(frames, ra, dec, 2.0) == paths and fake.calls == calls  # disk cache

    far = _sky(NX + 100.0, 100.0)
    results, failures = s3range.fetch_patches_report([*frames, _frame("dr1/missing.fits")], *far, 1.0)
    assert results == [] and [f.s3_key for f, _ in failures][2] == "dr1/missing.fits"
    assert all(msg.startswith(("NoOverlap", "KeyError")) for _, msg in failures)
    mixed = s3range.fetch_patches([frames[0], _frame("dr1/missing.fits"), frames[1]], ra, dec, 2.0)
    assert mixed == [paths[0], None, paths[1]]  # aligned, None for the failed frame, never raises


def test_concurrent_reads_of_one_key_walk_once_and_never_fail(l2, monkeypatch):
    """16 threads on one key (different positions, then duplicate frames): one directory walk,
    one patch read per distinct patch, and no failed frame (on Windows, concurrent os.replace on
    the same cache file used to raise PermissionError [WinError 5])."""
    key, _, planes, fake = l2
    walks: list[str] = []
    real_walk = s3range._walk

    def slow_walk(k, reader):
        walks.append(k)
        time.sleep(0.05)  # widen the race window
        return real_walk(k, reader)

    monkeypatch.setattr(s3range, "_walk", slow_walk)
    positions = [_sky(20.0 + 15 * i, 30.0 + 8 * i) for i in range(16)]
    with ThreadPoolExecutor(16) as pool:
        imgs = list(pool.map(lambda p: s3range.read_patch(key, *p, 2.0), positions))
    assert walks == [key]
    for img in imgs:
        x0, x1, y0, y1 = img.extra["bbox"]
        np.testing.assert_array_equal(img.data, planes["IMAGE"][y0 : y1 + 1, x0 : x1 + 1])

    for run in range(5):  # the same frame 16 times in one batch
        calls = fake.calls
        results, failures = s3range.fetch_patches_report([_frame(key)] * 16, *positions[run], 3.0 + run)
        assert failures == [] and len({p for _, p in results}) == 1
        assert fake.calls - calls <= 5  # IMAGE, VARIANCE, ZODI, FLAGS descriptors + heap: once
    assert walks == [key]
    assert not list(settings.CACHE_DIR.rglob("*.part"))


def test_cache_write_failures_never_fail_a_read(l2, monkeypatch):
    """Caches are optional: a failing os.replace (Windows sharing violation) must not fail a frame."""
    key, _, planes, _ = l2
    monkeypatch.setattr(s3range.time, "sleep", lambda s: None)

    def denied(src, dst):
        raise PermissionError(13, "Access is denied", str(dst))

    monkeypatch.setattr(s3range.os, "replace", denied)
    ra, dec = _sky(150.0, 100.0)
    img = s3range.read_patch(key, ra, dec, 2.0)  # the directory cannot be cached: still fine
    x0, x1, y0, y1 = img.extra["bbox"]
    np.testing.assert_array_equal(img.data, planes["IMAGE"][y0 : y1 + 1, x0 : x1 + 1])
    assert not s3range._dir_cache_path(key).exists()
    with pytest.raises(PermissionError):  # nobody wrote the patch: a real failure, reported
        s3range.fetch_patch(_frame(key), ra, dec, 2.0)

    def lost_race(src, dst):  # another process wrote the same file first and still has it open
        Path(dst).write_bytes(Path(src).read_bytes())
        raise PermissionError(13, "Access is denied", str(dst))

    monkeypatch.setattr(s3range.os, "replace", lost_race)
    path = s3range.fetch_patch(_frame(key), ra, dec, 2.0)
    np.testing.assert_array_equal(fits_io.read_spherex(path).data, img.data)
    assert not list(settings.CACHE_DIR.rglob("*.part"))  # temp files are always cleaned up


class _Resp:
    def __init__(self, status: int, body: bytes = b"", headers: dict | None = None):
        self.status_code, self.content, self.headers = status, body, headers or {}

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def raise_for_status(self):
        import requests

        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}", response=self)


class _Session:
    def __init__(self, responses):
        self.responses = list(responses)
        self.ranges = []

    def get(self, url, headers, stream, timeout):
        self.ranges.append(headers["Range"])
        return self.responses.pop(0)


def test_read_range_retries_and_guards(monkeypatch):
    monkeypatch.setattr(s3range.time, "sleep", lambda s: None)
    sess = _Session([_Resp(503), _Resp(206, b"abcd", {"Content-Range": "bytes 10-13/100"})])
    monkeypatch.setattr(s3range, "_session", lambda: sess)
    assert s3range.read_range("k", 10, 14) == b"abcd" and sess.ranges == ["bytes=10-13"] * 2
    sess = _Session([_Resp(206, b"xy", {"Content-Range": "bytes 98-99/100"})])  # short read at EOF is fine
    monkeypatch.setattr(s3range, "_session", lambda: sess)
    assert s3range.read_range("k", 98, 120) == b"xy"
    monkeypatch.setattr(s3range, "_session", lambda: _Session([_Resp(416)]))
    assert s3range.read_range("k", 200, 300) == b""
    monkeypatch.setattr(s3range, "_session", lambda: _Session([_Resp(200, b"whole file")]))
    with pytest.raises(OSError, match="ignored the Range"):
        s3range.read_range("k", 0, 10)
    monkeypatch.setattr(s3range, "_session", lambda: _Session([_Resp(503)] * s3range.RANGE_RETRIES))
    with pytest.raises(OSError, match="failed after"):
        s3range.read_range("k", 0, 10)
    # a 206 for the wrong range is never returned as if it were the requested bytes
    sess = _Session([_Resp(206, b"abcd", {"Content-Range": "bytes 0-3/100"}), _Resp(206, b"klmn", {})])
    monkeypatch.setattr(s3range, "_session", lambda: sess)
    assert s3range.read_range("k", 10, 14) == b"klmn" and len(sess.ranges) == 2


def test_read_tail_suffix_range(monkeypatch):
    """One ``bytes=-N`` request returns the tail and the object size (from Content-Range)."""
    monkeypatch.setattr(s3range.time, "sleep", lambda s: None)
    sess = _Session([_Resp(503), _Resp(206, b"wxyz", {"Content-Range": "bytes 96-99/100"})])
    monkeypatch.setattr(s3range, "_session", lambda: sess)
    assert s3range.read_tail("k", 4) == (b"wxyz", 100) and sess.ranges == ["bytes=-4"] * 2
    sess = _Session([_Resp(206, b"tiny", {"Content-Range": "bytes 0-3/4"})])  # object shorter than asked
    monkeypatch.setattr(s3range, "_session", lambda: sess)
    assert s3range.read_tail("k", 5760) == (b"tiny", 4)
    for bad in (
        _Resp(206, b"wx", {"Content-Range": "bytes 96-99/100"}),  # short body
        _Resp(206, b"wxyz", {}),  # no Content-Range: the size is unknown
        _Resp(206, b"wxyz", {"Content-Range": "bytes 90-93/100"}),  # not the tail
    ):
        monkeypatch.setattr(s3range, "_session", lambda bad=bad: _Session([bad] * s3range.RANGE_RETRIES))
        with pytest.raises(OSError, match="suffix read failed"):
            s3range.read_tail("k", 4)
    monkeypatch.setattr(s3range, "_session", lambda: _Session([_Resp(200, b"whole file")]))
    with pytest.raises(OSError, match="ignored the Range"):
        s3range.read_tail("k", 4)
    with pytest.raises(ValueError):
        s3range.read_tail("k", 0)


def test_session_loads_the_ca_bundle_once_and_keeps_verifying(monkeypatch):
    """Stock requests re-parses the CA bundle on every new TLS connection (~0.2-0.7 s of CPU each, measured):
    the adapter shares one pre-loaded SSLContext, still CERT_REQUIRED with hostname checks."""
    import ssl

    monkeypatch.delenv("REQUESTS_CA_BUNDLE", raising=False)
    monkeypatch.delenv("CURL_CA_BUNDLE", raising=False)
    adapter = s3range._adapter()
    assert isinstance(adapter, s3range._PreloadedCAAdapter)
    ctx = adapter._ssl_context
    assert ctx.verify_mode == ssl.CERT_REQUIRED and ctx.check_hostname
    assert ctx.cert_store_stats()["x509_ca"] > 50  # requests' default bundle, loaded once

    class Pool:
        ca_certs = ca_cert_dir = cert_reqs = None

        def __init__(self, ssl_context=None):
            self.conn_kw = {"ssl_context": ssl_context}

    pool = Pool(ctx)
    adapter.cert_verify(pool, "https://nasa-irsa-spherex.s3.us-east-1.amazonaws.com/x", True, None)
    assert pool.cert_reqs == "CERT_REQUIRED" and pool.ca_certs is None  # verified with the shared context
    other = Pool()  # a pool without the shared context (e.g. through a proxy manager) keeps the bundle path
    adapter.cert_verify(other, "https://nasa-irsa-spherex.s3.us-east-1.amazonaws.com/x", True, None)
    assert other.ca_certs == requests.utils.DEFAULT_CA_BUNDLE_PATH
    custom = Pool()
    adapter.cert_verify(custom, "https://example.org/x", str(REAL_HEADER), None)  # a custom bundle path
    assert custom.ca_certs == str(REAL_HEADER)  # stock behaviour for anything but the default bundle
    monkeypatch.setenv("REQUESTS_CA_BUNDLE", str(REAL_HEADER))
    assert type(s3range._adapter()) is requests.adapters.HTTPAdapter


def test_preloaded_adapter_sends_custom_trust_through_a_stock_adapter(monkeypatch):
    """urllib3 loads a custom CA (verify=<path>), a client cert or CERT_NONE INTO the pool's SSLContext: those
    requests must never reach the shared one."""
    monkeypatch.delenv("REQUESTS_CA_BUNDLE", raising=False)
    monkeypatch.delenv("CURL_CA_BUNDLE", raising=False)
    adapter = s3range._adapter()
    seen = []
    monkeypatch.setattr(adapter._stock, "send", lambda req, **kw: seen.append((kw["verify"], kw["cert"])) or "stock")
    req = requests.Request("GET", "https://127.0.0.1:9/").prepare()
    assert adapter.send(req, verify="custom.pem") == "stock"
    assert adapter.send(req, verify=False) == "stock"
    assert adapter.send(req, verify=True, cert="client.pem") == "stock"
    assert seen == [("custom.pem", None), (False, None), (True, "client.pem")]
    with pytest.raises(requests.ConnectionError):  # the default goes through the shared context (port 9: closed)
        adapter.send(req, verify=True, timeout=5)


def _self_signed(tmp_path: Path) -> tuple[Path, Path]:
    import shutil
    import subprocess

    openssl = shutil.which("openssl")
    if openssl is None:
        pytest.skip("openssl not available to make a test certificate")
    crt, key = tmp_path / "self.crt", tmp_path / "self.key"
    cmd = [openssl, "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "2", "-subj", "/CN=localhost"]
    cmd += ["-addext", "subjectAltName=DNS:localhost,IP:127.0.0.1", "-keyout", str(key), "-out", str(crt)]
    try:
        subprocess.run(cmd, check=True, capture_output=True, timeout=60)
    except (OSError, subprocess.SubprocessError) as e:
        pytest.skip(f"openssl could not make a test certificate: {e}")
    return crt, key


def _https_server(crt: Path, key: Path):
    import ssl

    class Ok(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Length", "2")
            self.end_headers()
            self.wfile.write(b"ok")

        def log_message(self, *a):
            pass

    httpd = ThreadingHTTPServer(("127.0.0.1", 0), Ok)
    httpd.handle_error = lambda *a: None  # failed handshakes are the point of the test
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(str(crt), str(key))
    httpd.socket = ctx.wrap_socket(httpd.socket, server_side=True)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd


def test_shared_session_rejects_untrusted_certs_even_after_custom_trust(tmp_path, monkeypatch):
    """End to end on localhost: a self-signed certificate is rejected; trusting it for ONE request
    (verify=<its path>) or skipping verification (verify=False) never makes the shared session trust it."""
    import ssl
    import warnings as _w

    crt, key = _self_signed(tmp_path)
    for var in ("REQUESTS_CA_BUNDLE", "CURL_CA_BUNDLE", "HTTPS_PROXY", "https_proxy", "ALL_PROXY", "all_proxy"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("NO_PROXY", "localhost,127.0.0.1")
    monkeypatch.setenv("no_proxy", "localhost,127.0.0.1")
    monkeypatch.setattr(s3range, "_SESSION", None)
    servers = [_https_server(crt, key), _https_server(crt, key)]
    sess = s3range._session()
    try:
        ctx = sess.adapters["https://"]._ssl_context
        n_ca = ctx.cert_store_stats()["x509_ca"]
        url = f"https://localhost:{servers[0].server_address[1]}/"
        with pytest.raises(requests.exceptions.SSLError):
            sess.get(url, timeout=10)
        assert sess.get(url, timeout=10, verify=str(crt)).content == b"ok"
        with _w.catch_warnings():
            _w.simplefilter("ignore")
            assert sess.get(url, timeout=10, verify=False).content == b"ok"
        for port in (servers[0].server_address[1], servers[1].server_address[1]):
            with pytest.raises(requests.exceptions.SSLError):
                sess.get(f"https://localhost:{port}/", timeout=10)
        assert ctx.verify_mode == ssl.CERT_REQUIRED and ctx.check_hostname
        assert ctx.cert_store_stats()["x509_ca"] == n_ca  # nothing was added to the shared trust store
    finally:
        sess.close()
        for httpd in servers:
            httpd.shutdown()
            httpd.server_close()


def test_read_range_meta_reports_object_size_and_etag(monkeypatch):
    sess = _Session([_Resp(206, b"abcd", {"Content-Range": "bytes 10-13/100", "ETag": '"e1"'})])
    monkeypatch.setattr(s3range, "_session", lambda: sess)
    assert s3range.read_range_meta("k", 10, 14) == (b"abcd", 100, '"e1"')
    monkeypatch.setattr(s3range, "_session", lambda: _Session([_Resp(206, b"abcd", {})]))
    assert s3range.read_range_meta("k", 10, 14) == (b"abcd", None, "")
    monkeypatch.setattr(s3range, "_session", lambda: _Session([_Resp(416)]))
    assert s3range.read_range_meta("k", 200, 300) == (b"", None, "")


def test_parse_header_helper():
    h = fits.Header([("XTENSION", "IMAGE"), ("BITPIX", -32), ("NAXIS", 0), ("EXTNAME", "X")])
    raw = h.tostring().encode("ascii")
    got, hlen = s3range.parse_header(raw + b"\0" * 100)
    assert got["EXTNAME"] == "X" and hlen == 2880
    assert s3range.parse_header(raw[:1600]) is None  # END not read yet
    assert s3range.parse_header(b"") is None
    with pytest.raises(ValueError, match="no FITS header"):
        s3range.parse_header(b"\0" * 2880)
    assert s3range.data_size(fits.Header([("BITPIX", -32), ("NAXIS", 2), ("NAXIS1", 3), ("NAXIS2", 2)])) == 24
    assert s3range.padded(1) == 2880 and s3range.padded(2880) == 2880


def test_read_range_retries_a_body_cut_mid_transfer(monkeypatch):
    """S3 closes the connection after the 206 status and half the body (requests raises
    ChunkedEncodingError, not ConnectionError): the read must be retried, not fail the frame."""
    body = bytes(range(256)) * 120
    hits: list[str] = []

    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def do_GET(self):
            a, b = (int(v) for v in re.match(r"bytes=(\d+)-(\d+)", self.headers["Range"]).groups())
            part = body[a : b + 1]
            hits.append(self.headers["Range"])
            self.send_response(206)
            self.send_header("Content-Length", str(len(part)))
            self.send_header("Content-Range", f"bytes {a}-{b}/{len(body)}")
            self.end_headers()
            if len(hits) == 1:  # first answer: half the promised bytes, then hang up
                self.wfile.write(part[: len(part) // 2])
                self.wfile.flush()
                self.close_connection = True
                return
            self.wfile.write(part)

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    session = requests.Session()
    session.trust_env = False  # never route 127.0.0.1 through a proxy from the environment
    try:
        monkeypatch.setattr(settings, "S3_HTTPS", f"http://127.0.0.1:{server.server_address[1]}")
        monkeypatch.setattr(s3range, "_session", lambda: session)
        monkeypatch.setattr(s3range.time, "sleep", lambda s: None)
        assert s3range.read_range("dr1/x.fits", 1000, 21000) == body[1000:21000]
        assert hits == ["bytes=1000-20999"] * 2
    finally:
        session.close()
        server.shutdown()
        server.server_close()


def test_read_patch_carries_the_wave_table(l2, tmp_path, monkeypatch):
    """An in-memory patch has the file's WCS-WAVE table (``wave``), so ``wavelength_at`` works without writing and
    re-reading the patch (WS2 photometry flagged every in-memory patch 'no_wavelength')."""
    from errante.imaging import photometry

    key, blob, _, _ = l2
    ra, dec = _sky(150.3, 99.8)
    img = s3range.read_patch(key, ra, dec, 3.0)
    assert img.wave is not None and "wave_error" not in img.extra
    with fits.open(io.BytesIO(blob)) as full:
        want = fits_io.wavelength_at(full, ra, dec)
    assert img.wavelength_at(ra, dec) == pytest.approx(want, abs=1e-12)
    back = fits_io.read_spherex(s3range.write_patch_fits(img, tmp_path / "p.fits"))
    assert img.wavelength_at(ra, dec) == pytest.approx(back.wavelength_at(ra, dec), abs=1e-12)
    np.testing.assert_array_equal(img.wave.wavelength, back.wave.wavelength)
    assert (img.mjd, img.date_obs) == (back.mjd, back.date_obs)  # mid-exposure instant (DATE-AVG), not DATE-OBS
    m = photometry.measure(img, ra, dec)
    assert m.wavelength_um == pytest.approx(want[0], abs=1e-12) and "no_wavelength" not in m.flags

    def broken(hdu):
        raise ValueError("VALUES shape (1,) != (14, 9, 2)")

    monkeypatch.setattr(s3range.fits_io.WaveTable, "from_hdu", classmethod(lambda cls, hdu: broken(hdu)))
    s3range.wave_table_from_bytes.cache_clear()
    bad = s3range.read_patch(key, *_sky(100.0, 50.0), 2.0)  # an unusable table never fails the patch
    assert bad.wave is None and bad.extra["wave_error"].startswith("ValueError")
    assert bad.wavelength_at(*_sky(100.0, 50.0)) is None
    s3range.wave_table_from_bytes.cache_clear()


# Cards astropy cannot parse (found by fuzzing a real-layout WCS-WAVE, review 2026-11-15): VerifyError and a
# _CorruptedHDU without .data (AttributeError) escaped read_patch's except tuple, so the whole patch failed.
_CORRUPT_WAVE_CARDS = {
    "VerifyError": (b"TFORM1  = '9J      '" + b" " * 10, b"TFORM1  = 821-9Y=2AC9'.5=YXZ70"),
    "AttributeError": (
        b"XTENSION= 'BINTABLE'           / binary table extension",
        b"XTENSION= 5  -Z'252'.58742YB.1 / binary table extension",
    ),
}


@pytest.mark.filterwarnings("ignore::astropy.io.fits.verify.VerifyWarning")  # the corrupt card, cached as JSON
@pytest.mark.parametrize("astropy_error", sorted(_CORRUPT_WAVE_CARDS))
def test_an_unparsable_wave_card_never_fails_the_patch(l2, monkeypatch, astropy_error):
    key, blob, _, fake = l2
    raw = s3range.hdu_directory(key).wcs_wave
    old, new = _CORRUPT_WAVE_CARDS[astropy_error]
    assert raw.count(old) == 1 and len(new) == len(old)
    bad_raw = raw.replace(old, new)
    s3range.wave_table_from_bytes.cache_clear()
    with pytest.raises(ValueError, match="unparsable WCS-WAVE") as err:
        s3range.wave_table_from_bytes(bad_raw)
    assert type(err.value.__cause__).__name__ == astropy_error  # what astropy raised, kept as the cause
    bad_key = key.replace("_0321_", "_0322_")
    fake.objects[bad_key] = blob[: -len(raw)] + bad_raw
    ra, dec = _sky(150.3, 99.8)
    img = s3range.read_patch(bad_key, ra, dec, 3.0)
    assert img.wave is None and img.extra["wave_error"].startswith("ValueError: unparsable WCS-WAVE")
    assert img.wavelength_at(ra, dec) is None
    np.testing.assert_array_equal(img.data, s3range.read_patch(key, ra, dec, 3.0).data)  # the pixels are intact


def test_read_range_meta_honours_a_deadline_and_a_cancel_flag(monkeypatch):
    """A caller with a deadline (point_series) never waits HTTP_TIMEOUT_S (120 s) x 4 attempts: each attempt's
    timeout is what is left, no retry or backoff runs past it, and a cancelled read sends nothing more."""

    class Stalled:
        def __init__(self):
            self.timeouts = []

        def get(self, url, headers, stream, timeout):
            self.timeouts.append(timeout)
            time.sleep(timeout)  # a server that never answers
            raise requests.ReadTimeout("stalled")

    for read in (lambda **kw: s3range.read_range_meta("k", 0, 10, **kw), lambda **kw: s3range.read_tail("k", 4, **kw)):
        sess = Stalled()
        monkeypatch.setattr(s3range, "_session", lambda sess=sess: sess)
        t0 = time.monotonic()
        with pytest.raises(TimeoutError):
            read(deadline=t0 + 0.4)
        assert time.monotonic() - t0 < 0.9 and sess.timeouts and max(sess.timeouts) <= 0.4 + 1e-6
        cancel = threading.Event()
        cancel.set()
        sess.timeouts.clear()
        with pytest.raises(TimeoutError):
            read(cancel=cancel)
        assert sess.timeouts == []  # cancelled: no request at all

    # without a deadline nothing changes: the configured timeout per attempt
    class Ok:
        def __init__(self):
            self.timeouts = []

        def get(self, url, headers, stream, timeout):
            self.timeouts.append(timeout)
            return _Resp(206, b"abcd", {"Content-Range": "bytes 10-13/100"})

    ok = Ok()
    monkeypatch.setattr(s3range, "_session", lambda: ok)
    assert s3range.read_range("k", 10, 14) == b"abcd" and ok.timeouts == [settings.HTTP_TIMEOUT_S]


def test_s3_requests_in_flight_are_capped_process_wide(monkeypatch):
    """Every s3range request takes one of S3_MAX_CONNECTIONS process-wide slots, the size of the session's
    connection pool: concurrent readers (two point series, a field build) can never overflow it."""
    monkeypatch.setattr(s3range, "S3_MAX_CONNECTIONS", 3)
    monkeypatch.setattr(s3range, "_REQUEST_SLOTS", None)
    lock = threading.Lock()
    state = {"now": 0, "peak": 0}

    class Counting:
        def get(self, url, headers, stream, timeout):
            with lock:
                state["now"] += 1
                state["peak"] = max(state["peak"], state["now"])
            time.sleep(0.02)
            with lock:
                state["now"] -= 1
            return _Resp(206, b"abcd", {"Content-Range": "bytes 10-13/100"})

    monkeypatch.setattr(s3range, "_session", lambda: Counting())
    with ThreadPoolExecutor(12) as pool:
        assert list(pool.map(lambda _: s3range.read_range("k", 10, 14), range(24))) == [b"abcd"] * 24
    assert state["peak"] == 3
    adapter = s3range._adapter()
    assert adapter.poolmanager.connection_pool_kw["maxsize"] == 3  # the pool keeps every connection in use


def test_header_without_end_is_bounded():
    """A corrupt header with no END card fails after a bounded read, not at EOF of a 60 MB file."""
    blob = b"SIMPLE  =                    T" + b" " * 50 + b"COMMENT " + b"x" * 72
    blob += b"COMMENT " * (8 * 1024 * 1024 // 8)
    fake = FakeS3({"k": blob})
    with pytest.raises(ValueError, match="END"):
        s3range.hdu_directory("k", reader=fake, use_cache=False)
    assert fake.bytes <= s3range.MAX_HEADER_BYTES + 12 * 2880


# --- live ------------------------------------------------------------------------

needs_network = pytest.mark.skipif(os.environ.get("ERRANTE_NETWORK_TESTS") != "1", reason="set ERRANTE_NETWORK_TESTS=1")
# A DR1 D3 frame that covers Barnard's Star (checked 2026-11-14 against IBE cutouts).
BARNARD_KEY = "dr1/level2/2025W33_2C/l2b-v27-2026-228/3/level2_2025W33_2C_0321_1D3_spx_l2b-v27-2026-228.fits"
BARNARD = (269.44623, 4.76870)


@pytest.mark.network
@needs_network
def test_real_directory(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "CACHE_DIR", tmp_path)
    d = s3range.hdu_directory(BARNARD_KEY)
    assert [h.name for h in d.hdus] == ["PRIMARY", "IMAGE", "FLAGS", "VARIANCE", "ZODI", "EPSF", "WCS-WAVE"]
    im, fl = d["IMAGE"].header, d["FLAGS"].header
    assert (im["BITPIX"], im["NAXIS1"], im["NAXIS2"]) == (-32, 2040, 2040)
    assert (fl["ZCMPTYPE"].strip(), fl["ZTILE1"], fl["ZTILE2"]) == ("RICE_1", 2040, 1)
    assert d["WCS-WAVE"].header["TDIM3"] == "(2,9,14)"  # D3 grid is 9x14
    assert d.hdus[-1].end % 2880 == 0


@pytest.mark.network
@needs_network
def test_real_tail_and_verified_tls():
    tail, size = s3range.read_tail(BARNARD_KEY, 5760)
    assert size % 2880 == 0 and tail.startswith(b"XTENSION= 'BINTABLE'") and b"WCS-WAVE" in tail[:2880]
    assert s3range.read_range(BARNARD_KEY, size - 5760, size) == tail
    adapter = s3range._session().adapters["https://"]
    pools = list(adapter.poolmanager.pools._container.values())
    conns = [
        c for pool in pools for c in list(pool.pool.queue) if c is not None and getattr(c, "sock", None) is not None
    ]
    assert conns and all(c.is_verified for c in conns)
    if isinstance(adapter, s3range._PreloadedCAAdapter):  # the bundle is not re-loaded per connection
        assert all(pool.conn_kw.get("ssl_context") is adapter._ssl_context and pool.ca_certs is None for pool in pools)
    data, size2, etag = s3range.read_range_meta(BARNARD_KEY, 0, 80)
    assert data.startswith(b"SIMPLE  =") and size2 == size and len(etag) > 2  # S3 names the object it read


@pytest.mark.network
@needs_network
def test_real_patch_equals_ibe_cutout(tmp_path, monkeypatch):
    from errante.data.cutouts import fetch_cutout

    monkeypatch.setattr(settings, "CACHE_DIR", tmp_path)
    img = s3range.read_patch(BARNARD_KEY, *BARNARD, 5.0)
    assert img.extra["flags"] == "ok" and img.data.shape == (49, 49)
    cut = fetch_cutout(_frame(BARNARD_KEY), *BARNARD, 5.0)
    with fits.open(cut) as h:
        for name, mine in (("IMAGE", img.data), ("FLAGS", img.flags), ("VARIANCE", img.variance), ("ZODI", img.zodi)):
            np.testing.assert_array_equal(mine, h[name].data, err_msg=name)
        ch = h["IMAGE"].header
        for k in ("CRPIX1", "CRPIX2", "CRPIX1A", "CRPIX2A", "CRPIX1W", "CRPIX2W", "NAXIS1", "NAXIS2"):
            assert img.header[k] == ch[k], k
        np.testing.assert_allclose(img.wcs.all_world2pix([BARNARD], 0), _wcs(ch).all_world2pix([BARNARD], 0))
    # the written patch keeps a working spectral WCS (alternate 'W' + WCS-WAVE)
    path = s3range.write_patch_fits(img, tmp_path / "p.fits")
    with fits.open(path) as h, warnings.catch_warnings():
        warnings.simplefilter("ignore")
        sw = WCS(h["IMAGE"].header, fobj=h, key="W")
        sw.sip = None
        lam, bw = sw.pixel_to_world_values(*img.wcs.all_world2pix([BARNARD], 0)[0])
    assert 1.6 < float(lam) < 2.42 and 0 < float(bw) < 0.2  # D3 band
    # ... and the patch in memory already has it (WCS-WAVE table attached), equal to the written patch
    assert img.wave is not None
    assert img.wavelength_at(*BARNARD) == pytest.approx(fits_io.read_spherex(path).wavelength_at(*BARNARD), abs=1e-12)
