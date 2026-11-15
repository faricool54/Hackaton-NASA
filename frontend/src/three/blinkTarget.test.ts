import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';
import type { Field, SystemModel } from '../api/types';
import { BlinkViewer } from '../components/BlinkViewer';
import { predictedFramePixel } from '../components/framePrediction';
import {
  BLINK_TARGET_PHRASE,
  formatShift,
  insideGrid,
  isGaiaAstrometry,
  predictFromAstrometry,
  predictTarget,
  shortSource,
  tanWorldToPng,
  type BlinkTargetPrediction,
} from './blinkTarget';
import { astrometricPlace, trackAstrometry, TRACK_SOURCES } from './skyTrack';

// The real published products (the same JSON the site serves as the "real" dataset).
const FIELDS = Object.values(
  import.meta.glob<Field>('../../../data/products/fields/*/field.json', { eager: true, import: 'default' }),
);
const SYSTEMS = Object.values(
  import.meta.glob<SystemModel>('../../../data/products/systems/*.json', { eager: true, import: 'default' }),
);
const DEMO_FIELDS = Object.values(
  import.meta.glob<Field>('../../../data/demo/fields/*/field.json', { eager: true, import: 'default' }),
);
const DEMO_SYSTEMS = Object.values(
  import.meta.glob<SystemModel>('../../../data/demo/systems/*.json', { eager: true, import: 'default' }),
);

function byId<T extends { id: string }>(list: T[], id: string): T {
  const x = list.find((item) => item.id === id);
  if (!x) throw new Error(`${id} missing`);
  return x;
}
const field = (id: string) => byId(FIELDS, id);
const system = (id: string) => byId(SYSTEMS, id);
type Points = BlinkTargetPrediction['points'];
/** Frames split into SPHEREx seasons (gaps of more than 60 days). */
function seasonsOf(points: Points): Points[] {
  const seasons: Points[] = [];
  for (const q of points) {
    const cur = seasons[seasons.length - 1];
    if (cur && q.mjd - cur[cur.length - 1].mjd < 60) cur.push(q);
    else seasons.push([q]);
  }
  return seasons;
}
const meanOf = (s: Points) => ({
  x: s.reduce((t, q) => t + q.x, 0) / s.length,
  y: s.reduce((t, q) => t + q.y, 0) / s.length,
});
function predict(systemId: string, fieldId: string): BlinkTargetPrediction {
  const p = predictTarget(system(systemId), field(fieldId));
  if (!p) throw new Error(`no prediction for ${systemId}`);
  return p;
}

describe('tanWorldToPng', () => {
  // Generated on 2026-11-15 with the worktree venv:
  //   .venv/Scripts/python <script> with errante.imaging.grid.sky_to_png_xy(Grid(**field.json["grid"]), ra, dec)
  // on the published barnards-star, wise-0855 and eps-indi-b grids (88 x 88 px, 6.15"/px): the
  // centre, an off-centre point, points near/just outside the corners and the north edge; plus
  // errante.imaging.grid.make_grid(0.02, 10.0, 0.15) for the RA wrap through 0/360.
  const REFERENCE: [string, number, number, number, number][] = [
    ['barnards-star', 269.44623, 4.7687, 43.5, 43.50000000000205],
    ['barnards-star', 269.45857272529696, 4.7998, 36.30032591569275, 25.29505527542652],
    ['barnards-star', 269.3757861531833, 4.6982, 84.59692148529776, 84.7662442160936],
    ['barnards-star', 269.52098878330264, 4.6939, -0.11453006054315296, 87.28306228094013],
    ['barnards-star', 269.44523000000004, 4.8436, 44.083275949128904, -0.34392784387499375],
    ['wise-0855', 133.7598, -7.24219, 43.5, 43.50000000000205],
    ['wise-0855', 133.77219891678916, -7.2110899999999996, 36.29950325319333, 25.29521796015608],
    ['wise-0855', 133.6890354505204, -7.31269, 84.58627791690827, 84.77154300871405],
    ['wise-0855', 133.83489913014574, -7.31699, -0.10254557959807187, 87.28903007424972],
    ['wise-0855', 133.7588, -7.1672899999999995, 44.080792355067025, -0.34392678172559954],
    ['eps-indi-b', 331.09665, -56.80066, 43.5, 43.50000000000205],
    ['eps-indi-b', 331.1191135548838, -56.76956, 36.294027601829924, 25.296301763639455],
    ['eps-indi-b', 330.96844336968763, -56.87116, 84.51540941194514, 84.80674268431072],
    ['eps-indi-b', 331.2327097429953, -56.875460000000004, -0.022747220284344394, 87.32866908900156],
    ['eps-indi-b', 331.09565000000003, -56.72576, 43.82115948583713, -0.34392507091072844],
  ];
  const WRAP_GRID = {
    width_px: 88,
    height_px: 88,
    wcs: {
      CTYPE1: 'RA---TAN', CTYPE2: 'DEC--TAN', CRVAL1: 0.02, CRVAL2: 10.0, CRPIX1: 44.5, CRPIX2: 44.5,
      CDELT1: -0.0017083333333333334, CDELT2: 0.0017083333333333334, CUNIT1: 'deg', CUNIT2: 'deg', NAXIS1: 88, NAXIS2: 88,
    },
  };
  const WRAP_REFERENCE: [number, number, number, number][] = [
    [359.98, 10.01, 66.55820718283604, 37.64494235534975],
    [0.06, 9.97, 20.43895427620368, 61.0595835281723],
  ];

  it('matches the pipeline sky_to_png_xy on the real grids to 1e-6 px', () => {
    for (const [id, ra, dec, x, y] of REFERENCE) {
      const p = tanWorldToPng(field(id).grid, ra, dec);
      expect(p, id).not.toBeNull();
      expect(Math.abs(p!.x - x), `${id} x at ${ra}, ${dec}`).toBeLessThan(1e-6);
      expect(Math.abs(p!.y - y), `${id} y at ${ra}, ${dec}`).toBeLessThan(1e-6);
    }
  });

  it('wraps RA through 0/360', () => {
    for (const [ra, dec, x, y] of WRAP_REFERENCE) {
      const p = tanWorldToPng(WRAP_GRID, ra, dec)!;
      expect(Math.abs(p.x - x)).toBeLessThan(1e-6);
      expect(Math.abs(p.y - y)).toBeLessThan(1e-6);
      // The same place written as a negative RA projects to the same pixel.
      const q = tanWorldToPng(WRAP_GRID, ra - 360, dec)!;
      expect(Math.abs(q.x - x)).toBeLessThan(1e-6);
    }
  });

  it('draws north up and east left, and flags positions off the grid', () => {
    const g = field('barnards-star').grid;
    const c = tanWorldToPng(g, 269.44623, 4.7687)!;
    expect(tanWorldToPng(g, 269.44623, 4.7787)!.y).toBeLessThan(c.y); // north = up
    expect(tanWorldToPng(g, 269.45623, 4.7687)!.x).toBeLessThan(c.x); // east = left
    expect(insideGrid(g, c)).toBe(true);
    expect(insideGrid(g, { x: -0.6, y: 10 })).toBe(false); // pixel 0 spans -0.5 to +0.5
    expect(insideGrid(g, { x: 10, y: 87.6 })).toBe(false);
    expect(insideGrid(g, { x: 87.5, y: -0.5 })).toBe(true);
  });

  it('returns null behind the tangent plane or for a grid that is not plain TAN', () => {
    const g = field('barnards-star').grid;
    expect(tanWorldToPng(g, 269.44623 - 180, -4.7687)).toBeNull(); // antipode
    expect(tanWorldToPng(g, 269.44623 + 95, 0)).toBeNull(); // beyond the horizon
    expect(tanWorldToPng({ ...g, wcs: { ...g.wcs, CTYPE1: 'RA---SIN' } }, 269.44623, 4.7687)).toBeNull();
    expect(tanWorldToPng({ ...g, wcs: { ...g.wcs, CDELT1: 0 } }, 269.44623, 4.7687)).toBeNull();
  });
});

describe("predictTarget: Barnard's Star", () => {
  const p = predict('barnards-star', 'barnards-star');

  it('moves 1.68 px from the first to the last season of the published frames, as the validation log expects', () => {
    // docs/validation/barnards-star.md: "En los 40 PNG publicados ... el centroide de la meseta
    // saturada se mueve 1,60 px contra 1,68 px esperados" (14/13/13 frames per season). The expected
    // 1.68 px is the shift between the season means; it is rounded to 0.01 px, and this propagation
    // differs from that astropy one by < 0.001 px (heliocentric low-precision Earth, at most 4 mas of
    // parallax: skyTrack.ts), so 0.01 px covers the rounding.
    expect(p.points).toHaveLength(40);
    const seasons = seasonsOf(p.points);
    expect(seasons.map((s) => s.length)).toEqual([14, 13, 13]);
    const s0 = meanOf(seasons[0]);
    const s2 = meanOf(seasons[2]);
    expect(Math.abs(Math.hypot(s2.x - s0.x, s2.y - s0.y) - 1.68)).toBeLessThan(0.01);
  });

  it('moves ~1.7 px from the first to the last frame: the proper motion over the baseline, plus parallax', () => {
    // First and last frames are 375.8 days apart, a little more than the season means, so the shift
    // is the catalog proper motion over that time (1.69 px/yr) to within the parallax semi-amplitude
    // (<= 0.089 px, docs/validation/barnards-star.md).
    const years = (p.last.mjd - p.first.mjd) / 365.25;
    expect(Math.abs(p.totalShiftPx - p.perYearPx * years)).toBeLessThan(0.089);
    expect(p.totalShiftPx).toBeGreaterThan(1.65);
    expect(p.totalShiftPx).toBeLessThan(1.8);
    expect(p.totalShiftArcsec).toBeCloseTo(p.totalShiftPx * 6.15, 9);
  });

  it('moves mostly north (up, y decreasing), slightly west (+x)', () => {
    const dx = p.last.x - p.first.x;
    const dy = p.last.y - p.first.y;
    expect(dy).toBeLessThan(0);
    expect(-dy).toBeGreaterThan(0.99 * p.totalShiftPx); // PA ~356 deg
    expect(dx).toBeGreaterThan(0);
    // ~1.69 px per year from the catalog proper motion (10.39"/yr at 6.15"/px).
    expect(p.perYearPx).toBeCloseTo(Math.hypot(-801.551, 10362.394) / 1000 / 6.15, 9);
  });

  it('stays on the grid, near the field centre, frame by frame in time order', () => {
    for (const q of p.points) {
      expect(q.inGrid).toBe(true);
      expect(Math.hypot(q.x - 43.5, q.y - 43.5)).toBeLessThan(3);
    }
    const mjds = p.points.map((q) => q.mjd);
    expect(mjds).toEqual([...mjds].sort((a, b) => a - b));
    expect(p.astrometryOrigin).toBe('system');
    expect(p.source).toBe(TRACK_SOURCES['barnards-star'].source);
  });

  it('follows the frames it is given (e.g. one detector)', () => {
    const f = field('barnards-star');
    const d6 = f.frames.filter((x) => x.detector === 6);
    const q = predictTarget(system('barnards-star'), f, d6)!;
    expect(q.points.map((x) => x.frameId).sort()).toEqual(d6.map((x) => x.id).sort());
    expect(q.caption).toContain(`Over the ${d6.length} frames shown`);
  });
});

describe('predictTarget: other targets', () => {
  it("tracks Epsilon Indi B with B's own solution, not A (65 px west, off the grid)", () => {
    const p = predict('epsilon-indi', 'eps-indi-b');
    expect(p.astrometryOrigin).toBe('ws7-constant');
    expect(p.target).toBe('Epsilon Indi B (Ba+Bb, unresolved)');
    expect(p.points.every((q) => q.inGrid)).toBe(true);
    expect(Math.hypot(p.mean.x - 43.5, p.mean.y - 43.5)).toBeLessThan(3);
    // A (the system centre) propagated the same way lands ~65 px west (= +x) of B, off the grid.
    const s = system('epsilon-indi');
    const a = trackAstrometry({ ...s, id: 'epsilon-indi-a-check' })!;
    const placeA = astrometricPlace(a, p.points[0].mjd);
    const xyA = tanWorldToPng(field('eps-indi-b').grid, placeA.raDeg, placeA.decDeg)!;
    expect(xyA.x - p.points[0].x).toBeGreaterThan(60);
    expect(insideGrid(field('eps-indi-b').grid, xyA)).toBe(false);
  });

  it('projects the static field star next to WISE 0855 and names it in the legend', () => {
    const p = predict('wise-0855', 'wise-0855');
    expect(p.staticSources).toHaveLength(1);
    const star = p.staticSources[0];
    expect(star.name).toBe('Gaia DR3 5756956644387831296');
    expect(star.inGrid).toBe(true);
    // Its catalog position, projected the same way as everything else.
    expect(star).toMatchObject(tanWorldToPng(field('wise-0855').grid, 133.7581825, -7.2411559)!);
    // Within a pixel of the predicted target: the D1-D3 blob at the target position.
    const nearest = Math.min(...p.points.map((q) => Math.hypot(q.x - star.x, q.y - star.y)));
    expect(nearest).toBeLessThan(1);
    expect(p.caption).toContain('Dashed circle: Gaia DR3 5756956644387831296 (static).');
    // The visible line says the target itself is only in D5/D6, so no D1–D4 blob reads as WISE 0855
    // (docs/validation/wise-0855.md: "Observado en D1–D4: solo aparece la estrella de fondo").
    expect(p.caption).toContain('The target shows only in D5/D6; in D1–D4 the blob at the crosshair is that star.');
    expect(p.details.join('\n')).toContain('in D1–D4 the blob at the target position is this star');
    expect(p.details.join(' ')).not.toContain('in D1–D3 the blob');
    expect(p.details.join('\n')).toContain('docs/validation/wise-0855.md');
    // docs/validation/wise-0855.md: "La separación es 1,85 / 1,32 / 0,70 px en S0/S1/S2". Rounded
    // to 0.01 px; that log may use the team's own WISE fit, 0.05 px from this Kirkpatrick et al.
    // 2021 track (skyTrack.ts note), so 0.06 px.
    const seps = seasonsOf(p.points).map((season) => {
      const m = meanOf(season);
      return Math.hypot(m.x - star.x, m.y - star.y);
    });
    expect(seps).toHaveLength(3);
    [1.85, 1.32, 0.7].forEach((expected, i) => expect(Math.abs(seps[i] - expected), `S${i}`).toBeLessThan(0.06));
  });

  it('marks every real field with motion: all five targets land on their grid', () => {
    for (const s of SYSTEMS) {
      const p = predictTarget(s, field(s.field_id!));
      expect(p, s.id).not.toBeNull();
      expect(p!.points.filter((q) => q.inGrid).length, s.id).toBe(p!.points.length);
    }
  });
});

describe('predictTarget: nothing to draw', () => {
  it('is null for a system without motion', () => {
    const s = system('barnards-star');
    expect(predictTarget({ ...s, motion: null }, field('barnards-star'))).toBeNull();
    expect(predictTarget({ ...s, motion: { ...s.motion!, parallax_mas: null } }, field('barnards-star'))).toBeNull();
  });

  it('is null for the synthetic demo field (its system has no motion) and without a system', () => {
    const demoField = byId(DEMO_FIELDS, 'demo-ecliptic');
    const demoSystem = byId(DEMO_SYSTEMS, 'demo-ecliptic-orbits');
    expect(demoField.provenance.synthetic).toBe(true);
    expect(predictTarget(demoSystem, demoField)).toBeNull();
    expect(predictTarget(null, demoField)).toBeNull();
    expect(predictTarget(undefined, field('barnards-star'))).toBeNull();
  });

  it("is null for a system of another field, or a real star on a synthetic field", () => {
    expect(predictTarget(system('barnards-star'), field('wise-0855'))).toBeNull();
    const f = field('barnards-star');
    const synthetic = { ...f, provenance: { ...f.provenance, synthetic: true } };
    expect(predictTarget(system('barnards-star'), synthetic)).toBeNull();
  });

  it('is null when no frame position falls on the grid', () => {
    const s = system('barnards-star');
    const f = field('barnards-star');
    const far = { ...f, grid: { ...f.grid, wcs: { ...f.grid.wcs, CRVAL2: 5.5 } } };
    expect(predictTarget(s, far)).toBeNull();
  });
});

describe('labels', () => {
  it('format the shift in px and arcsec at the grid scale, and call a sub-0.1 px track static', () => {
    expect(formatShift(1.7351, 6.15)).toBe('1.74 px (10.7″ at 6.15″/px)');
    expect(formatShift(0.004, 6.15)).toBe('0.0040 px (25 mas at 6.15″/px), static at this pixel scale');
    expect(predict('r-draconis', 'r-draconis').caption).toContain('static at this pixel scale');
    expect(predict('barnards-star', 'barnards-star').caption).not.toContain('static at this pixel scale');
  });

  it('say "predicted from catalog, not a measurement" and never "measured"', () => {
    expect(BLINK_TARGET_PHRASE).toBe('predicted from catalog, not a measurement');
    for (const s of SYSTEMS) {
      const p = predictTarget(s, field(s.field_id!))!;
      expect(p.caption).toContain('predicted from catalog, not a measurement');
      expect(p.reticleTitle).toContain('predicted from catalog, not a measurement');
      expect(p.caption).toContain(`(${shortSource(p.source)})`);
      // The full source and the method are one click away, in the disclosure.
      expect(p.details).toContain(`Astrometry: ${p.source}; ${p.method}.`);
      expect(p.method).toContain('Butkevich & Lindegren 2014');
      expect(p.caption).not.toMatch(/\bmeasured\b/i);
    }
  });

  it('keep the visible line short: it sits between the stage and the scrubber', () => {
    // ~50 characters per line in the 343 px phone column at 0.85rem: ~4 lines, ~7 for WISE 0855,
    // which also names its field star and the detectors the target shows in (was 352-542 characters).
    for (const s of SYSTEMS) {
      const p = predictTarget(s, field(s.field_id!))!;
      expect(p.caption.length, s.id).toBeLessThanOrEqual(s.id === 'wise-0855' ? 350 : 240);
    }
  });

  it('explain the track and rings only when there is a track to see', () => {
    const moving = predict('barnards-star', 'barnards-star');
    expect(moving.showTrack).toBe(true);
    expect(moving.caption).toContain('Faint line: its track; rings: first/last frame.');
    for (const id of ['r-draconis', 'rw-aurigae']) {
      const p = predict(id, id);
      expect(p.showTrack, id).toBe(false);
      expect(p.caption, id).not.toContain('Faint line');
    }
  });

  it('shorten the source to its Gaia DR3 ids, else its leading reference', () => {
    expect(shortSource(TRACK_SOURCES['barnards-star'].source)).toBe('Gaia DR3 4472832130942575872');
    expect(shortSource(TRACK_SOURCES['epsilon-indi'].source)).toBe('Gaia DR3 6412596012146801152');
    expect(shortSource(TRACK_SOURCES['wise-0855'].source)).toBe('Kirkpatrick et al. 2021');
    expect(shortSource(TRACK_SOURCES['r-draconis'].source)).toBe('Gaia DR3 1648328016354496384');
    // RW Aur: position of A, motion of B, both named.
    expect(shortSource(TRACK_SOURCES['rw-aurigae'].source)).toBe('Gaia DR3 156430817820015232 + 156430822114424576');
    expect(shortSource('catalog SpaceMotion of this system (no source listed in the WS7 table)')).toBe(
      'catalog SpaceMotion of this system',
    );
  });
});

describe("predictFromAstrometry agrees with WS5's reticle (framePrediction.ts, #96)", () => {
  it('track points are the reticle positions: image-edge = PNG pixel + 0.5, for every frame of the five fields', () => {
    let n = 0;
    for (const s of SYSTEMS) {
      const f = field(s.field_id!);
      const a = trackAstrometry(s)!;
      const p = predictFromAstrometry(a, f)!;
      expect(p, s.id).not.toBeNull();
      expect(p.systemId).toBeNull();
      for (const q of p.points) {
        const edge = predictedFramePixel(f.grid, a, q.mjd);
        if (!q.inGrid || !edge) continue;
        expect(Math.abs(edge.x - (q.x + 0.5)), `${s.id} ${q.frameId}`).toBeLessThan(1e-6);
        expect(Math.abs(edge.y - (q.y + 0.5)), `${s.id} ${q.frameId}`).toBeLessThan(1e-6);
        n++;
      }
    }
    expect(n).toBeGreaterThan(150);
  });

  it('names the catalog in the note and the toggle: Gaia for Gaia astrometry, the paper otherwise', () => {
    const barnard = predictFromAstrometry(trackAstrometry(system('barnards-star'))!, field('barnards-star'))!;
    expect(isGaiaAstrometry(barnard)).toBe(true);
    expect(barnard.catalogName).toBe('the Gaia catalog');
    expect(barnard.toggleLabel).toBe('Gaia prediction');
    const wise = predictFromAstrometry(trackAstrometry(system('wise-0855'))!, field('wise-0855'))!;
    expect(isGaiaAstrometry(wise)).toBe(false);
    expect(wise.catalogName).toBe('Kirkpatrick et al. 2021');
    expect(wise.toggleLabel).toBe('Catalog prediction');
  });
});

describe('BlinkViewer with a prediction (server-rendered markup, WS5 reticle + WS7 track and legend)', () => {
  const render = (fieldId: string, withPrediction = true, composites: Field['composites'] | null = null) => {
    const f = field(fieldId);
    const s = SYSTEMS.find((x) => x.field_id === fieldId)!;
    return renderToStaticMarkup(
      createElement(BlinkViewer, {
        field: f,
        frames: [...f.frames].sort((a, b) => a.mjd - b.mjd),
        composites,
        imageUrl: (image: string) => image,
        candidates: [],
        known: [],
        selectedId: null,
        onSelect: () => undefined,
        prediction: withPrediction ? trackAstrometry(s) : null,
      }),
    );
  };

  it("keeps WS5's zoom, toggle and note, and adds the track, rings and legend (Barnard's Star)", () => {
    const html = render('barnards-star');
    const p = predictFromAstrometry(trackAstrometry(system('barnards-star'))!, field('barnards-star'))!;
    expect(html).toContain('aria-label="Image zoom"');
    expect(html).toContain('Gaia prediction</button>');
    expect(html).toContain('Crosshair shows the position predicted from the Gaia catalog, not a measurement.');
    expect(html).toContain(BLINK_TARGET_PHRASE);
    // Like WS5's reticle, the WS7 track and rings wait for the frame image to load (none has, server-side);
    // their positions are pinned to the reticle's by the predictFromAstrometry test above.
    expect(html).not.toContain('<polyline');
    expect(html).not.toContain('blink-prediction-reticle');
    expect(p.showTrack).toBe(true);
    expect(html).toContain('Source and method</span></summary>');
    expect(html).toContain(`Astrometry: ${p.source}`);
    // Markers toggle and scrubber unchanged.
    expect(html).toContain('Markers</button>');
    expect(html).toContain('role="slider"');
  });

  it('WISE 0855: catalog (not Gaia) prediction, and the static field star as a dashed circle', () => {
    const html = render('wise-0855');
    expect(html).toContain('Catalog prediction</button>');
    expect(html).toContain('predicted from Kirkpatrick et al. 2021, not a measurement.');
    expect(html).not.toContain('stroke-dasharray="3 2"'); // drawn once the frame image has loaded
    expect(html).toContain('Dashed circle: Gaia DR3 5756956644387831296 (static).');
    expect(html).toContain('in D1–D4 the blob at the crosshair is that star');
  });

  it('draws no track for a target that is static at this pixel scale (R Draconis)', () => {
    const html = render('r-draconis');
    expect(html).toContain('Gaia prediction</button>');
    expect(html).not.toContain('<polyline');
    expect(html).toContain('static at this pixel scale');
  });

  it('adds nothing but the zoom without a prediction, and nothing in the colour modes', () => {
    const html = render('barnards-star', false);
    expect(html).not.toContain('prediction</button>');
    expect(html).not.toContain('blink-prediction-note');
    expect(html).toContain('aria-label="Image zoom"');
    const f = field('barnards-star');
    if (f.composites?.length) {
      const colour = render('barnards-star', true, f.composites);
      expect(colour).not.toContain('<polyline');
      expect(colour).not.toContain('blink-prediction-note');
    }
  });
});
