import { useEffect, useMemo, useState } from 'react';
import { client } from '../api/client';
import type { Candidate, Field, KnownObject } from '../api/types';
import { DETECTOR_BANDS } from '../api/format';
import { BlinkViewer } from '../components/BlinkViewer';
import type { BlinkMode } from '../components/blinkModes';
import { BLINK_MODES, compositesForMode, isModeAvailable, modeTitle } from '../components/blinkModes';
import { CandidateList } from '../components/CandidateList';
import { CandidatePanel } from '../components/CandidatePanel';
import { SkyMap } from '../components/SkyMap';
import { SyntheticBadge } from '../components/SyntheticBadge';

export function FieldPage({ fieldId }: { fieldId: string }) {
  const [field, setField] = useState<Field | null>(null);
  const [candidates, setCandidates] = useState<Candidate[]>([]);
  const [known, setKnown] = useState<KnownObject[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [detector, setDetector] = useState<number | 'all'>('all');
  const [mode, setMode] = useState<BlinkMode>('bw');
  const [systemId, setSystemId] = useState<string | null>(null);

  useEffect(() => {
    setField(null);
    setError(null);
    Promise.all([client.getField(fieldId), client.getCandidates(fieldId), client.getKnown(fieldId)])
      .then(([f, c, k]) => {
        setField(f);
        setCandidates(c.candidates);
        setKnown(k.objects);
      })
      .catch((e: Error) => setError(e.message));
    // WS7: is there a 3D model of the objects in this field?
    client
      .getManifest()
      .then((m) => setSystemId((m.systems ?? []).find((s) => s.field_id === fieldId)?.id ?? null))
      .catch(() => setSystemId(null));
  }, [fieldId]);

  const frames = useMemo(() => {
    const all = [...(field?.frames ?? [])].sort((a, b) => a.mjd - b.mjd);
    return detector === 'all' ? all : all.filter((f) => f.detector === detector);
  }, [field, detector]);
  const composites = useMemo(
    () => (mode === 'bw' ? null : compositesForMode(field?.composites, mode)),
    [field, mode],
  );
  const detectors = useMemo(() => [...new Set(field?.frames.map((f) => f.detector))].sort(), [field]);
  const selected = candidates.find((c) => c.id === selectedId) ?? null;

  if (error) return <main className="error">Could not load field "{fieldId}": {error}</main>;
  if (!field) return <main className="muted">Loading…</main>;

  return (
    <main>
      <p>
        <a href="#/">← All fields</a>
      </p>
      <h1>
        {field.name} <SyntheticBadge synthetic={field.provenance.synthetic} />
      </h1>
      <p className="muted">{field.description}</p>
      {systemId && (
        <p>
          <a href={`#/system/${systemId}`}>Explore these objects in 3D →</a>
        </p>
      )}

      <div className="field-layout">
        <section>
          <div className="toolbar">
            <div className="segmented" role="group" aria-label="Image mode">
              {BLINK_MODES.map(({ mode: m, label }) => (
                <button
                  key={m}
                  type="button"
                  aria-pressed={mode === m}
                  disabled={!isModeAvailable(m, field.composites)}
                  title={modeTitle(m, field.composites)}
                  onClick={() => setMode(m)}
                >
                  {label}
                </button>
              ))}
            </div>
            <label title={mode === 'bw' ? undefined : 'The detector filter applies to the B/W frames only'}>
              Detector{' '}
              <select
                value={String(detector)}
                disabled={mode !== 'bw'}
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
            <span className="muted small">Space = play/pause · ←/→ = step</span>
          </div>
          <BlinkViewer
            field={field}
            frames={frames}
            composites={composites}
            imageUrl={(image) => client.fieldFileUrl(field.id, image)}
            candidates={candidates}
            known={known}
            selectedId={selectedId}
            onSelect={setSelectedId}
          />
          <SkyMap field={field} />
        </section>
        <aside>
          <h2>What moved?</h2>
          <CandidateList candidates={candidates} selectedId={selectedId} onSelect={setSelectedId} />
          {selected && <CandidatePanel candidate={selected} />}
          <p className="legend small">
            <span className="dot known" /> known object <span className="dot unconfirmed" /> unconfirmed{' '}
            <span className="dot artifact" /> artifact <span className="sq" /> catalog prediction
          </p>
        </aside>
      </div>
    </main>
  );
}
