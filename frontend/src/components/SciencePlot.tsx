import '../styles/science.css';

/** A hovered plot point: x and y are fractions (0–1) of the figure box, lines are the values to show. */
export interface PlotTip { x: number; y: number; lines: string[] }

/** Glass tooltip shared by the science plots (FE-8). Purely visual: every value is also in the SVG <title>. */
export function PlotTooltip({ tip }: { tip: PlotTip | null }) {
  if (!tip) return null;
  const className = `sci-tip${tip.x > 0.6 ? ' sci-tip--left' : ''}${tip.y < 0.3 ? ' sci-tip--below' : ''}`;
  return <div className={className} aria-hidden="true" style={{ left: `${(tip.x * 100).toFixed(2)}%`, top: `${(tip.y * 100).toFixed(2)}%` }}>
    {tip.lines.map((line) => <span key={line}>{line}</span>)}
  </div>;
}
