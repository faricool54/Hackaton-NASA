import { describe, expect, it } from 'vitest';
import type { Body, Field, SystemModel, VariabilityKind } from '../api/types';
import { formatMjd } from '../api/format';
import { hasDatasetWindow, SPHEREX_TARGET_IDS } from './datasetGate';
import { variabilityTracks } from './ephemerides';
import {
  ARCHIVE_SEASON_GAP_DAYS,
  betweenVisits,
  coverageFor,
  DATASET_PLAY_SECONDS,
  datasetBounds,
  datasetSpeed,
  datasetWindow,
  DATASET_TODAY_ISO,
  DATASET_TODAY_MJD,
  dateTicks,
  DR1_START_MJD,
  freeRunningArbitraryPhase,
  groupPasses,
  isSpherexTarget,
  isoDateToMjd,
  mjdToIsoDate,
  nearestPass,
  passAt,
  phaseStatus,
  phaseStatusLine,
  QR3_LAST_MJD,
  SPHEREX_COVERAGE,
  SPHEREX_COVERAGE_SOURCE,
  SPHEREX_PASSES,
  timelineDomain,
  VISIT_GAP_DAYS,
  type SpherexTargetId,
} from './spherexCoverage';

// Every demo system and field shipped with the site (the same JSON the pipeline writes).
const SYSTEMS = Object.values(
  import.meta.glob<SystemModel>('../../../data/demo/systems/*.json', { eager: true, import: 'default' }),
);
const FIELDS = Object.values(
  import.meta.glob<Field>('../../../data/demo/fields/*/field.json', { eager: true, import: 'default' }),
);
const system = (id: string): SystemModel => {
  const s = SYSTEMS.find((x) => x.id === id);
  if (!s) throw new Error(`demo system ${id} missing`);
  return s;
};
const field = (id: string): Field => {
  const f = FIELDS.find((x) => x.id === id);
  if (!f) throw new Error(`demo field ${id} missing`);
  return f;
};
const TARGETS = Object.keys(SPHEREX_COVERAGE) as SpherexTargetId[];

// Independent copy of the pass windows as given in the M4 work-package spec (from docs/DATA.md):
// [startMjd, endMjd, nImages].
const SPEC_PASSES: Record<SpherexTargetId, [number, number, number][]> = {
  'barnards-star': [[60903, 60949, 118], [61110, 61165, 121], [61269, 61306, 119]],
  'epsilon-indi': [[60790, 60836, 120], [60947, 60992, 147], [61149, 61164, 73], [61305, 61315, 120]],
  'wise-0855': [[60801, 60802, 30], [60980, 61022, 128], [61151, 61174, 100]],
  'rw-aurigae': [[60919, 60938, 112], [61092, 61111, 114], [61285, 61300, 109]],
  'r-draconis': [[60790, 60879, 240], [60916, 61310, 2253]],
};

/** Day [d, d+1) of an ISO date overlaps a window edge given to the day (+-0.5 d rounding). */
function dateMatchesRoundedMjd(iso: string, roundedMjd: number): boolean {
  const d = isoDateToMjd(iso);
  return d > roundedMjd - 1.5 && d < roundedMjd + 0.5;
}

describe('MJD <-> ISO dates', () => {
  it('matches independent references', () => {
    expect(isoDateToMjd('1858-11-17')).toBe(0); // MJD zero point
    expect(isoDateToMjd('1970-01-01')).toBe(40587); // Unix epoch
    expect(isoDateToMjd('2000-01-01T12:00:00Z')).toBe(51544.5); // J2000.0 (orbits.ts J2000_MJD)
    expect(isoDateToMjd(DATASET_TODAY_ISO)).toBe(61358);
    expect(DATASET_TODAY_MJD).toBe(61358);
  });

  it('reads the DR1 and QR3 limits quoted in RECON 2.1', () => {
    expect(mjdToIsoDate(DR1_START_MJD)).toBe('2025-04-24');
    expect(isoDateToMjd('2025-04-24T18:00:00Z')).toBe(DR1_START_MJD);
    expect(isoDateToMjd('2025-04-24T18:00:00')).toBe(DR1_START_MJD); // no zone = UTC, not local time
    expect(formatMjd(DR1_START_MJD)).toBe('2025-04-24 18:00 UTC'); // agrees with api/format
    expect(mjdToIsoDate(QR3_LAST_MJD)).toBe('2026-10-05');
    expect(mjdToIsoDate(61174.49)).toBe('2026-05-14'); // DR1 end
  });

  it('round-trips every calendar date of the coverage table', () => {
    const dates = TARGETS.flatMap((id) => {
      const c = SPHEREX_COVERAGE[id];
      return [
        ...c.dateRange,
        ...c.passes.flatMap((p) => [...(p.dates ?? []), ...(p.subVisits ?? []).flatMap((v) => v.dates)]),
      ];
    });
    expect(dates.length).toBeGreaterThan(30);
    for (const iso of dates) expect(mjdToIsoDate(isoDateToMjd(iso))).toBe(iso);
    for (let mjd = 60780; mjd < 61400; mjd += 0.25) expect(isoDateToMjd(mjdToIsoDate(mjd))).toBe(Math.floor(mjd));
  });

  it('rejects what is not a date', () => {
    expect(isoDateToMjd('not a date')).toBeNaN();
    expect(mjdToIsoDate(Number.NaN)).toBe('');
    expect(mjdToIsoDate(1e12)).toBe('');
  });
});

describe('SPHEREX_COVERAGE (IRSA DR1 + QR3, queried 2026-11-14)', () => {
  it('is keyed by the real demo systems, and covers all of them', () => {
    const ids = SYSTEMS.map((s) => s.id);
    for (const id of TARGETS) {
      expect(ids).toContain(id);
      expect(system(id).provenance.synthetic).toBe(false);
    }
    const real = SYSTEMS.filter((s) => !s.provenance.synthetic).map((s) => s.id);
    expect([...real].sort()).toEqual([...TARGETS].sort());
    expect(Object.keys(SPHEREX_PASSES).sort()).toEqual([...TARGETS].sort());
    expect(coverageFor('demo-ecliptic-orbits')).toBeNull();
    expect(coverageFor('toString')).toBeNull(); // no prototype keys
    // The tiny id list the viewer imports statically (main chunk) is the same set.
    expect([...SPHEREX_TARGET_IDS].sort()).toEqual([...TARGETS].sort());
    expect(isSpherexTarget('toString')).toBe(false);
  });

  it('matches the pass windows of the work-package spec', () => {
    for (const id of TARGETS) {
      expect(SPHEREX_PASSES[id].map((p) => [p.startMjd, p.endMjd, p.nImages])).toEqual(SPEC_PASSES[id]);
    }
  });

  it('has ordered windows inside the archive span, separated by more than 30 days', () => {
    for (const id of TARGETS) {
      const passes = SPHEREX_PASSES[id];
      passes.forEach((p, i) => {
        expect(p.startMjd).toBeLessThanOrEqual(p.endMjd);
        expect(p.startMjd).toBeGreaterThanOrEqual(DR1_START_MJD - 0.5);
        expect(p.endMjd).toBeLessThanOrEqual(QR3_LAST_MJD + 0.5);
        if (i > 0) expect(p.startMjd - passes[i - 1].endMjd).toBeGreaterThan(ARCHIVE_SEASON_GAP_DAYS);
      });
    }
  });

  it('agrees with the RECON 4.2 calendar dates to the day', () => {
    let checked = 0;
    for (const id of TARGETS) {
      const c = SPHEREX_COVERAGE[id];
      for (const p of c.passes) {
        if (!p.dates) continue;
        expect(dateMatchesRoundedMjd(p.dates[0], p.startMjd), `${id} start ${p.dates[0]}`).toBe(true);
        expect(dateMatchesRoundedMjd(p.dates[1], p.endMjd), `${id} end ${p.dates[1]}`).toBe(true);
        checked += 2;
      }
      // DATA.md "Fechas" = first and last date of the whole coverage.
      expect(dateMatchesRoundedMjd(c.dateRange[0], c.passes[0].startMjd)).toBe(true);
      expect(dateMatchesRoundedMjd(c.dateRange[1], c.passes[c.passes.length - 1].endMjd)).toBe(true);
    }
    expect(checked).toBe(2 * (3 + 4 + 3 + 3)); // R Dra: RECON gives months only
  });

  it('has image counts that add up across the tables', () => {
    for (const id of TARGETS) {
      const c = SPHEREX_COVERAGE[id];
      const byPass = c.passes.reduce((n, p) => n + p.nImages, 0);
      const byCollection = Object.values(c.imagesByCollection).reduce((n, k) => n + k, 0);
      const byDetector = c.imagesByDetector.reduce((n, k) => n + k, 0);
      expect(byPass, id).toBe(byCollection);
      // RECON's per-detector counts come from a slightly different query (Eps Ind: 458 vs 460).
      expect(Math.abs(byDetector - byPass), id).toBeLessThanOrEqual(2);
      for (const p of c.passes) {
        if (p.nImagesLongWave !== null) expect(p.nImagesLongWave).toBeLessThanOrEqual(p.nImages);
      }
    }
    expect(SPHEREX_COVERAGE['barnards-star'].imagesByDetector.reduce((n, k) => n + k, 0)).toBe(358);
    expect(SPHEREX_COVERAGE['r-draconis'].passes.reduce((n, p) => n + p.nImages, 0)).toBe(2493);
  });

  it('splits WISE 0855 pass 2 into two visits 27 days apart (RECON 4.2)', () => {
    const p = SPHEREX_PASSES['wise-0855'][1];
    const [nov, dec] = p.subVisits ?? [];
    expect(nov.nImages + dec.nImages).toBe(p.nImages);
    expect(nov.startMjd).toBe(p.startMjd);
    expect(dec.endMjd).toBe(p.endMjd);
    const gap = dec.startMjd - nov.endMjd;
    expect(gap).toBeGreaterThan(VISIT_GAP_DAYS);
    expect(gap).toBeLessThanOrEqual(ARCHIVE_SEASON_GAP_DAYS);
    for (const v of [nov, dec]) {
      expect(isoDateToMjd(v.dates[0])).toBeLessThanOrEqual(v.startMjd);
      expect(isoDateToMjd(v.dates[1]) + 1).toBeGreaterThanOrEqual(v.endMjd);
    }
  });

  it("matches R Draconis's monthly counts to its two passes", () => {
    const c = SPHEREX_COVERAGE['r-draconis'];
    const monthly = c.monthly ?? [];
    expect(monthly.map((m) => m.month)).toHaveLength(18); // 2025-04 ... 2026-09
    const sum = (from: string, to: string) =>
      monthly.filter((m) => m.month >= from && m.month <= to).reduce((n, m) => n + m.nImages, 0);
    expect(sum('2025-04', '2025-07')).toBe(c.passes[0].nImages);
    expect(sum('2025-08', '2026-09')).toBe(c.passes[1].nImages);
    expect(mjdToIsoDate(c.passes[0].endMjd).slice(0, 7)).toBe('2025-07');
    expect(mjdToIsoDate(c.passes[1].startMjd).slice(0, 7)).toBe('2025-08');
    expect(mjdToIsoDate(c.passes[1].endMjd).slice(0, 7)).toBe('2026-09');
  });

  it('records the detectors of the last Epsilon Indi pass', () => {
    expect(SPHEREX_PASSES['epsilon-indi'][3].detectors).toEqual([2, 3, 5, 6]);
    expect(SPHEREX_PASSES['epsilon-indi'].slice(0, 3).every((p) => p.detectors === null)).toBe(true);
  });
});

describe('groupPasses', () => {
  /** Evenly spaced times inside a window (a stand-in for frames when only the window is known). */
  const spread = (start: number, end: number, n: number) =>
    Array.from({ length: n }, (_, i) => start + ((end - start) * i) / Math.max(n - 1, 1));

  // WISE 0855 frame times placed inside the RECON 4.2 visit windows.
  const wise = SPHEREX_PASSES['wise-0855'];
  const wiseMjds = [
    ...spread(wise[0].startMjd, wise[0].endMjd, wise[0].nImages),
    ...(wise[1].subVisits ?? []).flatMap((v) => spread(v.startMjd, v.endMjd, v.nImages)),
    ...spread(wise[2].startMjd, wise[2].endMjd, wise[2].nImages),
  ].reverse(); // input order must not matter

  it('splits WISE 0855 at 10 days and merges it at 30 days', () => {
    expect(groupPasses(wiseMjds).map((g) => g.count)).toEqual([30, 110, 18, 100]);
    expect(groupPasses(wiseMjds, 10).length).toBe(4);
    const merged = groupPasses(wiseMjds, 30);
    expect(merged.map((g) => g.count)).toEqual(wise.map((p) => p.nImages));
    merged.forEach((g, i) => {
      expect(g.startMjd).toBeCloseTo(wise[i].startMjd, 6);
      expect(g.endMjd).toBeCloseTo(wise[i].endMjd, 6);
    });
  });

  it('returns input indices in time order and skips non-finite times', () => {
    const groups = groupPasses([61000, Number.NaN, 60000, 60001, 61003]);
    expect(groups).toEqual([
      { startMjd: 60000, endMjd: 60001, count: 2, indices: [2, 3] },
      { startMjd: 61000, endMjd: 61003, count: 2, indices: [0, 4] },
    ]);
    expect(groupPasses([])).toEqual([]);
  });

  it('splits only on gaps longer than gapDays', () => {
    expect(groupPasses([0, 10]).length).toBe(1);
    expect(groupPasses([0, 10.001]).length).toBe(2);
    expect(() => groupPasses([1], 0)).toThrow(RangeError);
    expect(() => groupPasses([1], Number.NaN)).toThrow(RangeError);
  });

  it('groups the demo fields frames', () => {
    expect(groupPasses(field('demo-ecliptic').frames.map((f) => f.mjd)).map((g) => g.count)).toEqual([6]);
    const nep = field('demo-nep-deep').frames.map((f) => f.mjd);
    expect(groupPasses(nep).map((g) => g.count)).toEqual([2, 2, 2, 2]);
    expect(groupPasses(nep, 100).length).toBe(1);
  });
});

describe('datasetWindow', () => {
  it('gives every real system its archive passes, hatched (no frames built)', () => {
    for (const id of TARGETS) {
      const w = datasetWindow(system(id));
      expect(w, id).not.toBeNull();
      if (!w) continue;
      const archive = SPHEREX_PASSES[id];
      expect(w.framesBuilt).toBe(false);
      expect(w.synthetic).toBe(false);
      expect(w.source).toBe(SPHEREX_COVERAGE_SOURCE);
      expect(w.passes.map((p) => [p.startMjd, p.endMjd, p.nImages])).toEqual(
        archive.map((p) => [p.startMjd, p.endMjd, p.nImages]),
      );
      expect(w.passes.every((p) => p.kind === 'archive' && p.frames.length === 0)).toBe(true);
      w.passes.forEach((p, i) => {
        expect(p.index).toBe(i);
        expect(p.midMjd).toBe((p.startMjd + p.endMjd) / 2);
        expect(passAt(w, p.midMjd)).toBe(i);
      });
      // Calendar dates shown to the user are RECON's, not the day-rounded MJDs (R Dra: approximate).
      expect(w.passes.map((p) => p.dates)).toEqual(
        archive.map((p) => (p.dates ? [...p.dates] : [mjdToIsoDate(p.startMjd), mjdToIsoDate(p.endMjd)])),
      );
      expect(w.passes.every((p) => p.datesApprox === (id === 'r-draconis'))).toBe(true);
      expect(w.startMjd).toBe(DR1_START_MJD);
      expect(w.endMjd).toBe(archive[archive.length - 1].endMjd);
      expect(w.totalImages).toBe(archive.reduce((n, p) => n + p.nImages, 0));
      const [lo, hi] = timelineDomain(w);
      expect(lo).toBeLessThan(DR1_START_MJD);
      expect(hi).toBeGreaterThan(DATASET_TODAY_MJD);
    }
  });

  it('gives the synthetic system the demo-ecliptic frames as solid, built passes', () => {
    const sys = system('demo-ecliptic-orbits');
    expect(sys.field_id).toBe('demo-ecliptic');
    expect(datasetWindow(sys)).toBeNull(); // no archive coverage and no frames
    const frames = field('demo-ecliptic').frames;
    const w = datasetWindow(sys, frames);
    expect(w).not.toBeNull();
    if (!w) return;
    expect(w.framesBuilt).toBe(true);
    expect(w.synthetic).toBe(true);
    expect(w.source).toContain('synthetic');
    expect(w.source).not.toContain('IRSA');
    expect(w.passes).toHaveLength(1);
    const [p] = w.passes;
    expect(p.kind).toBe('built');
    expect(p.frames).toHaveLength(6);
    expect(p.detectors).toEqual([2]);
    expect(p.dates).toEqual(['2025-05-15', '2025-05-16']);
    expect(p.datesApprox).toBe(false);
    expect(p.startMjd).toBe(Math.min(...frames.map((f) => f.mjd)));
    expect(w.endMjd).toBe(Math.max(...frames.map((f) => f.mjd)));
    expect(w.startMjd).toBe(DR1_START_MJD);
  });

  it('puts built frames of a real field inside its archive passes, others in new passes', () => {
    const frames = [
      { id: 'a', mjd: 60910.2, detector: 3, wavelength_um: 1.9 },
      { id: 'b', mjd: 60910.3, detector: 6, wavelength_um: 4.6 },
      { id: 'c', mjd: 61000.0, detector: 1, wavelength_um: 0.9 }, // between passes 1 and 2
    ];
    const w = datasetWindow(system('barnards-star'), frames);
    expect(w).not.toBeNull();
    if (!w) return;
    expect(w.framesBuilt).toBe(true);
    expect(w.source).toContain(SPHEREX_COVERAGE_SOURCE);
    expect(w.source).toContain('frames built in this dataset (field barnards-star)');
    expect(w.passes.map((p) => p.kind)).toEqual(['archive', 'built', 'archive', 'archive']);
    expect(w.passes[0].frames.map((f) => f.id)).toEqual(['a', 'b']);
    expect(w.passes[0].nImages).toBe(118); // the archive count, not the built frames
    expect(w.passes[1].frames.map((f) => f.id)).toEqual(['c']);
    expect(w.passes[1].nImagesLongWave).toBe(0);
    expect(w.passes.map((p) => p.index)).toEqual([0, 1, 2, 3]);
  });

  it('is null for an unknown system without frames', () => {
    expect(datasetWindow({ id: 'nowhere' })).toBeNull();
    expect(datasetWindow({ id: 'nowhere' }, [{ mjd: Number.NaN }])).toBeNull();
  });

  it('is available exactly when datasetGate.hasDatasetWindow says so (the viewer enables the button from it)', () => {
    const frameSets = [null, [], [{ mjd: Number.NaN }], [{ mjd: 60810.2 }], field('demo-ecliptic').frames];
    const ids = [...SYSTEMS.map((s) => s.id), 'nowhere', 'toString'];
    for (const id of ids) {
      for (const frames of frameSets) {
        const sys = SYSTEMS.find((s) => s.id === id) ?? { id };
        expect(hasDatasetWindow(id, frames), `${id} ${JSON.stringify(frames)}`).toBe(datasetWindow(sys, frames) !== null);
      }
    }
  });

  it('locates a date among the passes and visits', () => {
    const w = datasetWindow(system('wise-0855'));
    if (!w) throw new Error('no window');
    expect(passAt(w, 60801.5)).toBe(0);
    expect(passAt(w, 60800.6)).toBe(0); // day rounding of the window edge
    expect(passAt(w, 60900)).toBe(-1);
    expect(nearestPass(w, 60850)).toBe(0);
    expect(nearestPass(w, 60900)).toBe(1); // 80 d before pass 2, 98 d after pass 1
    expect(nearestPass(w, 60970)).toBe(1);
    expect(nearestPass(w, DATASET_TODAY_MJD)).toBe(2);
    expect(betweenVisits(w.passes[1], 61007)).toBe(true); // between 2025-11-14 and 2025-12-11
    expect(betweenVisits(w.passes[1], 60985)).toBe(false);
    expect(betweenVisits(w.passes[0], 60801.5)).toBe(false); // no visit split recorded
  });
});

describe('dateTicks', () => {
  it('puts readable month ticks on the dataset axis', () => {
    const [lo, hi] = timelineDomain({ startMjd: DR1_START_MJD, endMjd: QR3_LAST_MJD });
    const narrow = dateTicks(lo, hi, 5); // ~375 px phone
    expect(narrow.map((t) => t.label)).toEqual(['Jul 2025', '2026', 'Jul']);
    const wide = dateTicks(lo, hi, 13);
    expect(wide.length).toBeLessThanOrEqual(14);
    expect(wide[0].label).toBe('May 2025');
    for (const t of [...narrow, ...wide]) {
      expect(mjdToIsoDate(t.mjd).endsWith('-01')).toBe(true);
      expect(t.major).toBe(t.label.length === 4);
    }
  });

  it('switches to days and hours for short spans', () => {
    const days = dateTicks(isoDateToMjd('2025-05-15'), isoDateToMjd('2025-05-25'), 12);
    expect(days[0].label).toBe('05-15');
    expect(days).toHaveLength(11);
    const hours = dateTicks(60810.1, 60811.27, 4);
    expect(hours.map((t) => t.label)).toEqual(['12:00', '05-16']);
    expect(dateTicks(5, 5, 4)).toEqual([]);
  });
});

describe('phaseStatus', () => {
  const orbiting = (s: SystemModel) => s.bodies.filter((b) => b.orbit).map((b) => b.id);

  it('splits every orbiting body of every demo system by whether it has an epoch', () => {
    for (const s of SYSTEMS) {
      const st = phaseStatus(s);
      expect([...st.dated, ...st.arbitrary].sort(), s.id).toEqual(orbiting(s).sort());
      expect(st.dated).toEqual(s.bodies.filter((b) => b.orbit && b.orbit.epoch_mjd != null).map((b) => b.id));
    }
  });

  it('lists every orbiting body of Epsilon Indi as arbitrary', () => {
    const st = phaseStatus(system('epsilon-indi'));
    expect(st.dated).toEqual([]);
    expect(st.arbitrary).toEqual(['eps-indi-ab', 'eps-indi-ba', 'eps-indi-bb']);
    expect(phaseStatusLine(system('epsilon-indi'))).toBe(
      'Real epoch: none · Arbitrary phase: Epsilon Indi Ab, Epsilon Indi Ba, Epsilon Indi Bb',
    );
  });

  it("dates every Barnard planet after M5 (Basant et al. 2025 t0)", () => {
    const s = system('barnards-star');
    const st = phaseStatus(s);
    expect(st.dated).toEqual(['barnard-d', 'barnard-b', 'barnard-c', 'barnard-e']);
    expect(st.arbitrary).toEqual([]);
    expect(phaseStatusLine(s)).toBe('Real epoch: Barnard d, Barnard b, Barnard c, Barnard e · Arbitrary phase: none');
    // Removing an epoch moves the planet back to "arbitrary".
    const without: SystemModel = {
      ...s,
      bodies: s.bodies.map((b) => (b.id === 'barnard-b' && b.orbit ? { ...b, orbit: { ...b.orbit, epoch_mjd: null } } : b)),
    };
    const after = phaseStatus(without);
    expect(after.arbitrary).toEqual(['barnard-b']);
    expect(after.dated).not.toContain('barnard-b');
  });

  it('predicts R Dra from the WS7 ephemeris table (S3), never an irregular variable (RW Aur)', () => {
    const rdra = system('r-draconis');
    expect(phaseStatus(rdra)).toMatchObject({ pulsationPredicted: ['r-draconis'], pulsationArbitrary: [], irregular: [] });
    expect(phaseStatusLine(rdra)).toBe('Predicted pulsation phase (catalogue ephemeris): R Draconis');
    // Without a table entry (another system id) the same star is phase-unknown, i.e. frozen on a real date.
    const other: Pick<SystemModel, 'id' | 'bodies'> = { id: 'not-in-the-table', bodies: rdra.bodies };
    expect(phaseStatus(other).pulsationArbitrary).toEqual(['r-draconis']);
    expect(phaseStatusLine(other)).toBe('Variability phase unknown, mean brightness: R Draconis');
    const rw = phaseStatus(system('rw-aurigae'));
    expect(rw).toMatchObject({ pulsationPredicted: [], pulsationArbitrary: [], irregular: ['rw-aur-a', 'rw-aur-b'], arbitrary: ['rw-aur-b'] });
    expect(phaseStatusLine(system('rw-aurigae'))).toBe(
      'Real epoch: none · Arbitrary phase: RW Aurigae B · Irregular, unpredictable: RW Aurigae A, RW Aurigae B',
    );
  });

  it('says when nothing depends on a phase', () => {
    expect(phaseStatus(system('wise-0855'))).toEqual({
      dated: [],
      arbitrary: [],
      pulsationPredicted: [],
      pulsationArbitrary: [],
      irregular: [],
    });
    expect(phaseStatusLine(system('wise-0855'))).toBe('Nothing in this model depends on an orbital or pulsation phase.');
  });

  it('classifies variability exactly like the timeline (ephemerides.variabilityPhase)', () => {
    const base = system('rw-aurigae').bodies[0];
    const vary = (id: string, kind: VariabilityKind, period: number | null): Body => ({
      ...base,
      id,
      name: id,
      orbit: null,
      variability: { kind, period_days: period, amplitude_mag: 1, band: 'V' },
    });
    const made: Pick<SystemModel, 'id' | 'bodies'> = {
      id: 'x',
      bodies: [vary('rot', 'rotation', null), vary('puls', 'pulsation', null), vary('ecl', 'eclipse', 3), vary('irr', 'irregular', 12)],
    };
    for (const s of [...SYSTEMS, made]) {
      const st = phaseStatus(s);
      const byKind = (k: string) => variabilityTracks(s).filter((t) => t.kind === k).map((t) => t.bodyId);
      expect(st.irregular, s.id).toEqual(byKind('irregular'));
      expect(st.pulsationPredicted, s.id).toEqual(byKind('predicted'));
      expect(st.pulsationArbitrary, s.id).toEqual(byKind('unknown'));
    }
    // No period but not irregular = unknown (frozen), listed; irregular even with a period.
    expect(phaseStatus(made)).toMatchObject({ pulsationArbitrary: ['rot', 'puls', 'ecl'], irregular: ['irr'] });
  });

  it('says when free-running starts a phase arbitrarily', () => {
    expect(freeRunningArbitraryPhase(system('epsilon-indi'))).toBe(true); // undated orbits
    expect(freeRunningArbitraryPhase(system('r-draconis'))).toBe(true); // animated pulsation
    expect(freeRunningArbitraryPhase(system('wise-0855'))).toBe(false);
    // Barnard: every orbit is dated and nothing pulsates.
    expect(freeRunningArbitraryPhase(system('barnards-star'))).toBe(false);
  });
});

describe('dataset clock', () => {
  it('runs from the dataset start to the query date, never faster than the window in 60 s', () => {
    const w = datasetWindow(system('epsilon-indi'));
    if (!w) throw new Error('no window');
    expect(datasetBounds(w)).toEqual([DR1_START_MJD, DATASET_TODAY_MJD]);
    const span = DATASET_TODAY_MJD - DR1_START_MJD;
    expect(datasetSpeed(500, w)).toBeCloseTo(span / DATASET_PLAY_SECONDS, 9); // Eps Ind: 11-yr binary, capped
    expect(datasetSpeed(0.29, w)).toBe(0.29); // Barnard-like speed: kept
  });
});
