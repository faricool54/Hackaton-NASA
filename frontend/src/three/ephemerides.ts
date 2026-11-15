// WS7 ephemeris tables for the 3D gallery's "Dataset time" mode (M5, S2, S3). Pure: no React, no three.js.
//
// The contract (0.2.1) has no fields for epoch or period uncertainties, nor an epoch for a Variability,
// so those values live here, each with its source (user decision: no contract change). The orbital
// epochs themselves are in the catalog (Orbit.epoch_mjd, mean_anomaly_deg); the tests check that this
// table and the shipped JSON agree.
//
//   Orbits (M5, S2)   Barnard b-e: t0 and P with 1-sigma from Basant et al. 2025, Table 3. t0 is read as the
//                     time of inferior conjunction (juliet passes it to RadVel as 'tc'); the paper text
//                     says periastron. Phase spread sigma_phi = sqrt(sigma_t0^2 + N^2 sigma_P^2) / P,
//                     N = (t - t0) / P (linear propagation; covariance not published, ignored).
//   Mira (S3)         R Dra: AAVSO VSX epoch of maximum HJD 2457370.00, P = 246.12 d, rise 45 %. Predicted
//                     maxima stay on the VSX dates; their 1-sigma timing band is the RMS of the O-C of
//                     observed maxima 2015-2024 about VSX, sqrt(4.7^2 + 4.6^2) = 6.6 d (mean -4.7 d,
//                     s.d. 4.6 d, Karlsson list), so the band also covers the mean offset.
//   Unknown phases    Why the other orbits stay arbitrary (Eps Ind Ab, Bb, RW Aur B), with sources.
import type { Body, Orbit, OrbitQuality, SystemModel, VariabilityKind } from '../api/types';
import { mjdToDate } from '../api/format';
import { drawsPulsation, ORBIT_COLOR, PULSATION_RADIUS_AMPLITUDE } from './sceneLayout';

/** MJD = JD - 2400000.5 (BJD_TDB/HJD vs UTC differ by ~69 s and minutes: negligible at day precision). */
export const JD_MINUS_MJD = 2400000.5;

export function jdToMjd(jd: number): number {
  return jd - JD_MINUS_MJD;
}

function frac(x: number): number {
  return x - Math.floor(x);
}

function isoDay(mjd: number): string {
  const d = mjdToDate(mjd);
  return Number.isFinite(d.getTime()) ? d.toISOString().slice(0, 10) : '?';
}

// --- orbits (M5, S2) ------------------------------------------------------------------------------

export interface OrbitEphemeris {
  systemId: string;
  bodyId: string;
  /** Reference time as published (BJD). */
  t0Bjd: number;
  /** t0 as printed in the source (e.g. '+0.08/−0.07'). */
  t0ErrText: string;
  /** 1-sigma of t0 (days): the larger side of an asymmetric error. */
  t0ErrDays: number;
  periodDays: number;
  periodErrDays: number;
  /** What t0 is (shown with every phase on a real date). */
  convention: string;
  source: string;
}

export const BASANT_2025_SOURCE = 'Basant et al. 2025, ApJL 982, L1, Table 3 (arXiv:2503.08095)';

/** Short form of the t0 convention, shown with every Barnard phase. */
export const CONJUNCTION_CONVENTION =
  'time of inferior conjunction as used by juliet/RadVel (tc); the paper text says periastron';

/** Mean anomaly (deg) at conjunction in the WS7 frame: AU (0, −a, 0) = scene +z, the 'toward Earth' arrow. */
export const CONJUNCTION_MEAN_ANOMALY_DEG = 270;

export const LINE_OF_SIGHT_LABEL = 'toward Earth (line of sight projected on the orbit plane; inclination unknown)';

const barnard = (bodyId: string, t0Bjd: number, t0ErrText: string, t0ErrDays: number, periodDays: number, periodErrDays: number): OrbitEphemeris => ({
  systemId: 'barnards-star',
  bodyId,
  t0Bjd,
  t0ErrText,
  t0ErrDays,
  periodDays,
  periodErrDays,
  convention: CONJUNCTION_CONVENTION,
  source: BASANT_2025_SOURCE,
});

/** Table 3 lists t0 as BJD − 2450000; full BJD here. e's period error is the paper's 0.0028 d (the archive rounds to 0.003). */
export const ORBIT_EPHEMERIDES: readonly OrbitEphemeris[] = [
  barnard('barnard-d', 2460243.7, '+0.08/−0.07', 0.08, 2.3402, 0.0003),
  barnard('barnard-b', 2460243.38, '± 0.09', 0.09, 3.1542, 0.0004),
  barnard('barnard-c', 2460242.92, '± 0.10', 0.1, 4.1244, 0.0006),
  barnard('barnard-e', 2460245.3, '+0.37/−0.36', 0.37, 6.7392, 0.0028),
];

export function orbitEphemerisFor(systemId: string, bodyId: string): OrbitEphemeris | null {
  return ORBIT_EPHEMERIDES.find((e) => e.systemId === systemId && e.bodyId === bodyId) ?? null;
}

/** Cycles elapsed since t0 (N, signed). */
export function cyclesSinceT0(eph: OrbitEphemeris, mjd: number): number {
  return (mjd - jdToMjd(eph.t0Bjd)) / eph.periodDays;
}

/** 1-sigma orbital phase spread (cycles) at `mjd`: sqrt(σt0² + N²σP²) / P. */
export function phaseSigmaCycles(eph: OrbitEphemeris, mjd: number): number {
  const n = cyclesSinceT0(eph, mjd);
  return Math.hypot(eph.t0ErrDays, n * eph.periodErrDays) / eph.periodDays;
}

export function phaseSigmaDeg(eph: OrbitEphemeris, mjd: number): number {
  return 360 * phaseSigmaCycles(eph, mjd);
}

/** Above this 1-sigma spread the phase is no longer pinned down: drawn as a ring, not an arc. */
export const RING_SIGMA_CYCLES = 0.5;

// --- phase clouds: 64 points per orbit (S2) --------------------------------------------------------

export const CLOUD_POINTS = 64;
/** The arc covers ±2σ in mean anomaly. */
export const ARC_HALF_WIDTH_SIGMA = 2;
/** Φ(2), the standard normal CDF at 2. */
const PHI_2 = 0.9772498680518208;

/** Inverse standard normal CDF (Acklam 2003 rational approximation, relative error < 1.2e-9). */
export function normalQuantile(p: number): number {
  if (!(p > 0 && p < 1)) return p === 0 ? -Infinity : p === 1 ? Infinity : NaN;
  const a = [-39.69683028665376, 220.9460984245205, -275.9285104469687, 138.357751867269, -30.66479806614716, 2.506628277459239];
  const b = [-54.47609879822406, 161.5858368580409, -155.6989798598866, 66.80131188771972, -13.28068155288572];
  const c = [-0.007784894002430293, -0.3223964580411365, -2.400758277161838, -2.549732539343734, 4.374664141464968, 2.938163982698783];
  const d = [0.007784695709041462, 0.3224671290700398, 2.445134137142996, 3.754408661907416];
  const tail = (q: number) =>
    (((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1);
  const pLow = 0.02425;
  if (p < pLow) return tail(Math.sqrt(-2 * Math.log(p)));
  if (p > 1 - pLow) return -tail(Math.sqrt(-2 * Math.log(1 - p)));
  const q = p - 0.5;
  const r = q * q;
  return ((((((a[0] * r + a[1]) * r + a[2]) * r + a[3]) * r + a[4]) * r + a[5]) * q) /
    (((((b[0] * r + b[1]) * r + b[2]) * r + b[3]) * r + b[4]) * r + 1);
}

/**
 * Fixed standard-normal quantiles of the arc: equal-probability points inside ±2σ, so their spacing
 * follows the Gaussian. The first half is computed and mirrored, so the set is exactly symmetric and
 * never changes between frames.
 */
export const ARC_Z: readonly number[] = (() => {
  const lo = 1 - PHI_2;
  const span = 2 * PHI_2 - 1;
  const half = Array.from({ length: CLOUD_POINTS / 2 }, (_, k) => normalQuantile(lo + ((k + 0.5) / CLOUD_POINTS) * span));
  return [...half, ...half.map((z) => -z).reverse()];
})();

/** Opacity of each arc point: follows the Gaussian density (1 at the centre), with a floor. */
export const ARC_ALPHA: readonly number[] = ARC_Z.map((z) => 0.15 + 0.85 * Math.exp(-0.5 * z * z));

/** Opacity of the points of an unknown-phase ring. */
export const RING_ALPHA = 0.45;

/** Ring: mean anomalies uniform in [0, 2π) = uniform in time, so the ring is denser near apoapsis. */
export const RING_MEAN_ANOMALIES: readonly number[] = Array.from({ length: CLOUD_POINTS }, (_, k) => (2 * Math.PI * k) / CLOUD_POINTS);

export type PhaseCloud =
  | { kind: 'arc'; sigmaCycles: number; meanAnomalies: number[] }
  | { kind: 'ring'; reason: 'no-epoch' | 'too-uncertain'; meanAnomalies: readonly number[] };

/**
 * The points drawn around an orbit on a real date: an arc of ±2σ in mean anomaly about the predicted
 * position (`meanAnomaly`, rad) for a dated orbit with a tabulated σ ≤ 0.5 cycle, a ring otherwise.
 * null for a dated orbit without a tabulated σ (its spread is unknown, so nothing is drawn).
 */
export function phaseCloud(orbit: Orbit, eph: OrbitEphemeris | null, mjd: number, meanAnomaly: number): PhaseCloud | null {
  if (orbit.epoch_mjd == null) return { kind: 'ring', reason: 'no-epoch', meanAnomalies: RING_MEAN_ANOMALIES };
  if (!eph) return null;
  const sigma = phaseSigmaCycles(eph, mjd);
  if (!(sigma <= RING_SIGMA_CYCLES)) return { kind: 'ring', reason: 'too-uncertain', meanAnomalies: RING_MEAN_ANOMALIES };
  const s = 2 * Math.PI * sigma;
  return { kind: 'arc', sigmaCycles: sigma, meanAnomalies: ARC_Z.map((z) => meanAnomaly + z * s) };
}

/** Phase clouds use the orbit colour of the legend, lightened so 3-px points read on the black sky. */
function mixHex(hex: string, t: number): string {
  const n = parseInt(hex.slice(1), 16);
  const ch = [(n >> 16) & 255, (n >> 8) & 255, n & 255].map((v) => Math.round(v + (255 - v) * t));
  return `#${ch.map((v) => v.toString(16).padStart(2, '0')).join('')}`;
}

export const UNCERTAINTY_COLOR: Record<OrbitQuality, string> = {
  fitted: mixHex(ORBIT_COLOR.fitted, 0.45),
  assumed: mixHex(ORBIT_COLOR.assumed, 0.45),
  hypothetical: mixHex(ORBIT_COLOR.hypothetical, 0.45),
};

/** Dated circle in the reference plane (i = Ω = ω = 0): the 'toward Earth' arrow applies to it. */
export function isLineOfSightOrbit(orbit: Orbit): boolean {
  return orbit.epoch_mjd != null && orbit.inclination_deg === 0 && orbit.ascending_node_deg === 0 && orbit.arg_periapsis_deg === 0;
}

// --- why the other phases are unknown -------------------------------------------------------------

export interface UnknownPhaseReason {
  text: string;
  source: string;
}

export const UNKNOWN_PHASE_REASONS: Readonly<Record<string, UnknownPhaseReason>> = {
  'epsilon-indi/eps-indi-ab': {
    text: 'Sanghi et al. 2026 give a periastron time JD 2441420.76 (+2675/−3217 d) and P = 25450 (+4387/−3302) d; the two are strongly correlated and the covariance is not published, so the phase is not propagated',
    source: 'Sanghi et al. 2026, AJ 172, 115 (NASA Exoplanet Archive)',
  },
  'epsilon-indi/eps-indi-bb': {
    text: 'Chen et al. 2022 fitted a periastron time but do not publish it (Table 4 lists P, a, e, ω, Ω and i only)',
    source: 'Chen et al. 2022, AJ 163, 288, Sect. VI.1 and Table 4',
  },
  'rw-aurigae/rw-aur-b': {
    text: 'periastron 295 (+136/−457) yr before the last ALMA epoch (about 1590–2180 AD), and the mapping of the orbit frame onto the sky is not documented',
    source: 'Kurtovic et al. 2024, A&A (arXiv:2407.18828), Table 3 and Sect. 3.3',
  },
};

export function unknownPhaseReason(systemId: string, body: Body): UnknownPhaseReason {
  const r = UNKNOWN_PHASE_REASONS[`${systemId}/${body.id}`];
  if (r) return r;
  if (body.orbit && body.orbit.quality && body.orbit.quality !== 'fitted') {
    return { text: `${body.orbit.quality} orbit, not fitted: there is no phase to predict`, source: 'catalog (Orbit.quality)' };
  }
  return { text: 'no published epoch for this orbit', source: 'catalog (Orbit.epoch_mjd is null)' };
}

/**
 * Tooltip of a body dimmed on a real date (orbit without an epoch). Only a fitted orbit's ring shows
 * where the body could be; an assumed or hypothetical orbit is itself a guess.
 */
export function undatedOrbitTitle(quality: OrbitQuality): string {
  if (quality === 'fitted') {
    return 'No published epoch for this orbit: its position on this date is not known (dimmed; the ring shows where it could be).';
  }
  return `Ring on ${quality === 'assumed' ? 'an assumed' : 'a hypothetical'} orbit: neither the orbit nor the phase is known (dimmed; the ring only shows the drawn guess, not where the body could be).`;
}

// --- Mira pulsation (S3) --------------------------------------------------------------------------

export interface MiraEphemeris {
  systemId: string;
  bodyId: string;
  /** Epoch of maximum light (V), HJD. */
  epochHjd: number;
  periodDays: number;
  /** Rise time from minimum to maximum as a fraction of the period ((M − m)/P). */
  riseFraction: number;
  band: string;
  /** Mean O−C of observed maxima against this ephemeris (days; negative = the maxima came early). */
  ocMeanDays: number;
  /** Standard deviation of that O−C about its mean (days). */
  ocSdDays: number;
  /**
   * 1-sigma band of a predicted maximum (days) about the ephemeris date: the RMS of the O−C,
   * sqrt(mean² + s.d.²). The predicted dates are not shifted by the mean, so the band carries it.
   */
  timingSigmaDays: number;
  /** Eddington-Plakidis random cycle-length term (days); null = not sourced. */
  epsDays: number | null;
  source: string;
  timingSource: string;
  note: string;
}

export const MIRA_PREDICTION_CAVEAT =
  'V-band prediction from a catalogue ephemeris; IR amplitude is smaller and IR maxima lag the visual ones; not a SPHEREx light curve';

export const MIRA_EPHEMERIDES: readonly MiraEphemeris[] = [
  {
    systemId: 'r-draconis',
    bodyId: 'r-draconis',
    epochHjd: 2457370.0,
    periodDays: 246.12,
    riseFraction: 0.45,
    band: 'V',
    ocMeanDays: -4.7,
    ocSdDays: 4.6,
    timingSigmaDays: Math.hypot(4.7, 4.6), // 6.58 d: RMS of the O−C about VSX
    epsDays: null,
    source: 'AAVSO VSX R Dra (oid 13673, revision 4, 2024-01-18): epoch of maximum HJD 2457370.00, P = 246.12 d, rise 45 %',
    timingSource:
      'O−C of observed maxima 2015–2024 against the VSX ephemeris (T. Karlsson, Maxima of Mira stars, var.saaf.se): s.d. 4.6 d, mean −4.7 d; band = RMS about VSX, √(4.7² + 4.6²) ≈ 6.6 d',
    note: 'VSX gives no epoch or period errors. The predicted maxima are the VSX dates, not shifted: observed maxima came on average 4.7 d before them, so the ±6.6 d band (1σ) is the RMS of the O−C about VSX, which includes that offset, not only the 4.6 d scatter. It is not a formal error and still underestimates the uncertainty: no cycle-to-cycle (Eddington–Plakidis) term is sourced and the period wanders over decades. The catalog period (GCVS 245.6 d) drives the free-running animation; dataset time uses the VSX epoch and period together.',
  },
];

export function miraEphemerisFor(systemId: string, bodyId: string): MiraEphemeris | null {
  return MIRA_EPHEMERIDES.find((e) => e.systemId === systemId && e.bodyId === bodyId) ?? null;
}

/** Cycle count since the epoch of maximum, (t − E0)/P. */
export function miraCycle(eph: MiraEphemeris, mjd: number): number {
  return (mjd - jdToMjd(eph.epochHjd)) / eph.periodDays;
}

/** Predicted phase φ = frac((t − E0)/P); 0 = maximum light. */
export function miraPhase(eph: MiraEphemeris, mjd: number): number {
  return frac(miraCycle(eph, mjd));
}

/** 1-sigma timing band (days): sqrt(σ_band² + N ε²); ε is not sourced, so the band alone today. */
export function miraTimingSigmaDays(eph: MiraEphemeris, mjd: number): number {
  const n = Math.abs(miraCycle(eph, mjd));
  return Math.sqrt(eph.timingSigmaDays ** 2 + (eph.epsDays !== null ? n * eph.epsDays ** 2 : 0));
}

/** A timing band as shown in the UI, to 0.1 d (e.g. '6.6'). */
export function formatTimingDays(days: number): string {
  return days.toFixed(1);
}

export function miraPhaseSigma(eph: MiraEphemeris, mjd: number): number {
  return miraTimingSigmaDays(eph, mjd) / eph.periodDays;
}

/** Phase of minimum light: maximum is at 0 and the rise takes riseFraction of the period. */
export function minimumPhase(eph: MiraEphemeris): number {
  return 1 - eph.riseFraction;
}

/** Light-curve shape in [−1, 1] (+1 at maximum): half-cosines falling to minimum, then rising (asymmetric). */
export function miraShape(eph: MiraEphemeris, phase: number): number {
  const p = frac(phase);
  const m = minimumPhase(eph);
  return p < m ? Math.cos((Math.PI * p) / m) : -Math.cos((Math.PI * (p - m)) / eph.riseFraction);
}

/** Within this many cycles of maximum or minimum, the state reads "near maximum/minimum" (display choice). */
export const NEAR_EXTREMUM_CYCLES = 0.1;

export function miraState(eph: MiraEphemeris, phase: number): string {
  const p = frac(phase);
  const m = minimumPhase(eph);
  const toMax = Math.min(p, 1 - p);
  if (toMax <= NEAR_EXTREMUM_CYCLES) return p > 0.5 ? 'rising, near maximum' : 'just past maximum';
  if (Math.abs(p - m) <= NEAR_EXTREMUM_CYCLES) return 'near minimum';
  return p < m ? 'declining' : 'rising';
}

/** Predicted maxima (MJD) in [lo, hi]. */
export function predictedMaxima(eph: MiraEphemeris, lo: number, hi: number): number[] {
  const out: number[] = [];
  const e0 = jdToMjd(eph.epochHjd);
  for (let k = Math.ceil((lo - e0) / eph.periodDays); e0 + k * eph.periodDays <= hi; k++) out.push(e0 + k * eph.periodDays);
  return out;
}

/** Next predicted maximum at or after `mjd`. */
export function nextMaximum(eph: MiraEphemeris, mjd: number): number {
  const e0 = jdToMjd(eph.epochHjd);
  return e0 + Math.ceil((mjd - e0) / eph.periodDays) * eph.periodDays;
}

export interface PredictedPulsation {
  phase: number;
  phaseSigma: number;
  /** Shape in [−1, 1] (+1 at maximum). */
  shape: number;
  /** V brightness factor (linear flux ratio, 1 = mean), over the catalog's full V range. */
  factor: number;
  /** Radius factor: 1 ± the class-typical 10 %, drawn in phase with the light (display convention). */
  radiusScale: number;
}

/** The drawn pulsation of a body at `mjd` from its Mira ephemeris (dataset time). */
export function predictedPulsation(eph: MiraEphemeris, body: Body, mjd: number): PredictedPulsation {
  const phase = miraPhase(eph, mjd);
  const shape = miraShape(eph, phase);
  const amp = body.variability?.amplitude_mag ?? 0;
  return {
    phase,
    phaseSigma: miraPhaseSigma(eph, mjd),
    shape,
    factor: Math.pow(10, 0.2 * amp * shape), // dmag = −(A/2)·shape
    radiusScale: drawsPulsation(body) ? 1 + PULSATION_RADIUS_AMPLITUDE * shape : 1,
  };
}

// --- what the HUD and the timeline say on a real date ---------------------------------------------

/**
 * How a body's variability is drawn on a real date. ONE rule for the timeline, the "On this date" list,
 * the status line (spherexCoverage.phaseStatus) and the scene (SystemScene):
 *   'irregular'  only kind === 'irregular': never a curve, never predicted;
 *   'predicted'  a periodic variable (period_days > 0) with a WS7 ephemeris whose pulsation is drawn;
 *   'unknown'    everything else - periodic without an ephemeris, or any other kind without a
 *                period: frozen at mean brightness.
 * null when the body has no variability.
 */
export type VariabilityPhase = 'predicted' | 'irregular' | 'unknown';

export function variabilityPhase(systemId: string, body: Body): VariabilityPhase | null {
  const v = body.variability;
  if (!v) return null;
  if (v.kind === 'irregular') return 'irregular';
  if ((v.period_days ?? 0) > 0 && miraEphemerisFor(systemId, body.id) && drawsPulsation(body)) return 'predicted';
  return 'unknown';
}

/**
 * Label of variables frozen at mean brightness: 'pulsation phase unknown' when every kind is a
 * pulsation, 'variability phase unknown' otherwise.
 */
export function phaseUnknownLabel(kinds: VariabilityKind | readonly VariabilityKind[]): string {
  const list: readonly VariabilityKind[] = typeof kinds === 'string' ? [kinds] : kinds;
  return `${list.length > 0 && list.every((k) => k === 'pulsation') ? 'pulsation' : 'variability'} phase unknown`;
}

export type VariabilityTrack =
  | { kind: 'predicted'; bodyId: string; name: string; ephemeris: MiraEphemeris }
  | { kind: 'irregular'; bodyId: string; name: string }
  | { kind: 'unknown'; bodyId: string; name: string; variabilityKind: VariabilityKind };

/** One entry per variable body, classified by variabilityPhase: predicted, irregular or unknown (frozen). */
export function variabilityTracks(system: Pick<SystemModel, 'id' | 'bodies'>): VariabilityTrack[] {
  const out: VariabilityTrack[] = [];
  for (const b of system.bodies) {
    const phase = variabilityPhase(system.id, b);
    if (phase === null || !b.variability) continue;
    const eph = miraEphemerisFor(system.id, b.id);
    if (phase === 'irregular') out.push({ kind: 'irregular', bodyId: b.id, name: b.name });
    else if (phase === 'predicted' && eph) out.push({ kind: 'predicted', bodyId: b.id, name: b.name, ephemeris: eph });
    else out.push({ kind: 'unknown', bodyId: b.id, name: b.name, variabilityKind: b.variability.kind });
  }
  return out;
}

export const IRREGULAR_TEXT = 'irregular: cannot be predicted - look at the frames';

/** Predicted phase over one pass, e.g. "phase 0.90 → 0.26 (±0.03); predicted maximum 2025-05-20 ± 6.6 d". */
export function passPhaseSummary(eph: MiraEphemeris, startMjd: number, endMjd: number): string {
  const sig = miraPhaseSigma(eph, (startMjd + endMjd) / 2);
  const cycles = (endMjd - startMjd) / eph.periodDays;
  const maxima = predictedMaxima(eph, startMjd, endMjd).map((m) => `${isoDay(m)} ± ${formatTimingDays(miraTimingSigmaDays(eph, m))} d`);
  const parts = [`predicted ${eph.band} phase ${miraPhase(eph, startMjd).toFixed(2)} → ${miraPhase(eph, endMjd).toFixed(2)} (±${sig.toFixed(2)})`];
  if (cycles >= 1) parts.push(`${cycles.toFixed(1)} cycles`);
  parts.push(maxima.length ? `predicted maxim${maxima.length > 1 ? 'a' : 'um'} ${maxima.join(', ')}` : 'no predicted maximum in this pass');
  return parts.join('; ');
}

export interface DateLine {
  bodyId: string;
  name: string;
  kind: 'dated' | 'dated-untabulated' | 'arbitrary' | 'predicted' | 'frozen' | 'irregular';
  text: string;
  source: string | null;
}

/** "On this date" lines for every body whose drawing depends on a phase. */
export function onThisDate(system: Pick<SystemModel, 'id' | 'bodies'>, mjd: number): DateLine[] {
  const lines: DateLine[] = [];
  for (const b of system.bodies) {
    const o = b.orbit;
    if (o && b.kind !== 'disk') {
      if (o.epoch_mjd != null) {
        const phase = frac((mjd - o.epoch_mjd) / o.period_days + (o.mean_anomaly_deg - CONJUNCTION_MEAN_ANOMALY_DEG) / 360);
        const eph = orbitEphemerisFor(system.id, b.id);
        if (eph) {
          const s = phaseSigmaCycles(eph, mjd);
          const spread = s > RING_SIGMA_CYCLES ? 'phase no longer constrained (σ > 0.5 cycle)' : `± ${s.toFixed(2)} (±${Math.round(360 * s)}°, 1σ)`;
          lines.push({
            bodyId: b.id,
            name: b.name,
            kind: 'dated',
            text: `orbital phase ${phase.toFixed(2)} ${spread} after inferior conjunction (t0 = ${eph.convention})`,
            source: eph.source,
          });
        } else {
          lines.push({ bodyId: b.id, name: b.name, kind: 'dated-untabulated', text: `orbital phase ${phase.toFixed(2)} from the catalog epoch; uncertainty not tabulated`, source: null });
        }
      } else {
        const r = unknownPhaseReason(system.id, b);
        lines.push({ bodyId: b.id, name: b.name, kind: 'arbitrary', text: `phase unknown: ${r.text}`, source: r.source });
      }
    }
  }
  for (const t of variabilityTracks(system)) {
    if (t.kind === 'predicted') {
      const e = t.ephemeris;
      const phase = miraPhase(e, mjd);
      const next = nextMaximum(e, mjd);
      lines.push({
        bodyId: t.bodyId,
        name: t.name,
        kind: 'predicted',
        text: `predicted ${e.band} phase ${phase.toFixed(2)} ± ${miraPhaseSigma(e, mjd).toFixed(2)} (VSX ephemeris, ±${formatTimingDays(miraTimingSigmaDays(e, mjd))} d 1σ timing band about the VSX dates) · ${miraState(e, phase)} · next predicted maximum ${isoDay(next)}`,
        source: e.source,
      });
    } else if (t.kind === 'irregular') {
      lines.push({ bodyId: t.bodyId, name: t.name, kind: 'irregular', text: IRREGULAR_TEXT, source: null });
    } else {
      lines.push({ bodyId: t.bodyId, name: t.name, kind: 'frozen', text: `${phaseUnknownLabel(t.variabilityKind)}: drawn at mean brightness`, source: null });
    }
  }
  return lines;
}
