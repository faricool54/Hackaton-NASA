# Errante - SPHEREx sky explorer

NASA Space Apps Challenge 2026, "Planet X and SPHEREx". Working project name.

Errante is being built as a public tool where users enter right ascension and declination and play images
of the same sky region from different dates. The required validation targets are Barnard's Star, Epsilon
Indi B, WISE 0855, RW Aurigae and R Draconis. Automatic detection and Planet X education are later extensions.

## Current status

**This repository currently provides a synthetic demonstration, not a completed real-data SPHEREx tool.**

Available: labelled synthetic fields, temporal playback, detector filtering, candidate/spectrum examples,
a product-reading API, shared JSON schemas (version **0.2.0**) and an image-first build structure. The default build publishes
images and metadata without automatic analysis; `--analyze` opts into detection and catalog matching.

An optional 3D gallery is available at `#/systems` and `#/system/<id>[/<body>]`. It includes illustrative
models of the five challenge targets and one synthetic system. Parameters are hand-entered and unverified;
these views are models, not SPHEREx images, measured orbits, spectra or completed target-validation runs.
The 3D extension does not replace the required coordinate-to-image workflow.

Pending: real archive search, cutout downloads and reprojection; public coordinate-to-sequence requests;
public deployment; and documented tests of all five required targets. Optional enhancements are also planned.
No discovery, real-object recovery, real spectrum or sensitivity result is claimed from synthetic examples.

## Run the demonstration

```bash
git clone https://github.com/faricool54/Hackaton-NASA
cd Hackaton-NASA
python scripts/dev.py setup
python scripts/dev.py web
```

The frontend opens at `http://localhost:5173` and uses synthetic products without a backend.
Optionally run `python scripts/dev.py api` and use `?mode=api`; API documentation is at `http://localhost:8000/docs`.
The current static mode serves prebuilt fields and does not implement arbitrary-coordinate exploration.

`scripts/dev.py` works the same on Windows, macOS and Linux (on Windows you can type `py` instead of `python`;
`make <task>` still works where `make` exists). Run `python scripts/dev.py` to list all tasks.
Team rules for working in parallel without conflicts: [`docs/COLLABORATION.md`](docs/COLLABORATION.md).

## Pipeline and checks

```bash
errante demo                               # regenerate labelled numerical simulations
errante search --ra 269.4463 --dec 4.7665   # real archive search: currently a stub
errante build barnards-star                 # real image build: still blocked by data/reprojection stubs
errante build barnards-star --analyze       # opt into optional analysis after saving image products
errante systems                            # write illustrative 3D models; currently unverified parameters
errante validate --dir data/demo
python scripts/dev.py check
```

Python 3.11+ is required. Heavy astronomy libraries are in the optional `science` extra. Use `python scripts/dev.py
setup-science` for work on real-data processing. Downloads and FITS files belong in ignored caches.

## Project structure

| Location | Role |
|---|---|
| `pipeline/` | Archive/cutout access, FITS/WCS, aligned images and optional scientific analysis |
| `backend/` | FastAPI product service; coordinate-build jobs are planned |
| `frontend/` | React/TypeScript temporal viewer |
| `pipeline/errante/systems/`, `frontend/src/three/` | Optional 3D models and procedural rendering, with verification caveats |
| `shared/schema/` | Generated JSON contracts shared by pipeline, API and frontend |
| `data/demo/` | Committed numerical simulations, explicitly labelled as synthetic |
| `data/products/` | Curated real-data products when the real pipeline is implemented |
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

NASA/IPAC Infrared Science Archive [SPHEREx resources](https://irsa.ipac.caltech.edu/Missions/spherex.html)
and the [IRSA tutorial notebooks](https://caltech-ipac.github.io/irsa-tutorials/spherex/) informed development.
Real SPHEREx observations have not yet been integrated into the committed demonstration. Catalog services,
WISE/Gaia context and other partner datasets are planned; listing them as planned does not claim they
were processed. A complete inventory of sources, licenses, contributors and acknowledgments remains a
submission task.

OpenAI Codex assisted with source review, documentation, technical planning, code changes and tests.
The imported 3D contribution declares Claude assistance in its commit metadata; its parameters and full
provenance still require team review.
See [AI_USAGE.md](AI_USAGE.md) for the verified scope and pending team review.
