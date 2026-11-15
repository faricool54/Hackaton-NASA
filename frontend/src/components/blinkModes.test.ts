import { describe, expect, it } from 'vitest';
import type { Composite, CompositeChannel, CompositeColor, CompositeMode } from '../api/types';
import { channelLegend, compositesForMode, effectiveMode, isModeAvailable, modeHints, modeTitle, seasonRange } from './blinkModes';

function channel(color: CompositeColor, detector: number | null, wavelength_um: number | null): CompositeChannel {
  return { color, detector, wavelength_um, wavelength_min_um: wavelength_um, wavelength_max_um: wavelength_um, frame_ids: [] };
}

function composite(mode: CompositeMode, season: number, mjd_min = 61000 + season * 180, mjd_max = mjd_min + 10): Composite {
  return {
    id: `${mode}_S${season}`,
    mode,
    season,
    mjd_min,
    mjd_max,
    image: `color/${mode}_S${season}.png`,
    channels: [channel('red', 6, 4.5973), channel('green', 3, 1.8095), channel('blue', 1, 0.9403)],
    notes: [],
  };
}

describe('compositesForMode', () => {
  it('keeps one mode and sorts it by season', () => {
    const all = [composite('detectors', 2), composite('jhk', 0), composite('detectors', 0), composite('detectors', 1)];
    expect(compositesForMode(all, 'detectors').map((c) => c.id)).toEqual(['detectors_S0', 'detectors_S1', 'detectors_S2']);
    expect(compositesForMode(all, 'jhk').map((c) => c.id)).toEqual(['jhk_S0']);
  });

  it('treats products older than contract 0.3.1 (no composites) as empty', () => {
    expect(compositesForMode(undefined, 'jhk')).toEqual([]);
  });
});

describe('isModeAvailable / modeTitle', () => {
  const onlyDetectors = [composite('detectors', 0), composite('detectors', 1)];

  it('always offers B/W', () => {
    expect(isModeAvailable('bw', undefined)).toBe(true);
    expect(modeTitle('bw', undefined)).toMatch(/grayscale/);
  });

  it('describes an available color mode with its number of seasons', () => {
    expect(isModeAvailable('detectors', onlyDetectors)).toBe(true);
    expect(modeTitle('detectors', onlyDetectors)).toMatch(/^False color.*\(2 seasons\)$/);
  });

  it('explains why a color mode is disabled', () => {
    expect(isModeAvailable('jhk', onlyDetectors)).toBe(false);
    expect(modeTitle('jhk', onlyDetectors)).toMatch(/^Not available: .*J, H and Ks/);
    expect(isModeAvailable('detectors', undefined)).toBe(false);
    expect(modeTitle('detectors', [])).toBe('Not available: no false-color composites were built for this field');
  });
});

describe('channelLegend', () => {
  it('lists red, green and blue with wavelength and detector', () => {
    expect(channelLegend(composite('detectors', 0))).toBe('R 4.60 µm (D6) · G 1.81 µm (D3) · B 0.94 µm (D1)');
  });

  it('does not invent missing metadata', () => {
    const base = composite('jhk', 0);
    const c: Composite = { ...base, channels: [channel('red', null, null), base.channels[1], base.channels[2]] };
    expect(channelLegend(c)).toBe('R λ n/a (mixed detectors) · G 1.81 µm (D3) · B 0.94 µm (D1)');
  });
});

describe('seasonRange', () => {
  it('shows the dates of the first and last input exposure', () => {
    expect(seasonRange(composite('detectors', 0, 60905.8569, 60923.1104))).toBe('2025-08-18 – 2025-09-05');
  });

  it('collapses a single-day season', () => {
    expect(seasonRange(composite('jhk', 0, 61000.2, 61000.6))).toBe('2025-11-21');
  });
});

describe('effectiveMode / modeHints', () => {
  const onlyDetectors = [composite('detectors', 0), composite('detectors', 1)];

  it('falls back to B/W when the field has no composites of the chosen mode', () => {
    expect(effectiveMode('jhk', onlyDetectors)).toBe('bw');
    expect(effectiveMode('detectors', onlyDetectors)).toBe('detectors');
    expect(effectiveMode('detectors', undefined)).toBe('bw');
  });

  it('describes the shown mode first, then says why the other modes are off', () => {
    const hints = modeHints('jhk', onlyDetectors);
    expect(hints[0]).toMatch(/grayscale/);
    expect(hints.slice(1)).toEqual(['Color · J/H/K: not available, no season of this field has exposures near all of J, H and Ks.']);
    expect(modeHints('detectors', onlyDetectors)).toEqual([
      'False color, full range: three SPHEREx detectors from 0.75 to 5.0 µm, one image per season (2 seasons).',
      'Color · J/H/K: not available, no season of this field has exposures near all of J, H and Ks.',
    ]);
  });

  it('lists both color modes as unavailable for products without composites', () => {
    expect(modeHints('bw', undefined)).toHaveLength(3);
  });
});
