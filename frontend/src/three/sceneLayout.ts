// Pure layout math for the 3D system scene: distance mapping, body radius caps, camera
// framing and model-time stepping. No three.js here, so it is unit-testable without WebGL.
// Everything is a MODEL REPRESENTATION: sizes are exaggerated, distances optionally compressed.
import type { Body, Orbit, OrbitQuality } from '../api/types';
import { compressDistance } from './appearance';
import { topoOrder } from './orbits';

export type DistanceMode = 'compressed' | 'linear';

export const AU_PER_KM = 1 / 1.495978707e8;

/** Smallest radius (scene units) a body is drawn with, unless that would make it overlap a neighbour. */
export const MIN_VISIBLE_RADIUS: Record<DistanceMode, number> = { compressed: 0.12, linear: 0.03 };

/** Pulsating stars change size a little (factor^0.08), brightness a lot. */
export const PULSATION_SIZE_EXPONENT = 0.08;

/** Orbit line colors (also used by the legend under the canvas, so both always agree). */
export const ORBIT_COLOR: Record<OrbitQuality, string> = {
  fitted: '#3a4a6b',
  assumed: '#fbbf24',
  hypothetical: '#c084fc',
};

/** Largest real-time step (s) one animation frame may advance; avoids a leap after a background tab. */
export const MAX_FRAME_SECONDS = 0.1;

/**
 * Names of bodies whose orbit is not a published fit, for the legend under the canvas
 * (a missing quality means 'fitted', as in products older than 0.2.1), and whether any is fitted.
 */
export function nonFittedOrbits(bodies: Body[]): { assumed: string[]; hypothetical: string[]; fitted: boolean } {
  const orbiting = bodies.filter((b) => b.orbit);
  const named = (q: OrbitQuality) => orbiting.filter((b) => b.orbit!.quality === q).map((b) => b.name);
  return {
    assumed: named('assumed'),
    hypothetical: named('hypothetical'),
    fitted: orbiting.some((b) => (b.orbit!.quality ?? 'fitted') === 'fitted'),
  };
}

export function periapsisAu(orbit: Orbit): number {
  return orbit.semi_major_axis_au * (1 - orbit.eccentricity);
}

export function apoapsisAu(orbit: Orbit): number {
  return orbit.semi_major_axis_au * (1 + orbit.eccentricity);
}

/**
 * Reference distance (AU) of the compressed mapping: the smallest periapsis in the system (or the
 * smallest disk radius). Using periapsis rather than semi-major axis means no orbit ever dips into
 * the linear core of the mapping, where it could pass inside its parent's display radius.
 */
export function referenceAu(bodies: Body[]): number {
  const scales = bodies.flatMap((b) => [
    b.orbit ? periapsisAu(b.orbit) : undefined,
    b.kind === 'disk' && b.radius_km ? b.radius_km * AU_PER_KM : undefined,
  ]);
  const valid = scales.filter((v): v is number => typeof v === 'number' && Number.isFinite(v) && v > 0);
  return valid.length ? Math.min(...valid) : 1;
}

/** Scene units per AU in "true proportions" mode: the whole parent chain fits in ~30 units. */
export function linearScale(bodies: Body[]): number {
  const maxExtent = bodies.reduce((s, b) => s + (b.orbit ? apoapsisAu(b.orbit) : 0), 0);
  return maxExtent > 0 ? 30 / maxExtent : 1;
}

/** AU → scene units for a distance mode. */
export function distanceMapper(mode: DistanceMode, refAu: number, scale: number): (au: number) => number {
  return mode === 'compressed' ? (au) => compressDistance(au, refAu) : (au) => au * scale;
}

/** Size factor of a body for a brightness factor (1 = mean). */
export function pulsationScale(brightnessFactor: number): number {
  return Math.pow(brightnessFactor, PULSATION_SIZE_EXPONENT);
}

/** Largest size factor a body reaches while pulsating (1 if it is not drawn as pulsating). */
export function maxPulsationScale(body: Body): number {
  const v = body.variability;
  if (!v || !v.amplitude_mag || !v.period_days) return 1; // same conditions as variabilityFactor
  return pulsationScale(Math.pow(10, 0.4 * (Math.abs(v.amplitude_mag) / 2)));
}

/** Non-disk bodies that orbit an existing body, grouped by parent id. */
export function childrenByParent(bodies: Body[]): Map<string, Body[]> {
  const ids = new Set(bodies.map((b) => b.id));
  const byParent = new Map<string, Body[]>();
  for (const b of bodies) {
    if (!b.orbit || b.kind === 'disk' || !ids.has(b.orbit.parent)) continue;
    byParent.set(b.orbit.parent, [...(byParent.get(b.orbit.parent) ?? []), b]);
  }
  return byParent;
}

/**
 * Cap display radii (scene units) so that, in this distance mode,
 *  - a parent never reaches its nearest child's periapsis, and
 *  - parentRadius + childRadius < child periapsis for EVERY parent/child pair (bodies never
 *    pass through each other), with siblings kept apart where their orbits do not cross.
 * The visibility floor (MIN_VISIBLE_RADIUS) only applies where it does not break these rules.
 * Radii returned are nominal; the guarantee holds at the largest pulsation size too.
 */
export function capRadii(
  bodies: Body[],
  mode: DistanceMode,
  base: Map<string, number>,
  map: (au: number) => number,
): Map<string, number> {
  const floor = MIN_VISIBLE_RADIUS[mode];
  const byId = new Map(bodies.map((b) => [b.id, b]));
  const grow = (id: string) => {
    const b = byId.get(id);
    return b ? maxPulsationScale(b) : 1;
  };
  const radius = new Map(base);
  const byParent = childrenByParent(bodies);

  // 1. A parent and each child together use at most 80% of that child's periapsis. When they do not
  //    fit, both shrink by the same factor, so their size ratio is kept (Eps Ind Ba and Bb are the
  //    same size and must look it). Parents first: a body's radius is final before its children's.
  for (const body of topoOrder(bodies)) {
    const kids = byParent.get(body.id);
    if (!kids) continue;
    const kP = grow(body.id);
    let rP = radius.get(body.id) ?? 0;
    for (const kid of kids) {
      const peri = map(periapsisAu(kid.orbit!));
      const kC = grow(kid.id);
      const rC = radius.get(kid.id) ?? 0;
      const sum = rP * kP + rC * kC;
      if (sum > 0.8 * peri && sum > 0) {
        const s = (0.8 * peri) / sum;
        rP *= s;
        radius.set(kid.id, rC * s);
      }
    }
    // Visibility floor for the parent only where it fits (its equal share of the 80% budget).
    const nearest = Math.min(...kids.map((k) => map(periapsisAu(k.orbit!))));
    radius.set(body.id, Math.max(rP * kP, Math.min(floor, 0.4 * nearest)) / kP);
  }

  // 2. Children: stay off the parent's surface and away from the siblings whose orbits they share.
  for (const body of topoOrder(bodies)) {
    const kids = byParent.get(body.id);
    if (!kids) continue;
    const parentR = (radius.get(body.id) ?? 0) * grow(body.id);
    const spans = kids
      .map((k) => ({ id: k.id, peri: map(periapsisAu(k.orbit!)), apo: map(apoapsisAu(k.orbit!)) }))
      .sort((x, y) => x.peri - y.peri);
    // Closest approach between neighbours: each periapsis vs the previous sibling's apoapsis.
    const siblingGaps: number[] = [];
    for (let i = 1; i < spans.length; i++) siblingGaps.push(spans[i].peri - spans[i - 1].apo);
    const siblingCap = siblingGaps.length ? 0.4 * Math.min(...siblingGaps) : Infinity;
    for (const s of spans) {
      const room = Math.max(0, s.peri - parentR); // distance from the parent's surface at periapsis
      const childFloor = Math.min(floor, 0.4 * room);
      const cap = Math.max(childFloor, Math.min(0.9 * room, siblingCap));
      const k = grow(s.id);
      radius.set(s.id, Math.min((radius.get(s.id) ?? cap / k) * k, cap) / k);
    }
  }
  return radius;
}

/** Vertical and horizontal half fields of view (radians) for a vertical FOV and aspect (w/h). */
export function halfFovs(fovDeg: number, aspect: number): { vHalf: number; hHalf: number } {
  const vHalf = (fovDeg / 2) * (Math.PI / 180);
  return { vHalf, hHalf: Math.atan(Math.tan(vHalf) * (aspect > 0 ? aspect : 1)) };
}

/** Half field of view (radians) of the tighter screen axis. */
export function tighterHalfFov(fovDeg: number, aspect: number): number {
  const { vHalf, hHalf } = halfFovs(fovDeg, aspect);
  return Math.min(vHalf, hHalf);
}

/**
 * Camera distance that shows the whole system (radius `extent`, mostly flat) on BOTH screen axes,
 * for a camera placed at (0, 0.55·d, d) looking at the origin. Vertically the system is
 * foreshortened by the viewing angle (0.9 is enough); horizontally it is not, so portrait and
 * square stages need the full extent / tan(hHalf).
 */
export function fitDistance(extent: number, maxRadius: number, fovDeg: number, aspect: number): number {
  const { vHalf, hHalf } = halfFovs(fovDeg, aspect);
  return Math.max(extent / Math.tan(hHalf), (extent / Math.tan(vHalf)) * 0.9, maxRadius * 4.5, 6);
}

/**
 * Camera distance when entering a body. Disks are framed whole on both axes; other bodies at a
 * few radii. In compressed mode a 2.5-unit floor keeps neighbours in view; in true proportions
 * bodies are tiny, so the camera follows the radius (otherwise the body is a few pixels).
 */
export function focusDistance(
  kind: 'disk' | 'body',
  radius: number,
  mode: DistanceMode,
  fovDeg: number,
  aspect: number,
): number {
  if (kind === 'disk') return (radius / Math.sin(tighterHalfFov(fovDeg, aspect))) * 1.1;
  return mode === 'linear' ? radius * 6 : Math.max(radius * 6, 2.5);
}

/**
 * Advance model time by one animation frame. Never wraps: positions and variability are periodic
 * functions of a continuous time (the Kepler solver reduces the mean anomaly mod 2π), so a wrap
 * that is not a whole number of every period would make bodies jump.
 */
export function advanceModelTime(mjd: number, daysPerSecond: number, frameSeconds: number): number {
  const dt = Math.min(Math.max(frameSeconds, 0), MAX_FRAME_SECONDS);
  return mjd + daysPerSecond * dt;
}
