import { describe, expect, it } from 'vitest';
import type { Appearance, AppearanceModel, Body, Orbit, SystemModel } from '../api/types';
import { displayRadius } from './appearance';
import { orbitalPosition, variabilityFactor } from './orbits';
import {
  advanceModelTime,
  apoapsisAu,
  capRadii,
  childrenByParent,
  distanceMapper,
  fitDistance,
  focusDistance,
  linearScale,
  MAX_FRAME_SECONDS,
  maxPulsationScale,
  MIN_VISIBLE_RADIUS,
  nonFittedOrbits,
  periapsisAu,
  referenceAu,
  tighterHalfFov,
  type DistanceMode,
} from './sceneLayout';

// Every demo system shipped with the site (the same JSON the pipeline writes).
const SYSTEMS = Object.values(
  import.meta.glob<SystemModel>('../../../data/demo/systems/*.json', { eager: true, import: 'default' }),
);

const orbit = (o: Partial<Orbit>): Orbit => ({
  parent: 'star',
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

const look = (model: AppearanceModel): Appearance => ({ model, color_hex: null, mesh_url: null, texture_url: null });

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

/** Radii for both modes exactly as SystemScene builds them (linear starts from the compressed caps). */
function layout(bodies: Body[]) {
  const refAu = referenceAu(bodies);
  const scale = linearScale(bodies);
  const base = new Map(bodies.map((b) => [b.id, displayRadius(b)]));
  const compressed = capRadii(bodies, 'compressed', base, distanceMapper('compressed', refAu, scale));
  const linear = capRadii(bodies, 'linear', compressed, distanceMapper('linear', refAu, scale));
  return {
    radii: { compressed, linear } as Record<DistanceMode, Map<string, number>>,
    map: (mode: DistanceMode) => distanceMapper(mode, refAu, scale),
  };
}

/** Smallest surface-to-surface clearance (scene units) over all parent/child pairs, at max pulsation size. */
function clearances(bodies: Body[], mode: DistanceMode) {
  const { radii, map } = layout(bodies);
  const byId = new Map(bodies.map((b) => [b.id, b]));
  const out: { pair: string; clearance: number }[] = [];
  for (const [parentId, kids] of childrenByParent(bodies)) {
    const rP = radii[mode].get(parentId)! * maxPulsationScale(byId.get(parentId)!);
    for (const k of kids) {
      const rC = radii[mode].get(k.id)! * maxPulsationScale(k);
      out.push({ pair: `${parentId}/${k.id}`, clearance: map(mode)(periapsisAu(k.orbit!)) - rP - rC });
    }
  }
  return out;
}

describe('radius caps: bodies never pass through each other', () => {
  it('loads every demo system', () => {
    expect(SYSTEMS.length).toBeGreaterThanOrEqual(6);
  });

  for (const mode of ['compressed', 'linear'] as const) {
    it(`parentRadius + childRadius < periapsis for every pair in every demo system (${mode})`, () => {
      let pairs = 0;
      for (const system of SYSTEMS) {
        for (const { pair, clearance } of clearances(system.bodies, mode)) {
          pairs++;
          expect(clearance, `${system.id} ${pair}`).toBeGreaterThan(0);
        }
      }
      expect(pairs).toBeGreaterThan(5); // the check really ran
    });
  }

  it('a tight binary far from its star (Eps Indi Ba/Bb geometry) does not overlap in true proportions', () => {
    const dwarf: Partial<Body> = { kind: 'brown_dwarf', radius_km: 64343, appearance: look('brown_dwarf') };
    const bodies = [
      body({ id: 'a', kind: 'star', radius_km: 493947, appearance: look('star') }),
      body({ id: 'ab', radius_km: 71492, orbit: orbit({ parent: 'a', semi_major_axis_au: 28, eccentricity: 0.4 }) }),
      body({ id: 'ba', ...dwarf, orbit: orbit({ parent: 'a', semi_major_axis_au: 1460 }) }),
      body({ id: 'bb', ...dwarf, orbit: orbit({ parent: 'ba', semi_major_axis_au: 2.403, eccentricity: 0.54 }) }),
    ];
    const { radii, map } = layout(bodies);
    const peri = map('linear')(periapsisAu(bodies[3].orbit!));
    expect(peri).toBeLessThan(2 * MIN_VISIBLE_RADIUS.linear); // the old floors alone would overlap
    expect(radii.linear.get('ba')! + radii.linear.get('bb')!).toBeLessThan(peri);
    // Ba and Bb are the same size: shrinking to fit must keep that ratio (not 0.6 vs 0.4 of the room).
    for (const mode of ['compressed', 'linear'] as const) {
      const ratio = radii[mode].get('ba')! / radii[mode].get('bb')!;
      expect(ratio, mode).toBeGreaterThan(0.8);
      expect(ratio, mode).toBeLessThan(1.25);
    }
    for (const mode of ['compressed', 'linear'] as const) {
      for (const { pair, clearance } of clearances(bodies, mode)) {
        expect(clearance, `${mode} ${pair}`).toBeGreaterThan(0);
      }
    }
  });

  it('keeps the visibility floor where there is room', () => {
    const bodies = [
      body({ id: 'sun', kind: 'star', radius_km: 695700, appearance: look('star') }),
      body({ id: 'earth', radius_km: 6371, orbit: orbit({ parent: 'sun', eccentricity: 0.017 }) }),
      body({ id: 'rock', radius_km: 5, orbit: orbit({ parent: 'sun', semi_major_axis_au: 3.8, eccentricity: 0.05 }) }),
      body({ id: 'far', radius_km: 150, orbit: orbit({ parent: 'sun', semi_major_axis_au: 42.2 }) }),
    ];
    const { radii } = layout(bodies);
    for (const b of bodies) {
      expect(radii.compressed.get(b.id)!, b.id).toBeGreaterThanOrEqual(MIN_VISIBLE_RADIUS.compressed - 1e-12);
      expect(radii.linear.get(b.id)!, b.id).toBeGreaterThanOrEqual(MIN_VISIBLE_RADIUS.linear - 1e-12);
    }
  });

  it('an eccentric inner orbit does not pass through a big star in compressed mode', () => {
    const bodies = [
      body({ id: 'star', kind: 'star', radius_km: 5e7, appearance: look('star') }),
      body({ id: 'p', orbit: orbit({ semi_major_axis_au: 1, eccentricity: 0.95 }) }),
      body({ id: 'q', radius_km: 70000, orbit: orbit({ semi_major_axis_au: 1.02, eccentricity: 0.9 }) }),
    ];
    expect(referenceAu(bodies)).toBeCloseTo(0.05, 12); // smallest periapsis, not the smallest a
    for (const mode of ['compressed', 'linear'] as const) {
      for (const { pair, clearance } of clearances(bodies, mode)) {
        expect(clearance, `${mode} ${pair}`).toBeGreaterThan(0);
      }
    }
  });

  it('a pulsating parent keeps clear of its companion at its largest size', () => {
    const bodies = [
      body({
        id: 'star',
        kind: 'star',
        radius_km: 2e8,
        appearance: look('star'),
        variability: { kind: 'pulsation', period_days: 300, amplitude_mag: 8, band: 'V' },
      }),
      body({ id: 'c', orbit: orbit({ semi_major_axis_au: 0.5 }) }),
    ];
    expect(maxPulsationScale(bodies[0])).toBeGreaterThan(1.3);
    for (const mode of ['compressed', 'linear'] as const) {
      for (const { clearance } of clearances(bodies, mode)) expect(clearance).toBeGreaterThan(0);
    }
  });

  it('only pulsates bodies the scene animates', () => {
    expect(maxPulsationScale(body({}))).toBe(1);
    const irregular = body({ variability: { kind: 'irregular', period_days: null, amplitude_mag: 2, band: 'V' } });
    expect(maxPulsationScale(irregular)).toBe(1);
  });
});

describe('camera framing', () => {
  /** NDC of a world point for a camera at (0, 0.55d, d) looking at the origin (three.js frame, y-up). */
  function project(p: [number, number, number], d: number, fovDeg: number, aspect: number): [number, number] {
    const cam = [0, 0.55 * d, d];
    const len = Math.hypot(...cam);
    const fwd = cam.map((c) => -c / len); // camera has no yaw, so right = +x
    const up = [0, -fwd[2], fwd[1]]; // right × fwd
    const v = p.map((c, i) => c - cam[i]);
    const z = v[0] * fwd[0] + v[1] * fwd[1] + v[2] * fwd[2];
    const tanV = Math.tan((fovDeg / 2) * (Math.PI / 180));
    return [v[0] / z / (tanV * aspect), (v[1] * up[1] + v[2] * up[2]) / z / tanV];
  }

  it('shows a flat system of any extent whole on portrait, square and landscape stages', () => {
    for (const aspect of [0.3, 0.46, 0.6, 1, 1.33, 1.78, 2.5]) {
      const extent = 30;
      const d = fitDistance(extent, 1, 50, aspect);
      for (let i = 0; i < 360; i++) {
        const t = (i / 360) * 2 * Math.PI;
        const [x, y] = project([extent * Math.cos(t), 0, extent * Math.sin(t)], d, 50, aspect);
        expect(Math.abs(x), `aspect ${aspect}`).toBeLessThan(1);
        expect(Math.abs(y), `aspect ${aspect}`).toBeLessThan(1);
      }
    }
  });

  it('portrait screens back the camera off; wide screens keep the previous framing', () => {
    expect(fitDistance(30, 1, 50, 0.6)).toBeGreaterThan(fitDistance(30, 1, 50, 1.78) * 1.5);
    const vHalf = (25 * Math.PI) / 180;
    expect(fitDistance(30, 1, 50, 1.78)).toBeCloseTo((30 / Math.tan(vHalf)) * 0.9, 9);
    expect(fitDistance(0.1, 0.2, 50, 1.5)).toBe(6); // tiny systems keep a sensible minimum
  });

  it('frames a disk whole on the tighter axis and follows tiny bodies in true proportions', () => {
    expect(tighterHalfFov(50, 0.6)).toBeLessThan(tighterHalfFov(50, 1.5));
    const disk = (aspect: number) => focusDistance('disk', 10, 'compressed', 50, aspect);
    expect(disk(0.6)).toBeGreaterThan(disk(1.5));
    expect(focusDistance('body', 0.004, 'linear', 50, 1.5)).toBeCloseTo(0.024, 12);
    expect(focusDistance('body', 0.004, 'compressed', 50, 1.5)).toBe(2.5);
    expect(focusDistance('body', 1, 'compressed', 50, 1.5)).toBe(6);
  });
});

describe('model time never wraps, so nothing jumps', () => {
  it('advances monotonically and clamps long frames', () => {
    expect(advanceModelTime(60000, 10, 0.05)).toBeCloseTo(60000.5, 9);
    expect(advanceModelTime(60000, 10, 5)).toBeCloseTo(60000 + 10 * MAX_FRAME_SECONDS, 9);
    expect(advanceModelTime(60000, 10, -1)).toBe(60000);
  });

  it('a body moves smoothly far past the old 2.5e6-day wrap point', () => {
    // RW Aur B: 681,195-day orbit; 2.5e6 days was 3.67 orbits, so it jumped 241 degrees at each wrap.
    const o = orbit({ semi_major_axis_au: 200, period_days: 681195 });
    const speed = 681195 / 8; // days per second
    const frame = 1 / 60;
    const maxStepRad = ((2 * Math.PI) / o.period_days) * speed * frame;
    let mjd = 60000;
    let prev = orbitalPosition(o, mjd);
    for (let i = 0; i < 6000; i++) {
      mjd = advanceModelTime(mjd, speed, frame); // 100 s of animation
      const p = orbitalPosition(o, mjd);
      const cos = (p[0] * prev[0] + p[1] * prev[1] + p[2] * prev[2]) / (Math.hypot(...p) * Math.hypot(...prev));
      expect(Math.acos(Math.min(1, cos))).toBeLessThan(maxStepRad * 1.01 + 1e-9);
      prev = p;
    }
    expect(mjd - 60000).toBeGreaterThan(2.5e6 * 3);
  });

  it('a pulsation stays continuous over many cycles (R Draconis-like)', () => {
    const star = body({ variability: { kind: 'pulsation', period_days: 245.6, amplitude_mag: 6.5, band: 'V' } });
    const speed = 245.6 / 8;
    let mjd = 60000;
    let prev = variabilityFactor(star, mjd);
    for (let i = 0; i < 20000; i++) {
      mjd = advanceModelTime(mjd, speed, 1 / 60); // far past the old 3650-day span
      const f = variabilityFactor(star, mjd);
      expect(Math.abs(Math.log10(f / prev))).toBeLessThan(0.05);
      prev = f;
    }
    expect(mjd - 60000).toBeGreaterThan(3650);
  });
});

describe('orbit legend', () => {
  it('lists assumed and hypothetical orbits by name', () => {
    const bodies = [
      body({ id: 's' }),
      body({ id: 'ba', name: 'Ba', orbit: orbit({ quality: 'assumed' }) }),
      body({ id: 'p9', name: 'Planet Nine', orbit: orbit({ quality: 'hypothetical' }) }),
      body({ id: 'old', name: 'Old', orbit: orbit({ quality: undefined }) }), // pre-0.2.1: fitted
    ];
    expect(nonFittedOrbits(bodies)).toEqual({ assumed: ['Ba'], hypothetical: ['Planet Nine'], fitted: true });
    expect(nonFittedOrbits([body({ id: 's' })])).toEqual({ assumed: [], hypothetical: [], fitted: false });
  });

  it('apoapsis and periapsis bracket the semi-major axis', () => {
    const o = orbit({ semi_major_axis_au: 2, eccentricity: 0.25 });
    expect(periapsisAu(o)).toBeCloseTo(1.5, 12);
    expect(apoapsisAu(o)).toBeCloseTo(2.5, 12);
  });
});
