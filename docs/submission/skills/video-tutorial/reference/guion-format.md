# Script format

A video folder (`internal/NN - Title/`) holds versioned scripts, `guion-vN.md` (or `script-vN.md`). The one in
use has `vigente: true` (or `current: true`) in its frontmatter — exactly one per folder. A rewrite is a new
version; older ones get `vigente: false` and a note pointing to the current one. Start a video with
`scaffold.py video <course> "NN - Title"`; it writes `guion-v1.md` from the course-language template.

## The montage sheet

Under a `## Hoja de montaje` (or `## Montage sheet`) heading:

| # | Locución | Imagen | Entra | Sale | Dur. |
|---|---|---|---|---|---|
| 1 | Una frase de locución. | 🖼️ Slide 1 | | | |
| 2 | Otra frase. 0.5s Y otra, tras una pausa exacta. | 🎬 D1 | | | |
| 3 | Un tramo de una toma larga. | 🎬 D2 [0:04–0:09.5] | | | |
| 4 | Una imagen fija que se acerca despacio. | 🖼️ Slide 2 · zoom | | | |

- **One row = one narration phrase + one visual.** The visual cell holds exactly one: `Slide N` (the N-th
  exported slide, after builds expand) or `DN` / `DNa` (a take in `grabaciones/`). Alternatives go to the
  production notes, never into the cell.
- `0.5s` inside the narration is an exact pause (split point for the voice). A row whose narration is only
  a pause (`3s`) holds its visual in silence: use it after a question, or to let a screen be read. Pauses are
  at most 9.9 s; a longer `Ns` token (`1990s`) is read as text.
- `[m:ss–m:ss]` trims a take; without it the take plays from its start.
- `zoom` is opt-in, only when the user asks for it.
- `Entra / Sale / Dur.` are written by `locutor.py --sync`. Never type them.
- Narration is plain text for TTS: no markdown, no parentheses read aloud. Product terms as the UI shows them.
- **Speed for one video:** `velocidad: '+5%'` (or `speed:`) in the frontmatter overrides `voice.rate`.

## Writing the narration

- The voice never reads the slide: the slide summarizes, the voice explains why.
- Pause weight as neural voices read it: comma < semicolon < period. **A colon barely pauses** — use a period
  when the user wants a break. Use a semicolon on purpose, to separate items read in one breath.
- A period between very short phrases sounds slow: keep a short list in one row.
- No still over 12–13 s: split a long slide row into several rows over a build (`data-steps`), or cut to a take.
- Rows are renumbered when one is inserted or removed: update every citation (`fila N` in the script, `row N`
  in `tomas.py` comments) in the same change.

## The rest of the script

After the sheet: **Slides** (what each shows and which row it goes in), **Tomas** (per take: where it starts,
what the cursor does, tied to the narration), **Notas de producción**, and **Diferencias con los docs** (what
the docs say, what the product does, what the script follows). Verify every label and step against the product
or its code before writing it.
