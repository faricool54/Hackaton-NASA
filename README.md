# Errante - SPHEREx sky explorer

NASA Space Apps Challenge 2026, "Planet X and SPHEREx". Working project name.

Errante lets users search by name or sky coordinates, click an infrared map and play real NASA SPHEREx
images of the same region from different dates.

**[Open the public application](https://errante.34-148-242-13.sslip.io)** ·
[About, science and credits](https://errante.34-148-242-13.sslip.io/#/about).

## Current status

Updated **November 15, 2026**, against `main` **3ed5c91** (#97), also verified on the public deployment.

The home displays the SPHEREx DR1 sky through Aladin Lite/IRSA. Its wavelength selector and optional AllWISE
context layer do not represent time. In live API mode, a map click or form submission builds real exposures
through bounded background jobs; the viewer shows dates, wavelength, release and provenance. Five prebuilt
real challenge fields contain 40 frames each. Local static mode can open them with
`?mode=static&dataset=real`; separate synthetic development fixtures remain labelled. The public app
defaults to real data and the live API. Shared contract: **0.7.0**.

The image build runs without automatic analysis; `--analyze` opts into detection/catalog matching. Empty
candidate lists without analysis are not evidence that nothing was detected. All
five targets (R05) have offline FITS records and separate agent re-measurements. **Human review remains
pending**; image playback and deployment tests do not certify those scientific results.

Implemented features include position spectra, catalog object cards, season comparisons (196 precomputed
PNG products), two real precomputed light curves, and image zoom. Barnard's reticle predicts catalog
position; it is not a position measurement from the displayed image. The catalog-based 3D gallery cites
sources and representation limits; SPHEREx-derived temperature/radius and physical reconstruction are
not implemented. WS7's further model corrections are in open PR #90, not in this release.

Remaining work includes the compact view, additional curve views, quality/map enhancements, human validation and final
submission materials. #97 adds visible curve warnings/floors/data selection and loading of exported
static curves when their JSON has been exported. Its limits and data-selection blocks were checked
on the public app. Static comparison UI remains separate work. Automatic detection, detection limits and
Planet X remain extensions. See [the current plan](docs/PARALLEL_PLAN.md) for dependencies and owners.

## Run the demonstration

```bash
git clone https://github.com/faricool54/Hackaton-NASA
cd Hackaton-NASA
python scripts/dev.py setup
python scripts/dev.py web
```

Local Vite defaults to static synthetic fixtures. Open `http://localhost:5173/?mode=static&dataset=real#/`
for the five curated real fields. For coordinate builds, first run `python scripts/dev.py setup-science`,
set `ERRANTE_ENABLE_JOBS=1` (`export ERRANTE_ENABLE_JOBS=1` in Bash or `$env:ERRANTE_ENABLE_JOBS='1'`
in PowerShell), and run `python scripts/dev.py api` in another terminal. Open
`http://localhost:5173/?mode=api&dataset=real#/`; API docs are at `http://localhost:8000/docs`.
The runner seeds a private runtime copy under `data/cache/local/` and preserves existing jobs/products.
On Windows, use `py` instead of `python` if needed. No cloud account is needed for local use.
See [backend/README.md](backend/README.md) and [frontend/README.md](frontend/README.md) for roots, limits,
CORS, shareable links and local configuration. Public hosting is Google Compute Engine with web/API on
one HTTPS origin and persistent storage. [Team redeploy instructions](backend/deploy/README.md) use each
operator's own Google account. Merging a PR does not deploy it automatically; the custom domain is optional.

`scripts/dev.py` works the same on Windows, macOS and Linux (on Windows you can type `py` instead of `python`;
`make <task>` still works where `make` exists). Run `python scripts/dev.py` to list all tasks.
Team rules for working in parallel without conflicts: [`docs/COLLABORATION.md`](docs/COLLABORATION.md).

## Pipeline and checks

```bash
errante demo                               # regenerate labelled numerical simulations
errante search --ra 269.4463 --dec 4.7665   # real archive search
errante build barnards-star                 # real image build without optional analysis
errante build barnards-star --analyze       # opt into optional analysis after saving image products
errante systems                            # catalog-based 3D context; sources/representation limits apply
errante validate --dir data/demo
python scripts/dev.py check
```

Python 3.11+ is required. Heavy astronomy libraries are in the optional `science` extra. Use `python scripts/dev.py
setup-science` for work on real-data processing. Downloads and FITS files belong in ignored caches.

## Project structure

| Location | Role |
|---|---|
| `pipeline/` | Archive/cutout access, FITS/WCS, aligned images and optional scientific analysis |
| `backend/` | FastAPI product service and persistent coordinate-build jobs |
| `frontend/` | React/TypeScript temporal viewer |
| `pipeline/errante/systems/`, `frontend/src/three/` | Catalog-based 3D models, sources and representation limits |
| `shared/schema/` | Generated JSON contracts shared by pipeline, API and frontend |
| `data/demo/` | Committed numerical simulations, explicitly labelled as synthetic |
| `data/products/` | Five curated real SPHEREx challenge fields (40 frames each) |
| `data/cache/` | Ignored downloads and cached queries |
| `docs/`, `tasks/` | Team planning, validation, sources and workstream assignments |

The public README and submission materials are in English. Internal contributor planning remains in
Spanish under `docs/` and `tasks/`; it is not a replacement for English judging materials.

## Submission preparation

The team supplied the [Project Submission Guide](<docs/references/NASA Space Apps Challenge.pdf>), dated
November 13, 2026. Its demo limit is **a video of at most 30 seconds or a deck of at most 7 slides**,
including title and introduction. The project page and linked judging materials must be in English;
a video narrated in another language must have English subtitles.

The team confirmed **Universidad de Palermo, Buenos Aires, Argentina** as its Local Event. The guide-based
deadline is **November 15, 2026 at 23:59 ART (UTC-3)**, equivalent to **November 16 at 02:59 UTC**.
The internal submission target is November 15 at 21:00 ART. Local judging times still need confirmation
with the Local Lead. This is preparation guidance, not a submitted project.
The source repository is currently private. Before judging, provide anonymous access to the final demo,
application and any linked materials; the current repository URL alone does not provide public access.

The supplied [Judging & Awards Guide](<docs/references/NASA Space Apps Challenge Judging & Awards Guide.pdf>)
scores **Impact, Creativity, Validity, Relevance and Presentation from 1 to 5 each** at every judging level.
It publishes no numeric weights or aggregate formula. Relevance calls for meaningful NASA data integration;
reading references alone does not establish a working SPHEREx sequence. Presentation covers both the demo
and the full project. No official score or award status is claimed here.

Local Event teams must have **1–6 registered, accepted members**, including the Team Owner at the same event,
all listed under Members; Universal teams require 2–6. New members cannot be added after submission closes.
The team's member registration remains to be checked. Local awards do not establish Global Nominee status;
only official nominations advance. The guide describes ten Global Awards, decided through executive judging.

English drafts and provenance:

- [Project submission draft](docs/submission/PROJECT.md) - incomplete fields are explicitly marked.
- [AI assistance and content provenance](AI_USAGE.md).
- [Machine-readable assistance metadata](docs/submission/ai-usage.json).
- [Reference document provenance](docs/references/README.md).

## Sources and acknowledgments

Real SPHEREx DR1/QR3 observations, the DR1 spectral cube and HiPS come from
[NASA/IPAC IRSA](https://irsa.ipac.caltech.edu/Missions/spherex.html).
[IRSA tutorial notebooks](https://caltech-ipac.github.io/irsa-tutorials/spherex/) informed development.
Aladin Lite 3.8.2 (CDS, GPL-3) displays the sky; AllWISE provides separate-mission context through ESA's
mirror. Gaia DR3, Sesame/SIMBAD/VizieR, 2MASS/CatWISE2020, the NASA Exoplanet Archive and AAVSO provide
catalog or validation context; they are not SPHEREx detections of planets or resolved 3D surfaces.
Full SPHEREx/Gaia/Exoplanet Archive acknowledgments are visible on the
[public About page](https://errante.34-148-242-13.sslip.io/#/about). A complete license/contributor/media
inventory and team review remain submission tasks.

OpenAI Codex and Anthropic Claude Code assisted contributors with documentation, implementation,
integration, tests, deployment and scientific analysis/review. Agent re-measurements are not human review.
See [AI_USAGE.md](AI_USAGE.md) for the verified scope and pending team review.
