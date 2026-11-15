import { afterEach, describe, expect, it, vi } from 'vitest';
import {
  getGaiaMarkers, getGaiaView, GaiaViewCache, gaiaViewRadiusDeg, gaiaViewVisibleRadiusDeg, GAIA_DEFAULT_EPOCH,
  GAIA_SOURCE_LIMIT, GAIA_VIEW_MAX_FOV, type GaiaMarkerSet,
} from './gaiaLayer';
// Real VizieR CfA asu-tsv responses for I/355/gaiadr3 with the columns the map asks for, fetched on 2026-11-15
// (Barnard's Star, 90″ cone): brightest rows, faintest rows, negative parallaxes, and an empty 0.05″ cone.
import brightTsv from './__fixtures__/vizier-gaiadr3-barnard-bright.tsv?raw';
import faintTsv from './__fixtures__/vizier-gaiadr3-barnard-faint.tsv?raw';
import negativeTsv from './__fixtures__/vizier-gaiadr3-barnard-negative-plx.tsv?raw';
import emptyTsv from './__fixtures__/vizier-gaiadr3-empty-cone.tsv?raw';

const center = { ra: 269.44623, dec: 4.76870 };
const corners = [
  { ra: 269.52, dec: 4.69 }, { ra: 269.37, dec: 4.69 },
  { ra: 269.37, dec: 4.84 }, { ra: 269.52, dec: 4.84 },
];
const EPOCH = 61116.6838019213;

function stubCatalog(tsv: string) {
  const fetch = vi.fn(async (_url: string, _init?: RequestInit) => new Response(tsv));
  vi.stubGlobal('fetch', fetch);
  return fetch;
}
function loadCatalog(tsv: string) {
  stubCatalog(tsv);
  return getGaiaMarkers(center, corners, EPOCH, new AbortController().signal);
}

afterEach(() => vi.unstubAllGlobals());

describe('Gaia DR3 map catalog', () => {
  it('the fixtures carry the exact VizieR column names the map requests', () => {
    expect(brightTsv).toContain('\nSource\tRA_ICRS\tDE_ICRS\tPlx\te_Plx\tpmRA\tpmDE\tGmag\tBP-RP\tRV\n');
    for (const tsv of [brightTsv, emptyTsv]) expect(tsv).toContain('#Table\tI_355_gaiadr3:');
  });

  it('accepts the metadata-only response VizieR sends for an empty cone', async () => {
    await expect(loadCatalog(emptyTsv)).resolves.toEqual({ markers: [], limited: false });
  });

  it('reports an explicit catalog failure even if the response includes the Gaia metadata', async () => {
    await expect(loadCatalog(`${emptyTsv}\n#INFO\tQUERY_STATUS=ERROR\tserver unavailable`)).rejects.toThrow('Gaia DR3 query failed');
  });

  it('rejects a table without the requested columns', async () => {
    await expect(loadCatalog(emptyTsv.replace(/^#Column\te_Plx.*$/m, ''))).rejects.toThrow('Unexpected Gaia DR3 table');
    await expect(loadCatalog(brightTsv.replace('\tGmag\tBP-RP\tRV\n', '\tGmag\tBPRP\tRV\n'))).rejects.toThrow('Unexpected Gaia DR3 table');
  });

  it('propagates Barnard to the sequence epoch without rounding its Gaia source ID', async () => {
    const { markers, limited } = await loadCatalog(brightTsv);
    expect(limited).toBe(false);
    expect(markers).toHaveLength(6);
    expect(markers[0].sourceId).toBe('4472832130942575872');
    // Independent geocentric ICRS reference from Astropy space motion and Earth's barycentric position.
    expect(Math.abs(markers[0].ra - 269.4463725391953)).toBeLessThan(1e-6);
    expect(Math.abs(markers[0].dec - 4.768815881735359)).toBeLessThan(1e-6);
  });

  it('keeps the catalog values the hover card needs, and null where Gaia DR3 has none', async () => {
    const { markers } = await loadCatalog(brightTsv);
    expect(markers[0]).toMatchObject({
      gmag: 8.193974, bpRp: 2.833697, parallax: 546.9759, parallaxError: 0.0401, pmRa: -801.551, pmDec: 10362.394, rv: -110.47,
    });
    expect(markers[1]).toMatchObject({ sourceId: '4472832513187484544', rv: 91.13 });
    expect(markers[2]).toMatchObject({ sourceId: '4472832822422325632', rv: null, parallax: 1.4144 });
  });

  it('skips two-parameter sources (no proper motion: no position at the epoch)', async () => {
    expect(faintTsv).toMatch(/\n4472832818133721856\t269\.45118678719\t\+04\.73147042190\t\s+\t/);
    await expect(loadCatalog(faintTsv)).resolves.toEqual({ markers: [], limited: false });
  });

  it('moves negative-parallax sources by proper motion alone', async () => {
    const { markers } = await loadCatalog(negativeTsv);
    expect(markers.map(({ sourceId }) => sourceId)).toEqual(['4472835876142884224', '4472832234010403072', '4472832856786795264']);
    expect(markers[2].parallax).toBe(-0.4681);
    // −5.351 mas/yr over 9.73 yr from J2016.0 is ≈ −52 mas in declination.
    expect((markers[2].dec - 4.74705362495) * 3_600_000).toBeCloseTo(-5.351 * (EPOCH - 57388.5) / 365.25, 0);
  });

  it(`stops at ${GAIA_SOURCE_LIMIT} sources and says the query was limited`, async () => {
    const [head, firstRow] = brightTsv.split(/\n(?=4472832130942575872\t)/);
    const rows = Array.from({ length: GAIA_SOURCE_LIMIT + 1 }, (_, k) =>
      firstRow.split('\n')[0].replace('4472832130942575872', String(4472832130942575872n + BigInt(k))));
    const { markers, limited } = await loadCatalog(`${head}\n${rows.join('\n')}\n`);
    expect(markers).toHaveLength(GAIA_SOURCE_LIMIT);
    expect(limited).toBe(true);
  });
});

describe('Gaia DR3 stars per view (FE-4b)', () => {
  it('queries views of at most 0.5° (dense fields took 16–18 s for a 1° view on VizieR CfA)', () => {
    expect(GAIA_VIEW_MAX_FOV).toBe(0.5);
  });

  it('covers the visible half-diagonal, 1.2 × wider for small pans, or 0.71 × fov without both sides', () => {
    const wide = { ra: 0, dec: 0, fov: 0.5, fovX: 0.5, fovY: 0.3 };
    expect(gaiaViewVisibleRadiusDeg(wide)).toBeCloseTo(Math.hypot(0.5, 0.3) / 2, 12);
    expect(gaiaViewRadiusDeg(wide)).toBeCloseTo(1.2 * Math.hypot(0.5, 0.3) / 2, 12);
    expect(gaiaViewVisibleRadiusDeg({ ra: 0, dec: 0, fov: 0.5 })).toBeCloseTo(0.5 * Math.SQRT1_2, 12);
    // The square bound is never smaller than the real half-diagonal.
    expect(gaiaViewVisibleRadiusDeg({ ra: 0, dec: 0, fov: 0.5 })).toBeGreaterThanOrEqual(gaiaViewVisibleRadiusDeg(wide));
  });

  it('asks VizieR CfA for the brightest sources in that cone, plus the motion margin', async () => {
    const fetch = stubCatalog(brightTsv);
    const view = { ra: 269.44623, dec: 4.7687, fov: 0.5, fovX: 0.5, fovY: 0.5 * 601 / 916 };
    await getGaiaView(view, GAIA_DEFAULT_EPOCH, new AbortController().signal);
    const url = new URL(fetch.mock.calls[0][0]);
    expect(url.origin + url.pathname).toBe('https://vizier.cfa.harvard.edu/viz-bin/asu-tsv');
    expect(url.searchParams.get('-source')).toBe('I/355/gaiadr3');
    expect(url.searchParams.get('-out')).toBe('Source,RA_ICRS,DE_ICRS,Plx,e_Plx,pmRA,pmDE,Gmag,BP-RP,RV');
    expect(url.searchParams.get('-sort')).toBe('Gmag');
    expect(url.searchParams.get('-out.max')).toBe(String(GAIA_SOURCE_LIMIT + 1));
    expect(url.searchParams.get('-c')).toBe('269.4462300 4.7687000');
    const margin = 12 * (GAIA_DEFAULT_EPOCH - 57388.5) / 365.25; // 12″/yr from J2016.0 to MJD 61000
    expect(Number(url.searchParams.get('-c.rs'))).toBeCloseTo(1.2 * Math.hypot(0.5, 0.5 * 601 / 916) / 2 * 3600 + margin, 2);
    // ≈ 0.39°: the cone size timed at 2.9–4.3 s on VizieR CfA around the five targets (gaiaLayer.ts).
    expect(Number(url.searchParams.get('-c.rs')) / 3600).toBeCloseTo(0.39, 2);
  });

  it('aborts the request when a newer view takes over', async () => {
    const fetch = vi.fn((_url: string, init?: RequestInit) => new Promise<Response>((_, reject) => {
      init?.signal?.addEventListener('abort', () => reject(new DOMException('aborted', 'AbortError')));
    }));
    vi.stubGlobal('fetch', fetch);
    const abort = new AbortController();
    const pending = getGaiaView({ ra: 10, dec: 20, fov: 0.3 }, GAIA_DEFAULT_EPOCH, abort.signal);
    abort.abort();
    await expect(pending).rejects.toThrow('aborted');
    expect(fetch.mock.calls[0][1]?.signal?.aborted).toBe(true);
  });
});

describe('per-view cache', () => {
  const result = (limited = false): GaiaMarkerSet => ({ markers: [], limited });
  const view = { ra: 269.44623, dec: 4.7687, fov: 0.5 };

  it('answers the same view and smaller views it covers, at the same epoch only', () => {
    const cache = new GaiaViewCache(20);
    const stored = result();
    cache.set(view, GAIA_DEFAULT_EPOCH, stored);
    expect(cache.get(view, GAIA_DEFAULT_EPOCH)).toBe(stored);
    expect(cache.get({ ...view, ra: view.ra + 0.05, fov: 0.3 }, GAIA_DEFAULT_EPOCH)).toBe(stored);
    expect(cache.get({ ...view, ra: view.ra + 0.2 }, GAIA_DEFAULT_EPOCH)).toBeUndefined();
    expect(cache.get(view, EPOCH)).toBeUndefined();
  });

  it('asks again when zooming into a cone that was cut at the source limit', () => {
    const cache = new GaiaViewCache(20);
    cache.set(view, GAIA_DEFAULT_EPOCH, result(true));
    expect(cache.get({ ...view, fov: 0.45 }, GAIA_DEFAULT_EPOCH)).toBeDefined();
    expect(cache.get({ ...view, fov: 0.2 }, GAIA_DEFAULT_EPOCH)).toBeUndefined();
  });

  it('answers a pan of 0.1 × fov at the same zoom, also for a cone cut at the source limit', () => {
    const sides = { ...view, fovX: 0.5, fovY: 0.5 * 601 / 916 };
    const pan = (fraction: number) => ({ ...sides, ra: sides.ra + fraction * sides.fov / Math.cos(sides.dec * Math.PI / 180) });
    for (const limited of [false, true]) {
      const cache = new GaiaViewCache(20);
      const stored = result(limited);
      cache.set(sides, GAIA_DEFAULT_EPOCH, stored);
      expect(cache.get(pan(0.1), GAIA_DEFAULT_EPOCH)).toBe(stored);
      expect(cache.get(pan(-0.1), GAIA_DEFAULT_EPOCH)).toBe(stored);
      // A quarter of the view away, the visible corners leave the cached cone.
      expect(cache.get(pan(0.25), GAIA_DEFAULT_EPOCH)).toBeUndefined();
    }
  });

  it('keeps the 20 most recently used views', () => {
    const cache = new GaiaViewCache(20);
    const views = Array.from({ length: 21 }, (_, k) => ({ ra: 10 * k, dec: 0, fov: 0.5 }));
    views.slice(0, 20).forEach((v) => cache.set(v, GAIA_DEFAULT_EPOCH, result()));
    expect(cache.get(views[0], GAIA_DEFAULT_EPOCH)).toBeDefined(); // view 0 becomes the most recent
    cache.set(views[20], GAIA_DEFAULT_EPOCH, result());
    expect(cache.size).toBe(20);
    expect(cache.get(views[0], GAIA_DEFAULT_EPOCH)).toBeDefined();
    expect(cache.get(views[1], GAIA_DEFAULT_EPOCH)).toBeUndefined();
    expect(cache.get(views[20], GAIA_DEFAULT_EPOCH)).toBeDefined();
  });
});
