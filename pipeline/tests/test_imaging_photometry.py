"""WS2 forced photometry: correct flux in mJy on native pixels, honest flags, spectrum assembly."""

import json
import math
from pathlib import Path

import numpy as np
import pytest
from test_imaging_reproject import DEC0, PIXEL_DEG, RA0, fake_image

from errante.cli import main
from errante.data import cutouts, fits_io, irsa
from errante.imaging import photometry
from errante.imaging.flags import FLAG_BITS
from errante.imaging.photometry import (
    aperture_weights,
    measure,
    pixel_solid_angle_sr,
    propagate,
    spectrum_at,
    to_spectrum_points,
)
from errante.models import FrameRef, SearchResult, SkyCoord

TARGET_AMP = 50.0  # MJy/sr peak; sigma 1 px -> total 2*pi*50 MJy/sr*px
FIELD = [  # bright, isolated field stars (offsets in px) for the curve of growth
    (-28.3, -18.6, 80.0), (27.6, -17.2, 70.0), (-26.8, 19.3, 90.0), (28.9, 18.4, 60.0), (0.4, -24.7, 75.0),
    (-0.3, 23.8, 85.0),
]  # fmt: skip


def stars(target=TARGET_AMP):
    out = [(RA0, DEC0, target)] if target else []
    for dx, dy, amp in FIELD:
        out.append((RA0 - dx * PIXEL_DEG / math.cos(math.radians(DEC0)), DEC0 + dy * PIXEL_DEG, amp))
    return tuple(out)


def image(target=TARGET_AMP, **kw):
    img = fake_image(stars=stars(target), shape=(90, 110), rotation_deg=20, **kw)
    img.header["OMEGA_MEDIAN"] = 37.9
    return img


def mjy(total_mjy_sr_px, header):
    return total_mjy_sr_px * pixel_solid_angle_sr(header) * 1e9


def test_aperture_weights_cover_the_circle_area():
    yy, xx = np.mgrid[0:21, 0:21]
    w = aperture_weights(xx, yy, 10.3, 9.6, 2.0, n=9)
    assert w.sum() == pytest.approx(math.pi * 4, rel=0.01)
    assert w.max() == 1.0 and w.min() == 0.0


def test_solid_angle_uses_omega_median_or_the_nominal_pixel():
    from astropy.io import fits

    h = fits.Header()
    assert pixel_solid_angle_sr(h) == pytest.approx((6.15 * math.pi / 648000) ** 2)
    h["OMEGA_MEDIAN"] = 37.9
    assert pixel_solid_angle_sr(h) == pytest.approx(37.9 * (math.pi / 648000) ** 2)


def test_forced_flux_recovers_the_total_flux_after_aperture_correction():
    img = image()
    img.wavelength_at = lambda ra, dec: (1.25, 0.03)
    p = measure(img, RA0, DEC0)
    truth = mjy(2 * math.pi * TARGET_AMP * 1.0**2, img.header)
    assert p.aperture_correction == pytest.approx(1 / (1 - math.exp(-2.0)), rel=0.03)  # r=2 px, sigma=1 px
    assert p.flux_mjy == pytest.approx(truth, rel=0.03)
    assert p.flux_err_mjy > 0 and p.usable
    assert p.sky_mjy_sr == pytest.approx(0.0, abs=0.01)  # zodi removed, local sky ~ 0


def test_empty_position_gives_zero_flux_within_errors():
    p = measure(image(target=0.0), RA0, DEC0)
    assert abs(p.flux_mjy) < 3 * p.flux_err_mjy


def test_saturated_and_edge_points_are_flagged_and_not_usable():
    img = image()
    x, y = (int(round(float(v))) for v in img.wcs.all_world2pix(RA0, DEC0, 0))
    img.data[y, x] = np.nan
    img.flags[y, x] = 1 << FLAG_BITS["OVERFLOW"]
    sat = measure(img, RA0, DEC0)
    assert "saturated" in sat.flags and not sat.usable
    ny, nx = img.data.shape
    ra_e, dec_e = img.wcs.all_pix2world(1.0, ny / 2, 0)
    edge = measure(img, float(ra_e), float(dec_e))
    assert "edge" in edge.flags and not edge.usable
    assert measure(img, RA0 + 1.0, DEC0) is None  # off this file


def test_wavelength_comes_from_the_file_at_that_position():
    img = image()
    asked = []
    img.wavelength_at = lambda ra, dec: asked.append((ra, dec)) or (1.912, 0.047)
    p = measure(img, RA0, DEC0)
    assert (p.wavelength_um, p.bandwidth_um) == (1.912, 0.047) and asked == [(RA0, DEC0)]
    img.wavelength_at = lambda ra, dec: None
    assert "no_wavelength" in measure(img, RA0, DEC0).flags


def test_proper_motion_propagation():
    ra, dec = propagate(10.0, 0.0, (1000.0, -1000.0, 51544.5), 51544.5 + 365.25)  # 1"/yr each way
    assert ra == pytest.approx(10.0 + 1 / 3600) and dec == pytest.approx(-1 / 3600)
    assert propagate(10.0, 0.0, None, 60000.0) == (10.0, 0.0)


def test_spectrum_at_assembles_sorted_points_and_reports_failures(monkeypatch):
    refs = [
        FrameRef(obs_id="A", detector=1, mjd=60900.0, release="dr1"),
        FrameRef(obs_id="A", detector=1, mjd=60900.0, release="qr3"),  # duplicate exposure
        FrameRef(obs_id="B", detector=4, mjd=60900.0, release="dr1"),
        FrameRef(obs_id="C", detector=2, mjd=61100.0, release="dr1"),
    ]
    monkeypatch.setattr(irsa, "search_frames", lambda *a, **kw: SearchResult(
        center=SkyCoord(ra=RA0, dec=DEC0), radius_deg=0, frames=refs))  # fmt: skip

    def fetch(frames, ra, dec, size):
        return [None if f.obs_id == "C" else Path(f"{f.obs_id}{f.detector}.fits") for f in frames], [
            (f, "boom") for f in frames if f.obs_id == "C"
        ]

    monkeypatch.setattr(cutouts, "fetch_frames_report", fetch)
    waves = {"A1": 0.95, "B4": 3.1}

    def read(path):
        img = image()
        lam = waves[Path(path).stem]
        img.wavelength_at = lambda ra, dec, lam=lam: (lam, 0.03)
        return img

    monkeypatch.setattr(fits_io, "read_spherex", read)
    res = spectrum_at(RA0, DEC0)
    assert [p.frame_id for p in res.points] == ["AD1", "BD4"]  # sorted by wavelength, duplicate dropped
    assert res.points[0].release == "dr1"
    assert res.failures == [("CD2", "boom")]
    pts = to_spectrum_points(res)
    assert [pt.wavelength_um for pt in pts] == [0.95, 3.1] and pts[0].flux_mjy > 0


def test_frames_without_field_stars_use_the_detector_fit(monkeypatch):
    refs = [FrameRef(obs_id=o, detector=3, mjd=60900.0 + i, release="dr1") for i, o in enumerate("PQ")]
    monkeypatch.setattr(irsa, "search_frames", lambda *a, **kw: SearchResult(
        center=SkyCoord(ra=RA0, dec=DEC0), radius_deg=0, frames=refs))  # fmt: skip
    monkeypatch.setattr(
        cutouts, "fetch_frames_report", lambda frames, *a: ([Path(f"{f.obs_id}.fits") for f in frames], [])
    )

    def read(path):
        if Path(path).stem == "P":
            img = image()
        else:
            img = fake_image(stars=((RA0, DEC0, TARGET_AMP),), shape=(90, 110), rotation_deg=20)  # no field stars
            img.header["OMEGA_MEDIAN"] = 37.9
        img.wavelength_at = lambda ra, dec: (2.0, 0.04)
        return img

    monkeypatch.setattr(fits_io, "read_spherex", read)
    p, q = sorted(spectrum_at(RA0, DEC0).points, key=lambda pt: pt.frame_id)
    assert p.aperture_correction is not None and "no_aperture_correction" not in q.flags
    assert q.aperture_correction == pytest.approx(p.aperture_correction)  # pooled per detector
    assert q.flux_mjy == pytest.approx(p.flux_mjy, rel=0.03)


def test_correction_fit_follows_wavelength_and_falls_back_to_the_median():
    from errante.imaging.photometry import fit_corrections

    lam = np.linspace(2.4, 3.8, 40)
    fits = fit_corrections({4: [(x, 1.05 + 0.1 * x) for x in lam], 1: [(0.9, 1.1), (0.95, 1.12), (1.0, 1.08)]})
    a, b = fits[4]
    assert a == pytest.approx(1.05, abs=1e-6) and b == pytest.approx(0.1, abs=1e-6)
    assert fits[1] == (pytest.approx(1.1), 0.0)
    assert 2 not in fit_corrections({2: [(1.2, 1.1)]})  # too few stars


def test_spectral_outliers_are_flagged_within_a_season_only():
    from errante.imaging.photometry import ForcedFlux, flag_spectral_outliers

    def pt(i, lam, flux, mjd):
        return ForcedFlux(f"F{i}", f"O{i}", 2, mjd, "dr1", RA0, DEC0, 5.0, 5.0, lam, 0.03, flux, 0.1, 0.0, 1.1, ())

    season1 = [pt(i, 1.30 + 0.002 * i, 10.0, 60900.0 + i) for i in range(6)]
    spike = pt(9, 1.305, 40.0, 60903.5)  # cosmic ray
    season2 = [pt(20 + i, 1.30 + 0.002 * i, 20.0, 61100.0 + i) for i in range(4)]  # the star got brighter
    out = flag_spectral_outliers([*season1, spike, *season2])
    assert {p.frame_id for p in out if "spectral_outlier" in p.flags} == {"F9"}


def test_cli_spectrum_writes_strict_json(monkeypatch, tmp_path):
    from errante.imaging.photometry import ForcedFlux, SpectrumResult

    pt = ForcedFlux("AD1", "A", 1, 60900.0, "dr1", RA0, DEC0, 10.0, 10.0, 0.95, 0.03, 12.5, 0.4, 0.0, 1.15, ())
    monkeypatch.setattr(photometry, "spectrum_at", lambda *a, **kw: SpectrumResult(RA0, DEC0, [pt], [], ["1 exposure"]))
    out = tmp_path / "s.json"
    assert main(["spectrum", "--ra", str(RA0), "--dec", str(DEC0), "--pm-ra", "100", "--out", str(out)]) == 0
    doc = json.loads(out.read_text(), parse_constant=lambda t: 1 / 0)
    assert doc["points"][0]["flux_mjy"] == 12.5 and doc["proper_motion"]["pm_ra_masyr"] == 100


def test_fast_movers_are_searched_and_cut_out_where_they_are_now(monkeypatch):
    """eps Indi B moves ~4.7"/yr: its J2000 position is ~2' off in 2025-2026."""
    calls = {}

    def search(ra, dec, **kw):
        calls["search"] = (ra, dec)
        return SearchResult(center=SkyCoord(ra=ra, dec=dec), radius_deg=0, frames=[
            FrameRef(obs_id="A", detector=1, mjd=61000.0, release="dr1")])  # fmt: skip

    def fetch(frames, ra, dec, size):
        calls["fetch"] = (ra, dec)
        return [None for _ in frames], [(f, "test") for f in frames]

    monkeypatch.setattr(irsa, "search_frames", search)
    monkeypatch.setattr(cutouts, "fetch_frames_report", fetch)
    pm = (3981.977, -2466.832, 51544.5)
    spectrum_at(331.04414659, -56.7828442, pm=pm)
    expected = propagate(331.04414659, -56.7828442, pm, 61000.0)
    assert calls["search"] == pytest.approx(expected) and calls["fetch"] == pytest.approx(expected)
