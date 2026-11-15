import type { ComparisonImage, Field, SpectralMeasurement, SpectrumResponse } from './types';

export function plotMeasurements(points: SpectralMeasurement[]) {
  return points.filter((p) => p.usable && p.wavelength_um !== null && Number.isFinite(p.wavelength_um)
    && p.flux !== null && Number.isFinite(p.flux));
}

export function comparisonSelection(field: Field, detector: number, from: string, to: string): string[] {
  const lower = from ? Date.parse(`${from}T00:00:00Z`) / 86400000 + 40587 : -Infinity;
  const upper = to ? Date.parse(`${to}T00:00:00Z`) / 86400000 + 40588 : Infinity;
  if (Number.isNaN(lower) || Number.isNaN(upper) || lower >= upper) throw new Error('Choose an ordered UTC date range.');
  const selected = field.frames.filter((f) => (!detector || f.detector === detector) && f.mjd >= lower && f.mjd < upper);
  if (selected.length < 2) throw new Error('Choose at least two frames.');
  if (selected.length > 60) throw new Error('Narrow the date range or detector: at most 60 frames can be compared.');
  return selected.map((f) => f.id);
}

export function comparisonTitle(image: ComparisonImage): string {
  return image.kind === 'weighted_mean' ? `D${image.detector} · season ${image.season} weighted mean`
    : `D${image.detector} · ${image.later} − ${image.flux_scale?.toFixed(3)} × ${image.earlier}`;
}

export type SpectrumSource = SpectrumResponse['source'];

/** Labels of the two spectrum sources (FE-8: shared by the options menu and the result summary). */
export const SPECTRUM_SOURCE_LABELS: Record<SpectrumSource, string> = {
  dr1_cube: 'DR1 cube · static quick look',
  l2_exposures: 'L2 exposures · aperture photometry',
};

/** The honesty legend of each source; it must stay visible next to any plot of that source. */
export function spectrumCaveat(source: SpectrumSource): string {
  return source === 'dr1_cube'
    ? 'Static surface brightness (MJy/sr), without background subtraction or flux errors. Saturated cores can be missing.'
    : 'Background-subtracted aperture flux (mJy) at each exposure date. Wavelength and time vary together; do not interpret a mixed-epoch curve as a simultaneous spectrum.';
}

/** One-line result summary: "N usable / M measured points · K failed inputs". */
export function spectrumSummary(result: Pick<SpectrumResponse, 'points' | 'failures'>): string {
  return `${result.points.filter((p) => p.usable).length} usable / ${result.points.length} measured points · `
    + `${result.failures.length} failed inputs`;
}
