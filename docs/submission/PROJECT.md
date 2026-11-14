# Project submission draft (English)

> **Owner:** WS6. The coordinator copies this into the official form on spaceappschallenge.org (team page →
> *Project* tab).
> One heading per **official form field**, from the
> [Project Submission Guide](https://www.spaceappschallenge.org/resources/project-submission-guide/) (checked
> 2026-11-14). **Everything in the form and in linked materials must be in English.**
> **Rules for this draft:**
> - The idea, name, tagline and narrative are written **by the team, in its own words** (SI rule: SI must not be
>   used to come up with the idea). Text marked `TODO(team)` must not be filled in by an AI assistant.
> - Only state what actually ships and only **measured** numbers. Never claim a discovery. Synthetic data is never
>   presented as real.
> - The technical facts below are a **draft taken from [`../PLAN.md`](../PLAN.md)** (the plan as of 2026-11-14).
>   Update them to what is actually deployed on Sunday.

---

## Project Name

*What goes here: the project's name.*

TODO(team). "Errante" is only a provisional working title that came out of an AI-assisted scaffold. The team
confirms or replaces it at the kickoff.

## High-Level Project Summary

*What goes here: what we developed, how it addresses the challenge, and why it matters. Short paragraph.*

TODO(team). It must make clear that the tool shows **real NASA SPHEREx images** for coordinates the user
enters, as a time series ("like a little video"), and that it was tested on the five official targets.

## Link to Project Demo

*What goes here: a public link (no password, permission or registration) to a **video of 30 s or less** or a
**slide deck of up to 7 slides** (title and intro included). Exceeding either limit makes the project ineligible
for Global Judging. A video in another language needs English subtitles. Script and rules:
[`PITCH.md`](PITCH.md).*

TODO: URL (tested in an incognito window).

## Link to Final Project

*What goes here: a public link to the final project: the deployed website and/or the code repository. No login.*

- Live site: TODO (WS4 deploy, target Sun 12:00 local time).
- Repository: https://github.com/faricool54/Hackaton-NASA. **Currently private** (returned 404 to anonymous
  visitors on 2026-11-14). Make it public before submitting, or link only the live site. If the repo is linked,
  its README must be in English.

## Detailed Project Description

*What goes here (questions from the guide): what exactly does it do? How does it work? What benefits does it
have? What do you hope to achieve? What tools, coding languages, hardware or software did you use?*

**What it does / benefits / goals:** TODO(team), in the team's own words.

**How it works (technical draft, from the plan; update to what ships):**

- The user enters a sky position (RA/Dec in decimal or sexagesimal, or an object name) and a field of view, or
  picks one of the five official test targets. The state lives in the URL (`?ra=…&dec=…&fov=…`), so a view can
  be shared or embedded.
- A Python backend (FastAPI) finds every SPHEREx exposure that covers that position. It searches IRSA with the
  SIA2 service (VOTable) over configurable collections (`spherex_dr1`, `spherex_qr3`; the `*_deep` ones are
  optional) and falls back to TAP. A backend is required because IRSA's search and cutout services do not send
  CORS headers.
- It reads only the pixel rows it needs (IMAGE, VARIANCE, ZODI) from the public AWS S3 bucket
  `nasa-irsa-spherex` with HTTP Range requests: about 0.4 MB and about 1 s per frame for a 5′ patch, versus
  about 4 MB for an IRSA cutout. IRSA cutouts remain the fallback.
- Frames are reprojected to a common north-up grid and the zodiacal background (ZODI) is subtracted. Within one
  survey season, each exposure samples a different wavelength (linear variable filter). So the "video" is built
  from inverse-variance-weighted **coadds per season × detector**, and the user can switch to the **difference
  between two seasons**.
- Motions are small. Over the available DR1+QR3 baseline, the catalog proper motions predict 1.86 px for
  Barnard's Star, 1.36 px for WISE 0855 and 1.10 px for Epsilon Indi B (6.15″ pixels; expected values, not yet
  measured). The viewer therefore offers pixel zoom, a reticle and the position predicted from each target's
  proper motion.
- Variable stars (RW Aurigae, R Draconis) do not move; their brightness changes. They are compared through
  season coadds (and spectra per season, if shipped).
- The five targets are also precomputed as static "golden fields", so the site still works if IRSA is slow.
- New data releases are handled through configuration. Collections are not hard-coded, and file paths always
  come from the search results.
- Optional, only if shipped: on-the-fly spectra or photometry, a Gaia DR3 overlay in Aladin Lite, contamination
  flag layers, false-color composites.

**Results (only measured numbers):** TODO, e.g. observed vs. expected displacement for the moving targets. Fill
in only after measuring.

**Limitations (honest):** TODO(team) to word them; facts to cover:
- Epsilon Indi B is a pair of brown dwarfs, but SPHEREx pixels (6.15″) do not resolve it: it appears as one
  source.
- The coordinate given in the challenge for WISE 0855 corresponds to ~2010; the object is now ~126″ west of it.
- Movements are 1–2 pixels over the current data, so they are visible only with zoom, difference images or
  predicted positions.
- No discovery claims.

**Tools and languages:** Python (astropy, numpy, FastAPI), TypeScript (React, Vite). TODO: final list, checked
against `pipeline/pyproject.toml`, `backend/pyproject.toml` and `frontend/package.json`. Add Aladin Lite if it
ships.

## Use of Super Intelligence (SI)

*What goes here: whether SI tools were used and how. Judges do not see this answer, but they do see the SI
indicators inside the project (watermarks, descriptive text, metadata). Code and data generated with SI must be
acknowledged in descriptive text and metadata; SI-generated images and videos need a visible watermark.*

TODO(team): confirm and complete. Draft facts:
- AI coding assistants were used. TODO: exact list (for example Claude Code by Anthropic; add Codex or others if
  used). They were used to scaffold the repository (the initial commit on 2026-11-14 is authored by "Claude"),
  to review it against the official challenge text, and to write code, tests and documentation under team
  review.
- Commits made with agents carry a `Co-Authored-By:` trailer naming the tool. The README has a "Use of SI"
  section.
- The idea, the name, the tagline and the key decisions are the team's. TODO(team): describe how the team
  decided them.
- SI-generated images or video, if any: TODO (list them; each one carries a visible watermark).

## NASA Data

*What goes here: specifically which NASA data and resources were used. At least one is required to be eligible
for a Global Award.*

Draft (keep only what is actually used):
- **SPHEREx Level 2 spectral images** (NASA/JPL-Caltech/IPAC), releases **DR1** and **QR3** (IRSA collections
  `spherex_dr1`, `spherex_qr3`; TODO: whether `*_deep` was used), from the **NASA/IPAC Infrared Science Archive
  (IRSA)**:
  - SIA2 and TAP search services;
  - public AWS S3 bucket `nasa-irsa-spherex` (HTTP Range reads);
  - IRSA cutout service (fallback).
- **IRSA SPHEREx tutorial notebooks** (https://caltech-ipac.github.io/irsa-tutorials/spherex/): TODO, only if we
  used them as reference.
- **IRSA HiPS** (SPHEREx DR1 all-sky cube, 2MASS/AllWISE mirrors): TODO, only if the overlay ships.
- **WiseView** (http://byw.tools/wiseview), listed as a NASA resource in the challenge: TODO, only if we say we
  used it as a UX model.
- JPL services: none planned. Add them only if they are used.

## Space Agency Partner Data and Other References

*What goes here: **all** data, resources and tools used, including code, text and images, even open-source or
free ones. Copyrighted material needs permission.*

**Space Agency Partner Data**
- ESA **Gaia DR3** (ESA/Gaia/DPAC): TODO, only if the overlay or the target proper motions use it. Accessed via
  the VizieR mirror at CfA and/or the ESA Gaia archive. The challenge lists Gaia DR3 at MAST
  (https://archive.stsci.edu/missions-and-data/gaia) as a resource.
- CSA NEOSSat / CADC (listed by the challenge): **not used** unless the team decides otherwise. Do not claim
  them.

**Other References** (TODO: keep only what was used)
- Astropy, NumPy, FastAPI, React, Vite, TypeScript (and other dependencies in the lockfiles).
- Aladin Lite 3.8.2 (CDS, Strasbourg), loaded from jsdelivr: if used.
- Sesame name resolver (CDS), queried through the CfA mirror: if used.
- Target positions and proper motions stored in the repo: TODO, cite the source catalog for each.
- IMCCE SkyBoT (known asteroids): if used.
- WiseView and Backyard Worlds, as inspiration: if cited.
- Any code adapted from tutorials or other projects: TODO, list it with a link.
- SI tools: see "Use of Super Intelligence (SI)".

---

### Internal notes (not form fields)

- The challenge ("Planet X and SPHEREx") is not one of the form fields listed in the guide. Check that the team
  page shows it.
- Before clicking "Submit for Judging", tick **Terms and Conditions** and **Confirm All Work is Original**.
  Full checklist: [`CHECKLIST.md`](CHECKLIST.md).
