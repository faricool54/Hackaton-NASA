import { describe, expect, it } from 'vitest';
import type { Body, Fact, Orbit, SystemModel, Variability } from '../api/types';
import {
  formatOrbitPeriod,
  formatPeriod,
  isNonFittedOrbit,
  modelValuesUnverified,
  twoSigFigs,
  variabilityAnimationNote,
  variabilityText,
} from './bodyFormat';

const orbit = (o: Partial<Orbit>): Orbit => ({
  parent: 'a',
  semi_major_axis_au: 1,
  period_days: 365.25,
  eccentricity: 0,
  inclination_deg: 0,
  ascending_node_deg: 0,
  arg_periapsis_deg: 0,
  mean_anomaly_deg: 0,
  epoch_mjd: null,
  quality: 'fitted',
  note: null,
  ...o,
});

const fact = (verified: boolean): Fact => ({ label: 'x', value: '1', unit: null, source: null, verified });

const body = (facts: Fact[]): Body => ({
  id: 'x',
  name: 'x',
  kind: 'star',
  description: '',
  radius_km: null,
  mass_kg: null,
  teff_k: null,
  spectral_type: null,
  rotation_period_hours: null,
  orbit: null,
  variability: null,
  appearance: { model: 'star', color_hex: null, mesh_url: null, texture_url: null },
  facts,
  candidate_id: null,
});

const system = (bodies: Body[]): SystemModel =>
  ({ id: 's', name: 's', bodies, provenance: { synthetic: false } }) as unknown as SystemModel;

describe('twoSigFigs / formatPeriod', () => {
  it('rounds to 2 significant figures', () => {
    expect(twoSigFigs(59648.3)).toBe('60,000');
    expect(twoSigFigs(274.1)).toBe('270');
    expect(twoSigFigs(1865)).toBe('1,900');
    expect(twoSigFigs(2.34)).toBe('2.3');
  });

  it('keeps precise periods for fitted orbits', () => {
    expect(formatPeriod(2.34)).toBe('2.3 days');
    expect(formatPeriod(1)).toBe('24.0 hours');
    expect(formatPeriod(4331.1)).toBe('11.9 years');
  });

  it('marks approximate periods with ~ and 2 significant figures', () => {
    expect(formatPeriod(21786616, true)).toBe('~60,000 years'); // Eps Indi Ba, assumed orbit
    expect(formatPeriod(100128.8, true)).toBe('~270 years');
    expect(formatPeriod(245.6, true)).toBe('~250 days');
    expect(formatPeriod(0.5, true)).toBe('~12 hours');
  });

  it('rounds only orbits that are not fitted', () => {
    expect(isNonFittedOrbit(orbit({ quality: 'fitted' }))).toBe(false);
    expect(isNonFittedOrbit(orbit({ quality: undefined }))).toBe(false); // older products: fitted
    expect(isNonFittedOrbit(orbit({ quality: 'assumed' }))).toBe(true);
    expect(isNonFittedOrbit(orbit({ quality: 'hypothetical' }))).toBe(true);
    expect(formatOrbitPeriod(orbit({ period_days: 21786616, quality: 'assumed' }))).toBe('~60,000 years');
    expect(formatOrbitPeriod(orbit({ period_days: 60226.9, quality: 'fitted' }))).toBe('164.9 years');
    expect(formatOrbitPeriod(orbit({ period_days: 60226.9, quality: undefined }))).toBe('164.9 years');
  });
});

describe('variabilityText', () => {
  const v = (x: Partial<Variability>): Variability => ({
    kind: 'pulsation',
    period_days: null,
    amplitude_mag: null,
    band: null,
    ...x,
  });

  it('periodic: full amplitude peak-to-peak with band (R Dra, V range 6.7-13.2 mag)', () => {
    expect(variabilityText(v({ kind: 'pulsation', period_days: 245.6, amplitude_mag: 6.5, band: 'V' }))).toBe(
      'pulsation, every 245.6 days, 6.5 mag peak-to-peak in V band',
    );
  });

  it('irregular: dims by up to the full amplitude (RW Aur A, ~2 mag dimming)', () => {
    expect(variabilityText(v({ kind: 'irregular', amplitude_mag: 2, band: 'V' }))).toBe(
      'irregular, dims by up to 2 mag in V band',
    );
  });

  it('eclipse and accretion use "dims by up to"; rotation is peak-to-peak', () => {
    expect(variabilityText(v({ kind: 'eclipse', period_days: 3, amplitude_mag: 0.8, band: 'W1' }))).toBe(
      'eclipse, every 3.0 days, dims by up to 0.8 mag in W1 band',
    );
    expect(variabilityText(v({ kind: 'accretion', amplitude_mag: 1.25, band: 'K' }))).toBe(
      'accretion, dims by up to 1.3 mag in K band',
    );
    expect(variabilityText(v({ kind: 'rotation', period_days: 0.5, amplitude_mag: 0.1, band: 'J' }))).toBe(
      'rotation, every 12.0 hours, 0.1 mag peak-to-peak in J band',
    );
  });

  it('omits missing band / amplitude and does not double "band"', () => {
    expect(variabilityText(v({ kind: 'irregular', amplitude_mag: 2 }))).toBe('irregular, dims by up to 2 mag');
    expect(variabilityText(v({ kind: 'pulsation', amplitude_mag: 1, band: 'V band' }))).toBe(
      'pulsation, 1 mag peak-to-peak in V band',
    );
    expect(variabilityText(v({ kind: 'irregular' }))).toBe('irregular');
  });

  it('describes how the scene animates it (sinusoid only when periodic)', () => {
    expect(variabilityAnimationNote(v({ period_days: 245.6, amplitude_mag: 6.5 }))).toMatch(/sinusoid/);
    expect(variabilityAnimationNote(v({ kind: 'irregular', amplitude_mag: 2 }))).toMatch(/Not animated/);
    expect(variabilityAnimationNote(v({ kind: 'irregular' }))).toBeNull();
  });
});

describe('modelValuesUnverified', () => {
  it('is false only when there are facts and all are verified', () => {
    expect(modelValuesUnverified(system([body([fact(true)]), body([fact(true)])]))).toBe(false);
    expect(modelValuesUnverified(system([body([fact(true)]), body([fact(false)])]))).toBe(true);
    expect(modelValuesUnverified(system([body([])]))).toBe(true); // no source at all
  });
});
