import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';
import {
  BottomSheet, FLICK_SPEED, nextSnap, SHEET_SNAPS, snapAfterDrag, snapAfterKey, stepSnap, type SheetSnap,
} from './BottomSheet';
import { isMapEscape, PHONE_QUERY, raiseSheet, selectionSnap, SHORT_QUERY } from './SkyExplorer';

// Vitest does not load CSS (`?raw` gives ''), so the stylesheets are read from disk (node:fs, no @types/node here).
const readCss = async (name: string) => {
  type Fs = { readFileSync: (p: URL, enc: 'utf8') => string };
  const fs = (await import(/* @vite-ignore */ 'node:fs' as string)) as Fs;
  return fs.readFileSync(new URL(`../styles/${name}`, import.meta.url), 'utf8');
};

const render = (snap: SheetSnap) => renderToStaticMarkup(createElement(BottomSheet,
  { label: 'position details', snap, onSnapChange: () => {}, children: createElement('p', null, 'Dock content') }));

describe('BottomSheet markup (FE-10)', () => {
  it('peek: a labelled region with the handle and the content, and no close button', () => {
    expect(render('peek')).toBe('<section class="sh-root" data-snap="peek" aria-label="position details">'
      + '<div class="sh-bar"><button type="button" class="sh-handle" aria-label="Expand position details" '
      + 'aria-expanded="false"><span class="sh-grip" aria-hidden="true"></span></button></div>'
      + '<div class="sh-body"><p>Dock content</p></div></section>');
  });

  it('half: the handle says it expands to full height and × lowers the sheet', () => {
    const html = render('half');
    expect(html).toContain('data-snap="half"');
    expect(html).toContain('aria-label="Expand position details to full height" aria-expanded="true"');
    expect(html).toContain('<button type="button" class="sh-close" aria-label="Collapse position details">'
      + '<span aria-hidden="true">×</span></button>');
    expect(html).toContain('<p>Dock content</p>');
  });

  it('full: the handle collapses, × is still there, and the content is the same element tree', () => {
    const html = render('full');
    expect(html).toContain('data-snap="full"');
    expect(html).toContain('class="sh-handle" aria-label="Collapse position details" aria-expanded="true"');
    expect(html).toContain('class="sh-close"');
    // Only the bar changes between heights: the children keep their place, so nothing under them remounts.
    const body = (markup: string) => markup.slice(markup.indexOf('<div class="sh-body">'));
    expect(body(html)).toBe(body(render('peek')));
    expect(body(render('half'))).toBe(body(render('peek')));
  });

  it('never touches the browser history and keeps 44 px controls', async () => {
    const source = (await import('./BottomSheet.tsx?raw')).default;
    expect(source).not.toMatch(/history\.|pushState|popstate/);
    const sheetCss = await readCss('sheet.css');
    expect(sheetCss).toMatch(/\.sh-bar \{[^}]*height: var\(--touch-min, 44px\)/);
    expect(sheetCss).toMatch(
      /\.sh-root \.sh-close \{[^}]*width: var\(--touch-min, 44px\);\s*height: var\(--touch-min, 44px\)/);
    expect(sheetCss).toMatch(/\.sh-root \.sh-handle \{[^}]*touch-action: none/);
  });
});

describe('BottomSheet heights', () => {
  it('a tap cycles peek → half → full → peek; arrows step and stop at the ends', () => {
    expect(SHEET_SNAPS.map(nextSnap)).toEqual(['half', 'full', 'peek']);
    expect(stepSnap('peek', 1)).toBe('half');
    expect(stepSnap('full', 1)).toBe('full');
    expect(stepSnap('half', -1)).toBe('peek');
    expect(stepSnap('peek', -1)).toBe('peek');
  });

  it('a slow release goes to the nearest height, a flick one step in its direction', () => {
    expect(snapAfterDrag('peek', 0.3, 0)).toBe('peek');
    expect(snapAfterDrag('peek', 0.5, 0)).toBe('half');
    expect(snapAfterDrag('half', 0.9, 0)).toBe('full');
    expect(snapAfterDrag('full', 0.1, 0)).toBe('peek');
    expect(snapAfterDrag('half', 0.55, FLICK_SPEED + 0.1)).toBe('full');
    expect(snapAfterDrag('half', 0.45, -(FLICK_SPEED + 0.1))).toBe('peek');
    expect(snapAfterDrag('full', 0.95, FLICK_SPEED + 1)).toBe('full');
  });

  it('Esc lowers an open sheet to peek unless something above already took it', () => {
    expect(snapAfterKey('Escape', 'full', false)).toBe('peek');
    expect(snapAfterKey('Escape', 'half', false)).toBe('peek');
    expect(snapAfterKey('Escape', 'peek', false)).toBeNull();
    // A pinned map card or a theater view consumed this Esc first (FE-11 order).
    expect(snapAfterKey('Escape', 'full', true)).toBeNull();
    expect(snapAfterKey('Enter', 'full', false)).toBeNull();
  });
});

describe('Explorer on phones (FE-10)', () => {
  it('a selection raises a lowered sheet to half and leaves a taller one alone', () => {
    expect(raiseSheet('peek')).toBe('half');
    expect(raiseSheet('half')).toBe('half');
    expect(raiseSheet('full')).toBe('full');
    expect(raiseSheet('peek', 'full')).toBe('full');
    expect(raiseSheet('half', 'full')).toBe('full');
  });

  it('a chip, search or tab on a short phone goes to full; a pick on the map keeps it in view at half', () => {
    expect(SHORT_QUERY).toBe('(max-height: 700px)');
    expect(selectionSnap(false, true)).toBe('full');
    expect(selectionSnap(true, true)).toBe('half');
    expect(selectionSnap(false, false)).toBe('half');
    expect(selectionSnap(true, false)).toBe('half');
  });

  it("hears the map iframe's forwarded Esc only from this origin", () => {
    const origin = 'https://errante.example';
    expect(isMapEscape({ origin, data: { source: 'errante-sky', type: 'escape' } }, origin)).toBe(true);
    expect(isMapEscape({ origin: 'https://other.example', data: { source: 'errante-sky', type: 'escape' } }, origin)).toBe(false);
    expect(isMapEscape({ origin, data: { source: 'errante-sky', type: 'view' } }, origin)).toBe(false);
    expect(isMapEscape({ origin, data: null }, origin)).toBe(false);
  });

  it('keeps the map credits above a half sheet (FRONTEND_PLAN §4.4)', async () => {
    const explorerCss = await readCss('explorer.css');
    expect(explorerCss).toContain(".xp-explorer[data-sheet='half'] .xp-map .mp-root .mp-zone--credits { bottom: calc(50% - var(--sh-peek) / 2 + 8px); }");
  });

  it('switches at the same width in the component and in explorer.css', async () => {
    const explorerCss = await readCss('explorer.css');
    expect(PHONE_QUERY).toBe('(max-width: 900px)');
    expect(explorerCss).toContain(`@media ${PHONE_QUERY} {`);
    // The map is never hidden on phones (§4.8): no display:none or visibility on the map or its iframe.
    const phone = explorerCss.slice(explorerCss.indexOf(`@media ${PHONE_QUERY} {`));
    const hiding = phone.split('}').map((rule) => rule.split('{'))
      .filter(([, body]) => /display: none|visibility: hidden/.test(body ?? ''));
    expect(hiding.length).toBeGreaterThan(0);
    for (const [selector] of hiding) {
      // The element a hiding rule applies to is the last compound of each selector in the list.
      const subjects = selector.replace(/\/\*[\s\S]*?\*\//g, '').split(',')
        .map((part) => part.trim().split(/\s+/).pop() ?? '');
      for (const subject of subjects) expect(subject).not.toMatch(/xp-map|mp-root|mp-frame|iframe/);
    }
  });
});
