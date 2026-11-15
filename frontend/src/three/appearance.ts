// Look of a body in the 3D scene: base colour, surface-pattern gate and display-scale helpers.
// Everything here is part of a MODEL REPRESENTATION, not an image.
//
// Real systems draw only what is measured or physically derived (AGENTS.md rules 3-5):
//   stars        blackbody colour at the catalog Teff through the CIE 1931 2° observer (astro.ts)
//   planets      a neutral 18 % grey sphere: albedo and colour are unknown for every real target
//   brown dwarfs neutral: their visible spectra are not blackbodies (Burrows, Marley & Sharp 2000,
//                ApJ 531, 438), so no visible colour is computed
//   disks        neutral, translucent: the scattered-light colour is not computed
// No random craters, bands, blotches or convection cells on real bodies (docs/VISION.md). A body whose
// Teff is unknown is drawn grey and one whose radius is unknown at a fixed marker size (factOrigin.ts).
// The hand palette below and kelvinToRgb (Tanner Helland fit) are used ONLY for the synthetic demo
// system (provenance.synthetic), which also keeps its procedural textures.
import type { Body, SystemModel } from '../api/types';
import { bodyColor as blackbodyBodyColor } from './astro';
import { isSizeKnown } from './factOrigin';

const clamp = (v: number, lo: number, hi: number) => Math.min(hi, Math.max(lo, v));

/**
 * Approximate blackbody color (sRGB 0–255) for a temperature in kelvin.
 * Tanner Helland's fit, valid ~1000–40000 K; below 1000 K we fade to a dark red.
 * Synthetic demo system only: real systems use the CIE 1931 colour from astro.ts.
 */
export function kelvinToRgb(kelvin: number): [number, number, number] {
  const t = clamp(kelvin, 1000, 40000) / 100;
  let r: number, g: number, b: number;
  if (t <= 66) {
    r = 255;
    g = 99.4708025861 * Math.log(t) - 161.1195681661;
    b = t <= 19 ? 0 : 138.5177312231 * Math.log(t - 10) - 305.0447927307;
  } else {
    r = 329.698727446 * Math.pow(t - 60, -0.1332047592);
    g = 288.1221695283 * Math.pow(t - 60, -0.0755148492);
    b = 255;
  }
  let rgb: [number, number, number] = [clamp(r, 0, 255), clamp(g, 0, 255), clamp(b, 0, 255)];
  if (kelvin < 1000) {
    const k = clamp((kelvin - 200) / 800, 0.15, 1); // dim toward black
    rgb = [rgb[0] * k, rgb[1] * k * 0.6, rgb[2] * k * 0.6];
  }
  return rgb.map(Math.round) as [number, number, number];
}

export function rgbToHex([r, g, b]: [number, number, number]): string {
  return '#' + [r, g, b].map((v) => v.toString(16).padStart(2, '0')).join('');
}

/** Reflectance used for bodies whose albedo is unknown (a photographic mid grey). */
export const NEUTRAL_ALBEDO = 0.18;

/** NEUTRAL_ALBEDO as an sRGB-encoded hex: linear 0.18 → sRGB 0.461 → 118 = 0x76. */
export const NEUTRAL_GREY_HEX = '#767676';

/** Hand palette of the synthetic demo system (decoration, never used for a real body). */
const SYNTHETIC_PALETTE: Record<string, string> = {
  gas_giant: '#c9a27a',
  icy: '#bcd7e8',
  disk: '#d9a066',
  brown_dwarf: '#7a2e3b',
};

/** The legacy look, kept for the synthetic demo system: override > temperature fit > palette. */
function syntheticColor(body: Body): string {
  if (body.appearance.color_hex) return body.appearance.color_hex;
  if (body.teff_k && (body.kind === 'star' || body.kind === 'brown_dwarf')) return rgbToHex(kelvinToRgb(body.teff_k));
  return SYNTHETIC_PALETTE[body.appearance.model] ?? '#9a8f84';
}

/**
 * Base visible colour of a body ('#rrggbb', sRGB). Real systems (the default when `system` is not
 * given): the CIE 1931 blackbody colour for stars and brown dwarfs ≥ 2500 K, otherwise the neutral
 * 18 % grey (a hand-set appearance.color_hex is ignored: it would not be physically derived).
 * Synthetic systems keep the legacy palette and temperature fit. Brightness is applied separately.
 */
export function bodyColor(body: Body, system?: Pick<SystemModel, 'provenance'> | null): string {
  if (system?.provenance.synthetic) return syntheticColor(body);
  return blackbodyBodyColor(body).value?.hex ?? NEUTRAL_GREY_HEX;
}

/** Kinds that can carry a surface pattern (stars use the star shader, disks are rings). */
const PATTERNED_KINDS: ReadonlySet<Body['kind']> = new Set<Body['kind']>([
  'brown_dwarf',
  'planet',
  'dwarf_planet',
  'moon',
  'asteroid',
  'comet',
  'tno',
  'unknown',
]);

/**
 * 'procedural' = the synthetic demo's seeded bands / craters (decoration, labelled SYNTHETIC);
 * 'none' = a smooth sphere. Real bodies never get a pattern: no surface map is measured for any of
 * them (docs/VISION.md: no invented spots, clouds or bands), so the old class-typical toggle is gone.
 */
export type SurfacePattern = 'none' | 'procedural';

/** Which surface pattern a body gets: 'procedural' in the synthetic demo system only, 'none' for every real body. */
export function surfacePattern(body: Body, system: Pick<SystemModel, 'provenance'>): SurfacePattern {
  if (!PATTERNED_KINDS.has(body.kind) || body.appearance.model === 'mesh') return 'none';
  return system.provenance.synthetic ? 'procedural' : 'none';
}

/** The gate of SystemScene's procedural textures (synthetic demo only). */
export function hasSurfacePattern(body: Body, system: Pick<SystemModel, 'provenance'>): boolean {
  return surfacePattern(body, system) !== 'none';
}

/**
 * Compressed distance mapping (AU → scene units) so 0.02 AU and 1500 AU fit in one view.
 * Linear up to the system's smallest orbit (`refAu` → 3 units), logarithmic beyond it:
 * each ×10 in distance adds 10 units. Continuous and monotonic.
 */
export function compressDistance(au: number, refAu: number): number {
  const r = au / refAu;
  return r <= 1 ? 3 * r : 3 + 10 * Math.log10(r);
}

/**
 * Display radius (scene units) of a body whose radius is unknown: a fixed marker, the same for every
 * kind, between the 0.12 floor and Earth's ~0.35. Not scaled from any radius (docs/VISION.md: size
 * unknown, not scaled); the scene labels it 'size unknown · not to scale'.
 */
export const UNKNOWN_SIZE_DISPLAY_RADIUS = 0.3;

/** Exaggerated, always-visible display radius (scene units) from a physical radius. */
export function displayRadius(body: Body): number {
  if (body.kind === 'disk') return 0;
  if (!isSizeKnown(body)) return UNKNOWN_SIZE_DISPLAY_RADIUS;
  // Earth (6371 km) → ~0.35, Jupiter → ~0.6, Sun → ~1.2, giant stars capped.
  return clamp(0.12 * Math.pow(body.radius_km as number, 0.18), 0.12, 2.2);
}

/** Re-exported for the 3D modules; main-chunk code imports it from ./kindLabels (astro-free). */
export { KIND_LABEL } from './kindLabels';
