// three's ShaderMaterial is plain JS: these tests run in node, with no WebGL context.
import { describe, expect, it } from 'vitest';
import type { Body, SystemModel } from '../api/types';
import { bodyLook, srgbDecode, starLimbDarkening, type ColorMode } from './colorModes';
import { createRimMaterial, createStarMaterial, LD_SAMPLES, ldArray, RIM_DASHES, RIM_LINE_PX, setRimDashes, setStarLook, type StarLook } from './starMaterial';

const SYSTEMS = Object.values(
  import.meta.glob<SystemModel>('../../../data/demo/systems/*.json', { eager: true, import: 'default' }),
);
const sys = (id: string) => SYSTEMS.find((s) => s.id === id)!;
const bod = (systemId: string, bodyId: string): Body => sys(systemId).bodies.find((b) => b.id === bodyId)!;

/** The StarLook SystemScene builds for one star in one colour mode (its own table per mode). */
function starLook(body: Body, system: SystemModel, mode: ColorMode): StarLook {
  const look = bodyLook(body, system, mode);
  return { ld: starLimbDarkening(body, mode), hue: look.hue, brightness: srgbDecode(look.level) };
}

const uLd = (mat: ReturnType<typeof createStarMaterial>) => mat.uniforms.uLd.value as Float32Array;

describe('star material: the limb-darkening uniform never aliases the caller tables', () => {
  const barnard = bod('barnards-star', 'barnards-star');
  const system = sys('barnards-star');

  it('IR -> visible -> IR restores the IR table and leaves both source tables unchanged', () => {
    const ir = starLook(barnard, system, 'ir');
    const vis = starLook(barnard, system, 'visible');
    const irCopy = Float32Array.from(ir.ld);
    const visCopy = Float32Array.from(vis.ld);
    // The two tables really differ (IR limb darkening is much weaker), or the test proves nothing.
    expect(ir.ld[0]).toBeGreaterThan(vis.ld[0] + 0.2);

    const mat = createStarMaterial(ir, null);
    expect(uLd(mat)).not.toBe(ir.ld); // an owned copy
    expect([...uLd(mat)]).toEqual([...irCopy]);

    setStarLook(mat, vis);
    expect([...uLd(mat)]).toEqual([...visCopy]);
    expect([...ir.ld]).toEqual([...irCopy]); // the scene's IR table survived the switch

    setStarLook(mat, ir);
    expect([...uLd(mat)]).toEqual([...irCopy]);
    expect([...vis.ld]).toEqual([...visCopy]);

    // Several more round trips: still exact.
    for (let i = 0; i < 3; i++) {
      setStarLook(mat, vis);
      setStarLook(mat, ir);
    }
    expect([...uLd(mat)]).toEqual([...irCopy]);
    expect([...ir.ld]).toEqual([...irCopy]);
    expect([...vis.ld]).toEqual([...visCopy]);
  });

  it('a material built in visible mode and switched to IR keeps the visible source table', () => {
    const ir = starLook(barnard, system, 'ir');
    const vis = starLook(barnard, system, 'visible');
    const visCopy = Float32Array.from(vis.ld);
    const mat = createStarMaterial(vis, null);
    setStarLook(mat, ir);
    expect([...vis.ld]).toEqual([...visCopy]);
    setStarLook(mat, vis);
    expect([...uLd(mat)]).toEqual([...visCopy]);
  });

  it('colour and brightness follow the mode; the uniform array keeps its size', () => {
    const ir = starLook(barnard, system, 'ir');
    const vis = starLook(barnard, system, 'visible');
    const mat = createStarMaterial(ir, null);
    const colour = mat.uniforms.uColor.value;
    setStarLook(mat, vis);
    expect(mat.uniforms.uBrightness.value).toBe(vis.brightness);
    expect(mat.uniforms.uColor.value).toBe(colour); // updated in place, not replaced
    setStarLook(mat, ir);
    expect(mat.uniforms.uBrightness.value).toBe(ir.brightness);
    expect(uLd(mat).length).toBe(LD_SAMPLES * 3);
    expect(mat.defines.LD_N).toBe(LD_SAMPLES);
  });

  it('ldArray always returns a new array; other lengths are resampled linearly in mu', () => {
    const t = starLimbDarkening(barnard, 'visible');
    const copy = ldArray(t);
    expect(copy).not.toBe(t);
    expect([...copy]).toEqual([...t]);
    const coarse = starLimbDarkening(barnard, 'visible', 4);
    const fine = ldArray(coarse);
    expect(fine.length).toBe(LD_SAMPLES * 3);
    for (let ch = 0; ch < 3; ch++) {
      expect(fine[ch]).toBeCloseTo(coarse[ch], 6); // mu = 0
      expect(fine[(LD_SAMPLES - 1) * 3 + ch]).toBeCloseTo(coarse[9 + ch], 6); // mu = 1
    }
  });

  it('granulation uniforms are set only when cells are drawn', () => {
    const ir = starLook(barnard, system, 'ir');
    expect(createStarMaterial(ir, null).uniforms.uGranCells.value).toBe(0);
    const g = createStarMaterial(ir, { cells: 8, contrast: 0.15, seed: 12345 });
    expect(g.uniforms.uGranCells.value).toBe(8);
    expect(g.uniforms.uContrast.value).toBe(0.15);
  });
});

describe('rim material (DISPLAY outline)', () => {
  it('is a thin pixel-width line; dashes switch on and off without a rebuild', () => {
    const rim = createRimMaterial('#9aa4b8', 0.55);
    expect(rim.uniforms.uLinePx.value).toBe(RIM_LINE_PX);
    expect(RIM_LINE_PX).toBeLessThanOrEqual(3);
    expect(rim.uniforms.uDashes.value).toBe(0);
    setRimDashes(rim, RIM_DASHES);
    expect(rim.uniforms.uDashes.value).toBe(RIM_DASHES);
    setRimDashes(rim, 0);
    expect(rim.uniforms.uDashes.value).toBe(0);
    // The dashed (qualitative) branch draws only the silhouette line: no Fresnel term over the disc.
    const dashed = rim.fragmentShader.slice(rim.fragmentShader.indexOf('if (uDashes > 0.0)'), rim.fragmentShader.indexOf('} else {'));
    expect(dashed).toMatch(/line \*/);
    expect(dashed).not.toMatch(/pow\(/);
  });
});
