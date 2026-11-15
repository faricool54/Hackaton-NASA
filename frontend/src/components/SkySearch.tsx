import { useEffect, useRef, useState } from 'react';
import { ApiError, client } from '../api/client';
import { formatRaDec } from '../api/format';
import { searchPosition, searchSequences, type SearchSequence } from '../api/skySearch';
import type { SkyCoord } from '../api/types';
import { SyntheticBadge } from './SyntheticBadge';

interface Props {
  sequences: SearchSequence[];
  onLocate: (point: SkyCoord, label?: string, source?: string) => void;
}

export function SkySearch({ sequences, onLocate }: Props) {
  const [query, setQuery] = useState('');
  const [status, setStatus] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const request = useRef<AbortController | null>(null);
  const live = client.config.mode === 'api';
  useEffect(() => () => request.current?.abort(), []);

  let point: SkyCoord | null = null;
  let positionError = '';
  try { point = searchPosition(query); }
  catch (e) { positionError = (e as Error).message; }
  const matches = positionError ? [] : searchSequences(sequences, query, point ?? undefined).slice(0, 5);

  async function submit() {
    request.current?.abort();
    setBusy(false); setStatus(''); setError('');
    if (positionError) { setError(positionError); return; }
    if (matches.length === 1) { location.href = matches[0].href; return; }
    if (matches.length > 1) { setStatus('Choose a matching sequence below.'); return; }
    if (point) {
      onLocate(point);
      setStatus(live ? 'Position selected. Build a time sequence in the panel below.'
        : 'Position selected on the map. No saved sequence matched; building a new one requires the live API.');
      return;
    }
    if (!live) { setStatus('No saved sequence matched. Looking up other names requires the live API.'); return; }
    const abort = new AbortController();
    request.current = abort;
    setBusy(true);
    try {
      const result = await client.resolveName(query.trim(), abort.signal);
      if (abort.signal.aborted) return;
      onLocate(result, result.resolved_name, result.source);
      setStatus('Position selected. Build a time sequence in the panel below.');
    } catch (e) {
      if (!abort.signal.aborted) {
        setError(e instanceof ApiError && e.status === 404 ? 'Object name not found. Try another name or enter RA and Dec.'
          : 'Name lookup is unavailable. Try again or enter RA and Dec.');
      }
    } finally {
      if (!abort.signal.aborted) setBusy(false);
    }
  }

  return <section className="panel sky-search" aria-label="Sky search">
    <form role="search" onSubmit={(e) => { e.preventDefault(); void submit(); }}>
      <label htmlFor="sky-query">Search the sky</label>
      <div className="sky-search-row">
        <input type="search" id="sky-query" value={query} maxLength={120} autoComplete="off"
          placeholder="Barnard’s Star or 269.44623, +4.76870" aria-describedby="sky-query-help"
          onChange={(e) => {
            request.current?.abort();
            setQuery(e.target.value); setBusy(false); setError(''); setStatus('');
          }} />
        <button type="submit" className="primary-action" disabled={!query.trim() || busy}>
          {busy ? 'Searching…' : 'Search'}
        </button>
      </div>
    </form>
    <p id="sky-query-help" className="muted small">Use an object name or RA and Dec in degrees or HH:MM:SS, ±DD:MM:SS.
      {' '}{live ? 'Other names use the live catalog.' : 'Saved sequences work without the live API.'}</p>
    {error && <p className="error small" role="alert">{error}</p>}
    <p className="small search-status" role="status">{status || (busy ? 'Looking up the object name…' : '')}</p>
    {matches.length > 0 && <ul className="search-matches" aria-label="Matching sequences">
      {matches.map(({ field, href }) => <li key={href}>
        <a className="card search-match" href={href}>
          <span>{field.id.startsWith('job-') ? 'SPHEREx sequence' : field.name} <SyntheticBadge synthetic={field.synthetic} /></span>
          <span className="muted small">{formatRaDec(field.center.ra, field.center.dec)} · {field.n_frames} frames</span>
        </a>
      </li>)}
    </ul>}
  </section>;
}
