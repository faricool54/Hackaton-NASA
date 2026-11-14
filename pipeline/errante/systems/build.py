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
