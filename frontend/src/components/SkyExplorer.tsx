import { useEffect, useRef, useState } from 'react';
import { client } from '../api/client';
import type { JobStatusResponse, JobSubmitRequest, SkyCoord, SystemSummary } from '../api/types';
import { isTerminal, parseCoordinate, positionUrl, readPosition, watchJob } from '../api/jobs';
import { DETECTOR_BANDS } from '../api/format';
import { coordinateLookup, nameLookup, positionLookup, type ObjectLookup } from '../api/objectCard';
import { SHOWCASE_TARGETS } from '../api/showcase';
import { localTargetSequences, type SearchSequence } from '../api/skySearch';
import type { MapSelection } from '../api/mapHover';
import { BottomSheet, SHEET_SNAPS, type SheetSnap } from './BottomSheet';
import { ExplorerMap } from './ExplorerMap';
import type { ExplorerView } from './ExplorerDock';
import { ObjectCard } from './ObjectCard';
import { PositionResults } from './PositionResults';
import { SkySearch } from './SkySearch';
import { TargetChips } from './TargetChips';
import { matchesMediaQuery, useMediaQuery } from './useMediaQuery';

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
  /** One-line provenance shown in the dock header (preset astrometry or name resolver). */
  note?: string;
  /** The pick came from the map (a tap or a target marker): on phones the sheet keeps the map in view. */
  fromMap?: boolean;
}

export type SelectionOrigin = 'map' | 'preset' | 'search' | 'form';

/** D-1: presets and searches never start a job; a map click does only live and away from a saved sequence. */
export function buildsOnSelect(origin: SelectionOrigin, live: boolean, savedFieldId?: string) {
  return live && ((origin === 'map' && !savedFieldId) || origin === 'form');
}

export function presetNote(target: { name: string; mjd: number }) {
  return `${target.name}: ICRS position propagated to mean epoch MJD ${target.mjd}. Sesame/SIMBAD CfA astrometry, `
    + 'checked 14 Nov 2026. This preset is not a validated detection.';
}

export function resolverNote(name: string, source?: string) {
  return `${name} · ${source || 'name resolver'}. Catalog position; coverage is checked separately. High proper-motion `
    + 'targets can move from their catalog position; use the propagated challenge targets.';
}

/** The backend's 503 text names an environment variable; visitors get a plain sentence instead. */
export function buildFailureText(message: string) {
  return message.startsWith('Job engine is disabled.') ? 'Generating new sequences is disabled on this server.' : message;
}

/** FE-10: at this width the dock becomes a bottom sheet over a full-screen map (same query as explorer.css). */
export const PHONE_QUERY = '(max-width: 900px)';

/** FE-10: a phone this short shows only the dock header and tabs at half height (360x640: no panel at all). */
export const SHORT_QUERY = '(max-height: 700px)';

/** A selection raises a lowered sheet to `to` (half by default) and leaves a taller one alone. */
export const raiseSheet = (snap: SheetSnap, to: SheetSnap = 'half'): SheetSnap =>
  SHEET_SNAPS.indexOf(snap) < SHEET_SNAPS.indexOf(to) ? to : snap;

/**
 * How far a selection raises the sheet. A pick on the map keeps the map in view (half); a chip, a search or a tab on a
 * short phone goes to full, so the panel (the P0 video) shows without a scroll.
 */
export const selectionSnap = (fromMap: boolean, short: boolean): SheetSnap => (short && !fromMap ? 'full' : 'half');

/** Esc pressed inside the map iframe reaches the page only as this message (sky-map.html forwards it). */
export function isMapEscape(event: Pick<MessageEvent, 'origin' | 'data'>, origin: string) {
  return event.origin === origin && event.data?.source === 'errante-sky' && event.data?.type === 'escape';
}

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
  // Bumped on every non-map selection, so picking the same target again recentres a panned map (FE-4).
  const [recenter, setRecenter] = useState(0);
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
  const [note, setNote] = useState('');
  const [quickLook, setQuickLook] = useState(false);
  const [explicitFieldId, setExplicitFieldId] = useState<string>();
  const [view, setView] = useState<ExplorerView>(initial.linked || initial.error ? 'Time' : 'Object');
  const phone = useMediaQuery(PHONE_QUERY);
  const short = useMediaQuery(SHORT_QUERY);
  // A shared link or a job opens with its result in view; the plain home starts with the map and a peek.
  const [sheet, setSheet] = useState<SheetSnap>(() =>
    initial.linked || initial.error || new URLSearchParams(location.search).has('job')
      ? selectionSnap(false, matchesMediaQuery(SHORT_QUERY)) : 'peek');
  const controller = useRef<AbortController | null>(null);
  const explorer = useRef<HTMLElement>(null);
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
  // On phones the dock scrolls as one piece inside the sheet: a new selection starts at its name again.
  useEffect(() => {
    explorer.current?.querySelector('.sh-root .xp-dock')?.scrollTo({ top: 0 });
  }, [position, label]);
  // A tap on the map moves the focus into its iframe, so the sheet's own Esc listener never hears the key there. The
  // map forwards it; Esc order (FE-11): an open map card closes first (the map does that), then the sheet lowers.
  useEffect(() => {
    if (!phone) return;
    const onMessage = (event: MessageEvent) => {
      const frame = explorer.current?.querySelector<HTMLIFrameElement>('.xp-map iframe');
      if (!isMapEscape(event, location.origin) || !frame || event.source !== frame.contentWindow) return;
      // The map card is a portal and closes on the same message; it is still in the DOM while this runs.
      if (document.querySelector('.mp-card')) return;
      setSheet('peek');
    };
    window.addEventListener('message', onMessage);
    return () => window.removeEventListener('message', onMessage);
  }, [phone]);

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
    if (origin !== 'map') {
      setMapCenter(point);
      setRecenter((n) => n + 1);
    }
    const fieldId = options.fieldId ?? localTargetSequences(sequences, point)[0]?.field.id;
    setExplicitFieldId(fieldId);
    setLabel(options.label ?? '');
    setNote(options.note ?? '');
    setQuickLook(true);
    const to = selectionSnap(origin === 'map' || !!options.fromMap, short);
    setSheet((snap) => raiseSheet(snap, to));
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
    if (buildsOnSelect(origin, live, fieldId)) void build(body);
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
    {(error || job?.error_detail) && <p className="error" role="alert">{buildFailureText(error || job?.error_detail || '')}</p>}
    <div className="xp-build-actions">
      {busy && <button type="button" onClick={() => {
        controller.current?.abort();
        setBusy(false);
        setNotice('Stopped watching. The server may continue the build.');
      }}>Stop watching</button>}
      {!busy && job && !isTerminal(job) && <button type="button" onClick={() => void resume()}>Resume watching</button>}
    </div>
  </>;

  // A tab tapped on a lowered sheet raises it too (the sheet state is unused on desktop).
  const results = <PositionResults position={position} sequences={sequences} systems={systems} selectedFieldId={selectedFieldId}
    job={job} quickLook={quickLook} lookup={lookup} label={label} note={note} synthetic={synthetic}
    view={view} onView={(next) => { setView(next); setSheet((snap) => raiseSheet(snap, selectionSnap(false, short))); }} object={<ObjectCard lookup={lookup} />}
    onCopyLink={() => { void navigator.clipboard.writeText(shareUrl).then(
      () => setNotice('Link copied.'), () => setNotice('Copy the link from your browser address bar.')); }}
    build={buildPanel} notice={notice} />;

  // data-sheet lets explorer.css keep the map's credits above a half sheet (FRONTEND_PLAN §4.4).
  return <section ref={explorer} className="xp-explorer" aria-label="SPHEREx sky explorer" data-sheet={phone ? sheet : undefined}>
    <div className="xp-map">
      <ExplorerMap layout="fill" center={mapCenter} footprintFieldId={footprintFieldId} recenterKey={recenter}
        autoZoomKey={recenter > 0 || initial.linked ? recenter : undefined}
        onSelect={(point: MapSelection) => {
          // A challenge-target marker opens its saved sequence like its chip (no job); a Gaia star keeps its id.
          const target = SHOWCASE_TARGETS.find((t) => t.fieldId === point.targetId);
          if (target) {
            select(target, 'preset', {
              label: target.name, catalogName: target.catalogName, detector: target.detector, size: 0.15, note: presetNote(target),
              fromMap: true,
            });
            return;
          }
          select({ ra: point.ra, dec: point.dec }, 'map', {
            fieldId: point.insideFieldId === footprintFieldId ? footprintFieldId : undefined,
            label: point.sourceId ? `Gaia DR3 ${point.sourceId}` : undefined,
          });
        }} />
      <div className="xp-search">
        <SkySearch sequences={sequences} onSelectSequence={selectSearchSequence}
          onLocate={(point, name, source) => select(point, 'search',
            { label: name, note: name ? resolverNote(name, source) : undefined })} />
        <TargetChips sequences={sequences} activeName={SHOWCASE_TARGETS.some((t) => t.name === label) ? label : undefined}
          onPick={(target) => select(target, 'preset', {
            label: target.name, catalogName: target.catalogName, detector: target.detector, size: 0.15, note: presetNote(target),
          })} />
        {manifestError && <p className="error small" role="alert">Could not load saved fields: {manifestError}</p>}
      </div>
    </div>
    {phone ? <BottomSheet label="position details" snap={sheet} onSnapChange={setSheet}>{results}</BottomSheet> : results}
  </section>;
}
