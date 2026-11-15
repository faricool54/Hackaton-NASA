"""One isolated scientific operation; only private request/result paths are accepted."""

import json
import os
import sys
import threading
import traceback
from pathlib import Path

from errante.models import SkyField, SpectrumRequest

from .jobs.child import _watch_parent
from .publication import atomic_bytes
from .science_ops import comparisons, spectrum


def run(request_path: Path, result_path: Path):
    doc = json.loads(request_path.read_text(encoding="utf-8"))
    field = SkyField.model_validate(doc["field"]) if doc.get("field") is not None else None
    output = request_path.parent / "output"
    output.mkdir()
    try:
        result = (
            spectrum(SpectrumRequest.model_validate(doc["request"]), field)
            if doc["operation"] == "spectrum"
            else comparisons(field, output, doc["id"])
        )
        atomic_bytes(result_path, result.model_dump_json().encode())
    except Exception:
        traceback.print_exc()
        raise


if __name__ == "__main__":
    if os.environ.get("ERRANTE_JOB_SUPERVISED") == "1":
        threading.Thread(target=_watch_parent, daemon=True).start()
    run(Path(sys.argv[1]), Path(sys.argv[2]))
