import { parseCoordinate } from './jobs';
import { SHOWCASE_TARGETS } from './showcase';
import type { FieldSummary, SkyCoord } from './types';
import { separationArcsec } from '../three/skyTrack';

export interface SearchSequence {
  field: FieldSummary;
  href: string;
}

/** A saved field can cover many stars. Match its target within about half a SPHEREx pixel. */
export function localTargetSequences(entries: SearchSequence[], position: SkyCoord): SearchSequence[] {
  const point = { raDeg: position.ra, decDeg: position.dec };
  return entries.filter(({ field, href }) => !field.synthetic && href.startsWith('#/') &&
    separationArcsec(point, { raDeg: field.center.ra, decDeg: field.center.dec }) <= 3);
}

export function searchKey(text: string): string {
  return text.toLowerCase().normalize('NFKD').replace(/[\u0300-\u036f'’]/g, '')
    .replace(/[^a-z0-9]+/g, ' ').trim();
}

/** A name returns null; a coordinate-shaped input is validated before any catalog call. */
export function searchPosition(query: string): SkyCoord | null {
  const text = query.trim();
  const parts = text.includes(',') ? text.split(',') : text.split(/\s+/);
  if (!text.includes(',') && !(parts.length >= 2 && parts.every((part) => /^[+−-]?[\d.:]+$/.test(part)))) return null;
  if (parts.length !== 2) throw new Error('Enter RA and Dec separated by a comma.');
  return { ra: parseCoordinate(parts[0], true), dec: parseCoordinate(parts[1], false) };
}

export function searchSequences(entries: SearchSequence[], query: string, point?: SkyCoord): SearchSequence[] {
  if (point) {
    const rad = Math.PI / 180;
    return entries.flatMap((entry) => {
      const { center, size_deg } = entry.field;
      const a = Math.sin((center.dec - point.dec) * rad / 2) ** 2
        + Math.cos(center.dec * rad) * Math.cos(point.dec * rad) * Math.sin((center.ra - point.ra) * rad / 2) ** 2;
      const distance = 2 * Math.asin(Math.sqrt(Math.min(1, a))) / rad;
      // Use the circle inside the square field as a conservative match.
      return distance <= size_deg / 2 ? [{ entry, distance }] : [];
    }).sort((a, b) => Number(a.entry.field.synthetic) - Number(b.entry.field.synthetic) || a.distance - b.distance)
      .map(({ entry }) => entry);
  }
  const key = searchKey(query);
  if (!key) return [];
  return entries.flatMap((entry) => {
    const { id, name } = entry.field;
    const preset = SHOWCASE_TARGETS.find((target) => searchKey(target.name) === searchKey(name));
    const names = [name, id, preset?.catalogName ?? ''].map(searchKey);
    const rank = names.includes(key) ? 0 : names.some((n) => n.includes(key)) ? 1 : -1;
    return rank < 0 ? [] : [{ entry, rank }];
  }).sort((a, b) => a.rank - b.rank || Number(a.entry.field.synthetic) - Number(b.entry.field.synthetic))
    .map(({ entry }) => entry);
}
