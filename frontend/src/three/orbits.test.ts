import { describe, expect, it } from 'vitest';
import type { Body, Orbit } from '../api/types';
import { compressDistance, displayRadius, kelvinToRgb } from './appearance';
import { J2000_MJD, orbitalPosition, solveKepler, topoOrder, variabilityFactor } from './orbits';

const orbit = (o: Partial<Orbit>): Orbit => ({
  parent: 'sun',
  semi_major_axis_au: 1,
  period_days: 365.25,
  eccentricity: 0,
  inclination_deg: 0,
  ascending_node_deg: 0,
  arg_periapsis_deg: 0,
  mean_anomaly_deg: 0,
  epoch_mjd: null,
  ...o,
});

const body = (b: Partial<Body>): Body => ({
  id: 'x',
  name: 'x',
  kind: 'planet',
  description: '',
  radius_km: null,
  mass_kg: null,
  teff_k: null,
  spectral_type: null,
  rotation_period_hours: null,
  orbit: null,
  variability: null,
  appearance: { model: 'rocky', color_hex: null, mesh_url: null, texture_url: null },
  facts: [],
  candidate_id: null,
  ...b,
});

describe('orbits', () => {
  it('solves Kepler for circular and eccentric orbits', () => {
    expect(solveKepler(1.2, 0)).toBeCloseTo(1.2, 10);
    const E = solveKepler(1.0, 0.9);
    expect(E - 0.9 * Math.sin(E)).toBeCloseTo(1.0, 9);
  });

  it('a circular orbit returns to its start after one period and keeps its radius', () => {
    const o = orbit({ semi_major_axis_au: 2 });
    const p0 = orbitalPosition(o, J2000_MJD);
    const pq = orbitalPosition(o, J2000_MJD + 365.25 / 4);
    const p1 = orbitalPosition(o, J2000_MJD + 365.25);
    expect(p0[0]).toBeCloseTo(2, 9);
    expect(Math.hypot(...pq)).toBeCloseTo(2, 9);
    expect(pq[1]).toBeCloseTo(2, 9); // quarter turn counter-clockwise
    expect(p1[0]).toBeCloseTo(p0[0], 6);
  });

  it('periapsis distance is a(1-e) and inclination lifts the orbit out of the plane', () => {
    const p = orbitalPosition(orbit({ semi_major_axis_au: 3, eccentricity: 0.5 }), J2000_MJD);
    expect(Math.hypot(...p)).toBeCloseTo(1.5, 9);
    const q = orbitalPosition(orbit({ inclination_deg: 90 }), J2000_MJD + 365.25 / 4);
    expect(q[2]).toBeCloseTo(1, 9);
  });

  it('orders parents before children', () => {
    const order = topoOrder([
      body({ id: 'moon', orbit: orbit({ parent: 'planet' }) }),
      body({ id: 'planet', orbit: orbit({ parent: 'star' }) }),
      body({ id: 'star' }),
    ]).map((b) => b.id);
    expect(order).toEqual(['star', 'planet', 'moon']);
  });

  it('variability is 1 for non-variables and spans the amplitude for periodic ones', () => {
    expect(variabilityFactor(body({}), J2000_MJD)).toBe(1);
    const v = body({ variability: { kind: 'pulsation', period_days: 100, amplitude_mag: 5, band: 'V' } });
    const max = variabilityFactor(v, J2000_MJD + 75); // sin = -1 → brightest
    const min = variabilityFactor(v, J2000_MJD + 25);
    expect(max / min).toBeCloseTo(100, 6); // 5 mag = factor 100
  });
});

describe('appearance', () => {
  it('maps temperature to plausible colors', () => {
    const [r1, , b1] = kelvinToRgb(3000);
    const [r2, , b2] = kelvinToRgb(10000);
    expect(r1).toBeGreaterThan(b1); // cool stars are red
    expect(b2).toBeGreaterThanOrEqual(r2 - 30); // hot stars are white/blue
  });

  it('compresses distances monotonically and keeps radii visible', () => {
    expect(compressDistance(0.02, 0.02)).toBeLessThan(compressDistance(28, 0.02));
    expect(compressDistance(1460, 0.02)).toBeLessThan(60);
    expect(displayRadius(body({ radius_km: 5 }))).toBeGreaterThanOrEqual(0.12);
    expect(displayRadius(body({ kind: 'star', radius_km: 695700 }))).toBeGreaterThan(
      displayRadius(body({ radius_km: 6371 })),
    );
  });
});
