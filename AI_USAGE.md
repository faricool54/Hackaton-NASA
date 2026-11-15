# AI assistance and content provenance

This is a working disclosure of the assistance that can be verified from the current development session.
It must be reviewed and completed by the team before submission. The 2026 Project Submission Guide uses
the term "Super Intelligence (SI)" for these tools.

## Verified assistance on November 14, 2026

OpenAI Codex assisted with:

- Reviewing the existing repository, challenge statement and both team-provided submission and judging/awards guides.
- Checking access to linked reference pages and documenting the results.
- Revising documentation, requirement coverage, technical workflow and task priorities.
- Modifying `pipeline/errante/build.py` and `pipeline/errante/cli.py` to separate image publication from
  optional automatic analysis, and adding regression coverage in `pipeline/tests/test_build.py`.
- Preparing draft submission text and a demo outline. These drafts do not establish scientific results,
  deployment, a completed video or team approval.

Machine-readable metadata: [docs/submission/ai-usage.json](docs/submission/ai-usage.json).
The public application also discloses development assistance on its About page.

## Claude Code assistance (November 14, 2026)

Claude Code (Anthropic) assisted team member faricool54 (workstream WS1) with:

- **Collaboration infrastructure:** task runner, ownership guard, CI job and agent permissions (#2). Documentation
  of verified SPHEREx data facts (#3, #24).
- **WS1 code:** frame search, S3 Range patches with an IBE cutout fallback, per-pixel wavelength and mid-exposure
  time (#21–#23).
  - AI agents implemented each part, other AI agents reviewed it adversarially, and the result was
    integration-tested on real SPHEREx data.
  - Human review of this code is pending.
- **Validation of the five challenge targets:** records for all five targets in `docs/validation/` (Barnard's Star,
  Epsilon Indi B, WISE 0855, RW Aurigae, R Draconis).
  - AI agents measured the real SPHEREx FITS files, and separate AI agents re-measured the key numbers with
    their own code.
  - The figures are plots drawn by code the agents wrote from real SPHEREx data, not generated images.
  - Human review of these records is pending.

## Claude Code assistance in WS1 and WS3 (November 15, 2026)

Claude Code (Anthropic, Claude Opus 5.5) kept assisting team member faricool54, who took WS3 (science) on
November 15 in addition to WS1. Every pull request below was directed and merged by faricool54. The reviews named
in them were run by AI agents in Claude Code (review and adversarial-verification subagents), not by people.

- **WS1 (data access):** cube spectra (#42), committed search snapshots (#43), point series of S3 stamps (#45, #50,
  #61, #92), deploy facts and fixtures (#49), DATA.md facts (#44, #67, #105). Machine-readable record:
  [pipeline/errante/data/ai-usage.json](pipeline/errante/data/ai-usage.json).
- **WS3 (science):** object context for a click or a name (#58, #74, #101), position spectra and light curves
  (#59, #93, #106), scientific reviews of texts, the 3D and the light curves (#60, #65, #85), field texts (#87).
  Machine-readable record: [pipeline/errante/science/ai-usage.json](pipeline/errante/science/ai-usage.json).
  rpccp's conditional spectral temperatures (#102, OpenAI Codex) have their own record,
  [pipeline/errante/science/continuum-ai-usage.json](pipeline/errante/science/continuum-ai-usage.json).
- **Work in other workstreams' files, with notice:** the object-card contract (#73), API (#76) and card (#75); the
  black-map fix (#86); the light-curve panel (#97); republished light curves (#94); field descriptions (#88).
  Each component's owner should add these to their component record.
- **Coordination:** validation records and their addenda (#36, #46, #62, #66, #104), the live status guide (#77,
  #89).
- Light curves, spectra and validation figures are measurements made by code on real SPHEREx FITS files. No AI image,
  video or audio model output is used, and no NASA branding was generated.
- Human line-by-line review of this work and the human sign-off of the five validation records are still pending.

## Origin of the product vision (November 14, 2026)

Team member faricool54 stated the product vision recorded in [docs/VISION.md](docs/VISION.md):

- an interactive map of the real SPHEREx sky with search by name or coordinates;
- clicking a point opens the real SPHEREx time sequence, the spectrum, and a realistic 3D model built only from
  measurements.

Claude had earlier drafted a different product outline. The team rejected it and stated this vision instead.
Claude's role was limited to:

- checking feasibility against the data and services, including a live test of Aladin Lite with the IRSA SPHEREx
  HiPS;
- restating the vision as requirements;
- writing the document.

This records what happened in that session; team review of this record is pending.

## Imported 3D contribution

The integrated commit `cb19f8cd44bb6e91a875c534a5196d522187ac8d` declares Claude assistance in its
author/co-author metadata. It adds the 3D system catalog, procedural rendering, API/contracts, data and
tests. This is a recorded contributor declaration, not an independent audit of every asset or parameter.
The following preview-configuration commit is preserved as part of that branch.

Codex integrated that branch with the supplied guides and revised priorities, public copy and provenance.
Later catalog/source checks are recorded per `Fact.verified` and in the WS3 reviews; current models must
not all be described as unverified. Further corrections are in open PR #90. They are not SPHEREx images,
measured orbital phases or completed target tests. Rendering tests do not verify astronomical values.

## Data and media

`data/demo/` contains labelled numerical simulations generated by `errante.synthetic`. The public app
uses the separate real SPHEREx products in `data/products/` and real FITS-derived scientific products;
the five real fields are not simulations. Neither numerical fixtures nor processed FITS images establish
use of an AI image generator. The original scaffold/generator's complete authorship history remains unaudited.

Both supplied reference PDFs are copied unchanged. No AI-generated image-model output, video or audio were created during
this session. No NASA logo, flag or mission identity graphic was created or modified during this session.
This statement covers observed work, not every asset a contributor might add later.

## Team review before submission

- Record the origin of the project idea and the team's decisions. The guide limits SI use in formulating
  the solution idea; this disclosure must not be used as a claim that the entire idea has verified human origin.
- Add other tools, contributors, affected code/data/assets, dates and human review evidence.
- For SI-generated images/video, apply a visible generation watermark. For SI-generated audio, code and
  data, acknowledge generation in descriptive text and metadata as required by the guide.
- Review source permissions and NASA branding restrictions before publishing generated assets.
- Complete the SI form field as well as the public acknowledgments. The private form answer alone does
  not replace attribution in the project.

No unreviewed attribution, originality or eligibility claim is made by this draft.

## WS4 review and frontend integration (November 14, 2026)

At rpccp's request, OpenAI Codex reviewed and repaired job concurrency, publication/recovery, served/build
roots, browser CORS and child-process supervision; formalized the additive 0.3.0 job/resolver contract; and
connected the map, coordinate/name input, polling, sharing and real-image playback. Real browser testing
found and fixed Sesame's colon-formatted coordinates. Local tests included three 40-frame real builds,
desktop/mobile playback and shared-link restoration. These checks do not establish R05 scientific recovery.

Component metadata: [backend/ai-usage.json](backend/ai-usage.json),
[frontend/ai-usage.json](frontend/ai-usage.json). Human review remains pending. No AI-generated sky imagery
or new physical measurements were used; Aladin, IRSA and ESA imagery retain their source credits.

## Cache and scientific panels (November 15, 2026)

At rpccp's request, Codex implemented processing-fingerprint cache invalidation, the additive 0.4.0
spectrum/comparison contract, supervised scientific API adapters, atomic analysis publication, and React
controls/plots/quality tables. Code and regression tests were AI-assisted; team review remains pending.
The implementation calls existing WS1/WS2 extraction and photometry/comparison methods rather than
generating sky data. Live integration checked Barnard cube/season comparisons and RW Aurigae exposure
photometry; saturated/invalid measurements were retained and excluded from usable plots. These are
technical acceptance checks, not R05 validation. No AI image-model output, video or audio was generated.


## Conditional spectral interpretation (November 15, 2026)

Codex assisted with the user-requested WS3 V18 colour-temperature/IR-colour diagnostics and the remaining
LC24 scatter summary, building on Farid's earlier science work. The independent WS3 review by
faricool54 with Claude Code requested conservative uncertainty floors and additional quality/coverage
rejection; those follow-ups were implemented before API integration. The component record is
[pipeline/errante/science/continuum-ai-usage.json](pipeline/errante/science/continuum-ai-usage.json).
The native FITS fixture is observed photometry, not generated sky imagery. Algorithm tests, review by
agents and browser checks do not constitute human R05 approval or a calibrated stellar Teff measurement.
Farid's RW Aur identity correction (#101) and LC24 follow-up (#106) retain their own authorship.

## WS2 imaging and comparison (November 14–15, 2026)

Claude Code (Anthropic, Claude Opus 5.5) assisted V0id47 in WS2: reprojection onto the field grid,
season/detector frame selection, bad-frame rejection, registration checks, rendering and display-only
repairs, season coadds and flux-matched differences, forced photometry, false-color composites and tests.
The contribution also includes the composites contract (#39), image-mode toggle (#40), published-product
checks and demonstration animations. The current contributor record lists #13, #16, #17, #19, #25, #31,
#35, #37, #39, #40, #41, #48, #68–#72 and #88; later changes require their own inventory updates.

The five golden fields were built from real SPHEREx DR1/QR3 exposures. PNG frames and composites render
measured pixel values; they are not AI-generated sky imagery. Saturated cores and detector-defect pixels
may be repaired from neighbours for display only; pixels invalid in every composite input are neutral.
The products disclose these operations in their provenance. Display repairs are not scientific measurements.

V0id47 directed the work and merged the listed PRs; several reviews were performed by AI agents.
Line-by-line human review and formal human R05 approval are not claimed. #88 was authored and merged by
faricool54 with Claude Code to synchronize descriptions and is also disclosed in WS3's record.
The formal validation records remain in `docs/validation/` with their own review status.

Machine-readable source: [pipeline/errante/imaging/ai-usage.json](pipeline/errante/imaging/ai-usage.json).

## Public-delivery follow-up (November 15, 2026)

At rpccp's request, Codex implemented the curated API manifest selection, verified and added the IRSA
acknowledgment/data DOIs, integrated the contributor-authored WS2 disclosure, and prepared the English
Barnard D2 season-difference demo take proposed by WS2. Job products and direct/share URLs are retained.
The update does not generate a final narrated video, submit the form or establish human R05 approval.
Metadata and checked sources: [final-delivery-ai-usage.json](docs/submission/final-delivery-ai-usage.json).
