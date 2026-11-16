"""Measurement layer of the WS7 3D systems (V13, docs/VISION.md).

``catalog`` holds the literature layer of each system: published values, each with its Fact. This module
adds, from data only (``targets.toml`` and the frozen WS3 object-context snapshots in ``inputs/objects/``):

- the facts measured by SPHEREx (validation records, docs/SCIENCE.md block A5; ``Fact.source`` starts with
  "SPHEREx"), appended to their body;
- catalog cross-checks from the WS3 object context (Gaia DR3, SIMBAD, AAVSO VSX), appended to their body with
  WS3's own source text plus :data:`CATALOG_SUFFIX`. Only verified values are attached and no drawn value
  changes: they let a reader compare, e.g., Barnard's published 3195 K with Gaia GSP-Phot's 3100 K;
- a system note for a context that cannot be given to one body (an unresolved blend, an A/B identity swap);
- a note "Not measured, so not drawn (shown as unknown): <body>: <param> (<reason>); ..." for every drawn
  field (temperature, radius, mass) that stays ``None``. Unknown values never become Facts: an 'unknown' Fact
  would count as an unverified value in the UI.

Nothing here touches the network or imports WS3 code: a WS3 change cannot change the published 3D until
someone re-records a snapshot (``errante systems --record``) and reviews the diff. Adding a target means a
``[snapshots]`` entry, ``--record`` and a ``[[system]]`` block; a target with no ``catalog`` function can be
built from its snapshot alone with :func:`system_from_snapshot` (catalog values only, unknowns left unknown).
"""

from __future__ import annotations

import json
import re
import tomllib
from dataclasses import dataclass, field
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path

from ..models import Appearance, Body, Fact, Orbit, Provenance, SkyCoord, SpaceMotion, SystemModel

HERE = Path(__file__).parent
REGISTRY_PATH = HERE / "targets.toml"
OBJECTS_DIR = HERE / "inputs" / "objects"
REGISTRY_SCHEMA = 1
SNAPSHOT_SCHEMA = 1

CATALOG_SUFFIX = " (via WS3 object context; catalog, not measured by SPHEREx)"
# Appended to the label of a cross-check fact, so it reads apart from the drawn value's fact of the same name.
CROSS_CHECK_LABEL_SUFFIX = " (catalog cross-check)"
UNKNOWN_NOTE_PREFIX = "Not measured, so not drawn (shown as unknown): "
SPHEREX_SOURCE_PREFIX = "SPHEREx"

# WS3 parameter keys (errante.science.context.derive_parameters).
PARAM_KEYS = (
    "teff",
    "radius",
    "luminosity",
    "mass",
    "distance",
    "spectral_type",
    "variability_type",
    "variability_period",
)
# Drawn body fields that can be unknown, by WS3 parameter key, and how the notes name them.
BODY_FIELDS = {"teff": "teff_k", "radius": "radius_km", "mass": "mass_kg"}
PARAM_NAMES = {"teff": "temperature", "radius": "radius", "mass": "mass"}
# Added to every unknown of that kind: the SPHEREx route of docs/VISION.md does not exist yet.
SPHEREX_GAP = {
    "teff": "no temperature fit to the SPHEREx spectrum yet, WS3 V18",
    "radius": "no radius from the SPHEREx flux and the distance yet, WS7-8",
}
STELLAR_KINDS = ("star", "brown_dwarf")

R_SUN_KM = 695_700.0
M_SUN_KG = 1.989e30
R_EARTH_KM = 6_371.0
M_EARTH_KG = 5.972e24

# Fact labels that back a drawn field (same reading as frontend/src/three/astro.ts FACT_LABEL_PATTERNS).
FACT_LABELS = {
    "teff": re.compile(r"^((effective\s+)?temperature|t\s*_?eff)\b", re.I),
    "radius": re.compile(r"^((dust\s+)?disk\s+)?radius\b", re.I),
    "mass": re.compile(r"^(minimum\s+)?mass\b", re.I),
    "distance": re.compile(r"^distance\b", re.I),
}


class RegistryError(ValueError):
    """targets.toml or a snapshot does not support what the registry asks for."""


@dataclass
class BodySpec:
    id: str
    snapshot: str | None = None
    cross_check: tuple[str, ...] = ()
    spherex_facts: tuple[Fact, ...] = ()
    unknown: dict[str, str] = field(default_factory=dict)


@dataclass
class SystemSpec:
    id: str
    bodies: list[BodySpec] = field(default_factory=list)
    snapshot: str | None = None
    snapshot_keys: tuple[str, ...] = ()
    snapshot_note: str | None = None
    new: dict | None = None  # context-only target (system_from_snapshot): name, description, field_id, kind

    def body(self, body_id: str) -> BodySpec | None:
        return next((b for b in self.bodies if b.id == body_id), None)


@dataclass
class Registry:
    snapshots: dict[str, str]  # slug -> WS3 object_context(name=...) query
    systems: list[SystemSpec]

    def system(self, system_id: str) -> SystemSpec | None:
        return next((s for s in self.systems if s.id == system_id), None)


def _keys(values, where: str) -> tuple[str, ...]:
    bad = [k for k in values if k not in PARAM_KEYS]
    if bad:
        raise RegistryError(f"{where}: unknown WS3 parameter keys {bad} (known: {list(PARAM_KEYS)})")
    return tuple(values)


def _spherex_fact(raw: dict, where: str) -> Fact:
    fact = Fact(label=raw["label"], value=raw["value"], unit=raw.get("unit"), source=raw["source"], verified=True)
    if not fact.source.startswith(SPHEREX_SOURCE_PREFIX):
        raise RegistryError(f"{where}: a SPHEREx fact's source must start with {SPHEREX_SOURCE_PREFIX!r}")
    return fact


def load_registry(path: Path = REGISTRY_PATH) -> Registry:
    doc = tomllib.loads(path.read_text(encoding="utf-8"))
    if doc.get("schema") != REGISTRY_SCHEMA:
        raise RegistryError(f"{path.name}: schema {doc.get('schema')!r}, expected {REGISTRY_SCHEMA}")
    snapshots = dict(doc.get("snapshots", {}))
    systems = []
    for raw in doc.get("system", []):
        sid = raw["id"]
        bodies = []
        for rb in raw.get("body", []):
            where = f"{sid}/{rb['id']}"
            unknown = dict(rb.get("unknown", {}))
            bad = [k for k in unknown if k not in BODY_FIELDS]
            if bad:
                raise RegistryError(f"{where}: 'unknown' accepts {list(BODY_FIELDS)}, not {bad}")
            bodies.append(
                BodySpec(
                    id=rb["id"],
                    snapshot=rb.get("snapshot"),
                    cross_check=_keys(rb.get("cross_check", []), where),
                    spherex_facts=tuple(_spherex_fact(f, where) for f in rb.get("spherex_fact", [])),
                    unknown=unknown,
                )
            )
        spec = SystemSpec(
            id=sid,
            bodies=bodies,
            snapshot=raw.get("snapshot"),
            snapshot_keys=_keys(raw.get("snapshot_keys", []), sid),
            snapshot_note=raw.get("snapshot_note"),
            new=raw.get("new"),
        )
        for slug in [spec.snapshot, *(b.snapshot for b in bodies)]:
            if slug is not None and slug not in snapshots:
                raise RegistryError(f"{sid}: snapshot {slug!r} is not listed in [snapshots]")
        systems.append(spec)
    return Registry(snapshots=snapshots, systems=systems)


@lru_cache(maxsize=64)
def _read_snapshot(path: Path) -> dict:
    doc = json.loads(path.read_text(encoding="utf-8"))
    if doc.get("schema") != SNAPSHOT_SCHEMA:
        raise RegistryError(f"{path.name}: snapshot schema {doc.get('schema')!r}, expected {SNAPSHOT_SCHEMA}")
    return doc


def load_snapshot(slug: str, objects_dir: Path = OBJECTS_DIR) -> dict:
    """The frozen WS3 object context ``inputs/objects/<slug>.json`` (see ``systems.record``)."""
    path = objects_dir / f"{slug}.json"
    if not path.is_file():
        raise RegistryError(f"snapshot {slug!r} not recorded: run `errante systems --record {slug}`")
    return _read_snapshot(path)


def snapshot_fact(snapshot: dict, key: str) -> Fact | None:
    """WS3's contract Fact for one parameter, as recorded, or None when it is unknown or not verified."""
    param = snapshot["parameters"].get(key)
    if param is None or param.get("value") is None:
        return None
    fact = next((Fact(**f) for f in snapshot["facts"] if f["label"] == param["label"]), None)
    if fact is None or not fact.verified or fact.value == "unknown":
        return None
    return fact


def cross_check_fact(snapshot: dict, key: str, *, label_suffix: bool = True) -> Fact | None:
    """A verified snapshot value as a catalog fact. ``label_suffix=False`` when it is the drawn value itself
    (system_from_snapshot), so it is not labelled as a cross-check of another value."""
    fact = snapshot_fact(snapshot, key)
    if fact is None:
        return None
    update = {"source": (fact.source or "WS3 object context") + CATALOG_SUFFIX}
    if label_suffix:
        update["label"] = fact.label + CROSS_CHECK_LABEL_SUFFIX
    return fact.model_copy(update=update)


def _snapshot_reason(snapshot: dict, key: str) -> str | None:
    param = snapshot["parameters"].get(key)
    if param is None or param.get("value") is not None:
        return None
    return f"WS3 object context: {param['method'].rstrip('.')}" if param.get("method") else None


def _fact_text(fact: Fact) -> str:
    return f"{fact.label} {fact.value}" + (f" {fact.unit}" if fact.unit else "")


def drawn_params(body: Body) -> tuple[str, ...]:
    """The fields the viewer draws for this kind of body (colour only for emitters)."""
    return ("teff", "radius", "mass") if body.kind in STELLAR_KINDS else ("radius",)


def unknown_entries(body: Body, spec: BodySpec | None, snapshots: dict[str, dict]) -> list[tuple[str, str]]:
    """(param, reason) for every drawn field of ``body`` that is None. Raises when the registry gives no reason."""
    out = []
    snap = snapshots.get(spec.snapshot) if spec and spec.snapshot else None
    for key in drawn_params(body):
        if getattr(body, BODY_FIELDS[key]) is not None:
            continue
        reason = (spec.unknown.get(key) if spec else None) or None
        if reason is None:
            raise RegistryError(f"{body.id}: {PARAM_NAMES[key]} is unknown and targets.toml gives no reason")
        reasons = [reason]
        if snap is not None and (extra := _snapshot_reason(snap, key)):
            reasons.append(extra)
        if key in SPHEREX_GAP:
            reasons.append(SPHEREX_GAP[key])
        out.append((key, "; ".join(reasons)))
    return out


def _context_note(spec: SystemSpec, snap: dict) -> str:
    ident = snap["identity"]
    gaia = f", Gaia DR3 {ident['gaia_source_id']}" if ident.get("gaia_source_id") else ""
    used, skipped = [], []
    for key in spec.snapshot_keys:
        fact = snapshot_fact(snap, key)
        if fact is not None:
            used.append(_fact_text(fact))
        else:
            skipped.append(snap["parameters"][key]["label"])
    text = (
        f"WS3 object context of {snap['query']['name']!r} ({ident.get('display_name') or ident.get('main_id')}{gaia}, match "
        f"'{ident.get('match')}'; catalog, not measured by SPHEREx): {'; '.join(used)}."
    )
    if skipped:
        text += f" Not used (unknown or not verified in WS3): {', '.join(skipped)}."
    return text + (f" {spec.snapshot_note}" if spec.snapshot_note else "")


def _inputs_note(slugs: list[str], snapshots: dict[str, dict]) -> str:
    parts = []
    for slug in slugs:
        snap = snapshots[slug]
        span = snap["origin"].get("retrieved_utc") or ["?", "?"]
        how = "replayed offline from the WS3 fixtures" if snap["origin"].get("kind") == "ws3-fixtures" else "live"
        parts.append(f"'{slug}' (query {snap['query']['name']!r}; services answered {span[0]} to {span[1]}; {how})")
    noun = "snapshot" if len(parts) == 1 else "snapshots"
    return (
        f"Catalog values from the frozen WS3 object-context {noun} {', '.join(parts)}, "
        "pipeline/errante/systems/inputs/objects/: not measured by SPHEREx, and not queried when the site is built."
    )


def apply_registry(
    systems: list[SystemModel], registry: Registry | None = None, objects_dir: Path = OBJECTS_DIR
) -> list[SystemModel]:
    """Attach the measurement layer to the literature systems (synthetic systems are returned unchanged)."""
    registry = registry or load_registry()
    out = []
    for system in systems:
        if system.provenance.synthetic:
            out.append(system)
            continue
        spec = registry.system(system.id)
        slugs = []
        if spec is not None:
            slugs = [s for s in [spec.snapshot, *(b.snapshot for b in spec.bodies)] if s]
        snapshots = {s: load_snapshot(s, objects_dir) for s in dict.fromkeys(slugs)}
        bodies, unknown = [], []
        for body in system.bodies:
            bspec = spec.body(body.id) if spec else None
            facts = list(body.facts)
            if bspec is not None:
                facts += list(bspec.spherex_facts)
                for key in bspec.cross_check:
                    fact = cross_check_fact(snapshots[bspec.snapshot], key)
                    if fact is None:
                        raise RegistryError(
                            f"{system.id}/{body.id}: cross-check {key!r} has no verified value in {bspec.snapshot!r}"
                        )
                    facts.append(fact)
            entries = unknown_entries(body, bspec, snapshots)
            if entries:
                unknown.append(f"{body.name}: " + ", ".join(f"{PARAM_NAMES[k]} ({why})" for k, why in entries))
            bodies.append(body.model_copy(update={"facts": facts}))
        notes = list(system.provenance.notes)
        if spec is not None and spec.snapshot:
            notes.append(_context_note(spec, snapshots[spec.snapshot]))
        if snapshots:
            notes.append(_inputs_note(list(snapshots), snapshots))
        if unknown:
            notes.append(UNKNOWN_NOTE_PREFIX + "; ".join(unknown) + ".")
        provenance = system.provenance.model_copy(update={"notes": notes})
        out.append(system.model_copy(update={"bodies": bodies, "provenance": provenance}))
    return out


# --- explain: where each drawn value comes from (errante systems --explain) --------------------------------


@dataclass
class ExplainRow:
    system: str
    body: str
    parameter: str
    value: str
    origin: str
    reason: str


def _origin_of(fact: Fact) -> str:
    if (fact.source or "").startswith(SPHEREX_SOURCE_PREFIX):
        return "SPHEREx-measured (offline analysis)"
    if "(derived" in fact.label:
        return "derived"
    if CATALOG_SUFFIX in (fact.source or ""):
        return "catalog cross-check (WS3 snapshot)"
    return "catalog, not measured by SPHEREx"


def _fmt_value(value: float | None, unit: str) -> str:
    return "unknown" if value is None else f"{value:.6g} {unit}".strip()


def explain(
    systems: list[SystemModel], registry: Registry | None = None, objects_dir: Path = OBJECTS_DIR
) -> list[ExplainRow]:
    """One row per drawn value (temperature, radius, mass, distance, variability) and per attached fact."""
    registry = registry or load_registry()
    rows: list[ExplainRow] = []
    for system in systems:
        if system.provenance.synthetic:
            continue
        spec = registry.system(system.id)
        slugs = [s for s in ([spec.snapshot, *(b.snapshot for b in spec.bodies)] if spec else []) if s]
        snapshots = {s: load_snapshot(s, objects_dir) for s in dict.fromkeys(slugs)}
        for body in system.bodies:
            bspec = spec.body(body.id) if spec else None
            try:
                reasons = dict(unknown_entries(body, bspec, snapshots))
            except RegistryError as e:
                reasons = {k: str(e) for k in drawn_params(body)}
            for key in drawn_params(body):
                value = getattr(body, BODY_FIELDS[key])
                unit = {"teff": "K", "radius": "km", "mass": "kg"}[key]
                backing = [f for f in body.facts if FACT_LABELS[key].match(f.label.strip()) and not _is_extra(f)]
                if value is None:
                    rows.append(ExplainRow(system.id, body.id, PARAM_NAMES[key], "unknown", "not drawn", reasons[key]))
                elif backing:
                    f = backing[0]
                    rows.append(
                        ExplainRow(
                            system.id,
                            body.id,
                            PARAM_NAMES[key],
                            _fmt_value(value, unit),
                            _origin_of(f),
                            f"Fact '{_fact_text(f)}' ({f.source})",
                        )
                    )
                else:
                    rows.append(
                        ExplainRow(
                            system.id, body.id, PARAM_NAMES[key], _fmt_value(value, unit), "no Fact", "no backing Fact"
                        )
                    )
            if body.variability is not None:
                v = body.variability
                origin = (
                    "SPHEREx-measured" if (v.band or "").startswith("SPHEREx") else "catalog, not measured by SPHEREx"
                )
                text = f"{v.kind}, P {v.period_days} d, {v.amplitude_mag} mag ({v.band})"
                rows.append(ExplainRow(system.id, body.id, "variability", text, origin, "Body.variability"))
            for f in body.facts:
                if _is_extra(f):
                    text = f"{f.value} {f.unit or ''}".strip()
                    rows.append(ExplainRow(system.id, body.id, f.label, text, _origin_of(f), f.source or ""))
        if system.motion and system.motion.distance_pc:
            facts = [
                f
                for b in system.bodies
                for f in b.facts
                if FACT_LABELS["distance"].match(f.label.strip()) and not _is_extra(f)
            ]
            rows.append(
                ExplainRow(
                    system.id,
                    "(system)",
                    "distance",
                    f"{system.motion.distance_pc:g} pc",
                    _origin_of(facts[0]) if facts else "no Fact",
                    f"Fact '{_fact_text(facts[0])}' ({facts[0].source})" if facts else "no backing Fact",
                )
            )
    return rows


def _is_extra(fact: Fact) -> bool:
    """Facts attached by this module (SPHEREx-measured or WS3 cross-check), not the catalog layer."""
    return (fact.source or "").startswith(SPHEREX_SOURCE_PREFIX) or CATALOG_SUFFIX in (fact.source or "")


# --- a target with no catalog function: built from its snapshot alone (stretch, V13) ------------------------

CONTEXT_REPRESENTATION = (
    "3D model built from the catalog values of a WS3 object context (Gaia DR3, SIMBAD, NASA Exoplanet Archive), "
    "not measured by SPHEREx - not an image. What the context does not give is not drawn: an unknown temperature "
    "is drawn grey and an unknown size at a fixed marker size, not to scale."
)


def _kind_from_otype(otype: str | None) -> str | None:
    if not otype:
        return None
    if otype.startswith("BD"):
        return "brown_dwarf"
    return "star" if otype.endswith("*") else None


def system_from_snapshot(spec: SystemSpec, snapshot: dict, *, pipeline_version: str | None = None) -> SystemModel:
    """A star (or brown dwarf) and its confirmed planets from one snapshot: verified catalog values or unknown.

    ``spec.new`` gives ``name`` and optionally ``description``, ``field_id`` and ``body_id``. Teff, radius, mass
    and distance come from verified WS3 parameters only; the rest stays None and is explained in a note. A planet
    gets an orbit only when both its period and semi-major axis are published.
    """
    from .. import __version__

    new = spec.new or {}
    ident = snapshot["identity"]
    kind = _kind_from_otype(ident.get("object_type"))
    if kind is None:
        raise RegistryError(f"{spec.id}: SIMBAD type {ident.get('object_type')!r} is not a star or brown dwarf")
    if ident.get("match") not in ("name", "matched"):
        raise RegistryError(f"{spec.id}: identity '{ident.get('match')}' is not secure enough for a 3D model")
    gaia = snapshot.get("gaia")
    params = snapshot["parameters"]

    def verified_value(key: str) -> float | None:
        fact = snapshot_fact(snapshot, key)
        value = params.get(key, {}).get("value")
        return float(value) if fact is not None and isinstance(value, int | float) else None

    teff, radius, mass = verified_value("teff"), verified_value("radius"), verified_value("mass")
    root_id = new.get("body_id", spec.id)
    facts = [cross_check_fact(snapshot, k, label_suffix=False) for k in PARAM_KEYS]  # the drawn values themselves
    root = Body(
        id=root_id,
        name=new.get("name") or ident.get("display_name") or spec.id,
        kind=kind,  # type: ignore[arg-type]
        teff_k=teff,
        radius_km=radius * R_SUN_KM if radius is not None else None,
        mass_kg=mass * M_SUN_KG if mass is not None else None,
        spectral_type=ident.get("spectral_type"),
        appearance=Appearance(model="brown_dwarf" if kind == "brown_dwarf" else "star"),
        facts=[f for f in facts if f is not None],
    )
    bodies = [root]
    skipped = []
    for planet in snapshot.get("planets", []):
        name = planet["name"]
        if planet.get("period_d") is None or planet.get("semi_major_axis_au") is None:
            skipped.append(name)
            continue
        pid = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
        e = planet.get("eccentricity")
        ref = planet.get("reference")
        psrc = "NASA Exoplanet Archive" + (f" ({ref})" if ref else "") + CATALOG_SUFFIX
        pfacts = [
            Fact(label="Orbital period", value=f"{planet['period_d']}", unit="days", source=psrc, verified=True),
            Fact(label="Orbit size", value=f"{planet['semi_major_axis_au']}", unit="AU", source=psrc, verified=True),
        ]
        mass_kg = None
        if planet.get("mass_earth") is not None:
            label = "Minimum mass" if planet.get("mass_kind") == "Msini" else "Mass"
            pfacts.append(
                Fact(label=label, value=f"{planet['mass_earth']}", unit="Earth masses", source=psrc, verified=True)
            )
            mass_kg = planet["mass_earth"] * M_EARTH_KG
        radius_km = None
        if planet.get("radius_earth") is not None:
            calculated = bool(planet.get("radius_calculated"))
            pfacts.append(
                Fact(
                    label="Radius (model estimate)" if calculated else "Radius",
                    value=f"{planet['radius_earth']}",
                    unit="Earth radii",
                    source=psrc + ("; calculated from the mass, not measured" if calculated else ""),
                    verified=True,
                )
            )
            radius_km = planet["radius_earth"] * R_EARTH_KM
        bodies.append(
            Body(
                id=pid,
                name=name,
                kind="planet",
                radius_km=radius_km,
                mass_kg=mass_kg,
                orbit=Orbit(
                    parent=root_id,
                    semi_major_axis_au=planet["semi_major_axis_au"],
                    period_days=planet["period_d"],
                    eccentricity=e if e is not None else 0.0,
                    note=("Eccentricity not published: drawn circular. " if e is None else "")
                    + "Orbit orientation and phase not modelled.",
                ),
                appearance=Appearance(model="rocky" if (planet.get("mass_earth") or 0) < 10 else "gas_giant"),
                facts=pfacts,
            )
        )
    distance = verified_value("distance")
    motion = None
    if gaia is not None:
        motion = SpaceMotion(
            distance_pc=distance,
            parallax_mas=gaia.get("parallax") if (gaia.get("parallax") or 0) > 0 else None,
            pm_ra_cosdec_mas_yr=gaia.get("pmra"),
            pm_dec_mas_yr=gaia.get("pmdec"),
            radial_velocity_km_s=gaia.get("radial_velocity"),
            epoch=f"J{gaia.get('ref_epoch', 2016.0)}",
        )
    elif distance is not None:
        motion = SpaceMotion(distance_pc=distance)
    center = SkyCoord(ra=gaia["ra"], dec=gaia["dec"]) if gaia else None
    if center is None:
        raise RegistryError(f"{spec.id}: no Gaia DR3 position in the snapshot")
    notes = [_inputs_note([snapshot["slug"]], {snapshot["slug"]: snapshot})]
    unknown = []
    for key in drawn_params(root):
        if getattr(root, BODY_FIELDS[key]) is None:
            reasons = [r for r in (_snapshot_reason(snapshot, key), SPHEREX_GAP.get(key)) if r]
            if not reasons:
                reasons = ["the WS3 value is not verified"]
            unknown.append(f"{root.name}: {PARAM_NAMES[key]} ({'; '.join(reasons)})")
    for planet in bodies[1:]:
        if planet.radius_km is None:
            unknown.append(f"{planet.name}: radius (not in the NASA Exoplanet Archive)")
    if unknown:
        notes.append(UNKNOWN_NOTE_PREFIX + "; ".join(unknown) + ".")
    if skipped:
        notes.append(f"Planets without a published period and orbit size are not drawn: {', '.join(skipped)}.")
    if len(bodies) > 1:
        notes.append(
            "Planet appearance classes are display choices from the archive mass (rocky below 10 Earth masses, gas "
            "giant above), not a measured composition."
        )
    return SystemModel(
        id=spec.id,
        name=new.get("name") or root.name,
        description=new.get("description", ""),
        tags=["context-only"],
        center=center,
        motion=motion,
        field_id=new.get("field_id"),
        bodies=bodies,
        representation_note=CONTEXT_REPRESENTATION,
        provenance=Provenance(
            pipeline_version=pipeline_version or __version__,
            built_at=datetime.now(UTC),
            synthetic=False,
            notes=notes,
        ),
    )
