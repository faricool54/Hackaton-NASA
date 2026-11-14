// Mirror of pipeline/errante/models.py (the source of truth) and shared/schema/*.json.
// Contract changes: see docs/WORKFLOW.md (PR "contract: ..." + make schema + update this file).
//
// Pixel convention for every x/y: PNG convention — origin at the TOP-LEFT pixel,
// 0-based, x → right, y → DOWN, on the field's common north-up grid (east left).

export const SCHEMA_VERSION = '0.1.0';

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
  mjd: number;
  date_obs: string; // ISO 8601
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

export interface Manifest {
  schema_version: string;
  generated_at: string;
  synthetic: boolean;
  fields: FieldSummary[];
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
