// About / science / honesty page. Owner: WS6 (copy) + WS3 (science review).
export function AboutPage() {
  return (
    <main className="prose">
      <h1>About Errante</h1>
      <h2>Explore the changing infrared sky</h2>
      <p>
        Errante is a public explorer of real observations from NASA’s SPHEREx mission. Search by name or
        sky coordinates, or click the map, to build a dated sequence of images. Play, pause, step through
        frames and compare detectors, with source and wavelength information alongside the images.
      </p>
      <p>
        The map shows the SPHEREx DR1 infrared sky cube through Aladin Lite. It is a static coadd;
        the time sequence is built separately from individual observations. The optional AllWISE layer
        provides context from another mission, not another SPHEREx epoch.
      </p>
      <h2>What is SPHEREx?</h2>
      <p>
        SPHEREx is a NASA space telescope launched in 2025 that maps the entire sky in 102 infrared wavelengths
        between 0.75 and 5 µm. It covers the whole sky every six months, and observes two deep fields near the
        ecliptic poles far more often.
      </p>
      <h2>Real data and scientific context</h2>
      <p>
        The public application uses real SPHEREx DR1 and QR3 images from NASA/IPAC IRSA. Five showcase fields
        contain 40 frames each: Barnard’s Star, Epsilon Indi B, WISE 0855-0714, RW Aurigae and R Draconis.
        Coordinate jobs build additional sequences where archive coverage is available. Spectra, season
        comparisons, catalog context and precomputed light curves provide complementary evidence.
        Separate synthetic development fixtures remain explicitly labelled.
      </p>
      <h2>What the five targets show</h2>
      <p>
        Offline analyses of the scientific FITS files recover known motion in Barnard’s Star, Epsilon Indi B
        and WISE 0855-0714, and brightness changes in RW Aurigae and R Draconis. Separate agents re-measured
        the results. DankoLiv signed the five records after a guided human review on November 15, 2026;
        the analyses were not rerun during that review. This sign-off is distinct from browser playback,
        deployment checks and a line-by-line code review. No new astronomical discovery is claimed.
      </p>
      <p>
        Motion is only about 1–2 native pixels over the available baselines. Saturation and faint sources
        can hide changes in the displayed previews. WISE 0855 is detected at the longest wavelengths
        (3.8–5.0 µm), with stronger evidence from combined exposures. Epsilon Indi Ba and Bb are unresolved.
        Display PNG brightness is not calibrated photometry.
      </p>
      <h2>Reading light curves and spectra</h2>
      <p>
        Brightness comparisons need compatible wavelengths and quality checks. Each spectral sample may
        come from a different date, so a variable star’s brightness changes can mix with its spectral shape.
        A difference between images is not automatically a change in the object itself.
      </p>
      <p>
        RW Aurigae’s light curve measures the unresolved A+BC system. Saturated measurements are excluded,
        preferentially removing bright states; it is not a complete brightness history and establishes no
        period. R Draconis’s published light curve uses wide-survey DR1+QR3 observations, excluding the deep
        collections in the larger offline analysis. Its saturated core requires relative PSF-wing photometry,
        not a measurement of total flux.
      </p>
      <p>
        Light-curve error bars are statistical and do not include all systematic uncertainties.
        Published relative magnitudes do not apply comparison-star zero-point corrections. A significant
        period test indicates time-ordered variability; it does not confirm a unique physical period.
      </p>
      <h2>3D models and candidates</h2>
      <p>
        The 3D gallery provides catalog-based context with sources and representation notes. These are
        models, not SPHEREx images, resolved surfaces or measured orbital phases. Catalog parameters and
        illustrative choices are identified in the models. SPHEREx-derived temperature, radius and
        physical 3D reconstruction are not claimed as implemented measurements.
      </p>
      <p>
        Automatic detection is optional. An <strong>unconfirmed</strong> candidate may be an artifact,
        a measurement error, or an object not matched to a catalog. Empty candidate lists do not establish
        a negative detection result. Errante does not claim a Planet X discovery.
      </p>
      <h2>Sources and acknowledgments</h2>
      <p>
        This research has made use of the NASA/IPAC Infrared Science Archive, which is funded by the
        National Aeronautics and Space Administration and operated by the California Institute of Technology.
        {' '}<a href="https://irsa.ipac.caltech.edu/ack.html">IRSA acknowledgment and citation guidance</a>.
      </p>
      <p>
        This publication makes use of data products from the Spectro-Photometer for the History of the
        Universe, Epoch of Reionization and Ices Explorer (SPHEREx), which is a joint project of the Jet
        Propulsion Laboratory and the California Institute of Technology, and is funded by the National
        Aeronautics and Space Administration.
      </p>
      <ul>
        <li><a href="https://irsa.ipac.caltech.edu/Missions/spherex.html">NASA/IPAC IRSA</a>:
          SPHEREx images, archive search, DR1 cube and HiPS.
          {' '}Data DOIs: DR1 spectral images{' '}
          <a href="https://doi.org/10.26131/IRSA678">10.26131/IRSA678</a>; QR3 spectral images{' '}
          <a href="https://doi.org/10.26131/IRSA662">10.26131/IRSA662</a>; DR1 spectral all-sky cube{' '}
          <a href="https://doi.org/10.26131/IRSA679">10.26131/IRSA679</a>.
          {' '}<a href="https://caltech-ipac.github.io/irsa-tutorials/spherex/">IRSA tutorials</a> informed development.</li>
        <li><a href="https://aladin.cds.unistra.fr/AladinLite/">Aladin Lite 3.8.2</a> (CDS, GPL-3): sky viewer.
          AllWISE color HiPS (NASA/IPAC/CDS, ESA ESASky mirror): optional map context.</li>
        <li>Sesame, SIMBAD and VizieR (CDS, through the CfA mirror), Gaia DR3, 2MASS and CatWISE2020:
          catalog positions, motion and source identity.</li>
        <li>AAVSO International Database: observations used in the offline R Draconis phase comparison.</li>
        <li>WiseView: inspiration for temporal image comparison. Astropy and the credited open-source
          dependencies support scientific processing and display.</li>
      </ul>
      <p>
        This work has made use of data from the European Space Agency (ESA) mission Gaia
        {' '}(<a href="https://www.cosmos.esa.int/gaia">Gaia</a>), processed by the Gaia Data Processing
        and Analysis Consortium (<a href="https://www.cosmos.esa.int/web/gaia/dpac/consortium">DPAC</a>).
        Funding for the DPAC has been provided by national institutions, in particular the institutions
        participating in the Gaia Multilateral Agreement.
      </p>
      <p>
        This research has made use of the <a href="https://exoplanetarchive.ipac.caltech.edu/">NASA Exoplanet Archive</a>,
        which is operated by the California Institute of Technology, under contract with the National
        Aeronautics and Space Administration under the Exoplanet Exploration Program. Confirmed planets
        provide catalog context; they are not detections in these SPHEREx images.
      </p>
      <h2>AI-assisted development</h2>
      <p>
        OpenAI Codex and Anthropic Claude Code assisted contributors with documentation, implementation,
        integration, tests, deployment and scientific analysis/review. Scientific records include independent
        agent re-measurements; that is not human review. The team is completing the full contribution,
        source and asset inventory before submission. Real FITS-derived images and plots are processed
        observations, not invented sky imagery; synthetic fixtures are labelled separately.
      </p>
    </main>
  );
}
