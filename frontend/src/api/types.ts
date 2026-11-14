// Mirror of pipeline/errante/models.py (the source of truth) and shared/schema/*.json.
// Contract changes: see docs/WORKFLOW.md (PR "contract: ..." + make schema + update this file).
//
// Pixel convention for every x/y: PNG convention — origin at the TOP-LEFT pixel,
// 0-based, x → right, y → DOWN, on the field's common north-up grid (east left).

export const SCHEMA_VERSION = '0.3.0';

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
 * How a FALSE-COLOR composite maps SPHEREx infrared wavelengths to RGB (added in 0.3.0).
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
 * FALSE-COLOR infrared composite of one observing season (added in 0.3.0).
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
  composites?: Composite[]; // added in 0.3.0 (absent in older products: treat as [])
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
