// Colour modes of the 3D scene (M3): what colour and brightness each body is drawn with, and the
// legend text that says how. Pure (no three.js, no DOM), so SystemViewer can show the legend from
// the main chunk and the mapping is unit-tested.
//
// 'ir' (DEFAULT) — SPHEREx false colour, 0.75–5 µm (user decision: the SPHEREx link is the point)
//   blue  = D1+D2 (0.746–1.650 µm)   green = D3+D4 (1.630–3.847 µm)   red = D5+D6 (3.811–5.010 µm)
//   Each channel is the frequency-averaged surface brightness  ⟨I_ν⟩ = Σ ∫B_λ dλ / Σ Δν  over the two
//   detectors (W m⁻² Hz⁻¹ sr⁻¹, the units of the SPHEREx MJy/sr images), from the astro.ts band
//   fractions of a blackbody at the catalog Teff (MODEL). The composite preserves colour (Lupton et
//   al. 2004, PASP 116, 133): all three channels of a body share one stretch factor, so the screen
//   ratios equal the ⟨I_ν⟩ ratios. The stretch is logarithmic over a FIXED 10 mag (4 decades) below
//   the brightest body × channel of the system (DISPLAY). Below 2500 K (L/T/Y dwarfs) the blackbody
//   hue is only a qualitative guide (tier MODEL, no numbers shown): molecular bands move the flux by
//   magnitudes (Burrows, Sudarsky & Lunine 2003, ApJ 596, 587). Planets and disks: emission and
//   reflected light are not modelled, so they are drawn as outlines.
// 'visible' — CIE 1931 2° colour of the blackbody for stars (astro.ts), brightness on the astro.ts
//   display scale (DISPLAY); brown dwarfs and planets: visible colour not computed (neutral).
import type { Body, SystemModel } from '../api/types';
import {
  bandFraction,
  BLACKBODY_MIN_TEFF_K,
  bodyColor as blackbodyBodyColor,
  bodyLimbDarkening,
  derivedTier,
  displayBrightness,
  granulationParams,
  limbDarkeningAt,
  luminosity,
  paramTier,
  PHYS,
  spherexReliability,
  visibleLuminosity,
  type Tier,
} from './astro';
import { bodyColor as baseColor, NEUTRAL_ALBEDO, surfacePattern } from './appearance';
import { drawsPulsation, PULSATION_RADIUS_AMPLITUDE } from './sceneLayout';
import { SPHEREX_DETECTORS, type SpherexDetector, type SpherexDetectorId } from './spherexBands';

export type ColorMode = 'ir' | 'visible';

/** User decision: SPHEREx false colour is the default on every 3D view. */
export const DEFAULT_COLOR_MODE: ColorMode = 'ir';

export const COLOR_MODE_LABEL: Record<ColorMode, string> = {
  ir: 'SPHEREx IR (false colour)',
  visible: 'Visible (CIE 1931, blackbody)',
};

/** Dynamic range of the IR stretch: bodies more than this many magnitudes below the system peak are black. */
export const IR_DYNAMIC_RANGE_MAG = 10;

export const LUPTON_CITATION = 'Lupton et al. 2004, PASP 116, 133 (colour-preserving composite)';

const det = (id: SpherexDetectorId): SpherexDetector => SPHEREX_DETECTORS.find((d) => d.id === id)!;

export interface IrChannel {
  readonly channel: 'r' | 'g' | 'b';
  readonly detectors: readonly [SpherexDetector, SpherexDetector];
  readonly loUm: number;
  readonly hiUm: number;
  /** Geometric mean of the edges: the wavelength the IR limb-darkening table is evaluated at. */
  readonly centerUm: number;
}

function channel(name: 'r' | 'g' | 'b', a: SpherexDetectorId, b: SpherexDetectorId): IrChannel {
  const da = det(a);
  const db = det(b);
  return {
    channel: name,
    detectors: [da, db],
    loUm: da.lambdaMinUm,
    hiUm: db.lambdaMaxUm,
    centerUm: Math.sqrt(da.lambdaMinUm * db.lambdaMaxUm),
  };
}

/** The IR mapping, red first: R = D5+D6, G = D3+D4, B = D1+D2. */
export const IR_CHANNELS: readonly [IrChannel, IrChannel, IrChannel] = [
  channel('r', 'D5', 'D6'),
  channel('g', 'D3', 'D4'),
  channel('b', 'D1', 'D2'),
];

const fmtUm = (x: number) => (Math.round(x * 100) / 100).toString();

/** Wavelength span of the IR mode, for the 'FALSE COLOUR · SPHEREx …' label. */
export const IR_SPAN_TEXT = `${Number(det('D1').lambdaMinUm.toPrecision(2))}–${Number(det('D6').lambdaMaxUm.toPrecision(2))} µm`;

/** One-line legend of the channel mapping. */
export const IR_MAPPING_TEXT = IR_CHANNELS.map(
  (c) =>
    `${c.channel === 'r' ? 'red' : c.channel === 'g' ? 'green' : 'blue'} = ${c.detectors[0].id}+${c.detectors[1].id} (${fmtUm(c.loUm)}–${fmtUm(c.hiUm)} µm)`,
)
  .reverse()
  .join(', ');

// --- radiometry ---------------------------------------------------------------------------------

/** Frequency width of one detector band (Hz). */
function bandwidthHz(d: SpherexDetector): number {
  return PHYS.c / (d.lambdaMinUm * 1e-6) - PHYS.c / (d.lambdaMaxUm * 1e-6);
}

/**
 * Frequency-averaged blackbody surface brightness over one detector, ⟨I_ν⟩ = ∫B_λ dλ / Δν
 * (W m⁻² Hz⁻¹ sr⁻¹), from the astro.ts band fraction: ∫B_λ dλ = fraction × σT⁴/π. Null without Teff.
 */
export function detectorMeanIntensity(teffK: number, d: SpherexDetector): number | null {
  const f = bandFraction(teffK, d.lambdaMinUm, d.lambdaMaxUm).value;
  if (f === null) return null;
  return (f * PHYS.sigma * teffK ** 4) / Math.PI / bandwidthHz(d);
}

export interface RgbIntensity {
  readonly r: number;
  readonly g: number;
  readonly b: number;
}

const channelCache = new Map<number, RgbIntensity | null>();

/** ⟨I_ν⟩ of each IR channel: Σ ∫B_λ dλ / Σ Δν over its two detectors (W m⁻² Hz⁻¹ sr⁻¹). */
export function irChannelIntensity(teffK: number): RgbIntensity | null {
  if (!(teffK > 0)) return null;
  const cached = channelCache.get(teffK);
  if (cached !== undefined) return cached;
  const out: Record<'r' | 'g' | 'b', number> = { r: 0, g: 0, b: 0 };
  let result: RgbIntensity | null = out;
  for (const c of IR_CHANNELS) {
    let band = 0;
    let width = 0;
    for (const d of c.detectors) {
      const i = detectorMeanIntensity(teffK, d);
      if (i === null) result = null;
      else band += i * bandwidthHz(d);
      width += bandwidthHz(d);
    }
    out[c.channel] = band / width;
  }
  if (channelCache.size > 256) channelCache.clear();
  channelCache.set(teffK, result);
  return result;
}

const isStellar = (b: Body) => b.kind === 'star' || b.kind === 'brown_dwarf';
const emits = (b: Body): b is Body & { teff_k: number } => isStellar(b) && typeof b.teff_k === 'number' && b.teff_k > 0;

/** Brightest channel ⟨I_ν⟩ of any star or brown dwarf of the system (the top of the IR stretch). */
export function systemIrPeak(system: Pick<SystemModel, 'bodies'>): number | null {
  let peak = 0;
  for (const b of system.bodies) {
    if (!emits(b)) continue;
    const i = irChannelIntensity(b.teff_k);
    if (i) peak = Math.max(peak, i.r, i.g, i.b);
  }
  return peak > 0 ? peak : null;
}

/** Display level of an intensity: 1 at the system peak, 0 at IR_DYNAMIC_RANGE_MAG below it (log). */
export function irLevel(intensity: number, peak: number): number {
  if (!(intensity > 0) || !(peak > 0)) return 0;
  const decades = IR_DYNAMIC_RANGE_MAG / 2.5;
  return Math.min(1, Math.max(0, 1 + Math.log10(intensity / peak) / decades));
}

/** IEC 61966-2-1 sRGB transfer curve (linear → encoded), one channel in [0, 1]. */
export function srgbEncode(v: number): number {
  const c = Math.min(1, Math.max(0, v));
  return c <= 0.0031308 ? 12.92 * c : 1.055 * Math.pow(c, 1 / 2.4) - 0.055;
}

/** Inverse sRGB transfer curve (encoded → linear). */
export function srgbDecode(v: number): number {
  const c = Math.min(1, Math.max(0, v));
  return c <= 0.04045 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4);
}

function toHex(rgb: readonly [number, number, number]): string {
  return '#' + rgb.map((v) => Math.round(Math.min(1, Math.max(0, v)) * 255).toString(16).padStart(2, '0')).join('');
}

function hexToRgb(hex: string): [number, number, number] {
  const n = parseInt(hex.replace('#', '').slice(0, 6), 16);
  return [((n >> 16) & 255) / 255, ((n >> 8) & 255) / 255, (n & 255) / 255];
}

// --- per-body look ------------------------------------------------------------------------------

export type DrawnAs =
  /** Star (or brown dwarf ≥ 2500 K): blackbody at the catalog Teff (MODEL). */
  | 'blackbody'
  /** IR mode below 2500 K: blackbody hue as a qualitative guide only (MODEL, no numbers shown). */
  | 'qualitative'
  /** Visible mode, colour not computed: neutral at the display brightness (DISPLAY). */
  | 'neutral-emission'
  /** Visible mode planet / small body: 18 % grey (albedo unknown) lit by its star (DISPLAY). */
  | 'reflected-grey'
  /** Emission and reflection not modelled: drawn as an outline (DISPLAY). */
  | 'outline'
  /** Synthetic demo system: legacy palette (decoration). */
  | 'synthetic';

export interface BodyLook {
  /** Channel ratios on screen (sRGB-encoded values, largest = 1). */
  readonly hue: readonly [number, number, number];
  /** Display brightness level, 0–1 (sRGB-encoded). For lit bodies it is the albedo scale. */
  readonly level: number;
  /** hue × level, '#rrggbb'. */
  readonly hex: string;
  readonly drawnAs: DrawnAs;
  readonly tier: Tier;
  readonly note: string;
}

const NEUTRAL: readonly [number, number, number] = [1, 1, 1];
const GREY_LEVEL = srgbEncode(NEUTRAL_ALBEDO);

function look(hue: readonly [number, number, number], level: number, drawnAs: DrawnAs, tier: Tier, note: string): BodyLook {
  const l = Math.min(1, Math.max(0, level));
  return { hue, level: l, hex: toHex([hue[0] * l, hue[1] * l, hue[2] * l]), drawnAs, tier, note };
}

function irLook(body: Body, system: SystemModel): BodyLook {
  if (!emits(body)) {
    const what = body.kind === 'disk' ? 'disk' : body.kind.replace('_', ' ');
    return look(NEUTRAL, GREY_LEVEL, 'outline', 'display', `${what}: SPHEREx-band emission not modelled (outline only)`);
  }
  const i = irChannelIntensity(body.teff_k)!;
  const peak = systemIrPeak(system) ?? Math.max(i.r, i.g, i.b);
  const top = Math.max(i.r, i.g, i.b);
  const hue: [number, number, number] = top > 0 ? [i.r / top, i.g / top, i.b / top] : [0, 0, 0];
  const level = irLevel(top, peak);
  const T = paramTier(body, 'teff');
  if (body.teff_k < BLACKBODY_MIN_TEFF_K) {
    return look(
      hue,
      level,
      'qualitative',
      'model',
      `below ${BLACKBODY_MIN_TEFF_K} K: blackbody hue as a qualitative guide only (molecular bands move the flux by magnitudes)`,
    );
  }
  const excess = isYoungWithExcess(body, system);
  return look(
    hue,
    level,
    'blackbody',
    derivedTier([T.tier], 'model'),
    `blackbody ⟨I_ν⟩ per channel at Teff (${T.tier}); log stretch over ${IR_DYNAMIC_RANGE_MAG} mag below the system peak${excess ? '; photosphere only: the IR excess of its disk and accretion is not modelled' : ''}`,
  );
}

/** astro.spherexReliability says the star has an unmodelled IR excess (T Tauri star, disk in the system). */
function isYoungWithExcess(body: Body, system: SystemModel): boolean {
  return body.kind === 'star' && spherexReliability(body, system).value === 'photosphere only - IR excess not modelled';
}

function visibleLook(body: Body, system: Pick<SystemModel, 'provenance'>): BodyLook {
  if (system.provenance.synthetic) {
    return look(
      hexToRgb(baseColor(body, system)),
      body.kind === 'star' && body.teff_k ? displayBrightness(body.teff_k).value : 1,
      'synthetic',
      'illustrative',
      'synthetic demo: hand palette / approximate blackbody fit (decoration)',
    );
  }
  if (isStellar(body)) {
    const db = body.teff_k && body.teff_k > 0 ? displayBrightness(body.teff_k).value : 0.05;
    const c = blackbodyBodyColor(body);
    if (c.value) {
      const hue = c.value.linear.map(srgbEncode) as [number, number, number];
      return look(hue, db, 'blackbody', c.tier, 'CIE 1931 2° colour of a blackbody at Teff; brightness on the display scale');
    }
    return look(
      NEUTRAL,
      db,
      'neutral-emission',
      'display',
      body.kind === 'brown_dwarf'
        ? 'visible colour not computed (T/Y-dwarf spectra are not blackbodies); neutral at the display brightness'
        : 'visible colour not computed; neutral at the display brightness',
    );
  }
  if (body.kind === 'disk') return look(NEUTRAL, GREY_LEVEL, 'outline', 'display', 'disk: scattered-light colour not computed (neutral, translucent)');
  return look(NEUTRAL, GREY_LEVEL, 'reflected-grey', 'display', '18 % neutral grey: albedo and colour unknown; lit by the host star');
}

/** Colour, brightness and provenance of one body in a colour mode. */
export function bodyLook(body: Body, system: SystemModel, mode: ColorMode): BodyLook {
  return mode === 'ir' ? irLook(body, system) : visibleLook(body, system);
}

// --- star shader inputs -------------------------------------------------------------------------

/** A flat table (no limb darkening): used when no atmosphere model applies. */
export function flatLimbDarkening(n = 16): Float32Array {
  return new Float32Array(Math.max(2, Math.floor(n)) * 3).fill(1);
}

/**
 * IR limb darkening for the false-colour star shader: the same grey Eddington-atmosphere model as
 * astro.limbDarkeningLut, evaluated monochromatically at each IR channel centre (r, g, b =
 * 4.37, 2.50, 1.11 µm). Same layout: n entries μ = i/(n−1), [r, g, b] per entry. MODEL.
 */
export function irLimbDarkeningLut(teffK: number, n = 16): Float32Array {
  const count = Math.max(2, Math.floor(n));
  const out = new Float32Array(count * 3);
  for (let i = 0; i < count; i++) {
    const mu = i / (count - 1);
    IR_CHANNELS.forEach((c, ch) => {
      out[i * 3 + ch] = teffK > 0 ? limbDarkeningAt(teffK, c.centerUm * 1000, mu).value : 1;
    });
  }
  return out;
}

/** Limb-darkening table of a star in a colour mode (flat when Teff is missing or < 2500 K). */
export function starLimbDarkening(body: Body, mode: ColorMode, n = 16): Float32Array {
  if (!body.teff_k || body.teff_k < BLACKBODY_MIN_TEFF_K) return flatLimbDarkening(n);
  if (mode === 'ir') return irLimbDarkeningLut(body.teff_k, n);
  return bodyLimbDarkening(body, n).value ?? flatLimbDarkening(n);
}

// --- glow (DISPLAY) -----------------------------------------------------------------------------

/** Decades of luminosity below the system's brightest star over which the glow shrinks to its minimum. */
export const GLOW_DECADES = 4;

/**
 * Luminosity (L_sun) a star's glow is scaled with, in the light the mode shows: visible light
 * L × f(380–780 nm) (M2), or the light in the SPHEREx span L × f(0.746–5.01 µm) in IR mode.
 */
export function glowLuminosity(body: Body, mode: ColorMode): number | null {
  if (body.kind !== 'star') return null;
  if (mode === 'visible') return visibleLuminosity(body).value;
  const L = luminosity(body).value;
  if (L === null || !body.teff_k) return null;
  const f = bandFraction(body.teff_k, det('D1').lambdaMinUm, det('D6').lambdaMaxUm).value;
  return f === null ? null : L * f;
}

/**
 * Glow sprite size in units of the star's display radius: 2 + 3n, where n = 1 + log10(L/L_max)/4
 * clamped to [0, 1] is log L normalised within the system (L_max = its brightest star in this mode,
 * over a fixed 4 decades). 5 for the brightest star, 2 for one 4 decades fainter or of unknown L.
 * DISPLAY.
 */
export function glowScaleFactor(lum: number | null, maxLum: number | null): number {
  if (lum === null || maxLum === null || !(lum > 0) || !(maxLum > 0)) return 2;
  const n = Math.min(1, Math.max(0, 1 + Math.log10(lum / maxLum) / GLOW_DECADES));
  return 2 + 3 * n;
}

/** Glow size factor of every star of the system in a colour mode. */
export function systemGlowFactors(system: Pick<SystemModel, 'bodies'>, mode: ColorMode): Map<string, number> {
  const lums = new Map(system.bodies.map((b) => [b.id, glowLuminosity(b, mode)]));
  const values = [...lums.values()].filter((v): v is number => v !== null && v > 0);
  const max = values.length ? Math.max(...values) : null;
  const out = new Map<string, number>();
  for (const b of system.bodies) if (b.kind === 'star') out.set(b.id, glowScaleFactor(lums.get(b.id) ?? null, max));
  return out;
}

/**
 * Glow opacity: the display level of the star, modulated by its V-band light curve in visible mode
 * only (brightness factor f, 1 = mean; f^0.25). No IR light curve is modelled, so the IR glow is
 * steady. DISPLAY.
 */
export function glowOpacity(level: number, brightnessFactor: number, mode: ColorMode): number {
  const f = mode === 'visible' && brightnessFactor > 0 ? Math.pow(brightnessFactor, 0.25) : 1;
  return Math.min(1, Math.max(0.05, level * f));
}

/** Glow size modulation by the V-band light curve (visible mode only; f^0.3). DISPLAY. */
export function glowPulse(brightnessFactor: number, mode: ColorMode): number {
  return mode === 'visible' && brightnessFactor > 0 ? Math.pow(brightnessFactor, 0.3) : 1;
}

// --- legend -------------------------------------------------------------------------------------

function names(bodies: readonly Body[]): string {
  return bodies.map((b) => b.name).join(', ');
}

/** Legend lines for the colour mode of one system (no numbers for bodies below 2500 K). */
export function colorLegend(mode: ColorMode, system: SystemModel): string[] {
  const cold = system.bodies.filter((b) => emits(b) && b.teff_k < BLACKBODY_MIN_TEFF_K);
  const dark = system.bodies.filter((b) => !emits(b));
  const lines: string[] = [];
  if (mode === 'ir') {
    lines.push(
      `False colour: ${IR_MAPPING_TEXT}. Each channel is the band-averaged surface brightness F_ν of a blackbody at the catalog Teff (MODEL); colours preserved, after Lupton et al. 2004 (PASP 116, 133); brightness log-scaled over ${IR_DYNAMIC_RANGE_MAG} mag below the brightest body and channel of this system (DISPLAY).`,
    );
    const young = system.bodies.filter((b) => isYoungWithExcess(b, system));
    if (young.length) {
      lines.push(
        `${names(young)}: photosphere only. The infrared excess of the disk and accretion, which makes the real system several magnitudes brighter at 3–5 µm, is not modelled.`,
      );
    }
    if (cold.length) lines.push(`${names(cold)}: below ${BLACKBODY_MIN_TEFF_K} K, qualitative only (molecular bands, not a blackbody; MODEL).`);
    if (dark.length) lines.push(`${names(dark)}: SPHEREx-band emission not modelled, drawn as an outline.`);
  } else {
    if (system.bodies.some((b) => b.kind === 'star')) {
      lines.push(
        system.provenance.synthetic
          ? 'Visible: synthetic demo colours (hand palette and an approximate blackbody fit), not measurements.'
          : 'Visible: stars take the CIE 1931 2° colour of a blackbody at the catalog Teff (MODEL), at a log display brightness (DISPLAY).',
      );
    }
    const bds = system.bodies.filter((b) => b.kind === 'brown_dwarf' && !blackbodyBodyColor(b).value);
    if (bds.length) {
      lines.push(
        `${names(bds)}: visible colour not computed (T/Y-dwarf spectra are shaped by Na I and K I wings, Burrows, Marley & Sharp 2000); drawn neutral at the display brightness, so a dark silhouette: switch to SPHEREx IR.`,
      );
    }
    const lit = system.bodies.filter((b) => !isStellar(b) && b.kind !== 'disk');
    if (lit.length && !system.provenance.synthetic) {
      lines.push(`${names(lit)}: neutral 18 % grey (albedo and colour unknown), lit by the host star's colour.`);
    }
  }
  return lines;
}

const round2 = (x: number) => Number(x.toPrecision(2)).toLocaleString('en');

/**
 * Legend lines on surfaces and sizes: limb darkening, convection cells (drawn only where
 * astro.granulationParams says they are resolvable), Mira pulsation, and the class-typical toggle.
 */
export function surfaceLegend(system: Pick<SystemModel, 'bodies' | 'provenance'>, mode: ColorMode, classTypical: boolean): string[] {
  const lines: string[] = [];
  const stars = system.bodies.filter((b) => b.kind === 'star');
  if (stars.length) {
    const drawn: string[] = [];
    const small: string[] = [];
    for (const s of stars) {
      const g = granulationParams(s);
      if (g.value === null) continue;
      if (g.draw) {
        const tau = g.turnoverDays.value;
        drawn.push(
          `${s.name}: ≈${round2(g.value)} convection cells across (cell size 10 H_p, MODEL; ±${Math.round(g.contrast.value * 100)} % contrast, ILLUSTRATIVE)${tau ? `, renewed every ≈${round2(tau)} d of model time` : ''}`,
        );
      } else small.push(`${s.name} ≈${round2(g.value)}`);
    }
    const cells = [
      ...drawn,
      ...(small.length ? [`granules too small to draw (cells across: ${small.join(', ')})`] : []),
    ];
    lines.push(
      `Stars: limb darkening and reddening from a grey Eddington atmosphere (MODEL)${cells.length ? `; ${cells.join('; ')}` : ''}.`,
    );
  }
  for (const s of system.bodies.filter(drawsPulsation)) {
    lines.push(
      `${s.name}: radius pulsates ±${Math.round(PULSATION_RADIUS_AMPLITUDE * 100)} % (CLASS-TYPICAL Mira diameter change); its ${s.variability?.band ?? 'visual'}-band light curve drives the glow${mode === 'ir' ? ' in the visible mode only (no SPHEREx light curve is modelled)' : ''}.`,
    );
  }
  if (system.provenance.synthetic) {
    lines.push('Synthetic demo: planet textures are procedural decoration.');
    return lines;
  }
  const others = system.bodies.filter((b) => b.kind !== 'star' && b.kind !== 'disk');
  if (!others.length) return lines;
  if (!classTypical) {
    lines.push(`No surface features on ${names(others)}: none is measured, so each is a uniform sphere.`);
    return lines;
  }
  const bands = others.filter((b) => surfacePattern(b, system, true) === 'bands');
  const mottled = others.filter((b) => surfacePattern(b, system, true) === 'mottling');
  const parts = [
    ...(bands.length ? [`bands on ${names(bands)}`] : []),
    ...(mottled.length ? [`albedo mottling on ${names(mottled)}`] : []),
  ];
  if (parts.length) {
    const hidden = mode === 'ir' && others.some((b) => !isStellar(b) && surfacePattern(b, system, true) !== 'none');
    lines.push(
      `ILLUSTRATIVE class-typical features: ${parts.join('; ')}. Random patterns typical of the class, not observed on these objects${hidden ? '; planets show them in the visible mode only' : ''}.`,
    );
  }
  return lines;
}

/** Text of the overlay chip shown whenever the IR mode is on. */
export const FALSE_COLOUR_CHIP = `FALSE COLOUR · SPHEREx ${IR_SPAN_TEXT}`;

/** Text of the overlay chip shown while the class-typical toggle is on. */
export const CLASS_TYPICAL_CHIP = 'CLASS-TYPICAL FEATURES · ILLUSTRATIVE';
