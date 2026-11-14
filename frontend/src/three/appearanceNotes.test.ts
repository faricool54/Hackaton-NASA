import { describe, expect, it } from 'vitest';
import type { Body, SystemModel } from '../api/types';
import notesSource from './appearanceNotes.ts?raw';
import { surfacePattern } from './appearance';
import {
  FLAG_TEXT,
  GRANULATION_SENSITIVITY,
  NOTE_TIER_LABEL,
  NOTE_TIER_MEANING,
  NOTE_TIERS,
  NOTES_HEADER,
  ROTATION_NOT_DRAWN_NOTES,
  SPHEREX_SCALE_NOTE,
  appearanceNotes,
  pixelText,
  separationVerdict,
  type AppearanceNote,
} from './appearanceNotes';
import { PHYS, spherexPrediction } from './astro';
import { bodyLook } from './colorModes';
import { drawsPulsation, spinModel } from './sceneLayout';

// Every demo system shipped with the site (the same JSON the pipeline writes).
const SYSTEMS = Object.values(
  import.meta.glob<SystemModel>('../../../data/demo/systems/*.json', { eager: true, import: 'default' }),
);
const ALL = SYSTEMS.flatMap((system) => system.bodies.map((body) => ({ system, body })));

function system(id: string): SystemModel {
  const s = SYSTEMS.find((x) => x.id === id);
  if (!s) throw new Error(`demo system ${id} missing`);
  return s;
}

function bodyIn(systemId: string, bodyId: string): Body {
  const b = system(systemId).bodies.find((x) => x.id === bodyId);
  if (!b) throw new Error(`body ${bodyId} missing from ${systemId}`);
  return b;
}

const notesOf = (systemId: string, bodyId: string) => appearanceNotes(bodyIn(systemId, bodyId), system(systemId));

function rowOf(notes: readonly AppearanceNote[], property: string | RegExp): AppearanceNote {
  const r = notes.find((n) => (typeof property === 'string' ? n.property === property : property.test(n.property)));
  if (!r) throw new Error(`no row ${String(property)} in ${notes.map((n) => n.property).join(' | ')}`);
  return r;
}

const verdictOf = (systemId: string, bodyId: string) => rowOf(notesOf(systemId, bodyId), 'Resolved by SPHEREx?').value;
const IR_COLOUR = /^Colour · SPHEREx IR/;
const VISIBLE_COLOUR = /^Colour · Visible/;
const BAD_TEXT = /\bNaN\b|\bundefined\b|\bnull\b|Infinity|\[object/;

describe('every demo body', () => {
  it('gets both panel sections, and every row has a value, tier, method, citation and known flags', () => {
    expect(ALL.length).toBeGreaterThanOrEqual(20);
    for (const { system: s, body: b } of ALL) {
      const notes = appearanceNotes(b, s);
      const where = `${s.id}/${b.id}`;
      expect(notes.some((n) => n.section === 'drawn'), where).toBe(true);
      expect(notes.some((n) => n.section === 'spherex'), where).toBe(true);
      for (const n of notes) {
        const at = `${where} · ${n.property}`;
        expect(['drawn', 'derived', 'spherex'], at).toContain(n.section);
        expect(n.property.trim(), at).not.toBe('');
        expect(n.value.trim(), at).not.toBe('');
        expect(n.method.trim(), at).not.toBe('');
        expect(n.citation.trim(), at).not.toBe('');
        for (const text of [n.property, n.value, n.unit, n.method, n.citation]) expect(text, at).not.toMatch(BAD_TEXT);
        expect(NOTE_TIERS, at).toContain(n.tier);
        expect(NOTE_TIER_LABEL[n.tier], at).toBeTruthy();
        expect(NOTE_TIER_MEANING[n.tier], at).toBeTruthy();
        for (const f of n.flags) expect(FLAG_TEXT[f], `${at} flag ${f}`).toBeTruthy();
      }
    }
  });

  it('lists every visual property of the drawing', () => {
    for (const { system: s, body: b } of ALL) {
      const props = appearanceNotes(b, s)
        .filter((n) => n.section === 'drawn')
        .map((n) => n.property);
      const where = `${s.id}/${b.id}`;
      for (const p of [IR_COLOUR, VISIBLE_COLOUR, /^Surface pattern$/, /^Size on screen$/, /^Rotation$/, /^Lighting$/]) {
        expect(props.some((x) => p.test(x)), `${where} ${String(p)}`).toBe(true);
      }
      if (b.kind === 'star') for (const p of ['Glow', 'Limb darkening', 'On-screen brightness']) expect(props, where).toContain(p);
      // The class-typical toggle only exists for real systems (the synthetic demo keeps its textures).
      expect(props.includes("Toggle 'Show class-typical features'"), where).toBe(!s.provenance.synthetic);
    }
    // IR false colour is the default colour mode and the panel says so.
    expect(rowOf(notesOf('barnards-star', 'barnards-star'), IR_COLOUR).property).toMatch(/default view/);
  });

  it('never calls anything saturated (only the non-linearity onset is known) and never mutates the system', () => {
    for (const s of SYSTEMS) {
      const before = JSON.stringify(s);
      for (const b of s.bodies) {
        for (const n of appearanceNotes(b, s)) expect(JSON.stringify(n), `${b.id} ${n.property}`).not.toMatch(/saturat/i);
      }
      expect(JSON.stringify(s)).toBe(before);
    }
  });

  it("describes what the scene's rule modules draw (colour, surface pattern, spin, pulsation)", () => {
    for (const { system: s, body: b } of ALL) {
      const notes = appearanceNotes(b, s);
      const where = `${s.id}/${b.id}`;
      const ir = bodyLook(b, s, 'ir');
      const irRow = rowOf(notes, IR_COLOUR);
      if (ir.drawnAs === 'blackbody') expect(irRow.value.startsWith(ir.hex), where).toBe(true);
      if (ir.drawnAs === 'qualitative') {
        expect(irRow.value, where).toMatch(/^qualitative/);
        expect(irRow.value, where).not.toMatch(/#|\d\.\d/); // no numbers below 2500 K
        expect(irRow.flags, where).toContain('blackbody-unreliable');
      }
      if (ir.drawnAs === 'outline') expect(irRow.tier, where).toBe('not-drawn');

      const spin = spinModel(b, s.bodies);
      expect(rowOf(notes, 'Rotation').tier, where).toBe(spin.kind === 'none' ? 'not-drawn' : spin.tier);

      expect(notes.some((n) => n.property === 'Pulsation (radius)'), where).toBe(drawsPulsation(b));

      if (b.kind !== 'star') {
        const pattern = surfacePattern(b, s, false);
        expect(rowOf(notes, 'Surface pattern').tier, where).toBe(pattern === 'none' ? 'not-drawn' : 'illustrative');
      }
    }
  });
});

describe('How this body is drawn', () => {
  it('real non-stellar bodies carry no surface pattern; the synthetic demo keeps its procedural textures', () => {
    for (const { system: s, body: b } of ALL) {
      if (b.kind === 'star') continue;
      const row = rowOf(appearanceNotes(b, s), 'Surface pattern');
      if (s.provenance.synthetic) {
        expect(row.tier, b.id).toBe('illustrative');
        expect(row.value, b.id).toMatch(/procedural/);
      } else {
        expect(row.tier, b.id).toBe('not-drawn');
        expect(row.value, b.id).toMatch(/^none/);
      }
    }
  });

  it('the class-typical toggle is off by default and its features are labelled CLASS-TYPICAL / ILLUSTRATIVE', () => {
    for (const { system: s, body: b } of ALL) {
      if (s.provenance.synthetic) continue;
      const row = rowOf(appearanceNotes(b, s), "Toggle 'Show class-typical features'");
      expect(row.value, b.id).toMatch(/^off by default/);
      const adds = surfacePattern(b, s, true) !== 'none';
      expect(row.tier, b.id).toBe(adds ? 'class-typical' : 'not-drawn');
      if (adds) expect(row.value, b.id).toMatch(/ILLUSTRATIVE/);
    }
    expect(rowOf(notesOf('epsilon-indi', 'eps-indi-ba'), /class-typical/).value).toMatch(/bands/);
  });

  it('stars: granulation only where resolvable; dwarfs say how many cells and why they are not drawn', () => {
    const barnard = rowOf(notesOf('barnards-star', 'barnards-star'), 'Surface pattern');
    expect(barnard.value).toBe('none: ≈1,600 cells across, too small to draw');
    expect(barnard.tier).toBe('model');
    expect(barnard.method).toMatch(/26× smaller/);
    for (const [sysId, id] of [
      ['epsilon-indi', 'eps-indi-a'],
      ['rw-aurigae', 'rw-aur-a'],
      ['rw-aurigae', 'rw-aur-b'],
    ] as const) {
      expect(rowOf(notesOf(sysId, id), 'Surface pattern').value, id).toMatch(/too small to draw/);
    }
    // R Dra: drawn once the catalog gives it its illustrative 1 M_sun (M2); until then not computed.
    const rdra = bodyIn('r-draconis', 'r-draconis');
    const row = rowOf(appearanceNotes(rdra, system('r-draconis')), 'Surface pattern');
    if (rdra.mass_kg === null) expect(row.tier).toBe('not-drawn');
    else expect(row.value).toMatch(/convection cells across/);
  });

  it('R Dra with the illustrative 1 M_sun: about 8 cells, and the verdict holds for 200–300 R_sun and 1–2 M_sun', () => {
    const base = bodyIn('r-draconis', 'r-draconis');
    const rdra: Body = {
      ...base,
      mass_kg: PHYS.GMSun / PHYS.G,
      facts: [
        ...base.facts.filter((f) => !/^mass\b/i.test(f.label)),
        { label: 'Mass (illustrative)', value: '1.0', unit: 'solar masses', source: 'no dynamical mass; typical Mira 1-2 M_sun', verified: false },
      ],
    };
    const sys: SystemModel = { ...system('r-draconis'), bodies: [rdra] };
    const notes = appearanceNotes(rdra, sys);
    const row = rowOf(notes, 'Surface pattern');
    expect(row.value).toMatch(/^≈8(\.\d)? convection cells across, ±15 % contrast, turnover ≈ 1\d\d d$/);
    expect(row.tier).toBe('illustrative');
    expect(row.method).toMatch(/for R 200–300 R☉ and M 1–2 M☉ \(illustrative ranges\) the count is 6\.\d–2\d, so the verdict holds/);
    expect(GRANULATION_SENSITIVITY['r-draconis']).toEqual({ radiusRsun: [200, 300], massMsun: [1, 2] });
    expect(rowOf(notes, 'Luminosity').tier).toBe('illustrative');
  });

  it('rotation: only a verified period or the tidal-lock rule makes a body spin', () => {
    const star = rowOf(notesOf('barnards-star', 'barnards-star'), 'Rotation');
    expect(star.value).toBe('one turn per 145.0 days');
    expect(star.tier).toBe('measured');
    expect(star.citation).toMatch(/Toledo-Padrón et al\. 2019/);
    for (const id of ['barnard-b', 'barnard-c', 'barnard-d', 'barnard-e']) {
      const r = rowOf(notesOf('barnards-star', id), 'Rotation');
      expect(r.tier, id).toBe('theory');
      expect(r.value, id).toMatch(/^tidally locked/);
      expect(r.citation, id).toMatch(/Barnes 2017/);
    }
    for (const { system: s, body: b } of ALL) {
      if (spinModel(b, s.bodies).kind !== 'none') continue;
      const r = rowOf(appearanceNotes(b, s), 'Rotation');
      expect(r.value, b.id).toBe('rotation unknown: not drawn');
      expect(r.tier, b.id).toBe('not-drawn');
    }
    // The literature notes explain bodies that do NOT spin, and name real demo bodies.
    for (const id of Object.keys(ROTATION_NOT_DRAWN_NOTES)) {
      const hit = ALL.find(({ body }) => body.id === id);
      expect(hit, id).toBeDefined();
      expect(hit!.body.rotation_period_hours, id).toBeNull();
      expect(rowOf(appearanceNotes(hit!.body, hit!.system), 'Rotation').citation, id).toBe(ROTATION_NOT_DRAWN_NOTES[id].citation);
    }
  });

  it('colour: brown dwarfs have no visible colour, planets are a neutral grey, cold bodies are qualitative in IR', () => {
    for (const [sysId, id] of [
      ['epsilon-indi', 'eps-indi-ba'],
      ['epsilon-indi', 'eps-indi-bb'],
      ['wise-0855', 'wise-0855'],
    ] as const) {
      const notes = notesOf(sysId, id);
      expect(rowOf(notes, VISIBLE_COLOUR).value, id).toMatch(/^not computed: neutral/);
      expect(rowOf(notes, VISIBLE_COLOUR).citation, id).toMatch(/Burrows, Marley & Sharp 2000/);
      expect(rowOf(notes, IR_COLOUR).value, id).toMatch(/^qualitative: brightest in red \(D5\+D6\)/);
    }
    expect(rowOf(notesOf('wise-0855', 'wise-0855'), VISIBLE_COLOUR).method).toMatch(/3\.4e-24 of its light/);
    expect(rowOf(notesOf('barnards-star', 'barnard-b'), VISIBLE_COLOUR).value).toBe('neutral 18 % grey');
    expect(rowOf(notesOf('barnards-star', 'barnard-b'), VISIBLE_COLOUR).method).toMatch(/minimum mass/);
    expect(rowOf(notesOf('barnards-star', 'barnards-star'), VISIBLE_COLOUR).value).toMatch(/^#[0-9a-f]{6} \(x 0\.\d{4}, y 0\.\d{4}\)/);
  });
});

describe('At SPHEREx scale', () => {
  it('separation verdicts follow the 0.5 / 2 FWHM rule', () => {
    expect(separationVerdict(0, 3.44).verdict).toBe('always one SPHEREx source');
    expect(separationVerdict(0, 3.46).verdict).toBe('depends on date/orientation');
    expect(separationVerdict(16.7, 20).verdict).toBe('separate sources');
    expect(separationVerdict(16.5, 20).verdict).toBe('depends on date/orientation');
    expect(separationVerdict(0, 5).method).toMatch(/below the Sparrow limit in every detector/);
    expect(separationVerdict(0, 6).method).not.toMatch(/below the Sparrow limit in every detector/);
  });

  it("Barnard's planets and Eps Ind Bb are always blended; A–Ba is separate; A–Ab depends on the date", () => {
    for (const id of ['barnard-b', 'barnard-c', 'barnard-d', 'barnard-e']) {
      expect(verdictOf('barnards-star', id), id).toBe('always one SPHEREx source');
    }
    expect(verdictOf('epsilon-indi', 'eps-indi-ba')).toBe('separate sources');
    expect(verdictOf('epsilon-indi', 'eps-indi-bb')).toBe('always one SPHEREx source');
    expect(verdictOf('epsilon-indi', 'eps-indi-ab')).toBe('depends on date/orientation');
    expect(rowOf(notesOf('epsilon-indi', 'eps-indi-ab'), 'Resolved by SPHEREx?').method).toMatch(/below the Sparrow limit/);
  });

  it('RW Aur A–B is always one source, from the measured separation with an orbit-independent drift bound', () => {
    const notes = notesOf('rw-aurigae', 'rw-aur-b');
    expect(verdictOf('rw-aurigae', 'rw-aur-b')).toBe('always one SPHEREx source');
    expect(rowOf(notes, /^Measured projected separation/).value).toBe('1.5″ = 0.24 px');
    expect(rowOf(notes, /^Separation from/).value).toMatch(/^≤ 2\.95″ = 0\.48 px/);
    const v = rowOf(notes, 'Resolved by SPHEREx?');
    expect(v.method).toMatch(/escape speed/);
    expect(v.method).toMatch(/blend RW Aurigae A \+ RW Aurigae B/);
    expect(v.tier).toBe('derived');
  });

  it('angular sizes and separations against the 6.15″ pixel', () => {
    expect(rowOf(notesOf('barnards-star', 'barnards-star'), 'Angular diameter').value).toBe('0.94 mas = 1/6,500 px');
    expect(rowOf(notesOf('r-draconis', 'r-draconis'), 'Angular diameter').value).toBe('2.9 mas = 1/2,100 px');
    expect(rowOf(notesOf('barnards-star', 'barnard-e'), /^Separation from/).value).toBe('≤ 0.0208″ = 1/300 px');
    expect(rowOf(notesOf('epsilon-indi', 'eps-indi-bb'), /^Separation from/).value).toMatch(/^≤ 1\.02″ = 0\.17 px \(true separation 0\.304–1\.02″/);
    expect(rowOf(notesOf('epsilon-indi', 'eps-indi-ab'), /^Separation from/).value).toMatch(/^≤ 5\.42″ = 0\.88 px/);
    expect(rowOf(notesOf('epsilon-indi', 'eps-indi-ba'), /^Measured projected separation/).value).toBe('401″ = 65 px');
    expect(pixelText(6.15)).toBe('1 px');
    expect(pixelText(0.00094)).toBe('1/6,500 px');
    expect(SPHEREX_SCALE_NOTE).toMatch(/6\.152″ measured/);
    expect(NOTES_HEADER).toBe('Calculated in your browser from the catalog values above with the stated formulae - not new measurements');
  });

  it('shows AB per detector only when the reliability rule allows it, else the reason', () => {
    let shown = 0;
    for (const { system: s, body: b } of ALL) {
      const notes = appearanceNotes(b, s).filter((n) => n.section === 'spherex');
      const pred = spherexPrediction(b, s);
      const abRows = notes.filter((n) => n.unit === 'AB mag');
      const allowed = pred.value.filter((x) => x.abMag.value !== null);
      expect(abRows.length, b.id).toBe(allowed.length);
      abRows.forEach((r, i) => expect(Number(r.value), `${b.id} ${r.property}`).toBeCloseTo(allowed[i].abMag.value as number, 2));
      if (!allowed.length) expect(rowOf(notes, 'Predicted AB (D1–D6)').value, b.id).toBe(`not shown: ${pred.reliability}`);
      shown += abRows.length;
    }
    expect(shown).toBeGreaterThanOrEqual(12); // Barnard's Star and Eps Ind A at least
    for (const [sysId, id] of [
      ['epsilon-indi', 'eps-indi-ba'],
      ['epsilon-indi', 'eps-indi-bb'],
      ['wise-0855', 'wise-0855'],
    ] as const) {
      const notes = notesOf(sysId, id);
      expect(notes.filter((n) => n.unit === 'AB mag'), id).toEqual([]);
      expect(rowOf(notes, 'Predicted AB (D1–D6)').value, id).toBe('not shown: blackbody unreliable - not shown');
    }
  });

  it('flags predictions brighter than the pre-launch non-linearity onset', () => {
    const ab = notesOf('barnards-star', 'barnards-star').filter((n) => n.unit === 'AB mag');
    expect(ab.map((n) => n.value)).toEqual(['6.93', '6.45', '6.46', '6.82', '7.22', '7.42']);
    for (const r of ab) {
      expect(r.flags, r.property).toContain('brighter-than-nonlinearity');
      expect(r.method, r.property).toMatch(/non-linearity onset AB [\d.]+ \(pre-launch model\)/);
    }
    expect(FLAG_TEXT['brighter-than-nonlinearity']).toMatch(/OVERFLOW and NONLINEAR/);
  });

  it('the blend fraction appears only for blended stellar pairs, with numbers only when both are reliable', () => {
    const bb = rowOf(notesOf('epsilon-indi', 'eps-indi-bb'), /^Blend fraction/);
    expect(bb.value).toBe('not shown: needs reliable AB predictions for both');
    expect(notesOf('barnards-star', 'barnard-b').some((n) => n.property.startsWith('Blend fraction'))).toBe(false);
    expect(notesOf('epsilon-indi', 'eps-indi-ba').some((n) => n.property.startsWith('Blend fraction'))).toBe(false); // separate
    // A twin of Eps Ind A on a 1 AU orbit: both reliable, so each detector shares the light 50/50.
    const eps = system('epsilon-indi');
    const a = bodyIn('epsilon-indi', 'eps-indi-a');
    const twin: Body = {
      ...a,
      id: 'twin',
      name: 'Twin',
      orbit: {
        parent: a.id,
        semi_major_axis_au: 1,
        period_days: 365,
        eccentricity: 0,
        inclination_deg: 0,
        ascending_node_deg: 0,
        arg_periapsis_deg: 0,
        mean_anomaly_deg: 0,
        epoch_mjd: null,
        quality: 'fitted',
      },
    };
    const binary: SystemModel = { ...eps, bodies: [a, twin] };
    const blend = rowOf(appearanceNotes(twin, binary), /^Blend fraction/);
    expect(blend.value).toBe('D1 0.5 · D2 0.5 · D3 0.5 · D4 0.5 · D5 0.5 · D6 0.5');
  });
});

describe('physical quantities behind the drawing', () => {
  it('stars get L, log g, H_p and band fractions; planets get Teq for A_B 0 and 0.3, S and the mass class', () => {
    const star = notesOf('barnards-star', 'barnards-star').filter((n) => n.section === 'derived');
    expect(star.map((n) => n.property)).toEqual([
      'Luminosity',
      'Surface gravity log g',
      'Pressure scale height H_p',
      'Visible fraction (380–780 nm)',
      'Fraction of the light per SPHEREx detector',
      'Spectral class (parsed)',
    ]);
    const planet = notesOf('barnards-star', 'barnard-b').filter((n) => n.section === 'derived');
    expect(planet.map((n) => n.property)).toEqual([
      'Equilibrium temperature (A_B = 0)',
      'Equilibrium temperature (A_B = 0.3)',
      'Insolation S/S⊕',
      'Mass class',
    ]);
    expect(rowOf(planet, 'Mass class').flags).toContain('lower-bound');
    expect(rowOf(notesOf('r-draconis', 'r-draconis'), 'Luminosity').tier).toBe('illustrative');
  });

  it("snapshot of Barnard's Star and Barnard b (property, value, unit, tier, flags)", () => {
    const compact = (systemId: string, bodyId: string) =>
      notesOf(systemId, bodyId).map(
        (n) => `${n.section} | ${n.property} | ${n.value}${n.unit ? ` ${n.unit}` : ''} | ${n.tier}${n.flags.length ? ` | ${n.flags.join(',')}` : ''}`,
      );
    expect(compact('barnards-star', 'barnards-star')).toMatchInlineSnapshot(`
      [
        "drawn | Colour · SPHEREx IR (false colour), default view | #85ffe1: R 0.52 · G 1 · B 0.88; the system's brightest (top of the stretch) | model",
        "drawn | Colour · Visible (CIE 1931, blackbody) | #ffbe7a (x 0.4237, y 0.3991), at display brightness 0.8 | model",
        "drawn | On-screen brightness | visible 0.8 · IR 1 | display",
        "drawn | Glow | ×5 display radius (IR), ×5 (visible) | display",
        "drawn | Limb darkening | I(limb)/I(centre): visible R 0.18 · G 0.13 · B 0.073; IR (4.37/2.5/1.11 µm) R 0.69 · G 0.6 · B 0.37 | model",
        "drawn | Surface pattern | none: ≈1,600 cells across, too small to draw | model",
        "drawn | Toggle 'Show class-typical features' | off by default; nothing to add for this kind of body | not-drawn",
        "drawn | Size on screen | ×4.1 true size (true-proportions mode), ×7.3 (compressed mode) | display",
        "drawn | Rotation | one turn per 145.0 days | measured",
        "drawn | Lighting | self-luminous; its light takes its drawn hue (visible #ffbe7a, IR #85ffe1) | display",
        "derived | Luminosity | 0.00321 L☉ | derived",
        "derived | Surface gravity log g | 5.11 dex (cgs) | derived",
        "derived | Pressure scale height H_p | 15.6 km | model",
        "derived | Visible fraction (380–780 nm) | 0.16 of the light | model",
        "derived | Fraction of the light per SPHEREx detector | D1 0.26 · D2 0.28 · D3 0.19 · D4 0.11 · D5 0.017 · D6 0.01 | model",
        "derived | Spectral class (parsed) | M4 V (main-sequence) | derived",
        "spherex | Angular diameter | 0.94 mas = 1/6,500 px | derived",
        "spherex | Predicted AB, D1 (0.746–1.117 µm) | 6.93 AB mag | model | brighter-than-nonlinearity",
        "spherex | Predicted AB, D2 (1.103–1.65 µm) | 6.45 AB mag | model | brighter-than-nonlinearity",
        "spherex | Predicted AB, D3 (1.63–2.435 µm) | 6.46 AB mag | model | brighter-than-nonlinearity",
        "spherex | Predicted AB, D4 (2.403–3.847 µm) | 6.82 AB mag | model | brighter-than-nonlinearity",
        "spherex | Predicted AB, D5 (3.811–4.43 µm) | 7.22 AB mag | model | brighter-than-nonlinearity",
        "spherex | Predicted AB, D6 (4.412–5.01 µm) | 7.42 AB mag | model | brighter-than-nonlinearity",
      ]
    `);
    expect(compact('barnards-star', 'barnard-b')).toMatchInlineSnapshot(`
      [
        "drawn | Colour · SPHEREx IR (false colour), default view | emission not modelled: drawn as an outline | not-drawn | not-modelled",
        "drawn | Colour · Visible (CIE 1931, blackbody) | neutral 18 % grey | display | not-modelled",
        "drawn | Surface pattern | none (uniform) | not-drawn",
        "drawn | Toggle 'Show class-typical features' | off by default; when on: albedo mottling, ±10 % (ILLUSTRATIVE) | class-typical",
        "drawn | Size on screen | ×36 true size (true-proportions mode), ×64 (compressed mode) | display",
        "drawn | Rotation | tidally locked: one turn per orbit (3.2 days) | theory",
        "drawn | Lighting | visible: light of Barnard's Star #ffbe7a; IR: dark, with an outline | display",
        "derived | Equilibrium temperature (A_B = 0) | 438 K | model",
        "derived | Equilibrium temperature (A_B = 0.3) | 401 K | model",
        "derived | Insolation S/S⊕ | 6.1 S⊕ | model",
        "derived | Mass class | Terran | derived | lower-bound",
        "spherex | Angular diameter | 0.034 mas = 1/180,000 px | model",
        "spherex | Separation from Barnard's Star | ≤ 0.0125″ = 1/490 px | model",
        "spherex | Resolved by SPHEREx? | always one SPHEREx source | model",
        "spherex | Predicted AB (D1–D6) | not shown: not modelled | model | not-modelled",
      ]
    `);
  });
});

describe('bundle boundary', () => {
  it('appearanceNotes.ts never imports three.js (BodyPanel is in the main chunk)', () => {
    expect(notesSource).not.toMatch(/from\s+['"]three(\/|['"])/);
    expect(notesSource).not.toMatch(/import\(/);
    const imports = [...notesSource.matchAll(/^\s*import\b[^;]*?\bfrom\s+['"]([^'"]+)['"]/gm)].map((m) => m[1]);
    expect(imports.length).toBeGreaterThan(0);
    for (const i of imports) {
      expect(['../api/types', './appearance', './astro', './bodyFormat', './colorModes', './sceneLayout', './spherexBands'], i).toContain(i);
    }
  });

  it('nor does any module it pulls into the main chunk', () => {
    const sources = import.meta.glob<string>(['./appearance.ts', './bodyFormat.ts', './colorModes.ts', './orbits.ts', './sceneLayout.ts'], {
      eager: true,
      query: '?raw',
      import: 'default',
    });
    expect(Object.keys(sources).length).toBe(5);
    for (const [name, src] of Object.entries(sources)) {
      expect(src, name).not.toMatch(/from\s+['"]three(\/|['"])/);
      expect(src, name).not.toMatch(/import\(\s*['"]three/);
      expect(src, name).not.toMatch(/from\s+['"]\.\/SystemScene['"]/);
    }
  });
});
