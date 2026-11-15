import { useEffect, useRef, useState } from 'react';
import { client } from '../api/client';
import { formatMjd } from '../api/format';
import { getGaiaMarkers, medianFrameEpoch, GAIA_SOURCE_LIMIT } from '../api/gaiaLayer';
import type { SkyCoord } from '../api/types';
import { validPosition } from '../api/jobs';
import { fieldFootprint, footprintRadiusArcsec } from '../api/skyFootprint';

interface SequenceOverlay {
  fieldId: string;
  center: SkyCoord | null;
  corners: SkyCoord[] | null;
  epoch: number | null;
}

export function ExplorerMap({ center, footprintFieldId, onSelect }: {
  center: SkyCoord;
  footprintFieldId?: string;
  onSelect: (p: SkyCoord) => void;
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
  const hasGaiaEpoch = !!corners && mapField?.epoch != null;
  return <section className="explorer-map" aria-label="Infrared sky map">
    <div className="toolbar map-heading">
      <strong>SPHEREx DR1 · infrared sky</strong>
      <label>Context wavelength{' '}<select aria-label="Map wavelength" value={plane} disabled={!ready}
        onChange={(e) => setPlane(Number(e.target.value))}>
        {wavelengths.length ? wavelengths.map((w, k) => k > 0 && k !== 50 && k !== 51 ?
          <option key={k} value={k}>{w.toFixed(3)} µm</option> : null) : <option value={90}>4.600 µm</option>}
      </select></label>
      <label><input type="checkbox" checked={allwise} disabled={!ready} onChange={(e) => setAllwise(e.target.checked)} />
        {' '}AllWISE context (45%)</label>
      {corners && <label><input type="checkbox" checked={showFootprint} disabled={!ready}
        onChange={(e) => setShowFootprint(e.target.checked)} />{' '}Sequence footprint</label>}
      {hasGaiaEpoch && <label><input type="checkbox" checked={showGaia} disabled={!ready}
        onChange={(e) => {
          if (e.target.checked && currentGaia?.data === null) setGaia(null);
          setShowGaia(e.target.checked);
        }} />{' '}Gaia DR3</label>}
      {mapField?.center && corners && <button type="button" disabled={!ready} onClick={() => {
        const position = mapField.center;
        if (!position) return;
        frame.current?.contentWindow?.postMessage({
          source: 'errante-ui', type: 'zoom-footprint', ...position,
          radius: footprintRadiusArcsec(position, corners) / 3600,
        }, location.origin);
      }}>Zoom to sequence</button>}
    </div>
    {(!ready || error) && <p className={error ? 'error map-message' : 'muted map-message'} role="status">
      {error || 'Loading Aladin sky map…'}</p>}
    <iframe ref={frame} src={`${import.meta.env.BASE_URL}sky-map.html`} title="Interactive SPHEREx sky map"
      className="sky-map-frame" onError={() => setError('Map unavailable. Use coordinate search.')} />
    {corners === null && <p className="muted small" role="status">A SPHEREx footprint is unavailable for this sequence.</p>}
    {showGaia && hasGaiaEpoch && mapField?.epoch != null && <p className="muted small" role="status">
      {currentGaia?.data
        ? `${currentGaia.data.markers.length} Gaia DR3 sources with proper motion predicted for ${formatMjd(mapField.epoch)} (median frame date).${currentGaia.data.limited ? ` Query limited to ${GAIA_SOURCE_LIMIT} sources.` : ''}`
        : currentGaia ? 'Gaia DR3 is unavailable. Toggle the layer to try again.' : 'Loading Gaia DR3 sources…'}
      {' '}<a href="https://vizier.cfa.harvard.edu/viz-bin/VizieR?-source=I/355/gaiadr3" target="_blank" rel="noreferrer">Gaia DR3 · VizieR</a>
    </p>}
    <p className="muted small map-credit">Click the sky to open Time, Spectrum, and 3D views. Drag to pan; scroll to zoom.
      {' '}This map is a static coadd, not a video. Wavelength changes affect this context map only.
      {' '}<a href="https://irsa.ipac.caltech.edu/data/SPHEREx/" target="_blank" rel="noreferrer">NASA/SPHEREx · Caltech/IPAC</a>
      {' · '}<a href="https://aladin.cds.unistra.fr/AladinLite/" target="_blank" rel="noreferrer">Aladin Lite 3.8.2 (GPL-3)</a>
      {showFootprint && corners && <> · Purple outline: reprojected sequence grid</>}
      {allwise && <> · AllWISE W4/W2/W1 · NASA/IPAC/CDS · ESA mirror (2010, not SPHEREx)</>}
    </p>
  </section>;
}
