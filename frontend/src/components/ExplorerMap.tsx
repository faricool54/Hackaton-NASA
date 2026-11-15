import { useEffect, useRef, useState } from 'react';
import type { SkyCoord } from '../api/types';
import { validPosition } from '../api/jobs';

export function ExplorerMap({ center, onSelect }: { center: SkyCoord; onSelect: (p: SkyCoord) => void }) {
  const frame = useRef<HTMLIFrameElement>(null);
  const selectRef = useRef(onSelect);
  selectRef.current = onSelect;
  const [ready, setReady] = useState(false);
  const [error, setError] = useState('');
  const [wavelengths, setWavelengths] = useState<number[]>([]);
  const [plane, setPlane] = useState(90);
  const [allwise, setAllwise] = useState(false);
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
    </div>
    {(!ready || error) && <p className={error ? 'error map-message' : 'muted map-message'} role="status">
      {error || 'Loading Aladin sky map…'}</p>}
    <iframe ref={frame} src={`${import.meta.env.BASE_URL}sky-map.html`} title="Interactive SPHEREx sky map"
      className="sky-map-frame" onError={() => setError('Map unavailable. Use coordinate search.')} />
    <p className="muted small map-credit">Click the sky to open Time, Spectrum, and 3D views. Drag to pan; scroll to zoom.
      {' '}This map is a static coadd, not a video. Wavelength changes affect this context map only.
      {' '}<a href="https://irsa.ipac.caltech.edu/data/SPHEREx/" target="_blank" rel="noreferrer">NASA/SPHEREx · Caltech/IPAC</a>
      {' · '}<a href="https://aladin.cds.unistra.fr/AladinLite/" target="_blank" rel="noreferrer">Aladin Lite 3.8.2 (GPL-3)</a>
      {allwise && <> · AllWISE W4/W2/W1 · NASA/IPAC/CDS · ESA mirror (2010, not SPHEREx)</>}
    </p>
  </section>;
}
