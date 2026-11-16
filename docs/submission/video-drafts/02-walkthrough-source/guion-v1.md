---
version: 1
current: true
status: draft
updated: '2026-11-15'
---
> Errante walkthrough (second demo cut), following the route proposed by faricool54 in #100:
> pick a target (Barnard) and show the blink in Time; hover a Gaia star for its card and
> click it; open its Object card and its 3D view. English narration, no subtitles.
> Maximum 30 seconds. The optional new-point build (~80–90 s) is not shown.

## Montage sheet

| # | Narration | Visual | In | Out | Dur. |
|---|---|---|---|---|---|
| 1 | Errante connects real NASA images, spectra, and light curves in one public explorer. | 🖼️ Slide 1 | 0:00.1 | 0:06.7 | 6.5 s |
| 2 | Pick Barnard's Star to blink its real SPHEREx frames. | 🎬 D1 | 0:06.7 | 0:10.8 | 4.2 s |
| 3 | Hover a Gaia star for its catalog card; click to select it. | 🎬 D2 | 0:10.8 | 0:15.7 | 4.9 s |
| 4 | Object lists its catalog facts, each with a source. | 🎬 D3 | 0:15.7 | 0:20.2 | 4.5 s |
| 5 | 3D models its confirmed planets from catalog data. | 🎬 D4 | 0:20.2 | 0:24.4 | 4.3 s |
| 6 | Explore the changing sky with Errante. | 🖼️ Slide 2 | 0:24.4 | 0:28.2 | 3.7 s |

## Takes

- D1: home page with the map ready. Click the Barnard's Star target chip; the map centers on it
  and the Time tab plays the real SPHEREx frames (blink). Frames are preloaded off camera so the
  blink starts promptly; nothing is sped up.
- D2: Barnard selected via its chip off camera, Gaia markers loaded. On camera the cursor moves
  onto the Gaia DR3 marker of Barnard's Star, the hover card shows (Gaia DR3 catalog, not SPHEREx
  measurements), then a click selects it ("Selected", dock title becomes the Gaia DR3 id).
- D3: same selection. Click the Object tab: catalog card with Barnard's star, Gaia match, distance,
  spectral type, variability and planets, each with its source. The catalog lookup is loaded off
  camera first (Retry used off camera if a catalog service does not answer).
- D4: same selection, Object tab showing. Click the 3D tab: "3D MODEL · NOT AN IMAGE" model of
  the Barnard's Star system built from catalog values; its labels stay in frame.

## Cards

- Slide 1 and Slide 2 are the same cards as video 01 (team, members, challenge; URL, credits,
  data DOIs, AI narration credit).

## Review before delivery

- The selection triggers POST /api/spectra; the write guard blocks it. The Spectrum tab is not
  shown. Check the captures for any visible error caused by the blocked request.
- Keep the catalog labels ("Catalog · not SPHEREx", "3D MODEL · NOT AN IMAGE") inside the frame.
- Inspect contact sheets and watch/listen to the full final MP4.

## Differences with the docs

| Documentation or proposed shot | Verified behavior in the deployed product | Consequence for the edit |
|---|---|---|
| "Click a Gaia star to see its card and the 3D" (#100) | Clicking selects it and keeps the Time tab; Object and 3D are opened from the dock tabs | D3 and D4 click the Object and 3D tabs on camera |
| Object card always filled | First lookup may report catalogs without answer; Retry fills it (verified 2026-11-15) | Lookup is loaded and retried off camera before D3 |
| Optional new-point build | Takes ~80–90 s | Not shown in this cut |
