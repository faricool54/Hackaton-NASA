---
name: video-tutorial
description: >-
  Produce narrated tutorials, courses and short product demos, including a strict
  30-second NASA Space Apps / Errante delivery profile, and iterate on
  them line by line - a script with a montage sheet (one narration phrase + one
  visual per row), an HTML slide deck, an AI voice-over (edge-tts) with a
  pronunciation dictionary, automated screen takes recorded with Playwright
  (with boxes, arrows, spotlight, labels, steps, zoom and blur on request), and
  an ffmpeg montage. Use it when the user wants to create or edit a video
  course, a tutorial or demo video, a screencast with voice-over, or asks to set
  up a new course; read course.yaml when handling a video project, and use it for requests like "line 8: give me pronunciation options",
  "split slide 4 in two", "record every take", "rebuild the montage".
---

# video-tutorial

Turns a script into a finished video: **script → deck → slides → narration → takes → montage → publish**.
Everything after the script is generated, so iterating is cheap: the user edits one line, one slide or one take,
and only what changed is regenerated.

The scripts live next to this file, in `scripts/`. Run them with the Python that has the dependencies
(`py` on Windows, `python3` elsewhere): `python "<this skill>/scripts/<script>.py" ...`.

## First, find the course

For an Errante / NASA Space Apps final demo, read `reference/errante-demo.md` first.
Use the English 30-second profile rather than the course wizard. The user's choice
is **English narration without subtitles**. Reviewing or adapting this skill does
not imply generating, uploading or publishing a video.
The first **approximately 10 seconds** must explain Errante's distinguishing value
and why it is compelling; the later real-application shots must demonstrate it.

Look for `course.yaml` in the working folder or its parents.

- **None** → the user is starting a course: run the **setup wizard**, `reference/setup-wizard.md`. Do not
  improvise a structure.
- **Found** → read it and applicable `AGENTS.md` / `CLAUDE.md` conventions. The course root is
  the folder holding `course.yaml`; videos live in its production folder (`internal/` by default).

## Where to read next

| The user wants to… | Read |
|---|---|
| make the English 30-second Errante / NASA Space Apps demo | `reference/errante-demo.md` |
| set up a course, or learn how to use this skill | `reference/setup-wizard.md` |
| start a video, or write / restructure a script | `reference/guion-format.md` |
| change wording, rows, slides, takes, speed — any iteration | `reference/iteration.md` |
| fix a pronunciation, change the voice or its speed | `reference/voice.md` |
| record or fix a take: cursor, timing, annotations, blur | `reference/recording.md` |
| change the deck, its design system, builds | `reference/deck.md` |
| publish | `reference/publishing.md` |

## Commands

```
scaffold.py init  <course> --answers answers.yaml     # the wizard's last step
scaffold.py demo  <production-folder> [--base-url URL] # one Errante demo; English, no subtitles, strict 30 s
scaffold.py cards <video>                             # refresh Errante identity/credit cards from course.yaml
scaffold.py video <course> "NN - Title"                # a new video from the templates
scaffold.py deck  <course>                             # re-apply the design system to _template/
voces.py    <course> [--voz X --velocidades +0% +5%]   # voice samples (edge-tts and Kokoro), before any video exists
kokoro_setup.py [--check]                              # the local Kokoro engine, in its own venv (only if a Kokoro voice is used)
slides.py   <video>                                    # deck → assets/slides/slide-NN.png
locutor.py  <video> [--sync] [--muestras]              # narration + timings (prints the rows that changed)
variantes.py <video> --fila N --buscar "x" --opciones "y" "z"   # numbered audio options for one row
pausas.py   <video> [--filas 5,7]                      # where each phrase starts, to pace takes
grabar.py   <course> --login                           # the user signs in; Claude never types credentials
grabar.py   <video> [--tomas D1,D3] [--capturas] [--headed]
montar.py   <video> [--placeholder] [--out file.mp4]   # the final video
verificar.py <video> [--final | --draft] [--placeholder] # final profile is strict by default; draft is never submission-ready
```

## Golden rules

1. **The audio is the timing source of truth.** Never estimate durations: run `locutor.py`, read what it measured.
2. **One row = one narration phrase + one visual.** The cut lands in the pause before the phrase, never on a word.
3. **The voice never reads the slide.** The slide carries the summary; the narration carries the reasoning.
4. **No still over 12–13 s.** Flag it and split the row or cut to a take. Never fix it with an effect.
5. **Nothing the user did not ask for:** no zoom, transitions, speed changes, boxes or arrows by default.
6. **Options by ear.** For any wording or pronunciation request, render numbered samples (`variantes.py`) and
   let the user pick. **Deliver playable audio files**, including v1 and numbered captions,
   through the host's native attachment/audio rendering (Codex: absolute-path media embeds).
   A table of respellings is not an audio sample. Keep wording the user has adjusted.
7. **Pronunciation fixes go to `course.yaml`**, never into the script, the slides or UI labels.
8. **Verify against the product, not its docs.** Each script ends with a *differences with the docs* table.
9. **Regenerate only what changed.** After an audio change, read the *changed rows* line, re-measure those
   rows (`pausas.py`), re-pace and re-record only the affected takes, rebuild the montage.
10. **Test before claiming.** Every change ends with `verificar.py <video>` passing, and a look at frames
    (contact sheets) of every take and montage you produce. Never tell the user a video is ready with an
    error open; report its warnings. For final deliveries, require the MP4, exact duration,
    current narration/build inputs, source/AI credits and metadata. `--draft` / placeholders
    can never establish submission readiness. If scripts change, run `pytest scripts/tests` too.
11. **Production writes are off camera and idempotent**, and every write is reported. Uploading, sending or
    publishing requires authorization for that action; do not request it again when already granted.

## Dependencies

Python 3.11+ is required. The supplied `requirements.txt` pins the default pipeline dependencies.

`edge-tts imageio-ffmpeg playwright pillow pyyaml` (pytest to run `scripts/tests`). **You install them**, in the
setup wizard (Block 3) or whenever an import fails. Use a virtual environment outside the
skill's distributable folder. The recorder uses system Chrome (`channel="chrome"`),
as in the original skill; no browser download. ffmpeg comes from imageio-ffmpeg. A Kokoro voice (`ef_dora`…)
additionally needs `kokoro_setup.py` (its own venv, ~1 GB) and `espeak-ng`; see `reference/voice.md`.
