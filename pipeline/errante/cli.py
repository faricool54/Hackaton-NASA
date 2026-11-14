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
    from .systems.build import validate_hierarchy

    for ss in manifest.systems:
        validate_hierarchy(store.read_system(ss.id))
    print(f"OK: {len(manifest.fields)} fields and {len(manifest.systems)} systems valid in {store.root}")
    return 0


def cmd_search(args: argparse.Namespace) -> int:
    from collections import Counter

    from astropy.time import Time

    from .data.epochs import group_visits, season_summary
    from .data.irsa import SearchError, search_frames_report

    try:
        rep = search_frames_report(
            args.ra,
            args.dec,
            args.radius,
            detectors=args.detector,
            mjd_min=args.mjd_min,
            mjd_max=args.mjd_max,
            collections=args.collections,
            use_cache=not args.no_cache,
        )
    except (SearchError, ValueError) as e:
        print(f"Search failed: {e}", file=sys.stderr)
        return 2
    if args.json:
        print(rep.result.model_dump_json(indent=2))
        return 0

    frames = rep.result.frames
    origin = rep.service.upper()
    if rep.stale:
        origin += " (EXPIRED cache: IRSA unavailable)"
    elif rep.from_cache:
        origin += " (cache)"
    print(
        f"{len(frames)} frames at ({rep.result.center.ra:.5f}, {rep.result.center.dec:.5f}) "
        f"r={rep.result.radius_deg:.6g} deg via {origin} in {rep.elapsed_s:.2f} s"
    )
    print(f"  collections searched: {', '.join(rep.collections)}")
    for err in rep.errors:
        print(f"  fallback after: {err}")
    if rep.overflow:
        print("  WARNING: result truncated at MAXREC (raise ERRANTE_SIA_MAXREC or narrow the search)")
    if rep.n_duplicates:
        print(f"  duplicates removed (same obs_id+detector): {rep.n_duplicates}")
    if not frames:
        return 0

    def counts(values) -> str:
        return ", ".join(f"{k}: {n}" for k, n in sorted(Counter(values).items()))

    print(f"  by collection: {counts(r.collection or '?' for r in rep.rows)}")
    print(f"  by release:    {counts(f.release for f in frames)}")
    print(f"  by detector:   {counts(f'D{f.detector}' for f in frames)}")
    print(f"  visits (gap > 6 h): {len(group_visits(frames))}")
    print("  seasons (gap > 30 d):")
    for i, s in enumerate(season_summary(frames), 1):
        d0, d1 = (Time(m, format="mjd").to_value("iso", subfmt="date") for m in (s["mjd_min"], s["mjd_max"]))
        print(
            f"    {i}. MJD {s['mjd_min']:.2f}-{s['mjd_max']:.2f} ({d0} -> {d1}): {s['n']} frames, {s['visits']} visits"
        )
    return 0


def cmd_systems(args: argparse.Namespace) -> int:
    from .products import ProductStore
    from .systems.build import write_systems
    from .systems.catalog import curated_systems

    store = ProductStore(Path(args.out))
    ids = write_systems(store, curated_systems())
    manifest = store.rebuild_manifest()
    print(f"3D systems written to {store.root / 'systems'}: {ids}")
    if not manifest.fields:
        print("Note: no fields in this directory yet; the backend and web keep using the demo until one is built.")
    return 0


def cmd_build(args: argparse.Namespace) -> int:
    from .build import build_field, load_field_configs

    cfgs = load_field_configs()
    if args.field_id not in cfgs:
        print(f"Unknown field '{args.field_id}'. Known: {sorted(cfgs)}", file=sys.stderr)
        return 2
    try:
        build_field(cfgs[args.field_id], Path(args.out), analyze=args.analyze)
    except NotImplementedError as e:
        print(f"Build stopped at a stage that is not implemented yet: {e}", file=sys.stderr)
        return 3
    except ValueError as e:
        print(f"Build failed: {e}", file=sys.stderr)
        return 2
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="errante", description="SPHEREx temporal sky explorer pipeline")
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
    s.add_argument("--detector", type=int, action="append", choices=range(1, 7), help="repeat for several")
    s.add_argument("--radius", type=float, default=0.0, help="search radius [deg]; 0 = point (1 arcsec)")
    s.add_argument("--mjd-min", type=float, default=None)
    s.add_argument("--mjd-max", type=float, default=None)
    s.add_argument(
        "--collections",
        default=None,
        help="comma-separated IRSA collections (default: ERRANTE_COLLECTIONS or spherex_dr1,spherex_qr3; "
        "deep fields: spherex_dr1_deep,spherex_qr3_deep)",
    )
    s.add_argument("--no-cache", action="store_true", help="ignore and do not write the query cache")
    s.add_argument("--json", action="store_true", help="print the SearchResult JSON instead of the summary")
    s.set_defaults(func=cmd_search)

    s = sub.add_parser("systems", help="write the curated 3D system models (WS7)")
    s.add_argument("--out", default=str(settings.PRODUCTS_DIR))
    s.set_defaults(func=cmd_systems)

    s = sub.add_parser("build", help="build real products for a field in config/fields.toml")
    s.add_argument("field_id")
    s.add_argument("--out", default=str(settings.PRODUCTS_DIR))
    s.add_argument("--analyze", action="store_true", help="also run automatic detection and catalog matching")
    s.set_defaults(func=cmd_build)

    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
