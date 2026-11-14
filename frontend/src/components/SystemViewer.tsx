// 3D viewer for a SystemModel. three.js is loaded on demand (dynamic import) so the
// blink viewer and the rest of the site stay light. Everything imported statically here
// (sceneLayout, colorModes) is pure and three-free.
import { useEffect, useRef, useState, type CSSProperties } from 'react';
import type { SystemModel } from '../api/types';
import { formatElapsed, formatMjd } from '../api/format';
import type { SystemScene } from '../three/SystemScene';
import {
  CLASS_TYPICAL_CHIP,
  COLOR_MODE_LABEL,
  colorLegend,
  DEFAULT_COLOR_MODE,
  FALSE_COLOUR_CHIP,
  surfaceLegend,
  type ColorMode,
} from '../three/colorModes';
import { nonFittedOrbits, ORBIT_COLOR, spinLegend, suggestedSpeed, type DistanceMode } from '../three/sceneLayout';

interface Props {
  system: SystemModel;
  selectedId: string | null;
  onSelect: (bodyId: string | null) => void;
}

const SPEED_STEPS = [0.25, 0.5, 1, 2, 4, 8];

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
  // Phases without an epoch (and all variability) are arbitrary: show elapsed time, not a calendar date.
  const arbitraryPhase = system.bodies.some(
    (b) => (b.orbit && b.orbit.epoch_mjd == null) || (b.variability?.period_days ?? 0) > 0,
  );
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

  // Same pure function the scene uses (sceneLayout.ts), so the label and the animation agree.
  const daysPerSec = suggestedSpeed(system) * speedMul;

  useEffect(() => sceneRef.current?.setPlaying(playing), [playing, status]);
  useEffect(() => sceneRef.current?.setSpeed(daysPerSec), [daysPerSec, status]);
  useEffect(
    () => sceneRef.current?.setOptions({ distanceMode, showOrbits, showLabels, colorMode, classTypical }),
    [distanceMode, showOrbits, showLabels, colorMode, classTypical, status],
  );
  useEffect(() => sceneRef.current?.focus(selectedId), [selectedId, status]);

  const notFitted = nonFittedOrbits(system.bodies);
  const colourLines = colorLegend(colorMode, system);
  const surfaceLines = surfaceLegend(system, colorMode, classTypical);

  return (
    <div className="system-viewer">
      <div className="scene-stage" ref={containerRef} role="group" aria-label={`3D model of ${system.name}`}>
        <div style={CHIPS} aria-hidden="true">
          <span className="badge model" style={CHIP}>
            3D MODEL · NOT AN IMAGE
          </span>
          {colorMode === 'ir' && (
            <span className="badge" style={FALSE_CHIP}>
              {FALSE_COLOUR_CHIP}
            </span>
          )}
          {classTypical && !system.provenance.synthetic && (
            <span className="badge" style={ILLUSTRATIVE_CHIP}>
              {CLASS_TYPICAL_CHIP}
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
      <div className="blink-controls">
        <button type="button" onClick={() => setPlaying((p) => !p)} aria-label={playing ? 'Pause' : 'Play'}>
          {playing ? '❚❚ Pause' : '▶ Play'}
        </button>
        <label>
          Speed{' '}
          <select value={speedMul} onChange={(e) => setSpeedMul(Number(e.target.value))}>
            {SPEED_STEPS.map((s) => (
              <option key={s} value={s}>
                ×{s}
              </option>
            ))}
          </select>
        </label>
        <span className="muted small">{formatDaysPerSecond(daysPerSec)}</span>
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
            <option value="ir">{COLOR_MODE_LABEL.ir}</option>
            <option value="visible">{COLOR_MODE_LABEL.visible}</option>
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
        {colorMode === 'ir' && (
          <p style={{ margin: '0 0 4px' }}>
            <strong style={{ color: '#f9a8d4' }}>{FALSE_COLOUR_CHIP}</strong> (not what the eye would see).
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
        <p style={{ margin: '0 0 4px' }}>{spinLegend(system, daysPerSec)}</p>
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
      <p className="muted small">
        Model time:{' '}
        {mjd === null
          ? '—'
          : arbitraryPhase && startMjd !== null
            ? `${formatElapsed(mjd - startMjd)} (arbitrary starting phase, not a prediction for a real date)`
            : formatMjd(mjd)}{' '}
        · drag to rotate, scroll to zoom, click a body to enter it
      </p>
    </div>
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
