import { useEffect, useRef, useState } from 'react';
import { client } from '../api/client';
import type { JobStatusResponse, JobSubmitRequest, SkyCoord, SystemSummary } from '../api/types';
import { isTerminal, parseCoordinate, positionUrl, readPosition, watchJob } from '../api/jobs';
import { DETECTOR_BANDS } from '../api/format';
import { coordinateLookup, nameLookup, positionLookup, type ObjectLookup } from '../api/objectCard';
import { SHOWCASE_TARGETS } from '../api/showcase';
import { localTargetSequences, type SearchSequence } from '../api/skySearch';
import { ExplorerMap } from './ExplorerMap';
import type { ExplorerView } from './ExplorerDock';
import { ObjectCard } from './ObjectCard';
import { PositionResults } from './PositionResults';
import { SkySearch } from './SkySearch';

interface Props {
  sequences: SearchSequence[];
  systems: SystemSummary[];
  synthetic: boolean;
  manifestError: string;
}

interface SelectionOptions {
  label?: string;
  catalogName?: string;
  fieldId?: string;
  detector?: number;
  size?: number;
}

type SelectionOrigin = 'map' | 'preset' | 'search' | 'form';

function initialPosition() {
  try {
    const params = new URLSearchParams(location.search);
    return { request: readPosition(location.search), linked: params.has('ra') && params.has('dec'), error: '' };
  } catch (e) {
    return { request: readPosition(''), linked: false, error: `Invalid shared position: ${(e as Error).message}` };
  }
}

export function SkyExplorer({ sequences, systems, synthetic, manifestError }: Props) {
  const [initial] = useState(initialPosition);
  const [position, setPosition] = useState<SkyCoord>(initial.request);
  const [mapCenter, setMapCenter] = useState<SkyCoord>(initial.request);
  const [ra, setRa] = useState(String(initial.request.ra));
  const [dec, setDec] = useState(String(initial.request.dec));
  const [fov, setFov] = useState(String(initial.request.size_deg));
  const [detector, setDetector] = useState(initial.request.detectors![0]);
  const [job, setJob] = useState<JobStatusResponse | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(initial.error);
  const [notice, setNotice] = useState('');
  const [shareUrl, setShareUrl] = useState(location.href);
  const [lookup, setLookup] = useState<ObjectLookup | null>(() =>
    initial.linked ? coordinateLookup(initial.request.ra, initial.request.dec) : null);
  const [label, setLabel] = useState('');
  const [explicitFieldId, setExplicitFieldId] = useState<string>();
  const [view, setView] = useState<ExplorerView>(initial.linked ? 'Time' : 'Object');
  const controller = useRef<AbortController | null>(null);
  const live = client.config.mode === 'api';
  const selectedFieldId = explicitFieldId ?? (lookup ? localTargetSequences(sequences, position)[0]?.field.id : undefined);
  const footprintFieldId = job?.status === 'ready' ? job.result_field_id ?? selectedFieldId : selectedFieldId;

  const updateShare = (body: JobSubmitRequest, jobId?: string) => {
    const url = positionUrl(location.href, body, jobId);
    history.replaceState(null, '', url);
    setShareUrl(url);
  };

  useEffect(() => {
    const id = new URLSearchParams(location.search).get('job');
    if (!id || !live || initial.error) return;
    const abort = new AbortController();
    controller.current = abort;
    setView('Time');
    setBusy(true);
    client.getJob(id, abort.signal).then((first) => watchJob(client, first, abort.signal, setJob))
      .catch((e: Error) => { if (!abort.signal.aborted) setError(e.message); })
      .finally(() => { if (!abort.signal.aborted) setBusy(false); });
    return () => abort.abort();
  }, [live, initial.error]);
  useEffect(() => () => controller.current?.abort(), []);

  const build = async (body: JobSubmitRequest) => {
    controller.current?.abort();
    const abort = new AbortController();
    controller.current = abort;
    setBusy(true);
    setError('');
    setNotice('');
    setJob(null);
    updateShare(body);
    try {
      const first = await client.submitJob(body, abort.signal);
      if (abort.signal.aborted) return;
      updateShare(body, first.id);
      await watchJob(client, first, abort.signal, setJob);
    } catch (e) {
      if (!abort.signal.aborted) setError((e as Error).message);
    } finally {
      if (!abort.signal.aborted) setBusy(false);
    }
  };

  const select = (point: SkyCoord, origin: SelectionOrigin, options: SelectionOptions = {}) => {
    controller.current?.abort();
    setBusy(false);
    setJob(null);
    setError('');
    setNotice('');
    setPosition(point);
    setRa(String(point.ra));
    setDec(String(point.dec));
    if (origin !== 'map') setMapCenter(point);
    const fieldId = options.fieldId ?? localTargetSequences(sequences, point)[0]?.field.id;
    setExplicitFieldId(fieldId);
    setLabel(options.label ?? '');
    const catalogName = options.catalogName ?? (options.fieldId ? undefined : options.label);
    setLookup(origin === 'map' ? positionLookup(point.ra, point.dec)
      : catalogName ? nameLookup(catalogName) : coordinateLookup(point.ra, point.dec));
    setView(origin === 'map' && !live && !fieldId ? 'Object' : 'Time');
    const typedSize = Number(fov);
    const size = options.size ?? (typedSize >= 0.01 && typedSize <= 0.5 ? typedSize : initial.request.size_deg);
    const selectedDetector = options.detector ?? detector;
    setFov(String(size));
    setDetector(selectedDetector);
    const body: JobSubmitRequest = { ra: point.ra, dec: point.dec, size_deg: size, detectors: [selectedDetector], max_frames: 40 };
    if (live && ((origin === 'map' && !fieldId) || origin === 'form')) void build(body);
    else updateShare(body);
  };

  const submit = () => {
    if (!live) return;
    try {
      const point = { ra: parseCoordinate(ra, true), dec: parseCoordinate(dec, false) };
      const size = Number(fov);
      if (!(size >= 0.01 && size <= 0.5)) throw new Error('Field side must be 0.01–0.5 degrees.');
      if (lookup && point.ra === position.ra && point.dec === position.dec) {
        void build({ ...point, size_deg: size, detectors: [detector], max_frames: 40 });
      } else {
        select(point, 'form', { size, detector });
      }
    } catch (e) {
      setError((e as Error).message);
    }
  };

  const selectSearchSequence = ({ field, href }: SearchSequence) => {
    if (!href.startsWith('#/')) {
      location.assign(positionUrl(new URL(href, location.href).toString(), { ...initial.request, ...field.center }));
      return;
    }
    select(field.center, 'search', { fieldId: field.id, label: field.name });
  };

  const resume = async () => {
    if (!job) return;
    controller.current?.abort();
    const abort = new AbortController();
    controller.current = abort;
    setError('');
    setNotice('');
    setBusy(true);
    try {
      const first = await client.getJob(job.id, abort.signal);
      await watchJob(client, first, abort.signal, setJob);
    } catch (e) {
      if (!abort.signal.aborted) setError((e as Error).message);
    } finally {
      if (!abort.signal.aborted) setBusy(false);
    }
  };

  const buildPanel = <>
    {!live && <p className="small">New SPHEREx sequences need the live API.</p>}
    <form className="xp-build" onSubmit={(event) => { event.preventDefault(); submit(); }}>
      <details>
        <summary>Build options</summary>
        <label>Right ascension<input value={ra} onChange={(event) => setRa(event.target.value)} required /></label>
        <label>Declination<input value={dec} onChange={(event) => setDec(event.target.value)} required /></label>
        <p className="muted small">Enter ICRS coordinates in degrees or sexagesimal format.</p>
        <label>Field side (degrees)<input type="number" min="0.01" max="0.5" step="any" value={fov}
          onChange={(event) => setFov(event.target.value)} required /></label>
        <label>Detector<select value={detector} onChange={(event) => setDetector(Number(event.target.value))}>
          {[1, 2, 3, 4, 5, 6].map((d) => <option key={d} value={d}>D{d} · {DETECTOR_BANDS[d]}</option>)}
        </select></label>
      </details>
      <button className="primary-action" disabled={!live || busy} type="submit">Build SPHEREx sequence</button>
    </form>
    {busy && <p className="small" role="status">Preparing SPHEREx observations{job ? ` · ${job.stage}` : '…'}</p>}
    {!busy && job?.status === 'ready' && <p className="small" role="status">Time sequence ready.</p>}
    {!busy && job?.status === 'no_coverage' && <p className="small" role="status">
      No usable archive coverage. Try another position, detector or field size.
    </p>}
    {(error || job?.error_detail) && <p className="error" role="alert">{error || job?.error_detail}</p>}
    <div className="xp-build-actions">
      {busy && <button type="button" onClick={() => {
        controller.current?.abort();
        setBusy(false);
        setNotice('Stopped watching. The server may continue the build.');
      }}>Stop watching</button>}
      {!busy && job && !isTerminal(job) && <button type="button" onClick={() => void resume()}>Resume watching</button>}
    </div>
  </>;

  return <section className="xp-explorer" aria-label="SPHEREx sky explorer">
    <div className="xp-map">
      <ExplorerMap layout="fill" center={mapCenter} footprintFieldId={footprintFieldId}
        onSelect={(point: SkyCoord & { insideFieldId?: string }) => {
          select(point, 'map', { fieldId: point.insideFieldId === footprintFieldId ? footprintFieldId : undefined });
        }} />
      <div className="xp-search">
        <SkySearch sequences={sequences} onSelectSequence={selectSearchSequence}
          onLocate={(point, name) => select(point, 'search', { label: name })} />
        <label>Challenge target<select value="" onChange={(event) => {
          if (!event.target.value) return;
          const target = SHOWCASE_TARGETS[Number(event.target.value)];
          if (target) select(target, 'preset', { label: target.name, catalogName: target.catalogName, detector: target.detector, size: 0.15 });
        }}><option value="">Choose a challenge target…</option>
          {SHOWCASE_TARGETS.map((target, index) => <option key={target.name} value={index}>{target.name}</option>)}
        </select></label>
        {manifestError && <p className="error small" role="alert">Could not load saved fields: {manifestError}</p>}
      </div>
    </div>
    <PositionResults position={position} sequences={sequences} systems={systems} selectedFieldId={selectedFieldId}
      job={job} quickLook={Boolean(lookup)} lookup={lookup} label={label} synthetic={synthetic}
      view={view} onView={setView} object={<ObjectCard lookup={lookup} />}
      onCopyLink={() => { void navigator.clipboard.writeText(shareUrl).then(
        () => setNotice('Link copied.'), () => setNotice('Copy the link from your browser address bar.')); }}
      build={buildPanel} notice={notice} />
  </section>;
}
