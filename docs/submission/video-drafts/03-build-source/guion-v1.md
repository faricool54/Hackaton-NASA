---
version: 1
current: true
status: draft
updated: '2026-11-15'
---
> Errante build walkthrough (third cut), following faricool54's route after the e89ab45 deploy (#100):
> pick a point, build its SPHEREx sequence (color), click a Gaia star for its Object card and 3D,
> and cut the build wait, saying so in the video. English narration, no subtitles. Maximum 30 s.

## Montage sheet

| # | Narration | Visual | In | Out | Dur. |
|---|---|---|---|---|---|
| 1 | Errante connects real NASA images, spectra, and light curves in one public explorer. | 🖼️ Slide 1 | 0:00.1 | 0:06.7 | 6.5 s |
| 2 | Pick a point in the sky and build its SPHEREx sequence. | 🎬 D1 | 0:06.7 | 0:10.9 | 4.2 s |
| 3 | After a two-minute cut, its real frames blink in false color. | 🎬 D2 | 0:10.9 | 0:15.6 | 4.7 s |
| 4 | Hover a Gaia star for its card; click it for its catalog facts. | 🎬 D3 | 0:15.6 | 0:20.7 | 5.0 s |
| 5 | 3D draws it from catalog values. | 🎬 D4 | 0:20.7 | 0:24.1 | 3.4 s |
| 6 | Explore the changing sky with Errante. | 🖼️ Slide 2 | 0:24.1 | 0:27.8 | 3.7 s |

## Takes

- D1: a selected sky position (76.73197°, +30.23697°, Gaia DR3 156328460158131584, the star faricool54
  and DankoLiv verified after #160). On camera the cursor clicks "Build SPHEREx sequence" with the
  default "All detectors · color"; the dock shows the real job starting. This is a real build request
  (POST /api/jobs, allowed by the write guard); it is reported to the team.
- D2: after the cut. The same job, finished (~80–90 s measured off camera). On camera: "Color ·
  detectors" is clicked and the real frames blink in false colour. A label on screen states the cut.
- D3: same field, zoomed so the Gaia DR3 markers load. Hover the star for its card, click it, open
  Object (Matched, distance from the Gaia DR3 parallax). The lookup is loaded off camera first.
- D4: same selection; click 3D: the star drawn from catalog values, "3D MODEL · NOT AN IMAGE".

## Review before delivery

- The cut must be stated in the narration and on screen; no claim that the build is instant.
- Keep "Catalog · not SPHEREx" and "3D MODEL · NOT AN IMAGE" in frame. False colour is named as such.
- Inspect contact sheets and watch/listen to the full final MP4.

## Differences with the docs

| Documentation or proposed shot | Verified behavior in the deployed product | Consequence for the edit |
|---|---|---|
| Build ~80–90 s (#100) | Off camera 76.73197, +30.23697 built in 93 s (e89ab45); the recorded D1 job at 76.73297 took 1 min 53 s (01:07:34Z → 01:09:27Z, job 7aa7d11f) | Wait cut; narration and on-screen label give the measured time |
| Gaia markers after a build | The post-build view (42′ × 30′) showed "Gaia DR3 stars did not load for this wide view (VizieR did not answer)" | Zoom in off camera before hovering |
| Blink colour | B/W by default; "Color · detectors" available; "Color · J/H/K" not available for this field | D2 clicks "Color · detectors" on camera |
