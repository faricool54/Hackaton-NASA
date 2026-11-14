// Blink comparator (WS5, P0 — basic version implemented, improve freely).
// All frames of a field share one north-up grid, so frame PNGs are stacked and
// toggled; overlays use an SVG whose viewBox is the grid size in pixels, so the
// contract's x/y (PNG convention) can be drawn directly.
import { useEffect, useMemo, useState } from 'react';
import type { Candidate, Field, Frame, KnownObject } from '../api/types';
import { DETECTOR_BANDS, formatDuration, formatMjd } from '../api/format';

interface Props {
  field: Field;
  frames: Frame[];
  imageUrl: (frame: Frame) => string;
  candidates: Candidate[];
  known: KnownObject[];
  selectedId: string | null;
  onSelect: (id: string | null) => void;
}

const STATUS_COLOR: Record<string, string> = {
  known: 'var(--known)',
  unconfirmed: 'var(--unconfirmed)',
  artifact: 'var(--artifact)',
  injected: 'var(--injected)',
};

export function BlinkViewer({ field, frames, imageUrl, candidates, known, selectedId, onSelect }: Props) {
  const [index, setIndex] = useState(0);
  const [playing, setPlaying] = useState(true);
  const [intervalMs, setIntervalMs] = useState(700);
  const [showOverlays, setShowOverlays] = useState(true);

  const n = frames.length;
  const current = frames[Math.min(index, n - 1)];

  useEffect(() => setIndex(0), [frames]);

  useEffect(() => {
    if (!playing || n < 2) return;
    const t = setInterval(() => setIndex((i) => (i + 1) % n), intervalMs);
    return () => clearInterval(t);
  }, [playing, intervalMs, n]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.target as HTMLElement)?.tagName === 'INPUT') return;
      if (e.key === ' ') {
        e.preventDefault();
        setPlaying((p) => !p);
      } else if (e.key === 'ArrowRight') setIndex((i) => (i + 1) % n);
      else if (e.key === 'ArrowLeft') setIndex((i) => (i - 1 + n) % n);
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [n]);

  const selected = useMemo(() => candidates.find((c) => c.id === selectedId) ?? null, [candidates, selectedId]);
  const t0 = frames[0]?.mjd ?? 0;

  if (!current) return <div className="panel">This field has no frames.</div>;
  const { width_px: w, height_px: h } = field.grid;
  const r = Math.max(2.5, w / 40);

  return (
    <div className="blink">
      <div className="blink-stage" style={{ aspectRatio: `${w} / ${h}` }}>
        {frames.map((f, i) => (
          <img
            key={f.id}
            src={imageUrl(f)}
            alt={`SPHEREx frame ${f.id}`}
            className="blink-frame"
            style={{ visibility: i === index ? 'visible' : 'hidden' }}
            draggable={false}
          />
        ))}
        {showOverlays && (
          <svg className="blink-overlay" viewBox={`0 0 ${w} ${h}`} preserveAspectRatio="none">
            {selected && (
              <polyline
                points={selected.detections.map((d) => `${d.x + 0.5},${d.y + 0.5}`).join(' ')}
                className="track"
              />
            )}
            {candidates.map((c) =>
              c.detections
                .filter((d) => d.frame_id === current.id)
                .map((d) => (
                  <circle
                    key={`${c.id}-${d.frame_id}`}
                    cx={d.x + 0.5}
                    cy={d.y + 0.5}
                    r={c.id === selectedId ? r * 1.4 : r}
                    stroke={STATUS_COLOR[c.status]}
                    className="marker"
                    onClick={() => onSelect(c.id)}
                  >
                    <title>{`${c.id} (${c.status})`}</title>
                  </circle>
                )),
            )}
            {known.map((k) =>
              k.positions
                .filter((p) => p.frame_id === current.id && p.in_frame)
                .map((p) => (
                  <rect
                    key={`${k.designation}-${p.frame_id}`}
                    x={p.x + 0.5 - r * 0.7}
                    y={p.y + 0.5 - r * 0.7}
                    width={r * 1.4}
                    height={r * 1.4}
                    className="known-marker"
                  >
                    <title>{`Known: ${k.designation}`}</title>
                  </rect>
                )),
            )}
          </svg>
        )}
        <div className="blink-caption">
          <strong>{formatMjd(current.mjd)}</strong> · +{formatDuration((current.mjd - t0) * 24)} · D{current.detector}
          {current.wavelength_um ? ` · λ ${current.wavelength_um.toFixed(3)} µm` : ` · ${DETECTOR_BANDS[current.detector]}`}
        </div>
      </div>

      <div className="blink-controls">
        <button onClick={() => setIndex((i) => (i - 1 + n) % n)} aria-label="Previous frame">◀</button>
        <button onClick={() => setPlaying((p) => !p)} aria-label={playing ? 'Pause' : 'Play'}>
          {playing ? '❚❚' : '▶'}
        </button>
        <button onClick={() => setIndex((i) => (i + 1) % n)} aria-label="Next frame">▶▶</button>
        <input
          type="range"
          min={0}
          max={n - 1}
          value={index}
          onChange={(e) => {
            setPlaying(false);
            setIndex(Number(e.target.value));
          }}
          aria-label="Frame"
        />
        <span className="muted">
          {index + 1}/{n}
        </span>
        <label className="muted">
          speed
          <input
            type="range"
            min={150}
            max={2000}
            step={50}
            value={2150 - intervalMs}
            onChange={(e) => setIntervalMs(2150 - Number(e.target.value))}
            aria-label="Blink speed"
          />
        </label>
        <label className="muted">
          <input type="checkbox" checked={showOverlays} onChange={(e) => setShowOverlays(e.target.checked)} /> markers
        </label>
      </div>
      {/* TODO(WS5): difference-image layer, zoom/pan, crosshair with RA/Dec readout
          (use grid.wcs), "time-lapse" export as GIF/MP4, color composite of bands. */}
    </div>
  );
}
