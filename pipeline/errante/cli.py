"""Command line: `errante <command>` (or `python -m errante.cli <command>`)."""

from __future__ import annotations

import argparse
import json
import math
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
        images = [f.image for f in field.frames] + [c.image for c in field.composites]
        missing = [image for image in images if not (store.field_dir(fs.id) / image).exists()]
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


POINT_NO_SAMPLES = 3
"""`errante point` exit code when the series has no sample at all (nothing read: every frame timed out, failed
or missed the pixel, or none was found). 2 = the search failed or the input is invalid; 0 = at least one sample."""


def cmd_point(args: argparse.Namespace) -> int:
    from .data.irsa import SearchError
    from .data.point import point_series

    try:
        series = point_series(
            args.ra,
            args.dec,
            box_px=args.box,
            detectors=args.detector,
            mjd_min=args.mjd_min,
            mjd_max=args.mjd_max,
            collections=args.collections,
            max_frames=args.max_frames,
            max_workers=args.workers,
            use_cache=not args.no_cache,
            deadline_s=args.deadline,
        )
    except (SearchError, ValueError) as e:
        print(f"Point series failed: {e}", file=sys.stderr)
        return 2
    paths = series.save(args.out) if args.out else None
    t = series.timings
    if not args.summary:
        doc = {
            "ra": series.ra,
            "dec": series.dec,
            "box_px": series.box_px,
            "search": series.search,
            "timings": t,
            "failures": [{"obs_id": f.obs_id, "detector": f.detector, "reason": r} for f, r in series.failures],
            "samples": series.summary_rows(),
        }
        print(json.dumps(doc, indent=1))
    else:
        from collections import Counter

        if t.get("from_cache"):
            origin = "cache"
        else:  # what was READ, not what was asked: timed-out and failed frames are not "read"
            origin = f"read from S3: {len(series.samples)} of {t.get('frames')} frames"
            if t.get("timed_out"):
                origin += f", {t['timed_out']} timed out"
        print(
            f"{len(series.samples)} samples at ({series.ra:.5f}, {series.dec:.5f}), box {series.box_px} px "
            f"({origin}) in {t.get('total_s')} s"
        )
        s = series.search
        print(
            f"  search: {s.get('n_found')} frames via {s.get('service')}"
            f"{' (cache)' if s.get('from_cache') else ''}{' STALE' if s.get('stale') else ''}"
            f"{' TRUNCATED' if s.get('overflow') else ''}, {s.get('n_selected')} selected"
        )
        if not t.get("from_cache"):
            print(
                f"  S3: {t.get('requests')} requests ({t.get('requests_per_frame')}/frame), "
                f"{(t.get('bytes') or 0) / 1e6:.1f} MB ({(t.get('bytes_per_frame') or 0) / 1e3:.0f} KB/frame), "
                f"fetch {t.get('fetch_s')} s, layouts {t.get('layouts')}"
            )
        by_det: dict[int, list] = {}
        for smp in series.samples:
            by_det.setdefault(smp.detector, []).append(smp)
        for det, smps in sorted(by_det.items()):
            lam = [x.wavelength_um for x in smps if x.wavelength_um is not None]
            rng = f"{min(lam):.3f}-{max(lam):.3f} um" if lam else "no wavelength"
            rel = ", ".join(f"{k}: {n}" for k, n in sorted(Counter(x.release for x in smps).items()))
            print(f"  D{det}: {len(smps)} samples, {rng}, MJD {smps[0].mjd:.2f}-{smps[-1].mjd:.2f} ({rel})")
        if series.failures:
            reasons = Counter(r.split(":", 1)[0] for _, r in series.failures)
            print(f"  failures: {len(series.failures)} ({', '.join(f'{k}: {n}' for k, n in reasons.items())})")
        if t.get("timed_out"):
            print("  deadline cut, per season (samples read / frames asked):")
            for c in t.get("seasons") or []:
                cut = f", {c['timed_out']} timed out" if c.get("timed_out") else ""
                print(
                    f"    {c['release']} MJD {c['mjd_min']:.1f}-{c['mjd_max']:.1f}: {c['samples']}/{c['frames']}{cut}"
                )
    if t.get("wave_errors"):
        print(
            f"WARNING: {t['wave_errors']} samples have no wavelength because S3 failed (not cached: ask again)",
            file=sys.stderr,
        )
    if t.get("timed_out"):
        print(f"WARNING: {t['timed_out']} frames not read within --deadline (not cached)", file=sys.stderr)
    if paths:
        print(f"Wrote {paths[0]} and {paths[1]}", file=sys.stderr)
    if not series.samples:
        print(
            f"ERROR: no sample at ({series.ra:.5f}, {series.dec:.5f}): {t.get('frames')} frames, "
            f"{len(series.failures)} failed or cut (exit {POINT_NO_SAMPLES})",
            file=sys.stderr,
        )
        return POINT_NO_SAMPLES
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


def cmd_cube_spectrum(args: argparse.Namespace) -> int:
    from .data.cube import cube_spectrum

    try:
        spec = cube_spectrum(
            args.ra,
            args.dec,
            aperture_px=args.aperture,
            with_nhits=args.nhits,
            with_flags=args.flags,
            use_cache=not args.no_cache,
        )
    except ValueError as e:
        print(f"Invalid request: {e}", file=sys.stderr)
        return 2
    except OSError as e:
        print(f"Cube read failed: {e}", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(spec.to_dict(), indent=2))
        return 0

    t = spec.timings
    print(
        f"SPHEREx DR1 cube spectrum at ({spec.ra:.6f}, {spec.dec:+.6f}): tile Norder{spec.tile.order}/Npix{spec.tile.npix} "
        f"pixel x={spec.pixel[0]} y={spec.pixel[1]} (centre {spec.pixel_center[0]:.6f}, {spec.pixel_center[1]:+.6f}; "
        f'{spec.pixel_scale_arcsec:.2f}"/px)'
    )
    ap = f"aperture r={spec.aperture_px} px ({spec.n_pixels} px)" if spec.aperture_px else "single pixel"
    if t.get("from_cache"):
        how = f"from the result cache in {t.get('total_s', 0):.3f} s"
    else:
        how = (
            f"via {spec.source} in {t.get('total_s', 0):.2f} s ({t.get('mode', '?')}: "
            f"{t.get('header_requests', 0)} header + {t.get('pixel_requests', 0)} pixel range requests)"
        )
    print(f"  {ap}; {int(spec.valid.sum())}/{len(spec.flux)} valid planes; {how}")
    print(f"  {spec.tile.url}")
    for note in spec.notes:
        print(f"  note: {note}")
    print(
        f"  {'k':>3} {'det':>3} {'ch':>3} {'lambda_um':>9} {'dlam_um':>7} {'flux[' + spec.unit + ']':>14} {'nhits':>5}"
    )
    for k in range(len(spec.flux)):
        flux = f"{spec.flux[k]:14.5g}" if spec.valid[k] else f"{'--':>14}"
        hits = "" if spec.nhits is None else f"{int(spec.nhits[k]):5d}"
        print(
            f"  {k:3d} {int(spec.detector[k]):3d} {int(spec.channel[k]):3d} "
            f"{spec.wavelength_um[k]:9.4f} {spec.bandwidth_um[k]:7.4f} {flux} {hits}"
        )
    return 0


def cmd_systems(args: argparse.Namespace) -> int:
    from .products import ProductStore
    from .systems.build import write_real_systems, write_systems
    from .systems.catalog import curated_systems

    store = ProductStore(Path(args.out))
    if args.real_only:
        try:
            ids, skipped = write_real_systems(store, curated_systems())
        except ValueError as e:
            print(f"error: {e}", file=sys.stderr)
            return 1
        if skipped:
            print(f"Skipped synthetic systems (not for a real dataset): {skipped}")
    else:
        ids = write_systems(store, curated_systems())
    manifest = store.rebuild_manifest()
    print(f"3D systems written to {store.root / 'systems'}: {ids}")
    if not manifest.fields:
        print("Note: no fields in this directory yet; the backend and web keep using the demo until one is built.")
    return 0


def _positive_int(text: str) -> int:
    value = int(text)
    if value < 1:
        raise argparse.ArgumentTypeError(f"must be a positive integer, got {text}")
    return value


def cmd_build(args: argparse.Namespace) -> int:
    from .build import build_field, load_field_configs

    cfgs = load_field_configs()
    if args.field_id not in cfgs:
        print(f"Unknown field '{args.field_id}'. Known: {sorted(cfgs)}", file=sys.stderr)
        return 2
    overrides = {}
    if args.max_frames is not None:
        overrides["max_frames"] = args.max_frames
    if args.detectors:
        overrides["detectors"] = sorted(set(args.detectors))
    try:
        build_field(
            cfgs[args.field_id],
            Path(args.out),
            analyze=args.analyze,
            overrides=overrides,
            jhk_topup=not args.no_jhk_topup,
        )
    except NotImplementedError as e:
        print(f"Build stopped at a stage that is not implemented yet: {e}", file=sys.stderr)
        return 3
    except ValueError as e:
        print(f"Build failed: {e}", file=sys.stderr)
        return 2
    return 0


def cmd_compare(args: argparse.Namespace) -> int:
    """Season coadds + flux-matched season differences of a built field (WS2-7)."""
    from .imaging.compare import compare_field, load_from_cutouts
    from .products import ProductStore

    store = ProductStore(Path(args.dir))
    if not store.has_field(args.field_id):
        print(f"No built field '{args.field_id}' in {args.dir}; run `errante build` first.", file=sys.stderr)
        return 2
    field = store.read_field(args.field_id)
    try:
        meta = compare_field(field, store.field_dir(field.id), load_from_cutouts(field))
    except NotImplementedError as e:
        print(f"Compare stopped at a stage that is not implemented yet: {e}", file=sys.stderr)
        return 3
    except ValueError as e:
        print(f"Compare failed: {e}", file=sys.stderr)
        return 2
    print(
        f"{field.id}: {len(meta['coadds'])} season coadds and {len(meta['differences'])} differences in "
        f"{store.field_dir(field.id) / 'compare'}"
    )
    return 0


def _finite_json(value):
    """NaN/inf -> None (strict JSON for the browser), recursively."""
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, dict):
        return {k: _finite_json(v) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [_finite_json(v) for v in value]
    return value


def cmd_spectrum(args: argparse.Namespace) -> int:
    """Forced photometry of one position on every SPHEREx exposure (WS2, for WS3-5)."""
    from dataclasses import asdict

    from .imaging.photometry import spectrum_at

    pm = None
    if args.pm_ra is not None or args.pm_dec is not None:
        pm = (args.pm_ra or 0.0, args.pm_dec or 0.0, args.pm_epoch)
    try:
        res = spectrum_at(args.ra, args.dec, pm=pm, detectors=args.detector, max_frames=args.max_frames)
    except NotImplementedError as e:
        print(f"Spectrum stopped at a stage that is not implemented yet: {e}", file=sys.stderr)
        return 3
    except ValueError as e:
        print(f"Spectrum failed: {e}", file=sys.stderr)
        return 2
    doc = {
        "ra": res.ra,
        "dec": res.dec,
        "proper_motion": None if pm is None else {"pm_ra_masyr": pm[0], "pm_dec_masyr": pm[1], "epoch_mjd": pm[2]},
        "notes": res.notes,
        "failures": [{"frame_id": f, "reason": r} for f, r in res.failures],
        "points": [asdict(pt) for pt in res.points],
    }
    text = json.dumps(_finite_json(doc), indent=2, allow_nan=False)
    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text + "\n", encoding="utf-8")
    for note in res.notes:
        print(note)
    usable = [pt for pt in res.points if pt.usable]
    for det in sorted({pt.detector for pt in usable}):
        mine = [pt for pt in usable if pt.detector == det]
        lam = [pt.wavelength_um for pt in mine]
        flux = [pt.flux_mjy for pt in mine]
        print(
            f"D{det}: {len(mine)} points, {min(lam):.3f}-{max(lam):.3f} um, median flux {sorted(flux)[len(flux) // 2]:.3g} mJy"
        )
    if not args.out:
        print(text)
    return 0


def _write_or_print(doc: dict, out: str | None, show: bool) -> None:
    text = json.dumps(_finite_json(doc), indent=1, allow_nan=False)
    if out:
        path = Path(out)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text + "\n", encoding="utf-8")
        print(f"Wrote {path}", file=sys.stderr)
    if show:
        print(text)


def cmd_position_spectrum(args: argparse.Namespace) -> int:
    """Spectrum of a position with seasons, saturation and a variability check (WS3-5, on WS2's photometry)."""
    from .data.irsa import SearchError
    from .science.spectra import interpret_spectrum, interpretation_notes, position_spectrum

    pm = None
    if args.pm_ra is not None or args.pm_dec is not None:
        pm = (args.pm_ra or 0.0, args.pm_dec or 0.0, args.pm_epoch)
    try:
        spec = position_spectrum(args.ra, args.dec, pm=pm, detectors=args.detector, max_frames=args.max_frames)
    except (SearchError, ValueError) as e:
        print(f"Spectrum failed: {e}", file=sys.stderr)
        return 2
    _write_or_print(spec.to_dict(), args.out, args.json)
    if args.json:
        return 0 if spec.samples else 4
    print(
        f"SPHEREx spectrum at ({spec.ra:.6f}, {spec.dec:+.6f}): {len(spec.usable())} of {len(spec.samples)} exposures usable"
    )
    for s in spec.seasons:
        lam = f"{s.wavelength_min_um:.3f}-{s.wavelength_max_um:.3f} um" if s.wavelength_min_um else "no usable point"
        print(
            f"  season {s.season}: {s.date_min[:10]} -> {s.date_max[:10]}, {s.n_usable}/{s.n_points} usable "
            f"({s.n_saturated} saturated), D{','.join(map(str, s.detectors))}, {lam}"
        )
    for w in spec.warnings:
        print(f"  WARNING: {w}")
    for n in spec.notes:
        print(f"  note: {n}")
    for n in interpretation_notes(interpret_spectrum(spec)):
        print(f"  interpretation: {n}")
    if spec.failures:
        print(f"  {len(spec.failures)} exposures could not be measured")
    return 0 if spec.samples else 4


def cmd_lightcurve(args: argparse.Namespace) -> int:
    """Light curve of a position within narrow wavelength bins, with comparison stars (WS3-9)."""
    from .data.irsa import SearchError
    from .science.variability import false_alarm_text, light_curve, matched_pairs

    cols = args.collections
    if args.deep:
        cols = "spherex_dr1,spherex_qr3,spherex_dr1_deep,spherex_qr3_deep"
    try:
        lc = light_curve(
            args.ra,
            args.dec,
            detectors=args.detector,
            lambda_bin_frac=args.bin_frac,
            method=args.method,
            collections=cols,
            deadline_s=args.deadline,
            box_px=args.box,
            max_frames=args.max_frames,
            mjd_min=args.mjd_min,
            mjd_max=args.mjd_max,
            min_bin_span_days=args.min_bin_span,
            period=True if args.period else None,
            n_bootstrap=args.bootstrap,
            n_permutations=args.permutations,
        )
    except (SearchError, ValueError) as e:
        print(f"Light curve failed: {e}", file=sys.stderr)
        return 2
    doc = lc.to_dict()
    doc["matched_pairs"] = matched_pairs(lc, max_frac=lc.lambda_bin_frac)
    _write_or_print(doc, args.out, args.json)
    if args.json:
        return 0 if lc.used() else 4
    print(f"SPHEREx light curve at ({lc.ra:.6f}, {lc.dec:+.6f}), method {lc.method}, flux in {lc.unit}")
    for n in lc.notes:
        print(f"  {n}")
    for det, s in sorted(lc.summary.items()):
        ctl = lc.control.get(det, {})
        print(
            f"  D{det}: {s.get('n', 0)} points in {s['n_bins']} bins, robust scatter {s.get('robust_sigma_mag', 0):.3f} mag, "
            f"p5-p95 {s.get('p5_to_p95_mag', 0):.2f} mag; control {ctl.get('robust_sigma_mag', float('nan')):.3f} mag "
            f"({ctl.get('n_stars', 0)} stars); excluded {s['excluded'] or 'none'}"
        )
    pairs = doc["matched_pairs"]
    if pairs:
        print(
            f"  matched pairs (same detector, |dlambda|/lambda < {lc.lambda_bin_frac:.1%}, >= 30 d apart): {len(pairs)}"
        )
        for p in pairs[:20]:
            ens = "" if p["ensemble_mag"] is None else f", comparisons {p['ensemble_mag']:+.3f} ({p['n_ensemble']})"
            print(
                f"    D{p['detector']} {p['date_a'][:10]} -> {p['date_b'][:10]} at {p['wavelength_a_um']:.4f}/"
                f"{p['wavelength_b_um']:.4f} um: {p['delta_mag']:+.3f} mag{ens}"
            )
    if lc.period and lc.period.significant:  # the notes above already say when it is not
        pe = lc.period
        err = f" +- {pe.period_err_formal_days:.1f} (formal)" if pe.period_err_formal_days else ""
        boot = (
            f", bootstrap 95 % {pe.bootstrap_95_days[0]:.0f}-{pe.bootstrap_95_days[1]:.0f} d"
            if pe.bootstrap_95_days
            else ""
        )
        other = ", ".join(f"{p:.0f} d" for p, _ in pe.peaks[1:])
        print(
            f"  period {pe.period_days:.1f} d{err}{boot}, false-alarm {false_alarm_text(pe)}; "
            f"other peaks {other or 'none'}"
        )
    if lc.period:
        print(f"  caveat: {lc.period.caveat}")
    if lc.failures:
        print(f"  {len(lc.failures)} exposures not read or not on the detector")
    return 0 if lc.used() else 4


def _say(text: str) -> None:
    """print() that never dies on a console code page without the character (Windows cp1252)."""
    enc = getattr(sys.stdout, "encoding", None) or "utf-8"
    print(text.encode(enc, errors="replace").decode(enc, errors="replace"))


def cmd_object(args: argparse.Namespace) -> int:
    """Catalog context of a position or a name: identity, Gaia DR3, VSX, planets, 2MASS/AllWISE (WS3-10)."""
    from .science.context import ContextError, object_context, physical_parameters

    if args.name is None and (args.ra is None or args.dec is None):
        print("give --ra and --dec, or --name", file=sys.stderr)
        return 2
    if args.name is not None and (args.ra is not None or args.dec is not None):
        print("give either --ra/--dec or --name, not both", file=sys.stderr)
        return 2
    try:
        ctx = object_context(
            args.ra,
            args.dec,
            name=args.name,
            epoch_mjd=args.epoch_mjd,
            radius_arcsec=args.radius,
            use_cache=not args.no_cache,
            offline=args.offline,
        )
    except (ContextError, ValueError) as e:
        print(f"Object context failed: {e}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(ctx.to_dict(), indent=2, allow_nan=False))
        return 0
    head = ctx.display_name or "(no catalogued object)"
    kind = ", ".join(x for x in (ctx.main_id, ctx.object_type_label or ctx.object_type, ctx.spectral_type) if x)
    _say(f"{head}" + (f"  [{kind}]" if kind else ""))
    if ctx.ra is not None:
        _say(f"Position at MJD {ctx.epoch_mjd:.1f}: {ctx.ra:.6f} {ctx.dec:+.6f}  ({ctx.position_source})")
    g = ctx.gaia.source if ctx.gaia else None
    if g is not None:
        _say(
            f'Gaia DR3 {g.source_id}: {g.sep_arcsec:.2f}" from the query at the epoch, G = {g.phot_g_mean_mag}, '
            f"plx = {g.parallax} mas, pm = ({g.pmra}, {g.pmdec}) mas/yr, RUWE = {g.ruwe} "
            f"[{ctx.gaia.method}{', AMBIGUOUS' if ctx.gaia.ambiguous else ''}"
            f"{', FAR FROM THE CLICK' if ctx.gaia.loose else ''}]"
        )
    else:
        _say("Gaia DR3: no counterpart")
    _say("Physical parameters (catalog values; 'unknown' = not measured):")
    for f in physical_parameters(ctx):
        mark = "verified" if f.verified else "not verified"
        _say(f"  {f.label:<22} {f.value} {f.unit or ''}  [{mark}]")
        if f.source:
            _say(f"      {f.source}")
    if ctx.planets:
        _say("Confirmed planets (NASA Exoplanet Archive pscomppars):")
        for pl in ctx.planets:
            _say(
                f"  {pl.name}: P = {pl.period_d} d, a = {pl.semi_major_axis_au} AU, "
                f"{pl.mass_kind or 'mass'} = {pl.mass_earth} M_earth ({pl.discovery_method}, {pl.discovery_year})"
            )
    if ctx.photometry:
        _say("Context photometry from OTHER missions (Vega mag; not SPHEREx):")
        for m in ctx.photometry:
            lim = " (upper limit)" if m.upper_limit else ""
            who = ", IDENTITY UNCERTAIN" if m.identity_uncertain else ""
            _say(
                f"  {m.mission:<6} {m.band:<3} {m.wavelength_um:>6.3f} um  {m.mag}{lim}  "
                f"[{m.designation}, q={m.quality}{who}]"
            )
    for w in ctx.warnings:
        _say(f"WARNING: {w}")
    _say("Sources:")
    for p in ctx.provenance:
        flag = " (cached)" if p.cached else ""
        _say(f"  {p.service:<11} {p.status:<8} {p.retrieved_utc or '-'}{flag}  {p.note or ''}")
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
        "point",
        help="stamps of every SPHEREx exposure at a position, read from S3 (WS1)",
        epilog=f"Exit codes: 0 = at least one sample; 2 = the archive search failed or invalid input; "
        f"{POINT_NO_SAMPLES} = no sample at all (every frame timed out, failed or missed the pixel; the JSON "
        "is still printed).",
    )
    s.add_argument("--ra", type=float, required=True)
    s.add_argument("--dec", type=float, required=True)
    s.add_argument(
        "--box",
        type=int,
        default=11,
        help="stamp side [px] (default 11; 1 px = 6.15 arcsec; >= 15 for imaging.photometry's sky annulus)",
    )
    s.add_argument("--detector", type=int, action="append", choices=range(1, 7), help="repeat for several")
    s.add_argument("--mjd-min", type=float, default=None)
    s.add_argument("--mjd-max", type=float, default=None)
    s.add_argument(
        "--collections",
        default=None,
        help="comma-separated IRSA collections (default: spherex_dr1,spherex_qr3; deep fields: "
        "spherex_dr1_deep,spherex_qr3_deep)",
    )
    s.add_argument("--max-frames", type=int, default=None, help="cap, spread over detectors and visits")
    s.add_argument("--workers", type=int, default=None, help="max S3 requests in flight (default 48, at most 64)")
    s.add_argument(
        "--deadline",
        type=float,
        default=None,
        help="seconds for the whole call, archive search included (a cold search takes 1-9 s via SIA; under ~20 s "
        "TAP cannot stand in for a hung SIA); frames not read by then are failures (TimeoutError), not cached; "
        "what is read is spread over every season",
    )
    s.add_argument("--out", default=None, help="write the series to OUT.npz + OUT.json")
    s.add_argument("--no-cache", action="store_true", help="ignore and do not write the series cache")
    s.add_argument("--summary", action="store_true", help="human-readable summary instead of the JSON")
    s.set_defaults(func=cmd_point)

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

    s = sub.add_parser(
        "cube-spectrum", help="SPHEREx spectrum (102 planes) of a position from the DR1 all-sky cube on S3 (WS1)"
    )
    s.add_argument("--ra", type=float, required=True)
    s.add_argument("--dec", type=float, required=True)
    s.add_argument("--aperture", type=int, default=0, help='radius in cube pixels (12.9"); 0 = single pixel')
    s.add_argument("--flags", action="store_true", help="also read the coadded FLAGS bits of the centre pixel")
    s.add_argument("--nhits", action="store_true", help="also read NHITS, the input samples per plane (2x requests)")
    s.add_argument("--no-cache", action="store_true", help="ignore and do not write the result cache")
    s.add_argument("--json", action="store_true", help="print the full result as JSON")
    s.set_defaults(func=cmd_cube_spectrum)

    s = sub.add_parser("systems", help="write the curated 3D system models (WS7)")
    s.add_argument("--out", default=str(settings.PRODUCTS_DIR))
    s.add_argument(
        "--real-only",
        action="store_true",
        help="real dataset (e.g. data/products): write only non-synthetic systems and refuse if "
        "<out>/systems already holds a synthetic one",
    )
    s.set_defaults(func=cmd_systems)

    s = sub.add_parser("build", help="build real products for a field in config/fields.toml")
    s.add_argument("field_id")
    s.add_argument("--out", default=str(settings.PRODUCTS_DIR))
    s.add_argument("--analyze", action="store_true", help="also run automatic detection and catalog matching")
    s.add_argument(
        "--no-jhk-topup",
        action="store_true",
        help="do not download extra D2/D3 frames for the J/H/Ks false-color composites (faster)",
    )
    s.add_argument(
        "--max-frames", type=_positive_int, default=None, metavar="N", help="override max_frames of fields.toml"
    )
    s.add_argument(
        "--detectors",
        type=int,
        nargs="+",
        choices=range(1, 7),
        default=None,
        metavar="D",
        help="override the detectors of fields.toml (1-6, several allowed)",
    )
    s.set_defaults(func=cmd_build)

    s = sub.add_parser("compare", help="season coadds and season differences of a built field (WS2-7)")
    s.add_argument("field_id")
    s.add_argument("--dir", default=str(settings.PRODUCTS_DIR))
    s.set_defaults(func=cmd_compare)

    s = sub.add_parser("spectrum", help="forced-photometry spectrum of a position on all SPHEREx exposures (WS2)")
    s.add_argument("--ra", type=float, required=True)
    s.add_argument("--dec", type=float, required=True)
    s.add_argument("--pm-ra", type=float, default=None, help="proper motion in RA*cos(dec) [mas/yr]")
    s.add_argument("--pm-dec", type=float, default=None, help="proper motion in Dec [mas/yr]")
    s.add_argument("--pm-epoch", type=float, default=51544.5, help="epoch (MJD) of --ra/--dec [default J2000]")
    s.add_argument("--detector", type=int, action="append")
    s.add_argument("--max-frames", type=int, default=None)
    s.add_argument("--out", default=None, help="write the full result (all points, flags) as JSON")
    s.set_defaults(func=cmd_spectrum)

    s = sub.add_parser(
        "position-spectrum",
        help="spectrum of a position by season, with saturation and a variability check (WS3-5)",
        epilog="Exit codes: 0 = spectrum; 2 = search failed or invalid input; 4 = no exposure measured.",
    )
    s.add_argument("--ra", type=float, required=True)
    s.add_argument("--dec", type=float, required=True)
    s.add_argument("--pm-ra", type=float, default=None, help="proper motion in RA*cos(dec) [mas/yr]")
    s.add_argument("--pm-dec", type=float, default=None, help="proper motion in Dec [mas/yr]")
    s.add_argument("--pm-epoch", type=float, default=51544.5, help="epoch (MJD) of --ra/--dec [default J2000]")
    s.add_argument("--detector", type=int, action="append", choices=range(1, 7), help="repeat for several")
    s.add_argument(
        "--max-frames", type=_positive_int, default=None, help="exposures evenly spread in time (~2 MB each)"
    )
    s.add_argument("--json", action="store_true", help="print the full result as JSON")
    s.add_argument("--out", default=None, help="write the full result as JSON")
    s.set_defaults(func=cmd_position_spectrum)

    s = sub.add_parser(
        "lightcurve",
        help="light curve of a position in narrow wavelength bins, with comparison stars and a period (WS3-9)",
        epilog="Exit codes: 0 = light curve; 2 = search failed or invalid input; 4 = no point in the light curve.",
    )
    s.add_argument("--ra", type=float, required=True)
    s.add_argument("--dec", type=float, required=True)
    s.add_argument(
        "--method",
        choices=("aperture", "wing"),
        default="aperture",
        help="aperture (r = 3 px, saturated exposures excluded) or wing (PSF wing of a saturated star, relative)",
    )
    s.add_argument("--detector", type=int, action="append", choices=range(1, 7), help="repeat for several")
    s.add_argument("--collections", default=None, help="comma-separated IRSA collections (default dr1,qr3)")
    s.add_argument("--deep", action="store_true", help="add the deep-field collections (dr1_deep, qr3_deep)")
    s.add_argument("--max-frames", type=_positive_int, default=None, help="cap, spread over detectors and visits")
    s.add_argument("--mjd-min", type=float, default=None)
    s.add_argument("--mjd-max", type=float, default=None)
    s.add_argument("--deadline", type=float, default=None, help="seconds for the whole archive read")
    s.add_argument("--box", type=int, default=None, help="stamp side [px] (default 81 aperture, 111 wing)")
    s.add_argument("--bin-frac", type=float, default=0.01, help="wavelength bin width, fraction of lambda (0.01)")
    s.add_argument("--min-bin-span", type=float, default=30.0, help="drop bins spanning fewer days (default 30)")
    s.add_argument("--period", action="store_true", help="always estimate a period (default: with >= 30 points)")
    s.add_argument("--bootstrap", type=int, default=0, help="visit-bootstrap resamples for the period (e.g. 100)")
    s.add_argument(
        "--permutations",
        type=int,
        default=100,
        help="visit permutations for the period's false-alarm probability (default 100; 0 = untested)",
    )
    s.add_argument("--json", action="store_true", help="print the full result (and matched pairs) as JSON")
    s.add_argument("--out", default=None, help="write the full result as JSON")
    s.set_defaults(func=cmd_lightcurve)

    s = sub.add_parser(
        "object",
        help="catalog context of a position or a name: SIMBAD, Gaia DR3, VSX, planets, 2MASS/AllWISE (WS3)",
        description="Who is at this position (or this name) and what other catalogs measured: identity, Gaia DR3 "
        "match after proper-motion propagation, physical parameters as contract Facts ('unknown' when not "
        "measured), confirmed planets and context photometry. Exit 2 = name not resolved or invalid input.",
    )
    s.add_argument("--ra", type=float, default=None, help="ICRS degrees, at --epoch-mjd")
    s.add_argument("--dec", type=float, default=None)
    s.add_argument("--name", default=None, help='any name Sesame (CfA) resolves, e.g. "Barnard\'s Star"')
    s.add_argument("--epoch-mjd", type=float, default=None, help="epoch of the position (default 61000, SPHEREx era)")
    s.add_argument("--radius", type=float, default=8.0, help="match radius [arcsec] (default 8)")
    s.add_argument("--no-cache", action="store_true", help="ignore and do not write the response cache")
    s.add_argument("--offline", action="store_true", help="only replay cached responses (no network)")
    s.add_argument("--json", action="store_true", help="print the full context, parameters and Facts as JSON")
    s.set_defaults(func=cmd_object)

    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
