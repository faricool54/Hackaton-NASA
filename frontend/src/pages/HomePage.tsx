import { useEffect, useState } from 'react';
import { ApiError, client } from '../api/client';
import type { Manifest } from '../api/types';
import { formatMjd, formatRaDec } from '../api/format';
import { SyntheticBadge } from '../components/SyntheticBadge';
import { SkyExplorer } from '../components/SkyExplorer';

export function HomePage() {
  const [manifest, setManifest] = useState<Manifest | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [empty, setEmpty] = useState(false);

  useEffect(() => {
    client.getManifest().then(setManifest).catch((e: Error) => {
      if (client.config.mode === 'api' && e instanceof ApiError && e.status === 404) setEmpty(true);
      else setError(e.message);
    });
  }, []);

  return (
    <main>
      <section className="hero">
        <h1>Watch the infrared sky change</h1>
        <p>
          NASA's SPHEREx telescope maps the whole sky in 102 infrared colors, again and again. Comparing dates
          can reveal moving objects, nearby stars with proper motion, and changes in brightness. Explore the
          sky map, choose a position, and build a sequence of real observations. Curated fields are also available below.
        </p>
        <p>
          <a href={`${import.meta.env.BASE_URL}?mode=static&dataset=real#/`}>Browse the five real challenge fields →</a>
          {' · '}
          <a href="#/systems">Explore illustrative 3D models of the challenge targets →</a>
        </p>
        {/* TODO(WS6): final copy, project name, call to action. TODO(WS5): coordinate/name search box (api mode). */}
      </section>

      <SkyExplorer />
      {error && <p className="error">Could not load curated fields: {error}</p>}
      {empty && <p className="muted">No curated fields yet. Build your first sequence above.</p>}
      {!manifest && !error && !empty && <p className="muted">Loading…</p>}
      {manifest && (
        <section>
          <h2>
            Available sequences <SyntheticBadge synthetic={manifest.synthetic} />
          </h2>
          <div className="cards">
            {manifest.fields.map((f) => (
              <a key={f.id} className="card" href={`#/field/${f.id}`}>
                {f.thumbnail && (
                  <img src={client.fieldFileUrl(f.id, f.thumbnail)} alt="" className="thumb" loading="lazy" />
                )}
                <div className="card-body">
                  <h3>{f.id.startsWith('job-') ? `SPHEREx at ${formatRaDec(f.center.ra, f.center.dec)}` : f.name}</h3>
                  <p className="muted">{f.description}</p>
                  <p className="muted small">
                    {formatRaDec(f.center.ra, f.center.dec)} · {f.n_frames} frames · {f.n_candidates} candidates
                    {f.mjd_range && (
                      <>
                        <br />
                        {formatMjd(f.mjd_range[0])} → {formatMjd(f.mjd_range[1])}
                      </>
                    )}
                  </p>
                  <SyntheticBadge synthetic={f.synthetic} />
                </div>
              </a>
            ))}
          </div>
        </section>
      )}
    </main>
  );
}
