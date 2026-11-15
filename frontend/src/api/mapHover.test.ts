import { describe, expect, it, vi } from 'vitest';
import { readMarkers, type GaiaMarker } from './gaiaLayer';
import {
  atViewCentre, cardAnnouncement, createCursorStore, formatCursor, formatDecDms, formatDistance, formatEpochDate,
  formatParallax, formatProperMotion, formatRaHms, gaiaCard, MAP_TARGETS, parallaxDistancePc, placeCard,
  showcaseTargetId, snapToMarker, targetCard, targetId, totalProperMotionArcsecYr, validMarkerId, viewPixel, viewScaleDeg,
} from './mapHover';
import { pointInFootprint } from './skyFootprint';
import { SHOWCASE_TARGETS } from './showcase';
// Real VizieR CfA responses (I/355/gaiadr3), fetched on 2026-11-15 around Barnard's Star.
import brightTsv from './__fixtures__/vizier-gaiadr3-barnard-bright.tsv?raw';
import lowSnrTsv from './__fixtures__/vizier-gaiadr3-barnard-low-snr.tsv?raw';
import negativeTsv from './__fixtures__/vizier-gaiadr3-barnard-negative-plx.tsv?raw';

const EPOCH = 61116.6838019213; // median frame date of the Barnard's Star sequence
const stars = (tsv: string) => readMarkers(tsv, EPOCH).markers;
const barnard = stars(brightTsv)[0];
const card = (star: GaiaMarker, pinned = false) => gaiaCard(star, EPOCH, pinned);
const text = (star: GaiaMarker, pinned = false) => {
  const c = card(star, pinned);
  return [c.title, ...c.lines, c.footer].join('\n');
};

describe('distance only from a significant parallax', () => {
  it('uses 1/parallax for a positive parallax measured to better than 20 %', () => {
    expect(parallaxDistancePc(546.9759, 0.0401)).toBeCloseTo(1.82823, 4);
    expect(parallaxDistancePc(5.01, 1)).toBeCloseTo(199.6, 1);
  });

  it('refuses a distance at parallax/error ≤ 5, for zero or negative parallaxes and for missing values', () => {
    expect(parallaxDistancePc(5, 1)).toBeNull();
    expect(parallaxDistancePc(0.7617, 0.2798)).toBeNull(); // real row, parallax/error = 2.7
    expect(parallaxDistancePc(-0.4681, 0.2022)).toBeNull();
    expect(parallaxDistancePc(0, 0.1)).toBeNull();
    expect(parallaxDistancePc(1, 0)).toBeNull();
    expect(parallaxDistancePc(null, 0.1)).toBeNull();
    expect(parallaxDistancePc(1, null)).toBeNull();
  });

  it('formats the distance in pc below 1 kpc and in kpc above, with three significant digits', () => {
    expect(formatDistance(1.8282)).toBe('≈ 1.83 pc');
    expect(formatDistance(707.0)).toBe('≈ 707 pc');
    expect(formatDistance(3037.7)).toBe('≈ 3.04 kpc');
  });

  it('formats the parallax with the significant digits of its error', () => {
    expect(formatParallax(546.9759, 0.0401)).toBe('546.976 ± 0.040 mas');
    expect(formatParallax(0.7617, 0.2798)).toBe('0.76 ± 0.28 mas');
    expect(formatParallax(-0.4681, 0.2022)).toBe('−0.47 ± 0.20 mas');
  });

  it('gives a parallax that rounds to zero enough decimals to show its sign and first digit', () => {
    // Real row of the negative-parallax fixture: Plx −0.0039 ± 0.1666 mas, which toFixed(2) would print as "−0.00".
    expect(formatParallax(-0.0039, 0.1666)).toBe('−0.004 ± 0.167 mas');
    expect(formatParallax(0.0004, 0.0123)).toBe('0.0004 ± 0.0123 mas');
    expect(formatParallax(-0.00001, 0.17)).toBe('0.0000 ± 0.1700 mas');
    expect(formatParallax(0, 0.17)).toBe('0.00 ± 0.17 mas');
    expect(formatParallax(-0.0039, null)).toBe('−0.004 mas');
  });
});

describe('total proper motion', () => {
  it('adds pmRA·cos(Dec) and pmDec in quadrature and reports arcsec per year', () => {
    expect(totalProperMotionArcsecYr(-801.551, 10362.394)).toBeCloseTo(10.39335, 4);
    expect(totalProperMotionArcsecYr(3, 4)).toBeCloseTo(0.005, 9);
    expect(formatProperMotion(10.39335)).toBe('10.39″/yr');
    expect(formatProperMotion(0.0047862)).toBe('0.0048″/yr');
    expect(formatProperMotion(0.0921)).toBe('0.092″/yr');
  });
});

describe('Gaia DR3 hover card (from the real VizieR fixture)', () => {
  it("shows Barnard's Star with photometry, distance, motion, RV, the epoch and the honesty footer", () => {
    const c = card(barnard);
    expect(c.title).toBe('Gaia DR3 4472832130942575872');
    expect(c.lines).toEqual([
      'G 8.19 · BP−RP 2.83',
      'Parallax 546.976 ± 0.040 mas → ≈ 1.83 pc (1/parallax)',
      'Proper motion 10.39″/yr',
      'RV −110.5 km/s',
      'Position predicted for 2026-03-17 from Gaia DR3 proper motion',
    ]);
    expect(c.footer).toBe('Gaia DR3 catalog · not SPHEREx measurements · Click to select');
    expect(card(barnard, true).footer).toBe('Gaia DR3 catalog · not SPHEREx measurements · Selected');
  });

  it('never shows a temperature or a GSP-Phot distance (the object card owns them)', () => {
    for (const star of [...stars(brightTsv), ...stars(lowSnrTsv), ...stars(negativeTsv)]) {
      expect(text(star)).not.toMatch(/Teff|temperature|GSP|Dist\b/i);
      expect(text(star)).not.toMatch(/\d\s*K\b/);
      expect(text(star)).toContain('not SPHEREx');
    }
  });

  it('says the parallax is too uncertain instead of giving a distance', () => {
    const [uncertain] = stars(lowSnrTsv);
    expect(uncertain.sourceId).toBe('4472835841783121664');
    expect(card(uncertain).lines).toContain('Parallax 0.76 ± 0.28 mas');
    expect(card(uncertain).lines).toContain('Parallax too uncertain for a distance');
    expect(text(uncertain)).not.toMatch(/pc|1\/parallax/);
    const [negative] = stars(negativeTsv);
    expect(negative).toMatchObject({ sourceId: '4472835876142884224', parallax: -0.0039, parallaxError: 0.1666 });
    expect(card(negative).lines).toEqual(expect.arrayContaining(['Parallax −0.004 ± 0.167 mas', 'Parallax too uncertain for a distance']));
    expect(text(negative)).not.toMatch(/−0\.00\b/);
  });

  it('leaves out RV and colour when Gaia DR3 does not list them', () => {
    const noRv = stars(brightTsv).find(({ sourceId }) => sourceId === '4472832822422325632')!;
    expect(noRv.rv).toBeNull();
    expect(text(noRv)).not.toContain('RV');
    const noColour = { ...barnard, bpRp: null, gmag: null };
    expect(card(noColour).lines[0]).toMatch(/^Parallax/);
    expect(card({ ...barnard, parallax: null }).lines).toContain('No Gaia DR3 parallax · no distance');
  });
});

describe('challenge targets', () => {
  it('are the five showcase presets with short unique ids, the saved field id when showcase.ts has one', () => {
    expect(MAP_TARGETS).toHaveLength(SHOWCASE_TARGETS.length);
    expect(new Set(MAP_TARGETS.map(({ id }) => id)).size).toBe(SHOWCASE_TARGETS.length);
    for (const [k, target] of MAP_TARGETS.entries()) {
      const preset = SHOWCASE_TARGETS[k] as typeof SHOWCASE_TARGETS[number] & { fieldId?: string };
      expect(validMarkerId('targets', target.id)).toBe(true);
      expect(target.id).toBe(preset.fieldId ?? targetId(preset.name));
      expect(target).toEqual({ id: target.id, name: preset.name, ra: preset.ra, dec: preset.dec, mjd: preset.mjd });
    }
    expect(showcaseTargetId({ name: "Barnard's Star", fieldId: 'barnards-star' } as { name: string })).toBe('barnards-star');
    expect(showcaseTargetId({ name: "Barnard's Star" })).toBe('barnard-s-star');
    expect(showcaseTargetId({ name: 'x', fieldId: '<b>' } as { name: string })).toBe('x');
  });

  it('label the card as a challenge target whose position is dated and is not a detection', () => {
    const barnardTarget = MAP_TARGETS.find(({ name }) => name === "Barnard's Star")!;
    expect(barnardTarget.mjd).toBe(61104);
    const c = targetCard(barnardTarget);
    expect(c.title).toBe("Barnard's Star · Challenge target");
    // showcase.ts: Sesame/SIMBAD astrometry propagated to each target's mean SPHEREx epoch, not a catalog-epoch place.
    expect(c.lines).toEqual(['Position predicted for 2026-03-05 from SIMBAD astrometry · not a SPHEREx detection']);
    expect(c.footer).toBe('Click to open');
    expect(targetCard(barnardTarget, true).footer).toBe('Selected');
    for (const target of MAP_TARGETS) {
      expect(targetCard(target).lines.join(' ')).toMatch(/^Position predicted for \d{4}-\d{2}-\d{2} .*not a SPHEREx detection$/);
    }
  });

  it('announce a pinned card with all its text', () => {
    expect(cardAnnouncement(targetCard(MAP_TARGETS[0], true)))
      .toBe(`${MAP_TARGETS[0].name} · Challenge target. ${targetCard(MAP_TARGETS[0]).lines[0]}. Selected`);
    expect(cardAnnouncement(card(barnard, true))).toContain('not SPHEREx measurements');
  });
});

describe('dates and coordinates', () => {
  it('formats the prediction epoch as a UTC calendar date', () => {
    expect(formatEpochDate(61000)).toBe('2025-11-21');
    expect(formatEpochDate(EPOCH)).toBe('2026-03-17');
    expect(formatEpochDate(51544.5)).toBe('2000-01-01');
  });

  it('formats the cursor in sexagesimal with carries and a real minus sign', () => {
    expect(formatCursor({ ra: 269.44623, dec: 4.7687 })).toBe('RA 17h57m47.1s · Dec +04°46′07″');
    expect(formatRaHms(15 * (1 + 59 / 60 + 59.96 / 3600))).toBe('02h00m00.0s');
    expect(formatRaHms(359.999999)).toBe('00h00m00.0s');
    expect(formatRaHms(0)).toBe('00h00m00.0s');
    expect(formatDecDms(-12.5)).toBe('−12°30′00″');
    expect(formatDecDms(-0.00001)).toBe('+00°00′00″');
    expect(formatDecDms(89.99999)).toBe('+90°00′00″');
  });
});

describe('card geometry', () => {
  const bounds = { left: 0, top: 0, right: 956, bottom: 602 };
  const size = { width: 260, height: 150 };

  it('sits 14 px right of and below the cursor', () => {
    expect(placeCard({ x: 100, y: 100 }, size, bounds)).toEqual({ left: 114, top: 114, flipX: false, flipY: false });
  });

  it('flips to the left and above near the right and bottom edges', () => {
    expect(placeCard({ x: 900, y: 560 }, size, bounds)).toEqual({ left: 900 - 14 - 260, top: 560 - 14 - 150, flipX: true, flipY: true });
  });

  it('never leaves the map container, in all four corners and with offset bounds', () => {
    const box = { left: 40, top: 120, right: 40 + 956, bottom: 120 + 602 };
    for (const x of [box.left, box.left + 3, box.right - 3, box.right]) {
      for (const y of [box.top, box.top + 3, box.bottom - 3, box.bottom]) {
        const { left, top } = placeCard({ x, y }, size, box);
        expect(left).toBeGreaterThanOrEqual(box.left);
        expect(top).toBeGreaterThanOrEqual(box.top);
        expect(left + size.width).toBeLessThanOrEqual(box.right);
        expect(top + size.height).toBeLessThanOrEqual(box.bottom);
      }
    }
  });

  it('keeps the top left corner inside a container smaller than the card', () => {
    expect(placeCard({ x: 50, y: 50 }, { width: 400, height: 300 }, { left: 0, top: 0, right: 200, bottom: 100 }))
      .toMatchObject({ left: 0, top: 0 });
  });
});

describe('touch: snapping a tap to a marker', () => {
  // A 916×601 px map (FE-2 at 1366×650) showing 0.5° × 0.328° around Barnard's Star.
  const size = { width: 916, height: 601 };
  const view = { ra: 269.44623, dec: 4.7687, fov: 0.5, fovX: 0.5, fovY: 0.5 * 601 / 916 };
  const scale = 0.5 / 916; // degrees per pixel
  const star = { layer: 'gaia' as const, id: '4472832130942575872', ra: 269.4463725391953, dec: 4.768815881735359 };
  // East is to the left: `px` pixels to the right of `point` is west, a smaller RA.
  const right = (point: { ra: number; dec: number }, px: number) =>
    ({ ra: point.ra - px * scale / Math.cos(point.dec * Math.PI / 180), dec: point.dec });

  it('uses the horizontal field of view per pixel, or the larger side without it', () => {
    expect(viewScaleDeg(view, size)).toBeCloseTo(scale, 12);
    expect(viewScaleDeg({ ra: 0, dec: 0, fov: 0.5 }, size)).toBeCloseTo(scale, 12);
    expect(viewScaleDeg({ ra: 0, dec: 0, fov: 0.5 }, { width: 0, height: 0 })).toBeNaN();
  });

  it('places the view centre in the middle, east to the left and north up', () => {
    expect(viewPixel(view, size, view)).toEqual({ x: 458, y: 300.5 });
    const point = viewPixel(view, size, right(view, 100));
    expect(point.x).toBeCloseTo(558, 1);
    expect(point.y).toBeCloseTo(300.5, 1);
    expect(viewPixel(view, size, { ra: view.ra, dec: view.dec + 50 * scale }).y).toBeCloseTo(250.5, 1);
  });

  it('snaps to the nearest marker within 15 px, and to nothing beyond', () => {
    const target = { layer: 'targets' as const, id: 'barnard-s-star', ...right(star, 10) };
    const tap = right(star, -4); // 4 px left of the Gaia marker and 14 px from the target square
    const snapped = snapToMarker(tap, [target, star], view, size);
    expect(snapped?.marker).toBe(star);
    expect(snapped?.x).toBeCloseTo(viewPixel(view, size, star).x, 6);
    expect(snapToMarker(right(star, 14.5), [star], view, size)?.marker).toBe(star);
    expect(snapToMarker(right(star, 16), [star], view, size)).toBeNull();
    expect(snapToMarker(tap, [], view, size)).toBeNull();
    // Zoomed out 4×: the same sky offset is 4× fewer pixels and snaps.
    expect(snapToMarker(right(star, 40), [star], { ...view, fov: 2, fovX: 2, fovY: 4 * view.fovY }, size)?.marker).toBe(star);
  });
});

describe('map helpers', () => {
  it('detects a point inside the sequence footprint, also across RA = 0', () => {
    const center = { ra: 269.44623, dec: 4.7687 };
    const corners = [{ ra: 269.52, dec: 4.69 }, { ra: 269.37, dec: 4.69 }, { ra: 269.37, dec: 4.84 }, { ra: 269.52, dec: 4.84 }];
    expect(pointInFootprint(center, corners, center)).toBe(true);
    expect(pointInFootprint(center, corners, { ra: 269.53, dec: 4.7687 })).toBe(false);
    expect(pointInFootprint(center, corners, { ra: 89.4, dec: -4.7 })).toBe(false);
    const wrap = [{ ra: 0.05, dec: -0.05 }, { ra: 359.95, dec: -0.05 }, { ra: 359.95, dec: 0.05 }, { ra: 0.05, dec: 0.05 }];
    expect(pointInFootprint({ ra: 0, dec: 0 }, wrap, { ra: 359.99, dec: 0.01 })).toBe(true);
    expect(pointInFootprint({ ra: 0, dec: 0 }, wrap, { ra: 0.06, dec: 0 })).toBe(false);
    expect(pointInFootprint(center, corners.slice(0, 2), center)).toBe(false);
  });

  it('knows when the map is centred on a marker', () => {
    expect(atViewCentre({ ra: 269.4463725391953, dec: 4.768815881735359 }, { ra: 269.4463725391953 + 1e-9, dec: 4.768815881735359 })).toBe(true);
    expect(atViewCentre({ ra: 269.44, dec: 4.76 }, { ra: 269.4463, dec: 4.7688 })).toBe(false);
  });

  it('notifies the cursor readout only when the cursor moves', () => {
    const store = createCursorStore();
    const listener = vi.fn();
    const stop = store.subscribe(listener);
    store.set({ ra: 1, dec: 2 });
    store.set({ ra: 1, dec: 2 });
    store.set(null);
    store.set(null);
    expect(listener).toHaveBeenCalledTimes(2);
    stop();
    store.set({ ra: 3, dec: 4 });
    expect(listener).toHaveBeenCalledTimes(2);
    expect(store.get()).toEqual({ ra: 3, dec: 4 });
  });
});
