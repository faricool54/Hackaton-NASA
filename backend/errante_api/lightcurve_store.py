"""Read validated, precomputed WS3 products; HTTP reads never contact archives."""

from __future__ import annotations

import hashlib
import threading
from collections import OrderedDict
from pathlib import Path

from fastapi import HTTPException

from errante.models import LightCurveIndex, LightCurveProduct, LightCurveSummary

MAX_PRODUCT_BYTES = 8 * 1024**2
MAX_PRODUCTS = 32


class LightCurveStore:
    def __init__(self, root: Path, bundled: Path | None = None):
        self.root = root.resolve()
        self.bundled = (bundled or Path(__file__).parent / "curated" / "lightcurves").resolve()
        self._cache: OrderedDict[tuple[str, str], tuple[LightCurveProduct, bytes, str]] = OrderedDict()
        self._lock = threading.Lock()

    def _path(self, target_id: str) -> Path:
        # Also protects CLI callers; HTTP routes validate their path parameter independently.
        import re

        if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,79}", target_id):
            raise HTTPException(404, "Light curve not found.")
        for root in (self.root, self.bundled):
            path = root / f"{target_id}.json"
            if not path.resolve().is_relative_to(root):
                raise HTTPException(404, "Light curve not found.")
            if path.exists():
                return path
        raise HTTPException(404, "No precomputed light curve for this target.")

    def read(self, target_id: str) -> tuple[LightCurveProduct, bytes, str]:
        try:
            path = self._path(target_id)
            with path.open("rb") as stream:
                content = stream.read(MAX_PRODUCT_BYTES + 1)
            if len(content) > MAX_PRODUCT_BYTES:
                raise ValueError("Light curve exceeds size limit")
            key = (target_id, hashlib.sha256(content).hexdigest())
            with self._lock:
                if key in self._cache:
                    self._cache.move_to_end(key)
                    return self._cache[key]
            product = LightCurveProduct.model_validate_json(content)
            if product.target_id != target_id:
                raise ValueError("Light curve identity does not match filename")
            payload = product.model_dump_json().encode()
            result = product, payload, '"' + hashlib.sha256(payload).hexdigest() + '"'
            with self._lock:
                self._cache[key] = result
                while len(self._cache) > MAX_PRODUCTS:
                    self._cache.popitem(last=False)
            return result
        except (OSError, ValueError) as error:
            raise HTTPException(503, "Precomputed light curve is unavailable or invalid; retry later.") from error

    def index(self) -> LightCurveIndex:
        try:
            ids = set()
            for root in (self.root, self.bundled):
                for path in root.glob("*.json"):
                    ids.add(path.stem)
                    if len(ids) > MAX_PRODUCTS:
                        raise ValueError("Too many public light curves")
            summaries = []
            for target_id in sorted(ids):
                product, _, _ = self.read(target_id)
                summaries.append(
                    LightCurveSummary(
                        target_id=product.target_id,
                        target_name=product.target_name,
                        id=product.id,
                        built_at=product.built_at,
                        method=product.curve.method,
                        status=product.status,
                        n_points=len(product.curve.points),
                        n_used=sum(p.rel_mag is not None for p in product.curve.points),
                        partial=product.provenance.partial,
                    )
                )
            return LightCurveIndex(products=summaries)
        except (OSError, ValueError) as error:
            raise HTTPException(503, "Precomputed light-curve index is unavailable.") from error
