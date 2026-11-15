// #/system/<id>[/<bodyId>] — 3D view of one system; a body id "enters" that body.
import { lazy, Suspense, useEffect, useState, type CSSProperties } from 'react';
import { client } from '../api/client';
import type { SystemModel } from '../api/types';
import { formatRaDec } from '../api/format';
import { BodyPanel } from '../components/BodyPanel';
import { ErrorBoundary } from '../components/ErrorBoundary';
import { SyntheticBadge } from '../components/SyntheticBadge';
import { SystemViewer } from '../components/SystemViewer';
import { SystemViewerContext } from '../three/viewerLink';

// The sky-track panel and its astrometry module load on demand, like the 3D scene, so the
// main chunk does not grow.
const SkyTrackPanel = lazy(() => import('../three/SkyTrackPanel').then((m) => ({ default: m.SkyTrackPanel })));

const infoPanelStyle: CSSProperties = {
  padding: 18,
  borderRadius: 16,
  background:
    'radial-gradient(ellipse at 100% 0%, rgba(124, 196, 255, 0.08), transparent 48%), linear-gradient(155deg, #121a2a, #0d111c 76%)',
  boxShadow: '0 14px 36px rgba(0, 0, 0, 0.18)',
};

const eyebrowStyle: CSSProperties = {
  margin: 0,
  color: '#8e97ad',
  fontSize: '0.68rem',
  fontWeight: 700,
  letterSpacing: '0.12em',
  textTransform: 'uppercase',
};

const sectionHeadingStyle: CSSProperties = { margin: '4px 0 0', fontSize: '1.12rem' };

const bodyLinkStyle: CSSProperties = {
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'space-between',
  gap: 12,
  minHeight: 42,
  padding: '9px 11px',
  border: '1px solid rgba(184, 199, 218, 0.1)',
  borderRadius: 10,
  background: 'rgba(255, 255, 255, 0.025)',
  color: '#dce8f7',
  textDecoration: 'none',
};

export function SystemPage({ systemId, bodyId }: { systemId: string; bodyId: string | null }) {
  const [system, setSystem] = useState<SystemModel | null>(null);
  // Field id -> synthetic flag, from the manifest (a field from a synthetic manifest is synthetic).
  const [fields, setFields] = useState<Map<string, boolean>>(new Map());
  const [error, setError] = useState<string | null>(null);
  // Dataset-time date of the 3D view (null in free-running), marked on the sky-track panel.
  const [datasetMjd, setDatasetMjd] = useState<number | null>(null);

  useEffect(() => {
    setSystem(null);
    setError(null);
    client.getSystem(systemId).then(setSystem).catch((e: Error) => setError(e.message));
    client
      .getManifest()
      .then((m) => setFields(new Map(m.fields.map((f) => [f.id, f.synthetic || m.synthetic]))))
      .catch(() => setFields(new Map()));
  }, [systemId]);

  const select = (id: string | null) => {
    window.location.hash = id ? `#/system/${systemId}/${id}` : `#/system/${systemId}`;
  };

  if (error) return <main className="error">Could not load system “{systemId}”: {error}</main>;
  if (!system) return <main className="muted">Loading…</main>;

  const body = bodyId ? system.bodies.find((b) => b.id === bodyId) ?? null : null;
  const unverified = system.bodies.some((b) => b.facts.some((f) => !f.verified));
  const fieldExists = !!system.field_id && fields.has(system.field_id);
  // Never call a synthetic field (or the field of a synthetic system) "SPHEREx images".
  const fieldSynthetic = system.provenance.synthetic || (!!system.field_id && fields.get(system.field_id) === true);
  const m = system.motion;

  return (
    <main>
      <p>
        <a href="#/systems">← All 3D systems</a>
      </p>
      <h1>
        {system.name} <SyntheticBadge synthetic={system.provenance.synthetic} />{' '}
        <span className="badge model" title={system.representation_note}>
          3D MODEL · NOT AN IMAGE
        </span>{' '}
        {unverified && !system.provenance.synthetic && (
          <span className="badge unverified-badge" title="Some values are estimates that no catalog or paper states (see the facts marked unverified)">
            UNVERIFIED VALUES
          </span>
        )}
      </h1>
      <p className="muted">{system.description}</p>

      <div className="field-layout">
        <section>
          <ErrorBoundary what="The 3D view">
            {/* The page already knows whether the field exists (no second manifest fetch) and shows the 3D view's date. */}
            <SystemViewerContext.Provider value={{ fieldExists, onDatasetMjd: setDatasetMjd }}>
            <SystemViewer system={system} selectedId={body?.id ?? null} onSelect={select} />
            </SystemViewerContext.Provider>
          </ErrorBoundary>
          <p className="muted small">{system.representation_note}</p>
        </section>
        <aside>
          {body ? (
            <BodyPanel system={system} body={body} fieldExists={fieldExists} fieldSynthetic={fieldSynthetic} />
          ) : (
            <div className="panel" style={infoPanelStyle}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12, marginBottom: 14 }}>
                <div>
                  <p style={eyebrowStyle}>Explore the model</p>
                  <h2 style={sectionHeadingStyle}>In this system</h2>
                </div>
                <span
                  style={{
                    flex: 'none',
                    padding: '4px 9px',
                    border: '1px solid rgba(124, 196, 255, 0.2)',
                    borderRadius: 999,
                    color: '#a9d9ff',
                    background: 'rgba(124, 196, 255, 0.07)',
                    fontSize: '0.73rem',
                    fontVariantNumeric: 'tabular-nums',
                  }}
                >
                  {system.bodies.length} {system.bodies.length === 1 ? 'body' : 'bodies'}
                </span>
              </div>
              <ul
                className="body-list"
                aria-label="Bodies in this system"
                style={{ display: 'grid', gap: 7, padding: 0, margin: 0, listStyle: 'none' }}
              >
                {system.bodies.map((b, index) => (
                  <li key={b.id}>
                    <a href={`#/system/${system.id}/${b.id}`} style={bodyLinkStyle}>
                      <span style={{ display: 'flex', alignItems: 'center', gap: 10, minWidth: 0 }}>
                        <span
                          aria-hidden="true"
                          style={{
                            display: 'grid',
                            placeItems: 'center',
                            flex: 'none',
                            width: 23,
                            height: 23,
                            borderRadius: '50%',
                            color: '#9aabc3',
                            background: 'rgba(255, 255, 255, 0.06)',
                            fontSize: '0.68rem',
                            fontVariantNumeric: 'tabular-nums',
                          }}
                        >
                          {String(index + 1).padStart(2, '0')}
                        </span>
                        <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{b.name}</span>
                      </span>
                      <span aria-hidden="true" style={{ color: '#7cc4ff', fontSize: '1.1rem', lineHeight: 1 }}>
                        →
                      </span>
                    </a>
                  </li>
                ))}
              </ul>
            </div>
          )}
          <div className="panel small" style={infoPanelStyle}>
            <p style={eyebrowStyle}>Sky coordinates{m?.epoch ? ` · ${m.epoch}` : ''}</p>
            <h3 style={{ ...sectionHeadingStyle, marginBottom: 13 }}>Where it is</h3>
            <div
              style={{
                padding: '11px 12px',
                border: '1px solid rgba(124, 196, 255, 0.14)',
                borderRadius: 11,
                background: 'rgba(3, 8, 16, 0.38)',
              }}
            >
              <div style={{ color: '#8e97ad', fontSize: '0.69rem', letterSpacing: '0.08em', textTransform: 'uppercase' }}>
                Right ascension · declination
              </div>
              <div style={{ marginTop: 3, color: '#e6f3ff', fontSize: '1.04rem', fontWeight: 650, fontVariantNumeric: 'tabular-nums' }}>
                {formatRaDec(system.center.ra, system.center.dec)}
              </div>
            </div>
            {(m?.distance_pc || (m?.pm_ra_cosdec_mas_yr != null && m?.pm_dec_mas_yr != null)) && (
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(125px, 1fr))', gap: 8, marginTop: 9 }}>
                {m?.distance_pc && (
                  <div style={{ padding: '9px 10px', borderRadius: 10, background: 'rgba(255, 255, 255, 0.035)' }}>
                    <div style={{ color: '#8e97ad', fontSize: '0.69rem' }}>Distance</div>
                    <div style={{ marginTop: 2, fontWeight: 600, fontVariantNumeric: 'tabular-nums' }}>
                      {m.distance_pc} pc <span style={{ color: '#a7b3c7', fontSize: '0.78rem' }}>· {(m.distance_pc * 3.2616).toFixed(1)} ly</span>
                    </div>
                  </div>
                )}
                {m?.pm_ra_cosdec_mas_yr != null && m?.pm_dec_mas_yr != null && (
                  <div style={{ padding: '9px 10px', borderRadius: 10, background: 'rgba(255, 255, 255, 0.035)' }}>
                    <div style={{ color: '#8e97ad', fontSize: '0.69rem' }}>Sky motion</div>
                    <div style={{ marginTop: 2, fontWeight: 600, fontVariantNumeric: 'tabular-nums' }}>
                      {(Math.hypot(m.pm_ra_cosdec_mas_yr, m.pm_dec_mas_yr) / 1000).toFixed(2)}″ / year
                    </div>
                  </div>
                )}
              </div>
            )}
            {/* TODO(WS7-5): "move through space" view using SpaceMotion (parallax + proper motion + RV). */}
            {system.field_id &&
              (fieldExists ? (
                <a
                  href={`#/field/${system.field_id}`}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    gap: 10,
                    marginTop: 12,
                    padding: '10px 12px',
                    border: '1px solid rgba(124, 196, 255, 0.2)',
                    borderRadius: 10,
                    background: 'rgba(124, 196, 255, 0.07)',
                    textDecoration: 'none',
                  }}
                >
                  {fieldSynthetic ? 'See the synthetic demo field (not SPHEREx) →' : 'See it in SPHEREx images →'}
                </a>
              ) : (
                <div
                  className="muted"
                  style={{ marginTop: 12, padding: '9px 11px', borderLeft: '2px solid #68758d', background: 'rgba(255, 255, 255, 0.025)', borderRadius: '0 8px 8px 0' }}
                >
                  {fieldSynthetic
                    ? 'The synthetic demo field for this system is not built yet in this dataset.'
                    : 'SPHEREx images for this target are not built yet in this dataset.'}
                </div>
              ))}
            {system.provenance.notes.length > 0 && (
              <ul
                className="notes"
                style={{ display: 'grid', gap: 6, paddingLeft: 18, margin: '12px 0 0', fontSize: '0.81rem', lineHeight: 1.45 }}
              >
                {system.provenance.notes.map((n, i) => (
                  <li key={i}>{n}</li>
                ))}
              </ul>
            )}
          </div>
          {m && (
            // Where SPHEREx should see the target on its pass dates (prediction from catalog astrometry).
            <ErrorBoundary what="The sky-track panel">
              <Suspense fallback={<div className="panel small muted" style={infoPanelStyle}>Loading the predicted sky track…</div>}>
                <SkyTrackPanel system={system} mjd={datasetMjd} />
              </Suspense>
            </ErrorBoundary>
          )}
        </aside>
      </div>
    </main>
  );
}
