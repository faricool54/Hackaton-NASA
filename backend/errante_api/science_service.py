"""Bounded/cached science calls and immutable atomic analysis publication."""

from __future__ import annotations

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
from dataclasses import replace
from pathlib import Path

import psutil
from fastapi import HTTPException
from PIL import Image
from pydantic import TypeAdapter

from errante.models import ComparisonRequest, ComparisonResponse, SkyField, SpectrumRequest, SpectrumResponse

from .jobs.process import collect_log, kill_tree, tree_bytes
from .live_service import LiveService
from .processing import source_fingerprint
from .publication import atomic_bytes, publication_lock
from .settings import Settings

log = logging.getLogger(__name__)
_MAX_STAGE_BYTES = 512 * 1024**2
_DEADLINE_S = 140


class ScienceService:
    def __init__(self, settings: Settings, *, runner=None):
        self.settings = settings
        self._work = settings.live_cache_dir / "science-work"
        self._live = LiveService(
            replace(
                settings,
                live_cache_dir=settings.live_cache_dir / "science-results",
                live_max_concurrent=1,
                live_timeout_s=150,
            )
        )
        self._runner = runner or self._run_child
        self._stop = threading.Event()

    def close(self):
        self._stop.set()
        self._live.close()

    def _identity(self, operation, request, field):
        payload = {
            "operation": operation,
            "request": request.model_dump(mode="json"),
            "field": field.model_dump(mode="json") if field else None,
            "processing": source_fingerprint(),
            "adapter": hashlib.sha256(Path(__file__).with_name("science_ops.py").read_bytes()).hexdigest(),
        }
        key = hashlib.sha256(json.dumps(payload, sort_keys=True, allow_nan=False).encode()).hexdigest()
        return {**payload, "id": key}

    async def spectrum(self, request: SpectrumRequest, field: SkyField | None = None):
        if field is not None:
            self._real_field(field)
            from errante.imaging.photometry import SPHEREX_ERA_MJD, propagate

            motion = request.proper_motion
            pm = (motion.ra_cosdec_masyr, motion.dec_masyr, motion.epoch_mjd) if motion else None
            self._inside(field, *propagate(request.ra, request.dec, pm, SPHEREX_ERA_MJD))
        doc = self._identity("spectrum", request, field)
        return await self._live.call(
            "spectrum", doc, lambda: self._run(doc, SpectrumResponse), TypeAdapter(SpectrumResponse)
        )

    async def comparisons(self, field: SkyField, request: ComparisonRequest):
        self._real_field(field)
        selected = {f.id for f in field.frames}
        if request.frame_ids is not None and not set(request.frame_ids) <= selected:
            raise HTTPException(422, "Unknown frame ID in the selected field.")
        frames = [
            f
            for f in field.frames
            if (not request.detectors or f.detector in request.detectors)
            and (request.frame_ids is None or f.id in request.frame_ids)
        ]
        if len(frames) < 2:
            raise HTTPException(422, "Select at least two frames from the field.")
        if len(frames) > 60 or field.grid.width_px * field.grid.height_px > 512**2:
            raise HTTPException(413, "Comparison exceeds the 60-frame / 512-square-pixel limit.")
        field = field.model_copy(update={"frames": frames, "composites": []})
        doc = self._identity("comparison", request, field)
        return await self._live.call(
            "comparison",
            doc,
            lambda: self._run(doc, ComparisonResponse),
            TypeAdapter(ComparisonResponse),
            cache_validator=lambda r: self._artifacts_ok(r, field),
        )

    @staticmethod
    def _real_field(field):
        if field.provenance.synthetic or any(f.release == "synthetic" or not f.source_uri for f in field.frames):
            raise HTTPException(409, "Scientific operations require real SPHEREx provenance.")

    @staticmethod
    def _inside(field, ra, dec):
        import math

        from astropy.wcs import WCS

        try:
            x, y = WCS(field.grid.wcs).all_world2pix(ra, dec, 0)
        except Exception as error:
            raise HTTPException(503, "Field coordinate grid is unavailable.") from error
        if not (
            math.isfinite(x)
            and math.isfinite(y)
            and -0.5 <= x < field.grid.width_px - 0.5
            and -0.5 <= y < field.grid.height_px - 0.5
        ):
            raise HTTPException(422, "Spectrum position is outside the selected field.")

    def _artifacts_ok(self, result, field, root=None):
        root = root or self.settings.data_dir
        try:
            stored = ComparisonResponse.model_validate_json(
                (root / "analyses" / result.id / "analysis.json").read_text()
            )
            if stored != result:
                return False
            for item in result.images:
                path = root / item.image
                if not path.resolve().is_relative_to(root.resolve()):
                    return False
                with Image.open(path) as image:
                    if image.format != "PNG" or image.size != (field.grid.width_px, field.grid.height_px):
                        return False
                    image.verify()
            return True
        except (OSError, ValueError, SyntaxError):
            return False

    def _run(self, doc, model):
        try:
            self._work.mkdir(parents=True, exist_ok=True)
        except OSError as error:
            raise HTTPException(503, "Private scientific workspace is unavailable.") from error
        if tree_bytes(self._work) + tree_bytes(self.settings.data_dir / "analyses") > 1024**3:
            raise HTTPException(503, "Scientific storage is full; remove expired analysis products before retrying.")
        if shutil.disk_usage(self._work).free < _MAX_STAGE_BYTES:
            raise HTTPException(503, "Insufficient space for scientific processing.")
        with tempfile.TemporaryDirectory(dir=self._work) as name:
            stage = Path(name)
            result = model.model_validate(self._runner(doc, stage))
            if model is ComparisonResponse:
                field = SkyField.model_validate(doc["field"])
                if (
                    result.id != doc["id"]
                    or result.field_id != field.id
                    or result.field_built_at != field.provenance.built_at
                    or result.input_frames != field.frames
                ):
                    raise ValueError("Comparison result does not match its inputs")
                result = self._publish(result, stage / "output", field)
            else:
                request = SpectrumRequest.model_validate(doc["request"])
                if (result.center.ra, result.center.dec, result.source, result.field_id, result.proper_motion) != (
                    request.ra,
                    request.dec,
                    request.source,
                    request.field_id,
                    request.proper_motion,
                ):
                    raise ValueError("Spectrum result does not match its position/source")
            return result

    def _publish(self, result, output, field):
        root = self.settings.data_dir
        root.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix=".analysis-", dir=root.parent) as name:
            private = Path(name)
            incoming = private / "analyses" / result.id
            incoming.parent.mkdir()
            shutil.copytree(output, incoming)
            atomic_bytes(incoming / "analysis.json", result.model_dump_json(indent=2).encode())
            if not self._artifacts_ok(result, field, private):
                raise ValueError("Analysis contains missing or invalid PNGs")
            destination = root / "analyses" / result.id
            destination.parent.mkdir(exist_ok=True)
            with publication_lock(root):
                if destination.exists():
                    try:
                        previous = ComparisonResponse.model_validate_json((destination / "analysis.json").read_text())
                        if self._artifacts_ok(previous, field):
                            return previous
                    except (ValueError, OSError):
                        pass
                    os.replace(destination, private / "damaged")
                os.replace(incoming, destination)
        return result

    def _run_child(self, doc, stage):
        request, result = stage / "request.json", stage / "result.json"
        atomic_bytes(request, json.dumps(doc, allow_nan=False).encode())
        env = {
            **os.environ,
            "ERRANTE_CACHE_DIR": str(stage / "cache"),
            "ERRANTE_JOB_SUPERVISED": "1",
            "ERRANTE_JOB_OWNER_PID": str(os.getpid()),
            "ERRANTE_JOB_OWNER_CREATED": str(psutil.Process().create_time()),
        }
        options = (
            {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP}
            if sys.platform == "win32"
            else {"start_new_session": True}
        )
        proc = subprocess.Popen(
            [sys.executable, "-m", "errante_api.science_child", str(request), str(result)],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            env=env,
            **options,
        )
        output = collect_log(proc, stage / "worker.log", 1024**2)
        try:
            until = time.monotonic() + _DEADLINE_S
            while proc.poll() is None:
                if self._stop.is_set():
                    raise RuntimeError("Science service is stopping")
                if time.monotonic() > until:
                    raise TimeoutError("Science worker deadline")
                if tree_bytes(stage) > _MAX_STAGE_BYTES:
                    raise OSError("Science worker disk budget")
                time.sleep(0.1)
            if proc.returncode:
                log.error("Science worker failed: %s", (stage / "worker.log").read_text(errors="replace")[-4000:])
                raise RuntimeError("Scientific operation failed")
            return json.loads(result.read_text(encoding="utf-8"))
        finally:
            if proc.poll() is None:
                kill_tree(proc)
            proc.wait(timeout=5)
            output.join(timeout=5)
