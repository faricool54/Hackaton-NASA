"""Validated frozen comparisons and immutable PNGs, with no archive calls on GET."""

from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi import Path as Param
from fastapi.responses import FileResponse
from PIL import Image

from errante.models import ComparisonResponse, SkyField

from .routes.science import read_field

BUNDLE = Path(__file__).parent / "curated" / "comparisons"
router = APIRouter(tags=["precomputed comparisons"])


def asset(public: Path, relative: str) -> Path:
    for root in (public, BUNDLE):
        path = root / relative
        if not path.resolve().is_relative_to(root.resolve()):
            raise HTTPException(404, "Comparison image not found.")
        if path.is_file():
            return path
    raise HTTPException(404, "Comparison image not found.")


def read_snapshot(public: Path, field: SkyField) -> ComparisonResponse:
    candidates = (public / "fields" / field.id / "comparisons.json", BUNDLE / "index" / f"{field.id}.json")
    path = next((p for p in candidates if p.is_file()), None)
    if path is None:
        raise HTTPException(404, "No precomputed comparisons for this field.")
    try:
        if not path.resolve().is_relative_to(public.resolve()) and not path.resolve().is_relative_to(BUNDLE.resolve()):
            raise ValueError("Snapshot escapes its product root")
        with path.open("rb") as stream:
            payload = stream.read(2 * 1024**2 + 1)
        if len(payload) > 2 * 1024**2:
            raise ValueError("Oversized comparison snapshot")
        result = ComparisonResponse.model_validate_json(payload)
        if (
            field.provenance.synthetic
            or result.field_id != field.id
            or result.field_built_at != field.provenance.built_at
        ):
            raise HTTPException(409, "Comparison snapshot does not match the current real field; regenerate it.")
        originals = {f.id: f for f in field.frames}
        if any(originals.get(f.id) != f or f.release == "synthetic" or not f.source_uri for f in result.input_frames):
            raise HTTPException(409, "Comparison inputs differ from the current real field.")
        for item in result.images:
            try:
                image_path = asset(public, item.image)
            except HTTPException as error:
                raise ValueError("Missing comparison PNG") from error
            with Image.open(image_path) as image:
                if image.format != "PNG" or image.size != (field.grid.width_px, field.grid.height_px):
                    raise ValueError("Invalid comparison PNG")
                image.verify()
        return result
    except (OSError, ValueError, SyntaxError) as error:
        raise HTTPException(503, "Precomputed comparison is unavailable or invalid.") from error


@router.get("/api/fields/{field_id}/comparisons", response_model=ComparisonResponse)
def snapshot(request: Request, field_id: str = Param(pattern=r"^[a-z0-9][a-z0-9-]*$")):
    """Frozen WS2 comparison; unknown snapshot 404, changed inputs 409, damaged JSON/PNG 503."""
    return read_snapshot(request.app.state.store.root, read_field(request, field_id))


@router.get("/data/analyses/{analysis_id}/compare/{filename}", include_in_schema=False)
def image(
    request: Request,
    analysis_id: str = Param(pattern=r"^[a-f0-9]{64}$"),
    filename: str = Param(pattern=r"^[a-zA-Z0-9_-]+\.png$"),
):
    return FileResponse(asset(request.app.state.store.root, f"analyses/{analysis_id}/compare/{filename}"))
