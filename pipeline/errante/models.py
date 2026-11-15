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
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, FiniteFloat, field_validator, model_validator

SCHEMA_VERSION = "0.5.0"

Release = Literal["dr1", "qr2", "qr3", "synthetic"]
"""SPHEREx data release a frame comes from (see docs/DATA.md)."""

ObjectType = Literal["asteroid", "comet", "tno", "dwarf_planet", "planet", "star", "brown_dwarf", "unknown"]
CandidateKind = Literal["moving", "proper_motion", "variable"]
CandidateStatus = Literal["unconfirmed", "known", "artifact", "injected"]
"""unconfirmed = not matched to any catalog (NOT a discovery claim);
known = matched to a cataloged object; artifact = rejected by vetting;
injected = simulated object planted to measure sensitivity."""

MatchSource = Literal["jpl_sbident", "jpl_horizons", "skybot", "simbad", "synthetic"]

CompositeMode = Literal["detectors", "jhk"]
"""How a FALSE-COLOR composite maps SPHEREx infrared wavelengths to red/green/blue.
detectors = channels built from whole SPHEREx detectors over the full 0.75-5.0 um range;
jhk = 2MASS-like: channels from exposures near the J, H and Ks bands (~1.25, ~1.65, ~2.15 um).
By convention blue = shortest and red = longest wavelengths (chromatic order)."""
CompositeColor = Literal["red", "green", "blue"]


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
    mjd: float = Field(
        description="Mid-exposure time [MJD days]: header MJD-AVG (fallbacks in docs/DATA.md; MJD-OBS is the START)"
    )
    date_obs: datetime = Field(description="Same instant as mjd, ISO-8601 UTC (header DATE-AVG)")
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


class CompositeChannel(_Model):
    """One color channel of a FALSE-COLOR composite: which infrared exposures were mapped to it."""

    color: CompositeColor = Field(description="Display channel these infrared exposures are mapped to")
    detector: int | None = Field(
        default=None, ge=1, le=6, description="SPHEREx detector of every input; None = inputs from several detectors"
    )
    wavelength_um: float | None = Field(
        default=None, gt=0, description="Mean central wavelength of the inputs at the field centre [um]"
    )
    wavelength_min_um: float | None = Field(
        default=None, gt=0, description="Shortest central wavelength among the inputs at the field centre [um]"
    )
    wavelength_max_um: float | None = Field(
        default=None, gt=0, description="Longest central wavelength among the inputs at the field centre [um]"
    )
    frame_ids: list[str] = Field(
        min_length=1,
        description="Exposures combined into this channel (Frame.id convention). They may include exposures "
        "that are not published in Field.frames.",
    )

    @model_validator(mode="after")
    def _check_wavelength_range(self) -> CompositeChannel:
        lo, hi, mean = self.wavelength_min_um, self.wavelength_max_um, self.wavelength_um
        if lo is not None and hi is not None and lo > hi:
            raise ValueError(f"wavelength_min_um ({lo}) > wavelength_max_um ({hi})")
        if mean is not None and lo is not None and hi is not None and not lo <= mean <= hi:
            raise ValueError(f"wavelength_um ({mean}) outside [{lo}, {hi}]")
        return self


class Composite(_Model):
    """A FALSE-COLOR infrared composite of one observing season, as an RGB(A) PNG on the field grid.

    SPHEREx observes 0.75-5.0 um, invisible to the eye: red/green/blue are assigned to infrared
    wavelengths (see CompositeMode). It is NOT a true-color image and the UI must say so.
    """

    id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]*$", description="Unique within the field, e.g. 'detectors_S0'")
    mode: CompositeMode = Field(
        description="detectors = whole SPHEREx detectors over the full 0.75-5.0 um range; jhk = 2MASS-like, "
        "exposures near J/H/Ks (~1.25/1.65/2.15 um). Blue = shortest, red = longest wavelengths."
    )
    season: int = Field(ge=0, description="0-based observing season of the field (0 = earliest)")
    mjd_min: float = Field(description="Earliest mid-exposure MJD among the inputs [days]")
    mjd_max: float = Field(description="Latest mid-exposure MJD among the inputs [days]")
    image: str = Field(
        pattern=r"\.png$",
        description="RGB/RGBA PNG on the field grid, path relative to the field directory (no '..', no "
        "absolute or Windows paths), e.g. 'color/detectors_S0.png'",
    )
    channels: list[CompositeChannel] = Field(
        min_length=3, max_length=3, description="Exactly three channels, in the order red, green, blue"
    )
    notes: list[str] = Field(default_factory=list, description="Plain-language caveats for the UI")

    @model_validator(mode="after")
    def _check_composite(self) -> Composite:
        image = self.image
        parts = image.split("/")
        if (
            "\\" in image
            or image.startswith("/")
            or (len(image) > 1 and image[1] == ":")
            or ".." in parts
            or "" in parts
            or any(ch in image for ch in "?#")
        ):
            raise ValueError(f"image must be a relative path inside the field directory, got {image!r}")
        if self.mjd_min > self.mjd_max:
            raise ValueError(f"mjd_min ({self.mjd_min}) > mjd_max ({self.mjd_max})")
        colors = [c.color for c in self.channels]
        if colors != ["red", "green", "blue"]:
            raise ValueError(f"channels must be red, green, blue in this order, got {colors}")
        return self


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
    composites: list[Composite] = Field(
        default_factory=list,
        description="Optional FALSE-COLOR infrared composites per observing season (infrared wavelengths mapped "
        "to RGB, not true color). Empty when none were built; absent in products older than 0.3.1.",
    )

    @model_validator(mode="after")
    def _check_unique_composite_ids(self) -> SkyField:
        ids = [c.id for c in self.composites]
        duplicates = sorted({i for i in ids if ids.count(i) > 1})
        if duplicates:
            raise ValueError(f"composite ids must be unique within a field, repeated: {duplicates}")
        return self


# --- 3D systems (WS7): models of the objects we track and their systems ------
#
# A SystemModel describes a star/planetary system (or a single object) so the
# frontend can draw it in 3D: bodies with physical parameters, Keplerian orbits
# around a parent body, variability, and plain-language facts with sources.
# It is a MODEL REPRESENTATION built from catalog parameters, never an image:
# the UI must say so (see docs/VISION_3D.md). Values typed by hand that have not
# been checked against a catalog carry `verified = false`.

BodyKind = Literal[
    "star", "brown_dwarf", "planet", "dwarf_planet", "moon", "asteroid", "comet", "tno", "disk", "unknown"
]
AppearanceModel = Literal["star", "brown_dwarf", "rocky", "icy", "gas_giant", "disk", "mesh"]
VariabilityKind = Literal["pulsation", "accretion", "eclipse", "rotation", "irregular"]
OrbitQuality = Literal["fitted", "assumed", "hypothetical"]


class Fact(_Model):
    """One human-readable fact shown in a body's info panel."""

    label: str = Field(description="e.g. 'Distance', 'Spectral type'")
    value: str = Field(description="Display value, already formatted, e.g. '1.83'")
    unit: str | None = Field(default=None, description="e.g. 'pc', 'K', 'Earth masses'")
    source: str | None = Field(default=None, description="Catalog/paper/URL the value comes from")
    verified: bool = Field(default=False, description="True only if checked against `source`")


class Orbit(_Model):
    """Keplerian orbit of a body around its parent (two-body approximation)."""

    parent: str = Field(description="Body.id of the body it orbits (or the barycenter body)")
    semi_major_axis_au: float = Field(gt=0)
    period_days: float = Field(gt=0)
    eccentricity: float = Field(default=0.0, ge=0, lt=1)
    inclination_deg: float = Field(default=0.0, ge=0, le=180)
    ascending_node_deg: float = Field(default=0.0, ge=0, lt=360)
    arg_periapsis_deg: float = Field(default=0.0, ge=0, lt=360)
    mean_anomaly_deg: float = Field(default=0.0, ge=0, lt=360, description="At epoch_mjd")
    epoch_mjd: float | None = Field(default=None, description="Epoch of mean_anomaly_deg; None = arbitrary phase")
    quality: OrbitQuality = Field(
        default="fitted",
        description="fitted = published orbital solution; assumed = NOT fitted (e.g. circle at a projected "
        "separation or a distance estimate); hypothetical = proposed object (e.g. Planet Nine). The UI marks "
        "anything but 'fitted'.",
    )
    note: str | None = Field(default=None, description="Plain-language caveat about this orbit, shown in the UI")


class Variability(_Model):
    kind: VariabilityKind
    period_days: float | None = Field(default=None, gt=0)
    amplitude_mag: float | None = Field(default=None, ge=0)
    band: str | None = Field(default=None, description="Band the amplitude refers to, e.g. 'V', 'K', 'SPHEREx 2 um'")


class Appearance(_Model):
    """Rendering hints. The UI derives everything it can from physics (teff -> color)."""

    model: AppearanceModel
    color_hex: str | None = Field(default=None, pattern=r"^#[0-9a-fA-F]{6}$", description="Override base color")
    mesh_url: str | None = Field(
        default=None, description="glTF/OBJ shape model (e.g. radar/lightcurve asteroid shape)"
    )
    texture_url: str | None = None


class Body(_Model):
    id: str = Field(pattern=r"^[a-z0-9][a-z0-9-]*$", description="URL-safe slug, unique within the system")
    name: str
    kind: BodyKind
    description: str = ""
    radius_km: float | None = Field(default=None, gt=0)
    mass_kg: float | None = Field(default=None, gt=0)
    teff_k: float | None = Field(default=None, gt=0, description="Effective temperature; drives the color")
    spectral_type: str | None = None
    rotation_period_hours: float | None = Field(default=None, gt=0)
    orbit: Orbit | None = Field(default=None, description="None = the system's root body (sits at the origin)")
    variability: Variability | None = None
    appearance: Appearance
    facts: list[Fact] = Field(default_factory=list)
    candidate_id: str | None = Field(default=None, description="Linked Candidate.id in SystemModel.field_id")


class SpaceMotion(_Model):
    """Where the system is and how it moves through the Galaxy (drives the 'move through space' view)."""

    distance_pc: float | None = Field(default=None, gt=0)
    parallax_mas: float | None = Field(default=None, gt=0)
    pm_ra_cosdec_mas_yr: float | None = None
    pm_dec_mas_yr: float | None = None
    radial_velocity_km_s: float | None = None
    epoch: str | None = Field(default=None, description="Reference epoch of position/motion, e.g. 'J2016.0' (Gaia DR3)")


class SystemModel(_Model):
    id: str = Field(pattern=r"^[a-z0-9][a-z0-9-]*$", description="URL-safe slug")
    name: str
    description: str = ""
    tags: list[str] = Field(default_factory=list, description="e.g. 'test-target', 'brown-dwarf', 'variable'")
    center: SkyCoord
    motion: SpaceMotion | None = None
    field_id: str | None = Field(default=None, description="SPHEREx field (SkyField.id) where it is observed")
    bodies: list[Body] = Field(min_length=1)
    representation_note: str = Field(
        default="Model representation built from catalog parameters - not an image. Sizes and distances may be "
        "exaggerated for visibility.",
        description="Shown by the UI next to every 3D view",
    )
    provenance: Provenance


class SystemSummary(_Model):
    id: str
    name: str
    description: str = ""
    tags: list[str] = Field(default_factory=list)
    center: SkyCoord
    n_bodies: int
    kinds: list[BodyKind] = Field(default_factory=list, description="Distinct body kinds, for icons/filters")
    field_id: str | None = None
    synthetic: bool


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
    synthetic: bool = Field(description="True if ANY field or system is synthetic")
    fields: list[FieldSummary]
    systems: list[SystemSummary] = Field(default_factory=list, description="3D system models (WS7)")


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


class JobSubmitRequest(_Model):
    """POST /api/jobs. Optional filters default to a bounded real-image build."""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    ra: float = Field(ge=0, lt=360)
    dec: float = Field(ge=-90, le=90)
    size_deg: float = Field(default=0.25, ge=0.01, le=0.5)
    detectors: list[Annotated[int, Field(ge=1, le=6)]] = Field(default_factory=list)
    mjd_min: float | None = None
    mjd_max: float | None = None
    max_frames: int = Field(default=40, ge=2, le=120)

    @model_validator(mode="after")
    def ordered_epochs(self):
        if self.mjd_min is not None and self.mjd_max is not None and self.mjd_min > self.mjd_max:
            raise ValueError("mjd_min must not exceed mjd_max")
        return self


PublicJobStatus = Literal["queued", "running", "ready", "failed", "no_coverage", "pipeline_not_ready"]


class JobStatusResponse(_Model):
    """POST /api/jobs (202) and GET /api/jobs/{id} (200). Publication maps to running."""

    id: str
    status: PublicJobStatus
    stage: str
    created_at: datetime
    updated_at: datetime
    result_field_id: str | None = None
    error_detail: str | None = None


class ResolvedRegion(SkyCoord):
    """GET /api/resolve-name. A catalog coordinate, not proof of SPHEREx coverage."""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    object_type: ObjectType
    resolved_name: str
    source: str


class SpectrumRequest(SkyCoord):
    """Bounded extraction at a fixed ICRS position; independent of detected candidates."""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    source: Literal["dr1_cube", "l2_exposures"] = "dr1_cube"
    detectors: list[Annotated[int, Field(ge=1, le=6)]] = Field(default_factory=list)
    mjd_min: FiniteFloat | None = None
    mjd_max: FiniteFloat | None = None
    field_id: str | None = Field(default=None, pattern=r"^[a-z0-9][a-z0-9-]*$")
    aperture_px: int = Field(default=0, ge=0, le=3, description="Cube aperture radius; L2 uses WS2's native aperture")
    max_frames: int = Field(default=24, ge=2, le=60)

    @model_validator(mode="after")
    def compatible_selection(self):
        if self.mjd_min is not None and self.mjd_max is not None and self.mjd_min > self.mjd_max:
            raise ValueError("mjd_min must not exceed mjd_max")
        if self.source == "dr1_cube" and (self.mjd_min is not None or self.mjd_max is not None):
            raise ValueError("A static cube cannot be filtered by observation date")
        if self.source == "l2_exposures" and self.aperture_px:
            raise ValueError("aperture_px selects a cube aperture; L2 uses WS2's native aperture")
        return self


class MeasurementFailure(_Model):
    frame_id: str | None = None
    reason: Literal["download_failed", "measurement_failed", "no_overlap", "invalid_pixels"]


class SpectralMeasurement(_Model):
    id: str
    detector: int = Field(ge=1, le=6)
    wavelength_um: FiniteFloat | None = Field(default=None, gt=0)
    bandwidth_um: FiniteFloat | None = Field(default=None, gt=0)
    flux: FiniteFloat | None = None
    flux_err: FiniteFloat | None = Field(default=None, ge=0)
    usable: bool
    flags: list[str] = Field(default_factory=list)
    frame_id: str | None = None
    mjd: FiniteFloat | None = None
    release: Release = "dr1"
    source_uri: str | None = None
    nhits: int | None = Field(default=None, ge=0)
    n_used: int | None = Field(default=None, ge=0)
    aperture_correction: FiniteFloat | None = None

    @model_validator(mode="after")
    def valid_measurement(self):
        if self.usable and (self.flux is None or self.wavelength_um is None):
            raise ValueError("Usable measurements need finite flux and wavelength")
        return self


class SpectrumResponse(_Model):
    schema_version: str = SCHEMA_VERSION
    center: SkyCoord
    source: Literal["dr1_cube", "l2_exposures"]
    unit: Literal["MJy/sr", "mJy"]
    static_coadd: bool
    points: list[SpectralMeasurement]
    built_at: datetime
    field_id: str | None = None
    mjd_range: tuple[FiniteFloat | None, FiniteFloat | None] = (None, None)
    pixel_scale_arcsec: FiniteFloat | None = None
    aperture_px: FiniteFloat
    background_subtracted: bool
    synthetic: Literal[False] = False
    truncated: bool = False
    stale: bool = False
    notes: list[str] = Field(default_factory=list)
    failures: list[MeasurementFailure] = Field(default_factory=list)

    @model_validator(mode="after")
    def consistent_units(self):
        if (self.source == "dr1_cube") != (self.unit == "MJy/sr" and self.static_coadd):
            raise ValueError("Cube spectra are static surface brightness; exposure spectra are mJy")
        if self.source == "l2_exposures" and (self.unit != "mJy" or self.static_coadd):
            raise ValueError("Exposure photometry must retain its mJy and time interpretation")
        return self


class ComparisonRequest(_Model):
    detectors: list[Annotated[int, Field(ge=1, le=6)]] = Field(default_factory=list)
    frame_ids: list[str] | None = Field(default=None, min_length=2, max_length=60)

    @field_validator("frame_ids")
    @classmethod
    def unique_frames(cls, ids):
        if ids is not None and len(ids) != len(set(ids)):
            raise ValueError("Frame IDs must be unique")
        return ids


class ComparisonImage(_Model):
    id: str
    kind: Literal["weighted_mean", "scaled_difference"]
    detector: int = Field(ge=1, le=6)
    image: str = Field(description="PNG relative to the API /data root")
    frame_ids: list[str] = Field(min_length=1)
    mjd_min: FiniteFloat
    mjd_max: FiniteFloat
    wavelength_range_um: tuple[FiniteFloat, FiniteFloat] | None = None
    season: int | None = None
    earlier: str | None = None
    later: str | None = None
    valid_fraction: FiniteFloat | None = Field(default=None, ge=0, le=1)
    flux_scale: FiniteFloat | None = None
    flux_scale_fitted: bool | None = None
    flux_scale_stars: int | None = Field(default=None, ge=0)
    noise_mjy_sr: FiniteFloat | None = Field(default=None, ge=0)
    display_limit_mjy_sr: FiniteFloat | None = Field(default=None, ge=0)
    target_exclude_px: FiniteFloat | None = Field(default=None, ge=0)
    weights: list[FiniteFloat] | None = Field(default=None, description="Null: individual weights not exported by WS2")
    notes: list[str] = Field(default_factory=list)

    @field_validator("image")
    @classmethod
    def contained_png(cls, value):
        import re

        if not re.fullmatch(r"analyses/[a-f0-9]{64}/compare/[a-zA-Z0-9_-]+\.png", value):
            raise ValueError("Expected a contained analysis PNG path")
        return value

    @model_validator(mode="after")
    def ordered_epochs(self):
        if self.mjd_min > self.mjd_max:
            raise ValueError("Reversed comparison epochs")
        if self.kind == "scaled_difference" and not (self.earlier and self.later and self.flux_scale is not None):
            raise ValueError("Differences need both inputs and the applied flux scale")
        return self


class ComparisonResponse(_Model):
    schema_version: str = SCHEMA_VERSION
    id: str = Field(pattern=r"^[a-f0-9]{64}$")
    field_id: str
    field_built_at: datetime
    built_at: datetime
    unit: Literal["MJy/sr"] = "MJy/sr"
    method: str
    input_frames: list[Frame] = Field(min_length=2, max_length=60)
    images: list[ComparisonImage]
    failures: list[MeasurementFailure] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    synthetic: Literal[False] = False

    @model_validator(mode="after")
    def referenced_inputs(self):
        frames = {frame.id: frame for frame in self.input_frames}
        if len(frames) != len(self.input_frames):
            raise ValueError("Input frame IDs must be unique")
        if len({image.id for image in self.images}) != len(self.images):
            raise ValueError("Image IDs must be unique")
        for image in self.images:
            if any(fid not in frames or frames[fid].detector != image.detector for fid in image.frame_ids):
                raise ValueError("Comparison references unknown or cross-detector frames")
            if image.image.split("/")[1] != self.id:
                raise ValueError("Image identity differs from its analysis")
            if image.kind == "scaled_difference":
                known = {i.id for i in self.images if i.kind == "weighted_mean" and i.detector == image.detector}
                if image.earlier not in known or image.later not in known:
                    raise ValueError("Differences must reference published coadds")
        return self


# --- Object card: catalog context of a position or a name (WS3 -> WS4 `/api/object`, 0.5.0, C05) --------------

ObjectMatch = Literal["name", "matched", "ambiguous", "loose", "none", "unavailable"]
"""How the catalog identity was reached.
name = the requested name was resolved by SIMBAD (Gaia DR3 identification, if any, not ambiguous);
matched = a click matched one Gaia DR3 source after proper-motion propagation to the epoch;
ambiguous = several Gaia DR3 sources of similar brightness inside the radius (identity not verified);
loose = the adopted Gaia DR3 source is farther than half the radius from the click (identity not verified);
none = no secure identification: no Gaia DR3 source inside the radius, or a name not resolved by SIMBAD;
unavailable = Gaia DR3 could not be reached: the identity is unknown, NOT a negative result."""
ContextServiceStatus = Literal["ok", "no_match", "error", "skipped"]
"""ok = answered with data; no_match = answered, nothing matched; error = did not answer (unknown, not a negative
result); skipped = not queried."""


class ObjectQuery(_Model):
    """What was asked: exactly one of ``name`` or ``ra`` + ``dec`` (ICRS degrees at ``epoch_mjd``)."""

    ra: FiniteFloat | None = Field(default=None, ge=0, lt=360)
    dec: FiniteFloat | None = Field(default=None, ge=-90, le=90)
    name: str | None = Field(default=None, min_length=1, max_length=200)
    epoch_mjd: FiniteFloat = Field(description="Epoch of the clicked position and of the reported one [MJD]")
    radius_arcsec: FiniteFloat = Field(gt=0, description="Match radius around the position [arcsec]")

    @model_validator(mode="after")
    def name_or_position(self):
        if (self.name is None) == (self.ra is None or self.dec is None) or (self.ra is None) != (self.dec is None):
            raise ValueError("Give either a name or both ra and dec")
        return self


class ObjectPosition(SkyCoord):
    """Adopted position of the object at ``epoch_mjd`` (ICRS degrees)."""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    epoch_mjd: FiniteFloat
    source: str = Field(description="e.g. 'Gaia DR3 propagated to the epoch' or 'query position (static)'")


class ObjectIdentity(_Model):
    """Who the object is, according to SIMBAD and Gaia DR3 (never according to SPHEREx)."""

    display_name: str | None = Field(default=None, description="SIMBAD main id without catalog prefix")
    main_id: str | None = Field(default=None, description="SIMBAD main identifier")
    object_type: str | None = Field(default=None, description="SIMBAD object type code, e.g. 'BY*'")
    object_type_label: str | None = Field(default=None, description="Readable label of a few SIMBAD types")
    spectral_type: str | None = Field(default=None, description="SIMBAD spectral type")
    resolver: str | None = Field(default=None, description="Service that gave the identity, e.g. SIMBAD via Sesame")
    gaia_source_id: str | None = Field(
        default=None, pattern=r"^\d+$", description="Gaia DR3 source_id as a STRING (64-bit; exceeds JS numbers)"
    )
    gaia_method: Literal["simbad_crossid", "nearest_after_propagation", "brightest_within_radius"] | None = None
    match: ObjectMatch
    identity_uncertain: bool = Field(
        default=False, description="True: identity-dependent values may belong to a neighbouring source"
    )
    separation_arcsec: FiniteFloat | None = Field(
        default=None, ge=0, description="Query position to the adopted Gaia DR3 source, both at the epoch"
    )
    n_gaia_within_radius: int | None = Field(default=None, ge=0)


class ObjectVariability(_Model):
    """Catalogued variability (AAVSO VSX). A missing entry does not prove the object is constant."""

    name: str
    var_type: str | None = None
    period_days: FiniteFloat | None = Field(default=None, gt=0)
    mag_max: FiniteFloat | None = None
    mag_min: FiniteFloat | None = Field(default=None, description="Faintest magnitude, or amplitude (see flag)")
    min_is_amplitude: bool = False
    passband: str | None = None
    separation_arcsec: FiniteFloat | None = Field(default=None, ge=0)
    url: str | None = None
    source: str


class ObjectPlanet(_Model):
    """One CONFIRMED planet of this object (NASA Exoplanet Archive pscomppars). Nothing hypothetical."""

    name: str
    hostname: str
    match: Literal["gaia_dr3_id", "hostname", "position"]
    period_days: FiniteFloat | None = None
    semi_major_axis_au: FiniteFloat | None = None
    radius_earth: FiniteFloat | None = None
    radius_calculated: bool = Field(default=False, description="True: estimated by the archive, not measured")
    mass_earth: FiniteFloat | None = None
    mass_kind: str | None = Field(default=None, description="e.g. 'Mass' or 'Msini' (minimum mass)")
    eccentricity: FiniteFloat | None = None
    inclination_deg: FiniteFloat | None = None
    discovery_year: int | None = None
    discovery_method: str | None = None
    discovery_facility: str | None = None
    reference: str | None = None
    controversial: bool = False
    source: str


class NearbyPlanetHost(_Model):
    """A confirmed planet host NEAR the object but not the object itself (e.g. eps Ind A next to eps Ind B)."""

    hostname: str
    separation_arcsec: FiniteFloat = Field(ge=0)
    planets: list[str] = Field(default_factory=list)


class ContextMagnitude(_Model):
    """Context photometry from OTHER missions (2MASS, AllWISE): never a SPHEREx measurement."""

    mission: Literal["2MASS", "WISE"]
    other_mission: Literal[True] = True
    catalog: str
    designation: str
    band: str
    wavelength_um: FiniteFloat = Field(gt=0, description="Nominal band centre")
    mag: FiniteFloat | None = None
    mag_err: FiniteFloat | None = Field(default=None, ge=0)
    system: str = "Vega"
    quality: str | None = None
    contamination: str | None = None
    upper_limit: bool = False
    epoch_mjd: FiniteFloat | None = None
    separation_arcsec: FiniteFloat | None = Field(default=None, ge=0)
    identity_uncertain: bool = False


class ContextService(_Model):
    """Provenance of one external call: which catalog, when, and whether it answered."""

    service: str
    catalog: str
    url: str | None = None
    status: ContextServiceStatus
    retrieved_utc: datetime | None = None
    cached: bool = False
    stale: bool = Field(default=False, description="An expired cache entry served because the service failed")
    note: str | None = None


class ObjectContextResponse(_Model):
    """GET /api/object: catalog context of a clicked position or a name (C05, WS3 object context).

    Every value comes from another catalog/mission and carries its source; ``Fact.value == 'unknown'`` means not
    measured or not found, and a service with ``status: 'error'`` is a gap, never a negative result.
    """

    schema_version: str = SCHEMA_VERSION
    query: ObjectQuery
    position: ObjectPosition | None = None
    identity: ObjectIdentity
    facts: list[Fact] = Field(default_factory=list, description="Physical parameters; 'unknown' when not measured")
    variability: ObjectVariability | None = None
    planets: list[ObjectPlanet] = Field(default_factory=list)
    nearby_planet_hosts: list[NearbyPlanetHost] = Field(default_factory=list)
    photometry: list[ContextMagnitude] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    provenance: list[ContextService] = Field(default_factory=list)
    partial: bool = Field(
        default=False, description="True when a service did not answer in time: its values are unknown, not negative"
    )
    built_at: datetime
    note: str = Field(description="Catalog context, not SPHEREx measurements")
    synthetic: Literal[False] = False


ALL_MODELS: dict[str, type[BaseModel]] = {
    "Manifest": Manifest,
    "Field": SkyField,
    "CandidateList": CandidateList,
    "KnownObjectList": KnownObjectList,
    "SearchResult": SearchResult,
    "SystemModel": SystemModel,
    "JobSubmitRequest": JobSubmitRequest,
    "JobStatusResponse": JobStatusResponse,
    "ResolvedRegion": ResolvedRegion,
    "SpectrumRequest": SpectrumRequest,
    "SpectrumResponse": SpectrumResponse,
    "ComparisonRequest": ComparisonRequest,
    "ComparisonResponse": ComparisonResponse,
    "ObjectContextResponse": ObjectContextResponse,
}
"""Top-level documents, one JSON Schema file each in shared/schema/."""
