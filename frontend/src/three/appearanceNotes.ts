// "How this body is drawn" and "At SPHEREx scale" for the body panel (WS7, work package M6).
//
// Pure: no React, no three.js. BodyPanel loads this module on demand (dynamic import, when one of
// its two <details> sections is first opened or hovered), so it and its tables stay out of the
// main chunk; three.js must stay in the separate 3D chunk. Every row is
// { section, property, value, unit, tier, method, citation, flags }, so a reviewer can audit and
// reproduce each pixel decision and each derived number:
//   drawn    every visual property of the 3D view: colour in every colour mode (SPHEREx false
//            colour, the six single-detector greys D1–D6, visible), on-screen brightness, glow,
//            limb darkening, surface pattern, size, pulsation (both clocks: free-running and
//            Dataset time; the radius is constant), rotation and lighting. A value that is not
//            measured is said to be unknown (grey colour, fixed marker size), never guessed
//   derived  the physical quantities behind the drawing (L, log g, H_p, Teq, S, band fractions ...)
//   spherex  the body as SPHEREx sees it: angular size and separation against the 6.15″ pixel and
//            the PSF, and the predicted AB per detector when the reliability rule allows it
// The numbers come from astro.ts (deriveBody and its primitives). The drawing rules are read from
// the same pure modules the scene uses, so the panel cannot drift from the picture:
//   colorModes.ts   bodyLook (IR false colour is the DEFAULT mode, visible CIE 1931 the other),
//                   glow factors, the IR and visible limb-darkening tables
//   appearance.ts   surfacePattern (no pattern on any real body; synthetic demo textures only),
//                   displayRadius (fixed marker size when the radius is unknown)
//   sceneLayout.ts  spinModel (spin only from a verified period, or the tidal-lock rule),
//                   drawsPulsation, capRadii (display radii)
//   astro.ts        granulationParams (convection cells drawn only on the synthetic demo)
//   ephemerides.ts  the Mira ephemeris Dataset time draws R Dra with (this module is a lazy chunk,
//                   so importing it here adds nothing to the main chunk)
import type { Body, Fact, SystemModel } from '../api/types';
import { NEUTRAL_ALBEDO, compressDistance, displayRadius, surfacePattern } from './appearance';
import {
  BLACKBODY_MIN_TEFF_K,
  GRANULATION_MAX_CELLS,
  MIRA_CITE,
  MIRA_TIO_CITATION,
  PHYS,
  TIERS,
  VISIBLE_BAND_NM,
  bandFraction,
  deriveBody,
  derivedTier,
  distanceTier,
  miraReason,
  paramTier,
  spherexPrediction,
  weakestTier,
  type BodyDerivation,
  type Derived,
  type Flag,
  type SpectralType,
  type Tier,
} from './astro';
import {
  COLOR_MODES,
  COLOR_MODE_LABEL,
  DEFAULT_COLOR_MODE,
  GLOW_DECADES,
  IR_CHANNELS,
  IR_DYNAMIC_RANGE_MAG,
  IR_MAPPING_TEXT,
  LUPTON_CITATION,
  SPHEREX_LIGHT_CURVE_POINTER,
  bodyLook,
  glowLuminosity,
  irChannelIntensity,
  isDetectorMode,
  starLimbDarkening,
  systemGlowFactors,
  systemIrPeak,
  type BodyLook,
  type DetectorMode,
} from './colorModes';
import { UNKNOWN_COLOUR_REASON, UNKNOWN_COLOUR_TEXT, UNKNOWN_SIZE_REASON, UNKNOWN_SIZE_TEXT, isSizeKnown } from './factOrigin';
import {
  AU_PER_KM,
  SPIN_ALIAS_MAX_DEG_PER_FRAME,
  capRadii,
  distanceMapper,
  drawsPulsation,
  linearScale,
  referenceAu,
  spinModel,
} from './sceneLayout';
import { MIRA_PREDICTION_CAVEAT, miraEphemerisFor } from './ephemerides';
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

/** Defaults of the 3D view. The panel does not see the viewer's current choice, so it lists every colour mode. */
export const SCENE_DRAWING_DEFAULTS = {
  colourMode: COLOR_MODE_LABEL[DEFAULT_COLOR_MODE],
  otherColourModes: COLOR_MODES.filter((m) => m !== DEFAULT_COLOR_MODE).map((m) => COLOR_MODE_LABEL[m]),
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
    note: 'no secure period: a candidate of about 5.5–5.7 d without a formal uncertainty; AAVSO VSX lists 2.64 d for RW Aur (type CTTS/ROT, A+B unresolved, component not stated): not adopted',
    citation: 'Petrov et al. 2001, A&A 369, 993; Dodin, Lamzin & Chountonov 2012, arXiv:1111.2309 (Sect. 4)',
  },
};

/**
 * What the literature says about the surface or variability of a real non-stellar body that the 3D
 * view draws as a uniform sphere, and why none of it is a map (sources from the WS7 stage-2
 * literature research of 2026-11-14, as for ROTATION_NOT_DRAWN_NOTES). Appended to the
 * 'Surface pattern' row.
 */
export const SURFACE_NOT_DRAWN_NOTES: Readonly<Record<string, { readonly note: string; readonly citation: string }>> = {
  'wise-0855': {
    note: 'rotational modulation itself IS measured: Spitzer 3.6 and 4.5 µm light curves vary by a few per cent (Esplin et al. 2016) and JWST spectra vary too, but the period is not determined, no amplitude is verified for this catalog, and a disc-integrated light curve does not show where the clouds are',
    citation: 'Esplin et al. 2016, ApJ 832, 58 (Sect. 3); Wilson et al. 2025, arXiv:2510.24575; Miles et al. 2026, arXiv:2609.20664 (Sect. 5.2)',
  },
  'eps-indi-ba': {
    note: 'Ba and Bb are unresolved in the I-band monitoring of the pair: no period, mean brightness changes of up to 0.10 mag over ≥ 2 d; no significant variability in the NACO and FORS2 data',
    citation: 'Hitchcock et al. 2020, arXiv:2005.06906 (Sect. 4.1); Chen et al. 2022, AJ 163, 288 (Sect. V)',
  },
  'eps-indi-bb': {
    note: 'Ba and Bb are unresolved in the I-band monitoring of the pair: no period, mean brightness changes of up to 0.10 mag over ≥ 2 d; no significant variability in the NACO and FORS2 data',
    citation: 'Hitchcock et al. 2020, arXiv:2005.06906 (Sect. 4.1); Chen et al. 2022, AJ 163, 288 (Sect. V)',
  },
  'eps-indi-ab': {
    note: 'JWST/MIRI imaging sees the planet only as an unresolved point of light',
    citation: 'Matthews et al. 2024, Nature 633, 789',
  },
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
  const mira = miraReason(body);
  const miraCaveat = mira
    ? `; ${mira}: H₂O and CO bands and circumstellar dust are not modelled, so this hue is that of the photosphere blackbody only, not the star's SPHEREx colour`
    : '';
  const mapping = `${IR_MAPPING_TEXT}; each channel is the frequency-averaged blackbody ⟨I_ν⟩ = Σ∫B_λ dλ / ΣΔν over its two detectors (surface brightness, MJy/sr-like units); all three channels share one stretch, so the colour is preserved (Lupton et al. 2004), and the stretch is logarithmic over the ${IR_DYNAMIC_RANGE_MAG} mag below the brightest body × channel of the system. This body: ${look.note}${miraCaveat}`;
  const citation = `${LUPTON_CITATION}; ${SPHEREX_BANDS_CITATION}; ${COLOR_MODES_CITE}${mira ? `; ${MIRA_CITE}` : ''}`;
  if (look.drawnAs === 'synthetic') return syntheticColourRow(prop, look);
  if (look.drawnAs === 'unknown-colour') return unknownColourRow(prop);
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

const SYNTHETIC_CITE = 'synthetic demo (provenance.synthetic); frontend/src/three/appearance.ts';

/** A star or brown dwarf without a measured Teff: neutral grey in every colour mode. */
function unknownColourRow(prop: string): AppearanceNote {
  return row('drawn', prop, `${UNKNOWN_COLOUR_TEXT}: neutral grey`, 'not-drawn', `${UNKNOWN_COLOUR_REASON}, in every colour mode`, WS7_RULE, ['missing-input']);
}

/** A synthetic demo body drawn with its hand palette (decoration). */
function syntheticColourRow(prop: string, look: BodyLook): AppearanceNote {
  return row('drawn', prop, `${look.hex} (demo palette)`, look.tier, `${look.note}; not from measurements`, SYNTHETIC_CITE);
}

/** The single-detector colour modes of colorModes (one SPHEREx detector drawn in grey). */
const DETECTOR_MODES: readonly DetectorMode[] = COLOR_MODES.filter(isDetectorMode);

function detectorColourRow({ body, system, d }: Ctx): AppearanceNote | null {
  if (!DETECTOR_MODES.length) return null;
  const ids = `${DETECTOR_MODES[0]}–${DETECTOR_MODES[DETECTOR_MODES.length - 1]}`;
  const prop = `Grey level · SPHEREx single detector (${ids})`;
  const looks = DETECTOR_MODES.map((id) => ({ id, look: bodyLook(body, system, id) }));
  const first = looks[0].look;
  const citation = `${SPHEREX_BANDS_CITATION}; ${COLOR_MODES_CITE}`;
  if (first.drawnAs === 'synthetic') return syntheticColourRow(prop, first);
  if (first.drawnAs === 'unknown-colour') return unknownColourRow(prop);
  if (first.drawnAs === 'outline') {
    return row('drawn', prop, 'emission not modelled: drawn as an outline', 'not-drawn', first.note, WS7_RULE, ['not-modelled']);
  }
  const method = `each single-detector mode draws the blackbody ⟨I_ν⟩ of that one detector (surface brightness, MJy/sr-like units) in grey, on a log stretch over the ${IR_DYNAMIC_RANGE_MAG} mag below the system's brightest body in that detector, so the levels of different detectors are not on one scale`;
  if (looks.some(({ look }) => look.drawnAs === 'qualitative')) {
    return row(
      'drawn',
      prop,
      'qualitative grey level in each detector (no numbers)',
      first.tier,
      `${method}; no numbers are shown below ${BLACKBODY_MIN_TEFF_K} K`,
      `${citation}; Burrows, Sudarsky & Lunine 2003, ApJ 596, 587`,
      ['blackbody-unreliable'],
    );
  }
  const mira = miraReason(body);
  return row(
    'drawn',
    prop,
    `display level ${looks.map(({ id, look }) => `${id} ${fmt(look.level, 2)}`).join(' · ')}`,
    weakestTier(looks.map(({ look }) => look.tier)),
    `${method}. This body: blackbody at Teff (${d.inputs.teff.tier})${isYoungWithExcess(d) ? '; photosphere only: the IR excess of its disk and accretion is not modelled' : ''}${mira ? `; ${mira}: H₂O and CO bands and circumstellar dust are not modelled` : ''}`,
    mira ? `${citation}; ${MIRA_CITE}` : citation,
  );
}

/** astro's reliability rule found an unmodelled IR excess (T Tauri star, disk in the system). */
const isYoungWithExcess = (d: BodyDerivation) => d.spherex.reliability === 'photosphere only - IR excess not modelled';

function visibleColourRow({ body, system, d }: Ctx): AppearanceNote {
  const prop = `Colour · ${COLOR_MODE_LABEL.visible}`;
  const look = bodyLook(body, system, 'visible');
  switch (look.drawnAs) {
    case 'synthetic':
      return syntheticColourRow(prop, look);
    case 'unknown-colour':
      return unknownColourRow(prop);
    case 'blackbody': {
      const c = d.color;
      const xy = c.value ? ` (x ${c.value.x.toFixed(4)}, y ${c.value.y.toFixed(4)})` : '';
      const mira = miraReason(body);
      return row(
        'drawn',
        prop,
        `${c.value?.hex ?? look.hex}${xy}, at display brightness ${fmt(look.level, 2)}`,
        look.tier,
        `${c.method}; ${look.note}${mira ? `; ${mira}: its visible spectrum is dominated by TiO absorption bands, so this is the colour of the photosphere blackbody only` : ''}`,
        mira ? `${c.citation}; TiO in Mira visual light: ${MIRA_TIO_CITATION}` : c.citation,
        mira ? [...c.flags, 'not-modelled'] : c.flags,
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
  if (ir.drawnAs === 'unknown-colour') {
    return row(
      'drawn',
      'On-screen brightness',
      `neutral grey, level ${fmt(ir.level, 2)} in every colour mode`,
      'display',
      `${UNKNOWN_COLOUR_REASON}: the ${fmt(NEUTRAL_ALBEDO * 100, 2)} % grey reference level, not a brightness computed from a temperature`,
      WS7_RULE,
      ['missing-input'],
    );
  }
  const irText = ir.drawnAs === 'qualitative' ? 'qualitative' : fmt(ir.level, 2);
  return row(
    'drawn',
    'On-screen brightness',
    `visible ${b.value === null ? 'dimmest level' : fmt(b.value, 2)} · IR ${irText}`,
    'display',
    `fraction of the display range. Visible: ${b.method}. IR: 1 + log10(⟨I_ν⟩/peak)/${IR_DYNAMIC_RANGE_MAG / 2.5}, clamped to [0, 1] (log over ${IR_DYNAMIC_RANGE_MAG} mag below the system's brightest body × channel); the single-detector levels are in the grey-level row`,
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
  // Dataset time draws the light curve from a catalogue ephemeris (R Dra) only for a drawn pulsation.
  const eph = drawsPulsation(body) ? miraEphemerisFor(system.id, body.id) : null;
  let variable = '';
  if (v && v.amplitude_mag && v.period_days) {
    const curve = `the ${fmt(v.amplitude_mag, 2)} mag${v.band ? ` ${v.band}-band` : ''} light curve (catalog, not measured by SPHEREx) modulates the glow in visible mode only (opacity × f^0.25, size × f^0.3, f = flux / mean flux; the radius stays constant; ${SPHEREX_LIGHT_CURVE_POINTER})`;
    const clocks = eph
      ? `free-running clock, a sine at the catalog period with an arbitrary phase; Dataset time, the predicted ${eph.band} phase on the asymmetric curve of the ephemeris in the pulsation row (${MIRA_PREDICTION_CAVEAT})`
      : 'free-running clock, a sine at the catalog period with an arbitrary phase; Dataset time, held at the mean (no catalogue ephemeris: phase unknown)';
    const tio = miraReason(body) ? `; that swing is driven by TiO absorption, not by the Planck function (${MIRA_TIO_CITATION})` : '';
    variable = `; ${curve}: ${clocks}${tio}`;
  } else if (v && !v.period_days) {
    variable = '; the irregular dimming is not animated (no periodic model)';
  }
  const single = DETECTOR_MODES.length
    ? `, or in the band of one detector (single-detector modes: ×${DETECTOR_MODES.map((id) => fmt(systemGlowFactors(system, id).get(body.id) ?? 2, 2)).join('/')} for ${DETECTOR_MODES.join('/')})`
    : '';
  return row(
    'drawn',
    'Glow',
    `×${fmt(ir, 2)} display radius (IR), ×${fmt(vis, 2)} (visible)`,
    'display',
    `sprite size = display radius × (2 + 3n), n = 1 + log10(L/L_max)/${GLOW_DECADES} clamped to [0, 1], with L the luminosity in the SPHEREx span (IR: ${lIr === null ? 'not computed' : `${fmt(lIr, 2)} L☉`}) or at ${VISIBLE_BAND_NM[0]}–${VISIBLE_BAND_NM[1]} nm (visible: ${lVis === null ? 'not computed' : `${fmt(lVis, 2)} L☉`})${single}, and L_max the system's brightest star in that mode; opacity follows the display brightness${variable}`,
    `${COLOR_MODES_CITE}; L = 4πR²σTeff⁴ × blackbody band fraction (astro.ts)${eph ? `; ephemeris: ${eph.source}` : ''}`,
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
    `${ld.method}. IR mode: the same grey-atmosphere model evaluated monochromatically at the IR channel centres${DETECTOR_MODES.length ? '; single-detector modes: at the centre of that detector, the same in every channel (grey)' : ''}. The limb is redder because T(τ = μ) is cooler there; real M-dwarf and Mira atmospheres are molecular, not grey`,
    ld.citation,
    ld.flags,
  );
}

function surfaceRow({ body, system, d, synthetic }: Ctx): AppearanceNote {
  const prop = 'Surface pattern';
  if (body.kind === 'star') {
    const g = d.granulation;
    if (g.value === null) {
      return row('drawn', prop, 'none: smooth sphere (convection cells not computed)', 'not-drawn', g.method, g.citation, g.flags);
    }
    const cells = g.value;
    if (g.draw && synthetic) {
      return row(
        'drawn',
        prop,
        `≈${fmt(cells, 2)} convection cells across, ±${fmt(g.contrast.value * 100, 2)} % contrast, turnover ≈ ${fmt(g.turnoverDays.value ?? 0, 2)} d (synthetic demo)`,
        'illustrative',
        `synthetic demo star: ${g.method}; drawn as 3D cellular noise in object space seeded by the body id, evolving with model time (τ: ${g.turnoverDays.method}); contrast ${g.contrast.tier}: ${g.contrast.method}`,
        `${g.citation}; synthetic demo (provenance.synthetic)`,
        g.flags,
      );
    }
    if (g.draw) {
      return row(
        'drawn',
        prop,
        'none: smooth sphere with limb darkening',
        'not-drawn',
        `no surface of this star is resolved or mapped, so no convection cells are drawn (docs/VISION.md: no invented spots, cells or bands), although ≈${fmt(cells, 2)} cells across would be large enough to draw (${g.method})`,
        `${g.citation}; ${WS7_RULE}`,
        g.flags,
      );
    }
    return row(
      'drawn',
      prop,
      `none: ≈${fmt(cells, 2)} cells across, too small to draw`,
      g.tier,
      `${g.method}; cells are drawn only on the synthetic demo, and only when fewer than ${GRANULATION_MAX_CELLS} fit across the disc; the verdict holds unless M/(Teff·R) is ≥ ${fmt(cells / GRANULATION_MAX_CELLS, 2)}× smaller than drawn (N ∝ M/(Teff·R))`,
      g.citation,
      g.flags,
    );
  }
  const pattern = surfacePattern(body, system);
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
  if (body.kind === 'disk') {
    const r = paramTier(body, 'radius');
    return row(
      'drawn',
      prop,
      'none (uniform translucent ring)',
      'not-drawn',
      `the ring only marks the disk radius (${r.tier}: ${r.method}); no brightness structure of the disk (rings, gaps, a radial profile, e.g. from resolved millimetre images) is drawn`,
      r.fact ? `${r.citation}; ${WS7_RULE}` : WS7_RULE,
    );
  }
  const literature = SURFACE_NOT_DRAWN_NOTES[body.id];
  return row(
    'drawn',
    prop,
    'none (uniform)',
    'not-drawn',
    `${modulationText(body)}${literature ? `; ${literature.note}` : ''}`,
    literature ? `${literature.citation}; ${WS7_RULE}` : WS7_RULE,
  );
}

/**
 * Why a real non-stellar body is drawn without a surface pattern: what the catalog has (a
 * rotational light-curve amplitude or nothing) and why that is not a map.
 */
function modulationText(body: Body): string {
  const v = body.variability;
  if (v?.kind === 'rotation' && v.amplitude_mag) {
    const band = v.band ? ` (${v.band})` : '';
    return `no surface map of this body is measured; the catalog gives a rotational modulation of ${fmt(v.amplitude_mag, 2)} mag${band}, but a disc-integrated light curve is not a map and the 3D view does not turn it into spots or bands, so no pattern is drawn`;
  }
  return 'no surface map of this body is measured, and the catalog has no verified rotational-modulation amplitude for it, so no craters, bands or spots are drawn';
}

function sizeRow({ body, system }: Ctx): AppearanceNote {
  const prop = 'Size on screen';
  const bodies = system.bodies;
  const refAu = referenceAu(bodies);
  const scale = linearScale(bodies);
  if (body.kind === 'disk') {
    if (!isSizeKnown(body)) {
      return row(
        'drawn',
        prop,
        `fixed marker ring (${UNKNOWN_SIZE_TEXT})`,
        'not-drawn',
        "no disk radius is measured, so the ring is drawn at a fixed 2.5 × the host's display radius, not scaled from any radius",
        WS7_RULE,
        ['missing-input'],
      );
    }
    const outerAu = (body.radius_km as number) * AU_PER_KM;
    return row(
      'drawn',
      prop,
      `ring to ${fmt(outerAu, 3)} AU`,
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
  if (!isSizeKnown(body)) {
    return row(
      'drawn',
      prop,
      `fixed marker, ${fmt(rc, 2)} scene units (${UNKNOWN_SIZE_TEXT})`,
      'not-drawn',
      `${UNKNOWN_SIZE_REASON} (the same marker for every body without a radius, then capped like the others: capRadii); the scene label says '${UNKNOWN_SIZE_TEXT}'`,
      WS7_RULE,
      ['missing-input'],
    );
  }
  const rAu = (body.radius_km as number) * AU_PER_KM;
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

/** The radius of a pulsating star: constant in both clocks, because its size change is not measured. */
function pulsationRow({ body, system }: Ctx): AppearanceNote | null {
  if (!drawsPulsation(body)) return null;
  const eph = miraEphemerisFor(system.id, body.id);
  return row(
    'drawn',
    'Pulsation (radius)',
    'radius drawn constant',
    'not-drawn',
    `the size change of this pulsating star is not measured, so its radius is drawn constant in both clocks (docs/VISION.md: a pulsation is drawn from a measured light curve, otherwise a static model); only the glow follows the ${body.variability?.band ?? 'visual'}-band light curve (catalog, not measured by SPHEREx; see the glow row)${eph ? `, which Dataset time dates with the ephemeris ${eph.source} (±${fmt(eph.timingSigmaDays, 2)} d timing band, 1σ)` : ''}; ${SPHEREX_LIGHT_CURVE_POINTER}`,
    eph ? `${WS7_RULE}; SCIENCE.md 3D review (V12b); ephemeris: ${eph.source}; timing band: ${eph.timingSource}` : `${WS7_RULE}; SCIENCE.md 3D review (V12b)`,
  );
}

function rotationRow({ body, system }: Ctx): AppearanceNote {
  const prop = 'Rotation';
  const spin = spinModel(body, system.bodies);
  if (spin.kind === 'period') {
    return row(
      'drawn',
      prop,
      `one turn per ${spin.periodText}`,
      spin.tier,
      `${spin.method}; drawn at P = ${fmt(spin.periodHours, 4)} h (${fmt(spin.periodHours / 24, 4)} d, the catalog's central value); angle = 2π · 24 · (MJD − 51544.5) / P_h, so scrubbing the time works; the rotational phase is not known (zero at J2000); the spin is held still while it would advance more than ${SPIN_ALIAS_MAX_DEG_PER_FRAME}° per rendered frame (aliasing guard)`,
      spin.citation,
    );
  }
  if (spin.kind === 'tidal-lock') {
    return row('drawn', prop, `tidally locked: one turn per orbit (${spin.periodText})`, spin.tier, `${spin.method}; not observed`, spin.citation);
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

function lightingRow({ body, system, d, synthetic }: Ctx): AppearanceNote {
  const prop = 'Lighting';
  const hues = (s: Body) => `visible ${hueHex(bodyLook(s, system, 'visible').hue)}, IR ${hueHex(bodyLook(s, system, 'ir').hue)}`;
  if (body.kind === 'star') {
    return row(
      'drawn',
      prop,
      synthetic
        ? `self-luminous; its light keeps its visible hue ${hueHex(bodyLook(body, system, 'visible').hue)} in every colour mode`
        : `self-luminous; its light takes its drawn hue (${hues(body)})`,
      'display',
      `a star is not lit: its disc comes from its own temperature (star shader). It carries a point light ${synthetic ? 'in its visible hue in every colour mode (the demo planets keep their visible look)' : 'in its hue of the current colour mode'}, with a display-normalised intensity (no 1/r² fall-off)`,
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
  if (bodyLook(body, system, 'ir').drawnAs === 'synthetic') {
    return row(
      'drawn',
      prop,
      stars.length ? `lit by ${stars.map((s) => s.name).join(', ')} in every colour mode (demo palette and texture)` : 'ambient light only',
      'display',
      `synthetic demo: the point light of each star in that star's visible hue, display-normalised with no 1/r² fall-off, plus a faint white ambient light; the body keeps its hand palette and procedural texture in every colour mode (decoration)${S}`,
      `${SYNTHETIC_CITE}; ${DISPLAY_CITE}`,
    );
  }
  return row(
    'drawn',
    prop,
    stars.length
      ? `visible: light of ${stars.map((s) => `${s.name} ${hueHex(bodyLook(s, system, 'visible').hue)}`).join(', ')}; SPHEREx modes: dark, with an outline`
      : 'ambient light only',
    'display',
    `the point light of each star in that star's drawn hue, display-normalised with no 1/r² fall-off, plus a faint white ambient light so the night side is not black; in the SPHEREx modes (false colour and single detectors) the body's SPHEREx-band emission and reflection are not modelled, so it is a dark sphere with a Fresnel outline${S}`,
    DISPLAY_CITE,
  );
}

function drawnRows(ctx: Ctx): AppearanceNote[] {
  const rows: (AppearanceNote | null)[] = [
    irColourRow(ctx),
    detectorColourRow(ctx),
    visibleColourRow(ctx),
    brightnessRow(ctx),
    glowRow(ctx),
    limbRow(ctx),
    surfaceRow(ctx),
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
