# Project submission draft - Errante

**Draft: not ready for submission.** Complete team names, public links, measured outcomes and source/AI
review before copying into the Project page. The field headings below follow the team-provided Project
Submission Guide (pages 6-9). No character limit for these fields is specified in that PDF.

Local Event confirmed by the team: **Universidad de Palermo, Buenos Aires, Argentina**.
Guide-based deadline: **November 15, 2026 at 23:59 ART (UTC-3)**. Internal submission target: **21:00 ART**.
Local judging times still require confirmation with the Local Lead. For this Local Event, verify **1–6
accepted members**, including the Team Owner at the same event and everyone on the Members tab, before
the deadline; the guide does not permit adding members after submission closes. Registration is not yet verified.

## Project Name

Errante - watch the infrared sky change (working title; team confirmation pending).

## High-Level Project Summary

Errante is being developed as a public temporal explorer for NASA SPHEREx images. Users will enter right
ascension and declination and play aligned observations of the same sky region to inspect motion and
brightness changes. The validation plan covers Barnard's Star, Epsilon Indi B, WISE 0855, RW Aurigae and
R Draconis. Image viewing is independent of optional automatic detection. Planned enhancements include
wavelength selection, detector coadds, image arithmetic, configurable field of view, Gaia/WISE context,
coordinate URLs and quality metadata. The current application is a labelled synthetic demonstration;
real-data access, public coordinate requests and the five validation runs are still pending. Replace this
status with verified outcomes before submission, without describing planned features as completed work.

## Link to Project Demo

TODO: public external URL for a **video no longer than 30 seconds OR a deck of no more than 7 slides**,
including title and introduction. All slides must be in English. A video narrated in another language
requires English subtitles. Check the final file's duration/count and anonymous access.

## Link to Final Project

- Public application: TODO; deployment is pending.
- Source repository: [Hackaton-NASA](https://github.com/faricool54/Hackaton-NASA).
- The repository is currently private; it does not by itself satisfy anonymous access for judges.
- Verify the final link without login, registration, passwords or permission requests.

## Detailed Project Description

### Challenge, user and benefit

Planet X and SPHEREx - NASA Space Apps Challenge 2026. The intended users are learners and citizen
scientists who want to inspect how the infrared sky changes without handling large scientific FITS files.
The intended benefit is a clear coordinate-to-sequence workflow with dates, wavelength context and honest
quality information. User benefit remains to be tested rather than assumed.

### Behavior and implementation status

- Required: public RA/Dec input, real SPHEREx temporal image sequences and usable playback.
- Required validation: all five named targets, with identity, coordinates/epochs, provenance and evidence.
- Available: numerical synthetic fields, playback, detector filter, candidate/spectrum examples, product API
  and shared schemas. The image build is separated from optional analysis.
- Available extension: a 3D gallery with five target-system presets and a synthetic orbital example.
  These are illustrative models with hand-entered, unverified parameters, not SPHEREx images or validation results.
- Pending: archive search/cutouts/reprojection, coordinate-build jobs, public deployment and five real tests.
- Optional challenge considerations: releases, bands/coadds/spectra, addition/subtraction, FOV,
  Gaia DR3/WISE, coordinate URLs/embedding, contamination metadata and public astronomy tools.
- Team extensions: detection, JPL/SkyBoT matching, distance estimates, sensitivity tests and Planet X context.

### How it works

Target flow: coordinates -> archive/cached coverage -> FITS cutouts -> aligned grid and PNGs -> temporal
viewer. Images are saved before optional analysis; `--analyze` opts into those later stages. Static mode
currently reads prebuilt fields. The public service for arbitrary coordinates is not implemented yet.

### Validation and limitations

| Target | Observed result |
|---|---|
| Barnard's Star | Pending real-data test |
| Epsilon Indi B | Pending real-data test and component identity check |
| WISE 0855 | Pending real-data test and epoch/astrometry verification |
| RW Aurigae | Pending compatible-wavelength brightness comparison |
| R Draconis | Pending compatible-wavelength brightness comparison |

Report attempts separately from positive results. Synthetic examples do not establish a real recovery,
spectrum, sensitivity or discovery. Unconfirmed sources may be artifacts, measurement errors or
uncatalogued objects. No discovery of Planet X is claimed.

### Contribution and evidence for judging

The team is developing an accessible temporal workflow for SPHEREx. WiseView and IRSA tools are credited
as references; the team must identify a meaningful, demonstrated contribution rather than claim novelty
for an existing blink interaction or a planned feature. The separated image/analysis build and shared
contracts are implemented engineering choices, not evidence of a new astronomical result.
The optional 3D gallery is an implemented presentation layer; its parameters, source claims and field links
still require validation. Showing a model for each target does not establish successful observation of those targets.

The Judging & Awards Guide evaluates each criterion from 1 to 5; this draft assigns no official or internal
score. Complete the evidence below with actual observations before submission.

| Criterion | Evidence to include | Current gap |
|---|---|---|
| Impact | Defined audience, problem and user-test observations; distinguish expected from measured benefit | User testing remains pending |
| Creativity | Credited inspirations and a meaningful, working contribution | Describe the demonstrated improvement and its limits |
| Validity | Reproducible real workflow, scientific checks, usability and five target-test results | Real archive/image processing and validation are pending |
| Relevance | RA/Dec to actual SPHEREx sequences with provenance and dates | NASA observations are not yet integrated into the committed demo |
| Presentation | Clear challenge, solution and significance across the written page and demo | Final demo, public links and team review are pending |

Weights and an aggregate-score formula are not specified by the guide. The pipeline's 0–1 candidate
confidence is unrelated to judging scores. Award categories are not a claim of nomination or success.

### Tools and team

Python, NumPy, Astropy, Pydantic, Pillow and Requests; FastAPI/Uvicorn; React, TypeScript and Vite.
The optional 3D scene uses Three.js with a dynamically imported renderer.
Validation uses pytest, Ruff, JSON Schema and Vitest. Optional scientific packages are only needed when
the corresponding real-data stages are implemented. Complete versions and acknowledgments for actual use.

TODO: team name, all member names and roles; verify Team Owner, Members tab, 1–6 local members and no waitlist.

## Use of Super Intelligence (SI)

Yes. OpenAI Codex assisted with repository/source review, link checks, documentation, requirement and
technical-workflow revisions, build/CLI changes, regression tests, draft submission text and attribution
text. The verified scope is recorded in [AI_USAGE.md](../../AI_USAGE.md) and
[ai-usage.json](ai-usage.json). The original scaffold and generator history still require team review.
The imported 3D contribution declares Claude assistance in commit `cb19f8c`; that declaration is recorded
without claiming a complete authorship audit or verified scientific parameters.

The team must complete the origin-of-idea review and identify any other SI tools and generated assets.
No AI-generated video, audio or image-model output was created in the reviewed session. Numerical demo
images are labelled as simulations. This is not a claim that all existing assets have been audited.

The guide requires visible watermarks for SI-generated images/videos and descriptive text plus metadata
for SI-generated audio/code/data. Review NASA branding restrictions and source permissions. Public
attribution remains necessary even though the form's SI answer itself is not shown to judges.

## NASA Data

Resources consulted during development:

- [NASA/IPAC IRSA SPHEREx resources](https://irsa.ipac.caltech.edu/Missions/spherex.html).
- [IRSA SPHEREx tutorial notebooks](https://caltech-ipac.github.io/irsa-tutorials/spherex/).

Planned scientific input: SPHEREx Level 2 spectral images (NASA/JPL-Caltech/IPAC, via IRSA). **No real
SPHEREx observations have yet been integrated into the committed demonstration.** When implemented,
record actual releases, observation IDs, dates, source URIs and applicable acknowledgments.

The guide requires at least one NASA data/resource for Global Award eligibility. Citing a consulted
resource does not establish that the SPHEREx image-viewing requirement has been implemented.
The Relevance criterion further calls for NASA data to be integral to the proposed solution. Demonstrate
real observations driving the viewer rather than relying on a reference link or acknowledgment alone.

## Space Agency Partner Data and Other References

TODO: complete the inventory of all code, text, data, images and tools used, including free/open-source
material, permission/license and attribution. Separate resources consulted from datasets actually processed.

- WiseView was consulted as a reference for interaction; its imagery is not SPHEREx imagery.
- Gaia/MAST, CSA NEOSSat, CADC and the NEOSSat tutorial/dataset pages were checked as challenge resources;
  no processing of those datasets is claimed.
- Astropy is used for FITS/WCS. Aladin integration and JPL/SkyBoT analysis remain planned.
- Add exact resources, dependencies and contributor acknowledgments that the final project actually uses.
- Team-provided [Project Submission Guide](<../references/NASA Space Apps Challenge.pdf>) and
  [Judging & Awards Guide](<../references/NASA Space Apps Challenge Judging & Awards Guide.pdf>), both dated
  November 13, 2026, informed submission planning. The files are preserved unchanged in this repository.

Partner resources are encouraged by the guide; they do not replace the required NASA resource and
SPHEREx workflow. Review permissions and complete the inventory before submission.
