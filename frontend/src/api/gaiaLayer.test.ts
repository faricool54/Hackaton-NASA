import { afterEach, describe, expect, it, vi } from 'vitest';
import { getGaiaMarkers } from './gaiaLayer';

const center = { ra: 269.44623, dec: 4.76870 };
const corners = [
  { ra: 269.52, dec: 4.69 }, { ra: 269.37, dec: 4.69 },
  { ra: 269.37, dec: 4.84 }, { ra: 269.52, dec: 4.84 },
];
const columns = ['Source', 'RA_ICRS', 'DE_ICRS', 'Plx', 'pmRA', 'pmDE', 'Gmag', 'RV'];
const metadata = ['#Table\tI_355_gaiadr3:', ...columns.map((name) => `#Column\t${name}\t(F)\tDescription`)].join('\n');

function loadCatalog(tsv: string) {
  vi.stubGlobal('fetch', vi.fn(async () => new Response(tsv)));
  return getGaiaMarkers(center, corners, 61116.6838019213, new AbortController().signal);
}

afterEach(() => vi.unstubAllGlobals());

describe('Gaia DR3 map catalog', () => {
  it('accepts the metadata-only response VizieR sends for an empty cone', async () => {
    await expect(loadCatalog(metadata)).resolves.toEqual({ markers: [], limited: false });
  });

  it('reports an explicit catalog failure even if the response includes the Gaia metadata', async () => {
    await expect(loadCatalog(`${metadata}\n#INFO\tQUERY_STATUS=ERROR\tserver unavailable`)).rejects.toThrow('Gaia DR3 query failed');
  });

  it('propagates Barnard to the sequence epoch without rounding its Gaia source ID', async () => {
    const row = '4472832130942575872\t269.44850252544\t+04.73942005111\t546.9759\t-801.551\t10362.394\t8.193974\t-110.47';
    const { markers } = await loadCatalog(`${metadata}\n${columns.join('\t')}\n${row}`);
    expect(markers).toHaveLength(1);
    expect(markers[0].sourceId).toBe('4472832130942575872');
    // Independent geocentric ICRS reference from Astropy space motion and Earth's barycentric position.
    expect(Math.abs(markers[0].ra - 269.4463725391953)).toBeLessThan(1e-6);
    expect(Math.abs(markers[0].dec - 4.768815881735359)).toBeLessThan(1e-6);
  });
});
