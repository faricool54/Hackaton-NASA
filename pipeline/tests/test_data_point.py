"""WS1 point series: every exposure at a sky point as small stamps read from S3 (errante.data.point).

Offline tests use synthetic L2 files with the real layout (docs/DATA.md §2: PRIMARY, IMAGE, FLAGS
tile-compressed RICE_1 with one tile per row, VARIANCE, ZODI, EPSF, WCS-WAVE; VARIANCE/ZODI headers
shorter than the IMAGE one; the real DR1 D3 TAN-SIP header with its ``[CALIB] spectral_wcs`` HISTORY),
served by a fake Range reader. Live checks are marked ``network``.
"""

from __future__ import annotations

import io
import json
import math
import os
import warnings
from pathlib import Path

import numpy as np
import pytest
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
    """Serves byte ranges (b"" past the end) and suffix reads of in-memory objects, like the S3 bucket."""

    def __init__(self, objects: dict[str, bytes]):
        self.objects = objects
        self.calls = 0
        self.tails = 0
        self.bytes = 0

    def __call__(self, key: str, start: int, stop: int) -> bytes:
        self.calls += 1
        data = self.objects[key][start:stop]
        self.bytes += len(data)
        return data

    def tail(self, key: str, nbytes: int) -> tuple[bytes, int]:
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
    assert npz.name == "out.npz" and js.name == "out.json" and json.loads(js.read_text())["format"] == 1
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
    assert len(series.samples) == 12 and not series.failures
    assert {s.detector for s in series.samples} == set(range(1, 7))  # spread over every band
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
        assert s.shape == (11, 11) and s.io["requests"] <= 10 and s.io["rounds"] <= 2
        # smoke: Barnard's Star (J ~ 5) dominates its core in every detector (its core may be NaN: saturated)
        r, c = s.center_pixel
        core = s.image[r - 1 : r + 2, c - 1 : c + 2]
        assert np.nanmax(core) > 20 * np.nanmedian(s.image)
        assert s.core_flags & (1 << 21)  # SOURCE
