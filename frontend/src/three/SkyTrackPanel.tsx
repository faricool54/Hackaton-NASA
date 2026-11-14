// "Where SPHEREx should see it" (work package S4): the predicted sky track of a system over the
// SPHEREx dataset, on the 6.15″ pixel scale, with one dot per pass. A 2D panel, React + SVG with
// inline styles only (styles.css belongs to WS5). All numbers come from skyTrack.ts (unit-tested);
// this file only draws them. SVG coordinates are real pixels (the width is measured), so the text
// stays legible at 375 px.
import { useEffect, useId, useMemo, useRef, useState, type CSSProperties } from 'react';
import type { SystemModel } from '../api/types';
import {
  buildSkyTrack,
  formatArcsec,
  formatPlace,
  formatPx,
  gridValues,
  plotLayout,
  SKY_TRACK_BADGE,
  SKY_TRACK_CAPTION,
  SKY_TRACK_TITLE,
  SPHEREX_PIXEL_ARCSEC,
  trackPointAt,
  RECON_VALIDATION,
  type Offset,
  type PlotLayout,
  type PlotMode,
  type SkyTrack,
  type TrackMark,
  type TrackPoint,
} from './skyTrack';
import { mjdToIsoDate } from './spherexCoverage';

export interface SkyTrackPanelProps {
  system: SystemModel;
  /** Current dataset date of the 3D view (MJD), when it shows one: drawn as a ring on the track. */
  mjd?: number | null;
}

const C = {
  text: 'var(--text, #e6e9f2)',
  muted: 'var(--muted, #8e97ad)',
  border: 'var(--border, #232a3d)',
  accent: 'var(--accent, #7cc4ff)',
  today: 'var(--unconfirmed, #fbbf24)',
  bg: 'var(--bg, #07090f)',
  marker: '#f9a8d4',
};
const FONT = 11;
const TIER_LABEL: Readonly<Record<string, string>> = {
  measured: 'MEASURED',
  derived: 'DERIVED',
  model: 'MODEL',
  display: 'DISPLAY',
};
const TIER_COLOR: Readonly<Record<string, string>> = {
  derived: 'var(--known, #4ade80)',
  model: 'var(--unconfirmed, #fbbf24)',
  display: C.muted,
};

const S: Record<string, CSSProperties> = {
  // Same card look as the other SystemPage panels (SystemPage.tsx infoPanelStyle).
  root: {
    color: C.text,
    padding: 18,
    borderRadius: 16,
    background:
      'radial-gradient(ellipse at 100% 0%, rgba(124, 196, 255, 0.08), transparent 48%), linear-gradient(155deg, #121a2a, #0d111c 76%)',
    boxShadow: '0 14px 36px rgba(0, 0, 0, 0.18)',
  },
  h3: { margin: '0 0 4px', display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: 6 },
  badge: { color: C.today, fontSize: '0.66rem' },
  caption: { margin: '0 0 6px', fontWeight: 600 },
  muted: { color: C.muted, margin: '4px 0' },
  row: { display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: 6, margin: '6px 0' },
  svg: { display: 'block', width: '100%', borderRadius: 6 },
  legend: { display: 'flex', flexWrap: 'wrap', gap: '2px 12px', color: C.muted, margin: '4px 0', fontSize: '0.78rem' },
  legendItem: { display: 'inline-flex', alignItems: 'center', gap: 4 },
  list: { listStyle: 'none', padding: 0, margin: '6px 0' },
  passBtn: {
    display: 'block',
    width: '100%',
    textAlign: 'left',
    padding: '6px 8px',
    margin: '0 0 4px',
    minHeight: 32,
    background: 'transparent',
    color: C.text,
    border: `1px solid ${C.border}`,
    borderRadius: 6,
    font: 'inherit',
    cursor: 'pointer',
    overflowWrap: 'anywhere',
  },
  chip: { display: 'inline-block', fontSize: '0.66rem', fontWeight: 700, border: '1px solid currentColor', borderRadius: 999, padding: '0 6px', marginRight: 4 },
  small: { fontSize: '0.78rem', color: C.muted, margin: '4px 0', overflowWrap: 'anywhere' },
};
const HALO: CSSProperties = { paintOrder: 'stroke', stroke: C.bg, strokeWidth: 3, strokeLinejoin: 'round' };

/** Width of an element in CSS pixels, kept up to date with ResizeObserver. */
function useWidth(fallback: number) {
  const ref = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(fallback);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const measure = () => {
      const w = Math.round(el.clientWidth);
      if (w > 0) setWidth(Math.max(w, 200));
    };
    measure();
    if (typeof ResizeObserver === 'undefined') return;
    const ro = new ResizeObserver(measure);
    ro.observe(el);
    return () => ro.disconnect();
  }, []);
  return [ref, width] as const;
}

const signedPx = (arcsec: number) => {
  const px = Math.round((arcsec / SPHEREX_PIXEL_ARCSEC) * 100) / 100;
  return px === 0 ? '0' : `${px > 0 ? '+' : '−'}${Math.abs(px)}`;
};
const signedArcsec = (arcsec: number) => (Math.abs(arcsec) < 1e-12 ? '0' : `${arcsec > 0 ? '+' : '−'}${formatArcsec(Math.abs(arcsec))}`);
const both = (arcsec: number) => `${formatArcsec(arcsec)} (${formatPx(arcsec)})`;
/** Short label for grid lines and the scale bar: "5″", "0.5″", "20 mas". */
const compactArcsec = (arcsec: number) => {
  const a = Math.abs(arcsec);
  return a < 0.1 ? `${Number((arcsec * 1000).toPrecision(3))} mas` : `${Number(arcsec.toPrecision(3))}″`;
};

function markWindow(m: TrackMark): string {
  const a = m.datesApprox ? '~' : '';
  return m.dates[0] === m.dates[1] ? `${a}${m.dates[0]}` : `${a}${m.dates[0]} → ${a}${m.dates[1]}`;
}

/** Largest 1-2-5 length (arcsec) whose bar is at most `maxPx` long on screen. */
function scaleBarArcsec(scale: number, maxPx: number): number {
  let best = 0.001;
  for (let e = -3; e <= 3; e++) {
    for (const f of [1, 2, 5]) {
      const v = f * 10 ** e;
      if (v * scale <= maxPx) best = v;
    }
  }
  return best;
}

export function SkyTrackPanel({ system, mjd }: SkyTrackPanelProps) {
  const track = useMemo(() => buildSkyTrack(system), [system]);
  const [mode, setMode] = useState<PlotMode>('pixels');
  const [selected, setSelected] = useState<number | null>(null);
  const [wrapRef, width] = useWidth(320);
  const headingId = useId();

  if (!track) {
    return (
      <section className="panel small" aria-labelledby={headingId} style={S.root}>
        <h3 id={headingId} style={S.h3}>
          {SKY_TRACK_TITLE}
        </h3>
        <p style={S.muted}>
          No sky track: this system's catalog motion lacks a parallax, a proper motion or a readable epoch, so its position
          on SPHEREx dates cannot be predicted.
        </p>
      </section>
    );
  }

  const datePoint = mjd != null && Number.isFinite(mjd) ? trackPointAt(track, mjd) : null;
  const sel = selected !== null && selected < track.marks.length ? track.marks[selected] : null;
  const first = track.marks[0];
  const last = track.marks[track.marks.length - 1];
  const a = track.astrometry;

  return (
    <section className="panel small" aria-labelledby={headingId} style={S.root}>
      <h3 id={headingId} style={S.h3}>
        <span>{SKY_TRACK_TITLE}</span>
        <span className="badge" style={S.badge}>
          {SKY_TRACK_BADGE}
        </span>
      </h3>
      <p style={S.caption}>{SKY_TRACK_CAPTION}.</p>
      <p style={S.muted}>
        Tracks {a.target}. Offsets from the {track.reference.label}: {formatPlace(track.reference)} (ICRS, as seen from
        the Earth).
      </p>

      <div role="group" aria-label="Plot scale" style={S.row}>
        {(
          [
            ['pixels', 'SPHEREx pixel grid'],
            ['fit', 'Zoom to the track'],
          ] as const
        ).map(([m, label]) => (
          <button
            key={m}
            type="button"
            aria-pressed={mode === m}
            onClick={() => setMode(m)}
            style={{ minHeight: 32, borderColor: mode === m ? C.accent : undefined, fontWeight: mode === m ? 600 : 400 }}
          >
            {label}
          </button>
        ))}
      </div>

      <div ref={wrapRef}>
        <TrackPlot track={track} width={width} mode={mode} selected={selected} datePoint={datePoint} />
      </div>

      <div style={S.legend} aria-hidden="true">
        <span style={S.legendItem}>
          <svg width={18} height={8}>
            <line x1={1} x2={17} y1={4} y2={4} style={{ stroke: C.muted, strokeWidth: 1.5 }} />
          </svg>
          predicted track {mjdToIsoDate(track.startMjd)} → {mjdToIsoDate(track.endMjd)}
        </span>
        {track.marks.length > 0 && (
          <span style={S.legendItem}>
            <svg width={18} height={10}>
              <line x1={2} x2={16} y1={5} y2={5} style={{ stroke: C.accent, strokeWidth: 5, opacity: 0.75, strokeLinecap: 'round' }} />
              <circle cx={9} cy={5} r={3.5} style={{ fill: C.accent }} />
            </svg>
            SPHEREx pass (window and middle)
          </span>
        )}
        <span style={S.legendItem}>○ start {mjdToIsoDate(track.startMjd)}</span>
        <span style={{ ...S.legendItem, color: C.today }}>◆ today: no later data in this dataset</span>
        {datePoint && <span style={{ ...S.legendItem, color: C.marker }}>◯ date of the 3D view</span>}
        {track.staticSources.length > 0 && <span style={S.legendItem}>✕ static field star</span>}
      </div>
      <p style={S.small}>
        {mode === 'pixels'
          ? `Grid: ${SPHEREX_PIXEL_ARCSEC}″ SPHEREx pixels east (numbers along the bottom; east is left) and north (left side) of the reference place. Display alignment only: every real frame has its own pixel phase and orientation.`
          : 'Zoomed on the track: grid numbers are arcsec or mas east (bottom; east is left) and north (left side) of the reference place, not pixels.'}{' '}
        North up, east left.
      </p>

      <Summary track={track} datePoint={datePoint} />

      {track.marks.length > 0 && (
        <>
          <p style={{ ...S.muted, margin: '8px 0 2px' }}>Predicted place in each pass (select one to highlight it):</p>
          <ol style={S.list} aria-label="Predicted place per SPHEREx pass">
            {track.marks.map((m, i) => (
              <li key={m.label}>
                <button
                  type="button"
                  aria-pressed={selected === i}
                  onClick={() => setSelected(selected === i ? null : i)}
                  style={{ ...S.passBtn, borderColor: selected === i ? C.accent : C.border }}
                >
                  <strong>Pass {m.label}</strong> · {markWindow(m)} · {m.nImages.toLocaleString('en')} image
                  {m.nImages === 1 ? '' : 's'}
                  <br />
                  <span style={{ color: C.muted }}>
                    middle {mjdToIsoDate(m.mjd)}: {formatPlace(m.position)}
                    <br />
                    {i === 0
                      ? 'reference place (offset 0)'
                      : `${both(m.shiftFromPreviousArcsec ?? 0)} from Pass ${track.marks[i - 1].label}${
                          i > 1 ? ` · ${both(m.shiftFromFirstArcsec)} from Pass ${first.label}` : ''
                        }`}
                    {' · '}drifts {both(m.driftArcsec)} during the window
                  </span>
                </button>
              </li>
            ))}
          </ol>
          {sel && (
            <p style={S.small}>
              Pass {sel.label}: {signedArcsec(sel.position.east)} east, {signedArcsec(sel.position.north)} north of the
              reference ({signedPx(sel.position.east)} px, {signedPx(sel.position.north)} px).
            </p>
          )}
        </>
      )}
      {track.marks.length === 0 && (
        <p style={S.muted}>No SPHEREx pass table for this system: only the track over the dataset window is drawn.</p>
      )}
      {track.marks.length > 1 && last && (
        <p style={S.small}>
          Pass {first.label} → Pass {last.label}: {both(track.totalShiftArcsec)}.
        </p>
      )}

      <details style={{ margin: '6px 0 0' }}>
        <summary style={{ cursor: 'pointer' }}>How this is computed</summary>
        <ul style={{ ...S.list, margin: '6px 0' }}>
          {track.tiers.map((t) => (
            <li key={t.label} style={{ margin: '0 0 6px' }}>
              <span style={{ ...S.chip, color: TIER_COLOR[t.tier] ?? C.muted }}>{TIER_LABEL[t.tier] ?? t.tier.toUpperCase()}</span>
              <strong>{t.label}:</strong> <span style={{ color: C.muted }}>{t.text}</span>
            </li>
          ))}
          <li style={{ margin: '0 0 6px', color: C.muted }}>
            Checked against {RECON_VALIDATION}: Barnard's Star and Epsilon Indi B on 2026.0 agree within 0.01″ (unit-tested).
          </li>
        </ul>
        {a.notes.length > 0 && (
          <ul style={{ margin: '4px 0', paddingLeft: 18, color: C.muted }}>
            {a.notes.map((n, i) => (
              <li key={i}>{n}</li>
            ))}
          </ul>
        )}
        {track.coverageSource && <p style={S.small}>Pass windows: {track.coverageSource}.</p>}
      </details>
    </section>
  );
}

function Summary({ track, datePoint }: { track: SkyTrack; datePoint: TrackPoint | null }) {
  const beta = track.eclipticLatitudeDeg;
  return (
    <div style={{ margin: '6px 0' }}>
      {track.staticAtPixelScale ? (
        <p style={S.muted}>
          <strong style={{ color: C.text }}>Static at SPHEREx resolution:</strong> the whole track spans{' '}
          {both(track.spanArcsec)}. Use "Zoom to the track" to see its shape.
        </p>
      ) : (
        <p style={S.muted}>
          Moves {formatArcsec(track.pmArcsecPerYr)} = {track.pmPxPerYr.toFixed(2)} px per year toward position angle{' '}
          {track.pmPositionAngleDeg.toFixed(1)}° (north through east).
        </p>
      )}
      <p style={S.muted}>
        Annual parallax {formatArcsec(track.parallaxArcsec)} ({formatPx(track.parallaxArcsec)}): a yearly ellipse with
        semi-axes {formatArcsec(track.parallaxArcsec)} × {formatArcsec(track.parallaxMinorArcsec)} (ecliptic latitude{' '}
        {beta >= 0 ? '+' : '−'}
        {Math.abs(beta).toFixed(1)}°).
      </p>
      {track.staticSources.map((s) => (
        <p key={s.name} style={S.muted}>
          Closest to {s.name} ({s.note}): {both(s.closest.separationArcsec)} around {mjdToIsoDate(s.closest.mjd)}.
        </p>
      ))}
      {datePoint && (
        <p style={{ ...S.muted, color: C.marker }}>
          On {mjdToIsoDate(datePoint.mjd)} (date of the 3D view): {formatPlace(datePoint)}, {signedArcsec(datePoint.east)} east
          and {signedArcsec(datePoint.north)} north of the reference.
        </p>
      )}
    </div>
  );
}

function pathOf(points: readonly Offset[], sx: (o: Offset) => number, sy: (o: Offset) => number): string {
  return points.map((p, i) => `${i ? 'L' : 'M'} ${sx(p).toFixed(1)} ${sy(p).toFixed(1)}`).join(' ');
}

function gridLabel(v: number, l: PlotLayout): string {
  if (l.gridInPixels) return signedPx(v);
  return Math.abs(v) < 1e-12 ? '0' : `${v > 0 ? '+' : '−'}${compactArcsec(Math.abs(v))}`;
}

function TrackPlot({
  track,
  width,
  mode,
  selected,
  datePoint,
}: {
  track: SkyTrack;
  width: number;
  mode: PlotMode;
  selected: number | null;
  datePoint: TrackPoint | null;
}) {
  const clipId = `sky-clip-${useId().replace(/[^a-zA-Z0-9_-]/g, '')}`;
  const near = track.staticSources.filter((s) => s.closest.separationArcsec < 20);
  const extentPoints: Offset[] = [...track.samples, ...near, ...(datePoint ? [datePoint] : [])];
  const l = plotLayout(extentPoints, width, mode);
  const sx = (o: Offset) => l.width / 2 - (o.east - l.centerEast) * l.scale;
  const sy = (o: Offset) => l.height / 2 - (o.north - l.centerNorth) * l.scale;
  const H = l.height;
  const W = l.width;

  const eastLines = gridValues(l.east[0], l.east[1], l.gridStepArcsec);
  const northLines = gridValues(l.north[0], l.north[1], l.gridStepArcsec);
  const spacing = l.gridStepArcsec * l.scale;
  const labelEvery = spacing >= 26 ? 1 : spacing >= 13 ? 2 : 5;
  const showLabel = (v: number) => Math.round(v / l.gridStepArcsec) % labelEvery === 0;

  // Marks closer together on screen than a label are drawn once ("Passes 1-3").
  const markSpanPx =
    track.marks.length > 1
      ? Math.max(...track.marks.map((m) => Math.hypot(sx(m.position) - sx(track.marks[0].position), sy(m.position) - sy(track.marks[0].position))))
      : 0;
  const collapsed = track.marks.length > 1 && markSpanPx < 12;
  const bar = scaleBarArcsec(l.scale, Math.min(110, W * 0.35));

  const summary = `${SKY_TRACK_TITLE}: predicted track of ${track.astrometry.target}, ${track.marks.length} SPHEREx pass${
    track.marks.length === 1 ? '' : 'es'
  }, ${track.staticAtPixelScale ? `static at SPHEREx resolution (span ${formatArcsec(track.spanArcsec)})` : `${formatPx(track.totalShiftArcsec)} from the first to the last pass`}. ${SKY_TRACK_CAPTION}.`;

  return (
    <svg role="img" aria-label={summary} width={W} height={H} viewBox={`0 0 ${W} ${H}`} style={{ ...S.svg, height: H, background: C.bg }}>
      <defs>
        <clipPath id={clipId}>
          <rect x={0} y={0} width={W} height={H} />
        </clipPath>
      </defs>
      <g clipPath={`url(#${clipId})`}>
        {/* Grid: SPHEREx pixels (or a 1-2-5 arcsec grid when zoomed). */}
        {eastLines.map((v) => (
          <line
            key={`e${v}`}
            x1={sx({ east: v, north: 0 })}
            x2={sx({ east: v, north: 0 })}
            y1={0}
            y2={H}
            style={{ stroke: C.border, strokeWidth: Math.abs(v) < 1e-9 ? 1.5 : 1 }}
          />
        ))}
        {northLines.map((v) => (
          <line
            key={`n${v}`}
            x1={0}
            x2={W}
            y1={sy({ east: 0, north: v })}
            y2={sy({ east: 0, north: v })}
            style={{ stroke: C.border, strokeWidth: Math.abs(v) < 1e-9 ? 1.5 : 1 }}
          />
        ))}
        {eastLines.filter((v) => showLabel(v) && sx({ east: v, north: 0 }) > 22).map((v) => (
          <text key={`el${v}`} x={sx({ east: v, north: 0 }) + 2} y={H - 4} style={{ fill: C.muted, fontSize: FONT - 1, ...HALO }}>
            {gridLabel(v, l)}
          </text>
        ))}
        {northLines.filter((v) => showLabel(v) && sy({ east: 0, north: v }) < H - 18 && sy({ east: 0, north: v }) > 12).map((v) => (
          <text key={`nl${v}`} x={3} y={sy({ east: 0, north: v }) - 3} style={{ fill: C.muted, fontSize: FONT - 1, ...HALO }}>
            {gridLabel(v, l)}
          </text>
        ))}

        {/* Track over the whole dataset window. */}
        <path d={pathOf(track.samples, sx, sy)} fill="none" style={{ stroke: C.muted, strokeWidth: 1.5, strokeLinejoin: 'round' }} />

        {/* Pass windows. */}
        {track.marks.map((m, i) => (
          <path
            key={`seg${m.label}`}
            d={pathOf(m.segment, sx, sy)}
            fill="none"
            style={{
              stroke: C.accent,
              strokeWidth: selected === i ? 7 : 5,
              opacity: selected === null || selected === i ? 0.75 : 0.35,
              strokeLinecap: 'round',
              strokeLinejoin: 'round',
            }}
          />
        ))}

        {/* Static field stars. */}
        {near.map((s) => {
          const x = sx(s);
          const y = sy(s);
          return (
            <g key={s.name}>
              <title>{`${s.name} (static): ${s.note}. ${s.source}`}</title>
              <path d={`M ${x - 4} ${y - 4} L ${x + 4} ${y + 4} M ${x - 4} ${y + 4} L ${x + 4} ${y - 4}`} style={{ stroke: C.text, strokeWidth: 1.5 }} />
              <text x={x + 6} y={y + 12} style={{ fill: C.muted, fontSize: FONT - 1, ...HALO }}>
                static star
              </text>
            </g>
          );
        })}

        {/* Start of the dataset and "today". */}
        <circle cx={sx(track.start)} cy={sy(track.start)} r={3} style={{ fill: C.bg, stroke: C.muted, strokeWidth: 1.5 }}>
          <title>{`Start of the track: ${mjdToIsoDate(track.start.mjd)} (first SPHEREx DR1 frames)`}</title>
        </circle>
        <path
          d={`M ${sx(track.end)} ${sy(track.end) - 5} L ${sx(track.end) + 5} ${sy(track.end)} L ${sx(track.end)} ${sy(track.end) + 5} L ${sx(track.end) - 5} ${sy(track.end)} Z`}
          style={{ fill: C.today }}
        >
          <title>{`today ${mjdToIsoDate(track.end.mjd)}: no later data in this dataset`}</title>
        </path>

        {/* One dot per pass. */}
        {track.marks.map((m, i) => {
          const x = sx(m.position);
          const y = sy(m.position);
          const isSel = selected === i;
          const showText = collapsed ? i === 0 : true;
          const text = collapsed ? `Passes ${track.marks[0].label}–${track.marks[track.marks.length - 1].label}` : m.label;
          const right = x < W - 70;
          return (
            <g key={`dot${m.label}`}>
              <title>{`Pass ${m.label}, ${markWindow(m)}: predicted ${formatPlace(m.position)} at ${mjdToIsoDate(m.mjd)}`}</title>
              <circle cx={x} cy={y} r={isSel ? 6.5 : 4.5} style={{ fill: C.accent, stroke: isSel ? C.text : C.bg, strokeWidth: 1.5 }} />
              {showText && (
                <text
                  x={right ? x + 8 : x - 8}
                  y={y + (i % 2 === 0 ? -6 : 14)}
                  textAnchor={right ? 'start' : 'end'}
                  style={{ fill: C.accent, fontSize: FONT, fontWeight: 600, ...HALO }}
                >
                  {text}
                </text>
              )}
            </g>
          );
        })}

        {/* Date of the 3D view. */}
        {datePoint && (
          <g>
            <title>{`${mjdToIsoDate(datePoint.mjd)}: predicted ${formatPlace(datePoint)}`}</title>
            <circle cx={sx(datePoint)} cy={sy(datePoint)} r={8} fill="none" style={{ stroke: C.marker, strokeWidth: 2 }} />
          </g>
        )}
      </g>

      {/* Compass: north up, east left. */}
      <g transform={`translate(${W - 42}, 8)`} aria-hidden="true">
        <line x1={20} x2={20} y1={22} y2={4} style={{ stroke: C.text, strokeWidth: 1.5 }} />
        <path d="M 20 0 L 16.5 6 L 23.5 6 Z" style={{ fill: C.text }} />
        <line x1={20} x2={4} y1={22} y2={22} style={{ stroke: C.text, strokeWidth: 1.5 }} />
        <path d="M 0 22 L 6 18.5 L 6 25.5 Z" style={{ fill: C.text }} />
        <text x={24} y={10} style={{ fill: C.text, fontSize: FONT, ...HALO }}>
          N
        </text>
        <text x={0} y={36} style={{ fill: C.text, fontSize: FONT, ...HALO }}>
          E
        </text>
      </g>

      {/* Scale bar. */}
      <g transform={`translate(${W - 12 - bar * l.scale}, ${H - 22})`} aria-hidden="true">
        <line x1={0} x2={bar * l.scale} y1={0} y2={0} style={{ stroke: C.text, strokeWidth: 2 }} />
        <text x={(bar * l.scale) / 2} y={-4} textAnchor="middle" style={{ fill: C.text, fontSize: FONT - 1, ...HALO }}>
          {compactArcsec(bar)}
        </text>
      </g>
      <rect x={0.5} y={0.5} width={W - 1} height={H - 1} rx={6} fill="none" style={{ stroke: C.border }} />
    </svg>
  );
}
