// Pure text helpers for the body panel (no React, no WebGL) so they can be unit-tested.
import type { Orbit, SystemModel, Variability, VariabilityKind } from '../api/types';

/** Variability kinds whose `amplitude_mag` is a repeating peak-to-peak swing. */
const PERIODIC_KINDS: ReadonlySet<VariabilityKind> = new Set<VariabilityKind>(['pulsation', 'rotation']);

/** Round to 2 significant figures and format with thousands separators (59648 -> "60,000"). */
export function twoSigFigs(x: number): string {
  return x.toLocaleString('en', { maximumSignificantDigits: 2 });
}

export function formatAu(au: number): string {
  if (au < 0.1) return `${au.toFixed(4)} AU (${Math.round(au * 1.496e8).toLocaleString('en')} km)`;
  return `${au.toLocaleString('en', { maximumFractionDigits: 2 })} AU`;
}

/**
 * Human-readable period. `approx` (used for orbits that are not fitted solutions) rounds to
 * 2 significant figures and prefixes "~", so an assumed orbit does not look like a measurement.
 */
export function formatPeriod(days: number, approx = false): string {
  if (days < 2) {
    const hours = days * 24;
    return approx ? `~${twoSigFigs(hours)} hours` : `${hours.toFixed(1)} hours`;
  }
  if (days < 730) return approx ? `~${twoSigFigs(days)} days` : `${days.toFixed(1)} days`;
  const years = days / 365.25;
  return approx ? `~${twoSigFigs(years)} years` : `${years.toLocaleString('en', { maximumFractionDigits: 1 })} years`;
}

/** True when the orbit is not a published fitted solution (absent quality = 'fitted', per types.ts). */
export function isNonFittedOrbit(orbit: Orbit): boolean {
  return orbit.quality !== undefined && orbit.quality !== 'fitted';
}

/** Orbital period text; non-fitted orbits are rounded to 2 significant figures with "~". */
export function formatOrbitPeriod(orbit: Orbit): string {
  return formatPeriod(orbit.period_days, isNonFittedOrbit(orbit));
}

function bandSuffix(band: string | null): string {
  const b = band?.trim();
  if (!b) return '';
  return /\bband$/i.test(b) ? ` in ${b}` : ` in ${b} band`;
}

/**
 * Amplitude in mag: one decimal from 0.1 mag up, 2 significant digits below, so a millimag-level
 * catalog amplitude (a VSX BY Dra 0.02 mag) never reads as 0.
 */
export function formatAmplitude(mag: number): string {
  return Math.abs(mag) >= 0.1
    ? mag.toLocaleString('en', { maximumFractionDigits: 1 })
    : mag.toLocaleString('en', { maximumSignificantDigits: 2 });
}

/**
 * One-line variability summary. `amplitude_mag` is the full range (as in the facts, e.g. "Visual
 * range 6.7-13.2 mag" = 6.5 mag), so periodic kinds say "peak-to-peak" and irregular / accretion /
 * eclipse kinds say "dims by up to"; the photometric band is always shown when known.
 */
export function variabilityText(v: Variability): string {
  const parts: string[] = [v.kind];
  if (v.period_days) parts.push(`every ${formatPeriod(v.period_days)}`);
  if (v.amplitude_mag) {
    const amp = `${formatAmplitude(v.amplitude_mag)} mag`;
    const band = bandSuffix(v.band);
    parts.push(PERIODIC_KINDS.has(v.kind) ? `${amp} peak-to-peak${band}` : `dims by up to ${amp}${band}`);
  }
  return parts.join(', ');
}

/**
 * How the 3D view renders this variability, in both clocks: free-running = variabilityFactor in
 * orbits.ts (a sinusoid, arbitrary phase); Dataset time = a tabulated dating where one exists
 * (ephemerides.ts, R Dra: measured maxima inside the SPHEREx window, the catalogue ephemeris outside),
 * otherwise the mean. Generic on purpose: this module is in the main chunk
 * and must not import the ephemeris table; the drawing notes give the per-body details.
 */
export function variabilityAnimationNote(v: Variability): string | null {
  if (!v.amplitude_mag) return null;
  return v.period_days
    ? 'Free-running, the 3D view animates its glow as a simple sinusoid with an arbitrary phase (not a prediction for a date); the radius stays constant, because no size change is measured. In Dataset time it follows a tabulated dating (measured maxima or a catalogue ephemeris) where one exists (see How this body is drawn), otherwise it is held at the mean.'
    : 'Not animated in the 3D view (no periodic model).';
}

/**
 * True unless the system has at least one fact and every fact is verified. The model parameters
 * (temperature, orbit, variability) were typed alongside those facts, so they share their status.
 */
export function modelValuesUnverified(system: SystemModel): boolean {
  const facts = system.bodies.flatMap((b) => b.facts);
  return facts.length === 0 || facts.some((f) => !f.verified);
}
