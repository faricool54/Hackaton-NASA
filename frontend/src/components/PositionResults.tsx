import type { ReactNode } from 'react';
import type { ObjectLookup } from '../api/objectCard';
import { formatRaDec } from '../api/format';
import { searchSequences, type SearchSequence } from '../api/skySearch';
import type { JobStatusResponse, SkyCoord, SystemSummary } from '../api/types';
import { FieldPage } from '../pages/FieldPage';
import { ObjectSystemPreview } from '../three/ObjectSystemPreview';
import { ExplorerDock, ExplorerPanel, type ExplorerView } from './ExplorerDock';
import { PositionSpectrum } from './PositionSpectrum';
import { SystemPreview } from './SystemPreview';

interface Props {
  position: SkyCoord;
  sequences: SearchSequence[];
  systems: SystemSummary[];
  selectedFieldId?: string;
  job: JobStatusResponse | null;
  quickLook: boolean;
  lookup: ObjectLookup | null;
  view: ExplorerView;
  onView: (view: ExplorerView) => void;
  label: string;
  note: string;
  synthetic: boolean;
  notice: string;
  onCopyLink: () => void;
  object: ReactNode;
  build: ReactNode;
}

export function PositionResults({
  position, sequences, systems, selectedFieldId, job, quickLook, lookup,
  view, onView, label, note, synthetic, notice, onCopyLink, object, build,
}: Props) {
  const selected = Boolean(lookup || job || selectedFieldId);
  const timeFieldId = job?.status === 'ready' ? job.result_field_id ?? selectedFieldId : selectedFieldId;
  const field = sequences.find((entry) => entry.field.id === timeFieldId)?.field;
  const model = systems.find((system) => !system.synthetic && system.field_id === timeFieldId);
  const nearby = selected && !timeFieldId ? searchSequences(sequences, '', position) : [];
  const header = <>
    <h1>{label || field?.name || (selected ? 'Selected sky position' : 'Watch the infrared sky change')}</h1>
    {selected ? <p className="small">{formatRaDec(position.ra, position.dec)}</p>
      : <p className="small">Pick a challenge target, search a name, or click any star.</p>}
    {note && <p className="muted small xp-note">{note}</p>}
    {synthetic && <p className="small">SYNTHETIC DATA · NOT SPHEREx</p>}
    {selected && <div className="xp-dock-links small">
      <button type="button" className="link-button" onClick={onCopyLink}>Copy link</button>
      {timeFieldId && <a href={`#/field/${timeFieldId}`}>Open field page →</a>}
    </div>}
    {notice && <p className="small" role="status">{notice}</p>}
  </>;

  return <ExplorerDock view={view} onView={onView} header={header} timeReady={job?.status === 'ready'}>
    <ExplorerPanel name="Object" active={view === 'Object'}>
      {lookup && <p className="muted small">Catalog information</p>}
      {lookup ? object : <Welcome />}
    </ExplorerPanel>
    <ExplorerPanel name="Time" active={view === 'Time'}>
      {timeFieldId && !synthetic && !field?.synthetic && <p className="muted small">SPHEREx observations</p>}
      {timeFieldId && <FieldPage key={timeFieldId} fieldId={timeFieldId} embedded />}
      {build}
      {nearby.length > 0 && <ul aria-label="Saved sequences covering this position">
        {nearby.map(({ field: candidate, href }) => <li key={href}><a href={href}>{candidate.name}</a></li>)}
      </ul>}
    </ExplorerPanel>
    <ExplorerPanel name="Spectrum" active={view === 'Spectrum'}>
      {selected ? <PositionSpectrum key={`${position.ra}/${position.dec}/${timeFieldId ?? ''}/${quickLook}`} position={position} fieldId={timeFieldId} inline quickLook={quickLook} />
        : <p className="muted">Select a position to see its SPHEREx spectrum.</p>}
    </ExplorerPanel>
    <ExplorerPanel name="3D" active={view === '3D'}>
      {view === '3D' && (model ? <SystemPreview key={model.id} systemId={model.id} />
        : selected ? <ObjectSystemPreview position={position} lookup={lookup} />
          : <p className="muted">Select a catalog object. <a href="#/systems">Browse catalog models →</a></p>)}
    </ExplorerPanel>
  </ExplorerDock>;
}

/** What the empty dock shows before any selection: how to use the explorer and how its labels read. */
export function Welcome() {
  return <section className="xp-welcome" aria-label="How to use the explorer">
    <ol className="xp-steps">
      <li><strong>Pick</strong> a challenge target above the map, search a name or RA Dec, or click any star.</li>
      <li><strong>Time</strong> plays the real SPHEREx exposures of that spot, date by date.</li>
      <li><strong>Spectrum</strong>, <strong>Object</strong> and <strong>3D</strong> add its SPHEREx spectrum, its catalog
        data and a model built from catalog values.</li>
    </ol>
    <p className="muted small">Hover a star on the map for its Gaia DR3 values. Every panel says what it shows: a
      SPHEREx measurement, a catalog value or a model.</p>
    <p className="muted small">Real SPHEREx DR1 and QR3 images from NASA/IPAC IRSA.</p>
  </section>;
}
