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
- The five validation records got a guided human review by DankoLiv on 2026-11-15 (#126; analyses not re-run).
  Human line-by-line review of the code above is not claimed.

## Claude Code assistance to faricool54: frontend plan, basic flows and coordination (November 15, 2026, evening)

Claude Code (Anthropic, Claude Opus 5.5) assisted team member faricool54, who also coordinated the team. Every pull
request below was directed by faricool54. Most were implemented by Claude Code agents in their own git worktrees,
reviewed by an independent agent, fixed, checked in a browser by the main Claude Code session and merged by
faricool54's session. Reviews of other members' pull requests were run by AI agents with adversarial verification,
not by people.

- **Frontend plan:** the parallel plan itself (#123); map layout, floating layers and corner credits (FE-4a.0, #129);
  completion of FE-2 after its author could not continue (#127); the star card next to the mouse and Gaia DR3 stars
  per view (FE-4a/4b, #139), zoom to a picked target (#141), the empty-dock steps (#142), the compact blink player
  (FE-7, #143), spectrum chart first and the inline light-curve variant (FE-8, #146), keyboard shortcuts (FE-11,
  #148), the phone bottom sheet (FE-10, #151), Gaia at wider zoom with the WISE 0855 fix and the exact lookup of a
  clicked Gaia star (#155), color for map-click builds (#159) and the foldable map legend (#161). Records:
  `frontend/ai-usage/fe-2.json`, `fe-4.json`, `fe-7.json`, `fe-8.json`, `fe-10.json`, `fe-11.json`.
- **WS1:** the IRSA frame search now survives a flaky archive (#154), after live measurements on 2026-11-15
  (SIA ~23 s, intermittent HTTP 502). Record: [pipeline/errante/data/ai-usage.json](pipeline/errante/data/ai-usage.json).
- **Demo tooling (WS6, with notice):** the demo-video takes follow the tabbed field page (#152).
- **Reviews (AI agents, with adversarial verification):** WS2 #136, #137, #140; WS5 #144, #145; WS7 #138, #147,
  #156, #157, #158, #160; contract #119 (merged as coordination with WS2's OK).
- **Deployments:** public deploys of 850968e, d06896f, e89ab45 and 08dfb85 with `scripts/deploy_vm.py`, plus a
  republication of the five curated fields and five systems into the VM's runtime volume (WS4's `publish_field`),
  each followed by a smoke test and a comparison of the public API with `main`.
- No AI image, video or audio model output is used and no NASA branding was generated. Gaia, SIMBAD and catalog
  values are labelled as catalog values, not SPHEREx measurements. Human line-by-line review of this code is not
  claimed.

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

## Claude Code assistance in WS7 (3D) and frontend packages FE-5/FE-6 (November 14–15, 2026)

Claude Code (Anthropic) assisted team member DankoLiv in WS7, the optional 3D gallery (P2), and in two packages
of the frontend plan. Every pull request below was directed by DankoLiv. Reviews named in them were run by AI
agents in Claude Code; faricool54's WS3 reviews of #90, #99, #107, #138, #156, #157 and #160 were also run with
Claude Code.

- **WS7 3D systems:**
  - catalog verification and contract fixes (#7, #8, #9);
  - procedural 3D and dataset time (#47) and the five published systems (#64);
  - only measured or catalog values drawn (#90), and the follow-ups of the WS3 reviews (#156, #157, #158);
  - the blink reticle for all five targets (#99, on top of #96);
  - 3D for any object picked on the map (#107, #160);
  - 3D style and compact mode (#138, #147, #149).

  Machine-readable records: [pipeline/errante/systems/ai-usage.json](pipeline/errante/systems/ai-usage.json)
  and [frontend/src/three/ai-usage.json](frontend/src/three/ai-usage.json).
- **Frontend plan:** FE-5 object card and session cache (#144) and FE-6 field dashboard (#145), with records
  [frontend/ai-usage/fe-5.json](frontend/ai-usage/fe-5.json) and [fe-6.json](frontend/ai-usage/fe-6.json). The
  other packages (FE-1 to FE-4, FE-7 to FE-11) keep their own records in `frontend/ai-usage/`.
- **Coordination:** DankoLiv's guided human review of the five validation records (#126); the analyses were not
  re-run.
- The 3D views are catalog-based models labelled "3D MODEL · NOT AN IMAGE": they are not SPHEREx images and not
  R05 validations. No AI image, video or audio model output is used, and no NASA branding was generated. Human
  review of the 3D code is not claimed complete.

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
Follow-ups confirmed by WS2's review of #130 include the record refresh (#112) and the season-coadd
S/N check (#115). The frame-quality contract #119 was prepared by mateoa007 with
OpenAI Codex; it is separate from the Claude-authored WS2 contribution. WS2 maintains its own JSON record.

The five golden fields were built from real SPHEREx DR1/QR3 exposures. PNG frames and composites render
measured pixel values; they are not AI-generated sky imagery. Saturated cores and detector-defect pixels
may be repaired from neighbours for display only; pixels invalid in every composite input are neutral.
The products disclose these operations in their provenance. Display repairs are not scientific measurements.

V0id47 directed the work and merged the listed PRs; several reviews were performed by AI agents.
Line-by-line human review of WS2 code is not claimed. The separate R05 records now have DankoLiv's guided
human-review sign-off dated November 15, 2026 (#126); the analyses were not rerun. This later sign-off is
not a claim that WS2's display-product checks independently establish R05 validation. #88 was authored and merged by
faricool54 with Claude Code to synchronize descriptions and is also disclosed in WS3's record.
The formal validation records remain in `docs/validation/` with their own review status.

Machine-readable source: [pipeline/errante/imaging/ai-usage.json](pipeline/errante/imaging/ai-usage.json).

## Public-delivery follow-up (November 15, 2026)

At rpccp's request, Codex implemented the curated API manifest selection, verified and added the IRSA
acknowledgment/data DOIs, integrated the contributor-authored WS2 disclosure, and prepared the English
Barnard D2 season-difference demo take proposed by WS2. Job products and direct/share URLs are retained.
The update does not generate a final narrated video, submit the form or establish human R05 approval.
Metadata and checked sources: [final-delivery-ai-usage.json](docs/submission/final-delivery-ai-usage.json).

## Demo video (November 15, 2026)

**Who and how.** Claude Code (Anthropic, Claude Opus 5.5) produced the demo video at V0id47's request,
with the team's feedback in #100. It used the `docs/submission/skills/video-tutorial/` tool.

**AI-generated:**
- the narration script;
- the automated Playwright takes of the public app (`08dfb85` for the final cut);
- the ffmpeg montage;
- the on-screen text: animated opening title, section headlines, English captions and the edit-cut label;
- the narration audio, made with Microsoft Edge TTS. The final cut uses `en-US-AvaMultilingualNeural` and
  the drafts used `en-US-JennyNeural`. It is disclosed on the closing card, in the MP4 metadata and in the
  video description. Public-output terms for the TTS service are not marked cleared.

**Not AI-generated:**
- All imagery is screen recordings of the real application.
- The SPHEREx frames and the false-color season composites are the app's real products, labeled as false
  color.
- The 3D view keeps its «3D MODEL · NOT AN IMAGE» label.

No AI-generated images or video are used.

**The build shown is real** (job `ca52180e`). Its wait is cut, and the cut is labeled on screen with the
time measured from the job API.

**Writes to the public VM.** Recording and testing published job fields there. They are listed in the
machine-readable record.

**Where things are.** Drafts, scripts and contact sheets are in the `ws6/demo-video-drafts` branch. The team
does the final selection, upload, form and Submit for Judging; none of these is implied here.

Machine-readable record: [docs/submission/demo-video-ai-usage.json](docs/submission/demo-video-ai-usage.json).
