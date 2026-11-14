import { useEffect, useMemo, useState } from 'react';
import { client } from '../api/client';
import type { Candidate, Field, KnownObject } from '../api/types';
import { DETECTOR_BANDS, formatRaDec } from '../api/format';
import { BlinkViewer } from '../components/BlinkViewer';
import { CandidateList } from '../components/CandidateList';
import { CandidatePanel } from '../components/CandidatePanel';
import { SkyMap } from '../components/SkyMap';
import { SyntheticBadge } from '../components/SyntheticBadge';

export function FieldPage({ fieldId, embedded = false }: { fieldId: string; embedded?: boolean }) {
  const [field, setField] = useState<Field | null>(null);
  const [candidates, setCandidates] = useState<Candidate[]>([]);
  const [known, setKnown] = useState<KnownObject[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [detector, setDetector] = useState<number | 'all'>('all');
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
            <label>
              Detector{' '}
              <select
                value={String(detector)}
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
            key={`${field.id}/${detector}`}
            field={field}
            frames={frames}
            imageUrl={(f) => client.frameImageUrl(field.id, f)}
            candidates={candidates}
            known={known}
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
          <p className="small muted">Spectra and physical 3D models require measured fluxes and catalog constraints; they are not inferred from this video.</p>
          {selected && <CandidatePanel candidate={selected} />}
          <p className="legend small">
            <span className="dot known" /> known object <span className="dot unconfirmed" /> unconfirmed{' '}
            <span className="dot artifact" /> artifact <span className="sq" /> catalog prediction
          </p>
        </aside>
      </div>
    </Container>
  );
}
