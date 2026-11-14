from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

from errante import settings as core


def has_real_fields(root: Path) -> bool:
    """True if <root>/manifest.json lists at least one field (a systems-only manifest doesn't count)."""
    try:
        manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
        return bool(manifest.get("fields"))
    except (OSError, ValueError):
        return False


@dataclass
class Settings:
    data_dir: Path
    cors_origins: list[str] = field(default_factory=lambda: ["*"])

    @classmethod
    def from_env(cls) -> Settings:
        """ERRANTE_DATA_DIR wins; else real products if they have fields; else the synthetic demo."""
        if os.environ.get("ERRANTE_DATA_DIR"):
            data_dir = Path(os.environ["ERRANTE_DATA_DIR"]).resolve()
        elif has_real_fields(core.PRODUCTS_DIR):
            data_dir = core.PRODUCTS_DIR
        else:
            data_dir = core.DEMO_DIR
        origins = os.environ.get("ERRANTE_CORS_ORIGINS", "*").split(",")
        return cls(data_dir=data_dir, cors_origins=origins)
