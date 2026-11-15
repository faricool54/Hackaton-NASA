import { useEffect, useId, useRef, useState } from 'react';
import { ApiError, client } from '../api/client';
import { formatRaDec } from '../api/format';
import { searchPosition, searchSequences, type SearchSequence } from '../api/skySearch';
import type { SkyCoord } from '../api/types';
import { SyntheticBadge } from './SyntheticBadge';
import '../styles/search.css';

interface Props {
  sequences: SearchSequence[];
  onLocate: (point: SkyCoord, label?: string, source?: string) => void;
  onSelectSequence: (sequence: SearchSequence) => void;
}

export function SkySearch({ sequences, onLocate, onSelectSequence }: Props) {
  const [query, setQuery] = useState('');
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(-1);
  const [status, setStatus] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const request = useRef<AbortController | null>(null);
  const input = useRef<HTMLInputElement>(null);
  const listId = useId();
  const optionId = (index: number) => `${listId}-${index}`;
  const live = client.config.mode === 'api';

  useEffect(() => {
    const focusSearch = (event: KeyboardEvent) => {
      if (event.key !== '/' || event.ctrlKey || event.metaKey || event.altKey || event.defaultPrevented) return;
      if (event.target instanceof HTMLElement && (
        event.target.isContentEditable || event.target.closest('input, textarea, select, [role="textbox"]')
      )) return;
      event.preventDefault();
      input.current?.focus();
    };
    document.addEventListener('keydown', focusSearch);
    return () => {
      document.removeEventListener('keydown', focusSearch);
      request.current?.abort();
    };
  }, []);

  let point: SkyCoord | null = null;
  let positionError = '';
  try { point = searchPosition(query); }
  catch (e) { positionError = (e as Error).message; }
  const matches = positionError ? [] : searchSequences(sequences, query, point ?? undefined).slice(0, 5);
  const showMatches = open && matches.length > 0;
  const highlighted = showMatches ? matches[active] : undefined;

  const close = () => {
    setOpen(false);
    setActive(-1);
  };

  const select = (match: SearchSequence) => {
    request.current?.abort();
    setBusy(false);
    setStatus('');
    setError('');
    close();
    onSelectSequence(match);
  };

  async function submit() {
    request.current?.abort();
    setBusy(false);
    setStatus('');
    setError('');
    if (positionError) { close(); setError(positionError); return; }
    if (highlighted) { select(highlighted); return; }
    if (point) { close(); onLocate(point); return; }
    if (matches.length === 1) { select(matches[0]); return; }
    if (matches.length > 1) {
      setOpen(true);
      setStatus('Choose a matching sequence.');
      return;
    }
    close();
    if (!live) { setStatus('No saved sequence matched. Other names require the live API.'); return; }
    const abort = new AbortController();
    request.current = abort;
    setBusy(true);
    try {
      const result = await client.resolveName(query.trim(), abort.signal);
      if (!abort.signal.aborted) onLocate(result, result.resolved_name, result.source);
    } catch (e) {
      if (!abort.signal.aborted) {
        setError(e instanceof ApiError && e.status === 404 ? 'Object name not found. Try another name or enter RA and Dec.'
          : 'Name lookup is unavailable. Try again or enter RA and Dec.');
      }
    } finally {
      if (!abort.signal.aborted) setBusy(false);
    }
  }

  return <section className="sx-search" aria-label="Sky search">
    <form className="sx-form" role="search" onSubmit={(event) => { event.preventDefault(); void submit(); }}>
      <input ref={input} type="search" role="combobox" aria-label="Search the sky" aria-autocomplete="list"
        aria-expanded={showMatches} aria-controls={showMatches ? listId : undefined}
        aria-activedescendant={highlighted ? optionId(active) : undefined}
        value={query} maxLength={120} autoComplete="off" placeholder="Name or RA Dec"
        onFocus={() => { if (query.trim()) setOpen(true); }}
        onBlur={close}
        onChange={(event) => {
          request.current?.abort();
          setQuery(event.target.value);
          setOpen(true);
          setActive(-1);
          setBusy(false);
          setError('');
          setStatus('');
        }}
        onKeyDown={(event) => {
          if (event.key === 'Escape' && (open || status || error || busy)) {
            event.preventDefault();
            event.stopPropagation();
            request.current?.abort();
            setBusy(false);
            close();
            setStatus('');
            setError('');
          } else if ((event.key === 'ArrowDown' || event.key === 'ArrowUp') && matches.length) {
            event.preventDefault();
            setOpen(true);
            const step = event.key === 'ArrowDown' ? 1 : -1;
            setActive((index) => {
              const noSelection = index < 0 || index >= matches.length;
              return noSelection ? (step > 0 ? 0 : matches.length - 1) : (index + step + matches.length) % matches.length;
            });
          }
        }} />
      <button type="submit" className="primary-action" disabled={!query.trim() || busy}>Search</button>
    </form>
    {(showMatches || error || status || busy) && <div className="sx-popover">
      {error && <p className="error small" role="alert">{error}</p>}
      {(status || busy) && <p className="small" role="status">{status || 'Looking up the object name…'}</p>}
      {showMatches && <ul className="sx-results" id={listId} role="listbox" aria-label="Matching sequences">
        {matches.map((sequence, index) => {
          const { field, href } = sequence;
          return <li key={href} id={optionId(index)} role="option" aria-selected={index === active}
            onMouseDown={(event) => event.preventDefault()} onClick={() => select(sequence)}>
            <span>{field.id.startsWith('job-') ? 'SPHEREx sequence' : field.name} <SyntheticBadge synthetic={field.synthetic} /></span>
            <span className="muted small">{formatRaDec(field.center.ra, field.center.dec)} · {field.n_frames} frames</span>
          </li>;
        })}
      </ul>}
    </div>}
  </section>;
}
