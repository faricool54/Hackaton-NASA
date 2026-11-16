// Where a Fact comes from, and which drawn body values are unknown. Pure and astro-free (no three.js,
// no astro.ts), so BodyPanel can import it from the main chunk.
//
// Fact origin, read from the Fact itself (contract 0.7.0 has no origin field; WS7 convention, V13):
//   'spherex'  Fact.source starts with "SPHEREx": a value measured on SPHEREx data (offline analysis of
//              the FITS files, copied from the validation records; guided human review on 2026-11-15,
//              which did not re-run the analyses)
//   'derived'  the label contains "(derived": computed by WS7 from other values, the source says from what
//   'catalog'  a catalog or literature value (Gaia DR3, SIMBAD, VSX, NASA Exoplanet Archive, papers),
//              not measured by SPHEREx
//   'unsourced' a real-system fact with no source text (none ships today; never called catalog)
//   'synthetic' every fact of the synthetic demo system (provenance.synthetic): not a catalog value
//
// Unknown drawn values (docs/VISION.md: what is not measured is not drawn, or is shown as unknown):
//   colour  a star or brown dwarf without Teff is drawn neutral grey, never at a guessed temperature
//   size    a body without a radius is drawn at a fixed marker size, not scaled from any radius
import type { Body, Fact } from '../api/types';

export type FactOrigin = 'spherex' | 'derived' | 'catalog' | 'unsourced' | 'synthetic';

/** Chip text of each origin. */
export const FACT_ORIGIN_LABEL: Readonly<Record<FactOrigin, string>> = {
  spherex: 'SPHEREx-measured (offline)',
  derived: 'derived',
  catalog: 'catalog, not measured by SPHEREx',
  unsourced: 'no source given',
  synthetic: 'synthetic demo',
};

/** One-line meaning of each origin (chip tooltip). */
export const FACT_ORIGIN_MEANING: Readonly<Record<FactOrigin, string>> = {
  spherex: 'Measured on SPHEREx data: offline analysis of the SPHEREx FITS files (see the source line; its validation record had a guided human review on 2026-11-15 that did not re-run the analyses)',
  derived: 'Computed from other values with the relation named in the source; not measured by SPHEREx',
  catalog: 'A catalog or literature value (Gaia, SIMBAD, VSX, NASA Exoplanet Archive or a paper), not measured by SPHEREx',
  unsourced: 'No source is given for this value: treat it as unverified',
  synthetic: 'Part of the synthetic demo system: made up to show the viewer, not a measurement or a catalog value',
};

const SPHEREX_SOURCE = /^\s*SPHEREx\b/;
const DERIVED_LABEL = /\(derived/i;

/**
 * Origin of one Fact (see the header). `synthetic` is the system's provenance.synthetic: every fact of the
 * synthetic demo is 'synthetic', whatever its source text says.
 */
export function factOrigin(fact: Pick<Fact, 'label' | 'source'>, synthetic = false): FactOrigin {
  if (synthetic) return 'synthetic';
  if (SPHEREX_SOURCE.test(fact.source ?? '')) return 'spherex';
  if (DERIVED_LABEL.test(fact.label)) return 'derived';
  if (!fact.source || !fact.source.trim()) return 'unsourced';
  return 'catalog';
}

/** Label of a body whose radius is unknown (scene label suffix, legends and panel rows). */
export const UNKNOWN_SIZE_TEXT = 'size unknown · not to scale';

/** Colour of a star or brown dwarf whose Teff is unknown. */
export const UNKNOWN_COLOUR_TEXT = 'colour unknown (no single temperature adopted)';

/**
 * Why the size is unknown, in plain words: the generic fallback. The body's own reason, when the pipeline
 * wrote one, is in the system note read by unknownReason().
 */
export const UNKNOWN_SIZE_REASON =
  'no single radius is adopted for this body (none is published, or the published ones depend on assumptions: see its facts and the system notes), so it is drawn at a fixed marker size, not scaled';

/** Why the colour is unknown, in plain words: the generic fallback (see UNKNOWN_SIZE_REASON). */
export const UNKNOWN_COLOUR_REASON =
  'no single effective temperature is adopted for this body (none is published, or only a range: see its facts and the system notes) and no SPHEREx spectral fit exists yet, so it is drawn neutral grey';

/** Prefix of the provenance note the pipeline writes for the unknown drawn values (systems/measured.py). */
export const UNKNOWN_NOTE_PREFIX = 'Not measured, so not drawn (shown as unknown): ';

/** The drawn values the note can name, as the pipeline names them (measured.py PARAM_NAMES). */
export type UnknownParam = 'temperature' | 'radius' | 'mass';

/** Split `text` at `sep`, but only outside parentheses (the reasons cite papers in brackets). */
function splitTopLevel(text: string, sep: string): string[] {
  const out: string[] = [];
  let depth = 0;
  let start = 0;
  for (let i = 0; i < text.length; i++) {
    const c = text[i];
    if (c === '(') depth++;
    else if (c === ')') depth = Math.max(0, depth - 1);
    else if (depth === 0 && text.startsWith(sep, i)) {
      out.push(text.slice(start, i));
      start = i + sep.length;
      i += sep.length - 1;
    }
  }
  out.push(text.slice(start));
  return out;
}

/**
 * The per-body reasons of the unknown drawn values, read from the system note
 * "Not measured, so not drawn (shown as unknown): <body>: <param> (<reason>), <param> (<reason>); <body>: ...".
 * Keyed by body name, then parameter. Empty when the system has no such note.
 */
export function unknownReasons(
  system: { provenance: { notes: readonly string[] } },
): Map<string, Partial<Record<UnknownParam, string>>> {
  const out = new Map<string, Partial<Record<UnknownParam, string>>>();
  for (const note of system.provenance.notes) {
    if (!note.startsWith(UNKNOWN_NOTE_PREFIX)) continue;
    const body = note.slice(UNKNOWN_NOTE_PREFIX.length).replace(/\.\s*$/, '');
    for (const entry of splitTopLevel(body, '; ')) {
      const parts = splitTopLevel(entry, ': ');
      if (parts.length < 2) continue;
      const name = parts[0].trim();
      const params = out.get(name) ?? {};
      for (const item of splitTopLevel(parts.slice(1).join(': '), ', ')) {
        const m = /^\s*(temperature|radius|mass)\s*\(([\s\S]*)\)\s*$/.exec(item);
        if (m) params[m[1] as UnknownParam] = m[2].trim();
      }
      out.set(name, params);
    }
  }
  return out;
}

/** The pipeline's reason why one drawn value of this body is unknown, or null when it wrote none. */
export function unknownReason(
  system: { provenance: { notes: readonly string[] } },
  body: Pick<Body, 'name'>,
  param: UnknownParam,
): string | null {
  return unknownReasons(system).get(body.name)?.[param] ?? null;
}

/** Stars and brown dwarfs: their colour comes from Teff. */
export function isStellarKind(body: Pick<Body, 'kind'>): boolean {
  return body.kind === 'star' || body.kind === 'brown_dwarf';
}

/** False only for a star or brown dwarf without a positive Teff (other kinds never take a colour from Teff). */
export function isColourKnown(body: Pick<Body, 'kind' | 'teff_k'>): boolean {
  return !isStellarKind(body) || (typeof body.teff_k === 'number' && body.teff_k > 0);
}

/** True when the body has a positive radius (for a disk: its outer radius). */
export function isSizeKnown(body: Pick<Body, 'radius_km'>): boolean {
  return typeof body.radius_km === 'number' && body.radius_km > 0;
}

/** Scene label of a body: its name, plus the unknown-size suffix when no radius is known. */
export function bodyLabelText(body: Pick<Body, 'name' | 'radius_km'>): string {
  return isSizeKnown(body) ? body.name : `${body.name} · ${UNKNOWN_SIZE_TEXT}`;
}

// --- The fact behind a drawn value (compact body panel, FE-12) --------------------------------------------

/** The drawn values the compact body panel shows with the label of the fact that gives them. */
export type KeyQuantity = 'temperature' | 'radius';

const KEY_LABEL: Readonly<Record<KeyQuantity, RegExp>> = {
  temperature: /\b(temperature|t\s*_?eff)\b/i,
  radius: /\bradius\b/i,
};

/** Unit (lower-case, spaces collapsed) -> factor to K or km (IAU 2015 nominal radii, as the pipeline uses). */
const KEY_UNIT: Readonly<Record<KeyQuantity, Readonly<Record<string, number>>>> = {
  temperature: { k: 1, kelvin: 1 },
  radius: {
    km: 1,
    'solar radii': 695_700, 'solar radius': 695_700, r_sun: 695_700, rsun: 695_700,
    'jupiter radii': 71_492, r_jup: 71_492,
    'earth radii': 6_371, r_earth: 6_371,
    au: 149_597_870.7,
  },
};

/** The first number of a fact value ("3195 ± 28", "~0.69", "15.8 (+1.7/−1.4)"); null when there is none. */
function firstNumber(value: string): number | null {
  const m = /\d+(?:\.\d+)?(?:e[+-]?\d+)?/i.exec(value);
  const v = m ? Number(m[0]) : NaN;
  return Number.isFinite(v) ? v : null;
}

/**
 * The fact that gives a drawn value (Teff in K, radius in km), so a short view can show that value under the
 * fact's own label ("Radius (model estimate)"), origin and verified flag instead of a bare "Radius". The
 * candidates are the facts whose label names the quantity; with more than one (Barnard's Star lists a catalog
 * and a Gaia radius), the one whose value (first number x unit) is nearest the drawn value wins, and a value that
 * cannot be read ranks last. Null when no fact names the quantity.
 */
export function keyFact<F extends Pick<Fact, 'label' | 'value' | 'unit'>>(
  facts: readonly F[],
  quantity: KeyQuantity,
  drawn: number,
): F | null {
  const candidates = facts.filter((f) => KEY_LABEL[quantity].test(f.label));
  if (candidates.length <= 1 || !(drawn > 0)) return candidates[0] ?? null;
  let best = candidates[0];
  let bestDistance = Infinity;
  for (const f of candidates) {
    const factor = KEY_UNIT[quantity][(f.unit ?? '').trim().toLowerCase().replace(/\s+/g, ' ')];
    const v = firstNumber(f.value);
    if (factor === undefined || v === null || !(v > 0)) continue;
    const distance = Math.abs(Math.log((v * factor) / drawn));
    if (distance < bestDistance) {
      best = f;
      bestDistance = distance;
    }
  }
  return best;
}
