import { describe, expect, it } from 'vitest';
import type { Body, Fact, SystemModel } from '../api/types';
import astroSource from './astro.ts?raw';
import cieSource from './cie1931.ts?raw';
import bandsSource from './spherexBands.ts?raw';
import { CIE1931_2DEG } from './cie1931';
import {
  SPHEREX_CHANNELS_PER_DETECTOR,
  SPHEREX_D1_PUBLISHED_CENTERS_UM,
  SPHEREX_DETECTORS,
  SPHEREX_PIXEL_ARCSEC,
} from './spherexBands';
import {
  angularDiameterMas,
  bandFraction,
  blackbodyAbMag,
  blackbodyChromaticity,
  blackbodyColor,
  bodyColor,
  deriveBody,
  derivedTier,
  displayBrightness,
  distanceTier,
  equilibriumTemperature,
  granulationParams,
  insolation,
  limbDarkeningAt,
  limbDarkeningLut,
  luminosity,
  massClass,
  paramTier,
  PHYS,
  pressureScaleHeight,
  separationBoundsArcsec,
  spectralClass,
  spherexPrediction,
  spherexReliability,
  surfaceGravity,
  TIERS,
  weakestTier,
  type Derived,
  type Tier,
} from './astro';

// Every demo system shipped with the site (the same JSON the pipeline writes).
const SYSTEMS = Object.values(
  import.meta.glob<SystemModel>('../../../data/demo/systems/*.json', { eager: true, import: 'default' }),
);

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

const num = (d: Derived<number | null>): number => {
  expect(d.value, d.method).not.toBeNull();
  return d.value as number;
};
/** Rounded to the precision a fixture was quoted with. */
const sig = (x: number, n: number) => Number(x.toPrecision(n));
const rel = (x: number, ref: number) => Math.abs(x / ref - 1);

const BARNARD = system('barnards-star');
const EPS = system('epsilon-indi');
const RWAUR = system('rw-aurigae');
const WISE = system('wise-0855');
const RDRA = system('r-draconis');
const DEMO = system('demo-ecliptic-orbits');
const barnard = bodyIn('barnards-star', 'barnards-star');
const epsA = bodyIn('epsilon-indi', 'eps-indi-a');

/** R Dra as M2 will make it: 1 M_sun, Fact 'Mass (illustrative)', unverified. */
const rDraWithMass: Body = {
  ...bodyIn('r-draconis', 'r-draconis'),
  mass_kg: PHYS.GMSun / PHYS.G,
  facts: [
    ...bodyIn('r-draconis', 'r-draconis').facts.filter((f) => !/^mass\b/i.test(f.label)),
    { label: 'Mass (illustrative)', value: '1.0', unit: 'solar masses', source: 'no dynamical mass; typical Mira 1-2 M_sun', verified: false },
  ],
};

/** The IAU 2015 B3 nominal Sun. */
const SUN: Body = {
  ...bodyIn('demo-ecliptic-orbits', 'sun'),
  radius_km: PHYS.RSun / 1e3,
  mass_kg: PHYS.GMSun / PHYS.G,
  teff_k: PHYS.TeffSun,
};

describe('constants and tiers', () => {
  it('the nominal Sun has L = 1.000 L_sun and log g = 4.438', () => {
    expect(Math.abs(num(luminosity(SUN)) - 1)).toBeLessThan(0.001);
    expect(num(surfaceGravity(SUN))).toBeCloseTo(4.438, 3);
    // The demo Sun (catalog constants 695700 km, 1.989e30 kg) agrees too.
    const demoSun = bodyIn('demo-ecliptic-orbits', 'sun');
    expect(Math.abs(num(luminosity(demoSun)) - 1)).toBeLessThan(0.001);
    expect(num(surfaceGravity(demoSun))).toBeCloseTo(4.438, 3);
  });

  it('a derived value is DERIVED only from measured inputs, otherwise the weakest input', () => {
    expect(derivedTier(['measured', 'measured'])).toBe('derived');
    expect(derivedTier(['measured', 'range-pick'])).toBe('range-pick');
    expect(derivedTier(['measured', 'model', 'illustrative'])).toBe('illustrative');
    expect(derivedTier(['measured'], 'model')).toBe('model'); // the method's own floor
    expect(weakestTier(['derived', 'theory', 'class-typical'])).toBe('theory');
    expect(TIERS[0]).toBe('measured');
  });
});

describe('CIE 1931 table (CIE 018:2019 / CVRL ciexyz31, 5 nm)', () => {
  it('has 95 rows from 360 to 830 nm with the published peak and spot values', () => {
    expect(CIE1931_2DEG).toHaveLength(95);
    CIE1931_2DEG.forEach(([nm], i) => expect(nm).toBe(360 + 5 * i));
    const at = (nm: number) => CIE1931_2DEG.find((r) => r[0] === nm)!;
    expect(at(555)).toEqual([555, 0.5120501, 1.0, 0.005749999]); // ȳ peaks at 1 at 555 nm
    expect(at(360)).toEqual([360, 0.0001299, 0.000003917, 0.0006061]);
    expect(at(830)).toEqual([830, 0.000001251141, 0.00000045181, 0]);
    // Σȳ·Δλ ≈ 106.857 (the CIE metadata column sum of the 1 nm table).
    const sumY = CIE1931_2DEG.reduce((s, r) => s + r[2], 0) * 5;
    expect(rel(sumY, 106.8569171011719)).toBeLessThan(1e-3);
  });

  it('records its source and licence', () => {
    expect(cieSource).toMatch(/10\.25039\/CIE\.DS\.xvudnb9b/);
    expect(cieSource).toMatch(/CC BY-SA 4\.0/);
  });
});

describe('blackbody colour', () => {
  // Kim et al. 2002 (J. Korean Phys. Soc. 41, 865) cubic-spline Planckian locus, 1667-25000 K.
  function kimLocus(T: number): [number, number] {
    const x =
      T <= 4000
        ? -0.2661239e9 / T ** 3 - 0.2343589e6 / T ** 2 + 0.8776956e3 / T + 0.17991
        : -3.0258469e9 / T ** 3 + 2.1070379e6 / T ** 2 + 0.2226347e3 / T + 0.24039;
    const y =
      T <= 2222
        ? -1.1063814 * x ** 3 - 1.3481102 * x ** 2 + 2.18555832 * x - 0.20219683
        : T <= 4000
          ? -0.9549476 * x ** 3 - 1.37418593 * x ** 2 + 2.09137015 * x - 0.16748867
          : 3.081758 * x ** 3 - 5.8733867 * x ** 2 + 3.75112997 * x - 0.37001483;
    return [x, y];
  }

  it('lies on the Kim et al. 2002 Planckian locus within 0.001 from 3000 to 20000 K', () => {
    for (let T = 3000; T <= 20000; T += 100) {
      const c = blackbodyChromaticity(T).value!;
      const [kx, ky] = kimLocus(T);
      expect(Math.abs(c.x - kx), `x at ${T} K`).toBeLessThanOrEqual(0.001);
      expect(Math.abs(c.y - ky), `y at ${T} K`).toBeLessThanOrEqual(0.001);
    }
  });

  it('the Sun is near white, Barnard is red (R > G > B), and nothing is coloured below 2500 K', () => {
    const sun = blackbodyColor(5772).value!;
    expect(Math.min(...sun.linear)).toBeGreaterThan(0.75);
    for (const i of [1, 3, 5]) expect(parseInt(sun.hex.slice(i, i + 2), 16)).toBeGreaterThan(0xe0);
    const [r, g, b] = bodyColor(barnard).value!.linear;
    expect(r).toBe(1);
    expect(r).toBeGreaterThan(g);
    expect(g).toBeGreaterThan(b);
    const ba = blackbodyColor(1300);
    expect(ba.value).toBeNull();
    expect(ba.flags).toContain('blackbody-unreliable');
    expect(bodyColor(bodyIn('epsilon-indi', 'eps-indi-ba')).value).toBeNull();
  });

  it('display brightness: Sun 1, Barnard dimmer, cold dwarfs at the floor; tier DISPLAY', () => {
    expect(displayBrightness(5772).value).toBeCloseTo(1, 9);
    const vb = displayBrightness(3195).value;
    expect(vb).toBeGreaterThan(0.05);
    expect(vb).toBeLessThan(1);
    expect(displayBrightness(285).value).toBe(0.05);
    expect(displayBrightness(3195).tier).toBe('display');
  });
});

describe('judge fixtures (mu = 1.3), at the precision they were quoted', () => {
  it("Barnard's Star", () => {
    expect(rel(num(luminosity(barnard)), 0.00321)).toBeLessThan(0.005);
    expect(Math.abs(num(surfaceGravity(barnard)) - 5.11)).toBeLessThan(0.005);
    expect(sig(num(pressureScaleHeight(barnard)), 3)).toBe(15.6);
    expect(rel(num(granulationParams(barnard)), 1650)).toBeLessThan(0.01);
    expect(sig(num(bandFraction(3195, 0.38, 0.78)), 3)).toBe(0.157);
    const bands = spherexPrediction(barnard, BARNARD).value;
    expect(bands.map((b) => sig(num(b.fraction), 2))).toEqual([0.26, 0.28, 0.19, 0.11, 0.017, 0.01]);
    const ab = [6.93, 6.45, 6.46, 6.82, 7.22, 7.42];
    bands.forEach((b, i) => expect(Math.abs(num(b.abMag) - ab[i]), b.detector.id).toBeLessThanOrEqual(0.01));
    expect(Math.abs(num(angularDiameterMas(barnard, BARNARD)) - 0.94)).toBeLessThan(0.005);
  });

  it('Epsilon Indi A', () => {
    expect(rel(num(luminosity(epsA)), 0.224)).toBeLessThan(0.005);
    expect(Math.abs(num(surfaceGravity(epsA)) - 4.63)).toBeLessThan(0.01);
    const ab = [3.76, 3.77, 4.08, 4.64, 5.14, 5.38];
    spherexPrediction(epsA, EPS).value.forEach((b, i) =>
      expect(Math.abs(num(b.abMag) - ab[i]), b.detector.id).toBeLessThanOrEqual(0.01),
    );
  });

  it('R Draconis (R 250 R_sun, M 1 M_sun, both illustrative)', () => {
    const L = luminosity(rDraWithMass);
    expect(rel(num(L), 4560)).toBeLessThan(0.005);
    expect(L.tier).toBe('illustrative');
    expect(Math.abs(num(surfaceGravity(rDraWithMass)) + 0.36)).toBeLessThan(0.005);
    expect(rel(num(pressureScaleHeight(rDraWithMass)), 4.3e6)).toBeLessThan(0.015);
    const gran = granulationParams(rDraWithMass);
    expect(Math.abs(num(gran) - 8)).toBeLessThan(0.2);
    expect(gran.draw).toBe(true);
    expect(gran.tier).toBe('illustrative');
    expect(rel(num(gran.turnoverDays), 100)).toBeLessThan(0.02);
  });

  it('RW Aurigae A and B', () => {
    const a = bodyIn('rw-aurigae', 'rw-aur-a');
    const b = bodyIn('rw-aurigae', 'rw-aur-b');
    expect(rel(num(luminosity(a)), 0.878)).toBeLessThan(0.002);
    expect(Math.abs(num(surfaceGravity(a)) - 4.3)).toBeLessThan(0.005);
    expect(rel(num(luminosity(b)), 0.601)).toBeLessThan(0.002);
    // 4.084 from the catalog mass 0.995 M_sun (the judge's 4.09 used the rounded 1.00 M_sun).
    expect(Math.abs(num(surfaceGravity(b)) - 4.09)).toBeLessThan(0.01);
  });

  it('visible fractions of the brown dwarfs and the WISE 0855 SPHEREx fractions', () => {
    const vis = (id: string, sysId: string) => num(bandFraction(bodyIn(sysId, id).teff_k!, 0.38, 0.78));
    expect(sig(vis('eps-indi-ba', 'epsilon-indi'), 2)).toBe(3.8e-4);
    expect(sig(vis('eps-indi-bb', 'epsilon-indi'), 2)).toBe(1.9e-6);
    expect(sig(vis('wise-0855', 'wise-0855'), 2)).toBe(3.4e-24);
    const w = spherexPrediction(bodyIn('wise-0855', 'wise-0855'), WISE).value;
    expect(w.slice(2).map((b) => sig(num(b.fraction), 2))).toEqual([1.6e-6, 8.8e-4, 2.6e-3, 5.8e-3]);
    for (const b of w) expect(b.fraction.flags).toContain('blackbody-unreliable');
  });

  it("Barnard's planets: Teq 483/438/400/340 K and S 9.1/6.1/4.3/2.2 S_earth", () => {
    const expected: [string, number, number][] = [
      ['barnard-d', 483, 9.1],
      ['barnard-b', 438, 6.1],
      ['barnard-c', 400, 4.3],
      ['barnard-e', 340, 2.2],
    ];
    for (const [id, teq, s] of expected) {
      const p = bodyIn('barnards-star', id);
      const t = equilibriumTemperature(p, BARNARD);
      expect(Math.abs(num(t) - teq), id).toBeLessThanOrEqual(1);
      expect(t.tier, id).toBe('model'); // the albedo and redistribution are assumed
      expect(sig(num(insolation(p, BARNARD)), 2), id).toBe(s);
      expect(num(equilibriumTemperature(p, BARNARD, 0.3))).toBeLessThan(num(t));
    }
  });

  it('Epsilon Indi Ab Teq 48 K and Earth Teq (5772 K, 1 AU, A = 0) 278.3 K', () => {
    expect(Math.abs(num(equilibriumTemperature(bodyIn('epsilon-indi', 'eps-indi-ab'), EPS)) - 48)).toBeLessThan(0.5);
    expect(num(equilibriumTemperature(bodyIn('demo-ecliptic-orbits', 'earth'), DEMO))).toBeCloseTo(278.3, 1);
    expect(num(insolation(bodyIn('demo-ecliptic-orbits', 'earth'), DEMO))).toBeCloseTo(1, 3);
  });
});

describe('independent photometric checks', () => {
  it("Barnard's blackbody at Ks lies within 0.3 mag of 2MASS", () => {
    // 2MASS J17574849+0441405: Ks = 4.524 ± 0.020 (Vega), Qflg AAA (Cutri et al. 2003, VizieR II/246,
    // CfA mirror, queried 2026-11-14); K_AB − K_Vega = 1.85 (Blanton & Roweis 2007, AJ 133, 734).
    const ksAb = 4.524 + 1.85;
    const bb = blackbodyAbMag(3195, barnard.radius_km!, BARNARD.motion!.distance_pc!, 2.159);
    expect(bb.flags).toEqual([]);
    expect(Math.abs(num(bb) - ksAb)).toBeLessThan(0.3);
  });

  it('WISE 0855: the blackbody is > 2 mag fainter than W2, so the rule says unreliable', () => {
    // AllWISE J085510.74-071442.5: W2 = 13.704 ± 0.033 (Vega) (Cutri et al. 2013, VizieR II/328, CfA
    // mirror, queried 2026-11-14); W2_AB − W2_Vega = 3.339 (Jarrett et al. 2011, ApJ 735, 112).
    const w2Ab = 13.704 + 3.339;
    const body = bodyIn('wise-0855', 'wise-0855');
    const bb = blackbodyAbMag(body.teff_k!, body.radius_km!, WISE.motion!.distance_pc!, 4.6);
    expect(bb.flags).toContain('blackbody-unreliable');
    expect(num(bb) - w2Ab).toBeGreaterThan(2);
    expect(spherexReliability(body, WISE).value).toBe('blackbody unreliable - not shown');
  });

  it('no AB value is returned for any demo body with Teff < 2500 K', () => {
    let checked = 0;
    for (const s of SYSTEMS) {
      for (const b of s.bodies) {
        if (b.teff_k === null || b.teff_k >= 2500) continue;
        checked++;
        for (const band of spherexPrediction(b, s).value) expect(band.abMag.value, `${b.id} ${band.detector.id}`).toBeNull();
      }
    }
    expect(checked).toBeGreaterThanOrEqual(4); // Ba, Bb, Ab, WISE 0855
  });

  it('flags predictions brighter than the SPHEREx non-linearity onset', () => {
    for (const b of spherexPrediction(barnard, BARNARD).value) expect(b.abMag.flags).toContain('brighter-than-nonlinearity');
    const far: SystemModel = { ...BARNARD, motion: { ...BARNARD.motion!, distance_pc: 2000 } };
    for (const b of spherexPrediction(barnard, far).value) expect(b.abMag.flags).not.toContain('brighter-than-nonlinearity');
  });
});

describe('reliability of the SPHEREx numbers', () => {
  it('follows the rule for every demo star and brown dwarf', () => {
    const expected: Record<string, string> = {
      'barnards-star': 'blackbody approx.',
      'eps-indi-a': 'blackbody approx.',
      'eps-indi-ba': 'blackbody unreliable - not shown',
      'eps-indi-bb': 'blackbody unreliable - not shown',
      'wise-0855': 'blackbody unreliable - not shown',
      'r-draconis': 'illustrative inputs',
      'rw-aur-a': 'illustrative inputs', // radius is an unverified estimate
      'rw-aur-b': 'illustrative inputs', // Teff picked inside 4100-4200 K
      sun: 'not modelled', // synthetic system: no distance
    };
    for (const s of SYSTEMS) {
      for (const b of s.bodies) {
        const r = spherexReliability(b, s).value;
        if (b.kind === 'star' || b.kind === 'brown_dwarf') expect(r, b.id).toBe(expected[b.id]);
        else expect(r, b.id).toBe('not modelled');
      }
    }
  });
});

describe('input tiers from Facts', () => {
  type Row = Partial<Record<'teff' | 'radius' | 'mass' | 'semiMajorAxis', Tier>>;
  // Explicit expected tiers for every demo body (a new body must be added here).
  const EXPECTED: Record<string, Row> = {
    'barnards-star': { teff: 'measured', radius: 'measured', mass: 'measured' },
    'barnard-d': { radius: 'model', mass: 'measured', semiMajorAxis: 'measured' },
    'barnard-b': { radius: 'model', mass: 'measured', semiMajorAxis: 'measured' },
    'barnard-c': { radius: 'model', mass: 'measured', semiMajorAxis: 'measured' },
    'barnard-e': { radius: 'model', mass: 'measured', semiMajorAxis: 'measured' },
    sun: { teff: 'illustrative', radius: 'illustrative', mass: 'illustrative' },
    earth: { radius: 'illustrative', semiMajorAxis: 'illustrative' },
    jupiter: { radius: 'illustrative', semiMajorAxis: 'illustrative' },
    neptune: { radius: 'illustrative', semiMajorAxis: 'illustrative' },
    'syn-2026-aa': { radius: 'illustrative', semiMajorAxis: 'illustrative' },
    'syn-tno-1': { radius: 'illustrative', semiMajorAxis: 'illustrative' },
    'eps-indi-a': { teff: 'measured', radius: 'measured', mass: 'measured' },
    'eps-indi-ab': { teff: 'measured', radius: 'model', mass: 'measured', semiMajorAxis: 'measured' },
    'eps-indi-ba': { teff: 'measured', radius: 'illustrative', mass: 'measured', semiMajorAxis: 'illustrative' },
    'eps-indi-bb': { teff: 'measured', radius: 'illustrative', mass: 'measured', semiMajorAxis: 'measured' },
    'wise-0855': { teff: 'model', radius: 'model', mass: 'range-pick' },
    'r-draconis': { teff: 'range-pick', radius: 'illustrative', mass: 'illustrative' },
    'rw-aur-a': { teff: 'measured', radius: 'illustrative', mass: 'measured' },
    'rw-aur-a-disk': { radius: 'measured' },
    'rw-aur-b': { teff: 'range-pick', radius: 'measured', mass: 'measured', semiMajorAxis: 'illustrative' },
  };

  it('matches the expected table for every demo body', () => {
    let n = 0;
    for (const s of SYSTEMS) {
      for (const b of s.bodies) {
        const row = EXPECTED[b.id];
        expect(row, `add ${b.id} to the expected-tier table`).toBeDefined();
        for (const [param, tier] of Object.entries(row) as [keyof Row, Tier][]) {
          const t = paramTier(b, param);
          expect(t.tier, `${b.id} ${param}: ${t.method}`).toBe(tier);
          n++;
        }
      }
    }
    expect(n).toBeGreaterThan(40);
  });

  it('flags minimum masses and keeps the mass class a lower bound', () => {
    const p = bodyIn('barnards-star', 'barnard-b');
    expect(paramTier(p, 'mass').flags).toContain('lower-bound');
    const mc = massClass(p);
    expect(mc.value).toBe('Terran');
    expect(mc.flags).toContain('lower-bound');
    expect(surfaceGravity(p).flags).toContain('lower-bound');
  });

  it('weakens a verified Fact that does not match the drawn value, or whose unit is unknown', () => {
    const fact = (value: string, unit: string | null): Fact => ({ label: 'Temperature', value, unit, source: 'x', verified: true });
    expect(paramTier({ ...barnard, facts: [fact('3195 ± 28', 'K')] }, 'teff').tier).toBe('measured');
    expect(paramTier({ ...barnard, facts: [fact('2800', 'K')] }, 'teff').tier).toBe('illustrative');
    expect(paramTier({ ...barnard, facts: [fact('3195', 'furlongs')] }, 'teff').tier).toBe('illustrative');
    expect(paramTier({ ...barnard, facts: [fact('3000–3400', 'K')] }, 'teff').tier).toBe('range-pick');
    expect(paramTier({ ...barnard, facts: [] }, 'teff').tier).toBe('illustrative');
  });

  it('reads the system distance from Distance Facts', () => {
    expect(distanceTier(BARNARD).tier).toBe('measured');
    expect(distanceTier(RDRA).tier).toBe('measured'); // ~790 pc vs 792 pc
    expect(distanceTier(RWAUR).tier).toBe('illustrative'); // no Distance Fact in the catalog
    expect(distanceTier(DEMO).value).toBeNull();
  });

  it('propagates tiers into derived values', () => {
    expect(luminosity(barnard).tier).toBe('derived');
    expect(surfaceGravity(barnard).tier).toBe('derived');
    expect(pressureScaleHeight(barnard).tier).toBe('model'); // mu = 1.3 is assumed
    expect(luminosity(bodyIn('rw-aurigae', 'rw-aur-b')).tier).toBe('range-pick');
    expect(angularDiameterMas(barnard, BARNARD).tier).toBe('derived');
    expect(spherexPrediction(barnard, BARNARD).tier).toBe('model');
  });
});

describe('classifiers', () => {
  const typed = (spectral_type: string): Body => ({ ...barnard, spectral_type, facts: [] });

  it('parses MK-style spectral types', () => {
    const giant = spectralClass(typed('M5e–M9eIII')).value!;
    expect([giant.letter, giant.subtype, giant.subtypeMax, giant.luminosityClass, giant.stage]).toEqual(['M', 5, 9, 'III', 'giant']);
    expect(giant.peculiarities).toEqual(['e']);
    const tt = spectralClass(typed('K1–K4 (T Tauri)')).value!;
    expect([tt.letter, tt.subtype, tt.subtypeMax, tt.stage]).toEqual(['K', 1, 4, 'pre-main-sequence']);
    const y = spectralClass(typed('Y4 (approx.)')).value!;
    expect([y.letter, y.subtype, y.approximate, y.stage]).toEqual(['Y', 4, true, 'brown dwarf']);
    const m = spectralClass(barnard);
    expect([m.value!.letter, m.value!.subtype, m.value!.stage]).toEqual(['M', 4, 'main-sequence']);
    expect(m.tier).toBe('derived'); // verified 'Spectral type' Fact
    expect(spectralClass(bodyIn('epsilon-indi', 'eps-indi-bb')).value!.stage).toBe('brown dwarf');
    expect(spectralClass(bodyIn('rw-aurigae', 'rw-aur-b')).value!.subtype).toBe(6.5);
    expect(spectralClass(typed('unknown')).value).toBeNull();
  });

  it('classifies masses after Chen & Kipping 2017', () => {
    expect(massClass(bodyIn('epsilon-indi', 'eps-indi-ab')).value).toBe('Jovian');
    expect(massClass(bodyIn('epsilon-indi', 'eps-indi-ba')).value).toBe('Jovian'); // brown dwarfs are Jovian here
    expect(massClass(bodyIn('wise-0855', 'wise-0855')).tier).toBe('range-pick');
    expect(massClass(barnard).value).toBe('Stellar');
    expect(massClass({ ...barnard, mass_kg: 5 * 5.972e24 }).value).toBe('Neptunian');
  });
});

describe('star shader inputs (M2, pure parts)', () => {
  const stars = SYSTEMS.flatMap((s) => s.bodies).filter((b) => b.kind === 'star' && (b.teff_k ?? 0) >= 2500);

  it('limb-darkening LUT: 16 x RGB, 1 at the centre, monotonic in mu, redder at the limb', () => {
    expect(stars.length).toBeGreaterThanOrEqual(5);
    for (const s of stars) {
      const lut = limbDarkeningLut(s.teff_k!).value;
      expect(lut).toHaveLength(48);
      for (let ch = 0; ch < 3; ch++) {
        expect(lut[15 * 3 + ch]).toBeCloseTo(1, 6);
        for (let i = 1; i < 16; i++) expect(lut[i * 3 + ch], `${s.id} ch${ch} i${i}`).toBeGreaterThan(lut[(i - 1) * 3 + ch]);
      }
      const [r, g, b] = [lut[0], lut[1], lut[2]];
      expect(r, s.id).toBeGreaterThan(g);
      expect(g, s.id).toBeGreaterThan(b);
    }
  });

  it('the grey model gives I(0)/I(1) about 0.33 for the Sun at 550 nm', () => {
    expect(Math.abs(limbDarkeningAt(5772, 550, 0).value - 0.33)).toBeLessThan(0.01);
    expect(limbDarkeningAt(5772, 550, 1).value).toBeCloseTo(1, 12);
  });

  it('granulation: dwarfs are smooth, only R Dra could be drawn', () => {
    expect(rel(num(granulationParams(SUN)), 1040)).toBeLessThan(0.01);
    expect(rel(num(granulationParams(epsA)), 1440)).toBeLessThan(0.02);
    for (const s of SYSTEMS) {
      for (const b of s.bodies) {
        const g = granulationParams(b);
        // R Dra is drawn once the catalog gives it a mass (M2); every other body stays smooth.
        expect(g.draw, b.id).toBe(b.id === 'r-draconis' && b.mass_kg !== null);
      }
    }
    expect(granulationParams(barnard).seed).toBe(granulationParams(barnard).seed);
    expect(granulationParams(barnard).seed).not.toBe(granulationParams(epsA).seed);
  });
});

describe('geometry', () => {
  it('separation bounds are [0, a(1+e)/d] arcsec', () => {
    const ab = bodyIn('epsilon-indi', 'eps-indi-ab');
    const [lo, hi] = separationBoundsArcsec(ab, EPS).value!;
    expect(lo).toBe(0);
    expect(hi).toBeCloseTo((15.76 * 1.25) / 3.638, 9);
    expect(separationBoundsArcsec(bodyIn('epsilon-indi', 'eps-indi-ba'), EPS).flags).toContain('assumed-orbit');
  });
});

describe('SPHEREx bands', () => {
  it('has the six RECON §2.2 detectors and the 6.15 arcsec pixel', () => {
    expect(SPHEREX_PIXEL_ARCSEC).toBe(6.15);
    expect(SPHEREX_DETECTORS.map((d) => [d.id, d.lambdaMinUm, d.lambdaMaxUm])).toEqual([
      ['D1', 0.746, 1.117],
      ['D2', 1.103, 1.65],
      ['D3', 1.63, 2.435],
      ['D4', 2.403, 3.847],
      ['D5', 3.811, 4.43],
      ['D6', 4.412, 5.01],
    ]);
    for (const d of SPHEREX_DETECTORS) {
      expect(d.channelCentersUm).toHaveLength(SPHEREX_CHANNELS_PER_DETECTOR);
      expect(d.channelCentersUm[0]).toBeGreaterThan(d.lambdaMinUm);
      expect(d.channelCentersUm[16]).toBeLessThan(d.lambdaMaxUm);
    }
  });

  it('log-uniform channels reproduce the published D1 centres within 0.4 % (an eighth of a channel)', () => {
    SPHEREX_DETECTORS[0].channelCentersUm.forEach((c, i) =>
      expect(rel(c, SPHEREX_D1_PUBLISHED_CENTERS_UM[i]), `channel ${i}`).toBeLessThan(0.004),
    );
  });
});

describe('every demo body', () => {
  function walk(x: unknown, path: string, out: string[]) {
    if (x === undefined) out.push(`${path} is undefined`);
    else if (typeof x === 'number' && !Number.isFinite(x)) out.push(`${path} = ${x}`);
    else if (x instanceof Float32Array) x.forEach((v, i) => walk(v, `${path}[${i}]`, out));
    else if (x && typeof x === 'object') {
      const o = x as Record<string, unknown>;
      if ('tier' in o && 'method' in o) {
        if (!TIERS.includes(o.tier as Tier)) out.push(`${path}.tier = ${String(o.tier)}`);
        if (typeof o.method !== 'string' || !o.method) out.push(`${path}.method empty`);
        if (typeof o.citation !== 'string' || !o.citation) out.push(`${path}.citation empty`);
        if (!Array.isArray(o.flags)) out.push(`${path}.flags missing`);
      }
      for (const [k, v] of Object.entries(o)) if (k !== 'fact' && k !== 'detector') walk(v, `${path}.${k}`, out);
    }
  }

  it('derives every quantity without NaN or undefined, each with a tier, method and citation', () => {
    let bodies = 0;
    for (const s of SYSTEMS) {
      for (const b of s.bodies) {
        const problems: string[] = [];
        walk(deriveBody(b, s), `${s.id}/${b.id}`, problems);
        expect(problems, b.id).toEqual([]);
        bodies++;
      }
    }
    expect(bodies).toBeGreaterThanOrEqual(20);
  });
});

describe('bundle boundary', () => {
  it('astro.ts and its data modules never import three.js (BodyPanel is in the main chunk)', () => {
    for (const [name, src] of [
      ['astro.ts', astroSource],
      ['cie1931.ts', cieSource],
      ['spherexBands.ts', bandsSource],
    ] as const) {
      expect(src, name).not.toMatch(/from\s+['"]three(\/|['"])/);
      expect(src, name).not.toMatch(/import\(\s*['"]three/);
      const imports = [...src.matchAll(/^\s*(?:import|export)\b[^;]*?\bfrom\s+['"]([^'"]+)['"]/gm)].map((m) => m[1]);
      expect(imports.length, name).toBe(name === 'astro.ts' ? 3 : 0);
      for (const i of imports) expect(['../api/types', './cie1931', './spherexBands'], `${name} imports ${i}`).toContain(i);
    }
  });
});
