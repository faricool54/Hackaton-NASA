import { useState } from 'react';
import { ApiError, client } from '../api/client';
import { formatMjd } from '../api/format';
import type { LightCurveData, LightCurveExclusion, LightCurvePoint, LightCurveProduct } from '../api/types';
import { useScienceRequest } from './useScienceRequest';

const exclusionLabels: Record<LightCurveExclusion, string> = {
  no_flags: 'Quality flags unavailable',
  saturated: 'Saturation',
  edge: 'Image edge',
  bad_pixels: 'Bad pixels',
  no_sky: 'Background unavailable',
  no_variance: 'Uncertainty unavailable',
  no_wavelength: 'Wavelength unavailable',
  non_positive: 'Non-positive signal',
  lone_bin: 'No comparable wavelength measurement',
  short_bin: 'Insufficient time span in this band',
};

function brightnessRatio(relativeMagnitude: number) {
  return 10 ** (-0.4 * relativeMagnitude);
}

function LightCurvePlot({ points, wing }: {
  points: (LightCurvePoint & { rel_mag: number })[];
  wing: boolean;
}) {
  const samples = points.map((p) => ({
    ...p,
    value: 100 * (brightnessRatio(p.rel_mag) - 1),
    low: 100 * (brightnessRatio(p.rel_mag + (p.rel_mag_err ?? 0)) - 1),
    high: 100 * (brightnessRatio(p.rel_mag - (p.rel_mag_err ?? 0)) - 1),
  }));
  const min = Math.min(0, ...samples.map((p) => p.low));
  const max = Math.max(0, ...samples.map((p) => p.high));
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
        {p.rel_mag_err !== null && <line x1={x(p.mjd)} x2={x(p.mjd)} y1={y(p.low)} y2={y(p.high)} stroke="var(--accent)" />}
        <circle cx={x(p.mjd)} cy={y(p.value)} r={3.5} fill="var(--accent)">
          <title>{`${formatMjd(p.mjd)} · ${p.value.toFixed(1)}% relative to the band reference`}</title>
        </circle>
      </g>)}
    </svg>
    <figcaption className="muted small">Each point is relative to the mean magnitude in this wavelength band (0%).
      Bars show the reported statistical uncertainty. Points are individual exposures.</figcaption>
  </figure>;
}

function Measurements({ points, unit }: { points: LightCurvePoint[]; unit: LightCurveData['unit'] }) {
  return <div className="science-table-wrap" role="region" aria-label="Light curve measurements" tabIndex={0}>
    <table className="science-table">
      <thead><tr><th>Date (UTC)</th><th>Detector</th><th>λ (µm)</th><th>Measured signal ({unit})</th><th>Statistical error</th><th>Quality</th></tr></thead>
      <tbody>{points.map((p) => <tr key={p.frame_id}>
        <td>{formatMjd(p.mjd)}</td><td>D{p.detector}</td><td>{p.wavelength_um?.toFixed(4) ?? '—'}</td>
        <td>{p.flux?.toPrecision(5) ?? '—'}</td><td>{p.flux_err?.toPrecision(3) ?? '—'}</td>
        <td>{p.excluded ? exclusionLabels[p.excluded] : 'Used'}{p.flags.length > 0 && ` · ${p.flags.join(', ')}`}</td>
      </tr>)}</tbody>
    </table>
  </div>;
}

function ProductView({ product }: { product: LightCurveProduct }) {
  const { curve, provenance } = product;
  const [selected, setSelected] = useState<number | undefined>(() =>
    curve.bins.reduce<LightCurveData['bins'][number] | undefined>(
      (best, bin) => !best || bin.n_points > best.n_points ? bin : best, undefined,
    )?.index);
  const usable = curve.points.filter((p) => p.excluded === null && p.rel_mag !== null);
  const points = usable.filter((p): p is LightCurvePoint & { rel_mag: number } => p.bin === selected && p.rel_mag !== null)
    .sort((a, b) => a.mjd - b.mjd);
  const rejected = curve.points.filter((p) => p.excluded !== null);
  const period = curve.period;
  const wing = curve.method === 'wing';
  const first = points[0], last = points[points.length - 1];
  const change = points.length > 1 && last.mjd > first.mjd
    ? 100 * (brightnessRatio(last.rel_mag - first.rel_mag) - 1) : null;

  return <>
    <h3>{product.target_name}</h3>
    <p>{wing ? 'Relative brightness from the unsaturated wings of the image. The core is saturated, so total flux cannot be measured here.'
      : 'Background-subtracted aperture photometry.'} {usable.length} of {curve.points.length} measurements used.</p>
    {(provenance.partial || provenance.stale_search || provenance.truncated_search) && <p className="muted small">
      Archive selection: {[provenance.partial && 'partial', provenance.stale_search && 'cached search', provenance.truncated_search && 'truncated']
        .filter(Boolean).join(' · ')}.</p>}
    {curve.bins.length > 0 && <label>Comparable wavelength band
      <select value={selected} onChange={(e) => setSelected(Number(e.target.value))}>
        {curve.bins.map((bin) => <option key={bin.index} value={bin.index}>
          D{bin.detector} · {bin.lambda_min_um.toFixed(4)}–{bin.lambda_max_um.toFixed(4)} µm · {bin.n_points} observations
        </option>)}
      </select>
    </label>}
    {points.length ? <>
      <LightCurvePlot points={points} wing={wing} />
      {change !== null && <p className="small">First to last in this band ({formatMjd(first.mjd).slice(0, 10)} to {formatMjd(last.mjd).slice(0, 10)}):
        {' '}{change >= 0 ? '+' : ''}{change.toFixed(1)}% {wing ? 'relative wing brightness' : 'aperture flux'}.</p>}
      <details><summary>Measurements in this band ({points.length})</summary><Measurements points={points} unit={curve.unit} /></details>
    </> : <p role="status">No usable measurements in a comparable wavelength band.</p>}
    <details>
      <summary>Excluded measurements ({rejected.length}) · failed inputs ({curve.failures.length})</summary>
      {rejected.length > 0 && <>
        <p>{Object.entries(curve.excluded).map(([reason, count]) => `${exclusionLabels[reason as LightCurveExclusion]}: ${count}`).join(' · ')}</p>
        <Measurements points={rejected} unit={curve.unit} />
      </>}
      {curve.failures.map((f, i) => <p className="small" key={i}>{f.frame_id ?? 'Input'}: {f.reason.replaceAll('_', ' ')}</p>)}
      {!rejected.length && !curve.failures.length && <p>No exclusions or input failures reported.</p>}
    </details>
    <h4>Period evidence</h4>
    {period ? <>
      <p>{period.significant === true ? `Candidate cycle: ${period.period_days.toFixed(1)} days. Significant in the visit-permutation test.`
        : period.significant === false ? 'The test found no significant period.' : 'The candidate cycle was not tested for significance.'}
        {period.false_alarm !== null && ` False-alarm probability: ${(period.false_alarm * 100).toFixed(2)}% (${period.n_permutations} permutations).`}
        {period.significant === true && period.bootstrap_95_days &&
          ` Bootstrap 95% interval: ${period.bootstrap_95_days.map((d) => d.toFixed(1)).join('–')} days.`}</p>
      <p className="muted small">{period.caveat}</p>
    </> : <p className="muted">No period estimate is available for this product.</p>}
  </>;
}

export function LightCurvePanel({ targetId }: { targetId: string }) {
  const request = useScienceRequest<LightCurveProduct | 'missing'>(targetId);
  const live = client.config.mode === 'api';
  const load = () => request.run(async (signal) => {
    try {
      return await client.getLightCurve(targetId, signal);
    } catch (error) {
      if (error instanceof ApiError && error.status === 404) return 'missing';
      throw error;
    }
  });

  return <details className="panel science-panel" onToggle={(e) => {
    if (e.currentTarget.open && live && !request.data && !request.busy && !request.error) void load();
  }}>
    <summary>Light curve</summary>
    {!live && <p>Open this field in live API mode to look for a precomputed light curve.</p>}
    {request.busy && <p role="status">Loading light curve…</p>}
    {request.error && <><p role="alert" className="error">{request.error}</p>
      <button type="button" onClick={() => void load()}>Retry</button></>}
    {request.data === 'missing' && <p role="status">No precomputed light curve is available for this field.</p>}
    {request.data && request.data !== 'missing' && <ProductView product={request.data} />}
  </details>;
}
