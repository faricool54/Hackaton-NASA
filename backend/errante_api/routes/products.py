"""Read-only endpoints over the product tree (implemented)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, HTTPException, Path, Request

from errante.models import CandidateList, KnownObjectList, Manifest, SkyField, SystemModel
from errante.products import ProductStore

router = APIRouter(tags=["products"])
Slug = Annotated[str, Path(pattern=r"^[a-z0-9][a-z0-9-]*$")]


def _store(request: Request) -> ProductStore:
    return request.app.state.store


def _require_field(store: ProductStore, field_id: str) -> None:
    if not store.has_field(field_id):
        raise HTTPException(status_code=404, detail=f"Unknown field '{field_id}'")


@router.get("/manifest", response_model=Manifest)
def get_manifest(request: Request) -> Manifest:
    store = _store(request)
    if not store.manifest_path.exists():
        raise HTTPException(
            status_code=503,
            detail="No products built. Run `make demo` or `errante build`.",
        )
    return store.read_manifest()


@router.get("/fields/{field_id}", response_model=SkyField)
def get_field(field_id: Slug, request: Request) -> SkyField:
    store = _store(request)
    _require_field(store, field_id)
    return store.read_field(field_id)


@router.get("/fields/{field_id}/candidates", response_model=CandidateList)
def get_candidates(field_id: Slug, request: Request) -> CandidateList:
    store = _store(request)
    _require_field(store, field_id)
    return store.read_candidates(field_id)


@router.get("/fields/{field_id}/known", response_model=KnownObjectList)
def get_known(field_id: Slug, request: Request) -> KnownObjectList:
    store = _store(request)
    _require_field(store, field_id)
    return store.read_known(field_id)


@router.get("/systems/{system_id}", response_model=SystemModel)
def get_system(system_id: Slug, request: Request) -> SystemModel:
    store = _store(request)
    if not store.has_system(system_id):
        raise HTTPException(status_code=404, detail=f"Unknown system '{system_id}'")
    return store.read_system(system_id)
