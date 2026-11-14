"""Validated publication shared by preset batches and coordinate jobs."""

from __future__ import annotations

import hashlib
import math
import os
import re
import shutil
from collections.abc import Callable
from pathlib import Path
from tempfile import NamedTemporaryFile, mkdtemp

from PIL import Image

from errante.models import SkyField
from errante.products import ProductStore

from .locking import FileLock


class PublicationRecoveryError(RuntimeError):
    def __init__(self, recovery_dir: Path):
        self.recovery_dir = recovery_dir
        super().__init__(f"Publication rollback failed; retain recovery_dir={recovery_dir}")


def atomic_bytes(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with NamedTemporaryFile(dir=path.parent, delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


class AtomicProductStore(ProductStore):
    @staticmethod
    def _write(path, model):
        atomic_bytes(path, (model.model_dump_json(indent=2) + "\n").encode())
        return path


def field_path(root: Path, field_id: str) -> Path:
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", field_id):
        raise ValueError("Invalid field slug")
    path = root / "fields" / field_id
    if not path.resolve().is_relative_to(root.resolve()):
        raise ValueError("Field path escapes product root")
    return path


def validate_product(root: Path, field_id: str) -> SkyField:
    directory = field_path(root, field_id)
    if not (directory / "field.json").is_file():
        raise ValueError(f"field.json missing for {field_id}")
    for name in ("field.json", "candidates.json", "known.json"):
        path = directory / name
        if not path.is_file() or not path.resolve().is_relative_to(directory.resolve()):
            raise ValueError("Product JSON missing or outside the field directory")
    store = ProductStore(root)
    field = store.read_field(field_id)
    if field.id != field_id:
        raise ValueError("Field identity does not match its directory")
    if len(field.frames) < 2:
        raise ValueError("Need at least 2 frames")
    if any(not math.isfinite(f.mjd) for f in field.frames):
        raise ValueError("Frame times must be finite")
    if len({f.mjd for f in field.frames}) < 2:
        raise ValueError("Frames share the same MJD")
    if field.provenance.synthetic or not field.provenance.pipeline_version:
        raise ValueError("Expected real provenance with a pipeline version")
    for frame in field.frames:
        image = directory / frame.image
        if not image.resolve().is_relative_to(directory.resolve()):
            raise ValueError("Image escapes staging field")
        if not image.is_file():
            raise ValueError("Frame PNG missing")
        if frame.release == "synthetic" or not frame.source_uri:
            raise ValueError("Expected real frame provenance")
        try:
            with Image.open(image) as png:
                if png.format != "PNG" or png.size != (field.grid.width_px, field.grid.height_px):
                    raise ValueError("PNG dimensions do not match field grid")
                png.verify()
        except (OSError, SyntaxError) as error:
            raise ValueError("Frame is not a valid PNG") from error
    if store.read_candidates(field_id).field_id != field_id or store.read_known(field_id).field_id != field_id:
        raise ValueError("Product list identity does not match the field")
    return field


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def hashes(root: Path, field_id: str) -> dict[str, str]:
    directory = field_path(root, field_id)
    return {str(p.relative_to(directory)): file_hash(p) for p in directory.rglob("*") if p.is_file()}


def publication_lock(root: Path) -> FileLock:
    return FileLock(root / ".publish.lock")


def publish_field(
    staged: Path,
    field_id: str,
    products: Path,
    *,
    replace: bool = False,
    prepared: Callable[[dict[str, str]], None] | None = None,
) -> str:
    validate_product(staged, field_id)
    products = products.resolve()
    products.mkdir(parents=True, exist_ok=True)
    private = Path(mkdtemp(prefix=".errante-publish-", dir=products.parent)).resolve()
    preserve = False
    try:
        incoming = field_path(private, field_id)
        incoming.parent.mkdir(parents=True)
        shutil.copytree(field_path(staged, field_id), incoming)
        validate_product(private, field_id)
        fingerprint = hashes(private, field_id)
        with publication_lock(products):
            destination = field_path(products, field_id)
            destination.parent.mkdir(parents=True, exist_ok=True)
            if destination.exists() and not replace:
                raise FileExistsError("Job field already published; reconcile before retry")
            if prepared is not None:
                prepared(fingerprint)
            backup = private / "previous"
            manifest = products / "manifest.json"
            previous_manifest = manifest.read_bytes() if manifest.exists() else None
            installed = False
            try:
                if destination.exists():
                    os.replace(destination, backup)
                os.replace(incoming, destination)
                installed = True
                AtomicProductStore(products).rebuild_manifest()
            except BaseException:
                try:
                    if installed:
                        os.replace(destination, incoming)
                    if backup.exists():
                        os.replace(backup, destination)
                    if previous_manifest is not None:
                        atomic_bytes(manifest, previous_manifest)
                    elif manifest.exists():
                        manifest.unlink()
                except OSError as error:
                    preserve = True
                    raise PublicationRecoveryError(private) from error
                raise
        return field_id
    finally:
        if not preserve:
            assert private.parent == products.parent and private.name.startswith(".errante-publish-")
            shutil.rmtree(private)
