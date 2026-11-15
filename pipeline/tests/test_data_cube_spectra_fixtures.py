"""Real DR1 cube spectra (errante.data.cube.cube_spectrum) saved as fixtures for WS4/WS5 (offline).

``fixtures/ws1/cube_spectra/<id>_ap<k>.json`` is ``CubeSpectrum.to_dict()`` of a LIVE call (2026-11-15 ~02:10
UTC, S3, ``with_nhits=True, with_flags=True, use_cache=False``) at the ``config/fields.toml`` centre of the five
R05 targets and at one empty-sky point (RA 200.0, Dec +40.1: no Gaia DR3 source within 45", nearest AllWISE
W1 = 17.2 at 19", VizieR CfA), with ``aperture_px`` 0 and 2. Strict JSON (NaN -> null). docs/DATA.md §3.3.

What was measured (and is asserted below, so a regenerated fixture that changes it fails loudly):

* every spectrum has 102 planes, 0.753-4.988 um, MJy/sr; planes 50/51 (dichroic) are blank and invalid;
* eps Ind B, WISE 0855 and the empty sky: 100/102 valid (only the blank planes are not);
* the saturated stars lose their core in the coadd (NaN, NHITS = 0): Barnard's Star keeps 10 planes
  (D5/D6, >= 4.29 um), RW Aur loses 15 D4 planes (2.51-3.77 um), R Dra keeps none; the aperture (2 px)
  never rescues them (same valid planes as aperture 0);
* in the coadded FLAGS, every lost core plane has SUR_ERROR and BLOOM but not OVERFLOW; OVERFLOW marks 50
  VALID planes of RW Aur and 2 of Barnard instead (finite, probably underestimated); SOURCE is set at the
  empty sky too (useless as a "there is a star" signal).
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pytest

from errante.data import cube

FIXTURES = Path(__file__).parent / "fixtures" / "ws1" / "cube_spectra"
POINTS = ("barnards-star", "eps-indi-b", "wise-0855", "rw-aurigae", "r-draconis", "empty-sky")
APERTURES = (0, 2)
FILES = [f"{p}_ap{k}.json" for p in POINTS for k in APERTURES]
MAX_BYTES = 60_000

OVERFLOW, SUR_ERROR, SOURCE, BLOOM = 1 << 1, 1 << 2, 1 << 21, 1 << 26
SATURATION_BITS = OVERFLOW | SUR_ERROR | BLOOM

# Keys of CubeSpectrum.to_dict(): what WS4 would serialise (see the contract proposal in DATA.md §3.3).
KEYS = {
    "ra", "dec", "product", "release", "unit", "wavelength_um", "bandwidth_um", "flux", "valid", "core_valid",
    "n_used", "min_used", "nhits", "flags", "detector", "channel", "blank_planes", "tile", "pixel",
    "pixel_center", "pixel_scale_arcsec", "pixel_sr", "aperture_px", "n_pixels", "clipped", "mjd_range",
    "source", "timings", "notes",
}  # fmt: skip
PER_PLANE = ("wavelength_um", "bandwidth_um", "flux", "valid", "core_valid", "n_used", "nhits", "flags",
             "detector", "channel")  # fmt: skip

# Measured live on 2026-11-15 UTC (see the module docstring): valid planes per point, identical for both apertures.
ALL_BUT_BLANK = tuple(k for k in range(cube.N_PLANES) if k not in cube.BLANK_PLANES)
EXPECTED_VALID = {
    "barnards-star": (81, 84, 85, 88, 94, 95, 97, 98, 100, 101),
    "eps-indi-b": ALL_BUT_BLANK,
    "wise-0855": ALL_BUT_BLANK,
    "rw-aurigae": tuple(k for k in ALL_BUT_BLANK if not (52 <= k <= 67 and k != 54)),
    "r-draconis": (),
    "empty-sky": ALL_BUT_BLANK,
}
SATURATED = {"barnards-star", "rw-aurigae", "r-draconis"}
# Valid planes whose coadded FLAGS still carry OVERFLOW (finite flux, but some inputs saturated).
EXPECTED_VALID_OVERFLOW = {"barnards-star": 2, "rw-aurigae": 50}


def _strict(token: str):
    raise ValueError(f"non-strict JSON token {token}")


def load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"), parse_constant=_strict)


def saturation_hint(d: dict) -> dict:
    """The 'saturated' hint rule proposed in DATA.md §3.3, from ``CubeSpectrum.to_dict()`` alone.

    ``core_missing``: non-blank planes whose centre pixel has no data (``core_valid`` False; NaN and
    NHITS = 0 in the coadd). Needs no FLAGS, so it works on the default (cheapest) call. ``overflow_valid``:
    valid planes that still carry OVERFLOW in the coadded FLAGS (only with ``with_flags=True``).
    """
    blank = set(d["blank_planes"])
    core_missing = [k for k, ok in enumerate(d["core_valid"]) if k not in blank and not ok]
    flags = d.get("flags")
    overflow_valid = None
    if flags is not None:
        overflow_valid = [k for k, ok in enumerate(d["valid"]) if ok and flags[k] & OVERFLOW]
    return {
        "saturated": bool(core_missing),
        "core_missing": core_missing,
        "overflow_valid": overflow_valid,
    }


def test_every_fixture_is_there_and_small():
    names = sorted(p.name for p in FIXTURES.glob("*.json"))
    assert names == sorted(FILES)
    for name in names:
        assert (FIXTURES / name).stat().st_size < MAX_BYTES, name


@pytest.mark.parametrize("name", FILES)
def test_fixture_round_trips_through_cube_spectrum(name):
    d = load(name)
    assert set(d) == KEYS
    spec = cube.CubeSpectrum.from_dict(d)
    back = spec.to_dict()
    # 'release' comes from the environment (ERRANTE_CUBE_PREFIX) in to_dict(): compare it to DR1 directly.
    assert d["release"] == cube.DR1_PREFIX
    assert {k: v for k, v in back.items() if k != "release"} == {k: v for k, v in d.items() if k != "release"}


@pytest.mark.parametrize("name", FILES)
def test_fixture_shape_units_and_blank_planes(name):
    point, ap = name.removesuffix(".json").rsplit("_ap", 1)
    d = load(name)
    spec = cube.CubeSpectrum.from_dict(d)
    for key in PER_PLANE:
        assert len(d[key]) == cube.N_PLANES, key
    assert d["unit"] == "MJy/sr"
    assert d["source"] == "s3" and d["product"].startswith("SPHEREx DR1")
    assert d["aperture_px"] == int(ap)
    assert (d["n_pixels"], d["min_used"]) == ((1, 1) if ap == "0" else (13, 7))
    assert d["timings"]["from_cache"] is False

    # Wavelengths: one fixed table for the whole cube, strictly increasing, 0.753-4.988 um.
    wl = np.asarray(d["wavelength_um"])
    assert np.all(np.diff(wl) > 0)
    assert (wl[0], wl[-1]) == (0.753, 4.988)
    assert all(0.0 < b < 0.11 for b in d["bandwidth_um"])
    assert d["detector"] == [k // 17 + 1 for k in range(cube.N_PLANES)]
    assert d["channel"] == [k % 17 + 1 for k in range(cube.N_PLANES)]

    # Blank (dichroic) planes 50 and 51: never valid, no data.
    assert tuple(d["blank_planes"]) == cube.BLANK_PLANES == (50, 51)
    for k in cube.BLANK_PLANES:
        assert d["valid"][k] is False and d["flux"][k] is None and d["nhits"][k] == 0

    # flux is null exactly where valid is False; valid needs the centre pixel (core_valid).
    assert [v is not None for v in d["flux"]] == d["valid"]
    assert all(cv for v, cv in zip(d["valid"], d["core_valid"], strict=True) if v)
    assert all(math.isfinite(v) for v in d["flux"] if v is not None)
    assert np.array_equal(np.isfinite(spec.flux), spec.valid)

    # The pixel is the one the offline HEALPix mapping gives for (ra, dec): no network needed to locate it.
    tp = cube.sky_to_tile_pixel(d["ra"], d["dec"])
    assert (tp.npix, tp.x, tp.y) == (d["tile"]["npix"], d["pixel"]["x"], d["pixel"]["y"])
    assert d["tile"]["key"] == cube.tile_key(tp.npix)
    lo, hi = d["mjd_range"]
    assert 60700 < lo < hi < 61400  # DR1 inputs: 2025-2026


@pytest.mark.parametrize("point", POINTS)
def test_measured_validity_per_point(point):
    expected = EXPECTED_VALID[point]
    for ap in APERTURES:
        d = load(f"{point}_ap{ap}.json")
        valid = tuple(k for k, ok in enumerate(d["valid"]) if ok)
        assert valid == expected, (point, ap)
    if point == "barnards-star":  # what survives saturation is only the longest wavelengths (D5/D6)
        wl = load("barnards-star_ap0.json")["wavelength_um"]
        assert min(wl[k] for k in expected) == pytest.approx(4.294)
        assert {k // 17 + 1 for k in expected} == {5, 6}


@pytest.mark.parametrize("point", POINTS)
def test_saturation_hint_rule(point):
    d = load(f"{point}_ap0.json")
    hint = saturation_hint(d)
    assert hint["saturated"] is (point in SATURATED)
    assert len(hint["overflow_valid"]) == EXPECTED_VALID_OVERFLOW.get(point, 0)
    flags, nhits = d["flags"], d["nhits"]
    for k in hint["core_missing"]:
        # Every lost core plane: no input samples, SUR_ERROR + BLOOM in the coadded FLAGS, and NOT OVERFLOW
        # (in the L2 exposures the same cores carry OVERFLOW: DATA.md §3.2).
        assert nhits[k] == 0 and flags[k] & SUR_ERROR and flags[k] & BLOOM, k
        assert not flags[k] & OVERFLOW, k
    # cube_spectrum already says so in its notes (the same rule, as text for the UI).
    lost_note = [n for n in d["notes"] if "no input samples at the centre pixel" in n]
    assert bool(lost_note) is hint["saturated"]
    if lost_note:
        assert lost_note[0].startswith(f"{len(hint['core_missing'])} planes")
    # The visualization caveat is always there.
    assert d["notes"][0] == cube.NOTE_VISUALIZATION


def test_source_bit_is_not_a_star_detector():
    """Coadded FLAGS OR the inputs: SOURCE is set at the empty-sky point in every non-blank plane."""
    d = load("empty-sky_ap0.json")
    assert sum(1 for f in d["flags"] if f & SOURCE) == 100
    assert not any(f & SATURATION_BITS for f in d["flags"])
