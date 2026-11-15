// Reusable SPHEREx sequence player (FE-6): image mode + detector bar, BlinkViewer and an Expand (theater) mode
// that Esc closes. FieldPage hands it the data it already loaded; on its own (`<SequencePlayer fieldId compact />`,
// e.g. a dock tab) it loads the field, its candidates and known objects, and the WS7 catalog prediction itself.
import { useEffect, useMemo, useRef, useState } from 'react';
import { client } from '../api/client';
import { DETECTOR_BANDS } from '../api/format';
import type { Candidate, Field, KnownObject } from '../api/types';
import { trackAstrometry, type TrackAstrometry } from '../three/skyTrack';
import { BlinkViewer } from './BlinkViewer';
import type { BlinkMode } from './blinkModes';
import { BLINK_MODES, compositesForMode, effectiveMode, isModeAvailable, modeHints, modeTitle } from './blinkModes';
import { Skeleton } from './Skeleton';
import '../styles/field.css';

export interface FieldSequence {
  id: string;
  field: Field | null;
  candidates: Candidate[];
  known: KnownObject[];
  error: string | null;
}

/** The field, its candidates and its known objects (one request each). `null` while loading or when no id. */
export function useFieldSequence(fieldId: string | null): FieldSequence | null {
  const [state, setState] = useState<FieldSequence | null>(null);
  useEffect(() => {
    if (!fieldId) return;
    let current = true;
    Promise.all([client.getField(fieldId), client.getCandidates(fieldId), client.getKnown(fieldId)])
      .then(([f, c, k]) => {
        if (current) setState({ id: fieldId, field: f, candidates: c.candidates, known: k.objects, error: null });
      })
      .catch((e: Error) => {
        if (current) setState({ id: fieldId, field: null, candidates: [], known: [], error: e.message });
      });
    return () => { current = false; };
  }, [fieldId]);
  return state && state.id === fieldId ? state : null;
}

/**
 * WS7 catalog prediction wiring (#99/#96), unchanged: the field's 3D system from the manifest, then
 * client.getSystem → trackAstrometry → BlinkViewer's `prediction`. Never from a synthetic model, and only when the
 * system belongs to this field. `null` turns it off (a container that passes its own prediction).
 */
export function useCatalogPrediction(fieldId: string | null): { systemId: string | null; prediction: TrackAstrometry | null } {
  const [systemId, setSystemId] = useState<string | null>(null);
  const [prediction, setPrediction] = useState<TrackAstrometry | null>(null);

  useEffect(() => {
    setSystemId(null);
    if (!fieldId) return;
    let current = true;
    // Both display modes can use the associated system for the blink prediction.
    client.getManifest().then((m) => {
      if (current) setSystemId((m.systems ?? []).find((s) => s.field_id === fieldId)?.id ?? null);
    }).catch(() => { /* The field and science panels remain available. */ });
    return () => { current = false; };
  }, [fieldId]);

  // Every field with a 3D system gets the catalog prediction (WS7: the five targets, e.g. eps Ind B's own
  // Gaia solution and WISE 0855's Kirkpatrick 2021 one, from skyTrack.ts), not only Barnard's Star.
  useEffect(() => {
    setPrediction(null);
    if (!systemId || !fieldId) return;
    let active = true;
    client.getSystem(systemId).then((system) => {
      if (active && system.id === systemId && system.field_id === fieldId && !system.provenance.synthetic) {
        setPrediction(trackAstrometry(system));
      }
    }).catch(() => { /* The image sequence still works if the catalog model is unavailable. */ });
    return () => { active = false; };
  }, [fieldId, systemId]);

  return { systemId, prediction };
}

interface Props {
  fieldId: string;
  /** Narrow containers (dock): no keyboard help line. */
  compact?: boolean;
  /** Data a container already loaded (FieldPage), so the player does not request it twice. */
  field?: Field;
  candidates?: Candidate[];
  known?: KnownObject[];
  prediction?: TrackAstrometry | null;
  selectedId?: string | null;
  onSelect?: (id: string | null) => void;
}

export function SequencePlayer({ fieldId, compact = false, field: given, candidates, known, prediction, selectedId, onSelect }: Props) {
  const own = useFieldSequence(given ? null : fieldId);
  const ownPrediction = useCatalogPrediction(given ? null : fieldId).prediction;
  const [ownSelected, setOwnSelected] = useState<string | null>(null);

  if (!given && own?.error) {
    return <p className="error" role="alert">Could not load field "{fieldId}": {own.error}</p>;
  }
  const field = given ?? own?.field ?? null;
  if (!field) return <Skeleton label="Loading sequence" lines={4} />;
  return <PlayerView
    key={field.id}
    field={field}
    candidates={candidates ?? own?.candidates ?? []}
    known={known ?? own?.known ?? []}
    prediction={given ? prediction ?? null : ownPrediction}
    selectedId={onSelect ? selectedId ?? null : ownSelected}
    onSelect={onSelect ?? setOwnSelected}
    compact={compact}
  />;
}

/** Makes everything outside `el` inert, up to <body> (no Tab, clicks or focus() behind a modal); returns the undo. */
function inertOutside(el: HTMLElement): () => void {
  const changed: HTMLElement[] = [];
  for (let node: HTMLElement = el; node.parentElement && node !== document.body; node = node.parentElement) {
    for (const sibling of Array.from(node.parentElement.children)) {
      if (sibling !== node && sibling instanceof HTMLElement && !sibling.inert) {
        sibling.inert = true;
        changed.push(sibling);
      }
    }
  }
  return () => { for (const sibling of changed) sibling.inert = false; };
}

function PlayerView({ field, candidates, known, prediction, selectedId, onSelect, compact }: {
  field: Field;
  candidates: Candidate[];
  known: KnownObject[];
  prediction: TrackAstrometry | null;
  selectedId: string | null;
  onSelect: (id: string | null) => void;
  compact: boolean;
}) {
  const [detector, setDetector] = useState<number | 'all'>('all');
  const [mode, setMode] = useState<BlinkMode>('bw');
  const [theater, setTheater] = useState(false);
  const playerRef = useRef<HTMLDivElement>(null);
  const expandRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    const player = playerRef.current;
    if (!theater || !player) return;
    let live = true;
    let seen: KeyboardEvent | null = null;
    const close = () => { if (live) setTheater(false); };
    // Esc order (plan FE-11): popup > theater > sheet. Whatever sits above the theater consumes Esc with
    // preventDefault() and the theater leaves it alone; when the theater closes, it consumes the Esc too.
    const onKey = (e: KeyboardEvent) => {
      seen = e;
      if (e.key !== 'Escape' || e.defaultPrevented) return;
      e.preventDefault();
      close();
    };
    // Some children stop key events from bubbling (WS7's "Source and method" <details> in BlinkViewer), so an Esc
    // may never reach window: the capture listener checks after the dispatch whether nobody saw or consumed it.
    const onKeyCapture = (e: KeyboardEvent) => {
      if (e.key !== 'Escape' || e.defaultPrevented) return;
      setTimeout(() => { if (seen !== e && !e.defaultPrevented) close(); });
    };
    window.addEventListener('keydown', onKeyCapture, true);
    window.addEventListener('keydown', onKey);
    // A real modal: the page under the overlay is inert (no Tab into covered controls, no `/` search focus).
    const restore = inertOutside(player);
    expandRef.current?.focus({ preventScroll: true });
    return () => {
      live = false;
      window.removeEventListener('keydown', onKeyCapture, true);
      window.removeEventListener('keydown', onKey);
      restore();
    };
  }, [theater]);

  const frames = useMemo(() => {
    const all = [...field.frames].sort((a, b) => a.mjd - b.mjd);
    return detector === 'all' ? all : all.filter((f) => f.detector === detector);
  }, [field, detector]);
  // A mode the current field has no composites for (e.g. after switching fields) shows B/W.
  const shownMode = effectiveMode(mode, field.composites);
  const composites = useMemo(
    () => (shownMode === 'bw' ? null : compositesForMode(field.composites, shownMode)),
    [field, shownMode],
  );
  const detectors = useMemo(() => [...new Set(field.frames.map((f) => f.detector))].sort(), [field]);

  return (
    <div
      ref={playerRef}
      className={`fd-player${compact ? ' fd-player--compact' : ''}${theater ? ' fd-theater' : ''}`}
      role={theater ? 'dialog' : undefined}
      aria-modal={theater || undefined}
      aria-label={theater ? `${field.name} · expanded sequence player` : undefined}
    >
      <div className="fd-player-bar">
        <div className="fd-seg" role="group" aria-label="Image mode">
          {BLINK_MODES.map(({ mode: m, label }) => (
            <button
              key={m}
              type="button"
              aria-pressed={shownMode === m}
              disabled={!isModeAvailable(m, field.composites)}
              title={modeTitle(m, field.composites)}
              onClick={() => setMode(m)}
            >
              {label}
            </button>
          ))}
        </div>
        <button
          ref={expandRef}
          type="button"
          className="u-btn fd-expand"
          onClick={() => setTheater((on) => !on)}
          title={theater ? 'Close the expanded player (Esc)' : 'Expand the player to the whole window'}
        >
          {theater ? 'Close · Esc' : 'Expand'}
        </button>
      </div>
      <div className="fd-stage">
        <BlinkViewer
          key={`${field.id}/${detector}/${shownMode}`}
          field={field}
          frames={frames}
          composites={composites}
          imageUrl={(image) => client.fieldFileUrl(field.id, image)}
          candidates={candidates}
          known={known}
          prediction={!field.provenance.synthetic ? prediction : null}
          selectedId={selectedId}
          onSelect={onSelect}
        />
      </div>
      <div className="fd-player-foot">
        <label className="fd-detector" title={shownMode === 'bw' ? undefined : 'The detector filter applies to the B/W frames only'}>
          Detector
          <select
            value={String(detector)}
            disabled={shownMode !== 'bw'}
            onChange={(e) => setDetector(e.target.value === 'all' ? 'all' : Number(e.target.value))}
          >
            <option value="all">all ({field.frames.length} frames)</option>
            {detectors.map((d) => (
              <option key={d} value={d}>
                D{d} · {DETECTOR_BANDS[d]}
              </option>
            ))}
          </select>
        </label>
        {!compact && <span className="muted small">Space = play/pause · ←/→ = step · Esc closes Expand</span>}
      </div>
      <p className="fd-hint muted small" aria-live="polite">
        {modeHints(mode, field.composites).join(' ')}
      </p>
    </div>
  );
}
