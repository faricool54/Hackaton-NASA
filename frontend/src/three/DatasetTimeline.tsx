// "Dataset time" timeline for the 3D gallery (work package M4): the real SPHEREx pass dates of one
// target on a calendar axis. React + SVG with inline styles only (styles.css belongs to WS5).
//
// - Archive passes (IRSA windows whose frames this dataset does not contain) are hatched and
//   captioned; frames this dataset does contain are solid ticks coloured by detector, and the
//   selected pass gets a date x wavelength strip (each LVF exposure samples a different wavelength
//   at the target, docs/RECON_SPHEREX.md 2.3).
// - A "today" marker at the query date says that no later data is in this dataset.
// - The axis is a keyboard slider (arrows +-1 d, Shift +-10 d, PageUp/PageDown +-30 d, Home/End);
//   "Pass N" buttons seek to the pass mid-date (onSeek) and then report the pass (onPass).
// SVG coordinates are real pixels (the width is measured), so text stays legible at 375 px.
import {
  useEffect,
  useId,
  useRef,
  useState,
  type CSSProperties,
  type KeyboardEvent as ReactKeyboardEvent,
  type PointerEvent as ReactPointerEvent,
} from 'react';
import { DETECTOR_BANDS, formatMjd } from '../api/format';
import {
  ARCHIVE_CAPTION,
  betweenVisits,
  dateTicks,
  DATASET_TODAY_MJD,
  mjdToIsoDate,
  nearestPass,
  passAt,
  TODAY_LABEL,
  timelineDomain,
  type CoveragePass,
  type DatasetWindow,
} from './spherexCoverage';

export interface DatasetTimelineProps {
  /** From datasetWindow(system, field?.frames). */
  window: DatasetWindow;
  /** Current scene time (MJD). */
  mjd: number;
  /** Set the scene clock (clicks and drags on the axis, keyboard, Pass buttons). */
  onSeek: (mjd: number) => void;
  /** Called after a "Pass N" button seeks to that pass's mid-date (0-based index). */
  onPass?: (index: number) => void;
  /** Accessible name; defaults to "SPHEREx coverage of <target>" (or "Synthetic frame dates of <id>"). */
  label?: string;
}

const C = {
  text: 'var(--text, #e6e9f2)',
  muted: 'var(--muted, #8e97ad)',
  border: 'var(--border, #232a3d)',
  accent: 'var(--accent, #7cc4ff)',
  today: 'var(--unconfirmed, #fbbf24)',
};
/** One colour per detector, short to long wavelength (D1 blue ... D6 red). */
const DETECTOR_COLORS: Record<number, string> = {
  1: '#8fb8ff',
  2: '#5fd4c4',
  3: '#a6dd6a',
  4: '#f5d061',
  5: '#f59e5b',
  6: '#f0706e',
};
const NO_DETECTOR = '#c8cedc';
const FONT = 11;
const PAD_X = 10;
/** Rough width of one character at 11 px (system-ui), to decide when the today label must wrap. */
const CHAR_PX = 6;

const S: Record<string, CSSProperties> = {
  root: { margin: '8px 0 12px', color: C.text, fontSize: '0.85rem', maxWidth: '100%' },
  svg: { display: 'block', width: '100%', overflow: 'visible', cursor: 'pointer', touchAction: 'pan-y', outline: 'none' },
  row: { display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: 6, margin: '6px 0' },
  muted: { color: C.muted, margin: '4px 0' },
  legend: { display: 'flex', flexWrap: 'wrap', gap: '4px 12px', color: C.muted, margin: '4px 0' },
  legendItem: { display: 'inline-flex', alignItems: 'center', gap: 4, minWidth: 0 },
  chip: { display: 'inline-flex', alignItems: 'center', gap: 4, whiteSpace: 'nowrap' },
};

function clamp(x: number, lo: number, hi: number): number {
  return Math.min(Math.max(x, lo), hi);
}

/** Width of an element in CSS pixels, kept up to date with ResizeObserver. */
function useWidth(fallback: number) {
  const ref = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(fallback);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const measure = () => {
      const w = Math.round(el.clientWidth);
      if (w > 0) setWidth(Math.max(w, 240));
    };
    measure();
    if (typeof ResizeObserver === 'undefined') return;
    const ro = new ResizeObserver(measure);
    ro.observe(el);
    return () => ro.disconnect();
  }, []);
  return [ref, width] as const;
}

/** Duration of a pass: exact for built frames, to the day (+-1 d) for archive windows. */
function duration(p: CoveragePass): string {
  const n = p.endMjd - p.startMjd;
  if (p.kind === 'archive') return `~${Math.max(1, Math.round(n))} d`;
  return n < 2 ? `${(n * 24).toFixed(1)} h` : `${Math.round(n)} d`;
}

/** Where `mjd` falls with respect to the passes, in words (status line and slider value text). */
function whereText(w: DatasetWindow, mjd: number): string {
  const i = passAt(w, mjd);
  if (i >= 0) {
    const p = w.passes[i];
    if (betweenVisits(p, mjd)) return `Pass ${i + 1}, between its visits: no frame of this target on this date`;
    if (p.frames.length > 0) {
      const n = p.frames.length;
      return `inside Pass ${i + 1}: ${n} ${w.synthetic ? 'synthetic ' : ''}frame${n === 1 ? '' : 's'} built in this dataset`;
    }
    return `inside Pass ${i + 1}: SPHEREx observed this target in this window (frames not built in this dataset)`;
  }
  const first = w.passes[0];
  const last = w.passes[w.passes.length - 1];
  if (first && mjd < first.startMjd) return 'before the first frame of this target';
  if (last && mjd > last.endMjd) return 'after the last frame of this target in this dataset';
  return 'between passes: no frame of this target on this date';
}

function passSummary(p: CoveragePass): string {
  const parts = [
    `Pass ${p.index + 1}`,
    p.datesApprox ? `~${p.dates[0]} → ~${p.dates[1]}` : `${p.dates[0]} → ${p.dates[1]}`,
    duration(p),
    `${p.nImages.toLocaleString('en')} image${p.nImages === 1 ? '' : 's'}`,
  ];
  if (p.nImagesLongWave !== null) parts.push(`${p.nImagesLongWave} at λ 3.9–5 µm`);
  if (p.detectors) parts.push(`detectors ${p.detectors.map((d) => `D${d}`).join(', ')}`);
  if (p.subVisits.length > 1) parts.push(`${p.subVisits.length} separate visits`);
  parts.push(
    p.frames.length === 0
      ? 'archive coverage'
      : p.kind === 'archive'
        ? `archive coverage, ${p.frames.length} frames built here`
        : 'frames built in this dataset',
  );
  return parts.join(' · ');
}

function Hatch({ id }: { id: string }) {
  return (
    <pattern id={id} width={6} height={6} patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
      <line x1={0} y1={0} x2={0} y2={6} style={{ stroke: C.muted, strokeWidth: 2, opacity: 0.75 }} />
    </pattern>
  );
}

function HatchSwatch({ id }: { id: string }) {
  return (
    <svg width={18} height={10} aria-hidden="true" style={{ display: 'block' }}>
      <defs>
        <Hatch id={id} />
      </defs>
      <rect x={0.5} y={0.5} width={17} height={9} fill={`url(#${id})`} style={{ stroke: C.muted, strokeWidth: 1 }} />
    </svg>
  );
}

function Dot({ color }: { color: string }) {
  return (
    <span
      aria-hidden="true"
      style={{ display: 'inline-block', width: 9, height: 9, borderRadius: '50%', background: color, flex: 'none' }}
    />
  );
}

export function DatasetTimeline({ window: win, mjd, onSeek, onPass, label }: DatasetTimelineProps) {
  const [wrapRef, width] = useWidth(640);
  const svgRef = useRef<SVGSVGElement>(null);
  const dragging = useRef(false);
  const [focused, setFocused] = useState(false);
  const [chosen, setChosen] = useState<number | null>(null);
  const uid = useId().replace(/[^a-zA-Z0-9_-]/g, '');
  const hatchId = `dt-hatch-${uid}`;

  const [lo, hi] = timelineDomain(win);
  const now = Number.isFinite(mjd) ? mjd : win.startMjd;
  const plotW = width - 2 * PAD_X;
  const x = (m: number) => PAD_X + ((clamp(m, lo, hi) - lo) / (hi - lo)) * plotW;
  const mjdAtX = (px: number) => lo + (clamp(px - PAD_X, 0, plotW) / plotW) * (hi - lo);

  // The pass the details refer to: the one under the cursor, else the last one picked, else the nearest.
  const under = passAt(win, now);
  const activeIndex = under >= 0 ? under : chosen !== null && chosen < win.passes.length ? chosen : nearestPass(win, now);
  const active = activeIndex >= 0 ? win.passes[activeIndex] : null;
  const anyUnbuilt = win.passes.some((p) => p.frames.length === 0);
  const anyArchive = win.passes.some((p) => p.kind === 'archive');

  // --- overview geometry (px) ---
  const todayWraps = TODAY_LABEL.length * CHAR_PX > plotW;
  const BAND_TOP = 24;
  const BAND_H = 22;
  const AXIS_Y = BAND_TOP + BAND_H + 6;
  const TICK_LABEL_Y = AXIS_Y + 15;
  const TODAY_Y = TICK_LABEL_Y + 16;
  const H = TODAY_Y + (todayWraps ? 14 : 0) + 4;
  const ticks = dateTicks(lo, hi, Math.max(2, Math.floor(plotW / 58)));
  const minorMonths = plotW / ((hi - lo) / 30.44) >= 6 ? dateTicks(lo, hi, Math.ceil((hi - lo) / 30.44) + 1) : [];
  const xToday = x(DATASET_TODAY_MJD);
  const xNow = x(now);
  const nowLabel = mjdToIsoDate(now);
  const nowAnchor = xNow < PAD_X + 34 ? 'start' : xNow > width - PAD_X - 34 ? 'end' : 'middle';

  // Seeking stops at the dataset start and at "today": the axis margins are not selectable dates.
  const seekLo = win.startMjd;
  const seekHi = Math.max(win.endMjd, DATASET_TODAY_MJD);
  const seekTo = (m: number) => onSeek(clamp(m, seekLo, seekHi));
  const seekFromPointer = (e: ReactPointerEvent<SVGSVGElement>) => {
    const svg = svgRef.current;
    if (!svg) return;
    const rect = svg.getBoundingClientRect();
    if (rect.width <= 0) return;
    seekTo(mjdAtX(((e.clientX - rect.left) / rect.width) * width));
  };
  const onPointerDown = (e: ReactPointerEvent<SVGSVGElement>) => {
    if (e.button !== 0) return;
    dragging.current = true;
    e.currentTarget.setPointerCapture?.(e.pointerId);
    seekFromPointer(e);
  };
  const onPointerMove = (e: ReactPointerEvent<SVGSVGElement>) => {
    if (dragging.current) seekFromPointer(e);
  };
  const endDrag = () => {
    dragging.current = false;
  };
  const onKeyDown = (e: ReactKeyboardEvent<SVGSVGElement>) => {
    const step = e.shiftKey ? 10 : 1;
    let next: number;
    switch (e.key) {
      case 'ArrowLeft':
      case 'ArrowDown':
        next = now - step;
        break;
      case 'ArrowRight':
      case 'ArrowUp':
        next = now + step;
        break;
      case 'PageDown':
        next = now - 30;
        break;
      case 'PageUp':
        next = now + 30;
        break;
      case 'Home':
        next = seekLo;
        break;
      case 'End':
        next = seekHi;
        break;
      default:
        return;
    }
    e.preventDefault();
    seekTo(next);
  };
  const jumpToPass = (p: CoveragePass) => {
    setChosen(p.index);
    onSeek(p.midMjd);
    onPass?.(p.index);
  };

  const name =
    label ??
    (win.target ? `SPHEREx coverage of ${win.target}` : `${win.synthetic ? 'Synthetic frame' : 'Frame'} dates of ${win.systemId}`);
  const legendText = !win.framesBuilt
    ? ARCHIVE_CAPTION
    : anyArchive && anyUnbuilt
      ? 'hatched: archive coverage (frames not built in this dataset) · ticks: frames built in this dataset'
      : 'ticks: frames built in this dataset, coloured by detector';

  return (
    <section ref={wrapRef} aria-label={name} style={S.root}>
      <svg
        ref={svgRef}
        role="slider"
        tabIndex={0}
        aria-label={`${name}: dataset date`}
        aria-valuemin={Math.round(seekLo * 10) / 10}
        aria-valuemax={Math.round(seekHi * 10) / 10}
        aria-valuenow={Math.round(clamp(now, seekLo, seekHi) * 10) / 10}
        aria-valuetext={`${nowLabel || 'no date'}, ${whereText(win, now)}`}
        aria-orientation="horizontal"
        width={width}
        height={H}
        viewBox={`0 0 ${width} ${H}`}
        style={{ ...S.svg, height: H }}
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={endDrag}
        onPointerCancel={endDrag}
        onLostPointerCapture={endDrag}
        onKeyDown={onKeyDown}
        onFocus={() => setFocused(true)}
        onBlur={() => setFocused(false)}
      >
        <defs>
          <Hatch id={hatchId} />
        </defs>
        {focused && (
          <rect
            x={1}
            y={1}
            width={width - 2}
            height={H - 2}
            rx={4}
            fill="none"
            style={{ stroke: C.accent, strokeWidth: 1.5, strokeDasharray: '4 3' }}
          />
        )}

        {/* No data after the last frame (up to the query date). */}
        {xToday > x(win.endMjd) + 1 && (
          <rect
            x={x(win.endMjd)}
            y={BAND_TOP}
            width={xToday - x(win.endMjd)}
            height={BAND_H}
            style={{ fill: C.muted, opacity: 0.08 }}
          />
        )}

        {/* Pass bands. */}
        {win.passes.map((p) => {
          const x0 = x(p.startMjd);
          const w = Math.max(x(p.endMjd) - x0, 2);
          const isActive = p.index === activeIndex;
          const stroke = { stroke: isActive ? C.accent : C.muted, strokeWidth: isActive ? 1.5 : 1 };
          return (
            <g key={p.index}>
              <title>{passSummary(p)}</title>
              {p.subVisits.length > 0 ? (
                <>
                  <rect x={x0} y={BAND_TOP} width={w} height={BAND_H} fill="none" style={{ ...stroke, opacity: 0.6 }} />
                  {p.subVisits.map((v, k) => (
                    <rect
                      key={k}
                      x={x(v.startMjd)}
                      y={BAND_TOP + 3}
                      width={Math.max(x(v.endMjd) - x(v.startMjd), 2)}
                      height={BAND_H - 6}
                      fill={`url(#${hatchId})`}
                    />
                  ))}
                </>
              ) : (
                <rect
                  x={x0}
                  y={BAND_TOP}
                  width={w}
                  height={BAND_H}
                  fill={p.kind === 'archive' ? `url(#${hatchId})` : 'none'}
                  style={stroke}
                />
              )}
              {p.frames.map((f, k) => (
                <line
                  key={f.id ?? k}
                  x1={x(f.mjd)}
                  x2={x(f.mjd)}
                  y1={BAND_TOP + 2}
                  y2={BAND_TOP + BAND_H - 2}
                  style={{ stroke: f.detector !== null ? (DETECTOR_COLORS[f.detector] ?? NO_DETECTOR) : NO_DETECTOR, strokeWidth: 1.5 }}
                />
              ))}
            </g>
          );
        })}

        {/* Axis with month ticks. */}
        <line x1={PAD_X} x2={width - PAD_X} y1={AXIS_Y} y2={AXIS_Y} style={{ stroke: C.muted, strokeWidth: 1 }} />
        {minorMonths.map((t) => (
          <line key={`m${t.mjd}`} x1={x(t.mjd)} x2={x(t.mjd)} y1={AXIS_Y} y2={AXIS_Y + 3} style={{ stroke: C.muted, opacity: 0.6 }} />
        ))}
        {ticks.map((t, k) => {
          const tx = x(t.mjd);
          const anchor = k === 0 && tx < PAD_X + 24 ? 'start' : 'middle';
          return (
            <g key={`t${t.mjd}`}>
              <line x1={tx} x2={tx} y1={AXIS_Y} y2={AXIS_Y + (t.major ? 7 : 5)} style={{ stroke: C.muted }} />
              <text
                x={tx}
                y={TICK_LABEL_Y}
                textAnchor={anchor}
                style={{ fill: t.major ? C.text : C.muted, fontSize: FONT, fontWeight: t.major ? 600 : 400 }}
              >
                {t.label}
              </text>
            </g>
          );
        })}

        {/* Today marker: nothing later is in this dataset. */}
        <line
          x1={xToday}
          x2={xToday}
          y1={BAND_TOP - 4}
          y2={AXIS_Y + 7}
          style={{ stroke: C.today, strokeWidth: 1.5, strokeDasharray: '3 2' }}
        />
        {todayWraps ? (
          <text x={xToday} y={TODAY_Y} textAnchor="end" style={{ fill: C.today, fontSize: FONT }}>
            <tspan x={xToday} dy={0}>
              {TODAY_LABEL.split(' · ')[0]}
            </tspan>
            <tspan x={xToday} dy={14}>
              {TODAY_LABEL.split(' · ')[1]}
            </tspan>
          </text>
        ) : (
          <text x={xToday} y={TODAY_Y} textAnchor="end" style={{ fill: C.today, fontSize: FONT }}>
            {TODAY_LABEL}
          </text>
        )}

        {/* Current time. */}
        <line x1={xNow} x2={xNow} y1={BAND_TOP - 3} y2={AXIS_Y} style={{ stroke: C.accent, strokeWidth: 2 }} />
        <path d={`M ${xNow - 5} ${BAND_TOP - 8} L ${xNow + 5} ${BAND_TOP - 8} L ${xNow} ${BAND_TOP - 2} Z`} style={{ fill: C.accent }} />
        {nowLabel && (
          <text x={xNow} y={BAND_TOP - 11} textAnchor={nowAnchor} style={{ fill: C.accent, fontSize: FONT, fontWeight: 600 }}>
            {nowLabel}
          </text>
        )}
      </svg>

      <p style={{ ...S.muted, color: C.text }}>
        {Number.isFinite(mjd) ? formatMjd(mjd) : '—'} · MJD {Number.isFinite(mjd) ? mjd.toFixed(2) : '—'} ·{' '}
        <span style={{ color: C.muted }}>{whereText(win, now)}</span>
      </p>

      {win.passes.length > 0 && (
        <div role="group" aria-label="Jump to a pass" style={S.row}>
          {win.passes.map((p) => {
            const isActive = p.index === activeIndex;
            return (
              <button
                key={p.index}
                type="button"
                aria-pressed={isActive}
                aria-label={`Jump to the middle of ${passSummary(p)}`}
                title={passSummary(p)}
                onClick={() => jumpToPass(p)}
                style={{
                  borderColor: isActive ? C.accent : undefined,
                  fontWeight: isActive ? 600 : 400,
                  minHeight: 32,
                }}
              >
                Pass {p.index + 1}
              </button>
            );
          })}
        </div>
      )}

      {active && (
        <>
          <p style={S.muted}>{passSummary(active)}</p>
          {active.note && <p style={{ ...S.muted, fontStyle: 'italic' }}>{active.note}</p>}
          {active.frames.length > 0 ? (
            <FrameStrip pass={active} mjd={now} width={width} synthetic={win.synthetic} />
          ) : (
            <p style={S.muted}>
              Per-frame dates and wavelengths are not in this dataset: only the archive window and counts are.
            </p>
          )}
        </>
      )}

      <div style={S.legend}>
        {anyArchive && (
          <span style={S.legendItem}>
            <span style={{ flex: 'none' }}>
              <HatchSwatch id={`${hatchId}-sw`} />
            </span>
            {legendText}
          </span>
        )}
        {!anyArchive && <span style={S.legendItem}>{legendText}</span>}
        {win.synthetic && win.framesBuilt && (
          <span style={{ ...S.legendItem, color: '#f472b6' }}>synthetic frames, not SPHEREx observations</span>
        )}
      </div>
      {win.note && <p style={S.muted}>{win.note}</p>}
      <p style={{ ...S.muted, fontSize: '0.78rem' }}>Source: {win.source}</p>
    </section>
  );
}

/** Date x wavelength strip of one pass's built frames, coloured by detector. */
function FrameStrip({ pass, mjd, width, synthetic }: { pass: CoveragePass; mjd: number; width: number; synthetic: boolean }) {
  const pad = { l: 34, r: 10, t: 8, b: 22 };
  const H = 132;
  const span = Math.max(pass.endMjd - pass.startMjd, 0);
  const margin = Math.max(span * 0.06, 2 / 24);
  const x0 = pass.startMjd - margin;
  const x1 = pass.endMjd + margin;
  const plotW = width - pad.l - pad.r;
  const plotH = H - pad.t - pad.b;
  const lam0 = 0.7;
  const lam1 = 5.1;
  const sx = (m: number) => pad.l + ((m - x0) / (x1 - x0)) * plotW;
  const sy = (l: number) => pad.t + (1 - (clamp(l, lam0, lam1) - lam0) / (lam1 - lam0)) * plotH;
  const ticks = dateTicks(x0, x1, Math.max(2, Math.floor(plotW / 64)));
  const detectors = [...new Set(pass.frames.map((f) => f.detector))].sort((a, b) => (a ?? 99) - (b ?? 99));
  const lambdas = pass.frames.map((f) => f.wavelengthUm).filter((l): l is number => l !== null);
  const range = lambdas.length ? `${Math.min(...lambdas).toFixed(2)}–${Math.max(...lambdas).toFixed(2)} µm` : 'no wavelengths recorded';
  const missing = pass.frames.length - lambdas.length;
  const showNow = mjd >= x0 && mjd <= x1;

  return (
    <figure style={{ margin: '6px 0' }}>
      <svg
        role="img"
        aria-label={`Pass ${pass.index + 1}: ${pass.frames.length} frames, local wavelength (${range}) versus date${synthetic ? ', synthetic' : ''}`}
        width={width}
        height={H}
        viewBox={`0 0 ${width} ${H}`}
        style={{ display: 'block', width: '100%', height: H }}
      >
        {[1, 2, 3, 4, 5].map((l) => (
          <g key={l}>
            <line x1={pad.l} x2={width - pad.r} y1={sy(l)} y2={sy(l)} style={{ stroke: C.border, strokeWidth: 1 }} />
            <text x={pad.l - 4} y={sy(l) + 4} textAnchor="end" style={{ fill: C.muted, fontSize: FONT }}>
              {l}
            </text>
          </g>
        ))}
        <text x={2} y={pad.t + 2} style={{ fill: C.muted, fontSize: FONT }}>
          µm
        </text>
        <line x1={pad.l} x2={width - pad.r} y1={H - pad.b} y2={H - pad.b} style={{ stroke: C.muted }} />
        {ticks.map((t) => (
          <g key={t.mjd}>
            <line x1={sx(t.mjd)} x2={sx(t.mjd)} y1={H - pad.b} y2={H - pad.b + 4} style={{ stroke: C.muted }} />
            <text x={sx(t.mjd)} y={H - pad.b + 15} textAnchor="middle" style={{ fill: C.muted, fontSize: FONT }}>
              {t.label}
            </text>
          </g>
        ))}
        {showNow && (
          <line x1={sx(mjd)} x2={sx(mjd)} y1={pad.t} y2={H - pad.b} style={{ stroke: C.accent, strokeWidth: 1.5 }} />
        )}
        {pass.frames.map((f, k) => {
          const color = f.detector !== null ? (DETECTOR_COLORS[f.detector] ?? NO_DETECTOR) : NO_DETECTOR;
          const cy = f.wavelengthUm !== null ? sy(f.wavelengthUm) : H - pad.b - 4;
          return (
            <circle
              key={f.id ?? k}
              cx={sx(f.mjd)}
              cy={cy}
              r={3.5}
              style={f.wavelengthUm !== null ? { fill: color } : { fill: 'none', stroke: color, strokeWidth: 1.5 }}
            >
              <title>
                {`${f.id ?? 'frame'} · ${formatMjd(f.mjd)} · ${f.detector !== null ? `D${f.detector}` : 'detector ?'} · ${
                  f.wavelengthUm !== null ? `${f.wavelengthUm.toFixed(3)} µm` : 'λ not recorded'
                }`}
              </title>
            </circle>
          );
        })}
      </svg>
      <figcaption style={{ color: C.muted }}>
        <span style={S.legend}>
          {detectors.map((d) => (
            <span key={d ?? 'none'} style={S.chip}>
              <Dot color={d !== null ? (DETECTOR_COLORS[d] ?? NO_DETECTOR) : NO_DETECTOR} />
              {d !== null ? `D${d}${DETECTOR_BANDS[d] ? ` ${DETECTOR_BANDS[d]}` : ''}` : 'detector not recorded'}
            </span>
          ))}
          {missing > 0 && <span style={S.legendItem}>hollow: wavelength not recorded ({missing})</span>}
        </span>
        <span style={{ display: 'block', margin: '2px 0' }}>
          Local wavelength at the target, per frame. Each exposure of the linear variable filter samples a different
          wavelength, so brightness changes between frames mix spectrum and variability.
        </span>
      </figcaption>
    </figure>
  );
}
