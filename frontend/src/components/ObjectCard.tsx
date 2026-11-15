import { useEffect, useState } from 'react';
import { client } from '../api/client';
import {
  describeObjectError, factRows, identityCaveat, isEmptySky, lookupKey, lookupLabel, matchSummary, photometryGroups,
  planetLine, planetsSummary, serviceRows, servicesSummary, variabilityText, type ObjectLookup,
} from '../api/objectCard';
import type { ObjectContextResponse } from '../api/types';

// The backend answers within its own deadline (< 30 s, partial results after that); this only guards a hung network.
const CLIENT_TIMEOUT_MS = 45_000;

interface CardState { key: string; busy: boolean; data: ObjectContextResponse | null; error: string }

/** Catalog context of the chosen position/name. Independent of the SPHEREx build: it never blocks the job/video. */
export function ObjectCard({ lookup }: { lookup: ObjectLookup | null }) {
  const live = client.config.mode === 'api';
  const key = lookupKey(lookup);
  const [attempt, setAttempt] = useState(0);
  const [state, setState] = useState<CardState>({ key: '', busy: false, data: null, error: '' });
  useEffect(() => {
    if (!lookup || !live) return;
    const abort = new AbortController();
    const timer = setTimeout(() => abort.abort(new DOMException('Catalog context timed out', 'TimeoutError')), CLIENT_TIMEOUT_MS);
    setState({ key, busy: true, data: null, error: '' });
    client.getObjectContext(lookup, abort.signal)
      .then((data) => { if (!abort.signal.aborted) setState({ key, busy: false, data, error: '' }); })
      .catch((e: unknown) => {
        const timedOut = abort.signal.reason instanceof DOMException && abort.signal.reason.name === 'TimeoutError';
        if (abort.signal.aborted && !timedOut) return; // superseded by a newer position
        setState({ key, busy: false, data: null, error: describeObjectError(timedOut ? abort.signal.reason : e) });
      })
      .finally(() => clearTimeout(timer));
    return () => { clearTimeout(timer); abort.abort(); };
  }, [key, live, attempt]); // `key` identifies `lookup`; `attempt` is the retry button

  if (!lookup) return null;
  const current = state.key === key ? state : { key, busy: live, data: null, error: '' };
  return <section className="object-card" aria-labelledby="object-card-title" aria-busy={current.busy}>
    <h3 id="object-card-title">Catalog context <span className="muted small">· {lookupLabel(lookup)}</span></h3>
    <p className="object-note small">Catalog context, not SPHEREx measurements.</p>
    {!live && <p className="muted small">SIMBAD, Gaia DR3, VSX, exoplanet and 2MASS/AllWISE context needs the live API.</p>}
    {current.busy && <p className="small" role="status">Looking up SIMBAD, Gaia DR3, AAVSO VSX, the NASA Exoplanet Archive,
      2MASS and AllWISE… (up to ~30 s). The SPHEREx build does not wait for this.</p>}
    {current.error && <p className="error small" role="alert">{current.error}{' '}
      <button className="link-button" onClick={() => setAttempt((n) => n + 1)}>Retry</button></p>}
    {current.data && <ObjectCardBody data={current.data} onRetry={() => setAttempt((n) => n + 1)} />}
  </section>;
}

function ObjectCardBody({ data, onRetry }: { data: ObjectContextResponse; onRetry: () => void }) {
  const id = data.identity;
  const match = matchSummary(data);
  const empty = isEmptySky(data);
  const type = [id.object_type_label ?? id.object_type, id.object_type && id.object_type_label ? `(${id.object_type})` : '']
    .filter(Boolean).join(' ');
  const services = serviceRows(data.provenance);
  const photometry = photometryGroups(data.photometry);
  const caveat = identityCaveat(data);
  return <>
    <p className="object-name">{id.display_name ?? (empty ? 'No catalogued source' : 'Unidentified position')}</p>
    {(type || id.spectral_type) && <p className="small">{type || 'Type not given'}{id.spectral_type ? ` · spectral type ${id.spectral_type}` : ''}</p>}
    <p className={`object-match tone-${match.tone}`} role="status"><strong>{match.label}.</strong> {match.detail}</p>
    {id.identity_uncertain && id.match !== 'ambiguous' && id.match !== 'loose' &&
      <p className="object-match tone-warn small">Identity not secure: values matched by position may belong to a neighbouring source.</p>}
    {data.partial && <p className="object-match tone-warn small">Partial: some catalogs did not answer, so their values are
      unknown (not negative).{' '}<button className="link-button" onClick={onRetry}>Retry</button></p>}
    {empty ? <p className="small">Nothing is catalogued here in Gaia DR3, AAVSO VSX, 2MASS or AllWISE within {data.query.radius_arcsec}″.
      SPHEREx may still show emission at this position.</p> : <>
      <p className="muted small">Physical parameters from catalogs (“unknown” = not measured or not found):</p>
      <ul className="object-facts" aria-label="Physical parameters from catalogs">
        {factRows(data.facts).map((f) => <li key={f.label}>
          <div className="fact-line"><span className="fact-label">{f.label}</span>
            <span className={f.unknown ? 'fact-value muted' : 'fact-value'}>{f.value}</span>
            {!f.unknown && <span className={`fact-status fact-${f.status.replace(' ', '-')}`}>{f.status}</span>}</div>
          <div className="object-source">{f.source}</div>
        </li>)}
      </ul>
      {data.variability && <p className="small"><strong>Variability (AAVSO VSX):</strong> {variabilityText(data.variability)}
        {' · '}{data.variability.url ? <a href={data.variability.url} target="_blank" rel="noreferrer">{data.variability.name}</a>
          : data.variability.name}{caveat && <span className="tone-warn"> · {caveat}</span>}</p>}
      <p className="small"><strong>{planetsSummary(data)}</strong></p>
      {data.planets.length > 0 && <ul className="small object-list">{data.planets.map((p) => <li key={p.name}>{planetLine(p)}</li>)}</ul>}
      {data.nearby_planet_hosts.length > 0 && <p className="small muted">Nearby planet host, NOT this object:{' '}
        {data.nearby_planet_hosts.map((h) => `${h.hostname} (${Math.round(h.separation_arcsec)}″: ${h.planets.join(', ')})`).join('; ')}</p>}
      {photometry.length > 0 && <details className="object-details">
        <summary>Context photometry · other missions (2MASS/AllWISE), not SPHEREx</summary>
        {photometry.map((g) => <div key={g.designation} className="small">
          <p className="object-mission"><strong>{g.label}</strong> · {g.designation}
            {g.identityUncertain && <span className="tone-warn"> · identity uncertain (may be a neighbour)</span>}</p>
          <ul className="object-list">{g.rows.map((r) => <li key={r.band}>{r.band} ({r.wavelength}): {r.magnitude}
            {r.flags !== '—' && <span className="muted"> · {r.flags}</span>}</li>)}</ul>
        </div>)}
      </details>}
    </>}
    {data.warnings.length > 0 && <ul className="small object-list object-warnings">{data.warnings.map((w, i) => <li key={i}>{w}</li>)}</ul>}
    <p className="muted small">{data.note}</p>
    <details className="object-details small">
      <summary>Catalog services · {servicesSummary(data.provenance)}</summary>
      <ul className="object-list">{services.map((s, i) => <li key={i}><span className={`tone-${s.tone}`}>{s.name}: {s.status}</span>
        <br /><span className="muted object-source">{s.detail}</span></li>)}</ul>
    </details>
  </>;
}
