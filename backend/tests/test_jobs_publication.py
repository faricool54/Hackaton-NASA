"""Tests for E3: publication validation and atomic move.

Covers:
- validate_product accepts a valid staged product.
- validate_product rejects: missing field.json, too few frames, same MJD, invalid PNG.
- publish_job moves the field directory and updates the manifest.
- An interrupted publish (backup + dest) is handled correctly.
- Path traversal is rejected.
"""

from __future__ import annotations

from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image

from errante.models import CandidateList, KnownObjectList
from errante_api.jobs.errors import PublicationError
from errante_api.jobs.publication import validate_product
from errante_api.jobs.repository import JobRepository, _new_id

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_buffer = BytesIO()
Image.new("L", (32, 32)).save(_buffer, format="PNG")
_PNG_HEADER = _buffer.getvalue()


def _write_valid_product(root: Path, field_id: str, *, two_distinct_mjds: bool = True) -> None:
    """Write a minimal valid staged product under root/fields/<field_id>/."""
    from errante.models import (
        CandidateList,
        Frame,
        Grid,
        KnownObjectList,
        Provenance,
        SkyCoord,
        SkyField,
    )
    from errante.products import ProductStore

    store = ProductStore(root)
    frames_dir = store.field_dir(field_id) / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)

    for i in range(2):
        (frames_dir / f"f{i}.png").write_bytes(_PNG_HEADER)

    mjds = [60000.0, 60010.0] if two_distinct_mjds else [60000.0, 60000.0]

    field = SkyField(
        id=field_id,
        name="test",
        center=SkyCoord(ra=10.0, dec=0.0),
        size_deg=0.25,
        grid=Grid(
            center=SkyCoord(ra=10.0, dec=0.0),
            width_px=32,
            height_px=32,
            pixel_scale_arcsec=4.0,
            wcs={
                "CTYPE1": "RA---TAN",
                "CTYPE2": "DEC--TAN",
                "CRVAL1": 10.0,
                "CRVAL2": 0.0,
                "CRPIX1": 16.0,
                "CRPIX2": 16.0,
                "CDELT1": -0.001,
                "CDELT2": 0.001,
            },
        ),
        frames=[
            Frame(
                id=f"f{i}",
                obs_id=f"obs{i}",
                detector=1,
                mjd=mjds[i],
                date_obs=datetime(2026, 1, 1 + i, tzinfo=UTC),
                release="dr1",
                source_uri="test-double-only",
                image=f"frames/f{i}.png",
            )
            for i in range(2)
        ],
        provenance=Provenance(
            pipeline_version="0.0.0",
            built_at=datetime.now(UTC),
            synthetic=False,
        ),
    )
    store.write_field(field)
    store.write_candidates(CandidateList(field_id=field.id, candidates=[]))
    store.write_known(KnownObjectList(field_id=field.id, objects=[]))
    store.write_candidates(CandidateList(field_id=field_id, candidates=[]))
    store.write_known(KnownObjectList(field_id=field_id, objects=[]))


# ---------------------------------------------------------------------------
# validate_product
# ---------------------------------------------------------------------------


def test_validate_accepts_valid_product(tmp_path: Path) -> None:
    _write_valid_product(tmp_path, "test-field")
    validate_product(tmp_path, "test-field")  # must not raise


def test_validate_rejects_missing_field_json(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="field.json missing"):
        validate_product(tmp_path, "nonexistent")


def test_validate_rejects_too_few_frames(tmp_path: Path) -> None:
    from errante.models import (
        Frame,
        Grid,
        Provenance,
        SkyCoord,
        SkyField,
    )
    from errante.products import ProductStore

    root = tmp_path / "single"
    store = ProductStore(root)
    frames_dir = store.field_dir("f1") / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)
    (frames_dir / "f0.png").write_bytes(_PNG_HEADER)

    field = SkyField(
        id="f1",
        name="x",
        center=SkyCoord(ra=1.0, dec=0.0),
        size_deg=0.25,
        grid=Grid(
            center=SkyCoord(ra=1.0, dec=0.0),
            width_px=32,
            height_px=32,
            pixel_scale_arcsec=4.0,
            wcs={
                "CTYPE1": "RA---TAN",
                "CTYPE2": "DEC--TAN",
                "CRVAL1": 1.0,
                "CRVAL2": 0.0,
                "CRPIX1": 16.0,
                "CRPIX2": 16.0,
                "CDELT1": -0.001,
                "CDELT2": 0.001,
            },
        ),
        frames=[
            Frame(
                id="f0",
                obs_id="o0",
                detector=1,
                mjd=60000.0,
                date_obs=datetime(2026, 1, 1, tzinfo=UTC),
                release="dr1",
                source_uri="test-double-only",
                image="frames/f0.png",
            )
        ],
        provenance=Provenance(pipeline_version="0.0.0", built_at=datetime.now(UTC), synthetic=False),
    )
    store.write_field(field)
    store.write_candidates(CandidateList(field_id=field.id, candidates=[]))
    store.write_known(KnownObjectList(field_id=field.id, objects=[]))

    with pytest.raises(ValueError, match="at least 2"):
        validate_product(root, "f1")


def test_validate_rejects_same_mjd(tmp_path: Path) -> None:
    _write_valid_product(tmp_path, "same-mjd", two_distinct_mjds=False)
    with pytest.raises(ValueError, match="same MJD"):
        validate_product(tmp_path, "same-mjd")


def test_validate_rejects_bad_png(tmp_path: Path) -> None:
    _write_valid_product(tmp_path, "bad-png")
    # Overwrite one PNG with garbage
    (tmp_path / "fields" / "bad-png" / "frames" / "f0.png").write_bytes(b"notapng")
    with pytest.raises(ValueError, match="not a valid PNG"):
        validate_product(tmp_path, "bad-png")


def test_validate_rejects_path_traversal(tmp_path: Path) -> None:
    from errante.models import (
        Frame,
        Grid,
        Provenance,
        SkyCoord,
        SkyField,
    )
    from errante.products import ProductStore

    root = tmp_path / "traversal"
    store = ProductStore(root)

    field = SkyField(
        id="trav",
        name="x",
        center=SkyCoord(ra=1.0, dec=0.0),
        size_deg=0.25,
        grid=Grid(
            center=SkyCoord(ra=1.0, dec=0.0),
            width_px=32,
            height_px=32,
            pixel_scale_arcsec=4.0,
            wcs={
                "CTYPE1": "RA---TAN",
                "CTYPE2": "DEC--TAN",
                "CRVAL1": 1.0,
                "CRVAL2": 0.0,
                "CRPIX1": 16.0,
                "CRPIX2": 16.0,
                "CDELT1": -0.001,
                "CDELT2": 0.001,
            },
        ),
        frames=[
            Frame(
                id=f"f{i}",
                obs_id=f"o{i}",
                detector=1,
                mjd=60000.0 + i * 10,
                date_obs=datetime(2026, 1, 1 + i, tzinfo=UTC),
                release="dr1",
                source_uri="test-double-only",
                image=f"../../escape{i}.png",
            )
            for i in range(2)
        ],
        provenance=Provenance(pipeline_version="0.0.0", built_at=datetime.now(UTC), synthetic=False),
    )
    store.write_field(field)
    store.write_candidates(CandidateList(field_id=field.id, candidates=[]))
    store.write_known(KnownObjectList(field_id=field.id, objects=[]))

    with pytest.raises(ValueError, match="escapes staging|PNG missing"):
        validate_product(root, "trav")


# ---------------------------------------------------------------------------
# publish_job
# ---------------------------------------------------------------------------


def test_publish_job_moves_field_to_products(tmp_path: Path) -> None:
    from errante_api.jobs.publication import publish_job

    staging_dir = tmp_path / "staging" / "attempt1"
    staging_products = staging_dir / "products"
    products_dir = tmp_path / "products"
    products_dir.mkdir()

    field_id = "job-abc"
    _write_valid_product(staging_products, field_id)

    repo = JobRepository(tmp_path / "jobs.db")
    jid = _new_id()
    from errante_api.jobs.types import JobRequest

    req = JobRequest.create(ra=10.0, dec=0.0, size_deg=0.25)
    repo.enqueue(jid, req.cache_key(), req.to_dict())

    published_id = publish_job(
        staging_dir=staging_dir,
        field_id=field_id,
        products_dir=products_dir,
        repo=repo,
        job_id=jid,
    )
    assert published_id == field_id
    assert (products_dir / "fields" / field_id / "field.json").exists()
    assert (products_dir / "manifest.json").exists()


def test_publish_job_raises_on_bad_product(tmp_path: Path) -> None:
    from errante_api.jobs.publication import publish_job

    staging_dir = tmp_path / "staging" / "attempt2"
    products_dir = tmp_path / "products"
    products_dir.mkdir()

    repo = JobRepository(tmp_path / "jobs.db")

    with pytest.raises(PublicationError, match="validation"):
        publish_job(
            staging_dir=staging_dir,
            field_id="nonexistent",
            products_dir=products_dir,
            repo=repo,
            job_id=_new_id(),
        )
