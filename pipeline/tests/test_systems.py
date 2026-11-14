"""3D system models (WS7): physics helpers and catalog integrity."""

import pytest

from errante.models import Appearance, Body, Orbit, Provenance, SkyCoord, SystemModel
from errante.products import ProductStore
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
