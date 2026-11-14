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
from errante.data.cutouts import FetchError, NoOverlap
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
    with pytest.raises(FetchError) as ei:
        s3range.fetch_patches([frames[0], _frame("dr1/missing.fits"), frames[1]], ra, dec, 2.0)
    assert [f.s3_key for f, _ in ei.value.results] == [kb, None]
    assert [f.s3_key for f, _ in ei.value.failures] == ["dr1/missing.fits"]


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
