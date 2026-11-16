// 3D tab of the selected sky position when no curated system covers it (V14, WS7-11): a catalog model of the object
// the object card (GET /api/object) identifies there, built in the browser by contextSystem.ts. Live API only.
import { useEffect, useState, type MouseEvent } from 'react';
import { client } from '../api/client';
import { describeObjectError, lookupKey, matchSummary, positionLookup, type ObjectLookup } from '../api/objectCard';
import { getObjectContextCached } from '../api/objectCardCache';
import type { ObjectContextResponse, SkyCoord } from '../api/types';
import { BodyPanel } from '../components/BodyPanel';
import { ErrorBoundary } from '../components/ErrorBoundary';
import { SystemViewer } from '../components/SystemViewer';
import type { ContextSystemResult } from './contextSystem';
import './system.css';

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

// Styles: three/system.css (.s3d-).

interface Props {
  position: SkyCoord;
  /** The object card's own lookup (a name search stays a NAME lookup, so the 3D and the card describe the same
   *  object). Without it the 3D looks up `position`. SkyExplorer passes it through PositionResults. */
  lookup?: ObjectLookup | null;
  /**
   * Dock / tab size (FE-12): compact viewer (<= 320 px stage), the body panel reduced to its key data with the
   * full panel behind a disclosure, and the model notes collapsed. The catalog badge, the 3D MODEL chip and the
   * representation note stay visible. Default false.
   */
  compact?: boolean;
}

export function ObjectSystemPreview({ position, lookup, compact = false }: Props) {
  if (client.config.mode !== 'api') {
    return <>
      <p className="muted">{STATIC_MESSAGE}</p>
      <p className="muted small">{STATIC_HINT}</p>
    </>;
  }
  return <LiveObjectSystem position={position} lookup={lookup ?? null} compact={compact} />;
}

type Load =
  | { state: 'loading' }
  | { state: 'error'; message: string }
  | { state: 'ready'; ctx: ObjectContextResponse; result: ContextSystemResult };

function LiveObjectSystem({ position, lookup: given, compact }: { position: SkyCoord; lookup: ObjectLookup | null; compact: boolean }) {
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
    // Through FE-5's session cache (api/objectCardCache.ts): the card's answer for the same lookup, or its request
    // in flight, is reused instead of a second GET /api/object. Aborting `ctrl` (timeout, new lookup, unmount) only
    // stops this wait: the shared request lives on while the card still waits for it, and errors and partial
    // answers are never cached, so a timeout here leaves nothing behind for the card and Retry asks again.
    getObjectContextCached(lookup, ctrl.signal).then(
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
  return <ObjectModelView ctx={load.ctx} result={load.result} selectedId={selectedId} onSelect={setSelectedId} compact={compact} />;
}

export interface ObjectModelViewProps {
  ctx: ObjectContextResponse;
  result: ContextSystemResult;
  selectedId: string | null;
  onSelect: (bodyId: string | null) => void;
  compact?: boolean;
}

/** The catalog model once the object card has answered (exported for the SSR tests). */
export function ObjectModelView({ ctx, result, selectedId, onSelect, compact = false }: ObjectModelViewProps) {
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
  const unverified = system.bodies.some((b) => b.facts.some((f) => !f.verified));
  // BodyPanel links other bodies to #/system/<id>/<body>, a page that does not exist for a model built here:
  // select the body in this view instead.
  const prefix = `#/system/${system.id}/`;
  const onPanelClick = (e: MouseEvent<HTMLDivElement>) => {
    const href = (e.target as Element | null)?.closest?.('a')?.getAttribute('href') ?? '';
    if (href.startsWith(prefix)) {
      e.preventDefault();
      onSelect(href.slice(prefix.length));
    }
  };
  const notes = <ul className="notes muted small s3d-model-notes" aria-label="Model notes">
    {system.provenance.notes.map((n, i) => <li key={i}>{n}</li>)}
  </ul>;

  return <div className={`s3d-preview${compact ? ' s3d-preview--compact' : ''}`}>
    <h3 className="s3d-preview-title">{system.name}{' '}
      <span className="badge u-badge u-badge--catalog">{CATALOG_BADGE}</span>
      {/* Compact: the stage chip already says it, and the dock has no room for a second line of badges. */}
      {!compact && <>{' '}<span className="badge u-badge u-badge--model">3D MODEL · NOT AN IMAGE</span></>}
      {unverified && <>{' '}<span className="badge u-badge u-badge--warn" title="Some values are estimates that no catalog or paper states">UNVERIFIED VALUES</span></>}
    </h3>
    {identity}
    <p className="muted small s3d-note">{system.representation_note}</p>
    <ErrorBoundary what="The 3D view">
      <SystemViewer key={system.id} system={system} selectedId={selectedId} onSelect={onSelect} fieldExists={false} compact={compact} />
    </ErrorBoundary>
    {system.bodies.length > 1 && <p className="small s3d-bodies" role="group" aria-label="Bodies in this model">
      {system.bodies.map((b) => <button key={b.id} type="button" className="u-chip" aria-pressed={b.id === body.id}
        onClick={() => onSelect(b.id)}>{b.name}</button>)}
    </p>}
    <div onClickCapture={onPanelClick}>
      <BodyPanel system={system} body={body} fieldExists={false} compact={compact} />
    </div>
    {compact
      ? system.provenance.notes.length > 0 && <details className="s3d-disclosure">
        <summary>Model notes ({system.provenance.notes.length})</summary>{notes}
      </details>
      : notes}
  </div>;
}
