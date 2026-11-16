import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';
import { createObjectContextCache } from '../api/objectCardCache';
import type { Fact, ObjectContextResponse, ObjectPlanet, SystemModel } from '../api/types';
import { BodyPanel } from '../components/BodyPanel';
import { appearanceNotes } from './appearanceNotes';
import { paramTier, PHYS } from './astro';
import {
  classifyObjectType,
  CONTEXT_TAG,
  M_EARTH_KG,
  massProvenance,
  M_SUN_KG,
  R_EARTH_KM,
  R_SUN_KM,
  SOLAR_SYSTEM_NOTE,
  systemFromObjectContext,
  variabilityKind,
  isFlareType,
  isPlanetTransitType,
  WHITE_DWARF_REASON,
} from './contextSystem';
import { hasDatasetWindow } from './datasetGate';
import { bodyLabelText, isColourKnown, UNKNOWN_NOTE_PREFIX, UNKNOWN_SIZE_TEXT, unknownReasons } from './factOrigin';
import { CATALOG_BADGE, ObjectModelView, ObjectSystemPreview, STATIC_HINT, STATIC_MESSAGE } from './ObjectSystemPreview';
import * as kit from './viewerKit';

// The frozen WS3 object-context snapshots of the five targets (pipeline/errante/systems/inputs/objects/*.json),
// replayed as the GET /api/object response they were recorded from (the snapshots use `period_d`, the API `period_days`).
// eslint-disable-next-line @typescript-eslint/no-explicit-any
type Snapshot = Record<string, any>;
const SNAPSHOTS = import.meta.glob<Snapshot>('../../../pipeline/errante/systems/inputs/objects/*.json', { eager: true, import: 'default' });
const snapshot = (slug: string): Snapshot => {
  const s = Object.entries(SNAPSHOTS).find(([path]) => path.endsWith(`/${slug}.json`))?.[1];
  if (!s) throw new Error(`no snapshot ${slug}`);
  return s;
};

function fromSnapshot(s: Snapshot): ObjectContextResponse {
  const id = s.identity;
  const g = s.gaia;
  return {
    schema_version: '0.7.0',
    query: { ra: null, dec: null, name: s.query.name, epoch_mjd: s.query.epoch_mjd, radius_arcsec: s.query.radius_arcsec },
    position: g ? { ra: g.ra, dec: g.dec, epoch_mjd: s.query.epoch_mjd, source: 'Gaia DR3' } : null,
    identity: {
      display_name: id.display_name, main_id: id.main_id, object_type: id.object_type, object_type_label: id.object_type_label,
      spectral_type: id.spectral_type, resolver: 'SIMBAD (Sesame, CfA)', gaia_source_id: id.gaia_source_id,
      gaia_method: id.gaia_method, match: id.match, identity_uncertain: id.identity_uncertain, separation_arcsec: null,
      n_gaia_within_radius: g ? 1 : 0,
    },
    facts: s.facts,
    variability: s.variability ? {
      name: s.variability.name, var_type: s.variability.var_type, period_days: s.variability.period_d,
      mag_max: s.variability.mag_max, mag_min: s.variability.mag_min, min_is_amplitude: s.variability.min_is_amplitude,
      passband: s.variability.passband, separation_arcsec: s.variability.sep_arcsec, url: s.variability.url, source: 'AAVSO VSX',
    } : null,
    planets: (s.planets ?? []).map((p: Snapshot): ObjectPlanet => ({
      name: p.name, hostname: id.display_name, match: p.match, period_days: p.period_d, semi_major_axis_au: p.semi_major_axis_au,
      radius_earth: p.radius_earth, radius_calculated: p.radius_calculated, mass_earth: p.mass_earth, mass_kind: p.mass_kind,
      eccentricity: p.eccentricity, inclination_deg: p.inclination_deg, discovery_year: null, discovery_method: null,
      discovery_facility: null, reference: p.reference, controversial: p.controversial,
      source: 'NASA Exoplanet Archive pscomppars (TAP)',
    })),
    nearby_planet_hosts: (s.nearby_planet_hosts ?? []).map((h: Snapshot) => ({ hostname: h.hostname, separation_arcsec: h.sep_arcsec, planets: h.planets })),
    photometry: [],
    warnings: s.warnings ?? [],
    provenance: s.origin.services.map((p: Snapshot) => ({ ...p, url: null, stale: false })),
    partial: false,
    built_at: s.recorded_utc,
    note: s.origin.note,
    synthetic: false,
  };
}

const POS = { ra: 10, dec: 20 };
const build = (slug: string) => systemFromObjectContext(fromSnapshot(snapshot(slug)), POS);
const systemOf = (slug: string): SystemModel => {
  const r = build(slug);
  if (!r.system) throw new Error(`no system for ${slug}: ${r.reason}`);
  return r.system;
};

/** A literal response: a star found by position, with every catalog answering. */
function literal(over: Partial<ObjectContextResponse> = {}, identity: Partial<ObjectContextResponse['identity']> = {}): ObjectContextResponse {
  const base = fromSnapshot(snapshot('barnards-star'));
  return {
    ...base,
    query: { ...base.query, name: null, ra: POS.ra, dec: POS.dec },
    planets: [],
    variability: null,
    warnings: [],
    ...over,
    identity: { ...base.identity, display_name: 'Test star', main_id: 'TYC 1-2-3', match: 'matched', ...identity },
  };
}

const planet = (over: Partial<ObjectPlanet>): ObjectPlanet => ({
  name: 'Test b', hostname: 'Test star', match: 'gaia_dr3_id', period_days: 10, semi_major_axis_au: 0.1, radius_earth: null,
  radius_calculated: false, mass_earth: null, mass_kind: null, eccentricity: null, inclination_deg: null, discovery_year: 2020,
  discovery_method: 'Radial Velocity', discovery_facility: null, reference: 'Doe et al. 2020', controversial: false,
  source: 'NASA Exoplanet Archive pscomppars', ...over,
});

const row = (service: string, status: 'ok' | 'no_match' | 'error') =>
  ({ service, catalog: service, url: null, status, retrieved_utc: null, cached: false, stale: false, note: null });

const SYSTEMS = ['barnards-star', 'eps-indi-b', 'wise-0855', 'r-draconis'].map(systemOf);

function allText(system: SystemModel): string[] {
  return [system.name, system.description, system.representation_note, ...system.provenance.notes,
    ...system.bodies.flatMap((b) => [b.description, b.orbit?.note ?? '', ...b.facts.flatMap((f) => [f.label, f.value, f.source ?? ''])])];
}

describe('systemFromObjectContext: the five targets', () => {
  it("Barnard's Star: star with verified Teff and radius, 4 planets, mass unknown", () => {
    const s = systemOf('barnards-star');
    const [star, ...planets] = s.bodies;
    expect(star.kind).toBe('star');
    expect(star.teff_k).toBe(3100);
    expect(star.radius_km).toBeCloseTo(0.202 * R_SUN_KM, 3);
    expect(star.mass_kg).toBeNull();
    expect(star.spectral_type).toBe('M4V');
    expect(star.variability).toEqual({ kind: 'rotation', period_days: 130, amplitude_mag: 0.02, band: 'V' });
    expect(planets.map((p) => p.name)).toEqual(['Barnard d', 'Barnard b', 'Barnard c', 'Barnard e']);
    for (const p of planets) {
      expect(p.orbit?.parent).toBe(star.id);
      expect(p.orbit?.epoch_mjd).toBeNull(); // phase unknown
      expect(p.facts.find((f) => f.label === 'Minimum mass')).toBeTruthy(); // Msini
      expect(p.facts.find((f) => f.label === 'Radius (model estimate)')?.source).toMatch(/calculated from the mass, not measured/);
    }
    expect(s.motion?.distance_pc).toBeCloseTo(1.828, 3);
    expect(s.motion?.pm_ra_cosdec_mas_yr).toBeNull(); // no proper motion is invented
    expect(s.tags).toEqual([CONTEXT_TAG]);
    expect(s.provenance.synthetic).toBe(false);
    expect(unknownReasons(s).get("Barnard's star")).toEqual({ mass: 'Gaia DR3 FLAME gives no mass for this source' });
  });

  it('eps Ind B: brown dwarf blend, Teff from ESP-UCD, radius and mass unknown, nearby host not drawn', () => {
    const s = systemOf('eps-indi-b');
    expect(s.bodies).toHaveLength(1);
    const [bd] = s.bodies;
    expect(bd.kind).toBe('brown_dwarf');
    expect(bd.appearance.model).toBe('brown_dwarf');
    expect(bd.teff_k).toBe(1417);
    expect(bd.variability).toBeNull(); // VSX gives no period
    const reasons = unknownReasons(s).get('eps Ind B');
    expect(reasons?.radius).toMatch(/FLAME gives no radius/);
    expect(reasons?.mass).toMatch(/FLAME gives no mass/);
    expect(s.provenance.notes.some((n) => /composite/.test(n) && n.includes('T1V+T6V'))).toBe(true);
    expect(s.provenance.notes.some((n) => /NOT this object, not drawn: eps Ind A/.test(n))).toBe(true);
  });

  it('WISE 0855: no Gaia counterpart, every drawn value unknown with the card reason; SIMBAD distance kept', () => {
    const s = systemOf('wise-0855');
    const [bd] = s.bodies;
    expect([bd.kind, bd.teff_k, bd.radius_km, bd.mass_kg]).toEqual(['brown_dwarf', null, null, null]);
    expect(unknownReasons(s).get('WISEA J085510.74-071442.5')).toEqual({
      temperature: 'No Gaia DR3 counterpart', radius: 'No Gaia DR3 counterpart', mass: 'No Gaia DR3 counterpart',
    });
    expect(s.motion?.distance_pc).toBeCloseTo(2.278, 3);
    expect(s.center).toEqual(POS); // no Gaia position: the picked one
  });

  it('R Dra: Mira with the VSX period and V range, Teff unknown (grey)', () => {
    const s = systemOf('r-draconis');
    const [star] = s.bodies;
    expect(star.teff_k).toBeNull();
    expect(star.variability).toEqual({ kind: 'pulsation', period_days: 246.12, amplitude_mag: 6.5, band: 'V' });
    expect(unknownReasons(s).get('R Dra')?.temperature).toBe('Gaia DR3 has no temperature for this source');
  });

  it('RW Aur: ambiguous identity, no model, and the reason says why', () => {
    const r = build('rw-aurigae');
    expect(r.system).toBeNull();
    expect(r.reason).toMatch(/Ambiguous identification/);
    expect(r.reason).toContain(SOLAR_SYSTEM_NOTE);
  });

  it('draws nothing unverified and never claims a SPHEREx measurement', () => {
    for (const s of SYSTEMS) {
      for (const b of s.bodies) {
        for (const f of b.facts) {
          expect(f.verified, `${s.id}/${b.id} ${f.label}`).toBe(true);
          expect(f.value.toLowerCase()).not.toBe('unknown');
          expect(f.source?.startsWith('SPHEREx')).toBe(false);
        }
        if (b.teff_k !== null) expect(b.facts.some((f) => /temperature/i.test(f.label) && f.verified)).toBe(true);
        if (b.radius_km !== null) expect(b.facts.some((f) => /^radius/i.test(f.label) && f.verified)).toBe(true);
      }
      for (const text of allText(s)) expect(text).not.toMatch(/(?<!not )measured by SPHEREx/i);
      expect(s.representation_note).toMatch(/not measured by SPHEREx/);
      const note = s.provenance.notes.find((n) => n.startsWith(UNKNOWN_NOTE_PREFIX));
      // Every unknown drawn value of every body is in the note, and the note parses back.
      for (const b of s.bodies) {
        const expected = b.kind === 'planet' ? [b.radius_km] : [b.teff_k, b.radius_km, b.mass_kg];
        if (expected.some((v) => v === null)) expect(note && unknownReasons(s).has(b.name), `${s.id}/${b.name}`).toBe(true);
      }
    }
  });
});

describe('systemFromObjectContext: other objects', () => {
  it('a galaxy, a QSO and a cluster are not modelled, and the reason names the type', () => {
    for (const [code, label, word] of [['G', 'Galaxy', 'galaxy'], ['QSO', 'Quasar', 'quasar'], ['Cl*', 'Cluster of Stars', 'cluster'], ['PN', 'Planetary Nebula', 'nebula']]) {
      const r = systemFromObjectContext(literal({}, { object_type: code, object_type_label: label, spectral_type: null }), POS);
      expect(r.system).toBeNull();
      expect(r.reason).toContain(`'${code}'`);
      expect(r.reason).toContain(word);
      expect(r.reason).toContain(SOLAR_SYSTEM_NOTE);
    }
  });

  const EMPTY_ID = { display_name: null, main_id: null, object_type: null, object_type_label: null, spectral_type: null, match: 'none', gaia_source_id: null } as const;
  const emptySky = (provenance: ObjectContextResponse['provenance'], partial = false) => literal({
    facts: [{ label: 'Effective temperature', value: 'unknown', unit: null, source: 'No Gaia DR3 source.', verified: false }],
    photometry: [], provenance, partial,
  }, EMPTY_ID);

  it('empty sky: no 3D, asteroids are not ruled out, and SIMBAD is not claimed (it is reached only through Gaia)', () => {
    const r = systemFromObjectContext(emptySky([row('gaia-esa', 'no_match'), row('vsx', 'no_match'), row('2mass', 'no_match'), row('allwise', 'no_match'), row('exoplanets', 'no_match')]), POS);
    expect(r.system).toBeNull();
    expect(r.reason).toMatch(/^Nothing the object card could identify at this position: No Gaia DR3 source within/);
    expect(r.reason).toContain('AAVSO VSX, 2MASS, AllWISE and the NASA Exoplanet Archive answered with nothing here.');
    expect(r.reason).toMatch(/SIMBAD is reached only through a Gaia DR3 source, so it was not checked here/);
    expect(r.reason).not.toMatch(/SIMBAD[^.]*list nothing|nothing to model/);
    expect(r.reason).toMatch(/asteroids, comets/);
    expect(r.reason).toMatch(/not evidence that none is there/);
    expect(r.reason).toMatch(/This 3D lookup is by position/);
  });

  it('empty sky with the exoplanet archive down names only the services that answered, and the gap', () => {
    const r = systemFromObjectContext(emptySky([row('gaia-esa', 'no_match'), row('vsx', 'no_match'), row('2mass', 'ok'), row('allwise', 'ok'), row('exoplanets', 'error')], true), POS);
    expect(r.reason).toContain('AAVSO VSX, 2MASS and AllWISE answered with nothing here.');
    expect(r.reason).toContain('The NASA Exoplanet Archive did not answer (a gap, not a negative result).');
  });

  it('no Gaia source but some catalog values: the type is unknown, and SIMBAD is not claimed as checked', () => {
    const r = systemFromObjectContext(literal({ provenance: [row('gaia-esa', 'no_match'), row('vsx', 'ok')] }, EMPTY_ID), POS);
    expect(r.system).toBeNull();
    expect(r.reason).not.toMatch(/No SIMBAD or Gaia DR3 identification/);
    expect(r.reason).toMatch(/SIMBAD is reached only through a Gaia DR3 source/);
    expect(r.reason).toMatch(/object type is unknown, so no 3D model is drawn/);
  });

  it('ESA Gaia down but the VizieR Gaia DR3 copy answered: Gaia is not reported as a gap (Vega by position, live 2026-11-15)', () => {
    const r = systemFromObjectContext(literal({ partial: true, provenance: [row('gaia-esa', 'error'), row('gaia-vizier', 'ok'), row('vsx', 'ok')] }, EMPTY_ID), POS);
    expect(r.reason).toMatch(/^Nothing identified at this position: No Gaia DR3 source within/);
    expect(r.reason).not.toMatch(/Gaia DR3 did not answer/);
  });

  it('a loose match with no SIMBAD type gives the identity reason, not a type reason (TRAPPIST-1 by position)', () => {
    const r = systemFromObjectContext(literal({ provenance: [row('gaia-vizier', 'ok'), row('sesame', 'no_match')] },
      { match: 'loose', identity_uncertain: true, separation_arcsec: 6.5, object_type: null, object_type_label: null, spectral_type: null }), POS);
    expect(r.reason).toMatch(/^Loose match: /);
    expect(r.reason).not.toMatch(/no SIMBAD object type/);
  });

  it('a SIMBAD outage after a Gaia match is a gap, not "no SIMBAD type"', () => {
    const r = systemFromObjectContext(literal({ partial: true, provenance: [row('gaia-esa', 'ok'), row('sesame', 'error')] },
      { object_type: null, object_type_label: null, spectral_type: null }), POS);
    expect(r.system).toBeNull();
    expect(r.reason).toMatch(/^SIMBAD \(Sesame CfA\) did not answer, so the object type is unknown \(a gap, not a negative result\)/);
    expect(r.reason).not.toMatch(/identifies no SIMBAD object type/);
    // SIMBAD answered with no entry: then "no SIMBAD type" is a real catalog answer.
    const none = systemFromObjectContext(literal({ provenance: [row('gaia-esa', 'ok'), row('sesame', 'no_match')] },
      { object_type: null, object_type_label: null, spectral_type: null }), POS);
    expect(none.reason).toMatch(/identifies no SIMBAD object type: an object with no SIMBAD type/);
  });

  it('a name lookup has no position-lookup caveat', () => {
    expect(build('rw-aurigae').reason).not.toMatch(/This 3D lookup is by position/);
  });

  it('Gaia unavailable is a gap, not an empty sky', () => {
    const r = systemFromObjectContext(literal({}, { match: 'unavailable' }), POS);
    expect(r.system).toBeNull();
    expect(r.reason).toMatch(/gap, not a negative result/);
  });

  it('a partial response says unknowns may be gaps', () => {
    const r = systemFromObjectContext(literal({ partial: true }), POS);
    expect(r.system?.provenance.notes.some((n) => /may be gaps/.test(n))).toBe(true);
  });

  it('exoplanet archive down: the model says the planets are unknown, not absent', () => {
    const s = systemFromObjectContext(literal({ partial: true, provenance: [row('gaia-esa', 'ok'), row('sesame', 'ok'), row('exoplanets', 'error')] }), POS).system!;
    expect(s.bodies).toHaveLength(1);
    expect(s.provenance.notes).toContain('Confirmed planets unknown: the NASA Exoplanet Archive did not answer, so no planets are drawn (a gap, not a negative result).');
  });

  it('planet mass provenance: only Msini is a minimum; an M-R relationship mass is a model estimate', () => {
    expect(massProvenance('Msini')).toMatchObject({ label: 'Minimum mass', minimum: true });
    expect(massProvenance('Msin(i)/sin(i)')).toMatchObject({ label: 'Mass', minimum: false });
    expect(massProvenance('M-R relationship')).toMatchObject({ label: 'Mass (model estimate)', minimum: false });
    expect(massProvenance('Mass')).toEqual({ label: 'Mass', suffix: '', minimum: false });
    const s = systemFromObjectContext(literal({ planets: [
      planet({ name: 'Kepler-257 d', mass_earth: 21.7, mass_kind: 'M-R relationship', radius_earth: 5.4 }),
      planet({ name: 'HD 10180 f', mass_earth: 23.9, mass_kind: 'Msin(i)/sin(i)', period_days: 122.7, semi_major_axis_au: 0.49 }),
    ] }), POS).system!;
    const [, mr, sini] = s.bodies;
    expect(mr.facts.find((f) => /^mass/i.test(f.label))).toMatchObject({ label: 'Mass (model estimate)' });
    expect(mr.facts.find((f) => /^mass/i.test(f.label))?.source).toMatch(/mass-radius relation, not measured/);
    expect(paramTier(mr, 'mass').tier).not.toBe('measured');
    expect(sini.facts.find((f) => /^mass/i.test(f.label))?.label).toBe('Mass');
    expect(paramTier(sini, 'mass').flags).not.toContain('lower-bound');
  });

  it('planets: drawn only with period and orbit size, never when controversial; Msini is a minimum mass', () => {
    const r = systemFromObjectContext(literal({
      planets: [
        planet({ name: 'Test b', mass_earth: 300, mass_kind: 'Msini', eccentricity: 0.2 }),
        planet({ name: 'Test c', semi_major_axis_au: null }),
        planet({ name: 'Test d', controversial: true }),
        planet({ name: 'Test e', radius_earth: 1.1, mass_earth: 2, mass_kind: 'Mass' }),
      ],
    }), POS);
    const s = r.system!;
    expect(s.bodies.map((b) => b.name)).toEqual(['Test star', 'Test b', 'Test e']);
    const [, b, e] = s.bodies;
    expect(b.facts.find((f) => f.label === 'Minimum mass')?.value).toBe('300');
    expect(b.mass_kg).toBeCloseTo(300 * M_EARTH_KG, -18);
    expect(b.orbit?.eccentricity).toBe(0.2);
    expect(b.appearance.model).toBe('gas_giant');
    expect(b.radius_km).toBeNull();
    expect(e.facts.find((f) => f.label === 'Mass')?.value).toBe('2');
    expect(e.radius_km).toBeCloseTo(1.1 * R_EARTH_KM, 6);
    expect(e.orbit?.note).toMatch(/Eccentricity not published: drawn circular/);
    expect(s.provenance.notes).toContain('Planets not drawn: no published period and orbit size: Test c.');
    expect(s.provenance.notes.some((n) => /controversial.*Test d/.test(n))).toBe(true);
    expect(unknownReasons(s).get('Test b')).toEqual({ radius: 'not in the NASA Exoplanet Archive' });
  });

  it('an unverified or unparseable value stays unknown with a reason', () => {
    const facts: Fact[] = [
      { label: 'Effective temperature', value: '5800', unit: 'K', source: 'Gaia DR3', verified: false },
      { label: 'Radius', value: 'n/a', unit: 'R_sun', source: 'Gaia DR3', verified: true },
      { label: 'Mass', value: '1.0', unit: 'M_sun', source: 'Gaia DR3 FLAME', verified: true },
    ];
    const s = systemFromObjectContext(literal({ facts }), POS).system!;
    const [star] = s.bodies;
    expect([star.teff_k, star.radius_km]).toEqual([null, null]);
    expect(star.mass_kg).toBeCloseTo(M_SUN_KG, -25);
    expect(star.facts.map((f) => f.label)).toEqual(['Radius', 'Mass']); // the unverified Teff is not attached
    const reasons = unknownReasons(s).get('Test star');
    expect(reasons?.temperature).toMatch(/not verified/);
    expect(reasons?.radius).toMatch(/not a positive number/);
  });

  // V14 review (WS3, #107) minors 1-3. The fact sources below copy the wording of science/context.py.
  const GAIA_AP = 'Gaia DR3 1, gaiadr3.astrophysical_parameters (ESA Gaia archive, retrieved 2026-11-15)';
  const GSP_PHOT = `${GAIA_AP} | GSP-Phot (BP/RP spectra + parallax), 16th-84th percentiles`;
  const FLAME = `${GAIA_AP} | Gaia DR3 FLAME (from GSP-Phot parameters, G photometry and the Gaia distance), 16th-84th pct`;
  const M_DWARF_CAVEAT = 'Caveat: GSP-Phot temperatures of M dwarfs and cooler objects are unreliable (see the Gaia DR3 astrophysical-parameters documentation): indicative only.';

  it('a GSP-Phot Teff the card marks indicative only (M dwarf) is drawn as a MODEL value, with a note (Proxima-like)', () => {
    const teff: Fact = { label: 'Effective temperature', value: '2829', unit: 'K', source: `${GSP_PHOT} | ${M_DWARF_CAVEAT}`, verified: true };
    const s = systemFromObjectContext(literal({ facts: [teff] }, { display_name: 'Proxima-like test star', object_type: 'BY*', spectral_type: 'M5.5Ve' }), POS).system!;
    const [star] = s.bodies;
    expect(star.teff_k).toBe(2829); // still drawn (orange), but not as a measurement
    expect(paramTier(star, 'teff').tier).toBe('model');
    expect(s.provenance.notes).toContain('Temperature is drawn from Gaia DR3 values that the object card marks indicative only (GSP-Phot is unreliable for M dwarfs and cooler objects, and FLAME inherits its temperature): model values, not measurements.');
    // The caveat is what weakens it: the same fact without it stays MEASURED, and gets no note.
    const plain = systemFromObjectContext(literal({ facts: [{ ...teff, source: GSP_PHOT }] }), POS).system!;
    expect(paramTier(plain.bodies[0], 'teff').tier).toBe('measured');
    expect(plain.provenance.notes.some((n) => /indicative only/.test(n))).toBe(false);
  });

  it('a white dwarf gets no Teff, radius or mass from Gaia GSP-Phot / FLAME: unknown (grey, fixed size), with the reason', () => {
    const facts: Fact[] = [
      { label: 'Effective temperature', value: '9000', unit: 'K', source: GSP_PHOT, verified: true },
      { label: 'Radius', value: '0.5', unit: 'R_sun', source: FLAME, verified: true },
      { label: 'Mass', value: '0.6', unit: 'M_sun', source: FLAME, verified: true },
    ];
    const cases: Array<[Partial<ObjectContextResponse['identity']>, string]> = [
      [{ object_type: 'WD*', object_type_label: 'White Dwarf', spectral_type: null }, "SIMBAD type 'WD*' (White Dwarf) marks a white dwarf"],
      [{ object_type: 'WD?', object_type_label: 'White Dwarf Candidate', spectral_type: null }, "SIMBAD type 'WD?' (White Dwarf Candidate) marks a white dwarf candidate"],
      [{ object_type: '*', object_type_label: 'Star', spectral_type: 'DA2' }, "SIMBAD's spectral type DA2 marks a white dwarf"],
    ];
    for (const [identity, marks] of cases) {
      const s = systemFromObjectContext(literal({ facts }, identity), POS).system!;
      const [star] = s.bodies;
      expect([star.teff_k, star.radius_km, star.mass_kg], marks).toEqual([null, null, null]);
      expect(isColourKnown(star)).toBe(false); // neutral grey
      expect(bodyLabelText(star)).toContain(UNKNOWN_SIZE_TEXT); // fixed marker size
      expect(unknownReasons(s).get('Test star')).toEqual({ temperature: WHITE_DWARF_REASON, radius: WHITE_DWARF_REASON, mass: WHITE_DWARF_REASON });
      expect(s.provenance.notes).toContain(`${marks}: Gaia DR3 GSP-Phot, FLAME and ESP-UCD do not apply to white dwarfs, so the card's Gaia DR3 temperature, radius and mass are not drawn (shown as unknown).`);
      const html = renderToStaticMarkup(createElement(BodyPanel, { system: s, body: star, fieldExists: false }));
      expect(html).toContain(`Why: ${WHITE_DWARF_REASON}.`);
    }
    // The same Gaia values of a main-sequence star are drawn.
    const star = systemFromObjectContext(literal({ facts }, { object_type: '*', spectral_type: 'A0V' }), POS).system!.bodies[0];
    expect([star.teff_k, star.radius_km]).toEqual([9000, 0.5 * R_SUN_KM]);
  });

  it('a VSX type with flares (BY+UV) is not animated: the range may be a flare amplitude', () => {
    const s = systemFromObjectContext(literal({ variability: {
      name: 'Test star', var_type: 'BY+UV', period_days: 82.8, mag_max: 11.0, mag_min: 0.2, min_is_amplitude: true,
      passband: 'V', separation_arcsec: 0.1, url: null, source: 'AAVSO VSX',
    } }), POS).system!;
    expect(s.bodies[0].variability).toBeNull();
    expect(s.provenance.notes).toContain('AAVSO VSX period 82.8 d (type BY+UV) is not animated: the type includes flares, so the VSX magnitude range may be a flare amplitude, not the periodic variation.');
  });

  describe('an exoplanet entry (SIMBAD Pl / Pl?)', () => {
    const byName = (over: Partial<ObjectContextResponse> = {}, identity: Partial<ObjectContextResponse['identity']> = {}) => {
      const base = literal(over, { display_name: 'Test b', main_id: 'Test b', object_type: 'Pl', object_type_label: 'Extra-solar Planet',
        spectral_type: 'M4V', gaia_method: 'nearest_after_propagation', match: 'name', ...identity });
      return { ...base, query: { ...base.query, name: 'Test b', ra: null, dec: null } };
    };

    it("by name, draws the host the archive ties to the adopted Gaia source, without the planet entry's SIMBAD values", () => {
      const s = systemFromObjectContext(byName({ planets: [planet({}), planet({ name: 'Other b', hostname: 'Other star' })] }), POS).system!;
      expect(s.bodies.map((b) => b.name)).toEqual(['Test star', 'Test b']);
      const [host] = s.bodies;
      expect(host.kind).toBe('star');
      expect(host.description).toMatch(/^Host star of Test b/);
      expect(host.description).not.toMatch(/Extra-solar Planet from the object card/);
      expect(host.spectral_type).toBeNull();
      expect(host.facts.some((f) => /^simbad/i.test(f.source ?? ''))).toBe(false);
      expect(s.provenance.notes.some((n) => /SIMBAD lists Test b as an exoplanet: the model draws its host star Test star/.test(n))).toBe(true);
    });

    it("keeps a 'Pl?' candidate's caveat", () => {
      const s = systemFromObjectContext(byName({ planets: [planet({})] }, { object_type: 'Pl?', object_type_label: 'Extra-solar Planet Candidate' }), POS).system!;
      expect(s.provenance.notes.some((n) => /as a candidate exoplanet \(a candidate: it may not be a planet\)/.test(n))).toBe(true);
    });

    it('refuses by position (SIMBAD typed the adopted Gaia source itself a planet) and when the archive does not tie the host', () => {
      const pos = systemFromObjectContext(literal({ planets: [planet({})] }, { object_type: 'Pl', object_type_label: 'Extra-solar Planet' }), POS);
      expect(pos.system).toBeNull();
      expect(pos.reason).toMatch(/SIMBAD lists the adopted Gaia DR3 source \d+ itself as an exoplanet/);
      const untied = systemFromObjectContext(byName({ planets: [planet({ match: 'hostname' })] }), POS);
      expect(untied.system).toBeNull();
      expect(untied.reason).toMatch(/does not tie a host star/);
      const noFacts = systemFromObjectContext(byName({ planets: [planet({})], facts: [] }), POS);
      expect(noFacts.system).toBeNull();
      expect(noFacts.reason).toMatch(/exoplanet/);
    });
  });
});

describe('classification tables', () => {
  it('reads SIMBAD types conservatively', () => {
    const kind = (t: string | null, sp: string | null = null) => classifyObjectType(t, sp).kind;
    expect(['*', '**', 'V*', 'PM*', 'HPM', 'BY*', 'Mi*', 'TT*', 'Y*O', 'WD*', 'EB*'].map((t) => kind(t))).toEqual(Array(11).fill('star'));
    expect([kind('BD*'), kind('BD?'), kind('PM*', 'L5'), kind(null, 'T8')]).toEqual(['brown_dwarf', 'brown_dwarf', 'brown_dwarf', 'brown_dwarf']);
    expect(['G', 'QSO', 'AGN', 'Cl*', 'GlC', 'HII', 'PN', 'MoC', 'Rad', 'X', 'SN*', 'CV*', '?', 'Unknown'].map((t) => kind(t)))
      .toEqual(Array(14).fill('not-modelled'));
    expect(kind(null)).toBe('not-modelled');
    expect(kind('Pl')).toBe('planet');
  });

  it('variability kinds come from the VSX type, never invented', () => {
    expect(['M', 'SRB', 'BY', 'CTTS/ROT+CTTS', 'EA', 'VBD', 'CTTS', null].map(variabilityKind))
      .toEqual(['pulsation', 'pulsation', 'rotation', 'rotation', 'eclipse', null, null, null]);
    // A planetary transit (EP) is the planet's period, and a combined type of two kinds has one period for two
    // phenomena (e.g. HD 189733 'EP+BY', 2.219 d = the transit): neither is animated.
    expect(['EP', 'EP+BY', 'EA+BY', 'BY+ROT'].map(variabilityKind)).toEqual([null, null, null, 'rotation']);
    expect(isPlanetTransitType('EP+BY')).toBe(true);
    expect(isPlanetTransitType('BY')).toBe(false);
    // A type with flares (UV Ceti 'UV', 'UVN', 'FLARE') is not animated: the VSX range may be a flare amplitude
    // (Proxima Cen 'BY+UV' would otherwise spin as a 0.2 mag rotation).
    expect(['BY+UV', 'UV', 'UVN', 'UV:', 'FLARE', 'ROT+FLARE'].map(variabilityKind)).toEqual(Array(6).fill(null));
    expect(['BY+UV', 'UVN', 'FLARE'].map(isFlareType)).toEqual([true, true, true]);
    expect(['BY', 'RS', 'UVCET'].map(isFlareType)).toEqual([false, false, false]);
  });

  it('uses the same constants as astro.PHYS', () => {
    expect(R_SUN_KM).toBe(PHYS.RSun / 1e3);
    expect(R_EARTH_KM).toBe(PHYS.REarth / 1e3);
    expect(M_SUN_KG).toBe(PHYS.GMSun / PHYS.G);
  });
});

describe('the 3D code accepts a system id it has no tables for', () => {
  it('viewer helpers, drawing notes and the body panel work; Dataset time is unavailable', () => {
    for (const s of SYSTEMS) {
      expect(hasDatasetWindow(s.id, null)).toBe(false);
      expect(kit.datasetWindow(s, null)).toBeNull();
      expect(() => {
        kit.colorLegend(kit.DEFAULT_COLOR_MODE, s);
        kit.surfaceLegend(s, kit.DEFAULT_COLOR_MODE);
        kit.spinLegend(s, kit.suggestedSpeed(s));
        kit.phaseStatusLine(s);
        kit.freeRunningArbitraryPhase(s);
        kit.variabilityTracks(s);
        kit.nonFittedOrbits(s.bodies);
        kit.datasetLegend(s);
      }).not.toThrow();
      expect(Number.isFinite(kit.suggestedSpeed(s))).toBe(true);
      for (const b of s.bodies) {
        expect(appearanceNotes(b, s).length).toBeGreaterThan(0);
        const html = renderToStaticMarkup(createElement(BodyPanel, { system: s, body: b, fieldExists: false }));
        expect(html).toContain('catalog, not measured by SPHEREx');
      }
    }
  });

  it('the body panel shows the per-body reason of an unknown value', () => {
    const s = systemOf('wise-0855');
    const html = renderToStaticMarkup(createElement(BodyPanel, { system: s, body: s.bodies[0], fieldExists: false }));
    expect(html).toContain('Why: No Gaia DR3 counterpart.');
  });
});

describe('ObjectSystemPreview', () => {
  it('static mode keeps the original message and says a model needs the live API', () => {
    const html = renderToStaticMarkup(createElement(ObjectSystemPreview, { position: POS }));
    expect(html).toContain(STATIC_MESSAGE);
    expect(STATIC_MESSAGE).toBe('No catalog model is available for this position in the current dataset.');
    expect(html).toContain(STATIC_HINT);
    expect(html).not.toContain(CATALOG_BADGE);
    const named = renderToStaticMarkup(createElement(ObjectSystemPreview, { position: POS, lookup: { name: "Barnard's Star" } }));
    expect(named).toContain(STATIC_MESSAGE);
  });

  // The live 3D tab waits through FE-5's session cache (getObjectContextCached) with its own 45 s timeout signal.
  // The effect cannot run in these node SSR tests, so this checks the cache behaviour it relies on.
  it("a 3D timeout abort stops only the 3D wait: the card's shared request lives on and its answer is cached", async () => {
    const pending: { resolve: (r: ObjectContextResponse) => void }[] = [];
    const cache = createObjectContextCache((_lookup, signal) => new Promise((resolve, reject) => {
      pending.push({ resolve });
      signal.addEventListener('abort', () => reject(signal.reason), { once: true });
    }), { timeoutMs: 0 });
    const lookup = { name: "Barnard's Star" };
    const card = cache.get(lookup, new AbortController().signal);
    const preview = new AbortController();
    const wait3d = cache.get(lookup, preview.signal);
    preview.abort(new DOMException('Catalog context timed out', 'TimeoutError'));
    await expect(wait3d).rejects.toMatchObject({ name: 'TimeoutError' });
    await new Promise((r) => setTimeout(r, 0)); // the cache aborts an abandoned request one tick later
    expect(cache.inFlight()).toBe(1); // the card still waits on the same single request
    const answer = fromSnapshot(snapshot('barnards-star'));
    pending[0].resolve(answer);
    await expect(card).resolves.toBe(answer);
    expect(pending).toHaveLength(1);
    expect(cache.peek(lookup)).toBe(answer); // the next 3D lookup reuses it: no second GET /api/object
    expect(await cache.get(lookup, new AbortController().signal)).toBe(answer);
    expect(pending).toHaveLength(1);
  });
});

describe('ObjectSystemPreview compact (FE-12)', () => {
  const view = (slug: string, compact: boolean) => {
    const ctx = fromSnapshot(snapshot(slug));
    const result = systemFromObjectContext(ctx, POS);
    return renderToStaticMarkup(createElement(ObjectModelView, { ctx, result, selectedId: null, onSelect: () => {}, compact }));
  };

  it('keeps the catalog badge, the 3D MODEL chip and the representation note with a compact stage', () => {
    const html = view('barnards-star', true);
    expect(html).toContain(CATALOG_BADGE);
    expect(html).toContain('3D MODEL · NOT AN IMAGE');
    expect(html).toContain(systemOf('barnards-star').representation_note);
    expect(html).toContain('s3d-viewer--compact');
    expect(html).toMatch(/class="s3d-stage s3d-stage--compact"/);
    // The badge, the note and the stage come before the body panel and the notes, in that order.
    const at = (t: string) => html.indexOf(t);
    expect(at(CATALOG_BADGE)).toBeLessThan(at('s3d-stage--compact'));
    expect(at(systemOf('barnards-star').representation_note)).toBeLessThan(at('s3d-stage--compact'));
    expect(at('s3d-stage--compact')).toBeLessThan(at('s3d-body--compact'));
  });

  it('reduces the body panel to its key data and folds the full panel and the notes', () => {
    const html = view('barnards-star', true);
    expect(html).toContain('s3d-body--compact');
    // The star's values under the labels of the card facts that give them, each with its origin chip.
    expect(html).toMatch(/<dt>Effective temperature<\/dt><dd>~\d+ K <span class="s3d-origin s3d-origin--catalog"/);
    expect(html).toMatch(/<dt>Radius<\/dt><dd>~[\d,]+ km \([\d.]+ R☉\) <span class="s3d-origin s3d-origin--catalog"/);
    expect(html).toContain('catalog, not measured by SPHEREx'); // the origin chip
    expect(html).toContain('<summary>All facts, sources and drawing notes</summary>');
    expect(html).toMatch(/<summary>Model notes \(\d+\)<\/summary>/);
    // The notes list sits inside its disclosure.
    expect(html.indexOf('Model notes (')).toBeLessThan(html.indexOf('aria-label="Model notes"'));
  });

  it('never shows a calculated planet radius as a plain "Radius" while its qualifier is folded', () => {
    const ctx = fromSnapshot(snapshot('barnards-star'));
    const result = systemFromObjectContext(ctx, POS);
    const planets = result.system!.bodies.filter((b) => b.kind === 'planet');
    expect(planets.length).toBeGreaterThan(0);
    for (const p of planets) {
      expect(p.facts.find((f) => /^Radius/.test(f.label))?.label, p.name).toBe('Radius (model estimate)');
      const html = renderToStaticMarkup(createElement(ObjectModelView, { ctx, result, selectedId: p.id, onSelect: () => {}, compact: true }));
      const panel = html.slice(html.indexOf('s3d-body--compact'));
      const visible = panel.slice(0, panel.indexOf('<details'));
      expect(visible, p.name).toMatch(/<dt>Radius \(model estimate\)<\/dt><dd>~[\d,]+ km <span class="s3d-origin s3d-origin--catalog"/);
      expect(visible, p.name).not.toContain('<dt>Radius</dt>');
    }
  });

  it('the full view keeps the badges, the full body panel and the open notes list', () => {
    const html = view('barnards-star', false);
    expect(html).toContain(CATALOG_BADGE);
    expect(html).toContain('3D MODEL · NOT AN IMAGE');
    expect(html).not.toContain('s3d-stage--compact');
    expect(html).not.toContain('s3d-body--compact');
    expect(html).toContain('How this body is drawn');
    expect(html).not.toContain('All facts, sources and drawing notes');
    expect(html).not.toContain('View options');
    expect(html).toContain('aria-label="Model notes"');
    expect(html).not.toContain('Model notes (');
  });
});
