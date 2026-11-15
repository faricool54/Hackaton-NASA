import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';
import type { SystemModel } from '../api/types';
import { SkyTrackPanel } from './SkyTrackPanel';
import { isoDateToMjd } from './spherexCoverage';
import {
  astrometricPlace,
  barycentricFromGeocentric,
  buildSkyTrack,
  earthPositionAu,
  eclipticLatitudeDeg,
  formatArcsec,
  formatPlace,
  formatPx,
  gridValues,
  julianEpochToMjd,
  niceStep,
  parseEpoch,
  plotLayout,
  PLOT_MAX_HEIGHT,
  PLOT_MIN_HEIGHT,
  positionAngleDeg,
  separationArcsec,
  SKY_TRACK_CAPTION,
  SPHEREX_PIXEL_ARCSEC,
  SUN_BARYCENTRE_MAX_AU,
  tangentOffsetArcsec,
  trackAstrometry,
  trackPointAt,
  TRACK_SOURCES,
  type AstrometricSolution,
  type RaDec,
  type Vec3,
} from './skyTrack';

// Every demo system shipped with the site (the same JSON the pipeline writes).
const SYSTEMS = Object.values(
  import.meta.glob<SystemModel>('../../../data/demo/systems/*.json', { eager: true, import: 'default' }),
);
const system = (id: string): SystemModel => {
  const s = SYSTEMS.find((x) => x.id === id);
  if (!s) throw new Error(`demo system ${id} missing`);
  return s;
};
const astrometry = (id: string): AstrometricSolution => {
  const a = trackAstrometry(system(id));
  if (!a) throw new Error(`no astrometry for ${id}`);
  return a;
};
const at = (raDeg: number, decDeg: number): RaDec => ({ raDeg, decDeg });

/** J2026.0 = JD 2461041.5 (TT); the RECON "2026.0" positions are for this epoch. */
const J2026 = julianEpochToMjd(2026.0);

describe('epochs', () => {
  it('reads Julian epoch labels', () => {
    expect(parseEpoch('J2016.0')).toBe(57388.5);
    expect(parseEpoch('J2000')).toBe(51544.5);
    expect(parseEpoch('J2016.67')).toBeCloseTo(57633.2175, 6);
    expect(J2026).toBe(61041);
    for (const bad of [null, undefined, '', '2016.0', 'B1950.0', 'J20x6']) expect(parseEpoch(bad)).toBeNull();
  });

  it('uses the exact Kirkpatrick et al. 2021 epoch for WISE 0855, not the rounded label', () => {
    expect(system('wise-0855').motion?.epoch).toBe('J2016.67');
    expect(astrometry('wise-0855').epochMjd).toBe(57633.39);
  });
});

describe('Earth position (Astronomical Almanac low-precision Sun)', () => {
  // ERFA epv00 (astropy 8.0.2, erfa.epv00(2400000.5, mjd)), AU, BCRS axes: [heliocentric, barycentric].
  const EPV00: [number, Vec3, Vec3][] = [
    [60789.75, [-0.829469, -0.522074, -0.226305], [-0.834374, -0.526956, -0.228241]],
    [60926.0, [0.974342, -0.235246, -0.101981], [0.970435, -0.240338, -0.104028]],
    [61041.0, [-0.174282, 0.887925, 0.384898], [-0.177348, 0.882796, 0.382818]],
    [61137.5, [-0.955603, -0.273344, -0.118481], [-0.957988, -0.278411, -0.120548]],
    [61358.0, [0.619365, 0.708076, 0.306934], [0.618384, 0.703433, 0.305018]],
  ];
  const dist = (a: Vec3, b: Vec3) => Math.hypot(a[0] - b[0], a[1] - b[1], a[2] - b[2]);

  it('matches the heliocentric Earth of ERFA epv00 within 0.0003 AU and 0.012 deg', () => {
    for (const [mjd, helio] of EPV00) {
      const e = earthPositionAu(mjd);
      expect(dist(e, helio)).toBeLessThan(3e-4);
      const cos = (e[0] * helio[0] + e[1] * helio[1] + e[2] * helio[2]) / (Math.hypot(...e) * Math.hypot(...helio));
      expect((Math.acos(Math.min(1, cos)) * 180) / Math.PI).toBeLessThan(0.012);
    }
  });

  it('is within the documented Sun-barycentre bound of the barycentric Earth', () => {
    for (const [mjd, helio, bary] of EPV00) {
      expect(dist(helio, bary)).toBeLessThan(SUN_BARYCENTRE_MAX_AU);
      expect(dist(earthPositionAu(mjd), bary)).toBeLessThan(SUN_BARYCENTRE_MAX_AU + 3e-4);
    }
  });
});

describe('angles', () => {
  it('separations and tangent-plane offsets agree at small scales', () => {
    const a = at(269.4462952, 4.7681531);
    const b = at(269.4459, 4.7707);
    const o = tangentOffsetArcsec(a, b);
    expect(Math.hypot(o.east, o.north)).toBeCloseTo(separationArcsec(a, b), 6);
    expect(o.north).toBeGreaterThan(0);
    expect(o.east).toBeLessThan(0); // smaller RA = west
    expect(separationArcsec(a, a)).toBe(0);
  });

  it('position angles run north through east', () => {
    expect(positionAngleDeg({ east: 0, north: 1 })).toBe(0);
    expect(positionAngleDeg({ east: 1, north: 0 })).toBe(90);
    expect(positionAngleDeg({ east: -1, north: 0 })).toBe(270);
  });

  it('ecliptic latitudes of the targets', () => {
    // astropy BarycentricTrueEcliptic: Barnard +28.18, Eps Ind B -41.48, WISE 0855 -23.61 deg.
    expect(eclipticLatitudeDeg(at(269.4485, 4.7394))).toBeCloseTo(28.18, 1);
    expect(eclipticLatitudeDeg(at(331.0765, -56.7938))).toBeCloseTo(-41.48, 1);
    expect(eclipticLatitudeDeg(at(133.781, -7.2439))).toBeCloseTo(-23.61, 1);
  });
});

describe('catalog astrometry against docs/RECON_SPHEREX.md 4.1', () => {
  it('the demo systems carry the Gaia DR3 positions RECON lists', () => {
    // RECON 4.1 gives 7 decimals (0.36 mas).
    expect(separationArcsec(at(system('barnards-star').center.ra, system('barnards-star').center.dec), at(269.4485025, 4.7394201))).toBeLessThan(0.001);
    expect(separationArcsec(at(system('r-draconis').center.ra, system('r-draconis').center.dec), at(248.1673784, 66.7550067))).toBeLessThan(0.001);
  });

  it("reproduces Barnard's Star at 2026.0 (geocentric) within 0.01 arcsec", () => {
    const p = astrometricPlace(astrometry('barnards-star'), J2026);
    expect(separationArcsec(p, at(269.4462952, 4.7681531))).toBeLessThan(0.01);
  });

  it('reproduces Epsilon Indi B at 2026.0 (geocentric) within 0.01 arcsec', () => {
    const a = astrometry('epsilon-indi');
    expect(separationArcsec(astrometricPlace(a, J2026), at(331.0965591, -56.8006419))).toBeLessThan(0.01);
  });

  it('reproduces R Dra and RW Aur B at 2026.0 (geocentric) within 0.01 arcsec', () => {
    expect(separationArcsec(astrometricPlace(astrometry('r-draconis'), J2026), at(248.1672335, 66.7550235))).toBeLessThan(0.01);
    // RECON's RW Aur row is B's own Gaia DR3 position (156430822114424576) with the system motion.
    const m = system('rw-aurigae').motion!;
    const b: AstrometricSolution = {
      raDeg: 76.9560812,
      decDeg: 30.4012046,
      epochMjd: 57388.5,
      pmRaCosDecMasYr: m.pm_ra_cosdec_mas_yr!,
      pmDecMasYr: m.pm_dec_mas_yr!,
      parallaxMas: m.parallax_mas!,
      radialVelocityKmS: m.radial_velocity_km_s,
    };
    expect(separationArcsec(astrometricPlace(b, J2026), at(76.9560889, 30.4011286))).toBeLessThan(0.01);
  });

  it('reproduces the barycentric 2025.6 / 2026.2 / 2026.7 lists (5 decimals)', () => {
    const barnard = astrometry('barnards-star');
    const lists: [number, number, number][] = [
      [2025.6, 269.44636, 4.76705],
      [2026.2, 269.44622, 4.76878],
      [2026.7, 269.44611, 4.77022],
    ];
    for (const [y, ra, dec] of lists) {
      const mjd = julianEpochToMjd(y);
      // RECON's lists leave the radial velocity out: they match to the 5-decimal rounding without it...
      const noRv = astrometricPlace(barnard, mjd, { observer: 'barycentric', radialVelocity: false });
      expect(separationArcsec(noRv, at(ra, dec))).toBeLessThan(0.03);
      // ...and the perspective acceleration of the -110 km/s radial velocity adds 0.07 arcsec.
      const withRv = astrometricPlace(barnard, mjd, { observer: 'barycentric' });
      expect(separationArcsec(withRv, at(ra, dec))).toBeGreaterThan(0.04);
      expect(separationArcsec(withRv, at(ra, dec))).toBeLessThan(0.1);
    }
    const epsB = astrometry('epsilon-indi');
    for (const [y, ra, dec] of [
      [2025.6, 331.09585, -56.80039],
      [2026.7, 331.09807, -56.80114],
    ] as const) {
      const p = astrometricPlace(epsB, julianEpochToMjd(y), { observer: 'barycentric' });
      expect(separationArcsec(p, at(ra, dec))).toBeLessThan(0.03);
    }
  });

  it("reproduces RECON's WISE 0855 vector for 2026-11-14 from RECON's own fit", () => {
    // RECON 4.1: 2026.0 geocentric 133.7598387, -7.2421674; mu ~ (-8095, +696) mas/yr; parallax ~440 mas.
    const plx = 440;
    const bary = barycentricFromGeocentric(at(133.7598387, -7.2421674), plx, J2026);
    const own: AstrometricSolution = {
      ...bary,
      epochMjd: J2026,
      pmRaCosDecMasYr: -8095,
      pmDecMasYr: 696,
      parallaxMas: plx,
      radialVelocityKmS: null,
    };
    expect(separationArcsec(astrometricPlace(own, J2026), at(133.7598387, -7.2421674))).toBeLessThan(0.001);
    expect(separationArcsec(astrometricPlace(own, isoDateToMjd('2026-11-14')), at(133.757926, -7.24198))).toBeLessThan(0.05);
  });

  it('the Kirkpatrick et al. 2021 track is 0.31 arcsec (0.05 px) from that vector, as the panel says', () => {
    const d = separationArcsec(astrometricPlace(astrometry('wise-0855'), isoDateToMjd('2026-11-14')), at(133.757926, -7.24198));
    expect(d).toBeCloseTo(0.31, 1);
    expect(Math.abs(d - 0.31)).toBeLessThan(0.02);
    expect((d / SPHEREX_PIXEL_ARCSEC).toFixed(2)).toBe('0.05');
    expect(TRACK_SOURCES['wise-0855'].notes.some((n) => n.includes('0.31″ (0.05 px)'))).toBe(true);
  });

  it("Barnard's Star moves 15.7 arcsec = 2.56 px from 2025-05-01 to 2026-11-14 (RECON 4.1)", () => {
    const a = astrometry('barnards-star');
    const d = separationArcsec(astrometricPlace(a, isoDateToMjd('2025-05-01')), astrometricPlace(a, isoDateToMjd('2026-11-14')));
    expect(Math.abs(d - 15.7)).toBeLessThan(0.05);
    expect((d / SPHEREX_PIXEL_ARCSEC).toFixed(2)).toBe('2.56');
  });

  it('proper motions in px per year match the RECON table', () => {
    expect(buildSkyTrack(system('barnards-star'))!.pmPxPerYr.toFixed(2)).toBe('1.69');
    expect(buildSkyTrack(system('epsilon-indi'))!.pmPxPerYr.toFixed(2)).toBe('0.76');
  });
});

describe('Epsilon Indi: the track follows B, not the system centre (A)', () => {
  it("uses B's Gaia DR3 solution as a WS7 constant", () => {
    const a = trackAstrometry(system('epsilon-indi'))!;
    expect(a.origin).toBe('ws7-constant');
    expect(a.target).toContain('Epsilon Indi B');
    expect(a.source).toContain('6412596012146801152');
    // A (the centre) is 402.6 arcsec west of B (RECON 4.3).
    const s = system('epsilon-indi');
    expect(separationArcsec(at(s.center.ra, s.center.dec), a)).toBeCloseTo(402.6, -1);
  });

  it("A's radial velocity would change B's places by less than 0.01 arcsec (the note's claim)", () => {
    const b = astrometry('epsilon-indi');
    const withA = { ...b, radialVelocityKmS: -40.43 };
    for (let mjd = 60789.75; mjd <= 61358; mjd += 7) {
      expect(separationArcsec(astrometricPlace(b, mjd), astrometricPlace(withA, mjd))).toBeLessThan(0.01);
    }
    expect(TRACK_SOURCES['epsilon-indi'].notes.some((n) => n.includes('less than 0.01″'))).toBe(true);
  });

  it('the photocentre bound in the note is a(1+e) of the Chen et al. 2022 orbit', () => {
    const bb = system('epsilon-indi').bodies.find((b) => b.id === 'eps-indi-bb')?.orbit;
    expect(bb).toBeTruthy();
    const aArcsec = bb!.semi_major_axis_au / 3.638; // AU / pc = arcsec
    expect((aArcsec * (1 + bb!.eccentricity)).toFixed(2)).toBe('1.02');
    expect(((aArcsec * (1 + bb!.eccentricity)) / SPHEREX_PIXEL_ARCSEC).toFixed(2)).toBe('0.17');
  });
});

describe('buildSkyTrack', () => {
  const withMotion = SYSTEMS.filter((s) => s.motion);

  it('builds a track for every demo system with a SpaceMotion and none for the synthetic one', () => {
    expect(withMotion.length).toBeGreaterThanOrEqual(5);
    for (const s of withMotion) {
      const t = buildSkyTrack(s);
      expect(t, s.id).not.toBeNull();
      expect(Object.prototype.hasOwnProperty.call(TRACK_SOURCES, s.id), s.id).toBe(true);
      expect(t!.samples.length).toBeGreaterThan(100);
      expect(t!.start.mjd).toBeLessThanOrEqual(60789.75);
      expect(t!.end.mjd).toBeCloseTo(61358, 6);
      expect(t!.tiers.map((x) => x.tier)).toEqual(['derived', 'model', 'derived', 'display']);
      expect(t!.coverageSource).toContain('IRSA');
    }
    for (const s of SYSTEMS.filter((x) => !x.motion)) expect(buildSkyTrack(s)).toBeNull();
  });

  it('returns null without a parallax, a proper motion or a readable epoch', () => {
    const base = system('barnards-star');
    const m = base.motion!;
    for (const motion of [
      { ...m, parallax_mas: null },
      { ...m, parallax_mas: 0 },
      { ...m, pm_dec_mas_yr: null },
      { ...m, epoch: 'sometime' },
    ]) {
      expect(buildSkyTrack({ ...base, id: 'x-test', motion })).toBeNull();
    }
  });

  it('puts one dot per pass, one per visit where the 10-day gap splits a pass', () => {
    const labels = (id: string) => buildSkyTrack(system(id))!.marks.map((m) => m.label);
    expect(labels('barnards-star')).toEqual(['1', '2', '3']);
    expect(labels('epsilon-indi')).toEqual(['1', '2', '3', '4']);
    expect(labels('wise-0855')).toEqual(['1', '2a', '2b', '3']);
    expect(labels('rw-aurigae')).toEqual(['1', '2', '3']);
    expect(labels('r-draconis')).toEqual(['1', '2']);
  });

  it("offsets are from Pass 1; Barnard's Star moves north pass after pass", () => {
    const t = buildSkyTrack(system('barnards-star'))!;
    expect(t.reference.mjd).toBe((60903 + 60949) / 2);
    expect(Math.hypot(t.marks[0].position.east, t.marks[0].position.north)).toBeLessThan(1e-9);
    expect(t.marks[0].dates).toEqual(['2025-08-15', '2025-10-01']);
    for (let i = 1; i < t.marks.length; i++) {
      const m = t.marks[i];
      expect(m.position.north).toBeGreaterThan(t.marks[i - 1].position.north);
      expect(m.shiftFromPreviousArcsec).toBeCloseTo(separationArcsec(t.marks[i - 1].position, m.position), 9);
    }
    expect(t.marks[0].shiftFromPreviousArcsec).toBeNull();
    // Pass 1 -> Pass 3: about one year of 10.39 arcsec/yr plus the parallax swing.
    expect(t.totalShiftArcsec).toBeGreaterThan(9);
    expect(t.totalShiftArcsec).toBeLessThan(11.5);
    expect(t.pmPositionAngleDeg).toBeCloseTo(355.6, 1);
    // Drift within the first pass (46 days): ~1.3 arcsec, i.e. about 0.2 px.
    expect(t.marks[0].driftArcsec).toBeGreaterThan(0.8);
    expect(t.marks[0].driftArcsec).toBeLessThan(2);
  });

  it('parallax amplitude, ellipse and radial-velocity effect', () => {
    const t = buildSkyTrack(system('barnards-star'))!;
    expect(t.parallaxArcsec).toBeCloseTo(0.546976, 6);
    expect(t.parallaxMinorArcsec).toBeCloseTo(0.546976 * Math.sin((28.18 * Math.PI) / 180), 2);
    expect(t.parallaxMaxArcsec).toBeGreaterThan(0.95 * t.parallaxArcsec);
    expect(t.parallaxMaxArcsec).toBeLessThan(1.02 * t.parallaxArcsec);
    // astropy: 0.076 arcsec between with and without the radial velocity on 2026-11-14.
    expect(t.radialVelocityEffectArcsec).toBeCloseTo(0.076, 2);
    expect(buildSkyTrack(system('wise-0855'))!.radialVelocityEffectArcsec).toBeNull();
  });

  it('RW Aur and R Dra are static at SPHEREx resolution; the fast movers are not', () => {
    for (const id of ['rw-aurigae', 'r-draconis']) {
      const t = buildSkyTrack(system(id))!;
      expect(t.staticAtPixelScale, id).toBe(true);
      expect(t.spanArcsec / SPHEREX_PIXEL_ARCSEC).toBeLessThan(0.02);
    }
    for (const id of ['barnards-star', 'epsilon-indi', 'wise-0855']) {
      expect(buildSkyTrack(system(id))!.staticAtPixelScale, id).toBe(false);
    }
  });

  it('WISE 0855 passes the static Gaia star as RECON 4.3 tabulates', () => {
    const t = buildSkyTrack(system('wise-0855'))!;
    const star = t.staticSources[0];
    expect(star.name).toBe('Gaia DR3 5756956644387831296');
    // RECON 4.3 (month-level dates, the team's own fit): 11.3, 8.0, 4.1, ~3 (Aug-Sep 2026), 6.0 arcsec.
    const table: [string, number][] = [
      ['2025-05-05', 11.3],
      ['2025-11-15', 8.0],
      ['2026-05-15', 4.1],
      ['2027-05-15', 6.0],
    ];
    for (const [iso, sep] of table) {
      expect(Math.abs(separationArcsec(trackPointAt(t, isoDateToMjd(iso)), star) - sep), iso).toBeLessThan(0.5);
    }
    expect(star.closest.mjd).toBeGreaterThan(isoDateToMjd('2026-08-01'));
    expect(star.closest.mjd).toBeLessThan(isoDateToMjd('2026-09-30'));
    expect(Math.abs(star.closest.separationArcsec - 3)).toBeLessThan(0.3);
  });

  it('trackPointAt agrees with the samples', () => {
    const t = buildSkyTrack(system('epsilon-indi'))!;
    const s = t.samples[57];
    const p = trackPointAt(t, s.mjd);
    expect(p.east).toBeCloseTo(s.east, 9);
    expect(p.north).toBeCloseTo(s.north, 9);
  });

  it('caption is the S4 wording', () => {
    expect(SKY_TRACK_CAPTION).toBe('Predicted position from catalog astrometry - not a measurement');
  });
});

describe('plot layout', () => {
  it('keeps equal aspect, every point in view and the height in bounds', () => {
    for (const id of ['barnards-star', 'epsilon-indi', 'wise-0855', 'rw-aurigae', 'r-draconis']) {
      const t = buildSkyTrack(system(id))!;
      for (const width of [300, 343, 640]) {
        for (const mode of ['pixels', 'fit'] as const) {
          const l = plotLayout(t.samples, width, mode);
          expect(l.height).toBeGreaterThanOrEqual(PLOT_MIN_HEIGHT);
          expect(l.height).toBeLessThanOrEqual(PLOT_MAX_HEIGHT);
          expect((l.east[1] - l.east[0]) * l.scale).toBeCloseTo(l.width, 6);
          expect((l.north[1] - l.north[0]) * l.scale).toBeCloseTo(l.height, 6);
          for (const p of t.samples) {
            expect(p.east).toBeGreaterThanOrEqual(l.east[0]);
            expect(p.east).toBeLessThanOrEqual(l.east[1]);
            expect(p.north).toBeGreaterThanOrEqual(l.north[0]);
            expect(p.north).toBeLessThanOrEqual(l.north[1]);
          }
        }
      }
    }
  });

  it('pixel mode shows at least 1.5 SPHEREx pixels; fit mode zooms on a static track', () => {
    const t = buildSkyTrack(system('rw-aurigae'))!;
    const px = plotLayout(t.samples, 343, 'pixels');
    expect(Math.min(px.east[1] - px.east[0], px.north[1] - px.north[0])).toBeGreaterThanOrEqual(1.5 * SPHEREX_PIXEL_ARCSEC - 1e-9);
    expect(px.gridInPixels).toBe(true);
    expect(px.gridStepArcsec % SPHEREX_PIXEL_ARCSEC).toBeCloseTo(0, 9);
    const fit = plotLayout(t.samples, 343, 'fit');
    expect(fit.scale).toBeGreaterThan(50 * px.scale);
    expect(fit.gridInPixels).toBe(false);
  });

  it('grid helpers', () => {
    expect(niceStep(10, 4)).toBe(2);
    expect(niceStep(0.03, 4)).toBeCloseTo(0.01, 12);
    expect(gridValues(-6.2, 13, 6.15)).toEqual([-6.15, 0, 6.15, 12.3].map((x) => expect.closeTo(x, 9)));
    expect(gridValues(1, 0, 1)).toEqual([]);
  });
});

describe('SkyTrackPanel (server render)', () => {
  const render = (s: SystemModel, mjd?: number) => renderToStaticMarkup(createElement(SkyTrackPanel, { system: s, mjd }));

  it('renders every demo system with a SpaceMotion: caption, badge, one entry per pass, finite geometry', () => {
    for (const s of SYSTEMS.filter((x) => x.motion)) {
      const html = render(s);
      expect(html, s.id).toContain(SKY_TRACK_CAPTION);
      expect(html).toContain('PREDICTION · NOT A MEASUREMENT');
      expect(html).toContain('Where SPHEREx should see it');
      const t = buildSkyTrack(s)!;
      for (const m of t.marks) expect(html).toContain(`<strong>Pass ${m.label}</strong>`);
      // No NaN or Infinity in any SVG attribute or path.
      expect(html).not.toMatch(/="[^"]*(NaN|Infinity)[^"]*"/);
    }
  });

  it('draws the dataset date of the 3D view when it is given', () => {
    const html = render(system('barnards-star'), isoDateToMjd('2026-04-01'));
    expect(html).toContain('On 2026-04-01 (date of the 3D view)');
    expect(render(system('barnards-star'))).not.toContain('date of the 3D view');
  });

  it('says why when the motion cannot be propagated', () => {
    const s = system('barnards-star');
    const html = render({ ...s, id: 'x-test', motion: { ...s.motion!, parallax_mas: null } });
    expect(html).toContain('No sky track');
    expect(html).not.toContain('<svg');
  });
});

describe('formatting', () => {
  it('arcsec, pixels and places', () => {
    expect(formatArcsec(15.7208)).toBe('15.7″');
    expect(formatArcsec(1.234)).toBe('1.23″');
    expect(formatArcsec(0.546976)).toBe('0.547″');
    expect(formatArcsec(0.0758)).toBe('76 mas');
    expect(formatArcsec(0.00031)).toBe('0.3 mas');
    expect(formatPx(15.7208)).toBe('2.56 px');
    expect(formatPx(0.546976)).toBe('0.089 px');
    expect(formatPx(0.043)).toBe('0.0070 px');
    expect(formatPlace(at(269.4462952, 4.7681531))).toBe('269.4462952°, +4.7681531°');
    expect(formatPlace(at(331.0965591, -56.8006419))).toBe('331.0965591°, −56.8006419°');
  });
});
