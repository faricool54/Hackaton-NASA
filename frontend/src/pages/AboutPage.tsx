// About / science / honesty page. Owner: WS6 (copy) + WS3 (science review).
export function AboutPage() {
  return (
    <main className="prose">
      <h1>About</h1>
      <h2>What is SPHEREx?</h2>
      <p>
        SPHEREx is a NASA space telescope launched in 2025 that maps the entire sky in 102 infrared wavelengths
        between 0.75 and 5 µm. It covers the whole sky every six months, and observes two deep fields near the
        ecliptic poles far more often.
      </p>
      <h2>Why look for things that move?</h2>
      <p>
        Planets were named for wandering (Greek <em>planḗtēs</em>, “wanderer”). Anything in our solar system shifts
        against the background stars between observations. The hypothetical Planet X (or “Planet Nine”), if it
        exists hundreds of times farther than Earth from the Sun, would crawl only a few arcseconds per hour.
      </p>
      <h2>What we do — and what we don’t claim</h2>
      <p>
        We show real SPHEREx images taken at different times, detect moving sources, and check them against
        catalogs of known objects. An <strong>unconfirmed</strong> candidate is one we could not match to a
        catalog: it may be an artifact, a measurement error, or an object that is simply not cataloged. We do{' '}
        <strong>not</strong> claim to have discovered Planet X.
      </p>
      {/* TODO(WS6): data credits (NASA/JPL-Caltech/IPAC IRSA, JPL SSD, IMCCE SkyBoT), team, AI-use statement,
          pipeline diagram, measured detection limits from WS2 (injection-recovery). */}
      <h2>Data credits</h2>
      <p className="muted">
        SPHEREx data: NASA / JPL-Caltech / IPAC, via the NASA/IPAC Infrared Science Archive (IRSA). Solar-system
        ephemerides: JPL Solar System Dynamics; IMCCE SkyBoT.
      </p>
    </main>
  );
}
