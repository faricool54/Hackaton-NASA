import type { SpectrumPoint } from '../api/types';

const W = 360;
const H = 188;
const pad = { l: 43, r: 12, t: 14, b: 34 };

/** Fritsch–Carlson slopes give a smooth, shape-preserving curve through observations. */
function interpolate(points: SpectrumPoint[], sx: (x: number) => number, sy: (y: number) => number) {
  const sorted = [...points].sort((a, b) => a.wavelength_um - b.wavelength_um);
  const knots = sorted.reduce<{ x: number; y: number; count: number }[]>((items, point) => {
    const last = items.at(-1);
    if (last && Math.abs(last.x - point.wavelength_um) < 1e-6) {
      last.y += point.flux_mjy;
      last.count += 1;
    } else {
      items.push({ x: point.wavelength_um, y: point.flux_mjy, count: 1 });
    }
    return items;
  }, []);
  knots.forEach((point) => (point.y /= point.count));
  if (knots.length < 2) return '';

  const intervals = knots.slice(0, -1).map((point, i) => ({
    width: knots[i + 1].x - point.x,
    slope: (knots[i + 1].y - point.y) / (knots[i + 1].x - point.x),
  }));
  const slopes = knots.map((_, i) => {
    if (i === 0) return intervals[0].slope;
    if (i === knots.length - 1) return intervals.at(-1)!.slope;
    const left = intervals[i - 1];
    const right = intervals[i];
    if (left.slope === 0 || right.slope === 0 || Math.sign(left.slope) !== Math.sign(right.slope)) return 0;
    const w1 = 2 * right.width + left.width;
    const w2 = right.width + 2 * left.width;
    return (w1 + w2) / (w1 / left.slope + w2 / right.slope);
  });

  const samples: { x: number; y: number }[] = [];
  intervals.forEach(({ width }, i) => {
    const a = knots[i];
    const b = knots[i + 1];
    const steps = Math.max(8, Math.ceil(width * 12));
    for (let step = 0; step < steps; step += 1) {
      const t = step / steps;
      const t2 = t * t;
      const t3 = t2 * t;
      const y =
        (2 * t3 - 3 * t2 + 1) * a.y +
        (t3 - 2 * t2 + t) * width * slopes[i] +
        (-2 * t3 + 3 * t2) * b.y +
        (t3 - t2) * width * slopes[i + 1];
      samples.push({ x: a.x + t * width, y });
    }
  });
  const last = knots.at(-1)!;
  samples.push({ x: last.x, y: last.y });
  return samples.map((p, i) => `${i === 0 ? 'M' : 'L'}${sx(p.x).toFixed(2)},${sy(p.y).toFixed(2)}`).join(' ');
}

export function SpectrumChart({ points }: { points: SpectrumPoint[] }) {
  if (points.length === 0) return null;
  const xs = points.map((p) => p.wavelength_um);
  const ys = points.flatMap((p) => [p.flux_mjy - (p.flux_err_mjy ?? 0), p.flux_mjy + (p.flux_err_mjy ?? 0)]);
  const minX = Math.min(...xs);
  const maxX = Math.max(...xs);
  const x0 = Math.min(0.75, minX);
  const x1 = Math.max(5, maxX);
  const lowY = Math.min(0, ...ys);
  const highY = Math.max(...ys);
  const yPadding = Math.max((highY - lowY) * 0.12, Math.abs(highY) * 0.08, 0.1);
  const y0 = lowY - yPadding;
  const y1 = highY + yPadding;
  const sx = (x: number) => pad.l + ((x - x0) / (x1 - x0 || 1)) * (W - pad.l - pad.r);
  const sy = (y: number) => H - pad.b - ((y - y0) / (y1 - y0)) * (H - pad.t - pad.b);
  const ticks = [1, 2, 3, 4, 5].filter((t) => t >= x0 && t <= x1);
  const yTicks = Array.from({ length: 4 }, (_, i) => y0 + ((y1 - y0) * (i + 1)) / 5);
  const estimatePath = interpolate(points, sx, sy);
  const areaPath = estimatePath
    ? `${estimatePath} L${sx(maxX).toFixed(2)},${sy(y0).toFixed(2)} L${sx(minX).toFixed(2)},${sy(y0).toFixed(2)} Z`
    : '';

  return (
    <figure className="spectrum">
      <div className="spectrum-heading">
        <div>
          <h4>Spectral energy distribution</h4>
          <p className="muted">Brightness across infrared wavelengths</p>
        </div>
        <span className="spectrum-count">{points.length} measurements</span>
      </div>
      <div className="spectrum-legend" aria-label="Chart legend">
        <span><i className="legend-line" />Interpolated estimate</span>
        <span><i className="legend-point" />Observed measurement</span>
      </div>
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label="Infrared spectrum: observed flux measurements and interpolated estimate">
        <defs>
          <linearGradient id="spectrum-fill" x1="0" x2="0" y1="0" y2="1">
            <stop offset="0%" stopColor="var(--accent)" stopOpacity="0.2" />
            <stop offset="100%" stopColor="var(--accent)" stopOpacity="0.01" />
          </linearGradient>
        </defs>
        {yTicks.map((t) => (
          <g key={t}>
            <line x1={pad.l} x2={W - pad.r} y1={sy(t)} y2={sy(t)} className="spectrum-grid" />
            <text x={pad.l - 8} y={sy(t) + 3} className="tick spectrum-y-tick" textAnchor="end">{t.toFixed(1)}</text>
          </g>
        ))}
        {areaPath && <path d={areaPath} fill="url(#spectrum-fill)" />}
        {estimatePath && <path d={estimatePath} className="spectrum-estimate" />}
        <line x1={pad.l} y1={H - pad.b} x2={W - pad.r} y2={H - pad.b} className="axis" />
        <line x1={pad.l} y1={pad.t} x2={pad.l} y2={H - pad.b} className="axis" />
        {ticks.map((t) => (
          <g key={t}>
            <line x1={sx(t)} x2={sx(t)} y1={H - pad.b} y2={H - pad.b + 4} className="axis" />
            <text x={sx(t)} y={H - pad.b + 17} className="tick" textAnchor="middle">{t}</text>
          </g>
        ))}
        <text x={(W + pad.l) / 2} y={H - 3} className="tick spectrum-x-label" textAnchor="middle">Wavelength (µm)</text>
        <text x={pad.l} y={pad.t - 3} className="tick spectrum-y-label">mJy</text>
        {points.map((p) => (
          <g key={p.frame_id}>
            {p.flux_err_mjy != null && (
              <g className="spectrum-error">
                <line x1={sx(p.wavelength_um)} x2={sx(p.wavelength_um)} y1={sy(p.flux_mjy - p.flux_err_mjy)} y2={sy(p.flux_mjy + p.flux_err_mjy)} />
                <line x1={sx(p.wavelength_um) - 3} x2={sx(p.wavelength_um) + 3} y1={sy(p.flux_mjy - p.flux_err_mjy)} y2={sy(p.flux_mjy - p.flux_err_mjy)} />
                <line x1={sx(p.wavelength_um) - 3} x2={sx(p.wavelength_um) + 3} y1={sy(p.flux_mjy + p.flux_err_mjy)} y2={sy(p.flux_mjy + p.flux_err_mjy)} />
              </g>
            )}
            <circle cx={sx(p.wavelength_um)} cy={sy(p.flux_mjy)} r={4} className="point">
              <title>{`Observed: ${p.wavelength_um.toFixed(3)} µm, ${p.flux_mjy.toFixed(3)} mJy${p.flux_err_mjy == null ? '' : ` ± ${p.flux_err_mjy.toFixed(3)} mJy`}`}</title>
            </circle>
          </g>
        ))}
      </svg>
      <figcaption className="muted">A shape-preserving interpolation between measured wavelengths, not a physical fit. Measurements may come from separate exposures.</figcaption>
    </figure>
  );
}
