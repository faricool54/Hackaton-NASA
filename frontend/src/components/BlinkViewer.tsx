// Blink comparator (WS5, P0 — UI-2 scrubber redesign applied).
// All frames of a field share one north-up grid, so frame PNGs are stacked and
// toggled; overlays use an SVG whose viewBox is the grid size in pixels, so the
// contract's x/y (PNG convention) can be drawn directly.
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type { Candidate, Field, Frame, KnownObject } from '../api/types';
import { DETECTOR_BANDS, formatMjd } from '../api/format';

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

  // --- custom scrubber ---
  const trackRef = useRef<HTMLDivElement>(null);

  const seekToPointer = useCallback(
    (clientX: number) => {
      if (!trackRef.current || n < 2) return;
      const rect = trackRef.current.getBoundingClientRect();
      const ratio = Math.max(0, Math.min(1, (clientX - rect.left) / rect.width));
      setPlaying(false);
      setIndex(Math.round(ratio * (n - 1)));
    },
    [n],
  );

  const onTrackPointerDown = useCallback(
    (e: React.PointerEvent<HTMLDivElement>) => {
      e.currentTarget.setPointerCapture(e.pointerId);
      seekToPointer(e.clientX);
    },
    [seekToPointer],
  );

  const onTrackPointerMove = useCallback(
    (e: React.PointerEvent<HTMLDivElement>) => {
      if (e.buttons === 0) return;
      seekToPointer(e.clientX);
    },
    [seekToPointer],
  );

  const fillPct = n > 1 ? (index / (n - 1)) * 100 : 0;

  // tick positions (percent along track)
  const ticks = useMemo(
    () => (n <= 1 ? [] : Array.from({ length: n }, (_, i) => (i / (n - 1)) * 100)),
    [n],
  );

  const selected = useMemo(() => candidates.find((c) => c.id === selectedId) ?? null, [candidates, selectedId]);

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
          <strong>{formatMjd(current.mjd)}</strong> · D{current.detector}
          {current.wavelength_um ? ` · λ ${current.wavelength_um.toFixed(3)} µm` : ` · ${DETECTOR_BANDS[current.detector]}`}
        </div>
      </div>

      {/* Scrubber */}
      <div className="scrubber-wrap">
        <div
          className="scrubber-track-wrap"
          ref={trackRef}
          onPointerDown={onTrackPointerDown}
          onPointerMove={onTrackPointerMove}
          role="slider"
          aria-label="Frame"
          aria-valuemin={0}
          aria-valuemax={n - 1}
          aria-valuenow={index}
          tabIndex={0}
          onKeyDown={(e) => {
            if (e.key === 'ArrowRight') { e.preventDefault(); setIndex((i) => Math.min(i + 1, n - 1)); }
            if (e.key === 'ArrowLeft')  { e.preventDefault(); setIndex((i) => Math.max(i - 1, 0)); }
          }}
        >
          <div className="scrubber-track">
            <div className="scrubber-fill" style={{ width: `${fillPct}%` }} />
            <div className="scrubber-ticks">
              {ticks.map((pct, i) => (
                <div
                  key={i}
                  className={`scrubber-tick${i === index ? ' scrubber-tick--active' : ''}`}
                  style={{ left: `${pct}%` }}
                />
              ))}
            </div>
          </div>
          <div className="scrubber-thumb" style={{ left: `${fillPct}%` }} />
        </div>
      </div>

      {/* Playback controls */}
      <div className="blink-playback">
        <div className="blink-playback-btns">
          <button onClick={() => setIndex((i) => (i - 1 + n) % n)} aria-label="Previous frame">◀◀</button>
          <button onClick={() => setPlaying((p) => !p)} aria-label={playing ? 'Pause' : 'Play'}>
            {playing ? '❚❚' : '▶'}
          </button>
          <button onClick={() => setIndex((i) => (i + 1) % n)} aria-label="Next frame">▶▶</button>
        </div>
        <div className="blink-playback-secondary">
          <label>
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
          <label>
            <input type="checkbox" checked={showOverlays} onChange={(e) => setShowOverlays(e.target.checked)} /> markers
          </label>
        </div>
      </div>
      {/* TODO(WS5): difference-image layer, zoom/pan, crosshair with RA/Dec readout
          (use grid.wcs), "time-lapse" export as GIF/MP4, color composite of bands. */}
    </div>
  );
}
