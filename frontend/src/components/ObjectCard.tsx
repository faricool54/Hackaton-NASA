import { useEffect, useId, useState } from 'react';
import { client } from '../api/client';
import {
  describeObjectError, factRows, identityNotSecure, isEmptySky, keyRows, lookupKey, lookupLabel, matchBadge,
  matchSummary, objectTitle, objectTypeLine, photometryGroups, planetLine, serviceRows, servicesSummary,
  type KeyRow, type ObjectLookup,
} from '../api/objectCard';
import { forgetObjectContext, getObjectContextCached, peekObjectContext } from '../api/objectCardCache';
import type { ObjectContextResponse } from '../api/types';
import { Skeleton } from './Skeleton';
import '../styles/object-card.css';

export type ObjectCardVariant = 'dock' | 'full';

const IDENTITY_ALERT = 'Identity not secure: values matched by position may belong to a neighbouring source.';
const PARTIAL_ALERT = 'Partial: some catalogs did not answer, so their values are unknown (not negative).';

interface CardState { key: string; busy: boolean; data: ObjectContextResponse | null; error: string }

/** Catalog context of the chosen position/name. Independent of the SPHEREx build: it never blocks the job/video.
 *  `dock` is the default because the explorer dock is the only consumer today: it folds the details to fit a
 *  420 px dock. `full` lists every parameter, planet and warning for a page with room. Answers come from the
 *  session cache (objectCardCache.ts): reselecting an object makes no new /api/object request. */
export function ObjectCard({ lookup, variant = 'dock' }: { lookup: ObjectLookup | null; variant?: ObjectCardVariant }) {
  const live = client.config.mode === 'api';
  const key = lookupKey(lookup);
  const [attempt, setAttempt] = useState(0);
  const [state, setState] = useState<CardState>({ key: '', busy: false, data: null, error: '' });
  useEffect(() => {
    if (!lookup || !live) return;
    const abort = new AbortController();
    const cached = peekObjectContext(lookup);
    setState({ key, busy: !cached, data: cached, error: '' });
    getObjectContextCached(lookup, abort.signal)
      .then((data) => { if (!abort.signal.aborted) setState({ key, busy: false, data, error: '' }); })
      .catch((e: unknown) => {
        if (abort.signal.aborted) return; // superseded by a newer lookup (a shared request may live on)
        setState({ key, busy: false, data: null, error: describeObjectError(e) });
      });
    return () => abort.abort();
  }, [key, live, attempt]); // `key` identifies `lookup`; `attempt` is the retry button

  if (!lookup) return null;
  const retry = () => { forgetObjectContext(lookup); setAttempt((n) => n + 1); };
  // Until the effect runs for a new lookup, a cached answer renders at once (no skeleton flash on reselection).
  const cached = state.key === key || !live ? null : peekObjectContext(lookup);
  const current = state.key === key ? state : { key, busy: live && !cached, data: cached, error: '' };
  return <ObjectCardView lookup={lookup} variant={variant} live={live} busy={current.busy} data={current.data}
    error={current.error} onRetry={retry} />;
}

interface ViewProps {
  lookup: ObjectLookup; variant: ObjectCardVariant; live: boolean; busy: boolean;
  data: ObjectContextResponse | null; error: string; onRetry: () => void;
}

/** Stateless rendering of the card (the tests render it directly). */
export function ObjectCardView({ lookup, variant, live, busy, data, error, onRetry }: ViewProps) {
  const titleId = useId();
  const title = data ? objectTitle(data) : lookupLabel(lookup);
  const type = data ? objectTypeLine(data) : '';
  const badge = data ? matchBadge(data) : null;
  return <section className={`oc-card oc-card--${variant}`} aria-labelledby={titleId} aria-busy={busy}>
    <header className="oc-head">
      <div className="oc-title">
        <h3 id={titleId} className="oc-name" title={title}>{title}</h3>
        <span className="badge u-badge u-badge--catalog oc-badge">Catalog · not SPHEREx</span>
      </div>
      {(badge || type) && <p className="oc-sub">
        {badge && <span className={`u-badge oc-match-badge oc-match-badge--${badge.tone}`} title={badge.title}>{badge.label}</span>}
        {type && <span className="oc-type" title={type}>{type}</span>}
      </p>}
    </header>
    <p className="oc-note" title={data?.note}>Catalog context, not SPHEREx measurements.</p>
    {!live && <p className="oc-muted">SIMBAD, Gaia DR3, VSX, exoplanet and 2MASS/AllWISE context needs the live API.</p>}
    {busy && <>
      <Skeleton label="Loading catalog context" lines={4} />
      <p className="oc-muted">Looking up SIMBAD, Gaia DR3, AAVSO VSX, the NASA Exoplanet Archive, 2MASS and AllWISE
        (up to ~30 s). The SPHEREx sequence does not wait for this.</p>
    </>}
    {error && <p className="oc-error" role="alert">{error}{' '}
      <button type="button" className="link-button" onClick={onRetry}>Retry</button></p>}
    {data && <ObjectCardBody data={data} variant={variant} onRetry={onRetry} />}
  </section>;
}

function RowNote({ row, clip }: { row: KeyRow; clip: boolean }) {
  const className = clip ? 'oc-src oc-src--clip' : 'oc-src';
  return row.href
    ? <a className={className} href={row.href} target="_blank" rel="noreferrer" title={row.source}>{row.source}</a>
    : <span className={className} title={row.source}>{row.source}</span>;
}

function ObjectCardBody({ data, variant, onRetry }: { data: ObjectContextResponse; variant: ObjectCardVariant; onRetry: () => void }) {
  const dock = variant === 'dock';
  const match = matchSummary(data);
  const empty = isEmptySky(data);
  const photometry = photometryGroups(data.photometry);
  const services = serviceRows(data.provenance);
  const allFacts = factRows(data.facts);
  const n = data.warnings.length;
  const warnings = <ul className="oc-list oc-warnings">{data.warnings.map((w, i) => <li key={i}>{w}</li>)}</ul>;
  const planets = <ul className="oc-list">{data.planets.map((p) => <li key={p.name}>{planetLine(p)}</li>)}</ul>;
  return <>
    {/* The dock's header badge carries the match label; the callout keeps the explanation. */}
    <p className={`oc-match oc-match--${match.tone}`} role="status">
      {dock ? <span className="u-sr-only">{match.label}. </span> : <><strong>{match.label}.</strong>{' '}</>}{match.detail}</p>
    {/* Both alerts stay visible; the dock words them to fit one line at 420 px (full sentence in `title`). */}
    {identityNotSecure(data) && <p className="oc-alert" title={IDENTITY_ALERT}>
      {dock ? 'Identity not secure: values may belong to a neighbouring source.' : IDENTITY_ALERT}</p>}
    {data.partial && <p className="oc-alert" title={PARTIAL_ALERT}>
      {dock ? 'Partial: some catalogs did not answer (unknown, not negative).' : PARTIAL_ALERT}{' '}
      <button type="button" className="link-button" onClick={onRetry}>Retry</button></p>}
    {empty ? <p className="oc-muted">Nothing is catalogued here in Gaia DR3, AAVSO VSX, 2MASS or AllWISE within
      {' '}{data.query.radius_arcsec}″. SPHEREx may still show emission at this position.</p> : <>
      <dl className="oc-facts" aria-label="Physical parameters from catalogs">
        {keyRows(data, variant).map((row) => <div key={row.label} className="oc-row">
          <dt>{row.label}</dt>
          <dd>
            <span className="oc-value-line">
              <span className={row.unknown ? 'oc-value oc-value--unknown' : 'oc-value'}
                title={row.unknown ? 'Not measured or not found: unknown, not a negative result' : undefined}>{row.value}</span>
              {row.status && !row.unknown &&
                <span className={`oc-status oc-status--${row.status.replace(' ', '-')}`}>{row.status}</span>}
              {/* The dock clips the source note, so a caveat is marked here (full text in `title` and the fold). */}
              {row.caveat && !row.unknown &&
                <span className="oc-status oc-status--caveat" title={`Caveat: ${row.caveat}`}>caveat</span>}
              {dock && row.unknown && <span className="oc-hint">not a negative result</span>}
            </span>
            {row.label === 'Planets' && data.planets.length > 0
              ? dock
                ? <details className="oc-details oc-details--inline">
                  <summary><RowNote row={{ ...row, href: null }} clip={false} /></summary>{planets}
                </details>
                : <><RowNote row={row} clip={false} />{planets}</>
              : <RowNote row={row} clip={dock} />}
          </dd>
        </div>)}
      </dl>
      {data.nearby_planet_hosts.length > 0 && <p className="oc-muted">Nearby planet host, NOT this object:{' '}
        {data.nearby_planet_hosts.map((h) => `${h.hostname} (${Math.round(h.separation_arcsec)}″: ${h.planets.join(', ')})`).join('; ')}</p>}
    </>}
    {!dock && n > 0 && warnings}
    {!dock && <p className="oc-muted">{data.note}</p>}
    <div className="oc-folds">
      {!empty && dock && <details className="oc-details">
        <summary>All {allFacts.length} catalog parameters with sources</summary>
        <ul className="oc-list">{allFacts.map((f) => <li key={f.label}><strong>{f.label}:</strong> {f.value}
          {!f.unknown && ` (${f.status})`}<br /><span className="oc-src">{f.source}</span></li>)}</ul>
      </details>}
      {dock && n > 0 && <details className="oc-details oc-details--warn">
        <summary>{n} catalog warning{n === 1 ? '' : 's'}</summary>{warnings}
      </details>}
      {photometry.length > 0 && <details className="oc-details">
        <summary>Context photometry · other missions (2MASS/AllWISE), not SPHEREx</summary>
        {photometry.map((g) => <div key={g.designation}>
          <p className="oc-mission"><strong>{g.label}</strong> · {g.designation}
            {g.identityUncertain && <span className="oc-tone-warn"> · identity uncertain (may be a neighbour)</span>}</p>
          <ul className="oc-list">{g.rows.map((r) => <li key={r.band}>{r.band} ({r.wavelength}): {r.magnitude}
            {r.flags !== '—' && <span className="oc-muted"> · {r.flags}</span>}</li>)}</ul>
        </div>)}
      </details>}
      <details className="oc-details">
        <summary>Catalog services · {servicesSummary(data.provenance)}</summary>
        {dock && <p className="oc-muted">{data.note}</p>}
        <ul className="oc-list">{services.map((s, i) => <li key={i}><span className={`oc-tone-${s.tone}`}>{s.name}: {s.status}</span>
          <br /><span className="oc-src">{s.detail}</span></li>)}</ul>
      </details>
    </div>
  </>;
}
