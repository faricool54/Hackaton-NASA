from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from errante import settings as core


@dataclass
class Settings:
    data_dir: Path
    cors_origins: list[str] = field(default_factory=lambda: ["*"])

    @classmethod
    def from_env(cls) -> Settings:
        """ERRANTE_DATA_DIR wins; else real products if built; else the synthetic demo."""
        if os.environ.get("ERRANTE_DATA_DIR"):
            data_dir = Path(os.environ["ERRANTE_DATA_DIR"]).resolve()
        elif (core.PRODUCTS_DIR / "manifest.json").exists():
            data_dir = core.PRODUCTS_DIR
        else:
            data_dir = core.DEMO_DIR
        origins = os.environ.get("ERRANTE_CORS_ORIGINS", "*").split(",")
        return cls(data_dir=data_dir, cors_origins=origins)
