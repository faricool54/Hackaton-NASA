import type { ComparisonImage, Field, SpectralMeasurement } from './types';

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
