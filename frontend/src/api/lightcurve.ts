// Pure display logic for the light-curve panel. The wording follows the WS3 review in docs/SCIENCE.md
// ("Revisión científica de las curvas de luz", LC1-LC7 and LC19-LC22): the products carry their own caveats,
// error bars are statistical only, and a significant permutation test means time-correlated variability, not a
// confirmed period.
import { ApiError } from './client';
import { formatMjd } from './format';
import type {
  LightCurveData,
  LightCurvePeriod,
  LightCurvePoint,
  LightCurveProduct,
} from './types';

export type UsedPoint = LightCurvePoint & { rel_mag: number };

/** Brightness ratio for a relative magnitude (positive rel_mag = fainter). */
export function brightnessRatio(relMag: number): number {
  return 10 ** (-0.4 * relMag);
}

/**
 * Brightness relative to the band's mean magnitude, in % (positive = brighter). 0 % is the mean magnitude, i.e. the
 * geometric mean of the band's signals, so the % values of a band do not average to 0 (SCIENCE.md Q2).
 */
export function relativePercent(relMag: number): number {
  return 100 * (brightnessRatio(relMag) - 1);
}

export function signedPercent(percent: number, digits = 1): string {
  const text = Math.abs(percent).toFixed(digits);
  if (Number(text) === 0) return `${text}%`;
  return `${percent > 0 ? '+' : '−'}${text}%`;
}

function formatMag(mag: number): string {
  return mag < 0.01 ? mag.toFixed(4) : mag.toFixed(3);
}

function day(mjd: number): string {
  return formatMjd(mjd).slice(0, 10);
}

function listText(items: string[]): string {
  return items.length < 2 ? items.join('') : `${items.slice(0, -1).join(', ')} and ${items[items.length - 1]}`;
}

function median(values: number[]): number | null {
  if (!values.length) return null;
  const sorted = [...values].sort((a, b) => a - b);
  const mid = sorted.length >> 1;
  return sorted.length % 2 ? sorted[mid] : (sorted[mid - 1] + sorted[mid]) / 2;
}

/** What the measured number is (LC4): uncorrected aperture flux or relative wing brightness. */
export function methodText(method: LightCurveData['method']): string {
  // r = 3 px is APERTURE_PX in pipeline/errante/science/variability.py (a constant, not a product parameter).
  return method === 'wing'
    ? 'Relative brightness of the unsaturated PSF wing (MJy/sr, wing ring minus a background ring). The core is '
      + 'saturated, so total flux cannot be measured here: compare the points with each other only.'
    : 'Uncorrected aperture flux (r = 3 px, no aperture correction), background-subtracted: compare the points with '
      + 'each other, not with catalog fluxes.';
}

/** A saturated aperture flux is a lower limit (LC4): the true signal is brighter. */
export function signalText(point: Pick<LightCurvePoint, 'flux' | 'excluded'>): string {
  if (point.flux === null) return '—';
  const value = point.flux.toPrecision(5);
  return point.excluded === 'saturated' ? `≥ ${value}` : value;
}

/** Collections used, with the wide-survey caveat when no deep collection is included (LC5). */
export function collectionsText(collections: string[]): string {
  if (!collections.length) return 'Not recorded.';
  const deep = collections.some((c) => c.endsWith('_deep'));
  return `${collections.join(', ')}${deep ? '' : ' · wide survey only (deep collections not included)'}`;
}

/**
 * Visit-permutation false-alarm probability as WS3 defines it, (1 + k) / (1 + n): with k = 0 it is the smallest
 * value n permutations can give, a bound rather than a measurement (LC8).
 */
export function falseAlarmText(period: Pick<LightCurvePeriod, 'false_alarm' | 'n_permutations'>): string | null {
  const { false_alarm: probability, n_permutations: n } = period;
  if (probability === null || !(n > 0)) return null;
  const total = n + 1;
  const hits = Math.round(probability * total);
  if (hits < 1 || hits > total || Math.abs(probability * total - hits) > 0.01) {
    return `False-alarm probability ${(probability * 100).toPrecision(2)}% (${n} visit permutations).`;
  }
  return hits === 1
    ? `False-alarm probability 1/${total}: 0 of ${n} visit permutations reached the peak (the smallest value ${n} `
      + 'permutations can give).'
    : `False-alarm probability ${hits}/${total}: ${hits - 1} of ${n} visit permutations reached the peak.`;
}

/**
 * Significance means time-correlated variability, not a confirmed period (LC7); a non-significant test does not rule
 * out variability. WS3 writes the reason for an untested peak into the caveat ("Not tested for significance: ...")
 * only for the grid-edge / too-few-cycles guard; with no permutations run the caveat is the generic one.
 */
export function periodHeadline(
  period: Pick<LightCurvePeriod, 'period_days' | 'significant' | 'caveat' | 'n_permutations'>,
): string {
  const best = `${period.period_days.toFixed(1)} days`;
  if (period.significant === true) {
    return 'Significant time-correlated variability in the visit-permutation test. '
      + `Best-fitting cycle: ${best} (a candidate, not a confirmed period).`;
  }
  if (period.significant === false) {
    return 'Not significant in the visit-permutation test: the sinusoid does not fit significantly better than the '
      + `same visits with shuffled epochs. This does not rule out variability, and the best grid period (${best}) is `
      + 'not evidence of a cycle.';
  }
  const why = period.caveat.startsWith('Not tested for significance:') ? ' (the caveat below says why)'
    : period.n_permutations === 0 ? ' (no visit permutations were run)' : '';
  return `Not tested for significance${why}. Best grid period: ${best}, not a period estimate.`;
}

/** Peaks after the best one: with seasonal gaps they are likely aliases of the visit cadence. */
export function aliasPeaks(period: Pick<LightCurvePeriod, 'peaks' | 'period_days'>): number[] {
  return period.peaks.slice(1).map(([days]) => days)
    .filter((days) => Math.abs(days - period.period_days) > 1e-6 * period.period_days);
}

export function aliasText(period: Pick<LightCurvePeriod, 'peaks' | 'period_days'>): string | null {
  const others = aliasPeaks(period);
  if (!others.length) return null;
  return `Other peaks: ${listText(others.map((d) => d.toFixed(1)))} days (possible aliases of the visit cadence, `
    + 'not independent periods).';
}

export function bootstrapText(period: Pick<LightCurvePeriod, 'significant' | 'bootstrap_95_days'>): string | null {
  if (period.significant !== true || !period.bootstrap_95_days) return null;
  const [low, high] = period.bootstrap_95_days;
  return `Bootstrap 95% interval: ${low.toFixed(1)}–${high.toFixed(1)} days (conditional on the chosen peak).`;
}

/** Empirical uncertainty context for one detector (LC2): the bars alone are statistical only. */
export interface BandFloor {
  detector: number;
  method: LightCurveData['method'];
  /** Median statistical rel_mag_err of the plotted points (mag). */
  statisticalMag: number | null;
  /** Robust scatter of the comparison stars (aperture photometry in the same exposures). */
  controlMag: number | null;
  controlStars: number | null;
  /** Wing only: per-exposure scatter around the fitted sinusoid (an upper bound on the floor). */
  fitFloorMag: number | null;
  /** Half-width (mag) of the pale band drawn around each point, or null when no floor applies. */
  plotMag: number | null;
  /**
   * The statistical bars are a lower bound even on the statistical error: wing photometry without a VARIANCE plane
   * leaves out the wing's own photon noise (variability.py `_wing_flux`; SCIENCE.md Q1).
   */
  statisticalLowerBound: boolean;
}

/**
 * Whether the input stamps included the VARIANCE plane, read from the product's "Input stamps: ...; planes=..." note
 * (null when the note is absent). The pipeline's default wing stamps are IMAGE + FLAGS only.
 */
export function stampsHaveVariance(notes: string[]): boolean | null {
  const planes = notes.find((n) => n.startsWith('Input stamps:'))?.match(/planes=([A-Z_,]+)/)?.[1];
  return planes === undefined ? null : planes.split(',').includes('VARIANCE');
}

export function bandFloor(
  curve: Pick<LightCurveData, 'method' | 'control' | 'period'>,
  detector: number,
  points: Pick<LightCurvePoint, 'rel_mag_err'>[],
  variance: boolean | null = null,
): BandFloor {
  const control = curve.control[String(detector)];
  const controlMag = control?.robust_sigma_mag ?? null;
  const fitFloorMag = curve.method === 'wing' ? curve.period?.floor_mag[String(detector)] ?? null : null;
  return {
    detector,
    method: curve.method,
    statisticalMag: median(points.flatMap((p) => p.rel_mag_err === null ? [] : [p.rel_mag_err])),
    controlMag,
    controlStars: control?.n_stars ?? null,
    fitFloorMag,
    // For wing photometry the comparison stars are not the target's floor (they are aperture photometry of
    // fainter stars), so only the fit scatter is drawn.
    plotMag: curve.method === 'wing' ? fitFloorMag : controlMag,
    // An unrecorded plane list means the default wing stamps, which carry no VARIANCE plane.
    statisticalLowerBound: curve.method === 'wing' && variance !== true,
  };
}

/** Figure caption (LC22, LC2): what 0 % is, which way is brighter, and what the bars are. */
export function plotCaption(floor: Pick<BandFloor, 'plotMag' | 'statisticalLowerBound'> | null): string {
  return 'Each point is one exposure. 0% is this band\'s mean magnitude (the geometric mean of its signals), not a '
    + 'baseline or quiescent level: compare the points with each other. Positive % = brighter (up); the magnitudes '
    + 'in the product notes use the opposite sign (negative = brighter). The thin bars are the statistical '
    + `uncertainty only${floor?.statisticalLowerBound ? ' (for the wing, a lower bound even on that)' : ''}`
    + `${floor?.plotMag != null ? '; the pale bars show the empirical floor described below' : ''}.`;
}

export function floorTexts(floor: BandFloor): string[] {
  const d = `D${floor.detector}`;
  const texts = [floor.statisticalMag === null
    ? 'No statistical errors are reported for these points.'
    : `Error bars are statistical only (median ±${formatMag(floor.statisticalMag)} mag in this band) and leave out `
      + `systematics${floor.statisticalLowerBound
        ? '. For the wing they also leave out the wing\'s own photon noise (no VARIANCE plane), so they are a lower '
          + 'bound even on the statistical error'
        : ''}.`];
  const stars = floor.controlStars === null ? 'comparison stars' : `${floor.controlStars} comparison stars`;
  if (floor.method === 'aperture') {
    texts.push(floor.controlMag === null
      ? `No comparison-star control is published for ${d}: the real uncertainty is larger than these bars by an `
        + 'unknown amount.'
      : `Comparison stars measured with the same aperture in the same exposures scatter by ±${formatMag(floor.controlMag)} `
        + `mag (${d}, robust σ of ${stars}): an empirical estimate of the per-point floor (pale bars).`);
    return texts;
  }
  texts.push(floor.fitFloorMag === null
    ? `No empirical floor is published for ${d} without a period fit: the real uncertainty is larger than these bars.`
    : `Scatter of ${d} exposures around the fitted sinusoid: ±${formatMag(floor.fitFloorMag)} mag (pale bars). It is `
      + 'an upper bound on the measurement floor, because it also contains the non-sinusoidal shape of the light curve.');
  if (floor.controlMag !== null) {
    texts.push(`The comparison-star control (±${formatMag(floor.controlMag)} mag in ${d}, ${stars}) is aperture `
      + 'photometry of fainter stars, not the floor of this wing measurement.');
  }
  return texts;
}

export interface BandChange { percent: number; from: number; to: number }

/** Last vs first used point of one band (points sorted by time). */
export function bandChange(points: UsedPoint[]): BandChange | null {
  if (points.length < 2) return null;
  const first = points[0], last = points[points.length - 1];
  if (!(last.mjd > first.mjd)) return null;
  return { percent: 100 * (brightnessRatio(last.rel_mag - first.rel_mag) - 1), from: first.mjd, to: last.mjd };
}

/** LC21: with significant time-correlated variability, first-to-last compares two phases; it is never a trend. */
export function changeText(change: BandChange, { wing, cyclic }: { wing: boolean; cyclic: boolean }): string {
  const what = wing ? 'relative wing brightness' : 'aperture flux';
  const head = `Last vs first measurement in this band (${day(change.from)} to ${day(change.to)}): `
    + `${signedPercent(change.percent)} ${what}.`;
  return cyclic
    ? `${head} With significant time-correlated variability this is a difference between two phases, not a trend.`
    : `${head} A difference between two exposures, not a trend fit.`;
}

const SELECTION_NOTES = ['Search snapshot query date:'];
// Already shown as structured fields or purely technical; listed under "Technical provenance".
const TECHNICAL_NOTES = [
  'Archive search service:', 'Archive selection:', 'Measured exposures:', 'Input stamps:',
  'Effective package versions:', 'Product id is', 'Native measurement unit:',
];

/**
 * Split the product's own notes (LC1). Sorting only moves a note between visible blocks and the technical list:
 * an unknown note always lands in the visible limits.
 */
export function sortNotes(provenanceNotes: string[], curveNotes: string[]) {
  const limits: string[] = [], selection: string[] = [], technical: string[] = [];
  for (const note of new Set([...provenanceNotes, ...curveNotes])) {
    if (SELECTION_NOTES.some((p) => note.startsWith(p))) selection.push(note);
    else if (TECHNICAL_NOTES.some((p) => note.startsWith(p))) technical.push(note);
    else limits.push(note);
  }
  return { limits, selection, technical };
}

function dateFilterText(mjdMin: number | null, mjdMax: number | null): string {
  if (mjdMin === null && mjdMax === null) return 'None';
  if (mjdMin === null) return `Up to ${day(mjdMax as number)} (MJD ${mjdMax})`;
  if (mjdMax === null) return `From ${day(mjdMin)} (MJD ${mjdMin})`;
  return `${day(mjdMin)} to ${day(mjdMax)} (MJD ${mjdMin}–${mjdMax})`;
}

function builtText(builtAt: string): string {
  const date = new Date(builtAt);
  return Number.isFinite(date.getTime()) ? `${date.toISOString().replace('T', ' ').slice(0, 16)} UTC` : builtAt;
}

export interface SelectionRow { label: string; value: string }

/** The data actually used (LC1, LC5): collections, search, dates, failures and build date. */
export function selectionRows(product: LightCurveProduct): SelectionRow[] {
  const { curve, provenance, parameters } = product;
  // The contract carries only these booleans: a non-stale search may still be a cache hit within its TTL, and
  // `partial` is also set by a stale snapshot, a truncated selection or search errors (lightcurve_build.py).
  const search = [
    provenance.stale_search
      ? 'answered from a stale cache or snapshot (not by itself missing data)'
      : 'not answered from a stale cache or snapshot',
    provenance.truncated_search && 'selection truncated',
    provenance.partial && 'partial: the selection or the reading may be incomplete (see Inputs not measured and the notes)',
  ].filter(Boolean).join(' · ');
  const mjds = curve.points.map((p) => p.mjd);
  const used = curve.points.filter((p) => p.excluded === null && p.rel_mag !== null).length;
  const failures = new Map<string, number>();
  for (const f of curve.failures) {
    const reason = f.reason.replaceAll('_', ' ');
    failures.set(reason, (failures.get(reason) ?? 0) + 1);
  }
  return [
    { label: 'Collections', value: collectionsText(provenance.collections) },
    { label: 'Detectors', value: parameters.detectors.length ? parameters.detectors.map((d) => `D${d}`).join(', ') : 'All' },
    { label: 'Archive search', value: `${provenance.n_selected} selected of ${provenance.n_found ?? 'unknown'} found · ${search}` },
    { label: 'Date filter', value: dateFilterText(parameters.mjd_min, parameters.mjd_max) },
    {
      label: 'Exposures measured',
      value: mjds.length
        ? `${mjds.length}, ${day(Math.min(...mjds))} to ${day(Math.max(...mjds))} UTC; ${used} used in the light curve`
        : 'None',
    },
    {
      label: 'Inputs not measured',
      value: failures.size
        ? `${curve.failures.length} (${[...failures].map(([reason, n]) => `${reason}: ${n}`).join(', ')})`
        : 'None',
    },
    { label: 'Product built', value: `${builtText(product.built_at)} · pipeline ${provenance.pipeline_version}` },
  ];
}

/** Fetch a product; a missing product (404, or a static host's HTML fallback) is not an error. */
export async function loadLightCurve(
  source: { getLightCurve(targetId: string, signal?: AbortSignal): Promise<LightCurveProduct> },
  targetId: string,
  signal?: AbortSignal,
): Promise<LightCurveProduct | 'missing'> {
  try {
    const product = await source.getLightCurve(targetId, signal);
    // The contract forbids synthetic light curves; never show one if it ever appears.
    return (product as { synthetic: unknown }).synthetic === false ? product : 'missing';
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) return 'missing';
    throw error;
  }
}
