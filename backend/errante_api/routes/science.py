"""Scientific measurements are independent of candidates and leave the field intact."""

from fastapi import APIRouter, HTTPException, Path, Request

from errante.models import ComparisonRequest, ComparisonResponse, SpectrumRequest, SpectrumResponse

router = APIRouter(tags=["science"])


def read_field(request, field_id):
    store = request.app.state.store
    path = store.field_dir(field_id) / "field.json"
    if not path.resolve().is_relative_to(store.root.resolve()) or not path.is_file():
        raise HTTPException(404, "Field not found.")
    return store.read_field(field_id)


@router.post("/spectra", response_model=SpectrumResponse)
async def spectrum(body: SpectrumRequest, request: Request):
    """DR1 quick-look cube or native-exposure photometry (fixed sky position).

    Separate units, source, missing data, dates, quality and uncertainty. Bounded
    worker and single-flight cache; a disconnected caller does not cancel shared work.
    """
    field = read_field(request, body.field_id) if body.field_id else None
    return await request.app.state.science.spectrum(body, field)


@router.post("/fields/{field_id}/comparisons", response_model=ComparisonResponse)
async def comparisons(
    body: ComparisonRequest,
    request: Request,
    field_id: str = Path(pattern=r"^[a-z0-9][a-z0-9-]*$"),
):
    """Weighted season means and later - scale * earlier, per detector.

    Maximum 60 selected frames and 512×512 pixels. Unknown frames: 422;
    synthetic data: 409; admission busy: 503; bounded worker failure: 502/504.
    Returned PNG paths are relative to /data and are published atomically.
    """
    return await request.app.state.science.comparisons(read_field(request, field_id), body)
