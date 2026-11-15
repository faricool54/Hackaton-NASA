// Mirror of pipeline/errante/models.py (the source of truth) and shared/schema/*.json.
// Contract changes: see docs/WORKFLOW.md (PR "contract: ..." + make schema + update this file).
//
// Pixel convention for every x/y: PNG convention — origin at the TOP-LEFT pixel,
// 0-based, x → right, y → DOWN, on the field's common north-up grid (east left).

export const SCHEMA_VERSION = '0.6.0';

export type Release = 'dr1' | 'qr2' | 'qr3' | 'synthetic';
export type ObjectType =
  | 'asteroid'
  | 'comet'
  | 'tno'
  | 'dwarf_planet'
  | 'planet'
  | 'star'
  | 'brown_dwarf'
  | 'unknown';
export type CandidateKind = 'moving' | 'proper_motion' | 'variable';
/** unconfirmed = not matched to any catalog. It is NOT a discovery claim. */
export type CandidateStatus = 'unconfirmed' | 'known' | 'artifact' | 'injected';
export type MatchSource = 'jpl_sbident' | 'jpl_horizons' | 'skybot' | 'simbad' | 'synthetic';
/**
 * How a FALSE-COLOR composite maps SPHEREx infrared wavelengths to RGB (added in 0.3.1).
 * detectors = whole SPHEREx detectors over the full 0.75-5.0 um range;
 * jhk = 2MASS-like, exposures near J/H/Ks (~1.25/1.65/2.15 um). Blue = shortest, red = longest.
 */
export type CompositeMode = 'detectors' | 'jhk';
export type CompositeColor = 'red' | 'green' | 'blue';

export interface SkyCoord {
  ra: number; // deg ICRS
  dec: number; // deg ICRS
}

export interface Grid {
  center: SkyCoord;
  width_px: number;
  height_px: number;
  pixel_scale_arcsec: number;
  wcs: Record<string, number | string>;
}

export interface Stretch {
  vmin: number;
  vmax: number;
  unit: string;
  method: 'linear' | 'asinh' | 'log' | 'zscale';
}

export interface Frame {
  id: string;
  obs_id: string;
  detector: number; // 1-6
  mjd: number; // mid-exposure (header MJD-AVG), not the start (MJD-OBS)
  date_obs: string; // ISO 8601 UTC, same instant as mjd (DATE-AVG)
  wavelength_um: number | null;
  bandwidth_um: number | null;
  release: Release;
  image: string; // relative to the field dir
  source_uri: string | null;
  valid_fraction: number | null;
  stretch: Stretch | null;
}

export interface Detection {
  frame_id: string;
  mjd: number;
  position: SkyCoord;
  x: number;
  y: number;
  flux_mjy: number | null;
  flux_err_mjy: number | null;
  snr: number | null;
}

export interface Motion {
  rate_arcsec_per_hour: number;
  position_angle_deg: number;
  ra_cosdec_rate_arcsec_per_hour: number;
  dec_rate_arcsec_per_hour: number;
}

export interface DistanceEstimate {
  au_median: number;
  au_low: number | null;
  au_high: number | null;
  method: string;
}

export interface KnownMatch {
  designation: string;
  name: string | null;
  object_type: ObjectType;
  source: MatchSource;
  separation_arcsec: number;
  predicted_vmag: number | null;
}

export interface SpectrumPoint {
  frame_id: string;
  wavelength_um: number;
  bandwidth_um: number | null;
  flux_mjy: number;
  flux_err_mjy: number | null;
}

export interface Candidate {
  id: string;
  field_id: string;
  kind: CandidateKind;
  status: CandidateStatus;
  score: number; // 0..1
  detections: Detection[];
  motion: Motion | null;
  distance: DistanceEstimate | null;
  known_match: KnownMatch | null;
  spectrum: SpectrumPoint[];
  notes: string[];
}

export interface CandidateList {
  field_id: string;
  candidates: Candidate[];
}

export interface KnownObjectPosition {
  frame_id: string;
  mjd: number;
  position: SkyCoord;
  x: number;
  y: number;
  in_frame: boolean;
}

export interface KnownObject {
  designation: string;
  name: string | null;
  object_type: ObjectType;
  source: MatchSource;
  vmag: number | null;
  positions: KnownObjectPosition[];
}

export interface KnownObjectList {
  field_id: string;
  objects: KnownObject[];
}

export interface Provenance {
  pipeline_version: string;
  built_at: string;
  synthetic: boolean;
  data_releases: Release[];
  notes: string[];
}

/** One color channel of a FALSE-COLOR composite: which infrared exposures were mapped to it. */
export interface CompositeChannel {
  color: CompositeColor;
  detector: number | null; // 1-6; null = inputs from several detectors
  wavelength_um: number | null; // mean central wavelength of the inputs at the field centre
  wavelength_min_um: number | null; // shortest central wavelength among the inputs
  wavelength_max_um: number | null; // longest central wavelength among the inputs
  frame_ids: string[]; // Frame.id convention; may include exposures not in Field.frames
}

/**
 * FALSE-COLOR infrared composite of one observing season (added in 0.3.1).
 * SPHEREx sees 0.75-5.0 um, invisible to the eye: it is NOT a true-color image and the UI must say so.
 */
export interface Composite {
  id: string; // unique within the field, e.g. 'detectors_S0'
  mode: CompositeMode;
  season: number; // 0-based observing season (0 = earliest)
  mjd_min: number; // earliest mid-exposure MJD among the inputs
  mjd_max: number; // latest mid-exposure MJD among the inputs
  image: string; // RGB/RGBA PNG relative to the field dir, e.g. 'color/detectors_S0.png'
  channels: [CompositeChannel, CompositeChannel, CompositeChannel]; // red, green, blue (in this order)
  notes: string[];
}

export interface Field {
  id: string;
  name: string;
  description: string;
  tags: string[];
  center: SkyCoord;
  size_deg: number;
  grid: Grid;
  frames: Frame[];
  provenance: Provenance;
  composites?: Composite[]; // added in 0.3.1 (absent in older products: treat as [])
}

export interface FieldSummary {
  id: string;
  name: string;
  description: string;
  tags: string[];
  center: SkyCoord;
  size_deg: number;
  n_frames: number;
  n_candidates: number;
  mjd_range: [number, number] | null;
  thumbnail: string | null;
  synthetic: boolean;
}

// --- 3D systems (WS7). MODEL REPRESENTATIONS from catalog parameters, never images. ---

export type BodyKind =
  | 'star'
  | 'brown_dwarf'
  | 'planet'
  | 'dwarf_planet'
  | 'moon'
  | 'asteroid'
  | 'comet'
  | 'tno'
  | 'disk'
  | 'unknown';
export type AppearanceModel = 'star' | 'brown_dwarf' | 'rocky' | 'icy' | 'gas_giant' | 'disk' | 'mesh';
export type VariabilityKind = 'pulsation' | 'accretion' | 'eclipse' | 'rotation' | 'irregular';
/** fitted = published solution; assumed = NOT fitted; hypothetical = proposed object (e.g. Planet Nine). */
export type OrbitQuality = 'fitted' | 'assumed' | 'hypothetical';

export interface Fact {
  label: string;
  value: string;
  unit: string | null;
  source: string | null;
  /** True only if checked against `source`. The UI marks unverified values. */
  verified: boolean;
}

export interface Orbit {
  parent: string; // Body.id
  semi_major_axis_au: number;
  period_days: number;
  eccentricity: number;
  inclination_deg: number;
  ascending_node_deg: number;
  arg_periapsis_deg: number;
  mean_anomaly_deg: number; // at epoch_mjd
  epoch_mjd: number | null; // null = arbitrary phase
  quality?: OrbitQuality; // added in 0.2.1 (absent in older products: treat as 'fitted')
  note?: string | null; // added in 0.2.1
}

export interface Variability {
  kind: VariabilityKind;
  period_days: number | null;
  amplitude_mag: number | null;
  band: string | null;
}

export interface Appearance {
  model: AppearanceModel;
  color_hex: string | null;
  mesh_url: string | null;
  texture_url: string | null;
}

export interface Body {
  id: string;
  name: string;
  kind: BodyKind;
  description: string;
  radius_km: number | null;
  mass_kg: number | null;
  teff_k: number | null;
  spectral_type: string | null;
  rotation_period_hours: number | null;
  orbit: Orbit | null; // null = root body at the origin
  variability: Variability | null;
  appearance: Appearance;
  facts: Fact[];
  candidate_id: string | null;
}

export interface SpaceMotion {
  distance_pc: number | null;
  parallax_mas: number | null;
  pm_ra_cosdec_mas_yr: number | null;
  pm_dec_mas_yr: number | null;
  radial_velocity_km_s: number | null;
  epoch: string | null;
}

export interface SystemModel {
  id: string;
  name: string;
  description: string;
  tags: string[];
  center: SkyCoord;
  motion: SpaceMotion | null;
  field_id: string | null;
  bodies: Body[];
  representation_note: string;
  provenance: Provenance;
}

export interface SystemSummary {
  id: string;
  name: string;
  description: string;
  tags: string[];
  center: SkyCoord;
  n_bodies: number;
  kinds: BodyKind[];
  field_id: string | null;
  synthetic: boolean;
}

export interface Manifest {
  schema_version: string;
  generated_at: string;
  synthetic: boolean;
  fields: FieldSummary[];
  systems: SystemSummary[]; // added in 0.2.0 (may be absent in older products: treat as [])
}

export interface FrameRef {
  obs_id: string;
  detector: number;
  mjd: number;
  release: Release;
  irsa_uri: string | null;
  s3_key: string | null;
  wavelength_um: number | null;
}

export interface SearchResult {
  center: SkyCoord;
  radius_deg: number;
  frames: FrameRef[];
}

/** Shared contract 0.3.0. Empty detectors means all six; coordinates are ICRS degrees. */
export interface JobSubmitRequest {
  ra: number;
  dec: number;
  size_deg?: number;
  detectors?: number[];
  mjd_min?: number | null;
  mjd_max?: number | null;
  max_frames?: number;
}

export type PublicJobStatus = 'queued' | 'running' | 'ready' | 'failed' | 'no_coverage' | 'pipeline_not_ready';

export interface JobStatusResponse {
  id: string;
  status: PublicJobStatus;
  stage: string;
  created_at: string;
  updated_at: string;
  result_field_id: string | null;
  error_detail: string | null;
}

export interface ResolvedRegion extends SkyCoord {
  object_type: ObjectType;
  resolved_name: string;
  source: string;
}


export interface SpectrumRequest extends SkyCoord {
  source?: 'dr1_cube' | 'l2_exposures';
  field_id?: string | null;
  detectors?: number[];
  mjd_min?: number | null;
  mjd_max?: number | null;
  aperture_px?: number;
  max_frames?: number;
}
export interface MeasurementFailure {
  frame_id: string | null;
  reason: 'download_failed' | 'measurement_failed' | 'no_overlap' | 'invalid_pixels';
}
export interface SpectralMeasurement {
  id: string; detector: number; wavelength_um: number | null; bandwidth_um: number | null;
  flux: number | null; flux_err: number | null; usable: boolean; flags: string[];
  frame_id: string | null; mjd: number | null; release: Release; source_uri: string | null;
  nhits: number | null; n_used: number | null; aperture_correction: number | null;
}
export interface SpectrumResponse {
  schema_version: string; center: SkyCoord; source: 'dr1_cube' | 'l2_exposures'; unit: 'MJy/sr' | 'mJy';
  static_coadd: boolean; points: SpectralMeasurement[]; built_at: string; field_id: string | null;
  mjd_range: [number | null, number | null]; pixel_scale_arcsec: number | null; aperture_px: number;
  background_subtracted: boolean; synthetic: boolean; truncated: boolean; stale: boolean;
  notes: string[]; failures: MeasurementFailure[];
}
export interface ComparisonRequest { detectors?: number[]; frame_ids?: string[] | null; }
export interface ComparisonImage {
  id: string; kind: 'weighted_mean' | 'scaled_difference'; detector: number; image: string;
  frame_ids: string[]; mjd_min: number; mjd_max: number; wavelength_range_um: [number, number] | null;
  season: number | null; earlier: string | null; later: string | null; valid_fraction: number | null;
  flux_scale: number | null; flux_scale_fitted: boolean | null; flux_scale_stars: number | null;
  noise_mjy_sr: number | null; display_limit_mjy_sr: number | null; target_exclude_px: number | null;
  weights: number[] | null; notes: string[];
}
export interface ComparisonResponse {
  schema_version: string; id: string; field_id: string; field_built_at: string; built_at: string;
  unit: 'MJy/sr'; method: string; input_frames: Frame[]; images: ComparisonImage[];
  failures: MeasurementFailure[]; notes: string[]; synthetic: boolean;
}

/** Contract 0.5.0 (C05): GET /api/object, catalog context of a position or a name. Never SPHEREx measurements. */
export type ObjectMatch = 'name' | 'matched' | 'ambiguous' | 'loose' | 'none' | 'unavailable';
export type ContextServiceStatus = 'ok' | 'no_match' | 'error' | 'skipped';
/** Exactly one of `name` or `ra` + `dec`. */
export interface ObjectQuery {
  ra: number | null; dec: number | null; name: string | null; epoch_mjd: number; radius_arcsec: number;
}
export interface ObjectPosition extends SkyCoord { epoch_mjd: number; source: string; }
export interface ObjectIdentity {
  display_name: string | null; main_id: string | null; object_type: string | null;
  object_type_label: string | null; spectral_type: string | null; resolver: string | null;
  /** 64-bit Gaia DR3 source_id as a string (exceeds Number.MAX_SAFE_INTEGER). */
  gaia_source_id: string | null;
  gaia_method: 'simbad_crossid' | 'nearest_after_propagation' | 'brightest_within_radius' | null;
  match: ObjectMatch; identity_uncertain: boolean; separation_arcsec: number | null;
  n_gaia_within_radius: number | null;
}
export interface ObjectVariability {
  name: string; var_type: string | null; period_days: number | null; mag_max: number | null;
  mag_min: number | null; min_is_amplitude: boolean; passband: string | null;
  separation_arcsec: number | null; url: string | null; source: string;
}
export interface ObjectPlanet {
  name: string; hostname: string; match: 'gaia_dr3_id' | 'hostname' | 'position';
  period_days: number | null; semi_major_axis_au: number | null; radius_earth: number | null;
  radius_calculated: boolean; mass_earth: number | null; mass_kind: string | null;
  eccentricity: number | null; inclination_deg: number | null; discovery_year: number | null;
  discovery_method: string | null; discovery_facility: string | null; reference: string | null;
  controversial: boolean; source: string;
}
export interface NearbyPlanetHost { hostname: string; separation_arcsec: number; planets: string[]; }
/** Context photometry of OTHER missions (2MASS, AllWISE): never SPHEREx. */
export interface ContextMagnitude {
  mission: '2MASS' | 'WISE'; other_mission: true; catalog: string; designation: string; band: string;
  wavelength_um: number; mag: number | null; mag_err: number | null; system: string;
  quality: string | null; contamination: string | null; upper_limit: boolean;
  epoch_mjd: number | null; separation_arcsec: number | null; identity_uncertain: boolean;
}
export interface ContextService {
  service: string; catalog: string; url: string | null; status: ContextServiceStatus;
  retrieved_utc: string | null; cached: boolean; stale: boolean; note: string | null;
}
export interface ObjectContextResponse {
  schema_version: string; query: ObjectQuery; position: ObjectPosition | null; identity: ObjectIdentity;
  /** Physical parameters; value 'unknown' = not measured or not found. */
  facts: Fact[]; variability: ObjectVariability | null; planets: ObjectPlanet[];
  nearby_planet_hosts: NearbyPlanetHost[]; photometry: ContextMagnitude[]; warnings: string[];
  provenance: ContextService[];
  /** A service did not answer in time: its values are unknown, not negative. */
  partial: boolean; built_at: string; note: string; synthetic: false;
}
export type LightCurveExclusion = 'no_flags' | 'saturated' | 'edge' | 'bad_pixels' | 'no_sky' | 'no_variance' | 'no_wavelength' | 'non_positive' | 'lone_bin' | 'short_bin';
export interface LightCurveParameters extends SkyCoord {
  method?: 'aperture' | 'wing'; detectors?: number[]; collections?: string[]; max_frames?: number;
  mjd_min?: number | null; mjd_max?: number | null; lambda_bin_frac?: number; min_bin_span_days?: number;
  n_comparison?: number; period?: boolean; period_range_days?: [number, number]; n_bootstrap?: number; n_permutations?: number;
}
export interface LightCurvePoint {
  frame_id: string; obs_id: string; detector: number; release: Release; mjd: number; date: string; season: number;
  wavelength_um: number | null; bandwidth_um: number | null; flux: number | null; flux_err: number | null;
  bin: number | null; rel_mag: number | null; rel_mag_err: number | null; zero_point_mag: number | null;
  flags: string[]; excluded: LightCurveExclusion | null;
}
export interface LightCurveBin {
  index: number; detector: number; lambda_min_um: number; lambda_max_um: number; n_points: number;
  mjd_min: number; mjd_max: number; mean_mag: number;
}
export interface LightCurveComparison {
  id: string; ra: number; dec: number; found_in: number; frame_ids: string[]; detectors: number[];
  wavelength_um: (number | null)[]; flux_mjy: (number | null)[]; flux_err_mjy: (number | null)[];
  rel_mag: (number | null)[]; excluded: (LightCurveExclusion | null)[];
}
export interface LightCurveStatistics {
  n: number; median_mag: number | null; robust_sigma_mag: number | null; p95_abs_mag: number | null;
  max_abs_mag: number | null; p5_to_p95_mag: number | null; n_stars: number | null;
  n_exposures: number | null; n_bins: number | null; excluded: Partial<Record<LightCurveExclusion, number>>;
  scatter_over_control: number | null;
}
export interface LightCurvePeriod {
  period_days: number; delta_chi2: number; period_err_formal_days: number | null; bootstrap_95_days: [number, number] | null;
  peaks: [number, number][]; amplitude_mag: Record<string, number>; floor_mag: Record<string, number>;
  n_points: number; baseline_days: number; period_range_days: [number, number]; false_alarm: number | null;
  n_permutations: number; significant: boolean | null; caveat: string;
}
export interface LightCurvePair {
  detector: number; frame_a: string; frame_b: string; mjd_a: number; mjd_b: number; date_a: string; date_b: string;
  season_a: number; season_b: number; wavelength_a_um: number; wavelength_b_um: number; delta_mag: number;
  delta_mag_err: number | null; ensemble_mag: number | null; n_ensemble: number; delta_mag_corrected: number | null;
}
export interface LightCurveData extends SkyCoord {
  method: 'aperture' | 'wing'; unit: 'mJy' | 'MJy/sr'; relative_only: boolean; lambda_bin_frac: number;
  min_bin_span_days: number; points: LightCurvePoint[]; bins: LightCurveBin[]; comparisons: LightCurveComparison[];
  control: Record<string, LightCurveStatistics>; summary: Record<string, LightCurveStatistics>;
  excluded: Partial<Record<LightCurveExclusion, number>>; period: LightCurvePeriod | null;
  notes: string[]; failures: MeasurementFailure[]; matched_pairs: LightCurvePair[];
}
export interface LightCurveProvenance {
  pipeline_version: string; processing_fingerprint: string; collections: string[];
  sources: { frame_id: string; source_uri: string }[]; n_found: number | null; n_selected: number;
  stale_search: boolean; truncated_search: boolean; partial: boolean; notes: string[];
}
export interface LightCurveProduct {
  schema_version: string; id: string; target_id: string; target_name: string; built_at: string;
  status: 'ready' | 'no_usable_points'; parameters: Required<LightCurveParameters>;
  curve: LightCurveData; provenance: LightCurveProvenance; synthetic: false;
}
export interface LightCurveSummary {
  target_id: string; target_name: string; id: string; built_at: string; method: 'aperture' | 'wing';
  status: 'ready' | 'no_usable_points'; n_points: number; n_used: number; partial: boolean; synthetic: false;
}
export interface LightCurveIndex { schema_version: string; products: LightCurveSummary[] }
