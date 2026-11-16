import { describe, expect, it } from 'vitest';
import type { Body, Fact, SystemModel } from '../api/types';
import factOriginSource from './factOrigin.ts?raw';
import {
  bodyLabelText,
  FACT_ORIGIN_LABEL,
  FACT_ORIGIN_MEANING,
  factOrigin,
  isColourKnown,
  isSizeKnown,
  keyFact,
  UNKNOWN_COLOUR_TEXT,
  UNKNOWN_NOTE_PREFIX,
  UNKNOWN_SIZE_TEXT,
  unknownReason,
  unknownReasons,
  type FactOrigin,
} from './factOrigin';

// Every demo system shipped with the site (the same JSON the pipeline writes).
const SYSTEMS = Object.values(
  import.meta.glob<SystemModel>('../../../data/demo/systems/*.json', { eager: true, import: 'default' }),
);
const REAL = SYSTEMS.filter((s) => !s.provenance.synthetic);
const DEMO = SYSTEMS.filter((s) => s.provenance.synthetic);
const sys = (id: string) => SYSTEMS.find((s) => s.id === id)!;

const fact = (label: string, source: string | null): Fact => ({ label, value: '1', unit: null, source, verified: true });

describe('fact origin (V13 convention)', () => {
  it('SPHEREx when the source starts with "SPHEREx", derived when the label says "(derived", else catalog', () => {
    const cases: [Fact, FactOrigin][] = [
      [fact('Cycle seen by SPHEREx', 'SPHEREx DR1 + QR, offline FITS analysis (docs/validation/r-draconis.md)'), 'spherex'],
      [fact('Motion seen by SPHEREx', '  SPHEREx wing photometry'), 'spherex'],
      [fact('Radius (derived from the catalog luminosity)', 'derived by WS7: Herczeg & Hillenbrand 2014'), 'derived'],
      [fact('Distance (Derived)', 'Gaia DR3'), 'derived'],
      [fact('Temperature', 'NASA Exoplanet Archive, pscomppars'), 'catalog'],
      // No source is never called catalog.
      [fact('Temperature', null), 'unsourced'],
      [fact('Temperature', '   '), 'unsourced'],
      // A source that only mentions SPHEREx later is a catalog value: the prefix is the rule.
      [fact('Distance', 'Gaia DR3; see also SPHEREx'), 'catalog'],
      // Case matters: "spherex" is not the mission name as the pipeline writes it.
      [fact('Distance', 'spherex-like'), 'catalog'],
      // The label alone does not make a value SPHEREx-measured.
      [fact('Seen by SPHEREx', 'Gaia DR3'), 'catalog'],
    ];
    for (const [f, origin] of cases) expect(factOrigin(f), `${f.label} / ${f.source}`).toBe(origin);
    expect(FACT_ORIGIN_LABEL).toEqual({
      spherex: 'SPHEREx-measured (offline)',
      derived: 'derived',
      catalog: 'catalog, not measured by SPHEREx',
      unsourced: 'no source given',
      synthetic: 'synthetic demo',
    });
    for (const o of Object.keys(FACT_ORIGIN_LABEL) as FactOrigin[]) expect(FACT_ORIGIN_MEANING[o], o).toBeTruthy();
  });

  it('every fact of the shipped systems gets an origin; the derived RW Aur A radius is labelled derived', () => {
    let n = 0;
    for (const s of REAL) {
      for (const b of s.bodies) {
        for (const f of b.facts) {
          const o = factOrigin(f);
          expect(Object.keys(FACT_ORIGIN_LABEL), `${b.id} ${f.label}`).toContain(o);
          if (o === 'spherex') expect(f.source, `${b.id} ${f.label}`).toMatch(/^\s*SPHEREx/);
          n++;
        }
      }
    }
    expect(n).toBeGreaterThan(30);
    const rwA = REAL.flatMap((s) => s.bodies).find((b) => b.id === 'rw-aur-a')!;
    const radius = rwA.facts.filter((f) => /^radius\b/i.test(f.label));
    for (const f of radius) expect(factOrigin(f), f.label).toBe('derived');
  });

  it('no fact of a shipped real system is unsourced', () => {
    for (const s of REAL) for (const b of s.bodies) for (const f of b.facts) expect(factOrigin(f), `${b.id} ${f.label}`).not.toBe('unsourced');
  });

  it('every fact of the synthetic demo is "synthetic demo", never catalog, whatever its source says', () => {
    expect(DEMO.length).toBeGreaterThan(0);
    let n = 0;
    for (const s of DEMO) {
      for (const b of s.bodies) {
        for (const f of b.facts) {
          expect(factOrigin(f, s.provenance.synthetic), `${b.id} ${f.label}`).toBe('synthetic');
          n++;
        }
      }
    }
    expect(n).toBeGreaterThan(0);
    // The flag wins over a SPHEREx-looking source too.
    expect(factOrigin(fact('Seen', 'SPHEREx DR1'), true)).toBe('synthetic');
  });
});

describe('per-body reasons of the unknown values (the pipeline note)', () => {
  it('reads R Dra temperature, radius and mass reasons, with their nested parentheses', () => {
    const r = sys('r-draconis');
    const body = r.bodies.find((b) => b.id === 'r-draconis')!;
    const t = unknownReason(r, body, 'temperature')!;
    expect(t).toMatch(/^it changes with the pulsation: the literature gives ~2000–3300 K \(van Belle et al\. 2002; McDonald et al\. 2012\)/);
    expect(t).toMatch(/WS3 V18$/);
    expect(unknownReason(r, body, 'radius')).toMatch(/^published sizes depend on the assumed distance and the pulsation phase/);
    expect(unknownReason(r, body, 'mass')).toMatch(/^no dynamical mass is published for R Dra/);
  });

  it('reads one entry per body when several bodies share the note (eps Ind Ba and Bb)', () => {
    const eps = sys('epsilon-indi');
    const m = unknownReasons(eps);
    expect(m.get('Epsilon Indi Ba')?.radius).toMatch(/^no published radius for Ba;/);
    expect(m.get('Epsilon Indi Bb')?.radius).toMatch(/^no published radius for Bb;/);
    expect(m.get('Epsilon Indi Ba')?.temperature).toBeUndefined();
  });

  it('every unknown drawn colour or size of a shipped real system has a body-specific reason', () => {
    for (const s of REAL) {
      for (const b of s.bodies) {
        if (!isSizeKnown(b)) expect(unknownReason(s, b, 'radius'), `${s.id} ${b.id}`).toBeTruthy();
        if (!isColourKnown(b)) expect(unknownReason(s, b, 'temperature'), `${s.id} ${b.id}`).toBeTruthy();
      }
    }
  });

  it('returns nothing without the note, and tolerates a malformed entry', () => {
    expect(unknownReasons({ provenance: { notes: [] } }).size).toBe(0);
    const odd = unknownReasons({ provenance: { notes: [`${UNKNOWN_NOTE_PREFIX}X: colour (?), radius (a (b) c).`] } });
    expect(odd.get('X')).toEqual({ radius: 'a (b) c' });
  });
});

describe('unknown colour and size (docs/VISION.md: what is not measured is not drawn as if it were)', () => {
  const body = (b: Partial<Body>): Pick<Body, 'kind' | 'teff_k' | 'radius_km' | 'name'> => ({
    kind: 'star',
    teff_k: null,
    radius_km: null,
    name: 'X',
    ...b,
  });

  it('a star or brown dwarf without Teff has an unknown colour; other kinds never take a colour from Teff', () => {
    expect(isColourKnown(body({ kind: 'star', teff_k: 3195 }))).toBe(true);
    expect(isColourKnown(body({ kind: 'star', teff_k: null }))).toBe(false);
    expect(isColourKnown(body({ kind: 'brown_dwarf', teff_k: 0 }))).toBe(false);
    expect(isColourKnown(body({ kind: 'planet', teff_k: null }))).toBe(true);
    expect(isColourKnown(body({ kind: 'disk', teff_k: null }))).toBe(true);
    expect(UNKNOWN_COLOUR_TEXT).toBe('colour unknown (no single temperature adopted)');
  });

  it('a body without a positive radius has an unknown size, and its label says so', () => {
    expect(isSizeKnown(body({ radius_km: 128704 }))).toBe(true);
    expect(isSizeKnown(body({ radius_km: null }))).toBe(false);
    expect(isSizeKnown(body({ radius_km: 0 }))).toBe(false);
    expect(UNKNOWN_SIZE_TEXT).toBe('size unknown · not to scale');
    expect(bodyLabelText(body({ name: 'R Draconis', radius_km: null }))).toBe('R Draconis · size unknown · not to scale');
    expect(bodyLabelText(body({ name: "Barnard's Star", radius_km: 128704 }))).toBe("Barnard's Star");
  });

  it('works generically on the shipped JSON: whatever is null is unknown, whatever is set is known', () => {
    for (const s of REAL) {
      for (const b of s.bodies) {
        expect(isSizeKnown(b), b.id).toBe(b.radius_km !== null && b.radius_km > 0);
        if (b.kind === 'star' || b.kind === 'brown_dwarf') expect(isColourKnown(b), b.id).toBe(b.teff_k !== null && b.teff_k > 0);
      }
    }
  });

  it('is astro-free and three-free, so BodyPanel can import it from the main chunk', () => {
    const imports = [...factOriginSource.matchAll(/^\s*import\b[^;]*?\bfrom\s+['"]([^'"]+)['"]/gm)].map((m) => m[0]);
    for (const i of imports) expect(i).toMatch(/^import type .* from '\.\.\/api\/types'$/);
  });
});

describe('the fact behind a drawn value (compact body panel, FE-12)', () => {
  const f = (label: string, value: string, unit: string | null): Fact => ({ label, value, unit, source: 'x', verified: true });

  it('is null without a fact naming the quantity, and the only candidate otherwise', () => {
    expect(keyFact([f('Orbit size', '1', 'AU')], 'radius', 6371)).toBeNull();
    const est = f('Radius (model estimate)', '~0.69', 'Earth radii');
    expect(keyFact([f('Orbit size', '0.0188', 'AU'), est], 'radius', 4421)).toBe(est);
    const t = f('Temperature (model-dependent)', '~1300', 'K');
    expect(keyFact([t], 'temperature', 1300)).toBe(t);
    expect(keyFact([f('Teff', '3000', 'K')], 'temperature', 3000)?.label).toBe('Teff');
  });

  it('with several candidates, picks the one whose value is nearest the drawn value', () => {
    const catalog = f('Radius', '0.185 ± 0.006', 'solar radii');
    const gaia = f('Radius', '0.202 (0.198-0.206)', 'R_sun');
    expect(keyFact([gaia, catalog], 'radius', 0.185 * 695_700)).toBe(catalog);
    expect(keyFact([catalog, gaia], 'radius', 0.202 * 695_700)).toBe(gaia);
    const dust = f('Dust disk radius', '~19', 'AU');
    const gas = f('Gas (CO) disk radius', '~58', 'AU');
    expect(keyFact([gas, dust], 'radius', 19 * 149_597_870.7)).toBe(dust);
    // An unreadable unit ranks last; when none can be read, the first candidate.
    const odd = f('Radius', '5', 'furlongs');
    expect(keyFact([odd, catalog], 'radius', 0.185 * 695_700)).toBe(catalog);
    expect(keyFact([odd, f('Radius', 'n/a', 'km')], 'radius', 1000)).toBe(odd);
  });

  it('finds the fact of every drawn Teff and radius of the real systems', () => {
    for (const s of REAL) {
      for (const b of s.bodies) {
        if (b.teff_k) expect(keyFact(b.facts, 'temperature', b.teff_k), `${b.id} teff`).not.toBeNull();
        if (b.radius_km && b.kind !== 'disk') expect(keyFact(b.facts, 'radius', b.radius_km), `${b.id} radius`).not.toBeNull();
      }
    }
  });
});
