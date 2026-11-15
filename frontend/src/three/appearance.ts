// Look of a body in the 3D scene: base colour, surface-pattern gate and display-scale helpers.
// Everything here is part of a MODEL REPRESENTATION, not an image.
//
// Real systems draw only what is measured or physically derived (AGENTS.md rules 3-5):
//   stars        blackbody colour at the catalog Teff through the CIE 1931 2° observer (astro.ts)
//   planets      a neutral 18 % grey sphere: albedo and colour are unknown for every real target
//   brown dwarfs neutral: their visible spectra are not blackbodies (Burrows, Marley & Sharp 2000,
//                ApJ 531, 438), so no visible colour is computed
//   disks        neutral, translucent: the scattered-light colour is not computed
// No random craters, bands or blotches on real bodies; class-typical patterns appear only when the
// viewer turns them on, labelled ILLUSTRATIVE (S5). The hand palette below and kelvinToRgb (Tanner
// Helland fit) are used ONLY for the synthetic demo system (provenance.synthetic).
import type { Body, SystemModel } from '../api/types';
import { bodyColor as blackbodyBodyColor, spectralClass } from './astro';

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
 * 'mottling' is kept in the type for compatibility but is never returned: no class-level source
 * supports albedo mottling on the rocky exoplanets, so they stay uniform (S5).
 */
export type SurfacePattern = 'none' | 'procedural' | 'bands' | 'mottling';

/** Peak intensity contrast of the class-typical patterns (ILLUSTRATIVE drawing choice): 1 ± c about the mean. */
export const CLASS_TYPICAL_CONTRAST: Record<'bands' | 'mottling', number> = { bands: 0.15, mottling: 0.1 };

/** L/T-transition brown dwarfs: variability from patchy, banded clouds is common there. */
export const CLASS_TYPICAL_CITATION =
  'patchy / banded clouds of L/T-transition brown dwarfs: Radigan et al. 2014, ApJ 793, 75; Metchev et al. 2015, ApJ 799, 154; Apai et al. 2017, Science 357, 683';

/** Giant planets: zonal bands. */
export const GAS_GIANT_BANDS_CITATION =
  'zonal bands of Jupiter and Saturn: Vasavada & Showman 2005, Rep. Prog. Phys. 68, 1935; banding expected on rapidly rotating giant planets: Showman & Kaspi 2013, ApJ 776, 85';

/**
 * Spectral-type window of the L/T transition, from L9 to T3.5 (Radigan et al. 2014): the range where
 * strong rotational variability from patchy clouds is common. Outside it (later T, Y) no class
 * pattern is drawn.
 */
export const LT_TRANSITION = { from: { letter: 'L', subtype: 9 }, to: { letter: 'T', subtype: 3.5 } } as const;

/** True for a brown dwarf whose parsed spectral type lies in L9–T3.5. */
export function isLTTransition(body: Body): boolean {
  if (body.kind !== 'brown_dwarf') return false;
  const sp = spectralClass(body).value;
  if (!sp || sp.subtype === null) return false;
  if (sp.letter === 'L') return sp.subtype >= LT_TRANSITION.from.subtype;
  if (sp.letter === 'T') return sp.subtype <= LT_TRANSITION.to.subtype;
  return false;
}

/** What the class-typical toggle adds to one body, and the class-level source for it (S5). */
export interface ClassTypicalFeature {
  readonly pattern: 'bands' | 'none';
  /** What is drawn, in plain words ('' when nothing). */
  readonly what: string;
  /** The class the pattern is typical of ('' when nothing). */
  readonly basis: string;
  /** Class-level literature source, or 'none'. */
  readonly citation: string;
}

const NO_FEATURE: ClassTypicalFeature = { pattern: 'none', what: '', basis: '', citation: 'none' };

/**
 * The S5 list of class-typical features, and nothing more:
 *   L9–T3.5 brown dwarfs (Eps Ind Ba, T1)     patchy cloud bands (CLASS_TYPICAL_CITATION)
 *   gas giants (Eps Ind Ab)                   zonal bands (GAS_GIANT_BANDS_CITATION)
 * Later T dwarfs (Eps Ind Bb, T6), Y dwarfs (WISE 0855) and rocky or icy planets (Barnard b–e) get
 * nothing: no class-level source has been checked for a drawn pattern on them. Real systems only.
 */
export function classTypicalFeature(body: Body, system: Pick<SystemModel, 'provenance'>): ClassTypicalFeature {
  if (system.provenance.synthetic || !PATTERNED_KINDS.has(body.kind) || body.appearance.model === 'mesh') return NO_FEATURE;
  if (isLTTransition(body)) {
    return {
      pattern: 'bands',
      what: 'patchy cloud bands',
      basis: 'L/T-transition brown dwarfs (L9–T3.5)',
      citation: CLASS_TYPICAL_CITATION,
    };
  }
  if (body.kind !== 'brown_dwarf' && body.appearance.model === 'gas_giant') {
    return { pattern: 'bands', what: 'zonal bands', basis: 'giant planets', citation: GAS_GIANT_BANDS_CITATION };
  }
  return NO_FEATURE;
}

/**
 * Which surface pattern a body gets:
 *   'procedural' synthetic demo system only (the legacy seeded bands / craters), in both colour modes;
 *   'bands'      the class-typical features of classTypicalFeature (S5 list), only with the
 *                class-typical toggle on: ILLUSTRATIVE;
 *   'none'       everything else. A real body never gets a pattern with the toggle off: no
 *                object-level surface map or verified modulation amplitude exists for any demo target.
 */
export function surfacePattern(body: Body, system: Pick<SystemModel, 'provenance'>, classTypical = false): SurfacePattern {
  if (!PATTERNED_KINDS.has(body.kind) || body.appearance.model === 'mesh') return 'none';
  if (system.provenance.synthetic) return 'procedural';
  if (!classTypical) return 'none';
  return classTypicalFeature(body, system).pattern;
}

/** The gate of SystemScene's procedural / class-typical textures. */
export function hasSurfacePattern(body: Body, system: Pick<SystemModel, 'provenance'>, classTypical = false): boolean {
  return surfacePattern(body, system, classTypical) !== 'none';
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

/** Exaggerated, always-visible display radius (scene units) from a physical radius. */
export function displayRadius(body: Body): number {
  if (body.kind === 'disk') return 0;
  const km = body.radius_km ?? (body.kind === 'star' ? 700000 : 3000);
  // Earth (6371 km) → ~0.35, Jupiter → ~0.6, Sun → ~1.2, giant stars capped.
  return clamp(0.12 * Math.pow(km, 0.18), 0.12, 2.2);
}

/** Re-exported for the 3D modules; main-chunk code imports it from ./kindLabels (astro-free). */
export { KIND_LABEL } from './kindLabels';
