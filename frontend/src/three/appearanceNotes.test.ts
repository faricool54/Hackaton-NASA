import { describe, expect, it } from 'vitest';
import type { Body, SystemModel } from '../api/types';
import panelSource from '../components/BodyPanel.tsx?raw';
import notesSource from './appearanceNotes.ts?raw';
import { surfacePattern } from './appearance';
import {
  FLAG_TEXT,
  SCENE_DRAWING_DEFAULTS,
  NOTE_TIER_LABEL,
  NOTE_TIER_MEANING,
  NOTE_TIERS,
  NOTES_HEADER,
  ROTATION_NOT_DRAWN_NOTES,
  SPHEREX_SCALE_NOTE,
  SURFACE_NOT_DRAWN_NOTES,
  appearanceNotes,
  pixelText,
  separationVerdict,
  type AppearanceNote,
} from './appearanceNotes';
import { MIRA_TIO_CITATION, PHYS, granulationParams, spherexPrediction } from './astro';
import { COLOR_MODES, COLOR_MODE_LABEL, SPHEREX_LIGHT_CURVE_POINTER, bodyLook } from './colorModes';
import { MIRA_EPHEMERIDES, MIRA_PREDICTION_CAVEAT } from './ephemerides';
import { UNKNOWN_COLOUR_TEXT, UNKNOWN_SIZE_TEXT } from './factOrigin';
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
const DETECTOR_GREY = /^Grey level · SPHEREx single detector \(D1–D6\)$/;
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
      for (const p of [IR_COLOUR, DETECTOR_GREY, VISIBLE_COLOUR, /^Surface pattern$/, /^Size on screen$/, /^Rotation$/, /^Lighting$/]) {
        expect(props.some((x) => p.test(x)), `${where} ${String(p)}`).toBe(true);
      }
      if (b.kind === 'star') for (const p of ['Glow', 'Limb darkening', 'On-screen brightness']) expect(props, where).toContain(p);
      // The class-typical toggle is gone: no row describes it, and no row draws a class-typical feature.
      expect(props.some((x) => /class-typical/i.test(x)), where).toBe(false);
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
      if (ir.drawnAs === 'unknown-colour') {
        expect(irRow.value, where).toBe(`${UNKNOWN_COLOUR_TEXT}: neutral grey`);
        expect(irRow.tier, where).toBe('not-drawn');
        expect(irRow.flags, where).toContain('missing-input');
      }
      if (ir.drawnAs === 'synthetic') expect(irRow.value, where).toBe(`${ir.hex} (demo palette)`);
      const d1 = bodyLook(b, s, 'D1');
      const grey = rowOf(notes, DETECTOR_GREY);
      if (d1.drawnAs === 'outline') expect(grey.tier, where).toBe('not-drawn');
      if (d1.drawnAs === 'qualitative') expect(grey.value, where).not.toMatch(/\d/);
      if (d1.drawnAs === 'blackbody') expect(grey.value, where).toMatch(/^display level D1 [\d.]+ · D2 [\d.]+ · D3 [\d.]+ · D4 [\d.]+ · D5 [\d.]+ · D6 [\d.]+$/);

      const spin = spinModel(b, s.bodies);
      expect(rowOf(notes, 'Rotation').tier, where).toBe(spin.kind === 'none' ? 'not-drawn' : spin.tier);

      expect(notes.some((n) => n.property === 'Pulsation (radius)'), where).toBe(drawsPulsation(b));

      if (b.kind !== 'star') {
        const pattern = surfacePattern(b, s);
        expect(rowOf(notes, 'Surface pattern').tier, where).toBe(pattern === 'none' ? 'not-drawn' : 'illustrative');
      }
      // A real star is a smooth sphere: SystemScene draws convection cells on the synthetic demo only.
      if (!s.provenance.synthetic && b.kind === 'star') expect(rowOf(notes, 'Surface pattern').value, where).toMatch(/^none/);
      // Size unknown: a fixed marker, said so in the size row.
      if (b.kind !== 'disk' && !(b.radius_km && b.radius_km > 0) && !s.provenance.synthetic) {
        const size = rowOf(notes, 'Size on screen');
        expect(size.value, where).toMatch(new RegExp(`^fixed marker, [\\d.]+ scene units \\(${UNKNOWN_SIZE_TEXT}\\)$`));
        expect(size.tier, where).toBe('not-drawn');
      }
    }
  });

  it('never states a quantity in the wrong unit or a phase relation as physics', () => {
    for (const { system: s, body: b } of ALL) {
      for (const n of appearanceNotes(b, s)) {
        const text = `${n.value} ${n.method}`;
        expect(text, `${b.id} ${n.property}`).not.toMatch(/F_ν units/); // ⟨I_ν⟩ is a surface brightness
        expect(text, `${b.id} ${n.property}`).not.toMatch(/largest when brightest/);
        expect(text, `${b.id} ${n.property}`).not.toMatch(/mottling/);
      }
    }
    const ir = rowOf(notesOf('barnards-star', 'barnards-star'), IR_COLOUR);
    expect(ir.method).toMatch(/⟨I_ν⟩ = Σ∫B_λ dλ \/ ΣΔν over its two detectors \(surface brightness, MJy\/sr-like units\)/);
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

  it('no class-typical toggle or feature remains on any real body (docs/VISION.md: nothing invented)', () => {
    for (const { system: s, body: b } of ALL) {
      if (s.provenance.synthetic) continue;
      for (const n of appearanceNotes(b, s)) {
        expect(`${n.property} ${n.value}`, `${b.id} ${n.property}`).not.toMatch(/class-typical|ILLUSTRATIVE/i);
        expect(n.tier, `${b.id} ${n.property}`).not.toBe('class-typical');
      }
    }
  });

  it('surface-pattern rows say exactly what is known: no map, and no verified modulation amplitude in the catalog', () => {
    for (const { system: s, body: b } of ALL) {
      if (b.kind === 'star' || s.provenance.synthetic) continue;
      const row = rowOf(appearanceNotes(b, s), 'Surface pattern');
      // The old blanket claim was false for WISE 0855 (Esplin et al. 2016 measured its modulation).
      expect(row.method, b.id).not.toMatch(/rotational modulation exists/);
      if (b.kind === 'disk') {
        expect(row.value, b.id).toBe('none (uniform translucent ring)');
        expect(row.method, b.id).toMatch(/only marks the disk radius/);
      } else {
        expect(row.method, b.id).toMatch(/^no surface map of this body is measured, and the catalog has no verified rotational-modulation amplitude for it/);
      }
    }
    // WISE 0855: modulation IS measured (Spitzer), but period and amplitude are not verified for the catalog.
    const wise = notesOf('wise-0855', 'wise-0855');
    const surface = rowOf(wise, 'Surface pattern');
    expect(surface.method).toMatch(/rotational modulation itself IS measured: Spitzer 3\.6 and 4\.5 µm/);
    expect(surface.method).toMatch(/period is not determined, no amplitude is verified for this catalog/);
    expect(surface.citation).toMatch(/Esplin et al\. 2016, ApJ 832, 58/);
    // ... consistent with its Rotation row, which cites the same Spitzer fits.
    expect(rowOf(wise, 'Rotation').citation).toMatch(/Esplin et al\. 2016, ApJ 832, 58/);
    expect(rowOf(notesOf('rw-aurigae', 'rw-aur-a-disk'), 'Surface pattern').citation).toMatch(/Kurtovic et al\. 2024/);
    // The literature notes name real demo bodies that are drawn uniform.
    for (const id of Object.keys(SURFACE_NOT_DRAWN_NOTES)) {
      const hit = ALL.find(({ body }) => body.id === id);
      expect(hit, id).toBeDefined();
      const row = rowOf(appearanceNotes(hit!.body, hit!.system), 'Surface pattern');
      expect(row.tier, id).toBe('not-drawn');
      expect(row.method, id).toContain(SURFACE_NOT_DRAWN_NOTES[id].note);
      expect(row.citation, id).toContain(SURFACE_NOT_DRAWN_NOTES[id].citation);
    }
    // A catalog rotation amplitude would be named, and still not turned into a map.
    const ba = bodyIn('epsilon-indi', 'eps-indi-ba');
    const modulated: Body = { ...ba, variability: { kind: 'rotation', period_days: 0.1, amplitude_mag: 0.05, band: 'J' } };
    const sys: SystemModel = { ...system('epsilon-indi'), bodies: system('epsilon-indi').bodies.map((b) => (b.id === ba.id ? modulated : b)) };
    expect(rowOf(appearanceNotes(modulated, sys), 'Surface pattern').method).toMatch(
      /the catalog gives a rotational modulation of 0\.05 mag \(J\), but a disc-integrated light curve is not a map/,
    );
  });

  it('R Dra (Mira, no measured Teff or radius): grey and a fixed marker; the AB rule still names the molecular bands', () => {
    const notes = notesOf('r-draconis', 'r-draconis');
    for (const prop of [IR_COLOUR, DETECTOR_GREY, VISIBLE_COLOUR]) {
      const r = rowOf(notes, prop);
      expect(r.value, String(prop)).toBe(`${UNKNOWN_COLOUR_TEXT}: neutral grey`);
      expect(r.tier, String(prop)).toBe('not-drawn');
    }
    expect(rowOf(notes, 'On-screen brightness').value).toMatch(/^neutral grey, level 0\.46 in every colour mode$/);
    expect(rowOf(notes, 'Size on screen').value).toMatch(/size unknown · not to scale/);
    expect(rowOf(notes, 'Limb darkening').value).toBe('none (flat disc)');
    // The Mira reason comes before the missing-input rule (astro.spherexReliability).
    expect(rowOf(notes, 'Predicted AB (D1–D6)').value).toBe('not shown: photosphere blackbody - molecular bands and dust not modelled');
    expect(rowOf(notes, 'Predicted AB (D1–D6)').method).toMatch(/no Teff is measured for this star/);
    expect(notes.filter((n) => n.unit === 'AB mag')).toEqual([]);
    const puls = rowOf(notes, 'Pulsation (radius)');
    expect(puls.value).toBe('radius drawn constant');
    expect(puls.tier).toBe('not-drawn');
  });

  it('R Dra pulsation and glow rows: constant radius, catalog V light curve on the glow, pointer to the SPHEREx light curve', () => {
    const eph = MIRA_EPHEMERIDES.find((e) => e.systemId === 'r-draconis' && e.bodyId === 'r-draconis')!;
    expect(eph).toBeTruthy();
    const notes = notesOf('r-draconis', 'r-draconis');
    const puls = rowOf(notes, 'Pulsation (radius)');
    expect(puls.method).toMatch(/^the size change of this pulsating star is not measured, so its radius is drawn constant in both clocks/);
    expect(puls.method).toContain('V-band light curve (catalog, not measured by SPHEREx; see the glow row)');
    expect(puls.method).toContain(`${eph.source} (±9 d timing band, 1σ)`);
    expect(puls.method).toContain(SPHEREX_LIGHT_CURVE_POINTER);
    expect(puls.method).not.toMatch(/±10 %|class-typical/);
    expect(puls.citation).toContain(`ephemeris: ${eph.source}; timing band: ${eph.timingSource}`);
    // The glow: modulated in visible mode only, on both clocks, TiO-driven.
    const glow = rowOf(notes, 'Glow');
    expect(glow.method).toMatch(/light curve \(catalog, not measured by SPHEREx\) modulates the glow in visible mode only \(opacity × f\^0\.25, size × f\^0\.3/);
    expect(glow.method).toContain('the radius stays constant');
    expect(glow.method).toContain('free-running clock, a sine at the catalog period with an arbitrary phase');
    expect(glow.method).toContain(
      `Dataset time, the predicted ${eph.band} phase on the asymmetric curve of the ephemeris in the pulsation row (${MIRA_PREDICTION_CAVEAT})`,
    );
    expect(glow.method).toContain(`TiO absorption, not by the Planck function (${MIRA_TIO_CITATION})`);
    expect(glow.citation).toContain(eph.source);
    // A pulsating star without a tabulated ephemeris: still a constant radius, and the glow is held at the mean.
    const sys: SystemModel = { ...system('r-draconis'), id: 'not-in-the-table' };
    const other = appearanceNotes(sys.bodies[0], sys);
    expect(rowOf(other, 'Pulsation (radius)').value).toBe('radius drawn constant');
    expect(rowOf(other, 'Pulsation (radius)').citation).toMatch(/SCIENCE\.md 3D review \(V12b\)$/);
    expect(rowOf(other, 'Glow').method).toContain('Dataset time, held at the mean (no catalogue ephemeris: phase unknown)');
  });

  it('lists every colour mode: the panel says which one the view opens in and names the others', () => {
    expect(SCENE_DRAWING_DEFAULTS.colourMode).toBe(COLOR_MODE_LABEL.ir);
    expect(SCENE_DRAWING_DEFAULTS.otherColourModes).toEqual(COLOR_MODES.filter((m) => m !== 'ir').map((m) => COLOR_MODE_LABEL[m]));
    expect(SCENE_DRAWING_DEFAULTS.otherColourModes).toHaveLength(7); // visible + D1..D6
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

  it('a real star whose cells would be resolvable is still drawn smooth (no cell is observed on it)', () => {
    // Test inputs only (not catalog values): an R Dra-like giant with resolvable cells.
    const base = bodyIn('r-draconis', 'r-draconis');
    const giant: Body = { ...base, teff_k: 3000, radius_km: 250 * (PHYS.RSun / 1e3), mass_kg: PHYS.GMSun / PHYS.G };
    const sys: SystemModel = { ...system('r-draconis'), bodies: [giant] };
    expect(granulationParams(giant).draw).toBe(true);
    const row = rowOf(appearanceNotes(giant, sys), 'Surface pattern');
    expect(row.value).toBe('none: smooth sphere with limb darkening');
    expect(row.tier).toBe('not-drawn');
    expect(row.method).toMatch(/no surface of this star is resolved or mapped, so no convection cells are drawn/);
    // The synthetic demo keeps its decoration: the same star in a synthetic system gets cells.
    const demo: SystemModel = { ...sys, provenance: { ...sys.provenance, synthetic: true } };
    expect(rowOf(appearanceNotes(giant, demo), 'Surface pattern').value).toMatch(/convection cells across, .*\(synthetic demo\)$/);
  });

  it('rotation: only a verified period or the tidal-lock rule makes a body spin', () => {
    const star = rowOf(notesOf('barnards-star', 'barnards-star'), 'Rotation');
    // The Fact's own text with its error: no false decimal (145 ± 15 d, Toledo-Padrón et al. 2019).
    expect(star.value).toBe('one turn per 145 ± 15 days');
    expect(star.method).toMatch(/drawn at P = 3,480 h \(145 d, the catalog's central value\)/);
    expect(star.method).not.toMatch(/145\.0/);
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
    expect(rowOf(notesOf('r-draconis', 'r-draconis'), 'Angular diameter').value).toBe('not computed'); // radius unknown
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
        "drawn | Grey level · SPHEREx single detector (D1–D6) | display level D1 1 · D2 1 · D3 1 · D4 1 · D5 1 · D6 1 | model",
        "drawn | Colour · Visible (CIE 1931, blackbody) | #ffbe7a (x 0.4237, y 0.3991), at display brightness 0.8 | model",
        "drawn | On-screen brightness | visible 0.8 · IR 1 | display",
        "drawn | Glow | ×5 display radius (IR), ×5 (visible) | display",
        "drawn | Limb darkening | I(limb)/I(centre): visible R 0.18 · G 0.13 · B 0.073; IR (4.37/2.5/1.11 µm) R 0.69 · G 0.6 · B 0.37 | model",
        "drawn | Surface pattern | none: ≈1,600 cells across, too small to draw | model",
        "drawn | Size on screen | ×4.1 true size (true-proportions mode), ×7.3 (compressed mode) | display",
        "drawn | Rotation | one turn per 145 ± 15 days | measured",
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
        "drawn | Grey level · SPHEREx single detector (D1–D6) | emission not modelled: drawn as an outline | not-drawn | not-modelled",
        "drawn | Colour · Visible (CIE 1931, blackbody) | neutral 18 % grey | display | not-modelled",
        "drawn | Surface pattern | none (uniform) | not-drawn",
        "drawn | Size on screen | ×36 true size (true-proportions mode), ×64 (compressed mode) | display",
        "drawn | Rotation | tidally locked: one turn per orbit (3.2 days) | theory",
        "drawn | Lighting | visible: light of Barnard's Star #ffbe7a; SPHEREx modes: dark, with an outline | display",
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
  it('BodyPanel loads appearanceNotes only on demand (dynamic import), so it stays out of the main chunk', () => {
    const fromNotes = [...panelSource.matchAll(/^\s*import\s+(type\s+)?[^;]*?\bfrom\s+['"]\.\.\/three\/appearanceNotes['"]/gm)];
    expect(fromNotes.length).toBeGreaterThan(0);
    for (const m of fromNotes) expect(m[1], m[0]).toBe('type '); // type-only: erased at build time
    expect(panelSource).toMatch(/import\(\s*['"]\.\.\/three\/appearanceNotes['"]\s*\)/);
  });

  it('appearanceNotes.ts never imports three.js (it is loaded next to the main chunk, not with the 3D one)', () => {
    expect(notesSource).not.toMatch(/from\s+['"]three(\/|['"])/);
    expect(notesSource).not.toMatch(/import\(/);
    const imports = [...notesSource.matchAll(/^\s*import\b[^;]*?\bfrom\s+['"]([^'"]+)['"]/gm)].map((m) => m[1]);
    expect(imports.length).toBeGreaterThan(0);
    for (const i of imports) {
      expect(['../api/types', './appearance', './astro', './colorModes', './ephemerides', './factOrigin', './sceneLayout', './spherexBands'], i).toContain(i);
    }
  });

  it('nor does any module it pulls in', () => {
    const sources = import.meta.glob<string>(
      ['./appearance.ts', './bodyFormat.ts', './colorModes.ts', './ephemerides.ts', './factOrigin.ts', './kindLabels.ts', './orbits.ts', './sceneLayout.ts'],
      { eager: true, query: '?raw', import: 'default' },
    );
    expect(Object.keys(sources).length).toBe(8);
    for (const [name, src] of Object.entries(sources)) {
      expect(src, name).not.toMatch(/from\s+['"]three(\/|['"])/);
      expect(src, name).not.toMatch(/import\(\s*['"]three/);
      expect(src, name).not.toMatch(/from\s+['"]\.\/SystemScene['"]/);
    }
  });
});
