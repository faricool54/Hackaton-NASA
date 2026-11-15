import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { matchesMediaQuery, useMediaQuery } from './useMediaQuery';

function Probe() {
  return createElement('p', null, useMediaQuery('(max-width: 900px)') ? 'phone' : 'desktop');
}

describe('useMediaQuery (FE-10)', () => {
  afterEach(() => vi.unstubAllGlobals());

  it('is false on the server, where there is no window', () => {
    expect(typeof window).toBe('undefined');
    expect(matchesMediaQuery('(max-width: 900px)')).toBe(false);
    expect(renderToStaticMarkup(createElement(Probe))).toBe('<p>desktop</p>');
  });

  it('reads matchMedia in a browser, but a server render still uses the server value', () => {
    const queries: string[] = [];
    vi.stubGlobal('window', {
      matchMedia: (query: string) => {
        queries.push(query);
        return { matches: true, addEventListener: () => {}, removeEventListener: () => {} };
      },
    });
    expect(matchesMediaQuery('(max-width: 900px)')).toBe(true);
    expect(queries).toEqual(['(max-width: 900px)']);
    expect(renderToStaticMarkup(createElement(Probe))).toBe('<p>desktop</p>');
  });

  it('is false where matchMedia is missing', () => {
    vi.stubGlobal('window', {});
    expect(matchesMediaQuery('(max-width: 900px)')).toBe(false);
  });
});
