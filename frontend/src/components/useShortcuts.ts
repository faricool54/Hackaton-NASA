import { useEffect, useRef } from 'react';

/**
 * Page-wide single-key shortcuts (FRONTEND_PLAN FE-11).
 *
 * Only plain keys count: anything pressed with Ctrl, Meta or Alt is left to the browser and the system, an event
 * another handler already consumed (`defaultPrevented`) is skipped, and nothing fires while the user types in a
 * field, works inside a modal dialog, or has the keyboard focus inside the sky map iframe (those key events belong
 * to the iframe's own document and never reach this one). Esc is not a shortcut here: each owner closes its own
 * layer and calls `preventDefault()`, so one Esc closes one thing.
 */

/** The parts of a keydown event the filter reads; a real `KeyboardEvent` fits. */
export interface ShortcutEventLike {
  key: string;
  ctrlKey?: boolean;
  metaKey?: boolean;
  altKey?: boolean;
  defaultPrevented?: boolean;
  isComposing?: boolean;
  target?: unknown;
}

interface TargetLike {
  tagName?: unknown;
  isContentEditable?: unknown;
  isConnected?: unknown;
  ownerDocument?: unknown;
  closest?: unknown;
}

interface DocumentLike {
  querySelector?: unknown;
}

const TYPING_TAGS = new Set(['INPUT', 'TEXTAREA', 'SELECT', 'IFRAME']);
/** Fields, editors and modal dialogs: a plain key there is text or belongs to the dialog. */
const IGNORED_ANCESTORS = 'input, textarea, select, iframe, [contenteditable=""], [contenteditable="true"], '
  + '[contenteditable="plaintext-only"], [role="textbox"], [aria-modal="true"]';
const OPEN_MODAL = '[aria-modal="true"]:not([hidden])';

const currentDocument = (): DocumentLike | undefined => (typeof document === 'undefined' ? undefined : document);

/** True when a keydown should run a page shortcut. `doc` defaults to the page document (tests pass a stand-in). */
export function shouldHandleShortcut(event: ShortcutEventLike, doc: DocumentLike | undefined = currentDocument()): boolean {
  if (event.ctrlKey || event.metaKey || event.altKey) return false;
  if (event.defaultPrevented || event.isComposing) return false;
  if (doc && typeof doc.querySelector === 'function' && doc.querySelector(OPEN_MODAL)) return false;
  const target = event.target;
  // No element (window or document): nothing has the focus, so the page shortcut applies.
  if (!target || typeof target !== 'object') return true;
  const element = target as TargetLike;
  if (typeof element.tagName !== 'string') return true;
  if (TYPING_TAGS.has(element.tagName.toUpperCase())) return false;
  if (element.isContentEditable === true) return false;
  // A detached node, or one from another document (an iframe), is not part of this page.
  if (element.isConnected === false) return false;
  if (doc && element.ownerDocument && element.ownerDocument !== doc) return false;
  if (typeof element.closest === 'function' && element.closest(IGNORED_ANCESTORS)) return false;
  return true;
}

/** `1`…`count` → 0-based index; any other key (including `0` and Shift+digit symbols such as `!`) → null. */
export function digitShortcutIndex(key: string, count: number): number | null {
  if (!/^[1-9]$/.test(key)) return null;
  const index = Number(key) - 1;
  return index < count ? index : null;
}

export interface ShortcutOptions {
  /** Listen only while true (default true). */
  when?: boolean;
}

/**
 * Runs `handler` on a plain keydown of `key` (compared with `KeyboardEvent.key`, so `?` matches Shift+/ on most
 * layouts) anywhere on the page, after `preventDefault()`. `key` can be a list of keys sharing one handler.
 */
export function useShortcut(
  key: string | readonly string[],
  handler: (event: KeyboardEvent) => void,
  opts: ShortcutOptions = {},
): void {
  const latest = useRef(handler);
  useEffect(() => { latest.current = handler; });
  const when = opts.when ?? true;
  const keys = typeof key === 'string' ? key : key.join('\n');
  useEffect(() => {
    if (!when) return;
    const wanted = keys.split('\n');
    const listener = (event: KeyboardEvent) => {
      if (!wanted.includes(event.key) || !shouldHandleShortcut(event)) return;
      event.preventDefault();
      latest.current(event);
    };
    document.addEventListener('keydown', listener);
    return () => document.removeEventListener('keydown', listener);
  }, [keys, when]);
}
