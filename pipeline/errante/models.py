"""Data contract shared by pipeline, backend and frontend.

THIS FILE IS THE SOURCE OF TRUTH for every JSON file the pipeline writes and
every response the API returns. The frontend mirrors it in
``frontend/src/api/types.ts`` and ``shared/schema/*.json`` is generated from it.

Changing anything here is a *contract change* (see docs/WORKFLOW.md):
  1. Open a PR titled ``contract: ...`` and ping WS4 (backend) + WS5 (frontend).
  2. Run ``make schema`` to regenerate ``shared/schema/``.
  3. Update ``frontend/src/api/types.ts`` in the same PR.
  4. Bump ``SCHEMA_VERSION`` (minor = additive, major = breaking).
Prefer *adding optional fields* over renaming/removing.

Pixel convention for every ``x``/``y`` in this contract ("PNG convention"):
  origin at the TOP-LEFT pixel, 0-based, x grows to the right, y grows DOWN,
  on the field's common north-up grid (north up, east left). This is what the
  browser needs to draw overlays on the frame PNGs without any WCS math.
  FITS convention differs: x_fits = x + 1, y_fits = height - y.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

SCHEMA_VERSION = "0.1.0"

Release = Literal["dr1", "qr2", "qr3", "synthetic"]
"""SPHEREx data release a frame comes from (see docs/DATA.md)."""

ObjectType = Literal["asteroid", "comet", "tno", "dwarf_planet", "planet", "star", "brown_dwarf", "unknown"]
CandidateKind = Literal["moving", "proper_motion", "variable"]
CandidateStatus = Literal["unconfirmed", "known", "artifact", "injected"]
"""unconfirmed = not matched to any catalog (NOT a discovery claim);
known = matched to a cataloged object; artifact = rejected by vetting;
injected = simulated object planted to measure sensitivity."""

MatchSource = Literal["jpl_sbident", "jpl_horizons", "skybot", "simbad", "synthetic"]


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SkyCoord(_Model):
    ra: float = Field(ge=0, lt=360, description="ICRS right ascension [deg]")
    dec: float = Field(ge=-90, le=90, description="ICRS declination [deg]")


class Grid(_Model):
    """Common north-up TAN grid every frame of a field is reprojected onto."""

    center: SkyCoord
    width_px: int = Field(gt=0)
    height_px: int = Field(gt=0)
    pixel_scale_arcsec: float = Field(gt=0)
    wcs: dict[str, float | int | str] = Field(
        description="FITS WCS cards of the grid (CTYPE/CRVAL/CRPIX/CDELT), FITS convention"
    )


class Stretch(_Model):
    """How the PNG was scaled from physical units, so the UI can show a colorbar."""

    vmin: float
    vmax: float
    unit: str = "MJy/sr"
    method: Literal["linear", "asinh", "log", "zscale"] = "asinh"


class Frame(_Model):
    """One SPHEREx exposure (one detector), reprojected onto the field grid."""

    id: str = Field(description="Unique within the field, e.g. '2025W19_2B_0007_1D1'")
    obs_id: str = Field(description="SPHEREx OBSID header value")
    detector: int = Field(ge=1, le=6, description="1-3 SWIR, 4-6 MWIR")
    mjd: float = Field(description="Mid-exposure time (MJD-OBS) [days]")
    date_obs: datetime
    wavelength_um: float | None = Field(
        default=None, description="Central wavelength at the field center (from WCS-WAVE)"
    )
    bandwidth_um: float | None = None
    release: Release
    image: str = Field(description="PNG path relative to the field directory, e.g. 'frames/<id>.png'")
    source_uri: str | None = Field(default=None, description="Original FITS (IRSA or S3 URL)")
    valid_fraction: float | None = Field(
        default=None, ge=0, le=1, description="Fraction of grid with valid, unflagged pixels"
    )
    stretch: Stretch | None = None


class Detection(_Model):
    frame_id: str
    mjd: float
    position: SkyCoord
    x: float = Field(description="Grid pixel, PNG convention (see module docstring)")
    y: float
    flux_mjy: float | None = None
    flux_err_mjy: float | None = None
    snr: float | None = None


class Motion(_Model):
    rate_arcsec_per_hour: float = Field(ge=0)
    position_angle_deg: float = Field(ge=0, lt=360, description="Direction of motion, east of north")
    ra_cosdec_rate_arcsec_per_hour: float
    dec_rate_arcsec_per_hour: float


class DistanceEstimate(_Model):
    au_median: float = Field(gt=0)
    au_low: float | None = Field(default=None, gt=0)
    au_high: float | None = Field(default=None, gt=0)
    method: str = Field(description="e.g. 'opposition_rate', 'statistical_ranging', 'parallax_fit'")


class KnownMatch(_Model):
    designation: str
    name: str | None = None
    object_type: ObjectType = "unknown"
    source: MatchSource
    separation_arcsec: float = Field(ge=0)
    predicted_vmag: float | None = None


class SpectrumPoint(_Model):
    frame_id: str
    wavelength_um: float
    bandwidth_um: float | None = None
    flux_mjy: float
    flux_err_mjy: float | None = None


class Candidate(_Model):
    id: str
    field_id: str
    kind: CandidateKind
    status: CandidateStatus
    score: float = Field(ge=0, le=1, description="Pipeline confidence that it is a real object")
    detections: list[Detection] = Field(min_length=1)
    motion: Motion | None = None
    distance: DistanceEstimate | None = None
    known_match: KnownMatch | None = None
    spectrum: list[SpectrumPoint] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list, description="Plain-language caveats for the UI")


class CandidateList(_Model):
    field_id: str
    candidates: list[Candidate]


class KnownObjectPosition(_Model):
    frame_id: str
    mjd: float
    position: SkyCoord
    x: float
    y: float
    in_frame: bool = True


class KnownObject(_Model):
    designation: str
    name: str | None = None
    object_type: ObjectType = "unknown"
    source: MatchSource
    vmag: float | None = None
    positions: list[KnownObjectPosition]


class KnownObjectList(_Model):
    field_id: str
    objects: list[KnownObject]


class Provenance(_Model):
    pipeline_version: str
    built_at: datetime
    synthetic: bool = Field(description="True = fake data for development. The UI MUST say so.")
    data_releases: list[Release] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class SkyField(_Model):
    """A patch of sky with all its frames. Called 'Field' in JSON Schema / TypeScript."""

    model_config = ConfigDict(extra="forbid", title="Field")

    id: str = Field(pattern=r"^[a-z0-9][a-z0-9-]*$", description="URL-safe slug")
    name: str
    description: str = ""
    tags: list[str] = Field(default_factory=list, description="e.g. 'ecliptic', 'deep-field', 'planet-nine-region'")
    center: SkyCoord
    size_deg: float = Field(gt=0)
    grid: Grid
    frames: list[Frame]
    provenance: Provenance


class FieldSummary(_Model):
    id: str
    name: str
    description: str = ""
    tags: list[str] = Field(default_factory=list)
    center: SkyCoord
    size_deg: float
    n_frames: int
    n_candidates: int
    mjd_range: tuple[float, float] | None = None
    thumbnail: str | None = Field(default=None, description="Path relative to the field directory")
    synthetic: bool


class Manifest(_Model):
    schema_version: str = SCHEMA_VERSION
    generated_at: datetime
    synthetic: bool = Field(description="True if ANY field is synthetic")
    fields: list[FieldSummary]


# --- Live archive search (WS1 -> WS4 `/api/search`) -------------------------


class FrameRef(_Model):
    """A SPHEREx Level-2 file that covers a position (result of an archive query)."""

    obs_id: str
    detector: int = Field(ge=1, le=6)
    mjd: float
    release: Release
    irsa_uri: str | None = Field(default=None, description="Relative IRSA path 'ibe/data/spherex/...'")
    s3_key: str | None = Field(default=None, description="Key in s3://nasa-irsa-spherex/")
    wavelength_um: float | None = None


class SearchResult(_Model):
    center: SkyCoord
    radius_deg: float
    frames: list[FrameRef]


ALL_MODELS: dict[str, type[BaseModel]] = {
    "Manifest": Manifest,
    "Field": SkyField,
    "CandidateList": CandidateList,
    "KnownObjectList": KnownObjectList,
    "SearchResult": SearchResult,
}
"""Top-level documents, one JSON Schema file each in shared/schema/."""
