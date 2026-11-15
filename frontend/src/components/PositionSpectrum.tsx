import { useEffect, useState } from 'react';
import { client } from '../api/client';
import { formatMjd, formatRaDec } from '../api/format';
import { plotMeasurements } from '../api/science';
import type { SkyCoord, SpectrumRequest, SpectrumResponse } from '../api/types';
import { useScienceRequest } from './useScienceRequest';

function MeasurementPlot({ result }: { result: SpectrumResponse }) {
  const points = plotMeasurements(result.points);
  if (!points.length) return <p role="status">No usable measurements at this position. Saturation, missing coverage or flags can exclude points; see the table below.</p>;
  const values = points.flatMap((p) => [p.flux! - (p.flux_err ?? 0), p.flux! + (p.flux_err ?? 0)]);
  const lo = Math.min(0, ...values), hi = Math.max(0, ...values);
  const span = Math.max(hi - lo, Math.abs(hi) * .1, .001);
  const y0 = lo - span * .1, y1 = hi + span * .1;
  const sx = (x: number) => 62 + (x - .7) / 4.4 * 500;
  const sy = (y: number) => 228 - (y - y0) / (y1 - y0) * 200;
  return <figure className="measurement-plot">
    <svg viewBox="0 0 600 270" role="img" aria-label={`Measured spectrum: ${points.length} usable points, ${result.unit}`}>
      <path d="M62 20V228H570" fill="none" stroke="currentColor" />
      {[1,2,3,4,5].map((x) => <g key={x}><path d={`M${sx(x)} 228v5`} stroke="currentColor" /><text x={sx(x)} y={249} textAnchor="middle">{x}</text></g>)}
      {[0,.5,1].map((t) => { const v = y0 + t * (y1-y0); return <text key={t} x={56} y={sy(v)+4} textAnchor="end">{v.toPrecision(3)}</text>; })}
      {points.map((p) => <g key={p.id}>
        {p.flux_err !== null && <line x1={sx(p.wavelength_um!)} x2={sx(p.wavelength_um!)}
          y1={sy(p.flux! - p.flux_err)} y2={sy(p.flux! + p.flux_err)} stroke="var(--accent)" />}
        <circle cx={sx(p.wavelength_um!)} cy={sy(p.flux!)} r={3} fill="var(--accent)"><title>
          {`${p.wavelength_um!.toFixed(3)} µm · ${p.flux!.toPrecision(4)} ${result.unit}${p.mjd !== null ? ` · ${formatMjd(p.mjd)}` : ''}`}
        </title></circle>
      </g>)}
      <text x={310} y={267} textAnchor="middle">Wavelength (µm)</text>
      <text x={65} y={13}>{result.unit === 'mJy' ? 'Aperture flux (mJy)' : 'Surface brightness (MJy/sr)'}</text>
    </svg>
    <figcaption className="muted small">Each dot is a measurement; missing points are not interpolated.
      {result.source === 'dr1_cube' ? ' The cube supplies no flux uncertainties.' : ' Error bars are the reported photometric uncertainties.'}</figcaption>
  </figure>;
}

export function PositionSpectrum({ position, fieldId, inline = false, quickLook = false }: {
  position: SkyCoord; fieldId?: string; inline?: boolean; quickLook?: boolean;
}) {
  const [source, setSource] = useState<'dr1_cube' | 'l2_exposures'>('dr1_cube');
  const [aperture, setAperture] = useState(0);
  const [detector, setDetector] = useState(0);
  const [from, setFrom] = useState('');
  const [to, setTo] = useState('');
  const [maxFrames, setMaxFrames] = useState(24);
  const { ra, dec } = position;
  const exposureField = source === 'l2_exposures' ? fieldId : undefined;
  const request = useScienceRequest<SpectrumResponse>(`${ra}/${dec}/${source}/${aperture}/${detector}/${from}/${to}/${maxFrames}/${exposureField ?? ''}`);
  const { run } = request;
  const live = client.config.mode === 'api';
  useEffect(() => {
    if (!live || !quickLook) return;
    // Let Strict Mode finish its initial cleanup before starting the extraction.
    const timer = setTimeout(() => {
      void run((signal) => client.getSpectrum({ ra, dec, source: 'dr1_cube', aperture_px: 0, detectors: [] }, signal));
    }, 0);
    return () => clearTimeout(timer);
  }, [ra, dec, live, quickLook, run]);

  const content = <>
    <p className="muted small">Measures this fixed sky position, independently of candidates.</p>
    {!live && <p>Use live API mode to extract measurements.</p>}
    <form onSubmit={(e) => { e.preventDefault(); const body: SpectrumRequest = { ra: position.ra, dec: position.dec, source,
      detectors: detector ? [detector] : [], field_id: exposureField,
      ...(source === 'dr1_cube' ? {aperture_px: aperture} : {max_frames: maxFrames,
        mjd_min: from ? Date.parse(`${from}T00:00:00Z`)/86400000+40587 : null,
        mjd_max: to ? Date.parse(`${to}T23:59:59.999Z`)/86400000+40587 : null})};
      void request.run((signal) => client.getSpectrum(body, signal)); }}>
      <div className="science-controls">
        <label>Spectrum source<select value={source} onChange={(e) => setSource(e.target.value as typeof source)}>
          <option value="dr1_cube">DR1 cube · static quick look</option><option value="l2_exposures">L2 exposures · aperture photometry</option>
        </select></label>
        <label>Spectrum detector<select value={detector} onChange={(e) => setDetector(Number(e.target.value))}>
          <option value={0}>All detectors</option>{[1,2,3,4,5,6].map((d) => <option key={d} value={d}>D{d}</option>)}
        </select></label>
        {source === 'dr1_cube' ? <label>Cube aperture radius (pixels)<select value={aperture} onChange={(e) => setAperture(Number(e.target.value))}>
          {[0,1,2,3].map((n) => <option key={n} value={n}>{n === 0 ? '0 · native pixel' : n}</option>)}</select></label> : <>
          <label>Spectrum from (UTC)<input type="date" value={from} onChange={(e) => setFrom(e.target.value)} /></label>
          <label>Spectrum to (UTC)<input type="date" value={to} min={from || undefined} onChange={(e) => setTo(e.target.value)} /></label>
          <label>Maximum exposures<input type="number" min={2} max={60} required value={maxFrames} onChange={(e) => setMaxFrames(Number(e.target.value))} /></label>
        </>}
      </div>
      <p className="muted small">{source === 'dr1_cube' ? 'Static surface brightness (MJy/sr), without background subtraction or flux errors. Saturated cores can be missing.'
        : 'Background-subtracted aperture flux (mJy) at each exposure date. Wavelength and time vary together; do not interpret a mixed-epoch curve as a simultaneous spectrum.'}</p>
      <button disabled={!live || request.busy}>{request.busy ? 'Extracting measurements…' : 'Extract spectrum'}</button>
    </form>
    {request.busy && <button onClick={request.stop}>Stop waiting for spectrum</button>}
    {request.error && <p role="alert" className="error">{request.error}</p>}
    {request.data && <>
      <p role="status">{request.data.points.filter((p) => p.usable).length} usable / {request.data.points.length} measured points · {request.data.failures.length} failed inputs</p>
      {(request.data.stale || request.data.truncated) && <p className="error">Archive selection is {request.data.stale ? 'stale' : ''} {request.data.truncated ? 'truncated' : ''}; completeness is not established.</p>}
      <MeasurementPlot result={request.data} />
      <ul className="small muted">{request.data.notes.map((n, i) => <li key={i}>{n}</li>)}</ul>
      <details><summary>Measurements, dates and quality</summary><div className="science-table-wrap"><table className="science-table">
        <thead><tr><th>λ (µm)</th><th>Flux ({request.data.unit})</th><th>Error</th><th>UTC / release</th><th>Quality</th><th>Source</th></tr></thead>
        <tbody>{request.data.points.map((p) => <tr key={p.id}><td>{p.wavelength_um?.toFixed(3) ?? 'unknown'}</td>
          <td>{p.flux?.toPrecision(5) ?? 'missing'}</td><td>{p.flux_err?.toPrecision(3) ?? 'not provided'}</td>
          <td>{p.mjd !== null ? formatMjd(p.mjd) : 'static coadd'} · {p.release}</td><td>{p.flags.join(', ') || 'no flags reported'}</td>
          <td>{p.source_uri && /^https?:\/\//.test(p.source_uri) ? <a href={p.source_uri} target="_blank" rel="noreferrer">{p.frame_id ?? p.id}</a> : p.frame_id ?? p.id}</td></tr>)}</tbody>
      </table></div>
      {request.data.failures.map((f, i) => <p className="small error" key={i}>{f.frame_id ?? 'Input'}: {f.reason}</p>)}</details>
    </>}
  </>;

  return inline ? <section className="science-panel" aria-label="Position spectrum">{content}</section>
    : <details className="panel science-panel">
      <summary>Spectrum at {formatRaDec(ra, dec)}</summary>
      {content}
    </details>;
}
