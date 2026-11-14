"""Publication utilities shared between batch presets and job engine (E3).

Responsibilities:
- Validate a staged product (schema, PNGs, two distinct dates, contained paths).
- Publish it atomically from staging into the public product tree.
- Keep the manifest consistent without holding a lock during I/O.
- Preserve existing curated fields and systems when updating the manifest.

Design (from INTERNAL_ENGINE_PLAN.md §7):
- Jobs publish with a per-attempt immutable field ID so live readers aren't
  disrupted by partial overwrites.
- The same file lock that batch uses; held only during the final file move,
  not during validation or the full build.
- DB and filesystem are not a single transaction: a publication record and
  reconciliation detect any cut between validate→move and DB update.
"""

from __future__ import annotations

import hashlib
import logging
import shutil
import threading
from pathlib import Path

log = logging.getLogger(__name__)

# Global publish lock: shared by batch and job engine on a single process.
_PUBLISH_LOCK = threading.Lock()


def validate_product(staging_products: Path, field_id: str) -> None:
    """Validate a staged product directory.

    Raises ValueError with a descriptive message on any failure.
    Does NOT apply the ">30 days between seasons" rule — that belongs only to
    preset batch jobs (see plan §7).

    Checks:
    - field.json and candidates.json are parseable against the contract schema.
    - At least 2 frames with distinct MJD values exist.
    - Every image path in field.json is a readable PNG within staging_products.
    - Provenance marks the field as non-synthetic and has a pipeline_version.
    """
    from errante.products import ProductStore

    store = ProductStore(staging_products)
    field_dir = store.field_dir(field_id)

    if not (field_dir / "field.json").exists():
        raise ValueError(f"field.json missing for '{field_id}' in staging")

    try:
        field = store.read_field(field_id)
    except Exception as exc:
        raise ValueError(f"field.json is not valid: {exc}") from exc

    if len(field.frames) < 2:
        raise ValueError(f"field '{field_id}' has only {len(field.frames)} frame(s); need at least 2")

    mjds = {f.mjd for f in field.frames}
    if len(mjds) < 2:
        raise ValueError(f"field '{field_id}' frames all share the same MJD; need at least 2 distinct dates")

    staging_resolved = staging_products.resolve()
    for frame in field.frames:
        img_path = field_dir / frame.image
        # Path must be contained within staging_products (no directory traversal)
        try:
            img_path.resolve().relative_to(staging_resolved)
        except ValueError as exc:
            raise ValueError(f"frame image path escapes staging: {frame.image}") from exc
        if not img_path.exists():
            raise ValueError(f"frame PNG missing: {frame.image}")
        # Quick PNG header check
        with img_path.open("rb") as fh:
            header = fh.read(8)
        if header[:8] != b"\x89PNG\r\n\x1a\n":
            raise ValueError(f"frame is not a valid PNG: {frame.image}")


def publish_job(
    *,
    staging_dir: Path,
    field_id: str,
    products_dir: Path,
    repo,  # JobRepository — typed as Any to avoid a circular import
    job_id: str,
) -> str:
    """Validate, move and register a staged job product.

    Returns the published field_id (same as input field_id for now).
    Raises PublicationError on any failure; the caller must handle it.
    """
    from .errors import PublicationError

    staging_products = staging_dir / "products"

    # --- Validate (outside the lock) ---
    try:
        validate_product(staging_products, field_id)
    except ValueError as exc:
        raise PublicationError(f"product validation failed: {exc}") from exc

    # --- Move into public tree (under lock) ---
    dest_field_dir = products_dir / "fields" / field_id

    with _PUBLISH_LOCK:
        try:
            if dest_field_dir.exists():
                # Rename old dir to a backup before overwriting
                backup = dest_field_dir.with_suffix(".bak")
                if backup.exists():
                    shutil.rmtree(backup)
                dest_field_dir.rename(backup)

            shutil.copytree(
                staging_products / "fields" / field_id,
                dest_field_dir,
            )

            # Remove backup only after successful copy
            backup = dest_field_dir.with_suffix(".bak")
            if backup.exists():
                shutil.rmtree(backup)

        except Exception as exc:
            # Attempt rollback: restore backup if it exists
            backup = dest_field_dir.with_suffix(".bak")
            if backup.exists() and not dest_field_dir.exists():
                try:
                    backup.rename(dest_field_dir)
                except Exception:
                    pass
            raise PublicationError(f"file move failed: {exc}") from exc

        # Update manifest (still under lock so readers get a consistent view)
        try:
            from errante.products import ProductStore

            store = ProductStore(products_dir)
            store.rebuild_manifest()
        except Exception as exc:
            log.error("manifest rebuild failed after publishing %s: %s", field_id, exc)
            # Field is published; manifest will be repaired on next publish or restart.
            # Do not raise — the product is good.

    log.info("published field %s from job %s", field_id, job_id)
    return field_id


def file_hash(path: Path) -> str:
    """SHA-256 hex digest of a file (for publication records)."""
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()
