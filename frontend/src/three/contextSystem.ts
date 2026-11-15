// A 3D catalog model for ANY object picked on the map (V14, WS7-11), built in the browser from the object card
// (GET /api/object, contract ObjectContextResponse). Pure: no React, no three.js, no astro.ts (it ships with the
// position panel), tested in node.
//
// Same rules as the pipeline's snapshot builder (pipeline/errante/systems/measured.py system_from_snapshot):
//   - only stars and brown dwarfs are modelled, from a conservative reading of the SIMBAD object type (table
//     below); galaxies, QSOs, clusters, nebulae, radio/X-ray sources, unknown types and empty sky get a reason;
//   - the identity must be secure (match 'name' or 'matched'): an ambiguous or loose match gets a reason;
//   - Teff, radius and mass come only from VERIFIED facts with a readable number; anything else stays null
//     (drawn grey / at a fixed marker size) and is explained in the "Not measured, so not drawn" note that
//     factOrigin.unknownReasons reads, so the body panel shows the reason per body;
//   - variability only when AAVSO VSX gives a period (never an invented pulsation);
//   - planets only when confirmed, not controversial and with BOTH a published period and semi-major axis.
// Nothing here is measured by SPHEREx; every copied fact keeps its catalog source.
import { isEmptySky, isUnknown, matchSummary } from '../api/objectCard';
import type {
  Body,
  BodyKind,
  Fact,
  ObjectContextResponse,
  ObjectPlanet,
  SkyCoord,
  SpaceMotion,
  SystemModel,
  Variability,
  VariabilityKind,
} from '../api/types';
import { UNKNOWN_NOTE_PREFIX } from './factOrigin';

// Same constants as astro.PHYS (IAU 2015 B3 nominal values, CODATA 2018 G), so the drawn numbers read back
// as the facts they come from (astro.paramTier). Kept here so this module does not pull astro.ts in.
const G = 6.6743e-11;
export const R_SUN_KM = 695_700;
export const R_JUP_KM = 71_492;
export const R_EARTH_KM = 6_378.1;
export const M_SUN_KG = 1.3271244e20 / G;
export const M_JUP_KG = 1.2668653e17 / G;
export const M_EARTH_KG = 3.986004e14 / G;

export const CONTEXT_TAG = 'context-only';

export const CONTEXT_REPRESENTATION =
  'Catalog model built in the browser from the object card (Gaia DR3, SIMBAD, AAVSO VSX, NASA Exoplanet Archive): ' +
  'not measured by SPHEREx, and not an image. What the card does not give is not drawn: an unknown temperature is ' +
  'drawn neutral grey and an unknown size at a fixed marker size, not to scale.';

/** Appended to every "no 3D" reason: the card cannot see asteroids or comets, so it must not imply they are absent. */
export const SOLAR_SYSTEM_NOTE =
  'The object card does not look up solar-system bodies (asteroids, comets, planets) yet, so a moving body at this ' +
  'position would not be listed here: this is not evidence that none is there.';

export type ContextSystemResult = { system: SystemModel; reason?: undefined } | { system: null; reason: string };

// --- SIMBAD object types -------------------------------------------------------------------------------------

export type TypeClass =
  | { kind: 'star' | 'brown_dwarf'; candidate: boolean; binary: boolean }
  | { kind: 'planet' }
  | { kind: 'not-modelled'; what: string };

/** Non-stellar SIMBAD types (old and 2022 codes, candidates included), by what the reason calls them. */
const NOT_MODELLED: ReadonlyArray<readonly [string, readonly string[]]> = [
  ['a galaxy or group of galaxies', ['G', 'G?', 'GiG', 'GiC', 'GiP', 'BiC', 'IG', 'PaG', 'GrG', 'GrG?', 'CGG', 'ClG', 'ClG?', 'C?G', 'SCG', 'SC?', 'SCG?', 'LSB', 'bCG', 'SBG', 'H2G', 'EmG', 'rG', 'LeG', 'GG?', 'CG?', 'PoG']],
  ['an active galactic nucleus or quasar', ['AGN', 'AG?', 'AGN?', 'SyG', 'Sy1', 'Sy2', 'LIN', 'LI?', 'QSO', 'Q?', 'QSO?', 'Bla', 'Bz?', 'BLL', 'BL?', 'LeQ', 'Le?', 'LeI', 'gLe', 'gLS', 'Lev']],
  ['a star cluster, association or stream', ['Cl*', 'C?*', 'GlC', 'Gl?', 'GlC?', 'OpC', 'OpC?', 'As*', 'As?', 'St*', 'St?', 'MGr', 'MGr?']],
  ['a nebula or interstellar cloud', ['ISM', 'PN', 'PN?', 'HII', 'RNe', 'SNR', 'SNR?', 'SR?', 'Cld', 'GNe', 'BNe', 'DNe', 'MoC', 'glb', 'cor', 'SFR', 'HVC', 'bub', 'EmO', 'of?', 'out?', 'sh', 'HH', 'Cld?', 'MoC?']],
  ['a radio, infrared, X-ray or gamma-ray source without a stellar classification', ['Rad', 'mR', 'cm', 'mm', 'smm', 'HI', 'rB', 'Mas', 'IR', 'FIR', 'MIR', 'NIR', 'blu', 'UV', 'X', 'ULX', 'UX?', 'gam', 'gB', 'grv', 'Rad?']],
  ['a compact, explosive or accreting stellar remnant (not drawn as a plain star)', ['SN*', 'SN?', 'No*', 'No?', 'CV*', 'CV?', 'XB*', 'XB?', 'LXB', 'LX?', 'HXB', 'HX?', 'Psr', 'Psr?', 'BH', 'BH?', 'NS', 'N*?', 'N*', 'Mag', 'gLe?']],
  ['an object of unknown or uncertain nature', ['?', 'reg', 'err', 'PoC', 'ev', 'mul', 'vid', 'Unknown', 'Inexistent', 'Tra', 'Tr?', 'blend']],
];
const NOT_MODELLED_BY_CODE = new Map<string, string>(NOT_MODELLED.flatMap(([what, codes]) => codes.map((c) => [c, what] as const)));

/** Stellar codes that do not end in '*' (old 'HPM', young stellar objects) and stellar candidates (2022 '?' codes). */
const STELLAR_CODES = new Set(['*', 'HPM', 'Y*O', 'YSO', 'pr*', 'LM*', 'MS*', 'low-mass*', 'brownD*']);
const STELLAR_CANDIDATES = new Set([
  '*?', 'V*?', 'PM?', 'HV?', 'Y*?', 'TT?', 'Ae?', 'HB?', 'RB?', 'sg?', 's?r', 's?y', 's?b', 'AB?', 'LP?', 'Mi?', 'pA?',
  'WD?', 'LM?', 'Be?', 'BS?', 'SB?', 'EB?', 'C*?', 'S*?', 'OH?', 'WR?', 'Ce?', 'RR?', 'HS?', 'pr?', 'WU?', 'RS?', 'BY?', 'Er?', 'Ro?',
]);
/** Double / multiple / binary types: drawn as one body (the card resolves no components). */
const BINARY_CODES = new Set(['**', 'SB*', 'EB*', 'El*', 'Al*', 'bL*', 'WU*', 'RS*', '**?', 'SB?', 'EB?', 'WU?', 'RS?']);

/** Spectral class letter (O B A F G K M L T Y, carbon C, S, white dwarf D) of a SIMBAD spectral type, or null. */
export function spectralClass(spectralType: string | null | undefined): string | null {
  const m = /^\s*(?:sd|esd|usd|d|g|c)?([OBAFGKMLTYCSD])(?![a-z]{2})/.exec(spectralType ?? '');
  return m ? m[1] : null;
}

/** The SIMBAD object type, read conservatively: anything not clearly a star, brown dwarf or exoplanet is not modelled. */
export function classifyObjectType(objectType: string | null | undefined, spectralType?: string | null): TypeClass {
  const code = (objectType ?? '').trim();
  const sp = spectralClass(spectralType);
  const stellar = (candidate: boolean): TypeClass => ({
    kind: sp === 'L' || sp === 'T' || sp === 'Y' ? 'brown_dwarf' : 'star',
    candidate,
    binary: BINARY_CODES.has(code),
  });
  const known = NOT_MODELLED_BY_CODE.get(code);
  if (known) return { kind: 'not-modelled', what: known };
  if (code === 'Pl' || code === 'Pl?') return { kind: 'planet' };
  if (code.startsWith('BD')) return { kind: 'brown_dwarf', candidate: code.endsWith('?'), binary: false };
  if (STELLAR_CODES.has(code) || (code.endsWith('*') && code.length > 1)) return stellar(false);
  if (STELLAR_CANDIDATES.has(code)) return stellar(true);
  // No usable type: a stellar spectral class is still real SIMBAD data that says "star".
  if (!code && sp !== null) return stellar(false);
  return { kind: 'not-modelled', what: code ? 'an object type this viewer does not model' : 'an object with no SIMBAD type' };
}

// --- facts -----------------------------------------------------------------------------------------------------

/** The first number of a fact value such as "3100 (3099-3102)", "0.202", "1.2e5"; null when there is none. */
export function firstNumber(value: string): number | null {
  const m = /-?\d+(?:\.\d+)?(?:e[+-]?\d+)?/i.exec(value.replace(/−/g, '-'));
  if (!m) return null;
  const v = Number(m[0]);
  return Number.isFinite(v) ? v : null;
}

type Param = 'temperature' | 'radius' | 'mass';

const LABELS: Readonly<Record<Param | 'distance', RegExp>> = {
  temperature: /^((effective\s+)?temperature|t\s*_?eff)\b/i,
  radius: /^radius\b/i,
  mass: /^(minimum\s+)?mass\b/i,
  distance: /^distance\b/i,
};

/** Unit (lower-case, spaces collapsed) -> factor to K, km, kg or pc. */
const UNIT_FACTORS: Readonly<Record<Param | 'distance', Readonly<Record<string, number>>>> = {
  temperature: { k: 1, kelvin: 1 },
  radius: {
    km: 1, r_sun: R_SUN_KM, rsun: R_SUN_KM, 'solar radii': R_SUN_KM, 'solar radius': R_SUN_KM,
    r_jup: R_JUP_KM, 'jupiter radii': R_JUP_KM, r_earth: R_EARTH_KM, 'earth radii': R_EARTH_KM,
  },
  mass: {
    kg: 1, m_sun: M_SUN_KG, msun: M_SUN_KG, 'solar masses': M_SUN_KG, 'solar mass': M_SUN_KG,
    m_jup: M_JUP_KG, 'jupiter masses': M_JUP_KG, m_earth: M_EARTH_KG, 'earth masses': M_EARTH_KG,
  },
  distance: { pc: 1, parsec: 1, parsecs: 1 },
};

const trimDot = (s: string) => s.trim().replace(/\.+\s*$/, '');

/** A drawn value from the card's facts, or null with the reason it stays unknown. */
export function factValue(facts: readonly Fact[], param: Param | 'distance'): { value: number; fact: Fact } | { value: null; reason: string } {
  const fact = facts.find((f) => LABELS[param].test(f.label.trim()));
  if (!fact) return { value: null, reason: `the object card gives no ${param}` };
  if (isUnknown(fact.value)) return { value: null, reason: trimDot(fact.source || `no ${param} in the catalogs queried`) };
  if (!fact.verified) return { value: null, reason: `the catalog value ${fact.value}${fact.unit ? ` ${fact.unit}` : ''} is not verified` };
  const unit = (fact.unit ?? '').trim().toLowerCase().replace(/\s+/g, ' ');
  const factor = UNIT_FACTORS[param][unit];
  if (factor === undefined) return { value: null, reason: `unit '${fact.unit ?? ''}' of the catalog value is not recognised` };
  const v = firstNumber(fact.value);
  if (v === null || !(v > 0)) return { value: null, reason: `the catalog value '${fact.value}' is not a positive number` };
  return { value: v * factor, fact };
}

// --- variability -----------------------------------------------------------------------------------------------

/** True when the VSX type includes a planetary transit (EP): the period is the planet's, not the star's. */
export function isPlanetTransitType(varType: string | null | undefined): boolean {
  return (varType ?? '').toUpperCase().split(/[\s/+|:(),]+/).includes('EP');
}

/**
 * Kind of a VSX/GCVS variability type with a period, or null when the type does not say. A planetary transit (EP)
 * and a combined type whose parts are of different kinds (e.g. 'EP+BY': one period, two phenomena, and the
 * amplitude may belong to either) are never animated.
 */
export function variabilityKind(varType: string | null | undefined): VariabilityKind | null {
  const tokens = (varType ?? '').toUpperCase().split(/[\s/+|:(),]+/).filter(Boolean);
  if (tokens.includes('EP')) return null;
  const kindOf = (t: string): VariabilityKind | null => {
    if (/^(E|EA|EB|EW|EC)$/.test(t)) return 'eclipse';
    if (/^(ROT|BY|RS|ELL|ACV|SXARI|SPOT)$/.test(t)) return 'rotation';
    if (/^(M|SR[ABCDS]?|L[BC]?|RR(AB|C|D)?|CEP|DCEP(S)?|CW(A|B)?|DSCT(C)?|HADS|GDOR|BCEP(S)?|RV(A|B)?|ZZ[ABO]?|SXPHE|ACYG|LPV)$/.test(t)) return 'pulsation';
    return null;
  };
  const kinds = new Set(tokens.map(kindOf).filter((k): k is VariabilityKind => k !== null));
  return kinds.size === 1 ? [...kinds][0] : null;
}

function bodyVariability(ctx: ObjectContextResponse, notes: string[]): Variability | null {
  const v = ctx.variability;
  if (!v || v.period_days === null || !(v.period_days > 0)) return null;
  const periodFact = ctx.facts.find((f) => /^variability\s+period\b/i.test(f.label.trim()));
  if (periodFact && !periodFact.verified) {
    notes.push(`AAVSO VSX period ${v.period_days} d is not drawn: the object card does not verify it.`);
    return null;
  }
  const kind = variabilityKind(v.var_type);
  if (!kind && isPlanetTransitType(v.var_type)) {
    notes.push(`AAVSO VSX period ${v.period_days} d (type ${v.var_type}) is a planetary transit: the planet is drawn on its own orbit, and the star's brightness is not animated.`);
    return null;
  }
  if (!kind) {
    notes.push(`AAVSO VSX period ${v.period_days} d (type ${v.var_type ?? 'not given'}) is not animated: the type does not say whether it is a pulsation, a rotation or an eclipse.`);
    return null;
  }
  let amplitude: number | null = null;
  if (v.min_is_amplitude && v.mag_min !== null && v.mag_min > 0) amplitude = v.mag_min;
  else if (!v.min_is_amplitude && v.mag_min !== null && v.mag_max !== null && v.mag_min > v.mag_max) amplitude = Number((v.mag_min - v.mag_max).toFixed(3));
  return { kind, period_days: v.period_days, amplitude_mag: amplitude, band: v.passband };
}

// --- planets ---------------------------------------------------------------------------------------------------

export function slug(text: string): string {
  return text.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '');
}

const GOLDEN_ANGLE_DEG = 137.50776405;

/**
 * Label and source suffix of a planet mass from the archive's pl_bmassprov (pscomppars, 2026-11-15: 'Msini',
 * 'Mass', 'Msin(i)/sin(i)', 'M-R relationship'). Only 'Msini' is a lower bound; an 'M-R relationship' mass is
 * calculated by the archive from the radius, so it is labelled a model estimate (astro.paramTier reads the label).
 */
export function massProvenance(kind: string | null | undefined): { label: string; suffix: string; minimum: boolean } {
  const k = (kind ?? '').trim();
  if (/^m\s*sin\s*i$/i.test(k)) return { label: 'Minimum mass', suffix: '; M sin i, a lower bound', minimum: true };
  if (/^m\s*-\s*r\s+relation/i.test(k)) {
    return { label: 'Mass (model estimate)', suffix: '; calculated from the radius with a mass-radius relation, not measured', minimum: false };
  }
  if (/sin\s*\(\s*i\s*\)\s*\/\s*sin/i.test(k)) {
    return { label: 'Mass', suffix: '; from M sin i divided by sin i (a published inclination)', minimum: false };
  }
  return { label: 'Mass', suffix: '', minimum: false };
}

function planetBody(p: ObjectPlanet, parentId: string, index: number, id: string): Body {
  const src = `${p.source || 'NASA Exoplanet Archive'}${p.reference ? ` (${p.reference})` : ''}`;
  const facts: Fact[] = [
    { label: 'Orbital period', value: String(p.period_days), unit: 'days', source: src, verified: true },
    { label: 'Orbit size', value: String(p.semi_major_axis_au), unit: 'AU', source: src, verified: true },
  ];
  const e = p.eccentricity !== null && p.eccentricity >= 0 && p.eccentricity < 1 ? p.eccentricity : null;
  if (e !== null) facts.push({ label: 'Eccentricity', value: String(e), unit: null, source: src, verified: true });
  let massKg: number | null = null;
  if (p.mass_earth !== null && p.mass_earth > 0) {
    const m = massProvenance(p.mass_kind);
    facts.push({ label: m.label, value: String(p.mass_earth), unit: 'Earth masses', source: src + m.suffix, verified: true });
    massKg = p.mass_earth * M_EARTH_KG;
  }
  let radiusKm: number | null = null;
  if (p.radius_earth !== null && p.radius_earth > 0) {
    facts.push({ label: p.radius_calculated ? 'Radius (model estimate)' : 'Radius', value: String(p.radius_earth),
      unit: 'Earth radii', source: src + (p.radius_calculated ? '; calculated from the mass, not measured' : ''), verified: true });
    radiusKm = p.radius_earth * R_EARTH_KM;
  }
  if (p.discovery_method) {
    facts.push({ label: 'Discovery', value: [p.discovery_method, p.discovery_year].filter((x) => x !== null).join(', '),
      unit: null, source: src, verified: true });
  }
  const giant = p.mass_earth !== null ? p.mass_earth >= 10 : p.radius_earth !== null ? p.radius_earth >= 4 : false;
  return {
    id,
    name: p.name,
    kind: 'planet',
    description: 'Confirmed planet from the NASA Exoplanet Archive (catalog values, not measured by SPHEREx).',
    radius_km: radiusKm,
    mass_kg: massKg,
    teff_k: null,
    spectral_type: null,
    rotation_period_hours: null,
    orbit: {
      parent: parentId,
      semi_major_axis_au: p.semi_major_axis_au as number,
      period_days: p.period_days as number,
      eccentricity: e ?? 0,
      inclination_deg: 0,
      ascending_node_deg: 0,
      arg_periapsis_deg: 0,
      // Arbitrary phase (epoch null): spread with the golden angle so the planets do not sit in a line.
      mean_anomaly_deg: (index * GOLDEN_ANGLE_DEG) % 360,
      epoch_mjd: null,
      quality: 'fitted',
      note: `${e === null ? 'Eccentricity not published: drawn circular. ' : ''}Period and orbit size from the NASA Exoplanet Archive; orbit orientation and phase are not modelled (phase unknown, starting position arbitrary).`,
    },
    variability: null,
    appearance: { model: giant ? 'gas_giant' : 'rocky', color_hex: null, mesh_url: null, texture_url: null },
    facts,
    candidate_id: null,
  };
}

// --- the system ------------------------------------------------------------------------------------------------

// --- catalog services --------------------------------------------------------------------------------------------

/** Short names of the object card's services (provenance `service`), as the reasons cite them. */
const SERVICE_LABELS: Readonly<Record<string, string>> = {
  sesame: 'SIMBAD (Sesame, CfA)', 'gaia-esa': 'Gaia DR3', 'gaia-vizier': 'Gaia DR3', vsx: 'AAVSO VSX', '2mass': '2MASS',
  allwise: 'AllWISE', exoplanets: 'the NASA Exoplanet Archive',
};

/** Distinct names of the services whose provenance rows answered (ok / no_match) or failed (error). */
function servicesWith(ctx: ObjectContextResponse, answered: boolean, exclude: readonly string[] = []): string[] {
  const names = (ok: boolean) => new Set(ctx.provenance
    .filter((p) => !exclude.includes(p.service) && (ok ? p.status === 'ok' || p.status === 'no_match' : p.status === 'error'))
    .map((p) => SERVICE_LABELS[p.service] ?? p.service));
  const up = names(true);
  // A catalog with one failed mirror and one that answered (ESA Gaia down, VizieR CfA Gaia DR3 up) answered.
  return answered ? [...up] : [...names(false)].filter((n) => !up.has(n));
}

function failed(ctx: ObjectContextResponse, service: string): boolean {
  return ctx.provenance.some((p) => p.service === service && p.status === 'error');
}

/** Whether SIMBAD answered, failed, or was never asked (by position it is asked only through a Gaia DR3 source). */
function simbadStatus(ctx: ObjectContextResponse): 'answered' | 'failed' | 'not-queried' {
  const rows = ctx.provenance.filter((p) => p.service === 'sesame');
  if (rows.some((p) => p.status === 'ok' || p.status === 'no_match')) return 'answered';
  return rows.some((p) => p.status === 'error') ? 'failed' : 'not-queried';
}

/** 'A, B and C', starting a sentence (first letter upper-case). */
function listText(items: readonly string[]): string {
  const text = items.length <= 1 ? items.join('') : `${items.slice(0, -1).join(', ')} and ${items[items.length - 1]}`;
  return text.charAt(0).toUpperCase() + text.slice(1);
}

const SIMBAD_NOT_CHECKED =
  'SIMBAD is reached only through a Gaia DR3 source, so it was not checked here: an object absent from Gaia DR3 ' +
  '(a faint galaxy, a nebula, a cold brown dwarf) would not be identified.';

/** Services that did not answer, as a gap sentence ('' when all answered). */
function gapText(ctx: ObjectContextResponse, exclude: readonly string[] = []): string {
  const down = servicesWith(ctx, false, exclude);
  return down.length ? ` ${listText(down)} did not answer (a gap, not a negative result).` : '';
}

// --- the system ------------------------------------------------------------------------------------------------

function noModel(ctx: ObjectContextResponse, reason: string): ContextSystemResult {
  const parts = [reason];
  if (ctx.partial && !/did not answer/.test(reason)) {
    parts.push('Some catalog services did not answer (see the object card), so a retry may change this.');
  }
  // The 3D tab may look up a position that came from a name search (the J2000 catalog position): say what a
  // position lookup can miss, so a mismatch with the object card (looked up by name) is not read as a negative.
  if (ctx.query.name === null) {
    parts.push(`This 3D lookup is by position (Gaia DR3 within ${ctx.query.radius_arcsec}″ at epoch MJD ${ctx.query.epoch_mjd}), not by name: a high proper-motion star or a star absent from Gaia DR3 can be missed here even when the object card, looked up by name, identifies it.`);
  }
  parts.push(SOLAR_SYSTEM_NOTE);
  return { system: null, reason: parts.join(' ') };
}

function typeText(ctx: ObjectContextResponse): string {
  const id = ctx.identity;
  if (!id.object_type) return 'no SIMBAD object type';
  return `SIMBAD type '${id.object_type}'${id.object_type_label ? ` (${id.object_type_label})` : ''}`;
}

const isSimbadFact = (f: Fact) => /^simbad\b/i.test((f.source ?? '').trim());

/**
 * The catalog 3D model of the object the card identified at `position`, or null with the reason why no model is
 * drawn. Only real catalog values: nothing unknown or unverified is drawn.
 */
export function systemFromObjectContext(ctx: ObjectContextResponse, position: SkyCoord): ContextSystemResult {
  const id = ctx.identity;
  const simbad = simbadStatus(ctx);
  const simbadUnchecked = simbad === 'not-queried' ? ` ${SIMBAD_NOT_CHECKED}` : '';
  if (isEmptySky(ctx)) {
    const quiet = servicesWith(ctx, true, ['sesame', 'gaia-esa', 'gaia-vizier']);
    return noModel(ctx, `Nothing the object card could identify at this position: ${matchSummary(ctx).detail}`
      + (quiet.length ? ` ${listText(quiet)} answered with nothing here.` : '')
      + `${gapText(ctx, ['gaia-esa', 'gaia-vizier'])}${simbadUnchecked} No 3D model is drawn.`);
  }
  if (id.match === 'unavailable') {
    return noModel(ctx, 'Gaia DR3 could not be reached, so the identity at this position is unknown (a gap, not a negative result): retry later.');
  }
  if (!id.object_type && simbad === 'failed') {
    return noModel(ctx, 'SIMBAD (Sesame CfA) did not answer, so the object type is unknown (a gap, not a negative result): no 3D model is drawn; retry later.');
  }
  if (id.match === 'none' && !id.object_type) {
    const m = matchSummary(ctx);
    // matchSummary's position label ("No catalogued source") is meant for an empty sky; here something is catalogued.
    const label = ctx.query.name !== null ? m.label : 'Nothing identified at this position';
    return noModel(ctx, `${label}: ${m.detail}${simbadUnchecked}${gapText(ctx)} The object type is unknown, so no 3D model is drawn.`);
  }
  const insecure = id.match !== 'name' && id.match !== 'matched';
  const identityReason = () => {
    const m = matchSummary(ctx);
    return noModel(ctx, `${m.label}: ${m.detail} A 3D model needs a secure identity, so none is drawn.`);
  };
  // With no SIMBAD type the insecure identity is the reason (a type reason would describe a possible neighbour).
  if (insecure && !id.object_type) return identityReason();
  if (!id.object_type && !id.spectral_type && simbad === 'not-queried') {
    return noModel(ctx, 'SIMBAD was not queried for this source (see the object card\'s catalog services), so the object type is unknown (a gap, not a negative result): no 3D model is drawn.');
  }
  const cls = classifyObjectType(id.object_type, id.spectral_type);
  if (cls.kind === 'not-modelled') {
    return noModel(ctx, `The object card identifies ${typeText(ctx)}: ${cls.what}. This viewer draws only stars, brown dwarfs and their confirmed planets, so no 3D model is drawn.`);
  }
  if (insecure) return identityReason();
  const notes: string[] = [];
  let rootName = id.display_name ?? id.main_id ?? 'Selected object';
  let rootDescription: string | null = null;
  let rootSpectralType = id.spectral_type;
  // SIMBAD facts of a planet entry describe the planet, not its host: kept off the host body.
  let cardFacts: readonly Fact[] = ctx.facts;
  let kind: BodyKind;
  if (cls.kind === 'planet') {
    const what = id.object_type === 'Pl?' ? 'a candidate exoplanet' : 'an exoplanet';
    if (ctx.query.name === null) {
      // By position, SIMBAD was asked about the adopted Gaia DR3 source itself and typed THAT source a planet.
      return noModel(ctx, `The object card identifies ${typeText(ctx)}: SIMBAD lists the adopted Gaia DR3 source ${id.gaia_source_id ?? ''} itself as ${what}, so its Gaia DR3 values cannot be given to a host star: no 3D model is drawn.`.replace(/ {2,}/g, ' '));
    }
    // The archive must tie the adopted Gaia DR3 source to the host (its gaia_dr3_id), or the facts may be another star's.
    const host = ctx.planets.find((p) => p.match === 'gaia_dr3_id')?.hostname;
    cardFacts = ctx.facts.filter((f) => !isSimbadFact(f));
    const hasHostFacts = !!id.gaia_source_id && (['temperature', 'radius', 'mass'] as const)
      .some((p) => factValue(cardFacts, p).value !== null);
    if (!host || !hasHostFacts) {
      return noModel(ctx, `The object card identifies ${typeText(ctx)}: ${what}. The card does not tie a host star with catalog parameters to the adopted Gaia DR3 source (the NASA Exoplanet Archive lists no host with that Gaia DR3 id, or Gaia DR3 gives it no temperature, radius or mass), so no 3D model is drawn.`);
    }
    notes.push(`SIMBAD lists ${rootName} as ${what}${id.object_type === 'Pl?' ? ' (a candidate: it may not be a planet)' : ''}: the model draws its host star ${host} (the NASA Exoplanet Archive gives Gaia DR3 ${id.gaia_source_id} as its Gaia DR3 id) from Gaia DR3, and the archive's confirmed planets. SIMBAD values of the planet entry (such as its spectral type) are not given to the host.`);
    rootDescription = `Host star of ${rootName} (${typeText(ctx)}): Gaia DR3 catalog values only, not measured by SPHEREx.`;
    rootName = host;
    rootSpectralType = null;
    kind = 'star';
  } else {
    kind = cls.kind;
    if (cls.candidate) notes.push(`${typeText(ctx)} marks a candidate: the object may not be what the type says.`);
    if (cls.binary) notes.push(`${typeText(ctx)} is a double, multiple or binary star: drawn as one body, because the object card resolves no components.`);
    const sp = spectralClass(id.spectral_type);
    if (kind === 'brown_dwarf' && !id.object_type?.startsWith('BD')) {
      notes.push(`Drawn as a brown dwarf from its spectral class ${sp} (${id.spectral_type}): a display choice; early L dwarfs can be very-low-mass stars.`);
    }
    if (/\+\s*[OBAFGKMLTYD]/.test(id.spectral_type ?? '')) {
      notes.push(`SIMBAD's spectral type ${id.spectral_type} is composite (more than one component, unresolved): drawn as one body; a single catalog value may describe the blend or one component.`);
    }
    if (!id.object_type) notes.push(`No SIMBAD object type: classed as a ${kind === 'star' ? 'star' : 'brown dwarf'} from its spectral type ${id.spectral_type}.`);
  }

  const rootId = slug(rootName) || 'object';
  const unknown: string[] = [];
  const rootUnknown: string[] = [];
  const read = (p: Param) => {
    const r = factValue(cardFacts, p);
    if (r.value === null) rootUnknown.push(`${p} (${r.reason})`);
    return r.value;
  };
  const teff = read('temperature');
  const radius = read('radius');
  const mass = read('mass');
  if (rootUnknown.length) unknown.push(`${rootName}: ${rootUnknown.join(', ')}`);

  // Only verified facts with a value are attached (an 'unknown' Fact would read as an unverified value).
  const facts = cardFacts.filter((f) => f.verified && !isUnknown(f.value));
  const root: Body = {
    id: rootId,
    name: rootName,
    kind,
    description: rootDescription ?? `${id.object_type_label ?? (kind === 'star' ? 'Star' : 'Brown dwarf')} from the object card: catalog values only, not measured by SPHEREx.`,
    radius_km: radius,
    mass_kg: mass,
    teff_k: teff,
    spectral_type: rootSpectralType,
    rotation_period_hours: null,
    orbit: null,
    variability: bodyVariability(ctx, notes),
    appearance: { model: kind === 'brown_dwarf' ? 'brown_dwarf' : 'star', color_hex: null, mesh_url: null, texture_url: null },
    facts,
    candidate_id: null,
  };

  const bodies: Body[] = [root];
  const notDrawn: string[] = [];
  const controversial: string[] = [];
  // A planet entry's host: only the planets the archive gives for that host (never a neighbour's).
  const planets = cls.kind === 'planet' ? ctx.planets.filter((p) => p.hostname === rootName) : ctx.planets;
  for (const p of planets) {
    if (p.controversial) {
      controversial.push(p.name);
      continue;
    }
    if (!(p.period_days !== null && p.period_days > 0 && p.semi_major_axis_au !== null && p.semi_major_axis_au > 0)) {
      notDrawn.push(p.name);
      continue;
    }
    let pid = slug(p.name) || `planet-${bodies.length}`;
    while (bodies.some((b) => b.id === pid)) pid = `${pid}-${bodies.length}`;
    const body = planetBody(p, rootId, bodies.length - 1, pid);
    if (body.radius_km === null) unknown.push(`${p.name}: radius (not in the NASA Exoplanet Archive)`);
    bodies.push(body);
  }

  const distance = factValue(cardFacts, 'distance');
  const motion: SpaceMotion | null = distance.value !== null
    ? { distance_pc: distance.value, parallax_mas: null, pm_ra_cosdec_mas_yr: null, pm_dec_mas_yr: null, radial_velocity_km_s: null, epoch: null }
    : null;

  notes.unshift(`Values from the object card built ${ctx.built_at.slice(0, 16).replace('T', ' ')} UTC (Gaia DR3, SIMBAD, AAVSO VSX, NASA Exoplanet Archive): catalog values, not measured by SPHEREx. Proper motion is not in the card and is not drawn.`);
  if (id.identity_uncertain) notes.push('Warning: the identity of the adopted catalog source is uncertain (it may be a neighbour): values that depend on it may not belong to this object.');
  if (ctx.partial) notes.push('Some catalog services did not answer (see the object card): values shown as unknown may be gaps, not negative results.');
  if (failed(ctx, 'exoplanets') && !ctx.planets.length) {
    notes.push('Confirmed planets unknown: the NASA Exoplanet Archive did not answer, so no planets are drawn (a gap, not a negative result).');
  }
  for (const w of ctx.warnings) notes.push(`Object card warning: ${w}`);
  if (unknown.length) notes.push(`${UNKNOWN_NOTE_PREFIX}${unknown.join('; ')}.`);
  if (notDrawn.length) notes.push(`Planets not drawn: no published period and orbit size: ${notDrawn.join(', ')}.`);
  if (controversial.length) notes.push(`Planets not drawn: flagged controversial in the NASA Exoplanet Archive: ${controversial.join(', ')}.`);
  if (bodies.length > 1) notes.push('Planet appearance classes are display choices (rocky below 10 Earth masses, or below 4 Earth radii when only the radius is published; gas giant above), not a measured composition.');
  if (ctx.nearby_planet_hosts.length) {
    notes.push(`Confirmed planet host(s) nearby but NOT this object, not drawn: ${ctx.nearby_planet_hosts
      .map((h) => `${h.hostname} (~${Math.round(h.separation_arcsec)}″; ${h.planets.join(', ')})`).join(', ')}.`);
  }

  const center = ctx.position ? { ra: ctx.position.ra, dec: ctx.position.dec } : { ra: position.ra, dec: position.dec };
  const systemSlug = slug(cls.kind === 'planet' ? rootName : id.main_id ?? id.display_name ?? '') || `${position.ra.toFixed(5)}-${position.dec.toFixed(5)}`.replace(/[^0-9-]+/g, '-');
  return {
    system: {
      id: `context-${systemSlug}`.replace(/-+/g, '-'),
      name: rootName,
      description: `Catalog model of ${rootName} built in the browser from the object card: ${cls.kind === 'planet' ? `host star of ${id.display_name ?? id.main_id ?? 'the planet'} (${typeText(ctx)})` : typeText(ctx)}. Not measured by SPHEREx, not an image.`,
      tags: [CONTEXT_TAG],
      center,
      motion,
      field_id: null,
      bodies,
      representation_note: CONTEXT_REPRESENTATION,
      provenance: { pipeline_version: 'browser (three/contextSystem.ts)', built_at: ctx.built_at, synthetic: false, data_releases: [], notes },
    },
  };
}
