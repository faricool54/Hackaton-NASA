// Small display helpers shared by components.

export function mjdToDate(mjd: number): Date {
  return new Date((mjd - 40587) * 86400000); // MJD 40587 = 1970-01-01
}

export function formatMjd(mjd: number): string {
  const d = mjdToDate(mjd);
  if (!Number.isFinite(d.getTime())) return `MJD ${Math.round(mjd).toLocaleString('en')}`;
  const year = d.getUTCFullYear();
  if (year < 0 || year > 9999) return `year ${year.toLocaleString('en')}`;
  return d.toISOString().replace('T', ' ').slice(0, 16) + ' UTC';
}

/** Elapsed model time, e.g. "+3.2 days" or "+1,250 years". */
export function formatElapsed(days: number): string {
  const sign = days < 0 ? '−' : '+';
  const a = Math.abs(days);
  if (a < 2) return `${sign}${(a * 24).toFixed(1)} h`;
  if (a < 730) return `${sign}${a.toFixed(1)} days`;
  return `${sign}${(a / 365.25).toLocaleString('en', { maximumFractionDigits: a < 36525 ? 1 : 0 })} years`;
}

export function formatDuration(hours: number): string {
  if (Math.abs(hours) < 48) return `${hours.toFixed(1)} h`;
  return `${(hours / 24).toFixed(1)} d`;
}

export function formatRaDec(ra: number, dec: number): string {
  return `${ra.toFixed(4)}°, ${dec >= 0 ? '+' : ''}${dec.toFixed(4)}°`;
}

export const DETECTOR_BANDS: Record<number, string> = {
  1: '0.75–1.11 µm',
  2: '1.11–1.64 µm',
  3: '1.64–2.42 µm',
  4: '2.42–3.82 µm',
  5: '3.82–4.42 µm',
  6: '4.42–5.00 µm',
};

export const STATUS_LABEL: Record<string, string> = {
  known: 'Known object',
  unconfirmed: 'Unconfirmed (not in catalogs)',
  artifact: 'Artifact (rejected)',
  injected: 'Simulated (test)',
};
