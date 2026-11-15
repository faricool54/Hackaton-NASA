import { useState } from 'react';
import { client } from '../api/client';
import { formatMjd } from '../api/format';
import {
  aliasText, bandChange, bandFloor, bootstrapText, changeText, falseAlarmText, floorTexts, loadLightCurve, methodText,
  periodHeadline, plotCaption, relativePercent, selectionRows, signalText, signedPercent, sortNotes, stampsHaveVariance,
  type UsedPoint,
} from '../api/lightcurve';
import type { LightCurveData, LightCurveExclusion, LightCurvePoint, LightCurveProduct } from '../api/types';
import { useScienceRequest } from './useScienceRequest';

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

function LightCurvePlot({ points, wing, floorMag, caption }: {
  points: UsedPoint[]; wing: boolean; floorMag: number | null; caption: string;
}) {
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
  const x = (mjd: number) => first === last ? 323 : 70 + 506 * (mjd - first) / (last - first);
  const y = (percent: number) => 204 - 174 * (percent - min + padding) / (max - min + padding * 2);
  const axisTitle = wing ? 'Relative wing brightness (%)' : 'Relative aperture flux (%)';

  return <figure className="measurement-plot">
    <svg viewBox="0 0 600 248" role="img" aria-label={`${axisTitle} over time, ${samples.length} measurements`}>
      <path d="M70 22V204H576" fill="none" stroke="currentColor" />
      <path d={`M70 ${y(0)}H576`} fill="none" stroke="currentColor" strokeDasharray="4 4" />
      <text x={70} y={15}>{axisTitle}</text>
      {[...new Set([max, 0, min])].map((v) => <text key={v} x={64} y={y(v) + 4} textAnchor="end">
        {v.toLocaleString('en', { maximumFractionDigits: 1 })}%
      </text>)}
      <text x={70} y={222}>{formatMjd(first).slice(0, 10)}</text>
      {first !== last && <text x={576} y={222} textAnchor="end">{formatMjd(last).slice(0, 10)}</text>}
      <text x={323} y={244} textAnchor="middle">Observation date (UTC)</text>
      {samples.map((p) => <g key={p.frame_id}>
        {floorMag !== null && <rect x={x(p.mjd) - 4} width={8} y={y(p.floorHigh)} height={y(p.floorLow) - y(p.floorHigh)}
          fill="var(--accent)" opacity={0.2} />}
        {p.rel_mag_err !== null && <line x1={x(p.mjd)} x2={x(p.mjd)} y1={y(p.low)} y2={y(p.high)} stroke="var(--accent)" />}
        <circle cx={x(p.mjd)} cy={y(p.value)} r={3.5} fill="var(--accent)">
          <title>{`${formatMjd(p.mjd)} · ${signedPercent(p.value)} vs the band mean magnitude`}</title>
        </circle>
      </g>)}
    </svg>
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
export function LightCurveProductView({ product }: { product: LightCurveProduct }) {
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

  return <>
    <h3>{product.target_name}</h3>
    <p>{methodText(curve.method)} {usable.length} of {curve.points.length} measurements used.</p>
    {curve.bins.length > 0 && <label>Comparable wavelength band
      <select value={selected} onChange={(e) => setSelected(Number(e.target.value))}>
        {curve.bins.map((b) => <option key={b.index} value={b.index}>
          D{b.detector} · {b.lambda_min_um.toFixed(4)}–{b.lambda_max_um.toFixed(4)} µm · {b.n_points} observations
        </option>)}
      </select>
    </label>}
    {points.length ? <>
      <LightCurvePlot points={points} wing={wing} floorMag={floor?.plotMag ?? null} caption={plotCaption(floor)} />
      {floor && <p className="small">{floorTexts(floor).join(' ')}</p>}
      {change && <p className="small">{changeText(change, { wing, cyclic: curve.period?.significant === true })}</p>}
      <details><summary>Measurements in this band ({points.length})</summary>
        <Measurements points={points} unit={curve.unit} relative /></details>
    </> : <p role="status">No usable measurements in a comparable wavelength band.</p>}
    <h4>Period evidence</h4>
    <PeriodEvidence period={curve.period} />
    <details open className="lc-notes">
      <summary>Limits stated by this product ({notes.limits.length})</summary>
      <ul className="small lc-list">{notes.limits.map((note) => <li key={note}>{note}</li>)}</ul>
    </details>
    <h4>Data selection</h4>
    <dl className="lc-selection">
      {selectionRows(product).map((row) => <div key={row.label}><dt>{row.label}</dt><dd>{row.value}</dd></div>)}
    </dl>
    {notes.selection.map((note) => <p className="small muted" key={note}>{note}</p>)}
    <details>
      <summary>Excluded measurements ({rejected.length}) · failed inputs ({curve.failures.length})</summary>
      {rejected.length > 0 && <>
        <p>{Object.entries(curve.excluded).map(([reason, count]) => `${exclusionLabels[reason as LightCurveExclusion]}: ${count}`).join(' · ')}</p>
        {rejected.some((p) => p.excluded === 'saturated') && <p className="small">Saturated fluxes are lower limits
          (shown as ≥): the true signal is brighter, so these exposures cannot be compared with the others.</p>}
        <Measurements points={rejected} unit={curve.unit} />
      </>}
      {curve.failures.map((f, i) => <p className="small" key={i}>{f.frame_id ?? 'Input'}: {f.reason.replaceAll('_', ' ')}</p>)}
      {!rejected.length && !curve.failures.length && <p>No exclusions or input failures reported.</p>}
    </details>
    <details>
      <summary>Technical provenance</summary>
      <ul className="small lc-list provenance-row">
        <li>Product id (opaque content identity): {product.id}</li>
        <li>Processing fingerprint: {provenance.processing_fingerprint}</li>
        <li>Source files: {provenance.sources.length} SPHEREx exposures (IRSA archive on AWS S3)</li>
        {notes.technical.map((note) => <li key={note}>{note}</li>)}
      </ul>
    </details>
  </>;
}

export function LightCurvePanel({ targetId }: { targetId: string }) {
  const request = useScienceRequest<LightCurveProduct | 'missing'>(targetId);
  const load = () => request.run((signal) => loadLightCurve(client, targetId, signal));

  return <details className="panel science-panel" onToggle={(e) => {
    if (e.currentTarget.open && !request.data && !request.busy && !request.error) void load();
  }}>
    <summary>Light curve</summary>
    {request.busy && <p role="status">Loading light curve…</p>}
    {request.error && <><p role="alert" className="error">{request.error}</p>
      <button type="button" onClick={() => void load()}>Retry</button></>}
    {request.data === 'missing' && <p role="status">No precomputed light curve is available for this field.</p>}
    {request.data && request.data !== 'missing' && <LightCurveProductView product={request.data} />}
  </details>;
}
