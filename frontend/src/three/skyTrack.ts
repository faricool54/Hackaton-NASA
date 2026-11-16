// "Where SPHEREx should see it" (work package S4): the predicted sky track of a system over the
// SPHEREx dataset window, from its catalog astrometry. Pure math + data, no React and no three.js,
// so everything here is unit-tested (skyTrack.test.ts).
//
// Model (all of it is a PREDICTION from catalog values, never a measurement):
// - Linear space motion from the catalog epoch, radial velocity included when it is known: the
//   star moves on a straight line at constant velocity in the barycentric frame (Butkevich &
//   Lindegren 2014, A&A 570, A62). Position, proper motion and parallax give the position and the
//   transverse velocity (mu / parallax, in AU per year), the radial velocity the line-of-sight one.
//   Light-time effects of the radial motion cancel to first order in the observed proper motion
//   (as in ERFA starpm/pmsafe), so they are not modelled.
// - Annual parallax: the place is seen from the Earth. The Earth's position is the negative of the
//   Sun's geocentric position from the Astronomical Almanac low-precision solar coordinates
//   (Section C; Meeus 1998, Astronomical Algorithms, 2nd ed., ch. 25), precision about 0.01 deg in
//   longitude for 1950-2050. The longitude is made geometric (+0.00569 deg of annual aberration)
//   and referred to the equinox J2000 (-0.01397 deg per year since 2000, Meeus ch. 25), then
//   rotated to the equator with the J2000 obliquity. It is heliocentric, not barycentric: the Sun
//   is up to 0.0074 AU from the solar-system barycentre in 2025-2026 (checked against ERFA epv00 in
//   the tests), i.e. at most 0.75 % of the parallax (4 mas for Barnard's Star). SPHEREx's low Earth
//   orbit (~7000 km = 5e-5 AU from the geocentre) is far smaller and ignored.
// - Output: the geocentric ICRS astrometric place (no aberration, no light deflection), the place
//   used to match catalogs and to centre cut-outs. Offsets are gnomonic (tangent-plane) arcsec,
//   east and north of a reference place, drawn north up and east left.
// Validation: docs/RECON_SPHEREX.md 4.1 propagated the same catalog values with astropy
// (SkyCoord.apply_space_motion plus the Earth's position); the tests reproduce its vectors.
import type { SystemModel } from '../api/types';
import type { Tier } from './astro';
import { SPHEREX_PIXEL_ARCSEC } from './spherexBands';
import {
  datasetWindow,
  DATASET_TODAY_MJD,
  DR1_START_MJD,
  mjdToIsoDate,
  SPHEREX_COVERAGE_SOURCE,
  type DatasetWindow,
} from './spherexCoverage';

export { SPHEREX_PIXEL_ARCSEC };

// --- constants -------------------------------------------------------------------------------

/** MJD of J2000.0 (JD 2451545.0). */
export const MJD_J2000 = 51544.5;
export const JULIAN_YEAR_DAYS = 365.25;
const DEG = Math.PI / 180;
export const ARCSEC_PER_RAD = 648000 / Math.PI;
export const MAS_PER_RAD = ARCSEC_PER_RAD * 1000;
/** Astronomical unit (km), IAU 2012 Resolution B2. */
export const AU_KM = 149597870.7;
/** 1 km/s in AU per Julian year. */
const KM_S_TO_AU_PER_YR = (JULIAN_YEAR_DAYS * 86400) / AU_KM;
/** Mean obliquity of the ecliptic at J2000.0, 84381.448 arcsec (IAU 1976). */
export const OBLIQUITY_J2000_DEG = 84381.448 / 3600;
/** Annual aberration in solar longitude (Meeus 1998, ch. 25): the AA longitude is apparent. */
const SOLAR_ABERRATION_DEG = 0.00569;
/** Precession of the solar longitude to the equinox J2000 (Meeus 1998, ch. 25), deg per year. */
const LONGITUDE_PRECESSION_DEG_PER_YR = 0.01397;
/** Largest Sun - barycentre distance over the dataset (AU): the error of a heliocentric Earth. */
export const SUN_BARYCENTRE_MAX_AU = 0.0074;

export const SKY_TRACK_TITLE = 'Where SPHEREx should see it';
/** Caption the panel must carry (S4 acceptance). */
export const SKY_TRACK_CAPTION = 'Predicted position from catalog astrometry - not a measurement';
export const SKY_TRACK_BADGE = 'PREDICTION · NOT A MEASUREMENT';
export const EARTH_EPHEMERIS_CITATION =
  'Astronomical Almanac, Section C, low-precision formulas for the Sun; Meeus 1998, Astronomical Algorithms, 2nd ed., ch. 25';
export const SPACE_MOTION_CITATION = 'Butkevich & Lindegren 2014, A&A 570, A62';
export const RECON_VALIDATION =
  'docs/RECON_SPHEREX.md 4.1 (astropy SkyCoord.apply_space_motion plus the Earth position)';

// --- vectors and angles ----------------------------------------------------------------------

export type Vec3 = readonly [number, number, number];

export interface RaDec {
  raDeg: number;
  decDeg: number;
}

/** Tangent-plane offset (arcsec): east = +RA direction, north = +Dec. */
export interface Offset {
  east: number;
  north: number;
}

function unitVector(p: RaDec): Vec3 {
  const a = p.raDeg * DEG;
  const d = p.decDeg * DEG;
  return [Math.cos(d) * Math.cos(a), Math.cos(d) * Math.sin(a), Math.sin(d)];
}

function toRaDec(v: Vec3): RaDec {
  const ra = Math.atan2(v[1], v[0]) / DEG;
  return { raDeg: ra < 0 ? ra + 360 : ra, decDeg: Math.atan2(v[2], Math.hypot(v[0], v[1])) / DEG };
}

const dot = (a: Vec3, b: Vec3) => a[0] * b[0] + a[1] * b[1] + a[2] * b[2];

/** Angular separation (arcsec), atan2 form: accurate at milliarcsecond separations. */
export function separationArcsec(a: RaDec, b: RaDec): number {
  const u = unitVector(a);
  const v = unitVector(b);
  const cx = u[1] * v[2] - u[2] * v[1];
  const cy = u[2] * v[0] - u[0] * v[2];
  const cz = u[0] * v[1] - u[1] * v[0];
  return Math.atan2(Math.hypot(cx, cy, cz), dot(u, v)) * ARCSEC_PER_RAD;
}

/** Gnomonic offset of `p` from `ref` (arcsec, east and north). */
export function tangentOffsetArcsec(ref: RaDec, p: RaDec): Offset {
  const a = ref.raDeg * DEG;
  const d = ref.decDeg * DEG;
  const u0 = unitVector(ref);
  const east: Vec3 = [-Math.sin(a), Math.cos(a), 0];
  const north: Vec3 = [-Math.sin(d) * Math.cos(a), -Math.sin(d) * Math.sin(a), Math.cos(d)];
  const v = unitVector(p);
  const w = dot(v, u0);
  return { east: (dot(v, east) / w) * ARCSEC_PER_RAD, north: (dot(v, north) / w) * ARCSEC_PER_RAD };
}

/** Position angle of an offset (deg, north through east, 0-360). */
export function positionAngleDeg(o: Offset): number {
  const pa = Math.atan2(o.east, o.north) / DEG;
  return pa < 0 ? pa + 360 : pa;
}

/** Ecliptic latitude (deg, ecliptic and equinox J2000). */
export function eclipticLatitudeDeg(p: RaDec): number {
  const [, y, z] = unitVector(p);
  const e = OBLIQUITY_J2000_DEG * DEG;
  return Math.asin(Math.max(-1, Math.min(1, -Math.sin(e) * y + Math.cos(e) * z))) / DEG;
}

// --- epochs ----------------------------------------------------------------------------------

export function julianEpochToMjd(year: number): number {
  return MJD_J2000 + (year - 2000) * JULIAN_YEAR_DAYS;
}

/** MJD of a Julian epoch label such as "J2016.0" (SpaceMotion.epoch); null when unreadable. */
export function parseEpoch(label: string | null | undefined): number | null {
  const m = /^\s*J\s*(\d{4}(?:\.\d+)?)\s*$/i.exec(label ?? '');
  return m ? julianEpochToMjd(Number(m[1])) : null;
}

// --- the Earth ------------------------------------------------------------------------------

/**
 * Position of the Earth (AU, ICRS axes, origin at the Sun), from the Astronomical Almanac
 * low-precision Sun: 0.01 deg in longitude for 1950-2050. TT vs UTC (~69 s) is irrelevant here.
 */
export function earthPositionAu(mjd: number): Vec3 {
  const n = mjd - MJD_J2000; // days from J2000.0
  const meanLongitude = 280.46 + 0.9856474 * n; // includes aberration
  const g = (357.528 + 0.9856003 * n) * DEG; // mean anomaly
  const apparent = meanLongitude + 1.915 * Math.sin(g) + 0.02 * Math.sin(2 * g);
  const r = 1.00014 - 0.01671 * Math.cos(g) - 0.00014 * Math.cos(2 * g);
  const lambda = (apparent + SOLAR_ABERRATION_DEG - LONGITUDE_PRECESSION_DEG_PER_YR * (n / JULIAN_YEAR_DAYS)) * DEG;
  const e = OBLIQUITY_J2000_DEG * DEG;
  const x = r * Math.cos(lambda);
  const y = r * Math.sin(lambda);
  // The Earth is opposite the Sun as seen from the Earth.
  return [-x, -y * Math.cos(e), -y * Math.sin(e)];
}

// --- the star ------------------------------------------------------------------------------

/** Five- or six-parameter astrometric solution at one epoch (barycentric ICRS). */
export interface AstrometricSolution {
  raDeg: number;
  decDeg: number;
  epochMjd: number;
  pmRaCosDecMasYr: number;
  pmDecMasYr: number;
  parallaxMas: number;
  /** null = not measured: the radial motion (perspective acceleration) is left out. */
  radialVelocityKmS: number | null;
}

export interface PlaceOptions {
  /** 'geocentric' (default) adds the annual parallax; 'barycentric' is the catalog-style place. */
  observer?: 'geocentric' | 'barycentric';
  /** Include the radial velocity when known (default true). */
  radialVelocity?: boolean;
}

/** Barycentric position (AU) of the star at `mjd`, moving on a straight line. */
export function starPositionAu(s: AstrometricSolution, mjd: number, includeRadialVelocity = true): Vec3 {
  if (!(s.parallaxMas > 0)) throw new RangeError(`parallax must be > 0 mas (got ${s.parallaxMas})`);
  const a = s.raDeg * DEG;
  const d = s.decDeg * DEG;
  const ca = Math.cos(a);
  const sa = Math.sin(a);
  const cd = Math.cos(d);
  const sd = Math.sin(d);
  const dist = MAS_PER_RAD / s.parallaxMas; // AU
  const t = (mjd - s.epochMjd) / JULIAN_YEAR_DAYS;
  const vEast = s.pmRaCosDecMasYr / s.parallaxMas; // AU/yr: (mas/yr) / mas x 1 AU
  const vNorth = s.pmDecMasYr / s.parallaxMas;
  const vRad = includeRadialVelocity && s.radialVelocityKmS != null ? s.radialVelocityKmS * KM_S_TO_AU_PER_YR : 0;
  // Unit vectors: towards the star (u), east (e) and north (n) at the catalog position.
  const ux = cd * ca;
  const uy = cd * sa;
  const uz = sd;
  const ex = -sa;
  const ey = ca;
  const nx = -sd * ca;
  const ny = -sd * sa;
  const nz = cd;
  return [
    dist * ux + t * (vEast * ex + vNorth * nx + vRad * ux),
    dist * uy + t * (vEast * ey + vNorth * ny + vRad * uy),
    dist * uz + t * (vNorth * nz + vRad * uz),
  ];
}

/** ICRS astrometric place (deg) of the star at `mjd`: geocentric by default. */
export function astrometricPlace(s: AstrometricSolution, mjd: number, opts: PlaceOptions = {}): RaDec {
  const r = starPositionAu(s, mjd, opts.radialVelocity ?? true);
  if ((opts.observer ?? 'geocentric') === 'barycentric') return toRaDec(r);
  const earth = earthPositionAu(mjd);
  return toRaDec([r[0] - earth[0], r[1] - earth[1], r[2] - earth[2]]);
}

/** Barycentric direction of a geocentric place at `mjd` (inverse of the parallax step). */
export function barycentricFromGeocentric(geo: RaDec, parallaxMas: number, mjd: number): RaDec {
  const dist = MAS_PER_RAD / parallaxMas;
  const u = unitVector(geo);
  const earth = earthPositionAu(mjd);
  return toRaDec([dist * u[0] + earth[0], dist * u[1] + earth[1], dist * u[2] + earth[2]]);
}

// --- which astrometry each system uses --------------------------------------------------------

/** A static source near the track (e.g. a field star that blends with the target). */
export interface StaticSource {
  name: string;
  raDeg: number;
  decDeg: number;
  note: string;
  source: string;
}

export interface TrackSourceEntry {
  /** What the track follows. */
  target: string;
  /** Where the astrometry comes from. */
  source: string;
  /** Exact epoch (MJD) when SpaceMotion.epoch is a rounded label (e.g. "J2016.67"). */
  epochMjd?: number;
  /** WS7 constant solution, used when the tracked body is not SystemModel.center. */
  solution?: AstrometricSolution & { epochLabel: string };
  notes: readonly string[];
  staticSources?: readonly StaticSource[];
}

const RECON_41 = 'docs/RECON_SPHEREX.md 4.1';
const RECON_43 = 'docs/RECON_SPHEREX.md 4.3';

/**
 * Sources of the astrometry per demo system id. Values come from SystemModel.motion and .center
 * (catalog.py), except Epsilon Indi: its centre is A, while the SPHEREx field and coverage are of
 * the brown-dwarf pair B, so the track uses B's own Gaia DR3 solution as listed in RECON 4.1.
 */
export const TRACK_SOURCES: Readonly<Record<string, TrackSourceEntry>> = {
  'barnards-star': {
    target: "Barnard's Star",
    source: 'Gaia DR3 4472832130942575872: position, proper motion, parallax and radial velocity at J2016.0',
    notes: [
      'Saturated (OVERFLOW) in 357 of 358 exposures, in all six detectors; the core is NaN in 240 of them, almost all in D1–D4 (offline FITS analysis, docs/validation/barnards-star.md).',
    ],
  },
  'epsilon-indi': {
    target: 'Epsilon Indi B (Ba+Bb, unresolved)',
    source: `Gaia DR3 6412596012146801152 (Ba+Bb photocentre, RUWE 4.3) at J2016.0, values from ${RECON_41}`,
    solution: {
      raDeg: 331.0764526,
      decDeg: -56.7938121,
      epochMjd: julianEpochToMjd(2016.0),
      epochLabel: 'J2016.0',
      pmRaCosDecMasYr: 3981.98,
      pmDecMasYr: -2466.83,
      parallaxMas: 270.66,
      radialVelocityKmS: null,
    },
    notes: [
      "The system's centre is Epsilon Indi A, but the SPHEREx field and coverage are of B: this track uses B's own Gaia DR3 solution (a WS7 constant).",
      `No radial velocity of B is used (${RECON_41} lists none); A's −40.43 km/s would move the predicted places by less than 0.01″.`,
      'The Ba–Bb orbit (11.02 yr, separation up to a(1+e) = 1.02″; Chen et al. 2022, AJ 163, 288) also moves the unresolved photocentre: not modelled, below 1.02″ (0.17 px).',
      `Epsilon Indi A, saturated, lies 402.6″ (65.5 px) to the west and is not tracked here (${RECON_43}).`,
    ],
  },
  'wise-0855': {
    target: 'WISE 0855−0714',
    source: 'Kirkpatrick et al. 2021, ApJS 253, 7: position at the astrometric epoch MJD 57633.39, proper motion and parallax (not in Gaia)',
    epochMjd: 57633.39,
    notes: [
      'No radial velocity is measured: the radial motion (perspective acceleration) is not included.',
      "Adopted solution: Kirkpatrick et al. 2021, also used by fields.toml and docs/validation/wise-0855.md. Cross-check: the team's own unpublished WISE + NEOWISE fit (docs/RECON_SPHEREX.md 4.1, μ ≈ −8095, +696 mas/yr) is 0.31″ (0.05 px) away on 2026-11-14.",
      'Seen only in D5/D6 (3.8–5.0 µm), brightest at 4.25–4.70 µm: median S/N 3.4–3.8 per exposure (5 or more in 22 of 93) and 21–25 per detector with all exposures combined (offline FITS analysis, docs/validation/wise-0855.md).',
    ],
    staticSources: [
      {
        name: 'Gaia DR3 5756956644387831296',
        raDeg: 133.7581825,
        decDeg: -7.2411559,
        note: 'static field star (CatWISE J085501.95−071428.2, G 16.31): in D1–D4 the blob near the target position is this star (docs/validation/wise-0855.md)',
        source: RECON_43,
      },
    ],
  },
  'r-draconis': {
    target: 'R Draconis',
    source: 'Gaia DR3 1648328016354496384 (flagged VARIABLE) at J2016.0; radial velocity −132.8 km/s from SIMBAD (Wilson 1953)',
    notes: ['Saturated (OVERFLOW) in all 2,488 exposures with the star on the detector; the flagged core pixels are finite, not NaN (offline FITS analysis, docs/validation/r-draconis.md).'],
  },
  'rw-aurigae': {
    target: 'RW Aurigae A+B',
    source:
      'Position of A, Gaia DR3 156430817820015232; parallax and proper motion of B, Gaia DR3 156430822114424576, as adopted by Kurtovic et al. 2024 (A’s solution has RUWE 16); radial velocity 15 km/s from SIMBAD (Nguyen et al. 2012)',
    notes: [
      'The track is A’s: its Gaia DR3 position, propagated with B’s parallax and proper motion. B is 1.5″ (0.24 px) WSW and unresolved: SPHEREx sees the A+B blend as one point source.',
    ],
  },
};

export interface TrackAstrometry extends AstrometricSolution {
  epochLabel: string;
  target: string;
  source: string;
  /** 'system' = SystemModel.center + motion; 'ws7-constant' = TRACK_SOURCES solution. */
  origin: 'system' | 'ws7-constant';
  notes: readonly string[];
  staticSources: readonly StaticSource[];
}

export type SkyTrackSystem = Pick<SystemModel, 'id' | 'name' | 'center' | 'motion'> &
  Partial<Pick<SystemModel, 'field_id' | 'provenance'>>;

function sourceEntry(id: string): TrackSourceEntry | null {
  return Object.prototype.hasOwnProperty.call(TRACK_SOURCES, id) ? TRACK_SOURCES[id] : null;
}

/** The astrometry the track uses, or null when the catalog motion cannot be propagated. */
export function trackAstrometry(system: SkyTrackSystem): TrackAstrometry | null {
  const entry = sourceEntry(system.id);
  if (entry?.solution) {
    return {
      ...entry.solution,
      target: entry.target,
      source: entry.source,
      origin: 'ws7-constant',
      notes: entry.notes,
      staticSources: entry.staticSources ?? [],
    };
  }
  const m = system.motion;
  if (!m || m.parallax_mas == null || !(m.parallax_mas > 0)) return null;
  if (m.pm_ra_cosdec_mas_yr == null || m.pm_dec_mas_yr == null) return null;
  if (![system.center.ra, system.center.dec, m.pm_ra_cosdec_mas_yr, m.pm_dec_mas_yr].every(Number.isFinite)) return null;
  const epochMjd = entry?.epochMjd ?? parseEpoch(m.epoch);
  if (epochMjd === null) return null;
  return {
    raDeg: system.center.ra,
    decDeg: system.center.dec,
    epochMjd,
    epochLabel: m.epoch ?? `MJD ${epochMjd}`,
    pmRaCosDecMasYr: m.pm_ra_cosdec_mas_yr,
    pmDecMasYr: m.pm_dec_mas_yr,
    parallaxMas: m.parallax_mas,
    radialVelocityKmS: m.radial_velocity_km_s != null && Number.isFinite(m.radial_velocity_km_s) ? m.radial_velocity_km_s : null,
    target: entry?.target ?? system.name,
    source: entry?.source ?? 'catalog SpaceMotion of this system (no source listed in the WS7 table)',
    origin: 'system',
    notes: entry?.notes ?? [],
    staticSources: entry?.staticSources ?? [],
  };
}

// --- the track over the dataset ---------------------------------------------------------------

export interface TrackPoint extends RaDec, Offset {
  mjd: number;
}

/** One dot on the track: a SPHEREx pass, or one visit of a pass that the 10-day gap splits. */
export interface TrackMark {
  passIndex: number;
  /** "1", "2"... or "2a", "2b" for the separate visits of one pass. */
  label: string;
  startMjd: number;
  endMjd: number;
  /** Mid-date of the window: where the dot is. */
  mjd: number;
  dates: [string, string];
  datesApprox: boolean;
  nImages: number;
  position: TrackPoint;
  /** The track over the window, about one point per day. */
  segment: TrackPoint[];
  /** How far the target moves between the first and the last day of the window (arcsec). */
  driftArcsec: number;
  /** From the previous dot (arcsec); null for the first. */
  shiftFromPreviousArcsec: number | null;
  /** From the first dot (arcsec). */
  shiftFromFirstArcsec: number;
}

export interface TierLine {
  tier: Tier;
  label: string;
  text: string;
}

export interface SkyTrack {
  systemId: string;
  astrometry: TrackAstrometry;
  /** The offsets are from this geocentric place. */
  reference: TrackPoint & { label: string };
  startMjd: number;
  endMjd: number;
  samples: TrackPoint[];
  marks: TrackMark[];
  /** Start of the track (DR1 start) and the "today" end of the dataset. */
  start: TrackPoint;
  end: TrackPoint;
  staticSources: (StaticSource & Offset & { closest: { mjd: number; separationArcsec: number } })[];
  pmArcsecPerYr: number;
  pmPxPerYr: number;
  pmPositionAngleDeg: number;
  /** Semi-major axis of the parallax ellipse (= the parallax), arcsec. */
  parallaxArcsec: number;
  /** Semi-minor axis, parallax x |sin(ecliptic latitude)|, arcsec. */
  parallaxMinorArcsec: number;
  eclipticLatitudeDeg: number;
  /** Largest geocentric - barycentric difference along the track (arcsec). */
  parallaxMaxArcsec: number;
  /** How far the radial velocity moves the place at the end of the track (arcsec); null if unknown. */
  radialVelocityEffectArcsec: number | null;
  /** First dot to last dot (arcsec). */
  totalShiftArcsec: number;
  /** Largest distance between two points of the track (arcsec). */
  spanArcsec: number;
  /** The track never leaves a tenth of a pixel. */
  staticAtPixelScale: boolean;
  /** Where the dataset window and its passes come from (null without coverage). */
  coverageSource: string | null;
  coverageTarget: string | null;
  tiers: TierLine[];
}

/** Below this span (px) the target does not move measurably at SPHEREx resolution. */
export const STATIC_SPAN_PX = 0.1;

export interface SkyTrackOptions {
  /** Sampling step of the drawn track (days). */
  stepDays?: number;
  /** A dataset window computed elsewhere (e.g. with built frames); default datasetWindow(system). */
  window?: DatasetWindow | null;
}

function sampleTimes(start: number, end: number, step: number): number[] {
  const n = Math.max(1, Math.ceil((end - start) / step));
  return Array.from({ length: n + 1 }, (_, i) => start + ((end - start) * i) / n);
}

/**
 * The predicted track of a system over its SPHEREx dataset window (DR1 start to the "today" date of
 * this dataset), with one mark per pass. Null when the system has no usable astrometry.
 */
export function buildSkyTrack(system: SkyTrackSystem, opts: SkyTrackOptions = {}): SkyTrack | null {
  const astrometry = trackAstrometry(system);
  if (!astrometry) return null;
  const win =
    opts.window !== undefined
      ? opts.window
      : datasetWindow({ id: system.id, field_id: system.field_id ?? null, provenance: system.provenance });
  const passes = win?.passes ?? [];
  const startMjd = Math.min(DR1_START_MJD, ...passes.map((p) => p.startMjd));
  const endMjd = Math.max(DATASET_TODAY_MJD, ...passes.map((p) => p.endMjd));
  const step = opts.stepDays && opts.stepDays > 0 ? opts.stepDays : 2;

  // Windows that get a dot: each pass, or each of its visits when the 10-day gap splits it.
  const windows: { passIndex: number; label: string; start: number; end: number; nImages: number; approx: boolean }[] = [];
  for (const p of passes) {
    if (p.subVisits.length > 1) {
      p.subVisits.forEach((v, k) =>
        windows.push({
          passIndex: p.index,
          label: `${p.index + 1}${String.fromCharCode(97 + k)}`,
          start: v.startMjd,
          end: v.endMjd,
          nImages: v.nImages,
          approx: p.datesApprox,
        }),
      );
    } else {
      windows.push({ passIndex: p.index, label: String(p.index + 1), start: p.startMjd, end: p.endMjd, nImages: p.nImages, approx: p.datesApprox });
    }
  }

  const place = (mjd: number) => astrometricPlace(astrometry, mjd);
  const refMjd = windows.length ? (windows[0].start + windows[0].end) / 2 : startMjd;
  const refPlace = place(refMjd);
  const point = (mjd: number): TrackPoint => {
    const p = place(mjd);
    return { mjd, ...p, ...tangentOffsetArcsec(refPlace, p) };
  };

  const samples = sampleTimes(startMjd, endMjd, step).map(point);
  const marks: TrackMark[] = [];
  for (const w of windows) {
    const mid = (w.start + w.end) / 2;
    const position = point(mid);
    const segment = sampleTimes(w.start, w.end, 1).map(point);
    const prev = marks[marks.length - 1];
    marks.push({
      passIndex: w.passIndex,
      label: w.label,
      startMjd: w.start,
      endMjd: w.end,
      mjd: mid,
      dates: [mjdToIsoDate(w.start), mjdToIsoDate(w.end)],
      datesApprox: w.approx,
      nImages: w.nImages,
      position,
      segment,
      driftArcsec: separationArcsec(segment[0], segment[segment.length - 1]),
      shiftFromPreviousArcsec: prev ? separationArcsec(prev.position, position) : null,
      shiftFromFirstArcsec: marks.length ? separationArcsec(marks[0].position, position) : 0,
    });
  }
  // Pass windows from the coverage table use dates, not times: label them by the dated pass.
  for (const p of passes) {
    if (p.subVisits.length > 1) continue;
    const m = marks.find((k) => k.passIndex === p.index);
    if (m && !p.datesApprox) m.dates = [p.dates[0], p.dates[1]];
  }

  const pmMasYr = Math.hypot(astrometry.pmRaCosDecMasYr, astrometry.pmDecMasYr);
  const beta = eclipticLatitudeDeg(astrometry);
  const parallaxArcsec = astrometry.parallaxMas / 1000;
  let parallaxMaxArcsec = 0;
  for (const s of samples) {
    parallaxMaxArcsec = Math.max(parallaxMaxArcsec, separationArcsec(s, astrometricPlace(astrometry, s.mjd, { observer: 'barycentric' })));
  }
  const radialVelocityEffectArcsec =
    astrometry.radialVelocityKmS === null ? null : separationArcsec(place(endMjd), astrometricPlace(astrometry, endMjd, { radialVelocity: false }));

  let spanArcsec = 0;
  for (let i = 0; i < samples.length; i++) {
    for (let j = i + 1; j < samples.length; j += 1) {
      const d = Math.hypot(samples[i].east - samples[j].east, samples[i].north - samples[j].north);
      if (d > spanArcsec) spanArcsec = d;
    }
  }

  const staticSources = astrometry.staticSources.map((src) => {
    let closest = { mjd: startMjd, separationArcsec: Infinity };
    for (const s of samples) {
      const d = separationArcsec(s, src);
      if (d < closest.separationArcsec) closest = { mjd: s.mjd, separationArcsec: d };
    }
    return { ...src, ...tangentOffsetArcsec(refPlace, src), closest };
  });

  const track: Omit<SkyTrack, 'tiers'> = {
    systemId: system.id,
    astrometry,
    reference: {
      mjd: refMjd,
      ...refPlace,
      east: 0,
      north: 0,
      label: windows.length ? `predicted place at the middle of Pass ${windows[0].label} (${mjdToIsoDate(refMjd)})` : `predicted place on ${mjdToIsoDate(refMjd)}`,
    },
    startMjd,
    endMjd,
    samples,
    marks,
    start: samples[0],
    end: samples[samples.length - 1],
    staticSources,
    pmArcsecPerYr: pmMasYr / 1000,
    pmPxPerYr: pmMasYr / 1000 / SPHEREX_PIXEL_ARCSEC,
    pmPositionAngleDeg: positionAngleDeg({ east: astrometry.pmRaCosDecMasYr, north: astrometry.pmDecMasYr }),
    parallaxArcsec,
    parallaxMinorArcsec: parallaxArcsec * Math.abs(Math.sin(beta * DEG)),
    eclipticLatitudeDeg: beta,
    parallaxMaxArcsec,
    radialVelocityEffectArcsec,
    totalShiftArcsec: marks.length > 1 ? separationArcsec(marks[0].position, marks[marks.length - 1].position) : 0,
    spanArcsec,
    staticAtPixelScale: spanArcsec / SPHEREX_PIXEL_ARCSEC < STATIC_SPAN_PX,
    coverageSource: win && passes.length ? (win.source || SPHEREX_COVERAGE_SOURCE) : null,
    coverageTarget: win?.target ?? null,
  };
  return { ...track, tiers: trackTiers(track) };
}

/** The place and offset on any date (e.g. the current dataset date of the 3D view). */
export function trackPointAt(track: Pick<SkyTrack, 'astrometry' | 'reference'>, mjd: number): TrackPoint {
  const p = astrometricPlace(track.astrometry, mjd);
  return { mjd, ...p, ...tangentOffsetArcsec(track.reference, p) };
}

/** Evidence tier of each part of the panel, in the WS7 vocabulary (astro.ts Tier). */
function trackTiers(t: Omit<SkyTrack, 'tiers'>): TierLine[] {
  const a = t.astrometry;
  const rv =
    a.radialVelocityKmS === null
      ? 'no radial velocity, so the radial motion is left out'
      : `radial velocity ${fmtSigned(a.radialVelocityKmS, 2)} km/s included (it moves the place by ${formatArcsec(t.radialVelocityEffectArcsec ?? 0)} by ${mjdToIsoDate(t.endMjd)})`;
  const sunErrMas = SUN_BARYCENTRE_MAX_AU * a.parallaxMas;
  return [
    {
      tier: 'derived',
      label: 'Positions',
      text: `Propagated from the catalog epoch ${a.epochLabel} along a straight line in space (${SPACE_MOTION_CITATION}); ${rv}. Astrometry: ${a.source}.`,
    },
    {
      tier: 'model',
      label: 'Parallax',
      text: `Earth position from low-precision solar coordinates (${EARTH_EPHEMERIS_CITATION}), good to about 0.01° in longitude. It is heliocentric rather than barycentric (the Sun is within ${SUN_BARYCENTRE_MAX_AU} AU of the barycentre in 2025–2026), so the parallax shift is good to ${sunErrMas < 1 ? 'better than 1' : `about ${sunErrMas.toFixed(0)}`} mas. SPHEREx's own orbit around the Earth is negligible.`,
    },
    {
      tier: 'derived',
      label: 'Place',
      text: 'Geocentric ICRS astrometric place (no aberration or light deflection), as used to match catalogs and centre cut-outs. Each dot is the middle of a pass window; frames within a pass are spread over the drift shown.',
    },
    {
      tier: 'display',
      label: 'Grid',
      text: `Squares are the ${SPHEREX_PIXEL_ARCSEC}″ SPHEREx pixel scale, aligned on the reference place for display: every real frame has its own pixel phase and orientation. North up, east left.`,
    },
  ];
}

// --- plot layout (pure, for the SVG panel) ----------------------------------------------------

export type PlotMode = 'pixels' | 'fit';

export interface PlotLayout {
  width: number;
  height: number;
  /** Screen pixels per arcsec. */
  scale: number;
  /** Offsets at the centre of the plot (arcsec). */
  centerEast: number;
  centerNorth: number;
  /** Visible offsets (arcsec): east grows to the left. */
  east: [number, number];
  north: [number, number];
  /** Grid spacing (arcsec) and whether labels are in SPHEREx pixels. */
  gridStepArcsec: number;
  gridInPixels: boolean;
}

export const PLOT_MIN_HEIGHT = 180;
export const PLOT_MAX_HEIGHT = 340;

/** 1-2-5 step close to span / target. */
export function niceStep(span: number, target = 4): number {
  if (!(span > 0)) return 1;
  const raw = span / target;
  const mag = 10 ** Math.floor(Math.log10(raw));
  const f = raw / mag;
  return (f < 1.5 ? 1 : f < 3.5 ? 2 : f < 7.5 ? 5 : 10) * mag;
}

/**
 * Equal-aspect view of the track. 'pixels' keeps at least 2.5 x 1.5 SPHEREx pixels in view (the
 * grid is the pixel scale); 'fit' zooms on the track itself (a sub-pixel track then becomes visible).
 */
export function plotLayout(
  points: readonly Offset[],
  widthPx: number,
  mode: PlotMode,
  pad = 24,
): PlotLayout {
  const width = Math.max(200, Math.round(widthPx));
  const es = points.map((p) => p.east);
  const ns = points.map((p) => p.north);
  const eLo = es.length ? Math.min(...es) : 0;
  const eHi = es.length ? Math.max(...es) : 0;
  const nLo = ns.length ? Math.min(...ns) : 0;
  const nHi = ns.length ? Math.max(...ns) : 0;
  const centerEast = (eLo + eHi) / 2;
  const centerNorth = (nLo + nHi) / 2;
  // At least 2.5 x 1.5 pixels in pixel mode (a static target then gets a short, wide plot), and
  // 2 mas when fitting.
  const minSpanE = mode === 'pixels' ? 2.5 * SPHEREX_PIXEL_ARCSEC : 0.002;
  const minSpanN = mode === 'pixels' ? 1.5 * SPHEREX_PIXEL_ARCSEC : 0.002;
  const spanE = Math.max((eHi - eLo) * 1.12, minSpanE);
  const spanN = Math.max((nHi - nLo) * 1.12, minSpanN);
  const innerW = width - 2 * pad;
  const height = Math.round(Math.min(PLOT_MAX_HEIGHT, Math.max(PLOT_MIN_HEIGHT, (innerW * spanN) / spanE + 2 * pad)));
  const innerH = height - 2 * pad;
  const scale = Math.min(innerW / spanE, innerH / spanN);
  const halfE = width / 2 / scale;
  const halfN = height / 2 / scale;
  let gridStepArcsec: number;
  let gridInPixels: boolean;
  if (mode === 'pixels') {
    const mult = [1, 2, 5, 10, 20, 50].find((m) => m * SPHEREX_PIXEL_ARCSEC * scale >= 18) ?? 100;
    gridStepArcsec = mult * SPHEREX_PIXEL_ARCSEC;
    gridInPixels = true;
  } else {
    gridStepArcsec = niceStep(Math.min(2 * halfE, 2 * halfN), 4);
    gridInPixels = false;
  }
  return {
    width,
    height,
    scale,
    centerEast,
    centerNorth,
    east: [centerEast - halfE, centerEast + halfE],
    north: [centerNorth - halfN, centerNorth + halfN],
    gridStepArcsec,
    gridInPixels,
  };
}

/** Grid line positions (multiples of `step`) inside [lo, hi]. */
export function gridValues(lo: number, hi: number, step: number): number[] {
  if (!(step > 0) || !(hi > lo)) return [];
  const out: number[] = [];
  for (let k = Math.ceil(lo / step); k * step <= hi && out.length < 200; k++) out.push(k * step);
  return out;
}

// --- formatting --------------------------------------------------------------------------------

function fmtSigned(x: number, digits: number): string {
  return `${x >= 0 ? '+' : '−'}${Math.abs(x).toFixed(digits)}`;
}

/** Arcsec with a sensible precision: "15.72″", "0.547″", "64 mas", "0.3 mas". */
export function formatArcsec(arcsec: number): string {
  const a = Math.abs(arcsec);
  if (a >= 10) return `${arcsec.toFixed(1)}″`;
  if (a >= 0.1) return `${arcsec.toFixed(a >= 1 ? 2 : 3)}″`;
  const mas = arcsec * 1000;
  return `${Math.abs(mas) >= 1 ? mas.toFixed(0) : mas.toFixed(1)} mas`;
}

/** SPHEREx pixels: "2.56 px", "0.089 px", "0.0070 px". */
export function formatPx(arcsec: number): string {
  const px = arcsec / SPHEREX_PIXEL_ARCSEC;
  const a = Math.abs(px);
  return `${a >= 1 ? px.toFixed(2) : a >= 0.01 ? px.toFixed(3) : px.toPrecision(2)} px`;
}

/** "269.4462952°, +4.7681531°": 7 decimals (0.4 mas), enough to centre a cut-out. */
export function formatPlace(p: RaDec): string {
  return `${p.raDeg.toFixed(7)}°, ${fmtSigned(p.decDeg, 7)}°`;
}
