// FE-7: compact player variant (server-rendered markup, like ExplorerMap.test.tsx).
import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';
import type { Field, SystemModel } from '../api/types';
import { BlinkViewer } from './BlinkViewer';
import { trackAstrometry } from '../three/skyTrack';

const FIELDS = Object.values(
  import.meta.glob<Field>('../../../data/products/fields/*/field.json', { eager: true, import: 'default' }),
);
const SYSTEMS = Object.values(
  import.meta.glob<SystemModel>('../../../data/products/systems/*.json', { eager: true, import: 'default' }),
);

const render = (fieldId: string, compact?: boolean, withPrediction = true) => {
  const field = FIELDS.find((f) => f.id === fieldId)!;
  const system = SYSTEMS.find((s) => s.field_id === fieldId)!;
  return renderToStaticMarkup(
    createElement(BlinkViewer, {
      field,
      frames: [...field.frames].sort((a, b) => a.mjd - b.mjd),
      composites: null,
      imageUrl: (image: string) => image,
      candidates: [],
      known: [],
      selectedId: null,
      onSelect: () => undefined,
      prediction: withPrediction ? trackAstrometry(system) : null,
      compact,
    }),
  );
};
const rootClass = (html: string) => html.match(/^<div class="([^"]+)"/)?.[1];
const text = (html: string) => html.replace(/<[^>]+>/g, '').replace(/&amp;/g, '&').replace(/&#x27;/g, "'");

describe('BlinkViewer compact player (FE-7)', () => {
  it('the root is the .pl-root container; compact is opt-in and only adds a class', () => {
    // pl-has-note: the Gaia prediction exists, so a line for the crosshair caveat is reserved under the image.
    expect(rootClass(render('barnards-star'))).toBe('blink pl-root pl-has-note');
    expect(rootClass(render('barnards-star', false))).toBe('blink pl-root pl-has-note');
    expect(rootClass(render('barnards-star', true))).toBe('blink pl-root pl-compact pl-has-note');
    expect(rootClass(render('barnards-star', false, false))).toBe('blink pl-root');
    expect(render('barnards-star', true).replace(' pl-compact', '')).toBe(render('barnards-star'));
  });

  it('keeps one .blink-frame per frame, the frame label, the transport and the slider in compact', () => {
    const field = FIELDS.find((f) => f.id === 'barnards-star')!;
    const html = render('barnards-star', true);
    expect(html.match(/class="blink-frame"/g)?.length).toBe(field.frames.length);
    expect(html).toContain('class="blink-caption pl-caption"');
    expect(html).toMatch(/· D\d+ · λ \d\.\d{3} µm · DR\d/);
    expect(html).toContain('aria-label="Image zoom"');
    expect(html).toContain('role="slider"');
    for (const label of ['Previous frame', 'Pause', 'Next frame', 'Blink speed']) expect(html).toContain(`aria-label="${label}"`);
    expect(html).toContain('Markers</button>');
    // Two transport rows: buttons + scrubber, then options with the keyboard help popover.
    expect(html.match(/class="pl-row /g)?.length).toBe(2);
    expect(html).toContain('aria-label="Player keyboard help"');
    expect(html).toContain('play / pause');
    // Loading shows over the stage (no image has loaded server-side).
    expect(html).toMatch(/role="status" class="small">Loading sequence images… 0\/\d+/);
  });

  it('keeps every prediction caveat visible in compact (Barnard and WISE 0855)', () => {
    const barnard = text(render('barnards-star', true));
    expect(barnard).toContain('Gaia prediction');
    expect(barnard).toContain('Crosshair shows the position predicted from the Gaia catalog, not a measurement.');
    expect(barnard).toContain('predicted from catalog, not a measurement');
    const barnardHtml = render('barnards-star', true);
    expect(barnardHtml).toContain('Source and method</span></summary>');
    // The crosshair caveat sits between the image and the transport (visible in the dock), with space reserved.
    expect(barnardHtml).toMatch(/class="blink pl-root pl-compact pl-has-note"/);
    const note = barnardHtml.indexOf('pl-note--crosshair');
    expect(note).toBeGreaterThan(barnardHtml.indexOf('pl-stage'));
    expect(note).toBeLessThan(barnardHtml.indexOf('class="pl-transport"'));
    const wise = text(render('wise-0855', true));
    expect(wise).toContain('Catalog prediction');
    expect(wise).toContain('in D1–D4 the blob at the crosshair is that star');
  });

  it('without a prediction there is no prediction toggle or note, but the zoom and help stay', () => {
    const html = render('barnards-star', true, false);
    expect(html).not.toContain('prediction</button>');
    expect(html).not.toContain('blink-prediction-note');
    expect(html).not.toContain('pl-has-note');
    expect(html).toContain('aria-label="Image zoom"');
    expect(html).toContain('aria-label="Player keyboard help"');
  });
});
