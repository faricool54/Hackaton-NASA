import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';
import type { Field, Frame, FrameFlagSummary } from '../api/types';
import { BlinkViewer } from './BlinkViewer';

const field = Object.values(import.meta.glob<Field>(
  '../../../data/products/fields/barnards-star/field.json',
  { eager: true, import: 'default' },
))[0];
const frame = field.frames[0];

function renderFrame(quality: Partial<Frame>, flags?: FrameFlagSummary) {
  return renderToStaticMarkup(
    <BlinkViewer field={{ ...field, frame_flags: flags ? { [frame.id]: flags } : undefined }}
      frames={[{ ...frame, ...quality }]}
      imageUrl={(image) => image} candidates={[]} known={[]} selectedId={null} onSelect={() => {}} />,
  );
}

describe('frame quality in the blink viewer', () => {
  it('shows valid coverage and the FITS source for an exposure', () => {
    const html = renderFrame({ valid_fraction: 0.875 });
    expect(html).toContain('Valid-pixel coverage · 87.5%');
    expect(frame.source_uri).toMatch(/^ibe\/data\/spherex\//);
    expect(html).toContain(`href="https://irsa.ipac.caltech.edu/${frame.source_uri}"`);
    expect(html).toContain('Download FITS from IRSA');
    expect(html).toContain(`Frame ${frame.id}`);
    expect(html).toContain('The target can be saturated even when coverage is high');
    expect(html).toContain('Archive saturation and contamination flags are unavailable');
  });

  it('labels measured zero and missing archive bits separately', () => {
    const html = renderFrame({}, {
      coverage_fraction: 0.75, fractions: { OVERFLOW: 0.025, PERSIST: 0, SOURCE: 0.4 },
    });
    expect(html).toContain('Archive flags · 75.0% of grid sampled');
    expect(html).toContain('Saturation (OVERFLOW) · 2.5%');
    expect(html).toContain('Detector persistence (PERSIST) · 0.0%');
    expect(html).toContain('Optical ghost (GHOST) · unknown');
    expect(html).toContain('SOURCE marks detected sky sources');
  });

  it('keeps near-total and near-zero coverage distinct from the endpoints', () => {
    expect(renderFrame({ valid_fraction: 0.9999 })).toContain('Valid-pixel coverage · &gt;99.9%');
    expect(renderFrame({ valid_fraction: 0.0001 })).toContain('Valid-pixel coverage · &lt;0.1%');
    expect(renderFrame({ valid_fraction: 1 })).toContain('Valid-pixel coverage · 100.0%');
  });

  it('distinguishes zero valid pixels from missing metadata', () => {
    expect(renderFrame({ valid_fraction: 0 })).toContain('Valid-pixel coverage · 0.0%');
    const html = renderFrame({ valid_fraction: null, source_uri: null });
    expect(html).toContain('Valid-pixel coverage · unknown');
    expect(html).toContain('Original FITS: unavailable');
  });

  it('does not attach exposure quality to a season composite', () => {
    const html = renderToStaticMarkup(
      <BlinkViewer field={field} frames={[frame]} composites={field.composites}
        imageUrl={(image) => image} candidates={[]} known={[]} selectedId={null} onSelect={() => {}} />,
    );
    expect(html).toContain('False color (infrared)');
    expect(html).not.toContain('Valid-pixel coverage');
  });
});
