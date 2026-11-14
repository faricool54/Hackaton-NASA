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
      <h2>Why compare different dates?</h2>
      <p>
        Comparing observations can reveal moving objects, nearby stars with proper motion, and stars whose
        brightness changes. Brightness comparisons also need compatible wavelengths and quality checks:
        a change between images is not automatically a change in the object itself.
      </p>
      <h2>Current project status</h2>
      <p>
        This application currently demonstrates temporal playback with <strong>numerically simulated data</strong>.
        The images are labelled as synthetic and are not SPHEREx observations. Real-data access, public
        coordinate requests and validation of the five challenge targets are still being developed. Automatic
        detection and catalog matching are optional analysis stages.
      </p>
      <p>
        An optional 3D gallery illustrates the challenge targets with hand-entered, unverified parameters.
        These models are not SPHEREx images, measured orbits or completed validation runs.
      </p>
      <h2>Interpreting candidates</h2>
      <p>
        An <strong>unconfirmed</strong> candidate is one that has not been matched to a
        catalog: it may be an artifact, a measurement error, or an object that is simply not cataloged. We do{' '}
        <strong>not</strong> claim a discovery or a real-object recovery from synthetic examples.
      </p>
      <h2>Sources and acknowledgments</h2>
      <p className="muted">
        Development references include the{' '}
        <a href="https://irsa.ipac.caltech.edu/Missions/spherex.html">NASA/IPAC IRSA SPHEREx resources</a>{' '}
        and the{' '}
        <a href="https://caltech-ipac.github.io/irsa-tutorials/spherex/">IRSA tutorial notebooks</a>.
        Real SPHEREx products from NASA/JPL-Caltech/IPAC have not yet been integrated into this demonstration.
      </p>
      <h2>AI-assisted development</h2>
      <p>
        OpenAI Codex assisted with source review, documentation, technical planning, implementation and tests.
        A written disclosure and metadata inventory are maintained in the project repository. The team is
        completing the provenance review of earlier contributions and assets before submission.
        The imported 3D contribution declares Claude assistance in its commit metadata.
      </p>
    </main>
  );
}
