// Blink comparator (WS5, P0 — UI-2 scrubber redesign applied).
// All frames of a field share one north-up grid, so frame PNGs are stacked and
// toggled; overlays use an SVG whose viewBox is the grid size in pixels, so the
// contract's x/y (PNG convention) can be drawn directly. In the color modes the
// same stage blinks one false-color composite per season (same grid, no markers).
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type { Candidate, Composite, Field, Frame, KnownObject } from '../api/types';
import { DETECTOR_BANDS, formatMjd } from '../api/format';
import { channelLegend, seasonRange } from './blinkModes';

interface Props {
  field: Field;
  frames: Frame[];
  /** Color modes: season composites to blink instead of the frames. */
  composites?: Composite[] | null;
  imageUrl: (image: string) => string; // PNG path relative to the field dir
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

export function BlinkViewer({ field, frames, composites, imageUrl, candidates, known, selectedId, onSelect }: Props) {
  const [index, setIndex] = useState(0);
  const [playing, setPlaying] = useState(true);
  const [intervalMs, setIntervalMs] = useState(700);
  const [showOverlays, setShowOverlays] = useState(true);
  const [loaded, setLoaded] = useState<Record<string, 'ready' | 'error'>>({});
  const [retry, setRetry] = useState(0);

  const stack: (Frame | Composite)[] = composites ?? frames;
  const n = stack.length;
  // The stack can shrink before the reset effect runs (new field, filter or mode): never index past it.
  const shown = Math.min(index, Math.max(n - 1, 0));
  const current: Frame | undefined = composites ? undefined : frames[shown];
  const composite = composites?.[shown];
  const failed = stack.filter((f) => loaded[f.id] === 'error').length;
  const remaining = stack.filter((f) => !loaded[f.id]).length;

  useEffect(() => setIndex(0), [frames, composites]);

  useEffect(() => {
    if (!playing || n < 2 || remaining || failed) return;
    const t = setInterval(() => setIndex((i) => (i + 1) % n), intervalMs);
    return () => clearInterval(t);
  }, [playing, intervalMs, n, remaining, failed]);

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

  const fillPct = n > 1 ? (shown / (n - 1)) * 100 : 0;

  // tick positions (percent along track)
  const ticks = useMemo(
    () => (n <= 1 ? [] : Array.from({ length: n }, (_, i) => (i / (n - 1)) * 100)),
    [n],
  );

  const selected = useMemo(() => candidates.find((c) => c.id === selectedId) ?? null, [candidates, selectedId]);

  if (composites && !composite) return <div className="panel">No false-color composites for this mode.</div>;
  if (!current && !composite) return <div className="panel">This field has no frames.</div>;
  const { width_px: w, height_px: h } = field.grid;
  const r = Math.max(2.5, w / 40);
  const stepDate = composite ? seasonRange(composite) : current ? formatMjd(current.mjd) : '';

  return (
    <div className="blink" tabIndex={0} aria-label="Time sequence player" onKeyDown={(e) => {
      const target = e.target as HTMLElement;
      if (target.closest('input, select, textarea, button, [contenteditable="true"], [role="slider"]')) return;
      if (e.key === ' ') { e.preventDefault(); setPlaying((p) => !p); }
      else if (e.key === 'ArrowRight') { e.preventDefault(); setPlaying(false); setIndex((i) => (i + 1) % n); }
      else if (e.key === 'ArrowLeft') { e.preventDefault(); setPlaying(false); setIndex((i) => (i - 1 + n) % n); }
    }}>
      {remaining > 0 && <p role="status" className="muted small">Loading sequence images… {n - remaining}/{n}</p>}
      {failed > 0 && <p role="alert" className="error">{failed} image(s) could not load. Playback is paused.
        {' '}<button onClick={() => { setLoaded({}); setRetry((r) => r + 1); }}>Retry images</button></p>}
      <div className="blink-stage" style={{ aspectRatio: `${w} / ${h}` }}>
        {stack.map((f, i) => (
          <img
            key={`${f.id}/${retry}`}
            src={`${imageUrl(f.image)}${retry ? `?retry=${retry}` : ''}`}
            alt={composites ? `False-color infrared composite ${f.id}` : `SPHEREx frame ${f.id}`}
            className="blink-frame"
            style={{ visibility: i === shown ? 'visible' : 'hidden' }}
            draggable={false}
            onLoad={() => setLoaded((s) => ({ ...s, [f.id]: 'ready' }))}
            onError={() => setLoaded((s) => ({ ...s, [f.id]: 'error' }))}
          />
        ))}
        {showOverlays && current && (
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
          {composite ? (
            <>
              <strong>{stepDate}</strong> · <span title={composite.notes.join('\n')}>False color (infrared)</span> ·{' '}
              {channelLegend(composite)}
              {loaded[composite.id] === 'error' && ' · IMAGE UNAVAILABLE'}
            </>
          ) : (
            current && (
              <>
                <strong>{stepDate}</strong> · D{current.detector}
                {current.wavelength_um ? ` · λ ${current.wavelength_um.toFixed(3)} µm` : ` · ${DETECTOR_BANDS[current.detector]}`}
                {' · '}{current.release.toUpperCase()}
                {loaded[current.id] === 'error' && ' · IMAGE UNAVAILABLE'}
              </>
            )
          )}
        </div>
      </div>

      {/* Scrubber */}
      <div className="scrubber-wrap">
        <div className="scrubber-meta">
          <span className="scrubber-date">{stepDate}</span>
          <span className="scrubber-count">{composite ? 'SEASON' : 'FRAME'} {String(shown + 1).padStart(2, '0')} <span>/ {String(n).padStart(2, '0')}</span></span>
        </div>
        <div
          className="scrubber-track-wrap"
          ref={trackRef}
          onPointerDown={onTrackPointerDown}
          onPointerMove={onTrackPointerMove}
          role="slider"
          aria-label={composite ? 'Season' : 'Frame'}
          aria-valuemin={0}
          aria-valuemax={n - 1}
          aria-valuenow={shown}
          tabIndex={0}
          onKeyDown={(e) => {
            if (e.key === 'ArrowRight') { e.preventDefault(); setPlaying(false); setIndex((i) => Math.min(i + 1, n - 1)); }
            if (e.key === 'ArrowLeft')  { e.preventDefault(); setPlaying(false); setIndex((i) => Math.max(i - 1, 0)); }
          }}
        >
          <div className="scrubber-track">
            <div className="scrubber-fill" style={{ width: `${fillPct}%` }} />
            <div className="scrubber-ticks">
              {ticks.map((pct, i) => (
                <div
                  key={i}
                  className={`scrubber-tick${i === shown ? ' scrubber-tick--active' : ''}`}
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
          <button className="transport-btn" onClick={() => { setPlaying(false); setIndex((i) => Math.max(0, i - 1)); }} aria-label="Previous frame" title="Previous frame">
            <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 5v14M19 6l-9 6 9 6V6Z" /></svg>
          </button>
          <button className="transport-btn transport-btn--primary" onClick={() => setPlaying((p) => !p)} aria-label={playing ? 'Pause' : 'Play'} title={playing ? 'Pause playback' : 'Play sequence'}>
            {playing ? <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M8 5v14M16 5v14" /></svg> : <svg viewBox="0 0 24 24" aria-hidden="true"><path d="m8 5 12 7-12 7V5Z" /></svg>}
          </button>
          <button className="transport-btn" onClick={() => { setPlaying(false); setIndex((i) => Math.min(n - 1, i + 1)); }} aria-label="Next frame" title="Next frame">
            <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M18 5v14M5 6l9 6-9 6V6Z" /></svg>
          </button>
        </div>
        <div className="blink-playback-secondary">
          <label className="speed-control">
            <span>Playback speed</span>
            <input
              type="range"
              min={150}
              max={2000}
              step={50}
              value={2150 - intervalMs}
              onChange={(e) => setIntervalMs(2150 - Number(e.target.value))}
              aria-label="Blink speed"
            />
            <span className="speed-value">{(1000 / intervalMs).toFixed(1)}×</span>
          </label>
          <button
            className={`overlay-toggle${showOverlays ? ' is-on' : ''}`}
            type="button"
            aria-pressed={showOverlays}
            disabled={!current}
            title={current ? undefined : 'Markers are drawn on the B/W frames only'}
            onClick={() => setShowOverlays((shown) => !shown)}
          >
            <span className="toggle-indicator" aria-hidden="true" />
            Markers
          </button>
        </div>
      </div>
      {/* TODO(WS5): difference-image layer, zoom/pan, crosshair with RA/Dec readout
          (use grid.wcs), "time-lapse" export as GIF/MP4. */}
    </div>
  );
}
