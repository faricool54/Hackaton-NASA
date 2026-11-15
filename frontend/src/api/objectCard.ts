// Pure formatting/state logic of the object card (GET /api/object, contract 0.5.0). No DOM: tested in node.
// Every value here is CATALOG context from other missions/surveys, never a SPHEREx measurement.
import { ApiError } from './client';
import type {
  ContextMagnitude, ContextService, Fact, ObjectContextResponse, ObjectPlanet, ObjectVariability,
} from './types';
import { SHOWCASE_TARGETS } from './showcase';

/** What the card looks up: presets and name searches by NAME (better identity), map clicks by position. */
export type ObjectLookup = { name: string } | { ra: number; dec: number };
export type Tone = 'ok' | 'warn' | 'none';

export function nameLookup(name: string): ObjectLookup | null {
  const text = name.trim();
  return text ? { name: text } : null;
}

export function positionLookup(ra: number, dec: number): ObjectLookup | null {
  return Number.isFinite(ra) && Number.isFinite(dec) && ra >= 0 && ra < 360 && dec >= -90 && dec <= 90
    ? { ra, dec } : null;
}

// Presets carry 5 decimals: half the last digit (0.018″) tells "the preset's own position" from any edit.
const PRESET_MATCH_DEG = 5e-6;

interface NamedPosition { ra: number; dec: number; catalogName: string }

/** A TYPED or SHARED position (never a map click): a challenge preset's exact position keeps the preset's NAME
 *  lookup, so building its sequence or reopening its link does not swap the identity for the nearest Gaia source
 *  (at WISE 0855's position that is an unrelated G = 16 field star 6.9″ away). Any other position: by position. */
export function coordinateLookup(ra: number, dec: number,
  presets: readonly NamedPosition[] = SHOWCASE_TARGETS): ObjectLookup | null {
  const preset = presets.find((t) => Math.abs(t.ra - ra) <= PRESET_MATCH_DEG && Math.abs(t.dec - dec) <= PRESET_MATCH_DEG);
  return preset ? nameLookup(preset.catalogName) : positionLookup(ra, dec);
}

/** Stable identity of a lookup (effect dependency); '' when nothing is chosen. */
export function lookupKey(lookup: ObjectLookup | null): string {
  if (!lookup) return '';
  return 'name' in lookup ? `name:${lookup.name}` : `pos:${lookup.ra.toFixed(7)},${lookup.dec.toFixed(7)}`;
}

export function lookupLabel(lookup: ObjectLookup): string {
  if ('name' in lookup) return `“${lookup.name}”`;
  return `${lookup.ra.toFixed(5)}°, ${lookup.dec >= 0 ? '+' : ''}${lookup.dec.toFixed(5)}°`;
}

export function formatArcsec(value: number | null | undefined): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return 'unknown';
  return `${value < 10 ? value.toFixed(1) : value.toFixed(0)}″`;
}

/** Nothing catalogued at a clicked position: no identity, no measured fact, no magnitude, no variable, no planet,
 *  and every catalog named in that statement answered (an outage is never shown as empty sky). */
export function isEmptySky(r: ObjectContextResponse): boolean {
  return r.query.name === null && r.identity.match === 'none' && r.identity.display_name === null
    && r.photometry.length === 0 && r.variability === null && r.planets.length === 0
    && r.facts.every((f) => isUnknown(f.value))
    && !r.provenance.some((p) => p.status === 'error' && ['vsx', '2mass', 'allwise'].includes(p.service));
}

/** A Gaia DR3 query did not answer and nothing answered in its place: an ESA failure is covered when the VizieR CfA
 *  copy of Gaia DR3 (I/355/gaiadr3) answered instead; an ESA error with no VizieR answer is e.g. SIMBAD's Gaia
 *  cross-id that could not be fetched after the cone answered. */
function gaiaGap(r: ObjectContextResponse): boolean {
  const failed = (s: string) => r.provenance.some((p) => p.service === s && p.status === 'error');
  const answered = (s: string) => r.provenance.some((p) => p.service === s && (p.status === 'ok' || p.status === 'no_match'));
  return failed('gaia-vizier') || (failed('gaia-esa') && !answered('gaia-vizier'));
}

export function matchSummary(r: ObjectContextResponse): { label: string; tone: Tone; detail: string } {
  const id = r.identity;
  const radius = formatArcsec(r.query.radius_arcsec);
  const gaia = id.gaia_source_id ? `Gaia DR3 ${id.gaia_source_id}` : null;
  switch (id.match) {
    case 'name': {
      const label = 'Identified by name (SIMBAD)';
      if (gaia) return { label, tone: id.identity_uncertain ? 'warn' : 'ok',
        detail: `${gaia}${id.gaia_method === 'simbad_crossid' ? ' (SIMBAD cross-identification)' : ''}.` };
      // n_gaia_within_radius null = no Gaia DR3 cone answered (outage or API deadline): unknown, never a negative.
      if (id.n_gaia_within_radius === null || id.n_gaia_within_radius === undefined) return { label, tone: 'warn',
        detail: 'Gaia DR3 could not be reached: whether it has a Gaia DR3 counterpart is unknown (not a negative result), '
          + 'and so are its Gaia distance and parameters. Retry later.' };
      if (gaiaGap(r)) return { label, tone: 'warn',
        detail: 'No Gaia DR3 counterpart found, but a Gaia DR3 query did not answer (see catalog services): not a firm negative.' };
      return { label, tone: id.identity_uncertain ? 'warn' : 'ok',
        detail: 'No Gaia DR3 counterpart: values come from SIMBAD and the other catalogs only.' };
    }
    case 'matched':
      return { label: 'Matched to one Gaia DR3 source', tone: 'ok',
        detail: `${gaia ?? 'Gaia DR3 source'}, ${formatArcsec(id.separation_arcsec)} from the requested position at the epoch (after proper motion). `
          + 'A match by position: an object absent from Gaia DR3 (such as a cold brown dwarf) in the same SPHEREx pixel would not be found.' };
    case 'ambiguous':
      return { label: 'Ambiguous identification', tone: 'warn',
        detail: `Several Gaia DR3 sources of similar brightness within ${radius}: values that depend on the identity are not verified.` };
    case 'loose':
      return { label: 'Loose match', tone: 'warn',
        detail: `The adopted Gaia DR3 source is ${formatArcsec(id.separation_arcsec)} from the requested position: it may not be the object you meant.` };
    case 'unavailable':
      return { label: 'Identity unknown', tone: 'warn',
        detail: 'Gaia DR3 could not be reached: this is a gap, not a negative result. Retry later.' };
    default:
      return r.query.name !== null
        ? { label: 'Name not identified by SIMBAD', tone: 'warn',
          detail: `${id.resolver ?? 'The resolver'} gave a position only: no secure catalog identification.` }
        : { label: 'No catalogued source at this position', tone: 'none',
          detail: `No Gaia DR3 source within ${radius} at the epoch.` };
  }
}

export function isUnknown(value: string): boolean {
  return value.trim().toLowerCase() === 'unknown';
}

const UNITS: Record<string, string> = { R_sun: 'R☉', L_sun: 'L☉', M_sun: 'M☉' };

export interface FactRow {
  label: string; value: string; unknown: boolean; status: 'verified' | 'not verified' | 'unknown'; source: string;
}

export function factRows(facts: Fact[]): FactRow[] {
  return facts.map((f) => {
    const unknown = isUnknown(f.value);
    const unit = f.unit ? (UNITS[f.unit] ?? f.unit) : '';
    return {
      label: f.label,
      value: unknown ? 'unknown' : unit ? `${f.value} ${unit}` : f.value,
      unknown,
      status: unknown ? 'unknown' : f.verified ? 'verified' : 'not verified',
      source: f.source ?? 'no source given',
    };
  });
}

function trimNumber(value: number, digits: number): string {
  return Number(value.toPrecision(digits)).toString();
}

export function variabilityText(v: ObjectVariability): string {
  const band = v.passband ? `${v.passband} ` : '';
  const range = v.mag_max !== null && v.mag_min !== null
    ? v.min_is_amplitude ? `${band}amplitude ${v.mag_min} mag` : `${band}${v.mag_max}–${v.mag_min} mag`
    : null;
  const period = v.period_days !== null ? `period ${trimNumber(v.period_days, 5)} d` : null;
  return [v.var_type ?? 'variable (type not given)', range, period].filter(Boolean).join(' · ');
}

function serviceFailed(r: ObjectContextResponse, service: string): boolean {
  return r.provenance.some((p) => p.service === service && p.status === 'error');
}

/** Caveat for values attached to an adopted source whose identity is not secure (loose/ambiguous/unresolved). */
export function identityCaveat(r: ObjectContextResponse): string | null {
  return r.identity.identity_uncertain ? 'of the adopted source; identity uncertain (may be a neighbour)' : null;
}

export function planetsSummary(r: ObjectContextResponse): string {
  const n = r.planets.length;
  const caveat = identityCaveat(r);
  if (n) return `${n} confirmed planet${n === 1 ? '' : 's'} (NASA Exoplanet Archive)${caveat ? ` · ${caveat}` : ''}`;
  if (serviceFailed(r, 'exoplanets')) return 'Confirmed planets unknown: the NASA Exoplanet Archive did not answer';
  return caveat ? 'No confirmed planets listed for the adopted source (identity uncertain)' : 'No confirmed planets listed for this object';
}

export function planetLine(p: ObjectPlanet): string {
  const parts = [p.name];
  if (p.period_days !== null) parts.push(`P = ${trimNumber(p.period_days, 4)} d`);
  if (p.mass_earth !== null) {
    const minimum = (p.mass_kind ?? '').toLowerCase().includes('sini');
    parts.push(`${minimum ? 'M sin i' : 'M'} = ${trimNumber(p.mass_earth, 3)} M⊕${minimum ? ' (minimum)' : ''}`);
  }
  if (p.radius_earth !== null) parts.push(`R ≈ ${trimNumber(p.radius_earth, 3)} R⊕${p.radius_calculated ? ' (estimated, not measured)' : ''}`);
  const found = [p.discovery_method, p.discovery_year].filter((x) => x !== null && x !== undefined).join(', ');
  if (found) parts.push(found);
  if (p.controversial) parts.push('flagged controversial');
  return parts.join(' · ');
}

export interface PhotometryGroup {
  mission: '2MASS' | 'WISE'; label: string; designation: string; identityUncertain: boolean;
  rows: { band: string; wavelength: string; magnitude: string; flags: string }[];
}

const MISSION_LABEL = { '2MASS': '2MASS', WISE: 'AllWISE' } as const;

export function magnitudeText(m: ContextMagnitude): string {
  if (m.mag === null) return 'no measurement';
  if (m.upper_limit) return `> ${m.mag.toFixed(2)} (upper limit)`;
  return m.mag_err !== null ? `${m.mag.toFixed(2)} ± ${m.mag_err.toFixed(2)}` : m.mag.toFixed(2);
}

export function photometryGroups(mags: ContextMagnitude[]): PhotometryGroup[] {
  const groups: PhotometryGroup[] = [];
  for (const m of mags) {
    let group = groups.find((g) => g.mission === m.mission && g.designation === m.designation);
    if (!group) {
      group = { mission: m.mission, designation: m.designation, identityUncertain: false, rows: [],
        label: `${MISSION_LABEL[m.mission]} · other mission, not SPHEREx` };
      groups.push(group);
    }
    group.identityUncertain ||= m.identity_uncertain;
    const flags = [m.quality ? `quality ${m.quality}` : '', m.contamination && m.contamination !== '0' ? `contamination ${m.contamination}` : '']
      .filter(Boolean).join(', ');
    group.rows.push({ band: m.band, wavelength: `${m.wavelength_um} µm`, magnitude: `${magnitudeText(m)} (${m.system})`,
      flags: flags || '—' });
  }
  return groups;
}

const SERVICE_NAMES: Record<string, string> = {
  sesame: 'SIMBAD (Sesame, CfA)', 'gaia-esa': 'Gaia DR3 (ESA archive)', 'gaia-vizier': 'Gaia DR3 (VizieR, CfA)',
  vsx: 'AAVSO VSX', '2mass': '2MASS (VizieR, CfA)', allwise: 'AllWISE (VizieR, CfA)', exoplanets: 'NASA Exoplanet Archive',
};

export interface ServiceRow { name: string; status: string; tone: Tone; detail: string }

export function serviceRows(provenance: ContextService[]): ServiceRow[] {
  return provenance.map((p) => {
    const status = p.status === 'ok' ? 'answered' : p.status === 'no_match' ? 'answered, no match'
      : p.status === 'skipped' ? 'not queried' : 'no answer: unknown, not negative';
    const when = p.retrieved_utc ? `retrieved ${p.retrieved_utc.slice(0, 16).replace('T', ' ')} UTC` : '';
    const detail = [p.catalog, when, p.cached ? 'cached' : '', p.stale ? 'STALE cache (service failed)' : '', p.note ?? '']
      .filter(Boolean).join(' · ');
    return { name: SERVICE_NAMES[p.service] ?? p.service, status, detail,
      tone: p.status === 'error' || p.stale ? 'warn' : p.status === 'ok' ? 'ok' : 'none' };
  });
}

export function servicesSummary(provenance: ContextService[]): string {
  const failed = provenance.filter((p) => p.status === 'error').length;
  return failed ? `${provenance.length} catalog calls · ${failed} without answer` : `${provenance.length} catalog calls · all answered`;
}

/** Card error text for a failed lookup (the job/video is never affected). */
export function describeObjectError(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 404) return `${error.message} Try a SIMBAD name (e.g. “Barnard's Star”) or a position.`;
    if (error.status === 422) return `Invalid lookup: ${error.message}`;
    if (error.status === 503) return 'The catalog lookup is busy; retry in a few seconds.';
    if (error.status === 504) return 'Catalog services did not answer in time; retry shortly.';
    if (error.status === 502) return 'Catalog services could not be reached; retry later.';
    if (error.status === 0) return error.message;
    return `Catalog context failed (${error.status}): ${error.message}`;
  }
  if (error instanceof DOMException && error.name === 'TimeoutError') return 'Catalog context did not arrive in time; retry.';
  return 'Could not reach the API for catalog context.';
}
