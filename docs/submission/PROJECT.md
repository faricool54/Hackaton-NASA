# Project submission draft - Errante

**Technical status updated November 15, 2026. Team review is still required before submission.**
The application is public and uses real SPHEREx observations. Remaining submission items are the final
demo link, team/member details, source and AI inventory review, and confirmation of submission.

Local Event: **Universidad de Palermo, Buenos Aires, Argentina**. Guide-based deadline:
**November 15, 2026 at 23:59 ART (UTC-3)**; internal submission target: **21:00 ART**.
Confirm the Local Lead's judging schedule separately. Verify all accepted members, including the Team Owner,
on the same event's Members tab before the deadline.

## Project Name

Errante - watch the infrared sky change.

## High-Level Project Summary

Errante is a public explorer of NASA SPHEREx observations. Search by name or sky coordinates, or click
an infrared sky map, to build and play a dated sequence of real images. Five showcase fields offer
immediate access to the challenge targets. Spectra, season comparisons, catalog context and precomputed
light curves help investigate what changes, while provenance and quality information explain the limits.
Offline FITS analyses recover known motion and variability; small shifts, saturation and faint sources
mean those results are not necessarily visible in the displayed images. No new discovery is claimed.

## Link to Project Demo

TODO: add the public external URL for a **video no longer than 30 seconds OR a deck of no more than
7 slides**, including title and introduction. Include the team, members and challenge. Use English;
non-English narration needs English subtitles. Check duration/count and anonymous access.

## Link to Final Project

- [Open the public application](https://errante.34-148-242-13.sslip.io).
- [About, methods and credits](https://errante.34-148-242-13.sslip.io/#/about).
- [Source repository](https://github.com/faricool54/Hackaton-NASA), currently private; it is not the public
  access route for judges. Do not substitute this link for the application.
- The application and API share one HTTPS origin on Google Compute Engine. The address uses third-party
  sslip.io DNS; a custom domain is optional. Keep the submitted address available during judging.

## Detailed Project Description

### Challenge, user and benefit

Planet X and SPHEREx - NASA Space Apps Challenge 2026. SPHEREx's repeated infrared observations contain
motion and brightness changes, but comparing the underlying scientific files requires specialist tools.
Errante lets learners and citizen scientists explore a sky position in a browser, with dates, detector
and wavelength context alongside the images. Easier access is the intended benefit; user impact has not
yet been measured in a completed independent user study.

### Behavior and implementation status

- **Interactive map:** Aladin Lite displays IRSA's SPHEREx DR1 HiPS sky cube with a wavelength selector and
  optional AllWISE context. This map is a static coadd; the time sequence is built separately.
- **Coordinate-to-sequence workflow:** name resolution, RA/Dec and map clicks feed persistent jobs that
  search the archive, extract real FITS cutouts, align them and publish images. Progress, errors and
  no-coverage outcomes are explicit. Coverage and external archive availability constrain each request.
- **Temporal viewing:** play/pause, frame stepping, speed, detector selection, dates and source metadata.
  Five precomputed real fields contain 40 frames each. Image viewing does not require automatic detection.
- **Scientific context:** position spectra from the DR1 cube or L2 exposures, compatible season comparisons,
  catalog object cards and precomputed light-curve panels for RW Aurigae and R Draconis.
- **3D context:** catalog-based models link to the showcase targets and identify their sources and
  representation limits. They are models, not SPHEREx images or measured orbits. Building physical models
  from SPHEREx-derived temperature/radius remains separate work; no such inference is claimed here.
- **Development fixtures:** a separate numerical synthetic dataset remains available and labelled.
  It is not the data used by the public real-data application.

### How it works

Coordinates -> archive search or cached coverage -> FITS cutouts -> a common sky grid and display PNGs
-> temporal viewer. Images retain source URIs, observation dates, detector and release information.
Spectra and brightness measurements are extracted from scientific data, not from display PNG values.
The backend provides bounded jobs, caching and persistent runtime storage. The frontend and FastAPI API
run together behind HTTPS; the application does not depend on a teammate's local computer.

### Validation and limitations

These results summarize the [five validation records](../validation/) and [WS3's review](../SCIENCE.md).
They are offline FITS analyses with separate agent-based re-measurements, not five visual detections in
the browser. Human review remains pending. Technical deployment checks do not certify scientific results.

| Target | Offline result and interpretation limit |
|---|---|
| Barnard's Star | About 10.2 arcsec (1.66 SPHEREx pixels) of motion between the Aug 2025 and Aug 2026 seasons, consistent with the catalog prediction; 358 exposures. The core saturates in 357/358, so positions use the PSF wings. This does not establish parallax. |
| Epsilon Indi B | Ba+Bb are unresolved. About 1.03 pixels of motion between the May 2025 and Sep 2026 seasons agrees with the catalog prediction. No claim of resolving the pair or measuring its orbit. |
| WISE 0855-0714 | Detected at 3.8-5.0 micrometres (D5-D6); about 8.4-8.5 arcsec of motion in 360 days, with blending by a background source. Combined exposures provide much stronger evidence than the faint single frames. DR1 only. |
| RW Aurigae | About 1 mag of brightening at 0.75-0.77 micrometres between Sep 2025 and Sep 2026 in matched-wavelength, unsaturated D1 exposures. A+BC are unresolved. Saturation removes bright states and prevents a complete light curve; no period is established. |
| R Draconis | The core saturates in every usable exposure. Relative PSF-wing photometry shows 0.5-1.3 mag variation and an effective cycle around 260 days in the offline analysis. This is not absolute flux or a uniquely confirmed period. |

The app's R Draconis light curve uses **wide-survey DR1+QR3 only**, not the deep observations included in
the larger offline record. RW Aurigae's curve excludes saturated measurements, preferentially removing
bright states. Narrow wavelength bins, incomplete sampling and systematic errors limit interpretation.
Displayed error bars distinguish statistical uncertainties from empirical error floors; period significance
indicates time-ordered variability, not a unique physical period. Comparison-star zero-point corrections
are not applied to published relative magnitudes. The published light-curve panels now display limits, error floors, data selection and
candidate-period/alias warnings (#97). Additional detector/phase/matched-pair views remain pending.

Motion is only about 1-2 native pixels over these baselines. Saturated cores, display stretching and
faintness can hide changes in the 40-frame previews. Zoom and a catalog-predicted Barnard reticle are
published (#96); the reticle is not measured astrometry. Mobile layout corrections were checked at
390 px, while human testing on physical phones remains pending. No automatic discovery, Planet X
detection, measured distance, temperature or radius from SPHEREx is claimed.

### Contribution and evidence for judging

Errante combines a sky map, coordinate jobs, image playback and scientific context in one public workflow.
WiseView and IRSA tools are credited inspirations. The contribution is the working integration and its
traceable data/limitations, not a claim to have invented blink comparison. NASA observations drive both
the viewer and scientific products. User testing, the final demo and human review remain separate tasks.

### Tools and team

Python, NumPy, Astropy, Pydantic, Pillow, Requests and scientific processing dependencies; FastAPI/Uvicorn;
React, TypeScript, Vite, Three.js; Aladin Lite 3.8.2 (GPL-3); Docker, Caddy and Google Compute Engine.
Automated validation uses pytest, Ruff, JSON Schema and Vitest.

TODO: confirm team name, member names/roles and accepted registration. Review the complete dependency
and asset/license inventory before submitting.

## Use of Super Intelligence (SI)

Yes. OpenAI Codex assisted with review, documentation, implementation, integration, tests, deployment and
this submission/About update. Anthropic Claude Code assisted contributors with data access, scientific
analysis/review, catalog context and 3D work. Separate agents re-measured scientific results; that is not
human review. Scope and metadata are recorded in [AI_USAGE.md](../../AI_USAGE.md),
[submission metadata](ai-usage.json) and component inventories.

The team-stated vision and Claude's feasibility/documentation role are recorded in [VISION.md](../VISION.md);
the earlier agent-drafted outline was rejected. Team confirmation of the full idea-origin record,
earlier scaffold/assets and all contributors' tool use is still required. Real FITS-derived images and
plots are data processing, not invented sky imagery. Synthetic fixtures remain labelled. Review generated
media, metadata, source permissions and branding; this draft does not claim a complete authorship audit.

## NASA Data

The application uses **real SPHEREx L2 observations from DR1 and QR3**, served through NASA/IPAC IRSA,
plus the DR1 spectral cube and its HiPS representation. Products retain observation IDs, dates,
detector/release and source URIs. The separate offline R Draconis analysis also uses deep collections;
those are not included in the published precomputed light curve.

This publication makes use of data products from the Spectro-Photometer for the History of the Universe,
Epoch of Reionization and Ices Explorer (SPHEREx), which is a joint project of the Jet Propulsion
Laboratory and the California Institute of Technology, and is funded by the National Aeronautics and
Space Administration.

- [NASA/IPAC IRSA SPHEREx data and documentation](https://irsa.ipac.caltech.edu/Missions/spherex.html).
- [IRSA SPHEREx tutorial notebooks](https://caltech-ipac.github.io/irsa-tutorials/spherex/).
- [NASA Exoplanet Archive](https://exoplanetarchive.ipac.caltech.edu/): confirmed-planet catalog context,
  not planets detected in SPHEREx images. This research has made use of the NASA Exoplanet Archive, which
  is operated by the California Institute of Technology, under contract with the National Aeronautics and
  Space Administration under the Exoplanet Exploration Program.

## Space Agency Partner Data and Other References

- Gaia DR3 catalog astrometry provides reference positions and motions, not SPHEREx distance measurements.
  This work has made use of data from the European Space Agency (ESA) mission Gaia
  (https://www.cosmos.esa.int/gaia), processed by the Gaia Data Processing and Analysis Consortium (DPAC,
  https://www.cosmos.esa.int/web/gaia/dpac/consortium). Funding for the DPAC has been provided by national
  institutions, in particular the institutions participating in the Gaia Multilateral Agreement.
- AllWISE color context: NASA WISE/NEOWISE products, HiPS by CDS through the ESA ESASky mirror;
  separate from SPHEREx observations.
- Sesame, SIMBAD and VizieR through the CfA mirror; 2MASS and CatWISE2020 for identity checks.
- AAVSO International Database observations inform the offline R Draconis phase comparison.
- [Aladin Lite](https://aladin.cds.unistra.fr/AladinLite/) (CDS, GPL-3), Astropy and other dependencies;
  WiseView as an interaction reference. NEOSSat/CADC were consulted as challenge resources, not used
  as substitutes for SPHEREx images.
- The supplied [Project Submission Guide](<../references/NASA Space Apps Challenge.pdf>) and
  [Judging & Awards Guide](<../references/NASA Space Apps Challenge Judging & Awards Guide.pdf>) inform
  the submission process; the original PDFs are preserved unchanged.

TODO: complete the exact resource, code, image and license inventory with the team. Final materials and
links must be public and in English. Save Progress is not submission: confirm Submit for Judging and
retain the confirmation before the deadline.
