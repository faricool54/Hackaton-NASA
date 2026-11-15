"""Real DR1 cube spectra (errante.data.cube.cube_spectrum) saved as fixtures for WS4/WS5 (offline).

``fixtures/ws1/cube_spectra/<id>_ap<k>.json`` is ``CubeSpectrum.to_dict()`` of a LIVE call (S3,
``with_nhits=True, with_flags=True, use_cache=False``), with ``aperture_px`` 0 and 2. Strict JSON (NaN -> null).
docs/DATA.md §3.3. Points:

* 2026-11-15 ~02:10 UTC: the ``config/fields.toml`` centre of the five R05 targets and one empty-sky point
  (RA 200.0, Dec +40.1: no Gaia DR3 source within 45", nearest AllWISE W1 = 17.2 at 19", VizieR CfA);
* 2026-11-15 ~02:40 UTC: ``gc-coverage-hole`` (RA 268.09113, Dec -28.71602, ~1.5 deg from the Galactic Centre),
  inside a NaN region of the coadd: 33,014 and 11,312 px (bbox up to ~46'x67') in planes 8 and 34, the two
  read in full, where a saturated star's lost core spans 1-28 px (DATA.md §3.3 d). Its note is the current
  wording of ``cube_spectrum`` ("either the core of a saturated bright star ... or a gap in the coadd's
  coverage"); the six earlier points were recorded with the previous wording ("typical of a saturated bright
  star").

What was measured (and is asserted below, so a regenerated fixture that changes it fails loudly):

* every spectrum has 102 planes, 0.753-4.988 um, MJy/sr; planes 50/51 (dichroic) are blank and invalid;
* eps Ind B, WISE 0855 and the empty sky: 100/102 valid (only the blank planes are not);
* the saturated stars lose their core in the coadd (NaN, NHITS = 0): Barnard's Star keeps 10 planes
  (D5/D6, >= 4.29 um), RW Aur loses 15 D4 planes (2.51-3.77 um), R Dra keeps none; the aperture (2 px)
  never rescues them (same valid planes as aperture 0);
* in the coadded FLAGS, every lost core plane of a saturated star has SUR_ERROR and BLOOM but not OVERFLOW;
  OVERFLOW marks 50 VALID planes of RW Aur and 2 of Barnard instead (finite, probably underestimated);
  SOURCE is set at the empty sky too (useless as a "there is a star" signal);
* the coverage hole ALSO loses its core (32 planes of D1-D3, NHITS = 0), so "core missing" alone does not
  mean "saturated": there the lost planes carry CROSSTALK (32) and PERSIST (28), never SUR_ERROR, and BLOOM
  in one (plane 30). Hence the hint rule below needs FLAGS and BOTH SUR_ERROR and BLOOM.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pytest

from errante.data import cube

FIXTURES = Path(__file__).parent / "fixtures" / "ws1" / "cube_spectra"
POINTS = ("barnards-star", "eps-indi-b", "wise-0855", "rw-aurigae", "r-draconis", "empty-sky", "gc-coverage-hole")
APERTURES = (0, 2)
FILES = [f"{p}_ap{k}.json" for p in POINTS for k in APERTURES]
MAX_BYTES = 60_000

OVERFLOW, SUR_ERROR, PERSIST, CROSSTALK, SOURCE, BLOOM = 1 << 1, 1 << 2, 1 << 17, 1 << 20, 1 << 21, 1 << 26
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

# Measured live on 2026-11-15 UTC (see the module docstring): valid planes per point with aperture 0.
ALL_BUT_BLANK = tuple(k for k in range(cube.N_PLANES) if k not in cube.BLANK_PLANES)
GC_LOST = (*range(8, 17), 24, 26, 28, *range(30, 50))  # 32 planes of D1-D3, 0.910-2.345 um
EXPECTED_VALID = {
    "barnards-star": (81, 84, 85, 88, 94, 95, 97, 98, 100, 101),
    "eps-indi-b": ALL_BUT_BLANK,
    "wise-0855": ALL_BUT_BLANK,
    "rw-aurigae": tuple(k for k in ALL_BUT_BLANK if not (52 <= k <= 67 and k != 54)),
    "r-draconis": (),
    "empty-sky": ALL_BUT_BLANK,
    "gc-coverage-hole": tuple(k for k in ALL_BUT_BLANK if k not in GC_LOST),
}
# Planes valid with aperture 0 but not with aperture 2 (fewer than 7 of the 13 pixels have data). Only at the
# edge of the coverage hole; at the saturated stars the aperture changes nothing.
THIN_AT_AP2 = {"gc-coverage-hole": (7, 29)}
SATURATED = {"barnards-star", "rw-aurigae", "r-draconis"}
# Valid planes whose coadded FLAGS still carry OVERFLOW (finite flux, but some inputs saturated).
EXPECTED_VALID_OVERFLOW = {"barnards-star": 2, "rw-aurigae": 50, "gc-coverage-hole": 5}


def _strict(token: str):
    raise ValueError(f"non-strict JSON token {token}")


def load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"), parse_constant=_strict)


def saturation_hint(d: dict) -> dict:
    """The 'saturated' hint rule proposed in DATA.md §3.3 e), from ``CubeSpectrum.to_dict()`` alone.

    ``core_missing``: non-blank planes whose centre pixel has no data (``core_valid`` False; NaN and
    NHITS = 0 in the coadd). Needs no FLAGS, so it works on the default (cheapest) call, but it means
    "saturated core OR no coverage" (the coverage-hole fixture), not "saturated".

    ``core_saturated``: the lost planes whose coadded FLAGS carry BOTH SUR_ERROR and BLOOM, as every lost
    plane of the three saturated targets does. ``saturated`` is ``bool(core_saturated)`` and needs
    ``with_flags=True``; without FLAGS it is ``None`` (unknown), never False. ``overflow_valid``: valid planes
    that still carry OVERFLOW in the coadded FLAGS (also only with FLAGS).
    """
    blank = set(d["blank_planes"])
    core_missing = [k for k, ok in enumerate(d["core_valid"]) if k not in blank and not ok]
    flags = d.get("flags")
    if flags is None:
        return {"saturated": None, "core_missing": core_missing, "core_saturated": None, "overflow_valid": None}
    core_saturated = [k for k in core_missing if flags[k] & SUR_ERROR and flags[k] & BLOOM]
    overflow_valid = [k for k, ok in enumerate(d["valid"]) if ok and flags[k] & OVERFLOW]
    return {
        "saturated": bool(core_saturated),
        "core_missing": core_missing,
        "core_saturated": core_saturated,
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
    thin = THIN_AT_AP2.get(point, ())
    for ap in APERTURES:
        d = load(f"{point}_ap{ap}.json")
        valid = tuple(k for k, ok in enumerate(d["valid"]) if ok)
        expected = EXPECTED_VALID[point] if ap == 0 else tuple(k for k in EXPECTED_VALID[point] if k not in thin)
        assert valid == expected, (point, ap)
    if point == "barnards-star":  # what survives saturation is only the longest wavelengths (D5/D6)
        wl = load("barnards-star_ap0.json")["wavelength_um"]
        assert min(wl[k] for k in EXPECTED_VALID[point]) == pytest.approx(4.294)
        assert {k // 17 + 1 for k in EXPECTED_VALID[point]} == {5, 6}


@pytest.mark.parametrize("point", POINTS)
def test_saturation_hint_rule(point):
    d = load(f"{point}_ap0.json")
    hint = saturation_hint(d)
    assert hint["saturated"] is (point in SATURATED)
    assert len(hint["overflow_valid"]) == EXPECTED_VALID_OVERFLOW.get(point, 0)
    flags, nhits = d["flags"], d["nhits"]
    if point in SATURATED:
        # Every lost core plane: no input samples, SUR_ERROR + BLOOM in the coadded FLAGS, and NOT OVERFLOW
        # (in the L2 exposures the same cores carry OVERFLOW: DATA.md §3.2).
        assert hint["core_saturated"] == hint["core_missing"]
        for k in hint["core_missing"]:
            assert nhits[k] == 0 and flags[k] & SUR_ERROR and flags[k] & BLOOM, k
            assert not flags[k] & OVERFLOW, k
    else:
        assert hint["core_saturated"] == []
    # cube_spectrum says it in its notes whenever the core is lost, saturated or not (the note names both causes).
    lost_note = [n for n in d["notes"] if "no input samples at the centre pixel" in n]
    assert bool(lost_note) is bool(hint["core_missing"])
    if lost_note:
        assert lost_note[0].startswith(f"{len(hint['core_missing'])} planes")
    # The visualization caveat is always there.
    assert d["notes"][0] == cube.NOTE_VISUALIZATION


def test_coverage_hole_loses_the_core_without_saturation_flags():
    """Regression: 'core missing' alone (the first proposed rule) called this coverage gap a saturated star."""
    for ap in APERTURES:
        d = load(f"gc-coverage-hole_ap{ap}.json")
        hint = saturation_hint(d)
        assert tuple(hint["core_missing"]) == GC_LOST
        assert hint["saturated"] is False
        lost_flags = [d["flags"][k] for k in GC_LOST]
        assert all(d["nhits"][k] == 0 for k in GC_LOST)
        assert {d["detector"][k] for k in GC_LOST} == {1, 2, 3}
        assert not any(f & SUR_ERROR for f in lost_flags) and not any(f & OVERFLOW for f in lost_flags)
        assert all(f & CROSSTALK for f in lost_flags) and sum(1 for f in lost_flags if f & PERSIST) == 28
        # BLOOM alone shows up on a lost plane (30): "SUR_ERROR or BLOOM" would still misfire, hence "and".
        assert [k for k in GC_LOST if d["flags"][k] & BLOOM] == [30]
        # The current note names the coverage gap too.
        assert "gap in the coadd's coverage" in d["notes"][1]


@pytest.mark.parametrize("point", POINTS)
def test_saturation_hint_without_flags_is_unknown(point):
    """The default call (no FLAGS) still counts the lost planes, but cannot say why: saturated is None."""
    d = load(f"{point}_ap0.json")
    with_flags = saturation_hint(d)
    hint = saturation_hint({**d, "flags": None})
    assert hint["saturated"] is None and hint["core_saturated"] is None and hint["overflow_valid"] is None
    assert hint["core_missing"] == with_flags["core_missing"]


def test_source_bit_is_not_a_star_detector():
    """Coadded FLAGS OR the inputs: SOURCE is set at the empty-sky point in every non-blank plane."""
    d = load("empty-sky_ap0.json")
    assert sum(1 for f in d["flags"] if f & SOURCE) == 100
    assert not any(f & SATURATION_BITS for f in d["flags"])
