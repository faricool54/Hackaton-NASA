"""Contain product reads within the public root without changing the shared store."""

from __future__ import annotations

from pathlib import Path
from typing import TypeVar

from fastapi import HTTPException
from pydantic import BaseModel

from errante.products import ProductStore

M = TypeVar("M", bound=BaseModel)


class PublicProductStore(ProductStore):
    def _read(self, path: Path, cls: type[M]) -> M:
        if not path.resolve().is_relative_to(self.root.resolve()):
            raise HTTPException(404, "Product not found.")
        try:
            return super()._read(path, cls)
        except (OSError, ValueError) as error:
            raise HTTPException(503, "Product is unavailable or invalid; retry later.") from error
