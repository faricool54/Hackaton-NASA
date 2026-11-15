"""Bounded offline WS3 precomputation. No web request invokes this module."""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from datetime import UTC, datetime
from pathlib import Path

import psutil

from errante import __version__
from errante import settings as core
from errante.models import LightCurveParameters, LightCurveProduct, MeasurementFailure

from .jobs.process import collect_log, kill_tree, tree_bytes
from .lightcurve_metadata import acquisition_notes, target_notes
from .lightcurve_store import MAX_PRODUCT_BYTES
from .processing import source_fingerprint
from .publication import atomic_bytes, publication_lock

log = logging.getLogger(__name__)
PRESETS = {
    "rw-aurigae": (
        "RW Aurigae",
        {"ra": 76.95659, "dec": 30.40129, "detectors": [1], "method": "aperture", "mjd_max": 61300, "period": False},
    ),
    "r-draconis": (
        "R Draconis",
        {"ra": 248.16723, "dec": 66.75502, "method": "wing", "mjd_max": 61315, "period": True},
    ),
}


def processing_identity() -> str:
    """Includes WS3 algorithms and the adapter in addition to WS1/WS2 and library versions."""
    digest = hashlib.sha256(source_fingerprint().encode())
    root = Path(core.__file__).resolve().parent
    for path in sorted((root / "science").rglob("*.py")):
        digest.update(path.relative_to(root).as_posix().encode())
        digest.update(hashlib.sha256(path.read_bytes()).digest())
    for adapter in (Path(__file__), Path(__file__).with_name("lightcurve_metadata.py")):
        digest.update(adapter.read_bytes())
    return digest.hexdigest()


def public_failure(frame_id, reason, *, download=False):
    text = str(reason)
    if text.startswith("NoOverlap"):
        reason = "no_overlap"
    elif download and (text.startswith(("ValueError:", "EOFError:", "VerifyError:")) or "truncated FITS" in text):
        reason = "invalid_pixels"
    else:
        reason = "download_failed" if download else "measurement_failed"
    return MeasurementFailure(frame_id=frame_id, reason=reason).model_dump(mode="json")


def calculate(doc: dict) -> LightCurveProduct:
    """WS1 obtains samples; WS3 does every measurement, control and period calculation."""
    from errante.data.point import point_series
    from errante.science import variability as ws3

    params = LightCurveParameters.model_validate(doc["parameters"])
    series = point_series(
        params.ra,
        params.dec,
        detectors=params.detectors or None,
        collections=params.collections,
        max_frames=params.max_frames,
        mjd_min=params.mjd_min,
        mjd_max=params.mjd_max,
        box_px=ws3.DEFAULT_BOX_PX[params.method],
        planes=ws3.DEFAULT_PLANES[params.method],
        max_workers=32,
        deadline_s=doc["archive_deadline_s"],
    )
    exposures, measurement_failures = ws3.exposures_from_series(series)
    curve = ws3.light_curve_from_exposures(
        exposures,
        params.ra,
        params.dec,
        method=params.method,
        lambda_bin_frac=params.lambda_bin_frac,
        min_bin_span_days=params.min_bin_span_days,
        n_comparison=params.n_comparison,
        period=params.period,
        period_range_days=params.period_range_days,
        n_bootstrap=params.n_bootstrap,
        n_permutations=params.n_permutations,
    )
    native = curve.to_dict()
    for key in ("search", "timings"):
        native.pop(key, None)
    native["unit"] = "mJy" if params.method == "aperture" else "MJy/sr"
    native["relative_only"] = params.method == "wing"
    native["matched_pairs"] = ws3.matched_pairs(curve, max_frac=params.lambda_bin_frac)
    native["failures"] = [
        public_failure(f"{ref.obs_id}D{ref.detector}", reason, download=True) for ref, reason in series.failures
    ] + [public_failure(f.get("frame_id"), f.get("reason")) for f in measurement_failures]
    search = series.search
    found, selected = search.get("n_found"), search.get("n_selected", len(series.samples) + len(series.failures))
    truncated = bool(search.get("overflow") or search.get("truncated") or (found is not None and selected < found))
    provenance = {
        "pipeline_version": __version__,
        "processing_fingerprint": doc["processing_fingerprint"],
        "collections": params.collections,
        "sources": [{"frame_id": e.frame_id, "source_uri": e.image.source} for e in exposures],
        "n_found": found,
        "n_selected": selected,
        "stale_search": bool(search.get("stale")),
        "truncated_search": truncated,
        "partial": bool(
            any(f["reason"] != "no_overlap" for f in native["failures"])
            or truncated
            or search.get("stale")
            or search.get("errors")
            or getattr(series, "timings", {}).get("timed_out")
        ),
        "notes": [
            "Offline FITS measurement using WS3 variability methods; not a new R05 validation.",
            "Fixed sky position. This calculation does not follow proper motion or parallax.",
            "Aperture flux is uncorrected aperture flux; wing flux is relative surface brightness only.",
            "Relative magnitudes are normalized per detector/wavelength bin; negative means brighter.",
            "zero_point_mag is reported but not applied; rel_mag_err is statistical, read comparison controls for systematics.",
            "A truncated selection may alter a period estimate. Inspect significance, aliases and independent data.",
            f"Native measurement unit: {curve.unit}.",
            "Product id is an opaque content identity, not a Git revision or an independent validation certificate.",
        ],
    }
    provenance["notes"] += acquisition_notes(
        search,
        getattr(series, "timings", {}),
        box_px=ws3.DEFAULT_BOX_PX[params.method],
        planes=ws3.DEFAULT_PLANES[params.method],
        deadline_s=doc["archive_deadline_s"],
    ) + target_notes(doc["target_id"], params, curve)
    # Keep generic counts even when the archive reports a snapshot or a capped selection.
    provenance["notes"].append(
        f"Archive selection: {selected} selected of {found if found is not None else 'unknown'} found."
    )
    identity = {"parameters": params.model_dump(mode="json"), "curve": native, "provenance": provenance}
    product_id = hashlib.sha256(json.dumps(identity, sort_keys=True, allow_nan=False).encode()).hexdigest()
    return LightCurveProduct(
        id=product_id,
        target_id=doc["target_id"],
        target_name=doc["target_name"],
        built_at=datetime.now(UTC),
        status="ready" if curve.used() else "no_usable_points",
        parameters=params,
        curve=native,
        provenance=provenance,
    )


def publish(product: LightCurveProduct, out: Path) -> Path:
    payload = product.model_dump_json().encode()
    if len(payload) > MAX_PRODUCT_BYTES:
        raise ValueError("Published light curve exceeds the size limit")
    # Validate the exact bytes before replacing the previous complete product.
    LightCurveProduct.model_validate_json(payload)
    out = out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    destination = out / f"{product.target_id}.json"
    if not destination.resolve().is_relative_to(out):
        raise ValueError("Light curve path escapes the publication directory")
    with publication_lock(out):
        atomic_bytes(destination, payload)
    return destination


def run_bounded(doc: dict, work: Path, *, deadline_s=600, max_bytes=2 * 1024**3) -> LightCurveProduct:
    work.mkdir(parents=True, exist_ok=True)
    if shutil.disk_usage(work).free < min(max_bytes, 512 * 1024**2):
        raise OSError("Insufficient free space for light-curve precomputation")
    with tempfile.TemporaryDirectory(prefix="lightcurve-", dir=work) as name:
        stage = Path(name)
        request, result = stage / "request.json", stage / "result.json"
        atomic_bytes(request, json.dumps(doc, allow_nan=False).encode())
        env = {
            **os.environ,
            "ERRANTE_CACHE_DIR": str(stage / "cache"),
            "ERRANTE_JOB_SUPERVISED": "1",
            "ERRANTE_JOB_OWNER_PID": str(os.getpid()),
            "ERRANTE_JOB_OWNER_CREATED": str(psutil.Process().create_time()),
            "ERRANTE_SEARCH_DEADLINE_S": str(doc.get("archive_deadline_s", deadline_s)),
            "ERRANTE_SEARCH_FALLBACK_DEADLINE_S": str(doc.get("archive_deadline_s", deadline_s)),
        }
        options = (
            {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW}
            if sys.platform == "win32"
            else {"start_new_session": True}
        )
        proc = subprocess.Popen(
            [sys.executable, "-m", "errante_api.lightcurve_build", "--child", str(request), str(result)],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            env=env,
            **options,
        )
        drain = collect_log(proc, stage / "worker.log", 1024**2)
        until = time.monotonic() + deadline_s
        try:
            while proc.poll() is None:
                if time.monotonic() > until:
                    raise TimeoutError("Light-curve precomputation exceeded its deadline")
                if tree_bytes(stage) > max_bytes:
                    raise OSError("Light-curve precomputation exceeded its disk budget")
                time.sleep(0.1)
            if proc.returncode:
                drain.join(timeout=5)
                log.error("Light-curve worker failed: %s", (stage / "worker.log").read_text(errors="replace")[-4000:])
                raise RuntimeError("Light-curve precomputation failed; previous products are unchanged")
            with result.open("rb") as stream:
                payload = stream.read(MAX_PRODUCT_BYTES + 1)
            if len(payload) > MAX_PRODUCT_BYTES:
                raise ValueError("Worker result exceeds the public size limit")
            product = LightCurveProduct.model_validate_json(payload)
            if (
                product.target_id,
                product.target_name,
                product.parameters,
                product.provenance.processing_fingerprint,
            ) != (
                doc["target_id"],
                doc["target_name"],
                LightCurveParameters.model_validate(doc["parameters"]),
                doc["processing_fingerprint"],
            ):
                raise ValueError("Worker result does not match the requested calculation")
            return product
        finally:
            if proc.poll() is None:
                kill_tree(proc)
            proc.wait(timeout=5)
            drain.join(timeout=5)


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    if args and args[0] == "--child":
        from .jobs.child import _watch_parent

        threading.Thread(target=_watch_parent, daemon=True).start()
        result = calculate(json.loads(Path(args[1]).read_text(encoding="utf-8")))
        atomic_bytes(Path(args[2]), result.model_dump_json().encode())
        return 0
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--preset", choices=PRESETS, required=True)
    parser.add_argument(
        "--out", type=Path, required=True, help="Explicit lightcurves directory; no fields/manifest are modified"
    )
    parser.add_argument("--work-dir", type=Path, default=core.CACHE_DIR / "lightcurve-builds")
    parser.add_argument("--max-frames", type=int, default=600)
    parser.add_argument("--bootstrap", type=int, default=1000)
    parser.add_argument("--permutations", type=int, default=999)
    parser.add_argument("--archive-deadline", type=float, default=180)
    parser.add_argument("--deadline", type=float, default=600)
    parser.add_argument("--max-bytes", type=int, default=2 * 1024**3)
    ns = parser.parse_args(args)
    if not 0 < ns.archive_deadline <= ns.deadline <= 1800 or ns.max_bytes < 64 * 1024**2:
        parser.error("Require 0 < archive deadline <= deadline <= 1800 s and at least 64 MiB staging")
    if ns.work_dir.resolve().is_relative_to(ns.out.resolve()) or ns.out.resolve().is_relative_to(ns.work_dir.resolve()):
        parser.error("Work and publication directories must be separate")
    name, preset = PRESETS[ns.preset]
    params = LightCurveParameters(
        **preset, max_frames=ns.max_frames, n_bootstrap=ns.bootstrap, n_permutations=ns.permutations
    )
    doc = {
        "target_id": ns.preset,
        "target_name": name,
        "parameters": params.model_dump(mode="json"),
        "archive_deadline_s": ns.archive_deadline,
        "processing_fingerprint": processing_identity(),
    }
    product = run_bounded(doc, ns.work_dir, deadline_s=ns.deadline, max_bytes=ns.max_bytes)
    path = publish(product, ns.out)
    print(
        json.dumps(
            {
                "path": str(path),
                "status": product.status,
                "points": len(product.curve.points),
                "used": sum(p.rel_mag is not None for p in product.curve.points),
                "partial": product.provenance.partial,
                "period_significant": product.curve.period.significant if product.curve.period else None,
            }
        )
    )
    return 0 if product.status == "ready" else 4


if __name__ == "__main__":
    raise SystemExit(main())
