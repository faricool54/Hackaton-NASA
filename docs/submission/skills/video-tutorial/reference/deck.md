# Deck and slides

Each video has a self-contained `presentacion.html`, copied from the course's `_template/` (example slides
removed). `slides.py <video>` exports every slide to `assets/slides/slide-NN.png` at the course resolution, in
recording mode (`?rec`: no help line, no cursor, no entry animation), and removes stale PNGs.

## Design system

- Chosen in the setup wizard: `deck.design_system` = `neutral` or `custom` (with `deck.tokens` and
  `deck.font`). `scaffold.py deck <course>` re-applies it to `_template/` (the block between
  `/* @tokens:start */` and `/* @tokens:end */`, plus the `@font-face` block and the font files).
- Existing videos keep their copy; re-copy the token block by hand if the user wants them updated too.
- Colors come only from the tokens; never write a loose color in a component.
- The distributable bundles only the neutral preset with system fonts. For custom
  fonts or branding, record the source and redistribution permission before adding
  assets. Do not copy third-party corporate design systems into submission materials.

## Components (in `_template/presentacion.html`, the `data-guia` example slides)

cover (`.slide.cover`, background capture at 25 %), title + subtitle, `.steps` (a short path), `.fields`
(labelled facts), `.modes` (two options, `.on` = the one that matters), `.compare` (what it is not → what it
is), `.cards` (three, `.hi` = the one), `.prefixes` (big-label list, `.warn` for the confusing case, `.dense`
for 5+ items), `.warnbox` (the one warning of the video), `.chat` (a chat recreated — never a real
screenshot), `.split` + `.diagram` (SVG: white nodes, accent hub, grey arrows), `.shot` (a capture; shows the
missing file name when absent). Reuse them before inventing a new one.

## Rules

- One accent word (`.accent`) per title. The kicker describes the video, never its level.
- No progress bar or page counter.
- **Builds**: `<section class="slide" data-steps="N">` expands into N slides; an element with `data-in="k"`
  appears at step k (`.on` animates it). Use a build to keep a long explanation on screen across several rows
  without a still over 13 s. Exported numbering counts the expanded slides: renumber `Slide N` cells.
- A capture inside a slide comes from `grabar.py --capturas` (rendered at 2×), blurred like the takes.
- Keys while presenting: ← → navigate, T theme, F full screen, G recording mode; `#n` opens slide n.
