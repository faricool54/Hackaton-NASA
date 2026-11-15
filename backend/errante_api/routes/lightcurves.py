"""Read-only light-curve products. Expensive calculations run offline, never on GET."""

from fastapi import APIRouter, Path, Request, Response

from errante.models import LightCurveIndex, LightCurveProduct

router = APIRouter(tags=["light curves"])


@router.get("/lightcurves", response_model=LightCurveIndex)
def lightcurve_index(request: Request):
    """Schema-checked snapshots (including explicit no-usable-points results), not R05 certification."""
    return request.app.state.lightcurves.index()


@router.get("/lightcurves/{target_id}", response_model=LightCurveProduct)
def lightcurve(request: Request, target_id: str = Path(pattern=r"^[a-z0-9][a-z0-9-]{0,79}$")):
    """Snapshot of the WS3 calculation, with statistical errors, controls and exclusions.

    A best-fit sinusoid remains a candidate even when variability is significant. Wing
    values are relative PSF-wing surface brightness, never total source flux.
    404: no precomputed product; 503: invalid/unreadable product. No archive I/O.
    """
    _, payload, etag = request.app.state.lightcurves.read(target_id)
    headers = {"ETag": etag, "Cache-Control": "public, max-age=60, must-revalidate"}
    offered = [x.strip().removeprefix("W/") for x in request.headers.get("if-none-match", "").split(",")]
    if etag in offered or "*" in offered:
        return Response(status_code=304, headers=headers)
    return Response(content=payload, media_type="application/json", headers=headers)
