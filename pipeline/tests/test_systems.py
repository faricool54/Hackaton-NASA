"""3D system models (WS7): physics helpers, catalog integrity and catalog sources."""

import os
import re

import pytest

from errante.models import Appearance, Body, Orbit, Provenance, SkyCoord, SystemModel
from errante.products import ProductStore
from errante.systems import sources
from errante.systems.build import validate_hierarchy, write_systems
from errante.systems.catalog import curated_systems, demo_systems, kepler_a_au, kepler_period_days


def test_kepler_earth_and_roundtrip():
    assert kepler_period_days(1.0, 1.0) == pytest.approx(365.25)
    assert kepler_a_au(kepler_period_days(5.2, 1.0), 1.0) == pytest.approx(5.2)


@pytest.mark.parametrize("system", demo_systems(), ids=lambda s: s.id)
def test_catalog_hierarchies_are_valid(system):
    validate_hierarchy(system)


def test_verified_facts_cite_a_source_and_estimates_stay_unverified():
    """AGENTS.md rule 5: `verified` means checked against the cited source (WS7-2)."""
    for system in curated_systems():
        assert not system.provenance.synthetic
        for body in system.bodies:
            for fact in body.facts:
                where = f"{system.id}/{body.id}/{fact.label}"
                if fact.verified:
                    assert fact.source and fact.source.strip(), f"{where}: verified without a source"
                    assert "literature" != fact.source.strip().lower(), f"{where}: cite the paper, not 'literature'"
                if "illustrative" in fact.label.lower() or "drawing value" in (fact.source or ""):
                    assert not fact.verified, f"{where}: an illustrative value cannot be verified"


def test_real_systems_do_not_claim_to_be_hand_typed_or_synthetic():
    for system in curated_systems():
        assert "synthetic" not in system.representation_note.lower()
        assert not any("typed by hand" in note for note in system.provenance.notes), system.id


def test_synthetic_system_is_labelled():
    synthetic = [s for s in demo_systems() if s.provenance.synthetic]
    assert synthetic and all("synthetic" in s.tags for s in synthetic)
    assert all("SYNTHETIC" in s.representation_note for s in synthetic)


def test_committed_demo_systems_match_the_catalog():
    """data/demo/systems is generated: regenerate it (python scripts/dev.py demo) after editing catalog.py."""
    from errante import settings

    on_disk = {p.stem for p in (settings.DEMO_DIR / "systems").glob("*.json")}
    assert on_disk == {s.id for s in demo_systems()}
    store = ProductStore(settings.DEMO_DIR)
    for system in demo_systems():
        committed = store.read_system(system.id)
        assert committed.model_dump(exclude={"provenance"}) == system.model_dump(exclude={"provenance"}), system.id


# --- M5: Barnard b-e at their published phase (Basant et al. 2025, Table 3) ----

# Independent copy of Table 3 (t0 in BJD, P in days, 1-sigma; asymmetric t0 errors: the larger side).
BASANT_T3 = {
    "barnard-b": (2460243.38, 0.09, 3.1542, 0.0004),
    "barnard-c": (2460242.92, 0.10, 4.1244, 0.0006),
    "barnard-d": (2460243.70, 0.08, 2.3402, 0.0003),
    "barnard-e": (2460245.30, 0.37, 6.7392, 0.0028),
}


def _barnard_planets():
    return {b.id: b for b in _system_by_id("barnards-star").bodies if b.orbit}


def _ephemeris_mjd(pid):
    t0, s_t0, period, s_p = BASANT_T3[pid]
    return t0 - 2400000.5, s_t0, period, s_p


def test_barnard_planets_are_dated_at_conjunction():
    """epoch_mjd = t0(BJD) - 2400000.5 and M = 270 deg (planet toward Earth in the WS7 frame)."""
    from errante.systems.catalog import CONJUNCTION_MEAN_ANOMALY_DEG

    planets = _barnard_planets()
    assert set(planets) == set(BASANT_T3)
    assert CONJUNCTION_MEAN_ANOMALY_DEG == 270.0
    for pid, (t0, _, period, _) in BASANT_T3.items():
        orbit = planets[pid].orbit
        assert orbit.epoch_mjd == pytest.approx(t0 - 2400000.5, abs=1e-6), pid
        assert orbit.mean_anomaly_deg == 270.0
        assert orbit.period_days == period
        # The 'toward Earth' convention needs a circle in the reference plane (i = Omega = omega = 0).
        shape = (orbit.eccentricity, orbit.inclination_deg, orbit.ascending_node_deg, orbit.arg_periapsis_deg)
        assert shape == (0, 0, 0, 0)
        assert "inferior conjunction" in orbit.note and "periastron" in orbit.note
        t0_fact = next(f for f in planets[pid].facts if f.label == "Reference time t0")
        assert t0_fact.verified and t0_fact.unit == "BJD" and t0_fact.value.startswith(f"{t0:.2f} ")
        assert "Table 3" in t0_fact.source and "value only" in t0_fact.source


def test_basant_b_ephemeris_reaches_the_gonzalez_hernandez_2024_conjunction():
    """GH24 Table 6: Tc = BJD 2460139.204 +/- 0.149 (P 3.1533 d). Basant's b, 33 cycles earlier, must agree."""
    t0, _, period, _ = BASANT_T3["barnard-b"]
    cycles = (2460139.204 - t0) / period
    assert round(cycles) == -33
    assert abs(cycles - round(cycles)) < 0.05  # 0.028 cycles; a periastron reading would be ~0.23 off
    orbit = _barnard_planets()["barnard-b"].orbit  # the same with the catalog's own epoch
    cycles = ((2460139.204 - 2400000.5) - orbit.epoch_mjd) / orbit.period_days
    assert abs(cycles - round(cycles)) < 0.05


def test_barnard_phase_spread_matches_the_orbit_notes():
    """sigma_phi = sqrt(sigma_t0^2 + N^2 sigma_P^2) / P (M5): b 13.0 deg at DR1 start, 18.6 deg at QR3 end."""
    from errante.systems.catalog import phase_sigma_deg

    assert phase_sigma_deg(60789.75, *_ephemeris_mjd("barnard-b")) == pytest.approx(13.0, abs=0.05)
    assert phase_sigma_deg(61318.0, *_ephemeris_mjd("barnard-b")) == pytest.approx(18.6, abs=0.06)
    planets = _barnard_planets()
    for pid in BASANT_T3:
        for mjd, iso in ((60789.75, "2025-04-24"), (61318.0, "2026-10-05")):
            deg = phase_sigma_deg(mjd, *_ephemeris_mjd(pid))
            assert f"±{deg:.0f}° on {iso}" in planets[pid].orbit.note, pid
    # The spread widens with time, and e (largest t0 error) is the least well pinned down.
    assert phase_sigma_deg(61318.0, *_ephemeris_mjd("barnard-b")) > phase_sigma_deg(
        60789.75, *_ephemeris_mjd("barnard-b")
    )
    assert phase_sigma_deg(61318.0, *_ephemeris_mjd("barnard-e")) > phase_sigma_deg(
        61318.0, *_ephemeris_mjd("barnard-b")
    )


# --- R Dra: two clocks (free-running sine, Dataset time on the VSX ephemeris) ----


def test_r_draconis_notes_describe_both_clocks():
    """The old 'phases are arbitrary' and 'sine wave' notes contradicted Dataset time, which dates R Dra's phase."""
    from errante import settings
    from errante.systems.catalog import PHASE_NOTE, RDRA_GCVS_PERIOD_DAYS, RDRA_PULSATION_NOTE

    rdra = _system_by_id("r-draconis")
    assert PHASE_NOTE not in rdra.provenance.notes
    assert rdra.provenance.notes.count(RDRA_PULSATION_NOTE) == 1
    assert not any("sine wave" in n and "Dataset time" not in n for n in rdra.provenance.notes)
    assert rdra.bodies[0].variability.period_days == RDRA_GCVS_PERIOD_DAYS
    for text in (
        f"GCVS period ({RDRA_GCVS_PERIOD_DAYS} d)",
        "arbitrary phase",
        "Dataset time",
        "HJD 2457370.00, P = 246.12 d",
        "rises in 45 % of the cycle",
        "frontend/src/three/ephemerides.ts",
        "not a measured or SPHEREx light curve",
        "in phase with the light for display only",
    ):
        assert text in RDRA_PULSATION_NOTE, text
    # The shipped JSON carries the new note (regenerate data/demo after editing catalog.py).
    committed = ProductStore(settings.DEMO_DIR).read_system("r-draconis")
    assert RDRA_PULSATION_NOTE in committed.provenance.notes
    assert PHASE_NOTE not in committed.provenance.notes
    # Systems whose phases are all arbitrary keep the generic note; Barnard's planets are dated (M5).
    assert PHASE_NOTE in _system_by_id("epsilon-indi").provenance.notes
    assert PHASE_NOTE in _system_by_id("rw-aurigae").provenance.notes
    assert PHASE_NOTE not in _system_by_id("barnards-star").provenance.notes


def test_r_draconis_note_matches_the_frontend_ephemeris_table():
    """Dataset time reads MIRA_EPHEMERIDES in frontend/src/three/ephemerides.ts: the note must quote the same values."""
    from errante import settings
    from errante.systems.catalog import RDRA_VSX_EPOCH_HJD, RDRA_VSX_PERIOD_DAYS, RDRA_VSX_RISE_PERCENT

    table = settings.REPO_ROOT / "frontend" / "src" / "three" / "ephemerides.ts"
    if not table.exists():
        pytest.skip("frontend sources not present")
    src = table.read_text(encoding="utf-8")
    block = src[src.index("MIRA_EPHEMERIDES") :]
    m = re.search(
        r"bodyId: 'r-draconis',\s*epochHjd: ([\d.]+),\s*periodDays: ([\d.]+),\s*riseFraction: ([\d.]+),", block
    )
    assert m, "R Dra entry of MIRA_EPHEMERIDES not found"
    assert float(m[1]) == RDRA_VSX_EPOCH_HJD
    assert float(m[2]) == RDRA_VSX_PERIOD_DAYS
    assert round(float(m[3]) * 100) == RDRA_VSX_RISE_PERCENT


def _system(bodies):
    prov = Provenance(pipeline_version="t", built_at="2026-01-01T00:00:00Z", synthetic=True)
    return SystemModel(id="t", name="t", center=SkyCoord(ra=0, dec=0), bodies=bodies, provenance=prov)


def _body(bid, parent=None):
    orbit = Orbit(parent=parent, semi_major_axis_au=1, period_days=365) if parent else None
    return Body(id=bid, name=bid, kind="planet", orbit=orbit, appearance=Appearance(model="rocky"))


def test_hierarchy_rejects_unknown_parent_and_cycles():
    with pytest.raises(ValueError, match="unknown parent"):
        validate_hierarchy(_system([_body("a"), _body("b", "zzz")]))
    # the orphan listed after a body that walks through it must still give the clear error, not KeyError
    with pytest.raises(ValueError, match="unknown parent 'zzz'"):
        validate_hierarchy(_system([_body("root"), _body("moon", "x"), _body("x", "zzz")]))
    with pytest.raises(ValueError, match="cycle"):
        validate_hierarchy(_system([_body("root"), _body("a", "b"), _body("b", "a")]))


def test_store_roundtrip_and_manifest(tmp_path):
    store = ProductStore(tmp_path)
    write_systems(store, demo_systems())
    manifest = store.rebuild_manifest()
    assert {s.id for s in manifest.systems} == {s.id for s in demo_systems()}
    assert manifest.synthetic  # the demo-ecliptic-orbits system is synthetic
    assert store.read_system("barnards-star").bodies[0].kind == "star"


# --- sources: offline parsing ---------------------------------------------------


def test_adql_string_literals_are_escaped():
    assert sources.adql_str("Barnard's star") == "'Barnard''s star'"


def test_tap_rows_parses_both_answer_shapes(monkeypatch):
    answers = {
        sources.EXOPLANET_ARCHIVE_TAP: [{"pl_name": "x b", "pl_orbper": 1.5}],
        sources.SIMBAD_TAP: {"metadata": [{"name": "main_id"}, {"name": "plx_value"}], "data": [["* x", 12.5]]},
    }
    monkeypatch.setattr(sources, "_get_json", lambda url, params: (answers[url], url + "?q"))
    rows, url = sources.tap_rows(sources.EXOPLANET_ARCHIVE_TAP, "select 1")
    assert rows == [{"pl_name": "x b", "pl_orbper": 1.5}] and url.endswith("?q")
    rows, _ = sources.tap_rows(sources.SIMBAD_TAP, "select 1")
    assert rows == [{"main_id": "* x", "plx_value": 12.5}]


def test_archive_reference_links_become_text_and_url():
    raw = {
        "pl_orbper_reflink": "<a refstr=X href=https://ui.adsabs.harvard.edu/abs/2025X target=ref>Gonz&aacute;lez 2024</a>"
    }
    clean = sources._clean_refs(raw)
    assert clean["pl_orbper_reflink"] == "González 2024"
    assert clean["pl_orbper_reflink_url"] == "https://ui.adsabs.harvard.edu/abs/2025X"


# --- sources: live archives (ERRANTE_NETWORK_TESTS=1 pytest -m network) --------

live = pytest.mark.skipif(os.environ.get("ERRANTE_NETWORK_TESTS") != "1", reason="set ERRANTE_NETWORK_TESTS=1")


@pytest.mark.network
@live
def test_exoplanet_archive_knows_barnards_planets():
    system = sources.exoplanet_archive_system("Barnard's star")
    assert [p["pl_letter"] for p in system["planets"]] == ["d", "b", "c", "e"]  # ordered by period
    assert system["source"].startswith(sources.EXOPLANET_ARCHIVE_TAP)


@pytest.mark.network
@live
def test_simbad_and_gaia_answer_for_barnards_star():
    star = sources.simbad_star("GJ 699")
    assert star["main_id"] == "NAME Barnard's star" and star["parallax_mas"] > 540
    gaia = sources.gaia_dr3_source(4472832130942575872)
    assert gaia["ref_epoch"] == 2016.0 and gaia["parallax"] == pytest.approx(546.98, abs=0.1)


def _system_by_id(system_id):
    return next(s for s in curated_systems() if s.id == system_id)


@pytest.mark.network
@live
def test_catalog_planets_match_the_exoplanet_archive():
    """Re-run the WS7-2 check: periods, minimum masses and orbits as in pscomppars."""
    from errante.systems.catalog import M_EARTH_KG, M_JUP_KG

    archive = {p["pl_name"]: p for p in sources.exoplanet_archive_system("Barnard's star")["planets"]}
    for body in _system_by_id("barnards-star").bodies[1:]:
        row = archive[body.name]
        assert body.orbit.period_days == pytest.approx(row["pl_orbper"], rel=1e-4)
        assert body.orbit.semi_major_axis_au == pytest.approx(row["pl_orbsmax"], rel=1e-3)
        assert body.mass_kg / M_EARTH_KG == pytest.approx(row["pl_bmasse"], rel=1e-3)
    ab = sources.exoplanet_archive_system("eps Ind A")["planets"][0]
    body = next(b for b in _system_by_id("epsilon-indi").bodies if b.id == "eps-indi-ab")
    assert body.orbit.semi_major_axis_au == pytest.approx(ab["pl_orbsmax"], rel=1e-3)
    assert body.orbit.period_days == pytest.approx(ab["pl_orbper"], rel=1e-3)
    assert body.orbit.eccentricity == pytest.approx(ab["pl_orbeccen"], abs=1e-3)
    assert body.mass_kg / M_JUP_KG == pytest.approx(ab["pl_bmassj"], rel=1e-2)


@pytest.mark.network
@live
@pytest.mark.parametrize(
    ("system_id", "gaia_id", "same_source"),
    [
        ("barnards-star", 4472832130942575872, True),
        ("epsilon-indi", 6412595290592307840, True),
        ("r-draconis", 1648328016354496384, True),
        # RW Aur: centre on A, motion from B's solution (A's has RUWE 16); SIMBAD swaps their ids.
        ("rw-aurigae", 156430817820015232, False),
    ],
)
def test_catalog_positions_and_motions_match_gaia_dr3(system_id, gaia_id, same_source):
    system = _system_by_id(system_id)
    gaia = sources.gaia_dr3_source(gaia_id)
    assert system.motion.epoch.startswith("J2016.0")
    assert system.center.ra == pytest.approx(gaia["ra"], abs=1e-7)
    assert system.center.dec == pytest.approx(gaia["dec"], abs=1e-7)
    motion_source = gaia if same_source else sources.gaia_dr3_source(156430822114424576)
    assert system.motion.parallax_mas == pytest.approx(motion_source["parallax"], abs=1e-3)
    assert system.motion.pm_ra_cosdec_mas_yr == pytest.approx(motion_source["pmra"], abs=1e-3)
    assert system.motion.pm_dec_mas_yr == pytest.approx(motion_source["pmdec"], abs=1e-3)
