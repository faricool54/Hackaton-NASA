import { useEffect, useRef, type KeyboardEvent as ReactKeyboardEvent, type PointerEvent, type ReactNode } from 'react';
import '../styles/sheet.css';

/** Heights of the sheet: peek (a strip at the bottom), half and full (the whole container). */
export const SHEET_SNAPS = ['peek', 'half', 'full'] as const;
export type SheetSnap = (typeof SHEET_SNAPS)[number];

/** A tap on the handle cycles peek → half → full → peek. */
export function nextSnap(snap: SheetSnap): SheetSnap {
  return SHEET_SNAPS[(SHEET_SNAPS.indexOf(snap) + 1) % SHEET_SNAPS.length];
}

/** One step up (ArrowUp) or down (ArrowDown) from the current height, stopping at full and peek. */
export function stepSnap(snap: SheetSnap, direction: 1 | -1): SheetSnap {
  const index = Math.min(SHEET_SNAPS.length - 1, Math.max(0, SHEET_SNAPS.indexOf(snap) + direction));
  return SHEET_SNAPS[index];
}

/** A click this soon after a drag ended is the drag's own release, not a tap. */
const CLICK_AFTER_DRAG_MS = 400;

/** px/ms: a release faster than this moves one step in the drag direction, wherever the sheet is. */
export const FLICK_SPEED = 0.5;

/**
 * Where a drag ends. `fraction` is the share of the container the sheet covers on release and `velocity` the last
 * pointer speed in px/ms (positive = upwards). A flick moves one step from where the drag started; a slow release
 * goes to the nearest height (peek is about a quarter of a phone, half 50 %, full 100 %).
 */
export function snapAfterDrag(start: SheetSnap, fraction: number, velocity: number): SheetSnap {
  if (velocity > FLICK_SPEED) return stepSnap(start, 1);
  if (velocity < -FLICK_SPEED) return stepSnap(start, -1);
  return fraction < 0.36 ? 'peek' : fraction < 0.75 ? 'half' : 'full';
}

/**
 * Esc lowers an open sheet to peek. It is the last in the Esc order (popup > theater > sheet, FRONTEND_PLAN FE-11):
 * a key that something above already took (defaultPrevented) is left alone.
 */
export function snapAfterKey(key: string, snap: SheetSnap, defaultPrevented: boolean): SheetSnap | null {
  return key === 'Escape' && !defaultPrevented && snap !== 'peek' ? 'peek' : null;
}

const HANDLE_ACTION: Record<SheetSnap, (label: string) => string> = {
  peek: (label) => `Expand ${label}`,
  half: (label) => `Expand ${label} to full height`,
  full: (label) => `Collapse ${label}`,
};

interface Props {
  /** Names the sheet for assistive technology, e.g. "position details". */
  label: string;
  snap: SheetSnap;
  onSnapChange: (snap: SheetSnap) => void;
  children: ReactNode;
}

interface Drag {
  pointer: number;
  startY: number;
  startHeight: number;
  lastY: number;
  lastTime: number;
  velocity: number;
  moved: boolean;
}

/**
 * A bottom sheet for phones (FE-10). It covers the bottom of its positioned container and never hides or unmounts
 * what is under it (the map iframe stays, FRONTEND_PLAN §4.8). Drag the handle or tap it to change height; Esc or ×
 * lower it to peek. It does not touch the browser history: the explorer already uses replaceState for its shared
 * link and the router is hash based.
 */
export function BottomSheet({ label, snap, onSnapChange, children }: Props) {
  const root = useRef<HTMLElement>(null);
  const body = useRef<HTMLDivElement>(null);
  const handle = useRef<HTMLButtonElement>(null);
  const drag = useRef<Drag | null>(null);
  // When the last drag ended: the click that a mouse drag fires on release must not also cycle the height.
  const draggedAt = useRef(-Infinity);
  const latest = useRef({ snap, onSnapChange });
  latest.current = { snap, onSnapChange };

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      const next = snapAfterKey(event.key, latest.current.snap, event.defaultPrevented);
      if (!next) return;
      event.preventDefault();
      latest.current.onSnapChange(next);
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, []);

  // Lowered to peek, the content shows its beginning again (its first lines are what the peek is for).
  useEffect(() => {
    if (snap !== 'peek' || !body.current) return;
    for (const element of [body.current, ...Array.from(body.current.children)]) element.scrollTop = 0;
  }, [snap]);

  const containerHeight = (sheet: HTMLElement) => sheet.parentElement?.clientHeight || window.innerHeight;

  const onPointerDown = (event: PointerEvent<HTMLButtonElement>) => {
    if (event.button !== 0 || !root.current) return;
    event.currentTarget.setPointerCapture?.(event.pointerId);
    drag.current = {
      pointer: event.pointerId, startY: event.clientY, startHeight: root.current.getBoundingClientRect().height,
      lastY: event.clientY, lastTime: event.timeStamp, velocity: 0, moved: false,
    };
  };

  const onPointerMove = (event: PointerEvent<HTMLButtonElement>) => {
    const current = drag.current;
    const sheet = root.current;
    if (!current || current.pointer !== event.pointerId || !sheet) return;
    const rise = current.startY - event.clientY;
    if (!current.moved && Math.abs(rise) < 6) return;
    current.moved = true;
    const elapsed = event.timeStamp - current.lastTime;
    if (elapsed > 0) current.velocity = (current.lastY - event.clientY) / elapsed;
    current.lastY = event.clientY;
    current.lastTime = event.timeStamp;
    const height = Math.max(48, Math.min(containerHeight(sheet), current.startHeight + rise));
    sheet.dataset.dragging = '';
    sheet.style.height = `${height}px`;
  };

  const endDrag = (event: PointerEvent<HTMLButtonElement>, cancelled: boolean) => {
    const current = drag.current;
    const sheet = root.current;
    if (!current || current.pointer !== event.pointerId) return;
    drag.current = null;
    if (!sheet || !current.moved) return;
    draggedAt.current = event.timeStamp;
    const fraction = sheet.getBoundingClientRect().height / containerHeight(sheet);
    // A pointer that rested before the release is not a flick.
    const velocity = event.timeStamp - current.lastTime > 120 ? 0 : current.velocity;
    delete sheet.dataset.dragging;
    sheet.style.height = '';
    const next = cancelled ? snap : snapAfterDrag(snap, fraction, velocity);
    if (next !== snap) onSnapChange(next);
  };

  const onHandleKey = (event: ReactKeyboardEvent<HTMLButtonElement>) => {
    if (event.key !== 'ArrowUp' && event.key !== 'ArrowDown') return;
    event.preventDefault();
    const next = stepSnap(snap, event.key === 'ArrowUp' ? 1 : -1);
    if (next !== snap) onSnapChange(next);
  };

  return <section ref={root} className="sh-root" data-snap={snap} aria-label={label}>
    <div className="sh-bar">
      <button ref={handle} type="button" className="sh-handle" aria-label={HANDLE_ACTION[snap](label)}
        aria-expanded={snap !== 'peek'} onPointerDown={onPointerDown} onPointerMove={onPointerMove}
        onPointerUp={(event) => endDrag(event, false)} onPointerCancel={(event) => endDrag(event, true)}
        onKeyDown={onHandleKey}
        onClick={(event) => {
          if (event.timeStamp - draggedAt.current < CLICK_AFTER_DRAG_MS) return;
          onSnapChange(nextSnap(snap));
        }}>
        <span className="sh-grip" aria-hidden="true" />
      </button>
      {snap !== 'peek' && <button type="button" className="sh-close" aria-label={`Collapse ${label}`}
        onClick={() => {
          // × disappears at peek: the focus moves to the handle instead of falling back to the page.
          handle.current?.focus();
          onSnapChange('peek');
        }}><span aria-hidden="true">×</span></button>}
    </div>
    <div ref={body} className="sh-body">{children}</div>
  </section>;
}
