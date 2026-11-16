// 3D viewer for a SystemModel. three.js is loaded on demand (dynamic import) so the
// blink viewer and the rest of the site stay light. So are the helpers the controls and legends are
// built from (three/viewerKit: colour modes, scene layout, SPHEREx coverage, ephemerides) and the
// dataset timeline: only the tiny three/datasetGate and three/viewerLink are imported statically.
//
// Two clocks (M4): 'Free-running' animates from an arbitrary start and never shows a calendar date;
// 'Dataset time' runs on the real SPHEREx pass dates of the target (spherexCoverage.datasetWindow),
// shows the calendar date with the list of real-epoch and arbitrary-phase bodies, and what each body's
// phase is on that date (ephemerides.onThisDate).
import { lazy, Suspense, useContext, useEffect, useMemo, useRef, useState } from 'react';
import { client } from '../api/client';
import type { Frame, OrbitQuality, SystemModel } from '../api/types';
import { formatElapsed, formatMjd } from '../api/format';
import type { ColorMode } from '../three/colorModes';
import { hasDatasetWindow } from '../three/datasetGate';
import type { DistanceMode } from '../three/sceneLayout';
import type { SystemScene } from '../three/SystemScene';
import { SystemViewerContext, type SystemViewerLink } from '../three/viewerLink';
import '../three/system.css';

type ViewerKit = typeof import('../three/viewerKit');

// Loaded once per page, in parallel with the scene; a failed download is retried on the next mount.
let kitPromise: Promise<ViewerKit> | null = null;
function loadViewerKit(): Promise<ViewerKit> {
  kitPromise ??= import('../three/viewerKit').catch((e: unknown) => {
    kitPromise = null;
    throw e;
  });
  return kitPromise;
}

// Rendered only in Dataset time.
const DatasetTimeline = lazy(() => import('../three/DatasetTimeline').then((m) => ({ default: m.DatasetTimeline })));

interface Props extends SystemViewerLink {
  system: SystemModel;
  selectedId: string | null;
  onSelect: (bodyId: string | null) => void;
  /**
   * Dock / tab size (FE-12): stage <= 320 px, smaller controls that wrap, the view options and the legends
   * behind disclosures. The honesty chips on the stage stay visible. Default false (the full page).
   */
  compact?: boolean;
  /** With `compact`: link to the full 3D page (e.g. `#/system/<id>`), shown on the stage. */
  fullViewHref?: string;
}

/** 'load' = the three.js chunk did not download; 'webgl' = the browser could not create the 3D context. */
type ErrorKind = 'load' | 'webgl';

// Styles: three/system.css (.s3d-); the transport keeps the WS5-family class names (.system-viewer .blink-controls).
const LOS_HEX = '#7dd3fc'; // same colour as the arrow drawn by SystemScene

type TimeMode = 'free' | 'dataset';

export function SystemViewer(props: Props) {
  const { system, selectedId, onSelect, compact = false, fullViewHref } = props;
  // Page-level inputs: props first, then the page's context (SystemPage), else the viewer's own fallback.
  const link = useContext(SystemViewerContext);
  const fieldExists = props.fieldExists ?? link.fieldExists;
  const onDatasetMjd = props.onDatasetMjd ?? link.onDatasetMjd;

  const containerRef = useRef<HTMLDivElement>(null);
  const sceneRef = useRef<SystemScene | null>(null);
  const onSelectRef = useRef(onSelect);
  onSelectRef.current = onSelect;
  const selectedIdRef = useRef(selectedId);
  selectedIdRef.current = selectedId;
  const onDatasetMjdRef = useRef(onDatasetMjd);
  onDatasetMjdRef.current = onDatasetMjd;

  const [kit, setKit] = useState<ViewerKit | null>(null);
  const [status, setStatus] = useState<'loading' | 'ready' | 'error'>('loading');
  const [error, setError] = useState<{ kind: ErrorKind; message: string } | null>(null);
  const [mjd, setMjd] = useState<number | null>(null);
  const mjdRef = useRef(mjd);
  mjdRef.current = mjd;
  const [startMjd, setStartMjd] = useState<number | null>(null);
  const [timeMode, setTimeMode] = useState<TimeMode>('free');
  // Frames of the system's field, only when the manifest lists that field (real targets: not built).
  const [frames, setFrames] = useState<Frame[] | null>(null);
  const [playing, setPlaying] = useState(true);
  const [speedMul, setSpeedMul] = useState(1);
  const [distanceMode, setDistanceMode] = useState<DistanceMode>('compressed');
  const [showOrbits, setShowOrbits] = useState(true);
  const [showLabels, setShowLabels] = useState(true);
  // null = the default colour mode, known once the kit has loaded.
  const [colorChoice, setColorMode] = useState<ColorMode | null>(null);
  const colorMode = colorChoice ?? kit?.DEFAULT_COLOR_MODE ?? null;

  // The controls and legends fill in as soon as the kit arrives, before three.js has downloaded.
  useEffect(() => {
    let live = true;
    loadViewerKit().then(
      (k) => live && setKit(k),
      () => {
        // Reported by the scene effect below, which waits for the kit too.
      },
    );
    return () => {
      live = false;
    };
  }, []);

  // Create / destroy the scene when the system changes. 'ready' means the scene AND the kit are loaded.
  useEffect(() => {
    let disposed = false;
    const fail = (kind: ErrorKind, e: unknown) => {
      if (disposed) return;
      setError({ kind, message: e instanceof Error ? e.message : String(e) });
      setStatus('error');
    };
    setStatus('loading');
    setError(null);
    Promise.all([import('../three/SystemScene'), loadViewerKit()]).then(
      ([{ SystemScene }, k]) => {
        if (disposed || !containerRef.current) return;
        setKit(k);
        let scene: SystemScene;
        try {
          scene = new SystemScene(containerRef.current, system, {
            // Clicking the body that is already entered (mesh or label) flies back to it: the
            // selection (URL) does not change, so the parent would not re-trigger the focus.
            onSelect: (id) => {
              if (id && id === selectedIdRef.current) sceneRef.current?.focus(id);
              else onSelectRef.current(id);
            },
            onTick: setMjd,
            onClockStop: () => setPlaying(false),
          });
        } catch (e) {
          // Remove anything a half-built scene attached (React does not own these nodes).
          containerRef.current.querySelectorAll('canvas, .scene-labels').forEach((el) => el.remove());
          fail('webgl', e);
          return;
        }
        sceneRef.current = scene;
        setStartMjd(scene.getStartTime());
        setStatus('ready');
      },
      (e: unknown) => fail('load', e),
    );
    return () => {
      disposed = true;
      sceneRef.current?.dispose();
      sceneRef.current = null;
    };
  }, [system]);

  // A new system starts free-running.
  useEffect(() => setTimeMode('free'), [system]);

  // Fetch the field's frames only when the manifest lists the field. A page that has fetched the
  // manifest already says so (fieldExists); otherwise the viewer asks the manifest itself.
  useEffect(() => {
    let cancelled = false;
    setFrames(null);
    const fieldId = system.field_id;
    if (fieldId && fieldExists !== false) {
      (fieldExists === true
        ? client.getField(fieldId)
        : client.getManifest().then((m) => (m.fields.some((f) => f.id === fieldId) ? client.getField(fieldId) : null))
      )
        .then((f) => {
          if (!cancelled && f) setFrames(f.frames);
        })
        .catch(() => {
          // No frames: the dataset window falls back to the archive coverage (or is unavailable).
        });
    }
    return () => {
      cancelled = true;
    };
  }, [system, fieldExists]);

  // Known before the kit loads (datasetGate is tiny); win is non-null exactly when this is true.
  const datasetAvailable = hasDatasetWindow(system.id, frames);
  const win = useMemo(() => (kit ? kit.datasetWindow(system, frames) : null), [kit, system, frames]);
  const bounds = useMemo(() => (kit && win ? kit.datasetBounds(win) : null), [kit, win]);
  const dataset = timeMode === 'dataset' && win !== null;
  const tracks = useMemo(() => (kit ? kit.variabilityTracks(system) : []), [kit, system]);

  // Same pure function the scene uses (sceneLayout.ts), so the label and the animation agree. Dataset
  // time is capped so the whole window takes at least a minute (spherexCoverage.datasetSpeed).
  const freeSpeed = kit ? kit.suggestedSpeed(system) : null;
  const daysPerSec = kit && freeSpeed !== null ? (dataset && win ? kit.datasetSpeed(freeSpeed, win) : freeSpeed) * speedMul : null;

  useEffect(() => sceneRef.current?.setDatasetMode(dataset, bounds), [dataset, bounds, status]);
  useEffect(() => sceneRef.current?.setPlaying(playing), [playing, status]);
  useEffect(() => {
    if (daysPerSec !== null) sceneRef.current?.setSpeed(daysPerSec);
  }, [daysPerSec, status]);
  useEffect(() => {
    if (colorMode !== null) sceneRef.current?.setOptions({ distanceMode, showOrbits, showLabels, colorMode });
  }, [distanceMode, showOrbits, showLabels, colorMode, status]);
  useEffect(() => sceneRef.current?.focus(selectedId), [selectedId, status]);

  // Report the dataset date to the page (sky-track panel) only when the calendar day changes, not on
  // every onTick re-render; null in free-running and when the viewer goes away.
  const datasetDay = dataset && mjd !== null ? Math.floor(mjd) : null;
  useEffect(() => {
    onDatasetMjdRef.current?.(datasetDay === null ? null : mjdRef.current);
  }, [datasetDay]);
  useEffect(
    () => () => {
      onDatasetMjdRef.current?.(null);
    },
    [],
  );

  // The legends are static per system, mode and speed: build them once, not on every onTick re-render.
  const notFitted = useMemo(() => (kit ? kit.nonFittedOrbits(system.bodies) : null), [kit, system]);
  const colourLines = useMemo(() => (kit && colorMode ? kit.colorLegend(colorMode, system) : []), [kit, colorMode, system]);
  const surfaceLines = useMemo(() => (kit && colorMode ? kit.surfaceLegend(system, colorMode) : []), [kit, system, colorMode]);
  const spinLine = useMemo(() => (kit && daysPerSec !== null ? kit.spinLegend(system, daysPerSec) : ''), [kit, system, daysPerSec]);
  const modeChip = kit && colorMode ? kit.colourModeChip(colorMode) : null;
  const statusLine = useMemo(() => (kit ? kit.phaseStatusLine(system) : ''), [kit, system]);
  // Free-running phases are arbitrary for orbits without an epoch and for every animated variability.
  const arbitraryPhase = useMemo(() => (kit ? kit.freeRunningArbitraryPhase(system) : false), [kit, system]);
  const dateLines = kit && dataset && mjd !== null ? kit.onThisDate(system, mjd) : [];
  const cloudLegend = useMemo(() => (kit ? kit.datasetLegend(system) : null), [kit, system]);

  const chooseMode = (next: TimeMode) => {
    if (next === timeMode) return;
    const scene = sceneRef.current;
    if (next === 'dataset' && win && bounds) {
      // Jump to the middle of the first pass and hold there: the date shown is a real SPHEREx date.
      scene?.setDatasetMode(true, bounds);
      scene?.setTime(win.passes[0]?.midMjd ?? win.startMjd);
      setPlaying(false);
    } else {
      scene?.setDatasetMode(false);
      if (scene) {
        scene.setTime(scene.getTime()); // the free-running clock counts elapsed time from here
        setStartMjd(scene.getStartTime());
      }
    }
    setTimeMode(next);
  };

  const togglePlay = () => {
    // At the end of the dataset window, Play starts again from its beginning.
    if (!playing && dataset && bounds && mjd !== null && mjd >= bounds[1] - 1e-6) sceneRef.current?.setTime(bounds[0]);
    setPlaying((p) => !p);
  };

  // Distances, Colour, orbits and labels: in the transport row on the page, behind "View options" in compact.
  const viewOptions = (
    <>
      <label>
        Distances{' '}
        <select value={distanceMode} onChange={(e) => setDistanceMode(e.target.value as DistanceMode)}>
          <option value="compressed">compressed (log)</option>
          <option value="linear">true proportions</option>
        </select>
      </label>
      <label>
        Colour{' '}
        {kit && colorMode ? (
          <select value={colorMode} onChange={(e) => setColorMode(e.target.value as ColorMode)}>
            {kit.COLOR_MODES.map((m) => (
              <option key={m} value={m}>
                {kit.COLOR_MODE_LABEL[m]}
              </option>
            ))}
          </select>
        ) : (
          <select disabled aria-busy="true">
            <option>loading…</option>
          </select>
        )}
      </label>
      <label className="small">
        <input type="checkbox" checked={showOrbits} onChange={(e) => setShowOrbits(e.target.checked)} /> orbits
      </label>
      <label className="small">
        <input type="checkbox" checked={showLabels} onChange={(e) => setShowLabels(e.target.checked)} /> labels
      </label>
    </>
  );
  const wholeSystem = selectedId && (
    <button type="button" onClick={() => onSelect(null)}>
      ⤢ Whole system
    </button>
  );

  // Long legends (colour, surface, spin): behind a disclosure in compact.
  const colourLegend = (
    <>
      <div className="muted small s3d-legend" aria-live="polite">
        {kit && modeChip && colorMode && kit.isInfraredMode(colorMode) && (
          <p>
            <strong className="s3d-false-text">{modeChip}</strong> (not what the eye would see, and not SPHEREx data).
          </p>
        )}
        {colourLines.map((line, i) => (
          <p key={`c${i}`}>{line}</p>
        ))}
        {surfaceLines.map((line, i) => (
          <p key={`s${i}`}>{line}</p>
        ))}
        {spinLine && <p>{spinLine}</p>}
      </div>
    </>
  );
  // Short honesty lines kept visible in compact too (AGENTS.md rule 3: phase and parameter limits; faricool54 on #147).
  const orbitLegend = (
    <>
      {kit && notFitted && (notFitted.assumed.length > 0 || notFitted.hypothetical.length > 0) && (
        // Explained here too, not only inside the body panel: the whole-system view shows these orbits.
        <p className="muted small orbit-legend">
          {notFitted.assumed.length > 0 && (
            <span>
              <Swatch color={kit.ORBIT_COLOR.assumed} /> Yellow orbit = assumed, not fitted:{' '}
              {notFitted.assumed.join(', ')}.{' '}
            </span>
          )}
          {notFitted.hypothetical.length > 0 && (
            <span>
              <Swatch color={kit.ORBIT_COLOR.hypothetical} /> Violet orbit = hypothetical object:{' '}
              {notFitted.hypothetical.join(', ')}.{' '}
            </span>
          )}
          {notFitted.fitted && (
            <span>
              <Swatch color={kit.ORBIT_COLOR.fitted} />{' '}
              {system.provenance.synthetic
                ? 'Blue-grey orbit = synthetic demo orbit (not a published solution).'
                : 'Blue-grey orbit = fitted orbit from the cited catalog or paper.'}
            </span>
          )}
        </p>
      )}
    </>
  );
  // Dataset-time legend (On this date, arcs, rings, line of sight): long, behind the disclosure in compact.
  const cloudLegend_ = (
    <>
      {kit && dataset && cloudLegend && (
        <div className="muted small s3d-legend">
          {dateLines.length > 0 && (
            <>
              <p className="s3d-legend-title">
                <strong>On this date</strong>
              </p>
              <ul className="s3d-legend-list">
                {dateLines.map((l) => (
                  <li key={`${l.bodyId}-${l.kind}`}>
                    <strong>{l.name}</strong>: {l.text}
                    {l.source && <span className="s3d-legend-source"> ({l.source})</span>}
                  </li>
                ))}
              </ul>
            </>
          )}
          {cloudLegend.arc && (
            <p>
              <Dots color={kit.UNCERTAINTY_COLOR.fitted} /> Arc: {kit.CLOUD_POINTS} points over ±{kit.ARC_HALF_WIDTH_SIGMA}σ of orbital
              phase on this date, from the published t0 and period (linear propagation; their covariance is not published and is
              ignored); opacity follows the Gaussian density. It widens as the date moves away from t0.
            </p>
          )}
          {cloudLegend.fittedRing && (
            <p>
              <Dots color={kit.UNCERTAINTY_COLOR.fitted} faint /> Ring on a fitted orbit: phase unknown (no published epoch),{' '}
              {kit.CLOUD_POINTS} points uniform in time along the orbit (denser where the body moves slowly), i.e. where the body
              could be; the body is dimmed and labelled “phase unknown”.
            </p>
          )}
          {cloudLegend.guessedRing.length > 0 && (
            <p>
              {cloudLegend.guessedRing.map((q) => (
                <Dots key={q} color={kit.UNCERTAINTY_COLOR[q]} faint />
              ))}{' '}
              Ring on {guessedOrbitPhrase(cloudLegend.guessedRing)}: neither the orbit nor the phase is known, so the ring only
              follows the drawn orbit, not where the body could be; the body is dimmed and labelled “phase unknown”. Dot colours
              follow the orbit colours.
            </p>
          )}
          {cloudLegend.lineOfSight && (
            <p>
              <Swatch color={LOS_HEX} /> Arrow: {kit.LINE_OF_SIGHT_LABEL}. Each dated planet sits on it at its t0, read as the time of
              inferior conjunction; the sense of motion on the sky is unknown.
            </p>
          )}
        </div>
      )}
    </>
  );
  // Model time / arbitrary phase: always visible.
  const timeLine = (
    <>
      <p className="muted small">
        {dataset && mjd !== null ? (
          <>
            Dataset date: {formatMjd(mjd)} · {statusLine}
          </>
        ) : (
          <>
            Model time:{' '}
            {mjd === null || startMjd === null
              ? '—'
              : `${formatElapsed(mjd - startMjd)} (free-running${arbitraryPhase ? ', arbitrary starting phase' : ''}: not a prediction for a real date${datasetAvailable ? '; use Dataset time for the SPHEREx dates' : ''})`}
          </>
        )}{' '}
        · drag to rotate, scroll to zoom, click a body to enter it
      </p>
    </>
  );
  const legends = (
    <>
      {colourLegend}
      {orbitLegend}
      {cloudLegend_}
      {timeLine}
    </>
  );

  return (
    <div className={`system-viewer s3d-viewer${compact ? ' s3d-viewer--compact' : ''}${dataset ? ' s3d-viewer--dataset' : ''}`}>
      <div
        className={`s3d-stage${compact ? ' s3d-stage--compact' : ''}`}
        ref={containerRef}
        role="group"
        aria-label={`3D model of ${system.name}`}
      >
        <div className="s3d-chips" aria-hidden="true">
          <span className="badge u-badge u-badge--model s3d-chip">3D MODEL · NOT AN IMAGE</span>
          {modeChip && <span className="badge u-badge s3d-chip s3d-chip--false">{modeChip}</span>}
          {kit && dataset && mjd !== null && (
            <span className="badge u-badge u-badge--spherex s3d-chip">DATASET TIME · {kit.mjdToIsoDate(mjd)}</span>
          )}
        </div>
        {compact && fullViewHref && (
          <a className="s3d-fullview" href={fullViewHref}>
            Open full 3D view →
          </a>
        )}
        {status === 'loading' && (
          <p className="s3d-msg muted" role="status">
            Loading 3D view…
          </p>
        )}
        {status === 'error' && error?.kind === 'load' && (
          <div className="s3d-msg error" role="alert">
            <div>
              The 3D viewer could not be downloaded ({error.message}). Check your connection and reload the page.
              <br />
              <button type="button" onClick={() => window.location.reload()}>
                Reload
              </button>
            </div>
          </div>
        )}
        {status === 'error' && error?.kind === 'webgl' && (
          <p className="s3d-msg error" role="alert">
            The 3D view could not start ({error.message}). Your browser may not support WebGL, or it is turned off.
          </p>
        )}
      </div>
      {dataset && win && mjd !== null && (
        <Suspense
          fallback={
            <p className="muted small" role="status">
              Loading the SPHEREx timeline…
            </p>
          }
        >
          <DatasetTimeline window={win} mjd={mjd} onSeek={(m) => sceneRef.current?.setTime(m)} tracks={tracks} />
        </Suspense>
      )}
      <div className="blink-controls s3d-transport">
        {/* Play stays the first child: the shared transport styles (styles.css, WS5) make it the primary button. */}
        <button type="button" onClick={togglePlay} aria-label={playing ? 'Pause' : 'Play'}>
          {playing ? '❚❚ Pause' : '▶ Play'}
        </button>
        <label className="speed-control">
          <span>Speed</span>
          <input
            type="range"
            min={0.25}
            max={8}
            step={0.25}
            value={speedMul}
            onChange={(e) => setSpeedMul(Number(e.target.value))}
            aria-label="System playback speed"
          />
          <span className="speed-value">×{Number(speedMul.toFixed(2))}</span>
        </label>
        <span className="muted small">{daysPerSec !== null ? formatDaysPerSecond(daysPerSec) : ''}</span>
        <span role="group" aria-label="Clock" className="s3d-clock">
          <button type="button" className="s3d-clock-btn" aria-pressed={timeMode === 'free'} onClick={() => chooseMode('free')}>
            Free-running
          </button>
          <button
            type="button"
            className="s3d-clock-btn"
            aria-pressed={dataset}
            disabled={!datasetAvailable || status !== 'ready'}
            title={
              !datasetAvailable
                ? 'No SPHEREx coverage is known for this system'
                : status === 'loading'
                  ? 'Loading the 3D view and the SPHEREx pass dates…'
                  : 'Run the clock on the real SPHEREx pass dates of this target'
            }
            onClick={() => chooseMode('dataset')}
          >
            Dataset time (SPHEREx 2025-2026)
          </button>
        </span>
        {compact ? (
          <>
            {wholeSystem}
            <details className="s3d-options">
              <summary>View options</summary>
              <div className="s3d-options-body">{viewOptions}</div>
            </details>
          </>
        ) : (
          <>
            {viewOptions}
            {wholeSystem}
          </>
        )}
      </div>
      {compact ? (
        <>
          <div className="s3d-legends s3d-legends--compact">
            {orbitLegend}
            {timeLine}
          </div>
          <details className="s3d-disclosure s3d-legend-details">
            <summary>Colour, surface and date legends</summary>
            {colourLegend}
            {cloudLegend_}
          </details>
        </>
      ) : (
        <div className="s3d-legends">{legends}</div>
      )}
    </div>
  );
}

/** 'an assumed orbit', 'a hypothetical orbit' or 'an assumed or hypothetical orbit'. */
function guessedOrbitPhrase(qualities: readonly OrbitQuality[]): string {
  if (qualities.length > 1) return 'an assumed or hypothetical orbit';
  return qualities[0] === 'hypothetical' ? 'a hypothetical orbit' : 'an assumed orbit';
}

/** Three dots in a phase-cloud colour (legend). */
function Dots({ color, faint = false }: { color: string; faint?: boolean }) {
  return (
    <span aria-hidden="true" className="s3d-dots">
      {[0.4, 1, 0.4].map((o, i) => (
        // Dynamic: the colour comes from the viewer kit.
        <span key={i} className="s3d-dot" style={{ background: color, opacity: faint ? 0.6 : o }} />
      ))}
    </span>
  );
}

function Swatch({ color }: { color: string }) {
  // Dynamic: the orbit colour comes from the viewer kit.
  return <span aria-hidden="true" className="s3d-swatch" style={{ borderTopColor: color }} />;
}

function formatDaysPerSecond(d: number): string {
  if (d < 1) return `${(d * 24).toFixed(1)} h per second`;
  if (d < 365.25) return `${d.toFixed(1)} days per second`;
  return `${(d / 365.25).toFixed(1)} years per second`;
}
