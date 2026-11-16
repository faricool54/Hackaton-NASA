// #/systems — every tracked object/system that has a 3D model.
import { useEffect, useState } from 'react';
import { client } from '../api/client';
import type { Manifest } from '../api/types';
import { formatRaDec } from '../api/format';
import { SyntheticBadge } from '../components/SyntheticBadge';
import { KIND_LABEL } from '../three/kindLabels'; // astro-free: appearance.ts would pull astro.ts into the main chunk
import '../three/system.css';

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
      <section className="hero s3d-hero">
        <h1>Explore the objects in 3D</h1>
        <p>
          Explore models of the challenge targets{hasSynthetic ? ' and a synthetic example' : ''}. Their parameters were checked against
          the NASA Exoplanet Archive, SIMBAD, Gaia DR3 and the cited papers; values that are only estimates are
          marked as such. Watch model orbits and pulsations, or select a body to inspect its facts, sources and
          verification status.
        </p>
        <p>
          What SPHEREx measured for each target is listed as “Seen by SPHEREx”. Every other value is a catalog or derived
          value, not measured by SPHEREx. What is not measured is not invented: a body without a published temperature is
          drawn grey (colour unknown), and one without a published or model-estimated radius at a fixed marker size (size unknown, not to scale).
        </p>
        <p className="s3d-hero-note">
          These are model representations, not images: sizes are exaggerated and distances can be compressed so
          everything fits on screen. A model of a target does not establish that it has been observed or validated
          in SPHEREx images.
        </p>
      </section>
      {error && <p className="error">Could not load data: {error}</p>}
      {!manifest && !error && <p className="muted">Loading…</p>}
      {manifest && systems.length === 0 && <p className="muted">No 3D systems in this dataset yet.</p>}
      <div className="s3d-cards">
        {systems.map((s) => (
          <a key={s.id} className="s3d-card" href={`#/system/${s.id}`}>
            <h3>{s.name}</h3>
            <p className="s3d-card-badges">
              <span className="badge u-badge u-badge--model">3D MODEL · NOT AN IMAGE</span>
              <SyntheticBadge synthetic={s.synthetic} />
            </p>
            <p className="s3d-card-desc">{s.description}</p>
            <p className="s3d-card-meta">
              <span className="u-mono">{formatRaDec(s.center.ra, s.center.dec)}</span> · {s.n_bodies}{' '}
              {s.n_bodies === 1 ? 'body' : 'bodies'}
            </p>
            <p className="s3d-kinds">
              {s.kinds.map((k, i) => (
                <span key={`${k}-${i}`} className="s3d-kind">
                  {KIND_LABEL[k] ?? k}
                </span>
              ))}
            </p>
            <span className="s3d-card-open" aria-hidden="true">
              Open the 3D model →
            </span>
          </a>
        ))}
      </div>
    </main>
  );
}
