import { useEffect, useId, useMemo, useRef, useState, type CSSProperties } from 'react';
import { createPortal } from 'react-dom';
import { client } from '../api/client';
import { formatMjd } from '../api/format';
import {
  getGaiaMarkers, getGaiaView, gaiaViewMagLimit, medianFrameEpoch, GaiaViewCache, GAIA_DEFAULT_EPOCH, GAIA_FULL_FOV,
  GAIA_SOURCE_LIMIT, GAIA_VIEW_MAX_FOV, GAIA_WIDE_MAG_LIMIT, type GaiaMarker, type GaiaMarkerSet,
} from '../api/gaiaLayer';
import {
  cardAnnouncement, createCursorStore, createPositionSender, gaiaCard, INITIAL_MAP_STATE, MAP_TARGETS, parseMapMessage,
  reduceMapMessage, snapToMarker, targetCard, withGaiaEpoch, type Box, type MapCard, type MapCardContent, type MapContext,
  type MapEventMessage, type MapLayer, type MapMarker, type MapSelection, type MapState, type MapView,
} from '../api/mapHover';
import type { SkyCoord } from '../api/types';
import { fieldFootprint, footprintRadiusArcsec, pointInFootprint } from '../api/skyFootprint';
import { MapCursorReadout, MapHoverCard } from './MapHoverCard';
import '../styles/map.css';

export type { MapSelection } from '../api/mapHover';

/** How long the map waits for the open sequence's field (its footprint and Gaia epoch) before going on without it. */
const FIELD_TIMEOUT_MS = 12_000;

interface SequenceOverlay {
  fieldId: string;
  center: SkyCoord | null;
  corners: SkyCoord[] | null;
  epoch: number | null;
}

/**
 * 'panel' (default): the bordered card with the toolbar above the map and the credits below it.
 * 'fill': the map fills its container, which must give it a definite height; the controls float over the map in a
 * "Layers" menu (top right) with the status messages under it, and the legend and credits stay visible bottom right.
 * The top left corner is left to the search that FE-2 floats over the map (FRONTEND_PLAN §3.4).
 * Switching layouts keeps the same iframe element: Aladin and its WebGL context are never re-created.
 */
export type ExplorerMapLayout = 'panel' | 'fill';

/** The card on screen: the reducer's card plus its text and where it sits in the viewport. */
interface CardState {
  card: MapCard;
  content: MapCardContent;
  anchor: { x: number; y: number };
  bounds: Box;
}

const SPHEREX_CREDIT = 'https://irsa.ipac.caltech.edu/data/SPHEREx/';
const ALADIN_CREDIT = 'https://aladin.cds.unistra.fr/AladinLite/';
const GAIA_VIZIER = 'https://vizier.cfa.harvard.edu/viz-bin/VizieR?-source=I/355/gaiadr3';
const TARGETS = new Map(MAP_TARGETS.map((target) => [target.id, target]));
// A pick moves the map, loads the sequence epoch and zooms within ~1 s: only the settled view and epoch reach VizieR
// (QA 2026-11-15: queries fired for the old view at the new epoch were aborted here but still ran on VizieR CfA).
const STARS_SETTLE_MS = 600;
const coarsePointer = () => typeof matchMedia === 'function' && matchMedia('(pointer: coarse)').matches;
// Screen-reader-only text without a class (the panel layout keeps its markup free of .mp- classes).
const SR_ONLY: CSSProperties = {
  position: 'absolute', width: 1, height: 1, margin: -1, padding: 0, overflow: 'hidden', clip: 'rect(0 0 0 0)',
  whiteSpace: 'nowrap', border: 0,
};

export function ExplorerMap({ center, footprintFieldId, onSelect, layout = 'panel', recenterKey, onView, autoZoomKey }: {
  center: SkyCoord;
  footprintFieldId?: string;
  onSelect: (p: MapSelection) => void;
  layout?: ExplorerMapLayout;
  /** When it changes, the map goes back to `center` even if `center` did not change (the same preset again). */
  recenterKey?: string | number;
  /** The map view after the user pans or zooms (centre and the larger field-of-view side), at most every 500 ms. */
  onView?: (view: MapView) => void;
  /** When set or changed, the map zooms once to the open sequence's footprint as soon as it is known, so a picked
   *  target shows its grid outline and Gaia stars without opening Layers. The parent changes it only for picks
   *  (target chips, search), never for map clicks. */
  autoZoomKey?: string | number;
}) {
  const frame = useRef<HTMLIFrameElement>(null);
  const section = useRef<HTMLElement>(null);
  const selectRef = useRef(onSelect);
  selectRef.current = onSelect;
  const viewRef = useRef(onView);
  viewRef.current = onView;
  const [ready, setReady] = useState(false);
  const [error, setError] = useState('');
  const [wavelengths, setWavelengths] = useState<number[]>([]);
  const [plane, setPlane] = useState(90);
  const [allwise, setAllwise] = useState(false);
  const [showFootprint, setShowFootprint] = useState(true);
  const [showGaia, setShowGaia] = useState(false);
  const [showTargets, setShowTargets] = useState(true);
  const [overlay, setOverlay] = useState<SequenceOverlay | null>(null);
  const [gaia, setGaia] = useState<{ fieldId: string; data: GaiaMarkerSet | null } | null>(null);
  const [layersOpen, setLayersOpen] = useState(false);
  // FE-4b: Gaia DR3 stars around any view of at most GAIA_VIEW_MAX_FOV. On by default in the fill layout only.
  const [showStars, setShowStars] = useState(layout === 'fill');
  const [view, setView] = useState<MapView | null>(null);
  const [stars, setStars] = useState<{
    epoch: number; magLimit: number | null; data: GaiaMarkerSet | null; status: 'loading' | 'ready' | 'error';
  } | null>(null);
  const [viewCache] = useState(() => new GaiaViewCache(20));
  // The reducer state (api/mapHover.ts) lives in a ref; `card` is what React draws from it.
  const mapState = useRef<MapState>(INITIAL_MAP_STATE);
  const [card, setCard] = useState<CardState | null>(null);
  const [announcement, setAnnouncement] = useState('');
  const [cursor] = useState(createCursorStore);
  const [sendPosition] = useState(() => createPositionSender((p) =>
    frame.current?.contentWindow?.postMessage({ source: 'errante-ui', type: 'position', ...p }, location.origin)));
  const layersZone = useRef<HTMLDivElement>(null);
  const layersButton = useRef<HTMLButtonElement>(null);
  const layersId = useId();
  const legendId = useId();
  // The map legend starts folded so it does not cover the sky; the credits line below it always stays visible.
  const [legendOpen, setLegendOpen] = useState(false);
  const mapField = overlay?.fieldId === footprintFieldId ? overlay : null;
  const corners = mapField?.corners;
  const currentGaia = gaia?.fieldId === footprintFieldId ? gaia : null;
  const hasGaiaEpoch = !!corners && mapField?.epoch != null;
  // An open sequence's own Gaia predictions (#111) win over the stars of the view.
  const sequenceGaia = showGaia && hasGaiaEpoch && currentGaia?.data ? currentGaia.data : null;
  const starsEpoch = mapField?.epoch ?? GAIA_DEFAULT_EPOCH;
  // While an open sequence's field loads, its epoch is not known yet: wait instead of querying the default epoch.
  const starsEpochKnown = !footprintFieldId || overlay?.fieldId === footprintFieldId;
  const starsWanted = showStars && !sequenceGaia;
  const starsInView = starsWanted && !!view && view.fov <= GAIA_VIEW_MAX_FOV;
  const starsLimit = view ? gaiaViewMagLimit(view) : null;
  const gaiaSet = sequenceGaia && mapField?.epoch != null
    ? { ...sequenceGaia, epoch: mapField.epoch, origin: 'sequence' as const, magLimit: null }
    : starsInView && stars?.data && stars.epoch === starsEpoch
      ? { ...stars.data, epoch: starsEpoch, origin: 'view' as const, magLimit: stars.magLimit } : null;
  const gaiaMarkers = gaiaSet?.markers;
  const gaiaIndex = useMemo(() => new Map((gaiaMarkers ?? []).map((star) => [star.sourceId, star])), [gaiaMarkers]);
  const targetsShown = ready && showTargets;
  const frameReady = useRef(false);
  const fill = layout === 'fill';
  const post = (message: object) => frame.current?.contentWindow?.postMessage({ source: 'errante-ui', ...message }, location.origin);

  const lookupMarker = (layer: MapLayer, id: string): MapMarker | null => {
    if (layer === 'gaia') {
      const star: GaiaMarker | undefined = gaiaIndex.get(id);
      return star ? { layer, id, ra: star.ra, dec: star.dec } : null;
    }
    const target = showTargets ? TARGETS.get(id) : undefined;
    return target ? { layer, id, ra: target.ra, dec: target.dec, label: target.name } : null;
  };
  const cardContent = ({ layer, id, pinned }: MapCard): MapCardContent | null => {
    if (layer === 'gaia') {
      const star = gaiaIndex.get(id);
      return star && gaiaSet ? gaiaCard(star, gaiaSet.epoch, pinned) : null;
    }
    const target = TARGETS.get(id);
    return target ? targetCard(target, pinned) : null;
  };
  /**
   * The card is fixed to the viewport in a portal on document.body: FE-2's search floats over the map (z-index
   * --z-map-ui) and would cover a card drawn inside the map's stacking context. The bounds are still the map section.
   */
  const cardFor = (next: MapCard): CardState | null => {
    const content = cardContent(next);
    const frameBox = frame.current?.getBoundingClientRect();
    const box = section.current?.getBoundingClientRect();
    if (!content || !frameBox || !box) return null;
    return {
      card: next, content, anchor: { x: frameBox.left + next.x, y: frameBox.top + next.y },
      bounds: { left: box.left, top: box.top, right: box.right, bottom: box.bottom },
    };
  };
  const showCard = (next: MapCard | null) => {
    const shown = next ? cardFor(next) : null;
    mapState.current = { ...mapState.current, card: shown ? next : null };
    setCard(shown);
    if (shown?.card.pinned) setAnnouncement(cardAnnouncement(shown.content));
    else if (!shown) setAnnouncement('');
  };
  const closeCard = () => {
    if (mapState.current.card) showCard(null);
    else setCard(null);
  };
  const insideField = (p: SkyCoord) =>
    showFootprint && mapField?.center && corners && pointInFootprint(mapField.center, corners, p) ? mapField.fieldId : undefined;
  const snapCandidates = (): MapMarker[] => [
    ...(gaiaMarkers ?? []).map(({ sourceId, ra, dec }) => ({ layer: 'gaia' as const, id: sourceId, ra, dec })),
    ...(showTargets ? MAP_TARGETS.map(({ id, ra, dec, name }) => ({ layer: 'targets' as const, id, ra, dec, label: name })) : []),
  ];

  // Messages after 'ready'. Re-assigned on every render, so it always sees the current markers and view.
  const onMessage = useRef<(message: MapEventMessage, now: number) => void>(() => {});
  onMessage.current = (message, now) => {
    const size = { width: frame.current?.clientWidth ?? 0, height: frame.current?.clientHeight ?? 0 };
    const context: MapContext = {
      now, coarse: coarsePointer(), marker: lookupMarker, insideField,
      snap: (point) => view ? snapToMarker(point, snapCandidates(), view, size) : null,
      centre: { x: size.width / 2, y: size.height / 2 },
    };
    const before = mapState.current.card;
    const outcome = reduceMapMessage(mapState.current, message, context);
    mapState.current = outcome.state;
    if (outcome.state.card !== before) showCard(outcome.state.card);
    if (outcome.cursor !== undefined) cursor.set(outcome.cursor);
    if (outcome.view) { setView(outcome.view); viewRef.current?.(outcome.view); }
    // A clicked Gaia marker's ra/dec are its star's position predicted for the layer epoch, which goes along.
    if (outcome.select) selectRef.current(withGaiaEpoch(outcome.select, gaiaIndex, gaiaSet?.epoch));
  };

  useEffect(() => {
    const listener = (event: MessageEvent) => {
      if (event.origin !== location.origin || event.source !== frame.current?.contentWindow ||
        event.data?.source !== 'errante-sky') return;
      const message = parseMapMessage(event.data);
      if (!message) return;
      if (message.type === 'ready') { clearTimeout(timer); frameReady.current = true; setWavelengths(message.wavelengths); setReady(true); setError(''); }
      else if (message.type === 'error') setError('A map layer could not load. Try disabling AllWISE; coordinate search still works.');
      else onMessage.current(message, performance.now());
    };
    window.addEventListener('message', listener);
    const timer = setTimeout(() => { if (!frameReady.current) setError('The map is taking longer than expected. Coordinate search is available.'); }, 30000);
    return () => { window.removeEventListener('message', listener); clearTimeout(timer); };
  }, []);
  useEffect(() => {
    if (ready) sendPosition(center, recenterKey);
  }, [ready, center.ra, center.dec, recenterKey]);
  useEffect(() => {
    if (ready) post({ type: 'plane', plane });
  }, [ready, plane]);
  useEffect(() => {
    if (ready) post({ type: 'allwise', show: allwise });
  }, [ready, allwise]);
  // 'fill' hides the Aladin corner controls that sit under this component's overlays; 'panel' leaves Aladin as is.
  useEffect(() => {
    if (ready) post({ type: 'layout', layout });
    closeCard();
  }, [ready, layout]);
  useEffect(() => {
    if (ready) post({ type: 'targets', markers: showTargets ? MAP_TARGETS.map(({ id, ra, dec, name }) => ({ id, ra, dec, label: name })) : [] });
  }, [ready, showTargets]);
  useEffect(() => {
    if (!footprintFieldId) return;
    let current = true;
    const unavailable = { fieldId: footprintFieldId, center: null, corners: null, epoch: null };
    let settled = false;
    // A stalled API must not hold the per-view Gaia stars back (they wait for the sequence epoch): after
    // FIELD_TIMEOUT_MS they load at the default epoch, and a late field answer still replaces the overlay.
    const timer = setTimeout(() => { if (current && !settled) setOverlay(unavailable); }, FIELD_TIMEOUT_MS);
    client.getField(footprintFieldId).then((field) => {
      settled = true;
      if (!current) return;
      setOverlay(field.provenance.synthetic ? unavailable : {
        fieldId: footprintFieldId, center: field.center, corners: fieldFootprint(field.grid), epoch: medianFrameEpoch(field.frames),
      });
    }).catch(() => { settled = true; if (current) setOverlay(unavailable); });
    return () => { current = false; clearTimeout(timer); };
  }, [footprintFieldId]);
  useEffect(() => {
    if (ready) post({ type: 'footprint', corners: showFootprint ? corners ?? [] : [] });
  }, [ready, showFootprint, corners]);
  useEffect(() => {
    if (!showGaia || !mapField?.center || !mapField.corners || mapField.epoch === null || currentGaia) return;
    const abort = new AbortController();
    let current = true;
    const timer = setTimeout(() => abort.abort(), 12_000);
    getGaiaMarkers(mapField.center, mapField.corners, mapField.epoch, abort.signal)
      .then((data) => { if (current) setGaia({ fieldId: mapField.fieldId, data }); })
      .catch(() => { if (current) setGaia({ fieldId: mapField.fieldId, data: null }); })
      .finally(() => clearTimeout(timer));
    return () => { current = false; clearTimeout(timer); abort.abort(); };
  }, [showGaia, mapField, currentGaia]);
  // FE-4b: one VizieR query per settled view (the iframe debounces 'view' by 500 ms, and this waits STARS_SETTLE_MS for
  // the epoch and zoom of a pick to settle); a new view aborts the last one.
  useEffect(() => {
    if (!ready || !starsInView || !view || !starsEpochKnown) return;
    const magLimit = gaiaViewMagLimit(view);
    const cached = viewCache.get(view, starsEpoch);
    if (cached) { setStars({ epoch: starsEpoch, magLimit, data: cached, status: 'ready' }); return; }
    const abort = new AbortController();
    // The last stars stay on screen while loading only when they answer the same epoch and G limit.
    const keep = (last: typeof stars) => last?.epoch === starsEpoch && last.magLimit === magLimit ? last.data : null;
    setStars((last) => ({ epoch: starsEpoch, magLimit, data: keep(last), status: 'loading' }));
    const timer = setTimeout(() => {
      getGaiaView(view, starsEpoch, abort.signal).then((data) => {
        viewCache.set(view, starsEpoch, data);
        if (!abort.signal.aborted) setStars({ epoch: starsEpoch, magLimit, data, status: 'ready' });
      }).catch(() => {
        // VizieR failing never blocks the map: keep the last stars of this epoch and say so.
        if (!abort.signal.aborted) setStars((last) => ({ epoch: starsEpoch, magLimit, data: keep(last), status: 'error' }));
      });
    }, STARS_SETTLE_MS);
    return () => { clearTimeout(timer); abort.abort(); };
  }, [ready, starsInView, view, starsEpoch, starsEpochKnown, viewCache]);
  useEffect(() => {
    // Only ids and positions go to the iframe; the catalog values stay here for the hover card.
    if (ready) post({ type: 'gaia', markers: (gaiaMarkers ?? []).map(({ sourceId, ra, dec }) => ({ sourceId, ra, dec })) });
  }, [ready, gaiaMarkers]);
  useEffect(() => {
    // A hover card whose marker left the layer (new stars, or a layer switched off) closes; a pinned one keeps its text.
    const shown = mapState.current.card;
    if (shown && !shown.pinned && !lookupMarker(shown.layer, shown.id)) closeCard();
  }, [gaiaIndex, showTargets]);
  useEffect(() => {
    if (!card?.card.pinned) return;
    // Esc closes the topmost thing first (FRONTEND_PLAN FE-11). An open Layers menu with the focus is on top of the
    // card, so its own handler closes it and the card stays.
    const escape = (event: KeyboardEvent) => {
      if (event.key !== 'Escape' || event.defaultPrevented) return;
      if (layersOpen && layersZone.current?.contains(document.activeElement)) return;
      event.preventDefault();
      closeCard();
    };
    window.addEventListener('keydown', escape, true);
    return () => window.removeEventListener('keydown', escape, true);
  }, [card?.card.pinned, layersOpen]);
  const cardOpen = !!card;
  useEffect(() => {
    if (!cardOpen) return;
    // The card is fixed to the viewport: a resize, or a scroll that moves the map (the page, or a box around the map),
    // would leave it behind. Scrolling an unrelated box, such as the dock, keeps it.
    const close = () => closeCard();
    const scroll = (event: Event) => {
      const target = event.target;
      if (target instanceof Node && section.current && target.contains(section.current)) closeCard();
    };
    window.addEventListener('resize', close);
    window.addEventListener('scroll', scroll, true);
    return () => { window.removeEventListener('resize', close); window.removeEventListener('scroll', scroll, true); };
  }, [cardOpen]);
  useEffect(() => {
    if (!layersOpen) return;
    const outside = (event: PointerEvent) => {
      if (!layersZone.current?.contains(event.target as Node)) setLayersOpen(false);
    };
    // A click on the map never reaches this document: the iframe takes the focus and this window blurs.
    let check = 0;
    const blur = () => {
      check = window.setTimeout(() => { if (document.activeElement === frame.current) setLayersOpen(false); });
    };
    document.addEventListener('pointerdown', outside);
    window.addEventListener('blur', blur);
    return () => { document.removeEventListener('pointerdown', outside); window.removeEventListener('blur', blur); clearTimeout(check); };
  }, [layersOpen]);
  const gaiaState = !showGaia || !hasGaiaEpoch ? 'off' : currentGaia?.data ? 'ready' : currentGaia ? 'unavailable' : 'loading';
  const starsStatus = starsInView ? stars?.status : undefined;
  const zoomForStars = starsWanted && !!view && view.fov > GAIA_VIEW_MAX_FOV;
  const zoomToSequence = () => {
    const position = mapField?.center;
    if (!position || !corners) return;
    post({ type: 'zoom-footprint', ...position, radius: footprintRadiusArcsec(position, corners) / 3600 });
  };
  const autoZoomed = useRef<string | null>(null);
  useEffect(() => {
    if (autoZoomKey === undefined || !ready || !mapField?.center || !corners) return;
    // One zoom per key: a later map click into another sequence keeps the user's view.
    const key = String(autoZoomKey);
    if (autoZoomed.current === key) return;
    autoZoomed.current = key;
    zoomToSequence();
  }, [autoZoomKey, ready, mapField?.fieldId, mapField?.center, corners]);
  const toggleGaia = (checked: boolean) => {
    if (checked && currentGaia?.data === null) setGaia(null);
    setShowGaia(checked);
  };
  const leaveMap = () => {
    cursor.set(null);
    if (!mapState.current.card?.pinned) closeCard();
  };
  // The same controls in both layouts: only where they are drawn changes.
  const wavelengthSelect = <select aria-label="Map wavelength" value={plane} disabled={!ready}
    onChange={(e) => setPlane(Number(e.target.value))}>
    {wavelengths.length ? wavelengths.map((w, k) => k > 0 && k !== 50 && k !== 51 ?
      <option key={k} value={k}>{w.toFixed(3)} µm</option> : null) : <option value={90}>4.600 µm</option>}
  </select>;
  const allwiseToggle = <input type="checkbox" checked={allwise} disabled={!ready} onChange={(e) => setAllwise(e.target.checked)} />;
  const footprintToggle = <input type="checkbox" checked={showFootprint} disabled={!ready}
    onChange={(e) => setShowFootprint(e.target.checked)} />;
  const gaiaToggle = <input type="checkbox" checked={showGaia} disabled={!ready} onChange={(e) => toggleGaia(e.target.checked)} />;
  const starsToggle = <input type="checkbox" checked={showStars} disabled={!ready} onChange={(e) => setShowStars(e.target.checked)} />;
  const targetsToggle = <input type="checkbox" checked={showTargets} disabled={!ready} onChange={(e) => setShowTargets(e.target.checked)} />;
  const showGaiaLegend = !!gaiaSet?.markers.length;
  const gaiaDate = gaiaSet && <>{formatMjd(gaiaSet.epoch)}{gaiaSet.epoch === mapField?.epoch ? ' (median frame date)' : ''}</>;
  const gaiaLimit = gaiaSet?.limited
    ? gaiaSet.origin === 'sequence' ? ` · first ${GAIA_SOURCE_LIMIT} sources only` : ` · brightest ${GAIA_SOURCE_LIMIT} in view only` : '';
  const gaiaStars = gaiaSet?.magLimit != null ? `Gaia DR3 stars brighter than G ${gaiaSet.magLimit} in view: catalog`
    : 'Gaia DR3 catalog';
  const gaiaLegend = gaiaSet && <>{gaiaStars} positions predicted for {gaiaDate}, not SPHEREx detections{gaiaLimit}</>;
  const targetsLegend = 'challenge targets at SIMBAD positions predicted for their SPHEREx dates, not SPHEREx detections';
  const starsMessage = starsStatus === 'loading' ? 'Loading Gaia DR3 stars…'
    : starsStatus === 'error' ? starsLimit !== null
      // A timeout and a fast VizieR error answer look the same here, so the text names neither.
      ? 'Gaia DR3 stars did not load for this wide view (VizieR did not answer). Zoom in or try again later.'
      : 'Gaia DR3 stars are unavailable (VizieR did not answer). The map still works.' : '';
  // Wider than GAIA_FULL_FOV only the bright stars are shown; wider than GAIA_VIEW_MAX_FOV none.
  const zoomHint = zoomForStars ? 'Zoom in to see Gaia stars'
    : starsInView && starsLimit !== null && starsStatus === 'ready' ? 'Zoom in to see fainter Gaia stars' : '';
  // Children keep the same slots in both layouts, so the iframe (third child) is never unmounted (#86).
  return <section ref={section} className={fill ? 'explorer-map mp-root mp-fill' : 'explorer-map'} aria-label="Infrared sky map">
    {fill ? <div className="mp-zone mp-zone--layers" ref={layersZone} onKeyDown={(e) => {
      if (e.key !== 'Escape' || !layersOpen) return;
      e.stopPropagation();
      setLayersOpen(false);
      layersButton.current?.focus();
    }}>
      <button ref={layersButton} type="button" className="mp-glass mp-layers-button" aria-expanded={layersOpen}
        aria-controls={layersId} onClick={() => setLayersOpen((open) => !open)}>
        Layers <span className="mp-caret" aria-hidden="true">▾</span>
      </button>
      <div id={layersId} className="mp-glass mp-popover" role="group" aria-label="Map layers" hidden={!layersOpen}>
        <p className="mp-eyebrow">SPHEREx DR1 · infrared sky</p>
        <label className="mp-field"><span className="mp-eyebrow">Context wavelength</span>{wavelengthSelect}</label>
        <p className="mp-hint">Wavelength changes affect this context map only.</p>
        <label className="mp-check">{allwiseToggle}<span>AllWISE context (45%)</span></label>
        {corners && <label className="mp-check">{footprintToggle}<span>Sequence footprint</span></label>}
        {hasGaiaEpoch && <label className="mp-check">{gaiaToggle}<span>Gaia DR3</span></label>}
        {gaiaState === 'ready' && currentGaia?.data && <p className="mp-hint" role="status">
          {currentGaia.data.markers.length} Gaia DR3 sources with proper motion in the search region.
          {currentGaia.data.limited ? ` Query limited to ${GAIA_SOURCE_LIMIT} sources.` : ''}</p>}
        <label className="mp-check">{starsToggle}<span>Gaia DR3 stars</span></label>
        <p className="mp-hint">Brightest {GAIA_SOURCE_LIMIT} catalog stars when the view is {GAIA_FULL_FOV}° or smaller; up to
          {' '}{GAIA_VIEW_MAX_FOV}°, only stars brighter than G {GAIA_WIDE_MAG_LIMIT}. Hover for Gaia values; not SPHEREx measurements.</p>
        {(gaiaState !== 'off' || showStars) && <p className="mp-hint"><a href={GAIA_VIZIER} target="_blank" rel="noreferrer">Gaia DR3 · VizieR</a></p>}
        <label className="mp-check">{targetsToggle}<span>Challenge targets</span></label>
        {mapField?.center && corners && <button type="button" className="mp-button" disabled={!ready}
          onClick={zoomToSequence}>Zoom to sequence</button>}
        <p className="mp-hint mp-help">Click the sky to open Time, Spectrum, and 3D views. Drag to pan; scroll to zoom.</p>
      </div>
    </div> : <div className="toolbar map-heading">
      <strong>SPHEREx DR1 · infrared sky</strong>
      <label>Context wavelength{' '}{wavelengthSelect}</label>
      <label>{allwiseToggle}{' '}AllWISE context (45%)</label>
      {corners && <label>{footprintToggle}{' '}Sequence footprint</label>}
      {hasGaiaEpoch && <label>{gaiaToggle}{' '}Gaia DR3</label>}
      <label>{starsToggle}{' '}Gaia DR3 stars</label>
      <label>{targetsToggle}{' '}Challenge targets</label>
      {mapField?.center && corners && <button type="button" disabled={!ready} onClick={zoomToSequence}>Zoom to sequence</button>}
    </div>}
    {fill ? <div className="mp-zone mp-zone--status">
      {(!ready || error) && <p className={error ? 'mp-glass mp-note mp-note--error' : 'mp-glass mp-note'} role="status">
        {error || 'Loading Aladin sky map…'}</p>}
      {corners === null && <p className="mp-glass mp-note" role="status">A SPHEREx footprint is unavailable for this sequence.</p>}
      {gaiaState === 'loading' && <p className="mp-glass mp-note" role="status">Loading Gaia DR3 sources…</p>}
      {gaiaState === 'unavailable' && <p className="mp-glass mp-note" role="status">
        Gaia DR3 is unavailable. Toggle the layer to try again.</p>}
      {zoomHint && <p className="mp-glass mp-note mp-zoom-hint" role="status">{zoomHint}</p>}
      {starsMessage && <p className="mp-glass mp-note" role="status">{starsMessage}</p>}
    </div> : (!ready || error) && <p className={error ? 'error map-message' : 'muted map-message'} role="status">
      {error || 'Loading Aladin sky map…'}</p>}
    <iframe ref={frame} src={`${import.meta.env.BASE_URL}sky-map.html`} title="Interactive SPHEREx sky map"
      className={fill ? 'sky-map-frame mp-frame' : 'sky-map-frame'} onPointerLeave={leaveMap} onMouseLeave={leaveMap}
      onError={() => setError('Map unavailable. Use coordinate search.')} />
    {!fill && corners === null && <p className="muted small" role="status">A SPHEREx footprint is unavailable for this sequence.</p>}
    {!fill && showGaia && hasGaiaEpoch && mapField?.epoch != null && <p className="muted small" role="status">
      {currentGaia?.data
        ? `${currentGaia.data.markers.length} Gaia DR3 sources with proper motion in the search region.${currentGaia.data.limited ? ` Query limited to ${GAIA_SOURCE_LIMIT} sources.` : ''}`
        : currentGaia ? 'Gaia DR3 is unavailable. Toggle the layer to try again.' : 'Loading Gaia DR3 sources…'}
      {' '}<a href={GAIA_VIZIER} target="_blank" rel="noreferrer">Gaia DR3 · VizieR</a>
    </p>}
    {!fill && (zoomHint || starsMessage) && <p className="muted small" role="status">
      {starsMessage || `${zoomHint}.`}</p>}
    {fill ? <div className="mp-zone mp-zone--credits">
      <div className="mp-glass mp-strip">
        {(showFootprint && corners || showGaiaLegend || allwise || targetsShown) && <button type="button"
          className="mp-legend-toggle" aria-expanded={legendOpen} aria-controls={legendId}
          onClick={() => setLegendOpen((open) => !open)}>{legendOpen ? 'Hide legend ▾' : 'Legend ▸'}</button>}
        {(showFootprint && corners || showGaiaLegend || allwise || targetsShown) && <ul className="mp-legend" aria-label="Map legend"
          id={legendId} hidden={!legendOpen}>
          {showFootprint && corners && <li><span className="mp-swatch mp-swatch--footprint" aria-hidden="true" />
            Blue outline: reprojected SPHEREx sequence grid</li>}
          {showGaiaLegend && <li><span className="mp-swatch mp-swatch--gaia" aria-hidden="true" />
            Cyan circles: {gaiaLegend}</li>}
          {targetsShown && <li><span className="mp-swatch mp-swatch--targets" aria-hidden="true" />
            Gold squares: {targetsLegend}</li>}
          {allwise && <li><span className="mp-swatch mp-swatch--allwise" aria-hidden="true" />
            AllWISE W4/W2/W1 context (2010), not SPHEREx</li>}
        </ul>}
        <p className="mp-credits">Static coadd · not a video
          {' · '}<a href={SPHEREX_CREDIT} target="_blank" rel="noreferrer">NASA/SPHEREx · Caltech/IPAC</a>
          {' · '}<a href={ALADIN_CREDIT} target="_blank" rel="noreferrer">Aladin Lite 3.8.2 (GPL-3)</a>
          {showGaiaLegend && <> · ESA/Gaia/DPAC</>}
          {targetsShown && <> · SIMBAD/CDS</>}
          {allwise && <> · AllWISE: NASA/IPAC/CDS · ESA mirror</>}
        </p>
      </div>
    </div> : <p className="muted small map-credit">Click the sky to open Time, Spectrum, and 3D views. Drag to pan; scroll to zoom.
      {' '}This map is a static coadd, not a video. Wavelength changes affect this context map only.
      {' '}<a href={SPHEREX_CREDIT} target="_blank" rel="noreferrer">NASA/SPHEREx · Caltech/IPAC</a>
      {' · '}<a href={ALADIN_CREDIT} target="_blank" rel="noreferrer">Aladin Lite 3.8.2 (GPL-3)</a>
      {showFootprint && corners && <> · Blue outline: reprojected sequence grid</>}
      {showGaiaLegend && <> · Cyan circles show {gaiaLegend} · ESA/Gaia/DPAC</>}
      {targetsShown && <> · Gold squares show {targetsLegend} · SIMBAD/CDS</>}
      {allwise && <> · AllWISE W4/W2/W1 · NASA/IPAC/CDS · ESA mirror (2010, not SPHEREx)</>}
    </p>}
    {fill ? <div className="mp-zone mp-zone--readout"><MapCursorReadout store={cursor} /></div> : null}
    <p role="status" style={SR_ONLY}>{announcement}</p>
    {card && createPortal(<MapHoverCard card={card.content} anchor={card.anchor} bounds={card.bounds} position="fixed"
      pinned={card.card.pinned} onClose={() => { closeCard(); frame.current?.focus(); }} />, document.body)}
  </section>;
}
