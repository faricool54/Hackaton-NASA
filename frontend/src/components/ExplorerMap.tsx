import { useEffect, useId, useRef, useState } from 'react';
import { client } from '../api/client';
import { formatMjd } from '../api/format';
import { getGaiaMarkers, medianFrameEpoch, GAIA_SOURCE_LIMIT } from '../api/gaiaLayer';
import type { SkyCoord } from '../api/types';
import { validPosition } from '../api/jobs';
import { fieldFootprint, footprintRadiusArcsec } from '../api/skyFootprint';
import '../styles/map.css';

interface SequenceOverlay {
  fieldId: string;
  center: SkyCoord | null;
  corners: SkyCoord[] | null;
  epoch: number | null;
}

/**
 * 'panel' (default): the bordered card with the toolbar above the map and the credits below it.
 * 'fill': the map fills its container, which must give it a definite height; the controls float over the map in a
 * "Layers" menu (top right), status messages sit top left and the legend and credits stay visible bottom right.
 * Switching layouts keeps the same iframe element: Aladin and its WebGL context are never re-created.
 */
export type ExplorerMapLayout = 'panel' | 'fill';

const SPHEREX_CREDIT = 'https://irsa.ipac.caltech.edu/data/SPHEREx/';
const ALADIN_CREDIT = 'https://aladin.cds.unistra.fr/AladinLite/';
const GAIA_VIZIER = 'https://vizier.cfa.harvard.edu/viz-bin/VizieR?-source=I/355/gaiadr3';

export function ExplorerMap({ center, footprintFieldId, onSelect, layout = 'panel' }: {
  center: SkyCoord;
  footprintFieldId?: string;
  onSelect: (p: SkyCoord) => void;
  layout?: ExplorerMapLayout;
}) {
  const frame = useRef<HTMLIFrameElement>(null);
  const selectRef = useRef(onSelect);
  selectRef.current = onSelect;
  const [ready, setReady] = useState(false);
  const [error, setError] = useState('');
  const [wavelengths, setWavelengths] = useState<number[]>([]);
  const [plane, setPlane] = useState(90);
  const [allwise, setAllwise] = useState(false);
  const [showFootprint, setShowFootprint] = useState(true);
  const [showGaia, setShowGaia] = useState(false);
  const [overlay, setOverlay] = useState<SequenceOverlay | null>(null);
  const [gaia, setGaia] = useState<{ fieldId: string; data: Awaited<ReturnType<typeof getGaiaMarkers>> | null } | null>(null);
  const [layersOpen, setLayersOpen] = useState(false);
  const layersZone = useRef<HTMLDivElement>(null);
  const layersButton = useRef<HTMLButtonElement>(null);
  const layersId = useId();
  const mapField = overlay?.fieldId === footprintFieldId ? overlay : null;
  const corners = mapField?.corners;
  const currentGaia = gaia?.fieldId === footprintFieldId ? gaia : null;
  const markers = showGaia ? currentGaia?.data?.markers : undefined;
  const frameReady = useRef(false);
  useEffect(() => {
    const listener = (event: MessageEvent) => {
      if (event.origin !== location.origin || event.source !== frame.current?.contentWindow ||
        event.data?.source !== 'errante-sky') return;
      const data = event.data;
      if (data.type === 'ready') { clearTimeout(timer); frameReady.current = true; setWavelengths(data.wavelengths); setReady(true); setError(''); }
      else if (data.type === 'select' && validPosition(data)) selectRef.current(data);
      else if (data.type === 'error') setError('A map layer could not load. Try disabling AllWISE; coordinate search still works.');
    };
    window.addEventListener('message', listener);
    const timer = setTimeout(() => { if (!frameReady.current) setError('The map is taking longer than expected. Coordinate search is available.'); }, 30000);
    return () => { window.removeEventListener('message', listener); clearTimeout(timer); };
  }, []);
  useEffect(() => {
    if (ready) frame.current?.contentWindow?.postMessage({ source: 'errante-ui', type: 'position', ...center }, location.origin);
  }, [ready, center.ra, center.dec]);
  useEffect(() => {
    if (ready) frame.current?.contentWindow?.postMessage({ source: 'errante-ui', type: 'plane', plane }, location.origin);
  }, [ready, plane]);
  useEffect(() => {
    if (ready) frame.current?.contentWindow?.postMessage({ source: 'errante-ui', type: 'allwise', show: allwise }, location.origin);
  }, [ready, allwise]);
  // 'fill' hides the Aladin corner controls that sit under this component's overlays; 'panel' leaves Aladin as is.
  useEffect(() => {
    if (ready) frame.current?.contentWindow?.postMessage({ source: 'errante-ui', type: 'layout', layout }, location.origin);
  }, [ready, layout]);
  useEffect(() => {
    if (!footprintFieldId) return;
    let current = true;
    const unavailable = { fieldId: footprintFieldId, center: null, corners: null, epoch: null };
    client.getField(footprintFieldId).then((field) => {
      if (!current) return;
      setOverlay(field.provenance.synthetic ? unavailable : {
        fieldId: footprintFieldId, center: field.center, corners: fieldFootprint(field.grid), epoch: medianFrameEpoch(field.frames),
      });
    }).catch(() => { if (current) setOverlay(unavailable); });
    return () => { current = false; };
  }, [footprintFieldId]);
  useEffect(() => {
    if (ready) frame.current?.contentWindow?.postMessage({
      source: 'errante-ui', type: 'footprint', corners: showFootprint ? corners ?? [] : [],
    }, location.origin);
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
  useEffect(() => {
    if (ready) frame.current?.contentWindow?.postMessage({
      source: 'errante-ui', type: 'gaia', markers: markers ?? [],
    }, location.origin);
  }, [ready, markers]);
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
  const hasGaiaEpoch = !!corners && mapField?.epoch != null;
  const gaiaState = !showGaia || !hasGaiaEpoch ? 'off' : currentGaia?.data ? 'ready' : currentGaia ? 'unavailable' : 'loading';
  const zoomToSequence = () => {
    const position = mapField?.center;
    if (!position || !corners) return;
    frame.current?.contentWindow?.postMessage({
      source: 'errante-ui', type: 'zoom-footprint', ...position,
      radius: footprintRadiusArcsec(position, corners) / 3600,
    }, location.origin);
  };
  const toggleGaia = (checked: boolean) => {
    if (checked && currentGaia?.data === null) setGaia(null);
    setShowGaia(checked);
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
  const fill = layout === 'fill';
  const showGaiaLegend = !!markers?.length && mapField?.epoch != null;
  // Children keep the same slots in both layouts, so the iframe (third child) is never unmounted (#86).
  return <section className={fill ? 'explorer-map mp-root mp-fill' : 'explorer-map'} aria-label="Infrared sky map">
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
        {gaiaState !== 'off' && <p className="mp-hint"><a href={GAIA_VIZIER} target="_blank" rel="noreferrer">Gaia DR3 · VizieR</a></p>}
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
      {mapField?.center && corners && <button type="button" disabled={!ready} onClick={zoomToSequence}>Zoom to sequence</button>}
    </div>}
    {fill ? <div className="mp-zone mp-zone--status">
      {(!ready || error) && <p className={error ? 'mp-glass mp-note mp-note--error' : 'mp-glass mp-note'} role="status">
        {error || 'Loading Aladin sky map…'}</p>}
      {corners === null && <p className="mp-glass mp-note" role="status">A SPHEREx footprint is unavailable for this sequence.</p>}
      {gaiaState === 'loading' && <p className="mp-glass mp-note" role="status">Loading Gaia DR3 sources…</p>}
      {gaiaState === 'unavailable' && <p className="mp-glass mp-note" role="status">
        Gaia DR3 is unavailable. Toggle the layer to try again.</p>}
    </div> : (!ready || error) && <p className={error ? 'error map-message' : 'muted map-message'} role="status">
      {error || 'Loading Aladin sky map…'}</p>}
    <iframe ref={frame} src={`${import.meta.env.BASE_URL}sky-map.html`} title="Interactive SPHEREx sky map"
      className={fill ? 'sky-map-frame mp-frame' : 'sky-map-frame'} onError={() => setError('Map unavailable. Use coordinate search.')} />
    {!fill && corners === null && <p className="muted small" role="status">A SPHEREx footprint is unavailable for this sequence.</p>}
    {!fill && showGaia && hasGaiaEpoch && mapField?.epoch != null && <p className="muted small" role="status">
      {currentGaia?.data
        ? `${currentGaia.data.markers.length} Gaia DR3 sources with proper motion in the search region.${currentGaia.data.limited ? ` Query limited to ${GAIA_SOURCE_LIMIT} sources.` : ''}`
        : currentGaia ? 'Gaia DR3 is unavailable. Toggle the layer to try again.' : 'Loading Gaia DR3 sources…'}
      {' '}<a href={GAIA_VIZIER} target="_blank" rel="noreferrer">Gaia DR3 · VizieR</a>
    </p>}
    {fill ? <div className="mp-zone mp-zone--credits">
      <div className="mp-glass mp-strip">
        {(showFootprint && corners || showGaiaLegend || allwise) && <ul className="mp-legend" aria-label="Map legend">
          {showFootprint && corners && <li><span className="mp-swatch mp-swatch--footprint" aria-hidden="true" />
            Blue outline: reprojected SPHEREx sequence grid</li>}
          {showGaiaLegend && mapField?.epoch != null && <li><span className="mp-swatch mp-swatch--gaia" aria-hidden="true" />
            Cyan circles: Gaia DR3 catalog positions predicted for {formatMjd(mapField.epoch)} (median frame date),
            not SPHEREx detections{currentGaia?.data?.limited ? ` · first ${GAIA_SOURCE_LIMIT} sources only` : ''}</li>}
          {allwise && <li><span className="mp-swatch mp-swatch--allwise" aria-hidden="true" />
            AllWISE W4/W2/W1 context (2010), not SPHEREx</li>}
        </ul>}
        <p className="mp-credits">Static coadd · not a video
          {' · '}<a href={SPHEREX_CREDIT} target="_blank" rel="noreferrer">NASA/SPHEREx · Caltech/IPAC</a>
          {' · '}<a href={ALADIN_CREDIT} target="_blank" rel="noreferrer">Aladin Lite 3.8.2 (GPL-3)</a>
          {showGaiaLegend && <> · ESA/Gaia/DPAC</>}
          {allwise && <> · AllWISE: NASA/IPAC/CDS · ESA mirror</>}
        </p>
      </div>
    </div> : <p className="muted small map-credit">Click the sky to open Time, Spectrum, and 3D views. Drag to pan; scroll to zoom.
      {' '}This map is a static coadd, not a video. Wavelength changes affect this context map only.
      {' '}<a href={SPHEREX_CREDIT} target="_blank" rel="noreferrer">NASA/SPHEREx · Caltech/IPAC</a>
      {' · '}<a href={ALADIN_CREDIT} target="_blank" rel="noreferrer">Aladin Lite 3.8.2 (GPL-3)</a>
      {showFootprint && corners && <> · Blue outline: reprojected sequence grid</>}
      {!!markers?.length && mapField?.epoch != null && <> · Cyan circles show Gaia DR3 catalog positions predicted for {formatMjd(mapField.epoch)} (median frame date) · ESA/Gaia/DPAC</>}
      {allwise && <> · AllWISE W4/W2/W1 · NASA/IPAC/CDS · ESA mirror (2010, not SPHEREx)</>}
    </p>}
  </section>;
}
