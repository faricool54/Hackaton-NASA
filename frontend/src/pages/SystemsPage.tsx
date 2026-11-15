// #/systems — every tracked object/system that has a 3D model.
import { useEffect, useState } from 'react';
import { client } from '../api/client';
import type { Manifest } from '../api/types';
import { formatRaDec } from '../api/format';
import { SyntheticBadge } from '../components/SyntheticBadge';
import { KIND_LABEL } from '../three/kindLabels'; // astro-free: appearance.ts would pull astro.ts into the main chunk

export function SystemsPage() {
  const [manifest, setManifest] = useState<Manifest | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    client.getManifest().then(setManifest).catch((e: Error) => setError(e.message));
  }, []);

  const systems = manifest?.systems ?? [];
  // The real dataset has no synthetic system: only mention one when this dataset lists it.
  const hasSynthetic = systems.some((s) => s.synthetic);
  return (
    <main>
      <section className="hero">
        <h1>Explore the objects in 3D</h1>
        <p>
          Explore models of the challenge targets{hasSynthetic ? ' and a synthetic example' : ''}. Their parameters were checked against
          the NASA Exoplanet Archive, SIMBAD, Gaia DR3 and the cited papers; values that are only estimates are
          marked as such. Watch model orbits and pulsations, or select a body to inspect its facts, sources and
          verification status.
        </p>
        <p className="muted small">
          These are model representations, not images: sizes are exaggerated and distances can be compressed so
          everything fits on screen. A model of a target does not establish that it has been observed or validated
          in SPHEREx images.
        </p>
      </section>
      {error && <p className="error">Could not load data: {error}</p>}
      {!manifest && !error && <p className="muted">Loading…</p>}
      {manifest && systems.length === 0 && <p className="muted">No 3D systems in this dataset yet.</p>}
      <div className="cards">
        {systems.map((s) => (
          <a key={s.id} className="card" href={`#/system/${s.id}`}>
            <div className="card-body">
              <h3>{s.name}</h3>
              <p className="muted">{s.description}</p>
              <p className="muted small">
                {formatRaDec(s.center.ra, s.center.dec)} · {s.n_bodies} {s.n_bodies === 1 ? 'body' : 'bodies'}
                <br />
                {s.kinds.map((k) => KIND_LABEL[k] ?? k).join(' · ')}
              </p>
              <SyntheticBadge synthetic={s.synthetic} />
            </div>
          </a>
        ))}
      </div>
    </main>
  );
}
