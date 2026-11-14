// #/system/<id>[/<bodyId>] — 3D view of one system; a body id "enters" that body.
import { lazy, Suspense, useEffect, useState } from 'react';
import { client } from '../api/client';
import type { SystemModel } from '../api/types';
import { formatRaDec } from '../api/format';
import { BodyPanel } from '../components/BodyPanel';
import { ErrorBoundary } from '../components/ErrorBoundary';
import { SyntheticBadge } from '../components/SyntheticBadge';
import { SystemViewer } from '../components/SystemViewer';

// The sky-track panel (S4) and its astrometry module load on demand, like the 3D scene, so the
// main chunk does not grow.
const SkyTrackPanel = lazy(() => import('../three/SkyTrackPanel').then((m) => ({ default: m.SkyTrackPanel })));

export function SystemPage({ systemId, bodyId }: { systemId: string; bodyId: string | null }) {
  const [system, setSystem] = useState<SystemModel | null>(null);
  // Field id -> synthetic flag, from the manifest (a field from a synthetic manifest is synthetic).
  const [fields, setFields] = useState<Map<string, boolean>>(new Map());
  const [error, setError] = useState<string | null>(null);

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
            <SystemViewer system={system} selectedId={body?.id ?? null} onSelect={select} />
          </ErrorBoundary>
          <p className="muted small">{system.representation_note}</p>
        </section>
        <aside>
          {body ? (
            <BodyPanel system={system} body={body} fieldExists={fieldExists} fieldSynthetic={fieldSynthetic} />
          ) : (
            <div className="panel">
              <h2>In this system</h2>
              <ul className="body-list">
                {system.bodies.map((b) => (
                  <li key={b.id}>
                    <a href={`#/system/${system.id}/${b.id}`}>{b.name}</a>
                  </li>
                ))}
              </ul>
            </div>
          )}
          <div className="panel small">
            <h3>Where it is</h3>
            <p>
              Sky position{m?.epoch ? ` (${m.epoch})` : ''}: {formatRaDec(system.center.ra, system.center.dec)}
              {m?.distance_pc && (
                <>
                  <br />
                  Distance: {m.distance_pc} pc ({(m.distance_pc * 3.2616).toFixed(1)} light-years)
                </>
              )}
              {m?.pm_ra_cosdec_mas_yr != null && m?.pm_dec_mas_yr != null && (
                <>
                  <br />
                  Moves across the sky: {(Math.hypot(m.pm_ra_cosdec_mas_yr, m.pm_dec_mas_yr) / 1000).toFixed(2)}″ per
                  year
                </>
              )}
            </p>
            {/* The predicted sky track (proper motion + parallax + RV) is the panel below; a 3D
                "move through space" view is still TODO(WS7-5). */}
            {system.field_id &&
              (fieldExists ? (
                <a href={`#/field/${system.field_id}`}>
                  {fieldSynthetic ? 'See the synthetic demo field (not SPHEREx) →' : 'See it in SPHEREx images →'}
                </a>
              ) : (
                <span className="muted">
                  {fieldSynthetic
                    ? 'The synthetic demo field for this system is not built yet in this dataset.'
                    : 'SPHEREx images for this target are not built yet in this dataset.'}
                </span>
              ))}
            {system.provenance.notes.length > 0 && (
              <ul className="notes">
                {system.provenance.notes.map((n, i) => (
                  <li key={i}>{n}</li>
                ))}
              </ul>
            )}
          </div>
          {m && (
            // Where SPHEREx should see the target on its pass dates (prediction from catalog astrometry).
            <ErrorBoundary what="The sky-track panel">
              <Suspense fallback={<div className="panel small muted">Loading the predicted sky track…</div>}>
                <SkyTrackPanel system={system} />
              </Suspense>
            </ErrorBoundary>
          )}
        </aside>
      </div>
    </main>
  );
}
