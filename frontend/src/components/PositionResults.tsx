import { useState } from 'react';
import { client } from '../api/client';
import type { ObjectLookup } from '../api/objectCard';
import { formatRaDec } from '../api/format';
import { searchSequences, type SearchSequence } from '../api/skySearch';
import type { JobStatusResponse, SkyCoord, SystemSummary } from '../api/types';
import { FieldPage } from '../pages/FieldPage';
import { ObjectSystemPreview } from '../three/ObjectSystemPreview';
import { separationArcsec } from '../three/skyTrack';
import { PositionSpectrum } from './PositionSpectrum';
import { SystemPreview } from './SystemPreview';

const VIEWS = ['Time', 'Spectrum', '3D'] as const;
// A saved field can cover many stars. Use half a native SPHEREx pixel around
// the curated target center when associating a position with its catalog model.
const TARGET_RADIUS_ARCSEC = 3;

interface Props {
  position: SkyCoord;
  sequences: SearchSequence[];
  systems: SystemSummary[];
  selectedFieldId?: string;
  job: JobStatusResponse | null;
  building: boolean;
  buildError: string;
  quickLook: boolean;
  /** WS7 (V14): the object card's lookup, so the 3D tab describes the same object as the card. */
  lookup?: ObjectLookup | null;
}

export function PositionResults({ position, sequences, systems, selectedFieldId, job, building, buildError, quickLook, lookup }: Props) {
  const [view, setView] = useState<typeof VIEWS[number]>('Time');
  const live = client.config.mode === 'api';
  const readyFieldId = job?.status === 'ready' ? job.result_field_id ?? undefined : undefined;
  const nearby = searchSequences(sequences, '', position).filter(({ field }) => !field.synthetic);
  const point = { raDeg: position.ra, decDeg: position.dec };
  const targets = nearby.filter(({ field, href }) => href.startsWith('#/') &&
    separationArcsec(point, { raDeg: field.center.ra, decDeg: field.center.dec }) <= TARGET_RADIUS_ARCSEC);
  const savedFieldId = selectedFieldId ?? targets[0]?.field.id;
  const timeFieldId = readyFieldId ?? savedFieldId;
  const model = systems.find((system) => !system.synthetic && targets.some(({ field }) =>
    field.id === system.field_id && (!selectedFieldId || selectedFieldId === field.id)));
  const fieldPageId = model?.field_id ?? timeFieldId;
  const fieldName = fieldPageId && !fieldPageId.startsWith('job-')
    ? sequences.find(({ field }) => field.id === fieldPageId)?.field.name
    : undefined;
  const failure = buildError.startsWith('Job engine is disabled.')
    ? 'Generating new sequences is disabled on this server.'
    : buildError || job?.error_detail;

  return <section className="panel position-results" aria-labelledby="position-results-title">
    <h2 id="position-results-title">Selected sky position</h2>
    <p className="muted small">{formatRaDec(position.ra, position.dec)}</p>
    {fieldPageId && <p className="small">
      <a href={`#/field/${fieldPageId}`}>{fieldName ? `Open ${fieldName} field page →` : 'Open field page →'}</a>
    </p>}
    <div className="segmented position-views" role="group" aria-label="Position views">
      {VIEWS.map((name) => <button key={name} type="button" aria-pressed={view === name}
        onClick={() => setView(name)}>{name}</button>)}
    </div>
    {view === 'Time' && <section aria-label="Time sequence">
      {building && <p role="status">Preparing the SPHEREx time sequence…</p>}
      {!building && !readyFieldId && failure && <p className="error" role="alert">{failure}</p>}
      {!building && !timeFieldId && !failure && <p className="muted">
        {job ? 'Use the build controls above to check or retry the sequence.'
          : live ? 'Use Build time sequence above to load observations at this position.'
          : 'A new sequence requires the live API.'}
      </p>}
      {timeFieldId && <FieldPage key={timeFieldId} fieldId={timeFieldId} embedded />}
      {nearby.length > 0 && !timeFieldId && <ul aria-label="Saved sequences covering this position">
        {nearby.map(({ field, href }) => <li key={href}><a href={href}>Nearby saved sequence · {field.name}</a></li>)}
      </ul>}
    </section>}
    <div hidden={view !== 'Spectrum'}>
      <PositionSpectrum position={position} fieldId={timeFieldId} inline quickLook={quickLook} />
    </div>
    {view === '3D' && <section aria-label="3D catalog model">
      {model ? <SystemPreview key={model.id} systemId={model.id} />
        : <ObjectSystemPreview position={position} lookup={lookup} />}
    </section>}
  </section>;
}
