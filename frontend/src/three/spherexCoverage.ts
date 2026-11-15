// SPHEREx archive coverage of the five challenge targets, for the 3D gallery's "Dataset time" mode
// (work package M4). Pure data + helpers: no React, no three.js, so everything here is unit-tested.
//
// Where the numbers come from (IRSA SIA2 + TAP over spherex_dr1(_deep) and spherex_qr3(_deep),
// queried 2026-11-14):
// - Pass windows (MJD) and image counts: docs/DATA.md, "Cobertura de los 5 objetivos" (passes there
//   are "temporadas": blocks of frames separated by more than 30 days). The MJDs are given to the
//   day; DR1 starts at t_min 60789.75 and DATA.md writes 60790, so they are rounded (+-0.5 d).
// - Calendar dates, per-detector counts, counts at a local wavelength of 3.9-5 um, the detectors of
//   the last Epsilon Indi pass and the 10-day split of WISE 0855's second pass:
//   docs/RECON_SPHEREX.md section 4.2.
// The calendar dates of RECON and the MJDs of DATA.md agree within that rounding for every pass
// (checked in spherexCoverage.test.ts). The two queries differ slightly (TAP at the DATA.md centre vs
// SIA r = 1" at the 2026 position), so a few counts differ by 1-2 images; pass notes say where.
//
// These are ARCHIVE windows: IRSA has frames of the target there. This dataset may not contain them
// (most targets have no built field), and the UI must say so.
//
// Time scale: SPHEREx frame times are MJD-AVG (docs/RECON_SPHEREX.md 2.4). They are treated as UTC
// here; a TT/UTC ambiguity (~69 s) is irrelevant at the day-level precision of these windows.
import type { Body, Frame, Provenance, SystemModel } from '../api/types';
import { mjdToDate } from '../api/format';
import { isSpherexTarget, type SpherexTargetId } from './datasetGate';
import { variabilityPhase } from './ephemerides';

// The id list lives in datasetGate.ts (main chunk); this module loads with the 3D view.
export { isSpherexTarget, type SpherexTargetId };

export const SPHEREX_COVERAGE_SOURCE = 'IRSA SIA2+TAP DR1+QR3, queried 2026-11-14, docs/RECON_SPHEREX.md 4.2';

/** Caption for a pass band whose frames this dataset does not contain. */
export const ARCHIVE_CAPTION = 'archive coverage - frames not built in this dataset';
/** Label suffix for a body drawn on a real date with an arbitrary orbital phase. */
export const PHASE_UNKNOWN_SUFFIX = '(phase unknown)';

/** Visits are split where consecutive frames are more than this many days apart (RECON 2.6). */
export const VISIT_GAP_DAYS = 10;
/** Gap used by the published coverage tables (DATA.md "temporadas", RECON 4.2). */
export const ARCHIVE_SEASON_GAP_DAYS = 30;
/** The archive MJDs are rounded to the day: a frame within this margin of a window is inside it. */
export const PASS_EDGE_TOLERANCE_DAYS = 0.5;

/** First DR1 frame, t_min of spherex_dr1 (RECON 2.1): 2025-04-24 18:00 UTC. */
export const DR1_START_MJD = 60789.75;
/** Last QR3 frame indexed when queried, max t_min of spherex_qr3 (RECON 2.1): 2026-10-05. */
export const QR3_LAST_MJD = 61318.0;

// --- MJD <-> ISO dates -------------------------------------------------------------------------

/** 'YYYY-MM-DD' (UTC) of an MJD; '' when it is not a representable date. */
export function mjdToIsoDate(mjd: number): string {
  const d = mjdToDate(mjd);
  const year = d.getUTCFullYear();
  if (!Number.isFinite(d.getTime()) || year < 0 || year > 9999) return '';
  return d.toISOString().slice(0, 10);
}

/**
 * MJD of an ISO 8601 date or date-time. A bare date is 00:00 UTC, and a date-time without a zone
 * designator is read as UTC (SPHEREx DATE-OBS is UTC), never as browser local time. NaN if invalid.
 */
export function isoDateToMjd(iso: string): number {
  const s = iso.trim();
  let text = s;
  if (/^\d{4}-\d{2}-\d{2}$/.test(s)) text = `${s}T00:00:00Z`;
  else if (/^\d{4}-\d{2}-\d{2}T[\d:.]+$/.test(s)) text = `${s}Z`;
  const ms = Date.parse(text);
  return Number.isFinite(ms) ? ms / 86400000 + 40587 : NaN; // MJD 40587 = 1970-01-01
}

/** Date the coverage was queried; nothing later is in this dataset. */
export const DATASET_TODAY_ISO = '2026-11-14';
export const DATASET_TODAY_MJD = isoDateToMjd(DATASET_TODAY_ISO); // 61358
export const TODAY_LABEL = `today ${DATASET_TODAY_ISO} · no later data in this dataset`;

// --- archive coverage of the five targets -------------------------------------------------------

export interface ArchiveVisit {
  startMjd: number;
  endMjd: number;
  nImages: number;
  /** First and last observing date (UTC) as written in RECON 4.2. */
  dates: readonly [string, string];
}

export interface ArchivePass {
  startMjd: number; // DATA.md, rounded to the day
  endMjd: number;
  nImages: number; // DATA.md
  /** First and last observing date (UTC) as written in RECON 4.2; null when RECON gives months only. */
  dates: readonly [string, string] | null;
  /** Detectors with frames in this pass, when RECON names them (null = not recorded per pass). */
  detectors: readonly number[] | null;
  /** Images whose local LVF wavelength at the target is 3.9-5 um (RECON 4.2); null = not recorded. */
  nImagesLongWave: number | null;
  /** Separate visits inside the pass when the 10-day gap splits it (RECON 4.2). */
  subVisits?: readonly ArchiveVisit[];
  note?: string;
}

export interface TargetCoverage {
  /** What the coverage query was centred on (the 3D system may contain more bodies). */
  target: string;
  /** Centre of the TAP query (DATA.md), deg ICRS. */
  queryCenter: { ra: number; dec: number };
  /** Images per IRSA collection (DATA.md). */
  imagesByCollection: Readonly<Record<string, number>>;
  /** Images per detector D1..D6 (RECON 4.2, SIA r = 1" at the 2026 position). */
  imagesByDetector: readonly [number, number, number, number, number, number];
  /** First and last observing date (UTC), DATA.md "Fechas". */
  dateRange: readonly [string, string];
  /** Images per calendar month (UTC), when RECON gives them. */
  monthly?: readonly { month: string; nImages: number }[];
  passes: readonly ArchivePass[];
  note?: string;
}

export const SPHEREX_COVERAGE: Readonly<Record<SpherexTargetId, TargetCoverage>> = {
  'barnards-star': {
    target: "Barnard's Star",
    queryCenter: { ra: 269.4463, dec: 4.7665 },
    imagesByCollection: { spherex_dr1: 239, spherex_qr3: 119 },
    imagesByDetector: [60, 61, 59, 59, 61, 58],
    dateRange: ['2025-08-15', '2026-09-22'],
    passes: [
      { startMjd: 60903, endMjd: 60949, nImages: 118, dates: ['2025-08-15', '2025-10-01'], detectors: null, nImagesLongWave: 32 },
      { startMjd: 61110, endMjd: 61165, nImages: 121, dates: ['2026-03-11', '2026-05-05'], detectors: null, nImagesLongWave: 40 },
      { startMjd: 61269, endMjd: 61306, nImages: 119, dates: ['2026-08-16', '2026-09-22'], detectors: null, nImagesLongWave: 38 },
    ],
  },
  'epsilon-indi': {
    target: 'Epsilon Indi B (Ba+Bb, unresolved)',
    queryCenter: { ra: 331.0964, dec: -56.8006 },
    imagesByCollection: { spherex_dr1: 340, spherex_qr3: 120 },
    imagesByDetector: [46, 93, 96, 46, 84, 93], // 458: RECON's query; DATA.md counts 460
    dateRange: ['2025-04-24', '2026-10-02'],
    passes: [
      {
        startMjd: 60790, endMjd: 60836, nImages: 120, dates: ['2025-04-24', '2025-06-10'], detectors: null, nImagesLongWave: 50,
        note: 'RECON 4.2 (SIA, r = 1″ at the 2026 position) counts 118 images.',
      },
      {
        startMjd: 60947, endMjd: 60992, nImages: 147, dates: ['2025-09-28', '2025-11-12'], detectors: null, nImagesLongWave: 39,
        note: 'RECON 4.2 (SIA, r = 1″ at the 2026 position) counts 146 images.',
      },
      {
        startMjd: 61149, endMjd: 61164, nImages: 73, dates: ['2026-04-18', '2026-05-04'], detectors: null, nImagesLongWave: 16,
        note: 'RECON 4.2 (SIA, r = 1″ at the 2026 position) counts 74 images.',
      },
      {
        startMjd: 61305, endMjd: 61315, nImages: 120, dates: ['2026-09-22', '2026-10-02'], detectors: [2, 3, 5, 6], nImagesLongWave: 55,
        note: 'Only detectors D2, D3, D5 and D6 cover the target in this pass.',
      },
    ],
    note: 'Coverage queried at Epsilon Indi B; Epsilon Indi A is 402.6″ to the west.',
  },
  'wise-0855': {
    target: 'WISE 0855−0714',
    queryCenter: { ra: 133.76, dec: -7.2422 },
    imagesByCollection: { spherex_dr1: 258, spherex_qr3: 0 },
    imagesByDetector: [36, 48, 45, 36, 48, 45],
    dateRange: ['2025-05-05', '2026-05-14'],
    passes: [
      { startMjd: 60801, endMjd: 60802, nImages: 30, dates: ['2025-05-05', '2025-05-06'], detectors: null, nImagesLongWave: 11 },
      {
        startMjd: 60980, endMjd: 61022, nImages: 128, dates: ['2025-10-31', '2025-12-13'], detectors: null, nImagesLongWave: 43,
        // Visit ends are the mid-day of the RECON dates, clipped to the DATA.md window.
        subVisits: [
          { startMjd: 60980, endMjd: 60993.5, nImages: 110, dates: ['2025-10-31', '2025-11-14'] },
          { startMjd: 61020.5, endMjd: 61022, nImages: 18, dates: ['2025-12-11', '2025-12-13'] },
        ],
        note: 'Two visits 27 days apart: separate with the 10-day visit gap, one pass with 30 days.',
      },
      { startMjd: 61151, endMjd: 61174, nImages: 100, dates: ['2026-04-21', '2026-05-14'], detectors: null, nImagesLongWave: 34 },
    ],
    note: 'QR3 had no frames of this target yet when queried; the next pass (~Nov-Dec 2026) is an estimate, not verified.',
  },
  'rw-aurigae': {
    target: 'RW Aurigae (A+B, 1.5″ apart)',
    queryCenter: { ra: 76.9565, dec: 30.4014 },
    imagesByCollection: { spherex_dr1: 226, spherex_qr3: 109 },
    imagesByDetector: [56, 55, 56, 56, 56, 56],
    dateRange: ['2025-09-01', '2026-09-16'],
    passes: [
      { startMjd: 60919, endMjd: 60938, nImages: 112, dates: ['2025-09-01', '2025-09-20'], detectors: null, nImagesLongWave: null },
      { startMjd: 61092, endMjd: 61111, nImages: 114, dates: ['2026-02-20', '2026-03-12'], detectors: null, nImagesLongWave: null },
      { startMjd: 61285, endMjd: 61300, nImages: 109, dates: ['2026-09-02', '2026-09-16'], detectors: null, nImagesLongWave: null },
    ],
  },
  'r-draconis': {
    target: 'R Draconis',
    queryCenter: { ra: 248.1676, dec: 66.755 },
    imagesByCollection: { spherex_dr1: 413, spherex_qr3: 126, spherex_dr1_deep: 1225, spherex_qr3_deep: 729 },
    imagesByDetector: [584, 89, 574, 584, 89, 573],
    dateRange: ['2025-04-24', '2026-09-27'],
    monthly: [
      { month: '2025-04', nImages: 58 },
      { month: '2025-05', nImages: 41 },
      { month: '2025-06', nImages: 91 },
      { month: '2025-07', nImages: 50 },
      { month: '2025-08', nImages: 14 },
      { month: '2025-09', nImages: 188 },
      { month: '2025-10', nImages: 84 },
      { month: '2025-11', nImages: 82 },
      { month: '2025-12', nImages: 84 },
      { month: '2026-01', nImages: 20 },
      { month: '2026-02', nImages: 112 },
      { month: '2026-03', nImages: 500 },
      { month: '2026-04', nImages: 253 },
      { month: '2026-05', nImages: 84 },
      { month: '2026-06', nImages: 56 },
      { month: '2026-07', nImages: 119 },
      { month: '2026-08', nImages: 432 },
      { month: '2026-09', nImages: 225 },
    ],
    passes: [
      {
        startMjd: 60790, endMjd: 60879, nImages: 240, dates: null, detectors: null, nImagesLongWave: null,
        note: 'Monthly visits, April to July 2025 (58 + 41 + 91 + 50 images).',
      },
      {
        startMjd: 60916, endMjd: 61310, nImages: 2253, dates: null, detectors: null, nImagesLongWave: null,
        note: 'Near-continuous, monthly visits: R Dra lies in the NEP deep field. The largest gap (37.8 d) is the one before this pass.',
      },
    ],
  },
};

/** Archive pass windows keyed by system id. */
export const SPHEREX_PASSES: Readonly<Record<SpherexTargetId, readonly ArchivePass[]>> = {
  'barnards-star': SPHEREX_COVERAGE['barnards-star'].passes,
  'epsilon-indi': SPHEREX_COVERAGE['epsilon-indi'].passes,
  'wise-0855': SPHEREX_COVERAGE['wise-0855'].passes,
  'rw-aurigae': SPHEREX_COVERAGE['rw-aurigae'].passes,
  'r-draconis': SPHEREX_COVERAGE['r-draconis'].passes,
};

export function coverageFor(systemId: string): TargetCoverage | null {
  return isSpherexTarget(systemId) ? SPHEREX_COVERAGE[systemId] : null;
}

// --- grouping built frames into passes -----------------------------------------------------------

export interface MjdGroup {
  startMjd: number;
  endMjd: number;
  count: number;
  /** Positions in the input array, in time order. */
  indices: number[];
}

/**
 * Group frame times (Field.frames[].mjd, i.e. MJD-AVG) into passes: a new pass starts where two
 * consecutive frames are more than `gapDays` apart. 10 days (RECON 2.6) separates WISE 0855's
 * Nov and Dec 2025 visits, which a 30-day gap merges. Non-finite values are skipped.
 */
export function groupPasses(frameMjds: readonly number[], gapDays: number = VISIT_GAP_DAYS): MjdGroup[] {
  if (!Number.isFinite(gapDays) || gapDays <= 0) throw new RangeError(`gapDays must be > 0 (got ${gapDays})`);
  const order = frameMjds
    .map((_, i) => i)
    .filter((i) => Number.isFinite(frameMjds[i]))
    .sort((a, b) => frameMjds[a] - frameMjds[b] || a - b);
  const groups: MjdGroup[] = [];
  let current: MjdGroup | null = null;
  for (const i of order) {
    const mjd = frameMjds[i];
    if (current && mjd - current.endMjd <= gapDays) {
      current.endMjd = mjd;
      current.count += 1;
      current.indices.push(i);
    } else {
      current = { startMjd: mjd, endMjd: mjd, count: 1, indices: [i] };
      groups.push(current);
    }
  }
  return groups;
}

// --- the dataset window of one system -----------------------------------------------------------

/** The part of a Frame the timeline needs (Field.frames[] satisfies it). */
export type FrameLike = Pick<Frame, 'mjd'> & Partial<Pick<Frame, 'id' | 'detector' | 'wavelength_um'>>;

export interface PassFrame {
  id: string | null;
  mjd: number;
  detector: number | null;
  wavelengthUm: number | null;
}

export interface CoveragePass {
  index: number; // 0-based, in time order; the UI says "Pass index + 1"
  /** archive = window from the IRSA query; built = group of frames this dataset contains. */
  kind: 'archive' | 'built';
  startMjd: number;
  endMjd: number;
  /** Where "jump to pass" sets the clock. */
  midMjd: number;
  /** First and last observing date (UTC): RECON's dates, the built frames, or else the rounded MJDs. */
  dates: [string, string];
  /** True when `dates` come from MJDs rounded to the day (+-1 d), not from a dated source. */
  datesApprox: boolean;
  /** Images in the window (archive count, or the number of built frames). */
  nImages: number;
  /** Frames of this dataset inside the window; empty = not built here. */
  frames: PassFrame[];
  subVisits: { startMjd: number; endMjd: number; nImages: number }[];
  detectors: number[] | null;
  nImagesLongWave: number | null;
  note: string | null;
}

export interface DatasetWindow {
  systemId: string;
  /** What the coverage refers to (e.g. "Epsilon Indi B (Ba+Bb, unresolved)"); null for built-only fields. */
  target: string | null;
  fieldId: string | null;
  /** Axis start: DR1 start, or the first frame if earlier. */
  startMjd: number;
  /** Last frame (end of the last pass). */
  endMjd: number;
  passes: CoveragePass[];
  source: string;
  /** True when this dataset contains frames (Field.frames) of the system's field. */
  framesBuilt: boolean;
  /** The frames are synthetic (demo field), not SPHEREx observations. */
  synthetic: boolean;
  totalImages: number;
  note: string | null;
}

export type DatasetSystemRef = Pick<SystemModel, 'id'> & {
  field_id?: string | null;
  provenance?: Pick<Provenance, 'synthetic'>;
};

/** Built frames this close to an archive window belong to it (day rounding plus margin). */
const ARCHIVE_MATCH_DAYS = 1;
/** Frames whose local wavelength counts as "long" (where WISE 0855 is visible, RECON 4.3). */
const LONG_WAVE_MIN_UM = 3.9;

function toPassFrame(f: FrameLike): PassFrame {
  return {
    id: f.id ?? null,
    mjd: f.mjd,
    detector: typeof f.detector === 'number' ? f.detector : null,
    wavelengthUm: typeof f.wavelength_um === 'number' && Number.isFinite(f.wavelength_um) ? f.wavelength_um : null,
  };
}

function builtPassFields(frames: PassFrame[]): Pick<CoveragePass, 'detectors' | 'nImagesLongWave'> {
  const dets = [...new Set(frames.map((f) => f.detector).filter((d): d is number => d !== null))].sort((a, b) => a - b);
  const withLambda = frames.filter((f) => f.wavelengthUm !== null);
  return {
    detectors: dets.length ? dets : null,
    nImagesLongWave: withLambda.length ? withLambda.filter((f) => (f.wavelengthUm ?? 0) >= LONG_WAVE_MIN_UM).length : null,
  };
}

/**
 * The time span the "Dataset time" mode covers for one system: the archive passes of the target
 * (hatched, unless this dataset has frames in them) plus any frames of its built field, grouped
 * with `gapDays`. Returns null when neither is known (the mode is then unavailable).
 */
export function datasetWindow(
  system: DatasetSystemRef,
  fieldFrames?: readonly FrameLike[] | null,
  gapDays: number = VISIT_GAP_DAYS,
): DatasetWindow | null {
  const coverage = coverageFor(system.id);
  const frames = (fieldFrames ?? [])
    .filter((f) => Number.isFinite(f.mjd))
    .map(toPassFrame)
    .sort((a, b) => a.mjd - b.mjd);
  if (!coverage && frames.length === 0) return null;

  const passes: Omit<CoveragePass, 'index'>[] = [];
  const claimed = new Set<number>();
  for (const ap of coverage?.passes ?? []) {
    const inside: PassFrame[] = [];
    frames.forEach((f, i) => {
      if (claimed.has(i) || f.mjd < ap.startMjd - ARCHIVE_MATCH_DAYS || f.mjd > ap.endMjd + ARCHIVE_MATCH_DAYS) return;
      claimed.add(i);
      inside.push(f);
    });
    passes.push({
      kind: 'archive',
      startMjd: ap.startMjd,
      endMjd: ap.endMjd,
      midMjd: (ap.startMjd + ap.endMjd) / 2,
      dates: ap.dates ? [ap.dates[0], ap.dates[1]] : [mjdToIsoDate(ap.startMjd), mjdToIsoDate(ap.endMjd)],
      datesApprox: !ap.dates,
      nImages: ap.nImages,
      frames: inside,
      subVisits: (ap.subVisits ?? []).map((v) => ({ startMjd: v.startMjd, endMjd: v.endMjd, nImages: v.nImages })),
      detectors: ap.detectors ? [...ap.detectors] : null,
      nImagesLongWave: ap.nImagesLongWave,
      note: ap.note ?? null,
    });
  }
  const leftover = frames.filter((_, i) => !claimed.has(i));
  for (const g of groupPasses(
    leftover.map((f) => f.mjd),
    gapDays,
  )) {
    const groupFrames = g.indices.map((i) => leftover[i]);
    passes.push({
      kind: 'built',
      startMjd: g.startMjd,
      endMjd: g.endMjd,
      midMjd: (g.startMjd + g.endMjd) / 2,
      dates: [mjdToIsoDate(g.startMjd), mjdToIsoDate(g.endMjd)],
      datesApprox: false,
      nImages: g.count,
      frames: groupFrames,
      subVisits: [],
      ...builtPassFields(groupFrames),
      note: null,
    });
  }
  passes.sort((a, b) => a.startMjd - b.startMjd);
  const indexed: CoveragePass[] = passes.map((p, index) => ({ ...p, index }));

  const synthetic = system.provenance?.synthetic ?? false;
  const fieldId = system.field_id ?? null;
  const sources: string[] = [];
  if (coverage) sources.push(SPHEREX_COVERAGE_SOURCE);
  if (frames.length) {
    const field = fieldId ? ` (field ${fieldId})` : '';
    sources.push(
      synthetic
        ? `synthetic demo frames${field}, not SPHEREx observations`
        : `frames built in this dataset${field}`,
    );
  }
  return {
    systemId: system.id,
    target: coverage?.target ?? null,
    fieldId,
    startMjd: Math.min(DR1_START_MJD, ...indexed.map((p) => p.startMjd)),
    endMjd: Math.max(...indexed.map((p) => p.endMjd)),
    passes: indexed,
    source: sources.join('; '),
    framesBuilt: frames.length > 0,
    synthetic,
    totalImages: indexed.reduce((n, p) => n + p.nImages, 0),
    note: coverage?.note ?? null,
  };
}

/** Axis domain of the timeline: the dataset window extended to the "today" marker, with a margin. */
export function timelineDomain(w: Pick<DatasetWindow, 'startMjd' | 'endMjd'>): [number, number] {
  const lo = w.startMjd;
  const hi = Math.max(w.endMjd, DATASET_TODAY_MJD);
  const span = Math.max(hi - lo, 1);
  return [lo - span * 0.01, hi + span * 0.02];
}

function inWindow(mjd: number, start: number, end: number, tol = PASS_EDGE_TOLERANCE_DAYS): boolean {
  return mjd >= start - tol && mjd <= end + tol;
}

/** Index of the pass whose window contains `mjd` (+-0.5 d day rounding), or -1. */
export function passAt(w: Pick<DatasetWindow, 'passes'>, mjd: number): number {
  const p = w.passes.find((q) => inWindow(mjd, q.startMjd, q.endMjd));
  return p ? p.index : -1;
}

/** Index of the pass closest to `mjd` (0 distance inside a window), or -1 with no passes. */
export function nearestPass(w: Pick<DatasetWindow, 'passes'>, mjd: number): number {
  let best = -1;
  let bestD = Infinity;
  for (const p of w.passes) {
    const d = mjd < p.startMjd ? p.startMjd - mjd : mjd > p.endMjd ? mjd - p.endMjd : 0;
    if (d < bestD) {
      bestD = d;
      best = p.index;
    }
  }
  return best;
}

/** True when `mjd` is inside a pass but between its separate visits (no frames that day). */
export function betweenVisits(pass: Pick<CoveragePass, 'subVisits'>, mjd: number): boolean {
  return pass.subVisits.length > 0 && !pass.subVisits.some((v) => inWindow(mjd, v.startMjd, v.endMjd));
}

// --- axis ticks ---------------------------------------------------------------------------------

export interface DateTick {
  mjd: number;
  label: string;
  /** Year start (month steps), month start (day steps) or midnight (hour steps). */
  major: boolean;
}

type TickStep = { unit: 'hour' | 'day' | 'month'; n: number };
const TICK_STEPS: TickStep[] = [
  ...[1, 2, 3, 6, 12].map((n): TickStep => ({ unit: 'hour', n })),
  ...[1, 2, 5, 10].map((n): TickStep => ({ unit: 'day', n })),
  ...[1, 2, 3, 6, 12, 24, 60].map((n): TickStep => ({ unit: 'month', n })),
];
const STEP_DAYS = { hour: 1 / 24, day: 1, month: 30.44 } as const;
const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

function utcMjd(year: number, month: number, day = 1): number {
  return Date.UTC(year, month, day) / 86400000 + 40587;
}

/**
 * Calendar-aligned UTC ticks between two MJDs, at most `maxTicks` of them: hours, days or months
 * depending on the span. Month ticks read "Jul 2025" (first), "Oct", "2026"...; day ticks "MM-DD".
 */
export function dateTicks(startMjd: number, endMjd: number, maxTicks: number): DateTick[] {
  if (!(endMjd > startMjd) || !Number.isFinite(startMjd) || !Number.isFinite(endMjd) || maxTicks < 1) return [];
  const span = endMjd - startMjd;
  const step = TICK_STEPS.find((s) => span / (STEP_DAYS[s.unit] * s.n) <= maxTicks) ?? TICK_STEPS[TICK_STEPS.length - 1];
  const ticks: DateTick[] = [];
  if (step.unit === 'month') {
    const d = mjdToDate(startMjd);
    let y = d.getUTCFullYear();
    let m = d.getUTCMonth();
    for (let guard = 0; guard < 2400; guard++) {
      const mjd = utcMjd(y, m);
      if (mjd > endMjd) break;
      if (mjd >= startMjd && (y * 12 + m) % step.n === 0) {
        const first = ticks.length === 0;
        const label = m === 0 ? String(y) : first ? `${MONTHS[m]} ${y}` : MONTHS[m];
        ticks.push({ mjd, label, major: m === 0 });
      }
      m += 1;
      if (m === 12) {
        m = 0;
        y += 1;
      }
    }
  } else if (step.unit === 'day') {
    // Days of the month 1, 1+n, 1+2n... up to 28 at most, so the last tick never crowds the next "1".
    const maxDom = 1 + step.n * Math.floor(27 / step.n);
    for (let day = Math.ceil(startMjd); day <= endMjd; day++) {
      const dom = mjdToDate(day).getUTCDate();
      if ((dom - 1) % step.n !== 0 || dom > maxDom) continue;
      ticks.push({ mjd: day, label: mjdToIsoDate(day).slice(5), major: dom === 1 });
    }
  } else {
    const perDay = 24 / step.n;
    for (let k = Math.ceil(startMjd * perDay); k / perDay <= endMjd; k++) {
      const mjd = k / perDay;
      const midnight = k % perDay === 0;
      const hh = String(Math.round((mjd - Math.floor(mjd)) * 24) % 24).padStart(2, '0');
      ticks.push({ mjd, label: midnight ? mjdToIsoDate(mjd).slice(5) : `${hh}:00`, major: midnight });
    }
  }
  return ticks;
}

// --- playing inside the window -------------------------------------------------------------------

/** Dates the dataset clock can take: the dataset start to the last frame or the query date ("today"). */
export function datasetBounds(w: Pick<DatasetWindow, 'startMjd' | 'endMjd'>): [number, number] {
  return [w.startMjd, Math.max(w.endMjd, DATASET_TODAY_MJD)];
}

/** At ×1, playing through the whole dataset takes at least this long (seconds). */
export const DATASET_PLAY_SECONDS = 60;

/**
 * Speed (days per second) of the dataset clock: the free-running speed (fastest period in 8 s), but
 * never faster than the whole window in DATASET_PLAY_SECONDS, so a wide binary does not skip passes.
 */
export function datasetSpeed(freeDaysPerSecond: number, w: Pick<DatasetWindow, 'startMjd' | 'endMjd'>): number {
  const [lo, hi] = datasetBounds(w);
  return Math.min(freeDaysPerSecond, Math.max(hi - lo, 1) / DATASET_PLAY_SECONDS);
}

// --- which phases are real on a calendar date ----------------------------------------------------

export interface PhaseStatus {
  /** Orbiting bodies with an epoch (Orbit.epoch_mjd): their position on a real date is a prediction. */
  dated: string[];
  /** Orbiting bodies without an epoch: arbitrary phase, never a position for a real date. */
  arbitrary: string[];
  /** Variability 'predicted' (ephemerides.variabilityPhase): a WS7 catalogue ephemeris gives the phase on a real date. */
  pulsationPredicted: string[];
  /**
   * Variability 'unknown': periodic without an ephemeris, or a non-irregular kind without a period.
   * Frozen at mean brightness on a real date.
   */
  pulsationArbitrary: string[];
  /** Variability 'irregular' (kind === 'irregular'): never predicted. */
  irregular: string[];
}

function hasEpoch(b: Body): boolean {
  return !!b.orbit && b.orbit.epoch_mjd != null && Number.isFinite(b.orbit.epoch_mjd);
}

/**
 * Root bodies (no orbit) sit at the origin and are in neither orbit list. Contract 0.2.1 has no epoch
 * for a Variability, so a predicted pulsation comes only from the WS7 table, looked up by system and
 * body id: the id is required, or R Dra would silently lose its ephemeris. Variability follows the
 * one rule of ephemerides.variabilityPhase (also used by the timeline, the HUD and the scene).
 */
export function phaseStatus(system: Pick<SystemModel, 'id' | 'bodies'>): PhaseStatus {
  const out: PhaseStatus = { dated: [], arbitrary: [], pulsationPredicted: [], pulsationArbitrary: [], irregular: [] };
  for (const b of system.bodies) {
    if (b.orbit) (hasEpoch(b) ? out.dated : out.arbitrary).push(b.id);
    const v = variabilityPhase(system.id, b);
    if (v === 'irregular') out.irregular.push(b.id);
    else if (v === 'predicted') out.pulsationPredicted.push(b.id);
    else if (v === 'unknown') out.pulsationArbitrary.push(b.id);
  }
  return out;
}

/**
 * Free-running starts every orbit without an epoch and every animated variability (period_days > 0,
 * not irregular) at an arbitrary phase: the "Model time" hint says so.
 */
export function freeRunningArbitraryPhase(system: Pick<SystemModel, 'bodies'>): boolean {
  return system.bodies.some((b) => {
    const v = b.variability;
    return (!!b.orbit && !hasEpoch(b)) || (!!v && v.kind !== 'irregular' && (v.period_days ?? 0) > 0);
  });
}

/**
 * The line shown next to the calendar date in dataset mode, e.g.
 * "Real epoch: Barnard d, Barnard b, Barnard c, Barnard e · Arbitrary phase: none".
 */
export function phaseStatusLine(system: Pick<SystemModel, 'id' | 'bodies'>): string {
  const s = phaseStatus(system);
  const byId = new Map<string, Body>(system.bodies.map((b) => [b.id, b]));
  const names = (ids: string[]) => (ids.length ? ids.map((id) => byId.get(id)?.name ?? id).join(', ') : 'none');
  const parts: string[] = [];
  if (s.dated.length + s.arbitrary.length > 0) {
    parts.push(`Real epoch: ${names(s.dated)}`, `Arbitrary phase: ${names(s.arbitrary)}`);
  }
  if (s.pulsationPredicted.length > 0) parts.push(`Predicted pulsation phase (catalogue ephemeris): ${names(s.pulsationPredicted)}`);
  if (s.pulsationArbitrary.length > 0) parts.push(`Variability phase unknown, mean brightness: ${names(s.pulsationArbitrary)}`);
  if (s.irregular.length > 0) parts.push(`Irregular, unpredictable: ${names(s.irregular)}`);
  return parts.length ? parts.join(' · ') : 'Nothing in this model depends on an orbital or pulsation phase.';
}
