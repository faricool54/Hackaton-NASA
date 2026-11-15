// #/system/<id>[/<bodyId>] — 3D view of one system; a body id "enters" that body.
import { lazy, Suspense, useEffect, useLayoutEffect, useRef, useState } from 'react';
import { client } from '../api/client';
import type { SystemModel } from '../api/types';
import { formatRaDec } from '../api/format';
import { BodyPanel } from '../components/BodyPanel';
import { ErrorBoundary } from '../components/ErrorBoundary';
import { SyntheticBadge } from '../components/SyntheticBadge';
import { SystemViewer } from '../components/SystemViewer';
import { fieldLinkLabel, type FieldLinkInfo } from '../three/fieldLink';
import { SystemViewerContext } from '../three/viewerLink';
import '../three/system.css';

// The sky-track panel and its astrometry module load on demand, like the 3D scene, so the
// main chunk does not grow.
const SkyTrackPanel = lazy(() => import('../three/SkyTrackPanel').then((m) => ({ default: m.SkyTrackPanel })));

// Styles: three/system.css (.s3d-). The detail cards keep the look of BenjaminPondal's #30 (same values).

export function SystemPage({ systemId, bodyId }: { systemId: string; bodyId: string | null }) {
  const [system, setSystem] = useState<SystemModel | null>(null);
  // Field id -> name and synthetic flag, from the manifest (a field from a synthetic manifest is synthetic).
  const [fields, setFields] = useState<Map<string, FieldLinkInfo>>(new Map());
  const [error, setError] = useState<string | null>(null);
  // Dataset-time date of the 3D view (null in free-running), marked on the sky-track panel.
  const [datasetMjd, setDatasetMjd] = useState<number | null>(null);

  useEffect(() => {
    setSystem(null);
    setError(null);
    client.getSystem(systemId).then(setSystem).catch((e: Error) => setError(e.message));
    client
      .getManifest()
      .then((m) => setFields(new Map(m.fields.map((f) => [f.id, { name: f.name, synthetic: f.synthetic || m.synthetic }]))))
      .catch(() => setFields(new Map()));
  }, [systemId]);

  // The side column scrolls on its own (from 900 px up). A new selection replaces its top (the body list or a
  // body panel), so show it from the top: a column left scrolled down to the sky track would hide the panel of
  // the body just picked in the 3D view. Below 900 px the column does not scroll and this does nothing.
  const sideRef = useRef<HTMLElement>(null);
  useLayoutEffect(() => {
    if (sideRef.current) sideRef.current.scrollTop = 0;
  }, [bodyId]);

  const select = (id: string | null) => {
    window.location.hash = id ? `#/system/${systemId}/${id}` : `#/system/${systemId}`;
  };

  if (error) return <main className="error">Could not load system “{systemId}”: {error}</main>;
  if (!system) return <main className="muted">Loading…</main>;

  const body = bodyId ? system.bodies.find((b) => b.id === bodyId) ?? null : null;
  const unverified = system.bodies.some((b) => b.facts.some((f) => !f.verified));
  const fieldExists = !!system.field_id && fields.has(system.field_id);
  const field = system.field_id ? fields.get(system.field_id) : undefined;
  // Never call a synthetic field (or the field of a synthetic system) "SPHEREx images".
  const fieldSynthetic = system.provenance.synthetic || field?.synthetic === true;
  const m = system.motion;


  return (
    <main className="s3d-page">
      <header className="s3d-head">
        <div className="s3d-head-row">
          <p className="s3d-back">
            <a href="#/systems">← All 3D systems</a>
          </p>
          <h1 className="s3d-title">
            {system.name} <SyntheticBadge synthetic={system.provenance.synthetic} />{' '}
            <span className="badge u-badge u-badge--model" title={system.representation_note}>
              3D MODEL · NOT AN IMAGE
            </span>{' '}
            {unverified && !system.provenance.synthetic && (
              <span
                className="badge u-badge u-badge--warn unverified-badge"
                title="Some values are estimates that no catalog or paper states (see the facts marked unverified)"
              >
                UNVERIFIED VALUES
              </span>
            )}
          </h1>
        </div>
        <p className="s3d-desc">{system.description}</p>
        <p className="s3d-note">{system.representation_note}</p>
      </header>

      <div className="s3d-layout">
        <section className="s3d-main" aria-label="3D view">
          <ErrorBoundary what="The 3D view">
            {/* The page already knows whether the field exists (no second manifest fetch) and shows the 3D view's date. */}
            <SystemViewerContext.Provider value={{ fieldExists, onDatasetMjd: setDatasetMjd }}>
            <SystemViewer system={system} selectedId={body?.id ?? null} onSelect={select} />
            </SystemViewerContext.Provider>
          </ErrorBoundary>
        </section>
        <aside className="s3d-side" aria-label="System details" ref={sideRef}>
          {body ? (
            <BodyPanel system={system} body={body} fieldExists={fieldExists} fieldSynthetic={fieldSynthetic} />
          ) : (
            <div className="s3d-info">
              <div className="s3d-info-head">
                <div>
                  <p className="s3d-eyebrow">Explore the model</p>
                  <h2 className="s3d-section-heading">In this system</h2>
                </div>
                <span className="s3d-count">
                  {system.bodies.length} {system.bodies.length === 1 ? 'body' : 'bodies'}
                </span>
              </div>
              <ul className="s3d-body-list" aria-label="Bodies in this system">
                {system.bodies.map((b, index) => (
                  <li key={b.id}>
                    <a href={`#/system/${system.id}/${b.id}`} className="s3d-body-link">
                      <span className="s3d-body-link-name">
                        <span aria-hidden="true" className="s3d-body-index">
                          {String(index + 1).padStart(2, '0')}
                        </span>
                        <span className="s3d-truncate">{b.name}</span>
                      </span>
                      <span aria-hidden="true" className="s3d-arrow">
                        →
                      </span>
                    </a>
                  </li>
                ))}
              </ul>
            </div>
          )}
          <div className="s3d-info small">
            <p className="s3d-eyebrow">Sky coordinates{m?.epoch ? ` · ${m.epoch}` : ''}</p>
            <h3 className="s3d-section-heading">Where it is</h3>
            <div className="s3d-coords">
              <div className="s3d-coords-label">Right ascension · declination</div>
              <div className="s3d-coords-value">{formatRaDec(system.center.ra, system.center.dec)}</div>
            </div>
            {(m?.distance_pc || (m?.pm_ra_cosdec_mas_yr != null && m?.pm_dec_mas_yr != null)) && (
              <div className="s3d-stats">
                {m?.distance_pc && (
                  <div className="s3d-stat">
                    <div className="s3d-stat-label">Distance</div>
                    <div className="s3d-stat-value">
                      {m.distance_pc} pc <span className="s3d-stat-aside">· {(m.distance_pc * 3.2616).toFixed(1)} ly</span>
                    </div>
                  </div>
                )}
                {m?.pm_ra_cosdec_mas_yr != null && m?.pm_dec_mas_yr != null && (
                  <div className="s3d-stat">
                    <div className="s3d-stat-label">Sky motion</div>
                    <div className="s3d-stat-value">
                      {(Math.hypot(m.pm_ra_cosdec_mas_yr, m.pm_dec_mas_yr) / 1000).toFixed(2)}″ / year
                    </div>
                  </div>
                )}
              </div>
            )}
            {/* TODO(WS7-5): "move through space" view using SpaceMotion (parallax + proper motion + RV). */}
            {system.field_id &&
              (fieldExists ? (
                <a href={`#/field/${system.field_id}`} className="s3d-field-link">
                  {/* Names the field's target: it is not always the primary whose coordinates are above (Epsilon Indi). */}
                  {fieldLinkLabel(field, system.provenance.synthetic)}
                </a>
              ) : (
                <div className="muted s3d-field-missing">
                  {fieldSynthetic
                    ? 'The synthetic demo field for this system is not built yet in this dataset.'
                    : 'SPHEREx images for this target are not built yet in this dataset.'}
                </div>
              ))}
            {system.provenance.notes.length > 0 && (
              <ul className="notes s3d-prov-notes">
                {system.provenance.notes.map((n, i) => (
                  <li key={i}>{n}</li>
                ))}
              </ul>
            )}
          </div>
          {m && (
            // Where SPHEREx should see the target on its pass dates (prediction from catalog astrometry).
            <ErrorBoundary what="The sky-track panel">
              <Suspense fallback={<div className="s3d-info small muted">Loading the predicted sky track…</div>}>
                <SkyTrackPanel system={system} mjd={datasetMjd} />
              </Suspense>
            </ErrorBoundary>
          )}
        </aside>
      </div>
    </main>
  );
}
