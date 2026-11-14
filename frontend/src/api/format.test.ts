import { describe, expect, it } from 'vitest';
import { formatElapsed, formatMjd } from './format';

describe('formatMjd', () => {
  it('formats normal dates', () => {
    expect(formatMjd(61000)).toBe('2025-11-21 00:00 UTC');
  });

  it('never throws for model times far outside the calendar range', () => {
    expect(formatMjd(40587 + 365.25 * 12000)).toBe('year 13,970');
    expect(formatMjd(1e12)).toMatch(/^MJD /);
  });
});

describe('formatElapsed', () => {
  it('picks a readable unit', () => {
    expect(formatElapsed(0.5)).toBe('+12.0 h');
    expect(formatElapsed(10)).toBe('+10.0 days');
    expect(formatElapsed(365.25 * 1250)).toBe('+1,250 years');
  });
});
