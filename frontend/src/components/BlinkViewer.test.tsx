import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';
import type { Field, Frame } from '../api/types';
import { BlinkViewer } from './BlinkViewer';

const field = Object.values(import.meta.glob<Field>(
  '../../../data/products/fields/barnards-star/field.json',
  { eager: true, import: 'default' },
))[0];
const frame = field.frames[0];

function renderFrame(quality: Partial<Frame>) {
  return renderToStaticMarkup(
    <BlinkViewer field={field} frames={[{ ...frame, ...quality }]}
      imageUrl={(image) => image} candidates={[]} known={[]} selectedId={null} onSelect={() => {}} />,
  );
}

describe('frame quality in the blink viewer', () => {
  it('shows valid coverage and the FITS source for an exposure', () => {
    const html = renderFrame({ valid_fraction: 0.875 });
    expect(html).toContain('87.5% valid pixels');
    expect(frame.source_uri).toMatch(/^ibe\/data\/spherex\//);
    expect(html).toContain(`href="https://irsa.ipac.caltech.edu/${frame.source_uri}"`);
    expect(html).toContain('Individual contamination flags are unavailable');
  });

  it('distinguishes zero valid pixels from missing metadata', () => {
    expect(renderFrame({ valid_fraction: 0 })).toContain('0.0% valid pixels');
    const html = renderFrame({ valid_fraction: null, source_uri: null });
    expect(html).toContain('valid coverage unknown');
    expect(html).toContain('Original FITS: unavailable');
  });

  it('does not attach exposure quality to a season composite', () => {
    const html = renderToStaticMarkup(
      <BlinkViewer field={field} frames={[frame]} composites={field.composites}
        imageUrl={(image) => image} candidates={[]} known={[]} selectedId={null} onSelect={() => {}} />,
    );
    expect(html).toContain('False color (infrared)');
    expect(html).not.toContain('Frame quality');
  });
});
