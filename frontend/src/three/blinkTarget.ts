// Predicted position of the target on the blink frames (PARALLEL_PLAN V3, WS7 math for the WS5
// viewer). Pure math + text, no React and no three.js, unit-tested in blinkTarget.test.ts.
//
// WS5's #96 draws the reticle itself (components/framePrediction.ts predictedFramePixel, the same TAN
// projection in image-edge coordinates = the PNG pixel below + 0.5). This module adds what the
// reticle alone does not say: which target and astrometry it is for (all five targets, not only
// Barnard's Star), the honest label, the shift over the frames shown, the faint predicted track
// with its first/last points, and static field stars that sit near the target position.
//
// Why: the real fields move by only ~1-2 SPHEREx pixels over the whole baseline (Barnard's Star
// ~1.7 px, docs/validation/barnards-star.md), so the motion is hard to see in the blink without a
// mark of where the target should be in each frame.
//
// Model (a PREDICTION from catalog astrometry, never a measurement):
// - The astrometry is the one the WS7 sky track uses (skyTrack.ts trackAstrometry: the system's
//   catalog SpaceMotion, or the WS7 per-system table, e.g. Epsilon Indi B's own Gaia DR3 solution,
//   since the system centre is A, ~65 px west of the B field).
// - Each frame's place is the geocentric ICRS astrometric place at the frame's mid-exposure MJD
//   (skyTrack.ts astrometricPlace: straight-line space motion, Butkevich & Lindegren 2014, plus the
//   annual parallax). SPHEREx is in low Earth orbit (~7000 km = 5e-5 AU from the geocentre), so the
//   geocentric place is adequate: the orbit's own parallax is below 0.03 mas even for Barnard's Star.
// - The place is projected on the field's common grid with the FITS TAN (gnomonic) projection of
//   field.grid.wcs, the same as the pipeline's errante.imaging.grid.sky_to_png_xy (astropy
//   all_world2pix with origin 0, then y = (height - 1) - y0), giving contract PNG pixels: origin at
//   the top-left pixel centre, x right, y down, north up, east left.
import type { Field, Frame, SystemModel } from '../api/types';
import {
  astrometricPlace,
  SPACE_MOTION_CITATION,
  STATIC_SPAN_PX,
  trackAstrometry,
  type TrackAstrometry,
} from './skyTrack';

const DEG = Math.PI / 180;

/** The exact wording every predicted-position label carries (PARALLEL_PLAN V3). */
export const BLINK_TARGET_PHRASE = 'predicted from catalog, not a measurement';
/** Why the geocentric place is enough for SPHEREx (stated in the legend's tooltip). */
export const BLINK_TARGET_OBSERVER_NOTE =
  'Geocentric ICRS astrometric place: SPHEREx is in low Earth orbit, so its offset from the geocentre is negligible at this pixel scale.';

// --- projection -------------------------------------------------------------------------------

export interface PngXY {
  x: number;
  y: number;
}

type GridLike = Pick<Field['grid'], 'width_px' | 'height_px' | 'wcs'>;

function wcsNumber(wcs: GridLike['wcs'], key: string): number | null {
  const v = wcs[key];
  return typeof v === 'number' && Number.isFinite(v) ? v : null;
}

/**
 * ICRS (deg) -> contract PNG pixel on a field grid, FITS TAN projection with CRVAL at the reference
 * point and CDELT in deg/px (the pipeline's grid_wcs: no PC/CD matrix, no distortion).
 * Matches errante.imaging.grid.sky_to_png_xy. RA wraps through 0/360. Null when the grid is not a
 * plain RA---TAN/DEC--TAN grid or the point is on or behind the tangent plane's horizon.
 */
export function tanWorldToPng(grid: GridLike, raDeg: number, decDeg: number): PngXY | null {
  const { wcs } = grid;
  if (wcs.CTYPE1 !== 'RA---TAN' || wcs.CTYPE2 !== 'DEC--TAN') return null;
  const ra0 = wcsNumber(wcs, 'CRVAL1');
  const dec0 = wcsNumber(wcs, 'CRVAL2');
  const crpix1 = wcsNumber(wcs, 'CRPIX1');
  const crpix2 = wcsNumber(wcs, 'CRPIX2');
  const cdelt1 = wcsNumber(wcs, 'CDELT1');
  const cdelt2 = wcsNumber(wcs, 'CDELT2');
  if (ra0 === null || dec0 === null || crpix1 === null || crpix2 === null || !cdelt1 || !cdelt2) return null;
  if (!Number.isFinite(raDeg) || !Number.isFinite(decDeg) || !(grid.height_px > 0)) return null;
  // sin/cos of the RA difference are periodic, so RA wraps through 0/360 by itself.
  const dRa = (raDeg - ra0) * DEG;
  const d = decDeg * DEG;
  const d0 = dec0 * DEG;
  const cosC = Math.sin(d) * Math.sin(d0) + Math.cos(d) * Math.cos(d0) * Math.cos(dRa);
  if (!(cosC > 0)) return null; // the gnomonic projection only covers the near hemisphere
  // Intermediate world coordinates (deg): xi towards +RA (east), eta towards +Dec (north).
  const xi = (Math.cos(d) * Math.sin(dRa)) / cosC / DEG;
  const eta = (Math.sin(d) * Math.cos(d0) - Math.cos(d) * Math.sin(d0) * Math.cos(dRa)) / cosC / DEG;
  // 1-based FITS pixel, then 0-based (origin 0) and flipped to the PNG convention (y down).
  const p1 = crpix1 + xi / cdelt1;
  const p2 = crpix2 + eta / cdelt2;
  return { x: p1 - 1, y: grid.height_px - p2 };
}

/** True when a PNG pixel position falls on the grid (pixel i spans i - 0.5 to i + 0.5). */
export function insideGrid(grid: Pick<Field['grid'], 'width_px' | 'height_px'>, p: PngXY): boolean {
  return p.x >= -0.5 && p.x <= grid.width_px - 0.5 && p.y >= -0.5 && p.y <= grid.height_px - 0.5;
}

// --- prediction per frame ---------------------------------------------------------------------

export interface BlinkTargetPoint extends PngXY {
  frameId: string;
  mjd: number;
  raDeg: number;
  decDeg: number;
  inGrid: boolean;
}

export interface BlinkStaticSource extends PngXY {
  name: string;
  raDeg: number;
  decDeg: number;
  note: string;
  source: string;
  inGrid: boolean;
}

export interface BlinkTargetPrediction {
  /** null when built straight from a TrackAstrometry (predictFromAstrometry). */
  systemId: string | null;
  fieldId: string;
  /** What the reticle follows (e.g. "Epsilon Indi B (Ba+Bb, unresolved)"). */
  target: string;
  /** Where the astrometry comes from (skyTrack TRACK_SOURCES / SystemModel). */
  source: string;
  /** 'system' = SystemModel.center + motion; 'ws7-constant' = WS7 table solution. */
  astrometryOrigin: TrackAstrometry['origin'];
  epochLabel: string;
  method: string;
  notes: readonly string[];
  /** Static sources near the target (catalog positions, no motion), projected on the grid. */
  staticSources: BlinkStaticSource[];
  /** One point per frame, in time order. */
  points: BlinkTargetPoint[];
  first: BlinkTargetPoint;
  last: BlinkTargetPoint;
  /** Mean of the frame positions (the zoom centre). */
  mean: PngXY;
  /** First to last frame (px on the grid, and arcsec at grid.pixel_scale_arcsec). */
  totalShiftPx: number;
  totalShiftArcsec: number;
  /** Proper motion in grid pixels per Julian year. */
  perYearPx: number;
  pixelScaleArcsec: number;
  /** Whether the track and its first/last rings are worth drawing (false when static at this pixel scale). */
  showTrack: boolean;
  /** Hover text of the reticle. */
  reticleTitle: string;
  /** Short visible legend under the stage (target, phrase, short source, shift); contains BLINK_TARGET_PHRASE. */
  caption: string;
  /** What the astrometry is "predicted from" in WS5's one-line note: "the Gaia catalog" or a short source. */
  catalogName: string;
  /** Label of WS5's toggle: "Gaia prediction" for Gaia astrometry, "Catalog prediction" otherwise. */
  toggleLabel: string;
  /** The rest of the legend, one paragraph each, behind a disclosure: full source, method, notes. */
  details: readonly string[];
}

/**
 * Legend notes per tracked target (TrackAstrometry.target) that the visible caption must carry (not only the disclosure).
 * The captions stay within the length the tests allow (blinkTarget.test.ts); the sources and the rest are the detail line.
 * TODO(WS7): move into skyTrack.ts TRACK_SOURCES (its WISE 0855 field-star note already says D1–D4).
 */
const LEGEND_NOTES: Readonly<Record<string, { caption: string; detail: string; staticNote?: string }>> = {
  'WISE 0855−0714': {
    caption: 'Barely visible even in D5/D6; in D1–D4 the blob near the crosshair (0.7–1.8 px away) is that star.',
    // Replaces skyTrack's field-star note in the details: adds its distance from the crosshair in the published frames.
    staticNote:
      'static field star (CatWISE J085501.95−071428.2, G 16.31): in D1–D4 the blob near the target position (0.7–1.8 px away in the published frames) is this star (docs/validation/wise-0855.md; docs/RECON_SPHEREX.md 4.3 lists D1–D3)',
    detail:
      'WISE 0855−0714 is visible only at λ ≥ 3.9 µm, D5/D6 (docs/RECON_SPHEREX.md 4.3), and faint even there: median S/N 3.4–3.8 per exposure; the published blink does not show it convincingly (docs/validation/wise-0855.md). In D1–D4 only the background star appears, near the predicted position (docs/validation/wise-0855.md).',
  },
  'RW Aurigae A+B': {
    caption: "Crosshair at A's Gaia position; B is 1.5″ (0.24 px) WSW, unresolved: SPHEREx sees the blend.",
    detail: 'Gaia DR3: B is 1.493″ from A at PA 254.4° (docs/SCIENCE.md).',
  },
  'Epsilon Indi B (Ba+Bb, unresolved)': {
    caption: 'Not detected in 2 of the 5 D1 frames shown (< 0.83 µm): there the crosshair marks empty sky.',
    detail:
      'In 2 of the 5 published D1 frames (0.756 and 0.776 µm, bluer than ~0.83 µm) the T dwarf is not detected, so there the crosshair marks its predicted place on empty sky (docs/validation/eps-indi-b.md, update of 2026-11-15).',
  },
};

/**
 * Short name of an astrometry source for the visible legend: its Gaia DR3 source ids, else the
 * text before the first ':', ';', ',' or ' ('. The full source string goes in the details.
 */
export function shortSource(source: string): string {
  const ids = [...new Set(source.match(/Gaia DR3 \d+/g) ?? [])].map((s) => s.slice('Gaia DR3 '.length));
  if (ids.length) return `Gaia DR3 ${ids.join(' + ')}`;
  return source.split(/[:;,]| \(/)[0].trim() || source;
}

export type BlinkTargetSystem = Pick<SystemModel, 'id' | 'name' | 'center' | 'motion'> &
  Partial<Pick<SystemModel, 'field_id' | 'provenance'>>;

type BlinkField = Pick<Field, 'id' | 'grid' | 'frames'> & { provenance?: Pick<Field['provenance'], 'synthetic'> };

/** "1.73 px (10.7″ at 6.15″/px)", or "0.0040 px (25 mas at 6.15″/px), static at this pixel scale". */
export function formatShift(px: number, pixelScaleArcsec: number): string {
  const arcsec = px * pixelScaleArcsec;
  const scale = `at ${pixelScaleArcsec}″/px`;
  if (px >= STATIC_SPAN_PX) return `${px.toFixed(2)} px (${arcsec.toFixed(1)}″ ${scale})`;
  return `${px.toPrecision(2)} px (${(arcsec * 1000).toFixed(0)} mas ${scale}), static at this pixel scale`;
}

/**
 * Predicted PNG position of the system's tracked target in each frame (default: all frames of the
 * field), or null when there is nothing honest to draw: no system, a system of another field, a
 * real system on a synthetic field, no propagatable astrometry, or no frame position on the grid.
 */
export function predictTarget(
  system: BlinkTargetSystem | null | undefined,
  field: BlinkField,
  frames: readonly Pick<Frame, 'id' | 'mjd'>[] = field.frames,
): BlinkTargetPrediction | null {
  if (!system) return null;
  if (system.field_id != null && system.field_id !== field.id) return null;
  // Catalog astrometry of a real star says nothing about where a synthetic image puts things.
  if (field.provenance?.synthetic && !system.provenance?.synthetic) return null;
  let astrometry: TrackAstrometry | null;
  try {
    astrometry = trackAstrometry(system);
  } catch {
    return null;
  }
  if (!astrometry) return null;
  const p = predictFromAstrometry(astrometry, field, frames);
  return p && { ...p, systemId: system.id };
}

/** True when the astrometry comes from Gaia (WS5's note and toggle say "Gaia" then). */
export function isGaiaAstrometry(astrometry: Pick<TrackAstrometry, 'source'>): boolean {
  return /\bGaia DR3 \d+/.test(astrometry.source);
}

/**
 * The same prediction straight from a TrackAstrometry (what FieldPage hands the blink viewer), or
 * null when no frame position falls on the grid. The caller checks that the astrometry belongs to
 * this field and that the field is not synthetic (FieldPage does).
 */
export function predictFromAstrometry(
  astrometry: TrackAstrometry,
  field: Pick<Field, 'id' | 'grid' | 'frames'>,
  frames: readonly Pick<Frame, 'id' | 'mjd'>[] = field.frames,
): BlinkTargetPrediction | null {
  const grid = field.grid;
  const scale = grid.pixel_scale_arcsec;
  if (!(scale > 0)) return null;

  const points: BlinkTargetPoint[] = [];
  for (const f of [...frames].sort((a, b) => a.mjd - b.mjd)) {
    if (!Number.isFinite(f.mjd)) continue;
    const place = astrometricPlace(astrometry, f.mjd);
    const xy = tanWorldToPng(grid, place.raDeg, place.decDeg);
    if (!xy || !Number.isFinite(xy.x) || !Number.isFinite(xy.y)) continue;
    points.push({ frameId: f.id, mjd: f.mjd, raDeg: place.raDeg, decDeg: place.decDeg, ...xy, inGrid: insideGrid(grid, xy) });
  }
  if (!points.some((p) => p.inGrid)) return null;

  const staticSources: BlinkStaticSource[] = [];
  for (const s of astrometry.staticSources) {
    const xy = tanWorldToPng(grid, s.raDeg, s.decDeg);
    if (xy) staticSources.push({ ...s, ...xy, inGrid: insideGrid(grid, xy) });
  }

  const first = points[0];
  const last = points[points.length - 1];
  const mean = {
    x: points.reduce((sum, p) => sum + p.x, 0) / points.length,
    y: points.reduce((sum, p) => sum + p.y, 0) / points.length,
  };
  const totalShiftPx = Math.hypot(last.x - first.x, last.y - first.y);
  const totalShiftArcsec = totalShiftPx * scale;
  const perYearPx = Math.hypot(astrometry.pmRaCosDecMasYr, astrometry.pmDecMasYr) / 1000 / scale;
  const method = `proper motion + parallax from ${astrometry.epochLabel} (${SPACE_MOTION_CITATION})`;
  const n = points.length;
  const frameWord = `frame${n === 1 ? '' : 's'}`;
  // A track below STATIC_SPAN_PX (R Dra, RW Aur) is a dot under the crosshair: nothing to draw.
  const showTrack = n > 1 && totalShiftPx >= STATIC_SPAN_PX;
  const legendNote = Object.prototype.hasOwnProperty.call(LEGEND_NOTES, astrometry.target) ? LEGEND_NOTES[astrometry.target] : undefined;
  const gaia = isGaiaAstrometry(astrometry);

  const shownStatic = staticSources.filter((s) => s.inGrid);
  const staticText = shownStatic.length
    ? ` Dashed circle${shownStatic.length > 1 ? 's' : ''}: ${shownStatic.map((s) => s.name).join(', ')} (static).`
    : '';
  // Visible line kept short (it sits between the stage and the scrubber): the rest is in `details`.
  const caption =
    `${astrometry.target}: ${BLINK_TARGET_PHRASE} (${shortSource(astrometry.source)}).` +
    (showTrack ? ' Faint line: its track; rings: first/last frame.' : '') +
    ` Over the ${n} ${frameWord} shown it moves ${formatShift(totalShiftPx, scale)}.` +
    staticText +
    (legendNote ? ` ${legendNote.caption}` : '');
  const details = [
    ...(showTrack
      ? [`Faint line: the predicted track through the ${n} ${frameWord} shown, in time order; small rings: its first and last point.`]
      : []),
    `Astrometry: ${astrometry.source}; ${method}.`,
    ...shownStatic.map((s) => `Dashed circle, ${s.name}: ${legendNote?.staticNote ?? s.note} (${s.source}).`),
    ...(legendNote ? [legendNote.detail] : []),
    BLINK_TARGET_OBSERVER_NOTE,
    ...astrometry.notes,
  ];

  return {
    systemId: null,
    fieldId: field.id,
    target: astrometry.target,
    source: astrometry.source,
    astrometryOrigin: astrometry.origin,
    epochLabel: astrometry.epochLabel,
    method,
    notes: astrometry.notes,
    staticSources,
    points,
    first,
    last,
    mean,
    totalShiftPx,
    totalShiftArcsec,
    perYearPx,
    pixelScaleArcsec: scale,
    showTrack,
    reticleTitle: `Predicted position of ${astrometry.target}: ${BLINK_TARGET_PHRASE}`,
    caption,
    catalogName: gaia ? 'the Gaia catalog' : shortSource(astrometry.source),
    toggleLabel: gaia ? 'Gaia prediction' : 'Catalog prediction',
    details,
  };
}
