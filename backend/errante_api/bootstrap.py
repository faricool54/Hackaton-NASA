"""Seed a private runtime product tree without overwriting existing user products."""

import os
import shutil
from pathlib import Path

from errante.products import ProductStore

from .publication import AtomicProductStore, publication_lock


def _seed_frame_flags(source: ProductStore, destination: AtomicProductStore) -> None:
    """Fill missing flags on matching curated snapshots in an existing volume."""
    for summary in source.read_manifest().fields:
        if summary.synthetic or not destination.has_field(summary.id):
            continue
        seed = source.read_field(summary.id)
        if not seed.frame_flags:
            continue
        live = destination.read_field(summary.id)
        if live.provenance.synthetic or live.provenance.built_at != seed.provenance.built_at or live.grid != seed.grid:
            continue
        seed_frames = {frame.id: frame for frame in seed.frames}
        missing = {
            frame.id: seed.frame_flags[frame.id]
            for frame in live.frames
            if frame.id in seed.frame_flags and frame.id not in live.frame_flags and frame == seed_frames[frame.id]
        }
        if missing:
            live.frame_flags.update(missing)
            destination.write_field(live)


def seed_products(source: Path, destination: Path) -> None:
    source, destination = source.resolve(), destination.resolve()
    if source == destination or source.is_relative_to(destination) or destination.is_relative_to(source):
        raise ValueError("Seed and runtime products must be separate directories")
    destination.mkdir(parents=True, exist_ok=True)
    with publication_lock(destination):
        manifest = destination / "manifest.json"
        if manifest.exists():
            runtime = AtomicProductStore(destination)
            runtime.read_manifest()  # A corrupt existing tree needs operator attention.
            seed = ProductStore(source)
            if seed.manifest_path.is_file():
                _seed_frame_flags(seed, runtime)
            return
        store = ProductStore(source)
        doc = store.read_manifest()
        if doc.synthetic or not doc.fields:
            raise ValueError("Production seed must contain real fields")
        # Missing manifest after a failed first copy can be retried safely. Never replace a live manifest.
        for path in source.iterdir():
            if path.name == "manifest.json" or path.name.startswith("."):
                continue
            if path.is_dir():
                shutil.copytree(path, destination / path.name, dirs_exist_ok=True)
            else:
                shutil.copy2(path, destination / path.name)
        temporary = destination / ".seed-manifest"
        shutil.copy2(store.manifest_path, temporary)
        os.replace(temporary, manifest)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    seed_products(args.source, args.destination)
