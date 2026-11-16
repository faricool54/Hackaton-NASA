// FE-12: compact mode of the 3D viewer and body panel (server-rendered markup, no WebGL), and the inline-style
// budget of the 3D pages.
import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { beforeAll, describe, expect, it } from 'vitest';
import type { SystemModel } from '../api/types';
import { BodyPanel } from '../components/BodyPanel';
import { SystemViewer } from '../components/SystemViewer';

const SYSTEMS = Object.values(
  import.meta.glob<SystemModel>('../../../data/products/systems/*.json', { eager: true, import: 'default' }),
);
const DEMO = Object.values(
  import.meta.glob<SystemModel>('../../../data/demo/systems/*.json', { eager: true, import: 'default' }),
).find((s) => s.provenance.synthetic)!;
const system = (id: string): SystemModel => {
  const s = SYSTEMS.find((x) => x.id === id);
  if (!s) throw new Error(`system ${id} missing`);
  return s;
};

const viewer = (props: { compact?: boolean; fullViewHref?: string; selectedId?: string | null }) =>
  renderToStaticMarkup(
    createElement(SystemViewer, {
      system: system('barnards-star'),
      selectedId: props.selectedId ?? null,
      onSelect: () => {},
      fieldExists: true, // no manifest fetch (effects do not run on the server anyway)
      compact: props.compact,
      fullViewHref: props.fullViewHref,
    }),
  );

/** The transport's children, in order, as their opening tags (enough to compare the markup order). */
function transportChildren(html: string): string[] {
  const start = html.indexOf('class="blink-controls s3d-transport"');
  expect(start).toBeGreaterThan(0);
  const tail = html.slice(html.indexOf('>', start) + 1);
  const out: string[] = [];
  let depth = 0;
  for (const m of tail.matchAll(/<(\/?)([a-z]+)([^>]*?)(\/?)>/g)) {
    const [, close, tag, attrs, selfClose] = m;
    if (['input', 'br', 'img', 'hr'].includes(tag) && !close) {
      if (depth === 0) out.push(`<${tag}${attrs}>`);
      continue;
    }
    if (close) {
      if (depth === 0) break; // the transport's own closing tag
      depth -= 1;
    } else {
      if (depth === 0) out.push(`<${tag}${attrs}>`);
      if (!selfClose) depth += 1;
    }
  }
  return out;
}

describe('SystemViewer compact (FE-12)', () => {
  it('renders the stage with the compact modifier and keeps the honesty chip on it', () => {
    const html = viewer({ compact: true });
    expect(html).toContain('class="system-viewer s3d-viewer s3d-viewer--compact"');
    expect(html).toMatch(/class="s3d-stage s3d-stage--compact"[^>]*role="group"/);
    const stage = html.slice(html.indexOf('s3d-stage--compact'));
    expect(stage.indexOf('3D MODEL · NOT AN IMAGE')).toBeGreaterThan(0);
    expect(stage.indexOf('3D MODEL · NOT AN IMAGE')).toBeLessThan(stage.indexOf('blink-controls'));
  });

  it('shows the full-view link only in compact mode with an href', () => {
    const html = viewer({ compact: true, fullViewHref: '#/system/barnards-star' });
    expect(html).toContain('<a class="s3d-fullview" href="#/system/barnards-star">Open full 3D view →</a>');
    expect(viewer({ compact: true })).not.toContain('Open full 3D view');
    expect(viewer({ fullViewHref: '#/system/barnards-star' })).not.toContain('Open full 3D view');
  });

  it('keeps Play first and folds the view options and the legends behind disclosures', () => {
    const html = viewer({ compact: true, selectedId: 'barnards-star' });
    const kids = transportChildren(html);
    expect(kids[0]).toMatch(/^<button[^>]*aria-label="Pause"/);
    // Play, speed, days/s, clock, Whole system, then the folded view options.
    expect(kids).toHaveLength(6);
    expect(kids[3]).toBe('<span role="group" aria-label="Clock" class="s3d-clock">');
    expect(kids[4]).toMatch(/^<button/);
    expect(kids[5]).toBe('<details class="s3d-options">');
    expect(html).toContain('⤢ Whole system');
    expect(html).toContain('<summary>View options</summary>');
    expect(html).toContain('<summary>Colour, surface and date legends</summary>');
    const options = html.slice(html.indexOf('<summary>View options</summary>'));
    for (const t of ['Distances', 'Colour', 'orbits', 'labels']) expect(options.indexOf(t), t).toBeGreaterThan(0);
    // AGENTS.md rule 3 (faricool54 on #147): the model-time / arbitrary-phase line stays visible, before the disclosure.
    const fold = html.indexOf('<details class="s3d-disclosure s3d-legend-details">');
    expect(fold).toBeGreaterThan(0);
    expect(html.indexOf('drag to rotate')).toBeGreaterThan(-1);
    expect(html.indexOf('drag to rotate')).toBeLessThan(fold);
    expect(html.indexOf('Model time:')).toBeLessThan(fold);
  });

  it('keeps the orbit legend visible in compact (assumed / hypothetical orbits are honesty lines)', () => {
    const sys = SYSTEMS.find((s) => s.bodies.some((b) => b.orbit && b.orbit.quality && b.orbit.quality !== 'fitted'));
    if (!sys) return; // no shipped system with a non-fitted orbit: nothing to check
    const html = renderToStaticMarkup(createElement(SystemViewer, { system: sys, selectedId: null, onSelect: () => undefined, compact: true }));
    const fold = html.indexOf('<details class="s3d-disclosure s3d-legend-details">');
    const legend = html.indexOf('orbit-legend');
    if (legend >= 0) expect(legend).toBeLessThan(fold);
  });
});

describe('SystemViewer full page (unchanged sections)', () => {
  it('keeps the stage, the transport in its order and the open legends', () => {
    const html = viewer({ selectedId: 'barnards-star' });
    expect(html).toContain('class="system-viewer s3d-viewer"');
    expect(html).toContain('class="s3d-stage"');
    expect(html).not.toContain('s3d-stage--compact');
    expect(html).toContain('3D MODEL · NOT AN IMAGE');
    expect(html).not.toContain('<details');
    const kids = transportChildren(html);
    // Play, speed, days/s, clock, Distances, Colour, orbits, labels, Whole system (BenjaminPondal #26/#27 order).
    expect(kids).toHaveLength(9);
    expect(kids[0]).toMatch(/^<button[^>]*aria-label="Pause"/);
    expect(kids[1]).toBe('<label class="speed-control">');
    expect(kids[2]).toBe('<span class="muted small">');
    expect(kids[3]).toBe('<span role="group" aria-label="Clock" class="s3d-clock">');
    expect(kids.slice(4, 8)).toEqual(['<label>', '<label>', '<label class="small">', '<label class="small">']);
    expect(kids[8]).toMatch(/^<button/);
    for (const t of ['Free-running', 'Dataset time (SPHEREx 2025-2026)', 'compressed (log)', 'true proportions', ' orbits', ' labels', '⤢ Whole system']) {
      expect(html, t).toContain(t);
    }
    expect(html).toContain('<div class="s3d-legends">');
    expect(html).toContain('drag to rotate, scroll to zoom, click a body to enter it');
  });
});

describe('BodyPanel compact (FE-12)', () => {
  const s = system('barnards-star');
  const star = s.bodies[0];

  it('shows name, kind, temperature, radius and the fact origins, with the full panel folded', () => {
    const html = renderToStaticMarkup(createElement(BodyPanel, { system: s, body: star, fieldExists: true, compact: true }));
    expect(html).toContain('s3d-body--compact');
    expect(html).toContain(`<h2>${star.name.replace(/'/g, '&#x27;')}</h2>`);
    expect(html).toContain('Star');
    // Each value under its fact's label, with that fact's origin chip (the catalog radius 0.185 R☉, not Gaia's 0.202).
    expect(html).toMatch(/<dt>Temperature<\/dt><dd>~3195 K <span class="s3d-origin s3d-origin--catalog"/);
    expect(html).toMatch(/<dt>Radius<\/dt><dd>~130,000 km \(0\.\d+ R☉\) <span class="s3d-origin s3d-origin--catalog"/);
    expect(html).toContain('s3d-origin s3d-origin--catalog');
    expect(html).toContain('catalog, not measured by SPHEREx');
    expect(html).toContain('<summary>All facts, sources and drawing notes</summary>');
    // The full panel is inside the disclosure, without a second heading.
    const inside = html.slice(html.indexOf('All facts, sources and drawing notes'));
    expect(inside).toContain('class="facts s3d-facts"');
    expect(inside).toContain('How this body is drawn');
    expect(inside).not.toContain('<h2>');
  });

  it('keeps a qualified label, its origin and its unverified tag next to the value, not only in the disclosure', () => {
    const rw = system('rw-aurigae');
    const a = rw.bodies.find((b) => b.id === 'rw-aur-a')!;
    const html = renderToStaticMarkup(createElement(BodyPanel, { system: rw, body: a, fieldExists: true, compact: true }));
    const visible = html.slice(0, html.indexOf('<details'));
    expect(visible).toMatch(
      /<dt>Radius \(derived from the catalog luminosity\)<\/dt><dd>~[\d,]+ km \([\d.]+ R☉\) <span class="s3d-origin s3d-origin--derived"[^>]*>derived<\/span><span class="unverified s3d-unverified"[^>]*> unverified<\/span><\/dd>/,
    );
    // The disk's radius is its dust disk (19 AU), not the 58 AU gas disk.
    const disk = rw.bodies.find((b) => b.id === 'rw-aur-a-disk')!;
    const diskHtml = renderToStaticMarkup(createElement(BodyPanel, { system: rw, body: disk, fieldExists: true, compact: true }));
    expect(diskHtml).toContain('<dt>Dust disk radius</dt>');
    // A body whose drawn values carry no fact keeps the plain labels.
    const sun = renderToStaticMarkup(createElement(BodyPanel, { system: DEMO, body: DEMO.bodies[0], fieldExists: true, compact: true }));
    expect(sun).toMatch(/<dt>Temperature<\/dt><dd>~\d+ K<\/dd><dt>Radius<\/dt><dd>~[\d,]+ km \([\d.]+ R☉\)<\/dd>/);
  });

  it('puts the system-wide unverified flag on its own line, not among the body origin chips (#138 review)', () => {
    const rw = system('rw-aurigae'); // one unverified fact in the system
    const a = rw.bodies.find((b) => b.id === 'rw-aur-a')!;
    const html = renderToStaticMarkup(createElement(BodyPanel, { system: rw, body: a, fieldExists: true, compact: true }));
    const visible = html.slice(0, html.indexOf('<details'));
    const origins = /<p class="s3d-origins small">(.*?)<\/p>/.exec(visible)?.[1];
    expect(origins).toContain('All facts:');
    expect(origins).not.toContain('s3d-unverified');
    expect(origins).not.toContain('System model');
    expect(visible).toContain(
      '</p><p class="small s3d-system-unverified"><span class="unverified s3d-unverified" title="Some values of this system are estimates that no catalog or paper states">System model: some values unverified</span></p>',
    );
    // A system whose facts are all verified has no such line.
    const barnard = renderToStaticMarkup(createElement(BodyPanel, { system: s, body: star, fieldExists: true, compact: true }));
    expect(barnard).not.toContain('System model: some values unverified');
  });

  it('the full panel keeps its sections', () => {
    const html = renderToStaticMarkup(createElement(BodyPanel, { system: s, body: star, fieldExists: true }));
    expect(html).toMatch(/^<div class="panel body-panel s3d-body"><h2>/);
    expect(html).not.toContain('s3d-body--compact');
    expect(html).toContain('Model parameters used to draw the scene');
    expect(html).toContain('class="facts s3d-facts"');
    expect(html).toContain('How this body is drawn');
    expect(html).toContain('At SPHEREx scale');
    expect(html).toContain('Orbited by:');
  });
});

describe('inline-style budget of the 3D pages (FE-12)', () => {
  // style={{ … }} and style={CONST}: only truly dynamic values (colours computed at run time) may stay inline.
  const SOURCES = import.meta.glob<string>(
    [
      '../components/SystemViewer.tsx',
      '../components/BodyPanel.tsx',
      '../pages/SystemsPage.tsx',
      '../pages/SystemPage.tsx',
      './ObjectSystemPreview.tsx',
    ],
    { eager: true, query: '?raw', import: 'default' },
  );

  it('keeps at most 10 inline styles in the 3D pages, viewer and body panel', () => {
    expect(Object.keys(SOURCES)).toHaveLength(5);
    const counts = Object.fromEntries(Object.entries(SOURCES).map(([path, src]) => [path, (src.match(/style=\{/g) ?? []).length]));
    const total = Object.values(counts).reduce((a, b) => a + b, 0);
    expect(total, JSON.stringify(counts)).toBeLessThanOrEqual(10);
    expect(counts['../pages/SystemPage.tsx']).toBe(0);
    expect(counts['../pages/SystemsPage.tsx']).toBe(0);
  });

  it('every one of them imports the .s3d- stylesheet', () => {
    for (const [path, src] of Object.entries(SOURCES)) expect(src, path).toMatch(/^import '(\.\.\/three|\.)\/system\.css';$/m);
  });
});

describe('the .s3d- twins of the styles.css 3D section (FE-1b can delete it, FRONTEND_PLAN §4.4)', () => {
  const RAW = import.meta.glob<string>(['./SystemScene.ts', '../pages/SystemPage.tsx'], {
    eager: true,
    query: '?raw',
    import: 'default',
  });
  // Vitest empties every CSS import (even ?raw) unless its config opts in, so the stylesheet is read from disk.
  let css = '';
  beforeAll(async () => {
    const fs = (await import(/* @vite-ignore */ 'node:fs' as string)) as { readFileSync: (p: URL, enc: 'utf8') => string };
    css = fs.readFileSync(new URL('./system.css', import.meta.url), 'utf8');
  });

  it('gives the scene label layer and the body labels their own classes and rules', () => {
    expect(RAW['./SystemScene.ts']).toContain("labelRenderer.domElement.className = 'scene-labels s3d-labels'");
    expect(RAW['./SystemScene.ts']).toContain("div.className = 'body-label s3d-body-label'");
    // Without these the CSS2DRenderer layer sits below the canvas in the overflow:hidden stage: no labels.
    expect(css).toContain('.s3d-labels { position: absolute; inset: 0; pointer-events: none; }');
    expect(css).toMatch(/\.s3d-body-label \{[^}]*pointer-events: auto;/);
  });

  it('covers the body panel rules, and the compact rules are one class above the old ones on the same element', () => {
    for (const sel of ['.s3d-body dl {', '.s3d-body dt {', '.s3d-body dd {', '.s3d-facts {', '.s3d-facts th {', '.s3d-facts td {', '.s3d-unverified {']) {
      expect(css, sel).toContain(sel);
    }
    expect(css).toContain('.s3d-body .s3d-body-key {'); // beats .body-panel dl (0,1,1)
    expect(css).toContain('.s3d-preview .s3d-bodies {'); // beats .s3d-preview > p (0,1,1)
    expect(css).not.toMatch(/^\.s3d-body-key \{/m);
    expect(css).not.toMatch(/^\.s3d-bodies \{/m);
  });

  it('keeps the transport in view in Dataset time on the two-column page only (#138 review)', () => {
    // Free-running markup carries no dataset modifier, so the default and compact sizes are untouched.
    expect(viewer({})).not.toContain('s3d-viewer--dataset');
    expect(viewer({ compact: true })).not.toContain('s3d-viewer--dataset');
    const block = css.slice(css.indexOf('@media (min-width: 901px) {'));
    expect(block).toMatch(/^@media \(min-width: 901px\) \{\s*\.s3d-page \.s3d-viewer--dataset \.s3d-stage \{/);
    expect(block).toMatch(/\.s3d-page \.s3d-viewer--dataset \.s3d-transport \{[^}]*position: sticky;[^}]*bottom: 0;/);
    // Every dataset rule is scoped to the full page.
    for (const m of css.matchAll(/^[^\n{]*s3d-viewer--dataset[^\n{]*\{/gm)) expect(m[0].trim()).toMatch(/^\.s3d-page /);
  });

  it('defines the footer height with the FE-6 footer tokens and marks unverified tags with a glyph (#138 review)', () => {
    expect(css).toContain('--s3d-footer-h: calc(2 * var(--sp-3, 12px) + var(--fs-xs, 0.75rem) * var(--lh, 1.45) + 1px);');
    expect(css).toMatch(/\.s3d-unverified::before \{ content: '\\26A0\\FE0E';/);
    // The catalog chip keeps the plan's token.
    expect(css).toContain('.s3d-origin--catalog { --chip-c: var(--src-catalog, #f5c26b); }');
  });

  it('resets the side column scroll when the selected body changes', () => {
    const page = RAW['../pages/SystemPage.tsx'];
    expect(page).toMatch(/useLayoutEffect\(\(\) => \{\s*if \(sideRef\.current\) sideRef\.current\.scrollTop = 0;\s*\}, \[bodyId\]\);/);
    expect(page).toContain('<aside className="s3d-side" aria-label="System details" ref={sideRef}>');
  });
});
