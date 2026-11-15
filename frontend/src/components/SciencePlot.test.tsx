import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';
import { PlotTooltip } from './SciencePlot';

describe('PlotTooltip', () => {
  it('renders nothing without a hovered point', () => {
    expect(renderToStaticMarkup(createElement(PlotTooltip, { tip: null }))).toBe('');
  });

  it('places the tip in percent of the plot and flips it near the right and top edges', () => {
    const right = renderToStaticMarkup(createElement(PlotTooltip, { tip: { x: 0.9, y: 0.1, lines: ['1.234 µm', '5 MJy/sr'] } }));
    expect(right).toContain('sci-tip sci-tip--left sci-tip--below');
    expect(right).toContain('left:90.00%');
    expect(right).toContain('<span>1.234 µm</span><span>5 MJy/sr</span>');
    const left = renderToStaticMarkup(createElement(PlotTooltip, { tip: { x: 0.2, y: 0.5, lines: ['a'] } }));
    expect(left).toContain('class="sci-tip"');
  });
});
