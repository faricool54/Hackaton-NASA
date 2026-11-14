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

    frames = rep.result.frames
    origin = rep.service.upper()
    if rep.service == "snapshot":
        origin = "committed SNAPSHOT (IRSA unavailable)"  # the WARNING note gives its date
    elif rep.stale:
        origin += " (EXPIRED cache: IRSA unavailable)"
    elif rep.from_cache:
        origin += " (cache)"
    notes = [f"WARNING: {w}" for w in rep.warnings]
    notes += [f"fallback after: {err}" for err in rep.errors]
    if rep.overflow:
        notes.append("WARNING: result truncated at MAXREC (raise ERRANTE_SIA_MAXREC or narrow the search)")
    if not args.summary:
        # Default: the SearchResult JSON alone on stdout (WS1-2 acceptance); diagnostics go to stderr.
        print(rep.result.model_dump_json(indent=2))
        print(f"{len(frames)} frames via {origin} in {rep.elapsed_s:.2f} s", file=sys.stderr)
        for note in notes:
            print(f"  {note}", file=sys.stderr)
        return 0

    print(
        f"{len(frames)} frames at ({rep.result.center.ra:.5f}, {rep.result.center.dec:.5f}) "
        f"r={rep.result.radius_deg:.6g} deg via {origin} in {rep.elapsed_s:.2f} s"
    )
    print(f"  collections searched: {', '.join(rep.collections)}")
    for note in notes:
        print(f"  {note}")
    if rep.n_duplicates:
        print(f"  duplicates removed (same obs_id+detector): {rep.n_duplicates}")
    if not frames:
        return 0

    from collections import Counter

    from astropy.time import Time

    from .data.epochs import group_visits, season_summary

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


def cmd_snapshot_search(args: argparse.Namespace) -> int:
    """(Re)generate committed search snapshots (data/index/search/<field-id>.json) from a live SIA query."""
    from .build import load_field_configs
    from .data import irsa

    cfgs = load_field_configs()
    if args.all == bool(args.field_id):
        print("Give one field id or --all (every field tagged 'official-target').", file=sys.stderr)
        return 2
    ids = [fid for fid, c in cfgs.items() if "official-target" in c.tags] if args.all else [args.field_id]
    unknown = [fid for fid in ids if fid not in cfgs]
    if unknown:
        print(f"Unknown field {unknown}. Known: {sorted(cfgs)}", file=sys.stderr)
        return 2
    out_dir = Path(args.out) if args.out else (irsa.SNAPSHOT_DIR or irsa.DEFAULT_SNAPSHOT_DIR)
    failed = []
    unverified = []  # written, but the live point check failed or did not run: CI rejects such a file
    for fid in ids:
        cfg = cfgs[fid]
        try:
            doc = irsa.fetch_snapshot(
                fid,
                cfg.ra,
                cfg.dec,
                name=cfg.name,
                radius_deg=irsa.SNAPSHOT_RADIUS_DEG if args.radius is None else args.radius,
                collections=args.collections,
                rounds=args.rounds,
                pause_s=args.pause,
            )
        except (irsa.SearchError, ValueError) as e:
            print(f"{fid}: snapshot NOT written: {e}", file=sys.stderr)
            failed.append(fid)
            continue
        path = irsa.write_snapshot(doc, irsa.snapshot_path(fid, out_dir))
        prov = doc["provenance"]
        print(
            f"{fid}: {prov['rows']} frames within {doc['radius_deg']:g} deg ({', '.join(doc['collections'])}) "
            f"via SIA at {prov['queried_utc']} in {prov['elapsed_s']:.1f} s -> {path} ({path.stat().st_size / 1024:.0f} KB)"
        )
        check = prov["point_check"]
        if "error" in check:
            print(f"  point check NOT run (SIA failed): {check['error']}", file=sys.stderr)
        elif check["only_live"] or check["only_replayed"]:
            print(
                f"  WARNING point check: live {check['rows_live']} vs replayed {check['rows_replayed']} "
                f"(only live: {check['only_live']}; only replayed: {check['only_replayed']})",
                file=sys.stderr,
            )
        else:
            print(
                f"  point check OK: the replay at the centre matches the live point search ({check['rows_live']} frames)"
            )
            continue
        unverified.append(fid)
        print(
            f"  {path.name} fails CI (test_committed_snapshot_files): run `errante snapshot-search {fid}` again "
            f"once SIA answers, or restore the committed file (git checkout -- <path>)",
            file=sys.stderr,
        )
    return 1 if failed or unverified else 0


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
    out = s.add_mutually_exclusive_group()
    out.add_argument("--json", action="store_true", help="print the SearchResult JSON (default)")
    out.add_argument(
        "--summary",
        action="store_true",
        help="print counts by collection, release, detector, visit and season instead of the JSON",
    )
    s.set_defaults(func=cmd_search)

    s = sub.add_parser(
        "snapshot-search",
        help="(re)generate the committed search snapshot of a field (IRSA-outage fallback, WS1)",
        description="Query IRSA SIA live around a field of config/fields.toml and write data/index/search/<id>.json. "
        "search_frames reads these snapshots only when SIA and TAP both fail and nothing is cached.",
    )
    s.add_argument("field_id", nargs="?", help="field id in config/fields.toml")
    s.add_argument("--all", action="store_true", help="every field tagged 'official-target' (the five R05 targets)")
    s.add_argument("--radius", type=float, default=None, help="snapshot disk radius [deg] (default: 0.1)")
    s.add_argument("--collections", default=None, help="comma-separated (default: ERRANTE_COLLECTIONS or dr1,qr3)")
    s.add_argument("--out", default=None, help="output directory (default: data/index/search)")
    s.add_argument("--rounds", type=int, default=6, help="SIA rounds when IRSA keeps failing (default: 6)")
    s.add_argument("--pause", type=float, default=20.0, help="seconds between rounds (default: 20)")
    s.set_defaults(func=cmd_snapshot_search)

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
