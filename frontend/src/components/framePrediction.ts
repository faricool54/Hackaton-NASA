import type { Grid } from '../api/types';
import { astrometricPlace, separationArcsec, tangentOffsetArcsec, type AstrometricSolution } from '../three/skyTrack';

/** Predict a position for Errante's north-up TAN grid, in image-edge coordinates. */
export function predictedFramePixel(grid: Grid, astrometry: AstrometricSolution, mjd: number) {
  const wcs = grid.wcs;
  if (wcs.CTYPE1 !== 'RA---TAN' || wcs.CTYPE2 !== 'DEC--TAN' ||
    (wcs.CUNIT1 ?? 'deg') !== 'deg' || (wcs.CUNIT2 ?? 'deg') !== 'deg' ||
    Object.keys(wcs).some((key) => /^(PC|CD)\d+_\d+$|^CROTA/.test(key))) return null;

  const { CRVAL1, CRVAL2, CRPIX1, CRPIX2, CDELT1, CDELT2 } = wcs;
  if (typeof CRVAL1 !== 'number' || typeof CRVAL2 !== 'number' ||
    typeof CRPIX1 !== 'number' || typeof CRPIX2 !== 'number' ||
    typeof CDELT1 !== 'number' || typeof CDELT2 !== 'number' ||
    ![CRVAL1, CRVAL2, CRPIX1, CRPIX2, CDELT1, CDELT2, mjd].every(Number.isFinite) ||
    CDELT1 >= 0 || CDELT2 <= 0 || !(astrometry.parallaxMas > 0)) return null;

  const place = astrometricPlace(astrometry, mjd);
  const reference = { raDeg: CRVAL1, decDeg: CRVAL2 };
  // Restrict to the near side of the tangent plane; TAN mirrors the opposite hemisphere.
  if (separationArcsec(reference, place) >= 90 * 3600) return null;
  const { east, north } = tangentOffsetArcsec(reference, place);
  // FITS uses one-based pixel centres and y up. The rendered image has its origin at the top-left edge.
  const x = CRPIX1 - 0.5 + east / (3600 * CDELT1);
  const y = grid.height_px + 0.5 - CRPIX2 - north / (3600 * CDELT2);
  return x >= 0 && x < grid.width_px && y >= 0 && y < grid.height_px ? { x, y } : null;
}
