import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';
import { LightCurvePanel, LightCurveProductView } from '../components/LightCurvePanel';
import { ApiError } from './client';
import {
  aliasPeaks, aliasText, bandChange, bandFloor, bootstrapText, changeText, collectionsText, falseAlarmText, floorTexts,
  loadLightCurve, methodText, periodHeadline, plotCaption, relativePercent, selectionRows, signalText, signedPercent,
  sortNotes, stampsHaveVariance, type UsedPoint,
} from './lightcurve';
import type { LightCurvePeriod, LightCurvePoint, LightCurveProduct, LightCurveStatistics } from './types';

// Minimal objects copied from the bundled products (backend/errante_api/curated/lightcurves/*.json, built
// 2026-11-15 after #95). Only the fields under test are real values; the rest is neutral filler.
function point(extra: Partial<LightCurvePoint>): LightCurvePoint {
  return {
    frame_id: 'f', obs_id: 'o', detector: 1, release: 'dr1', mjd: 60000, date: '2023-02-25T00:00:00Z', season: 0,
    wavelength_um: 1, bandwidth_um: 0.02, flux: 1, flux_err: 0.01, bin: 0, rel_mag: 0, rel_mag_err: 0.001,
    zero_point_mag: null, flags: [], excluded: null, ...extra,
  };
}

function statistics(extra: Partial<LightCurveStatistics>): LightCurveStatistics {
  return {
    n: 0, median_mag: null, robust_sigma_mag: null, p95_abs_mag: null, max_abs_mag: null, p5_to_p95_mag: null,
    n_stars: null, n_exposures: null, n_bins: null, excluded: {}, scatter_over_control: null, ...extra,
  };
}

/** R Draconis period (wing, significant). */
const R_DRA_PERIOD: LightCurvePeriod = {
  period_days: 261.87730605532005, delta_chi2: 2319.6288264520686, period_err_formal_days: 4.948478227642994,
  bootstrap_95_days: [240.59702208180983, 276.0241434972408],
  peaks: [[261.87730605532005, 2319.6288264520686], [104.32991515066965, 1798.0834355547693],
    [150.37306907904792, 1229.8464704745425], [79.87328794816352, 1038.981312452796]],
  amplitude_mag: { 6: 0.9551628334163853 }, floor_mag: { 6: 0.0749741674139446 }, n_points: 450,
  baseline_days: 425.9159125579972, period_range_days: [20, 800], false_alarm: 0.001, n_permutations: 999,
  significant: true, caveat: 'Quick sinusoid-grid estimate.',
};

// R Dra, D6 bin 99: first and last used points.
const R_DRA_FIRST = point({ frame_id: '2025W20_2D_0243_1D6', detector: 6, mjd: 60811.956495333, bin: 99,
  rel_mag: -0.40115015989608926, rel_mag_err: 0.0020309121965969615 }) as UsedPoint;
const R_DRA_LAST = point({ frame_id: '2026W24_1A_0125_1D6', detector: 6, mjd: 61199.580380043, bin: 99,
  rel_mag: 0.5330946303145928, rel_mag_err: 0.004237070816538481 }) as UsedPoint;

// RW Aur, D1 bin 0, and one saturated (excluded) exposure.
const RW_AUR_FIRST = point({ frame_id: '2025W36_1A_0233_2D1', mjd: 60920.030804835, flux: 72.3532414084812,
  rel_mag: 0.2640843957557779, rel_mag_err: 0.004712517170102259 }) as UsedPoint;
const RW_AUR_LAST = point({ frame_id: '2026W10_2B_0591_3D1', mjd: 61107.676268921, flux: 117.686191534118,
  rel_mag: -0.2640843957557779, rel_mag_err: 0.003590950460104981 }) as UsedPoint;
const RW_AUR_SATURATED = point({ frame_id: '2025W36_1A_0155_1D1', mjd: 60919.687870495, flux: 66.49712977046472, bin: null, rel_mag: null,
  rel_mag_err: null, flags: ['bad_pixels', 'saturated'], excluded: 'saturated' });

function product(extra: { curve?: Partial<LightCurveProduct['curve']>; provenance?: Partial<LightCurveProduct['provenance']>;
  parameters?: Partial<LightCurveProduct['parameters']>; built_at?: string } = {}): LightCurveProduct {
  return {
    schema_version: '0.7.0', id: 'opaque', target_id: 'rw-aurigae', target_name: 'RW Aurigae',
    built_at: extra.built_at ?? '2026-11-15T16:12:32.867305Z', status: 'ready',
    parameters: {
      ra: 76.95659, dec: 30.40129, method: 'aperture', detectors: [1], collections: ['spherex_dr1', 'spherex_qr3'],
      max_frames: 600, mjd_min: null, mjd_max: 61300, lambda_bin_frac: 0.01, min_bin_span_days: 30, n_comparison: 8,
      period: false, period_range_days: [20, 800], n_bootstrap: 1000, n_permutations: 999, ...extra.parameters,
    },
    curve: {
      ra: 76.95659, dec: 30.40129, method: 'aperture', unit: 'mJy', relative_only: true, lambda_bin_frac: 0.01,
      min_bin_span_days: 30, points: [RW_AUR_FIRST, RW_AUR_LAST, RW_AUR_SATURATED], bins: [], comparisons: [],
      control: {}, summary: {}, excluded: { saturated: 1 }, period: null, notes: [], failures: [], matched_pairs: [],
      ...extra.curve,
    },
    provenance: {
      pipeline_version: '0.1.0', processing_fingerprint: 'd084', collections: ['spherex_dr1', 'spherex_qr3'], sources: [],
      n_found: 56, n_selected: 56, stale_search: false, truncated_search: false, partial: false, notes: [],
      ...extra.provenance,
    },
    synthetic: false,
  };
}

describe('relative brightness', () => {
  it('converts rel_mag to % of the band mean, brighter (negative magnitude) up', () => {
    expect(relativePercent(0)).toBe(0);
    expect(relativePercent(R_DRA_FIRST.rel_mag)).toBeCloseTo(44.70, 2);
    expect(relativePercent(RW_AUR_FIRST.rel_mag)).toBeCloseTo(-21.59, 2);
    expect(relativePercent(-1)).toBeGreaterThan(0);
    expect(signedPercent(relativePercent(R_DRA_FIRST.rel_mag))).toBe('+44.7%');
    expect(signedPercent(relativePercent(RW_AUR_FIRST.rel_mag))).toBe('−21.6%');
    expect(signedPercent(-0.01)).toBe('0.0%');
  });

  it('labels the measured quantity per method', () => {
    expect(methodText('aperture')).toContain('Uncorrected aperture flux (r = 3 px, no aperture correction)');
    expect(methodText('aperture')).toContain('not with catalog fluxes');
    expect(methodText('wing')).toContain('The core is saturated');
  });

  it('shows saturated fluxes as lower limits', () => {
    expect(signalText(RW_AUR_SATURATED)).toBe('≥ 66.497');
    expect(signalText(RW_AUR_FIRST)).toBe('72.353');
    expect(signalText({ flux: null, excluded: 'saturated' })).toBe('—');
  });
});

describe('period evidence', () => {
  it('writes the false-alarm probability as a permutation count', () => {
    expect(falseAlarmText(R_DRA_PERIOD)).toBe('False-alarm probability 1/1000: 0 of 999 visit permutations reached the '
      + 'peak (the smallest value 999 permutations can give).');
    // Earlier products: 100 permutations, false_alarm rounded to 0.0099.
    expect(falseAlarmText({ false_alarm: 0.0099, n_permutations: 100 })).toContain('1/101: 0 of 100 visit permutations');
    expect(falseAlarmText({ false_alarm: 0.006, n_permutations: 999 }))
      .toBe('False-alarm probability 6/1000: 5 of 999 visit permutations reached the peak.');
    expect(falseAlarmText({ false_alarm: 0.0123, n_permutations: 999 })).toBe('False-alarm probability 1.2% (999 visit permutations).');
    expect(falseAlarmText({ false_alarm: null, n_permutations: 999 })).toBeNull();
    expect(falseAlarmText({ false_alarm: 0.5, n_permutations: 0 })).toBeNull();
  });

  it('never presents significance as a confirmed period, nor non-significance as no variability', () => {
    expect(periodHeadline(R_DRA_PERIOD)).toBe('Significant time-correlated variability in the visit-permutation test. '
      + 'Best-fitting cycle: 261.9 days (a candidate, not a confirmed period).');
    expect(periodHeadline({ ...R_DRA_PERIOD, significant: false })).toBe('Not significant in the visit-permutation '
      + 'test: the sinusoid does not fit significantly better than the same visits with shuffled epochs. This does not '
      + 'rule out variability, and the best grid period (261.9 days) is not evidence of a cycle.');
  });

  it('points at the caveat for an untested peak only when the caveat gives the reason', () => {
    // variability.py: the reason goes into the caveat only for the grid-edge / too-few-cycles guard.
    const guarded = { ...R_DRA_PERIOD, significant: null, false_alarm: null, n_permutations: 0,
      caveat: 'Not tested for significance: best period within one grid step of the 800 d search limit. Quick ...' };
    expect(periodHeadline(guarded))
      .toBe('Not tested for significance (the caveat below says why). Best grid period: 261.9 days, not a period estimate.');
    const unrun = { ...guarded, caveat: 'Quick sinusoid-grid estimate.' };
    expect(periodHeadline(unrun)).toBe('Not tested for significance (no visit permutations were run). Best grid period: '
      + '261.9 days, not a period estimate.');
    expect(periodHeadline({ ...unrun, n_permutations: 999 }))
      .toBe('Not tested for significance. Best grid period: 261.9 days, not a period estimate.');
  });

  it('lists the other peaks as possible aliases and keeps the bootstrap interval', () => {
    expect(aliasText(R_DRA_PERIOD)).toBe('Other peaks: 104.3, 150.4 and 79.9 days (possible aliases of the visit '
      + 'cadence, not independent periods).');
    expect(aliasPeaks({ period_days: 100, peaks: [[100, 9], [100, 8], [50, 7]] })).toEqual([50]);
    expect(aliasText({ period_days: 100, peaks: [[100, 9]] })).toBeNull();
    expect(bootstrapText(R_DRA_PERIOD)).toBe('Bootstrap 95% interval: 240.6–276.0 days (conditional on the chosen peak).');
    expect(bootstrapText({ ...R_DRA_PERIOD, significant: null })).toBeNull();
  });
});

describe('uncertainty floor', () => {
  it('reads whether the input stamps carried a VARIANCE plane', () => {
    expect(stampsHaveVariance(['Input stamps: box_px=111; planes=IMAGE,FLAGS.'])).toBe(false);
    expect(stampsHaveVariance(['x', 'Input stamps: box_px=81; planes=IMAGE,VARIANCE,FLAGS.'])).toBe(true);
    expect(stampsHaveVariance(['Native measurement unit: mJy.'])).toBeNull();
  });

  it('uses the comparison-star control for aperture photometry (RW Aur D1)', () => {
    const floor = bandFloor({ method: 'aperture', period: null,
      control: { 1: statistics({ robust_sigma_mag: 0.017990368458767364, n_stars: 5 }) } }, 1, [RW_AUR_FIRST, RW_AUR_LAST],
    true);
    expect(floor.plotMag).toBeCloseTo(0.01799, 5);
    expect(floor.statisticalMag).toBeCloseTo(0.00415, 5);
    expect(floor.statisticalLowerBound).toBe(false);
    expect(floorTexts(floor)).toEqual([
      'Error bars are statistical only (median ±0.0042 mag in this band) and leave out systematics.',
      'Comparison stars measured with the same aperture in the same exposures scatter by ±0.018 mag (D1, robust σ of '
        + '5 comparison stars): an empirical estimate of the per-point floor (pale bars).',
    ]);
  });

  it('uses the fit scatter, not the control, as the wing floor (R Dra D6)', () => {
    const floor = bandFloor({ method: 'wing', period: R_DRA_PERIOD,
      control: { 6: statistics({ robust_sigma_mag: 0.1172503021467437, n_stars: 6 }) } }, 6, [R_DRA_FIRST, R_DRA_LAST],
    false);
    expect(floor.plotMag).toBeCloseTo(0.07497, 5);
    expect(floor.statisticalLowerBound).toBe(true);
    const [stat, fit, control] = floorTexts(floor);
    expect(stat).toBe('Error bars are statistical only (median ±0.0031 mag in this band) and leave out systematics. '
      + 'For the wing they also leave out the wing\'s own photon noise (no VARIANCE plane), so they are a lower bound '
      + 'even on the statistical error.');
    expect(fit).toContain('±0.075 mag (pale bars)');
    expect(fit).toContain('upper bound on the measurement floor');
    expect(control).toContain('±0.117 mag in D6, 6 comparison stars');
    expect(control).toContain('not the floor of this wing measurement');
  });

  it('treats wing bars as a lower bound unless a VARIANCE plane was read', () => {
    const wing = { method: 'wing' as const, period: R_DRA_PERIOD, control: {} };
    expect(bandFloor(wing, 6, [R_DRA_FIRST]).statisticalLowerBound).toBe(true);
    expect(bandFloor(wing, 6, [R_DRA_FIRST], true).statisticalLowerBound).toBe(false);
    expect(floorTexts(bandFloor(wing, 6, [R_DRA_FIRST], true))[0]).not.toContain('photon noise');
  });

  it('captions the plot with what 0% is and which way is brighter', () => {
    const caption = plotCaption({ plotMag: 0.075, statisticalLowerBound: true });
    expect(caption).toContain('0% is this band\'s mean magnitude (the geometric mean of its signals), not a baseline');
    expect(caption).toContain('Positive % = brighter (up); the magnitudes in the product notes use the opposite sign');
    expect(caption).toContain('statistical uncertainty only (for the wing, a lower bound even on that); the pale bars');
    expect(plotCaption(null)).toMatch(/statistical uncertainty only\.$/);
  });

  it('draws no floor when none is published', () => {
    const wing = bandFloor({ method: 'wing', period: null, control: {} }, 6, [point({ rel_mag_err: null })]);
    expect(wing.plotMag).toBeNull();
    expect(floorTexts(wing)).toEqual(['No statistical errors are reported for these points.',
      'No empirical floor is published for D6 without a period fit: the real uncertainty is larger than these bars.']);
    const aperture = bandFloor({ method: 'aperture', period: null, control: {} }, 2, []);
    expect(aperture.plotMag).toBeNull();
    expect(floorTexts(aperture)[1]).toContain('No comparison-star control is published for D2');
  });
});

describe('first-to-last change', () => {
  it('is a difference between two phases for a significant variable (R Dra)', () => {
    const change = bandChange([R_DRA_FIRST, R_DRA_LAST]);
    expect(change?.percent).toBeCloseTo(-57.7, 1);
    expect(changeText(change!, { wing: true, cyclic: true })).toBe('Last vs first measurement in this band (2025-05-16 '
      + 'to 2026-06-08): −57.7% relative wing brightness. With significant time-correlated variability this is a '
      + 'difference between two phases, not a trend.');
  });

  it('is never called a trend without a period (RW Aur)', () => {
    const change = bandChange([RW_AUR_FIRST, RW_AUR_LAST]);
    expect(changeText(change!, { wing: false, cyclic: false })).toBe('Last vs first measurement in this band '
      + '(2025-09-02 to 2026-03-08): +62.7% aperture flux. A difference between two exposures, not a trend fit.');
    expect(bandChange([RW_AUR_FIRST])).toBeNull();
    expect(bandChange([RW_AUR_FIRST, { ...RW_AUR_LAST, mjd: RW_AUR_FIRST.mjd }])).toBeNull();
  });
});

describe('product notes and data selection', () => {
  it('flags wide-survey-only selections', () => {
    expect(collectionsText(['spherex_dr1', 'spherex_qr3']))
      .toBe('spherex_dr1, spherex_qr3 · wide survey only (deep collections not included)');
    expect(collectionsText(['spherex_dr1', 'spherex_dr1_deep'])).toBe('spherex_dr1, spherex_dr1_deep');
    expect(collectionsText([])).toBe('Not recorded.');
  });

  it('keeps every caveat visible and moves only technical notes aside', () => {
    const notes = sortNotes([
      'Offline FITS measurement using WS3 variability methods; not a new R05 validation.',
      'Search snapshot query date: 2026-11-14T19:33:00.',
      'Effective package versions: errante=0.1.0, numpy=2.5.4.',
      'RW Aur A+BC is unresolved (about 1.5 arcsec separation); this is the blended system, not A alone.',
      'Archive selection: 56 selected of 56 found.',
      'Unknown future caveat.',
    ], [
      'Saturated exposures by season: S0 7/19, S1 14/19, S2 16/18.',
      'Offline FITS measurement using WS3 variability methods; not a new R05 validation.',
    ]);
    expect(notes.limits).toEqual([
      'Offline FITS measurement using WS3 variability methods; not a new R05 validation.',
      'RW Aur A+BC is unresolved (about 1.5 arcsec separation); this is the blended system, not A alone.',
      'Unknown future caveat.',
      'Saturated exposures by season: S0 7/19, S1 14/19, S2 16/18.',
    ]);
    expect(notes.selection).toEqual(['Search snapshot query date: 2026-11-14T19:33:00.']);
    expect(notes.technical).toEqual(['Effective package versions: errante=0.1.0, numpy=2.5.4.',
      'Archive selection: 56 selected of 56 found.']);
  });

  it('summarises the selection of the RW Aur product', () => {
    expect(selectionRows(product())).toEqual([
      { label: 'Collections', value: 'spherex_dr1, spherex_qr3 · wide survey only (deep collections not included)' },
      { label: 'Detectors', value: 'D1' },
      { label: 'Archive search', value: '56 selected of 56 found · not answered from a stale cache or snapshot' },
      { label: 'Date filter', value: 'Up to 2026-09-17 (MJD 61300)' },
      { label: 'Exposures measured', value: '3, 2025-09-01 to 2026-03-08 UTC; 2 used in the light curve' },
      { label: 'Inputs not measured', value: 'None' },
      { label: 'Product built', value: '2026-11-15 16:12 UTC · pipeline 0.1.0' },
    ]);
  });

  it('reports cached, truncated and partial searches and groups failures', () => {
    const rows = selectionRows(product({
      parameters: { detectors: [], mjd_min: 60800, mjd_max: null },
      provenance: { n_found: null, n_selected: 539, stale_search: true, truncated_search: true, partial: true },
      curve: { points: [], failures: [{ frame_id: '2025W48_2A_0693_2D5', reason: 'no_overlap' },
        { frame_id: null, reason: 'download_failed' }, { frame_id: 'x', reason: 'no_overlap' }] },
    }));
    const value = (label: string) => rows.find((row) => row.label === label)?.value;
    expect(value('Detectors')).toBe('All');
    expect(value('Archive search')).toBe('539 selected of unknown found · answered from a stale cache or snapshot (not '
      + 'by itself missing data) · selection truncated · partial: the selection or the reading may be incomplete (see '
      + 'Inputs not measured and the notes)');
    expect(value('Date filter')).toBe('From 2025-05-05 (MJD 60800)');
    expect(value('Exposures measured')).toBe('None');
    expect(value('Inputs not measured')).toBe('3 (no overlap: 2, download failed: 1)');
  });
});

describe('loading', () => {
  it('treats 404 as missing and never returns a synthetic product', async () => {
    const real = product();
    expect(await loadLightCurve({ getLightCurve: async () => real }, 'rw-aurigae')).toBe(real);
    expect(await loadLightCurve({ getLightCurve: async () => { throw new ApiError('Not found', 404); } }, 'x')).toBe('missing');
    const synthetic = { ...real, synthetic: true } as unknown as LightCurveProduct;
    expect(await loadLightCurve({ getLightCurve: async () => synthetic }, 'x')).toBe('missing');
    await expect(loadLightCurve({ getLightCurve: async () => { throw new ApiError('Boom', 500); } }, 'x'))
      .rejects.toThrow('Boom');
  });
});

// The panel itself, rendered from the products the backend ships (and the static export copies byte for byte).
const BUNDLED: Record<string, LightCurveProduct> = Object.fromEntries(Object.entries(
  import.meta.glob<LightCurveProduct>('../../../backend/errante_api/curated/lightcurves/*.json', {
    eager: true, import: 'default',
  }),
).map(([path, product]) => [path.slice(path.lastIndexOf('/') + 1, -'.json'.length), product]));

function renderProduct(id: string) {
  const product = BUNDLED[id];
  expect(product, `bundled light curve ${id}`).toBeDefined();
  const html = renderToStaticMarkup(createElement(LightCurveProductView, { product }));
  const text = html.replace(/<[^>]+>/g, ' ').replace(/&#x27;/g, "'").replace(/&quot;/g, '"').replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>').replace(/&amp;/g, '&').replace(/\s+/g, ' ');
  return { html, text };
}

const count = (html: string, tag: string) => html.split(`<${tag} `).length - 1;

describe('light-curve panel', () => {
  it('shows R Draconis with its limits, selection, uncertainty floor and period wording', () => {
    const { html, text } = renderProduct('r-draconis');
    expect(html).toMatch(/<details open="" class="lc-notes"><summary>Limits stated by this product \(\d+\)/);
    for (const expected of [
      'Offline FITS measurement using WS3 variability methods; not a new R05 validation.',
      'R Draconis: wide survey only (DR1+QR3)',
      'spherex_dr1, spherex_qr3 · wide survey only (deep collections not included)',
      'not answered from a stale cache or snapshot',
      'Relative brightness of the unsaturated PSF wing',
      "0% is this band's mean magnitude (the geometric mean of its signals)",
      'Positive % = brighter (up); the magnitudes in the product notes use the opposite sign (negative = brighter).',
      'so they are a lower bound even on the statistical error.',
      'It is an upper bound on the measurement floor',
      'not the floor of this wing measurement',
      'With significant time-correlated variability this is a difference between two phases, not a trend.',
      'vs band mean magnitude (%)',
      'Significant time-correlated variability in the visit-permutation test. Best-fitting cycle: 261.9 days (a '
        + 'candidate, not a confirmed period).',
      'False-alarm probability 1/1000: 0 of 999 visit permutations reached the peak',
      'Bootstrap 95% interval: 240.6–276.0 days',
      'Other peaks: 104.3, 150.4 and 79.9 days (possible aliases of the visit cadence',
    ]) expect(text).toContain(expected);
    // One pale floor band and one statistical bar per plotted point of the default band (D6, 10 exposures).
    expect(count(html, 'circle')).toBe(10);
    expect(count(html, 'rect')).toBe(10);
    expect(count(html, 'line')).toBe(10);
    expect(text).not.toMatch(/NaN|undefined|live API mode/);
  });

  it('shows RW Aurigae with the blend, the saturation lower limits and the comparison-star floor', () => {
    const { html, text } = renderProduct('rw-aurigae');
    expect(html).toMatch(/<details open="" class="lc-notes"><summary>Limits stated by this product \(\d+\)/);
    for (const expected of [
      'RW Aur A+BC is unresolved',
      'Saturated exposures by season:',
      'Uncorrected aperture flux (r = 3 px, no aperture correction), background-subtracted',
      'Comparison stars measured with the same aperture in the same exposures scatter by ±0.018 mag (D1',
      'A difference between two exposures, not a trend fit.',
      'No period estimate is available for this product.',
      'Saturated fluxes are lower limits (shown as ≥)',
      '≥ 66.497',
      'Collections spherex_dr1, spherex_qr3 · wide survey only (deep collections not included)',
    ]) expect(text).toContain(expected);
    expect(text).not.toContain('photon noise');
    expect(count(html, 'circle')).toBe(2);
    expect(count(html, 'rect')).toBe(2);
    expect(text).not.toMatch(/NaN|undefined|live API mode/);
  });

  it('no longer asks for live API mode in a static build', () => {
    const html = renderToStaticMarkup(createElement(LightCurvePanel, { targetId: 'r-draconis' }));
    expect(html).toContain('<summary>Light curve</summary>');
    expect(html).not.toContain('live API mode');
  });
});
