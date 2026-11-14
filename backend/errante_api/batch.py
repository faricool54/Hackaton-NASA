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
from tempfile import NamedTemporaryFile, mkdtemp

from PIL import Image

from errante import settings
from errante.build import load_field_configs
from errante.models import SkyField
from errante.products import ProductStore

TARGETS = ("barnards-star", "eps-indi-b", "wise-0855", "rw-aurigae", "r-draconis")


class AtomicProductStore(ProductStore):
    @staticmethod
    def _write(path, model):
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = None
        try:
            with NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False) as f:
                temporary = Path(f.name)
                f.write(model.model_dump_json(indent=2) + "\n")
            os.replace(temporary, path)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
        return path


def validate_field(root: Path, field_id: str) -> SkyField:
    field = ProductStore(root).read_field(field_id)
    if field.id != field_id or field.provenance.synthetic or len(field.frames) < 2:
        raise ValueError("Expected a non-synthetic field with at least two frames")
    if not any(
        len(mjds := [f.mjd for f in field.frames if f.detector == detector]) >= 2 and max(mjds) - min(mjds) > 30
        for detector in range(1, 7)
    ):
        raise ValueError("No detector spans two seasons (>30 days); check WS1/WS2 epoch selection")
    directory = (root / "fields" / field_id).resolve()
    if not directory.is_relative_to(root.resolve()):
        raise ValueError("Field escapes the staging root")
    for frame in field.frames:
        image = (directory / frame.image).resolve()
        if not image.is_relative_to(directory) or not image.is_file() or not frame.source_uri:
            raise ValueError("Missing image/provenance or image outside the field directory")
        with Image.open(image) as png:
            if png.format != "PNG" or png.size != (field.grid.width_px, field.grid.height_px):
                raise ValueError("Expected a PNG on the declared field grid")
            png.verify()
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
            preserve_stage = False
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
                    destination = out / "fields" / field_id
                    if not destination.resolve().is_relative_to(out):
                        raise ValueError("Field destination escapes the product root")
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    source = stage / "fields" / field_id
                    backup = stage / "previous"
                    installed = False
                    try:
                        if destination.exists():
                            os.replace(destination, backup)
                        os.replace(source, destination)
                        installed = True
                        AtomicProductStore(out).rebuild_manifest()
                    except BaseException:
                        try:
                            if installed:
                                os.replace(destination, source)
                            if backup.exists():
                                os.replace(backup, destination)
                        except OSError as error:
                            # Never delete the previous product if restore itself fails.
                            preserve_stage = True
                            item["recovery_dir"] = str(stage)
                            raise RuntimeError("Publication rollback failed; retain recovery_dir for repair") from error
                        raise
                    item.update(status="ready", n_frames=len(field.frames))
                except subprocess.TimeoutExpired:
                    item["error"] = "timeout"
                except Exception as error:
                    item.update(error="validation_or_publication_failed", detail=str(error))
            finally:
                if not preserve_stage:
                    # mkdtemp returned an owned child of the explicitly selected parent.
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
