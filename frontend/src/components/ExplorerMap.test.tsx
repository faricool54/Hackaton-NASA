import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it, vi } from 'vitest';
import { ExplorerMap, type ExplorerMapLayout } from './ExplorerMap';
import {
  createPositionSender, createSelectGate, INITIAL_MAP_STATE, parseMapMessage, reduceMapMessage, type MapContext,
  type MapEventMessage, type MapMarker, type MapSelection, type MapState, type MapView,
} from '../api/mapHover';
import skyMapSource from '../../public/sky-map.html?raw';
import explorerMapSource from './ExplorerMap.tsx?raw';

const barnard = { ra: 269.44623, dec: 4.7687 };
const render = (layout?: ExplorerMapLayout, recenterKey?: number) =>
  renderToStaticMarkup(createElement(ExplorerMap, { center: barnard, onSelect: () => {}, layout, recenterKey }));
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

  it('fill keeps the status in its own zone (under the Layers button, not FE-2\'s top left) and the credits outside the menu', () => {
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

describe('ExplorerMap messages from the map iframe (FE-4a)', () => {
  const star = { layer: 'gaia', id: '4472832130942575872', ra: 269.4463725391953, dec: 4.768815881735359, x: 320, y: 211 };

  it('the listener checks origin and source and then validates every message by type', () => {
    expect(explorerMapSource).toContain('if (event.origin !== location.origin || event.source !== frame.current?.contentWindow ||');
    expect(explorerMapSource).toContain("event.data?.source !== 'errante-sky') return;");
    expect(explorerMapSource).toMatch(/const message = parseMapMessage\(event\.data\);\s+if \(!message\) return;/);
  });

  it('accepts well-formed hover, hover-end, cursor, select, view and escape messages', () => {
    expect(parseMapMessage({ type: 'hover', ...star })).toEqual({ type: 'hover', ...star });
    expect(parseMapMessage({ type: 'hover', layer: 'targets', id: 'r-draconis', ra: 248.16723, dec: 66.75502, x: 0, y: 0 }))
      .toMatchObject({ layer: 'targets', id: 'r-draconis' });
    expect(parseMapMessage({ type: 'hover-end', id: star.id })).toEqual({ type: 'hover-end', id: star.id });
    expect(parseMapMessage({ type: 'cursor', ra: 12.5, dec: -3, x: 4, y: 5 })).toEqual({ type: 'cursor', ra: 12.5, dec: -3, x: 4, y: 5 });
    expect(parseMapMessage({ type: 'cursor', ra: null, dec: null, x: 0, y: 0 })).toEqual({ type: 'cursor', ra: null, dec: null, x: 0, y: 0 });
    expect(parseMapMessage({ type: 'select', ra: star.ra, dec: star.dec, sourceId: star.id, layer: 'gaia', x: 320, y: 211 }))
      .toEqual({ type: 'select', ra: star.ra, dec: star.dec, sourceId: star.id, layer: 'gaia', x: 320, y: 211 });
    expect(parseMapMessage({ type: 'select', ra: 10, dec: 20 })).toEqual({ type: 'select', ra: 10, dec: 20 });
    expect(parseMapMessage({ type: 'view', ra: 10, dec: 20, fov: 0.4 })).toEqual({ type: 'view', ra: 10, dec: 20, fov: 0.4 });
    expect(parseMapMessage({ type: 'view', ra: 10, dec: 20, fov: 0.4, fovX: 0.4, fovY: 0.26 }))
      .toEqual({ type: 'view', ra: 10, dec: 20, fov: 0.4, fovX: 0.4, fovY: 0.26 });
    // A bad side is dropped, not trusted: the view falls back to the square bound.
    expect(parseMapMessage({ type: 'view', ra: 10, dec: 20, fov: 0.4, fovX: -1, fovY: 0.26 })).toEqual({ type: 'view', ra: 10, dec: 20, fov: 0.4 });
    expect(parseMapMessage({ type: 'move', ra: 10, dec: 20, fov: 3 })).toEqual({ type: 'move', ra: 10, dec: 20 });
    expect(parseMapMessage({ type: 'escape', extra: '<b>' })).toEqual({ type: 'escape' });
    expect(parseMapMessage({ type: 'ready', wavelengths: [0.75, 'x'] })).toEqual({ type: 'ready', wavelengths: [] });
  });

  it('drops malformed messages', () => {
    const malformed: unknown[] = [
      null, 'hover', 42, {}, { type: 'unknown' },
      { type: 'hover', ...star, layer: 'simbad' },
      { type: 'hover', ...star, id: '<img src=x onerror=alert(1)>' },
      { type: 'hover', ...star, id: 4472832130942575872 },
      { type: 'hover', ...star, layer: 'targets', id: "Barnard's Star" },
      { type: 'hover', ...star, x: Number.NaN },
      { type: 'hover', ...star, y: '211' },
      { type: 'hover', ...star, ra: 360 },
      { type: 'hover', ...star, dec: -90.5 },
      { type: 'hover-end' },
      { type: 'hover-end', id: 'Gaia DR3 1' },
      { type: 'cursor', ra: null, dec: 4, x: 1, y: 1 },
      { type: 'cursor', ra: 1, dec: 4 },
      { type: 'select', ra: Number.POSITIVE_INFINITY, dec: 0 },
      { type: 'select', ra: 10, dec: 20, sourceId: star.id },
      { type: 'select', ra: 10, dec: 20, sourceId: 'abc', layer: 'gaia' },
      { type: 'select', ra: 10, dec: 20, layer: 'gaia' },
      { type: 'view', ra: 10, dec: 20 },
      { type: 'view', ra: 10, dec: 20, fov: 0 },
      { type: 'view', ra: 10, dec: 20, fov: 400 },
      { type: 'move', ra: 10 },
      { type: 'move', ra: '10', dec: 20 },
    ];
    for (const message of malformed) expect(parseMapMessage(message), JSON.stringify(message)).toBeNull();
  });

  it('drops the generic select that follows a marker click within 300 ms, and only that one', () => {
    const gate = createSelectGate(300);
    expect(gate({}, 0)).toBe(true); // empty sky
    expect(gate({ sourceId: star.id }, 1000)).toBe(true); // objectClicked: the marker position
    expect(gate({}, 1001)).toBe(false); // Aladin's click for the same mouse event
    expect(gate({}, 1100)).toBe(true); // a new click on empty sky
    expect(gate({ sourceId: star.id }, 2000)).toBe(true);
    expect(gate({}, 2300)).toBe(false);
    expect(gate({ sourceId: star.id }, 3000)).toBe(true);
    expect(gate({}, 3301)).toBe(true); // more than 300 ms later: a separate click
  });

  it('runs every message after ready through reduceMapMessage and hands on its selection, view and cursor', () => {
    expect(explorerMapSource).toContain('const outcome = reduceMapMessage(mapState.current, message, context);');
    expect(explorerMapSource).toContain('if (outcome.select) selectRef.current(withGaiaEpoch(outcome.select, gaiaIndex, gaiaSet?.epoch));');
    expect(explorerMapSource).toContain('if (outcome.view) { setView(outcome.view); viewRef.current?.(outcome.view); }');
  });
});

describe('ExplorerMap message handling (reduceMapMessage)', () => {
  const star: MapMarker = { layer: 'gaia', id: '4472832130942575872', ra: 269.4463725391953, dec: 4.768815881735359 };
  const target: MapMarker = { layer: 'targets', id: 'barnards-star', ra: 269.44623, dec: 4.7687, label: "Barnard's Star" };
  const known = new Map([star, target].map((m) => [`${m.layer}:${m.id}`, m]));
  const context = (patch: Partial<MapContext> = {}): MapContext => ({
    now: 0, coarse: false, marker: (layer, id) => known.get(`${layer}:${id}`) ?? null, snap: () => null,
    insideField: () => undefined, centre: { x: 478, y: 301 }, ...patch,
  });
  /** Feed [message, time] pairs; collect what ExplorerMap would hand to onSelect, onView and the readout. */
  function play(steps: Array<[MapEventMessage, number]>, patch: Partial<MapContext> = {}, start: MapState = INITIAL_MAP_STATE) {
    let state = start;
    const selects: MapSelection[] = [];
    const views: MapView[] = [];
    const cursors: unknown[] = [];
    for (const [message, now] of steps) {
      const outcome = reduceMapMessage(state, message, context({ ...patch, now }));
      state = outcome.state;
      if (outcome.select) selects.push(outcome.select);
      if (outcome.view) views.push(outcome.view);
      if (outcome.cursor !== undefined) cursors.push(outcome.cursor);
    }
    return { state, selects, views, cursors };
  }
  const hover = (m: MapMarker, x = 320, y = 211): MapEventMessage => ({ type: 'hover', layer: m.layer, id: m.id, ra: m.ra, dec: m.dec, x, y });
  // Aladin's own copy of the position can differ in the last digits; the store keeps the exact value.
  const preciseClick = (m: MapMarker): MapEventMessage =>
    ({ type: 'select', ra: m.ra + 2e-7, dec: m.dec - 2e-7, sourceId: m.id, layer: m.layer, x: 321, y: 212 });
  const genericClick = (ra: number, dec: number): MapEventMessage => ({ type: 'select', ra, dec });

  it('a hover shows the card at the cursor and hover-end of that marker hides it', () => {
    let run = play([[hover(star), 0]]);
    expect(run.state.card).toEqual({ layer: 'gaia', id: star.id, at: { ra: star.ra, dec: star.dec }, x: 320, y: 211, pinned: false });
    run = play([[{ type: 'hover-end', id: '1' }, 5]], {}, run.state);
    expect(run.state.card?.id).toBe(star.id); // another marker's hover-end
    expect(play([[{ type: 'hover-end', id: star.id }, 6]], {}, run.state).state.card).toBeNull();
    // Unknown markers (not in the parent store) never get a card.
    expect(play([[{ ...hover(star), id: '99' } as MapEventMessage, 0]]).state.card).toBeNull();
  });

  it('a marker click selects the stored marker position (≤ 1e-6°), pins the card and drops the generic select', () => {
    const run = play([[hover(star), 900], [preciseClick(star), 1000], [genericClick(269.4465, 4.7689), 1010]]);
    expect(run.selects).toEqual([{ ra: star.ra, dec: star.dec, origin: 'map', layer: 'gaia', sourceId: star.id }]);
    expect(Math.abs(run.selects[0].ra - star.ra)).toBeLessThanOrEqual(1e-6);
    expect(run.state.card).toEqual({ layer: 'gaia', id: star.id, at: { ra: star.ra, dec: star.dec }, x: 321, y: 212, pinned: true });
  });

  it('a later click on empty sky goes through, at the cursor, and closes the pinned card', () => {
    const run = play([[preciseClick(star), 1000], [genericClick(269.4465, 4.7689), 1010], [genericClick(269.5, 4.8), 1400]]);
    expect(run.selects.map(({ ra }) => ra)).toEqual([star.ra, 269.5]);
    expect(run.selects[1]).toEqual({ ra: 269.5, dec: 4.8, origin: 'map' });
    expect(run.state.card).toBeNull();
  });

  it('ignores hovers while a card is pinned', () => {
    const run = play([[preciseClick(star), 0], [hover(target, 10, 10), 50], [{ type: 'hover-end', id: star.id }, 60]]);
    expect(run.state.card).toMatchObject({ id: star.id, pinned: true, x: 321 });
  });

  it('a pan or zoom closes the pinned card unless the map recentres on its marker', () => {
    const pinned = play([[preciseClick(star), 0]]).state;
    expect(play([[{ type: 'move', ra: 269.3, dec: 4.7 }, 10]], {}, pinned).state.card).toBeNull();
    const elsewhere = play([[{ type: 'view', ra: 269.3, dec: 4.7, fov: 0.4 }, 10]], {}, pinned);
    expect(elsewhere.state.card).toBeNull();
    expect(elsewhere.views).toEqual([{ ra: 269.3, dec: 4.7, fov: 0.4 }]);
    const recentred = play([[{ type: 'move', ra: star.ra, dec: star.dec }, 10], [{ type: 'view', ra: star.ra, dec: star.dec, fov: 0.4, fovX: 0.4, fovY: 0.26 }, 510]], {}, pinned);
    expect(recentred.state.card).toMatchObject({ id: star.id, pinned: true, x: 478, y: 301 });
    expect(recentred.views).toEqual([{ ra: star.ra, dec: star.dec, fov: 0.4, fovX: 0.4, fovY: 0.26 }]);
  });

  it('Esc (forwarded by the iframe) closes the card', () => {
    const pinned = play([[preciseClick(star), 0]]).state;
    expect(play([[{ type: 'escape' }, 10]], {}, pinned).state.card).toBeNull();
  });

  it('a target click carries the target id and name, and the open sequence when the click is inside it', () => {
    const run = play([[preciseClick(target), 0]], { insideField: () => 'barnards-star' });
    expect(run.selects).toEqual([{
      ra: target.ra, dec: target.dec, origin: 'map', layer: 'targets', targetId: target.id, label: "Barnard's Star",
      insideFieldId: 'barnards-star',
    }]);
  });

  it('uses the last hover pixel for a click that carries none, and passes the cursor readout through', () => {
    const { x: _x, y: _y, ...noPixel } = preciseClick(star) as Extract<MapEventMessage, { type: 'select' }>;
    expect(play([[hover(star, 40, 50), 0], [noPixel, 10]]).state.card).toMatchObject({ x: 40, y: 50, pinned: true });
    expect(play([[noPixel, 10]]).state.card).toBeNull(); // nowhere to anchor it: the dock still gets the selection
    expect(play([[{ type: 'cursor', ra: 1, dec: 2, x: 0, y: 0 }, 0], [{ type: 'cursor', ra: null, dec: null, x: 0, y: 0 }, 1]]).cursors)
      .toEqual([{ ra: 1, dec: 2 }, null]);
  });

  it('touch: no hover cards, and a tap that missed objectClicked snaps to the marker it aimed at', () => {
    const snap = vi.fn(() => ({ marker: star, x: 300, y: 200 }));
    expect(play([[hover(star), 0]], { coarse: true, snap }).state.card).toBeNull();
    // A tap of 150 ms: Aladin sends only the generic select at the finger.
    const slow = play([[genericClick(star.ra + 3e-4, star.dec), 0]], { coarse: true, snap });
    expect(snap).toHaveBeenCalledWith({ type: 'select', ra: star.ra + 3e-4, dec: star.dec });
    expect(slow.selects).toEqual([{ ra: star.ra, dec: star.dec, origin: 'map', layer: 'gaia', sourceId: star.id }]);
    expect(slow.state.card).toEqual({ layer: 'gaia', id: star.id, at: { ra: star.ra, dec: star.dec }, x: 300, y: 200, pinned: true });
    // A quick tap: objectClicked, then the generic select, which is dropped before any snapping.
    snap.mockClear();
    const quick = play([[preciseClick(star), 0], [genericClick(star.ra + 3e-4, star.dec), 20]], { coarse: true, snap });
    expect(quick.selects).toHaveLength(1);
    expect(snap).not.toHaveBeenCalled();
    // Empty sky: nothing to snap to, a plain select.
    expect(play([[genericClick(10, 20), 0]], { coarse: true, snap: () => null }).selects).toEqual([{ ra: 10, dec: 20, origin: 'map' }]);
    // A mouse never snaps.
    expect(play([[genericClick(star.ra + 3e-4, star.dec), 0]], { snap }).selects[0].sourceId).toBeUndefined();
  });
});

describe('ExplorerMap recenterKey', () => {
  it('re-sends the same position when the key changes', () => {
    const post = vi.fn();
    const send = createPositionSender(post);
    expect(send(barnard, 1)).toBe(true);
    expect(send({ ...barnard }, 1)).toBe(false);
    expect(send(barnard, 2)).toBe(true); // the same preset chosen again
    expect(send({ ra: 10, dec: 20 }, 2)).toBe(true);
    expect(send({ ra: 10, dec: 20 })).toBe(true); // key removed
    expect(post.mock.calls).toEqual([[barnard], [barnard], [{ ra: 10, dec: 20 }], [{ ra: 10, dec: 20 }]]);
  });

  it('is part of the position effect and optional for existing callers', () => {
    expect(render('fill', 3)).toBe(render('fill'));
    expect(explorerMapSource).toContain('}, [ready, center.ra, center.dec, recenterKey]);');
    expect(explorerMapSource).toContain('if (ready) sendPosition(center, recenterKey);');
    expect(render('panel', 3)).toBe(render('panel'));
  });
});

describe('ExplorerMap Gaia DR3 stars per view (FE-4b) and hover layers', () => {
  it('the stars toggle starts off in the panel and on in the fill layout', () => {
    // React's server renderer writes `checked` after the other input attributes.
    const toggle = (html: string) => html.match(/<input type="checkbox" disabled=""( checked="")?\/>(?: |<span>)Gaia DR3 stars/);
    expect(toggle(render('panel'))).not.toBeNull();
    expect(toggle(render('panel'))?.[1]).toBeUndefined();
    expect(toggle(render('fill'))?.[1]).toBe(' checked=""');
  });

  it('server markup has no card, no cursor readout text and no zoom hint before the map reports a view', () => {
    for (const layout of ['panel', 'fill'] as const) {
      expect(render(layout)).not.toMatch(/mp-card|mp-readout|Zoom in to see Gaia stars/);
    }
    expect(render('fill')).toContain('<div class="mp-zone mp-zone--readout"></div>');
  });

  it('lists the challenge targets as a layer, on by default in both layouts', () => {
    expect(render('panel')).toMatch(/<label><input type="checkbox" disabled="" checked=""\/> Challenge targets<\/label>/);
    expect(render('fill')).toMatch(/<label class="mp-check"><input type="checkbox" disabled="" checked=""\/><span>Challenge targets<\/span><\/label>/);
    // Drawn (and credited in the legend) only once the map is ready.
    expect(explorerMapSource).toContain('const targetsShown = ready && showTargets;');
    expect(explorerMapSource).toContain("Gold squares: {targetsLegend}");
  });

  it('says "not SPHEREx" and the source cut in the Gaia legend of both layouts', () => {
    expect(explorerMapSource).toContain('<>{gaiaStars} positions predicted for {gaiaDate}, not SPHEREx detections{gaiaLimit}</>');
    // Wider views name their G limit; the full layer keeps "Gaia DR3 catalog positions predicted for ...".
    expect(explorerMapSource).toContain("`Gaia DR3 stars brighter than G ${gaiaSet.magLimit} in view: catalog`");
    expect(explorerMapSource).toContain("'Gaia DR3 catalog'");
    expect(explorerMapSource).toContain("'Zoom in to see fainter Gaia stars'");
    expect(explorerMapSource).toContain('Cyan circles: {gaiaLegend}');
    expect(explorerMapSource).toContain('Cyan circles show {gaiaLegend} · ESA/Gaia/DPAC');
  });

  it('has an empty live region for pinned cards, without .mp- classes in the panel', () => {
    for (const layout of ['panel', 'fill'] as const) expect(render(layout)).toMatch(/<p role="status" style="position:absolute;[^"]*"><\/p><\/section>$/);
    expect(render('panel')).not.toMatch(/mp-/);
  });

  it('keeps the iframe as the third child in both layouts (#86)', () => {
    const slot = (html: string) => {
      const children: string[] = [];
      let depth = 0;
      for (const tag of html.slice(html.indexOf('>') + 1).matchAll(/<(\/)?(\w+)[^>]*?(\/)?>/g)) {
        if (tag[1]) { depth -= 1; continue; }
        if (depth === 0) children.push(tag[2]);
        if (!tag[3] && !['input', 'br', 'img'].includes(tag[2])) depth += 1;
      }
      return children.indexOf('iframe');
    };
    expect(slot(render('fill'))).toBe(2);
    expect(slot(render('panel'))).toBe(2);
  });
});

describe('sky-map.html hover protocol (FE-4a)', () => {
  const marker = '// FE-4 (FRONTEND_PLAN §6.2)';
  const block = skyMapSource.slice(skyMapSource.indexOf(marker));

  it('registers each Aladin event once, after the #114 click handler and the existing message handler', () => {
    for (const name of ['click', 'objectHovered', 'objectHoveredStop', 'objectClicked', 'mouseMove', 'positionChanged', 'zoomChanged']) {
      expect(skyMapSource.split(`map.on('${name}'`).length - 1, name).toBe(1);
    }
    expect(skyMapSource.indexOf(marker)).toBeGreaterThan(skyMapSource.indexOf("map.on('click'"));
    expect(skyMapSource.indexOf(marker)).toBeGreaterThan(skyMapSource.indexOf("if (p.type === 'allwise')"));
  });

  it('never builds HTML from data and never opens the Aladin popup', () => {
    // Comments may name what is avoided; the code may not use it.
    const code = skyMapSource.replace(/\/\*[\s\S]*?\*\/|\/\/.*$/gm, '');
    expect(code).not.toMatch(/innerHTML|showPopup|insertAdjacentHTML|outerHTML|onClick:/);
  });

  it('sends one select per click, skips footprints, and throttles the cursor and the view', () => {
    expect(block).toContain("if (!k || typeof k.isFootprint !== 'function' || k.isFootprint()) return null;");
    expect(block).toContain('if (!m || (e && e === clickEvent)) return;');
    expect(block).toContain("send({ type: 'select', ra: m.ra, dec: m.dec, sourceId: m.id, layer: m.layer, ...at(e) });");
    expect(block).toContain('if (!pointerFrame) pointerFrame = requestAnimationFrame(sendCursor);');
    expect(block).toContain('if (!pointer || hover.resume(pointer) || hover.busy) return;');
    expect(block).toContain("map.pix2world(pointer.x, pointer.y, 'icrs')");
    expect(block).toContain('viewTimer = setTimeout(sendView, 500);');
    expect(block).toMatch(/getElementById\('map'\)\.addEventListener\('mouseleave'[\s\S]*?hover\.hide\(\);[\s\S]*?send\(\{ type: 'cursor', ra: null, dec: null/);
    // Only the debounced view (which queries VizieR) carries the field of view; 'move' only closes a pinned card.
    expect(block).toContain("send({ type: 'move', ra: ((ra % 360) + 360) % 360, dec });");
    expect(block).toContain('const view = { ra: ((ra % 360) + 360) % 360, dec, fov, fovX, fovY };');
    expect(block).not.toMatch(/followClick/);
  });

  describe('hover bookkeeping (createHoverTracker, run from the page source)', () => {
    type Tracker = { busy: boolean; enter(o: object, m: object, e: object, xy: object): void; leave(o: object, xy: object): void;
      hide(): void; resume(xy: object): boolean };
    const source = skyMapSource.slice(skyMapSource.indexOf('// hover-tracker:begin'), skyMapSource.indexOf('// hover-tracker:end'));
    const createHoverTracker = new Function(`${source}\nreturn createHoverTracker;`)() as (post: (m: object) => void) => Tracker;
    const marker = { layer: 'gaia', id: '4472832130942575872', ra: 269.4463725, dec: 4.7688159 };
    const other = { layer: 'gaia', id: '4472832513187484544', ra: 269.45, dec: 4.77 };
    const xy = { x: 10, y: 20 };
    const setup = () => {
      const sent: object[] = [];
      return { sent, tracker: createHoverTracker((m) => sent.push(m)) };
    };

    it('keeps the card when the parent replaces the markers under the cursor (same id, new Aladin object)', () => {
      const { sent, tracker } = setup();
      const before = {}, after = {};
      tracker.enter(before, marker, {}, xy);
      // New Gaia set: Aladin reports hovered(new) and then hoverStop(old) for the same mouse event.
      const event = {};
      tracker.enter(after, marker, event, { x: 11, y: 20 });
      tracker.leave(before, { x: 11, y: 20 });
      expect(sent).toEqual([{ type: 'hover', ...marker, ...xy }, { type: 'hover', ...marker, x: 11, y: 20 }]);
      expect(tracker.busy).toBe(true);
      tracker.leave(after, xy);
      expect(sent.at(-1)).toEqual({ type: 'hover-end', id: marker.id });
      expect(tracker.busy).toBe(false);
    });

    it('hides the card when the view moves and shows it again at the next pointer if Aladin still has it', () => {
      const { sent, tracker } = setup();
      const star = {};
      tracker.enter(star, marker, {}, xy);
      tracker.hide();
      expect(sent.at(-1)).toEqual({ type: 'hover-end', id: marker.id });
      // The cursor readout stays off over the star, and Aladin will not report it again: resume shows it.
      expect(tracker.busy).toBe(true);
      expect(tracker.resume({ x: 30, y: 40 })).toBe(true);
      expect(sent.at(-1)).toEqual({ type: 'hover', ...marker, x: 30, y: 40 });
      expect(tracker.resume({ x: 31, y: 40 })).toBe(false); // already shown
      // The pointer left the star after a mouseleave: Aladin's hoverStop clears it without a message.
      tracker.hide();
      const count = sent.length;
      tracker.leave(star, xy);
      expect(sent).toHaveLength(count);
      expect(tracker.resume(xy)).toBe(false);
      expect(tracker.busy).toBe(false);
    });

    it('sends one hover per mouse event and moves the card to the next marker when the shown one is left', () => {
      const { sent, tracker } = setup();
      const a = {}, b = {}, event = {};
      tracker.enter(a, marker, event, xy);
      tracker.enter(b, other, event, xy);
      expect(sent).toEqual([{ type: 'hover', ...marker, ...xy }]);
      tracker.leave(a, xy);
      expect(sent.at(-1)).toEqual({ type: 'hover', ...other, ...xy });
      tracker.leave(b, xy);
      expect(sent.at(-1)).toEqual({ type: 'hover-end', id: other.id });
    });
  });

  it('draws Gaia circles and challenge-target squares as two catalogs, large enough to point at', () => {
    expect(skyMapSource).toMatch(/A\.catalog\(\{ name: 'Gaia DR3 predictions', color: '#6ff4f1', hoverColor: '#ffffff'[^)]*shape: 'circle', sourceSize: 8 \}\)/);
    expect(block).toMatch(/A\.catalog\(\{ name: 'Challenge targets', color: '#f5c26b', hoverColor: '#ffffff'[^)]*shape: 'square', sourceSize: 8/);
    expect(skyMapSource).toContain("A.source(ra, dec, { name: `Gaia DR3 ${sourceId}`, id: sourceId, layer: 'gaia' })");
    expect(block).toContain("A.source(ra, dec, { id, layer: 'targets', label })");
  });
});

describe('ExplorerMap folded legend', () => {
  it('starts with the legend folded behind a toggle and keeps the credits visible', () => {
    const html = renderToStaticMarkup(createElement(ExplorerMap, { center: { ra: 269.44623, dec: 4.7687 }, onSelect: () => {}, layout: 'fill' }));
    expect(html).toContain('Static coadd · not a video');
    if (html.includes('class="mp-legend"')) {
      expect(html).toMatch(/<button type="button" class="mp-legend-toggle" aria-expanded="false"[^>]*>Legend ▸<\/button>/);
      expect(html).toMatch(/<ul class="mp-legend" aria-label="Map legend" id="[^"]+" hidden="">/);
    }
  });
});
