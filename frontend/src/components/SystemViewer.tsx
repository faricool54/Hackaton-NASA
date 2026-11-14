// 3D viewer for a SystemModel. three.js is loaded on demand (dynamic import) so the
// blink viewer and the rest of the site stay light.
import { useEffect, useRef, useState } from 'react';
import type { SystemModel } from '../api/types';
import { formatMjd } from '../api/format';
import type { DistanceMode, SystemScene } from '../three/SystemScene';

interface Props {
  system: SystemModel;
  selectedId: string | null;
  onSelect: (bodyId: string | null) => void;
}

const SPEED_STEPS = [0.25, 0.5, 1, 2, 4, 8];

export function SystemViewer({ system, selectedId, onSelect }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const sceneRef = useRef<SystemScene | null>(null);
  const baseSpeedRef = useRef(1);
  const onSelectRef = useRef(onSelect);
  onSelectRef.current = onSelect;

  const [status, setStatus] = useState<'loading' | 'ready' | 'error'>('loading');
  const [error, setError] = useState<string | null>(null);
  const [mjd, setMjd] = useState<number | null>(null);
  const [playing, setPlaying] = useState(true);
  const [speedMul, setSpeedMul] = useState(1);
  const [distanceMode, setDistanceMode] = useState<DistanceMode>('compressed');
  const [showOrbits, setShowOrbits] = useState(true);
  const [showLabels, setShowLabels] = useState(true);

  // Create / destroy the scene when the system changes.
  useEffect(() => {
    let disposed = false;
    setStatus('loading');
    import('../three/SystemScene')
      .then(({ SystemScene, suggestedSpeed }) => {
        if (disposed || !containerRef.current) return;
        const scene = new SystemScene(containerRef.current, system, {
          onSelect: (id) => onSelectRef.current(id),
          onTick: setMjd,
        });
        baseSpeedRef.current = suggestedSpeed(system);
        sceneRef.current = scene;
        setStatus('ready');
      })
      .catch((e: Error) => {
        if (disposed) return;
        setError(e.message);
        setStatus('error');
      });
    return () => {
      disposed = true;
      sceneRef.current?.dispose();
      sceneRef.current = null;
    };
  }, [system]);

  useEffect(() => sceneRef.current?.setPlaying(playing), [playing, status]);
  useEffect(() => sceneRef.current?.setSpeed(baseSpeedRef.current * speedMul), [speedMul, status]);
  useEffect(
    () => sceneRef.current?.setOptions({ distanceMode, showOrbits, showLabels }),
    [distanceMode, showOrbits, showLabels, status],
  );
  useEffect(() => sceneRef.current?.focus(selectedId), [selectedId, status]);

  const daysPerSec = baseSpeedRef.current * speedMul;

  return (
    <div className="system-viewer">
      <div className="scene-stage" ref={containerRef} role="img" aria-label={`3D model of ${system.name}`}>
        {status === 'loading' && <p className="scene-msg muted">Loading 3D view…</p>}
        {status === 'error' && (
          <p className="scene-msg error">
            The 3D view could not start ({error}). Your browser may not support WebGL.
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
        <label className="small">
          <input type="checkbox" checked={showOrbits} onChange={(e) => setShowOrbits(e.target.checked)} /> orbits
        </label>
        <label className="small">
          <input type="checkbox" checked={showLabels} onChange={(e) => setShowLabels(e.target.checked)} /> labels
        </label>
        {selectedId && (
          <button type="button" onClick={() => onSelect(null)}>
            ⤢ Whole system
          </button>
        )}
      </div>
      <p className="muted small">
        Model time: {mjd !== null ? formatMjd(mjd) : '—'} · drag to rotate, scroll to zoom, click a body to enter it
      </p>
    </div>
  );
}

function formatDaysPerSecond(d: number): string {
  if (d < 1) return `${(d * 24).toFixed(1)} h per second`;
  if (d < 365.25) return `${d.toFixed(1)} days per second`;
  return `${(d / 365.25).toFixed(1)} years per second`;
}
