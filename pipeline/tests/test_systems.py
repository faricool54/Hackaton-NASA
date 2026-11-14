"""3D system models (WS7): physics helpers, catalog integrity and catalog sources."""

import os

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


def test_curated_values_are_flagged_unverified_until_checked():
    """Hand-typed values must not pretend to be verified (AGENTS.md rule 5)."""
    for system in curated_systems():
        assert not system.provenance.synthetic
        for body in system.bodies:
            assert all(not f.verified for f in body.facts), f"{system.id}/{body.id}: verify via WS7-2 first"


def test_synthetic_system_is_labelled():
    synthetic = [s for s in demo_systems() if s.provenance.synthetic]
    assert synthetic and all("synthetic" in s.tags for s in synthetic)


def _system(bodies):
    prov = Provenance(pipeline_version="t", built_at="2026-01-01T00:00:00Z", synthetic=True)
    return SystemModel(id="t", name="t", center=SkyCoord(ra=0, dec=0), bodies=bodies, provenance=prov)


def _body(bid, parent=None):
    orbit = Orbit(parent=parent, semi_major_axis_au=1, period_days=365) if parent else None
    return Body(id=bid, name=bid, kind="planet", orbit=orbit, appearance=Appearance(model="rocky"))


def test_hierarchy_rejects_unknown_parent_and_cycles():
    with pytest.raises(ValueError, match="unknown parent"):
        validate_hierarchy(_system([_body("a"), _body("b", "zzz")]))
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
