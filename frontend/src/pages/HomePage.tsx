import { useEffect, useState } from 'react';
import { client } from '../api/client';
import type { Manifest } from '../api/types';
import { formatMjd, formatRaDec } from '../api/format';
import { SyntheticBadge } from '../components/SyntheticBadge';

export function HomePage() {
  const [manifest, setManifest] = useState<Manifest | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    client.getManifest().then(setManifest).catch((e: Error) => setError(e.message));
  }, []);

  return (
    <main>
      <section className="hero">
        <h1>Watch the infrared sky change</h1>
        <p>
          NASA's SPHEREx telescope maps the whole sky in 102 infrared colors, again and again. Stars stay put.
          Asteroids, distant icy worlds and nearby cold brown dwarfs move. Pick a patch of sky, blink between
          observations taken at different times, and see what wanders — the same way astronomers hunt for a
          hypothetical Planet X.
        </p>
        {/* TODO(WS6): final copy, project name, call to action. TODO(WS5): coordinate/name search box (api mode). */}
      </section>

      {error && <p className="error">Could not load data: {error}</p>}
      {!manifest && !error && <p className="muted">Loading…</p>}
      {manifest && (
        <section>
          <h2>
            Fields <SyntheticBadge synthetic={manifest.synthetic} />
          </h2>
          <div className="cards">
            {manifest.fields.map((f) => (
              <a key={f.id} className="card" href={`#/field/${f.id}`}>
                {f.thumbnail && (
                  <img src={client.fieldFileUrl(f.id, f.thumbnail)} alt="" className="thumb" loading="lazy" />
                )}
                <div className="card-body">
                  <h3>{f.name}</h3>
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
