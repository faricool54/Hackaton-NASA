import type { Grid, SkyCoord } from './types';
import { separationArcsec, tangentOffsetArcsec } from '../three/skyTrack';

const DEG = Math.PI / 180;

export function footprintRadiusArcsec(center: SkyCoord, corners: SkyCoord[]): number {
  const position = { raDeg: center.ra, decDeg: center.dec };
  return Math.max(...corners.map(({ ra, dec }) => separationArcsec(position, { raDeg: ra, decDeg: dec })));
}

/** Convert tangent-plane offsets in degrees to ICRS, including across RA = 0. */
export function tangentPlanePosition(center: SkyCoord, eastDeg: number, northDeg: number): SkyCoord {
  const east = eastDeg * DEG;
  const north = northDeg * DEG;
  const sinDec = Math.sin(center.dec * DEG);
  const cosDec = Math.cos(center.dec * DEG);
  const denominator = cosDec - north * sinDec;
  const ra = center.ra + Math.atan2(east, denominator) / DEG;
  const dec = Math.atan2(sinDec + north * cosDec, Math.hypot(denominator, east)) / DEG;
  return { ra: ((ra % 360) + 360) % 360, dec };
}

/**
 * True when `point` falls inside the footprint polygon (corners in order), tested on the tangent plane at `center`.
 * Footprints are a fraction of a degree, so anything more than 45° away is outside.
 */
export function pointInFootprint(center: SkyCoord, corners: SkyCoord[], point: SkyCoord): boolean {
  if (corners.length < 3) return false;
  const ref = { raDeg: center.ra, decDeg: center.dec };
  const plane = ({ ra, dec }: SkyCoord) => tangentOffsetArcsec(ref, { raDeg: ra, decDeg: dec });
  if (separationArcsec(ref, { raDeg: point.ra, decDeg: point.dec }) > 45 * 3600) return false;
  const { east: x, north: y } = plane(point);
  const polygon = corners.map(plane);
  let inside = false;
  for (let i = 0, j = polygon.length - 1; i < polygon.length; j = i++) {
    const a = polygon[i];
    const b = polygon[j];
    if ((a.north > y) !== (b.north > y) && x < (b.east - a.east) * (y - a.north) / (b.north - a.north) + a.east) inside = !inside;
  }
  return inside;
}

/** Corners of Errante's north-up TAN grid, at the outer FITS pixel edges. */
export function fieldFootprint(grid: Grid): SkyCoord[] | null {
  const { width_px: width, height_px: height, wcs } = grid;
  const { CTYPE1, CTYPE2, CRVAL1, CRVAL2, CRPIX1, CRPIX2, CDELT1, CDELT2 } = wcs;
  if (CTYPE1 !== 'RA---TAN' || CTYPE2 !== 'DEC--TAN' ||
    typeof CRVAL1 !== 'number' || typeof CRVAL2 !== 'number' ||
    typeof CRPIX1 !== 'number' || typeof CRPIX2 !== 'number' ||
    typeof CDELT1 !== 'number' || typeof CDELT2 !== 'number' ||
    ![width, height, CRVAL1, CRVAL2, CRPIX1, CRPIX2, CDELT1, CDELT2].every(Number.isFinite) ||
    width < 1 || height < 1 || Math.abs(CRVAL2) > 90 || CDELT1 >= 0 || CDELT2 <= 0) return null;

  const center = { ra: CRVAL1, dec: CRVAL2 };
  return [[0.5, 0.5], [width + 0.5, 0.5], [width + 0.5, height + 0.5], [0.5, height + 0.5]]
    .map(([x, y]) => tangentPlanePosition(center, (x - CRPIX1) * CDELT1, (y - CRPIX2) * CDELT2));
}
