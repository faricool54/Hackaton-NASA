import { useLayoutEffect, useRef, useState, useSyncExternalStore } from 'react';
import { formatCursor, placeCard, type Box, type CursorStore, type MapCardContent } from '../api/mapHover';

/**
 * FE-4 hover card: a glass card next to the cursor over a map marker. `anchor` and `bounds` are in the coordinates of
 * the card's containing block (the viewport for 'fixed': ExplorerMap renders the card in a portal on document.body, so
 * overlays that FE-2 floats over the map cannot cover it). Every text is a React text node: nothing from the iframe or
 * a catalog goes through innerHTML. A pinned card is a labelled group, not a dialog: it never takes the focus, and
 * ExplorerMap announces it through its own live region.
 */
export function MapHoverCard({ card, anchor, bounds, position, pinned, onClose }: {
  card: MapCardContent;
  anchor: { x: number; y: number };
  bounds: Box;
  position: 'absolute' | 'fixed';
  pinned: boolean;
  onClose: () => void;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const [place, setPlace] = useState<{ left: number; top: number } | null>(null);
  useLayoutEffect(() => {
    const element = ref.current;
    if (!element) return;
    const { left, top } = placeCard(anchor, { width: element.offsetWidth, height: element.offsetHeight }, bounds);
    setPlace((current) => current?.left === left && current.top === top ? current : { left, top });
  }, [anchor.x, anchor.y, bounds.left, bounds.top, bounds.right, bounds.bottom, card, pinned]);
  const className = `mp-card mp-card--${card.kind}${pinned ? ' mp-card--pinned' : ''}`;
  return <div ref={ref} className={className} role={pinned ? 'group' : 'tooltip'} aria-label={card.title}
    style={{ position, left: place?.left ?? anchor.x + 14, top: place?.top ?? anchor.y + 14, visibility: place ? undefined : 'hidden' }}>
    <p className="mp-card-title">{card.title}</p>
    {card.lines.map((line, index) => <p key={index} className="mp-card-line">{line}</p>)}
    <p className="mp-card-footer">{card.footer}</p>
    {pinned && <button type="button" className="mp-card-close" aria-label="Close" onClick={onClose}>×</button>}
  </div>;
}

/** Bottom-left cursor readout of the fill layout (empty sky only: the iframe stops sending it over a marker). */
export function MapCursorReadout({ store }: { store: CursorStore }) {
  const cursor = useSyncExternalStore(store.subscribe, store.get, () => null);
  return cursor ? <p className="mp-readout">{formatCursor(cursor)}</p> : null;
}
