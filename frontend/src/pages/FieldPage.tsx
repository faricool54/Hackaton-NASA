// Field page (FE-6): a no-scroll dashboard at #/field/<id> — 44 px title bar, the sequence player on the left and
// the evidence in tabs on the right. `embedded` (the explorer dock's Time tab) keeps the stacked layout.
import { useEffect, useState, type ReactNode } from 'react';
import { client } from '../api/client';
import { formatMjd, formatRaDec } from '../api/format';
import { loadLightCurve } from '../api/lightcurve';
import { nameLookup, positionLookup } from '../api/objectCard';
import { SHOWCASE_TARGETS } from '../api/showcase';
import type { Candidate, Field, LightCurveProduct } from '../api/types';
import { CandidateList } from '../components/CandidateList';
import { CandidatePanel } from '../components/CandidatePanel';
import { FieldComparisons } from '../components/FieldComparisons';
import { LightCurvePanel, LightCurveProductView } from '../components/LightCurvePanel';
import { ObjectCard } from '../components/ObjectCard';
import { PositionSpectrum } from '../components/PositionSpectrum';
import { SequencePlayer, useCatalogPrediction, useFieldSequence } from '../components/SequencePlayer';
import { Skeleton } from '../components/Skeleton';
import { SkyMap } from '../components/SkyMap';
import { SyntheticBadge } from '../components/SyntheticBadge';
import { Tabs } from '../components/Tabs';
import '../styles/field.css';

type CurveProbe = LightCurveProduct | 'missing' | 'error';
type TabId = 'lightcurve' | 'spectrum' | 'seasons' | 'evidence' | 'object';
interface TabItem { id: TabId; label: string; content: ReactNode }

/** Whether a precomputed light curve exists (one GET; 404 → 'missing'). `null` when not asked, 'checking' meanwhile. */
function useLightCurveProbe(targetId: string | null): CurveProbe | 'checking' | null {
  const [state, setState] = useState<{ id: string; value: CurveProbe } | null>(null);
  useEffect(() => {
    if (!targetId) return;
    const abort = new AbortController();
    loadLightCurve(client, targetId, abort.signal)
      .then((value) => { if (!abort.signal.aborted) setState({ id: targetId, value }); })
      .catch(() => { if (!abort.signal.aborted) setState({ id: targetId, value: 'error' }); });
    return () => abort.abort();
  }, [targetId]);
  if (!targetId) return null;
  return state?.id === targetId ? state.value : 'checking';
}

function fieldTitle(field: Field): string {
  return field.id.startsWith('job-') ? `SPHEREx at ${formatRaDec(field.center.ra, field.center.dec)}` : field.name;
}

function Legend() {
  return <p className="legend small">
    <span className="dot known" /> known object <span className="dot unconfirmed" /> unconfirmed{' '}
    <span className="dot artifact" /> artifact <span className="sq" /> catalog prediction
  </p>;
}

function Provenance({ field }: { field: Field }) {
  const { provenance } = field;
  return <details className="fd-provenance small">
    <summary>Provenance · {provenance.notes.length} note{provenance.notes.length === 1 ? '' : 's'}</summary>
    <dl className="u-kv">
      <dt>Pipeline</dt><dd className="u-mono">{provenance.pipeline_version}</dd>
      <dt>Built</dt><dd>{provenance.built_at}</dd>
      <dt>Releases</dt><dd>{provenance.data_releases.join(', ') || 'not reported'}</dd>
    </dl>
    {provenance.notes.map((note, index) => <p className="muted" key={index}>{note}</p>)}
  </details>;
}

function Evidence({ field, candidates, selectedId, onSelect }: {
  field: Field; candidates: Candidate[]; selectedId: string | null; onSelect: (id: string | null) => void;
}) {
  const selected = candidates.find((c) => c.id === selectedId) ?? null;
  return <>
    <CandidateList candidates={candidates} selectedId={selectedId} onSelect={onSelect} />
    {selected && <CandidatePanel candidate={selected} />}
    <Legend />
    <Provenance field={field} />
  </>;
}

export function FieldPage({ fieldId, embedded = false }: { fieldId: string; embedded?: boolean }) {
  const data = useFieldSequence(fieldId);
  // WS7 catalog prediction (systemId → client.getSystem → trackAstrometry → BlinkViewer `prediction`).
  const { systemId, prediction } = useCatalogPrediction(fieldId);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [tab, setTab] = useState<TabId | null>(null);
  const [objectSeen, setObjectSeen] = useState(false);
  const [copied, setCopied] = useState('');
  const field = data?.field ?? null;
  const realCurve = field && !field.provenance.synthetic && !field.id.startsWith('job-') ? field.id : null;
  const curve = useLightCurveProbe(embedded ? null : realCurve);

  useEffect(() => {
    if (!copied) return;
    const timer = setTimeout(() => setCopied(''), 2500);
    return () => clearTimeout(timer);
  }, [copied]);

  const Container = embedded ? 'section' : 'main';
  if (data?.error) {
    return <Container className={embedded ? undefined : 'fd-state'}>
      <p className="error" role="alert">Could not load field "{fieldId}": {data.error}</p>
      {!embedded && <a href="#/">← Explore</a>}
    </Container>;
  }
  if (!field || !data) {
    return <Container className={embedded ? undefined : 'fd-state'}><Skeleton label="Loading sequence" lines={4} /></Container>;
  }

  const { candidates, known } = data;
  const synthetic = field.provenance.synthetic;
  const title = fieldTitle(field);
  const player = <SequencePlayer fieldId={field.id} compact={embedded} field={field} candidates={candidates} known={known}
    prediction={prediction} selectedId={selectedId} onSelect={setSelectedId} />;

  if (embedded) {
    return <section className="fd-embedded">
      <h2 className="field-title">{title} <SyntheticBadge synthetic={synthetic} /></h2>
      <p className="muted">{field.description}</p>
      {player}
      <h2>Evidence and provenance</h2>
      <Evidence field={field} candidates={candidates} selectedId={selectedId} onSelect={setSelectedId} />
      {realCurve && <LightCurvePanel key={field.id} targetId={field.id} />}
      <FieldComparisons field={field} />
    </section>;
  }

  const target = SHOWCASE_TARGETS.find((t) => t.fieldId === field.id);
  const lookup = synthetic ? null
    : target ? nameLookup(target.catalogName) : positionLookup(field.center.ra, field.center.dec);
  const dates = field.frames.map((f) => f.mjd);
  const detectors = [...new Set(field.frames.map((f) => f.detector))].sort();

  const items: TabItem[] = [];
  // The tab appears only once the product is known to exist (or the probe failed and needs a retry), never while
  // checking: a field without a light curve must not show it and then drop it. The probe already holds the product,
  // so the tab renders FE-8's LightCurveProductView directly (visible without a click, no second request).
  if (curve && curve !== 'missing' && curve !== 'checking') {
    items.push({
      id: 'lightcurve', label: 'Light curve', content: curve === 'error' ? <>
        <p className="error small" role="alert">The light curve could not be loaded. Open the panel below to retry.</p>
        <LightCurvePanel key={field.id} targetId={field.id} />
      </>
        : <div className="science-panel fd-science"><LightCurveProductView product={curve} /></div>,
    });
  }
  items.push(
    {
      id: 'spectrum', label: 'Spectrum', content: synthetic
        ? <p className="muted">Spectra are measured only from real SPHEREx exposures; this field is synthetic.</p>
        : <>
          <h3 className="fd-section-title">Spectrum at {formatRaDec(field.center.ra, field.center.dec)}</h3>
          <PositionSpectrum position={field.center} fieldId={field.id} inline />
          <p className="small muted">Spectra are extracted independently from FITS; a physical 3D model still requires measured constraints.</p>
        </>,
    },
    {
      id: 'seasons', label: 'Seasons', content: synthetic
        ? <p className="muted">Season comparisons are rebuilt only from real SPHEREx exposures; this field is synthetic.</p>
        : <FieldComparisons field={field} inline />,
    },
    {
      id: 'evidence', label: candidates.length ? `Evidence · ${candidates.length}` : 'Evidence',
      content: <Evidence field={field} candidates={candidates} selectedId={selectedId} onSelect={setSelectedId} />,
    },
    {
      id: 'object', label: 'Object', content: <>
        <p>{field.description}</p>
        <SkyMap field={field} />
        <dl className="u-kv small fd-facts">
          <dt>Frames</dt><dd>{field.frames.length} · {detectors.map((d) => `D${d}`).join(', ') || 'none'}</dd>
          {dates.length > 0 && <><dt>Dates (UTC)</dt>
            <dd>{formatMjd(Math.min(...dates)).slice(0, 10)} → {formatMjd(Math.max(...dates)).slice(0, 10)}</dd></>}
        </dl>
        {systemId && <p className="small">
          <a href={`#/system/${systemId}`}>Explore these objects in 3D →</a> <span className="muted">3D model · not an image</span>
        </p>}
        {/* Full-page consumer: FE-5's "full" variant (the dock keeps the default "dock"). */}
        {synthetic ? <p className="muted small">Catalog context is not looked up for synthetic fields.</p>
          : objectSeen && <ObjectCard lookup={lookup} variant="full" />}
      </>,
    },
  );
  // Light curve is the default once it exists; Evidence until then. A tab the user picked (or focused into) stays.
  const active: TabId = tab && items.some((i) => i.id === tab) ? tab
    : items.some((i) => i.id === 'lightcurve') ? 'lightcurve' : 'evidence';

  const copyLink = () => {
    const done = (text: string) => setCopied(text);
    if (!navigator.clipboard) { done('Copy the address bar link'); return; }
    navigator.clipboard.writeText(window.location.href)
      .then(() => done('Link copied'), () => done('Copy the address bar link'));
  };

  return (
    <main className="fd-page">
      <header className="fd-titlebar">
        <div className="fd-titlemain">
          <a className="fd-back" href="#/">← Explore</a>
          <h1 className="fd-title u-truncate" title={title}>{title}</h1>
        </div>
        <div className="fd-titlemeta">
          {synthetic ? <SyntheticBadge synthetic /> : <span className="u-badge u-badge--spherex">SPHEREx · real frames</span>}
          {systemId && <a className="u-btn u-btn--ghost fd-titlebtn" href={`#/system/${systemId}`}
            title="Explore these objects in 3D (3D MODEL · NOT AN IMAGE)">3D model</a>}
          <button type="button" className="u-btn fd-titlebtn" onClick={copyLink}>{copied || 'Copy link'}</button>
          <span className="u-sr-only" role="status">{copied}</span>
        </div>
      </header>
      <div className="fd-body">
        <section className="fd-player-col" aria-label="SPHEREx image sequence">
          {player}
        </section>
        <section className="fd-side" aria-label="Field evidence" onFocus={() => { if (tab === null) setTab(active); }}>
          <Tabs label="Field panels" items={items} active={active} onChange={(id) => {
            setTab(id as TabId);
            if (id === 'object') setObjectSeen(true);
          }} />
        </section>
      </div>
    </main>
  );
}
