---
version: 1
current: true
status: draft
updated: '2026-11-15'
velocidad: '+6%'
---
> Errante final cut (v4), after the team's feedback on v3: a commercial, attention-grabbing opening
> (first ~10 s), no static opening slide, more movement, a more natural voice (Ava). Same honest
> route as v3 (point → real build with the cut stated → Gaia star → Object → 3D), recorded on 08dfb85.
> Movement and overlays were requested by the team (#100 / V0id47): animated title over the real
> expanded colour blink, slow push-in, zooms into the dock panels, closing card push-in. Max 30 s.

## Montage sheet

| # | Narration | Visual | In | Out | Dur. |
|---|---|---|---|---|---|
| 1 | The infrared sky is never still. Errante lets you watch it change, in real NASA SPHEREx images. | 🎬 D0 | 0:00.1 | 0:07.0 | 6.8 s |
| 2 | Pick any point, and Errante builds its sequence from the archive. | 🎬 D1 | 0:07.0 | 0:11.3 | 4.3 s |
| 3 | After a cut for the build, its real frames blink in false color. | 🎬 D2 | 0:11.3 | 0:15.5 | 4.3 s |
| 4 | Hover a Gaia star, click it, and read its catalog facts. 0.3s | 🎬 D3 | 0:15.5 | 0:19.8 | 4.3 s |
| 5 | Then explore it in 3D, from catalog values. | 🎬 D4 | 0:19.8 | 0:23.7 | 3.9 s |
| 6 | Errante. Explore the changing sky. | 🖼️ Slide 2 · zoom | 0:23.7 | 0:27.2 | 3.5 s |

## Takes

- D0 (hook): the finished job field from v3 (76.73297°, +30.23697°, job 7aa7d11f), "Color · detectors"
  and "Expand" set off camera: the real false-colour season blink fills the window. On camera an
  animated title overlay (ERRANTE · "Watch the infrared sky change." · "Real NASA SPHEREx images")
  fades in over a slow push-in. The images are the app's real composites; nothing is generated.
- D1: a fresh selected position next to Gaia DR3 156328460158131584; the cursor clicks "Build SPHEREx
  sequence" (All detectors · color) and the real job starts (POST /api/jobs, allowed and reported).
- D2: the same job, finished. The on-screen label gives the measured build time from the job API.
  "Color · detectors" is clicked: real frames blink in false colour.
- D3: zoomed map, hover the star (card), click, Object; then a zoom into the Object card.
- D4: 3D tab; zoom into the catalog model ("3D MODEL · NOT AN IMAGE" stays in frame).
- Slide 2: closing card (URL, team, members, NASA/IRSA credits, DOIs, AI narration) with a slow push-in.

## Review before delivery

- The cut is stated in voice and on screen with the measured time. False colour is named.
- Keep "Catalog · not SPHEREx" and "3D MODEL · NOT AN IMAGE" readable in frame.
- Inspect contact sheets and the full MP4.

## Differences with the docs

| Documentation or proposed shot | Verified behavior in the deployed product | Consequence for the edit |
|---|---|---|
| Build ~80–90 s (#100) | v3's recorded job took 1 min 53 s; public probes 60–310 s (queue) | Cut stated with the measured time of the recorded job |
| Gaia markers after a build | Wide post-build view: "Gaia DR3 stars did not load for this wide view (VizieR did not answer)" | Zoom in off camera before hovering |
| "Expand" in Time | Expands the player to the whole window (real composites, B/W or colour) | Used as the hook background |
