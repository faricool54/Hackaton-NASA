import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';
import { ExplorerMap, type ExplorerMapLayout } from './ExplorerMap';
import skyMapSource from '../../public/sky-map.html?raw';

const barnard = { ra: 269.44623, dec: 4.7687 };
const render = (layout?: ExplorerMapLayout) =>
  renderToStaticMarkup(createElement(ExplorerMap, { center: barnard, onSelect: () => {}, layout }));
const text = (html: string) => html.replace(/<[^>]+>/g, '').replace(/&amp;/g, '&');

describe('ExplorerMap layouts (FE-4a.0)', () => {
  it('panel is the default and keeps the toolbar above and the credits below the map', () => {
    const html = render();
    expect(render('panel')).toBe(html);
    expect(html).toContain('<section class="explorer-map" aria-label="Infrared sky map">');
    expect(html).toContain('<div class="toolbar map-heading"><strong>SPHEREx DR1 · infrared sky</strong>');
    expect(html).toContain('<label>Context wavelength <select aria-label="Map wavelength" disabled=""><option value="90" selected="">4.600 µm</option></select></label>');
    expect(html).toContain('<p class="muted map-message" role="status">Loading Aladin sky map…</p>');
    expect(html).toContain('class="sky-map-frame"');
    expect(text(html)).toContain('This map is a static coadd, not a video. Wavelength changes affect this context map only.');
    expect(text(html)).toContain('NASA/SPHEREx · Caltech/IPAC · Aladin Lite 3.8.2 (GPL-3)');
    // Nothing of the fill layout leaks into the panel.
    expect(html).not.toMatch(/mp-|aria-expanded|Layers/);
    const order = ['toolbar map-heading', 'map-message', '<iframe', 'map-credit'].map((s) => html.indexOf(s));
    expect(order.every((at, k) => at >= 0 && (k === 0 || at > order[k - 1]))).toBe(true);
  });

  it('fill moves the controls into a closed Layers menu over a full-size map', () => {
    const html = render('fill');
    expect(html).toContain('<section class="explorer-map mp-root mp-fill" aria-label="Infrared sky map">');
    expect(html).toContain('class="sky-map-frame mp-frame"');
    expect(html).not.toContain('toolbar map-heading');
    const button = html.match(/<button type="button" class="mp-glass mp-layers-button" aria-expanded="false" aria-controls="([^"]+)">Layers <span class="mp-caret" aria-hidden="true">▾<\/span><\/button>/);
    expect(button).not.toBeNull();
    const menuStart = html.indexOf(`<div id="${button![1]}" class="mp-glass mp-popover" role="group" aria-label="Map layers" hidden="">`);
    expect(menuStart).toBeGreaterThan(html.indexOf('mp-layers-button'));
    const menu = html.slice(menuStart, html.indexOf('mp-zone--status'));
    expect(menu).toContain('<select aria-label="Map wavelength" disabled="">');
    expect(text(menu)).toContain('AllWISE context (45%)');
    expect(text(menu)).toContain('Wavelength changes affect this context map only.');
    expect(menu).not.toMatch(/Caltech\/IPAC|Aladin Lite 3\.8\.2|Static coadd/);
  });

  it('fill keeps the status top left and the credits visible outside the menu', () => {
    const html = render('fill');
    const status = html.slice(html.indexOf('mp-zone--status'), html.indexOf('<iframe'));
    expect(status).toContain('<p class="mp-glass mp-note" role="status">Loading Aladin sky map…</p>');
    const strip = html.slice(html.indexOf('mp-zone--credits'));
    expect(strip).toContain('class="mp-glass mp-strip"');
    expect(text(strip)).toContain('Static coadd · not a video · NASA/SPHEREx · Caltech/IPAC · Aladin Lite 3.8.2 (GPL-3)');
    // No layer is on yet: no legend and no Gaia or AllWISE credit.
    expect(strip).not.toMatch(/mp-legend|ESA\/Gaia|AllWISE/);
    expect(html.indexOf('mp-zone--credits')).toBeGreaterThan(html.indexOf('<iframe'));
  });

  it('both layouts load the same map page', () => {
    const iframe = (html: string) => html.match(/<iframe src="([^"]+)" title="([^"]+)"/)?.slice(1);
    expect(iframe(render('fill'))).toEqual(iframe(render('panel')));
    // BASE_URL follows VITE_BASE (GitHub Pages builds set it), so do not hard-code '/'.
    expect(iframe(render('panel'))).toEqual([`${import.meta.env.BASE_URL}sky-map.html`, 'Interactive SPHEREx sky map']);
  });

  it('draws the sequence footprint in the SPHEREx colour, not the 3D-model violet', () => {
    expect(skyMapSource).toMatch(/graphicOverlay\(\{ name: 'Sequence footprint', color: '#7cc4ff'/);
    expect(skyMapSource).not.toContain('#c4a5ff');
    // The #86 plane fix and the #114 drag filter are still there.
    expect(skyMapSource).toContain('if (layer.added) layer.setFrequency');
    expect(skyMapSource).toContain('if (p && !p.isDragging && Number.isFinite(p.ra) && Number.isFinite(p.dec))');
  });

  it('hides only the Aladin corners under the fill overlays, and only in the fill layout', () => {
    expect(skyMapSource).toContain(
      "if (p.type === 'layout') document.documentElement.dataset.layout = p.layout === 'fill' ? 'fill' : 'panel';");
    const rule = skyMapSource.match(/([^{}]*)\{ display: none; \}/)?.[1] ?? '';
    const selectors = rule.replace(/\/\*[\s\S]*?\*\//g, '').split(',').map((s) => s.trim());
    expect(selectors).toEqual([
      "html[data-layout='fill'] .aladin-cooFrame", "html[data-layout='fill'] .aladin-location",
      "html[data-layout='fill'] .aladin-projection-control", "html[data-layout='fill'] .aladin-logo-container",
    ]);
  });
});
