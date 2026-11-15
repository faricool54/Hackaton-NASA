import { describe, expect, it } from 'vitest';
import { julianEpochToMjd } from '../three/skyTrack';
import { predictedFramePixel } from './framePrediction';

const grid = {
  center: { ra: 269.44623, dec: 4.7687 },
  width_px: 88,
  height_px: 88,
  pixel_scale_arcsec: 6.15,
  wcs: {
    CTYPE1: 'RA---TAN', CTYPE2: 'DEC--TAN', CRVAL1: 269.44623, CRVAL2: 4.7687,
    CRPIX1: 44.5, CRPIX2: 44.5, CDELT1: -6.15 / 3600, CDELT2: 6.15 / 3600,
  },
};
const barnard = {
  raDeg: 269.44850252543836, decDeg: 4.739420051112412, epochMjd: julianEpochToMjd(2016),
  pmRaCosDecMasYr: -801.551, pmDecMasYr: 10362.394, parallaxMas: 546.976, radialVelocityKmS: -110.47,
};

describe('frame prediction', () => {
  // Reference values from Astropy: Gaia DR3 space motion, Earth ephemeris and the published field's WCS.
  it.each([
    [60905.8569073, 44.00478, 44.87974],
    [61281.662753423, 44.14675, 43.15057],
  ])('matches the Barnard field reference at MJD %s', (mjd, x, y) => {
    const pixel = predictedFramePixel(grid, barnard, mjd);
    expect(pixel?.x).toBeCloseTo(x, 2);
    expect(pixel?.y).toBeCloseTo(y, 2);
  });

  it('hides the reticle on unsupported grids or for a target outside the field', () => {
    expect(predictedFramePixel({ ...grid, wcs: {} }, barnard, 60905.8569073)).toBeNull();
    expect(predictedFramePixel(grid, { ...barnard, raDeg: 1 }, 60905.8569073)).toBeNull();
  });
});
