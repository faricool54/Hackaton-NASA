// Minimal dependency-free SVG spectrum (flux vs wavelength). WS5 may swap in a chart library.
import type { SpectrumPoint } from '../api/types';

export function SpectrumChart({ points }: { points: SpectrumPoint[] }) {
  const W = 320;
  const H = 160;
  const pad = { l: 44, r: 10, t: 10, b: 30 };
  const xs = points.map((p) => p.wavelength_um);
  const ys = points.flatMap((p) => [p.flux_mjy - (p.flux_err_mjy ?? 0), p.flux_mjy + (p.flux_err_mjy ?? 0)]);
  const [x0, x1] = [Math.min(0.75, ...xs), Math.max(5.0, ...xs)];
  const [y0, y1] = [Math.min(0, ...ys), Math.max(...ys) * 1.1 || 1];
  const sx = (x: number) => pad.l + ((x - x0) / (x1 - x0)) * (W - pad.l - pad.r);
  const sy = (y: number) => H - pad.b - ((y - y0) / (y1 - y0)) * (H - pad.t - pad.b);
  const ticks = [1, 2, 3, 4, 5].filter((t) => t >= x0 && t <= x1);

  return (
    <figure className="spectrum">
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label="Spectrum: flux versus wavelength">
        <line x1={pad.l} y1={H - pad.b} x2={W - pad.r} y2={H - pad.b} className="axis" />
        <line x1={pad.l} y1={pad.t} x2={pad.l} y2={H - pad.b} className="axis" />
        {ticks.map((t) => (
          <text key={t} x={sx(t)} y={H - pad.b + 14} className="tick" textAnchor="middle">
            {t}
          </text>
        ))}
        <text x={(W + pad.l) / 2} y={H - 2} className="tick" textAnchor="middle">
          wavelength (µm)
        </text>
        <text x={4} y={pad.t + 8} className="tick">
          mJy
        </text>
        {points.map((p) => (
          <g key={p.frame_id}>
            {p.flux_err_mjy != null && (
              <line
                x1={sx(p.wavelength_um)}
                x2={sx(p.wavelength_um)}
                y1={sy(p.flux_mjy - p.flux_err_mjy)}
                y2={sy(p.flux_mjy + p.flux_err_mjy)}
                className="errbar"
              />
            )}
            <circle cx={sx(p.wavelength_um)} cy={sy(p.flux_mjy)} r={3} className="point">
              <title>{`${p.wavelength_um.toFixed(3)} µm: ${p.flux_mjy.toFixed(3)} mJy`}</title>
            </circle>
          </g>
        ))}
      </svg>
      <figcaption className="muted">Each point is one SPHEREx exposure at a different wavelength.</figcaption>
    </figure>
  );
}
