import type { KeyboardEvent, ReactNode } from 'react';

export const EXPLORER_VIEWS = ['Object', 'Time', 'Spectrum', '3D'] as const;
export type ExplorerView = (typeof EXPLORER_VIEWS)[number];

interface Props {
  view: ExplorerView;
  onView: (view: ExplorerView) => void;
  header: ReactNode;
  timeReady: boolean;
  children: ReactNode;
}

export function ExplorerDock({ view, onView, header, timeReady, children }: Props) {
  const selectWithKey = (event: KeyboardEvent<HTMLButtonElement>, index: number) => {
    let next: number;
    switch (event.key) {
      case 'ArrowRight': next = (index + 1) % EXPLORER_VIEWS.length; break;
      case 'ArrowLeft': next = (index + EXPLORER_VIEWS.length - 1) % EXPLORER_VIEWS.length; break;
      case 'Home': next = 0; break;
      case 'End': next = EXPLORER_VIEWS.length - 1; break;
      default: return;
    }
    event.preventDefault();
    onView(EXPLORER_VIEWS[next]);
    event.currentTarget.parentElement?.querySelectorAll('button')[next]?.focus();
  };

  return <aside className="xp-dock" aria-label="Sky position details">
    <header className="xp-dock-header">{header}</header>
    <div className="segmented xp-tabs" role="tablist" aria-label="Position views">
      {EXPLORER_VIEWS.map((name, index) => (
        <button key={name} type="button" role="tab" id={`xp-tab-${name}`}
          aria-controls={`xp-view-${name}`} aria-selected={view === name} tabIndex={view === name ? 0 : -1}
          onKeyDown={(event) => selectWithKey(event, index)}
          onClick={() => onView(name)}>{name === 'Time' && timeReady ? 'Time · ready' : name}</button>
      ))}
    </div>
    <div className="xp-dock-body">{children}</div>
  </aside>;
}

export function ExplorerPanel({ name, active, children }: { name: ExplorerView; active: boolean; children: ReactNode }) {
  return <div role="tabpanel" id={`xp-view-${name}`} aria-labelledby={`xp-tab-${name}`} hidden={!active}>
    {children}
  </div>;
}
