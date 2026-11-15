import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';
import { DOCK_TAB_KEYS, EXPLORER_VIEWS, ExplorerDock, dockViewForKey } from './ExplorerDock';
import { SHORTCUTS, ShortcutsHelp, ShortcutsList } from './ShortcutsHelp';
import { digitShortcutIndex, shouldHandleShortcut, type ShortcutEventLike } from './useShortcuts';

const text = (html: string) => html.replace(/<[^>]+>/g, ' ').replace(/&amp;/g, '&').replace(/\s+/g, ' ');

/** A stand-in element: `ancestors` are the selectors `closest()` finds. */
function element(tagName: string, opts: { ancestors?: string[]; editable?: boolean; doc?: object; connected?: boolean } = {}) {
  return {
    tagName,
    isContentEditable: opts.editable ?? false,
    isConnected: opts.connected ?? true,
    ownerDocument: opts.doc,
    closest: (selector: string) => {
      const parts = selector.split(',').map((part) => part.trim());
      return opts.ancestors?.find((ancestor) => parts.includes(ancestor)) ?? null;
    },
  };
}

const page = { querySelector: () => null };
const press = (key: string, extra: Partial<ShortcutEventLike> = {}): ShortcutEventLike =>
  ({ key, target: element('BODY', { doc: page }), ...extra });

describe('FE-11 shortcut filter', () => {
  it('takes plain keys on the page', () => {
    expect(shouldHandleShortcut(press('1'), page)).toBe(true);
    expect(shouldHandleShortcut(press('?', { target: element('BUTTON', { doc: page }) }), page)).toBe(true);
    expect(shouldHandleShortcut({ key: '?', target: null }, page)).toBe(true);
    expect(shouldHandleShortcut({ key: '2', target: {} }, page)).toBe(true);
  });

  it('leaves keys with Ctrl, Meta or Alt, consumed keys and IME composition alone', () => {
    expect(shouldHandleShortcut(press('1', { ctrlKey: true }), page)).toBe(false);
    expect(shouldHandleShortcut(press('1', { metaKey: true }), page)).toBe(false);
    expect(shouldHandleShortcut(press('?', { altKey: true }), page)).toBe(false);
    expect(shouldHandleShortcut(press('1', { defaultPrevented: true }), page)).toBe(false);
    expect(shouldHandleShortcut(press('1', { isComposing: true }), page)).toBe(false);
  });

  it('ignores keys typed in fields and editors', () => {
    for (const tag of ['INPUT', 'TEXTAREA', 'SELECT', 'input']) {
      expect(shouldHandleShortcut(press('1', { target: element(tag, { doc: page }) }), page)).toBe(false);
    }
    expect(shouldHandleShortcut(press('3', { target: element('DIV', { doc: page, editable: true }) }), page)).toBe(false);
    expect(shouldHandleShortcut(press('3', { target: element('SPAN', { doc: page, ancestors: ['[role="textbox"]'] }) }), page))
      .toBe(false);
    expect(shouldHandleShortcut(press('3', { target: element('B', { doc: page, ancestors: ['[contenteditable="true"]'] }) }), page))
      .toBe(false);
  });

  it('ignores the map iframe, other documents, detached nodes and open modal dialogs', () => {
    expect(shouldHandleShortcut(press('1', { target: element('IFRAME', { doc: page }) }), page)).toBe(false);
    expect(shouldHandleShortcut(press('1', { target: element('CANVAS', { doc: {} }) }), page)).toBe(false);
    expect(shouldHandleShortcut(press('1', { target: element('DIV', { doc: page, connected: false }) }), page)).toBe(false);
    expect(shouldHandleShortcut(press('1', { target: element('BUTTON', { doc: page, ancestors: ['[aria-modal="true"]'] }) }), page))
      .toBe(false);
    const withDialog = { querySelector: (selector: string) => (selector.includes('aria-modal') ? {} : null) };
    expect(shouldHandleShortcut(press('2', { target: element('BODY', { doc: withDialog }) }), withDialog)).toBe(false);
  });
});

describe('FE-11 dock tab keys', () => {
  it('maps 1–4 to Object, Time, Spectrum and 3D and nothing else', () => {
    expect(DOCK_TAB_KEYS).toEqual(['1', '2', '3', '4']);
    expect(DOCK_TAB_KEYS.map(dockViewForKey)).toEqual([...EXPLORER_VIEWS]);
    expect(EXPLORER_VIEWS).toEqual(['Object', 'Time', 'Spectrum', '3D']);
    for (const key of ['0', '5', '9', '!', '@', 'a', ' ', '10', 'Digit1']) expect(dockViewForKey(key)).toBeNull();
  });

  it('turns digits into 0-based indexes within the count', () => {
    expect(digitShortcutIndex('1', 4)).toBe(0);
    expect(digitShortcutIndex('4', 4)).toBe(3);
    expect(digitShortcutIndex('5', 4)).toBeNull();
    expect(digitShortcutIndex('0', 4)).toBeNull();
    expect(digitShortcutIndex('', 4)).toBeNull();
  });
});

describe('FE-11 dock and help markup', () => {
  it('keeps the four dock tabs with their ids and ARIA, and adds the Shortcuts button', () => {
    const html = renderToStaticMarkup(createElement(ExplorerDock, {
      view: 'Time', onView: () => {}, header: createElement('h1', null, 'Barnard'), timeReady: true, children: 'body',
    }));
    expect(html).toContain('role="tablist" aria-label="Position views"');
    for (const [index, name] of EXPLORER_VIEWS.entries()) {
      const selected = name === 'Time';
      expect(html).toContain(`role="tab" id="xp-tab-${name}" aria-controls="xp-view-${name}" `
        + `aria-selected="${selected}" tabindex="${selected ? 0 : -1}" aria-keyshortcuts="${index + 1}"`);
    }
    expect(text(html)).toContain('Time · ready');
    expect(html).toMatch(/<button type="button" class="kb-open" aria-haspopup="dialog" aria-keyshortcuts="\?">/);
    expect(text(html)).toContain('Shortcuts');
    // Closed by default: no dialog in the server markup.
    expect(html).not.toContain('role="dialog"');
  });

  it('documents every shortcut without the dialog open', () => {
    expect(renderToStaticMarkup(createElement(ShortcutsHelp))).not.toContain('aria-modal');
    const list = text(renderToStaticMarkup(createElement(ShortcutsList)));
    for (const row of SHORTCUTS) expect(list).toContain(row.action);
    expect(list).toContain('Focus the sky search');
    expect(list).toContain('Left arrow');
    expect(list).toContain('Right arrow');
    expect(SHORTCUTS.flatMap((row) => row.keys.map((key) => key.cap)))
      .toEqual(['/', '1', '2', '3', '4', 'Space', '←', '→', 'Esc', '?']);
  });
});
