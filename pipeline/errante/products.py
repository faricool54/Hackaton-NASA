"""Read/write the on-disk product layout (shared by pipeline and backend).

    <root>/manifest.json                    Manifest
    <root>/fields/<field_id>/field.json     SkyField
    <root>/fields/<field_id>/candidates.json CandidateList
    <root>/fields/<field_id>/known.json     KnownObjectList
    <root>/fields/<field_id>/frames/<frame_id>.png
    <root>/fields/<field_id>/thumb.png

The static frontend reads exactly these files, and the backend serves them
under /api/... (JSON) and /data/... (images). Keep this layout stable.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import TypeVar

from pydantic import BaseModel

from .models import (
    SCHEMA_VERSION,
    CandidateList,
    FieldSummary,
    KnownObjectList,
    Manifest,
    SkyField,
)

M = TypeVar("M", bound=BaseModel)


class ProductStore:
    def __init__(self, root: Path | str):
        self.root = Path(root)

    # --- paths -----------------------------------------------------------
    def field_dir(self, field_id: str) -> Path:
        return self.root / "fields" / field_id

    @property
    def manifest_path(self) -> Path:
        return self.root / "manifest.json"

    # --- generic IO ------------------------------------------------------
    @staticmethod
    def _write(path: Path, model: BaseModel) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(model.model_dump_json(indent=2, exclude_none=False) + "\n", encoding="utf-8")
        return path

    @staticmethod
    def _read(path: Path, cls: type[M]) -> M:
        return cls.model_validate_json(path.read_text(encoding="utf-8"))

    # --- writers (pipeline) ------------------------------------------------
    def write_field(self, field: SkyField) -> Path:
        return self._write(self.field_dir(field.id) / "field.json", field)

    def write_candidates(self, cands: CandidateList) -> Path:
        return self._write(self.field_dir(cands.field_id) / "candidates.json", cands)

    def write_known(self, known: KnownObjectList) -> Path:
        return self._write(self.field_dir(known.field_id) / "known.json", known)

    def rebuild_manifest(self) -> Manifest:
        """Scan fields/ and (re)write manifest.json. Call after building any field."""
        summaries: list[FieldSummary] = []
        fields_root = self.root / "fields"
        for fdir in sorted(p for p in fields_root.glob("*") if (p / "field.json").exists()):
            field = self._read(fdir / "field.json", SkyField)
            cands = self.read_candidates(field.id)
            mjds = [f.mjd for f in field.frames]
            summaries.append(
                FieldSummary(
                    id=field.id,
                    name=field.name,
                    description=field.description,
                    tags=field.tags,
                    center=field.center,
                    size_deg=field.size_deg,
                    n_frames=len(field.frames),
                    n_candidates=len(cands.candidates),
                    mjd_range=(min(mjds), max(mjds)) if mjds else None,
                    thumbnail="thumb.png" if (fdir / "thumb.png").exists() else None,
                    synthetic=field.provenance.synthetic,
                )
            )
        manifest = Manifest(
            schema_version=SCHEMA_VERSION,
            generated_at=datetime.now(UTC),
            synthetic=any(s.synthetic for s in summaries),
            fields=summaries,
        )
        self._write(self.manifest_path, manifest)
        return manifest

    # --- readers (backend) -------------------------------------------------
    def read_manifest(self) -> Manifest:
        return self._read(self.manifest_path, Manifest)

    def read_field(self, field_id: str) -> SkyField:
        return self._read(self.field_dir(field_id) / "field.json", SkyField)

    def read_candidates(self, field_id: str) -> CandidateList:
        path = self.field_dir(field_id) / "candidates.json"
        if not path.exists():
            return CandidateList(field_id=field_id, candidates=[])
        return self._read(path, CandidateList)

    def read_known(self, field_id: str) -> KnownObjectList:
        path = self.field_dir(field_id) / "known.json"
        if not path.exists():
            return KnownObjectList(field_id=field_id, objects=[])
        return self._read(path, KnownObjectList)

    def has_field(self, field_id: str) -> bool:
        return (self.field_dir(field_id) / "field.json").exists()
