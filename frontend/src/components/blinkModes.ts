// Image modes of the blink viewer (WS5): single SPHEREx exposures in grayscale, or the
// false-color season composites of contract 0.3.1 (Field.composites, built by WS2).
import type { Composite, CompositeChannel, CompositeColor, CompositeMode } from '../api/types';
import { formatMjd } from '../api/format';

export type BlinkMode = 'bw' | CompositeMode;

export const BLINK_MODES: { mode: BlinkMode; label: string }[] = [
  { mode: 'bw', label: 'B/W' },
  { mode: 'detectors', label: 'Color · detectors' },
  { mode: 'jhk', label: 'Color · J/H/K' },
];

const DESCRIPTION: Record<BlinkMode, string> = {
  bw: 'Single SPHEREx exposures in grayscale, one infrared wavelength each',
  detectors: 'False color, full range: three SPHEREx detectors from 0.75 to 5.0 µm, one image per season',
  jhk: 'False color, 2MASS-like: exposures near J, H and Ks (~1.25 / 1.65 / 2.17 µm), one image per season',
};

const UNAVAILABLE: Record<CompositeMode, string> = {
  detectors: 'no season of this field has usable frames for all three detector channels',
  jhk: 'no season of this field has exposures near all of J, H and Ks',
};

/** Composites of one mode, in season order. Products older than contract 0.3.1 have none. */
export function compositesForMode(composites: Composite[] | undefined, mode: CompositeMode): Composite[] {
  return (composites ?? []).filter((c) => c.mode === mode).sort((a, b) => a.season - b.season || a.mjd_min - b.mjd_min);
}

export function isModeAvailable(mode: BlinkMode, composites: Composite[] | undefined): boolean {
  return mode === 'bw' || compositesForMode(composites, mode).length > 0;
}

/** The mode actually shown: a mode this field has no composites for falls back to B/W. */
export function effectiveMode(mode: BlinkMode, composites: Composite[] | undefined): BlinkMode {
  return isModeAvailable(mode, composites) ? mode : 'bw';
}

/** Visible hint under the mode buttons: what the shown mode is, then why any mode is unavailable. */
export function modeHints(mode: BlinkMode, composites: Composite[] | undefined): string[] {
  const shown = effectiveMode(mode, composites);
  const missing = BLINK_MODES.filter(({ mode: m }) => !isModeAvailable(m, composites)).map(
    ({ mode: m, label }) => `${label}: ${modeTitle(m, composites).replace(/^Not available: /, 'not available, ')}.`,
  );
  return [`${modeTitle(shown, composites)}.`, ...missing];
}

/** Tooltip of a mode button. For a disabled mode it says why there is nothing to show. */
export function modeTitle(mode: BlinkMode, composites: Composite[] | undefined): string {
  if (mode === 'bw') return DESCRIPTION.bw;
  const n = compositesForMode(composites, mode).length;
  if (n > 0) return `${DESCRIPTION[mode]} (${n} season${n === 1 ? '' : 's'})`;
  if (!composites?.length) {
    return 'Not available: color needs frames from several detectors and this sequence has none'
      + ' (build it with "All detectors · color" to get color)';
  }
  return `Not available: ${UNAVAILABLE[mode]}`;
}

const LETTER: Record<CompositeColor, string> = { red: 'R', green: 'G', blue: 'B' };

/** e.g. "R 4.60 µm (D6)": mean wavelength at the field centre and detector of one channel. */
export function channelLabel(ch: CompositeChannel): string {
  const wavelength = ch.wavelength_um == null ? 'λ n/a' : `${ch.wavelength_um.toFixed(2)} µm`;
  const detector = ch.detector == null ? 'mixed detectors' : `D${ch.detector}`;
  return `${LETTER[ch.color]} ${wavelength} (${detector})`;
}

/** Channels come red, green, blue (order checked by the contract). */
export function channelLegend(c: Composite): string {
  return c.channels.map(channelLabel).join(' · ');
}

const day = (mjd: number) => formatMjd(mjd).replace(/ \d{2}:\d{2} UTC$/, '');

/** Dates of the first and last exposure that went into a season composite. */
export function seasonRange(c: Composite): string {
  const [first, last] = [day(c.mjd_min), day(c.mjd_max)];
  return first === last ? first : `${first} – ${last}`;
}
