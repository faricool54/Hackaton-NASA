import { afterEach, describe, expect, it, vi } from 'vitest';
import { ApiError, createClient } from './client';
import { loadLightCurve } from './lightcurve';

afterEach(() => vi.unstubAllGlobals());

describe('client URLs', () => {
  it('static mode maps resources to files', () => {
    const c = createClient({ mode: 'static', apiBase: 'http://x', staticBase: '/data/demo/' });
    expect(c.resourceUrl('manifest')).toBe('/data/demo/manifest.json');
    expect(c.resourceUrl('field', 'f1')).toBe('/data/demo/fields/f1/field.json');
    expect(c.resourceUrl('candidates', 'f1')).toBe('/data/demo/fields/f1/candidates.json');
    expect(c.fieldFileUrl('f1', 'frames/a.png')).toBe('/data/demo/fields/f1/frames/a.png');
    expect(c.systemUrl('eps')).toBe('/data/demo/systems/eps.json');
    expect(c.lightCurveUrl('r-draconis')).toBe('/data/demo/lightcurves/r-draconis.json');
  });

  it('api mode maps resources to endpoints', () => {
    const c = createClient({ mode: 'api', apiBase: 'http://localhost:8000', staticBase: '/data/demo/' });
    expect(c.resourceUrl('manifest')).toBe('http://localhost:8000/api/manifest');
    expect(c.resourceUrl('field', 'f1')).toBe('http://localhost:8000/api/fields/f1');
    expect(c.resourceUrl('known', 'f1')).toBe('http://localhost:8000/api/fields/f1/known');
    expect(c.fieldFileUrl('f1', 'thumb.png')).toBe('http://localhost:8000/data/fields/f1/thumb.png');
    expect(c.systemUrl('eps')).toBe('http://localhost:8000/api/systems/eps');
    expect(c.lightCurveUrl('a/b')).toBe('http://localhost:8000/api/lightcurves/a%2Fb');
  });
});

describe('static light curves', () => {
  // GitHub Pages: scripts/export_static_science.py writes <staticBase>lightcurves/<target_id>.json.
  const c = createClient({ mode: 'static', apiBase: 'http://x', staticBase: '/errante/data/real/' });

  it('reads the exported product file', async () => {
    const body = { target_id: 'r-draconis', synthetic: false };
    const fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify(body),
      { status: 200, headers: { 'content-type': 'application/json' } }));
    vi.stubGlobal('fetch', fetch);
    expect(await c.getLightCurve('r-draconis')).toEqual(body);
    expect(fetch.mock.calls[0][0]).toBe('/errante/data/real/lightcurves/r-draconis.json');
  });

  it('treats a 404 or an HTML app-shell fallback as missing', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('Not Found', { status: 404 })));
    await expect(c.getLightCurve('barnards-star')).rejects.toMatchObject({ status: 404 });
    expect(await loadLightCurve(c, 'barnards-star')).toBe('missing');
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('<!doctype html><title>Errante</title>',
      { status: 200, headers: { 'content-type': 'text/html; charset=utf-8' } })));
    expect(await loadLightCurve(c, 'wise-0855')).toBe('missing');
  });

  it('reports other HTTP errors', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('', { status: 503, statusText: 'Unavailable' })));
    const error = await c.getLightCurve('r-draconis').catch((e: unknown) => e);
    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({ status: 503, message: '503 Unavailable' });
  });
});
