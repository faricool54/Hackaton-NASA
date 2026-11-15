import { useState } from 'react';
import { client } from '../api/client';
import { formatMjd } from '../api/format';
import { comparisonSelection, comparisonTitle } from '../api/science';
import type { ComparisonImage, ComparisonResponse, Field } from '../api/types';
import { useScienceRequest } from './useScienceRequest';

function ComparisonPreview({ image }: { image: ComparisonImage }) {
  const [error, setError] = useState(false);
  const [attempt, setAttempt] = useState(0);
  return <figure>
    {error && <p className="error" role="alert">Comparison image could not load.{' '}
      <button onClick={() => { setError(false); setAttempt((a) => a+1); }}>Retry comparison image</button></p>}
    <img className="comparison-image" src={`${client.analysisImageUrl(image.image)}?retry=${attempt}`}
      alt={comparisonTitle(image)} onError={() => setError(true)} />
    <figcaption className="small">{formatMjd(image.mjd_min)} → {formatMjd(image.mjd_max)} · {image.frame_ids.length} inputs
      {image.wavelength_range_um && ` · λ ${image.wavelength_range_um[0].toFixed(3)}–${image.wavelength_range_um[1].toFixed(3)} µm`}
      {image.valid_fraction !== null && ` · ${(100*image.valid_fraction).toFixed(1)}% valid pixels`}
    </figcaption>
  </figure>;
}

/** Season comparisons. `inline` (FieldPage's Seasons tab) shows it open; otherwise a folded <details>. */
export function FieldComparisons({ field, inline = false }: { field: Field; inline?: boolean }) {
  const detectors = [...new Set(field.frames.map((f) => f.detector))].sort();
  const [detector, setDetector] = useState(detectors.includes(2) ? 2 : detectors[0] ?? 1);
  const [from, setFrom] = useState('');
  const [to, setTo] = useState('');
  const [selectedId, setSelectedId] = useState('');
  const request = useScienceRequest<ComparisonResponse>(`${field.id}/${field.provenance.built_at}/${detector}/${from}/${to}`);
  const live = client.config.mode === 'api';
  const selected = request.data?.images.find((i) => i.id === selectedId) ?? request.data?.images[0];
  if (field.provenance.synthetic) return null;
  const title = 'Compare seasons · weighted means and differences';
  const content = <>
    <p className="muted small">Rebuild from the field's selected real FITS exposures on the same grid, separately per detector.
      Different wavelengths can leave a residual even for a constant source.</p>
    {!live && <p>Comparison generation requires live API mode.</p>}
    <form onSubmit={(e) => { e.preventDefault(); void request.run((signal) => client.getComparisons(field.id, {
      detectors: detector ? [detector] : [], frame_ids: comparisonSelection(field, detector, from, to),
    }, signal)); }}>
      <div className="science-controls">
        <label>Comparison detector<select value={detector} onChange={(e) => setDetector(Number(e.target.value))}>
          {detectors.map((d) => <option key={d} value={d}>D{d}</option>)}<option value={0}>All · kept separate</option>
        </select></label>
        <label>Comparison from (UTC)<input type="date" value={from} onChange={(e) => setFrom(e.target.value)} /></label>
        <label>Comparison to (UTC)<input type="date" value={to} min={from || undefined} onChange={(e) => setTo(e.target.value)} /></label>
      </div>
      <p className="muted small">At most 60 frames. A weighted mean is not a raw sum. Differences use later − scale × earlier.</p>
      <button disabled={!live || request.busy}>{request.busy ? 'Building comparisons…' : 'Build comparisons'}</button>
    </form>
    {request.busy && <button onClick={request.stop}>Stop waiting for comparisons</button>}
    {request.error && <p className="error" role="alert">{request.error}</p>}
    {request.data && <>
      <p role="status">{request.data.images.length} products · {request.data.failures.length} failed inputs</p>
      {request.data.images.length === 0 && <p>No comparison products could be formed from these inputs.</p>}
      {!request.data.images.some((i) => i.kind === 'scaled_difference') && <p className="muted small">No overlapping season pair was available for a difference.</p>}
      {selected && <>
        <label>Comparison product<select value={selected.id} onChange={(e) => setSelectedId(e.target.value)}>
          {request.data.images.map((i) => <option key={i.id} value={i.id}>{comparisonTitle(i)}</option>)}
        </select></label>
        <ComparisonPreview key={selected.image} image={selected} />
        {selected.kind === 'scaled_difference' && <p className="small">Orange: positive (later brighter). Cyan: negative (earlier brighter).
          {' '}Scale {selected.flux_scale?.toPrecision(4)} · {selected.flux_scale_fitted ? `fitted on ${selected.flux_scale_stars} field stars` : 'not fitted; read limitations'}
          {' · '}Noise {selected.noise_mjy_sr?.toPrecision(3) ?? 'unknown'} MJy/sr.
        </p>}
        {selected.notes.map((n, i) => <p className="muted small" key={i}>{n}</p>)}
      </>}
      <details><summary>Method, limitations and input provenance</summary>
        <p className="small">{request.data.method}</p>
        <ul className="small muted">{request.data.notes.map((n, i) => <li key={i}>{n}</li>)}</ul>
        {request.data.input_frames.map((f) => <p className="small provenance-row" key={f.id}>{f.id} · {formatMjd(f.mjd)} · D{f.detector} · {f.release}
          {f.source_uri && /^https?:\/\//.test(f.source_uri) && <> · <a href={f.source_uri} target="_blank" rel="noreferrer">FITS source</a></>}</p>)}
        {request.data.failures.map((f, i) => <p className="small error" key={i}>{f.frame_id}: {f.reason}</p>)}
      </details>
    </>}
  </>;
  return inline
    ? <section className="science-panel fd-science" aria-label="Compare seasons"><h3 className="fd-section-title">{title}</h3>{content}</section>
    : <details className="panel science-panel"><summary>{title}</summary>{content}</details>;
}
