import { astrometricPlace, julianEpochToMjd, JULIAN_YEAR_DAYS } from '../three/skyTrack';
import { footprintRadiusArcsec, tangentPlanePosition } from './skyFootprint';
import type { Frame, SkyCoord } from './types';

const GAIA_DR3_EPOCH = julianEpochToMjd(2016);
const VIZIER_TSV = 'https://vizier.cfa.harvard.edu/viz-bin/asu-tsv';
const COLUMNS = 'Source,RA_ICRS,DE_ICRS,Plx,pmRA,pmDE,Gmag,RV';
export const GAIA_SOURCE_LIMIT = 500;

export interface GaiaMarker extends SkyCoord {
  sourceId: string;
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

function readMarkers(tsv: string, epoch: number): { markers: GaiaMarker[]; limited: boolean } {
  const lines = tsv.split(/\r?\n/);
  if (lines.some((line) => /^#(?:ERROR|INFO\s+QUERY_STATUS=ERROR)/i.test(line))) {
    throw new Error('Gaia DR3 query failed');
  }
  const header = lines.findIndex((line) => line.trim() === COLUMNS.replaceAll(',', '\t'));
  if (header < 0) {
    // VizieR returns catalog and column metadata without a row header for a successful empty cone.
    const columns = new Set(lines.filter((line) => line.startsWith('#Column\t')).map((line) => line.split('\t')[1]));
    if (lines.some((line) => line.startsWith('#Table\tI_355_gaiadr3:')) && COLUMNS.split(',').every((name) => columns.has(name))) {
      return { markers: [], limited: false };
    }
    throw new Error('Unexpected Gaia DR3 table');
  }
  const rows = lines.slice(header + 1).filter((line) => /^\d+\t/.test(line.trimStart()));
  const years = (epoch - GAIA_DR3_EPOCH) / JULIAN_YEAR_DAYS;
  const markers: GaiaMarker[] = [];
  for (const row of rows.slice(0, GAIA_SOURCE_LIMIT)) {
    const [id, raText, decText, parallaxText, eastText, northText, , rvText] = row.split('\t');
    const ra = optionalNumber(raText);
    const dec = optionalNumber(decText);
    const east = optionalNumber(eastText);
    const north = optionalNumber(northText);
    const parallax = optionalNumber(parallaxText);
    if (ra === null || dec === null || east === null || north === null) continue;
    if (parallax !== null && parallax > 0) {
      const place = astrometricPlace({
        raDeg: ra, decDeg: dec, epochMjd: GAIA_DR3_EPOCH,
        pmRaCosDecMasYr: east, pmDecMasYr: north, parallaxMas: parallax,
        radialVelocityKmS: optionalNumber(rvText),
      }, epoch);
      markers.push({ sourceId: id.trim(), ra: place.raDeg, dec: place.decDeg });
    } else {
      // Without a positive parallax, propagate angular proper motion alone.
      markers.push({ sourceId: id.trim(), ...tangentPlanePosition({ ra, dec }, east * years / 3_600_000, north * years / 3_600_000) });
    }
  }
  return { markers, limited: rows.length > GAIA_SOURCE_LIMIT };
}

export async function getGaiaMarkers(center: SkyCoord, corners: SkyCoord[], epoch: number, signal: AbortSignal) {
  const radius = footprintRadiusArcsec(center, corners);
  // Query outside the grid too so high proper-motion sources can move into it from J2016.0.
  const motionMargin = Math.max(30, 12 * Math.abs(epoch - GAIA_DR3_EPOCH) / JULIAN_YEAR_DAYS);
  const query = new URLSearchParams({
    '-source': 'I/355/gaiadr3',
    '-c': `${center.ra.toFixed(7)} ${center.dec.toFixed(7)}`,
    '-c.rs': (radius + motionMargin).toFixed(3),
    '-out': COLUMNS,
    '-sort': 'Gmag',
    '-out.max': String(GAIA_SOURCE_LIMIT + 1),
  });
  const response = await fetch(`${VIZIER_TSV}?${query}`, { signal });
  if (!response.ok) throw new Error(`Gaia DR3 service returned ${response.status}`);
  return readMarkers(await response.text(), epoch);
}
