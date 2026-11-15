"""WS1 point series: every exposure at a sky point as small stamps read from S3 (errante.data.point).

Offline tests use synthetic L2 files with the real layout (docs/DATA.md §2: PRIMARY, IMAGE, FLAGS
tile-compressed RICE_1 with one tile per row, VARIANCE, ZODI, EPSF, WCS-WAVE; VARIANCE/ZODI headers
shorter than the IMAGE one; the real DR1 D3 TAN-SIP header with its ``[CALIB] spectral_wcs`` HISTORY),
served by a fake Range reader. Live checks are marked ``network``.
"""

from __future__ import annotations

import hashlib
import io
import json
import logging
import math
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

from errante import cli, settings
from errante.data import fits_io, irsa, point, s3range
from errante.data.cutouts import NoOverlap
from errante.data.s3 import parse_key
from errante.models import FrameRef, SearchResult, SkyCoord

FIXTURES = Path(__file__).parent / "fixtures" / "ws1"
REAL_HEADER = FIXTURES / "dr1_D3_image_header.txt"
NX, NY = 300, 200  # non-square on purpose: catches x/y swaps
SWCS_D3 = "019f4f99-19af-763f-8f2e-b7dc6cd00055"  # the real D3 spectral_wcs calibration id (897 files)


def _wcs(h: fits.Header) -> WCS:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return WCS(h)


def _image_header(detector: int = 3, swcs: str | None = SWCS_D3) -> fits.Header:
    real = fits.Header.fromtextfile(REAL_HEADER)
    h = fits.Header([c for c in real.cards if not (c.keyword == "HISTORY" and "spectral_wcs" in str(c.value))])
    h["NAXIS1"], h["NAXIS2"] = NX, NY
    h["CRPIX1"], h["CRPIX2"] = NX / 2 + 0.5, NY / 2 + 0.5
    h["DETECTOR"] = detector
    if swcs is not None:
        h.add_history(f"[CALIB] spectral_wcs {swcs}")
    return h


def _plane_header(h: fits.Header, extra_cards: int = 0) -> fits.Header:
    """Like a real VARIANCE/ZODI header: WCS and times only (4 blocks instead of the IMAGE header's 8)."""
    out = fits.Header(
        [
            c
            for c in h.cards
            if point._CEL_CARD.match(c.keyword) or point._ALT_CARD.match(c.keyword) or c.keyword.startswith("MJD")
        ]
    )
    for i in range(extra_cards):
        out[f"PAD{i:05d}"] = (i, "padding to change the header length")
    return out


def make_l2(
    seed: int = 0,
    *,
    detector: int = 3,
    swcs: str | None = SWCS_D3,
    flags_tile_rows: int = 1,
    var_extra_cards: int = 0,
    wave_shift: float = 0.0,
) -> tuple[bytes, dict[str, np.ndarray]]:
    """A small L2-like MEF as bytes, plus the original planes."""
    rng = np.random.default_rng(seed)
    img = rng.normal(1.0, 0.1, (NY, NX)).astype(np.float32)
    img[101, 151] = np.nan
    img[100, 150] = 50.0  # a "star"
    var = rng.uniform(0.01, 0.02, (NY, NX)).astype(np.float32)
    zodi = rng.uniform(0.2, 0.3, (NY, NX)).astype(np.float32)
    flags = (rng.integers(0, 1 << 29, (NY, NX)) & rng.integers(0, 1 << 29, (NY, NX))).astype(np.int32)
    flags[:, :40] = 0  # long runs of zeros, like a real mask
    h = _image_header(detector, swcs)
    ph = _plane_header(h)
    hdus = [fits.PrimaryHDU(header=fits.Header([("VERSION", "7.0.5")]))]
    hdus.append(fits.ImageHDU(img, header=h, name="IMAGE"))
    hdus.append(
        fits.CompImageHDU(
            flags, header=ph.copy(), name="FLAGS", compression_type="RICE_1", tile_shape=(flags_tile_rows, NX)
        )
    )
    vh = _plane_header(h, var_extra_cards)
    vh["BUNIT"] = "MJy2 / sr2"
    hdus.append(fits.ImageHDU(var, header=vh, name="VARIANCE"))
    zh = ph.copy()
    zh["BUNIT"] = "MJy / sr"
    hdus.append(fits.ImageHDU(zodi, header=zh, name="ZODI"))
    hdus.append(
        fits.BinTableHDU.from_columns(
            [
                fits.Column(name="BINX", format="J", array=np.arange(7)),
                fits.Column(name="EPSF", format="9D", array=rng.normal(size=(7, 9))),
            ],
            name="EPSF",
        )
    )
    values = np.random.default_rng(99).uniform(1.6, 2.4, (1, 14, 9, 2)).astype(np.float32) + np.float32(wave_shift)
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
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        fits.HDUList(hdus).writeto(buf)
    return buf.getvalue(), {"IMAGE": img, "VARIANCE": var, "ZODI": zodi, "FLAGS": flags}


class FakeS3:
    """Serves byte ranges (b"" past the end) and suffix reads of in-memory objects, like the S3 bucket,
    with the object's size and ETag (an MD5 of its bytes, as S3 gives for single-part uploads)."""

    def __init__(self, objects: dict[str, bytes]):
        self.objects = objects
        self.calls = 0
        self.tails = 0
        self.bytes = 0
        self._etags: dict[int, str] = {}
        self._lock = threading.Lock()

    def __call__(self, key: str, start: int, stop: int) -> bytes:
        with self._lock:
            self.calls += 1
        data = self.objects[key][start:stop]
        with self._lock:
            self.bytes += len(data)
        return data

    def etag(self, key: str) -> str:
        obj = self.objects[key]
        if id(obj) not in self._etags:
            self._etags[id(obj)] = '"' + hashlib.md5(obj).hexdigest() + '"'
        return self._etags[id(obj)]

    def meta(self, key: str, start: int, stop: int, **limits) -> tuple[bytes, int | None, str]:
        data = self(key, start, stop)
        return data, len(self.objects[key]), self.etag(key)

    def tail(self, key: str, nbytes: int, **limits) -> tuple[bytes, int]:
        with self._lock:
            self.tails += 1
        obj = self.objects[key]
        return obj[-nbytes:], len(obj)


@pytest.fixture(autouse=True)
def _isolated(monkeypatch, tmp_path):
    """Fresh caches and hints for every test (they are process-wide in errante.data.point)."""
    monkeypatch.setattr(settings, "CACHE_DIR", tmp_path / "cache")
    for cache in (point._learned, point._layout_mem, point._wave_mem, s3range._mem):
        cache.clear()
    yield
    for cache in (point._learned, point._layout_mem, point._wave_mem, s3range._mem):
        cache.clear()


def _key(name: str, detector: int = 3, release: str = "dr1") -> str:
    return f"{release}/level2/2025W33_2C/l2b-v27-2026-228/{detector}/level2_{name}D{detector}_spx_l2b-v27-2026-228.fits"


def _frame(key: str, mjd: float = 60902.9) -> FrameRef:
    p = parse_key(key)
    return FrameRef(obs_id=p.obs_id, detector=p.detector, mjd=mjd, release=p.release, s3_key=key)


@pytest.fixture
def fake(monkeypatch):
    objects: dict[str, bytes] = {}
    f = FakeS3(objects)
    monkeypatch.setattr(s3range, "read_range", f)
    monkeypatch.setattr(s3range, "read_range_meta", f.meta, raising=False)
    monkeypatch.setattr(s3range, "read_tail", f.tail)
    return f


def _sky(px: float, py: float) -> tuple[float, float]:
    ra, dec = _wcs(_image_header()).all_pix2world([[px, py]], 0)[0]
    return float(ra), float(dec)


def _full(blob: bytes) -> tuple[fits.Header, fits_io.WaveTable]:
    with fits.open(io.BytesIO(blob)) as h:
        return h["IMAGE"].header.copy(), fits_io.WaveTable.from_hdu(h["WCS-WAVE"])


# --- stamps --------------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("px", "py", "box"),
    [(150.2, 99.7, 11), (150.0, 100.0, 7), (2.0, 50.4, 11), (298.6, 199.2, 11), (40.0, 190.0, 1), (77.5, 3.5, 12)],
)
def test_stamp_equals_the_file_pixels(fake, px, py, box):
    blob, planes = make_l2()
    key = _key("2025W33_2C_0321_1")
    fake.objects[key] = blob
    ra, dec = _sky(px, py)
    s = point.read_point_sample(_frame(key), ra, dec, box)
    x0, y0 = s.x0, s.y0
    ny, nx = s.shape
    sl = (slice(y0, y0 + ny), slice(x0, x0 + nx))
    np.testing.assert_array_equal(s.image, planes["IMAGE"][sl])
    np.testing.assert_array_equal(s.variance, planes["VARIANCE"][sl])
    np.testing.assert_array_equal(s.zodi, planes["ZODI"][sl])
    np.testing.assert_array_equal(s.flags, planes["FLAGS"][sl])  # RICE rows decoded exactly
    assert s.image.dtype == np.float32 and s.flags.dtype == np.int32
    # box rule: box_px square centred on the pixel holding the point (IBE rule), clipped at the edges
    for c, lo, n_full, n in ((px, x0, NX, nx), (py, y0, NY, ny)):
        want_lo = math.ceil(c - box / 2)
        assert lo == max(want_lo, 0) and lo + n - 1 == min(want_lo + box - 1, n_full - 1)
    # sub-pixel position from the full TAN-SIP WCS
    hdr, table = _full(blob)
    xf, yf = _wcs(hdr).all_world2pix([[ra, dec]], 0)[0]
    assert (s.x + x0, s.y + y0) == pytest.approx((xf, yf), abs=1e-6)
    assert s.center_pixel == (math.floor(yf + 0.5) - y0, math.floor(xf + 0.5) - x0)
    # wavelength at the point = fits_io lookup on the full file
    lam, bw = fits_io.wavelength_from_table(table, hdr, xf, yf)
    assert (s.wavelength_um, s.bandwidth_um) == pytest.approx((float(lam), float(bw)), abs=1e-12)
    assert s.frame.wavelength_um == s.wavelength_um and s.frame.s3_key == key
    assert s.mjd == pytest.approx(hdr["MJD-AVG"]) and s.mjd_source == "MJD-AVG"  # mid-exposure, not MJD-OBS
    assert (s.obs_id, s.detector, s.release) == ("2025W33_2C_0321_1", 3, "dr1")
    assert s.bunit == "MJy / sr" and s.omega_arcsec2 == pytest.approx(hdr["OMEGA_MEDIAN"])
    assert s.meta["OBSID"] == hdr["OBSID"] and s.meta["DATE-AVG"] == hdr["DATE-AVG"]
    # core flags: OR of the 3x3 pixels around the point (clipped), NaN fraction of the stamp
    cy, cx = s.center_pixel
    core = planes["FLAGS"][sl][max(cy - 1, 0) : cy + 2, max(cx - 1, 0) : cx + 2]
    assert s.core_flags == int(np.bitwise_or.reduce(core.astype(np.uint32).ravel()))
    assert s.nan_fraction == pytest.approx(float(np.isnan(planes["IMAGE"][sl]).mean()))


def test_stamp_equals_read_patch_region(fake, monkeypatch):
    blob, _ = make_l2(seed=5)
    key = _key("2025W33_2C_0321_1")
    fake.objects[key] = blob
    ra, dec = _sky(150.3, 100.2)
    s = point.read_point_sample(_frame(key), ra, dec, 11)
    patch = s3range.read_patch(key, ra, dec, 3.0)
    px0, _, py0, _ = patch.extra["bbox"]
    ny, nx = s.shape
    sl = (slice(s.y0 - py0, s.y0 - py0 + ny), slice(s.x0 - px0, s.x0 - px0 + nx))
    for mine, theirs in (
        (s.image, patch.data),
        (s.variance, patch.variance),
        (s.zodi, patch.zodi),
        (s.flags, patch.flags),
    ):
        np.testing.assert_array_equal(mine, theirs[sl])
    assert s.image[s.center_pixel] == np.float32(50.0)  # the "star" is at the point


def test_point_off_the_detector_is_no_overlap(fake):
    key = _key("2025W33_2C_0321_1")
    fake.objects[key] = make_l2()[0]
    for px, py in ((-3.0, 50.0), (NX + 2.0, 10.0)):
        with pytest.raises(NoOverlap):
            point.read_point_sample(_frame(key), *_sky(px, py))
    with pytest.raises(NoOverlap):  # the other side of the sky
        point.read_point_sample(_frame(key), 89.0, -4.0)


def test_requests_per_frame_cold_learned_and_cached(fake, monkeypatch):
    """Cold with wrong hints: correct, more requests. Cold with learned hints: 2 + 6 requests in 2 rounds.
    Layout cached (another point on the same file): 4 requests in ONE round. Wave table read once."""
    monkeypatch.setattr(point, "MERGE_GAP", 0)  # count requests without coalescing
    keys = [_key(f"2025W33_2C_03{i:02d}_1") for i in range(3)]
    planes = {}
    for i, k in enumerate(keys):
        fake.objects[k], planes[k] = make_l2(seed=i)
    ra, dec = _sky(150.2, 99.7)

    first = point.read_point_sample(_frame(keys[0]), ra, dec)  # default hints are for 2040x2040 files
    assert first.io["layout"] == "cold" and first.io["requests"] > 8
    assert fake.tails == 1  # WCS-WAVE: one 5760-byte suffix read, then cached by (detector, calibration)

    second = point.read_point_sample(_frame(keys[1]), ra, dec)  # hints learned from the first file
    assert (second.io["requests"], second.io["rounds"]) == (8, 2)
    assert fake.tails == 1

    other = _sky(60.0, 140.0)
    again = point.read_point_sample(_frame(keys[1]), *other)
    assert (again.io["layout"], again.io["requests"], again.io["rounds"]) == ("cached", 4, 1)
    for s, k in ((first, keys[0]), (second, keys[1]), (again, keys[1])):
        sl = (slice(s.y0, s.y0 + s.shape[0]), slice(s.x0, s.x0 + s.shape[1]))
        np.testing.assert_array_equal(s.image, planes[k]["IMAGE"][sl])
        np.testing.assert_array_equal(s.zodi, planes[k]["ZODI"][sl])
        np.testing.assert_array_equal(s.flags, planes[k]["FLAGS"][sl])

    point._layout_mem.clear()  # the layout also comes back from disk
    disk = point.read_point_sample(_frame(keys[2]), ra, dec)
    point._layout_mem.clear()
    calls = fake.calls
    from_disk = point.read_point_sample(_frame(keys[2]), *other)
    assert from_disk.io["layout"] == "cached" and fake.calls - calls == 4
    np.testing.assert_array_equal(
        disk.variance, planes[keys[2]]["VARIANCE"][disk.y0 : disk.y0 + 11, disk.x0 : disk.x0 + 11]
    )


def test_wrong_hints_never_give_wrong_pixels(fake, monkeypatch):
    """A VARIANCE header much longer than the hint (and than the learned one) only costs requests."""
    monkeypatch.setattr(point, "MERGE_GAP", 0)
    k1, k2 = _key("2025W33_2C_0001_1"), _key("2025W33_2C_0002_1")
    fake.objects[k1], _ = make_l2(seed=1)
    fake.objects[k2], planes = make_l2(seed=2, var_extra_cards=150)  # +4 blocks of VARIANCE header
    ra, dec = _sky(120.0, 80.0)
    point.read_point_sample(_frame(k1), ra, dec)  # learn the normal layout
    s = point.read_point_sample(_frame(k2), ra, dec)
    sl = (slice(s.y0, s.y0 + 11), slice(s.x0, s.x0 + 11))
    for name, arr in (("IMAGE", s.image), ("VARIANCE", s.variance), ("ZODI", s.zodi), ("FLAGS", s.flags)):
        np.testing.assert_array_equal(arr, planes[name][sl])
    assert s.io["requests"] > 8 and s.io["rounds"] >= 3


def test_planes_subset_then_full(fake, monkeypatch):
    monkeypatch.setattr(point, "MERGE_GAP", 0)
    key, other = _key("2025W33_2C_0321_1"), _key("2025W33_2C_0322_1")
    fake.objects[key], planes = make_l2()
    fake.objects[other], _ = make_l2(seed=8)
    ra, dec = _sky(150.0, 100.0)
    point.read_point_sample(_frame(other), ra, dec)  # learn the hints and the wave table first
    s = point.read_point_sample(_frame(key), ra, dec, planes=("IMAGE", "FLAGS"))
    assert s.variance is None and s.zodi is None and s.flags is not None
    assert (s.io["requests"], s.io["rounds"]) == (4, 2)  # no VARIANCE/ZODI header or rows
    full = point.read_point_sample(_frame(key), ra, dec)  # cached layout without VARIANCE/ZODI: completed
    sl = (slice(full.y0, full.y0 + 11), slice(full.x0, full.x0 + 11))
    np.testing.assert_array_equal(full.variance, planes["VARIANCE"][sl])
    np.testing.assert_array_equal(full.zodi, planes["ZODI"][sl])
    assert point._cached_layout(key).zodi is not None


def test_flags_unavailable_when_tiles_are_not_rows(fake):
    key = _key("2025W33_2C_0321_1")
    fake.objects[key], planes = make_l2(flags_tile_rows=16)
    s = point.read_point_sample(_frame(key), *_sky(100.0, 100.0))
    assert s.flags is None and s.core_flags is None and "ZTILE2" in s.meta["flags_error"]  # unknown, NOT clean
    np.testing.assert_array_equal(s.image, planes["IMAGE"][s.y0 : s.y0 + 11, s.x0 : s.x0 + 11])


def test_fast_rice_decoder_matches_astropy(fake, monkeypatch):
    key = _key("2025W33_2C_0321_1")
    fake.objects[key], planes = make_l2(seed=3)
    ra, dec = _sky(200.0, 150.0)
    fast = point.read_point_sample(_frame(key), ra, dec, 21)
    layout = point._cached_layout(key)
    assert layout.flags.rice == (32, 4, NX)  # astropy's RICE_1 defaults, one tile = one row

    def broken(*a, **k):
        raise ImportError("no private codec in this astropy")

    monkeypatch.setattr(point, "_rice_rows", broken)
    slow = point.read_point_sample(_frame(key), ra, dec, 21)
    np.testing.assert_array_equal(fast.flags, slow.flags)
    np.testing.assert_array_equal(slow.flags, planes["FLAGS"][slow.y0 : slow.y0 + 21, slow.x0 : slow.x0 + 21])


def test_wave_table_shared_by_calibration_id(fake):
    """Files naming the same spectral_wcs calibration share one table (verified on 897 real files);
    a file without the HISTORY id reads its own; a different id is read separately."""
    ka, kb = _key("2025W33_2C_0001_1"), _key("2025W33_2C_0002_1")
    kc, kd = _key("2025W33_2C_0003_1"), _key("2025W33_2C_0004_1")
    fake.objects[ka], _ = make_l2(seed=1)
    fake.objects[kb], _ = make_l2(seed=2)
    fake.objects[kc], _ = make_l2(seed=3, swcs=None, wave_shift=0.5)
    fake.objects[kd], _ = make_l2(seed=4, swcs="another-calibration", wave_shift=1.0)
    ra, dec = _sky(150.0, 100.0)
    lams = {}
    for k in (ka, kb, kc, kd):
        lams[k] = point.read_point_sample(_frame(k), ra, dec).wavelength_um
        hdr, table = _full(fake.objects[k])
        xf, yf = _wcs(hdr).all_world2pix([[ra, dec]], 0)[0]
        assert lams[k] == pytest.approx(float(fits_io.wavelength_from_table(table, hdr, xf, yf)[0]), abs=1e-12)
    assert fake.tails == 3  # ka (then kb from the cache), kc, kd
    assert lams[ka] == lams[kb] and lams[kc] == pytest.approx(lams[ka] + 0.5, abs=1e-6)
    assert sorted(p.name for p in (settings.CACHE_DIR / "point" / "wave").iterdir())[0].startswith("D3_")


def test_reduced_header_gives_the_same_wcs_and_wavelength():
    """The reduced IMAGE header (celestial cards for WCS, alternates for WCS-WAVE) of a REAL DR1 header."""
    full = fits.Header.fromtextfile(FIXTURES / "full_2025W33_2C_0321_1D3_image_header.txt")
    raw = point._raw(full)
    cel, aux = point._image_texts(raw)
    wf, wr = _wcs(full), _wcs(fits.Header.fromstring(cel))
    rng = np.random.default_rng(0)
    pix = rng.uniform(-5, 2045, (500, 2))
    np.testing.assert_array_equal(wf.all_pix2world(pix, 0), wr.all_pix2world(pix, 0))
    sky = wf.all_pix2world(pix, 0)
    np.testing.assert_allclose(wf.all_world2pix(sky, 0), wr.all_world2pix(sky, 0), atol=1e-9)
    table = fits_io.WaveTable.from_hdu(
        fits.BinTableHDU.from_columns(
            [
                fits.Column(name="X", format="9J", array=np.linspace(1, 2040, 9).astype(np.int32)[None]),
                fits.Column(name="Y", format="14J", array=np.linspace(1, 2040, 14).astype(np.int32)[None]),
                fits.Column(name="VALUES", format="252E", dim="(2,9,14)", array=rng.uniform(1.6, 2.4, (1, 14, 9, 2))),
            ],
            name="WCS-WAVE",
        )
    )
    a = fits_io.wavelength_from_table(table, full, pix[:, 0], pix[:, 1])
    b = fits_io.wavelength_from_table(table, fits.Header.fromstring(aux), pix[:, 0], pix[:, 1])
    np.testing.assert_array_equal(a[0], b[0])
    assert point._wave_id(raw, 3, "k") == f"D3_{SWCS_D3}"
    meta = point._meta(fits.Header.fromstring(aux))
    assert meta["OMEGA_MEDIAN"] == pytest.approx(37.86180576958074) and meta["BUNIT"] == "MJy / sr"


def test_layout_from_cached_s3range_directory(fake, monkeypatch):
    """A file whose HDU directory a field build already cached skips the header round."""
    monkeypatch.setattr(point, "MERGE_GAP", 0)
    key = _key("2025W33_2C_0321_1")
    fake.objects[key], planes = make_l2()
    s3range.hdu_directory(key)  # what read_patch leaves behind
    fake.tails = 0
    s = point.read_point_sample(_frame(key), *_sky(150.0, 100.0))
    assert s.io["layout"] == "directory" and fake.tails == 0  # WCS-WAVE from the directory too
    sl = (slice(s.y0, s.y0 + 11), slice(s.x0, s.x0 + 11))
    np.testing.assert_array_equal(s.variance, planes["VARIANCE"][sl])
    np.testing.assert_array_equal(s.flags, planes["FLAGS"][sl])


# --- bookkeeping helpers --------------------------------------------------------------------------------------


def test_segments_merge_and_coalesce():
    seg = point._Segments()
    seg.add(10, b"abcde")  # [10, 15)
    seg.add(20, b"klm")  # [20, 23)
    seg.add(15, b"fghij")  # bridges both: [10, 23)
    assert seg.parts == [(10, b"abcdefghijklm")]
    assert seg.get(12, 16) == b"cdef" and seg.covers(10, 23) and not seg.covers(9, 11)
    assert seg.from_(21) == b"lm" and seg.from_(30) == b""
    seg.add(12, b"XY")  # overlapping data never changes known bytes' positions
    assert seg.get(10, 15) == b"abXYe"
    assert point._coalesce([(50, 60), (0, 10), (12, 20), (-5, 3)], gap=2) == [(0, 20), (50, 60)]
    assert point._coalesce([(0, 10), (12, 20)], gap=0) == [(0, 10), (12, 20)]


def test_select_frames_spreads_over_detectors_and_time():
    frames = [
        FrameRef(obs_id=f"2025W01_1A_{i:04d}_1", detector=d, mjd=60000.0 + i * 3 + d * 0.01, release="dr1")
        for i in range(40)
        for d in (1, 4)
    ] + [FrameRef(obs_id="2025W01_1A_9999_1", detector=2, mjd=60050.0, release="dr1")]
    picked = point.select_frames(frames, 9)
    assert len(picked) == 9 and [f.mjd for f in picked] == sorted(f.mjd for f in picked)
    by_det = {d: [f for f in picked if f.detector == d] for d in (1, 2, 4)}
    assert len(by_det[1]) == len(by_det[4]) == 4 and len(by_det[2]) == 1
    assert by_det[1][0].mjd < 60010 and by_det[1][-1].mjd > 60100  # whole baseline, not the first weeks
    assert point.select_frames(frames, None) == frames and point.select_frames(frames[:3], 10) == frames[:3]


# --- the series ------------------------------------------------------------------------------------------------


def _report(frames: list[FrameRef], ra: float, dec: float) -> irsa.SearchReport:
    return irsa.SearchReport(
        result=SearchResult(center=SkyCoord(ra=ra, dec=dec), radius_deg=1 / 3600, frames=frames),
        rows=[],
        service="sia",
        from_cache=False,
        elapsed_s=0.5,
        collections=("spherex_dr1", "spherex_qr3"),
    )


@pytest.fixture
def series_setup(fake, monkeypatch):
    ra, dec = _sky(150.0, 100.0)
    frames = []
    planes = {}
    for i, (det, rel) in enumerate(((3, "dr1"), (3, "qr3"), (6, "dr1"))):
        k = _key(f"2025W33_2C_00{i:02d}_1", det, rel)
        fake.objects[k], planes[k] = make_l2(seed=i, detector=det, swcs=f"cal-D{det}")
        frames.append(_frame(k, mjd=60900.0 + 10 * (3 - i)))  # reverse time order on purpose
    calls = []

    def search(*args, **kwargs):
        calls.append((args, kwargs))
        return _report(list(frames), ra, dec)

    monkeypatch.setattr(irsa, "search_frames_report", search)
    return ra, dec, frames, planes, calls


def test_point_series_end_to_end_and_cache(series_setup, fake, monkeypatch):
    ra, dec, frames, planes, calls = series_setup
    s = point.point_series(ra, dec, detectors=[3, 6], collections="spherex_dr1,spherex_qr3")
    assert calls[0][0][:4] == (ra % 360.0, dec, 0.0, [3, 6])  # point search, detector filter passed on
    assert [x.mjd for x in s.samples] == sorted(x.mjd for x in s.samples) and len(s.samples) == 3
    assert s.failures == [] and s.search["service"] == "sia" and s.search["n_selected"] == 3
    assert s.timings["requests"] == sum(x.io["requests"] for x in s.samples) and s.timings["from_cache"] is False
    for smp in s.samples:
        k = smp.frame.s3_key
        sl = (slice(smp.y0, smp.y0 + smp.shape[0]), slice(smp.x0, smp.x0 + smp.shape[1]))
        np.testing.assert_array_equal(smp.image, planes[k]["IMAGE"][sl])
        np.testing.assert_array_equal(smp.flags, planes[k]["FLAGS"][sl])

    def boom(*a, **k):
        raise AssertionError("a cached series must not touch the network")

    monkeypatch.setattr(s3range, "read_range", boom)
    monkeypatch.setattr(irsa, "search_frames_report", boom)
    again = point.point_series(ra, dec, detectors=[6, 3], collections=["spherex_qr3", "spherex_dr1"])
    assert again.timings["from_cache"] is True and len(again.samples) == 3
    for a, b in zip(s.samples, again.samples, strict=True):
        np.testing.assert_array_equal(a.image, b.image)
        np.testing.assert_array_equal(a.flags, b.flags)
        assert (a.mjd, a.wavelength_um, a.x, a.y, a.core_flags, a.frame) == (
            b.mjd,
            b.wavelength_um,
            b.x,
            b.y,
            b.core_flags,
            b.frame,
        )
    with pytest.raises(AssertionError):  # another selection is another series
        point.point_series(ra, dec, box_px=9)


def test_point_series_failures_never_abort(series_setup, fake, monkeypatch):
    ra, dec, frames, planes, _ = series_setup
    missing = _frame(_key("2025W33_2C_0099_1"), mjd=60950.0)  # not in the bucket: KeyError from the fake
    off = _key("2025W33_2C_0098_1")
    fake.objects[off], _ = make_l2(seed=9)
    off_frame = _frame(off, mjd=60960.0)
    # Point the off frame's WCS far away so (ra, dec) misses it: patch its CRVAL in the bytes.
    blob = bytearray(fake.objects[off])
    i = blob.index(b"CRVAL1  =")
    blob[i : i + 80] = f"{'CRVAL1':8s}= {100.0:20.10f}".ljust(80).encode()
    fake.objects[off] = bytes(blob)
    every = [*frames, missing, off_frame]
    monkeypatch.setattr(irsa, "search_frames_report", lambda *a, **k: _report(every, ra, dec))
    s = point.point_series(ra, dec)
    assert len(s.samples) == 3 and len(s.failures) == 2
    reasons = {f.obs_id: r for f, r in s.failures}
    assert reasons[missing.obs_id].startswith("KeyError") and reasons[off_frame.obs_id].startswith("NoOverlap")
    assert s.timings["no_overlap"] == 1
    assert not list((settings.CACHE_DIR / "point" / "series").glob("*.npz"))  # a transient failure: not cached


def test_point_series_max_frames_given_frames_and_validation(series_setup, fake):
    ra, dec, frames, _, calls = series_setup
    s = point.point_series(ra, dec, max_frames=2, use_cache=False)
    assert len(s.samples) == 2 and s.search["n_found"] == 3 and s.search["n_selected"] == 2
    given = point.point_series(ra, dec, frames=frames[:1], use_cache=False)
    assert len(given.samples) == 1 and given.search["service"] == "given" and len(calls) == 1
    for bad in ({"box_px": 0}, {"box_px": 2.5}, {"core_px": 30}, {"planes": ("PSF",)}, {"max_frames": 0}):
        with pytest.raises(ValueError):
            point.point_series(ra, dec, **bad)
    with pytest.raises(ValueError):
        point.point_series(ra, 95.0)


def test_save_load_roundtrip_with_clipped_and_missing_planes(fake, tmp_path):
    key = _key("2025W33_2C_0321_1")
    fake.objects[key], _ = make_l2()
    edge = point.read_point_sample(_frame(key), *_sky(1.0, 198.2), 11)  # clipped: 7 x 7
    mid = point.read_point_sample(_frame(key), *_sky(150.0, 100.0), 11, planes=("IMAGE",))
    assert edge.shape == (7, 7) and mid.flags is None and mid.variance is None
    series = point.PointSeries(ra=1.0, dec=2.0, box_px=11, samples=[edge, mid], failures=[(_frame(key), "X: y")])
    npz, js = series.save(tmp_path / "out")
    assert (
        npz.name == "out.npz" and js.name == "out.json" and json.loads(js.read_text())["format"] == point.SERIES_FORMAT
    )
    back = point.PointSeries.load(npz)
    for a, b in zip(series.samples, back.samples, strict=True):
        np.testing.assert_array_equal(a.image, b.image)
        for name in ("variance", "zodi", "flags"):
            x, y = getattr(a, name), getattr(b, name)
            assert (x is None) == (y is None)
            if x is not None:
                np.testing.assert_array_equal(x, y)
        assert (a.x0, a.y0, a.x, a.y, a.mjd, a.core_flags, a.meta, a.frame) == (
            b.x0,
            b.y0,
            b.x,
            b.y,
            b.mjd,
            b.core_flags,
            b.meta,
            b.frame,
        )
    assert back.failures[0][1] == "X: y" and back.summary_rows()[0]["shape"] == [7, 7]


def test_cli_point(series_setup, capsys, tmp_path):
    ra, dec, *_ = series_setup
    out = tmp_path / "barnard"
    assert cli.main(["point", "--ra", str(ra), "--dec", str(dec), "--detector", "3", "--out", str(out)]) == 0
    doc = json.loads(capsys.readouterr().out)
    assert len(doc["samples"]) == 3 and {"wavelength_um", "x", "y", "core_flags", "s3_key"} <= set(doc["samples"][0])
    assert (tmp_path / "barnard.npz").exists() and (tmp_path / "barnard.json").exists()
    assert cli.main(["point", "--ra", str(ra), "--dec", str(dec), "--detector", "3", "--summary"]) == 0
    text = capsys.readouterr().out
    assert "3 samples" in text and "D3: 2 samples" in text and "(cache)" in text
    assert cli.main(["point", "--ra", "1", "--dec", "99"]) == 2


# --- review regressions (2026-11-14) ----------------------------------------------------------------------------


def _series_files() -> list[Path]:
    d = settings.CACHE_DIR / "point" / "series"
    return sorted(d.glob("*.npz")) if d.exists() else []


def test_transient_wave_error_is_retried_once_and_never_cached(series_setup, fake, monkeypatch):
    """An S3 error on the WCS-WAVE suffix read is network trouble, not a property of the file: the frame keeps
    its stamp, the wavelength is retried ONCE per calibration at the end (not by every frame thread in turn),
    and a series still missing wavelengths is never cached."""
    ra, dec, frames, planes, _ = series_setup
    real_tail = fake.tail
    state = {"fail": 10**9, "calls": 0}

    def flaky_tail(key, nbytes, **limits):
        state["calls"] += 1
        if state["fail"] > 0:
            state["fail"] -= 1
            raise OSError("S3 suffix read failed after 4 attempts (simulated 503s)")
        return real_tail(key, nbytes)

    monkeypatch.setattr(s3range, "read_tail", flaky_tail)
    s = point.point_series(ra, dec)  # S3 down for the whole call
    assert len(s.samples) == 3 and s.failures == []  # the stamps are still there (time video)
    assert all(x.wavelength_um is None and x.meta["wave_error"].startswith("OSError") for x in s.samples)
    assert all(x.meta.get("wave_error_transient") for x in s.samples)
    assert s.timings["wave_errors"] == 3
    assert state["calls"] == 4  # 2 calibrations (D3, D6) x (main pass + one retry): no serialized retries
    assert _series_files() == []  # NOT cached

    state.update(fail=2, calls=0)  # a short burst: the first try of each calibration fails, the retry works
    point._layout_mem.clear()
    s = point.point_series(ra, dec)
    assert state["calls"] == 4 and s.timings["wave_errors"] == 0 and s.timings["wave_retried"] == 3
    for x in s.samples:
        hdr, table = _full(fake.objects[x.frame.s3_key])
        lam, bw = fits_io.wavelength_from_table(table, hdr, x.x_detector, x.y_detector)
        assert (x.wavelength_um, x.bandwidth_um) == pytest.approx((float(lam), float(bw)), abs=1e-12)
        assert x.frame.wavelength_um == x.wavelength_um and "wave_error" not in x.meta
    assert len(_series_files()) == 1  # complete: cached

    again = point.point_series(ra, dec)
    assert again.timings["from_cache"] is True and all(x.wavelength_um is not None for x in again.samples)


def test_s3_outage_on_wcs_wave_never_serves_a_series_without_wavelengths(series_setup, fake, monkeypatch):
    """Review M1, black-box (only the API of the first version): every WCS-WAVE suffix read fails during one
    call; once S3 is healthy again the next call must NOT come from a cache holding samples without wavelength."""
    ra, dec, *_ = series_setup
    healthy = fake.tail

    def down(key, nbytes, **limits):
        raise OSError("S3 suffix read failed after 4 attempts (simulated 503s)")

    monkeypatch.setattr(s3range, "read_tail", down)
    first = point.point_series(ra, dec)
    assert len(first.samples) == 3 and all(x.wavelength_um is None for x in first.samples)
    assert first.timings.get("wave_errors") == 3  # visible in the result, not only in each sample's meta
    monkeypatch.setattr(s3range, "read_tail", healthy)
    second = point.point_series(ra, dec)
    assert second.timings["from_cache"] is False
    assert all(x.wavelength_um is not None for x in second.samples)


def test_cli_point_reports_missing_wavelengths_and_takes_a_deadline(series_setup, fake, monkeypatch, capsys):
    ra, dec, *_ = series_setup

    def down(key, nbytes, **limits):
        raise OSError("simulated 503s")

    monkeypatch.setattr(s3range, "read_tail", down)
    assert cli.main(["point", "--ra", str(ra), "--dec", str(dec), "--deadline", "60"]) == 0
    out = capsys.readouterr()
    doc = json.loads(out.out)
    assert doc["timings"]["wave_errors"] == 3 and "3 samples have no wavelength" in out.err
    assert all(r["wavelength_um"] is None and r["wave_error"].startswith("OSError") for r in doc["samples"])
    assert cli.main(["point", "--ra", str(ra), "--dec", str(dec), "--deadline", "0"]) == 2


def test_format_wave_errors_are_not_transient(fake):
    """A file whose tail is not a WCS-WAVE HDU is a property of the file (not retried, cacheable)."""
    key = _key("2025W33_2C_0321_1")
    blob, _ = make_l2()
    fake.objects[key] = blob[: -2 * 2880] + b"\0" * (2 * 2880)
    s = point.read_point_sample(_frame(key), *_sky(150.0, 100.0))
    assert s.wavelength_um is None and s.meta["wave_error"].startswith("ValueError")
    assert "wave_error_transient" not in s.meta


@pytest.mark.filterwarnings("ignore::astropy.io.fits.verify.VerifyWarning")
def test_corrupt_wave_hdu_is_a_wave_error_not_a_failed_frame(fake):
    """Review 2026-11-15: a WCS-WAVE whose XTENSION card astropy cannot parse (a _CorruptedHDU) raised
    AttributeError out of read_point_sample (and to_spherex_image); it is a deterministic wave_error now."""
    key = _key("2025W33_2C_0321_1")
    blob, _ = make_l2()
    tail = blob[-2 * 2880 :]
    old = b"XTENSION= 'BINTABLE'           / binary table extension"
    assert tail.startswith(old) and b"WCS-WAVE" in tail[:2880]
    fake.objects[key] = blob[: -len(tail)] + tail.replace(
        old, b"XTENSION= 5  -Z'252'.58742YB.1 / binary table extension"
    )
    s3range.wave_table_from_bytes.cache_clear()
    s = point.read_point_sample(_frame(key), *_sky(150.0, 100.0))
    assert s.wavelength_um is None and s.meta["wave_error"].startswith("ValueError")
    assert "wave_error_transient" not in s.meta
    img = point.to_spherex_image(s)
    assert img.wave is None and img.extra["wave_error"].startswith("ValueError")


def test_empty_and_all_no_overlap_series_are_not_cached(series_setup, fake, monkeypatch):
    """irsa never caches an empty answer (suspicious for an all-sky survey): neither does point_series."""
    ra, dec, frames, _, _ = series_setup
    monkeypatch.setattr(irsa, "search_frames_report", lambda *a, **k: _report([], ra, dec))
    assert point.point_series(ra, dec).samples == [] and _series_files() == []
    monkeypatch.setattr(irsa, "search_frames_report", lambda *a, **k: _report(list(frames), ra, dec))
    s = point.point_series(ra, dec)
    assert s.timings["from_cache"] is False and len(s.samples) == 3
    far = point.point_series(*_sky(-200.0, 100.0))  # every frame NoOverlap
    assert far.samples == [] and far.timings["no_overlap"] == 3
    assert len(_series_files()) == 1  # only the real series


def test_corrupt_or_mismatched_series_cache_is_recomputed(series_setup, fake):
    ra, dec, *_ = series_setup
    point.point_series(ra, dec)
    (npz,) = _series_files()
    js = npz.with_suffix(".json")
    good_npz, good_json = npz.read_bytes(), js.read_text()

    npz.write_bytes(good_npz[:100])  # truncated npz (BadZipFile)
    s = point.point_series(ra, dec)
    assert s.timings["from_cache"] is False and len(s.samples) == 3

    doc = json.loads(good_json)  # a json from another writer: one more sample than its npz
    doc["samples"].append(doc["samples"][-1])
    npz.write_bytes(good_npz)
    js.write_text(json.dumps(doc))
    s = point.point_series(ra, dec)
    assert s.timings["from_cache"] is False and len(s.samples) == 3

    other = point.point_series(ra, dec, max_frames=2, use_cache=False)  # same sample count, other content
    other.save(npz.with_name("other.npz"))
    js.write_text(good_json)
    npz.write_bytes(npz.with_name("other.npz").read_bytes())
    with pytest.raises(ValueError, match="not the npz"):  # the json names the npz it was written with (sha256)
        point.PointSeries.load(npz)
    s = point.point_series(ra, dec)
    assert s.timings["from_cache"] is False and len(s.samples) == 3


def test_rewritten_object_invalidates_its_cached_layout(fake, monkeypatch):
    """S3 objects are rewritten under the same key (RECON §2.4): a cached layout is checked against the
    object's ETag/size that every Range answer carries, and re-read when the object changed."""
    key = _key("2025W33_2C_0321_1")
    fake.objects[key], _ = make_l2(seed=1)
    ra, dec = _sky(150.0, 100.0)
    point.read_point_sample(_frame(key), ra, dec)  # layout cached (memory + disk)
    fake.objects[key], planes = make_l2(seed=1, var_extra_cards=150)  # VARIANCE header 4 blocks longer
    for clear_memory in (False, True):
        if clear_memory:
            fake.objects[key], planes = make_l2(seed=2)  # rewritten again; the old layout only on disk
            point._layout_mem.clear()
        s = point.read_point_sample(_frame(key), ra, dec)
        assert s.io["layout"] == "cold" and s.io["stale_layout"] is True
        sl = (slice(s.y0, s.y0 + 11), slice(s.x0, s.x0 + 11))
        for name, arr in (("IMAGE", s.image), ("VARIANCE", s.variance), ("ZODI", s.zodi), ("FLAGS", s.flags)):
            np.testing.assert_array_equal(arr, planes[name][sl])
    again = point.read_point_sample(_frame(key), *_sky(60.0, 140.0))
    assert again.io["layout"] == "cached" and "stale_layout" not in again.io
    np.testing.assert_array_equal(
        again.variance, planes["VARIANCE"][again.y0 : again.y0 + 11, again.x0 : again.x0 + 11]
    )


def test_rewritten_object_invalidates_a_cached_s3range_directory(fake):
    key = _key("2025W33_2C_0321_1")
    fake.objects[key], _ = make_l2(seed=1)
    s3range.hdu_directory(key)  # what read_patch leaves behind
    fake.objects[key], planes = make_l2(seed=1, var_extra_cards=150)
    s = point.read_point_sample(_frame(key), *_sky(150.0, 100.0))
    assert s.io["layout"] == "cold" and s.io["stale_layout"] is True
    sl = (slice(s.y0, s.y0 + 11), slice(s.x0, s.x0 + 11))
    np.testing.assert_array_equal(s.variance, planes["VARIANCE"][sl])
    np.testing.assert_array_equal(s.zodi, planes["ZODI"][sl])
    assert s3range.cached_directory(key) is None  # forgotten: read_patch walks the new object next time


@pytest.mark.parametrize("core_px", [1, 2, 3, 4, 5])
def test_core_is_exactly_core_px_square(fake, core_px):
    """``core_px`` x ``core_px`` pixels picked with the stamp's own rule (``ceil(c - n/2)``), even sizes too."""
    key = _key("2025W33_2C_0321_1")
    fake.objects[key], planes = make_l2()
    ra, dec = _sky(150.3, 99.8)
    s = point.read_point_sample(_frame(key), ra, dec, 11, core_px=core_px)
    hdr, _ = _full(fake.objects[key])
    xf, yf = _wcs(hdr).all_world2pix([[ra, dec]], 0)[0]
    x0, y0 = math.ceil(xf - core_px / 2), math.ceil(yf - core_px / 2)
    core = planes["FLAGS"][y0 : y0 + core_px, x0 : x0 + core_px]
    assert core.shape == (core_px, core_px)
    assert s.core_flags == int(np.bitwise_or.reduce(core.astype(np.uint32).ravel()))


def test_detector_list_must_not_be_empty_and_duplicate_frames_are_read_once(series_setup, fake):
    ra, dec, frames, _, _ = series_setup
    with pytest.raises(ValueError, match="detectors"):
        point.point_series(ra, dec, detectors=[])
    s = point.point_series(ra, dec, frames=[frames[0], frames[0], frames[1]], use_cache=False)
    assert len(s.samples) == 2 and s.search["n_found"] == 2 and s.search["n_duplicates"] == 1


def test_series_counts_every_request_and_caches_no_overlap_layouts(series_setup, fake, monkeypatch):
    """Requests of failed frames and the WCS-WAVE suffix read are counted; a NoOverlap frame's layout is cached,
    so asking again costs it no request."""
    ra, dec, frames, _, _ = series_setup
    off = _key("2025W33_2C_0098_1")
    blob = bytearray(make_l2(seed=9)[0])
    i = blob.index(b"CRVAL1  =")
    blob[i : i + 80] = f"{'CRVAL1':8s}= {100.0:20.10f}".ljust(80).encode()
    fake.objects[off] = bytes(blob)
    every = [*frames, _frame(off, mjd=60960.0)]
    monkeypatch.setattr(irsa, "search_frames_report", lambda *a, **k: _report(every, ra, dec))
    before = fake.calls + fake.tails
    s = point.point_series(ra, dec, use_cache=False)
    assert s.timings["no_overlap"] == 1
    assert s.timings["requests"] == fake.calls + fake.tails - before  # the NoOverlap frame's reads included
    assert s.timings["requests"] > sum(x.io["requests"] for x in s.samples)
    before = fake.calls + fake.tails
    s = point.point_series(ra, dec, use_cache=False)
    assert s.timings["no_overlap"] == 1 and s.timings["layouts"] == {"cached": 3}
    assert s.timings["requests"] == fake.calls + fake.tails - before == sum(x.io["requests"] for x in s.samples)


def test_wave_suffix_read_is_a_round_of_its_own(fake, monkeypatch):
    monkeypatch.setattr(point, "MERGE_GAP", 0)
    k1, k2 = _key("2025W33_2C_0001_1"), _key("2025W33_2C_0002_1")
    fake.objects[k1], _ = make_l2(seed=1)
    fake.objects[k2], _ = make_l2(seed=2, swcs="another-calibration")
    ra, dec = _sky(150.0, 100.0)
    point.read_point_sample(_frame(k1), ra, dec)  # learn the hints
    s = point.read_point_sample(_frame(k2), ra, dec)  # learned hints, but a new calibration: 8 + 1 requests
    assert (s.io["requests"], s.io["rounds"]) == (9, 3) and fake.tails == 2


def test_max_workers_caps_concurrent_requests(fake, monkeypatch):
    ra, dec = _sky(150.0, 100.0)
    frames = []
    for i in range(8):
        k = _key(f"2025W33_2C_00{i:02d}_1")
        fake.objects[k], _ = make_l2(seed=i)
        frames.append(_frame(k, mjd=60900.0 + i))
    lock = threading.Lock()
    state = {"now": 0, "peak": 0}

    def tracked(fn):
        def wrapper(*a, **limits):
            with lock:
                state["now"] += 1
                state["peak"] = max(state["peak"], state["now"])
            try:
                time.sleep(0.005)
                return fn(*a)
            finally:
                with lock:
                    state["now"] -= 1

        return wrapper

    monkeypatch.setattr(s3range, "read_range", tracked(fake))
    monkeypatch.setattr(s3range, "read_range_meta", tracked(fake.meta), raising=False)
    monkeypatch.setattr(s3range, "read_tail", tracked(fake.tail))
    s = point.point_series(ra, dec, frames=frames, max_workers=2, use_cache=False)
    assert len(s.samples) == 8 and state["peak"] <= 2


def test_deadline_turns_unfinished_frames_into_failures(series_setup, fake, monkeypatch):
    ra, dec, frames, _, _ = series_setup
    release = threading.Event()
    slow = frames[0].s3_key

    def stalled(key, start, stop, **limits):
        if key == slow:
            release.wait(20)
        return fake.meta(key, start, stop)

    monkeypatch.setattr(s3range, "read_range_meta", stalled, raising=False)
    t0 = time.perf_counter()
    try:
        s = point.point_series(ra, dec, deadline_s=0.5)
        elapsed = time.perf_counter() - t0
    finally:
        release.set()
    assert elapsed < 5
    assert len(s.samples) == 2 and [f.s3_key for f, _ in s.failures] == [slow]
    assert s.failures[0][1].startswith("TimeoutError") and s.timings["timed_out"] == 1
    assert _series_files() == []  # incomplete: not cached


def _same_spherex_image(img: fits_io.SpherexImage, s: point.PointSample, full: fits.Header, ra: float, dec: float):
    ny, nx = s.shape
    assert (img.header["NAXIS1"], img.header["NAXIS2"]) == (nx, ny) and img.data.shape == (ny, nx)
    assert (img.header["PATCH_X0"], img.header["PATCH_Y0"]) == (s.x0, s.y0)
    shifted = [k for k in full if s3range._CRPIX.match(k)]
    assert {"CRPIX1", "CRPIX2", "CRPIX1A", "CRPIX2A", "CRPIX1W", "CRPIX2W"} <= set(shifted)
    for k in shifted:  # sub-image convention: EVERY CRPIXn<key> moved by the stamp origin
        assert img.header[k] == pytest.approx(full[k] - (s.x0 if k[5] == "1" else s.y0), abs=1e-12)
    x, y = img.wcs.all_world2pix([[ra, dec]], 0)[0]
    assert (x, y) == pytest.approx((s.x, s.y), abs=1e-6)
    assert img.wavelength_at(ra, dec) == pytest.approx((s.wavelength_um, s.bandwidth_um), abs=1e-12)
    assert img.header["OMEGA_MEDIAN"] == full["OMEGA_MEDIAN"] and img.header["BUNIT"] == full["BUNIT"]
    assert (img.obs_id, img.detector, img.mjd) == (s.obs_id, s.detector, s.mjd)
    assert img.date_obs == full["DATE-AVG"]  # the same instant as mjd (mid-exposure)
    np.testing.assert_array_equal(img.data, s.image)
    np.testing.assert_array_equal(img.flags, s.flags)
    np.testing.assert_array_equal(img.data_minus_zodi, s.image - s.zodi)


def test_to_spherex_image_follows_the_subimage_convention(fake, tmp_path):
    """Review S8: a stamp usable where a cutout/patch SpherexImage is (WS2 photometry), equal to the cutout
    path (read_patch -> write_patch_fits -> read_spherex) on the same pixels."""
    key = _key("2025W33_2C_0321_1")
    blob, planes = make_l2(seed=3)
    fake.objects[key] = blob
    full, _ = _full(blob)
    ra, dec = _sky(150.3, 99.8)
    s = point.read_point_sample(_frame(key), ra, dec, 21)
    img = point.to_spherex_image(s)
    _same_spherex_image(img, s, full, ra, dec)
    sl = (slice(s.y0, s.y0 + 21), slice(s.x0, s.x0 + 21))
    np.testing.assert_array_equal(img.variance, planes["VARIANCE"][sl])
    assert img.extra["bbox"] == (s.x0, s.x0 + 20, s.y0, s.y0 + 20) and img.extra["flags"] == "ok"

    ref = fits_io.read_spherex(s3range.write_patch_fits(s3range.read_patch(key, ra, dec, 3.0), tmp_path / "p.fits"))
    dx, dy = s.x0 - ref.header["PATCH_X0"], s.y0 - ref.header["PATCH_Y0"]
    np.testing.assert_array_equal(img.data, ref.data[dy : dy + 21, dx : dx + 21])
    rx, ry = ref.wcs.all_world2pix([[ra, dec]], 0)[0]
    assert (rx - dx, ry - dy) == pytest.approx(tuple(img.wcs.all_world2pix([[ra, dec]], 0)[0]), abs=1e-9)
    assert img.wavelength_at(ra, dec) == pytest.approx(ref.wavelength_at(ra, dec), abs=1e-12)
    assert (img.mjd, img.date_obs) == (ref.mjd, ref.date_obs)

    # A sample loaded from disk has no cards: they come from the cached layout (no request) ...
    npz, _ = point.PointSeries(ra=ra, dec=dec, box_px=21, samples=[s], failures=[]).save(tmp_path / "s")
    back = point.PointSeries.load(npz).samples[0]
    point._layout_mem.clear()
    point._wave_mem.clear()
    before = fake.calls + fake.tails
    _same_spherex_image(point.to_spherex_image(back), s, full, ra, dec)
    assert fake.calls + fake.tails == before
    # ... or from S3 again when nothing is cached (round 1 of a cold read + the WCS-WAVE suffix read).
    import shutil

    shutil.rmtree(settings.CACHE_DIR)
    for cache in (point._layout_mem, point._wave_mem, s3range._mem):  # read_patch cached a directory too
        cache.clear()
    calls, tails = fake.calls, fake.tails
    _same_spherex_image(point.to_spherex_image(back), s, full, ra, dec)
    assert fake.calls - calls == 2 and fake.tails - tails == 1


def test_ws2_photometry_on_point_stamps_matches_the_cutout_from_box_15(fake, tmp_path):
    """Review S8: WS2's forced photometry (imaging.photometry.measure, #31) runs on to_spherex_image stamps and
    gives the cutout's numbers once the stamp holds its 4-7 px sky annulus (box_px >= 15); 11 px cuts the ring."""
    from errante.imaging import photometry

    key = _key("2025W33_2C_0321_1")
    fake.objects[key], _ = make_l2(seed=4)
    ra, dec = _sky(20.3, 99.6)  # columns < 40 carry no flag bits: every annulus pixel is usable
    ref = fits_io.read_spherex(s3range.write_patch_fits(s3range.read_patch(key, ra, dec, 3.0), tmp_path / "p.fits"))
    want = photometry.measure(ref, ra, dec, correction=1.0)
    assert want.flux_mjy is not None and want.sky_mjy_sr is not None and want.wavelength_um is not None
    for box in (15, 21):
        s = point.read_point_sample(_frame(key), ra, dec, box)
        got = photometry.measure(point.to_spherex_image(s), ra, dec, correction=1.0)
        assert (got.flux_mjy, got.flux_err_mjy, got.sky_mjy_sr) == pytest.approx(
            (want.flux_mjy, want.flux_err_mjy, want.sky_mjy_sr), rel=1e-9
        )
        assert (got.wavelength_um, got.bandwidth_um) == pytest.approx(
            (want.wavelength_um, want.bandwidth_um), abs=1e-12
        )
        assert got.flags == want.flags and (got.mjd, got.obs_id, got.detector) == (want.mjd, want.obs_id, want.detector)
        assert (got.x + s.x0, got.y + s.y0) == pytest.approx(
            (want.x + ref.header["PATCH_X0"], want.y + ref.header["PATCH_Y0"]), abs=1e-6
        )
    small = photometry.measure(point.to_spherex_image(point.read_point_sample(_frame(key), ra, dec, 11)), ra, dec)
    assert small.sky_mjy_sr != pytest.approx(want.sky_mjy_sr, rel=1e-6)  # truncated sky ring: another sky


def test_to_spherex_image_without_flags_or_wave_table(fake):
    key = _key("2025W33_2C_0321_1")
    blob, _ = make_l2()
    fake.objects[key] = blob[: -2 * 2880] + b"\0" * (2 * 2880)  # no WCS-WAVE HDU at the end
    s = point.read_point_sample(_frame(key), *_sky(150.0, 100.0), 15, planes=("IMAGE",))
    img = point.to_spherex_image(s)
    assert img.flags is None and img.variance is None and img.extra["flags"] == "unavailable"
    assert img.header["PATCHFLG"] == "unavailable"  # unknown, NOT clean
    assert img.wave is None and img.extra["wave_error"].startswith("ValueError")
    assert img.wavelength_at(*_sky(150.0, 100.0)) is None


# --- follow-ups of the #45 review (2026-11-14): deadline, cut spread, in-flight reads, pool, CLI ----------------


def test_deadline_covers_the_archive_search(fake, monkeypatch):
    """``deadline_s`` is for the WHOLE call: a stalled IRSA gets what is left of it, not SEARCH_DEADLINE_S (60 s)."""
    ra, dec = _sky(150.0, 100.0)
    monkeypatch.setattr(irsa, "find_snapshot", lambda *a, **k: None)  # no committed fallback: IRSA must answer
    seen: list[float] = []
    stop = threading.Event()

    def stalled_http(method, url, *, params=None, data=None, timeout):
        seen.append(timeout)
        stop.wait(min(timeout, 3.0))  # a stalled IRSA (bounded so that the old code fails in ~15 s, not minutes)
        raise requests.Timeout(f"{url} stalled")

    monkeypatch.setattr(irsa, "_http", stalled_http)
    t0 = time.perf_counter()
    try:
        with pytest.raises(irsa.SearchError) as err:
            point.point_series(ra, dec, deadline_s=3.0, use_cache=False)
    finally:
        stop.set()
    elapsed = time.perf_counter() - t0
    assert elapsed < 3.0 + 1.5
    assert seen and max(seen) <= 3.0  # no attempt was given more time than the call had
    assert isinstance(err.value.__cause__, requests.Timeout)  # the backend maps this cause to HTTP 504
    assert fake.calls == 0


def test_a_short_deadline_gives_sia_the_whole_search_budget(fake, monkeypatch):
    """Review 2026-11-15: point_series(deadline_s=5) gave SIA 2.5 s (half, the other half kept for TAP, which needs
    8-19 s), so a cold search that SIA answers in 3 s failed with SearchError (504) where main returned a series."""
    ra, dec = _sky(150.0, 100.0)
    key = _key("2025W33_2C_0001_1")
    fake.objects[key], _ = make_l2()
    rows = [irsa.ArchiveRow(_frame(key), "spherex_dr1", "l2b-v27-2026-228")]
    monkeypatch.setattr(irsa, "find_snapshot", lambda *a, **k: None)
    given: list[float] = []

    def sia(ra_, dec_, radius, mjd_min, mjd_max, cols, deadline=None):
        given.append(deadline - time.monotonic())
        return list(rows), False

    monkeypatch.setattr(irsa, "_search_sia", sia)
    s = point.point_series(ra, dec, deadline_s=5.0, use_cache=False)
    assert len(s.samples) == 1 and s.search["service"] == "sia"
    assert given and 4.0 < given[0] <= 5.0  # was 2.5 s: SIA (1-4 s, up to 9.3 s seen) now has the whole budget


def test_no_read_starts_once_the_search_used_up_the_deadline(series_setup, fake, monkeypatch):
    ra, dec, frames, _, _ = series_setup
    budgets = []

    def slow_search(*a, **k):
        budgets.append(k.get("deadline_s"))
        time.sleep(0.4)
        return _report(list(frames), ra, dec)

    monkeypatch.setattr(irsa, "search_frames_report", slow_search)
    s = point.point_series(ra, dec, deadline_s=0.3, use_cache=False)
    assert budgets and budgets[0] is not None and 0 < budgets[0] <= 0.3  # the search got the remaining budget
    assert s.samples == [] and fake.calls == 0 and fake.tails == 0  # nothing was sent to S3 after the deadline
    assert s.timings["timed_out"] == 3 and len(s.failures) == 3
    assert all(r.startswith("TimeoutError") and "search" in r for _, r in s.failures)  # says where the time went


def _season_frames(fake, n_per_season: int = 6) -> tuple[list[FrameRef], dict[str, int]]:
    """Four seasons (two DR1, two QR3), one visit every 2 days, in time order."""
    blob, _ = make_l2(seed=1)
    frames, season_of = [], {}
    for s_i, (rel, start) in enumerate((("dr1", 60800.0), ("dr1", 60990.0), ("qr3", 61180.0), ("qr3", 61370.0))):
        for i in range(n_per_season):
            k = _key(f"2025W33_2C_{s_i}{i:03d}_1", 3, rel)
            fake.objects[k] = blob
            frames.append(_frame(k, mjd=start + 2.0 * i))
            season_of[k] = s_i
    return frames, season_of


def test_read_order_spreads_every_prefix_over_seasons_releases_and_visits(fake):
    frames, season_of = _season_frames(fake, n_per_season=9)
    order = point._read_order(frames)
    assert sorted(f.s3_key for f in order) == sorted(f.s3_key for f in frames)  # a permutation
    assert [season_of[f.s3_key] for f in order[:4]] == [0, 1, 2, 3]  # every season (and release) first
    first = [f for f in order if season_of[f.s3_key] == 0]
    assert [f.mjd for f in first[:3]] == [60800.0, 60816.0, 60808.0]  # first, last, middle visit: coarse to fine
    groups = point._season_groups(frames)
    assert [(g[0].release, len(g)) for g in groups] == [("dr1", 9), ("dr1", 9), ("qr3", 9), ("qr3", 9)]


def test_deadline_cut_keeps_every_season_and_both_releases(fake, monkeypatch):
    """When the deadline cuts the series, the frames kept are spread over the whole baseline (every season, both
    releases), not the earliest weeks: frames are SUBMITTED interleaved by season and visit. Here only the first 4
    frames whose reads start can finish (4 frame threads, FIFO); every later one stalls past the deadline."""
    ra, dec = _sky(150.0, 100.0)
    frames, season_of = _season_frames(fake)
    started: list[str] = []
    lock = threading.Lock()
    release = threading.Event()
    real = point.read_point_sample

    def gated(frame, *a, **k):
        with lock:
            started.append(frame.s3_key)
            late = len(started) > 4
        if late:  # stalls without holding any S3 request slot
            release.wait(20)
            raise TimeoutError("released after the test")
        return real(frame, *a, **k)

    monkeypatch.setattr(point, "read_point_sample", gated)
    try:
        s = point.point_series(ra, dec, frames=frames, max_workers=4, deadline_s=1.5, use_cache=False)
    finally:
        release.set()
    assert len(s.samples) == 4 and sorted(season_of[x.frame.s3_key] for x in s.samples) == [0, 1, 2, 3]
    assert {x.release for x in s.samples} == {"dr1", "qr3"}
    assert [x.mjd for x in s.samples] == sorted(x.mjd for x in s.samples)  # the output is still in time order
    assert s.timings["timed_out"] == 20 and all(r.startswith("TimeoutError") for _, r in s.failures)
    cut = s.timings["seasons"]  # what the deadline cut, per (release, season)
    assert [(c["release"], c["frames"], c["samples"], c["timed_out"]) for c in cut] == [
        ("dr1", 6, 1, 5),
        ("dr1", 6, 1, 5),
        ("qr3", 6, 1, 5),
        ("qr3", 6, 1, 5),
    ]
    assert cut[0]["mjd_min"] == 60800.0 and cut[-1]["mjd_max"] == 61380.0


class _RangeHandler(BaseHTTPRequestHandler):
    """A tiny S3: GET with ``Range: bytes=a-b`` or ``bytes=-n`` answered 206 with Content-Range and ETag."""

    protocol_version = "HTTP/1.1"  # keep-alive, like S3: connections are pooled by the client

    def setup(self):
        super().setup()
        self.server.count("open", +1)

    def finish(self):
        try:
            super().finish()
        finally:
            self.server.count("open", -1)

    def do_GET(self):
        srv = self.server
        key = self.path.lstrip("/")
        if key in srv.stall:
            srv.release.wait(30)
        elif srv.delay:
            time.sleep(srv.delay)
        obj = srv.objects.get(key)
        m = re.fullmatch(r"bytes=(\d*)-(\d*)", self.headers.get("Range", ""))
        if obj is None or m is None:
            self.send_response(404 if obj is None else 400)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        size = len(obj)
        if m[1] == "":
            a, b = max(0, size - int(m[2])), size - 1
        else:
            a, b = int(m[1]), min(int(m[2]) if m[2] else size - 1, size - 1)
        if a >= size:
            self.send_response(416)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        part = obj[a : b + 1]
        self.send_response(206)
        self.send_header("Content-Length", str(len(part)))
        self.send_header("Content-Range", f"bytes {a}-{b}/{size}")
        self.send_header("ETag", '"' + hashlib.md5(obj).hexdigest() + '"')
        self.end_headers()
        self.wfile.write(part)

    def log_message(self, *args):
        pass


class _RangeServer(ThreadingHTTPServer):
    daemon_threads = True
    request_queue_size = 512  # many simultaneous connects (the default backlog of 5 refuses them on Windows)

    def __init__(self):
        super().__init__(("127.0.0.1", 0), _RangeHandler)
        self.objects: dict[str, bytes] = {}
        self.stall: set[str] = set()
        self.delay = 0.0
        self.release = threading.Event()
        self.now = {"open": 0}  # TCP connections open at the server
        self.peak = {"open": 0}
        self._lock = threading.Lock()

    def count(self, what: str, d: int) -> None:
        with self._lock:
            self.now[what] += d
            self.peak[what] = max(self.peak[what], self.now[what])

    def handle_error(self, request, client_address):
        pass  # a client that gave up (deadline) closed its socket under a stalled answer: expected here


@pytest.fixture
def s3_server(monkeypatch):
    """The real s3range readers (fresh pooled session) against a local Range server."""
    for var in ("HTTP_PROXY", "http_proxy", "ALL_PROXY", "all_proxy"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("NO_PROXY", "localhost,127.0.0.1")
    monkeypatch.setenv("no_proxy", "localhost,127.0.0.1")
    server = _RangeServer()
    threading.Thread(target=server.serve_forever, daemon=True).start()
    monkeypatch.setattr(settings, "S3_HTTPS", f"http://127.0.0.1:{server.server_address[1]}")
    monkeypatch.setattr(s3range, "_SESSION", None)
    monkeypatch.setattr(s3range, "_REQUEST_SLOTS", None, raising=False)
    try:
        yield server
    finally:
        server.release.set()
        if s3range._SESSION is not None:
            s3range._SESSION.close()
        server.shutdown()
        server.server_close()


def _point_threads() -> set[threading.Thread]:
    return {t for t in threading.enumerate() if t.name.startswith(("point-io", "point-frame"))}


def test_deadline_stops_in_flight_s3_reads(s3_server):
    """After the deadline the call returns AND its reader threads stop within a few seconds: a stalled S3 request
    gets a per-attempt timeout bounded by the deadline and no retry, instead of HTTP_TIMEOUT_S (120 s) x 4."""
    ra, dec = _sky(150.0, 100.0)
    frames = []
    for i in range(3):
        k = _key(f"2025W33_2C_00{i:02d}_1")
        s3_server.objects[k], _ = make_l2(seed=i)
        frames.append(_frame(k, mjd=60900.0 + i))
    s3_server.stall.add(frames[1].s3_key)
    before = _point_threads()
    t0 = time.perf_counter()
    s = point.point_series(ra, dec, frames=frames, deadline_s=1.5, use_cache=False)
    elapsed = time.perf_counter() - t0
    assert elapsed < 1.5 + 1.0
    assert len(s.samples) == 2 and [f.s3_key for f, _ in s.failures] == [frames[1].s3_key]
    assert s.failures[0][1].startswith("TimeoutError") and s.timings["timed_out"] == 1
    t1 = time.perf_counter()
    while (left := [t for t in _point_threads() - before if t.is_alive()]) and time.perf_counter() - t1 < 3.0:
        time.sleep(0.05)
    assert not left, f"{len(left)} reader threads still running {time.perf_counter() - t1:.1f} s after the call"


def test_two_concurrent_series_stay_within_the_s3_connection_pool(s3_server, caplog):
    """Two point series at once in one process (WS4 runs up to ERRANTE_API_MAX_CONCURRENT=2 jobs) never ask for
    more connections than s3range's pool holds: no urllib3 'Connection pool is full, discarding connection'."""
    blob, _ = make_l2(seed=1)
    ra, dec = _sky(150.0, 100.0)
    per_series = []
    for j in range(2):
        frames = []
        for i in range(40):
            k = _key(f"2025W33_2C_{j}{i:03d}_1")
            s3_server.objects[k] = blob
            frames.append(_frame(k, mjd=60900.0 + i))
        per_series.append(frames)
    s3_server.delay = 0.03  # every answer takes a while: both series' requests overlap
    caplog.set_level(logging.WARNING, logger="urllib3")
    with ThreadPoolExecutor(2) as pool:
        results = list(
            pool.map(lambda fr: point.point_series(ra, dec, frames=fr, max_workers=48, use_cache=False), per_series)
        )
    assert [len(r.samples) for r in results] == [40, 40] and not any(r.failures for r in results)
    assert [r.getMessage() for r in caplog.records if "pool is full" in r.getMessage()] == []
    adapter = s3range._session().get_adapter(settings.S3_HTTPS + "/x")
    limit = adapter.poolmanager.connection_pool_kw["maxsize"]
    # Never more connections than the pool keeps, but more than one series alone (capped at 48 requests) needs:
    # the two series did overlap. (Before the fix: up to 96 connections, the extra ones discarded with a warning.)
    assert 48 < s3_server.peak["open"] <= limit


def test_cli_point_summary_says_what_was_read_and_exits_3_without_samples(series_setup, fake, monkeypatch, capsys):
    ra, dec, frames, _, _ = series_setup
    release = threading.Event()
    slow = frames[0].s3_key

    def stalled(key, start, stop, **limits):
        if key == slow:
            release.wait(20)
        return fake.meta(key, start, stop)

    monkeypatch.setattr(s3range, "read_range_meta", stalled)
    try:
        code = cli.main(["point", "--ra", str(ra), "--dec", str(dec), "--deadline", "1", "--summary", "--no-cache"])
    finally:
        release.set()
    out = capsys.readouterr()
    assert code == 0  # 2 samples: a partial series is still a result
    assert "3 frames read from S3" not in out.out and "read from S3: 2 of 3 frames" in out.out
    assert "1 timed out" in out.out
    far = _sky(-200.0, 100.0)  # every frame NoOverlap: no sample at all
    assert cli.main(["point", "--ra", str(far[0]), "--dec", str(far[1]), "--no-cache"]) == cli.POINT_NO_SAMPLES == 3
    out = capsys.readouterr()
    doc = json.loads(out.out)  # the JSON is still printed (why: failures, timings)
    assert doc["samples"] == [] and doc["timings"]["no_overlap"] == 3 and "no sample" in out.err


def test_point_sample_docstring_says_saturated_cores_can_be_finite():
    """docs/validation/barnards-star.md: OVERFLOW in 357/358 Barnard exposures, NaN in 240, finite OVERFLOW
    pixels in 339; the old docstring said saturated cores were NaN."""
    doc = " ".join((point.PointSample.__doc__ or "").split())
    assert "Saturated cores are NaN with OVERFLOW" not in doc
    assert "finite" in doc and "NaN" in doc and "OVERFLOW" in doc


# --- live -------------------------------------------------------------------------------------------------------

needs_network = pytest.mark.skipif(os.environ.get("ERRANTE_NETWORK_TESTS") != "1", reason="set ERRANTE_NETWORK_TESTS=1")
BARNARD = (269.44623, 4.76870)
# WCS-WAVE table ranges per detector (docs/DATA.md §3.1), with 1 nm of slack.
TABLE_RANGE = {
    1: (0.7339, 1.1273),
    2: (1.0849, 1.6687),
    3: (1.6153, 2.4401),
    4: (2.3970, 3.8639),
    5: (3.7974, 4.4436),
    6: (4.4008, 5.0256),
}


@pytest.mark.network
@needs_network
def test_real_point_series_equals_read_patch():
    series = point.point_series(*BARNARD, max_frames=12, use_cache=False)
    assert len(series.samples) == 12 and not series.failures and series.timings["wave_errors"] == 0
    assert {s.detector for s in series.samples} == set(range(1, 7))  # spread over every band
    assert {s.release for s in series.samples} == {"dr1", "qr3"}  # spread over the baseline: both releases
    assert series.timings["requests"] == sum(s.io["requests"] for s in series.samples)
    for s in series.samples:
        patch = s3range.read_patch(s.frame.s3_key, *BARNARD, 2.0)
        px0, _, py0, _ = patch.extra["bbox"]
        sl = (slice(s.y0 - py0, s.y0 - py0 + s.shape[0]), slice(s.x0 - px0, s.x0 - px0 + s.shape[1]))
        for mine, theirs in (
            (s.image, patch.data),
            (s.variance, patch.variance),
            (s.zodi, patch.zodi),
            (s.flags, patch.flags),
        ):
            np.testing.assert_array_equal(mine, theirs[sl])
        lo, hi = TABLE_RANGE[s.detector]
        assert lo <= s.wavelength_um <= hi and 0 < s.bandwidth_um < 0.2
        # cold: 2 rounds (headers; stamps) + 1 suffix read of WCS-WAVE for the first file of a calibration
        assert s.shape == (11, 11) and s.io["requests"] <= 11 and s.io["rounds"] <= 3
        img = point.to_spherex_image(s)  # the sub-image convention on a real header (WS2 photometry input)
        assert img.wavelength_at(*BARNARD) == pytest.approx((s.wavelength_um, s.bandwidth_um), abs=1e-12)
        x, y = img.wcs.all_world2pix([[*BARNARD]], 0)[0]
        assert (x, y) == pytest.approx((s.x, s.y), abs=1e-6)
        px, py = patch.wcs.all_world2pix([[*BARNARD]], 0)[0]
        assert (px - (s.x0 - px0), py - (s.y0 - py0)) == pytest.approx((x, y), abs=1e-6)
        # smoke: Barnard's Star (J ~ 5) dominates its core in every detector (its core may be NaN: saturated)
        r, c = s.center_pixel
        core = s.image[r - 1 : r + 2, c - 1 : c + 2]
        assert np.nanmax(core) > 20 * np.nanmedian(s.image)
        assert s.core_flags & (1 << 21)  # SOURCE
