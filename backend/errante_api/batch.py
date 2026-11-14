"""Isolated preset builds, validation and staged publication (WS4, Codex-assisted).

This is a batch command, not the pending public jobs API. Each child has a hard
deadline. Invalid/empty products never replace a previously published field.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import shutil
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from tempfile import mkdtemp

from errante import settings
from errante.build import load_field_configs
from errante.models import SkyField

from .publication import AtomicProductStore, publish_field, validate_product  # noqa: F401 (compatibility export)

TARGETS = ("barnards-star", "eps-indi-b", "wise-0855", "rw-aurigae", "r-draconis")


def validate_field(root: Path, field_id: str) -> SkyField:
    field = validate_product(root, field_id)
    if not any(
        len(mjds := [f.mjd for f in field.frames if f.detector == detector]) >= 2 and max(mjds) - min(mjds) > 30
        for detector in range(1, 7)
    ):
        raise ValueError("No detector spans two seasons (>30 days); check WS1/WS2 epoch selection")
    return field


def build_fields(out: Path, targets=TARGETS, timeout_s: float = 900) -> dict:
    configs = load_field_configs()
    if (
        not math.isfinite(timeout_s)
        or timeout_s <= 0
        or not targets
        or any(t not in configs or not re.fullmatch(r"[a-z0-9][a-z0-9-]*", t) for t in targets)
    ):
        raise ValueError("Select configured field slugs and a positive timeout")
    out = out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    lock = out / ".build.lock"
    fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    report = {"generated_at": datetime.now(UTC).isoformat(), "fields": []}
    try:
        os.close(fd)
        for field_id in dict.fromkeys(targets):
            item = {"id": field_id, "status": "failed"}
            report["fields"].append(item)
            # Same filesystem as the destination, but outside the public root.
            stage = Path(mkdtemp(prefix=".errante-build-", dir=out.parent)).resolve()
            try:
                try:
                    child = subprocess.run(
                        [sys.executable, "-m", "errante.cli", "build", field_id, "--out", str(stage)],
                        capture_output=True,
                        text=True,
                        timeout=timeout_s,
                        check=False,
                    )
                    if child.returncode:
                        item["error"] = "pipeline_not_ready" if child.returncode == 3 else "build_failed"
                        continue
                    field = validate_field(stage, field_id)
                    publish_field(stage, field_id, out, replace=True)
                    item.update(status="ready", n_frames=len(field.frames))
                except subprocess.TimeoutExpired:
                    item["error"] = "timeout"
                except Exception as error:
                    item.update(error="validation_or_publication_failed", detail=str(error))
                    if hasattr(error, "recovery_dir"):
                        item["recovery_dir"] = str(error.recovery_dir)
            finally:
                assert stage.is_relative_to(out.parent) and stage.name.startswith(".errante-build-")
                shutil.rmtree(stage)
        return report
    finally:
        lock.unlink(missing_ok=True)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=settings.PRODUCTS_DIR)
    parser.add_argument("--field", action="append", choices=TARGETS)
    parser.add_argument("--timeout", type=float, default=900)
    args = parser.parse_args(argv)
    try:
        report = build_fields(args.out, args.field or TARGETS, args.timeout)
    except (ValueError, OSError) as error:
        print(f"Cannot start field builds: {error}", file=sys.stderr)
        return 2
    print(json.dumps(report, indent=2))
    return 0 if all(f["status"] == "ready" for f in report["fields"]) else 1
