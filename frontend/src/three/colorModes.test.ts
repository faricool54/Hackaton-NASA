import { describe, expect, it } from 'vitest';
import type { Body, SystemModel } from '../api/types';
import { bodyColor, hasSurfacePattern, NEUTRAL_GREY_HEX, surfacePattern } from './appearance';
import { limbDarkeningLut, MIRA_LAYERS_CITATION, MIRA_TIO_CITATION, PHYS } from './astro';
import { UNKNOWN_COLOUR_TEXT, UNKNOWN_SIZE_TEXT } from './factOrigin';
import {
  bodyLook,
  COLOR_MODE_LABEL,
  COLOR_MODES,
  colorLegend,
  colourModeChip,
  DEFAULT_COLOR_MODE,
  detectorCenterUm,
  detectorIntensity,
  detectorLimbDarkeningLut,
  detectorMeanIntensity,
  FALSE_COLOUR_CHIP,
  glowLuminosity,
  isDetectorMode,
  systemDetectorPeak,
  glowOpacity,
  glowPulse,
  IR_CHANNELS,
  IR_DYNAMIC_RANGE_MAG,
  irChannelIntensity,
  isInfraredMode,
  irLevel,
  irLimbDarkeningLut,
  srgbDecode,
  srgbEncode,
  SPHEREX_LIGHT_CURVE_POINTER,
  starLimbDarkening,
  surfaceLegend,
  systemGlowFactors,
  systemIrPeak,
  VISIBLE_CHIP,
  type ColorMode,
} from './colorModes';
import { SPHEREX_DETECTORS } from './spherexBands';

const SYSTEMS = Object.values(
  import.meta.glob<SystemModel>('../../../data/demo/systems/*.json', { eager: true, import: 'default' }),
);
const sys = (id: string) => SYSTEMS.find((s) => s.id === id)!;
const bod = (systemId: string, bodyId: string): Body => sys(systemId).bodies.find((b) => b.id === bodyId)!;
const MODES: readonly ColorMode[] = COLOR_MODES;

describe('colour modes (M3)', () => {
  it('SPHEREx false colour is the default, labelled as a blackbody MODEL in the SPHEREx bands', () => {
    expect(DEFAULT_COLOR_MODE).toBe('ir');
    expect(FALSE_COLOUR_CHIP).toBe('FALSE COLOUR · BLACKBODY MODEL · SPHEREx 0.75–5 µm bands');
    expect(colourModeChip('ir')).toBe(FALSE_COLOUR_CHIP);
    expect(colourModeChip('visible')).toBe(VISIBLE_CHIP);
    expect(VISIBLE_CHIP).toBe('VISIBLE · BLACKBODY COLOUR MODEL'); // SCIENCE.md 3D review A15
    expect(colourModeChip('D3')).toBe('SPHEREx D3 ONLY · GREY · BLACKBODY MODEL · 1.63–2.44 µm');
    expect(COLOR_MODES).toEqual(['ir', 'visible', 'D1', 'D2', 'D3', 'D4', 'D5', 'D6']);
    for (const m of COLOR_MODES) expect(COLOR_MODE_LABEL[m], m).toBeTruthy();
    expect(IR_CHANNELS.map((c) => `${c.channel}:${c.detectors.map((d) => d.id).join('+')}`)).toEqual(['r:D5+D6', 'g:D3+D4', 'b:D1+D2']);
  });

  it('every demo body yields a valid colour in both modes', () => {
    let n = 0;
    for (const system of SYSTEMS) {
      for (const b of system.bodies) {
        for (const mode of MODES) {
          const l = bodyLook(b, system, mode);
          expect(l.hex, `${system.id}/${b.id} ${mode}`).toMatch(/^#[0-9a-f]{6}$/);
          expect(l.level).toBeGreaterThanOrEqual(0);
          expect(l.level).toBeLessThanOrEqual(1);
          expect(Math.max(...l.hue)).toBeLessThanOrEqual(1 + 1e-12);
          expect(l.note.length).toBeGreaterThan(0);
          n++;
        }
        expect(bodyColor(b, system)).toMatch(/^#[0-9a-f]{6}$/);
      }
    }
    expect(n).toBeGreaterThan(30);
  });

  it('the synthetic palette (#7a2e3b brown dwarf, gas-giant tan) is unreachable for real systems', () => {
    for (const system of SYSTEMS.filter((s) => !s.provenance.synthetic)) {
      for (const b of system.bodies) {
        const c = bodyColor(b, system);
        expect(['#7a2e3b', '#c9a27a', '#bcd7e8', '#d9a066', '#9a8f84'], `${system.id}/${b.id}`).not.toContain(c);
        if (b.kind !== 'star') expect(c, b.id).toBe(NEUTRAL_GREY_HEX);
        for (const mode of MODES) expect(bodyLook(b, system, mode).drawnAs, mode).not.toBe('synthetic');
      }
    }
    // A hand-set colour is ignored for a real body, kept for the synthetic demo.
    const real = { ...bod('epsilon-indi', 'eps-indi-ba'), appearance: { ...bod('epsilon-indi', 'eps-indi-ba').appearance, color_hex: '#ff00ff' } };
    expect(bodyColor(real, sys('epsilon-indi'))).toBe(NEUTRAL_GREY_HEX);
    expect(bodyColor(real, sys('demo-ecliptic-orbits'))).toBe('#ff00ff');
  });

  it('IR hue: WISE 0855 glows only at D5/D6; Bb is redder than Ba; Barnard D1 and D5 agree within 2x', () => {
    const wise = irChannelIntensity(285)!;
    expect(wise.r).toBeGreaterThan(100 * wise.b);
    expect(wise.r).toBeGreaterThan(wise.g);
    const ba = bodyLook(bod('epsilon-indi', 'eps-indi-ba'), sys('epsilon-indi'), 'ir');
    const bb = bodyLook(bod('epsilon-indi', 'eps-indi-bb'), sys('epsilon-indi'), 'ir');
    expect(bb.hue[0]).toBeCloseTo(1, 12);
    expect(bb.hue[2]).toBeLessThan(ba.hue[2] / ba.hue[0]);
    expect(bb.hue[1]).toBeLessThan(ba.hue[1] / ba.hue[0]);
    // Barnard's Star: blackbody AB 6.93 (D1) vs 7.22 (D5), i.e. F_ν within 30 %.
    const d1 = detectorMeanIntensity(3195, SPHEREX_DETECTORS[0])!;
    const d5 = detectorMeanIntensity(3195, SPHEREX_DETECTORS[4])!;
    expect(d1 / d5).toBeGreaterThan(0.5);
    expect(d1 / d5).toBeLessThan(2);
    // A hot star is blue in this mapping, a cool dwarf peaks in green (F_ν peak near 1.6 µm at 3200 K).
    const hot = irChannelIntensity(5772)!;
    expect(hot.b).toBeGreaterThan(hot.r);
    const m = irChannelIntensity(3195)!;
    expect(m.g).toBeGreaterThan(m.r);
  });

  it('the band-mean F_ν equals the frequency average of B_ν (checked against direct quadrature)', () => {
    const h = 6.62607015e-34;
    const c = 299792458;
    const k = 1.380649e-23;
    for (const T of [285, 900, 3195, 5772]) {
      for (const d of SPHEREX_DETECTORS) {
        const n0 = c / (d.lambdaMaxUm * 1e-6);
        const n1 = c / (d.lambdaMinUm * 1e-6);
        const steps = 4000;
        let sum = 0;
        for (let i = 0; i < steps; i++) {
          const nu = n0 + ((i + 0.5) / steps) * (n1 - n0);
          sum += (2 * h * nu ** 3) / c ** 2 / Math.expm1((h * nu) / (k * T));
        }
        const direct = sum / steps;
        expect(detectorMeanIntensity(T, d)! / direct, `${T} K ${d.id}`).toBeCloseTo(1, 3);
      }
    }
  });

  it('IR stretch: log over a fixed 10 mag below the system peak', () => {
    expect(irLevel(1, 1)).toBe(1);
    expect(irLevel(10 ** (-0.4 * IR_DYNAMIC_RANGE_MAG), 1)).toBeCloseTo(0, 12);
    expect(irLevel(10 ** (-0.4 * 5), 1)).toBeCloseTo(0.5, 12);
    expect(irLevel(1e-9, 1)).toBe(0);
    expect(irLevel(0, 1)).toBe(0);
    for (const system of SYSTEMS) {
      const peak = systemIrPeak(system);
      if (!peak) continue;
      const levels = system.bodies.map((b) => bodyLook(b, system, 'ir')).filter((l) => l.drawnAs === 'blackbody' || l.drawnAs === 'qualitative');
      expect(Math.max(...levels.map((l) => l.level)), system.id).toBeCloseTo(1, 12);
    }
  });

  it('cold brown dwarfs: dark in visible light, visible (qualitative, MODEL) in SPHEREx IR', () => {
    for (const [s, b] of [
      ['epsilon-indi', 'eps-indi-ba'],
      ['epsilon-indi', 'eps-indi-bb'],
      ['wise-0855', 'wise-0855'],
    ] as const) {
      const vis = bodyLook(bod(s, b), sys(s), 'visible');
      const ir = bodyLook(bod(s, b), sys(s), 'ir');
      expect(vis.drawnAs, b).toBe('neutral-emission');
      expect(vis.hue).toEqual([1, 1, 1]);
      expect(ir.drawnAs, b).toBe('qualitative');
      expect(ir.tier, b).toBe('model');
      expect(ir.level, b).toBeGreaterThan(vis.level);
      expect(ir.level, b).toBeGreaterThan(0.3);
    }
    // astro.displayBrightness: Ba ≈ 0.2, Bb and WISE 0855 on the 0.05 floor.
    expect(bodyLook(bod('epsilon-indi', 'eps-indi-ba'), sys('epsilon-indi'), 'visible').level).toBeGreaterThan(0.1);
    expect(bodyLook(bod('epsilon-indi', 'eps-indi-ba'), sys('epsilon-indi'), 'visible').level).toBeLessThan(0.4);
    expect(bodyLook(bod('epsilon-indi', 'eps-indi-bb'), sys('epsilon-indi'), 'visible').level).toBeCloseTo(0.05, 12);
    expect(bodyLook(bod('wise-0855', 'wise-0855'), sys('wise-0855'), 'visible').level).toBeCloseTo(0.05, 12);
  });

  it('stars use the CIE colour in visible light and a blackbody false colour in IR', () => {
    const a = bodyLook(bod('epsilon-indi', 'eps-indi-a'), sys('epsilon-indi'), 'visible');
    expect(a.drawnAs).toBe('blackbody');
    expect(a.hue[0]).toBeCloseTo(1, 12); // 4700 K: red channel largest
    expect(a.hue[2]).toBeLessThan(a.hue[0]);
    const ir = bodyLook(bod('barnards-star', 'barnards-star'), sys('barnards-star'), 'ir');
    expect(ir.drawnAs).toBe('blackbody');
    expect(['model', 'derived']).toContain(ir.tier);
    expect(ir.level).toBeCloseTo(1, 12);
  });

  it('planets: neutral 18 % grey lit in visible light, outline only in IR; the disk is never coloured', () => {
    for (const p of sys('barnards-star').bodies.filter((b) => b.kind === 'planet')) {
      const vis = bodyLook(p, sys('barnards-star'), 'visible');
      expect(vis.drawnAs).toBe('reflected-grey');
      expect(vis.hex).toBe(NEUTRAL_GREY_HEX);
      expect(bodyLook(p, sys('barnards-star'), 'ir').drawnAs).toBe('outline');
    }
    const disk = bod('rw-aurigae', 'rw-aur-a-disk');
    for (const mode of MODES) {
      const l = bodyLook(disk, sys('rw-aurigae'), mode);
      expect(l.drawnAs).toBe('outline');
      expect(l.hue).toEqual([1, 1, 1]);
    }
  });

  it('the synthetic demo keeps its palette in every mode; only its star follows the mode', () => {
    const demo = sys('demo-ecliptic-orbits');
    for (const b of demo.bodies) {
      for (const mode of MODES) {
        const l = bodyLook(b, demo, mode);
        if (b.kind === 'star') {
          expect(l.drawnAs, `${b.id} ${mode}`).toBe(mode === 'visible' ? 'synthetic' : 'blackbody');
        } else {
          expect(l.drawnAs, `${b.id} ${mode}`).toBe('synthetic');
          expect(l.hex, `${b.id} ${mode}`).toBe(bodyColor(b, demo));
          expect(l.note, b.id).not.toMatch(/not modelled \(outline/);
        }
      }
    }
    // The legends say the same thing in every SPHEREx mode.
    for (const mode of ['ir', 'D4'] as const) {
      const text = colorLegend(mode, demo).join(' ');
      expect(text, mode).toMatch(/synthetic demo bodies, drawn with their hand palette and procedural textures in every colour mode/);
      expect(text, mode).not.toMatch(/drawn as an outline/);
      expect(surfaceLegend(demo, mode).join(' '), mode).toMatch(/procedural decoration, in every colour mode/);
    }
  });

  it('the IR legend names the surface brightness I_nu, never the flux density F_nu', () => {
    for (const system of SYSTEMS) {
      for (const mode of ['ir', 'D2'] as const) {
        const text = colorLegend(mode, system).join(' ');
        expect(text, `${system.id} ${mode}`).not.toMatch(/F_ν/);
        const withTeff = system.bodies.some((b) => (b.kind === 'star' || b.kind === 'brown_dwarf') && !!b.teff_k && b.teff_k > 0);
        if (withTeff) {
          expect(text, `${system.id} ${mode}`).toMatch(/surface brightness ⟨I_ν⟩ \(MJy\/sr-like units\)/);
        } else if (system.bodies.some((b) => b.kind === 'star' || b.kind === 'brown_dwarf')) {
          // R Dra: no body has a Teff, so no blackbody sentence describes a drawing nobody gets.
          expect(text, `${system.id} ${mode}`).not.toMatch(/blackbody at the catalog Teff/);
          expect(text, `${system.id} ${mode}`).toMatch(/No body of this system has a catalog Teff, so none is drawn as a blackbody/);
        }
      }
    }
  });

  it('sRGB transfer curve round-trips', () => {
    for (const v of [0, 0.002, 0.05, 0.18, 0.5, 1]) expect(srgbDecode(srgbEncode(v))).toBeCloseTo(v, 9);
    expect(srgbEncode(0.18)).toBeCloseTo(0x76 / 255, 2);
  });
});

describe('single-detector modes (D1..D6, grey)', () => {
  it('each body is grey at the mean I_nu of that detector, on a 10 mag stretch below the system peak in it', () => {
    for (const system of SYSTEMS.filter((s) => !s.provenance.synthetic)) {
      for (const mode of MODES.filter(isDetectorMode)) {
        const peak = systemDetectorPeak(system, mode);
        const levels: number[] = [];
        for (const b of system.bodies) {
          const l = bodyLook(b, system, mode);
          if (l.drawnAs === 'outline' || l.drawnAs === 'unknown-colour') continue;
          expect(l.hue, `${system.id}/${b.id} ${mode}`).toEqual([1, 1, 1]);
          const i = detectorIntensity(b.teff_k!, mode)!;
          expect(l.level, `${b.id} ${mode}`).toBeCloseTo(irLevel(i, peak!), 12);
          levels.push(l.level);
        }
        if (levels.length) expect(Math.max(...levels), `${system.id} ${mode}`).toBeCloseTo(1, 12);
      }
    }
  });

  it('WISE 0855 (285 K) is a million times brighter in D6 than in D1 and stays qualitative; Ba gains on A toward D6', () => {
    const wise = sys('wise-0855');
    const w = bod('wise-0855', 'wise-0855');
    expect(bodyLook(w, wise, 'D6').drawnAs).toBe('qualitative');
    expect(bodyLook(w, wise, 'D6').tier).toBe('model');
    expect(detectorIntensity(285, 'D6')! / detectorIntensity(285, 'D1')!).toBeGreaterThan(1e6);
    // Eps Ind: Ba and Bb are dimmer than A in D1, much closer to it in D6.
    const eps = sys('epsilon-indi');
    const ba = bod('epsilon-indi', 'eps-indi-ba');
    expect(bodyLook(ba, eps, 'D6').level).toBeGreaterThan(bodyLook(ba, eps, 'D1').level);
  });

  it('the single-detector limb darkening is the grey-atmosphere model at the detector centre, equal in r, g, b', () => {
    for (const mode of MODES.filter(isDetectorMode)) {
      const lut = detectorLimbDarkeningLut(3195, mode);
      expect(lut.length).toBe(48);
      for (let i = 0; i < 16; i++) {
        expect(lut[i * 3]).toBe(lut[i * 3 + 1]);
        expect(lut[i * 3]).toBe(lut[i * 3 + 2]);
      }
      expect(lut[45]).toBeCloseTo(1, 9);
      expect(lut[0]).toBeLessThan(1);
    }
    // Longer wavelengths darken less.
    expect(detectorLimbDarkeningLut(3195, 'D6')[0]).toBeGreaterThan(detectorLimbDarkeningLut(3195, 'D1')[0]);
    expect(detectorCenterUm('D1')).toBeCloseTo(Math.sqrt(0.746 * 1.117), 12);
    // The planets stay outlines and the disk a faint ring in a single-detector mode too.
    expect(bodyLook(bod('barnards-star', 'barnard-b'), sys('barnards-star'), 'D3').drawnAs).toBe('outline');
    expect(colorLegend('D5', sys('barnards-star')).join(' ')).toMatch(/Single detector D5 \(3\.81–4\.43 µm\) in grey/);
  });
});

describe('limb darkening tables for the star shader', () => {
  const monotonic = (lut: Float32Array) => {
    for (let ch = 0; ch < 3; ch++) for (let i = 1; i < lut.length / 3; i++) expect(lut[i * 3 + ch]).toBeGreaterThanOrEqual(lut[(i - 1) * 3 + ch] - 1e-6);
  };

  it('the IR table is monotonic, normalised at the disc centre, and darkens less than the visible one', () => {
    for (const T of [3000, 3195, 4150, 4700, 5772]) {
      const ir = irLimbDarkeningLut(T);
      const vis = limbDarkeningLut(T).value;
      expect(ir.length).toBe(48);
      monotonic(ir);
      for (let ch = 0; ch < 3; ch++) expect(ir[45 + ch]).toBeCloseTo(1, 9);
      // Limb (μ = 0): longer wavelengths darken less, so red (D5+D6) > green > blue (D1+D2).
      expect(ir[0]).toBeGreaterThan(ir[1]);
      expect(ir[1]).toBeGreaterThan(ir[2]);
      // Every IR channel is redward of the CIE red channel: weaker limb darkening.
      expect(ir[2]).toBeGreaterThan(vis[0]);
    }
  });

  it('each star gets a table in each mode; stars without a usable Teff are flat', () => {
    for (const system of SYSTEMS) {
      for (const b of system.bodies.filter((x) => x.kind === 'star')) {
        for (const mode of MODES) {
          const lut = starLimbDarkening(b, mode);
          expect(lut.length, b.id).toBe(48);
          monotonic(lut);
          // R Dra: no Teff measured, so a flat disc (no limb darkening is invented).
          if (b.teff_k === null) expect([...lut].every((v) => v === 1), `${b.id} ${mode}`).toBe(true);
          else expect(lut[0], `${b.id} ${mode}`).toBeLessThan(1);
        }
      }
    }
    const noT = { ...bod('barnards-star', 'barnards-star'), teff_k: null };
    expect([...starLimbDarkening(noT, 'visible')].every((v) => v === 1)).toBe(true);
  });
});

describe('glow (DISPLAY)', () => {
  it('scales with log L within the system: 5 radii for the brightest star, never below 2', () => {
    for (const system of SYSTEMS) {
      for (const mode of MODES) {
        const f = systemGlowFactors(system, mode);
        const values = [...f.values()];
        if (!values.length) continue;
        // A system whose stars all have an unknown luminosity (R Dra: no Teff, no radius) stays at 2.
        const known = system.bodies.some((b) => (glowLuminosity(b, mode) ?? 0) > 0);
        expect(Math.max(...values), `${system.id} ${mode}`).toBeCloseTo(known ? 5 : 2, 12);
        for (const v of values) {
          expect(v).toBeGreaterThanOrEqual(2);
          expect(v).toBeLessThanOrEqual(5);
        }
      }
    }
    const rw = systemGlowFactors(sys('rw-aurigae'), 'visible');
    expect(rw.get('rw-aur-b')!).toBeLessThan(rw.get('rw-aur-a')!);
  });

  it('the V light curve modulates the glow in visible mode only', () => {
    expect(glowOpacity(0.8, 10, 'ir')).toBe(0.8);
    expect(glowPulse(10, 'ir')).toBe(1);
    expect(glowOpacity(0.5, 10, 'visible')).toBeGreaterThan(0.5);
    expect(glowPulse(10, 'visible')).toBeGreaterThan(1);
    expect(glowOpacity(0.5, 0.1, 'visible')).toBeLessThan(0.5);
  });
});

describe('surfaces: real targets show only what is measured (M3, S5)', () => {
  it('no pattern on any real body (the class-typical toggle is gone); the synthetic demo keeps its textures', () => {
    for (const system of SYSTEMS) {
      for (const b of system.bodies) {
        if (system.provenance.synthetic) {
          expect(hasSurfacePattern(b, system), b.id).toBe(b.kind !== 'star' && b.kind !== 'disk');
        } else {
          expect(hasSurfacePattern(b, system), `${system.id}/${b.id}`).toBe(false);
          expect(surfacePattern(b, system), b.id).toBe('none');
        }
      }
    }
  });

  it('legends say what is drawn, and what is unknown', () => {
    const eps = sys('epsilon-indi');
    const ir = colorLegend('ir', eps).join(' ');
    expect(ir).toMatch(/blue = D1\+D2/);
    expect(ir).toMatch(/red = D5\+D6/);
    expect(ir).toMatch(/10 mag/);
    expect(ir).toMatch(/Lupton/);
    const cold = colorLegend('ir', eps).find((l) => l.includes('qualitative'))!;
    expect(cold).toMatch(/Ba/);
    expect(cold.replace('2500 K', '')).not.toMatch(/\d/); // no numbers for the cold bodies
    expect(colorLegend('visible', eps).join(' ')).toMatch(/visible colour not computed/);
    // T Tauri stars: the IR false colour is the photosphere only (disk + accretion excess not modelled).
    expect(colorLegend('ir', sys('rw-aurigae')).join(' ')).toMatch(/photosphere only/);
    expect(bodyLook(bod('rw-aurigae', 'rw-aur-a'), sys('rw-aurigae'), 'ir').note).toMatch(/IR excess/);
    expect(colorLegend('ir', sys('barnards-star')).join(' ')).not.toMatch(/photosphere only/);
    // R Dra: no Teff is measured, so it is grey and the legend says so (no photosphere blackbody is drawn).
    const rdraSys = sys('r-draconis');
    for (const m of MODES) {
      const lines = colorLegend(m, rdraSys).join(' ');
      expect(lines, m).toContain(`R Draconis: ${UNKNOWN_COLOUR_TEXT}. No single effective temperature is adopted for this body`);
      expect(lines, m).not.toMatch(/blackbody at the catalog Teff/);
      expect(lines, m).not.toMatch(/photosphere blackbody only|TiO/);
      expect(bodyLook(rdraSys.bodies[0], rdraSys, m).drawnAs, m).toBe('unknown-colour');
      expect(bodyLook(rdraSys.bodies[0], rdraSys, m).hex, m).toBe(NEUTRAL_GREY_HEX);
    }
    // Mira (R Dra with a test Teff): the legend under the canvas carries the same caveat as the panel rows and the AB rule.
    const rdraT: SystemModel = { ...rdraSys, bodies: [{ ...rdraSys.bodies[0], teff_k: 3000, radius_km: 250 * (PHYS.RSun / 1e3) }] };
    const miraIr = `R Draconis: photosphere blackbody only. The H₂O and CO bands of the extended pulsating atmosphere and the circumstellar dust, which shape the 0.75–5 µm spectrum of a Mira, are not modelled (${MIRA_LAYERS_CITATION}).`;
    expect(colorLegend('ir', rdraT)).toContain(miraIr);
    expect(colorLegend('D5', rdraT)).toContain(miraIr);
    expect(colorLegend('visible', rdraT)).toContain(
      `R Draconis: colour of the photosphere blackbody only. The visible light of a Mira is dominated by TiO absorption bands, which are not modelled (${MIRA_TIO_CITATION}).`,
    );
    expect(MIRA_LAYERS_CITATION).toBe('Höfner & Olofsson 2018, A&ARv 26, 1');
    expect(MIRA_TIO_CITATION).toBe('Reid & Goldston 2002, ApJ 568, 931');
    for (const id of ['barnards-star', 'epsilon-indi', 'rw-aurigae', 'wise-0855', 'demo-ecliptic-orbits']) {
      for (const m of MODES) expect(colorLegend(m, sys(id)).join(' '), `${id} ${m}`).not.toMatch(/Mira|TiO/);
    }
    // Surfaces and sizes: no class-typical feature anywhere; unknown sizes are named.
    for (const m of MODES) {
      expect(surfaceLegend(eps, m).join(' ')).toMatch(/No surface features/);
      expect(surfaceLegend(eps, m).join(' ')).toMatch(/no verified rotational-modulation amplitude/);
      for (const s of SYSTEMS.filter((x) => !x.provenance.synthetic)) {
        expect(surfaceLegend(s, m).join(' '), `${s.id} ${m}`).not.toMatch(/class-typical|ILLUSTRATIVE|±10 %/i);
      }
    }
    expect(surfaceLegend(eps, 'ir')).toContain(
      `Epsilon Indi Ba, Epsilon Indi Bb: ${UNKNOWN_SIZE_TEXT}. No single radius is adopted for this body (none is published, or the published ones depend on assumptions: see its facts and the system notes), so it is drawn at a fixed marker size, not scaled.`,
    );
    const rdra = surfaceLegend(rdraSys, 'ir').join(' ');
    // R Dra is its system's only star and has no Teff: no limb-darkening sentence for a drawing it does not get.
    expect(rdra).not.toMatch(/grey Eddington atmosphere/);
    expect(rdra).toMatch(/^Stars: Flat disc, no limb darkening, for R Draconis/);
    expect(surfaceLegend(sys('barnards-star'), 'ir').join(' ')).toMatch(/limb darkening and reddening from a grey Eddington atmosphere/);
    expect(rdra).toContain('R Draconis: radius drawn constant, because its size change is not measured.');
    expect(rdra).toContain('V-band light curve (catalog, not measured by SPHEREx) drives the glow in the visible mode only, so the glow is steady in this mode');
    expect(rdra).toContain(SPHEREX_LIGHT_CURVE_POINTER);
    expect(rdra).toMatch(/Flat disc, no limb darkening, for R Draconis \(no single temperature adopted/);
    expect(rdra).toMatch(new RegExp(`R Draconis: ${UNKNOWN_SIZE_TEXT}`));
    expect(rdra).not.toMatch(/largest when brightest|in phase/);
    expect(surfaceLegend(rdraSys, 'visible').join(' ')).not.toMatch(/glow is steady/);
    expect(isInfraredMode('visible')).toBe(false);
    // A real star whose cells would be resolvable is still smooth; the synthetic demo keeps its cells.
    const giant: SystemModel = { ...rdraT, bodies: [{ ...rdraT.bodies[0], mass_kg: PHYS.GMSun / PHYS.G }] };
    expect(surfaceLegend(giant, 'ir').join(' ')).toMatch(/R Draconis: smooth sphere \(no convection cell is observed on this star, so none is drawn\)/);
    const demoGiant: SystemModel = { ...giant, provenance: { ...giant.provenance, synthetic: true } };
    expect(surfaceLegend(demoGiant, 'ir').join(' ')).toMatch(/R Draconis: ≈\d+(\.\d)? convection cells across \(.*ILLUSTRATIVE; synthetic demo\)/);
    expect(surfaceLegend(sys('barnards-star'), 'visible').join(' ')).toMatch(/too small to draw/);
  });
});

describe('main-chunk safety', () => {
  // Raw text of every module the walk can reach: this folder (.ts and .tsx), the components, the pages
  // and the api client. Keys become paths under src/ ('three/astro.ts', 'components/SystemViewer.tsx').
  const RAW = import.meta.glob<string>(['./*.{ts,tsx}', '../components/*.{ts,tsx}', '../pages/*.{ts,tsx}', '../api/*.ts'], {
    eager: true,
    query: '?raw',
    import: 'default',
  });
  const SRC = new Map(Object.entries(RAW).map(([k, v]) => [k.startsWith('./') ? `three/${k.slice(2)}` : k.slice(3), v]));

  /**
   * Specifiers of the static value imports and re-exports of a module, in source order. `import type`
   * and `export type` are erased at build time and dynamic import() makes a separate chunk, so neither
   * counts. Mixed imports (`import { a, type B }`) count.
   */
  function staticImports(src: string): string[] {
    const out: { at: number; spec: string }[] = [];
    for (const m of src.matchAll(/^[ \t]*(?:import|export)\s+(type\s+)?[\w\s{},*$]*?\bfrom\s+['"]([^'"]+)['"]/gm)) {
      if (!m[1]) out.push({ at: m.index ?? 0, spec: m[2] });
    }
    for (const m of src.matchAll(/^[ \t]*import\s+['"]([^'"]+)['"]/gm)) out.push({ at: m.index ?? 0, spec: m[1] });
    return out.sort((a, b) => a.at - b.at).map((x) => x.spec);
  }

  /** A relative specifier resolved against the importing module ('components/X.tsx' + '../three/y' → 'three/y.ts'). */
  function resolve(from: string, spec: string): string | null {
    const parts = from.split('/').slice(0, -1);
    for (const seg of spec.split('/')) {
      if (seg === '..') parts.pop();
      else if (seg !== '.') parts.push(seg);
    }
    const base = parts.join('/');
    return [base, `${base}.ts`, `${base}.tsx`, `${base}/index.ts`].find((c) => SRC.has(c)) ?? null;
  }

  /** Every module reachable from `roots` through static imports, with the package imports each one makes. */
  function walk(roots: readonly string[]): Map<string, string[]> {
    const graph = new Map<string, string[]>();
    const queue = [...roots];
    while (queue.length) {
      const name = queue.shift()!;
      if (graph.has(name)) continue;
      const src = SRC.get(name);
      expect(src, `source of ${name}`).toBeTypeOf('string');
      const packages: string[] = [];
      for (const spec of staticImports(src!)) {
        if (!spec.startsWith('.')) packages.push(spec);
        else if (!/\.(css|json|svg|png)(\?|$)/.test(spec)) {
          const target = resolve(name, spec);
          expect(target, `${name} imports ${spec}`).not.toBeNull();
          queue.push(target!);
        }
      }
      graph.set(name, packages);
    }
    return graph;
  }

  it('the import parser keeps value imports and drops type-only and dynamic ones', () => {
    const src = [
      "import { a, type B } from './x';",
      "import type { C } from './y';",
      "export type { D } from './z';",
      "export { e } from './w';",
      "import * as T from 'three';",
      "const m = import('./SystemScene');",
      "import {\n  f,\n  g,\n} from './v';",
      "import './side-effect.css';",
    ].join('\n');
    expect(staticImports(src)).toEqual(['./x', './w', 'three', './v', './side-effect.css']);
    expect(resolve('components/SystemViewer.tsx', '../three/colorModes')).toBe('three/colorModes.ts');
    // The walk follows imports through files: the notes reach astro through their own imports.
    expect(walk(['three/appearanceNotes.ts']).has('three/astro.ts')).toBe(true);
  });

  it("nothing SystemViewer.tsx imports statically reaches three.js, SystemScene or starMaterial (its own imports, read at test time)", () => {
    const viewer = 'components/SystemViewer.tsx';
    const roots = staticImports(SRC.get(viewer)!).filter((s) => s.startsWith('.'));
    expect(roots.length).toBeGreaterThan(0);
    const graph = walk([viewer]); // the viewer itself and everything it reaches
    expect(graph.size).toBeGreaterThan(1);
    for (const [name, packages] of graph) {
      expect(name).not.toMatch(/^three\/(SystemScene|starMaterial)\.ts$/);
      for (const p of packages) expect(p, `${name} imports ${p} statically`).not.toMatch(/^three(\/|$)/);
    }
  });

  it('BodyPanel and SystemsPage take KIND_LABEL from the astro-free kindLabels, so they never reach astro.ts', () => {
    for (const page of ['components/BodyPanel.tsx', 'pages/SystemsPage.tsx']) {
      const graph = walk([page]);
      expect(graph.has('three/kindLabels.ts'), page).toBe(true);
      expect(graph.has('three/appearance.ts'), page).toBe(false);
      expect(graph.has('three/astro.ts'), page).toBe(false);
      for (const [name, packages] of graph) for (const p of packages) expect(p, `${name} imports ${p}`).not.toMatch(/^three(\/|$)/);
    }
  });
});
