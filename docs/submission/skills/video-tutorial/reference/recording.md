# Recording takes

`grabar.py` drives the product with Playwright (system Chrome) and records the takes a video's `tomas.py`
defines, at the course resolution, through a CDP screencast converted to constant fps. Each take lasts as long
as the longest row that shows it (from `timings.json`) plus 0.5 s: run `locutor.py` first.

## Before the first take

- For the public Errante 30-second demo, use `reference/errante-demo.md`; no login is needed.

- `grabar.py <course> --login` — the **user** signs in, in the Chrome window it opens, and closes it. The profile
  lives outside the course folder (`%LOCALAPPDATA%/video-tutorial/<course>`, or `recording.profile`).
- A redirect to an SSO host (`recording.sso_hosts`) means the session expired: ask the user to log in again.
- An unreachable host usually means a VPN is off.
- Every page gets `recording.local_storage` (theme, seasonal decorations…), a drawn black cursor, and
  `blur(6px)` on `recording.blur_selectors`. Record a capture and check the blur before the first take.

## tomas.py

```python
async def d3(t):
    await t.goto("/settings")                  # off camera: setup, never recorded
    await t.start(ready="main h1")             # recording starts once the page settles
    await t.at(2.1)                            # 2.1 s into the row: when the voice names it
    await t.click(t.page.get_by_role("button", name="Save"))
    await t.at(5.0)
    await t.highlight("button.save")           # a red box, only because the user asked
    await t.wait(1.0)

TOMAS = {"D3": d3}
CAPTURAS = {"background": background}          # PNGs for slides; may return a locator to crop to
```

Helpers: `goto`, `start(ready=)`, `settle`, `at(s)`, `wait(s)`, `move_to`, `click`, `hover`, `type_slow`,
`type_words`, `scroll`, `blur_words(selector, regex)`, and the annotations `highlight(target)`,
`highlight_zone(*targets)`, `arrow(target, side="left"|"right"|"top"|"bottom")`, `spotlight(target)` (dims
everything else), `label(target, text, side=)` (a short tag, kept on screen), `steps(*targets, start=1, side="corner")`
(numbered badges; one call per step reveals them one by one; a `side` beside the element for small text),
`zoom_to(target, scale=1.6)` / `zoom_out()`, and `unhighlight()`, which clears every annotation. Use `t.page`
for anything else. Annotations are red (`#ff0000`), 5 px — the style the user approved; use them only on
request.

- **Zoom** moves the element toward the middle of the screen but never past the edges of what was on screen,
  so an element near an edge stays near it. Draw annotations after `zoom_to`, and `unhighlight()` before
  `zoom_out()`: a box drawn at one zoom level does not follow the page to the other.
- **The cursor path** is the cursor helpers themselves (`move_to`, `hover`, `click`, `type_words`): when the user
  asks the cursor to go somewhere, it is a `move_to`/`hover` per stop, each at its `t.at()` mark.

## Pacing

- `pausas.py <video> --filas N` prints where each phrase of row N starts. Put `t.at(start - 0.2)` just before
  the word the action belongs to.
- **A cursor path takes ~2× its nominal duration while recording** (each step is a round trip). Budget for it,
  and shorten paths (`duration_s=0.4`) when a mark arrives late. `WARNING at(4.1): already 1.6 s late` means
  the actions before it took too long.
- Keystrokes slow ~5× on camera: use `type_words` for text that must appear within the row; `insert_text`
  for a paste.
- The take keeps recording 0.8 s after the last action (built in), so the last repaint is captured.
- Prefer stable selectors: roles and names, `data-*` attributes, ids. Read the product's code for them.

## Writes to the product

- With `recording.write_guard.enabled`, every non-read request to the app is aborted unless listed in `allow`,
  and reported at the end.
- A take that needs something to exist (an item, a conversation) creates it **in setup, off camera**, and only
  if it does not exist yet — an `ensure_*` function: look it up, create it if missing, return it. Re-recording
  must never duplicate. Report every write you make.
- Never press a write control on camera unless the script needs it, and never type credentials.

## Check every take

Extract frames at the moments that matter (`ffmpeg -ss T -i D3.mp4 -frames:v 1`), or a contact sheet
(`-vf "fps=1/2.5,scale=480:-1,tile=4x1"`), and look: right screen, cursor where the voice is, blur on, nothing
sensitive readable, annotations where asked.
