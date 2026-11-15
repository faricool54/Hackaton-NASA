"""Offline bounded WS2 comparisons; export JSON and PNGs for API or a static site."""

import argparse
import asyncio
from pathlib import Path

from errante import settings as core
from errante.models import ComparisonRequest
from errante.products import ProductStore

from .publication import atomic_bytes
from .science_service import ScienceService
from .settings import Settings


async def precompute(source: Path, out: Path, work: Path, targets: list[str]):
    source, out, work = source.resolve(), out.resolve(), work.resolve()
    if out == source or out.is_relative_to(source) or source.is_relative_to(out):
        raise ValueError("Export and source fields must be separate")
    store = ProductStore(source)
    fields = targets or [f.id for f in store.read_manifest().fields]
    service = ScienceService(Settings(data_dir=out, live_cache_dir=work))
    try:
        for name in fields:
            field = store.read_field(name)
            result = await service.comparisons(field, ComparisonRequest())
            if not result.images:
                raise ValueError(f"No usable comparison images for {name}")
            payload = result.model_dump_json(indent=2).encode()
            atomic_bytes(out / "index" / f"{name}.json", payload)
            # Same typed document for a backend-free static client. PNG paths stay relative to /data.
            atomic_bytes(out / "fields" / name / "comparisons.json", payload)
            print(f"{name}: {len(result.images)} images, {len(result.failures)} failed inputs", flush=True)
    finally:
        service.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=core.PRODUCTS_DIR)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--work-dir", type=Path, default=core.CACHE_DIR / "comparison-precompute")
    parser.add_argument("--target", action="append", default=[])
    args = parser.parse_args()
    asyncio.run(precompute(args.source, args.out, args.work_dir, args.target))
