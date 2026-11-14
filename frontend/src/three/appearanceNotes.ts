// "How this body is drawn" and "At SPHEREx scale" for the body panel (WS7, work package M6).
//
// Pure: no React, no three.js (BodyPanel is in the main chunk; three.js must stay in the lazily
// loaded 3D chunk). Every row is { section, property, value, unit, tier, method, citation, flags },
// so a reviewer can audit and reproduce each pixel decision and each derived number:
//   drawn    every visual property of the 3D view: colour in both colour modes, on-screen
//            brightness, glow, limb darkening, surface pattern, the class-typical toggle, size,
//            pulsation, rotation and lighting
//   derived  the physical quantities behind the drawing (L, log g, H_p, Teq, S, band fractions ...)
//   spherex  the body as SPHEREx sees it: angular size and separation against the 6.15″ pixel and
//            the PSF, and the predicted AB per detector when the reliability rule allows it
// The numbers come from astro.ts (deriveBody and its primitives). The drawing rules are read from
// the same pure modules the scene uses, so the panel cannot drift from the picture:
//   colorModes.ts   bodyLook (IR false colour is the DEFAULT mode, visible CIE 1931 the other),
//                   glow factors, the IR and visible limb-darkening tables
//   appearance.ts   surfacePattern (no pattern on a real body unless the class-typical toggle,
//                   OFF by default, is on), displayRadius
//   sceneLayout.ts  spinModel (spin only from a verified period, or the tidal-lock rule),
//                   pulsation amplitude, capRadii (display radii)
//   astro.ts        granulationParams (convection cells drawn only when resolvable)
import type { Body, Fact, SystemModel } from '../api/types';
import { CLASS_TYPICAL_CITATION, CLASS_TYPICAL_CONTRAST, NEUTRAL_ALBEDO, compressDistance, displayRadius, surfacePattern } from './appearance';
import {
  BLACKBODY_MIN_TEFF_K,
  GRANULATION_MAX_CELLS,
  PHYS,
  TIERS,
  VISIBLE_BAND_NM,
  bandFraction,
  deriveBody,
  derivedTier,
  distanceTier,
  paramTier,
  spherexPrediction,
  weakestTier,
  type BodyDerivation,
  type Derived,
  type Flag,
  type SpectralType,
  type Tier,
} from './astro';
import { formatPeriod } from './bodyFormat';
import {
  COLOR_MODE_LABEL,
  DEFAULT_COLOR_MODE,
  GLOW_DECADES,
  IR_CHANNELS,
  IR_DYNAMIC_RANGE_MAG,
  IR_MAPPING_TEXT,
  LUPTON_CITATION,
  bodyLook,
  glowLuminosity,
  irChannelIntensity,
  starLimbDarkening,
  systemGlowFactors,
  systemIrPeak,
} from './colorModes';
import {
  AU_PER_KM,
  PULSATION_CITATION,
  PULSATION_RADIUS_AMPLITUDE,
  SPIN_ALIAS_MAX_DEG_PER_FRAME,
  capRadii,
  distanceMapper,
  drawsPulsation,
  linearScale,
  referenceAu,
  spinModel,
} from './sceneLayout';
import { SPHEREX_BANDS_CITATION, SPHEREX_DETECTORS, SPHEREX_PIXEL_ARCSEC } from './spherexBands';

// --- row shape -----------------------------------------------------------------------------------

export type NoteSection = 'drawn' | 'derived' | 'spherex';

/** An evidence tier, or 'not-drawn' for a property the view deliberately leaves out (it is unknown). */
export type NoteTier = Tier | 'not-drawn';

/** Every note tier, strongest first ('not-drawn' last: nothing is shown). */
export const NOTE_TIERS: readonly NoteTier[] = [...TIERS, 'not-drawn'];

export interface AppearanceNote {
  readonly section: NoteSection;
  /** What is described ('Colour · SPHEREx IR false colour (default view)', 'Luminosity' ...). */
  readonly property: string;
  /** The value as shown (already formatted). */
  readonly value: string;
  /** Unit of `value` ('' when none). */
  readonly unit: string;
  readonly tier: NoteTier;
  /** Formula, rule and input tiers, in plain words. */
  readonly method: string;
  /** Where the formula, constants, data or rule come from. */
  readonly citation: string;
  readonly flags: readonly Flag[];
}

/** Header shown above the notes in the body panel. */
export const NOTES_HEADER =
  'Calculated in your browser from the catalog values above with the stated formulae - not new measurements';

/** Chip text for each note tier. */
export const NOTE_TIER_LABEL: Readonly<Record<string, string>> = {
  measured: 'MEASURED',
  derived: 'DERIVED',
  model: 'MODEL',
  'range-pick': 'RANGE PICK',
  'class-typical': 'CLASS-TYPICAL',
  theory: 'THEORY',
  illustrative: 'ILLUSTRATIVE',
  display: 'DISPLAY',
  'not-drawn': 'NOT DRAWN',
};

/** One-line meaning of each note tier (chip tooltip). */
export const NOTE_TIER_MEANING: Readonly<Record<string, string>> = {
  measured: 'Backed by a verified catalog or paper value for this object',
  derived: 'Computed only from measured inputs with an exact relation',
  model: 'A physical model or approximation is involved (blackbody, grey atmosphere, assumed albedo ...)',
  'range-pick': 'One number picked inside a range published for this object',
  'class-typical': 'Typical of the object class, not observed on this object',
  theory: 'A theoretical expectation, not an observation',
  illustrative: 'No verified source backs this value (drawing value or unverified estimate)',
  display: 'A screen mapping chosen for visibility, never photometry',
  'not-drawn': 'Not known for this body, so the 3D view leaves it out',
};

/** Human text for each flag. */
export const FLAG_TEXT: Readonly<Record<string, string>> = {
  'lower-bound': 'from a minimum mass (M sin i): a lower bound',
  'missing-input': 'an input is missing',
  'not-modelled': 'part of the physics is not modelled (see the method)',
  'blackbody-unreliable': `Teff < ${BLACKBODY_MIN_TEFF_K} K: blackbody unreliable, qualitative only`,
  'brighter-than-nonlinearity':
    'brighter than the pre-launch non-linearity onset: check the OVERFLOW and NONLINEAR pixel flags',
  'assumed-orbit': 'orbit assumed, not fitted',
};

/** Defaults of the 3D view. The panel does not see the viewer's current choice, so it lists both colour modes. */
export const SCENE_DRAWING_DEFAULTS = {
  colourMode: COLOR_MODE_LABEL[DEFAULT_COLOR_MODE],
  otherColourMode: COLOR_MODE_LABEL[DEFAULT_COLOR_MODE === 'ir' ? 'visible' : 'ir'],
  classTypicalFeatures: false,
} as const;

// --- SPHEREx instrument constants used here (RECON §2.2) -------------------------------------------

/** Pixel scale measured as sqrt|det PC| (RECON §2.2); the nominal 6.15″ is SPHEREX_PIXEL_ARCSEC. */
export const SPHEREX_PIXEL_MEASURED_ARCSEC = 6.152;

/** A Gaussian PSF separates two equal point sources only beyond ≈ 0.85 FWHM (Sparrow 1916, ApJ 44, 76). */
export const SPARROW_LIMIT_FWHM = 0.85;

/**
 * Years either side of a catalog separation over which the verdict must hold: from the 2016–2017
 * epochs of the Gaia DR3 and ALMA separations to 2031, which covers the SPHEREx survey (2025 on).
 */
export const DRIFT_WINDOW_YR = 15;

const FWHMS = SPHEREX_DETECTORS.map((d) => d.psfFwhmArcsec);
const FWHM_MIN = Math.min(...FWHMS);
const FWHM_MAX = Math.max(...FWHMS);

/** n significant figures; scientific notation outside [1e-3, 1e6). */
function fmt(x: number, n = 3): string {
  if (!Number.isFinite(x)) return String(x);
  if (x === 0) return '0';
  const ax = Math.abs(x);
  if (ax >= 1e-3 && ax < 1e6) return Number(x.toPrecision(n)).toLocaleString('en', { maximumSignificantDigits: n });
  const [m, e] = x.toExponential(n - 1).split('e');
  return `${Number(m)}e${Number(e)}`;
}

/** Pixel, PSF and non-linearity constants, for the header of the SPHEREx section. */
export const SPHEREX_SCALE_NOTE = `SPHEREx pixel ${SPHEREX_PIXEL_ARCSEC}″ (${SPHEREX_PIXEL_MEASURED_ARCSEC}″ measured as √|det PC|); PSF FWHM ${SPHEREX_DETECTORS.map((d) => `${d.id} ${d.psfFwhmArcsec}″`).join(', ')}, i.e. ${fmt(FWHM_MIN / SPHEREX_PIXEL_ARCSEC, 2)}–${fmt(FWHM_MAX / SPHEREX_PIXEL_ARCSEC, 3)} px (undersampled); non-linearity onsets AB ${SPHEREX_DETECTORS.map((d) => d.nonLinearityOnsetAB.toFixed(2)).join(' / ')} (D1–D6, pre-launch model). Source: docs/RECON_SPHEREX.md §2.2.`;

const RECON_PSF_CITE = 'docs/RECON_SPHEREX.md §2.2 (PSF FWHM per detector, 6.15″ pixel; SPHEREx Explanatory Supplement v2.1)';
const SPARROW_CITE = 'Sparrow 1916, ApJ 44, 76 (two-point resolution limit)';
const WS7_RULE = 'WS7 drawing rule (docs/VISION_3D.md: what is not known is not drawn as if it were known)';
const COLOR_MODES_CITE = 'WS7 colour modes (frontend/src/three/colorModes.ts)';
const DISPLAY_CITE = 'WS7 display convention (frontend/src/three/appearance.ts, sceneLayout.ts)';

// --- small helpers ---------------------------------------------------------------------------------

/** An angle in arcsec as a fraction of the SPHEREx pixel: '0.24 px' or '1/6,500 px'. */
export function pixelText(arcsec: number): string {
  const px = arcsec / SPHEREX_PIXEL_ARCSEC;
  if (!(px > 0)) return '0 px';
  return px >= 0.01 ? `${fmt(px, 2)} px` : `1/${fmt(1 / px, 2)} px`;
}

const isStellar = (b: Body) => b.kind === 'star' || b.kind === 'brown_dwarf';
const IRRADIATED: ReadonlySet<Body['kind']> = new Set<Body['kind']>(['planet', 'dwarf_planet', 'moon', 'asteroid', 'comet', 'tno', 'unknown']);
const M_SUN = PHYS.GMSun / PHYS.G;
const R_SUN_KM = PHYS.RSun / 1e3;
const YEAR_S = 365.25 * 86400;
const CHANNEL_NAME = { r: 'red', g: 'green', b: 'blue' } as const;

function row(
  section: NoteSection,
  property: string,
  value: string,
  tier: NoteTier,
  method: string,
  citation: string,
  flags: readonly Flag[] = [],
  unit = '',
): AppearanceNote {
  return { section, property, value, unit, tier, method, citation, flags: [...new Set(flags)] };
}

/** A row from a Derived number: the value formatted, or 'not computed' with the reason in the method. */
function derivedRow(section: NoteSection, property: string, d: Derived<number | null>, unit: string, digits = 3): AppearanceNote {
  if (d.value === null) return row(section, property, 'not computed', d.tier, d.method, d.citation, d.flags);
  return row(section, property, fmt(d.value, digits), d.tier, d.method, d.citation, d.flags, unit);
}

/** Show a Derived quantity unless it is simply not defined for this kind of body. */
const applicable = (d: Derived<unknown>) => d.value !== null || !d.flags.includes('not-modelled');

function spectralText(s: SpectralType): string {
  const range = s.subtypeMax !== null ? `–${s.letterMax ?? s.letter}${s.subtypeMax}` : '';
  return `${s.letter}${s.subtype ?? ''}${range}${s.luminosityClass ? ` ${s.luminosityClass}` : ''} (${s.stage})`;
}

function parentOf(body: Body, system: SystemModel): Body | null {
  return body.orbit ? system.bodies.find((b) => b.id === body.orbit!.parent) ?? null : null;
}

/** The body and every body that orbits it, directly or not. */
function subtree(root: Body, system: SystemModel): Body[] {
  const out: Body[] = [root];
  for (let i = 0; i < out.length && out.length <= system.bodies.length; i++) {
    for (const b of system.bodies) if (b.orbit?.parent === out[i].id && !out.includes(b)) out.push(b);
  }
  return out;
}

const factTier = (f: Fact): Tier => (f.verified ? 'measured' : 'illustrative');

/** Three channel values as 'R 0.47 · G 1 · B 0.93'. */
const rgbText = (v: ArrayLike<number>, offset = 0) => `R ${fmt(v[offset], 2)} · G ${fmt(v[offset + 1], 2)} · B ${fmt(v[offset + 2], 2)}`;

// --- separations: the verdict rule -------------------------------------------------------------------

export type SeparationVerdict = 'always one SPHEREx source' | 'separate sources' | 'depends on date/orientation';

/**
 * Verdict for an angular separation known to lie in [minArcsec, maxArcsec]:
 *   max < 0.5 FWHM in every detector  → 'always one SPHEREx source'
 *   min > 2 FWHM in every detector    → 'separate sources'
 *   anything else                     → 'depends on date/orientation'
 */
export function separationVerdict(minArcsec: number, maxArcsec: number): { verdict: SeparationVerdict; method: string } {
  const sparrow = SPARROW_LIMIT_FWHM * FWHM_MIN;
  const common = `a Gaussian PSF separates two equal sources only beyond the Sparrow limit ≈ ${SPARROW_LIMIT_FWHM} FWHM, and SPHEREx is undersampled (FWHM ${fmt(FWHM_MIN / SPHEREX_PIXEL_ARCSEC, 2)}–${fmt(FWHM_MAX / SPHEREX_PIXEL_ARCSEC, 3)} px)`;
  if (maxArcsec < 0.5 * FWHM_MIN) {
    return {
      verdict: 'always one SPHEREx source',
      method: `largest separation ${fmt(maxArcsec)}″ < 0.5 × FWHM in every detector (0.5 × ${FWHM_MIN}″ = ${fmt(0.5 * FWHM_MIN)}″); ${common}`,
    };
  }
  if (minArcsec > 2 * FWHM_MAX) {
    return {
      verdict: 'separate sources',
      method: `smallest separation ${fmt(minArcsec)}″ > 2 × FWHM in every detector (2 × ${FWHM_MAX}″ = ${fmt(2 * FWHM_MAX)}″); ${common}`,
    };
  }
  const belowSparrow =
    maxArcsec < sparrow ? `; even at ${fmt(maxArcsec)}″ it stays below the Sparrow limit in every detector (${fmt(sparrow)}″)` : '';
  return {
    verdict: 'depends on date/orientation',
    method: `separation range ${fmt(minArcsec)}–${fmt(maxArcsec)}″ is neither always < 0.5 FWHM (${fmt(0.5 * FWHM_MIN)}″) nor always > 2 FWHM (${fmt(2 * FWHM_MAX)}″)${belowSparrow}; ${common}`,
  };
}

interface MeasuredSeparation {
  readonly arcsec: number;
  readonly tier: Tier;
  readonly method: string;
  readonly citation: string;
  /** Total mass of the pair (the parent and everything orbiting it), kg, when every non-disk mass is known. */
  readonly massKg: number | null;
  readonly massTier: Tier;
}

const ARCSEC_UNITS = /^(arcsec|arcseconds?|″|")$/i;
const AU_UNITS = /^au$/i;

/** The catalog's projected separation from the parent ('Projected separation', 'Separation from A' '(projected)' ...). */
function measuredSeparation(body: Body, parent: Body, system: SystemModel): MeasuredSeparation | null {
  const projected = (f: Fact) =>
    /^projected\s+(separation|distance)\b/i.test(f.label.trim()) ||
    (/^separation\b/i.test(f.label.trim()) && /projected/i.test(`${f.label} ${f.value}`));
  const number = (f: Fact) => {
    const m = /-?\d+(?:\.\d+)?/.exec(f.value.replace(/,(?=\d{3}\b)/g, ''));
    return m ? +m[0] : NaN;
  };
  const candidates = body.facts.filter((f) => projected(f) && number(f) > 0);
  const inArcsec = candidates.find((f) => ARCSEC_UNITS.test((f.unit ?? '').trim()));
  const inAu = candidates.find((f) => AU_UNITS.test((f.unit ?? '').trim()));
  const d = distanceTier(system);
  // Mass of the pair: the parent and everything orbiting it, directly or not (disks are left out).
  const pair = subtree(parent, system).filter((b) => b.kind !== 'disk');
  const massKg = pair.every((b) => b.mass_kg !== null) ? pair.reduce((s, b) => s + (b.mass_kg ?? 0), 0) : null;
  const massTier = weakestTier(pair.map((b) => paramTier(b, 'mass').tier));
  if (inArcsec) {
    return {
      arcsec: number(inArcsec),
      tier: factTier(inArcsec),
      method: `${inArcsec.verified ? 'verified' : 'unverified'} Fact '${inArcsec.label}' = ${inArcsec.value} ${inArcsec.unit}`,
      citation: inArcsec.source ?? 'no source given',
      massKg,
      massTier,
    };
  }
  if (inAu && d.value !== null) {
    const au = number(inAu);
    return {
      arcsec: au / Number(d.value),
      tier: derivedTier([factTier(inAu), d.tier]),
      method: `${inAu.verified ? 'verified' : 'unverified'} Fact '${inAu.label}' = ${inAu.value} AU divided by the distance ${fmt(Number(d.value))} pc (${d.tier})`,
      citation: `${inAu.source ?? 'no source given'}; distance: ${d.citation}`,
      massKg,
      massTier,
    };
  }
  return null;
}

// --- per-body literature notes for properties that are NOT drawn (sources checked 2026-11-14) ---------

/**
 * Why a body does not spin in the 3D view although it rotates in reality: the published values, and
 * why none qualifies. Used only while the catalog has no rotation_period_hours for the body.
 */
export const ROTATION_NOT_DRAWN_NOTES: Readonly<Record<string, { readonly note: string; readonly citation: string }>> = {
  'eps-indi-a': {
    note: 'published periods disagree (about 18, 22 and 36 d, a possible factor-2 alias), so none is verified',
    citation:
      'Feng et al. 2019, arXiv:1910.06804 (Sect. 3, Table 2: 35.7 d); NASA Exoplanet Archive st_rotp: Sanghi et al. 2026, AJ 172, 115 (18.3 d) and Pizzolato et al. 2003 (22 d)',
  },
  'eps-indi-ba': {
    note: 'no period measured; v sin i = 28 ± 3 km/s implies P ≤ ~3 h for R ≈ 0.069 R☉ (measured before Bb was discovered)',
    citation: 'Hitchcock et al. 2020, arXiv:2005.06906 (Sect. 4.1); Chen et al. 2022, AJ 163, 288 (Sect. V); Smith et al. 2003, ApJ 599, L107',
  },
  'eps-indi-bb': {
    note: 'no period measured for either component of the pair',
    citation: 'Hitchcock et al. 2020, arXiv:2005.06906 (Sect. 4.1); Chen et al. 2022, AJ 163, 288 (Sect. V)',
  },
  'wise-0855': {
    note: 'not determined: Spitzer 3.6/4.5 µm double-sine fits give 9.7–14 h with the two epochs disagreeing at 2σ, and JWST is also inconclusive',
    citation: 'Esplin et al. 2016, ApJ 832, 58 (Sect. 3); Wilson et al. 2025, arXiv:2510.24575; Miles et al. 2026, arXiv:2609.20664 (Sect. 5.2)',
  },
  'rw-aur-a': {
    note: 'no secure period: a candidate of about 5.5–5.7 d without a formal uncertainty',
    citation: 'Petrov et al. 2001, A&A 369, 993; Dodin, Lamzin & Chountonov 2012, arXiv:1111.2309 (Sect. 4)',
  },
};

/**
 * Sensitivity ranges for illustrative inputs of the granulation count: they test whether the
 * drawn / not-drawn verdict depends on the guessed values. R Dra has no dynamical mass (typical Miras
 * have 1–2 M☉) and its 250 R☉ is a drawing value (published sizes depend on the distance and phase).
 */
export const GRANULATION_SENSITIVITY: Readonly<Record<string, { readonly radiusRsun: readonly [number, number]; readonly massMsun: readonly [number, number] }>> = {
  'r-draconis': { radiusRsun: [200, 300], massMsun: [1, 2] },
};

// --- the 'drawn' rows ----------------------------------------------------------------------------------

interface Ctx {
  readonly body: Body;
  readonly system: SystemModel;
  readonly d: BodyDerivation;
  readonly synthetic: boolean;
}

function irColourRow({ body, system }: Ctx): AppearanceNote {
  const prop = `Colour · ${COLOR_MODE_LABEL.ir}${DEFAULT_COLOR_MODE === 'ir' ? ', default view' : ''}`;
  const look = bodyLook(body, system, 'ir');
  const mapping = `${IR_MAPPING_TEXT}; each channel is the frequency-averaged blackbody surface brightness ⟨I_ν⟩ = Σ∫B_λ dλ / ΣΔν over its two detectors (F_ν units, like the SPHEREx MJy/sr images); all three channels share one stretch, so the colour is preserved (Lupton et al. 2004), and the stretch is logarithmic over the ${IR_DYNAMIC_RANGE_MAG} mag below the brightest body × channel of the system. This body: ${look.note}`;
  const citation = `${LUPTON_CITATION}; ${SPHEREX_BANDS_CITATION}; ${COLOR_MODES_CITE}`;
  if (look.drawnAs === 'outline') {
    return row('drawn', prop, 'emission not modelled: drawn as an outline', 'not-drawn', look.note, WS7_RULE, ['not-modelled']);
  }
  const i = body.teff_k !== null ? irChannelIntensity(body.teff_k) : null;
  const top = i ? Math.max(i.r, i.g, i.b) : 0;
  if (look.drawnAs === 'qualitative') {
    const brightest = IR_CHANNELS.find((c) => i && i[c.channel] === top) ?? IR_CHANNELS[0];
    return row(
      'drawn',
      prop,
      `qualitative: brightest in ${CHANNEL_NAME[brightest.channel]} (${brightest.detectors[0].id}+${brightest.detectors[1].id}), dashed outline`,
      look.tier,
      `${mapping}; no numbers are shown below ${BLACKBODY_MIN_TEFF_K} K`,
      `${citation}; Burrows, Sudarsky & Lunine 2003, ApJ 596, 587`,
      ['blackbody-unreliable'],
    );
  }
  const peak = systemIrPeak(system);
  const below = peak && top > 0 ? -2.5 * Math.log10(top / peak) : 0;
  return row(
    'drawn',
    prop,
    `${look.hex}: ${rgbText(look.hue)}; ${below < 0.005 ? "the system's brightest (top of the stretch)" : `${fmt(below, 2)} mag below the system's brightest`}`,
    look.tier,
    mapping,
    citation,
  );
}

function visibleColourRow({ body, system, d }: Ctx): AppearanceNote {
  const prop = `Colour · ${COLOR_MODE_LABEL.visible}`;
  const look = bodyLook(body, system, 'visible');
  switch (look.drawnAs) {
    case 'synthetic':
      return row('drawn', prop, `${look.hex} (demo palette)`, look.tier, `${look.note}; not from measurements`, 'synthetic demo (provenance.synthetic); frontend/src/three/appearance.ts');
    case 'blackbody': {
      const c = d.color;
      const xy = c.value ? ` (x ${c.value.x.toFixed(4)}, y ${c.value.y.toFixed(4)})` : '';
      return row(
        'drawn',
        prop,
        `${c.value?.hex ?? look.hex}${xy}, at display brightness ${fmt(look.level, 2)}`,
        look.tier,
        `${c.method}; ${look.note}`,
        c.citation,
        c.flags,
      );
    }
    case 'neutral-emission': {
      const teff = body.teff_k;
      const vis = teff !== null && teff > 0 ? bandFraction(teff, VISIBLE_BAND_NM[0] / 1e3, VISIBLE_BAND_NM[1] / 1e3).value : null;
      return row(
        'drawn',
        prop,
        `not computed: neutral, at display brightness ${fmt(look.level, 2)}`,
        look.tier,
        `${look.note}. Visible T/Y-dwarf spectra are shaped by pressure-broadened Na I and K I wings, not by a blackbody${vis !== null ? `; a blackbody would emit only ${fmt(vis, 2)} of its light at ${VISIBLE_BAND_NM[0]}–${VISIBLE_BAND_NM[1]} nm, so it is nearly a silhouette: switch to SPHEREx IR` : ''}`,
        'Burrows, Marley & Sharp 2000, ApJ 531, 438; Burrows et al. 2001, Rev. Mod. Phys. 73, 719',
        teff !== null && teff < BLACKBODY_MIN_TEFF_K ? ['blackbody-unreliable'] : [],
      );
    }
    case 'reflected-grey': {
      const lower = d.inputs.mass.flags.includes('lower-bound') ? '; its mass is a minimum mass (M sin i)' : '';
      return row(
        'drawn',
        prop,
        `neutral ${fmt(NEUTRAL_ALBEDO * 100, 2)} % grey`,
        look.tier,
        `${look.note}${lower}`,
        `${WS7_RULE}; 18 % grey: the photographic mid-grey reference`,
        ['not-modelled'],
      );
    }
    default:
      return row('drawn', prop, 'neutral, translucent', look.tier, `${look.note}; the shape only marks the measured size`, WS7_RULE, ['not-modelled']);
  }
}

function brightnessRow({ body, system, d }: Ctx): AppearanceNote | null {
  if (!isStellar(body)) return null;
  const b = d.displayBrightness;
  const ir = bodyLook(body, system, 'ir');
  const irText = ir.drawnAs === 'qualitative' ? 'qualitative' : fmt(ir.level, 2);
  return row(
    'drawn',
    'On-screen brightness',
    `visible ${b.value === null ? 'dimmest level' : fmt(b.value, 2)} · IR ${irText}`,
    'display',
    `fraction of the display range. Visible: ${b.method}. IR: 1 + log10(⟨I_ν⟩/peak)/${IR_DYNAMIC_RANGE_MAG / 2.5}, clamped to [0, 1] (log over ${IR_DYNAMIC_RANGE_MAG} mag below the system's brightest body × channel)`,
    `${b.citation}; ${COLOR_MODES_CITE}`,
    b.flags,
  );
}

function glowRow({ body, system }: Ctx): AppearanceNote | null {
  if (body.kind !== 'star') return null;
  const ir = systemGlowFactors(system, 'ir').get(body.id) ?? 2;
  const vis = systemGlowFactors(system, 'visible').get(body.id) ?? 2;
  const lIr = glowLuminosity(body, 'ir');
  const lVis = glowLuminosity(body, 'visible');
  const v = body.variability;
  const variable =
    v?.kind === 'pulsation' && v.amplitude_mag && v.period_days
      ? `; the ${fmt(v.amplitude_mag, 2)} mag ${v.band ?? ''} light curve modulates the glow in visible mode only: that swing is driven by TiO absorption, not by the Planck function (Reid & Goldston 2002, ApJ 568, 931)`
      : v && !v.period_days
        ? '; the irregular dimming is not animated (no periodic model)'
        : '';
  return row(
    'drawn',
    'Glow',
    `×${fmt(ir, 2)} display radius (IR), ×${fmt(vis, 2)} (visible)`,
    'display',
    `sprite size = display radius × (2 + 3n), n = 1 + log10(L/L_max)/${GLOW_DECADES} clamped to [0, 1], with L the luminosity in the SPHEREx span (IR: ${lIr === null ? 'not computed' : `${fmt(lIr, 2)} L☉`}) or at ${VISIBLE_BAND_NM[0]}–${VISIBLE_BAND_NM[1]} nm (visible: ${lVis === null ? 'not computed' : `${fmt(lVis, 2)} L☉`}) and L_max the system's brightest star in that mode; opacity follows the display brightness${variable}`,
    `${COLOR_MODES_CITE}; L = 4πR²σTeff⁴ × blackbody band fraction (astro.ts)`,
  );
}

function limbRow({ body, d }: Ctx): AppearanceNote | null {
  if (body.kind !== 'star') return null;
  const ld = d.limbDarkening;
  if (ld.value === null) {
    return row('drawn', 'Limb darkening', 'none (flat disc)', 'not-drawn', ld.method, ld.citation, ld.flags);
  }
  const vis = starLimbDarkening(body, 'visible');
  const ir = starLimbDarkening(body, 'ir');
  const centres = IR_CHANNELS.map((c) => fmt(c.centerUm, 3)).join('/');
  return row(
    'drawn',
    'Limb darkening',
    `I(limb)/I(centre): visible ${rgbText(vis)}; IR (${centres} µm) ${rgbText(ir)}`,
    ld.tier,
    `${ld.method}. IR mode: the same grey-atmosphere model evaluated monochromatically at the IR channel centres. The limb is redder because T(τ = μ) is cooler there; real M-dwarf and Mira atmospheres are molecular, not grey`,
    ld.citation,
    ld.flags,
  );
}

function granulationSensitivity(body: Body, cells: number): string {
  const s = GRANULATION_SENSITIVITY[body.id];
  if (!s || body.radius_km === null || body.mass_kg === null) return '';
  const r0 = body.radius_km / R_SUN_KM;
  const m0 = body.mass_kg / M_SUN;
  // N = 2R / (10 H_p) ∝ M / (Teff R): Teff fixed, corners of the ranges.
  const at = (r: number, m: number) => cells * (m / m0) * (r0 / r);
  const lo = at(s.radiusRsun[1], s.massMsun[0]);
  const hi = at(s.radiusRsun[0], s.massMsun[1]);
  const same = lo < GRANULATION_MAX_CELLS === hi < GRANULATION_MAX_CELLS && lo < GRANULATION_MAX_CELLS === cells < GRANULATION_MAX_CELLS;
  return `; for R ${s.radiusRsun[0]}–${s.radiusRsun[1]} R☉ and M ${s.massMsun[0]}–${s.massMsun[1]} M☉ (illustrative ranges) the count is ${fmt(lo, 2)}–${fmt(hi, 2)}, so the verdict ${same ? 'holds' : 'does NOT hold'}`;
}

function surfaceRow({ body, system, d }: Ctx): AppearanceNote {
  const prop = 'Surface pattern';
  if (body.kind === 'star') {
    const g = d.granulation;
    if (g.value === null) return row('drawn', prop, 'none (convection cells not computed)', 'not-drawn', g.method, g.citation, g.flags);
    const cells = g.value;
    const margin = g.draw
      ? `the verdict holds unless M/(Teff·R) is ≥ ${fmt(GRANULATION_MAX_CELLS / cells, 2)}× larger than drawn (N ∝ M/(Teff·R))`
      : `the verdict holds unless M/(Teff·R) is ≥ ${fmt(cells / GRANULATION_MAX_CELLS, 2)}× smaller than drawn (N ∝ M/(Teff·R))`;
    if (g.draw) {
      return row(
        'drawn',
        prop,
        `≈${fmt(cells, 2)} convection cells across, ±${fmt(g.contrast.value * 100, 2)} % contrast, turnover ≈ ${fmt(g.turnoverDays.value ?? 0, 2)} d`,
        g.tier,
        `${g.method}; drawn as 3D cellular noise in object space seeded by the body id, evolving with model time (τ: ${g.turnoverDays.method}); contrast ${g.contrast.tier}: ${g.contrast.method}; ${margin}${granulationSensitivity(body, cells)}`,
        `${g.citation}; giant cells observed on π¹ Gru: Paladini et al. 2018, Nature 553, 310`,
        g.flags,
      );
    }
    return row(
      'drawn',
      prop,
      `none: ≈${fmt(cells, 2)} cells across, too small to draw`,
      g.tier,
      `${g.method}; cells are drawn only when fewer than ${GRANULATION_MAX_CELLS} fit across the disc; ${margin}`,
      g.citation,
      g.flags,
    );
  }
  const pattern = surfacePattern(body, system, false);
  if (pattern === 'procedural') {
    return row(
      'drawn',
      prop,
      'procedural texture (demo)',
      'illustrative',
      'synthetic demo system: random bands (gas giants, brown dwarfs) or blotches and craters (rocky and icy bodies), seeded by the body id',
      'synthetic demo (provenance.synthetic); frontend/src/three/appearance.ts surfacePattern',
    );
  }
  return row(
    'drawn',
    prop,
    pattern === 'none' ? 'none (uniform)' : pattern,
    pattern === 'none' ? 'not-drawn' : 'illustrative',
    'no measured surface map or rotational modulation exists for this body, so no craters, bands or spots are drawn',
    WS7_RULE,
  );
}

function classTypicalRow({ body, system, synthetic }: Ctx): AppearanceNote | null {
  if (synthetic) return null;
  const prop = "Toggle 'Show class-typical features'";
  const on = surfacePattern(body, system, true);
  if (on === 'bands') {
    return row(
      'drawn',
      prop,
      `off by default; when on: zonal bands / patchy clouds, ±${fmt(CLASS_TYPICAL_CONTRAST.bands * 100, 2)} % (ILLUSTRATIVE)`,
      'class-typical',
      `${body.kind === 'brown_dwarf' ? 'brown dwarfs' : 'gas giants'} commonly show banded, patchy cloud structure; the drawn pattern is random and its contrast a drawing choice, never this body's observed map`,
      CLASS_TYPICAL_CITATION,
    );
  }
  if (on === 'mottling') {
    return row(
      'drawn',
      prop,
      `off by default; when on: albedo mottling, ±${fmt(CLASS_TYPICAL_CONTRAST.mottling * 100, 2)} % (ILLUSTRATIVE)`,
      'class-typical',
      'a random albedo mottling, as on rocky and icy surfaces of the solar system; no surface of this body is resolved or measured, and the contrast is a drawing choice',
      'WS7 drawing choice (frontend/src/three/appearance.ts surfacePattern, CLASS_TYPICAL_CONTRAST)',
    );
  }
  return row('drawn', prop, 'off by default; nothing to add for this kind of body', 'not-drawn', 'no class-typical surface feature is defined for this kind of body', WS7_RULE);
}

function sizeRow({ body, system }: Ctx): AppearanceNote {
  const prop = 'Size on screen';
  const bodies = system.bodies;
  const refAu = referenceAu(bodies);
  const scale = linearScale(bodies);
  if (body.kind === 'disk') {
    const outerAu = (body.radius_km ?? 0) * AU_PER_KM;
    return row(
      'drawn',
      prop,
      body.radius_km === null ? 'default ring' : `ring to ${fmt(outerAu, 3)} AU`,
      'display',
      `flat ring from 1.4 × the host's display radius out to the disk radius, mapped like the orbits (compressed: ${fmt(compressDistance(outerAu, refAu), 3)} units; true proportions: ${fmt(outerAu * scale, 3)} units)`,
      DISPLAY_CITE,
    );
  }
  const base = new Map(bodies.map((b) => [b.id, displayRadius(b)]));
  const compressed = capRadii(bodies, 'compressed', base, distanceMapper('compressed', refAu, scale));
  const linear = capRadii(bodies, 'linear', compressed, distanceMapper('linear', refAu, scale));
  const rc = compressed.get(body.id) ?? displayRadius(body);
  const rl = linear.get(body.id) ?? rc;
  const method = `display radius ÷ physical radius, in scene units. Display radius = clamp(0.12 · R_km^0.18, 0.12, 2.2), then capped so no body reaches its parent or a sibling (capRadii). True proportions: ${fmt(scale, 3)} units per AU; compressed: 3 units per ${fmt(refAu, 3)} AU in its linear core, logarithmic beyond`;
  if (body.radius_km === null || !(body.radius_km > 0)) {
    return row('drawn', prop, 'default size (radius unknown)', 'display', method, DISPLAY_CITE, ['missing-input']);
  }
  const rAu = body.radius_km * AU_PER_KM;
  const exLinear = rl / (rAu * scale);
  const exCompressed = rc / ((rAu * 3) / refAu);
  return row(
    'drawn',
    prop,
    `×${fmt(exLinear, 2)} true size (true-proportions mode), ×${fmt(exCompressed, 2)} (compressed mode)`,
    'display',
    `${method}; a factor below 1 means drawn smaller than true size; radius ${paramTier(body, 'radius').tier}`,
    DISPLAY_CITE,
  );
}

function pulsationRow({ body }: Ctx): AppearanceNote | null {
  if (!drawsPulsation(body)) return null;
  return row(
    'drawn',
    'Pulsation (radius)',
    `±${fmt(PULSATION_RADIUS_AMPLITUDE * 100, 2)} %`,
    'class-typical',
    `radius factor 1 − ${PULSATION_RADIUS_AMPLITUDE}·sin(phase), on the same sinusoid and phase as the V light curve (largest when brightest): the class-typical ~20 % peak-to-peak continuum diameter change of Mira variables. Only the period (${formatPeriod(body.variability!.period_days!)}) is this star's; the real lag between size and light is not modelled`,
    PULSATION_CITATION,
  );
}

function rotationRow({ body, system }: Ctx): AppearanceNote {
  const prop = 'Rotation';
  const spin = spinModel(body, system.bodies);
  if (spin.kind === 'period') {
    return row(
      'drawn',
      prop,
      `one turn per ${formatPeriod(spin.periodHours / 24)}`,
      spin.tier,
      `${spin.method}; angle = 2π · 24 · (MJD − 51544.5) / P_h, so scrubbing the time works; the rotational phase is not known (zero at J2000); the spin is held still while it would advance more than ${SPIN_ALIAS_MAX_DEG_PER_FRAME}° per rendered frame (aliasing guard)`,
      spin.citation,
    );
  }
  if (spin.kind === 'tidal-lock') {
    return row('drawn', prop, `tidally locked: one turn per orbit (${formatPeriod(spin.periodHours / 24)})`, spin.tier, `${spin.method}; not observed`, spin.citation);
  }
  const known = ROTATION_NOT_DRAWN_NOTES[body.id];
  return row(
    'drawn',
    prop,
    'rotation unknown: not drawn',
    'not-drawn',
    known ? `${known.note}; the body does not spin in the 3D view` : 'no verified rotation period in the catalog, so the body does not spin in the 3D view',
    known ? known.citation : WS7_RULE,
  );
}

/** '#rrggbb' of a hue triple (sRGB-encoded channel values in [0, 1]). */
function hueHex(hue: readonly number[]): string {
  return '#' + hue.map((v) => Math.round(Math.min(1, Math.max(0, v)) * 255).toString(16).padStart(2, '0')).join('');
}

function lightingRow({ body, system, d }: Ctx): AppearanceNote {
  const prop = 'Lighting';
  const hues = (s: Body) => `visible ${hueHex(bodyLook(s, system, 'visible').hue)}, IR ${hueHex(bodyLook(s, system, 'ir').hue)}`;
  if (body.kind === 'star') {
    return row(
      'drawn',
      prop,
      `self-luminous; its light takes its drawn hue (${hues(body)})`,
      'display',
      'a star is not lit: its disc comes from its own temperature (star shader). It carries a point light in its hue of the current colour mode, with a display-normalised intensity (no 1/r² fall-off)',
      `${COLOR_MODES_CITE}; ${DISPLAY_CITE}`,
    );
  }
  if (body.kind === 'brown_dwarf') {
    return row(
      'drawn',
      prop,
      'self-luminous: not lit by its companions',
      'display',
      'drawn unlit, at its display brightness (visible) or its SPHEREx-band level (IR), with a Fresnel rim outline that is a display aid, not emitted light; the rim is dashed while the IR colour is only qualitative',
      `${COLOR_MODES_CITE}; ${DISPLAY_CITE}`,
    );
  }
  if (body.kind === 'disk') {
    return row(
      'drawn',
      prop,
      'not lit: a translucent ring',
      'display',
      'drawn unlit and translucent (fainter in IR, where its emission is not modelled): scattered light from the stars is not computed',
      DISPLAY_CITE,
      ['not-modelled'],
    );
  }
  const stars = system.bodies.filter((b) => b.kind === 'star');
  const S = d.insolation.value === null ? '' : `; the true flux is S = ${fmt(d.insolation.value, 2)} S⊕ (see the physical quantities)`;
  return row(
    'drawn',
    prop,
    stars.length
      ? `visible: light of ${stars.map((s) => `${s.name} ${hueHex(bodyLook(s, system, 'visible').hue)}`).join(', ')}; IR: dark, with an outline`
      : 'ambient light only',
    'display',
    `the point light of each star in that star's drawn hue, display-normalised with no 1/r² fall-off, plus a faint white ambient light so the night side is not black; in IR mode the body's SPHEREx-band emission and reflection are not modelled, so it is a dark sphere with a Fresnel outline${S}`,
    DISPLAY_CITE,
  );
}

function drawnRows(ctx: Ctx): AppearanceNote[] {
  const rows: (AppearanceNote | null)[] = [
    irColourRow(ctx),
    visibleColourRow(ctx),
    brightnessRow(ctx),
    glowRow(ctx),
    limbRow(ctx),
    surfaceRow(ctx),
    classTypicalRow(ctx),
    sizeRow(ctx),
    pulsationRow(ctx),
    rotationRow(ctx),
    lightingRow(ctx),
  ];
  return rows.filter((r): r is AppearanceNote => r !== null);
}

// --- the 'derived' rows ---------------------------------------------------------------------------------

function derivedRows({ body, d }: Ctx): AppearanceNote[] {
  const out: AppearanceNote[] = [];
  const add = (property: string, q: Derived<number | null>, unit: string, digits = 3) => {
    if (applicable(q)) out.push(derivedRow('derived', property, q, unit, digits));
  };
  if (isStellar(body)) {
    add('Luminosity', d.luminosity, 'L☉');
    add('Surface gravity log g', d.logG, 'dex (cgs)');
    if (body.kind === 'star') add('Pressure scale height H_p', d.scaleHeightKm, 'km');
    if (body.teff_k !== null && body.teff_k > 0) {
      const vis = bandFraction(body.teff_k, VISIBLE_BAND_NM[0] / 1e3, VISIBLE_BAND_NM[1] / 1e3);
      out.push(
        derivedRow(
          'derived',
          `Visible fraction (${VISIBLE_BAND_NM[0]}–${VISIBLE_BAND_NM[1]} nm)`,
          { ...vis, tier: derivedTier([d.inputs.teff.tier], 'model'), method: `${vis.method}; input Teff ${d.inputs.teff.tier}` },
          'of the light',
          2,
        ),
      );
    }
    const fr = d.spherex.value.map((b) => b.fraction);
    if (fr.length && fr.every((f) => f.value !== null)) {
      out.push(
        row(
          'derived',
          'Fraction of the light per SPHEREx detector',
          d.spherex.value.map((b) => `${b.detector.id} ${fmt(b.fraction.value as number, 2)}`).join(' · '),
          weakestTier(fr.map((f) => f.tier)),
          `∫B_λ dλ over each detector band (IRSA SIA edges) / (σT⁴/π); ${d.spherex.value[0].detector.id}: ${fr[0].method}`,
          `${fr[0].citation}; ${SPHEREX_BANDS_CITATION}`,
          fr.flatMap((f) => f.flags),
        ),
      );
    }
  }
  if (IRRADIATED.has(body.kind)) {
    add('Equilibrium temperature (A_B = 0)', d.teqBondAlbedo0, 'K');
    add('Equilibrium temperature (A_B = 0.3)', d.teqBondAlbedo03, 'K');
    add('Insolation S/S⊕', d.insolation, 'S⊕', 2);
  }
  const sc = d.spectralClass;
  if (sc.value) out.push(row('derived', 'Spectral class (parsed)', spectralText(sc.value), sc.tier, sc.method, sc.citation, sc.flags));
  const mc = d.massClass;
  if (body.kind !== 'star' && body.kind !== 'disk' && mc.value) {
    out.push(row('derived', 'Mass class', mc.value, mc.tier, mc.method, mc.citation, mc.flags));
  }
  return out;
}

// --- the 'spherex' rows ---------------------------------------------------------------------------------

function spherexRows({ body, system, d }: Ctx): AppearanceNote[] {
  const out: AppearanceNote[] = [];
  const ad = d.angularDiameterMas;
  out.push(
    ad.value === null
      ? row('spherex', 'Angular diameter', 'not computed', ad.tier, ad.method, ad.citation, ad.flags)
      : row(
          'spherex',
          'Angular diameter',
          `${fmt(ad.value, 2)} mas = ${pixelText(ad.value / 1000)}`,
          ad.tier,
          `${ad.method}; against the ${SPHEREX_PIXEL_ARCSEC}″ SPHEREx pixel${ad.value / 1000 < 0.1 * FWHM_MIN ? ': an unresolved point source' : ''}`,
          `${ad.citation}; ${RECON_PSF_CITE}`,
          ad.flags,
        ),
  );

  const parent = parentOf(body, system);
  let verdict: SeparationVerdict | null = null;
  if (parent && body.orbit) {
    const sep = d.separationArcsec;
    const dist = Number(system.motion?.distance_pc);
    if (sep.value) {
      const max = sep.value[1];
      const peri = dist > 0 ? (body.orbit.semi_major_axis_au * (1 - body.orbit.eccentricity)) / dist : null;
      out.push(
        row(
          'spherex',
          `Separation from ${parent.name}`,
          `≤ ${fmt(max, 3)}″ = ${pixelText(max)}${peri !== null && body.orbit.eccentricity > 0 ? ` (true separation ${fmt(peri, 3)}–${fmt(max, 3)}″; projection can only shorten it)` : ''}`,
          sep.tier,
          sep.method,
          sep.citation,
          sep.flags,
        ),
      );
    } else {
      out.push(row('spherex', `Separation from ${parent.name}`, 'not computed', sep.tier, sep.method, sep.citation, sep.flags));
    }

    const measured = measuredSeparation(body, parent, system);
    if (measured) {
      out.push(
        row(
          'spherex',
          `Measured projected separation from ${parent.name}`,
          `${fmt(measured.arcsec, 3)}″ = ${pixelText(measured.arcsec)}`,
          measured.tier,
          measured.method,
          measured.citation,
        ),
      );
    }

    // The verdict: a catalog separation with an orbit-independent drift bound wins over the orbit bounds.
    let range: [number, number] | null = null;
    let how = '';
    let tier: Tier = sep.tier;
    let citation = `${RECON_PSF_CITE}; ${SPARROW_CITE}`;
    let flags: readonly Flag[] = sep.flags;
    if (measured && measured.massKg !== null && dist > 0) {
      const sAu = measured.arcsec * dist;
      const vEsc = Math.sqrt((2 * PHYS.G * measured.massKg) / (sAu * PHYS.au)); // m/s
      const drift = (((vEsc * YEAR_S) / PHYS.au) * DRIFT_WINDOW_YR) / dist; // arcsec
      range = [Math.max(0, measured.arcsec - drift), measured.arcsec + drift];
      how = `catalog separation ${fmt(measured.arcsec, 3)}″ ± ${fmt(drift, 2)}″: within ±${DRIFT_WINDOW_YR} yr it changes by at most v_esc·Δt/d, where v_esc = √(2GM/s) = ${fmt(vEsc / 1e3, 2)} km/s is the escape speed at the projected separation s = ${fmt(sAu, 3)} AU (a bound pair moves slower, and its true separation is ≥ s), M = ${fmt(measured.massKg / M_SUN, 3)} M☉ (${measured.massTier}); independent of the orbit fit`;
      tier = derivedTier([measured.tier, measured.massTier]);
      citation = `${measured.citation}; ${citation}`;
      flags = [];
    } else if (sep.value) {
      range = [sep.value[0], sep.value[1]];
      how = `orbit bounds [0, a(1+e)/d] = [0, ${fmt(sep.value[1], 3)}″] (the projected separation at a given date is not used, so the lower bound is 0)`;
      citation = `${sep.citation}; ${citation}`;
    }
    if (range) {
      const v = separationVerdict(range[0], range[1]);
      verdict = v.verdict;
      const blend =
        v.verdict === 'always one SPHEREx source' && isStellar(parent) && isStellar(body)
          ? `; SPHEREx photometry of this position is the blend ${parent.name} + ${body.name}`
          : '';
      out.push(row('spherex', 'Resolved by SPHEREx?', v.verdict, tier, `${how}; ${v.method}${blend}`, citation, flags));
    }
  }

  out.push(...abRows(d));

  if (parent && verdict !== null && verdict !== 'separate sources' && isStellar(parent) && isStellar(body)) {
    out.push(blendRow(body, parent, system, d));
  }
  return out;
}

function abRows(d: BodyDerivation): AppearanceNote[] {
  const sp = d.spherex;
  const bands = sp.value;
  if (bands.every((b) => b.abMag.value === null)) {
    return [row('spherex', 'Predicted AB (D1–D6)', `not shown: ${sp.reliability}`, sp.tier, `${sp.reliability}: ${sp.method}`, sp.citation, sp.flags)];
  }
  return bands.map((b) => {
    const prop = `Predicted AB, ${b.detector.id} (${b.detector.lambdaMinUm}–${b.detector.lambdaMaxUm} µm)`;
    if (b.abMag.value === null) return row('spherex', prop, 'not shown', b.abMag.tier, b.abMag.method, b.abMag.citation, b.abMag.flags);
    return row('spherex', prop, b.abMag.value.toFixed(2), b.abMag.tier, b.abMag.method, b.abMag.citation, b.abMag.flags, 'AB mag');
  });
}

function blendRow(body: Body, parent: Body, system: SystemModel, d: BodyDerivation): AppearanceNote {
  const prop = `Blend fraction ${body.name} / (${parent.name} + ${body.name})`;
  const mine = d.spherex;
  const theirs = spherexPrediction(parent, system);
  const pairs = mine.value.map((b, i) => [b, theirs.value[i]] as const);
  if (pairs.length && pairs.every(([a, p]) => a.abMag.value !== null && p?.abMag.value != null)) {
    const text = pairs
      .map(([a, p]) => {
        const fb = 10 ** (-0.4 * (a.abMag.value as number));
        const fa = 10 ** (-0.4 * (p.abMag.value as number));
        return `${a.detector.id} ${fmt(fb / (fa + fb), 2)}`;
      })
      .join(' · ');
    return row(
      'spherex',
      prop,
      text,
      weakestTier([mine.tier, theirs.tier]),
      `F_B/(F_A + F_B) per detector from the predicted AB of both (one SPHEREx source); ${body.name}: ${mine.reliability}; ${parent.name}: ${theirs.reliability}`,
      mine.citation,
      [...mine.flags, ...theirs.flags],
    );
  }
  const mineMissing = mine.value.some((b) => b.abMag.value === null);
  const weak = mineMissing ? mine : theirs;
  return row(
    'spherex',
    prop,
    'not shown: needs reliable AB predictions for both',
    weak.tier,
    `${mineMissing ? body.name : parent.name}: ${weak.reliability} (${weak.method})`,
    weak.citation,
    weak.flags,
  );
}

// --- entry point ---------------------------------------------------------------------------------------

/** Every note of one body: how it is drawn, the physics behind it, and how SPHEREx sees it. */
export function appearanceNotes(body: Body, system: SystemModel): AppearanceNote[] {
  const ctx: Ctx = { body, system, d: deriveBody(body, system), synthetic: system.provenance.synthetic };
  return [...drawnRows(ctx), ...derivedRows(ctx), ...spherexRows(ctx)];
}
