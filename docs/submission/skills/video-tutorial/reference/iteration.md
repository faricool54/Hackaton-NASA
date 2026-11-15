# Iteration recipes

Every change follows the same loop: **edit the source → regenerate only what depends on it → verify → rebuild
the montage → say what changed and what did not**. Re-read files before editing: the user edits between turns.

## What each change regenerates

| Change | Regenerate |
|---|---|
| Narration text of a row | `locutor.py <video> --sync` → read *changed rows* → `pausas.py --filas N` → re-pace and re-record the take of that row if its marks moved → `montar.py` |
| A pronunciation entry | same as narration (only rows containing the word change) |
| Video speed (`velocidad:`) | narration; every row moves ~proportionally: rescale each take's `t.at()` by its row's new/old duration ratio, re-record every take, rebuild |
| A slide's content | `slides.py <video>` → `montar.py` |
| Slides added/removed/split | deck + renumber `Slide N` cells → `slides.py` → `locutor.py --sync` (row count) → `montar.py` |
| Rows added, removed, merged | script + renumber citations (script and `tomas.py`) → `locutor.py --sync` → affected takes → `montar.py` |
| A take's actions, boxes, arrows | `tomas.py` → `grabar.py <video> --tomas DN` → check frames → `montar.py` |
| "This still stays too short/long" | the row's narration decides its length: add words, a `0.5s` pause, or a row; never pad with an effect |

## Typical requests

- **"Lines 5 to 8: drop this sentence."** Edit the rows. If a row becomes too short for its visual, say so and
  propose merging it with a neighbor.
- **"Move line 8 to the start."** Reorder rows and renumber; check that the takes still make sense in the new
  order (a take may start where the previous one ended).
- **"Line 3: give me options."** Write 2–3 genuinely different rewrites, render them with
  `variantes.py --fila 3 --textos "…" "…"`, send the files, recommend one. Apply only the pick.
- **"Line 8: I don't like how it says X."** `variantes.py --fila 8 --buscar "X" --opciones <4–6 respellings>`;
  include the original as v1 (automatic). The pick goes to `voice.pronunciation` (see `voice.md`). If none
  works, propose a wording change instead.
- **"Add a pause after X."** Insert `0.5s` in the narration after X.
- **"Slide 4: split it in two" / "add a diagram".** Edit the deck with existing components; re-export.
- **"This take is too long by 1.5 s."** Takes last as long as their row: shorten the row's narration, or trim
  with `[m:ss–m:ss]` if the take has dead time at the start.
- **"Put a red box / an arrow on X when it says Y."** `pausas.py` for the row → `t.at(start_of_Y - 0.2)` →
  `t.highlight` / `t.arrow` → `t.unhighlight()` when the user says it goes away (or at the next action).
- **"Remove take DN."** Its row needs another visual: merge the row with a neighbor over another take, or ask.
  Delete `grabaciones/DN.mp4` and the take from `tomas.py`.

## Verify, every time

- `locutor.py` prints *changed rows*: if a row you did not touch changed, look before going on (a truncated
  voice is retried automatically; a real change means an unintended edit).
- After recording, extract frames at the moments that matter (ffmpeg `-ss` + `-frames:v 1`, or a `tile`
  contact sheet) and look at them before saying a take is right.
- After the montage, a contact sheet every ~10 s.
- **Testing stage, mandatory:** `verificar.py <video>` (add `--placeholder` for a draft with takes still
  missing). It checks the script parses, every slide and take it cites exists, the narration matches the
  script (rows and speed), no still passes 13 s, takes cover their rows, and the montage has the narration's
  length, the course's resolution and fps, and is newer than its inputs. An error is fixed before going on;
  a warning is told to the user.
- Then report briefly: what changed, what was regenerated, what was checked, anything you noticed but did not
  change.
