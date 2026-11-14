// Pure orbital math for the 3D views (no three.js here, so it is unit-testable).
// Positions are in AU, in a right-handed frame where the reference plane is x–y
// and +z is "up" (the scene maps it to three.js +y).
import type { Body, Orbit } from '../api/types';

export const J2000_MJD = 51544.5;
const DEG = Math.PI / 180;

export type Vec3 = [number, number, number];

/** Solve Kepler's equation M = E − e·sin(E) for E (radians), Newton–Raphson. */
export function solveKepler(meanAnomaly: number, e: number): number {
  const M = ((meanAnomaly % (2 * Math.PI)) + 2 * Math.PI) % (2 * Math.PI);
  let E = e < 0.8 ? M : Math.PI;
  for (let i = 0; i < 50; i++) {
    const dE = (E - e * Math.sin(E) - M) / (1 - e * Math.cos(E));
    E -= dE;
    if (Math.abs(dE) < 1e-12) break;
  }
  return E;
}

/** Position (AU) of a body relative to its parent at time `mjd`. */
export function orbitalPosition(orbit: Orbit, mjd: number): Vec3 {
  const epoch = orbit.epoch_mjd ?? J2000_MJD;
  const n = (2 * Math.PI) / orbit.period_days; // rad/day
  const M = orbit.mean_anomaly_deg * DEG + n * (mjd - epoch);
  const e = orbit.eccentricity;
  const E = solveKepler(M, e);
  const a = orbit.semi_major_axis_au;
  // Position in the orbital plane (periapsis along +x).
  const xp = a * (Math.cos(E) - e);
  const yp = a * Math.sqrt(1 - e * e) * Math.sin(E);
  return rotateToReference(xp, yp, orbit);
}

/** Rotate orbital-plane coordinates by ω, i, Ω (standard 3-1-3 rotation). */
function rotateToReference(xp: number, yp: number, orbit: Orbit): Vec3 {
  const w = orbit.arg_periapsis_deg * DEG;
  const i = orbit.inclination_deg * DEG;
  const O = orbit.ascending_node_deg * DEG;
  const cw = Math.cos(w), sw = Math.sin(w), ci = Math.cos(i), si = Math.sin(i), cO = Math.cos(O), sO = Math.sin(O);
  const x = (cO * cw - sO * sw * ci) * xp + (-cO * sw - sO * cw * ci) * yp;
  const y = (sO * cw + cO * sw * ci) * xp + (-sO * sw + cO * cw * ci) * yp;
  const z = sw * si * xp + cw * si * yp;
  return [x, y, z];
}

/** Sampled closed orbit path (AU, relative to the parent) for drawing the ellipse. */
export function orbitPath(orbit: Orbit, segments = 256): Vec3[] {
  const e = orbit.eccentricity;
  const a = orbit.semi_major_axis_au;
  const pts: Vec3[] = [];
  for (let k = 0; k <= segments; k++) {
    const E = (2 * Math.PI * k) / segments;
    pts.push(rotateToReference(a * (Math.cos(E) - e), a * Math.sqrt(1 - e * e) * Math.sin(E), orbit));
  }
  return pts;
}

/** Bodies ordered so that every parent comes before its children. */
export function topoOrder(bodies: Body[]): Body[] {
  const byId = new Map(bodies.map((b) => [b.id, b]));
  const out: Body[] = [];
  const done = new Set<string>();
  const visit = (b: Body, depth: number) => {
    if (done.has(b.id) || depth > bodies.length) return;
    const parent = b.orbit ? byId.get(b.orbit.parent) : undefined;
    if (parent) visit(parent, depth + 1);
    done.add(b.id);
    out.push(b);
  };
  bodies.forEach((b) => visit(b, 0));
  return out;
}

/** Brightness factor (linear flux ratio, 1 = mean) of a variable at `mjd`. Sinusoidal approximation. */
export function variabilityFactor(body: Body, mjd: number): number {
  const v = body.variability;
  if (!v || !v.amplitude_mag) return 1;
  if (!v.period_days) return 1; // irregular: no periodic model, keep constant
  const phase = (2 * Math.PI * (mjd - J2000_MJD)) / v.period_days;
  const dmag = (v.amplitude_mag / 2) * Math.sin(phase);
  return Math.pow(10, -0.4 * dmag);
}
