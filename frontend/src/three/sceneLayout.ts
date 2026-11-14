// Pure layout math for the 3D system scene: distance mapping, body radius caps, camera
// framing, model-time stepping, the Mira pulsation radius and the spin rules (M2: a body turns
// only from a rotation period or the tidal-lock rule). No three.js here, so it is unit-testable
// without WebGL and SystemViewer can import it from the main chunk.
// Everything is a MODEL REPRESENTATION: sizes are exaggerated, distances optionally compressed.
import type { Body, Orbit, OrbitQuality, SystemModel } from '../api/types';
import { compressDistance } from './appearance';
import { paramTier, spectralClass, type Tier } from './astro';
import { formatPeriod } from './bodyFormat';
import { J2000_MJD, topoOrder, type Vec3 } from './orbits';

export type DistanceMode = 'compressed' | 'linear';

export const AU_PER_KM = 1 / 1.495978707e8;

/** Smallest radius (scene units) a body is drawn with, unless that would make it overlap a neighbour. */
export const MIN_VISIBLE_RADIUS: Record<DistanceMode, number> = { compressed: 0.12, linear: 0.03 };

/**
 * Radius modulation of a pulsating (Mira) star: ±10 %, i.e. the class-typical ~20 % peak-to-peak
 * change of the continuum diameter (CLASS-TYPICAL, PULSATION_CITATION). It replaces the old ad-hoc
 * f^0.08 size factor (±27 % for R Dra's 6.5 mag). The V swing itself is TiO-driven (Reid & Goldston
 * 2002, ApJ 568, 931), not a Planck effect, so it is carried by the glow only.
 */
export const PULSATION_RADIUS_AMPLITUDE = 0.1;

export const PULSATION_CITATION =
  'Ireland et al. 2004, MNRAS 350, 365; Woodruff et al. 2004, A&A 421, 703 (Mira continuum diameters change by ~20 % peak-to-peak)';

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

/** True when the scene animates the body's size: a periodic pulsation with an amplitude. */
export function drawsPulsation(body: Body): boolean {
  const v = body.variability;
  return !!v && v.kind === 'pulsation' && !!v.amplitude_mag && !!v.period_days;
}

/**
 * Radius factor of a pulsating star at `mjd`: 1 − A·sin(phase), on the same sinusoid and phase as
 * variabilityFactor (largest when brightest). The real phase lag between size and visual light is
 * not modelled. 1 for every body that is not drawn as pulsating.
 */
export function pulsationRadiusScale(body: Body, mjd: number): number {
  if (!drawsPulsation(body)) return 1;
  const phase = (2 * Math.PI * (mjd - J2000_MJD)) / body.variability!.period_days!;
  return 1 - PULSATION_RADIUS_AMPLITUDE * Math.sin(phase);
}

/** Largest size factor a body reaches while pulsating (1 if it is not drawn as pulsating). */
export function maxPulsationScale(body: Body): number {
  return drawsPulsation(body) ? 1 + PULSATION_RADIUS_AMPLITUDE : 1;
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

/**
 * Suggested animation speed (days per real second) so the fastest motion is easy to follow: the
 * shortest orbital, variability or rotation period, covered in 8 s.
 */
export function suggestedSpeed(system: Pick<SystemModel, 'bodies'>): number {
  const periods = system.bodies.flatMap((b) => [
    b.orbit?.period_days,
    b.variability?.period_days,
    typeof b.rotation_period_hours === 'number' ? b.rotation_period_hours / 24 : undefined,
  ]);
  const valid = periods.filter((p): p is number => typeof p === 'number' && Number.isFinite(p) && p > 0);
  return valid.length ? Math.min(...valid) / 8 : 1;
}

// --- rotation (M2) -------------------------------------------------------------------------------

/** Orbital periods below this make a planet of an M dwarf tidally locked (THEORY). */
export const TIDAL_LOCK_MAX_PERIOD_DAYS = 10;

export const TIDAL_LOCK_CITATION = 'Barnes 2017, Celest. Mech. Dyn. Astron. 129, 509 (tidal locking of habitable exoplanets)';

/** A spin is not drawn when it would advance more than this per rendered frame (it would alias). */
export const SPIN_ALIAS_MAX_DEG_PER_FRAME = 90;

/**
 * How a body spins in the scene:
 *   'period'     rotation_period_hours is set: it turns at that period in model time (tier of its
 *                'Rotation period' Fact; the spin-axis orientation is unknown and drawn upright);
 *   'tidal-lock' a planet with P_orb < 10 d around an M dwarf keeps one face to it (THEORY);
 *   'none'       rotation unknown: not drawn.
 */
export type SpinModel =
  | { readonly kind: 'period'; readonly periodHours: number; readonly tier: Tier; readonly method: string; readonly citation: string }
  | { readonly kind: 'tidal-lock'; readonly periodHours: number; readonly tier: 'theory'; readonly method: string; readonly citation: string }
  | { readonly kind: 'none'; readonly periodHours: null; readonly tier: null; readonly method: string; readonly citation: string };

/** An M-type main-sequence star (from the parsed spectral type). */
function isMDwarf(body: Body): boolean {
  if (body.kind !== 'star') return false;
  const sp = spectralClass(body).value;
  return !!sp && sp.letter === 'M' && (sp.stage === 'main-sequence' || sp.luminosityClass === 'V');
}

/** Bodies the tidal-lock rule applies to (planets and small bodies, as in astro.ts). */
const LOCKABLE: ReadonlySet<Body['kind']> = new Set<Body['kind']>(['planet', 'dwarf_planet', 'moon', 'asteroid', 'comet', 'tno', 'unknown']);

/** The spin model of one body of a system (see SpinModel). */
export function spinModel(body: Body, bodies: readonly Body[]): SpinModel {
  const p = body.rotation_period_hours;
  if (body.kind !== 'disk' && typeof p === 'number' && Number.isFinite(p) && p > 0) {
    const t = paramTier(body, 'rotationPeriod');
    return {
      kind: 'period',
      periodHours: p,
      tier: t.tier,
      method: `turns once per ${formatPeriod(p / 24)} in model time (${t.tier}: ${t.method}); spin-axis orientation unknown, drawn perpendicular to the reference plane`,
      citation: t.citation,
    };
  }
  const o = body.orbit;
  if (LOCKABLE.has(body.kind) && o && o.period_days > 0 && o.period_days < TIDAL_LOCK_MAX_PERIOD_DAYS) {
    const parent = bodies.find((b) => b.id === o.parent);
    if (parent && isMDwarf(parent)) {
      return {
        kind: 'tidal-lock',
        periodHours: o.period_days * 24,
        tier: 'theory',
        method: `orbital period ${formatPeriod(o.period_days)} < ${TIDAL_LOCK_MAX_PERIOD_DAYS} d around the M dwarf ${parent.name}: expected to be tidally locked, so it keeps one face to it`,
        citation: TIDAL_LOCK_CITATION,
      };
    }
  }
  return { kind: 'none', periodHours: null, tier: null, method: 'rotation unknown: not drawn', citation: 'none' };
}

/** Azimuth (rad) of a body around its parent in the reference plane, from its relative position (AU). */
export function orbitalPhaseAngle(rel: Vec3): number {
  return Math.atan2(rel[1], rel[0]);
}

/**
 * Spin angle (rad, about the scene's up axis) at `mjd`: 2π·24·(mjd − J2000)/P_h (mod 2π) for a
 * period, the orbital phase for a tidally locked planet (one face always points to the parent),
 * undefined when the rotation is unknown. Deterministic in model time, so scrubbing works.
 */
export function rotationAngle(spin: SpinModel, mjd: number, orbitalPhase: number | null): number | undefined {
  if (spin.kind === 'period') {
    const turns = (24 * (mjd - J2000_MJD)) / spin.periodHours;
    return 2 * Math.PI * (turns - Math.floor(turns));
  }
  if (spin.kind === 'tidal-lock') return orbitalPhase ?? undefined;
  return undefined;
}

/** True when a spin of this period would advance more than 90° in one frame of `stepDays` (it would alias). */
export function spinAliased(periodHours: number, stepDays: number): boolean {
  if (!(periodHours > 0)) return true;
  return ((Math.abs(stepDays) * 24) / periodHours) * 360 > SPIN_ALIAS_MAX_DEG_PER_FRAME;
}

/** Legend line on how the bodies of a system spin, at a given speed (days per second, 60 frames/s). */
export function spinLegend(system: Pick<SystemModel, 'bodies'>, daysPerSecond: number): string {
  const spins = system.bodies.map((b) => ({ b, s: spinModel(b, system.bodies) }));
  const parts: string[] = [];
  for (const { b, s } of spins) {
    if (s.kind !== 'period') continue;
    const held = spinAliased(s.periodHours, daysPerSecond / 60) ? ', held still at this speed (it would alias)' : '';
    const tier = s.tier === 'measured' ? 'MEASURED period' : `period ${s.tier.toUpperCase()}`;
    parts.push(`${b.name} turns once per ${formatPeriod(s.periodHours / 24)} (${tier}; axis orientation unknown, drawn upright${held})`);
  }
  const locked = spins.filter(({ s }) => s.kind === 'tidal-lock').map(({ b }) => b.name);
  if (locked.length) {
    parts.push(
      `${locked.join(', ')} keep one face to their star (tidal locking expected for P < ${TIDAL_LOCK_MAX_PERIOD_DAYS} d around an M dwarf: THEORY, Barnes 2017)`,
    );
  }
  const unknown = spins.some(({ b, s }) => s.kind === 'none' && b.kind !== 'disk');
  if (unknown) parts.push(parts.length ? 'other bodies: rotation unknown, not drawn' : 'rotation unknown for every body, so none is drawn spinning');
  return `Spin: ${parts.join('; ')}.`;
}
