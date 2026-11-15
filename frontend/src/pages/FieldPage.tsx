import { useEffect, useMemo, useState } from 'react';
import { client } from '../api/client';
import type { Candidate, Field, KnownObject } from '../api/types';
import { DETECTOR_BANDS, formatRaDec } from '../api/format';
import { BlinkViewer } from '../components/BlinkViewer';
import type { BlinkMode } from '../components/blinkModes';
import { BLINK_MODES, compositesForMode, effectiveMode, isModeAvailable, modeHints, modeTitle } from '../components/blinkModes';
import { CandidateList } from '../components/CandidateList';
import { CandidatePanel } from '../components/CandidatePanel';
import { SkyMap } from '../components/SkyMap';
import { SyntheticBadge } from '../components/SyntheticBadge';
import { FieldComparisons } from '../components/FieldComparisons';
import { PositionSpectrum } from '../components/PositionSpectrum';
import { LightCurvePanel } from '../components/LightCurvePanel';
import { trackAstrometry, type TrackAstrometry } from '../three/skyTrack';

const BARNARD_FIELD_ID = 'barnards-star';

export function FieldPage({ fieldId, embedded = false }: { fieldId: string; embedded?: boolean }) {
  const [field, setField] = useState<Field | null>(null);
  const [candidates, setCandidates] = useState<Candidate[]>([]);
  const [known, setKnown] = useState<KnownObject[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [detector, setDetector] = useState<number | 'all'>('all');
  const [mode, setMode] = useState<BlinkMode>('bw');
  const [systemId, setSystemId] = useState<string | null>(null);
  const [prediction, setPrediction] = useState<TrackAstrometry | null>(null);

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

  useEffect(() => {
    if (fieldId !== BARNARD_FIELD_ID) return;
    let active = true;
    client.getSystem(BARNARD_FIELD_ID).then((system) => {
      if (active && system.id === BARNARD_FIELD_ID && system.field_id === fieldId && !system.provenance.synthetic) {
        setPrediction(trackAstrometry(system));
      }
    }).catch(() => { /* The image sequence still works if the catalog model is unavailable. */ });
    return () => { active = false; };
  }, [fieldId]);

  const frames = useMemo(() => {
    const all = [...(field?.frames ?? [])].sort((a, b) => a.mjd - b.mjd);
    return detector === 'all' ? all : all.filter((f) => f.detector === detector);
  }, [field, detector]);
  // A mode the current field has no composites for (e.g. after switching fields) shows B/W.
  const shownMode = effectiveMode(mode, field?.composites);
  const composites = useMemo(
    () => (shownMode === 'bw' ? null : compositesForMode(field?.composites, shownMode)),
    [field, shownMode],
  );
  const detectors = useMemo(() => [...new Set(field?.frames.map((f) => f.detector))].sort(), [field]);
  const selected = candidates.find((c) => c.id === selectedId) ?? null;

  const Container = embedded ? 'section' : 'main';
  if (error) return <Container className="error">Could not load field "{fieldId}": {error}</Container>;
  if (!field) return <Container className="muted">Loading sequence…</Container>;

  return (
    <Container>
      {!embedded && <p>
        <a href="#/">← All fields</a>
      </p>}
      <h2 className="field-title">
        {field.id.startsWith('job-') ? `SPHEREx at ${formatRaDec(field.center.ra, field.center.dec)}` : field.name}
        {' '}<SyntheticBadge synthetic={field.provenance.synthetic} />
      </h2>
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
                  aria-pressed={shownMode === m}
                  disabled={!isModeAvailable(m, field.composites)}
                  title={modeTitle(m, field.composites)}
                  onClick={() => setMode(m)}
                >
                  {label}
                </button>
              ))}
            </div>
            <label title={shownMode === 'bw' ? undefined : 'The detector filter applies to the B/W frames only'}>
              Detector{' '}
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
            <span className="muted small">Space = play/pause · ←/→ = step</span>
          </div>
          <p className="mode-hint muted small" aria-live="polite">
            {modeHints(mode, field.composites).join(' ')}
          </p>
          <BlinkViewer
            key={`${field.id}/${detector}/${shownMode}`}
            field={field}
            frames={frames}
            composites={composites}
            imageUrl={(image) => client.fieldFileUrl(field.id, image)}
            candidates={candidates}
            known={known}
            prediction={field.id === BARNARD_FIELD_ID && !field.provenance.synthetic ? prediction : null}
            selectedId={selectedId}
            onSelect={setSelectedId}
          />
          {!embedded && <SkyMap field={field} />}
        </section>
        <aside>
          <h2>Evidence and provenance</h2>
          {candidates.length > 0 ? <CandidateList candidates={candidates} selectedId={selectedId} onSelect={setSelectedId} /> :
            <p className="muted">No candidate measurements provided. This is not a negative detection result.</p>}
          {field.provenance.notes.map((note, index) => <p className="small muted" key={index}>{note}</p>)}
          <p className="small muted">Spectra below are extracted independently from FITS; a physical 3D model still requires measured constraints.</p>
          {selected && <CandidatePanel candidate={selected} />}
          <p className="legend small">
            <span className="dot known" /> known object <span className="dot unconfirmed" /> unconfirmed{' '}
            <span className="dot artifact" /> artifact <span className="sq" /> catalog prediction
          </p>
        </aside>
      </div>
      {!field.provenance.synthetic && !embedded && <PositionSpectrum position={field.center} fieldId={field.id} />}
      {!field.provenance.synthetic && !field.id.startsWith('job-') &&
        <LightCurvePanel key={field.id} targetId={field.id} />}
      <FieldComparisons field={field} />
    </Container>
  );
}
