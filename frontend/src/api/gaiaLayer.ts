import { astrometricPlace, julianEpochToMjd, JULIAN_YEAR_DAYS, separationArcsec } from '../three/skyTrack';
import { footprintRadiusArcsec, tangentPlanePosition } from './skyFootprint';
import type { Frame, SkyCoord } from './types';

const GAIA_DR3_EPOCH = julianEpochToMjd(2016);
const VIZIER_TSV = 'https://vizier.cfa.harvard.edu/viz-bin/asu-tsv';
/** VizieR I/355/gaiadr3 column names, checked against real VizieR CfA responses on 2026-11-15 (api/__fixtures__). */
const COLUMNS = ['Source', 'RA_ICRS', 'DE_ICRS', 'Plx', 'e_Plx', 'pmRA', 'pmDE', 'Gmag', 'BP-RP', 'RV'] as const;
type Column = typeof COLUMNS[number];
export const GAIA_SOURCE_LIMIT = 500;
/**
 * Gaia DR3 stars per view (FE-4b) are queried when the map field of view is at most this many degrees; wider than
 * GAIA_FULL_FOV only the stars brighter than G 15 (gaiaViewMagLimit) are asked for. VizieR CfA timings on 2026-11-15
 * (-sort=Gmag, at most 501 rows): cones of 0.33–0.37° (a 0.5° view) took 2.9–4.3 s around all five targets. Cones of
 * 0.73–0.88° (a 1–1.2° view) with G < 15 took 4.5 s around WISE 0855, 5.5–13.8 s around RW Aurigae and 14.0–20.1 s
 * next to Barnard's Star. Wider views were too slow for the 20 s cap even with G < 12: a 3° view (cone ≈ 2.2°) took
 * 29.6 s twice around RW Aurigae, 9.5 s around R Draconis, 11.6 s around WISE 0855 and did not answer within 60 s next
 * to Barnard's Star; cones of 1.3–1.45° (a 1.5–2° view) took 24.3–28.8 s around RW Aurigae and did not answer within
 * 35 s next to Barnard's Star. VizieR scans the whole cone before the G cut, so a limit keeps the stars readable but
 * does not make wide cones fast; above this field of view the map says to zoom in.
 */
export const GAIA_VIEW_MAX_FOV = 1.2;
/** Views up to this field of view (degrees) get every Gaia DR3 source (the brightest 500), with no G limit. */
export const GAIA_FULL_FOV = 0.5;
/** G limit of the views wider than GAIA_FULL_FOV (up to GAIA_VIEW_MAX_FOV). */
export const GAIA_WIDE_MAG_LIMIT = 15;
/** Epoch of the per-view stars when no sequence is open: MJD 61000 = 2025-11-21 UTC. */
export const GAIA_DEFAULT_EPOCH = 61000;
// Per-view cones take 3–20 s (see GAIA_VIEW_MAX_FOV); the cap is wider than the 12 s of #111 for dense fields and slow days.
const QUERY_TIMEOUT_MS = 20_000;
/** A per-view query that failed fast (an incomplete or error answer, not a timeout) is asked once more after this. */
const RETRY_DELAY_MS = 1_500;
const FAST_FAILURE_MS = 8_000;
/** The queried cone is this much wider than the visible half-diagonal, so small pans are answered from the cache. */
const VIEW_SLACK = 1.2;

/** One Gaia DR3 source: its position predicted for the layer epoch plus the catalog values the hover card shows. */
export interface GaiaMarker extends SkyCoord {
  sourceId: string;
  /** G magnitude, BP−RP colour (mag), parallax and its error (mas), proper motion (mas/yr) and RV (km/s); null when
   *  Gaia DR3 does not list the value. */
  gmag: number | null;
  bpRp: number | null;
  parallax: number | null;
  parallaxError: number | null;
  pmRa: number;
  pmDec: number;
  rv: number | null;
}

export interface GaiaMarkerSet {
  markers: GaiaMarker[];
  limited: boolean;
}

export function medianFrameEpoch(frames: Frame[]): number | null {
  const dates = frames.map(({ mjd }) => mjd).filter(Number.isFinite).sort((a, b) => a - b);
  if (!dates.length) return null;
  return (dates[Math.floor((dates.length - 1) / 2)] + dates[Math.floor(dates.length / 2)]) / 2;
}

function optionalNumber(value = ''): number | null {
  const numeric = value.trim() ? Number(value) : NaN;
  return Number.isFinite(numeric) ? numeric : null;
}

/** Parse a VizieR asu-tsv response and propagate each source with proper motion to `epoch` (MJD). */
export function readMarkers(tsv: string, epoch: number): GaiaMarkerSet {
  const lines = tsv.split(/\r?\n/);
  if (lines.some((line) => /^#(?:ERROR|INFO\s+QUERY_STATUS=ERROR)/i.test(line))) {
    throw new Error('Gaia DR3 query failed');
  }
  const header = lines.findIndex((line) => line.startsWith('Source\t'));
  if (header < 0) {
    // VizieR returns catalog and column metadata without a row header for a successful empty cone.
    const columns = new Set(lines.filter((line) => line.startsWith('#Column\t')).map((line) => line.split('\t')[1]));
    if (lines.some((line) => line.startsWith('#Table\tI_355_gaiadr3:')) && COLUMNS.every((name) => columns.has(name))) {
      return { markers: [], limited: false };
    }
    throw new Error('Unexpected Gaia DR3 table');
  }
  const names = lines[header].split('\t').map((name) => name.trim());
  const index = Object.fromEntries(COLUMNS.map((name) => [name, names.indexOf(name)])) as Record<Column, number>;
  if (COLUMNS.some((name) => index[name] < 0)) throw new Error('Unexpected Gaia DR3 table');
  const rows = lines.slice(header + 1).filter((line) => /^\d+\t/.test(line.trimStart()));
  const years = (epoch - GAIA_DR3_EPOCH) / JULIAN_YEAR_DAYS;
  const markers: GaiaMarker[] = [];
  for (const row of rows.slice(0, GAIA_SOURCE_LIMIT)) {
    const cells = row.split('\t');
    const value = (name: Column) => optionalNumber(cells[index[name]]);
    const sourceId = cells[index.Source].trim();
    const ra = value('RA_ICRS');
    const dec = value('DE_ICRS');
    const east = value('pmRA');
    const north = value('pmDE');
    const parallax = value('Plx');
    const rv = value('RV');
    // Two-parameter solutions have no proper motion: their position at the layer epoch is unknown.
    if (!/^\d{1,20}$/.test(sourceId) || ra === null || dec === null || east === null || north === null) continue;
    const details = {
      sourceId, gmag: value('Gmag'), bpRp: value('BP-RP'), parallax, parallaxError: value('e_Plx'),
      pmRa: east, pmDec: north, rv,
    };
    if (parallax !== null && parallax > 0) {
      const place = astrometricPlace({
        raDeg: ra, decDeg: dec, epochMjd: GAIA_DR3_EPOCH,
        pmRaCosDecMasYr: east, pmDecMasYr: north, parallaxMas: parallax, radialVelocityKmS: rv,
      }, epoch);
      markers.push({ ...details, ra: place.raDeg, dec: place.decDeg });
    } else {
      // Without a positive parallax, propagate angular proper motion alone.
      markers.push({ ...details, ...tangentPlanePosition({ ra, dec }, east * years / 3_600_000, north * years / 3_600_000) });
    }
  }
  return { markers, limited: rows.length > GAIA_SOURCE_LIMIT };
}

/** Query outside the region too, so high proper-motion sources can move into it from J2016.0. */
function motionMarginArcsec(epoch: number): number {
  return Math.max(30, 12 * Math.abs(epoch - GAIA_DR3_EPOCH) / JULIAN_YEAR_DAYS);
}

async function queryCone(center: SkyCoord, radiusArcsec: number, epoch: number, signal: AbortSignal,
  magLimit: number | null = null) {
  const query = new URLSearchParams({
    '-source': 'I/355/gaiadr3',
    '-c': `${center.ra.toFixed(7)} ${center.dec.toFixed(7)}`,
    '-c.rs': radiusArcsec.toFixed(3),
    '-out': COLUMNS.join(','),
    '-sort': 'Gmag',
    '-out.max': String(GAIA_SOURCE_LIMIT + 1),
  });
  if (magLimit !== null) query.set('Gmag', `<${magLimit}`);
  const response = await fetch(`${VIZIER_TSV}?${query}`, { signal });
  if (!response.ok) throw new Error(`Gaia DR3 service returned ${response.status}`);
  return readMarkers(await response.text(), epoch);
}

/** Gaia DR3 sources around a sequence footprint, propagated to the sequence epoch (#111). */
export async function getGaiaMarkers(center: SkyCoord, corners: SkyCoord[], epoch: number, signal: AbortSignal) {
  return queryCone(center, footprintRadiusArcsec(center, corners) + motionMarginArcsec(epoch), epoch, signal);
}

/**
 * A map view: centre (ICRS degrees), the larger side of the field of view and, when the map reports them, the
 * horizontal and vertical sides (degrees).
 */
export interface GaiaView extends SkyCoord {
  fov: number;
  fovX?: number;
  fovY?: number;
}

/**
 * Radius (degrees) that covers everything visible: half the diagonal of the view. Without both sides, the view is
 * taken as square (0.71 × fov), which also bounds any other aspect ratio.
 */
export function gaiaViewVisibleRadiusDeg(view: GaiaView): number {
  return view.fovX && view.fovY ? Math.hypot(view.fovX, view.fovY) / 2 : view.fov * Math.SQRT1_2;
}

/** G magnitude limit of a view's Gaia stars: none up to GAIA_FULL_FOV, then GAIA_WIDE_MAG_LIMIT. */
export function gaiaViewMagLimit(view: Pick<GaiaView, 'fov'>): number | null {
  return view.fov <= GAIA_FULL_FOV ? null : GAIA_WIDE_MAG_LIMIT;
}

/** Cone radius (degrees, before the proper-motion margin) queried for the Gaia stars of a view. */
export function gaiaViewRadiusDeg(view: GaiaView): number {
  return gaiaViewVisibleRadiusDeg(view) * VIEW_SLACK;
}

async function queryViewOnce(view: GaiaView, epoch: number, signal: AbortSignal): Promise<GaiaMarkerSet> {
  const timeout = new AbortController();
  const timer = setTimeout(() => timeout.abort(), QUERY_TIMEOUT_MS);
  const stop = () => timeout.abort();
  if (signal.aborted) stop();
  signal.addEventListener('abort', stop);
  try {
    return await queryCone(view, gaiaViewRadiusDeg(view) * 3600 + motionMarginArcsec(epoch), epoch, timeout.signal,
      gaiaViewMagLimit(view));
  } finally {
    clearTimeout(timer);
    signal.removeEventListener('abort', stop);
  }
}

/**
 * The brightest Gaia DR3 sources (<= GAIA_SOURCE_LIMIT, brighter than gaiaViewMagLimit) around a map view, propagated
 * to `epoch` (FE-4b). A fast failure is asked once more; a timeout is not. QA 2026-11-15: VizieR CfA answered the
 * WISE 0855 cone with an 899-byte HTTP 200 body without the table, twice in a row, and with the full table later; it
 * also answered RW Aurigae and Barnard's Star cones within 0.7 s with a 1327-byte HTTP 200 body saying "The database
 * is not currently reachable" (#INFO QUERY_STATUS=ERROR), a server outage that zooming in does not fix.
 */
export async function getGaiaView(view: GaiaView, epoch: number, signal: AbortSignal,
  retryDelayMs = RETRY_DELAY_MS): Promise<GaiaMarkerSet> {
  const started = Date.now();
  try {
    return await queryViewOnce(view, epoch, signal);
  } catch (error) {
    if (signal.aborted || Date.now() - started > FAST_FAILURE_MS) throw error;
    await new Promise<void>((resolve, reject) => {
      const timer = setTimeout(resolve, retryDelayMs);
      signal.addEventListener('abort', () => { clearTimeout(timer); reject(error); }, { once: true });
    });
    return queryViewOnce(view, epoch, signal);
  }
}

interface CacheEntry {
  center: SkyCoord;
  /** Radius queried for that view (degrees, before the proper-motion margin, which is the same at the same epoch). */
  radius: number;
  epoch: number;
  /** G limit of that query (null: none). A brighter-limited cone cannot answer a fainter request, nor the reverse. */
  magLimit: number | null;
  result: GaiaMarkerSet;
}

/**
 * The last `capacity` per-view results, least recently used first out. A cached cone answers a new view at the same
 * epoch when it covers everything visible in it (the half-diagonal; the cones are queried 1.2 × wider, so small pans
 * hit the cache). A cone cut at GAIA_SOURCE_LIMIT only answers views that would query a cone of a similar size, so
 * zooming in asks again for the fainter stars.
 */
export class GaiaViewCache {
  private entries: CacheEntry[] = [];
  constructor(readonly capacity = 20) {}

  get size(): number {
    return this.entries.length;
  }

  get(view: GaiaView, epoch: number): GaiaMarkerSet | undefined {
    const visible = gaiaViewVisibleRadiusDeg(view);
    const wanted = gaiaViewRadiusDeg(view);
    const magLimit = gaiaViewMagLimit(view);
    const at = this.entries.findIndex(({ center, radius, epoch: cachedEpoch, magLimit: cachedLimit, result }) => {
      const offset = separationArcsec({ raDeg: view.ra, decDeg: view.dec }, { raDeg: center.ra, decDeg: center.dec }) / 3600;
      return cachedEpoch === epoch && cachedLimit === magLimit && offset + visible <= radius + 1e-9
        && (!result.limited || radius <= wanted * 1.25);
    });
    if (at < 0) return undefined;
    const [entry] = this.entries.splice(at, 1);
    this.entries.push(entry);
    return entry.result;
  }

  set(view: GaiaView, epoch: number, result: GaiaMarkerSet): void {
    this.entries.push({
      center: { ra: view.ra, dec: view.dec }, radius: gaiaViewRadiusDeg(view), epoch, magLimit: gaiaViewMagLimit(view), result,
    });
    while (this.entries.length > this.capacity) this.entries.shift();
  }
}
