import { useEffect, useId, useRef, useState, type KeyboardEvent as ReactKeyboardEvent } from 'react';
import { createPortal } from 'react-dom';
import { useShortcut } from './useShortcuts';
import '../styles/shortcuts.css';

interface Key {
  /** What the key cap shows. */
  cap: string;
  /** What a screen reader says when the cap is a symbol. */
  spoken?: string;
}

export interface ShortcutRow {
  keys: Key[];
  action: string;
}

/**
 * Every shortcut the explorer answers today. This list only documents them: `/` is SkySearch's (FE-3), `1`–`4` the
 * dock's, Space and the arrows the Time player's, Esc each layer's own handler, and `?` this component's.
 */
export const SHORTCUTS: readonly ShortcutRow[] = [
  { keys: [{ cap: '/' }], action: 'Focus the sky search' },
  {
    keys: [{ cap: '1' }, { cap: '2' }, { cap: '3' }, { cap: '4' }],
    action: 'Open the Object, Time, Spectrum or 3D tab of the details panel',
  },
  { keys: [{ cap: 'Space' }], action: 'Play or pause the Time sequence (when the player has the focus)' },
  {
    keys: [{ cap: '←', spoken: 'Left arrow' }, { cap: '→', spoken: 'Right arrow' }],
    action: 'Previous or next frame in the Time player (when the player has the focus)',
  },
  { keys: [{ cap: 'Esc' }], action: 'Close this dialog, an open map menu or the pinned map card' },
  { keys: [{ cap: '?' }], action: 'Show this help' },
];

function KeyCap({ cap, spoken }: Key) {
  return <kbd className="kb-key">{spoken ? <><span aria-hidden="true">{cap}</span><span className="u-sr-only">{spoken}</span></> : cap}</kbd>;
}

/** The dialog body, without the portal (server-rendered in tests). */
export function ShortcutsList() {
  return <>
    <dl className="kb-list">
      {SHORTCUTS.map((row) => <div className="kb-row" key={row.action}>
        <dt className="kb-keys">{row.keys.map((key, index) => <KeyCap key={index} {...key} />)}</dt>
        <dd className="kb-action">{row.action}</dd>
      </div>)}
    </dl>
    <p className="kb-note">
      Shortcuts are off while you type in a field or while the sky map has the keyboard focus (press Tab to leave it).
    </p>
  </>;
}

const FOCUSABLE = 'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), '
  + 'textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

/** Closes the help dialog that is open now, if any (only one can be open at a time). */
let closeOpenDialog: (() => void) | null = null;

/**
 * Esc closes the topmost layer first (FE-11). Several layers listen for Esc on the window in the capture phase (the
 * pinned map card in ExplorerMap does too), and listeners on the same target and phase run in registration order.
 * This one is registered when this module loads, before any component effect, so it runs before the map card's
 * listener wherever and whenever the dialog is mounted (no dependency on mount order). It marks the event as consumed
 * with preventDefault(); the map then sees defaultPrevented and keeps its card. Keep this module statically imported:
 * a lazy import would register the listener late and bring the ordering problem back.
 */
const escapeOpenDialog = (event: KeyboardEvent) => {
  if (event.key !== 'Escape' || !closeOpenDialog || event.defaultPrevented) return;
  event.preventDefault();
  closeOpenDialog();
};
if (typeof window !== 'undefined') {
  window.addEventListener('keydown', escapeOpenDialog, true);
  import.meta.hot?.dispose(() => window.removeEventListener('keydown', escapeOpenDialog, true));
}

/**
 * A "Shortcuts" button plus the modal help dialog it opens; `?` opens it from anywhere on the page. Mount it once
 * (today in the explorer dock; FE-1b may move it to the topbar).
 */
export function ShortcutsHelp({ className }: { className?: string }) {
  const [open, setOpen] = useState(false);
  const openRef = useRef(false);
  const button = useRef<HTMLButtonElement>(null);
  const dialog = useRef<HTMLDivElement>(null);
  const closeButton = useRef<HTMLButtonElement>(null);
  const opener = useRef<HTMLElement | null>(null);
  const pressedBackdrop = useRef(false);
  const titleId = useId();

  const show = () => {
    if (openRef.current) return;
    const active = document.activeElement;
    opener.current = active instanceof HTMLElement && active !== document.body ? active : button.current;
    openRef.current = true;
    setOpen(true);
  };
  const close = () => {
    if (!openRef.current) return;
    openRef.current = false;
    setOpen(false);
    const back = opener.current?.isConnected ? opener.current : button.current;
    back?.focus();
  };

  useShortcut('?', show, { when: !open });

  useEffect(() => {
    if (open) closeButton.current?.focus();
  }, [open]);

  useEffect(() => {
    // Hand this dialog's close to the module-level Esc listener while it is open (see escapeOpenDialog).
    if (!open) return;
    const closeThis = () => close();
    closeOpenDialog = closeThis;
    return () => { if (closeOpenDialog === closeThis) closeOpenDialog = null; };
  }, [open]);

  const keepFocusInside = (event: ReactKeyboardEvent<HTMLDivElement>) => {
    if (event.key !== 'Tab') {
      // Keys stay inside the modal: the page's own shortcuts (such as `/`) must not act behind it.
      event.stopPropagation();
      return;
    }
    const items = Array.from(dialog.current?.querySelectorAll<HTMLElement>(FOCUSABLE) ?? []);
    if (!items.length) { event.preventDefault(); return; }
    const first = items[0];
    const last = items[items.length - 1];
    const active = document.activeElement;
    if (event.shiftKey && (active === first || active === dialog.current)) { event.preventDefault(); last.focus(); }
    else if (!event.shiftKey && active === last) { event.preventDefault(); first.focus(); }
  };

  return <>
    <button ref={button} type="button" className={className ? `kb-open ${className}` : 'kb-open'}
      aria-haspopup="dialog" aria-keyshortcuts="?" onClick={show}>
      <span aria-hidden="true">⌨</span> Shortcuts
    </button>
    {open && createPortal(
      <div className="kb-backdrop"
        onMouseDown={(event) => {
          pressedBackdrop.current = event.target === event.currentTarget;
          // The backdrop is not focusable: without this, a press on it moves the focus to <body>, outside the modal
          // (Tab and the page's own `/` listener would then act behind it).
          if (pressedBackdrop.current) event.preventDefault();
        }}
        onClick={(event) => {
          // Only a click that starts and ends on the backdrop closes (not a text selection dragged out of the dialog).
          if (pressedBackdrop.current && event.target === event.currentTarget) close();
          pressedBackdrop.current = false;
        }}>
        <div ref={dialog} className="kb-dialog" role="dialog" aria-modal="true" aria-labelledby={titleId}
          tabIndex={-1} onKeyDown={keepFocusInside}>
          <div className="kb-head">
            <h2 id={titleId} className="kb-title">Keyboard shortcuts</h2>
            <button ref={closeButton} type="button" className="kb-close" onClick={close}>Close</button>
          </div>
          <ShortcutsList />
        </div>
      </div>,
      document.body,
    )}
  </>;
}
