// FE-4 (docs/FRONTEND_PLAN.md §6.2): the map iframe protocol, what each message does to the hover card and the
// selection (reduceMapMessage), the hover card text and its honesty rules, and the card geometry. Pure functions only,
// so they are tested without a browser.
import { separationArcsec, tangentOffsetArcsec } from '../three/skyTrack';
import type { GaiaMarker } from './gaiaLayer';
import { validPosition } from './jobs';
import { SHOWCASE_TARGETS } from './showcase';
import type { SkyCoord } from './types';

// --- iframe → parent messages ----------------------------------------------------------------------------------

export type MapLayer = 'gaia' | 'targets';

export interface MapView extends SkyCoord {
  /** Larger side of the field of view, degrees. */
  fov: number;
  /** Horizontal and vertical field of view, degrees (Aladin getFov()); absent from older senders. */
  fovX?: number;
  fovY?: number;
}

export type MapMessage =
  | { type: 'ready'; wavelengths: number[] }
  | { type: 'error' }
  | { type: 'hover'; layer: MapLayer; id: string; ra: number; dec: number; x: number; y: number }
  | { type: 'hover-end'; id: string }
  | { type: 'cursor'; ra: number | null; dec: number | null; x: number; y: number }
  | { type: 'select'; ra: number; dec: number; sourceId?: string; layer?: MapLayer; x?: number; y?: number }
  | ({ type: 'view' } & MapView)
  /** The view started to change (once per burst, before the debounced 'view'): closes a pinned card at once. */
  | { type: 'move'; ra: number; dec: number }
  | { type: 'escape' };

const GAIA_ID = /^\d{1,20}$/;
const TARGET_ID = /^[a-z0-9-]{1,40}$/;

/** Gaia DR3 ids are digits; target ids are short slugs. Anything else is not one of our markers. */
export function validMarkerId(layer: unknown, id: unknown): id is string {
  return typeof id === 'string' && (layer === 'gaia' ? GAIA_ID.test(id) : layer === 'targets' && TARGET_ID.test(id));
}

/** Iframe pixels: finite and inside any plausible viewport. */
function validPixel(value: unknown): value is number {
  return typeof value === 'number' && Number.isFinite(value) && value > -1e4 && value < 1e5;
}

/**
 * Validate one message from sky-map.html (the caller has already checked `event.source`, `origin` and
 * `source: 'errante-sky'`). Returns null for anything malformed, so it is dropped.
 */
export function parseMapMessage(data: unknown): MapMessage | null {
  if (!data || typeof data !== 'object') return null;
  const m = data as Record<string, unknown>;
  switch (m.type) {
    case 'ready': {
      const w = m.wavelengths;
      return { type: 'ready', wavelengths: Array.isArray(w) && w.every((v) => typeof v === 'number' && Number.isFinite(v)) ? w : [] };
    }
    case 'error':
      return { type: 'error' };
    case 'escape':
      return { type: 'escape' };
    case 'hover':
      if (!validMarkerId(m.layer, m.id) || !validPosition(m) || !validPixel(m.x) || !validPixel(m.y)) return null;
      return { type: 'hover', layer: m.layer as MapLayer, id: m.id, ra: m.ra as number, dec: m.dec as number, x: m.x, y: m.y };
    case 'hover-end':
      if (typeof m.id !== 'string' || !(GAIA_ID.test(m.id) || TARGET_ID.test(m.id))) return null;
      return { type: 'hover-end', id: m.id };
    case 'cursor': {
      if (!validPixel(m.x) || !validPixel(m.y)) return null;
      if (m.ra === null && m.dec === null) return { type: 'cursor', ra: null, dec: null, x: m.x, y: m.y };
      if (!validPosition(m)) return null;
      return { type: 'cursor', ra: m.ra as number, dec: m.dec as number, x: m.x, y: m.y };
    }
    case 'select': {
      if (!validPosition(m)) return null;
      const select: Extract<MapMessage, { type: 'select' }> = { type: 'select', ra: m.ra as number, dec: m.dec as number };
      if (m.sourceId !== undefined || m.layer !== undefined) {
        if (!validMarkerId(m.layer, m.sourceId)) return null;
        select.sourceId = m.sourceId;
        select.layer = m.layer as MapLayer;
      }
      if (validPixel(m.x) && validPixel(m.y)) { select.x = m.x; select.y = m.y; }
      return select;
    }
    case 'view': {
      if (!validPosition(m) || !validFov(m.fov)) return null;
      const view: Extract<MapMessage, { type: 'view' }> = { type: 'view', ra: m.ra as number, dec: m.dec as number, fov: m.fov };
      if (validFov(m.fovX) && validFov(m.fovY)) { view.fovX = m.fovX; view.fovY = m.fovY; }
      return view;
    }
    case 'move':
      if (!validPosition(m)) return null;
      return { type: 'move', ra: m.ra as number, dec: m.dec as number };
    default:
      return null;
  }
}

function validFov(value: unknown): value is number {
  return typeof value === 'number' && value > 0 && value <= 360;
}

export const SELECT_GATE_MS = 300;

/**
 * Aladin fires objectClicked and then click for the same mouse event, so a click on a marker reaches the parent as a
 * precise select (with sourceId) followed by the generic one at the cursor. The gate drops that generic select when
 * it arrives within `windowMs` of the precise one; any later click goes through.
 */
export function createSelectGate(windowMs = SELECT_GATE_MS) {
  let preciseAt = -Infinity;
  return (select: { sourceId?: string }, now: number): boolean => {
    const gate = gateSelect(preciseAt, select, now, windowMs);
    preciseAt = gate.preciseAt;
    return gate.pass;
  };
}

/** One step of the select gate: whether `select` goes through, and the new time of the last precise select. */
function gateSelect(preciseAt: number, select: { sourceId?: string }, now: number, windowMs = SELECT_GATE_MS) {
  if (select.sourceId !== undefined) return { pass: true, preciseAt: now };
  if (now - preciseAt <= windowMs) return { pass: false, preciseAt: -Infinity };
  return { pass: true, preciseAt };
}

/**
 * Sends the map position to the iframe when the centre changes, and again when `recenterKey` changes with the same
 * centre (choosing the same preset twice must bring the map back after the user panned away).
 */
export function createPositionSender(post: (center: SkyCoord) => void) {
  let last: { ra: number; dec: number; key: unknown } | null = null;
  return (center: SkyCoord, recenterKey?: string | number): boolean => {
    if (last && last.ra === center.ra && last.dec === center.dec && last.key === recenterKey) return false;
    last = { ra: center.ra, dec: center.dec, key: recenterKey };
    post({ ra: center.ra, dec: center.dec });
    return true;
  };
}

/**
 * True when `point` is the view centre (within `toleranceDeg`): after the map recentres on a clicked marker, its
 * pinned card can move to the middle of the map instead of closing.
 */
export function atViewCentre(view: SkyCoord, point: SkyCoord, toleranceDeg = 1e-5): boolean {
  return separationArcsec({ raDeg: view.ra, decDeg: view.dec }, { raDeg: point.ra, decDeg: point.dec }) <= toleranceDeg * 3600;
}

// --- touch: snap a tap to a marker ------------------------------------------------------------------------------

/** Degrees per iframe pixel of a view (Aladin keeps square pixels). */
export function viewScaleDeg(view: MapView, size: { width: number; height: number }): number {
  const scale = view.fovX && size.width > 0 ? view.fovX / size.width : view.fov / Math.max(size.width, size.height);
  return Number.isFinite(scale) && scale > 0 ? scale : NaN;
}

/** Iframe pixel of a sky position in a north-up view with east to the left (small fields; gnomonic offsets). */
export function viewPixel(view: MapView, size: { width: number; height: number }, point: SkyCoord) {
  const scale = viewScaleDeg(view, size) * 3600;
  const { east, north } = tangentOffsetArcsec({ raDeg: view.ra, decDeg: view.dec }, { raDeg: point.ra, decDeg: point.dec });
  return { x: size.width / 2 - east / scale, y: size.height / 2 - north / scale };
}

/** Aladin's touch tolerance for objects (aladin.js 3.8.2, touchend). */
export const TOUCH_TOLERANCE_PX = 15;

/**
 * The marker nearest to a tap, if it lies within `tolerancePx` at the view scale. Aladin 3.8.2 reports objectClicked
 * on touch only for taps shorter than 100 ms; longer taps reach the parent as the generic select at the finger, which
 * this turns back into the marker the user aimed at.
 */
export function snapToMarker<M extends SkyCoord>(point: SkyCoord, markers: Iterable<M>, view: MapView,
  size: { width: number; height: number }, tolerancePx = TOUCH_TOLERANCE_PX): { marker: M; x: number; y: number } | null {
  const limit = tolerancePx * viewScaleDeg(view, size) * 3600;
  if (!(limit > 0)) return null;
  const tap = { raDeg: point.ra, decDeg: point.dec };
  let best: { marker: M; distance: number } | null = null;
  for (const marker of markers) {
    const distance = separationArcsec(tap, { raDeg: marker.ra, decDeg: marker.dec });
    if (distance <= limit && (!best || distance < best.distance)) best = { marker, distance };
  }
  return best ? { marker: best.marker, ...viewPixel(view, size, best.marker) } : null;
}

// --- what each message does: card and selection ------------------------------------------------------------------

/** A selected Gaia marker carries the epoch its position was predicted for, when the selection is at that marker's own
 *  position in the layer shown (`stars` by source id); any other selection is returned unchanged. */
export function withGaiaEpoch(select: MapSelection, stars: ReadonlyMap<string, SkyCoord>, epoch: number | undefined): MapSelection {
  const star = select.sourceId !== undefined ? stars.get(select.sourceId) : undefined;
  return star && epoch !== undefined && Number.isFinite(epoch) && star.ra === select.ra && star.dec === select.dec
    ? { ...select, epochMjd: epoch } : select;
}

/** What a click on the map selected. ra/dec are the marker's own position when a marker was clicked. */
export interface MapSelection extends SkyCoord {
  /** Gaia DR3 source_id of a clicked Gaia marker. */
  sourceId?: string;
  /** Epoch (MJD) the clicked Gaia marker's position (ra/dec) was predicted for; ExplorerMap sets it. */
  epochMjd?: number;
  /** Marker id of a clicked challenge target (the saved field id when api/showcase.ts lists one). */
  targetId?: string;
  /** Name of a clicked challenge target. */
  label?: string;
  layer?: MapLayer;
  /** The open sequence, when the click falls inside its visible footprint. */
  insideFieldId?: string;
  origin: 'map';
}

/** A marker the parent knows: its stored position (exact values) and, for targets, its name. */
export interface MapMarker extends SkyCoord {
  layer: MapLayer;
  id: string;
  label?: string;
}

/** The hover card: which marker, its stored position, the iframe pixel it is anchored to, and whether it is pinned. */
export interface MapCard {
  layer: MapLayer;
  id: string;
  at: SkyCoord;
  x: number;
  y: number;
  pinned: boolean;
}

export interface MapState {
  card: MapCard | null;
  /** Last hover, to anchor the pinned card of a click that carries no pixel. */
  lastHover: { id: string; x: number; y: number } | null;
  /** Arrival time (ms) of the last precise select, for the generic-select gate. */
  preciseAt: number;
}

export const INITIAL_MAP_STATE: MapState = { card: null, lastHover: null, preciseAt: -Infinity };

export interface MapContext {
  now: number;
  /** pointer: coarse. No hover cards; a tap that missed Aladin's objectClicked snaps to a marker. */
  coarse: boolean;
  marker: (layer: MapLayer, id: string) => MapMarker | null;
  /** The marker a tap aimed at, with its iframe pixel (see snapToMarker). */
  snap: (point: SkyCoord) => { marker: MapMarker; x: number; y: number } | null;
  insideField: (point: SkyCoord) => string | undefined;
  /** Iframe pixel of the view centre. */
  centre: { x: number; y: number };
}

export interface MapOutcome {
  state: MapState;
  /** For onSelect. */
  select?: MapSelection;
  /** A settled view, for the Gaia query and onView. */
  view?: MapView;
  /** The cursor readout (null hides it). */
  cursor?: SkyCoord | null;
}

export type MapEventMessage = Exclude<MapMessage, { type: 'ready' } | { type: 'error' }>;

/** A pinned card follows its marker when the map recentres on it; any other pan or zoom closes the card. */
function followView(state: MapState, centre: SkyCoord, ctx: MapContext): MapState {
  const { card } = state;
  if (!card) return state;
  if (card.pinned && atViewCentre(centre, card.at)) return { ...state, card: { ...card, ...ctx.centre } };
  return { ...state, card: null };
}

/**
 * What one validated message from the map iframe does (FRONTEND_PLAN §6.2): the next card state, plus the selection,
 * view or cursor to hand on. Pure, so ExplorerMap's wiring is tested as sequences of messages.
 */
export function reduceMapMessage(state: MapState, message: MapEventMessage, ctx: MapContext): MapOutcome {
  switch (message.type) {
    case 'cursor':
      return { state, cursor: message.ra === null || message.dec === null ? null : { ra: message.ra, dec: message.dec } };
    case 'hover': {
      const next = { ...state, lastHover: { id: message.id, x: message.x, y: message.y } };
      if (ctx.coarse || state.card?.pinned) return { state: next };
      const found = ctx.marker(message.layer, message.id);
      if (!found) return { state: next };
      const card = { layer: message.layer, id: message.id, at: { ra: found.ra, dec: found.dec }, x: message.x, y: message.y, pinned: false };
      return { state: { ...next, card } };
    }
    case 'hover-end':
      return { state: state.card && !state.card.pinned && state.card.id === message.id ? { ...state, card: null } : state };
    case 'select': {
      const gate = gateSelect(state.preciseAt, message, ctx.now);
      let next: MapState = { ...state, preciseAt: gate.preciseAt };
      if (!gate.pass) return { state: next };
      let aimed: { layer: MapLayer; id: string; x?: number; y?: number } | null = message.sourceId !== undefined && message.layer
        ? { layer: message.layer, id: message.sourceId, x: message.x, y: message.y } : null;
      if (!aimed && ctx.coarse) {
        const snapped = ctx.snap(message);
        if (snapped) aimed = { layer: snapped.marker.layer, id: snapped.marker.id, x: snapped.x, y: snapped.y };
      }
      let point: SkyCoord = { ra: message.ra, dec: message.dec };
      let select: MapSelection = { ...point, origin: 'map' };
      if (aimed) {
        const found = ctx.marker(aimed.layer, aimed.id);
        if (found) point = { ra: found.ra, dec: found.dec };
        select = { ...point, origin: 'map', layer: aimed.layer };
        if (aimed.layer === 'gaia') select.sourceId = aimed.id;
        else select.targetId = aimed.id;
        if (found?.label) select.label = found.label;
        const pixel = aimed.x !== undefined && aimed.y !== undefined ? { x: aimed.x, y: aimed.y }
          : state.lastHover?.id === aimed.id ? state.lastHover : null;
        next = { ...next, card: found && pixel ? { layer: aimed.layer, id: aimed.id, at: point, x: pixel.x, y: pixel.y, pinned: true } : null };
      } else next = { ...next, card: null };
      const inside = ctx.insideField(point);
      if (inside) select.insideFieldId = inside;
      return { state: next, select };
    }
    case 'view': {
      const view: MapView = { ra: message.ra, dec: message.dec, fov: message.fov };
      if (message.fovX !== undefined && message.fovY !== undefined) { view.fovX = message.fovX; view.fovY = message.fovY; }
      return { state: followView(state, view, ctx), view };
    }
    case 'move':
      return { state: followView(state, message, ctx) };
    case 'escape':
      return { state: state.card ? { ...state, card: null } : state };
  }
}

/** A tiny external store for the cursor readout, so 60 cursor updates a second do not re-render the whole map. */
export function createCursorStore() {
  let value: SkyCoord | null = null;
  const listeners = new Set<() => void>();
  return {
    get: () => value,
    set(next: SkyCoord | null) {
      if (next === value || (next && value && next.ra === value.ra && next.dec === value.dec)) return;
      value = next;
      listeners.forEach((listener) => listener());
    },
    subscribe(listener: () => void) {
      listeners.add(listener);
      return () => { listeners.delete(listener); };
    },
  };
}
export type CursorStore = ReturnType<typeof createCursorStore>;

// --- challenge targets layer ---------------------------------------------------------------------------------------

export interface MapTarget extends SkyCoord {
  id: string;
  name: string;
  /** Epoch of the preset position (MJD): SIMBAD astrometry propagated to the target's mean SPHEREx date. */
  mjd: number;
}

export function targetId(name: string): string {
  return name.normalize('NFKD').toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '').slice(0, 40);
}

/** The marker id of a showcase target: its saved field id when api/showcase.ts lists one, else a slug of its name. */
export function showcaseTargetId(target: { name: string }): string {
  const fieldId = (target as { fieldId?: unknown }).fieldId;
  return typeof fieldId === 'string' && TARGET_ID.test(fieldId) ? fieldId : targetId(target.name);
}

/** The five challenge targets (search presets from api/showcase.ts), drawn as their own catalog on the map. */
export const MAP_TARGETS: MapTarget[] = SHOWCASE_TARGETS.map((target) => ({
  id: showcaseTargetId(target), name: target.name, ra: target.ra, dec: target.dec, mjd: target.mjd,
}));

// --- hover card text -------------------------------------------------------------------------------------------------

/** Distance ≈ 1/parallax only for a positive parallax measured to better than 20 % (parallax/error > 5). */
export function parallaxDistancePc(parallaxMas: number | null, errorMas: number | null): number | null {
  if (parallaxMas === null || errorMas === null || !(parallaxMas > 0) || !(errorMas > 0)) return null;
  return parallaxMas / errorMas > 5 ? 1000 / parallaxMas : null;
}

/** Total proper motion in arcsec per year, from pmRA·cos(Dec) and pmDec in mas/yr. */
export function totalProperMotionArcsecYr(pmRaMasYr: number, pmDecMasYr: number): number {
  return Math.hypot(pmRaMasYr, pmDecMasYr) / 1000;
}

const MINUS = '−';
const signed = (text: string) => text.startsWith('-') ? MINUS + text.slice(1) : text;
const significant = (value: number, digits: number) => String(Number(value.toPrecision(digits)));

export function formatProperMotion(arcsecYr: number): string {
  return `${arcsecYr >= 1 ? arcsecYr.toFixed(2) : significant(arcsecYr, 2)}″/yr`;
}

export function formatDistance(pc: number): string {
  return pc >= 1000 ? `≈ ${significant(pc / 1000, 3)} kpc` : `≈ ${significant(pc, 3)} pc`;
}

/**
 * Parallax and its error with the error's first two significant digits (at least 2 decimals, at most 4). A parallax
 * that would round to zero gets more decimals (up to 4) so its sign and first digit show (−0.0039 ± 0.1666 →
 * "−0.004 ± 0.167"); one still zero at 4 decimals is printed without a sign.
 */
export function formatParallax(parallaxMas: number, errorMas: number | null): string {
  let decimals = errorMas && errorMas > 0 ? Math.max(2, Math.min(4, 1 - Math.floor(Math.log10(errorMas)))) : 2;
  while (decimals < 4 && parallaxMas !== 0 && Number(parallaxMas.toFixed(decimals)) === 0) decimals += 1;
  const value = Number(parallaxMas.toFixed(decimals)) === 0 ? (0).toFixed(decimals) : signed(parallaxMas.toFixed(decimals));
  return `${value}${errorMas && errorMas > 0 ? ` ± ${errorMas.toFixed(decimals)}` : ''} mas`;
}

/** Calendar date (UTC) of an MJD, e.g. 61000 → "2025-11-21". */
export function formatEpochDate(mjd: number): string {
  const date = new Date((mjd - 40587) * 86_400_000);
  return Number.isFinite(date.getTime()) ? date.toISOString().slice(0, 10) : `MJD ${mjd}`;
}

/** Right ascension in hours, minutes and seconds to 0.1 s, e.g. "17h57m47.1s". */
export function formatRaHms(raDeg: number): string {
  const tenths = ((Math.round(raDeg / 15 * 36_000) % 864_000) + 864_000) % 864_000;
  const h = Math.floor(tenths / 36_000);
  const m = Math.floor((tenths % 36_000) / 600);
  const s = (tenths % 600) / 10;
  return `${String(h).padStart(2, '0')}h${String(m).padStart(2, '0')}m${s.toFixed(1).padStart(4, '0')}s`;
}

/** Declination in degrees, arcminutes and arcseconds to 1″, e.g. "+04°46′07″". */
export function formatDecDms(decDeg: number): string {
  const arcsec = Math.round(Math.abs(decDeg) * 3600);
  const d = Math.floor(arcsec / 3600);
  const m = Math.floor((arcsec % 3600) / 60);
  const s = arcsec % 60;
  const sign = decDeg < 0 && arcsec > 0 ? MINUS : '+';
  return `${sign}${String(d).padStart(2, '0')}°${String(m).padStart(2, '0')}′${String(s).padStart(2, '0')}″`;
}

export function formatCursor({ ra, dec }: SkyCoord): string {
  return `RA ${formatRaHms(ra)} · Dec ${formatDecDms(dec)}`;
}

export interface MapCardContent {
  kind: MapLayer;
  id: string;
  title: string;
  lines: string[];
  /** Honesty label and the click hint: always shown. */
  footer: string;
}

export const GAIA_CARD_SOURCE = 'Gaia DR3 catalog · not SPHEREx measurements';

/**
 * Hover card of a Gaia DR3 marker. No Teff and no GSP-Phot distance: the object card in the dock owns the
 * temperature (WS3, #117), and two different values for the same star would contradict each other.
 */
export function gaiaCard(star: GaiaMarker, epochMjd: number, pinned = false): MapCardContent {
  const lines: string[] = [];
  const photometry = [
    star.gmag !== null ? `G ${star.gmag.toFixed(2)}` : '',
    star.bpRp !== null ? `BP${MINUS}RP ${signed(star.bpRp.toFixed(2))}` : '',
  ].filter(Boolean);
  if (photometry.length) lines.push(photometry.join(' · '));
  if (star.parallax === null) lines.push('No Gaia DR3 parallax · no distance');
  else {
    const distance = parallaxDistancePc(star.parallax, star.parallaxError);
    const parallax = `Parallax ${formatParallax(star.parallax, star.parallaxError)}`;
    if (distance === null) lines.push(parallax, 'Parallax too uncertain for a distance');
    else lines.push(`${parallax} → ${formatDistance(distance)} (1/parallax)`);
  }
  lines.push(`Proper motion ${formatProperMotion(totalProperMotionArcsecYr(star.pmRa, star.pmDec))}`);
  if (star.rv !== null) lines.push(`RV ${signed(star.rv.toFixed(1))} km/s`);
  lines.push(`Position predicted for ${formatEpochDate(epochMjd)} from Gaia DR3 proper motion`);
  return {
    kind: 'gaia', id: star.sourceId, title: `Gaia DR3 ${star.sourceId}`, lines,
    footer: `${GAIA_CARD_SOURCE} · ${pinned ? 'Selected' : 'Click to select'}`,
  };
}

/** The search-preset position is SIMBAD astrometry propagated to the target's mean SPHEREx date: say which date. */
export const TARGET_CARD_SOURCE = 'from SIMBAD astrometry · not a SPHEREx detection';

export function targetCard(target: MapTarget, pinned = false): MapCardContent {
  return {
    kind: 'targets', id: target.id, title: `${target.name} · Challenge target`,
    lines: [`Position predicted for ${formatEpochDate(target.mjd)} ${TARGET_CARD_SOURCE}`],
    footer: pinned ? 'Selected' : 'Click to open',
  };
}

/** Text of a card for screen readers (the live region announces a pinned card). */
export function cardAnnouncement(card: MapCardContent): string {
  return [card.title, ...card.lines, card.footer].join('. ');
}

// --- card geometry -------------------------------------------------------------------------------------------------

export interface Box {
  left: number;
  top: number;
  right: number;
  bottom: number;
}

/**
 * Card position next to the anchor (+offset px right and below), flipped to the other side when it would cross the
 * right or bottom edge, then clamped so the card never leaves `bounds` (if it is larger than the bounds, its top left
 * corner stays inside).
 */
export function placeCard(anchor: { x: number; y: number }, size: { width: number; height: number }, bounds: Box, offset = 14) {
  const axis = (at: number, extent: number, min: number, max: number) => {
    let start = at + offset;
    const flipped = start + extent > max;
    if (flipped) start = at - offset - extent;
    return { start: Math.max(min, Math.min(start, max - extent)), flipped };
  };
  const x = axis(anchor.x, size.width, bounds.left, bounds.right);
  const y = axis(anchor.y, size.height, bounds.top, bounds.bottom);
  return { left: x.start, top: y.start, flipX: x.flipped, flipY: y.flipped };
}
