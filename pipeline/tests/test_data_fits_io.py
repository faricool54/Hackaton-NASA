"""WS1: per-pixel wavelength (WCS-WAVE) and mid-exposure time in errante.data.fits_io.

Offline fixtures (pipeline/tests/fixtures/ws1/, real data retrieved 2026-11-14; *.fits is git-ignored, so the
FITS files are rebuilt in tmp_path from text):
  - IMAGE headers of the full DR1 file 2025W33_2C_0321_1 D3 and of its IRSA IBE 5' cutout centred on Barnard;
  - the file's WCS-WAVE table (TDIM (2,9,14)) and reference values computed on the real files with the
    IRSA-tutorial method (astropy key='W', sip=None).
Network tests: ERRANTE_NETWORK_TESTS=1 pytest -m network pipeline/tests/test_data_fits_io.py
"""

from __future__ import annotations

import json
import os
import time
from collections.abc import Callable
from pathlib import Path

import numpy as np
import pytest
from astropy.io import fits

from errante.data import fits_io

FIX = Path(__file__).parent / "fixtures" / "ws1"
DOC = json.loads((FIX / "wcs_wave_2025W33_2C_0321_1D3.json").read_text(encoding="ascii"))
RA = DOC["provenance"]["sky_position"]["ra"]
DEC = DOC["provenance"]["sky_position"]["dec"]
REF = DOC["reference"]


def _header(kind: str) -> fits.Header:
    text = (FIX / f"{kind}_2025W33_2C_0321_1D3_image_header.txt").read_text(encoding="ascii")
    return fits.Header.fromstring(text, sep="\n")


def _wave_hdu(doc: dict | None = None, *, with_tdim: bool = True) -> fits.BinTableHDU:
    t = (doc or DOC)["wcs_wave"]
    h = t["header"]
    cols = [
        fits.Column(
            name=name,
            format=h[f"TFORM{i}"],
            dim=h[f"TDIM{i}"] if with_tdim else None,
            array=np.array([t[name]], dtype=np.int32 if name in "XY" else np.float32),
        )
        for i, name in enumerate(("X", "Y", "VALUES"), start=1)
    ]
    hdu = fits.BinTableHDU.from_columns(cols, name=fits_io.WAVE_EXTNAME)
    hdu.header["DETECTOR"] = h["DETECTOR"]
    return hdu


def _write_mef(path: Path, header: fits.Header, wave: fits.BinTableHDU | None = None) -> Path:
    shape = (header["NAXIS2"], header["NAXIS1"])
    hdus = [
        fits.PrimaryHDU(),
        fits.ImageHDU(np.zeros(shape, np.float32), header=header.copy(), name="IMAGE"),
        fits.ImageHDU(np.zeros(shape, np.int32), name="FLAGS"),
        fits.ImageHDU(np.zeros(shape, np.float32), name="VARIANCE"),
        fits.ImageHDU(np.zeros(shape, np.float32), name="ZODI"),
        wave if wave is not None else _wave_hdu(),
    ]
    fits.HDUList(hdus).writeto(path, output_verify="silentfix")
    return path


def _crop(header: fits.Header, x0: int, y0: int, nx: int, ny: int) -> fits.Header:
    """Sub-image convention (IBE cutouts and our S3 patches): shift CRPIXn, CRPIXnA, CRPIXnW by the origin."""
    h = header.copy()
    for key in ("", "A", "W"):
        h[f"CRPIX1{key}"] = h[f"CRPIX1{key}"] - x0
        h[f"CRPIX2{key}"] = h[f"CRPIX2{key}"] - y0
    h["NAXIS1"], h["NAXIS2"] = nx, ny
    return h


def _sky_pixel(header: fits.Header) -> tuple[float, float]:
    x, y = fits_io.celestial_wcs(header).world_to_pixel_values(RA, DEC)
    return float(x), float(y)


# --------------------------------------------------------------------------- table parsing


def test_wave_table_shape_comes_from_tdim():
    table = fits_io.WaveTable.from_hdu(_wave_hdu())
    assert table.shape == (9, 14)  # D3: TDIM3 = '(2,9,14)'
    assert table.wavelength.shape == table.bandwidth.shape == (14, 9)
    assert (table.x_nodes[0], table.x_nodes[-1], table.y_nodes[0], table.y_nodes[-1]) == (1, 2040, 1, 2040)
    assert 1.61 < table.wavelength.min() < table.wavelength.max() < 2.44  # D3


def test_flat_values_without_tdim_are_reshaped_in_paper3_order():
    a = fits_io.WaveTable.from_hdu(_wave_hdu())
    b = fits_io.WaveTable.from_hdu(_wave_hdu(with_tdim=False))
    np.testing.assert_array_equal(a.wavelength, b.wavelength)
    np.testing.assert_array_equal(a.bandwidth, b.bandwidth)


def test_inconsistent_table_shape_is_rejected():
    doc = json.loads(json.dumps(DOC))
    doc["wcs_wave"]["header"]["TDIM3"] = "(2,14,9)"  # swapped axes
    with pytest.raises(ValueError, match="VALUES shape"):
        fits_io.WaveTable.from_hdu(_wave_hdu(doc))


# --------------------------------------------------------------------------- real full frame vs real cutout


@pytest.mark.parametrize("kind", ["full", "cutout"])
def test_bilinear_lookup_matches_irsa_tutorial(kind):
    header, wave = _header(kind), _wave_hdu()
    nx, ny = header["NAXIS1"], header["NAXIS2"]
    gx, gy = np.meshgrid(np.linspace(-0.5, nx - 0.5, 23), np.linspace(-0.5, ny - 0.5, 29))
    lam, bw = fits_io.wavelength_from_table(wave, header, gx, gy)
    lam_t, bw_t = fits_io.spectral_wcs(header, wave).pixel_to_world_values(gx, gy)
    assert np.all(np.isfinite(lam)) and np.all(np.isfinite(bw))
    assert np.max(np.abs(lam - lam_t)) < 1e-9 and np.max(np.abs(bw - bw_t)) < 1e-9
    for px, py, lam_ref, bw_ref in REF[kind]["pixels"]:  # tutorial values computed on the real file
        got = fits_io.wavelength_from_table(wave, header, px, py)
        assert got == pytest.approx((lam_ref, bw_ref), abs=1e-9)


def test_full_frame_and_ibe_cutout_agree_at_the_same_sky_position():
    full, cut, wave = _header("full"), _header("cutout"), _wave_hdu()
    xf, yf = _sky_pixel(full)
    xc, yc = _sky_pixel(cut)
    assert (xf, yf) == pytest.approx((REF["full"]["x0"], REF["full"]["y0"]), abs=1e-6)
    # the cutout's W WCS maps its pixels back to detector pixels: CRPIX1W = 1 - 1605, CRPIX2W = 1 - 255
    assert (cut["CRPIX1W"], cut["CRPIX2W"]) == (-1604, -254)
    assert fits_io.detector_pixel(cut, xc, yc) == pytest.approx((xf + 1, yf + 1), abs=1e-6)
    lam_f, bw_f = (float(v) for v in fits_io.wavelength_from_table(wave, full, xf, yf))
    lam_c, bw_c = (float(v) for v in fits_io.wavelength_from_table(wave, cut, xc, yc))
    assert (lam_f, bw_f) == pytest.approx((lam_c, bw_c), abs=1e-9)
    assert (lam_c, bw_c) == pytest.approx((REF["full"]["wavelength_um"], REF["full"]["bandwidth_um"]), abs=1e-9)
    assert 1.64 <= lam_c <= 2.42  # inside the D3 band


def test_wavelength_at_reads_a_cutout_file_and_an_open_hdulist(tmp_path):
    path = _write_mef(tmp_path / "cutout.fits", _header("cutout"))
    expected = (REF["cutout"]["wavelength_um"], REF["cutout"]["bandwidth_um"])
    assert fits_io.wavelength_at(path, RA, DEC) == pytest.approx(expected, abs=1e-9)
    with fits.open(path) as hdul:
        assert fits_io.wavelength_at(hdul, RA, DEC) == pytest.approx(expected, abs=1e-9)


def test_wavelength_at_outside_the_array_is_none(tmp_path):
    path = _write_mef(tmp_path / "cutout.fits", _header("cutout"))
    assert fits_io.wavelength_at(path, RA, DEC + 0.2) is None  # 12' north of a 5' cutout
    assert fits_io.wavelength_at(path, (RA + 180) % 360, -DEC) is None  # other side of the sky


def test_patch_convention_shifted_crpix_gives_the_same_wavelength(tmp_path):
    cut = _header("cutout")
    patch = _crop(cut, x0=10, y0=7, nx=30, ny=33)
    xc, yc = _sky_pixel(cut)
    xp, yp = _sky_pixel(patch)
    assert (xp, yp) == pytest.approx((xc - 10, yc - 7), abs=1e-6)
    expected = (REF["cutout"]["wavelength_um"], REF["cutout"]["bandwidth_um"])
    assert fits_io.wavelength_from_table(_wave_hdu(), patch, xp, yp) == pytest.approx(expected, abs=1e-9)
    path = _write_mef(tmp_path / "patch.fits", patch)
    assert fits_io.wavelength_at(path, RA, DEC) == pytest.approx(expected, abs=1e-9)
    # a patch of a FULL frame (what an S3 range reader writes) follows the same rule
    full_patch = _crop(_header("full"), x0=1600, y0=250, nx=64, ny=64)
    xq, yq = _sky_pixel(full_patch)
    assert fits_io.wavelength_from_table(_wave_hdu(), full_patch, xq, yq) == pytest.approx(expected, abs=1e-9)


def test_falls_back_to_the_A_wcs_and_to_identity_on_full_frames():
    wave = _wave_hdu()
    expected = (REF["cutout"]["wavelength_um"], REF["cutout"]["bandwidth_um"])
    cut = _header("cutout")
    no_w = cut.copy()
    del no_w["CRPIX1W"], no_w["CRPIX2W"]
    assert fits_io.wavelength_from_table(wave, no_w, *_sky_pixel(cut)) == pytest.approx(expected, abs=1e-9)
    no_alt = no_w.copy()
    del no_alt["CRPIX1A"], no_alt["CRPIX2A"]
    with pytest.raises(ValueError, match="Cannot place"):
        fits_io.wavelength_from_table(wave, no_alt, 0, 0)
    full = _header("full")
    for k in ("CRPIX1W", "CRPIX2W", "CRPIX1A", "CRPIX2A"):
        del full[k]
    assert fits_io.wavelength_from_table(wave, full, *_sky_pixel(_header("full"))) == pytest.approx(expected, abs=1e-9)


# --------------------------------------------------------------------------- synthetic table, exact math


def _linear_table() -> tuple[fits.BinTableHDU, Callable]:
    """9x14 table (real D3 node positions) of a function that is linear in X and Y -> bilinear is exact."""
    x_nodes = np.array(DOC["wcs_wave"]["X"], float)
    y_nodes = np.array(DOC["wcs_wave"]["Y"], float)

    def truth(px, py):
        return 2.42 - 3.9e-4 * (py - 1) + 1.0e-5 * (px - 1), 0.03 + 1.5e-5 * (py - 1)

    gx, gy = np.meshgrid(x_nodes, y_nodes)
    lam, bw = truth(gx, gy)
    doc = json.loads(json.dumps(DOC))
    doc["wcs_wave"]["VALUES"] = np.stack([lam, bw], axis=-1).tolist()
    return _wave_hdu(doc), truth


def test_bilinear_is_exact_on_a_linear_table_and_nan_off_detector():
    wave, truth = _linear_table()
    table = fits_io.WaveTable.from_hdu(wave)
    rng = np.random.default_rng(1)
    px, py = rng.uniform(0.5, 2040.5, 500), rng.uniform(0.5, 2040.5, 500)
    lam, bw = table.at_detector(px, py)
    lam_t, bw_t = truth(px, py)
    np.testing.assert_allclose(lam, lam_t, atol=2e-6)  # float32 table nodes
    np.testing.assert_allclose(bw, bw_t, atol=2e-6)
    # half a pixel beyond the outermost nodes is still on the detector; further out (or NaN) is not
    lam, bw = table.at_detector(np.array([0.4, 0.5, 1.0, 2040.5, 2040.6, np.nan]), np.full(6, 5.0))
    assert np.isnan(lam[[0, 4, 5]]).all() and np.isnan(bw[[0, 4, 5]]).all()
    np.testing.assert_allclose(lam[1:4], truth(np.array([0.5, 1.0, 2040.5]), 5.0)[0], atol=2e-6)


def test_synthetic_full_frame_header_is_identity():
    wave, truth = _linear_table()
    hdr = fits.Header({"NAXIS1": 2040, "NAXIS2": 2040, "CRPIX1W": 1, "CRPIX2W": 1, "CRVAL1W": 1, "CRVAL2W": 1})
    lam, bw = fits_io.wavelength_from_table(wave, hdr, 99.0, 1499.0)  # 0-based -> detector (100, 1500)
    assert (float(lam), float(bw)) == pytest.approx(truth(100.0, 1500.0), abs=2e-6)


# --------------------------------------------------------------------------- time


def test_mid_exposure_mjd_prefers_mjd_avg_with_documented_fallbacks():
    h = _header("full")
    mjd, src = fits_io.mid_exposure_mjd(h)
    assert (mjd, src) == (60902.865380749, "MJD-AVG")
    assert mjd - h["MJD-OBS"] == pytest.approx(57.56 / 86400, abs=0.01 / 86400)  # start != middle
    del h["MJD-AVG"]
    mjd2, src2 = fits_io.mid_exposure_mjd(h)
    assert src2 == "(MJD-OBS+MJD-END)/2" and mjd2 == pytest.approx(mjd, abs=1e-8)
    del h["MJD-END"]
    mjd3, src3 = fits_io.mid_exposure_mjd(h)
    assert src3 == "MJD-OBS+XPOSURE/2" and mjd3 == pytest.approx(h["MJD-OBS"] + 113.5826 / 2 / 86400)
    assert abs(mjd3 - mjd) * 86400 < 1.0  # XPOSURE < MJD-END - MJD-OBS: ~0.8 s early
    del h["XPOSURE"]
    assert fits_io.mid_exposure_mjd(h) == (h["MJD-OBS"], "MJD-OBS")


def test_read_spherex_uses_mid_exposure_and_keeps_the_wave_table(tmp_path):
    img = fits_io.read_spherex(_write_mef(tmp_path / "cutout.fits", _header("cutout")))
    assert img.mjd == 60902.865380749
    assert img.extra["mjd_obs"] == 60902.86471456
    assert img.extra["mjd_end"] == 60902.866046939
    assert img.extra["date_avg"] == "2025-08-15T20:46:08.897"
    assert img.extra["mjd_source"] == "MJD-AVG"
    assert img.date_obs == "2025-08-15T20:46:08.897"  # DATE-AVG: the same instant as img.mjd
    assert img.extra["date_beg"] == "2025-08-15T20:45:11.338"
    assert (img.obs_id, img.detector) == ("2025W33_2C_0321_1", 3)
    assert img.data.shape == img.flags.shape == img.variance.shape == img.zodi.shape == (49, 49)
    assert img.wave is not None and img.wave.shape == (9, 14)
    expected = (REF["cutout"]["wavelength_um"], REF["cutout"]["bandwidth_um"])
    assert img.wavelength_at(RA, DEC) == pytest.approx(expected, abs=1e-9)
    assert img.wavelength_at(RA, DEC + 0.2) is None


def test_mid_exposure_date_names_the_same_instant_as_the_mjd():
    h = _header("cutout")
    assert fits_io.mid_exposure_date(h, *fits_io.mid_exposure_mjd(h)) == "2025-08-15T20:46:08.897"
    del h["MJD-AVG"]  # computed from (MJD-OBS + MJD-END) / 2: within a millisecond of DATE-AVG
    assert fits_io.mid_exposure_date(h, *fits_io.mid_exposure_mjd(h)) == "2025-08-15T20:46:08.897"
    del h["MJD-END"], h["XPOSURE"]  # only the start is known: DATE-OBS, consistent with mjd == MJD-OBS
    assert fits_io.mid_exposure_date(h, *fits_io.mid_exposure_mjd(h)) == "2025-08-15T20:45:11.338"


def test_read_spherex_survives_an_unusable_wave_table(tmp_path, caplog):
    doc = json.loads(json.dumps(DOC))
    doc["wcs_wave"]["header"]["TDIM3"] = "(2,14,9)"  # swapped axes -> WaveTable.from_hdu raises
    path = _write_mef(tmp_path / "odd.fits", _header("cutout"), _wave_hdu(doc))
    img = fits_io.read_spherex(path)
    assert img.wave is None and "VALUES shape" in img.extra["wave_error"]
    assert img.wavelength_at(RA, DEC) is None
    assert img.data.shape == (49, 49) and img.mjd == 60902.865380749
    assert "unusable WCS-WAVE" in caplog.text


@pytest.mark.filterwarnings("ignore::astropy.io.fits.verify.VerifyWarning")
@pytest.mark.filterwarnings("ignore::astropy.utils.exceptions.AstropyUserWarning")  # "treated as corrupted"
@pytest.mark.parametrize(
    ("card", "garbage", "astropy_error"),
    [
        (b"TFORM1  = ", b"821-9Y=2AC9'.5=YXZ70", "VerifyError"),
        (b"XTENSION= ", b"5  -Z'252'.58742YB.1", "AttributeError"),
    ],
    ids=["tform", "xtension"],
)
def test_read_spherex_survives_an_unparsable_wave_card(tmp_path, card, garbage, astropy_error):
    """Review 2026-11-15: a WCS-WAVE card astropy cannot parse raised VerifyError / AttributeError (_CorruptedHDU)
    out of read_spherex, whose docstring promises wave=None with extra['wave_error'] instead."""
    path = _write_mef(tmp_path / "odd.fits", _header("cutout"))
    blob = bytearray(path.read_bytes())
    start = blob.rindex(b"XTENSION= 'BINTABLE'")  # the WCS-WAVE HDU is the last one
    at = blob.index(card, start)
    assert at % 80 == 0
    blob[at + 10 : at + 30] = garbage
    path.write_bytes(bytes(blob))
    img = fits_io.read_spherex(path)
    assert img.wave is None and img.extra["wave_error"].startswith(astropy_error)
    assert img.data.shape == (49, 49) and img.mjd == 60902.865380749


def test_inconsistent_w_and_a_shifts_are_rejected():
    wave = _wave_hdu()
    bad = _header("cutout")
    bad["CRPIX1W"] = bad["CRPIX1W"] + 1600  # a patch writer that forgot to shift CRPIXnW
    bad["CRPIX2W"] = bad["CRPIX2W"] + 250
    with pytest.raises(ValueError, match="Inconsistent sub-image header"):
        fits_io.wavelength_from_table(wave, bad, *_sky_pixel(bad))
    ok = _header("cutout")  # real IBE cutout: W and A agree to the pixel
    assert np.isfinite(fits_io.wavelength_from_table(wave, ok, *_sky_pixel(ok))[0])


# --------------------------------------------------------------------------- live (network)


def network_marks(fn):
    fn = pytest.mark.skipif(os.environ.get("ERRANTE_NETWORK_TESTS") != "1", reason="set ERRANTE_NETWORK_TESTS=1")(fn)
    return pytest.mark.network(fn)


S3 = "https://nasa-irsa-spherex.s3.us-east-1.amazonaws.com/"
IBE = "https://irsa.ipac.caltech.edu/ibe/data/spherex/"
BARNARD_2026 = (269.44623, 4.76870)
BANDS = {1: (0.75, 1.11), 2: (1.11, 1.64), 3: (1.64, 2.42), 4: (2.42, 3.82), 5: (3.82, 4.42), 6: (4.42, 5.00)}
# One DR1 frame per detector covering Barnard (SIA2 2026-11-14) and lambda measured there on 2026-11-14.
LIVE_FRAMES = [
    ("dr1/level2/2025W35_1A/l2b-v27-2026-230/1/level2_2025W35_1A_0432_4D1_spx_l2b-v27-2026-230.fits", 0.75024),
    ("dr1/level2/2026W12_1A/l2b-v27-2026-235/2/level2_2026W12_1A_0311_3D2_spx_l2b-v27-2026-235.fits", 1.37871),
    # detector edge (y ~ 1972): below the nominal 1.11 um and SIA em_min 1.1033, still inside the table
    ("dr1/level2/2025W34_2B/l2b-v27-2026-229/2/level2_2025W34_2B_0090_4D2_spx_l2b-v27-2026-229.fits", 1.10125),
    ("dr1/level2/2025W33_2C/l2b-v27-2026-228/3/level2_2025W33_2C_0321_1D3_spx_l2b-v27-2026-228.fits", 2.30781),
    ("dr1/level2/2026W11_1A/l2b-v27-2026-232/4/level2_2026W11_1A_0511_3D4_spx_l2b-v27-2026-232.fits", 2.78154),
    ("dr1/level2/2026W12_1A/l2b-v27-2026-235/5/level2_2026W12_1A_0311_3D5_spx_l2b-v27-2026-235.fits", 4.15136),
    ("dr1/level2/2026W12_2A/l2b-v27-2026-235/6/level2_2026W12_2A_0520_3D6_spx_l2b-v27-2026-235.fits", 4.89425),
]


def _get(url: str, range_: str | None = None, tries: int = 4):
    import requests

    for attempt in range(tries):
        try:
            r = requests.get(url, headers={"Range": range_} if range_ else {}, timeout=120)
        except (requests.ConnectionError, requests.Timeout):  # IRSA/S3 hiccups: retry like a 5xx
            if attempt == tries - 1:
                raise
            time.sleep(2**attempt)
            continue
        if r.status_code < 500:
            r.raise_for_status()
            return r.content
        if attempt < tries - 1:
            time.sleep(2**attempt)
    r.raise_for_status()


def _range_image_header(url: str) -> fits.Header:
    """IMAGE header by HTTP Range: it starts after the 2880-byte PRIMARY header."""
    blob = b""
    for size in (40320, 80640):
        blob = _get(url, f"bytes=2880-{2880 + size - 1}")
        cards = [blob[i : i + 80] for i in range(0, len(blob) - 79, 80)]
        end = next((i for i, c in enumerate(cards) if c.startswith(b"END     ")), None)
        if end is not None:
            return fits.Header.fromstring(b"".join(cards[: end + 1]).decode("ascii"))
    raise AssertionError("IMAGE header END card not found")


def _range_wave(url: str) -> fits.BinTableHDU:
    return fits.BinTableHDU.fromstring(_get(url, "bytes=-5760"))  # WCS-WAVE is the last 5760 B of the file


@network_marks
@pytest.mark.parametrize(("key", "expected_um"), LIVE_FRAMES, ids=[k.split("/")[-1][7:26] for k, _ in LIVE_FRAMES])
def test_live_wavelength_at_barnard_per_detector(key, expected_um):
    header, wave = _range_image_header(S3 + key), _range_wave(S3 + key)
    det = int(header["DETECTOR"])
    assert int(wave.header["DETECTOR"]) == det
    x, y = fits_io.celestial_wcs(header).world_to_pixel_values(*BARNARD_2026)
    lam, bw = (float(v) for v in fits_io.wavelength_from_table(wave, header, x, y))
    lam_t, bw_t = fits_io.spectral_wcs(header, wave).pixel_to_world_values(x, y)
    assert (lam, bw) == pytest.approx((float(lam_t), float(bw_t)), abs=1e-9)
    assert lam == pytest.approx(expected_um, abs=2e-5)
    lo, hi = BANDS[det]
    assert lo - 0.03 <= lam <= hi + 0.03  # the per-pixel table overshoots the nominal band by up to ~25 nm
    mjd, src = fits_io.mid_exposure_mjd(header)
    assert src == "MJD-AVG" and (mjd - header["MJD-OBS"]) * 86400 == pytest.approx(57.56, abs=0.05)


@network_marks
def test_live_full_frame_and_ibe_cutout_agree(tmp_path):
    key = LIVE_FRAMES[3][0]  # 2025W33_2C_0321_1 D3, the fixture's file
    header, wave = _range_image_header(S3 + key), _range_wave(S3 + key)
    x, y = fits_io.celestial_wcs(header).world_to_pixel_values(RA, DEC)
    full = tuple(float(v) for v in fits_io.wavelength_from_table(wave, header, x, y))
    assert full == pytest.approx((REF["full"]["wavelength_um"], REF["full"]["bandwidth_um"]), abs=1e-9)
    cut = tmp_path / "cutout.fits"
    cut.write_bytes(_get(f"{IBE}{key}?center={RA},{DEC}&size=5arcmin"))
    with fits.open(cut) as hdul:
        assert hdul["IMAGE"].header["CRPIX1W"] != 1  # IBE shifts the W WCS, the table is untouched
        np.testing.assert_array_equal(hdul[fits_io.WAVE_EXTNAME].data["VALUES"], wave.data["VALUES"])
    assert fits_io.wavelength_at(cut, RA, DEC) == pytest.approx(full, abs=1e-9)
    img = fits_io.read_spherex(cut)
    assert img.mjd == header["MJD-AVG"] and img.wavelength_at(RA, DEC) == pytest.approx(full, abs=1e-9)
