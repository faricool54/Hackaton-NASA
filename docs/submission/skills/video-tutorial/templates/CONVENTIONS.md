# CLAUDE.md — ${name}

A narrated video project produced with the **video-tutorial** skill. Short videos (${target_duration}), narrated in
**${language}**, for **${audience}** (depth: ${depth}). ${platform_line}

The course settings live in `course.yaml`. The pipeline and the rules below come from the skill; this file
is where the course adds its own, as they come up.

## Layout

| Folder | What it is |
|---|---|
| `${production}/` | Production. One folder per video: `NN - Title/` with `guion-vN.md`, `presentacion.html`, `tomas.py`, `assets/`, `grabaciones/` (raw takes `D1.mp4`…), `locucion/` (narration and timings) |
| `${publish}/` | What gets published: one folder per video with the final `.mp4` and `descripcion.md` |
| `_template/` | The deck template with this course's design system. New videos start from it |

Folder names in `${production}/` and `${publish}/` match one to one. The final video goes to `${publish}/`, never
to `${production}/`.

## Pipeline

`script → deck → slides → narration → takes → montage → publish`. Scripts are in the skill:

```
python "${scripts}/scaffold.py" video . "NN - Title"          # a new video from the templates
python "${scripts}/slides.py"   "${production}/NN - Title"     # deck → assets/slides/slide-NN.png
python "${scripts}/locutor.py"  "${production}/NN - Title" --sync   # narration + timings, written into the script
python "${scripts}/variantes.py" "${production}/NN - Title" --fila 8 --buscar "x" --opciones "y" "z"
python "${scripts}/pausas.py"   "${production}/NN - Title" --filas 5,7   # where each phrase starts
python "${scripts}/grabar.py"   "${production}/NN - Title" [--tomas D1,D3] [--capturas]
python "${scripts}/montar.py"   "${production}/NN - Title" [--placeholder]
python "${scripts}/verificar.py" "${production}/NN - Title" [--placeholder]   # the testing stage
```

For the Errante final-demo profile, read the skill's `reference/errante-demo.md`.
`delivery.final` enables strict final checks by default: English narration, no subtitles,
an actual MP4 no longer than 30 seconds, current assets and source/AI credits. A preview
with `--draft` / `--placeholder` is not evidence of submission readiness. Update identity
and credits in course.yaml, refresh cards with `scaffold.py cards <video>`, then export slides.

- **Voice:** ${voice}. Pick it once, by ear, and keep it for the whole course. A video may change its speed
  (`velocidad: '+5%'` in its script frontmatter); everything else is the course's.
- **Recording:** ${recording_line}
- **Deck:** ${deck_line}

## Script versioning

- Scripts are `guion-vN.md`. A rewrite is a new file; older versions are kept.
- The script in use has `vigente: true` in its frontmatter — exactly one per folder. Superseded versions get
  `vigente: false` and a note at the top pointing to the current one.

## Content rules

- Verify every label, step and behavior against the product (or its code), not against its docs. Each script
  ends with a *Differences with the docs* table.
- **The voice never reads the slide.** The screen carries the summary; the narration carries the reasoning.
- No still image on screen for more than 12–13 s; past that, split the row or cut to a take. Flag it — never
  fix it with an effect.
- No zoom, transition or other effect unless the user asks for it. Annotations on a take (box, arrow, blur,
  spotlight, label, numbered steps, zoom) only where the user asks for them.
- One accent word per slide title. The kicker describes the video, never its level.
- Narration is written for TTS. Pause weight as the voice reads it: comma < semicolon < period; a colon barely
  pauses. Use `0.5s` inside a row for an exact pause; a row that is only `3s` is a silent hold on its visual.
- When the user asks for a rewrite or a pronunciation fix, render numbered audio options
  (`variantes.py`) and let them pick by ear. When the user has adjusted wording, keep it.
- Pronunciation fixes go to `voice.pronunciation` in `course.yaml`, never into the script, slides or UI labels.

## Iteration

- After any narration change, read the *changed rows* line `locutor.py` prints. Re-measure those rows with
  `pausas.py`, move the affected `t.at()` marks, re-record only those takes, then rebuild the montage.
- A cursor path takes ~2× its nominal duration while recording: budget `t.at()` marks accordingly.
- Every change ends with `verificar.py` passing (no errors; warnings reported to the user), plus contact
  sheets (frames every few seconds) of the montage. Nothing is called ready by assumption.

## Recording safety

- Claude never types credentials: the user signs in once with `grabar.py <course> --login`.
- Anything a take writes to the product (create, send, save) happens off camera, in setup, and is idempotent:
  reuse what already exists so re-recording never duplicates. Report every write to the user.
- Blur real names, teams and business figures (`recording.blur_selectors`), and check a capture before recording.

## Publishing

Copy the final video to `${publish}/<video>/`, write its `descripcion.md`, and prepare the rest (uploads,
messages, announcements). Uploading, sending or posting anything is always confirmed by the user first.

## Working with the user

- The user edits these files between turns. Re-read before editing, and never revert their changes.
- Touch only what was asked; propose anything else separately.
