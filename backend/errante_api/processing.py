"""Content identities for cached products; source paths never enter public responses."""

from __future__ import annotations

import hashlib
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

import errante

BUILD_REVISION = "display-mask-v4"


def source_fingerprint(root: Path | None = None) -> str:
    root = root or Path(errante.__file__).resolve().parent
    files = [root / name for name in ("build.py", "settings.py", "models.py")]
    for name in ("data", "imaging"):
        files.extend((root / name).rglob("*.py"))
    digest = hashlib.sha256()
    for path in sorted(set(files)):
        if path.is_file():
            digest.update(path.relative_to(root).as_posix().encode())
            digest.update(b"\0")
            digest.update(hashlib.sha256(path.read_bytes()).digest())
    for package in ("numpy", "astropy", "pillow", "scipy", "reproject"):
        try:
            value = version(package)
        except PackageNotFoundError:
            value = "unavailable"
        digest.update(f"{package}={value}\n".encode())
    return digest.hexdigest()
