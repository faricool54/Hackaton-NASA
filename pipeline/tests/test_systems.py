"""3D system models (WS7): physics helpers, catalog integrity and catalog sources."""

import dataclasses
import json
import os
import re

import pytest

from errante.models import Appearance, Body, Orbit, Provenance, SkyCoord, SystemModel
from errante.products import ProductStore
from errante.systems import sources
from errante.systems.build import synthetic_system_ids, validate_hierarchy, write_real_systems, write_systems
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


# --- V13: what no source gives is not drawn (docs/VISION.md, WS7) ----------------

# Body fields that held a hand-picked, illustrative or class-typical value before V13.
REMOVED_VALUES = {
    "r-draconis": ("teff_k", "radius_km", "mass_kg"),  # 3000 K range pick, 250 R_sun illustrative, 1 M_sun class
    "eps-indi-ba": ("radius_km",),  # 0.9 R_Jup illustrative (no published radius)
    "eps-indi-bb": ("radius_km",),
    "wise-0855": ("mass_kg",),  # 5 M_Jup picked inside the 3-10 M_Jup model range
}


def _real_bodies():
    return {b.id: b for s in curated_systems() for b in s.bodies}


def test_no_hand_picked_values_remain():
    bodies = _real_bodies()
    for bid, fields in REMOVED_VALUES.items():
        for name in fields:
            assert getattr(bodies[bid], name) is None, f"{bid}.{name} must stay unknown"
    for system in curated_systems():
        texts = [system.representation_note, *system.provenance.notes]
        texts += [f"{f.label} {f.source or ''}" for b in system.bodies for f in b.facts]
        for text in texts:
            low = text.lower()
            assert not any(w in low for w in ("illustrative", "class-typical", "drawing value")), (system.id, text)
        unverified = [(b.id, f.label) for b in system.bodies for f in b.facts if not f.verified]
        # The one estimate kept is RW Aur A's radius, labelled as derived (VISION: luminosity + distance).
        assert all("(derived" in label for _, label in unverified), (system.id, unverified)
    rw_a = bodies["rw-aur-a"]
    radius = next(f for f in rw_a.facts if f.label.lower().startswith("radius"))
    assert radius.label.startswith("Radius (derived") and not radius.verified
    assert "Herczeg & Hillenbrand 2014" in radius.source and "156.1" in radius.source
    from errante.systems.catalog import R_SUN_KM

    assert rw_a.radius_km == pytest.approx(1.3 * R_SUN_KM)  # drawn value unchanged
    # The published ranges stay as Facts: the value is unknown, not the literature.
    rdra_teff = next(f for f in bodies["r-draconis"].facts if f.label.startswith("Temperature"))
    assert rdra_teff.value == "~2000–3300" and rdra_teff.verified
    wise_mass = next(f for f in bodies["wise-0855"].facts if f.label.startswith("Mass"))
    assert wise_mass.value == "3–10" and wise_mass.verified


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
        assert committed.provenance.notes == system.provenance.notes, f"{system.id}: regenerate data/demo"


# --- V13 measurement layer: targets.toml + frozen WS3 snapshots (systems.measured) ----------------------------


def _registry():
    from errante.systems.measured import load_registry

    return load_registry()


def test_registry_matches_the_catalog_and_every_snapshot_is_recorded():
    from errante.systems.measured import OBJECTS_DIR, load_snapshot

    registry = _registry()
    systems = {s.id: s for s in curated_systems()}
    for spec in registry.systems:
        assert spec.id in systems, f"targets.toml lists unknown system {spec.id}"
        ids = {b.id for b in systems[spec.id].bodies}
        assert {b.id for b in spec.bodies} <= ids, spec.id
    assert {p.stem for p in OBJECTS_DIR.glob("*.json")} == set(registry.snapshots)
    for slug, query in registry.snapshots.items():
        snap = load_snapshot(slug)
        assert snap["slug"] == slug and snap["query"]["name"] == query
        # Replayed from the WS3 fixtures, or recorded live (`errante systems --record <slug> --live`): either way
        # with the cache files it read, no service error, and Gaia parameters from the ESA archive (not a fallback).
        assert snap["origin"]["kind"] in {"ws3-fixtures", "live"}, slug
        assert snap["origin"]["files"], slug
        assert not [s for s in snap["origin"]["services"] if s["status"] == "error"], slug
        if snap["origin"]["kind"] == "live" and snap["gaia"] is not None:
            assert "ESA" in (snap["gaia"].get("details_from") or ""), slug
        assert set(snap["parameters"]) == {
            "teff",
            "radius",
            "luminosity",
            "mass",
            "distance",
            "spectral_type",
            "variability_type",
            "variability_period",
        }
        assert {p["label"] for p in snap["parameters"].values()} == {f["label"] for f in snap["facts"]}


def test_build_reads_json_only_no_network_and_no_ws3_code():
    """The 3D build must not query an archive or run WS3 code (a WS3 change cannot alter the published 3D)."""
    import subprocess
    import sys

    code = (
        "import socket, sys\n"
        "def boom(*a, **k): raise OSError('network used during the systems build')\n"
        "socket.socket = boom; socket.create_connection = boom\n"
        "from errante.systems.catalog import curated_systems\n"
        "systems = curated_systems()\n"
        "assert 'errante.science.context' not in sys.modules, 'WS3 code imported at build time'\n"
        "print(len(systems))\n"
    )
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=120)
    assert out.returncode == 0, out.stderr
    assert out.stdout.strip() == "5"


def _science_md_a5_facts():
    import ast

    from errante import settings

    path = settings.REPO_ROOT / "docs" / "SCIENCE.md"
    if not path.exists():
        pytest.skip("docs/SCIENCE.md not present")
    text = path.read_text(encoding="utf-8")
    heading = "**A5. Facts SPHEREx para el 3D**"
    if heading not in text:
        pytest.skip("the A5 block of the 3D review is no longer in docs/SCIENCE.md")
    start = text.index("```python", text.index(heading)) + len("```python")
    block = text[start : text.index("```", start)]
    facts = []
    for node in ast.walk(ast.parse(block)):
        if isinstance(node, ast.Call) and getattr(node.func, "id", None) == "_vfact":
            facts.append(tuple(ast.literal_eval(a) for a in node.args))
    return facts


# Body that docs/SCIENCE.md (block A5) assigns each "seen by SPHEREx" fact to.
A5_BODIES = {
    "Motion seen by SPHEREx": "barnards-star",
    "Motion seen by SPHEREx (Ba+Bb as one source)": "eps-indi-ba",
    "Seen by SPHEREx": "wise-0855",
    "Brightness change seen by SPHEREx (A+B)": "rw-aur-a",
    "Cycle seen by SPHEREx": "r-draconis",
    "Brightness range seen by SPHEREx (0.74–5.0 µm, by detector)": "r-draconis",
}


def test_spherex_facts_are_the_a5_block_verbatim_on_their_bodies():
    expected = _science_md_a5_facts()
    assert len(expected) == len(A5_BODIES)
    shipped = {}
    for system in curated_systems():
        for body in system.bodies:
            for f in body.facts:
                if (f.source or "").startswith("SPHEREx"):
                    assert f.verified and "offline" in f.source, f.label
                    shipped[(f.label, f.value, f.unit, f.source)] = body.id
    assert set(shipped) == set(expected)
    for key, body_id in shipped.items():
        assert A5_BODIES[key[0]] == body_id, key[0]
    # Appended after the literature facts: BodyPanel order and the frontend tier tie-breaks do not change.
    rdra = _real_bodies()["r-draconis"]
    assert rdra.facts[0].label == "Variable type"


def test_measured_layer_changes_no_drawn_value():
    """Only facts and notes are added: every drawn number is the literature layer's."""
    from errante.systems.catalog import literature_systems

    for before, after in zip(literature_systems(), curated_systems(), strict=True):
        assert before.model_dump(exclude={"bodies", "provenance"}) == after.model_dump(exclude={"bodies", "provenance"})
        for b0, b1 in zip(before.bodies, after.bodies, strict=True):
            assert b0.model_dump(exclude={"facts"}) == b1.model_dump(exclude={"facts"}), b0.id
            assert b1.facts[: len(b0.facts)] == b0.facts, b0.id  # literature facts first, unchanged


def test_cross_checks_are_verified_catalog_facts_never_on_blended_or_swapped_components():
    from errante.systems.measured import CATALOG_SUFFIX, CROSS_CHECK_LABEL_SUFFIX

    assert CROSS_CHECK_LABEL_SUFFIX == " (catalog cross-check)"
    bodies = _real_bodies()
    for body in bodies.values():
        for f in body.facts:
            if CATALOG_SUFFIX in (f.source or ""):
                assert f.verified and f.value != "unknown", (body.id, f.label)
                assert f.source.endswith(CATALOG_SUFFIX)
                # The label says it too, so it reads apart from the drawn value's fact of the same name.
                assert f.label.endswith(CROSS_CHECK_LABEL_SUFFIX), (body.id, f.label)
        labels = [f.label for f in body.facts]
        assert len(labels) == len(set(labels)), (body.id, labels)
    # eps Ind B is one unresolved Gaia source; RW Aur's context is the A+B pair with swapped names (V15).
    for bid in ("eps-indi-ba", "eps-indi-bb", "rw-aur-a", "rw-aur-b", "rw-aur-a-disk"):
        assert not [f.label for f in bodies[bid].facts if CATALOG_SUFFIX in (f.source or "")], bid
    eps = _system_by_id("epsilon-indi").provenance.notes
    assert any(n.startswith("WS3 object context of 'eps Ind B'") and "Not attached to Ba or Bb" in n for n in eps)
    rw = _system_by_id("rw-aurigae").provenance.notes
    note = next(n for n in rw if n.startswith("WS3 object context of 'RW Aur'"))
    assert "match 'ambiguous'" in note and "Not used (unknown or not verified in WS3): Distance" in note
    assert "V15: fixed in the WS3 card by #101; this snapshot predates it" in note and "V15, open" not in note
    # Barnard: Gaia's own values sit next to the published ones, without replacing them.
    barnard = bodies["barnards-star"]
    teffs = [f.value for f in barnard.facts if "temperature" in f.label.lower()]
    assert teffs == ["3195 ± 28", "3100 (3099-3102)"] and barnard.teff_k == 3195


def test_unknowns_are_explained_in_notes_and_never_become_facts():
    from errante.systems.measured import BODY_FIELDS, PARAM_NAMES, UNKNOWN_NOTE_PREFIX, drawn_params

    for system in curated_systems():
        note = next((n for n in system.provenance.notes if n.startswith(UNKNOWN_NOTE_PREFIX)), "")
        for body in system.bodies:
            assert not [f.label for f in body.facts if f.value.strip().lower() == "unknown"], body.id
            missing = [k for k in drawn_params(body) if getattr(body, BODY_FIELDS[k]) is None]
            for key in missing:
                assert f"{body.name}: " in note and f"{PARAM_NAMES[key]} (" in note, (system.id, body.id, key)
    rdra = next(n for n in _system_by_id("r-draconis").provenance.notes if n.startswith(UNKNOWN_NOTE_PREFIX))
    for text in ("temperature (it changes with the pulsation", "WS3 V18", "radius (", "mass (no dynamical mass"):
        assert text in rdra, text
    assert "Gaia DR3 has no temperature for this source" in rdra  # WS3's own reason, from the snapshot
    # Systems where everything drawn is known carry no such note.
    assert not any(n.startswith(UNKNOWN_NOTE_PREFIX) for n in _system_by_id("barnards-star").provenance.notes)


def test_registry_refuses_an_unexplained_unknown_and_an_unverified_cross_check(tmp_path):
    from errante.systems.catalog import literature_systems
    from errante.systems.measured import REGISTRY_PATH, RegistryError, apply_registry, load_registry

    text = REGISTRY_PATH.read_text(encoding="utf-8")
    no_reason = tmp_path / "no-reason.toml"
    no_reason.write_text(text.replace('unknown = { radius = "no published radius for Ba" }', ""), encoding="utf-8")
    with pytest.raises(RegistryError, match="eps-indi-ba: radius is unknown"):
        apply_registry(literature_systems(), load_registry(no_reason))
    unverified = tmp_path / "unverified.toml"
    # RW Aur's WS3 distance is not verified (ambiguous match): asking for it on a body must fail.
    unverified.write_text(
        text.replace(
            '[[system.body]]\nid = "rw-aur-a"',
            '[[system.body]]\nid = "rw-aur-a"\nsnapshot = "rw-aurigae"\ncross_check = ["distance"]',
        ),
        encoding="utf-8",
    )
    with pytest.raises(RegistryError, match="no verified value"):
        apply_registry(literature_systems(), load_registry(unverified))


def test_astrometry_and_planets_agree_with_the_gaia_and_archive_snapshots():
    from errante.systems.measured import load_snapshot

    for system_id, slug in (("barnards-star", "barnards-star"), ("r-draconis", "r-draconis")):
        system, gaia = _system_by_id(system_id), load_snapshot(slug)["gaia"]
        assert system.center.ra == pytest.approx(gaia["ra"], abs=1e-7)
        assert system.center.dec == pytest.approx(gaia["dec"], abs=1e-7)
        assert system.motion.parallax_mas == pytest.approx(gaia["parallax"], abs=1e-3)
        assert system.motion.pm_ra_cosdec_mas_yr == pytest.approx(gaia["pmra"], abs=1e-3)
        assert system.motion.pm_dec_mas_yr == pytest.approx(gaia["pmdec"], abs=1e-3)
    # RW Aur is centred on A = Gaia DR3 156430817820015232 (WDS), the source WS3 adopted for "RW Aur".
    rw, snap = _system_by_id("rw-aurigae"), load_snapshot("rw-aurigae")
    assert snap["identity"]["gaia_source_id"] == "156430817820015232"
    assert rw.center.ra == pytest.approx(snap["gaia"]["ra"], abs=1e-7)
    from errante.systems.catalog import M_EARTH_KG

    archive = {p["name"]: p for p in load_snapshot("barnards-star")["planets"]}
    for body in _system_by_id("barnards-star").bodies[1:]:
        row = archive[body.name]
        assert body.orbit.period_days == pytest.approx(row["period_d"], rel=1e-4)
        assert body.orbit.semi_major_axis_au == pytest.approx(row["semi_major_axis_au"], rel=1e-3)
        assert body.mass_kg / M_EARTH_KG == pytest.approx(row["mass_earth"], rel=1e-3)
        assert row["mass_kind"] == "Msini" and row["radius_calculated"]


def test_explain_gives_origin_and_reason_for_every_drawn_value(capsys):
    from errante.cli import main
    from errante.systems.measured import explain

    rows = explain(curated_systems())
    unknown = [(r.body, r.parameter) for r in rows if r.value == "unknown"]
    assert sorted(unknown) == sorted(
        [
            ("r-draconis", "temperature"),
            ("r-draconis", "radius"),
            ("r-draconis", "mass"),
            ("eps-indi-ba", "radius"),
            ("eps-indi-bb", "radius"),
            ("wise-0855", "mass"),
        ]
    )
    assert all(r.reason for r in rows)
    origins = {(r.body, r.parameter): r.origin for r in rows}
    assert origins[("rw-aur-a", "radius")] == "derived"
    assert origins[("r-draconis", "Cycle seen by SPHEREx")].startswith("SPHEREx-measured")
    teff_check = ("barnards-star", "Effective temperature (catalog cross-check)")
    assert origins[teff_check] == "catalog cross-check (WS3 snapshot)"
    assert origins[("barnards-star", "temperature")] == "catalog, not measured by SPHEREx"
    assert main(["systems", "--explain", "--json"]) == 0
    printed = capsys.readouterr().out
    assert '"parameter": "temperature"' in printed and "not drawn" in printed


def test_cli_record_replays_the_ws3_fixtures(tmp_path):
    """Dev tool only. Skips (not fails) when the WS3 fixtures or queries changed: the build never depends on it."""
    from errante.cli import main
    from errante.systems.measured import load_snapshot
    from errante.systems.record import FIXTURES_DIR

    if not FIXTURES_DIR.is_dir():
        pytest.skip("WS3 fixtures not present")
    if main(["systems", "--record", "r-draconis", "--inputs", str(tmp_path)]) != 0:
        pytest.skip("the WS3 fixtures no longer replay this query: re-record and review the diff")
    fresh, committed = load_snapshot("r-draconis", tmp_path), load_snapshot("r-draconis")
    assert fresh["identity"] == committed["identity"]
    assert main(["systems", "--record", "no-such-target", "--inputs", str(tmp_path)]) == 1


def test_record_skips_live_snapshots_offline_and_refuses_naming_one(tmp_path, monkeypatch):
    """A live-recorded target has no fixtures: `--record all` offline skips it; naming it without --live fails."""
    import errante.systems.measured as M
    import errante.systems.record as R

    committed = tmp_path / "committed"
    committed.mkdir()
    for slug in ("r-draconis", "wise-0855"):
        doc = M.load_snapshot(slug)
        if slug == "wise-0855":
            doc = {**doc, "origin": {**doc["origin"], "kind": "live"}}
        (committed / f"{slug}.json").write_text(json.dumps(doc), encoding="utf-8")
    registry = M.load_registry()
    monkeypatch.setattr(M, "OBJECTS_DIR", committed)
    monkeypatch.setattr(
        M,
        "load_registry",
        lambda *a, **k: dataclasses.replace(
            registry, snapshots={k: v for k, v in registry.snapshots.items() if k in ("r-draconis", "wise-0855")}
        ),
    )
    replayed = []
    monkeypatch.setattr(R, "snapshot_document", lambda slug, query, live=False: replayed.append(slug) or {"slug": slug})
    out = tmp_path / "out"
    R.record(None, objects_dir=out)
    assert replayed == ["r-draconis"]
    with pytest.raises(R.RecordError, match="recorded live"):
        R.record(["wise-0855"], objects_dir=out)
    replayed.clear()
    R.record(["wise-0855"], live=True, objects_dir=out)
    assert replayed == ["wise-0855"]


def test_context_only_target_builds_from_its_snapshot_without_inventing():
    """Scalable path (V13 stretch): a target with no catalog function, here Barnard's Star as if it were new."""
    from errante.systems.catalog import M_SUN_KG, R_SUN_KM
    from errante.systems.measured import (
        CATALOG_SUFFIX,
        UNKNOWN_NOTE_PREFIX,
        RegistryError,
        SystemSpec,
        load_snapshot,
        system_from_snapshot,
    )

    spec = SystemSpec(id="new-barnard", new={"name": "Barnard's Star (context only)", "field_id": None})
    system = system_from_snapshot(spec, load_snapshot("barnards-star"))
    validate_hierarchy(system)
    star, planets = system.bodies[0], system.bodies[1:]
    assert star.kind == "star" and star.teff_k == pytest.approx(3099.6, abs=0.1)
    assert star.radius_km == pytest.approx(0.2022 * R_SUN_KM, rel=1e-3)
    assert star.mass_kg is None and M_SUN_KG  # FLAME gives no mass: unknown, not invented
    assert system.motion.distance_pc == pytest.approx(1.828, abs=1e-3)
    assert system.field_id is None and "context-only" in system.tags
    assert [p.name for p in planets] == ["Barnard d", "Barnard b", "Barnard c", "Barnard e"]
    for p in planets:
        assert p.orbit.parent == star.id and p.orbit.period_days > 0 and p.orbit.semi_major_axis_au > 0
        labels = {f.label for f in p.facts}
        assert "Minimum mass" in labels and "Radius (model estimate)" in labels
    assert not [f.label for f in star.facts if f.label.endswith(" (catalog cross-check)")]  # drawn values, not checks
    facts = [f for b in system.bodies for f in b.facts]
    assert facts and all(f.verified and f.value != "unknown" and CATALOG_SUFFIX in f.source for f in facts)
    note = next(n for n in system.provenance.notes if n.startswith(UNKNOWN_NOTE_PREFIX))
    assert "mass (WS3 object context: Gaia DR3 FLAME gives no mass for this source)" in note
    assert "SPHEREx" in system.representation_note and not system.provenance.synthetic
    # An ambiguous identity (RW Aur: two Gaia sources in the radius) gets no 3D model.
    with pytest.raises(RegistryError, match="ambiguous"):
        system_from_snapshot(SystemSpec(id="rw", new={"name": "RW Aur"}), load_snapshot("rw-aurigae"))


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


# --- R Dra: two clocks (free-running sine; Dataset time on the measured maxima, VSX outside) ----


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
        # V12a (full variant): measured AAVSO maxima inside the SPHEREx window, VSX outside it
        "dated by the V maxima measured by AAVSO in 2025–2026 (MJD 60811.4, 61046.5 and 61304.3",
        "±3 d band",
        "±9.0 d band",
        "frontend/src/three/ephemerides.ts",
        # V12 (D3, docs/SCIENCE.md 3D review): constant radius, and the SPHEREx measurement quoted (B5, verbatim)
        "the radius is drawn constant, because its size change is not measured",
        "catalog V-band drawings, not measured by SPHEREx",
        "much smaller in the infrared: offline measurements on the SPHEREx FITS files give 0.5–1.3 mag peak-to-peak "
        "at 0.74–5.0 µm and a ~260-day cycle in 2025–2026 (docs/validation/r-draconis.md). The animation is not that "
        "light curve, and the SPHEREx images in this app do not show it.",
    ):
        assert text in RDRA_PULSATION_NOTE, text
    assert "in phase with the light" not in RDRA_PULSATION_NOTE  # the size no longer changes
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


# --- real dataset (data/products): only non-synthetic systems (AGENTS.md rule 3) ---------


def test_write_real_systems_skips_the_synthetic_ones(tmp_path):
    store = ProductStore(tmp_path)
    written, skipped = write_real_systems(store, demo_systems())
    assert written == [s.id for s in curated_systems()]
    assert skipped == ["demo-ecliptic-orbits"]
    manifest = store.rebuild_manifest()
    assert not manifest.synthetic
    assert not any(s.synthetic for s in manifest.systems)


def test_write_real_systems_refuses_a_folder_holding_a_synthetic_system(tmp_path):
    store = ProductStore(tmp_path)
    write_systems(store, [s for s in demo_systems() if s.provenance.synthetic])
    with pytest.raises(ValueError, match="demo-ecliptic-orbits"):
        write_real_systems(store, curated_systems())
    assert synthetic_system_ids(store) == ["demo-ecliptic-orbits"]
    assert not store.has_system("barnards-star")  # refused before writing anything


def test_cli_systems_real_only_and_default_unchanged(tmp_path, capsys):
    from errante.cli import main

    assert main(["systems", "--out", str(tmp_path / "real"), "--real-only"]) == 0
    manifest = ProductStore(tmp_path / "real").read_manifest()
    assert [s.id for s in manifest.systems] == sorted(s.id for s in curated_systems())
    assert not manifest.synthetic
    # A folder that already holds the synthetic demo system is refused (exit 1), not published.
    demo = ProductStore(tmp_path / "demo")
    write_systems(demo, demo_systems())
    assert main(["systems", "--out", str(tmp_path / "demo"), "--real-only"]) == 1
    assert "demo-ecliptic-orbits" in capsys.readouterr().err
    # Without the flag nothing changes: the curated systems are written and the demo one is kept.
    assert main(["systems", "--out", str(tmp_path / "demo")]) == 0
    assert {s.id for s in demo.read_manifest().systems} == {s.id for s in demo_systems()}


def test_committed_real_systems_match_the_catalog_and_link_their_fields():
    """data/products/systems is generated: run `errante systems --out data/products --real-only` after
    editing catalog.py. Each system must point at a real field of that dataset (the 3D <-> images links)."""
    from errante import settings

    store = ProductStore(settings.REPO_ROOT / "data" / "products")
    manifest = store.read_manifest()
    assert {s.id for s in manifest.systems} == {s.id for s in curated_systems()}
    assert synthetic_system_ids(store) == []
    real_fields = {f.id for f in manifest.fields if not f.synthetic}
    for system in curated_systems():
        committed = store.read_system(system.id)
        assert committed.model_dump(exclude={"provenance"}) == system.model_dump(exclude={"provenance"}), system.id
        # A context-only target (measured.system_from_snapshot) may have no SPHEREx field yet; the five must link.
        if "context-only" not in committed.tags:
            assert committed.field_id in real_fields, f"{system.id}: field {committed.field_id} not in data/products"
        assert committed.provenance.notes == system.provenance.notes, f"{system.id}: regenerate data/products"


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
