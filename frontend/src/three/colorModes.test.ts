import { describe, expect, it } from 'vitest';
import type { Body, SystemModel } from '../api/types';
import appearanceSource from './appearance.ts?raw';
import colorModesSource from './colorModes.ts?raw';
import sceneLayoutSource from './sceneLayout.ts?raw';
import { bodyColor, hasSurfacePattern, NEUTRAL_GREY_HEX, surfacePattern } from './appearance';
import { limbDarkeningLut } from './astro';
import {
  bodyLook,
  colorLegend,
  DEFAULT_COLOR_MODE,
  detectorMeanIntensity,
  FALSE_COLOUR_CHIP,
  glowOpacity,
  glowPulse,
  IR_CHANNELS,
  IR_DYNAMIC_RANGE_MAG,
  irChannelIntensity,
  irLevel,
  irLimbDarkeningLut,
  srgbDecode,
  srgbEncode,
  starLimbDarkening,
  surfaceLegend,
  systemGlowFactors,
  systemIrPeak,
  type ColorMode,
} from './colorModes';
import { SPHEREX_DETECTORS } from './spherexBands';

const SYSTEMS = Object.values(
  import.meta.glob<SystemModel>('../../../data/demo/systems/*.json', { eager: true, import: 'default' }),
);
const sys = (id: string) => SYSTEMS.find((s) => s.id === id)!;
const bod = (systemId: string, bodyId: string): Body => sys(systemId).bodies.find((b) => b.id === bodyId)!;
const MODES: ColorMode[] = ['ir', 'visible'];

describe('colour modes (M3)', () => {
  it('SPHEREx false colour is the default, labelled with the SPHEREx span', () => {
    expect(DEFAULT_COLOR_MODE).toBe('ir');
    expect(FALSE_COLOUR_CHIP).toBe('FALSE COLOUR · SPHEREx 0.75–5 µm');
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
        for (const mode of MODES) expect(bodyLook(b, system, mode).drawnAs).not.toBe('synthetic');
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

  it('sRGB transfer curve round-trips', () => {
    for (const v of [0, 0.002, 0.05, 0.18, 0.5, 1]) expect(srgbDecode(srgbEncode(v))).toBeCloseTo(v, 9);
    expect(srgbEncode(0.18)).toBeCloseTo(0x76 / 255, 2);
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
          expect(lut[0], `${b.id} ${mode}`).toBeLessThan(1);
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
        expect(Math.max(...values), `${system.id} ${mode}`).toBeCloseTo(5, 12);
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
  it('no pattern on any real body unless the class-typical toggle is on; the synthetic demo keeps its textures', () => {
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

  it('with the toggle on: bands on gas giants and brown dwarfs, mottling on rocky planets, never on stars or disks', () => {
    const on = (s: string, b: string) => surfacePattern(bod(s, b), sys(s), true);
    expect(on('epsilon-indi', 'eps-indi-ab')).toBe('bands');
    expect(on('epsilon-indi', 'eps-indi-ba')).toBe('bands');
    expect(on('wise-0855', 'wise-0855')).toBe('bands');
    expect(on('barnards-star', 'barnard-b')).toBe('mottling');
    expect(on('barnards-star', 'barnards-star')).toBe('none');
    expect(on('rw-aurigae', 'rw-aur-a-disk')).toBe('none');
    expect(on('r-draconis', 'r-draconis')).toBe('none');
  });

  it('legends say what is drawn and label the illustrative parts', () => {
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
    expect(surfaceLegend(eps, 'ir', false).join(' ')).toMatch(/No surface features/);
    expect(surfaceLegend(eps, 'visible', true).join(' ')).toMatch(/ILLUSTRATIVE/);
    expect(surfaceLegend(sys('r-draconis'), 'ir', false).join(' ')).toMatch(/CLASS-TYPICAL Mira/);
    expect(surfaceLegend(sys('barnards-star'), 'visible', false).join(' ')).toMatch(/too small to draw/);
  });
});

describe('main-chunk safety', () => {
  it('the modules SystemViewer imports statically never import three.js', () => {
    for (const [name, src] of [
      ['colorModes.ts', colorModesSource],
      ['sceneLayout.ts', sceneLayoutSource],
      ['appearance.ts', appearanceSource],
    ] as const) {
      expect(src, name).not.toMatch(/from\s+['"]three/);
      expect(src, name).not.toMatch(/import\(\s*['"]three/);
      expect(src, name).not.toMatch(/from\s+['"]\.\/(SystemScene|starMaterial)['"]/);
    }
  });
});
