// 3D viewer for a SystemModel. three.js is loaded on demand (dynamic import) so the
// blink viewer and the rest of the site stay light. Everything imported statically here
// (sceneLayout, colorModes, spherexCoverage, ephemerides, DatasetTimeline) is pure and three-free.
//
// Two clocks (M4): 'Free-running' animates from an arbitrary start and never shows a calendar date;
// 'Dataset time' runs on the real SPHEREx pass dates of the target (spherexCoverage.datasetWindow),
// shows the calendar date with the list of real-epoch and arbitrary-phase bodies, and what each body's
// phase is on that date (ephemerides.onThisDate).
import { useEffect, useMemo, useRef, useState, type CSSProperties } from 'react';
import { client } from '../api/client';
import type { Frame, OrbitQuality, SystemModel } from '../api/types';
import { formatElapsed, formatMjd } from '../api/format';
import { DatasetTimeline } from '../three/DatasetTimeline';
import {
  ARC_HALF_WIDTH_SIGMA,
  CLOUD_POINTS,
  isLineOfSightOrbit,
  LINE_OF_SIGHT_LABEL,
  onThisDate,
  UNCERTAINTY_COLOR,
  variabilityTracks,
} from '../three/ephemerides';
import type { SystemScene } from '../three/SystemScene';
import { datasetBounds, datasetSpeed, datasetWindow, mjdToIsoDate, phaseStatus, phaseStatusLine } from '../three/spherexCoverage';
import {
  CLASS_TYPICAL_CHIP,
  COLOR_MODE_LABEL,
  COLOR_MODES,
  colorLegend,
  colourModeChip,
  DEFAULT_COLOR_MODE,
  isInfraredMode,
  surfaceLegend,
  type ColorMode,
} from '../three/colorModes';
import { nonFittedOrbits, ORBIT_COLOR, spinLegend, suggestedSpeed, type DistanceMode } from '../three/sceneLayout';

interface Props {
  system: SystemModel;
  selectedId: string | null;
  onSelect: (bodyId: string | null) => void;
}

/** 'load' = the three.js chunk did not download; 'webgl' = the browser could not create the 3D context. */
type ErrorKind = 'load' | 'webgl';

// Inline styles: styles.css belongs to WS5.
const CHIPS: CSSProperties = {
  position: 'absolute',
  top: 8,
  left: 8,
  right: 8,
  display: 'flex',
  flexWrap: 'wrap',
  gap: 6,
  pointerEvents: 'none',
  zIndex: 2,
};
const CHIP: CSSProperties = { background: 'rgba(3, 5, 10, 0.75)' };
const FALSE_CHIP: CSSProperties = { ...CHIP, color: '#f9a8d4' };
const ILLUSTRATIVE_CHIP: CSSProperties = { ...CHIP, color: 'var(--unconfirmed, #fbbf24)' };
const DATE_CHIP: CSSProperties = { ...CHIP, color: 'var(--accent, #7cc4ff)' };
const MODE_GROUP: CSSProperties = { display: 'inline-flex', flexWrap: 'wrap', gap: 4, alignItems: 'center' };
const P: CSSProperties = { margin: '0 0 4px' };
const LOS_HEX = '#7dd3fc'; // same colour as the arrow drawn by SystemScene

type TimeMode = 'free' | 'dataset';

/** Clock buttons sit inside a group span, so the transport's pill styles do not reach them: match them here. */
function clockButton(pressed: boolean): CSSProperties {
  return {
    minHeight: 34,
    padding: '5px 12px',
    borderRadius: 999,
    color: pressed ? 'var(--text, #e6e9f2)' : '#b8c7da',
    fontWeight: pressed ? 600 : 400,
    background: pressed ? 'rgba(124, 196, 255, 0.12)' : 'rgba(255, 255, 255, 0.035)',
    border: `1px solid ${pressed ? 'rgba(124, 196, 255, 0.55)' : 'rgba(184, 199, 218, 0.15)'}`,
  };
}

export function SystemViewer({ system, selectedId, onSelect }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const sceneRef = useRef<SystemScene | null>(null);
  const onSelectRef = useRef(onSelect);
  onSelectRef.current = onSelect;
  const selectedIdRef = useRef(selectedId);
  selectedIdRef.current = selectedId;

  const [status, setStatus] = useState<'loading' | 'ready' | 'error'>('loading');
  const [error, setError] = useState<{ kind: ErrorKind; message: string } | null>(null);
  const [mjd, setMjd] = useState<number | null>(null);
  const [startMjd, setStartMjd] = useState<number | null>(null);
  const [timeMode, setTimeMode] = useState<TimeMode>('free');
  // Frames of the system's field, only when the manifest lists that field (real targets: not built).
  const [frames, setFrames] = useState<Frame[] | null>(null);
  const phases = useMemo(() => phaseStatus(system), [system]);
  // Free-running phases are arbitrary for orbits without an epoch and for every variability.
  const arbitraryPhase = phases.arbitrary.length + phases.pulsationArbitrary.length + phases.pulsationPredicted.length > 0;
  const [playing, setPlaying] = useState(true);
  const [speedMul, setSpeedMul] = useState(1);
  const [distanceMode, setDistanceMode] = useState<DistanceMode>('compressed');
  const [showOrbits, setShowOrbits] = useState(true);
  const [showLabels, setShowLabels] = useState(true);
  const [colorMode, setColorMode] = useState<ColorMode>(DEFAULT_COLOR_MODE);
  const [classTypical, setClassTypical] = useState(false);

  // Create / destroy the scene when the system changes.
  useEffect(() => {
    let disposed = false;
    const fail = (kind: ErrorKind, e: unknown) => {
      if (disposed) return;
      setError({ kind, message: e instanceof Error ? e.message : String(e) });
      setStatus('error');
    };
    setStatus('loading');
    setError(null);
    import('../three/SystemScene').then(
      ({ SystemScene }) => {
        if (disposed || !containerRef.current) return;
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

  // A new system starts free-running; fetch its field's frames only when the manifest lists the field.
  useEffect(() => {
    let cancelled = false;
    setTimeMode('free');
    setFrames(null);
    const fieldId = system.field_id;
    if (fieldId) {
      client
        .getManifest()
        .then((m) => (m.fields.some((f) => f.id === fieldId) ? client.getField(fieldId) : null))
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
  }, [system]);

  const win = useMemo(() => datasetWindow(system, frames), [system, frames]);
  const bounds = useMemo(() => (win ? datasetBounds(win) : null), [win]);
  const dataset = timeMode === 'dataset' && win !== null;
  const tracks = useMemo(() => variabilityTracks(system), [system]);

  // Same pure function the scene uses (sceneLayout.ts), so the label and the animation agree. Dataset
  // time is capped so the whole window takes at least a minute (spherexCoverage.datasetSpeed).
  const freeSpeed = suggestedSpeed(system);
  const daysPerSec = (dataset && win ? datasetSpeed(freeSpeed, win) : freeSpeed) * speedMul;

  useEffect(() => sceneRef.current?.setDatasetMode(dataset, bounds), [dataset, bounds, status]);
  useEffect(() => sceneRef.current?.setPlaying(playing), [playing, status]);
  useEffect(() => sceneRef.current?.setSpeed(daysPerSec), [daysPerSec, status]);
  useEffect(
    () => sceneRef.current?.setOptions({ distanceMode, showOrbits, showLabels, colorMode, classTypical }),
    [distanceMode, showOrbits, showLabels, colorMode, classTypical, status],
  );
  useEffect(() => sceneRef.current?.focus(selectedId), [selectedId, status]);

  // The legends are static per system, mode and speed: build them once, not on every onTick re-render.
  const notFitted = useMemo(() => nonFittedOrbits(system.bodies), [system]);
  const colourLines = useMemo(() => colorLegend(colorMode, system), [colorMode, system]);
  const surfaceLines = useMemo(() => surfaceLegend(system, colorMode, classTypical), [system, colorMode, classTypical]);
  const spinLine = useMemo(() => spinLegend(system, daysPerSec), [system, daysPerSec]);
  const modeChip = colourModeChip(colorMode);
  const statusLine = useMemo(() => phaseStatusLine(system), [system]);
  const dateLines = dataset && mjd !== null ? onThisDate(system, mjd) : [];
  const cloudLegend = useMemo(() => datasetLegend(system), [system]);

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

  return (
    <div className="system-viewer">
      <div className="scene-stage" ref={containerRef} role="group" aria-label={`3D model of ${system.name}`}>
        <div style={CHIPS} aria-hidden="true">
          <span className="badge model" style={CHIP}>
            3D MODEL · NOT AN IMAGE
          </span>
          {modeChip && (
            <span className="badge" style={FALSE_CHIP}>
              {modeChip}
            </span>
          )}
          {classTypical && !system.provenance.synthetic && (
            <span className="badge" style={ILLUSTRATIVE_CHIP}>
              {CLASS_TYPICAL_CHIP}
            </span>
          )}
          {dataset && mjd !== null && (
            <span className="badge" style={DATE_CHIP}>
              DATASET TIME · {mjdToIsoDate(mjd)}
            </span>
          )}
        </div>
        {status === 'loading' && (
          <p className="scene-msg muted" role="status">
            Loading 3D view…
          </p>
        )}
        {status === 'error' && error?.kind === 'load' && (
          <div className="scene-msg error" role="alert">
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
          <p className="scene-msg error" role="alert">
            The 3D view could not start ({error.message}). Your browser may not support WebGL, or it is turned off.
          </p>
        )}
      </div>
      {dataset && win && mjd !== null && (
        <DatasetTimeline window={win} mjd={mjd} onSeek={(m) => sceneRef.current?.setTime(m)} tracks={tracks} />
      )}
      <div className="blink-controls">
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
        <span className="muted small">{formatDaysPerSecond(daysPerSec)}</span>
        <span role="group" aria-label="Clock" style={MODE_GROUP}>
          <button type="button" aria-pressed={timeMode === 'free'} onClick={() => chooseMode('free')} style={clockButton(timeMode === 'free')}>
            Free-running
          </button>
          <button
            type="button"
            aria-pressed={dataset}
            disabled={!win || status !== 'ready'}
            title={win ? 'Run the clock on the real SPHEREx pass dates of this target' : 'No SPHEREx coverage is known for this system'}
            onClick={() => chooseMode('dataset')}
            style={clockButton(dataset)}
          >
            Dataset time (SPHEREx 2025-2026)
          </button>
        </span>
        <label>
          Distances{' '}
          <select value={distanceMode} onChange={(e) => setDistanceMode(e.target.value as DistanceMode)}>
            <option value="compressed">compressed (log)</option>
            <option value="linear">true proportions</option>
          </select>
        </label>
        <label>
          Colour{' '}
          <select value={colorMode} onChange={(e) => setColorMode(e.target.value as ColorMode)}>
            {COLOR_MODES.map((m) => (
              <option key={m} value={m}>
                {COLOR_MODE_LABEL[m]}
              </option>
            ))}
          </select>
        </label>
        <label className="small">
          <input type="checkbox" checked={showOrbits} onChange={(e) => setShowOrbits(e.target.checked)} /> orbits
        </label>
        <label className="small">
          <input type="checkbox" checked={showLabels} onChange={(e) => setShowLabels(e.target.checked)} /> labels
        </label>
        {!system.provenance.synthetic && (
          <label className="small" title="Illustrative patterns typical of the object class; not observed on these bodies">
            <input type="checkbox" checked={classTypical} onChange={(e) => setClassTypical(e.target.checked)} /> show
            class-typical features (illustrative)
          </label>
        )}
        {selectedId && (
          <button type="button" onClick={() => onSelect(null)}>
            ⤢ Whole system
          </button>
        )}
      </div>
      <div className="muted small" aria-live="polite">
        {modeChip && isInfraredMode(colorMode) && (
          <p style={{ margin: '0 0 4px' }}>
            <strong style={{ color: '#f9a8d4' }}>{modeChip}</strong> (not what the eye would see, and not SPHEREx data).
          </p>
        )}
        {colourLines.map((line, i) => (
          <p key={`c${i}`} style={{ margin: '0 0 4px' }}>
            {line}
          </p>
        ))}
        {surfaceLines.map((line, i) => (
          <p key={`s${i}`} style={{ margin: '0 0 4px' }}>
            {line}
          </p>
        ))}
        <p style={{ margin: '0 0 4px' }}>{spinLine}</p>
      </div>
      {(notFitted.assumed.length > 0 || notFitted.hypothetical.length > 0) && (
        // Explained here too, not only inside the body panel: the whole-system view shows these orbits.
        <p className="muted small orbit-legend">
          {notFitted.assumed.length > 0 && (
            <span>
              <Swatch color={ORBIT_COLOR.assumed} /> Yellow orbit = assumed, not fitted:{' '}
              {notFitted.assumed.join(', ')}.{' '}
            </span>
          )}
          {notFitted.hypothetical.length > 0 && (
            <span>
              <Swatch color={ORBIT_COLOR.hypothetical} /> Violet orbit = hypothetical object:{' '}
              {notFitted.hypothetical.join(', ')}.{' '}
            </span>
          )}
          {notFitted.fitted && (
            <span>
              <Swatch color={ORBIT_COLOR.fitted} />{' '}
              {system.provenance.synthetic
                ? 'Blue-grey orbit = synthetic demo orbit (not a published solution).'
                : 'Blue-grey orbit = fitted orbit from the cited catalog or paper.'}
            </span>
          )}
        </p>
      )}
      {dataset && (
        <div className="muted small">
          {dateLines.length > 0 && (
            <>
              <p style={{ ...P, color: 'var(--text, #e6e9f2)' }}>
                <strong>On this date</strong>
              </p>
              <ul style={{ margin: '0 0 6px', paddingLeft: 18 }}>
                {dateLines.map((l) => (
                  <li key={`${l.bodyId}-${l.kind}`} style={{ margin: '0 0 2px' }}>
                    <strong>{l.name}</strong>: {l.text}
                    {l.source && <span style={{ opacity: 0.8 }}> ({l.source})</span>}
                  </li>
                ))}
              </ul>
            </>
          )}
          {cloudLegend.arc && (
            <p style={P}>
              <Dots color={UNCERTAINTY_COLOR.fitted} /> Arc: {CLOUD_POINTS} points over ±{ARC_HALF_WIDTH_SIGMA}σ of orbital phase on this
              date, from the published t0 and period (linear propagation; their covariance is not published and is ignored);
              opacity follows the Gaussian density. It widens as the date moves away from t0.
            </p>
          )}
          {cloudLegend.ring.length > 0 && (
            <p style={P}>
              {cloudLegend.ring.map((q) => (
                <Dots key={q} color={UNCERTAINTY_COLOR[q]} faint />
              ))}{' '}
              Ring: phase unknown (no published epoch), {CLOUD_POINTS} points uniform in time along the orbit (denser where the body
              moves slowly); the body is dimmed and labelled “phase unknown”. Dot colours follow the orbit colours.
            </p>
          )}
          {cloudLegend.lineOfSight && (
            <p style={P}>
              <Swatch color={LOS_HEX} /> Arrow: {LINE_OF_SIGHT_LABEL}. Each dated planet sits on it at its t0, read as the time of
              inferior conjunction; the sense of motion on the sky is unknown.
            </p>
          )}
        </div>
      )}
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
              : `${formatElapsed(mjd - startMjd)} (free-running${arbitraryPhase ? ', arbitrary starting phase' : ''}: not a prediction for a real date${win ? '; use Dataset time for the SPHEREx dates' : ''})`}
          </>
        )}{' '}
        · drag to rotate, scroll to zoom, click a body to enter it
      </p>
    </div>
  );
}

/** What the dataset-time legend has to explain for this system. */
function datasetLegend(system: SystemModel): { arc: boolean; ring: OrbitQuality[]; lineOfSight: boolean } {
  const orbiting = system.bodies.filter((b) => b.orbit && b.kind !== 'disk');
  const ring = [...new Set(orbiting.filter((b) => b.orbit!.epoch_mjd == null).map((b) => b.orbit!.quality ?? 'fitted'))];
  return {
    arc: orbiting.some((b) => b.orbit!.epoch_mjd != null),
    ring,
    lineOfSight: orbiting.some((b) => isLineOfSightOrbit(b.orbit!)),
  };
}

/** Three dots in a phase-cloud colour (legend). */
function Dots({ color, faint = false }: { color: string; faint?: boolean }) {
  return (
    <span aria-hidden="true" style={{ display: 'inline-flex', gap: 2, verticalAlign: 'middle', marginRight: 2 }}>
      {[0.4, 1, 0.4].map((o, i) => (
        <span key={i} style={{ width: 4, height: 4, borderRadius: '50%', background: color, opacity: faint ? 0.6 : o }} />
      ))}
    </span>
  );
}

function Swatch({ color }: { color: string }) {
  return (
    <span
      aria-hidden="true"
      style={{
        display: 'inline-block',
        width: 14,
        height: 0,
        borderTop: `3px solid ${color}`,
        verticalAlign: 'middle',
        marginRight: 2,
      }}
    />
  );
}

function formatDaysPerSecond(d: number): string {
  if (d < 1) return `${(d * 24).toFixed(1)} h per second`;
  if (d < 365.25) return `${d.toFixed(1)} days per second`;
  return `${(d / 365.25).toFixed(1)} years per second`;
}
