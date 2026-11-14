"""Child process entry point (E2).

Launched by the supervisor as:
    sys.executable -m errante_api.jobs.child <request_path> <result_path>

The child:
1. Reads the validated request JSON from <request_path>.
2. Builds a FieldConfig and calls build_field(..., analyze=False).
3. Writes a ChildResult JSON to <result_path>.
4. Exits 0 on success, 1 on failure.

The child writes ONLY to the staging directory supplied by the supervisor.
It never modifies the public product tree directly.
"""

from __future__ import annotations

import json
import sys
import traceback
from pathlib import Path


def _run(request_path: Path, result_path: Path) -> None:
    """Core logic, separated for testability."""
    # Read request
    try:
        raw = json.loads(request_path.read_text(encoding="utf-8"))
    except Exception as exc:
        _write_result(result_path, success=False, status="failed", error=f"cannot read request: {exc}")
        return

    # Validate request
    try:
        from .types import JobRequest

        req = JobRequest.from_dict(raw["request"])
    except Exception as exc:
        _write_result(result_path, success=False, status="failed", error=f"invalid request: {exc}")
        return

    staging_dir = Path(raw["staging_dir"])
    field_id = raw["field_id"]
    out_dir = staging_dir / "products"
    out_dir.mkdir(parents=True, exist_ok=True)

    # Build FieldConfig
    try:
        from errante.build import FieldConfig

        cfg = FieldConfig(
            id=field_id,
            name=f"Job field {field_id}",
            ra=req.ra,
            dec=req.dec,
            size_deg=req.size_deg,
            detectors=list(req.detectors) if req.detectors else None,
            mjd_min=req.mjd_min,
            mjd_max=req.mjd_max,
            max_frames=req.max_frames,
        )
    except Exception as exc:
        _write_result(
            result_path, success=False, status="failed", error=f"cannot build FieldConfig: {exc}", stage="build"
        )
        return

    # Execute pipeline
    try:
        from errante.build import build_field

        build_field(cfg, out_dir, analyze=False)
    except NotImplementedError as exc:
        _write_result(
            result_path,
            success=False,
            status="pipeline_not_ready",
            error=f"pipeline stub: {exc}",
            stage="build",
        )
        return
    except ValueError as exc:
        # build_field raises ValueError when no frames are found
        msg = str(exc)
        if "no usable" in msg.lower() or "no products" in msg.lower():
            _write_result(result_path, success=False, status="no_coverage", error=msg, stage="build")
        else:
            _write_result(result_path, success=False, status="failed", error=msg, stage="build")
        return
    except Exception as exc:
        tb = traceback.format_exc()
        _write_result(result_path, success=False, status="failed", error=f"{exc}\n{tb}", stage="build")
        return

    _write_result(result_path, success=True, field_id=field_id, status="ready", stage="publish")


def _write_result(
    result_path: Path,
    *,
    success: bool,
    field_id: str | None = None,
    status: str = "failed",
    error: str | None = None,
    stage: str | None = None,
) -> None:
    doc = {
        "success": success,
        "field_id": field_id,
        "status": status,
        "error": error,
        "stage": stage,
    }
    result_path.write_text(json.dumps(doc), encoding="utf-8")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(f"usage: {sys.argv[0]} <request_path> <result_path>", file=sys.stderr)
        sys.exit(2)
    _run(Path(sys.argv[1]), Path(sys.argv[2]))
    # Exit code reflects the result, so the supervisor doesn't need to parse
    # the result JSON just to know if it crashed vs. wrote a failure result.
    result_doc = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
    sys.exit(0 if result_doc.get("success") else 1)
