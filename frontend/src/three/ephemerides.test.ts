import { describe, expect, it } from 'vitest';
import type { Body, SystemModel } from '../api/types';
import {
  ARC_ALPHA,
  ARC_HALF_WIDTH_SIGMA,
  ARC_Z,
  CLOUD_POINTS,
  CONJUNCTION_MEAN_ANOMALY_DEG,
  formatTimingDays,
  IRREGULAR_TEXT,
  irregularText,
  isLineOfSightOrbit,
  jdToMjd,
  maximumText,
  MIRA_EPHEMERIDES,
  MIRA_PREDICTION_CAVEAT,
  minimumPhase,
  miraCycle,
  miraDatedByMaxima,
  miraEphemerisFor,
  miraMaxima,
  miraPhase,
  miraPhaseSigma,
  miraShape,
  miraState,
  miraTimingSigmaDays,
  nextMaximum,
  nextMiraMaximum,
  normalQuantile,
  OBSERVED_WINDOW_ROUNDING_DAYS,
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
import { DR1_START_MJD, PASS_EDGE_TOLERANCE_DAYS, QR3_LAST_MJD, SPHEREX_COVERAGE, isoDateToMjd, mjdToIsoDate } from './spherexCoverage';
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
/** Phase of the VSX ephemeris alone, frac((t − E0)/P), whatever the dating inside the SPHEREx window. */
const vsxPhase = (mjd: number): number => {
  const c = miraCycle(RDRA, mjd);
  return c - Math.floor(c);
};

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
    // The VSX phase itself (judge fixtures); inside the SPHEREx window the drawn phase uses the measured maxima.
    expect(vsxPhase(DR1_START_MJD)).toBeCloseTo(0.897, 3);
    expect(miraPhase(RDRA, QR3_LAST_MJD)).toBeCloseTo(0.043, 3); // 2026-10-05: after the window, VSX
    // ε not sourced: the O−C band alone. Centre = VSX dates (not shifted), so 1σ = RMS of O−C about VSX:
    // the 2025–2026 AAVSO maxima came −3.8, −14.8 and −3.1 d from VSX (SCIENCE.md 3D review V12a).
    expect(RDRA.ocMeanDays).toBe(-4.7);
    expect(RDRA.ocSdDays).toBe(4.6);
    const oc = [-3.8, -14.8, -3.1];
    expect(Math.sqrt(oc.reduce((s, x) => s + x * x, 0) / oc.length)).toBeCloseTo(9.0, 1);
    const outside = 61400; // after the SPHEREx window: the VSX band
    expect(miraDatedByMaxima(RDRA, outside)).toBe(false);
    expect(miraTimingSigmaDays(RDRA, outside)).toBe(9.0);
    expect(formatTimingDays(miraTimingSigmaDays(RDRA, outside))).toBe('9.0');
    // The band covers the earlier mean offset too: a maximum 4.7 d early is within 1σ.
    expect(Math.abs(RDRA.ocMeanDays)).toBeLessThan(miraTimingSigmaDays(RDRA, outside));
    expect(RDRA.note).toMatch(/±9\.0 d band \(1σ\) is the RMS of that O−C about VSX/);
    expect(RDRA.note).toMatch(/not shifted/);
    expect(RDRA.note).toMatch(/the radius is drawn constant/);
    expect(RDRA.timingSource).toBe(
      'RMS of the O−C of the 2025–2026 AAVSO maxima about VSX: −3.8, −14.8 and −3.1 d (offline WS3 analysis, docs/validation/r-draconis.md)',
    );
  });

  it('V12a: dates the phase with the measured AAVSO maxima inside the SPHEREx window', () => {
    expect(RDRA.observedMaximaMjd).toEqual([60811.4, 61046.5, 61304.3]);
    expect(RDRA.observedMaximaSource).toBe(
      'AAVSO International Database, 818 visual and V observations, JD 2460700–2461360; maxima from ±40 d parabolas (offline WS3 analysis, docs/validation/r-draconis.md)',
    );
    expect(RDRA.observedTimingDays).toBe(3);
    expect(RDRA.observedTimingSource).toMatch(/^SCIENCE\.md 3D review V12a: ±3 d about each measured maximum/);
    // The window is the SPHEREx archive window of R Dra, rounded to the day like the coverage table.
    const passes = SPHEREX_COVERAGE['r-draconis'].passes;
    expect(RDRA.observedWindowMjd).toEqual([passes[0].startMjd, passes[passes.length - 1].endMjd]);
    expect(OBSERVED_WINDOW_ROUNDING_DAYS).toBe(PASS_EDGE_TOLERANCE_DAYS);
    expect(miraDatedByMaxima(RDRA, DR1_START_MJD)).toBe(true); // the dataset clock starts inside it
    expect(miraDatedByMaxima(RDRA, 60789.4)).toBe(false);
    expect(miraDatedByMaxima(RDRA, 61310.5)).toBe(true);
    expect(miraDatedByMaxima(RDRA, 61310.6)).toBe(false);
    // The measured maxima are phase 0, dated as 2025-05-16, 2026-01-06 and 2026-09-21 (SCIENCE.md V12a).
    const measured = RDRA.observedMaximaMjd ?? [];
    expect(measured.map(mjdToIsoDate)).toEqual(['2025-05-16', '2026-01-06', '2026-09-21']);
    for (const m of measured) {
      expect(miraPhase(RDRA, m)).toBeCloseTo(0, 12);
      expect(miraPhase(RDRA, m - 1e-6)).toBeCloseTo(1, 6); // continuous through each maximum
    }
    // O−C of the measured maxima about VSX: −3.8, −14.8 and −3.1 d.
    const vsx = predictedMaxima(RDRA, 60700, 61360);
    expect(measured.map((m, i) => Number((m - vsx[i]).toFixed(1)))).toEqual([-3.8, -14.8, -3.1]);
    // Linear phase between consecutive maxima (cycles of 235.1 and 257.8 d).
    expect(miraPhase(RDRA, 60811.4 + 0.5 * 235.1)).toBeCloseTo(0.5, 9);
    expect(miraPhase(RDRA, 61046.5 + 0.25 * 257.8)).toBeCloseTo(0.25, 9);
    // Before the first and after the last maximum (still inside the window): VSX period from the nearest one.
    expect(miraPhase(RDRA, DR1_START_MJD)).toBeCloseTo(1 - (60811.4 - DR1_START_MJD) / 246.12, 12);
    expect(miraPhase(RDRA, 61310)).toBeCloseTo((61310 - 61304.3) / 246.12, 12);
    // The drawn minima (phase 1 − rise = 0.55) fall inside the measured AAVSO minima: 60939–60947 and 61185–61196.
    const minima = [60811.4 + 0.55 * 235.1, 61046.5 + 0.55 * 257.8];
    expect(minima[0]).toBeGreaterThanOrEqual(60939);
    expect(minima[0]).toBeLessThanOrEqual(60947);
    expect(minima[1]).toBeGreaterThanOrEqual(61185);
    expect(minima[1]).toBeLessThanOrEqual(61196);
    for (const m of minima) expect(miraShape(RDRA, miraPhase(RDRA, m))).toBeCloseTo(-1, 9);
    // ±3 d band inside the window; the phase spread is the band over the local cycle length.
    expect(miraTimingSigmaDays(RDRA, 61000)).toBe(3);
    expect(miraPhaseSigma(RDRA, 61000)).toBeCloseTo(3 / 235.1, 12);
    expect(miraPhaseSigma(RDRA, 61200)).toBeCloseTo(3 / 257.8, 12);
    expect(miraPhaseSigma(RDRA, 61400)).toBeCloseTo(9 / 246.12, 12);
    // At the window edges the phase jumps by less than 0.02 cycles (5 d) between the two datings.
    for (const [inside, outside] of [
      [60789.5, 60789.49],
      [61310.5, 61310.51],
    ]) {
      const d = Math.abs(miraPhase(RDRA, inside) - miraPhase(RDRA, outside));
      expect(Math.min(d, 1 - d)).toBeLessThan(0.02);
    }
  });

  it('predicts the 2025–2026 maxima of research item 3b (VSX), and draws the measured ones instead', () => {
    const maxima = predictedMaxima(RDRA, DR1_START_MJD, QR3_LAST_MJD).map(mjdToIsoDate);
    expect(maxima).toEqual(['2025-05-20', '2026-01-21', '2026-09-24']);
    const p = vsxPhase(isoDateToMjd('2025-05-20') + 0.18);
    expect(Math.min(p, 1 - p)).toBeLessThan(0.001);
    // One maximum per cycle: inside the window the measured date replaces the VSX one.
    const drawn = miraMaxima(RDRA, DR1_START_MJD, QR3_LAST_MJD);
    expect(drawn.map((m) => [mjdToIsoDate(m.mjd), m.measured, m.sigmaDays])).toEqual([
      ['2025-05-16', true, 3],
      ['2026-01-06', true, 3],
      ['2026-09-21', true, 3],
    ]);
    // Outside the window: the VSX dates with the 9.0 d band.
    const wide = miraMaxima(RDRA, 60400, 61700);
    expect(wide.map((m) => [mjdToIsoDate(m.mjd), m.measured, m.sigmaDays])).toEqual([
      ['2024-09-16', false, 9],
      ['2025-05-16', true, 3],
      ['2026-01-06', true, 3],
      ['2026-09-21', true, 3],
      ['2027-05-28', false, 9],
    ]);
    expect(maximumText(wide[0])).toBe('predicted maximum 2024-09-16 ± 9.0 d');
    expect(maximumText(wide[1])).toBe('measured maximum 2025-05-16 ± 3.0 d');
    // Next maximum: the measured one inside the window; after the last, the next VSX cycle (2026-09-24 is the measured one).
    expect(nextMiraMaximum(RDRA, DR1_START_MJD)).toEqual({ mjd: 60811.4, measured: true, sigmaDays: 3 });
    expect(nextMaximum(RDRA, 61000)).toBe(61046.5);
    expect(mjdToIsoDate(nextMaximum(RDRA, 61305))).toBe('2027-05-28');
    expect(nextMiraMaximum(RDRA, 61305).measured).toBe(false);
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

  it("spans the catalog's V range on the glow only: no radius factor (the size change is not measured)", () => {
    const rdra = bodyOf('r-draconis', 'r-draconis');
    const atMax = predictedPulsation(RDRA, rdra, 61046.5); // measured maximum of 2026-01-06
    const atMin = predictedPulsation(RDRA, rdra, 61046.5 + 0.55 * 257.8);
    expect(atMax.factor / atMin.factor).toBeCloseTo(Math.pow(10, 0.4 * 6.5), 0);
    expect(Object.keys(atMax).sort()).toEqual(['factor', 'phase', 'phaseSigma', 'shape']);
    expect(MIRA_PREDICTION_CAVEAT).toMatch(/^V-band prediction from a catalogue ephemeris, not a SPHEREx light curve\. Measured offline/);
    expect(MIRA_PREDICTION_CAVEAT).not.toMatch(/\.$/); // callers end the sentence
  });

  it('summarises the phase of each SPHEREx pass', () => {
    expect(passPhaseSummary(RDRA, 60790, 60879)).toBe(
      'V phase 0.91 → 0.29 (±0.01, dated by the measured AAVSO maxima); measured maximum 2025-05-16 ± 3.0 d',
    );
    expect(passPhaseSummary(RDRA, 60916, 61310)).toBe(
      'V phase 0.44 → 0.02 (±0.01, dated by the measured AAVSO maxima); 1.6 cycles; measured maximum 2026-01-06 ± 3.0 d, measured maximum 2026-09-21 ± 3.0 d',
    );
    expect(passPhaseSummary(RDRA, 61320, 61400)).toBe('predicted V phase 0.05 → 0.38 (±0.04, VSX ephemeris); no maximum in this pass');
    expect(passPhaseSummary(RDRA, 61300, 61400)).toBe(
      'V phase 0.98 → 0.38 (±0.04, measured AAVSO maxima inside the SPHEREx window, VSX ephemeris outside); measured maximum 2026-09-21 ± 3.0 d',
    );
  });

  it('never gives irregular variables a curve, and freezes periodic ones without an ephemeris', () => {
    expect(variabilityTracks(system('rw-aurigae')).map((t) => t.kind)).toEqual(['irregular', 'irregular']);
    expect(variabilityTracks(system('r-draconis')).map((t) => t.kind)).toEqual(['predicted']);
    const other = { ...system('r-draconis'), id: 'not-in-the-table' };
    expect(variabilityTracks(other).map((t) => t.kind)).toEqual(['unknown']);
    const rw = onThisDate(system('rw-aurigae'), 61000);
    expect(rw.filter((l) => l.kind === 'irregular').map((l) => l.bodyId)).toEqual(['rw-aur-a', 'rw-aur-b']);
    // V12c: no "look at the frames"; RW Aur says what was measured offline and that image brightness is not a measurement.
    expect(IRREGULAR_TEXT).toBe('irregular: cannot be predicted');
    for (const l of rw.filter((x) => x.kind === 'irregular')) {
      expect(l.text).toBe(irregularText('rw-aurigae'));
      expect(l.text).toMatch(/^irregular: cannot be predicted\. Measured offline on unsaturated SPHEREx D1 exposures at matched wavelength, RW Aur \(A\+B\) was about 1 mag brighter/);
      expect(l.text).toMatch(/image brightness here is not a measurement\.$/);
      expect(l.text).not.toMatch(/look at the frames/);
    }
    expect(irregularText('some-other-system')).toBe(IRREGULAR_TEXT);
    expect(rw.find((l) => l.bodyId === 'rw-aur-b' && l.kind === 'arbitrary')?.source).toMatch(/Kurtovic/);
    const line = onThisDate(system('r-draconis'), DR1_START_MJD)[0];
    expect(line.text).toBe(
      'V phase 0.91 ± 0.01 (dated by the measured AAVSO maxima, ±3.0 d band about each) · rising, near maximum · next measured maximum 2025-05-16',
    );
    expect(line.source).toBe(`${RDRA.observedMaximaSource}; outside the SPHEREx window: ${RDRA.source}`);
    const after = onThisDate(system('r-draconis'), QR3_LAST_MJD)[0];
    expect(after.text).toBe(
      'predicted V phase 0.04 ± 0.04 (VSX ephemeris, ±9.0 d 1σ timing band about the VSX dates) · just past maximum · next predicted maximum 2027-05-28',
    );
    expect(after.source).toBe(RDRA.source);
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
