"""Overlay validated WS4 snapshots on an already built static real dataset (no manifest changes)."""

import argparse
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def export(out: Path):
    from errante.models import ComparisonResponse, LightCurveProduct
    from errante.products import ProductStore
    from errante_api.comparison_snapshots import read_snapshot
    from errante_api.lightcurve_store import LightCurveStore

    curated = ROOT / "backend" / "errante_api" / "curated"
    for path in (curated / "lightcurves").glob("*.json"):
        product = LightCurveProduct.model_validate_json(path.read_bytes())
        destination = out / "lightcurves" / f"{product.target_id}.json"
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, destination)
    index = out / "lightcurves.json"
    index.parent.mkdir(parents=True, exist_ok=True)
    index.write_text(LightCurveStore(curated / "lightcurves").index().model_dump_json(), encoding="utf-8")
    for path in (curated / "comparisons" / "index").glob("*.json"):
        product = ComparisonResponse.model_validate_json(path.read_bytes())
        read_snapshot(ROOT / "data/products", ProductStore(ROOT / "data/products").read_field(product.field_id))
        destination = out / "fields" / product.field_id / "comparisons.json"
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, destination)
        for image in product.images:
            destination = out / image.image
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(curated / "comparisons" / image.image, destination)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=ROOT / "frontend/dist/data/real")
    args = parser.parse_args()
    export(args.out.resolve())
