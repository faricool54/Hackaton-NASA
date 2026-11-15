import { useEffect, useState } from 'react';
import { client } from '../api/client';
import { formatMjd } from '../api/format';
import {
  aliasText, bandChange, bandFloor, bootstrapText, changeText, falseAlarmText, floorTexts, loadLightCurve, methodText,
  periodHeadline, plotCaption, relativePercent, selectionRows, signalText, signedPercent, sortNotes, stampsHaveVariance,
  type UsedPoint,
} from '../api/lightcurve';
import type { LightCurveData, LightCurveExclusion, LightCurvePoint, LightCurveProduct } from '../api/types';
import { PlotTooltip, type PlotTip } from './SciencePlot';
import { useScienceRequest } from './useScienceRequest';
import '../styles/science.css';

const exclusionLabels: Record<LightCurveExclusion, string> = {
  no_flags: 'Quality flags unavailable',
  saturated: 'Saturated (lower limit)',
  edge: 'Image edge',
  bad_pixels: 'Bad pixels',
  no_sky: 'Background unavailable',
  no_variance: 'Uncertainty unavailable',
  no_wavelength: 'Wavelength unavailable',
  non_positive: 'Non-positive signal',
  lone_bin: 'No comparable wavelength measurement',
  short_bin: 'Insufficient time span in this band',
};

/** Plot boxes: the panel keeps its original geometry; the inline (dock) variant is narrower so labels stay legible. */
const PLOT_BOXES = {
  panel: { w: 600, h: 248, l: 70, r: 576, t: 30, b: 204 },
  inline: { w: 400, h: 232, l: 54, r: 390, t: 30, b: 190 },
};

function LightCurvePlot({ points, wing, floorMag, caption, compact = false }: {
  points: UsedPoint[]; wing: boolean; floorMag: number | null; caption: string; compact?: boolean;
}) {
  const [tip, setTip] = useState<PlotTip | null>(null);
  const box = compact ? PLOT_BOXES.inline : PLOT_BOXES.panel;
  const samples = points.map((p) => {
    const err = p.rel_mag_err ?? 0, floor = floorMag ?? 0;
    return {
      ...p,
      value: relativePercent(p.rel_mag),
      low: relativePercent(p.rel_mag + err),
      high: relativePercent(p.rel_mag - err),
      floorLow: relativePercent(p.rel_mag + floor),
      floorHigh: relativePercent(p.rel_mag - floor),
    };
  });
  const min = Math.min(0, ...samples.map((p) => Math.min(p.low, p.floorLow)));
  const max = Math.max(0, ...samples.map((p) => Math.max(p.high, p.floorHigh)));
  const padding = Math.max((max - min) * 0.12, 0.1);
  const first = samples[0].mjd;
  const last = samples[samples.length - 1].mjd;
  const mid = (box.l + box.r) / 2;
  const x = (mjd: number) => first === last ? mid : box.l + (box.r - box.l) * (mjd - first) / (last - first);
  const y = (percent: number) => box.b - (box.b - box.t) * (percent - min + padding) / (max - min + padding * 2);
  const axisTitle = wing ? 'Relative wing brightness (%)' : 'Relative aperture flux (%)';

  return <figure className={`measurement-plot sci-plot${compact ? ' sci-plot--compact' : ''}`} onMouseLeave={() => setTip(null)}>
    <div className="sci-plot-box">
    <svg viewBox={`0 0 ${box.w} ${box.h}`} role="img" aria-label={`${axisTitle} over time, ${samples.length} measurements`}>
      {[max, min].map((v, i) => <path key={i} className="sci-grid" d={`M${box.l} ${y(v)}H${box.r}`} />)}
      <path className="sci-axis" d={`M${box.l} ${box.t - 8}V${box.b}H${box.r}`} fill="none" stroke="currentColor" />
      <path className="sci-zero" d={`M${box.l} ${y(0)}H${box.r}`} fill="none" stroke="currentColor" strokeDasharray="4 4" />
      <text x={box.l} y={box.t - 15}>{axisTitle}</text>
      {[...new Set([max, 0, min])].map((v) => <text key={v} x={box.l - 6} y={y(v) + 4} textAnchor="end">
        {v.toLocaleString('en', { maximumFractionDigits: 1 })}%
      </text>)}
      <text x={box.l} y={box.b + 18}>{formatMjd(first).slice(0, 10)}</text>
      {first !== last && <text x={box.r} y={box.b + 18} textAnchor="end">{formatMjd(last).slice(0, 10)}</text>}
      <text x={mid} y={box.h - 4} textAnchor="middle">Observation date (UTC)</text>
      {samples.map((p) => <g key={p.frame_id} className="sci-point" onMouseEnter={() => setTip({
        x: x(p.mjd) / box.w, y: y(p.value) / box.h,
        lines: [formatMjd(p.mjd), `${signedPercent(p.value)} vs the band mean magnitude`,
          `Δmag ${p.rel_mag >= 0 ? '+' : ''}${p.rel_mag.toFixed(3)}${p.rel_mag_err !== null ? ` ± ${p.rel_mag_err.toFixed(3)}` : ''} (negative = brighter)`,
          p.flags.length ? `Flags: ${p.flags.join(', ')}` : 'No flags reported'],
      })}>
        {floorMag !== null && <rect x={x(p.mjd) - 4} width={8} y={y(p.floorHigh)} height={y(p.floorLow) - y(p.floorHigh)}
          className="sci-floor" fill="var(--accent)" opacity={0.2} />}
        {p.rel_mag_err !== null && <line className="sci-err" x1={x(p.mjd)} x2={x(p.mjd)} y1={y(p.low)} y2={y(p.high)} stroke="var(--accent)" />}
        <circle className="sci-dot" cx={x(p.mjd)} cy={y(p.value)} r={3.5} fill="var(--accent)">
          <title>{`${formatMjd(p.mjd)} · ${signedPercent(p.value)} vs the band mean magnitude`}</title>
        </circle>
      </g>)}
    </svg>
    <PlotTooltip tip={tip} />
    </div>
    <figcaption className="muted small">{caption}</figcaption>
  </figure>;
}

function Measurements({ points, unit, relative = false }: {
  points: LightCurvePoint[]; unit: LightCurveData['unit']; relative?: boolean;
}) {
  return <div className="science-table-wrap" role="region" aria-label="Light curve measurements" tabIndex={0}>
    <table className="science-table">
      <thead><tr><th>Date (UTC)</th><th>Detector</th><th>λ (µm)</th><th>Measured signal ({unit})</th><th>Statistical error</th>
        {relative && <th>vs band mean magnitude (%)</th>}<th>Quality</th></tr></thead>
      <tbody>{points.map((p) => <tr key={p.frame_id}>
        <td>{formatMjd(p.mjd)}</td><td>D{p.detector}</td><td>{p.wavelength_um?.toFixed(4) ?? '—'}</td>
        <td>{signalText(p)}</td><td>{p.flux_err?.toPrecision(3) ?? '—'}</td>
        {relative && <td>{p.rel_mag === null ? '—' : signedPercent(relativePercent(p.rel_mag))}</td>}
        <td>{p.excluded ? exclusionLabels[p.excluded] : 'Used'}{p.flags.length > 0 && ` · ${p.flags.join(', ')}`}</td>
      </tr>)}</tbody>
    </table>
  </div>;
}

function PeriodEvidence({ period }: { period: LightCurveData['period'] }) {
  if (!period) return <p className="muted">No period estimate is available for this product.</p>;
  const lines = [falseAlarmText(period), bootstrapText(period), period.significant === true ? aliasText(period) : null]
    .filter((line): line is string => line !== null);
  return <>
    <p>{periodHeadline(period)}</p>
    {lines.length > 0 && <ul className="small lc-list">{lines.map((line) => <li key={line}>{line}</li>)}</ul>}
    <p className="muted small">{period.caveat}</p>
  </>;
}

/** One precomputed product (exported so it can be rendered without fetching). */
export function LightCurveProductView({ product, variant = 'panel' }: {
  product: LightCurveProduct;
  /** "panel" (default): the full report. "inline": headline and plot first, the rest folded under "Limits and method". */
  variant?: 'panel' | 'inline';
}) {
  const { curve, provenance } = product;
  const [selected, setSelected] = useState<number | undefined>(() =>
    curve.bins.reduce<LightCurveData['bins'][number] | undefined>(
      (best, bin) => !best || bin.n_points > best.n_points ? bin : best, undefined,
    )?.index);
  const usable = curve.points.filter((p) => p.excluded === null && p.rel_mag !== null);
  const points = usable.filter((p): p is UsedPoint => p.bin === selected && p.rel_mag !== null)
    .sort((a, b) => a.mjd - b.mjd);
  const rejected = curve.points.filter((p) => p.excluded !== null);
  const bin = curve.bins.find((b) => b.index === selected);
  const wing = curve.method === 'wing';
  const floor = bin && points.length
    ? bandFloor(curve, bin.detector, points, stampsHaveVariance(provenance.notes)) : null;
  const change = bandChange(points);
  const notes = sortNotes(provenance.notes, curve.notes);
  const inline = variant === 'inline';

  const method = <p>{methodText(curve.method)} {usable.length} of {curve.points.length} measurements used.</p>;
  const bandSelect = curve.bins.length > 0 && <label className={inline ? 'sci-band' : undefined}>Comparable wavelength band
    <select value={selected} onChange={(e) => setSelected(Number(e.target.value))}>
      {curve.bins.map((b) => <option key={b.index} value={b.index}>
        D{b.detector} · {b.lambda_min_um.toFixed(4)}–{b.lambda_max_um.toFixed(4)} µm · {b.n_points} observations
      </option>)}
    </select>
  </label>;
  const plot = <LightCurvePlot points={points} wing={wing} floorMag={floor?.plotMag ?? null} caption={plotCaption(floor)}
    compact={inline} />;
  const floorLine = floor && <p className="small">{floorTexts(floor).join(' ')}</p>;
  const changeLine = change && <p className={inline ? 'small sci-change' : 'small'}>
    {changeText(change, { wing, cyclic: curve.period?.significant === true })}</p>;
  const bandMeasurements = <details><summary>Measurements in this band ({points.length})</summary>
    <Measurements points={points} unit={curve.unit} relative /></details>;
  const noPoints = <p role="status">No usable measurements in a comparable wavelength band.</p>;
  const limits = <ul className="small lc-list">{notes.limits.map((note) => <li key={note}>{note}</li>)}</ul>;
  const selection = <>
    <h4>Data selection</h4>
    <dl className="lc-selection">
      {selectionRows(product).map((row) => <div key={row.label}><dt>{row.label}</dt><dd>{row.value}</dd></div>)}
    </dl>
    {notes.selection.map((note) => <p className="small muted" key={note}>{note}</p>)}
  </>;
  const exclusions = <details>
    <summary>Excluded measurements ({rejected.length}) · failed inputs ({curve.failures.length})</summary>
    {rejected.length > 0 && <>
      <p>{Object.entries(curve.excluded).map(([reason, count]) => `${exclusionLabels[reason as LightCurveExclusion]}: ${count}`).join(' · ')}</p>
      {rejected.some((p) => p.excluded === 'saturated') && <p className="small">Saturated fluxes are lower limits
        (shown as ≥): the true signal is brighter, so these exposures cannot be compared with the others.</p>}
      <Measurements points={rejected} unit={curve.unit} />
    </>}
    {curve.failures.map((f, i) => <p className="small" key={i}>{f.frame_id ?? 'Input'}: {f.reason.replaceAll('_', ' ')}</p>)}
    {!rejected.length && !curve.failures.length && <p>No exclusions or input failures reported.</p>}
  </details>;
  const technical = <details>
    <summary>Technical provenance</summary>
    <ul className="small lc-list provenance-row">
      <li>Product id (opaque content identity): {product.id}</li>
      <li>Processing fingerprint: {provenance.processing_fingerprint}</li>
      <li>Source files: {provenance.sources.length} SPHEREx exposures (IRSA archive on AWS S3)</li>
      {notes.technical.map((note) => <li key={note}>{note}</li>)}
    </ul>
  </details>;

  if (inline) {
    return <div className="sci-lc">
      <p className="sci-lc-meta"><strong>{product.target_name}</strong> · {usable.length} of {curve.points.length} measurements used</p>
      <p className="sci-headline">{curve.period ? periodHeadline(curve.period) : 'No period estimate is available for this product.'}</p>
      {points.length ? <>{changeLine}{plot}{floorLine}</> : noPoints}
      {bandSelect}
      <details className="sci-more sci-limits">
        <summary>Limits and method ({notes.limits.length} limits stated by this product)</summary>
        {method}
        <h4>Period evidence</h4>
        <PeriodEvidence period={curve.period} />
        <h4>Limits stated by this product</h4>
        {limits}
        {selection}
        {points.length > 0 && bandMeasurements}
        {exclusions}
        {technical}
      </details>
    </div>;
  }

  return <>
    <h3>{product.target_name}</h3>
    {method}
    {bandSelect}
    {points.length ? <>
      {plot}
      {floorLine}
      {changeLine}
      {bandMeasurements}
    </> : noPoints}
    <h4>Period evidence</h4>
    <PeriodEvidence period={curve.period} />
    <details open className="lc-notes">
      <summary>Limits stated by this product ({notes.limits.length})</summary>
      {limits}
    </details>
    {selection}
    {exclusions}
    {technical}
  </>;
}

export function LightCurvePanel({ targetId, variant = 'panel' }: {
  targetId: string;
  /** "panel" (default): collapsed <details> that loads when opened. "inline": loads on mount, no wrapper. */
  variant?: 'panel' | 'inline';
}) {
  const request = useScienceRequest<LightCurveProduct | 'missing'>(targetId);
  const { run } = request;
  const load = () => request.run((signal) => loadLightCurve(client, targetId, signal));
  const inline = variant === 'inline';
  useEffect(() => {
    if (!inline) return;
    // Let Strict Mode finish its initial cleanup before starting the request.
    const timer = setTimeout(() => { void run((signal) => loadLightCurve(client, targetId, signal)); }, 0);
    return () => clearTimeout(timer);
  }, [inline, targetId, run]);

  const body = <>
    {request.busy && <p role="status" className={inline ? 'sci-busy' : undefined}>
      {inline && <span className="sci-busy-dot" aria-hidden="true" />}Loading light curve…</p>}
    {request.error && <><p role="alert" className="error">{request.error}</p>
      <button type="button" onClick={() => void load()}>Retry</button></>}
    {request.data === 'missing' && <p role="status">No precomputed light curve is available for this field.</p>}
    {request.data && request.data !== 'missing' && <LightCurveProductView product={request.data} variant={variant} />}
  </>;

  if (inline) return <section className="science-panel sci-lc-inline" aria-label="Light curve">{body}</section>;

  return <details className="panel science-panel" onToggle={(e) => {
    if (e.currentTarget.open && !request.data && !request.busy && !request.error) void load();
  }}>
    <summary>Light curve</summary>
    {body}
  </details>;
}
