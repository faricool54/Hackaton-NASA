"""Command line: `errante <command>` (or `python -m errante.cli <command>`)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import settings
from .models import ALL_MODELS


def cmd_demo(args: argparse.Namespace) -> int:
    from .synthetic import build_demo

    out = build_demo(Path(args.out))
    print(f"Synthetic demo written to {out}")
    return 0


def cmd_schema(args: argparse.Namespace) -> int:
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    stale = []
    for name, model in ALL_MODELS.items():
        text = json.dumps(model.model_json_schema(), indent=2, sort_keys=True) + "\n"
        path = out / f"{name}.schema.json"
        if args.check:
            if not path.exists() or path.read_text(encoding="utf-8") != text:
                stale.append(path.name)
        else:
            path.write_text(text, encoding="utf-8")
    if args.check and stale:
        print(f"Schema out of date: {stale}. Run `make schema` and commit.", file=sys.stderr)
        return 1
    print("Schema OK" if args.check else f"Schema written to {out}")
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    from .products import ProductStore

    store = ProductStore(Path(args.dir))
    manifest = store.read_manifest()
    for fs in manifest.fields:
        field = store.read_field(fs.id)
        store.read_candidates(fs.id)
        store.read_known(fs.id)
        missing = [f.image for f in field.frames if not (store.field_dir(fs.id) / f.image).exists()]
        if missing:
            print(f"{fs.id}: missing images {missing}", file=sys.stderr)
            return 1
    print(f"OK: {len(manifest.fields)} fields valid in {store.root}")
    return 0


def cmd_search(args: argparse.Namespace) -> int:
    from .data.irsa import search_frames

    res = search_frames(args.ra, args.dec, detectors=args.detector)
    print(res.model_dump_json(indent=2))
    return 0


def cmd_build(args: argparse.Namespace) -> int:
    from .build import build_field, load_field_configs

    cfgs = load_field_configs()
    if args.field_id not in cfgs:
        print(f"Unknown field '{args.field_id}'. Known: {sorted(cfgs)}", file=sys.stderr)
        return 2
    try:
        build_field(cfgs[args.field_id], Path(args.out))
    except NotImplementedError as e:
        print(f"Build stopped at a stage that is not implemented yet: {e}", file=sys.stderr)
        return 3
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="errante", description="SPHEREx moving-object pipeline")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("demo", help="write the synthetic demo dataset")
    s.add_argument("--out", default=str(settings.DEMO_DIR))
    s.set_defaults(func=cmd_demo)

    s = sub.add_parser("schema", help="export JSON Schema of the contract")
    s.add_argument("--out", default=str(settings.REPO_ROOT / "shared" / "schema"))
    s.add_argument("--check", action="store_true", help="fail if committed schema is stale")
    s.set_defaults(func=cmd_schema)

    s = sub.add_parser("validate", help="validate a products directory against the contract")
    s.add_argument("--dir", default=str(settings.DEMO_DIR))
    s.set_defaults(func=cmd_validate)

    s = sub.add_parser("search", help="list SPHEREx frames covering a position (WS1)")
    s.add_argument("--ra", type=float, required=True)
    s.add_argument("--dec", type=float, required=True)
    s.add_argument("--detector", type=int, action="append")
    s.set_defaults(func=cmd_search)

    s = sub.add_parser("build", help="build real products for a field in config/fields.toml")
    s.add_argument("field_id")
    s.add_argument("--out", default=str(settings.PRODUCTS_DIR))
    s.set_defaults(func=cmd_build)

    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
