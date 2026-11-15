import { useRef, type KeyboardEvent, type ReactNode } from 'react';
import { ShortcutsHelp } from './ShortcutsHelp';
import { digitShortcutIndex, useShortcut } from './useShortcuts';

export const EXPLORER_VIEWS = ['Object', 'Time', 'Spectrum', '3D'] as const;
export type ExplorerView = (typeof EXPLORER_VIEWS)[number];

/** Roving-tab keyboard order (←/→ wrap, Home/End); null for keys the tablist ignores. */
export function nextTabIndex(key: string, index: number, count: number = EXPLORER_VIEWS.length): number | null {
  switch (key) {
    case 'ArrowRight': return (index + 1) % count;
    case 'ArrowLeft': return (index + count - 1) % count;
    case 'Home': return 0;
    case 'End': return count - 1;
    default: return null;
  }
}

/** Keys `1`–`4` open the dock tabs in order (FE-11). */
export const DOCK_TAB_KEYS: readonly string[] = EXPLORER_VIEWS.map((_, index) => String(index + 1));

/** The dock tab a shortcut key opens, or null for any other key. */
export function dockViewForKey(key: string): ExplorerView | null {
  const index = digitShortcutIndex(key, EXPLORER_VIEWS.length);
  return index === null ? null : EXPLORER_VIEWS[index];
}

interface Props {
  view: ExplorerView;
  onView: (view: ExplorerView) => void;
  header: ReactNode;
  timeReady: boolean;
  children: ReactNode;
}

export function ExplorerDock({ view, onView, header, timeReady, children }: Props) {
  const tablist = useRef<HTMLDivElement>(null);
  useShortcut(DOCK_TAB_KEYS, (event) => {
    const next = dockViewForKey(event.key);
    if (!next) return;
    onView(next);
    tablist.current?.querySelectorAll<HTMLButtonElement>('[role="tab"]')[EXPLORER_VIEWS.indexOf(next)]?.focus();
  });

  const selectWithKey = (event: KeyboardEvent<HTMLButtonElement>, index: number) => {
    const next = nextTabIndex(event.key, index);
    if (next === null) return;
    event.preventDefault();
    onView(EXPLORER_VIEWS[next]);
    event.currentTarget.parentElement?.querySelectorAll('button')[next]?.focus();
  };

  return <aside className="xp-dock" aria-label="Sky position details">
    <header className="xp-dock-header">{header}</header>
    <div className="kb-tabrow">
      <div ref={tablist} className="segmented xp-tabs" role="tablist" aria-label="Position views">
        {EXPLORER_VIEWS.map((name, index) => (
          <button key={name} type="button" role="tab" id={`xp-tab-${name}`}
            aria-controls={`xp-view-${name}`} aria-selected={view === name} tabIndex={view === name ? 0 : -1}
            aria-keyshortcuts={DOCK_TAB_KEYS[index]}
            onKeyDown={(event) => selectWithKey(event, index)}
            onClick={() => onView(name)}>{name === 'Time' && timeReady ? 'Time · ready' : name}</button>
        ))}
      </div>
      <ShortcutsHelp />
    </div>
    <div className="xp-dock-body">{children}</div>
  </aside>;
}

export function ExplorerPanel({ name, active, children }: { name: ExplorerView; active: boolean; children: ReactNode }) {
  return <div role="tabpanel" id={`xp-view-${name}`} aria-labelledby={`xp-tab-${name}`} hidden={!active}>
    {children}
  </div>;
}
