import { afterEach, describe, expect, it, vi } from 'vitest';
import { createClient } from './client';
import { comparisonSelection, comparisonTitle, plotMeasurements, SPECTRUM_SOURCE_LABELS, spectrumCaveat, spectrumSummary } from './science';
import type { ComparisonImage, Field, SpectralMeasurement } from './types';

afterEach(() => vi.unstubAllGlobals());

describe('scientific API boundary', () => {
  it('sends explicit spectrum source/selection and comparison input IDs', async () => {
    const fetch = vi.fn().mockImplementation(async () => new Response('{}', {status: 200}));
    vi.stubGlobal('fetch', fetch);
    const api = createClient({mode:'api', apiBase:'http://science', staticBase:'/data/demo/'});
    const spectrum = {ra: 10, dec: 20, source:'l2_exposures' as const, detectors:[2], max_frames:24};
    await api.getSpectrum(spectrum);
    expect(fetch.mock.calls[0][0]).toBe('http://science/api/spectra');
    expect(JSON.parse(fetch.mock.calls[0][1].body)).toEqual(spectrum);
    await api.getComparisons('a/b', {detectors:[2], frame_ids:['first','last']});
    expect(fetch.mock.calls[1][0]).toBe('http://science/api/fields/a%2Fb/comparisons');
    expect(JSON.parse(fetch.mock.calls[1][1].body).frame_ids).toEqual(['first','last']);
    expect(api.analysisImageUrl('analyses/id/compare/x.png')).toBe('http://science/data/analyses/id/compare/x.png');
  });
  it('refuses scientific requests in static mode', async () => {
    const fetch = vi.fn(); vi.stubGlobal('fetch', fetch);
    const api = createClient({mode:'static', apiBase:'http://science', staticBase:'/data/demo/'});
    await expect(api.getSpectrum({ra:10,dec:20})).rejects.toThrow('live API');
    await expect(api.getComparisons('field',{})).rejects.toThrow('live API');
    expect(fetch).not.toHaveBeenCalled();
  });
});

describe('plotting and comparisons', () => {
  it('keeps measured negative flux and excludes missing/flagged/nonfinite measurements', () => {
    const point = {id:'one', flux:-2, wavelength_um:1, usable:true} as SpectralMeasurement;
    const input = [point, {...point, id:'invalid', usable:false}, {...point, flux:null},
      {...point, wavelength_um:null}, {...point, flux:NaN}];
    expect(plotMeasurements(input)).toEqual([point]);
    expect(input).toHaveLength(5);
  });
  const epoch = (date: string) => Date.parse(date+'T00:00:00Z')/86400000+40587;
  const field = {frames:[
    {id:'early-d2',detector:2,mjd:epoch('2026-01-01')},
    {id:'late-d2',detector:2,mjd:epoch('2026-01-02')+.99},
    {id:'other',detector:1,mjd:epoch('2026-01-02')},
  ]} as Field;
  it('uses whole UTC days and keeps detector selection', () => {
    expect(comparisonSelection(field,2,'2026-01-01','2026-01-02')).toEqual(['early-d2','late-d2']);
    expect(comparisonSelection(field,0,'2026-01-02','2026-01-02')).toEqual(['late-d2','other']);
  });
  it('rejects insufficient or unbounded requests instead of silently dropping frames', () => {
    expect(() => comparisonSelection(field,1,'','')).toThrow('at least two');
    expect(() => comparisonSelection(field,2,'2026-02-01','2026-01-01')).toThrow('ordered');
    expect(() => comparisonSelection({frames:Array.from({length:61},(_,i)=>({id:String(i),detector:2,mjd:i}))} as Field,
      2,'','')).toThrow('at most 60');
  });
  it('labels the actual difference direction and applied scale', () => {
    expect(comparisonTitle({kind:'scaled_difference', detector:2, earlier:'early', later:'late', flux_scale:1.2} as ComparisonImage))
      .toBe('D2 · late − 1.200 × early');
    expect(comparisonTitle({kind:'weighted_mean',detector:2,season:1} as ComparisonImage)).toContain('weighted mean');
  });
});

describe('spectrum panel texts (FE-8)', () => {
  it('keeps both honesty legends and the summary wording', () => {
    expect(spectrumCaveat('dr1_cube')).toMatch(/^Static surface brightness \(MJy\/sr\)/);
    expect(spectrumCaveat('l2_exposures')).toContain('do not interpret a mixed-epoch curve as a simultaneous spectrum');
    expect(SPECTRUM_SOURCE_LABELS.dr1_cube).toBe('DR1 cube · static quick look');
    const point = { usable: true } as SpectralMeasurement;
    expect(spectrumSummary({ points: [point, { ...point, usable: false }], failures: [] }))
      .toBe('1 usable / 2 measured points · 0 failed inputs');
  });
});
