import { useEffect, useRef, useState } from 'react';
import { client } from '../api/client';
import type { JobStatusResponse, JobSubmitRequest, SkyCoord, SystemSummary } from '../api/types';
import { isTerminal, parseCoordinate, positionUrl, readPosition, watchJob } from '../api/jobs';
import { DETECTOR_BANDS } from '../api/format';
import { coordinateLookup, nameLookup, positionLookup, type ObjectLookup } from '../api/objectCard';
import { SHOWCASE_TARGETS } from '../api/showcase';
import type { SearchSequence } from '../api/skySearch';
import { ExplorerMap } from './ExplorerMap';
import { ObjectCard } from './ObjectCard';
import { PositionResults } from './PositionResults';
import { SkySearch } from './SkySearch';

function initialPosition(): { request: JobSubmitRequest; error: string } {
  try { return { request: readPosition(location.search), error: '' }; }
  catch (e) { return { request: readPosition(''), error: `Invalid shared position: ${(e as Error).message}` }; }
}

/** A shared link with an explicit position opens its catalog card (a preset's link by the preset's name);
 *  the default position does not. */
function initialLookup(request: JobSubmitRequest, error: string): ObjectLookup | null {
  const params = new URLSearchParams(location.search);
  return !error && params.has('ra') && params.has('dec') ? coordinateLookup(request.ra, request.dec) : null;
}

export function SkyExplorer({ sequences, systems }: { sequences: SearchSequence[]; systems: SystemSummary[] }) {
  const [initial] = useState(initialPosition);
  const [center, setCenter] = useState<SkyCoord>(initial.request);
  const [ra, setRa] = useState(String(initial.request.ra));
  const [dec, setDec] = useState(String(initial.request.dec));
  const [fov, setFov] = useState(String(initial.request.size_deg));
  const [detector, setDetector] = useState(initial.request.detectors![0]);
  const [resolved, setResolved] = useState('');
  const [job, setJob] = useState<JobStatusResponse | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(initial.error);
  const [notice, setNotice] = useState('');
  const [shareUrl, setShareUrl] = useState(location.href);
  // Catalog card: names (presets, name search) by NAME for a better identity, map clicks and coordinates by position;
  // a preset's untouched position (Build, shared link) stays a NAME lookup (coordinateLookup).
  const [lookup, setLookup] = useState<ObjectLookup | null>(() => initialLookup(initial.request, initial.error));
  const [quickLook, setQuickLook] = useState(false);
  const [selectedFieldId, setSelectedFieldId] = useState<string>();
  const [reveal, setReveal] = useState(0);
  const resultRef = useRef<HTMLDivElement>(null);
  const controller = useRef<AbortController | null>(null);
  const live = client.config.mode === 'api';

  const observe = async (first: JobStatusResponse, signal: AbortSignal) => {
    await watchJob(client, first, signal, setJob);
  };
  // A shared job resumes observation; opening a coordinate link never submits a build implicitly.
  useEffect(() => {
    const id = new URLSearchParams(location.search).get('job');
    if (!id || !live || initial.error) return;
    const abort = new AbortController();
    controller.current = abort;
    setBusy(true);
    client.getJob(id, abort.signal).then((first) => observe(first, abort.signal))
      .catch((e: Error) => { if (!abort.signal.aborted) setError(e.message); })
      .finally(() => { if (!abort.signal.aborted) setBusy(false); });
    return () => abort.abort();
  }, [live, initial.error]);
  useEffect(() => () => controller.current?.abort(), []);
  useEffect(() => {
    if (!reveal) return;
    resultRef.current?.focus({ preventScroll: true });
    resultRef.current?.scrollIntoView({ block: 'start' });
  }, [reveal]);

  const submit = async (position?: SkyCoord) => {
    if (!live) return;
    controller.current?.abort();
    const abort = new AbortController();
    controller.current = abort;
    setBusy(true); setError(''); setNotice(''); setJob(null);
    try {
      const point = position ?? { ra: parseCoordinate(ra, true), dec: parseCoordinate(dec, false) };
      if (!position && !(lookup && 'name' in lookup && point.ra === center.ra && point.dec === center.dec)) {
        setLookup(coordinateLookup(point.ra, point.dec));
        setResolved('');
      }
      const size = Number(fov);
      if (!Number.isFinite(size) || size < 0.01 || size > 0.5) throw new Error('Field side must be 0.01–0.5 degrees.');
      // Catalog response fields belong to the resolver, not the job request.
      const body: JobSubmitRequest = { ra: point.ra, dec: point.dec, size_deg: size,
        detectors: [detector], max_frames: 40 };
      if (abort.signal.aborted) return;
      setCenter({ ra: body.ra, dec: body.dec }); setRa(String(body.ra)); setDec(String(body.dec));
      if (point.ra !== center.ra || point.dec !== center.dec) setSelectedFieldId(undefined);
      setQuickLook(true);
      history.replaceState(null, '', positionUrl(location.href, body));
      setShareUrl(location.href);
      const first = await client.submitJob(body, abort.signal);
      if (abort.signal.aborted) return;
      history.replaceState(null, '', positionUrl(location.href, body, first.id));
      setShareUrl(location.href);
      await observe(first, abort.signal);
    } catch (e) { if (!abort.signal.aborted) setError((e as Error).message); }
    finally { if (!abort.signal.aborted) setBusy(false); }
  };

  const locate = (point: SkyCoord, label?: string, source?: string) => {
    controller.current?.abort();
    setBusy(false); setJob(null); setError(''); setNotice('');
    setCenter(point); setRa(String(point.ra)); setDec(String(point.dec));
    setSelectedFieldId(undefined);
    setQuickLook(true);
    setLookup(label ? nameLookup(label) : coordinateLookup(point.ra, point.dec));
    setResolved(label ? `${label} · ${source}` : '');
    // Keep a valid share link even if the user was in the middle of editing the field size.
    const size = Number(fov);
    const url = positionUrl(location.href, { ...initial.request, ra: point.ra, dec: point.dec,
      size_deg: size >= 0.01 && size <= 0.5 ? size : initial.request.size_deg, detectors: [detector] });
    history.replaceState(null, '', url); setShareUrl(url);
  };

  const selectSearchSequence = ({ field, href }: SearchSequence) => {
    if (!href.startsWith('#/')) {
      // The real fields in the static demo are served by a separate dataset.
      location.assign(positionUrl(new URL(href, location.href).toString(), { ...initial.request, ...field.center }));
      return;
    }
    locate(field.center);
    setSelectedFieldId(field.id);
    setReveal((count) => count + 1);
  };

  const stop = () => {
    controller.current?.abort(); setBusy(false);
    setNotice('Stopped watching. The server may continue the build; resume to see its result.');
  };
  const resume = async () => {
    if (!job) return;
    controller.current?.abort();
    const abort = new AbortController(); controller.current = abort;
    setError(''); setNotice(''); setBusy(true);
    try { await observe(await client.getJob(job.id, abort.signal), abort.signal); }
    catch (e) { if (!abort.signal.aborted) setError((e as Error).message); }
    finally { if (!abort.signal.aborted) setBusy(false); }
  };

  return <section aria-labelledby="explore-title">
    <SkySearch sequences={sequences} onSelectSequence={selectSearchSequence} onLocate={(point, label, source) => {
      locate(point, label, source);
      setReveal((count) => count + 1);
    }} />
    <div className="explorer-layout">
      <ExplorerMap center={center} onSelect={(p) => {
        locate(p);
        setLookup(positionLookup(p.ra, p.dec));
        setReveal((count) => count + 1);
        if (live) void submit(p);
      }} />
      <aside className="panel explore-form">
        <h2 id="explore-title">Explore a position</h2>
        <p className="muted small">1. Pick a position. 2. Build real observations. 3. Play through their dates.</p>
        <label>Challenge target preset<select defaultValue="" onChange={(e) => {
          const target = SHOWCASE_TARGETS[Number(e.target.value)];
          if (!target) return;
          controller.current?.abort(); setBusy(false); setJob(null); setError(''); setResolved('');
          setCenter(target); setRa(String(target.ra)); setDec(String(target.dec));
          setSelectedFieldId(undefined);
          setQuickLook(true);
          setFov('0.15'); setDetector(target.detector); setLookup(nameLookup(target.catalogName));
          setNotice(`${target.name}: ICRS position propagated to mean epoch MJD ${target.mjd}. Sesame/SIMBAD CfA astrometry, checked 14 Nov 2026. This preset is not a validated detection.`);
          const url = positionUrl(location.href, { ra: target.ra, dec: target.dec, size_deg: 0.15, detectors: [target.detector] });
          history.replaceState(null, '', url); setShareUrl(url);
        }}><option value="" disabled>Choose one of the five targets…</option>
          {SHOWCASE_TARGETS.map((target, index) => <option key={target.name} value={index}>{target.name}</option>)}
        </select></label>
        {!live && <p className="mode-note">Static mode lets you explore positions and open saved sequences. Building a new sequence or looking up an unsaved name needs the live API.
          {' '}<a href={(() => { const u = new URL(location.href); u.searchParams.set('mode', 'api'); return u.toString(); })()}>Use live API →</a></p>}
        <form onSubmit={(e) => { e.preventDefault(); void submit(); }}>
            <label>Right ascension<input value={ra} onChange={(e) => setRa(e.target.value)} required
              aria-describedby="coordinate-help" placeholder="269.44623 or 17:57:47.1" /></label>
            <label>Declination<input value={dec} onChange={(e) => setDec(e.target.value)} required
              aria-describedby="coordinate-help" placeholder="+4.76870 or +04:46:07.3" /></label>
            <p className="muted small" id="coordinate-help">ICRS decimal degrees, or RA HH:MM:SS and Dec ±DD:MM:SS.</p>
          <div className="explore-filters">
            <label>Field side (degrees)<input type="number" min="0.01" max="0.5" step="any" value={fov}
              onChange={(e) => setFov(e.target.value)} required /></label>
            <label>Detector<select value={detector} onChange={(e) => setDetector(Number(e.target.value))}>
              {[1, 2, 3, 4, 5, 6].map((d) => <option key={d} value={d}>D{d} · {DETECTOR_BANDS[d]}</option>)}
            </select></label>
          </div>
          <p className="muted small">Up to 40 frames. One detector avoids mixing broad wavelength ranges; each exposure still has its own wavelength. Larger fields need more processing.</p>
          <button className="primary-action" disabled={!live || busy} type="submit">{busy ? 'Working…' : 'Build time sequence'}</button>
        </form>
        {resolved && <p className="small">{resolved}. Catalog position; coverage is checked separately.
          High proper-motion targets can move from their catalog position; use the propagated challenge presets above.</p>}
        {job && <div className="job-status" role="status" aria-live="polite">
          <strong>{job.status === 'ready' ? 'Sequence ready' : job.status === 'no_coverage' ? 'No archive coverage' :
            job.status === 'failed' ? 'Build failed' : job.status === 'pipeline_not_ready' ? 'Pipeline unavailable' :
            job.status === 'queued' ? 'Waiting for worker' : 'Building real observations'}</strong>
          <p className="small muted">Stage: {job.stage}. Job <code>{job.id.slice(0, 12)}</code></p>
          {job.error_detail && <p>{job.error_detail}</p>}
          {job.status === 'no_coverage' && <p className="small">Try another position, detector or field size. A map tile does not guarantee usable time observations.</p>}
          {job.status === 'ready' && job.result_field_id && <a href={`#/field/${job.result_field_id}`}>Open sequence on its own page →</a>}
        </div>}
        {error && <p className="error" role="alert">{error}</p>}
        {notice && <p className="small" role="status">{notice}</p>}
        <div className="explore-actions">
          {busy && <button onClick={stop}>Stop watching</button>}
          {!busy && job && !isTerminal(job) && <button onClick={() => void resume()}>Resume watching</button>}
          {!busy && live && (error || (job && ['failed', 'no_coverage', 'pipeline_not_ready'].includes(job.status))) &&
            <button onClick={() => void submit()}>Retry build</button>}
          <button onClick={() => { void navigator.clipboard.writeText(shareUrl).then(() => setNotice('Link copied.'),
            () => setNotice('Copy the link from your browser address bar.')); }}>Copy position link</button>
        </div>
        <ObjectCard lookup={lookup} />
      </aside>
    </div>
    {(lookup || job) && <div ref={resultRef} className="position-result-anchor" tabIndex={-1}>
      <PositionResults key={`${center.ra}/${center.dec}/${selectedFieldId ?? ''}/${quickLook}`}
        position={center} sequences={sequences} systems={systems} selectedFieldId={selectedFieldId}
        job={job} building={busy} buildError={error} quickLook={quickLook} />
    </div>}
  </section>;
}
