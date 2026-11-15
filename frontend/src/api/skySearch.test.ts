import { describe, expect, it } from 'vitest';
import type { FieldSummary } from './types';
import { searchPosition, searchSequences } from './skySearch';

function sequence(id: string, name: string, ra: number, dec: number, synthetic = false) {
  const field: FieldSummary = { id, name, center: { ra, dec }, size_deg: .15, synthetic,
    description: '', tags: [], n_frames: 40, n_candidates: 0, mjd_range: null, thumbnail: null };
  return { field, href: `#/field/${id}` };
}

describe('sky search', () => {
  it('accepts decimal and sexagesimal coordinates and rejects invalid ones', () => {
    expect(searchPosition('269.45 +4.76')).toEqual({ ra: 269.45, dec: 4.76 });
    expect(searchPosition('17:00:00, −04:30:00')).toEqual({ ra: 255, dec: -4.5 });
    expect(() => searchPosition('360, 10')).toThrow('RA must be');
    expect(() => searchPosition('10, 91')).toThrow('Declination must be');
    expect(searchPosition('2MASS J0855')).toBeNull();
  });

  it('matches names, a catalog alias, and curly apostrophes against saved fields', () => {
    const epsilon = sequence('eps-indi-b', 'Epsilon Indi B', 331, -56);
    const barnard = sequence('barnards-star', "Barnard's Star", 269, 4);
    expect(searchSequences([epsilon, barnard], 'EPS ind b')).toEqual([epsilon]);
    expect(searchSequences([epsilon, barnard], 'Barnard’s')).toEqual([barnard]);
    expect(searchSequences([epsilon, barnard], 'new object')).toEqual([]);
  });

  it('uses angular distance across the RA wrap and keeps real data ahead of a nearby demo', () => {
    const real = sequence('real', 'Real', 359.99, 1);
    const demo = sequence('example', 'Example', 0, 1, true);
    const elsewhere = sequence('far', 'Far', 0, 3);
    expect(searchSequences([elsewhere, demo, real], '', { ra: 0, dec: 1 })).toEqual([real, demo]);
  });
});
