// 3D tab of the selected sky position when no curated system covers it (V14, WS7-11): a catalog model of the object
// the object card (GET /api/object) identifies there, built in the browser by contextSystem.ts. Live API only.
import { useEffect, useState, type CSSProperties, type MouseEvent } from 'react';
import { client } from '../api/client';
import { describeObjectError, lookupKey, matchSummary, positionLookup, type ObjectLookup } from '../api/objectCard';
import type { ObjectContextResponse, SkyCoord } from '../api/types';
import { BodyPanel } from '../components/BodyPanel';
import { ErrorBoundary } from '../components/ErrorBoundary';
import { SystemViewer } from '../components/SystemViewer';
import type { ContextSystemResult } from './contextSystem';

// The model builder loads on demand (only when the 3D tab opens in live mode), so the main chunk stays light;
// a failed download is retried on the next lookup.
type ContextModule = typeof import('./contextSystem');
let contextModule: Promise<ContextModule> | null = null;
function loadContextModule(): Promise<ContextModule> {
  contextModule ??= import('./contextSystem').catch((e: unknown) => {
    contextModule = null;
    throw e;
  });
  return contextModule;
}

/** Shown in static mode, exactly as the position panel said before V14. */
export const STATIC_MESSAGE = 'No catalog model is available for this position in the current dataset.';
export const STATIC_HINT = 'A catalog 3D model of any object needs the live API (it is built from the object card).';
export const CATALOG_BADGE = 'CATALOG MODEL · built from the object card';

// Same guard as the object card: the backend answers within its own deadline (< 30 s), this only catches a hung network.
const CLIENT_TIMEOUT_MS = 45_000;

// Inline styles: styles.css belongs to WS5.
const BADGE: CSSProperties = { background: 'rgba(124, 196, 255, 0.1)', color: '#a9d9ff', border: '1px solid rgba(124, 196, 255, 0.35)' };
const NOTES: CSSProperties = { display: 'grid', gap: 4, paddingLeft: 18, margin: '8px 0 0' };

interface Props {
  position: SkyCoord;
  /** The object card's own lookup (a name search stays a NAME lookup, so the 3D and the card describe the same
   *  object). Without it the 3D looks up `position`. SkyExplorer passes it through PositionResults. */
  lookup?: ObjectLookup | null;
}

export function ObjectSystemPreview({ position, lookup }: Props) {
  if (client.config.mode !== 'api') {
    return <>
      <p className="muted">{STATIC_MESSAGE}</p>
      <p className="muted small">{STATIC_HINT}</p>
    </>;
  }
  return <LiveObjectSystem position={position} lookup={lookup ?? null} />;
}

type Load =
  | { state: 'loading' }
  | { state: 'error'; message: string }
  | { state: 'ready'; ctx: ObjectContextResponse; result: ContextSystemResult };

function LiveObjectSystem({ position, lookup: given }: { position: SkyCoord; lookup: ObjectLookup | null }) {
  const lookup = given ?? positionLookup(position.ra, position.dec);
  const key = lookupKey(lookup);
  const [load, setLoad] = useState<Load>({ state: 'loading' });
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0); // the Retry button

  useEffect(() => {
    setSelectedId(null);
    if (!lookup) {
      setLoad({ state: 'error', message: 'This position is outside the valid RA/Dec range.' });
      return;
    }
    const ctrl = new AbortController();
    const timer = setTimeout(() => ctrl.abort(new DOMException('Catalog context timed out', 'TimeoutError')), CLIENT_TIMEOUT_MS);
    const timedOut = () => ctrl.signal.reason instanceof DOMException && ctrl.signal.reason.name === 'TimeoutError';
    setLoad({ state: 'loading' });
    const code = loadContextModule();
    client.getObjectContext(lookup, ctrl.signal).then(
      (ctx) => {
        clearTimeout(timer); // the card arrived: the timeout no longer applies
        return code.then(
          (m) => {
            if (ctrl.signal.aborted) return;
            try {
              setLoad({ state: 'ready', ctx, result: m.systemFromObjectContext(ctx, position) });
            } catch (e) {
              // A catalog answer the builder cannot read is a gap in this view, never "no object here".
              setLoad({ state: 'error', message: `the catalog model could not be built from this answer (${e instanceof Error ? e.message : String(e)}).` });
            }
          },
          (e: unknown) => {
            if (!ctrl.signal.aborted) {
              setLoad({ state: 'error', message: `the 3D model code could not be downloaded (${e instanceof Error ? e.message : String(e)}).` });
            }
          },
        );
      },
      (e: unknown) => {
        if (ctrl.signal.aborted && !timedOut()) return; // superseded by a newer lookup
        setLoad({ state: 'error', message: describeObjectError(timedOut() ? ctrl.signal.reason : e) });
      },
    ).finally(() => clearTimeout(timer));
    return () => { clearTimeout(timer); ctrl.abort(); };
    // `key` stands for `lookup` and `position` (new objects every render); `attempt` is the Retry button.
  }, [key, attempt]);

  if (load.state === 'loading') return <p className="muted" role="status">Looking up the object card for a catalog 3D model…</p>;
  if (load.state === 'error') {
    return <p className="error" role="alert">
      Could not build a catalog 3D model: {load.message} This is a gap in the lookup, not a sign that nothing is here.{' '}
      <button className="link-button" type="button" onClick={() => setAttempt((n) => n + 1)}>Retry</button>
    </p>;
  }
  const { ctx, result } = load;

  const id = ctx.identity;
  const match = matchSummary(ctx);
  const identity = <p className="muted small">
    {id.display_name ?? id.main_id ?? 'No identified object'}
    {id.object_type && ` · ${id.object_type_label ?? id.object_type} (SIMBAD ${id.object_type})`}
    {` · ${match.label}`}{id.identity_uncertain ? ' · identity uncertain' : ''}
  </p>;

  if (!result.system) {
    return <>
      {identity}
      <p className="muted">No 3D model for this position. {result.reason}</p>
    </>;
  }
  const system = result.system;
  const body = system.bodies.find((b) => b.id === selectedId) ?? system.bodies[0];
  // BodyPanel links other bodies to #/system/<id>/<body>, a page that does not exist for a model built here:
  // select the body in this view instead.
  const prefix = `#/system/${system.id}/`;
  const onPanelClick = (e: MouseEvent<HTMLDivElement>) => {
    const href = (e.target as Element | null)?.closest?.('a')?.getAttribute('href') ?? '';
    if (href.startsWith(prefix)) {
      e.preventDefault();
      setSelectedId(href.slice(prefix.length));
    }
  };

  return <>
    <h3>{system.name}{' '}<span className="badge" style={BADGE}>{CATALOG_BADGE}</span></h3>
    {identity}
    <p className="muted small">{system.representation_note}</p>
    <ErrorBoundary what="The 3D view">
      <SystemViewer key={system.id} system={system} selectedId={selectedId} onSelect={setSelectedId} fieldExists={false} />
    </ErrorBoundary>
    {system.bodies.length > 1 && <p className="small" role="group" aria-label="Bodies in this model">
      {system.bodies.map((b) => <button key={b.id} type="button" aria-pressed={b.id === body.id}
        onClick={() => setSelectedId(b.id)} style={{ marginRight: 6, marginBottom: 4 }}>{b.name}</button>)}
    </p>}
    <div onClickCapture={onPanelClick}>
      <BodyPanel system={system} body={body} fieldExists={false} />
    </div>
    <ul className="notes muted small" style={NOTES} aria-label="Model notes">
      {system.provenance.notes.map((n, i) => <li key={i}>{n}</li>)}
    </ul>
  </>;
}
