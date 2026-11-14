// Physics core of the 3D gallery (WS7): every colour, brightness, scale and derived number the
// scene and the body panel show, each returned as { value, tier, method, citation, flags }.
//
// NO three.js here (and none in cie1931.ts / spherexBands.ts): BodyPanel, in the main chunk,
// imports this module, and three.js must stay in the lazily loaded 3D chunk.
//
// Evidence tiers, strongest first (TIERS):
//   measured      the drawn value is backed by a verified Fact (see paramTier for the mapping)
//   derived       computed only from measured inputs with an exact relation (L = 4πR²σT⁴, log g ...)
//   model         a physical model or approximation is involved (blackbody, μ = 1.3, Eddington
//                 atmosphere, assumed albedo), or an input is itself a model estimate
//   class-typical a value typical of the object class, not of this object
//   theory        a theoretical expectation (e.g. tidal locking)
//   range-pick    a single number drawn from a published range
//   illustrative  no verified source backs the value (drawing value, unverified, or no Fact at all)
//   display       a screen mapping (brightness for the glow), never photometry
// A derived value is 'derived' when all its inputs are measured; otherwise it takes the weakest
// input tier, and never anything stronger than the method's own floor (derivedTier).
//
// Constants: CODATA 2018 (h, c, k exact; σ, G), IAU 2015 Resolution B3 nominal solar and planetary
// values, IAU 2012 B2 (au), IAU 2015 B2 (pc).
import type { Body, Fact, SystemModel } from '../api/types';
import { CIE1931_2DEG, CIE1931_CITATION, CIE1931_STEP_NM } from './cie1931';
import { SPHEREX_BANDS_CITATION, SPHEREX_DETECTORS, type SpherexDetector } from './spherexBands';

// --- tiers, flags, result shape ------------------------------------------------------------

export type Tier =
  | 'measured'
  | 'derived'
  | 'model'
  | 'class-typical'
  | 'theory'
  | 'range-pick'
  | 'illustrative'
  | 'display';

/** All tiers, strongest first. */
export const TIERS: readonly Tier[] = [
  'measured',
  'derived',
  'model',
  'class-typical',
  'theory',
  'range-pick',
  'illustrative',
  'display',
];

export type Flag =
  /** An input is a minimum mass (M sin i): the true value can only be larger. */
  | 'lower-bound'
  /** An input needed by the method is absent: the value is null. */
  | 'missing-input'
  /** The quantity is not modelled for this kind of body: the value is null. */
  | 'not-modelled'
  /** Teff < 2500 K: molecular/cloudy atmospheres are far from a blackbody (colours and
   *  magnitudes are not shown; fractions are kept only as a model diagnostic). */
  | 'blackbody-unreliable'
  /** Predicted brighter than the SPHEREx non-linearity onset of that band (pre-launch model). */
  | 'brighter-than-nonlinearity'
  /** The orbit is assumed or hypothetical (Orbit.quality), not a fitted solution. */
  | 'assumed-orbit';

export interface Derived<T> {
  readonly value: T;
  readonly tier: Tier;
  /** Formula, assumptions and the tiers of its inputs, in plain words. */
  readonly method: string;
  /** Where the formula, constants or data come from. */
  readonly citation: string;
  readonly flags: readonly Flag[];
}

const rank = (t: Tier) => TIERS.indexOf(t);

/** The weakest of a list of tiers ('measured' for an empty list). */
export function weakestTier(tiers: readonly Tier[]): Tier {
  return tiers.reduce<Tier>((w, t) => (rank(t) > rank(w) ? t : w), 'measured');
}

/**
 * Tier of a value computed from inputs: 'derived' when every input is measured (or derived),
 * otherwise the weakest input tier; never stronger than the method's own `floor`.
 */
export function derivedTier(inputs: readonly Tier[], floor: Tier = 'derived'): Tier {
  return weakestTier([...inputs.map((t) => (t === 'measured' ? 'derived' : t)), floor]);
}

// --- constants -------------------------------------------------------------------------------

export const PHYS = {
  h: 6.62607015e-34, // J s, CODATA 2018 (exact)
  c: 299792458, // m/s (exact)
  k: 1.380649e-23, // J/K, CODATA 2018 (exact)
  sigma: 5.670374419e-8, // W m^-2 K^-4, CODATA 2018
  G: 6.6743e-11, // m^3 kg^-1 s^-2, CODATA 2018
  mH: 1.6735575e-27, // kg, mass of the hydrogen atom
  au: 1.495978707e11, // m, IAU 2012 Resolution B2
  pc: 3.0856775814913673e16, // m, IAU 2015 Resolution B2
  RSun: 6.957e8, // m, IAU 2015 B3 nominal solar radius
  LSun: 3.828e26, // W, IAU 2015 B3 nominal solar luminosity
  TeffSun: 5772, // K, IAU 2015 B3 nominal solar effective temperature
  GMSun: 1.3271244e20, // m^3 s^-2, IAU 2015 B3
  GMEarth: 3.986004e14, // m^3 s^-2, IAU 2015 B3
  GMJup: 1.2668653e17, // m^3 s^-2, IAU 2015 B3
  REarth: 6.3781e6, // m, IAU 2015 B3 nominal equatorial radius
  RJup: 7.1492e7, // m, IAU 2015 B3 nominal equatorial radius
  jansky: 1e-26, // W m^-2 Hz^-1
  abZeroJy: 3631, // AB zero point (Oke & Gunn 1983)
} as const;

export const PHYS_CITATION =
  'CODATA 2018 (h, c, k, σ, G); IAU 2015 Resolution B3 nominal solar/planetary values; IAU 2012 B2 (au); IAU 2015 B2 (pc)';

const M_SUN = PHYS.GMSun / PHYS.G;
const M_EARTH = PHYS.GMEarth / PHYS.G;
const M_JUP = PHYS.GMJup / PHYS.G;
const C2 = (PHYS.h * PHYS.c) / PHYS.k; // second radiation constant, m K

/** Mean molecular weight used for the pressure scale height (neutral H + He gas; an assumption). */
export const MEAN_MOLECULAR_WEIGHT = 1.3;
/** Below this Teff blackbody colours and magnitudes are not shown (see the 'blackbody-unreliable' flag). */
export const BLACKBODY_MIN_TEFF_K = 2500;
/** Visible band for the visible-light fraction (nm). */
export const VISIBLE_BAND_NM: readonly [number, number] = [380, 780];
/** Granulation is drawn only when fewer cells than this fit across the disc (M2). */
export const GRANULATION_MAX_CELLS = 64;

const STEFAN_BOLTZMANN = 'Stefan–Boltzmann law';
const PLANCK_CITE = 'Planck function, e.g. Rybicki & Lightman 1979, Radiative Processes in Astrophysics (Wiley)';
const BB_UNRELIABLE_CITE =
  'Burrows, Sudarsky & Lunine 2003, ApJ 596, 587; Marley & Robinson 2015, ARA&A 53, 279 (cool-dwarf spectra are far from a blackbody)';

// --- radiometry primitives (SI) --------------------------------------------------------------

/** Spectral radiance B_λ(T), W m^-3 sr^-1. */
function planckLambda(lambdaM: number, T: number): number {
  const x = C2 / (lambdaM * T);
  if (!(x < 700)) return 0; // exp overflow (and T <= 0): no emission at this wavelength
  return (2 * PHYS.h * PHYS.c * PHYS.c) / lambdaM ** 5 / Math.expm1(x);
}

/** Spectral radiance B_ν(T), W m^-2 Hz^-1 sr^-1. */
function planckNu(nuHz: number, T: number): number {
  const x = (PHYS.h * nuHz) / (PHYS.k * T);
  if (!(x < 700)) return 0;
  return (2 * PHYS.h * nuHz ** 3) / (PHYS.c * PHYS.c) / Math.expm1(x);
}

/** ∫ B_λ dλ over [lo, hi] (m), midpoint rule in ln λ. */
function bandRadiance(T: number, loM: number, hiM: number, steps: number): number {
  const a = Math.log(loM);
  const d = (Math.log(hiM) - a) / steps;
  let sum = 0;
  for (let i = 0; i < steps; i++) {
    const lambda = Math.exp(a + (i + 0.5) * d);
    sum += planckLambda(lambda, T) * lambda * d;
  }
  return sum;
}

/** Tristimulus X, Y, Z of a blackbody: sums over the tabulated CIE 1931 2° CMFs (5 nm). */
function cieXYZ(T: number): [number, number, number] {
  const dl = CIE1931_STEP_NM * 1e-9;
  let X = 0;
  let Y = 0;
  let Z = 0;
  for (const [nm, xb, yb, zb] of CIE1931_2DEG) {
    const b = planckLambda(nm * 1e-9, T) * dl;
    X += b * xb;
    Y += b * yb;
    Z += b * zb;
  }
  return [X, Y, Z];
}

/** XYZ → linear sRGB (D65), IEC 61966-2-1 matrix. */
function xyzToLinearSrgb([X, Y, Z]: [number, number, number]): [number, number, number] {
  return [
    3.2406 * X - 1.5372 * Y - 0.4986 * Z,
    -0.9689 * X + 1.8758 * Y + 0.0415 * Z,
    0.0557 * X - 0.204 * Y + 1.057 * Z,
  ];
}

/** sRGB transfer curve (IEC 61966-2-1) for one linear channel in [0, 1]. */
function encodeSrgb(v: number): number {
  const c = Math.min(1, Math.max(0, v));
  return c <= 0.0031308 ? 12.92 * c : 1.055 * Math.pow(c, 1 / 2.4) - 0.055;
}

const SRGB_CITE = 'IEC 61966-2-1:1999 (sRGB, D65 matrix and transfer curve)';

// --- colour and display brightness (functions of Teff only; tier = the method's) ------------

export interface BlackbodyColor {
  /** Linear-light sRGB (D65): negative channels clipped, scaled so the largest channel is 1. */
  readonly linear: readonly [number, number, number];
  /** The same colour sRGB-encoded, '#rrggbb' (for CSS / canvas). */
  readonly hex: string;
  /** CIE 1931 chromaticity coordinates. */
  readonly x: number;
  readonly y: number;
}

function unreliable(teffK: number): boolean {
  return !(teffK >= BLACKBODY_MIN_TEFF_K);
}

/**
 * CIE 1931 chromaticity of a blackbody (tabulated CMFs). Null below 2500 K (not a meaningful
 * colour for molecular atmospheres; flagged so the UI hides it).
 */
export function blackbodyChromaticity(teffK: number): Derived<{ x: number; y: number } | null> {
  const citation = `${CIE1931_CITATION}; ${PLANCK_CITE}`;
  if (unreliable(teffK)) {
    return {
      value: null,
      tier: 'model',
      method: `not computed below ${BLACKBODY_MIN_TEFF_K} K: the spectrum is far from a blackbody`,
      citation: `${citation}; ${BB_UNRELIABLE_CITE}`,
      flags: ['blackbody-unreliable'],
    };
  }
  const [X, Y, Z] = cieXYZ(teffK);
  const s = X + Y + Z;
  return {
    value: { x: X / s, y: Y / s },
    tier: 'model',
    method: `blackbody at ${fmt(teffK)} K summed over the tabulated CIE 1931 2° CMFs (360–830 nm, 5 nm)`,
    citation,
    flags: [],
  };
}

/** Visible colour of a blackbody (chromaticity only, no brightness). Null below 2500 K. */
export function blackbodyColor(teffK: number): Derived<BlackbodyColor | null> {
  const chroma = blackbodyChromaticity(teffK);
  if (!chroma.value) return { ...chroma, value: null };
  const rgb = xyzToLinearSrgb(cieXYZ(teffK)).map((v) => Math.max(0, v));
  const max = Math.max(...rgb);
  const linear = rgb.map((v) => v / max) as [number, number, number];
  const hex = '#' + linear.map((v) => Math.round(encodeSrgb(v) * 255).toString(16).padStart(2, '0')).join('');
  return {
    value: { linear, hex, x: chroma.value.x, y: chroma.value.y },
    tier: 'model',
    method: `${chroma.method}; XYZ → linear sRGB (D65), negatives clipped, normalised to the largest channel`,
    citation: `${chroma.citation}; ${SRGB_CITE}`,
    flags: [],
  };
}

/** CIE luminance Y of a blackbody surface (arbitrary units: only ratios are used). */
function surfaceLuminance(T: number): number {
  return cieXYZ(T)[1];
}

/**
 * Display brightness in [0.05, 1]: 1 + log10(Y(T) / Y(5772 K)) / 8, i.e. eight decades of visible
 * surface brightness mapped onto the display range. Tier 'display': it is NOT photometry.
 */
export function displayBrightness(teffK: number): Derived<number> {
  const cite = `${CIE1931_CITATION}; ${PLANCK_CITE}; mapping: WS7 display convention`;
  if (!(teffK > 0)) {
    return { value: 0.05, tier: 'display', method: 'no temperature: dimmest display level', citation: cite, flags: ['missing-input'] };
  }
  const ratio = surfaceLuminance(teffK) / surfaceLuminance(PHYS.TeffSun);
  const v = ratio > 0 ? 1 + Math.log10(ratio) / 8 : 0;
  return {
    value: Math.min(1, Math.max(0.05, v)),
    tier: 'display',
    method: 'clamp(1 + log10(Y(T)/Y(5772 K))/8, 0.05, 1): visible surface brightness relative to the Sun, 8 decades over the display range',
    citation: cite,
    flags: unreliable(teffK) ? ['blackbody-unreliable'] : [],
  };
}

/**
 * Fraction of a blackbody's surface flux emitted in [loUm, hiUm]: ∫B_λ dλ / (σT⁴/π), midpoint
 * quadrature in ln λ (default 4000 steps). Kept below 2500 K as a flagged model diagnostic.
 */
export function bandFraction(teffK: number, loUm: number, hiUm: number, steps = 4000): Derived<number | null> {
  const method = `∫B_λ dλ over ${fmt(loUm)}–${fmt(hiUm)} µm / (σT⁴/π), blackbody at ${fmt(teffK)} K, ${steps}-step log-λ quadrature`;
  if (!(teffK > 0) || !(hiUm > loUm && loUm > 0)) {
    return { value: null, tier: 'model', method, citation: PLANCK_CITE, flags: ['missing-input'] };
  }
  const total = (PHYS.sigma * teffK ** 4) / Math.PI;
  const value = bandRadiance(teffK, loUm * 1e-6, hiUm * 1e-6, Math.max(2000, steps)) / total;
  return {
    value,
    tier: 'model',
    method,
    citation: unreliable(teffK) ? `${PLANCK_CITE}; ${BB_UNRELIABLE_CITE}` : PLANCK_CITE,
    flags: unreliable(teffK) ? ['blackbody-unreliable'] : [],
  };
}

/**
 * Blackbody AB magnitude at one wavelength: F_ν = π B_ν(T) (R/d)², AB = −2.5 log10(F_ν / 3631 Jy).
 * A diagnostic primitive: below 2500 K the number is still returned but flagged
 * 'blackbody-unreliable' and must not be displayed (spherexPrediction returns no AB there).
 */
export function blackbodyAbMag(teffK: number, radiusKm: number, distancePc: number, lambdaUm: number): Derived<number | null> {
  const method = `F_ν = π B_ν(T)(R/d)² at ${fmt(lambdaUm)} µm, T = ${fmt(teffK)} K; AB = −2.5 log10(F_ν / 3631 Jy)`;
  const citation = `${PLANCK_CITE}; Oke & Gunn 1983, ApJ 266, 713 (AB system)`;
  if (!(teffK > 0 && radiusKm > 0 && distancePc > 0 && lambdaUm > 0)) {
    return { value: null, tier: 'model', method, citation, flags: ['missing-input'] };
  }
  const value = abFromFnu(fluxDensityNu(teffK, radiusKm, distancePc, lambdaUm));
  if (unreliable(teffK)) {
    return {
      value,
      tier: 'model',
      method: `${method}; diagnostic only, not for display below ${BLACKBODY_MIN_TEFF_K} K`,
      citation: `${citation}; ${BB_UNRELIABLE_CITE}`,
      flags: ['blackbody-unreliable'],
    };
  }
  return { value, tier: 'model', method, citation, flags: [] };
}

function fluxDensityNu(teffK: number, radiusKm: number, distancePc: number, lambdaUm: number): number {
  const ratio = (radiusKm * 1e3) / (distancePc * PHYS.pc);
  return Math.PI * planckNu(PHYS.c / (lambdaUm * 1e-6), teffK) * ratio * ratio;
}

function abFromFnu(fnu: number): number | null {
  return fnu > 0 ? -2.5 * Math.log10(fnu / (PHYS.abZeroJy * PHYS.jansky)) : null;
}

// --- limb darkening (M2) ---------------------------------------------------------------------

/** Grey Eddington atmosphere: T(τ) = Teff (3/4 (τ + 2/3))^(1/4); Eddington–Barbier: I(μ) ≈ B(T(τ = μ)). */
function eddingtonT(teffK: number, mu: number): number {
  return teffK * Math.pow(0.75 * (mu + 2 / 3), 0.25);
}

const LIMB_CITE =
  'Eddington–Barbier relation with a grey Eddington atmosphere, T⁴(τ) = ¾Teff⁴(τ + ⅔) (Mihalas 1978, Stellar Atmospheres; Gray 2005, The Observation and Analysis of Stellar Photospheres)';

/**
 * Limb-darkening table for the star shader: n entries (μ = i/(n−1), from the limb μ = 0 to the
 * disc centre μ = 1), each the linear-sRGB intensity I(μ)/I(1) per channel, packed as
 * [r0, g0, b0, r1, g1, b1, ...]. Limb reddening follows from the cooler T at small μ.
 * Tier 'model': real M-dwarf and Mira atmospheres are molecular, not grey.
 */
export function limbDarkeningLut(teffK: number, n = 16): Derived<Float32Array> {
  const count = Math.max(2, Math.floor(n));
  const out = new Float32Array(count * 3);
  const rgbAt = (mu: number) => xyzToLinearSrgb(cieXYZ(eddingtonT(teffK, mu))).map((v) => Math.max(0, v));
  const ref = rgbAt(1);
  const yRef = surfaceLuminance(eddingtonT(teffK, 1));
  for (let i = 0; i < count; i++) {
    const mu = i / (count - 1);
    const rgb = rgbAt(mu);
    const yRatio = yRef > 0 ? surfaceLuminance(eddingtonT(teffK, mu)) / yRef : 0;
    for (let ch = 0; ch < 3; ch++) out[i * 3 + ch] = ref[ch] > 0 ? rgb[ch] / ref[ch] : yRatio;
  }
  return {
    value: out,
    tier: 'model',
    method: `I(μ)/I(1) per linear-sRGB channel, B_λ(T(τ = μ)) summed over the CIE 1931 CMFs, ${count} samples μ = i/${count - 1}`,
    citation: `${LIMB_CITE}; ${CIE1931_CITATION}`,
    flags: unreliable(teffK) ? ['blackbody-unreliable'] : [],
  };
}

/** Monochromatic limb darkening I_λ(μ)/I_λ(1) of the same grey-atmosphere model. */
export function limbDarkeningAt(teffK: number, lambdaNm: number, mu: number): Derived<number> {
  const m = Math.min(1, Math.max(0, mu));
  const lam = lambdaNm * 1e-9;
  const ref = planckLambda(lam, eddingtonT(teffK, 1));
  return {
    value: ref > 0 ? planckLambda(lam, eddingtonT(teffK, m)) / ref : 0,
    tier: 'model',
    method: `B_λ(T(τ = μ))/B_λ(T(τ = 1)) at ${fmt(lambdaNm)} nm, μ = ${fmt(m)}`,
    citation: LIMB_CITE,
    flags: [],
  };
}

// --- Fact → parameter mapping and input tiers ------------------------------------------------

export type BodyParam = 'teff' | 'radius' | 'mass' | 'spectralType' | 'semiMajorAxis';

/**
 * How Facts are matched to body fields (by label, case-insensitive, anchored at the start):
 *   teff          'Temperature …', 'Effective temperature …', 'Teff …'
 *   radius        'Radius …'  (disks: also 'Dust disk radius …', 'Disk radius …')
 *   mass          'Mass …', 'Minimum mass …' (the latter flags a lower bound, M sin i)
 *   spectralType  'Spectral type …'
 *   semiMajorAxis 'Orbit size …', 'Semi-major axis …'
 *   distance      'Distance …' (any body of the system, compared with SystemModel.motion.distance_pc)
 * Labels such as 'Projected separation', 'Separation from A' or 'Gas (CO) disk radius' do NOT match:
 * they are not the drawn quantity. Unmatched fields fall to 'illustrative'.
 */
export const FACT_LABEL_PATTERNS = {
  teff: /^((effective\s+)?temperature|t\s*_?eff)\b/i,
  radius: /^radius\b/i,
  diskRadius: /^((dust\s+)?disk\s+)?radius\b/i,
  mass: /^(minimum\s+)?mass\b/i,
  spectralType: /^spectral\s+type\b/i,
  semiMajorAxis: /^(orbit\s+size|semi-?major\s+axis)\b/i,
  distance: /^distance\b/i,
} as const;

/** Words in a Fact label or source that weaken it: ILLUSTRATIVE first, then MODEL. */
const ILLUSTRATIVE_WORDS = /illustrativ|drawing value|placeholder|arbitrary/i;
const MODEL_WORDS = /estimat|model|calculated from|not measured/i;
const LOWER_BOUND_LABEL = /^minimum\s+mass\b|m\s*sin\s*i/i;

/** Unit (lower-case) → factor to the body field's unit (K, km, kg, AU, pc). */
const UNITS: Record<'teff' | 'radius' | 'mass' | 'semiMajorAxis' | 'distance', Record<string, number>> = {
  teff: { k: 1, kelvin: 1 },
  radius: {
    km: 1,
    'solar radii': PHYS.RSun / 1e3,
    'solar radius': PHYS.RSun / 1e3,
    'jupiter radii': PHYS.RJup / 1e3,
    'jupiter radius': PHYS.RJup / 1e3,
    'earth radii': PHYS.REarth / 1e3,
    'earth radius': PHYS.REarth / 1e3,
    au: PHYS.au / 1e3,
  },
  mass: {
    kg: 1,
    'solar masses': M_SUN,
    'solar mass': M_SUN,
    'jupiter masses': M_JUP,
    'jupiter mass': M_JUP,
    'earth masses': M_EARTH,
    'earth mass': M_EARTH,
  },
  semiMajorAxis: { au: 1 },
  distance: { pc: 1, parsec: 1, parsecs: 1 },
};

const PARAM_NAME: Record<BodyParam | 'distance', string> = {
  teff: 'Teff',
  radius: 'radius',
  mass: 'mass',
  spectralType: 'spectral type',
  semiMajorAxis: 'semi-major axis',
  distance: 'distance',
};

export interface ParamTier extends Derived<number | string | null> {
  readonly param: BodyParam | 'distance';
  /** The Fact that backs the drawn value (the strongest match), if any. */
  readonly fact: Fact | null;
}

interface ParsedNumbers {
  points: { v: number; err: number }[];
  ranges: [number, number][];
}

/** Numbers in a Fact value: '3195 ± 28', '6.5 (+0.7/−0.6)', '~2000–3300', '~250–300 (best fit 285)'. */
function parseFactNumbers(text: string): ParsedNumbers {
  let s = text.replace(/−/g, '-').replace(/[–—]/g, '–').replace(/(\d),(?=\d{3}\b)/g, '$1');
  const points: { v: number; err: number }[] = [];
  const ranges: [number, number][] = [];
  const num = '(\\d+(?:\\.\\d+)?)';
  s = s.replace(new RegExp(`${num}\\s*±\\s*${num}`, 'g'), (_, v, e) => {
    points.push({ v: +v, err: +e });
    return ' ';
  });
  s = s.replace(new RegExp(`${num}\\s*\\(\\s*\\+\\s*${num}\\s*/\\s*-\\s*${num}\\s*\\)`, 'g'), (_, v, up, lo) => {
    points.push({ v: +v, err: Math.max(+up, +lo) });
    return ' ';
  });
  s = s.replace(new RegExp(`${num}\\s*(?:–|\\bto\\b)\\s*${num}|${num}-${num}`, 'g'), (_, a, b, c, d) => {
    const lo = +(a ?? c);
    const hi = +(b ?? d);
    ranges.push([Math.min(lo, hi), Math.max(lo, hi)]);
    return ' ';
  });
  for (const m of s.matchAll(/(?<![\w.])-?\d+(?:\.\d+)?(?:e[+-]?\d+)?/gi)) points.push({ v: +m[0], err: 0 });
  return { points, ranges };
}

/** 'point' when the drawn value is one the Fact states, 'range' when it only falls inside a range. */
function matchNumbers(v: number, parsed: ParsedNumbers): 'point' | 'range' | 'none' {
  if (parsed.points.some((p) => Math.abs(v - p.v) <= Math.max(p.err, 0.05 * Math.abs(p.v)))) return 'point';
  if (parsed.ranges.some(([lo, hi]) => v >= lo * 0.98 && v <= hi * 1.02)) return 'range';
  return 'none';
}

/** Letter + subtype(s) + luminosity class, for comparing spectral-type strings. */
function spectralKey(raw: string): string {
  const p = parseSpectralType(raw);
  return p ? `${p.letter}${p.subtype ?? ''}${p.subtypeMax !== null ? `-${p.letterMax}${p.subtypeMax}` : ''}${p.luminosityClass ?? ''}` : raw.trim().toLowerCase();
}

function drawnValue(body: Body, param: BodyParam): number | string | null {
  switch (param) {
    case 'teff':
      return body.teff_k;
    case 'radius':
      return body.radius_km;
    case 'mass':
      return body.mass_kg;
    case 'spectralType':
      return body.spectral_type;
    case 'semiMajorAxis':
      return body.orbit ? body.orbit.semi_major_axis_au : null;
  }
}

function assessFact(fact: Fact, param: BodyParam | 'distance', drawn: number | string): ParamTier {
  const why: string[] = [];
  const tiers: Tier[] = [fact.verified ? 'measured' : 'illustrative'];
  why.push(fact.verified ? `verified Fact '${fact.label}'` : `unverified Fact '${fact.label}'`);
  const text = `${fact.label} ${fact.source ?? ''}`;
  if (ILLUSTRATIVE_WORDS.test(text)) {
    tiers.push('illustrative');
    why.push('labelled illustrative');
  } else if (MODEL_WORDS.test(text)) {
    tiers.push('model');
    why.push('labelled as an estimate/model value');
  }
  if (param === 'spectralType') {
    if (spectralKey(String(drawn)) !== spectralKey(fact.value)) {
      tiers.push('illustrative');
      why.push(`drawn '${drawn}' differs from the Fact '${fact.value}'`);
    }
  } else {
    const factor = UNITS[param][(fact.unit ?? '').trim().toLowerCase().replace(/\s+/g, ' ')];
    if (factor === undefined || typeof drawn !== 'number') {
      tiers.push('illustrative');
      why.push(`unit '${fact.unit ?? ''}' not recognised: the drawn value cannot be checked`);
    } else {
      const match = matchNumbers(drawn / factor, parseFactNumbers(fact.value));
      if (match === 'range') {
        tiers.push('range-pick');
        why.push(`drawn ${fmt(drawn / factor)} ${fact.unit} is one value picked inside the range '${fact.value}'`);
      } else if (match === 'none') {
        tiers.push('illustrative');
        why.push(`drawn ${fmt(drawn / factor)} ${fact.unit} does not match '${fact.value}'`);
      }
    }
  }
  const lowerBound = param === 'mass' && LOWER_BOUND_LABEL.test(fact.label);
  if (lowerBound) why.push('a minimum mass (M sin i): a lower bound');
  return {
    param,
    value: drawn,
    tier: weakestTier(tiers),
    method: why.join('; '),
    citation: fact.source ?? 'no source given',
    flags: lowerBound ? ['lower-bound'] : [],
    fact,
  };
}

function bestOf(candidates: ParamTier[]): ParamTier {
  return candidates.reduce((best, c) => (rank(c.tier) < rank(best.tier) ? c : best));
}

function noFact(param: BodyParam | 'distance', drawn: number | string | null, why: string, flags: Flag[] = []): ParamTier {
  return {
    param,
    value: drawn,
    tier: 'illustrative',
    method: why,
    citation: 'none',
    flags: drawn === null ? ['missing-input', ...flags] : flags,
    fact: null,
  };
}

/**
 * Evidence tier of one drawn body field. 'measured' only for a verified Fact matched by label
 * (FACT_LABEL_PATTERNS) whose label/source does not say estimate/model/illustrative and whose
 * value agrees with the drawn number (within its error, 5 %, or as one of the stated values);
 * a number picked inside a published range is 'range-pick'; anything else is weaker.
 */
export function paramTier(body: Body, param: BodyParam): ParamTier {
  const drawn = drawnValue(body, param);
  if (drawn === null) return noFact(param, null, `no ${PARAM_NAME[param]} on the body`);
  if (param === 'semiMajorAxis' && body.orbit?.quality && body.orbit.quality !== 'fitted') {
    return noFact(param, drawn, `orbit is '${body.orbit.quality}' (not a fitted solution)`, ['assumed-orbit']);
  }
  const pattern = param === 'radius' && body.kind === 'disk' ? FACT_LABEL_PATTERNS.diskRadius : FACT_LABEL_PATTERNS[param];
  const facts = body.facts.filter((f) => pattern.test(f.label.trim()));
  if (!facts.length) return noFact(param, drawn, `no Fact backs the drawn ${PARAM_NAME[param]}`);
  return bestOf(facts.map((f) => assessFact(f, param, drawn)));
}

/** Evidence tier of the system distance (SystemModel.motion.distance_pc) from 'Distance' Facts. */
export function distanceTier(system: SystemModel): ParamTier {
  const drawn = system.motion?.distance_pc ?? null;
  if (drawn === null) return noFact('distance', null, 'the system has no distance');
  const facts = system.bodies.flatMap((b) => b.facts).filter((f) => FACT_LABEL_PATTERNS.distance.test(f.label.trim()));
  if (!facts.length) return noFact('distance', drawn, 'no Distance Fact backs the system distance');
  return bestOf(facts.map((f) => assessFact(f, 'distance', drawn)));
}

function inputsText(inputs: readonly ParamTier[]): string {
  return 'inputs: ' + inputs.map((i) => `${PARAM_NAME[i.param]} ${i.tier}`).join(', ');
}

function inputFlags(inputs: readonly ParamTier[]): Flag[] {
  return inputs.some((i) => i.flags.includes('lower-bound')) ? ['lower-bound'] : [];
}

/** A null result: an input is missing (or the quantity is not modelled for this body). */
function missing(method: string, citation: string, flag: Flag = 'missing-input', tier: Tier = 'illustrative'): Derived<null> {
  return { value: null, tier, method, citation, flags: [flag] };
}

// --- derived stellar quantities --------------------------------------------------------------

const isStellar = (b: Body) => b.kind === 'star' || b.kind === 'brown_dwarf';

/** Bolometric luminosity L/L_sun = 4πR²σTeff⁴ / L_sun. */
export function luminosity(body: Body): Derived<number | null> {
  const citation = `${STEFAN_BOLTZMANN}; ${PHYS_CITATION}`;
  if (body.kind === 'disk') return missing('not defined for a disk', citation, 'not-modelled', 'model');
  const R = paramTier(body, 'radius');
  const T = paramTier(body, 'teff');
  if (body.radius_km === null || body.teff_k === null) return missing('needs radius and Teff', citation);
  const r = body.radius_km * 1e3;
  return {
    value: (4 * Math.PI * r * r * PHYS.sigma * body.teff_k ** 4) / PHYS.LSun,
    tier: derivedTier([R.tier, T.tier]),
    method: `L = 4πR²σTeff⁴ in nominal solar luminosities (3.828e26 W); ${inputsText([R, T])}`,
    citation,
    flags: [],
  };
}

/** Surface gravity log10(g / cm s⁻²), g = GM/R². */
export function surfaceGravity(body: Body): Derived<number | null> {
  const citation = `Newtonian gravity; ${PHYS_CITATION}`;
  if (body.kind === 'disk') return missing('not defined for a disk', citation, 'not-modelled', 'model');
  const M = paramTier(body, 'mass');
  const R = paramTier(body, 'radius');
  if (body.mass_kg === null || body.radius_km === null) return missing('needs mass and radius', citation);
  const r = body.radius_km * 1e3;
  return {
    value: Math.log10(((PHYS.G * body.mass_kg) / (r * r)) * 100),
    tier: derivedTier([M.tier, R.tier]),
    method: `log g = log10(GM/R²) in cgs; ${inputsText([M, R])}`,
    citation,
    flags: inputFlags([M, R]),
  };
}

/** Pressure scale height H_p = kT/(μ m_H g) in km, μ = 1.3 (MODEL). Stars only. */
export function pressureScaleHeight(body: Body): Derived<number | null> {
  const citation = `ideal-gas hydrostatic scale height (e.g. Gray 2005, The Observation and Analysis of Stellar Photospheres); ${PHYS_CITATION}`;
  if (body.kind !== 'star') return missing('computed for stars only (μ = 1.3 assumes a neutral H + He photosphere)', citation, 'not-modelled', 'model');
  const T = paramTier(body, 'teff');
  const M = paramTier(body, 'mass');
  const R = paramTier(body, 'radius');
  if (body.teff_k === null || body.mass_kg === null || body.radius_km === null) return missing('needs Teff, mass and radius', citation);
  const r = body.radius_km * 1e3;
  const g = (PHYS.G * body.mass_kg) / (r * r);
  return {
    value: (PHYS.k * body.teff_k) / (MEAN_MOLECULAR_WEIGHT * PHYS.mH * g) / 1e3,
    tier: derivedTier([T.tier, M.tier, R.tier], 'model'),
    method: `H_p = kTeff/(μ m_H g), μ = ${MEAN_MOLECULAR_WEIGHT} (assumed neutral H + He; molecular atmospheres have larger μ); ${inputsText([T, M, R])}`,
    citation,
    flags: inputFlags([M]),
  };
}

/** Convection cells for the star shader; `value` = cells across the disc, 2R / x (null when unknown). */
export interface GranulationParams extends Derived<number | null> {
  /** True when the cells would be resolvable on the drawn sphere (fewer than GRANULATION_MAX_CELLS across). */
  readonly draw: boolean;
  /** Cell size x = 10 H_p (km). */
  readonly cellSizeKm: number | null;
  /** Turnover time τ = x / (5 km/s), days (MODEL, order of magnitude). */
  readonly turnoverDays: Derived<number | null>;
  /** Intensity contrast of the drawn pattern, ±15 % (ILLUSTRATIVE). */
  readonly contrast: Derived<number>;
  /** Deterministic noise seed from the body id (FNV-1a). */
  readonly seed: number;
}

const GRANULE_CITE =
  'cell size ≈ 10 H_p, solar-calibrated (Trampedach et al. 2013, ApJ 769, 18; Freytag et al. 2017, A&A 600, A137); giant cells: Schwarzschild 1975, ApJ 195, 137';

/** 32-bit FNV-1a hash of a string (stable noise seed). */
function fnv1a(s: string): number {
  let h = 2166136261;
  for (let i = 0; i < s.length; i++) h = Math.imul(h ^ s.charCodeAt(i), 16777619);
  return h >>> 0;
}

/** Convection-cell parameters for the star shader (M2). */
export function granulationParams(body: Body): GranulationParams {
  const hp = pressureScaleHeight(body);
  const contrast: Derived<number> = {
    value: 0.15,
    tier: 'illustrative',
    method: '±15 % intensity contrast chosen for visibility',
    citation: 'illustrative drawing choice',
    flags: [],
  };
  const seed = fnv1a(body.id);
  const cellSizeKm = hp.value === null ? null : 10 * hp.value;
  if (cellSizeKm === null || body.radius_km === null) {
    return {
      value: null,
      tier: hp.tier,
      method: `no cell count: ${hp.method}`,
      citation: GRANULE_CITE,
      flags: hp.flags,
      draw: false,
      cellSizeKm: null,
      turnoverDays: { ...hp, value: null },
      contrast,
      seed,
    };
  }
  const cells = (2 * body.radius_km) / cellSizeKm;
  const draw = cells < GRANULATION_MAX_CELLS;
  return {
    value: cells,
    tier: weakestTier([hp.tier, 'model']),
    method: `2R / (10 H_p) = ${fmt(cells)} cells across; ${draw ? 'resolvable: drawn' : `too small to draw (≥ ${GRANULATION_MAX_CELLS})`}; H_p: ${hp.method}`,
    citation: GRANULE_CITE,
    flags: hp.flags,
    draw,
    cellSizeKm,
    turnoverDays: {
      value: cellSizeKm / 5 / 86400,
      tier: weakestTier([hp.tier, 'model']),
      method: 'τ = x / v with v = 5 km/s (assumed order-of-magnitude convective velocity)',
      citation: 'order of magnitude of photospheric convective velocities (Freytag et al. 2017, A&A 600, A137)',
      flags: hp.flags,
    },
    contrast,
    seed,
  };
}

// --- orbits: host star, equilibrium temperature, insolation, separations --------------------

/** The star a body is lit by, and the body (itself or an ancestor) that orbits that star. */
function hostStar(body: Body, system: SystemModel): { host: Body; orbiter: Body } | null {
  const byId = new Map(system.bodies.map((b) => [b.id, b]));
  let orbiter = body;
  for (let i = 0; i <= system.bodies.length && orbiter.orbit; i++) {
    const parent = byId.get(orbiter.orbit.parent);
    if (!parent) return null;
    if (parent.kind === 'star') return { host: parent, orbiter };
    orbiter = parent;
  }
  return null;
}

const IRRADIATED: ReadonlySet<Body['kind']> = new Set<Body['kind']>(['planet', 'dwarf_planet', 'moon', 'asteroid', 'comet', 'tno', 'unknown']);

const TEQ_CITE =
  'radiative balance with full heat redistribution (Seager 2010, Exoplanet Atmospheres, Princeton UP; Cowan & Agol 2011, ApJ 729, 54)';

/**
 * Equilibrium temperature T_eq = T_star sqrt(R_star / 2a) (1 − A_B)^(1/4) (K), full redistribution, at the
 * semi-major axis (eccentricity ignored). MODEL: the Bond albedo is assumed.
 */
export function equilibriumTemperature(body: Body, system: SystemModel, bondAlbedo = 0): Derived<number | null> {
  if (!IRRADIATED.has(body.kind)) return missing('computed for planets and small bodies only', TEQ_CITE, 'not-modelled', 'model');
  const hs = hostStar(body, system);
  if (!hs || hs.host.teff_k === null || hs.host.radius_km === null || !hs.orbiter.orbit) {
    return missing('needs a host star with Teff and radius', TEQ_CITE);
  }
  const T = paramTier(hs.host, 'teff');
  const R = paramTier(hs.host, 'radius');
  const a = paramTier(hs.orbiter, 'semiMajorAxis');
  const aM = hs.orbiter.orbit.semi_major_axis_au * PHYS.au;
  const value = hs.host.teff_k * Math.sqrt((hs.host.radius_km * 1e3) / (2 * aM)) * Math.pow(1 - bondAlbedo, 0.25);
  return {
    value,
    tier: derivedTier([T.tier, R.tier, a.tier], 'model'),
    method: `T_eq = T*·sqrt(R*/2a)·(1 − A_B)^¼ with A_B = ${bondAlbedo} (assumed), full redistribution, a = ${fmt(hs.orbiter.orbit.semi_major_axis_au)} AU around ${hs.host.name}; host ${inputsText([T, R])}, a ${a.tier}`,
    citation: TEQ_CITE,
    flags: a.flags.includes('assumed-orbit') ? ['assumed-orbit'] : [],
  };
}

/** Insolation S/S_earth = (L_star / L_sun) / (a/AU)². */
export function insolation(body: Body, system: SystemModel): Derived<number | null> {
  const citation = `inverse-square law; L* from the ${STEFAN_BOLTZMANN}; ${PHYS_CITATION}`;
  if (!IRRADIATED.has(body.kind)) return missing('computed for planets and small bodies only', citation, 'not-modelled', 'model');
  const hs = hostStar(body, system);
  if (!hs || !hs.orbiter.orbit) return missing('needs a host star', citation);
  const L = luminosity(hs.host);
  if (L.value === null) return missing('needs the host luminosity (Teff and radius)', citation);
  const a = paramTier(hs.orbiter, 'semiMajorAxis');
  const au = hs.orbiter.orbit.semi_major_axis_au;
  return {
    value: L.value / (au * au),
    tier: derivedTier([L.tier, a.tier]),
    method: `S/S⊕ = (L*/L☉)/(a/AU)², L* = ${fmt(L.value)} L☉ (${L.tier}), a = ${fmt(au)} AU (${a.tier})`,
    citation,
    flags: a.flags.includes('assumed-orbit') ? ['assumed-orbit'] : [],
  };
}

/** Angular diameter 2R/d (milliarcseconds). */
export function angularDiameterMas(body: Body, system: SystemModel): Derived<number | null> {
  const citation = `small-angle geometry; ${PHYS_CITATION}`;
  const R = paramTier(body, 'radius');
  const d = distanceTier(system);
  if (body.radius_km === null || d.value === null) return missing('needs radius and distance', citation);
  const rad = (2 * body.radius_km * 1e3) / (Number(d.value) * PHYS.pc);
  return {
    value: (rad * 180 * 3600 * 1000) / Math.PI,
    tier: derivedTier([R.tier, d.tier]),
    method: `θ = 2R/d; ${inputsText([R, d])}`,
    citation,
    flags: [],
  };
}

/**
 * Bounds on the angular separation from the parent, [0, a(1+e)/d] arcsec: orientation-free,
 * since projection can only shorten the true separation (largest at apoapsis).
 */
export function separationBoundsArcsec(body: Body, system: SystemModel): Derived<readonly [number, number] | null> {
  const citation = 'Keplerian apoapsis a(1+e); 1 AU at 1 pc subtends 1 arcsec';
  if (!body.orbit) return missing('no orbit', citation, 'not-modelled', 'model');
  const a = paramTier(body, 'semiMajorAxis');
  const d = distanceTier(system);
  if (d.value === null) return missing('needs the system distance', citation);
  const max = (body.orbit.semi_major_axis_au * (1 + body.orbit.eccentricity)) / Number(d.value);
  return {
    value: [0, max],
    tier: derivedTier([a.tier, d.tier]),
    method: `[0, a(1+e)/d] with e = ${fmt(body.orbit.eccentricity)} as drawn (inclination and phase unknown or not used); ${inputsText([a, d])}`,
    citation,
    flags: a.flags.includes('assumed-orbit') ? ['assumed-orbit'] : [],
  };
}

// --- classifiers -----------------------------------------------------------------------------

export type MassClass = 'Terran' | 'Neptunian' | 'Jovian' | 'Stellar';

/** Mass class of Chen & Kipping 2017: Terran < 2.0 M⊕ < Neptunian < 0.41 M_J < Jovian < 0.08 M☉ < Stellar. */
export function massClass(body: Body): Derived<MassClass | null> {
  const citation = 'Chen & Kipping 2017, ApJ 834, 17 (transitions at 2.0 M⊕, 0.41 M_J, 0.08 M☉)';
  if (body.kind === 'disk') return missing('not defined for a disk', citation, 'not-modelled', 'model');
  const M = paramTier(body, 'mass');
  if (body.mass_kg === null) return missing('needs a mass', citation);
  const m = body.mass_kg;
  const cls: MassClass = m < 2.0 * M_EARTH ? 'Terran' : m < 0.41 * M_JUP ? 'Neptunian' : m < 0.08 * M_SUN ? 'Jovian' : 'Stellar';
  const lower = M.flags.includes('lower-bound');
  return {
    value: cls,
    tier: derivedTier([M.tier]),
    method: `${cls} for ${fmt(m / M_EARTH)} M⊕ (${M.tier})${cls === 'Jovian' ? '; in this scheme the Jovian class includes brown dwarfs' : ''}${lower ? '; from a minimum mass, so the class is a lower bound' : ''}`,
    citation,
    flags: lower ? ['lower-bound'] : [],
  };
}

export type SpectralLetter = 'O' | 'B' | 'A' | 'F' | 'G' | 'K' | 'M' | 'L' | 'T' | 'Y';
export type EvolutionaryStage =
  | 'main-sequence'
  | 'subgiant'
  | 'giant'
  | 'bright giant'
  | 'supergiant'
  | 'subdwarf'
  | 'pre-main-sequence'
  | 'ultracool dwarf'
  | 'brown dwarf'
  | 'unknown';

export interface SpectralType {
  readonly raw: string;
  readonly letter: SpectralLetter;
  readonly subtype: number | null;
  /** Upper end of a range such as 'M5e–M9eIII' or 'K1–K4' (null when not a range). */
  readonly letterMax: SpectralLetter | null;
  readonly subtypeMax: number | null;
  /** MK luminosity class ('V', 'III', ...), null when absent. */
  readonly luminosityClass: string | null;
  readonly stage: EvolutionaryStage;
  /** Lower-case suffixes such as 'e' (emission lines). */
  readonly peculiarities: readonly string[];
  /** '~', '(approx.)', ':' or '?' in the string. */
  readonly approximate: boolean;
}

const STAGE_BY_CLASS: Record<string, EvolutionaryStage> = {
  '0': 'supergiant',
  'Ia+': 'supergiant',
  Ia: 'supergiant',
  Iab: 'supergiant',
  Ib: 'supergiant',
  I: 'supergiant',
  II: 'bright giant',
  III: 'giant',
  IV: 'subgiant',
  V: 'main-sequence',
  VI: 'subdwarf',
};

/**
 * Parse an MK-style spectral type: letter + subtype (+ range) + luminosity class + suffixes.
 * 'M5e–M9eIII' → M giant; 'K1–K4 (T Tauri)' → K pre-main-sequence; 'Y4 (approx.)' → Y brown dwarf.
 * Returns null when no spectral letter is found. (Plain parser; spectralClass adds the tier.)
 */
function parseSpectralType(raw: string): SpectralType | null {
  const approximate = /~|approx|:|\?/i.test(raw);
  const preMainSequence = /t\s*tau|pre-?main|\bpms\b|\byso\b/i.test(raw);
  let s = raw.replace(/\([^)]*\)/g, ' ').replace(/[−–—]/g, '-').replace(/~/g, '').trim();
  const first = /^([OBAFGKMLTY])(\d+(?:\.\d+)?)?([a-z]*)/.exec(s);
  if (!first) return null;
  const peculiarities: string[] = first[3] ? [first[3]] : [];
  s = s.slice(first[0].length);
  let letterMax: SpectralLetter | null = null;
  let subtypeMax: number | null = null;
  const range = /^\s*-\s*([OBAFGKMLTY])?(\d+(?:\.\d+)?)([a-z]*)/.exec(s);
  if (range) {
    letterMax = (range[1] ?? first[1]) as SpectralLetter;
    subtypeMax = +range[2];
    if (range[3]) peculiarities.push(range[3]);
    s = s.slice(range[0].length);
  }
  const lc = /^\s*(Ia\+|Iab|Ia|Ib|III|II|IV|I|VI|V|0)(?![A-Z])([a-z]*)/.exec(s);
  const luminosityClass = lc ? lc[1] : null;
  if (lc?.[2]) peculiarities.push(lc[2]);
  const letter = first[1] as SpectralLetter;
  let stage: EvolutionaryStage = 'unknown';
  if (preMainSequence) stage = 'pre-main-sequence';
  else if (luminosityClass) stage = STAGE_BY_CLASS[luminosityClass] ?? 'unknown';
  else if (letter === 'T' || letter === 'Y') stage = 'brown dwarf';
  else if (letter === 'L') stage = 'ultracool dwarf';
  return {
    raw,
    letter,
    subtype: first[2] !== undefined ? +first[2] : null,
    letterMax,
    subtypeMax,
    luminosityClass,
    stage,
    peculiarities: [...new Set(peculiarities)],
    approximate,
  };
}

/** Parsed spectral type of a body, with the tier of its 'Spectral type' Fact. */
export function spectralClass(body: Body): Derived<SpectralType | null> {
  const citation =
    'MK system (Morgan, Keenan & Kellman 1943); L/T dwarfs: Kirkpatrick 2005, ARA&A 43, 195; Y dwarfs: Cushing et al. 2011, ApJ 743, 50';
  if (!body.spectral_type) return missing('no spectral type', citation);
  const S = paramTier(body, 'spectralType');
  const parsed = parseSpectralType(body.spectral_type);
  if (!parsed) return missing(`'${body.spectral_type}' is not an MK-style type`, citation);
  return {
    value: parsed,
    tier: derivedTier([S.tier]),
    method: `parsed '${body.spectral_type}' → ${spectralKey(body.spectral_type)} (${parsed.stage}); ${inputsText([S])}`,
    citation,
    flags: [],
  };
}

// --- SPHEREx band predictions ------------------------------------------------------------------

export type SpherexReliability =
  | 'blackbody approx.'
  | 'illustrative inputs'
  | 'blackbody unreliable - not shown'
  | 'not modelled';

/**
 * How far the blackbody SPHEREx numbers of a body can be trusted:
 *   'blackbody approx.'                star or brown dwarf, Teff ≥ 2500 K, Teff, R and distance measured
 *   'illustrative inputs'              Teff ≥ 2500 K but Teff, R or distance is not measured (range pick,
 *                                      model or illustrative): numbers are shown with that tier
 *   'blackbody unreliable - not shown' Teff < 2500 K (L/T/Y dwarfs): molecular absorption and clouds
 *                                      move flux by magnitudes; no AB value is returned
 *   'not modelled'                     planets (reflected + thermal light), disks, or missing inputs
 */
export function spherexReliability(body: Body, system: SystemModel): Derived<SpherexReliability> {
  const citation = `${SPHEREX_BANDS_CITATION}; ${BB_UNRELIABLE_CITE}`;
  if (!isStellar(body)) {
    return { value: 'not modelled', tier: 'model', method: `${body.kind}: reflected and thermal light are not modelled`, citation, flags: ['not-modelled'] };
  }
  const T = paramTier(body, 'teff');
  const R = paramTier(body, 'radius');
  const d = distanceTier(system);
  if (body.teff_k === null || body.radius_km === null || d.value === null) {
    return { value: 'not modelled', tier: 'model', method: 'needs Teff, radius and distance', citation, flags: ['missing-input'] };
  }
  if (unreliable(body.teff_k)) {
    return {
      value: 'blackbody unreliable - not shown',
      tier: 'model',
      method: `Teff ${fmt(body.teff_k)} K < ${BLACKBODY_MIN_TEFF_K} K: a blackbody misplaces the flux of an L/T/Y dwarf by magnitudes`,
      citation,
      flags: ['blackbody-unreliable'],
    };
  }
  const inputs = [T, R, d];
  const allMeasured = inputs.every((i) => i.tier === 'measured');
  return {
    value: allMeasured ? 'blackbody approx.' : 'illustrative inputs',
    tier: derivedTier(inputs.map((i) => i.tier), 'model'),
    method: `${allMeasured ? 'blackbody of measured inputs' : 'blackbody of non-measured inputs'}; ${inputsText(inputs)}`,
    citation,
    flags: [],
  };
}

export interface SpherexBandEstimate {
  readonly detector: SpherexDetector;
  /** Blackbody fraction of the surface flux in the band (model; kept below 2500 K as a diagnostic). */
  readonly fraction: Derived<number | null>;
  /** Band-averaged AB magnitude; null unless the reliability is 'blackbody approx.' or 'illustrative inputs'. */
  readonly abMag: Derived<number | null>;
}

export interface SpherexPrediction extends Derived<readonly SpherexBandEstimate[]> {
  readonly reliability: SpherexReliability;
}

/**
 * Blackbody predictions for the six SPHEREx detectors: F_ν = π B_ν(T)(R/d)² averaged over the 17
 * log-uniform channels of each detector, AB = −2.5 log10(F_ν / 3631 Jy) (Oke & Gunn 1983).
 */
export function spherexPrediction(body: Body, system: SystemModel): SpherexPrediction {
  const rel = spherexReliability(body, system);
  const citation = `${PLANCK_CITE}; Oke & Gunn 1983, ApJ 266, 713 (AB); ${SPHEREX_BANDS_CITATION}`;
  const T = paramTier(body, 'teff');
  const showAb = rel.value === 'blackbody approx.' || rel.value === 'illustrative inputs';
  const d = distanceTier(system);
  const bands = SPHEREX_DETECTORS.map((det): SpherexBandEstimate => {
    const fr =
      isStellar(body) && body.teff_k !== null
        ? bandFraction(body.teff_k, det.lambdaMinUm, det.lambdaMaxUm)
        : missing(`${det.id}: ${rel.method}`, PLANCK_CITE, rel.flags[0] ?? 'not-modelled', 'model');
    const fraction: Derived<number | null> =
      fr.value === null ? fr : { ...fr, tier: derivedTier([T.tier], 'model'), method: `${fr.method}; ${inputsText([T])}` };
    if (!showAb || body.teff_k === null || body.radius_km === null || d.value === null) {
      return { detector: det, fraction, abMag: { value: null, tier: rel.tier, method: `${det.id}: ${rel.value} (${rel.method})`, citation, flags: rel.flags } };
    }
    const teff = body.teff_k;
    const radiusKm = body.radius_km;
    const dist = Number(d.value);
    const fnu = det.channelCentersUm.reduce((s, l) => s + fluxDensityNu(teff, radiusKm, dist, l), 0) / det.channelCentersUm.length;
    const ab = abFromFnu(fnu);
    const flags: Flag[] = ab !== null && ab < det.nonLinearityOnsetAB ? ['brighter-than-nonlinearity'] : [];
    return {
      detector: det,
      fraction,
      abMag: {
        value: ab,
        tier: rel.tier,
        method: `${det.id}: mean F_ν over ${det.channelCentersUm.length} log-uniform channels (${fmt(det.lambdaMinUm)}–${fmt(det.lambdaMaxUm)} µm); ${rel.value}; ${rel.method}${flags.length ? `; brighter than the non-linearity onset AB ${det.nonLinearityOnsetAB} (pre-launch model)` : ''}`,
        citation,
        flags,
      },
    };
  });
  return { value: bands, tier: rel.tier, method: rel.method, citation, flags: rel.flags, reliability: rel.value };
}

// --- body-level colour and visible light -------------------------------------------------------

/** Blackbody colour of a star or brown dwarf at its drawn Teff (null below 2500 K and for other kinds). */
export function bodyColor(body: Body): Derived<BlackbodyColor | null> {
  if (!isStellar(body)) return missing(`${body.kind}: reflected light, no blackbody colour`, SRGB_CITE, 'not-modelled', 'model');
  if (body.teff_k === null) return missing('no Teff', SRGB_CITE);
  const T = paramTier(body, 'teff');
  const c = blackbodyColor(body.teff_k);
  return { ...c, tier: derivedTier([T.tier], 'model'), method: `${c.method}; ${inputsText([T])}` };
}

/** Visible-light luminosity L × f(380–780 nm) of a blackbody, in L_sun (for glow scaling). */
export function visibleLuminosity(body: Body): Derived<number | null> {
  const L = luminosity(body);
  if (L.value === null || body.teff_k === null) return { ...L, value: null };
  const f = bandFraction(body.teff_k, VISIBLE_BAND_NM[0] / 1e3, VISIBLE_BAND_NM[1] / 1e3);
  if (f.value === null) return { ...f, value: null };
  return {
    value: L.value * f.value,
    tier: weakestTier([L.tier, f.tier]),
    method: `L × blackbody fraction in ${VISIBLE_BAND_NM[0]}–${VISIBLE_BAND_NM[1]} nm (${f.value.toExponential(2)}); ${L.method}`,
    citation: `${L.citation}; ${PLANCK_CITE}`,
    flags: [...L.flags, ...f.flags],
  };
}

// --- everything for one body (BodyPanel / M6) ----------------------------------------------------

export interface BodyDerivation {
  readonly inputs: {
    readonly teff: ParamTier;
    readonly radius: ParamTier;
    readonly mass: ParamTier;
    readonly spectralType: ParamTier;
    readonly semiMajorAxis: ParamTier;
    readonly distance: ParamTier;
  };
  readonly luminosity: Derived<number | null>;
  readonly visibleLuminosity: Derived<number | null>;
  readonly logG: Derived<number | null>;
  readonly scaleHeightKm: Derived<number | null>;
  readonly granulation: GranulationParams;
  readonly teqBondAlbedo0: Derived<number | null>;
  readonly teqBondAlbedo03: Derived<number | null>;
  readonly insolation: Derived<number | null>;
  readonly angularDiameterMas: Derived<number | null>;
  readonly separationArcsec: Derived<readonly [number, number] | null>;
  readonly massClass: Derived<MassClass | null>;
  readonly spectralClass: Derived<SpectralType | null>;
  readonly color: Derived<BlackbodyColor | null>;
  readonly displayBrightness: Derived<number | null>;
  readonly spherex: SpherexPrediction;
}

/** Every derived quantity of one body, each with its tier, method and citation. */
export function deriveBody(body: Body, system: SystemModel): BodyDerivation {
  return {
    inputs: {
      teff: paramTier(body, 'teff'),
      radius: paramTier(body, 'radius'),
      mass: paramTier(body, 'mass'),
      spectralType: paramTier(body, 'spectralType'),
      semiMajorAxis: paramTier(body, 'semiMajorAxis'),
      distance: distanceTier(system),
    },
    luminosity: luminosity(body),
    visibleLuminosity: visibleLuminosity(body),
    logG: surfaceGravity(body),
    scaleHeightKm: pressureScaleHeight(body),
    granulation: granulationParams(body),
    teqBondAlbedo0: equilibriumTemperature(body, system, 0),
    teqBondAlbedo03: equilibriumTemperature(body, system, 0.3),
    insolation: insolation(body, system),
    angularDiameterMas: angularDiameterMas(body, system),
    separationArcsec: separationBoundsArcsec(body, system),
    massClass: massClass(body),
    spectralClass: spectralClass(body),
    color: bodyColor(body),
    displayBrightness:
      isStellar(body) && body.teff_k !== null
        ? displayBrightness(body.teff_k)
        : missing('stars and brown dwarfs only', 'WS7 display convention', isStellar(body) ? 'missing-input' : 'not-modelled', 'display'),
    spherex: spherexPrediction(body, system),
  };
}

/** Compact number for method strings (4 significant figures). */
function fmt(x: number): string {
  return Number.isFinite(x) ? Number(x.toPrecision(4)).toString() : String(x);
}
