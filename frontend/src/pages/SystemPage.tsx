// #/system/<id>[/<bodyId>] — 3D view of one system; a body id "enters" that body.
import { useEffect, useState } from 'react';
import { client } from '../api/client';
import type { SystemModel } from '../api/types';
import { formatRaDec } from '../api/format';
import { BodyPanel } from '../components/BodyPanel';
import { SyntheticBadge } from '../components/SyntheticBadge';
import { SystemViewer } from '../components/SystemViewer';

export function SystemPage({ systemId, bodyId }: { systemId: string; bodyId: string | null }) {
  const [system, setSystem] = useState<SystemModel | null>(null);
  const [fieldIds, setFieldIds] = useState<Set<string>>(new Set());
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setSystem(null);
    setError(null);
    client.getSystem(systemId).then(setSystem).catch((e: Error) => setError(e.message));
    client
      .getManifest()
      .then((m) => setFieldIds(new Set(m.fields.map((f) => f.id))))
      .catch(() => setFieldIds(new Set()));
  }, [systemId]);

  const select = (id: string | null) => {
    window.location.hash = id ? `#/system/${systemId}/${id}` : `#/system/${systemId}`;
  };

  if (error) return <main className="error">Could not load system “{systemId}”: {error}</main>;
  if (!system) return <main className="muted">Loading…</main>;

  const body = bodyId ? system.bodies.find((b) => b.id === bodyId) ?? null : null;
  const unverified = system.bodies.some((b) => b.facts.some((f) => !f.verified));
  const fieldExists = !!system.field_id && fieldIds.has(system.field_id);
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
          <span className="badge unverified-badge" title="Some values have not been checked against catalogs yet">
            UNVERIFIED VALUES
          </span>
        )}
      </h1>
      <p className="muted">{system.description}</p>

      <div className="field-layout">
        <section>
          <SystemViewer system={system} selectedId={body?.id ?? null} onSelect={select} />
          <p className="muted small">{system.representation_note}</p>
        </section>
        <aside>
          {body ? (
            <BodyPanel system={system} body={body} fieldExists={fieldExists} />
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
              Sky position: {formatRaDec(system.center.ra, system.center.dec)}
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
            {/* TODO(WS7-5): "move through space" view using SpaceMotion (parallax + proper motion + RV). */}
            {system.field_id &&
              (fieldExists ? (
                <a href={`#/field/${system.field_id}`}>See it in SPHEREx images →</a>
              ) : (
                <span className="muted">SPHEREx images for this target are not built yet in this dataset.</span>
              ))}
            {system.provenance.notes.length > 0 && (
              <ul className="notes">
                {system.provenance.notes.map((n, i) => (
                  <li key={i}>{n}</li>
                ))}
              </ul>
            )}
          </div>
        </aside>
      </div>
    </main>
  );
}
