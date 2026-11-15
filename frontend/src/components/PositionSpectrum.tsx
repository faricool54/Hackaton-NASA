import { useEffect, useState } from 'react';
import { client } from '../api/client';
import { formatMjd, formatRaDec } from '../api/format';
import { plotMeasurements, SPECTRUM_SOURCE_LABELS, spectrumCaveat, spectrumSummary, type SpectrumSource } from '../api/science';
import type { SkyCoord, SpectrumRequest, SpectrumResponse } from '../api/types';
import { PlotTooltip, type PlotTip } from './SciencePlot';
import { SyntheticBadge } from './SyntheticBadge';
import { useScienceRequest } from './useScienceRequest';
import '../styles/science.css';

/** Plot box per layout: the dock gets a narrower viewBox so 11 px labels stay readable at ~420 px. */
const LAYOUTS = {
  wide: { w: 600, h: 270, l: 62, r: 30, t: 20, b: 42 },
  compact: { w: 400, h: 232, l: 50, r: 12, t: 20, b: 40 },
};

function MeasurementPlot({ result, compact = false }: { result: SpectrumResponse; compact?: boolean }) {
  const [tip, setTip] = useState<PlotTip | null>(null);
  const points = plotMeasurements(result.points);
  if (!points.length) return <p role="status" className="sci-empty">No usable measurements at this position. Saturation, missing coverage or flags can exclude points; see the table below.</p>;
  const box = compact ? LAYOUTS.compact : LAYOUTS.wide;
  const values = points.flatMap((p) => [p.flux! - (p.flux_err ?? 0), p.flux! + (p.flux_err ?? 0)]);
  const lo = Math.min(0, ...values), hi = Math.max(0, ...values);
  const span = Math.max(hi - lo, Math.abs(hi) * .1, .001);
  const y0 = lo - span * .1, y1 = hi + span * .1;
  const bottom = box.h - box.b;
  const sx = (x: number) => box.l + (x - .7) / 4.4 * (box.w - box.l - box.r);
  const sy = (y: number) => bottom - (y - y0) / (y1 - y0) * (bottom - box.t);
  const yTicks = [0, .25, .5, .75, 1].map((t) => y0 + t * (y1 - y0));
  const unitLabel = result.unit === 'mJy' ? 'Aperture flux (mJy)' : 'Surface brightness (MJy/sr)';
  return <figure className={`measurement-plot sci-plot${compact ? ' sci-plot--compact' : ''}`} onMouseLeave={() => setTip(null)}>
    <div className="sci-plot-box">
      <svg viewBox={`0 0 ${box.w} ${box.h}`} role="img" aria-label={`Measured spectrum: ${points.length} usable points, ${result.unit}`}>
        {yTicks.map((v, i) => <path key={i} className="sci-grid" d={`M${box.l} ${sy(v)}H${box.w - box.r}`} />)}
        {lo < 0 && <path className="sci-zero" d={`M${box.l} ${sy(0)}H${box.w - box.r}`} />}
        <path className="sci-axis" d={`M${box.l} ${box.t}V${bottom}H${box.w - box.r}`} fill="none" />
        {[1,2,3,4,5].map((x) => <g key={x}><path className="sci-axis" d={`M${sx(x)} ${bottom}v5`} /><text x={sx(x)} y={bottom + 17} textAnchor="middle">{x}</text></g>)}
        {[0, .5, 1].map((t) => { const v = y0 + t * (y1 - y0); return <text key={t} x={box.l - 6} y={sy(v) + 4} textAnchor="end">{v.toPrecision(3)}</text>; })}
        {points.map((p) => {
          const cx = sx(p.wavelength_um!), cy = sy(p.flux!);
          const lines = [`${p.wavelength_um!.toFixed(3)} µm · D${p.detector}`,
            `${p.flux!.toPrecision(4)} ${result.unit}${p.flux_err !== null ? ` ± ${p.flux_err.toPrecision(2)}` : ''}`,
            p.mjd !== null ? formatMjd(p.mjd) : 'static coadd', p.flags.length ? `Flags: ${p.flags.join(', ')}` : 'No flags reported'];
          return <g key={p.id} className="sci-point" onMouseEnter={() => setTip({ x: cx / box.w, y: cy / box.h, lines })}>
            {p.flux_err !== null && <line className="sci-err" x1={cx} x2={cx} y1={sy(p.flux! - p.flux_err)} y2={sy(p.flux! + p.flux_err)} />}
            <circle cx={cx} cy={cy} r={compact ? 3.2 : 3.5} className="sci-dot"><title>
              {`${p.wavelength_um!.toFixed(3)} µm · ${p.flux!.toPrecision(4)} ${result.unit}${p.mjd !== null ? ` · ${formatMjd(p.mjd)}` : ''}`}
            </title></circle>
          </g>;
        })}
        <text x={box.l + (box.w - box.l - box.r) / 2} y={box.h - 4} textAnchor="middle">Wavelength (µm)</text>
        <text x={box.l + 3} y={box.t - 7}>{unitLabel}</text>
      </svg>
      <PlotTooltip tip={tip} />
    </div>
    <figcaption className="muted small">Each dot is a measurement; missing points are not interpolated.
      {result.source === 'dr1_cube' ? ' The cube supplies no flux uncertainties.' : ' Error bars are the reported photometric uncertainties.'}</figcaption>
  </figure>;
}

function MeasurementTable({ data }: { data: SpectrumResponse }) {
  return <details className="sci-more"><summary>Measurements, dates and quality ({data.points.length})</summary><div className="science-table-wrap"><table className="science-table">
    <thead><tr><th>λ (µm)</th><th>Flux ({data.unit})</th><th>Error</th><th>UTC / release</th><th>Quality</th><th>Source</th></tr></thead>
    <tbody>{data.points.map((p) => <tr key={p.id}><td>{p.wavelength_um?.toFixed(3) ?? 'unknown'}</td>
      <td>{p.flux?.toPrecision(5) ?? 'missing'}</td><td>{p.flux_err?.toPrecision(3) ?? 'not provided'}</td>
      <td>{p.mjd !== null ? formatMjd(p.mjd) : 'static coadd'} · {p.release}</td><td>{p.flags.join(', ') || 'no flags reported'}</td>
      <td>{p.source_uri && /^https?:\/\//.test(p.source_uri) ? <a href={p.source_uri} target="_blank" rel="noreferrer">{p.frame_id ?? p.id}</a> : p.frame_id ?? p.id}</td></tr>)}</tbody>
  </table></div>
  {data.failures.map((f, i) => <p className="small error" key={i}>{f.frame_id ?? 'Input'}: {f.reason}</p>)}</details>;
}

export function PositionSpectrum({ position, fieldId, inline = false, quickLook = false, compact }: {
  position: SkyCoord; fieldId?: string; inline?: boolean; quickLook?: boolean;
  /** Chart-first layout with the controls folded into "Options"; defaults to `inline` (the home dock). */
  compact?: boolean;
}) {
  const dense = compact ?? inline;
  const [source, setSource] = useState<SpectrumSource>('dr1_cube');
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

  const data = request.data;
  // The legend follows the plotted result; before a result it describes the selected source.
  const shownSource: SpectrumSource = data?.source ?? source;
  const scope = <p className="muted small">Measures this fixed sky position, independently of candidates.</p>;

  const extract = () => { const body: SpectrumRequest = { ra: position.ra, dec: position.dec, source,
    detectors: detector ? [detector] : [], field_id: exposureField,
    ...(source === 'dr1_cube' ? {aperture_px: aperture} : {max_frames: maxFrames,
      mjd_min: from ? Date.parse(`${from}T00:00:00Z`)/86400000+40587 : null,
      mjd_max: to ? Date.parse(`${to}T23:59:59.999Z`)/86400000+40587 : null})};
    void request.run((signal) => client.getSpectrum(body, signal)); };

  const form = <form className="sci-form" onSubmit={(e) => { e.preventDefault(); extract(); }}>
    <div className="science-controls">
      <label>Spectrum source<select value={source} onChange={(e) => setSource(e.target.value as SpectrumSource)}>
        <option value="dr1_cube">{SPECTRUM_SOURCE_LABELS.dr1_cube}</option><option value="l2_exposures">{SPECTRUM_SOURCE_LABELS.l2_exposures}</option>
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
    {source !== shownSource && <p className="muted small">{spectrumCaveat(source)}</p>}
    <button className="sci-run" disabled={!live || request.busy}>{request.busy ? 'Extracting measurements…' : 'Extract spectrum'}</button>
  </form>;

  const status = <>
    {!live && <p className="sci-empty">Use live API mode to extract measurements.</p>}
    {request.busy && <div className="sci-busy" role="status">
      <span className="sci-busy-dot" aria-hidden="true" />Extracting measurements…
      <button type="button" className="link-button" onClick={request.stop}>Stop waiting for spectrum</button>
    </div>}
    {request.busy && dense && <div className="sci-skeleton" aria-hidden="true" />}
    {request.error && <p role="alert" className="error">{request.error}</p>}
  </>;

  const legend = <p className="sci-caveat small" data-source={shownSource}>
    <span className="sci-source">{SPECTRUM_SOURCE_LABELS[shownSource]}</span> {spectrumCaveat(shownSource)}
  </p>;

  const result = data && <>
    <MeasurementPlot result={data} compact={dense} />
    <p role="status" className="sci-summary">{spectrumSummary(data)}{data.synthetic && <> <SyntheticBadge synthetic /></>}</p>
    {(data.stale || data.truncated) && <p className="error small">Archive selection is {data.stale ? 'stale' : ''} {data.truncated ? 'truncated' : ''}; completeness is not established.</p>}
  </>;

  const notes = data && data.notes.length > 0 && (dense
    ? <details className="sci-more"><summary>Source and method notes ({data.notes.length})</summary>
      <ul className="small muted">{data.notes.map((n, i) => <li key={i}>{n}</li>)}</ul></details>
    : <ul className="small muted">{data.notes.map((n, i) => <li key={i}>{n}</li>)}</ul>);

  if (dense) {
    return <section className="science-panel sci-spectrum sci-spectrum--compact" aria-label="Position spectrum">
      {status}
      {result}
      {!data && !request.busy && live && <div className="sci-start">
        <p className="sci-empty">Measure the SPHEREx spectrum at this position.</p>
        <button type="button" className="sci-run u-btn u-btn--primary" onClick={extract}>Extract spectrum · {SPECTRUM_SOURCE_LABELS[source]}</button>
      </div>}
      {legend}
      {notes}
      {data && <MeasurementTable data={data} />}
      <details className="sci-options">
        <summary>Options · {SPECTRUM_SOURCE_LABELS[source]}</summary>
        {scope}
        {form}
      </details>
    </section>;
  }

  const content = <>
    {scope}
    {status}
    {result}
    {legend}
    {notes}
    {data && <MeasurementTable data={data} />}
    <details className="sci-options" open={!data}>
      <summary>Options · {SPECTRUM_SOURCE_LABELS[source]}</summary>
      {form}
    </details>
  </>;

  return inline ? <section className="science-panel sci-spectrum" aria-label="Position spectrum">{content}</section>
    : <details className="panel science-panel sci-spectrum">
      <summary>Spectrum at {formatRaDec(ra, dec)}</summary>
      {content}
    </details>;
}
