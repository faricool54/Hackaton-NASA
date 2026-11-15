"""Write 3D system products (WS7)."""

from __future__ import annotations

from ..models import SystemModel
from ..products import ProductStore


def validate_hierarchy(system: SystemModel) -> None:
    """Every orbit parent must exist, ids must be unique and there must be no cycles."""
    ids = [b.id for b in system.bodies]
    if len(ids) != len(set(ids)):
        raise ValueError(f"{system.id}: duplicate body ids")
    parents = {b.id: (b.orbit.parent if b.orbit else None) for b in system.bodies}
    # Check every parent first: the cycle walk below indexes parents[...] up the whole chain.
    for bid, parent in parents.items():
        if parent is not None and parent not in parents:
            raise ValueError(f"{system.id}: body '{bid}' orbits unknown parent '{parent}'")
    for bid, parent in parents.items():
        seen = {bid}
        while parent is not None:
            if parent in seen:
                raise ValueError(f"{system.id}: orbit cycle through '{parent}'")
            seen.add(parent)
            parent = parents[parent]
    if not any(p is None for p in parents.values()):
        raise ValueError(f"{system.id}: no root body (one body must have orbit=None)")


def write_systems(store: ProductStore, systems: list[SystemModel]) -> list[str]:
    """Validate and write each system. Call ``store.rebuild_manifest()`` afterwards."""
    for system in systems:
        validate_hierarchy(system)
        store.write_system(system)
    return [s.id for s in systems]


def synthetic_system_ids(store: ProductStore) -> list[str]:
    """Ids of the synthetic systems already on disk under ``<root>/systems``."""
    paths = sorted((store.root / "systems").glob("*.json"))
    return [p.stem for p in paths if store.read_system(p.stem).provenance.synthetic]


def write_real_systems(store: ProductStore, systems: list[SystemModel]) -> tuple[list[str], list[str]]:
    """Write only the non-synthetic systems, for a real dataset such as data/products (AGENTS.md rule 3).

    Returns ``(written ids, skipped synthetic ids)``. Raises ``ValueError`` and writes nothing when the
    folder already holds a synthetic system: ``rebuild_manifest`` lists every file in ``systems/``, so
    it would publish it next to the real fields. Call ``store.rebuild_manifest()`` afterwards.
    """
    stale = synthetic_system_ids(store)
    if stale:
        raise ValueError(
            f"{store.root / 'systems'} already holds synthetic systems {stale}; remove them first, "
            "or the manifest of this real dataset would list them"
        )
    real = [s for s in systems if not s.provenance.synthetic]
    skipped = [s.id for s in systems if s.provenance.synthetic]
    return write_systems(store, real), skipped
