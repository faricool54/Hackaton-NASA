import { describe, expect, it } from 'vitest';
import type { Body, SystemModel } from '../api/types';
import {
  ARC_ALPHA,
  ARC_HALF_WIDTH_SIGMA,
  ARC_Z,
  CLOUD_POINTS,
  CONJUNCTION_MEAN_ANOMALY_DEG,
  formatTimingDays,
  isLineOfSightOrbit,
  jdToMjd,
  MIRA_EPHEMERIDES,
  minimumPhase,
  miraEphemerisFor,
  miraPhase,
  miraShape,
  miraState,
  miraTimingSigmaDays,
  normalQuantile,
  onThisDate,
  ORBIT_EPHEMERIDES,
  orbitEphemerisFor,
  passPhaseSummary,
  phaseCloud,
  phaseSigmaDeg,
  phaseUnknownLabel,
  predictedMaxima,
  predictedPulsation,
  RING_MEAN_ANOMALIES,
  RING_SIGMA_CYCLES,
  UNCERTAINTY_COLOR,
  undatedOrbitTitle,
  UNKNOWN_PHASE_REASONS,
  variabilityPhase,
  variabilityTracks,
  type OrbitEphemeris,
} from './ephemerides';
import { DR1_START_MJD, QR3_LAST_MJD, isoDateToMjd, mjdToIsoDate } from './spherexCoverage';
import { orbitalPosition } from './orbits';
import { ORBIT_COLOR } from './sceneLayout';

const SYSTEMS = Object.values(
  import.meta.glob<SystemModel>('../../../data/demo/systems/*.json', { eager: true, import: 'default' }),
);
const system = (id: string): SystemModel => {
  const s = SYSTEMS.find((x) => x.id === id);
  if (!s) throw new Error(`demo system ${id} missing`);
  return s;
};
const bodyOf = (sid: string, bid: string): Body => {
  const b = system(sid).bodies.find((x) => x.id === bid);
  if (!b) throw new Error(`${sid}/${bid} missing`);
  return b;
};
const eph = (bid: string): OrbitEphemeris => {
  const e = orbitEphemerisFor('barnards-star', bid);
  if (!e) throw new Error(`no ephemeris for ${bid}`);
  return e;
};
const RDRA = miraEphemerisFor('r-draconis', 'r-draconis')!;

describe('orbit ephemerides (M5)', () => {
  it('agree with the catalog orbits shipped in data/demo (Basant et al. 2025, Table 3)', () => {
    expect(ORBIT_EPHEMERIDES.map((e) => e.bodyId).sort()).toEqual(['barnard-b', 'barnard-c', 'barnard-d', 'barnard-e']);
    for (const e of ORBIT_EPHEMERIDES) {
      const o = bodyOf(e.systemId, e.bodyId).orbit!;
      expect(o.epoch_mjd).not.toBeNull();
      expect(o.epoch_mjd!).toBeCloseTo(jdToMjd(e.t0Bjd), 6);
      expect(o.period_days).toBe(e.periodDays);
      expect(o.mean_anomaly_deg).toBe(CONJUNCTION_MEAN_ANOMALY_DEG);
      expect(isLineOfSightOrbit(o)).toBe(true);
      // The orbit note quotes the same spread the scene draws (DR1 start and QR3 end).
      for (const mjd of [DR1_START_MJD, QR3_LAST_MJD]) {
        expect(o.note, e.bodyId).toContain(`±${Math.round(phaseSigmaDeg(e, mjd))}° on ${mjdToIsoDate(mjd)}`);
      }
    }
    expect(jdToMjd(2460243.38)).toBeCloseTo(60242.88, 9);
  });

  it('reproduces the judge-recomputed phase spread of Barnard b (13.0° → 18.6°)', () => {
    expect(phaseSigmaDeg(eph('barnard-b'), DR1_START_MJD)).toBeCloseTo(13.0, 1);
    expect(phaseSigmaDeg(eph('barnard-b'), QR3_LAST_MJD)).toBeCloseTo(18.6, 0);
    expect(Math.abs(phaseSigmaDeg(eph('barnard-b'), QR3_LAST_MJD) - 18.6)).toBeLessThan(0.1);
    // Arcs widen across the dataset, and e (largest t0 error) is the least well pinned down.
    for (const e of ORBIT_EPHEMERIDES) expect(phaseSigmaDeg(e, QR3_LAST_MJD)).toBeGreaterThan(phaseSigmaDeg(e, DR1_START_MJD));
    expect(phaseSigmaDeg(eph('barnard-e'), DR1_START_MJD)).toBeGreaterThan(phaseSigmaDeg(eph('barnard-b'), QR3_LAST_MJD));
    // At t0 the spread is the t0 error alone.
    const b = eph('barnard-b');
    expect(phaseSigmaDeg(b, jdToMjd(b.t0Bjd))).toBeCloseTo((360 * 0.09) / 3.1542, 9);
  });

  it('puts a planet in front of the star at its epoch: AU (0, −a, 0) = scene +z', () => {
    const o = bodyOf('barnards-star', 'barnard-b').orbit!;
    const p = orbitalPosition(o, o.epoch_mjd!);
    expect(p[0]).toBeCloseTo(0, 12);
    expect(p[1]).toBeCloseTo(-o.semi_major_axis_au, 12);
    expect(p[2]).toBeCloseTo(0, 12);
    // Scene mapping (x, y, z) → (x, z, −y): scene z = −y = +a, toward the default camera.
    expect(-p[1]).toBeGreaterThan(0);
    const line = onThisDate(system('barnards-star'), o.epoch_mjd!).find((l) => l.bodyId === 'barnard-b')!;
    expect(line.kind).toBe('dated');
    expect(line.text).toMatch(/^orbital phase 0\.00 ± 0\.03 \(±10°, 1σ\) after inferior conjunction/);
  });
});

describe('phase clouds (S2)', () => {
  it('uses 64 fixed, symmetric standard-normal quantiles inside ±2σ', () => {
    expect(ARC_Z).toHaveLength(CLOUD_POINTS);
    for (let k = 0; k < CLOUD_POINTS; k++) {
      expect(ARC_Z[k]).toBe(-ARC_Z[CLOUD_POINTS - 1 - k]);
      if (k > 0) expect(ARC_Z[k]).toBeGreaterThan(ARC_Z[k - 1]);
      expect(Math.abs(ARC_Z[k])).toBeLessThan(ARC_HALF_WIDTH_SIGMA);
    }
    expect(ARC_Z[0]).toBeLessThan(-1.8); // the ends reach near ±2σ
    expect(Math.max(...ARC_ALPHA)).toBeLessThanOrEqual(1);
    expect(ARC_ALPHA[0]).toBeLessThan(ARC_ALPHA[CLOUD_POINTS / 2]);
    expect(normalQuantile(0.975)).toBeCloseTo(1.959964, 5);
    expect(normalQuantile(0.8413447460685429)).toBeCloseTo(1, 6);
    expect(normalQuantile(0.01)).toBeCloseTo(-2.326348, 5);
    expect(normalQuantile(0.5)).toBe(0);
  });

  it('draws an arc that is stable between frames and centred on the predicted position', () => {
    const o = bodyOf('barnards-star', 'barnard-e').orbit!;
    const a = phaseCloud(o, eph('barnard-e'), 61000, 1.234);
    const b = phaseCloud(o, eph('barnard-e'), 61000, 1.234);
    expect(a).toEqual(b);
    if (!a || a.kind !== 'arc') throw new Error('expected an arc');
    const mid = (a.meanAnomalies[31] + a.meanAnomalies[32]) / 2;
    expect(mid).toBeCloseTo(1.234, 12);
    expect(a.sigmaCycles).toBeLessThan(RING_SIGMA_CYCLES);
  });

  it('switches to a ring with no epoch or when σ exceeds 0.5 cycle', () => {
    const ab = bodyOf('epsilon-indi', 'eps-indi-ab').orbit!;
    expect(phaseCloud(ab, null, 61000, 0)).toMatchObject({ kind: 'ring', reason: 'no-epoch' });
    const o = bodyOf('barnards-star', 'barnard-b').orbit!;
    const sloppy: OrbitEphemeris = { ...eph('barnard-b'), periodErrDays: 0.05 };
    const far = phaseCloud(o, sloppy, 61318, 0);
    expect(far).toMatchObject({ kind: 'ring', reason: 'too-uncertain' });
    expect(phaseCloud(o, null, 61318, 0)).toBeNull(); // dated but no tabulated σ: nothing claimed
    expect(RING_MEAN_ANOMALIES).toHaveLength(CLOUD_POINTS);
    expect(RING_MEAN_ANOMALIES[1] - RING_MEAN_ANOMALIES[0]).toBeCloseTo((2 * Math.PI) / CLOUD_POINTS, 12);
  });

  it('colours the clouds from the orbit legend colours (lightened)', () => {
    for (const q of ['fitted', 'assumed', 'hypothetical'] as const) {
      expect(UNCERTAINTY_COLOR[q]).toMatch(/^#[0-9a-f]{6}$/);
      expect(UNCERTAINTY_COLOR[q]).not.toBe(ORBIT_COLOR[q]);
    }
  });

  it('explains every arbitrary orbit of the real targets, with a source', () => {
    for (const key of Object.keys(UNKNOWN_PHASE_REASONS)) {
      const [sid, bid] = key.split('/');
      expect(bodyOf(sid, bid).orbit?.epoch_mjd).toBeNull();
    }
    const eps = onThisDate(system('epsilon-indi'), 61000);
    expect(eps.map((l) => l.kind)).toEqual(['arbitrary', 'arbitrary', 'arbitrary']);
    expect(eps.find((l) => l.bodyId === 'eps-indi-ba')!.text).toMatch(/assumed orbit, not fitted/);
    expect(eps.every((l) => l.source)).toBe(true);
  });

  it('says a ring on an assumed or hypothetical orbit is not where the body could be', () => {
    expect(undatedOrbitTitle('fitted')).toMatch(/ring shows where it could be/);
    for (const q of ['assumed', 'hypothetical'] as const) {
      const t = undatedOrbitTitle(q);
      expect(t).toMatch(/neither the orbit nor the phase is known/);
      expect(t).not.toMatch(/shows where it could be/);
    }
    expect(undatedOrbitTitle('assumed')).toMatch(/^Ring on an assumed orbit/);
    expect(undatedOrbitTitle('hypothetical')).toMatch(/^Ring on a hypothetical orbit/);
    // Eps Ind Ba's orbit is assumed (never fitted): that is the case the ring wording must not overstate.
    expect(bodyOf('epsilon-indi', 'eps-indi-ba').orbit?.quality).toBe('assumed');
  });
});

describe('Mira ephemeris of R Dra (S3)', () => {
  it('matches the VSX values and the judge fixtures', () => {
    expect(MIRA_EPHEMERIDES).toHaveLength(1);
    expect(RDRA.epochHjd).toBe(2457370.0);
    expect(RDRA.periodDays).toBe(246.12);
    expect(miraPhase(RDRA, DR1_START_MJD)).toBeCloseTo(0.897, 3);
    expect(miraPhase(RDRA, QR3_LAST_MJD)).toBeCloseTo(0.043, 3);
    // ε not sourced: the O−C band alone. Centre = VSX dates (not shifted), so 1σ = RMS of O−C about VSX.
    expect(RDRA.ocMeanDays).toBe(-4.7);
    expect(RDRA.ocSdDays).toBe(4.6);
    expect(miraTimingSigmaDays(RDRA, 61000)).toBeCloseTo(Math.sqrt(4.7 ** 2 + 4.6 ** 2), 12);
    expect(miraTimingSigmaDays(RDRA, 61000)).toBe(Math.hypot(RDRA.ocMeanDays, RDRA.ocSdDays));
    expect(formatTimingDays(miraTimingSigmaDays(RDRA, 61000))).toBe('6.6');
    // The band covers the mean offset: an observed maximum 4.7 d early is within 1σ.
    expect(Math.abs(RDRA.ocMeanDays)).toBeLessThan(miraTimingSigmaDays(RDRA, 61000));
    expect(RDRA.note).toMatch(/±6\.6 d band \(1σ\) is the RMS of the O−C about VSX/);
    expect(RDRA.note).toMatch(/not shifted/);
    expect(RDRA.timingSource).toMatch(/√\(4\.7² \+ 4\.6²\) ≈ 6\.6 d/);
  });

  it('predicts the 2025–2026 maxima of research item 3b', () => {
    const maxima = predictedMaxima(RDRA, DR1_START_MJD, QR3_LAST_MJD).map(mjdToIsoDate);
    expect(maxima).toEqual(['2025-05-20', '2026-01-21', '2026-09-24']);
    const p = miraPhase(RDRA, isoDateToMjd('2025-05-20') + 0.18);
    expect(Math.min(p, 1 - p)).toBeLessThan(0.001);
  });

  it('draws an asymmetric curve: maximum at 0, minimum at 1 − rise = 0.55, continuous', () => {
    expect(minimumPhase(RDRA)).toBeCloseTo(0.55, 12);
    expect(miraShape(RDRA, 0)).toBeCloseTo(1, 12);
    expect(miraShape(RDRA, 0.55)).toBeCloseTo(-1, 12);
    expect(miraShape(RDRA, 0.55 - 1e-9)).toBeCloseTo(-1, 6);
    expect(miraShape(RDRA, 1 - 1e-9)).toBeCloseTo(1, 6);
    for (let p = 0; p < 1; p += 0.01) expect(Math.abs(miraShape(RDRA, p))).toBeLessThanOrEqual(1 + 1e-12);
    expect(miraState(RDRA, 0.95)).toBe('rising, near maximum');
    expect(miraState(RDRA, 0.03)).toBe('just past maximum');
    expect(miraState(RDRA, 0.5)).toBe('near minimum');
    expect(miraState(RDRA, 0.3)).toBe('declining');
    expect(miraState(RDRA, 0.75)).toBe('rising');
  });

  it("spans the catalog's V range and the class-typical ±10 % radius", () => {
    const rdra = bodyOf('r-draconis', 'r-draconis');
    const atMax = predictedPulsation(RDRA, rdra, isoDateToMjd('2026-01-21') + 0.3);
    const atMin = predictedPulsation(RDRA, rdra, isoDateToMjd('2026-01-21') + 0.3 + 0.55 * 246.12);
    expect(atMax.factor / atMin.factor).toBeCloseTo(Math.pow(10, 0.4 * 6.5), 0);
    expect(atMax.radiusScale).toBeCloseTo(1.1, 3);
    expect(atMin.radiusScale).toBeCloseTo(0.9, 3);
  });

  it('summarises the predicted phase of each SPHEREx pass', () => {
    expect(passPhaseSummary(RDRA, 60790, 60879)).toBe(
      'predicted V phase 0.90 → 0.26 (±0.03); predicted maximum 2025-05-20 ± 6.6 d',
    );
    expect(passPhaseSummary(RDRA, 60916, 61310)).toBe(
      'predicted V phase 0.41 → 0.01 (±0.03); 1.6 cycles; predicted maxima 2026-01-21 ± 6.6 d, 2026-09-24 ± 6.6 d',
    );
  });

  it('never gives irregular variables a curve, and freezes periodic ones without an ephemeris', () => {
    expect(variabilityTracks(system('rw-aurigae')).map((t) => t.kind)).toEqual(['irregular', 'irregular']);
    expect(variabilityTracks(system('r-draconis')).map((t) => t.kind)).toEqual(['predicted']);
    const other = { ...system('r-draconis'), id: 'not-in-the-table' };
    expect(variabilityTracks(other).map((t) => t.kind)).toEqual(['unknown']);
    const rw = onThisDate(system('rw-aurigae'), 61000);
    expect(rw.filter((l) => l.kind === 'irregular').map((l) => l.bodyId)).toEqual(['rw-aur-a', 'rw-aur-b']);
    expect(rw.find((l) => l.bodyId === 'rw-aur-b' && l.kind === 'arbitrary')?.source).toMatch(/Kurtovic/);
    const line = onThisDate(system('r-draconis'), DR1_START_MJD)[0];
    expect(line.text).toBe(
      'predicted V phase 0.90 ± 0.03 (VSX ephemeris, ±6.6 d 1σ timing band about the VSX dates) · rising · next predicted maximum 2025-05-20',
    );
  });

  it('classifies variability with one rule: only kind "irregular" is irregular', () => {
    const rdra = bodyOf('r-draconis', 'r-draconis');
    const withVar = (kind: 'pulsation' | 'rotation' | 'eclipse' | 'accretion' | 'irregular', period: number | null): Body => ({
      ...rdra,
      variability: { kind, period_days: period, amplitude_mag: 1, band: 'V' },
    });
    expect(variabilityPhase('r-draconis', rdra)).toBe('predicted');
    expect(variabilityPhase('not-in-the-table', rdra)).toBe('unknown');
    expect(variabilityPhase('r-draconis', { ...rdra, variability: null })).toBeNull();
    // No period but not irregular: unknown (frozen), never "irregular".
    for (const kind of ['pulsation', 'rotation', 'eclipse', 'accretion'] as const) {
      expect(variabilityPhase('r-draconis', withVar(kind, null)), kind).toBe('unknown');
    }
    // Irregular even with a period.
    expect(variabilityPhase('r-draconis', withVar('irregular', 100))).toBe('irregular');
    const sys = { id: 'x', bodies: [withVar('rotation', null), withVar('irregular', null)].map((b, i) => ({ ...b, id: `b${i}` })) };
    expect(variabilityTracks(sys).map((t) => t.kind)).toEqual(['unknown', 'irregular']);
    const lines = onThisDate(sys, 61000);
    expect(lines.map((l) => l.kind)).toEqual(['frozen', 'irregular']);
    expect(lines[0].text).toBe('variability phase unknown: drawn at mean brightness');
    expect(phaseUnknownLabel('pulsation')).toBe('pulsation phase unknown');
    expect(phaseUnknownLabel(['pulsation', 'rotation'])).toBe('variability phase unknown');
    expect(phaseUnknownLabel([])).toBe('variability phase unknown');
  });
});
