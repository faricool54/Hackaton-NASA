import { describe, expect, it } from 'vitest';
import { createClient } from './client';

describe('client URLs', () => {
  it('static mode maps resources to files', () => {
    const c = createClient({ mode: 'static', apiBase: 'http://x', staticBase: '/data/demo/' });
    expect(c.resourceUrl('manifest')).toBe('/data/demo/manifest.json');
    expect(c.resourceUrl('field', 'f1')).toBe('/data/demo/fields/f1/field.json');
    expect(c.resourceUrl('candidates', 'f1')).toBe('/data/demo/fields/f1/candidates.json');
    expect(c.fieldFileUrl('f1', 'frames/a.png')).toBe('/data/demo/fields/f1/frames/a.png');
  });

  it('api mode maps resources to endpoints', () => {
    const c = createClient({ mode: 'api', apiBase: 'http://localhost:8000', staticBase: '/data/demo/' });
    expect(c.resourceUrl('manifest')).toBe('http://localhost:8000/api/manifest');
    expect(c.resourceUrl('field', 'f1')).toBe('http://localhost:8000/api/fields/f1');
    expect(c.resourceUrl('known', 'f1')).toBe('http://localhost:8000/api/fields/f1/known');
    expect(c.fieldFileUrl('f1', 'thumb.png')).toBe('http://localhost:8000/data/fields/f1/thumb.png');
  });
});
