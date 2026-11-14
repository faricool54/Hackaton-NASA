"""WS1 cube: spectrum of any position from the SPHEREx DR1 all-sky HiPS FITS cube (errante.data.cube).

Offline tests serve a *virtual* 321 MB tile: the real headers of tile Npix7945 (fixtures/ws1/
cube_tile7945_headers.json) at their real byte offsets, and the three 102x512x512 data cubes
generated from formulas on demand, so every Range request is answered without any file or
network. The HEALPix/HiPS mapping is checked against wcslib (astropy) using the HPX WCS of 17
real tiles (fixtures/ws1/cube_mapping_refs.json) and against positions verified on real data.
Live checks are marked ``network`` (ERRANTE_NETWORK_TESTS=1).
"""

from __future__ import annotations

import base64
import io
import json
import math
import os
import threading
import time
import warnings
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import numpy as np
import pytest
from astropy.io import fits
from astropy.wcs import WCS

from errante import cli, settings
from errante.data import cube, s3range

FIXTURES = Path(__file__).parent / "fixtures" / "ws1"
HEADERS = json.loads((FIXTURES / "cube_tile7945_headers.json").read_text(encoding="utf-8"))
REFS = json.loads((FIXTURES / "cube_mapping_refs.json").read_text(encoding="utf-8"))
BARNARD = (269.44623, 4.76870)  # tile 7945, pixel (98, 103) (verified live)
SAT = (98, 103)  # the virtual tile has a "saturated" core here for planes >= SAT_FROM
SAT_FROM = 60
W, N = 512, 102


@pytest.fixture(autouse=True)
def _tmp_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "CACHE_DIR", tmp_path / "cache")


# --- virtual tile -----------------------------------------------------------------------


def image_value(k, y, x):
    v = (1000.0 * k + 2.0 * y + 0.5 * x).astype(np.float32)  # exact in float32
    blank = np.isin(k, (50, 51)) | ((x == SAT[0]) & (y == SAT[1]) & (k >= SAT_FROM))
    return np.where(blank, np.float32(np.nan), v)


def nhits_value(k, y, x):
    v = 1 + (x + 2 * y + k) % 9
    blank = np.isin(k, (50, 51)) | ((x == SAT[0]) & (y == SAT[1]) & (k >= SAT_FROM))
    return np.where(blank, 0, v).astype(np.int32)


def flags_value(k, y, x):
    return ((1 << 21) | ((x + y + k) % 4)).astype(np.int32)


class VirtualTile:
    """RangeReader over a DR1-like cube tile whose pixel data come from the formulas above."""

    def __init__(self, extra_image_cards: int = 0):
        self.parts: list[tuple[int, int, object]] = []  # (start, stop, bytes | (dtype, fn))
        self.requests: list[tuple[str, int, int]] = []
        self._lock = threading.Lock()
        tables = {
            "SPECTRAL_CHANNELS": base64.b64decode(HEADERS["spectral_channels_data_b64"]),
            "WCS-WAVE": base64.b64decode(HEADERS["wcs_wave_data_b64"]),
        }
        cubes = {"IMAGE": (">f4", image_value), "NHITS": (">i4", nhits_value), "FLAGS": (">i4", flags_value)}
        offset = 0
        for h in HEADERS["hdus"]:
            hdr = fits.Header.fromstring("\n".join(h["cards"]), sep="\n")
            if h["name"] == "IMAGE":
                for i in range(extra_image_cards):
                    hdr.append(("COMMENT", f"padding card {i}"), end=True)
            hb = hdr.tostring().encode("ascii")
            self.parts.append((offset, offset + len(hb), hb))
            doff, size = offset + len(hb), h["data_size"]
            if h["name"] in cubes:
                self.parts.append((doff, doff + size, cubes[h["name"]]))
            elif h["name"] in tables:
                assert len(tables[h["name"]]) == size
                self.parts.append((doff, doff + size, tables[h["name"]]))
            end = doff + -(-size // 2880) * 2880
            if end > doff + size:
                self.parts.append((doff + size, end, b"\0" * (end - doff - size)))
            offset = end
        self.size = offset

    def __call__(self, key: str, start: int, stop: int) -> bytes:
        with self._lock:
            self.requests.append((key, start, stop))
        stop = min(stop, self.size)
        out = bytearray()
        for a, b, src in self.parts:
            lo, hi = max(a, start), min(b, stop)
            if lo >= hi:
                continue
            if isinstance(src, bytes):
                out += src[lo - a : hi - a]
            else:
                dtype, fn = src
                e0, e1 = (lo - a) // 4, -(-(hi - a) // 4)
                e = np.arange(e0, e1, dtype=np.int64)
                k, rem = np.divmod(e, W * W)
                y, x = np.divmod(rem, W)
                raw = fn(k, y, x).astype(dtype).tobytes()
                out += raw[(lo - a) - 4 * e0 : (lo - a) - 4 * e0 + (hi - lo)]
        return bytes(out)


def expected_flux(k, x, y):
    return float(image_value(np.int64(k), np.int64(y), np.int64(x)))


# --- HEALPix ---------------------------------------------------------------------------


def test_base_pixel_centres_order0():
    # Textbook HEALPix: faces 0-3 centred at dec=+41.81 (ra 45, 135, ...), 4-7 on the equator
    # (ra 0, 90, 180, 270), 8-11 at dec=-41.81.
    zdec = math.degrees(math.asin(2.0 / 3.0))
    want = [(45 + 90 * i, zdec) for i in range(4)] + [(90 * i, 0.0) for i in range(4)]
    want += [(45 + 90 * i, -zdec) for i in range(4)]
    for pix, (ra, dec) in enumerate(want):
        got = cube.pix2ang_nest(0, pix)
        assert got == pytest.approx((ra, dec), abs=1e-9), pix
        assert cube.ang2pix_nest(0, ra, dec) == pix


@pytest.mark.parametrize("order", [0, 1, 2, 3, 5])
def test_pix2ang_ang2pix_roundtrip_all_pixels(order):
    pix = np.arange(12 * 4**order)
    ra, dec = cube.pix2ang_nest(order, pix)
    np.testing.assert_array_equal(cube.ang2pix_nest(order, ra, dec), pix)


def test_roundtrip_random_high_order():
    rng = np.random.default_rng(0)
    for order in (14, 20, 29):
        pix = rng.integers(0, 12 * 4**order, 5000, dtype=np.int64)
        ra, dec = cube.pix2ang_nest(order, pix)
        np.testing.assert_array_equal(cube.ang2pix_nest(order, ra, dec), pix)


def test_ang2pix_edge_cases():
    assert cube.ang2pix_nest(5, 0.0, 10.0) == cube.ang2pix_nest(5, 360.0, 10.0) == cube.ang2pix_nest(5, -360.0, 10.0)
    assert cube.ang2pix_nest(5, 123.0, 90.0) < 4 * 4**5  # north pole: faces 0-3
    assert cube.ang2pix_nest(5, 123.0, -90.0) >= 8 * 4**5  # south pole: faces 8-11
    assert isinstance(cube.ang2pix_nest(5, 1.0, 2.0), int)
    for bad in ((0.0, 91.0), (float("nan"), 0.0), (0.0, float("inf"))):
        with pytest.raises(ValueError):
            cube.ang2pix_nest(5, *bad)
    with pytest.raises(ValueError):
        cube.pix2ang_nest(5, 12 * 4**5)


# --- HiPS tile geometry -------------------------------------------------------------------


def _tile_wcs(npix: int) -> WCS:
    h = fits.Header()
    h["NAXIS"], h["NAXIS1"], h["NAXIS2"], h["WCSAXES"] = 2, W, W, 2
    for k, v in REFS["celestial_template"].items():
        h[k] = v
    h["CRPIX1"], h["CRPIX2"] = REFS["tiles"][str(npix)]["CRPIX1"], REFS["tiles"][str(npix)]["CRPIX2"]
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return WCS(h)


@pytest.mark.parametrize("npix", sorted(int(n) for n in REFS["tiles"]))
def test_tile_pixel_mapping_matches_wcslib(npix):
    """Points drawn inside random pixels of a real tile (via its HPX WCS) land on that tile/pixel."""
    w = _tile_wcs(npix)
    rng = np.random.default_rng(npix)
    xs, ys = rng.integers(0, W, 300), rng.integers(0, W, 300)
    sky = w.all_pix2world(np.c_[xs + rng.uniform(-0.45, 0.45, 300), ys + rng.uniform(-0.45, 0.45, 300)], 0)
    ok = np.isfinite(sky).all(axis=1)  # wcslib gives NaN for the half of a seam tile beyond x=+-180 deg
    assert ok.sum() > 100
    for (ra, dec), x, y in zip(sky[ok], xs[ok], ys[ok], strict=True):
        assert cube.sky_to_tile_pixel(ra, dec) == cube.TilePixel(5, npix, int(x), int(y))
    cra, cdec = cube.tile_pixel_to_sky(npix, xs[ok], ys[ok])
    wra, wdec = w.all_pix2world(np.c_[xs[ok], ys[ok]], 0).T
    sep = np.hypot(((cra - wra + 180) % 360 - 180) * np.cos(np.radians(cdec)), cdec - wdec) * 3600
    assert sep.max() < 1e-6  # arcsec


@pytest.mark.parametrize("p", REFS["points"], ids=[p["name"] for p in REFS["points"]])
def test_reference_points(p):
    tp = cube.sky_to_tile_pixel(p["ra"], p["dec"])
    assert (tp.npix, tp.x, tp.y) == (p["npix"], p["x"], p["y"])
    ra, dec = cube.tile_pixel_to_sky(tp.npix, tp.x, tp.y)
    sep = math.hypot(((ra - p["ra"] + 180) % 360 - 180) * math.cos(math.radians(dec)), dec - p["dec"]) * 3600
    assert sep < 12.0  # within the pixel (HEALPix pixels are equal-area but not square: up to ~9.7" seen)


def test_seam_tile_where_wcs_fails():
    """At the RA=180 seam wcslib's world->pixel jumps to another copy of the plane; HEALPix does not."""
    w = _tile_wcs(6912)
    ra, dec = 180.21776, 1.03502  # Gaia star verified on the real tile
    x, _ = w.all_world2pix([[ra, dec]], 0)[0]
    assert not 0 <= x < W  # the trap
    assert cube.sky_to_tile_pixel(ra, dec) == cube.TilePixel(5, 6912, 182, 250)


def test_tile_key_and_urls(monkeypatch):
    assert cube.tile_key(7945) == "dr1/hips5_cube/hips_20261026/Norder5/Dir0/Npix7945_cube.fits"
    assert cube.tile_key(10226).endswith("/Norder5/Dir10000/Npix10226_cube.fits")
    t = cube.cube_tile(10226)
    assert t.url == f"{settings.S3_HTTPS}/dr1/hips5_cube/hips_20261026/Norder5/Dir10000/Npix10226_cube.fits"
    assert t.irsa_url == (
        "https://irsa.ipac.caltech.edu/data/hips/SPHEREx/spherex_allsky_cube/Norder5/Dir10000/Npix10226_cube.fits"
    )
    with pytest.raises(ValueError):
        cube.irsa_url_for_key("dr1/level2/x.fits")
    with pytest.raises(ValueError):
        cube.sky_to_tile_pixel(0.0, 0.0, width=500)


def test_blank_planes():
    assert cube.blank_planes(fits.Header([("BLANKCH", "D3:17,D4:01")])) == (50, 51)
    assert cube.blank_planes(fits.Header([("BLANKCH", "D1:01")])) == (0,)
    assert cube.blank_planes(fits.Header()) == cube.BLANK_PLANES


# --- reading the virtual tile ---------------------------------------------------------------


def test_header_chunks_cover_the_layout():
    chunks = cube._header_chunks(cube.DR1_LAYOUT)
    assert len(chunks) == 4  # PRIMARY+IMAGE header, NHITS header, FLAGS header, the two tables
    assert chunks[-1][1] == HEADERS["file_size"]
    assert sum(b - a for a, b in chunks) < 64 * 1024


def test_virtual_tile_matches_real_layout():
    vt = VirtualTile()
    assert vt.size == HEADERS["file_size"]
    d = cube.tile_directory("k", reader=vt)
    assert cube.layout_of(d) == cube.DR1_LAYOUT
    wl, bw = cube.wavelength_table(d)
    assert (
        len(wl) == N
        and wl[0] == pytest.approx(0.753)
        and wl[90] == pytest.approx(4.600)
        and wl[-1] == pytest.approx(4.988)
    )
    assert np.all(np.diff(wl) > 0) and np.all(bw > 0)
    assert cube.blank_planes(d.primary) == (50, 51)
    # speculative reconstruction from the 4 header chunks gives the same directory
    chunks = {(a, b): vt("k", a, b) for a, b in cube._header_chunks(cube.DR1_LAYOUT)}
    spec = cube._directory_from_chunks("k", cube.DR1_LAYOUT, chunks)
    assert spec is not None and cube.layout_of(spec) == cube.layout_of(d) and spec.wcs_wave == d.wcs_wave
    assert spec["IMAGE"].header == d["IMAGE"].header


def test_spectrum_single_pixel_cold_then_warm_then_cached():
    vt = VirtualTile()
    s = cube.cube_spectrum(*BARNARD, with_nhits=True, reader=vt)
    assert (s.tile.npix, s.pixel) == (7945, (98, 103))
    assert s.timings["mode"] == "speculative" and s.timings["header_requests"] == 4
    assert s.timings["pixel_requests"] == 102 + 100  # IMAGE all planes + NHITS except the blank ones
    assert len(vt.requests) == 4 + 202
    assert all(key == s.tile.key for key, _, _ in vt.requests)
    assert s.unit == "MJy/sr" and s.source == "custom"
    for k in range(N):
        if k in (50, 51) or k >= SAT_FROM:
            assert not s.valid[k] and math.isnan(s.flux[k])
        else:
            assert s.valid[k] and s.flux[k] == expected_flux(k, 98, 103)
    assert s.nhits[10] == 1 + (98 + 206 + 10) % 9 and s.nhits[SAT_FROM] == 0
    assert any("NHITS = 0" in n for n in s.notes)
    assert any("for visualization" in n for n in s.notes)  # IRSA's own description of the cube
    assert list(s.core_valid) == list(s.valid)  # single pixel: valid <=> the centre pixel has data
    assert list(s.detector[[0, 16, 17, 101]]) == [1, 1, 2, 6] and list(s.channel[[0, 16, 17, 101]]) == [1, 17, 1, 17]
    assert s.pixel_scale_arcsec == pytest.approx(12.88, abs=0.01)
    assert s.mjd_range[0] < s.mjd_range[1]

    vt.requests.clear()
    s2 = cube.cube_spectrum(*BARNARD, reader=vt, use_cache=False)  # default: no NHITS
    assert s2.timings["mode"] == "cached-headers" and s2.timings["header_requests"] == 0
    assert len(vt.requests) == 102 and s2.nhits is None
    np.testing.assert_array_equal(s2.flux, s.flux)  # NaN <=> NHITS == 0: same validity without NHITS
    np.testing.assert_array_equal(s2.valid, s.valid)
    assert any("NHITS = 0" in n for n in s2.notes)

    vt.requests.clear()
    s3 = cube.cube_spectrum(BARNARD[0] + 1e-4, BARNARD[1], with_nhits=True, reader=vt)  # same pixel: cached
    assert s3.timings["from_cache"] and not vt.requests
    assert (s3.ra, s3.dec) == (BARNARD[0] + 1e-4, BARNARD[1])
    np.testing.assert_array_equal(s3.flux, s.flux)
    np.testing.assert_array_equal(s3.valid, s.valid)


def test_speculation_miss_falls_back_to_walking():
    vt = VirtualTile(extra_image_cards=40)  # IMAGE header one block longer: every offset shifts
    s = cube.cube_spectrum(*BARNARD, with_nhits=True, reader=vt)
    assert s.timings["mode"] == "speculation-missed"
    assert s.timings["header_requests"] > 4
    assert s.flux[10] == expected_flux(10, 98, 103)
    assert s.nhits[10] == 1 + (98 + 206 + 10) % 9
    d = cube.tile_directory(s.tile.key)  # now cached, with the real (shifted) layout
    assert d["IMAGE"].data_offset == cube.DR1_LAYOUT[1][2] + 2880


def test_no_speculation_walks(monkeypatch):
    monkeypatch.setattr(cube, "SPECULATE", False)
    s = cube.cube_spectrum(*BARNARD, reader=VirtualTile())
    assert s.timings["mode"] == "walk" and s.flux[10] == expected_flux(10, 98, 103)


def test_aperture_with_a_rejected_centre_is_invalid():
    s = cube.cube_spectrum(*BARNARD, aperture_px=1, with_nhits=True, reader=VirtualTile())
    assert s.n_pixels == 5 and not s.clipped and s.min_used == 3
    # the image is linear in x and y, so the mean over the symmetric cross equals the centre value
    assert s.flux[10] == pytest.approx(expected_flux(10, 98, 103))
    assert s.n_used[10] == 5 and s.valid[10] and s.core_valid[10]
    # centre rejected (NaN, NHITS 0), like a saturated star: the 4 neighbours have data, but the mean of
    # a ring around a lost core underestimates the source, so the plane is not a valid point
    assert s.n_used[SAT_FROM] == 4 and not s.core_valid[SAT_FROM]
    assert not s.valid[SAT_FROM] and math.isnan(s.flux[SAT_FROM])
    assert any("with or without an aperture" in n for n in s.notes)
    assert not s.valid[50] and not s.valid[51]


def test_aperture_skips_a_rejected_neighbour():
    ra, dec = cube.tile_pixel_to_sky(7945, SAT[0] + 1, SAT[1])  # the rejected pixel is now a neighbour
    s = cube.cube_spectrum(ra, dec, aperture_px=1, with_nhits=True, reader=VirtualTile())
    assert s.pixel == (SAT[0] + 1, SAT[1])
    assert s.core_valid[SAT_FROM] and s.n_used[SAT_FROM] == 4 and s.valid[SAT_FROM]
    want = np.mean([expected_flux(SAT_FROM, x, y) for x, y in ((99, 103), (100, 103), (99, 102), (99, 104))])
    assert s.flux[SAT_FROM] == pytest.approx(want)


def test_plane_values_rules():
    mask = np.ones((3, 3), dtype=bool)
    vals = np.full((3, 3), np.nan)
    vals[1, 1], vals[0, 0] = 5.0, 1.0  # centre + 1 of the 8 neighbours have data
    flux, used, core = cube._plane_values(vals, None, mask, 1, 1, 1, 5)
    assert math.isnan(flux) and used == 2 and core  # below the minimum coverage
    flux, used, core = cube._plane_values(vals, None, mask, 1, 1, 1, 2)
    assert flux == 3.0 and used == 2 and core
    hits = np.ones((3, 3), dtype=int)
    hits[1, 1] = 0  # a finite value with no input samples does not count
    flux, used, core = cube._plane_values(vals, hits, mask, 1, 1, 1, 1)
    assert math.isnan(flux) and used == 1 and not core
    flux, used, core = cube._plane_values(vals[1:2, 1:2], None, mask[1:2, 1:2], 0, 0, 0, 1)
    assert (flux, used, core) == (5.0, 1, True)


def test_aperture_clipped_at_tile_edge():
    ra, dec = cube.tile_pixel_to_sky(7945, 0, 200)
    s = cube.cube_spectrum(ra, dec, aperture_px=2, reader=VirtualTile())
    assert s.pixel == (0, 200) and s.clipped
    assert s.n_pixels == 13 - 4  # disc of radius 2 has 13 pixels; columns x=-1, -2 hold 3 + 1
    assert any("clipped" in n for n in s.notes)


def test_flags_and_no_nhits():
    vt = VirtualTile()
    s = cube.cube_spectrum(*BARNARD, with_flags=True, reader=vt)
    assert s.nhits is None
    assert s.flags[10] == (1 << 21) | ((98 + 103 + 10) % 4) and s.flags[50] == 0
    assert s.timings["pixel_requests"] == 102 + 100
    assert math.isnan(s.flux[SAT_FROM])  # NaN alone already invalidates a plane


def test_json_roundtrip():
    s = cube.cube_spectrum(*BARNARD, with_nhits=True, reader=VirtualTile())
    d = json.loads(json.dumps(s.to_dict()))  # strict JSON: NaN became null
    assert d["flux"][50] is None and d["valid"][50] is False and d["tile"]["npix"] == 7945
    assert d["pixel"] == {"x": 98, "y": 103, "convention": "0-based column, row of the FITS tile"}
    back = cube.CubeSpectrum.from_dict(d)
    np.testing.assert_array_equal(back.flux, s.flux)
    np.testing.assert_array_equal(back.nhits, s.nhits)
    assert back.tile == s.tile and back.pixel_sr == pytest.approx(s.pixel_sr)


def _down(key, start, stop):
    raise OSError("S3 range read failed")


def test_s3_failure_falls_back_to_irsa(monkeypatch):
    vt = VirtualTile()
    monkeypatch.setattr(s3range, "read_range", _down)
    monkeypatch.setattr(cube, "_s3_reader", _down, raising=False)
    monkeypatch.setattr(cube, "_irsa_reader", vt)
    s = cube.cube_spectrum(*BARNARD)
    assert s.source == "irsa" and s.flux[10] == expected_flux(10, 98, 103)
    assert any("S3 range read failed" in n for n in s.notes)

    # the outage note belongs to that call only: a later cache hit does not repeat it
    again = cube.cube_spectrum(*BARNARD)
    assert again.timings["from_cache"] and again.source == "irsa"
    assert not any("S3 range read failed" in n for n in again.notes)
    np.testing.assert_array_equal(again.flux, s.flux)

    monkeypatch.setattr(cube, "_irsa_reader", _down)
    with pytest.raises(OSError, match="unreadable"):
        cube.cube_spectrum(BARNARD[0], BARNARD[1] + 1.0)
    with pytest.raises(OSError):
        cube.cube_spectrum(BARNARD[0], BARNARD[1] + 1.0, fallback=False)


@pytest.mark.parametrize(
    "kwargs",
    [{"dec": 91.0}, {"ra": float("nan")}, {"ra": 400.0}, {"ra": -200.0}, {"aperture_px": -1}, {"aperture_px": 11}],
)
def test_invalid_input(kwargs):
    args = {"ra": 10.0, "dec": 0.0, **kwargs}
    ra, dec = args.pop("ra"), args.pop("dec")
    with pytest.raises(ValueError):
        cube.cube_spectrum(ra, dec, reader=VirtualTile(), **args)


def test_negative_ra_is_wrapped():
    s = cube.cube_spectrum(BARNARD[0] - 360.0, BARNARD[1], reader=VirtualTile())
    assert (s.tile.npix, s.pixel) == (7945, (98, 103)) and s.ra == pytest.approx(BARNARD[0])


def test_cli(monkeypatch, capsys):
    monkeypatch.setattr(s3range, "read_range", VirtualTile())
    monkeypatch.setattr(cube, "_s3_reader", VirtualTile(), raising=False)
    assert cli.main(["cube-spectrum", "--ra", str(BARNARD[0]), "--dec", str(BARNARD[1])]) == 0
    out = capsys.readouterr().out
    assert "Npix7945" in out and "x=98 y=103" in out and "MJy/sr" in out
    assert f"{expected_flux(10, 98, 103):14.5g}" in out
    assert cli.main(["cube-spectrum", "--ra", str(BARNARD[0]), "--dec", str(BARNARD[1]), "--json"]) == 0
    d = json.loads(capsys.readouterr().out)
    assert d["tile"]["npix"] == 7945 and d["timings"]["from_cache"] is True and d["nhits"] is None
    args = ["cube-spectrum", "--ra", str(BARNARD[0]), "--dec", str(BARNARD[1]), "--json", "--nhits", "--aperture", "1"]
    assert cli.main(args) == 0
    d = json.loads(capsys.readouterr().out)
    assert d["aperture_px"] == 1 and d["nhits"][10] == 1 + (98 + 206 + 10) % 9
    assert cli.main(["cube-spectrum", "--ra", "0", "--dec", "95"]) == 2


# --- HTTP Range on a URL (IRSA fallback) ------------------------------------------------------


class _Handler(BaseHTTPRequestHandler):
    blob = bytes(range(256)) * 64
    honour_range = True
    shift = 0

    def do_GET(self):  # noqa: N802
        rng = self.headers.get("Range")
        if rng and self.honour_range:
            a, b = (int(v) + self.shift for v in rng.split("=")[1].split("-"))
            body = self.blob[a : b + 1]
            self.send_response(206)
            self.send_header("Content-Range", f"bytes {a}-{a + len(body) - 1}/{len(self.blob)}")
        else:
            body = self.blob
            self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


def test_read_url_range_local_server():
    srv = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    th = threading.Thread(target=srv.serve_forever, daemon=True)
    th.start()
    try:
        url = f"http://127.0.0.1:{srv.server_address[1]}/tile.fits"
        assert cube.read_url_range(url, 100, 110) == _Handler.blob[100:110]
        assert cube.read_url_range(url, 5, 5) == b""
        _Handler.honour_range = False
        with pytest.raises(OSError, match="ignored the Range"):
            cube.read_url_range(url, 0, 10)
    finally:
        _Handler.honour_range = True
        srv.shutdown()


def test_read_url_range_checks_the_content_range_start(monkeypatch):
    monkeypatch.setattr(cube, "RANGE_BACKOFF_S", 0.01, raising=False)
    srv = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        url = f"http://127.0.0.1:{srv.server_address[1]}/tile.fits"
        _Handler.shift = 7  # a 206 for other bytes than asked (same length)
        with pytest.raises(OSError, match="range read failed"):
            cube.read_url_range(url, 100, 110)
    finally:
        _Handler.shift = 0
        srv.shutdown()
        srv.server_close()


# --- reliability: timeouts, cancellation, deadline, shared pool ------------------------------


class _BadS3(BaseHTTPRequestHandler):
    """A broken S3: 503 to everything, or accept the request and never answer."""

    mode = "503"
    hits = 0
    release = threading.Event()
    lock = threading.Lock()

    def do_GET(self):  # noqa: N802
        with _BadS3.lock:
            _BadS3.hits += 1
        if self.mode == "503":
            self.send_response(503)
            self.send_header("Content-Length", "0")
            self.end_headers()
        else:
            _BadS3.release.wait(30)

    def log_message(self, *args):
        pass


@pytest.fixture
def bad_s3(monkeypatch):
    _BadS3.hits, _BadS3.mode = 0, "503"
    _BadS3.release.clear()
    srv = ThreadingHTTPServer(("127.0.0.1", 0), _BadS3)
    srv.daemon_threads = True
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    monkeypatch.setattr(settings, "S3_HTTPS", f"http://127.0.0.1:{srv.server_address[1]}")
    monkeypatch.setattr(cube, "_irsa_reader", VirtualTile())
    yield _BadS3
    _BadS3.release.set()
    srv.shutdown()
    srv.server_close()


def test_s3_errors_stop_the_other_requests_and_fall_back_fast(bad_s3, monkeypatch):
    monkeypatch.setattr(cube, "RANGE_BACKOFF_S", 0.02, raising=False)
    monkeypatch.setattr(settings, "HTTP_TIMEOUT_S", 2.0)
    t = time.perf_counter()
    s = cube.cube_spectrum(*BARNARD, use_cache=False)
    assert s.source == "irsa" and s.flux[10] == expected_flux(10, 98, 103)
    assert time.perf_counter() - t < 5
    # one request failing for good stops the rest: not 106 requests x 4 attempts
    assert bad_s3.hits < 2 * cube.RANGE_RETRIES * cube.CUBE_PARALLEL


def test_s3_that_never_answers_falls_back_at_the_deadline(bad_s3, monkeypatch):
    bad_s3.mode = "hang"
    monkeypatch.setattr(cube, "CUBE_TIMEOUT", (1.0, 5.0), raising=False)
    monkeypatch.setattr(cube, "CUBE_DEADLINE_S", 1.0, raising=False)
    monkeypatch.setattr(settings, "HTTP_TIMEOUT_S", 5.0)
    t = time.perf_counter()
    s = cube.cube_spectrum(*BARNARD, use_cache=False)
    elapsed = time.perf_counter() - t
    assert s.source == "irsa" and s.flux[10] == expected_flux(10, 98, 103)
    assert elapsed < 4  # the S3 requests still hanging do not hold the IRSA reads back
    assert any("within 1 s" in n for n in s.notes)


def test_concurrent_calls_share_one_request_budget_and_read_headers_once(monkeypatch):
    monkeypatch.setattr(cube, "CUBE_PARALLEL", 4)
    vt = VirtualTile()
    state = {"now": 0, "max": 0}
    lock = threading.Lock()

    def reader(key, start, stop):
        with lock:
            state["now"] += 1
            state["max"] = max(state["max"], state["now"])
        try:
            time.sleep(0.001)
            return vt(key, start, stop)
        finally:
            with lock:
                state["now"] -= 1

    same = [cube.tile_pixel_to_sky(7945, x, y) for x, y in ((98, 103), (10, 20), (300, 400))]
    other = [cube.tile_pixel_to_sky(n, 50, 60) for n in (100, 9000)]
    with ThreadPoolExecutor(len(same) + len(other)) as ex:
        res = list(ex.map(lambda p: cube.cube_spectrum(*p, reader=reader), same + other))
    assert state["max"] <= 4  # all calls together, not 4 per call
    heads = {a for a, _ in cube._header_chunks(cube.DR1_LAYOUT)}
    key = cube.tile_key(7945)
    assert sum(1 for k, a, _ in vt.requests if k == key and a in heads) == 4  # one speculation for the tile
    assert [r.pixel for r in res[:3]] == [(98, 103), (10, 20), (300, 400)]
    assert res[1].flux[10] == expected_flux(10, 10, 20) and res[2].flux[10] == expected_flux(10, 300, 400)
    assert sorted(r.timings["mode"] for r in res[:3]) == ["cached-headers", "cached-headers", "speculative"]


def test_no_irsa_fallback_for_another_release(monkeypatch):
    irsa = VirtualTile()
    monkeypatch.setattr(s3range, "read_range", _down)
    monkeypatch.setattr(cube, "_s3_reader", _down, raising=False)
    monkeypatch.setattr(cube, "_irsa_reader", irsa)
    monkeypatch.setattr(cube, "CUBE_PREFIX", "dr2/hips5_cube/hips_20270101")
    monkeypatch.setattr(cube, "IRSA_BASE_FROM_ENV", False, raising=False)
    with pytest.raises(OSError, match="IRSA fallback"):
        cube.cube_spectrum(*BARNARD)
    assert not irsa.requests  # IRSA serves the DR1 tiles: never mixed into another release
    monkeypatch.setattr(cube, "IRSA_BASE_FROM_ENV", True)  # an explicit IRSA base for that release
    assert cube.cube_spectrum(*BARNARD).source == "irsa"


def test_malformed_tile_is_a_read_error_not_a_bad_request(monkeypatch, capsys):
    def broken(directory):
        raise ValueError("WCS-WAVE does not list planes 1..102")

    monkeypatch.setattr(cube, "wavelength_table", broken)
    with pytest.raises(OSError, match="malformed"):
        cube.cube_spectrum(*BARNARD, reader=VirtualTile())
    monkeypatch.setattr(s3range, "read_range", VirtualTile())
    monkeypatch.setattr(cube, "_s3_reader", VirtualTile(), raising=False)
    monkeypatch.setattr(cube, "_irsa_reader", VirtualTile())
    assert cli.main(["cube-spectrum", "--ra", str(BARNARD[0]), "--dec", str(BARNARD[1])]) == 1
    assert "Cube read failed" in capsys.readouterr().err


def test_directory_cache_ignores_other_versions():
    vt = VirtualTile()
    cube.tile_directory("k", reader=vt)
    path = cube._dir_path("k")
    raw = json.loads(path.read_text(encoding="ascii"))
    raw["version"] = 999
    path.write_text(json.dumps(raw), encoding="ascii")
    cube._dirs.pop((str(settings.CACHE_DIR), "k"), None)
    assert cube._cached_directory("k") is None
    vt.requests.clear()
    cube.tile_directory("k", reader=vt)
    assert vt.requests  # read again instead of trusting an unknown format


def test_wavelength_table_matches_astropy():
    d = cube.tile_directory("k", reader=VirtualTile())
    wl, bw = cube.wavelength_table(d)
    blob = fits.PrimaryHDU().header.tostring().encode("ascii") + d.wcs_wave
    with fits.open(io.BytesIO(blob), memmap=False) as hl:
        row = hl[1].data[0]
        assert list(np.ravel(row["PLANE"])) == list(range(1, N + 1))
        np.testing.assert_array_equal(wl, np.ravel(row["WAVELENGTHS"]).astype(float))
        np.testing.assert_array_equal(bw, np.ravel(row["BANDWIDTHS"]).astype(float))


def test_env_settings_never_break_the_import(monkeypatch):
    monkeypatch.setenv("ERRANTE_TEST_SETTING", "thirty-two")
    assert cube._env_int("ERRANTE_TEST_SETTING", 32, 1, 128) == 32
    monkeypatch.setenv("ERRANTE_TEST_SETTING", "1000")
    assert cube._env_int("ERRANTE_TEST_SETTING", 32, 1, 128) == 128
    monkeypatch.setenv("ERRANTE_TEST_SETTING", "nan")
    assert cube._env_float("ERRANTE_TEST_SETTING", 20.0, 1.0, 3600.0) == 20.0
    monkeypatch.setenv("ERRANTE_TEST_SETTING", "0")
    assert cube._env_float("ERRANTE_TEST_SETTING", 20.0, 1.0, 3600.0) == 1.0


# --- live ---------------------------------------------------------------------------------

needs_network = pytest.mark.skipif(os.environ.get("ERRANTE_NETWORK_TESTS") != "1", reason="set ERRANTE_NETWORK_TESTS=1")
# data_cube_crval3_arr of https://irsa.ipac.caltech.edu/data/hips/SPHEREx/spherex_allsky_cube/properties
PROPERTIES_WAVELENGTHS = [0.753, 0.771, 0.790, 0.809, 0.828, 0.848, 0.868, 0.889, 0.910, 0.932, 0.955, 0.978, 1.001, 1.025, 1.050, 1.075, 1.102, 1.113, 1.139, 1.167, 1.195, 1.224, 1.254, 1.284, 1.315, 1.346, 1.378, 1.412, 1.446, 1.481, 1.517, 1.554, 1.592, 1.631, 1.656, 1.695, 1.735, 1.775, 1.818, 1.861, 1.905, 1.949, 1.995, 2.041, 2.089, 2.139, 2.189, 2.240, 2.292, 2.345, 2.399, 2.445, 2.506, 2.575, 2.646, 2.719, 2.794, 2.871, 2.951, 3.033, 3.118, 3.204, 3.293, 3.383, 3.476, 3.570, 3.667, 3.768, 3.833, 3.867, 3.901, 3.935, 3.970, 4.005, 4.040, 4.076, 4.112, 4.148, 4.184, 4.220, 4.257, 4.294, 4.331, 4.368, 4.405, 4.435, 4.467, 4.500, 4.533, 4.566, 4.600, 4.635, 4.669, 4.704, 4.739, 4.773, 4.808, 4.843, 4.879, 4.915, 4.951, 4.988]  # fmt: skip


@pytest.mark.network
@needs_network
def test_real_tile_layout_and_wavelengths():
    d = cube.tile_directory(cube.tile_key(7945))
    assert cube.layout_of(d) == cube.DR1_LAYOUT
    assert d.primary["BLANKCH"] == "D3:17,D4:01"
    img = d["IMAGE"].header
    assert (img["CTYPE1"], img["CTYPE2"], img["CTYPE3"]) == ("RA---HPX", "DEC--HPX", "WAVE-TAB")
    assert (img["ORDER"], img["NPIX"], img["BUNIT"]) == (5, 7945, "MJy/sr")
    wl, _ = cube.wavelength_table(d)
    np.testing.assert_allclose(wl, PROPERTIES_WAVELENGTHS, atol=5e-7)


@pytest.mark.network
@needs_network
def test_real_barnard_saturated_core_and_rw_aur_peak():
    s = cube.cube_spectrum(*BARNARD, with_flags=True, with_nhits=True, use_cache=False)
    assert (s.tile.npix, s.pixel) == (7945, (98, 103))
    # Barnard's Star (K=4.5) saturates: the coadd rejected every sample of its core pixel at 4.6 um
    assert not s.valid[90] and s.nhits[90] == 0 and s.flags[90] & (1 << 1 | 1 << 26)
    key = s.tile.key
    d = cube.tile_directory(key)
    box = cube._read_span(key, d["IMAGE"], 90, 95, 101, 100, 106, s3range.read_range)
    assert np.isnan(box[3, 3]) and np.nanmax(box) > 20 and np.nanmedian(box) < 2  # bright ring around the hole
    # RW Aur (K~7) is not saturated at 0.955 um: its pixel is the 5x5 maximum
    rw = cube.cube_spectrum(76.95659, 30.40129, use_cache=False)
    rd = cube.tile_directory(rw.tile.key)
    x, y = rw.pixel
    b = cube._read_span(rw.tile.key, rd["IMAGE"], 10, x - 2, x + 2, y - 2, y + 2, s3range.read_range)
    assert np.nanargmax(b) == 12 and rw.valid[10]


@pytest.mark.network
@needs_network
def test_real_saturated_star_has_no_valid_aperture_planes():
    """R Dra (K~-1.7) is a NaN hole in every plane: an aperture only sees the ring around it."""
    s = cube.cube_spectrum(248.16723, 66.75502, aperture_px=3, use_cache=False)
    assert (s.tile.npix, s.pixel) == (2928, (20, 425))
    assert not s.core_valid.any() and not s.valid.any()
    assert s.n_used.max() >= s.min_used  # the ring has data; it is just not the star


@pytest.mark.network
@needs_network
def test_real_seam_star_peaks_on_predicted_pixel():
    ra, dec = 180.21776, 1.03502  # Gaia DR3 G=11.92, where the tile's own HPX WCS fails
    s = cube.cube_spectrum(ra, dec, aperture_px=0, use_cache=False)
    d = cube.tile_directory(s.tile.key)
    x, y = s.pixel
    b = cube._read_span(s.tile.key, d["IMAGE"], 25, x - 2, x + 2, y - 2, y + 2, s3range.read_range)
    assert np.nanargmax(b) == 12


@pytest.mark.network
@needs_network
def test_real_field_star_flux_matches_allwise():
    """2MASS K=9.34 / AllWISE W2=9.343 star 100" from Barnard: 31.5 mJy at 4.6 um from W2."""
    s = cube.cube_spectrum(269.44388, 4.79629, aperture_px=2, use_cache=False)
    ring = cube.cube_spectrum(269.44388, 4.79629, aperture_px=4, use_cache=False)
    k = 90
    inner = s.flux[k] * s.n_used[k]
    outer_mean = (ring.flux[k] * ring.n_used[k] - inner) / (ring.n_used[k] - s.n_used[k])
    mjy = (inner - outer_mean * s.n_used[k]) * s.pixel_sr * 1e9
    assert 0.6 * 31.5 < mjy < 1.3 * 31.5


@pytest.mark.network
@needs_network
def test_real_irsa_copy_is_identical():
    key = cube.tile_key(7945)
    for a, b in ((0, 8640), (94371840, 94381840), (320898240, 320909760)):
        assert cube._irsa_reader(key, a, b) == s3range.read_range(key, a, b)
