---
version: 1
current: true
status: draft
updated: '${date}'
---
> Errante final demo. English narration, no subtitles. Target 28–29 seconds; maximum 30.
> This is a starting script: measure the voice, then shorten wording or holds as needed.
> Opening requirement: within roughly the first 10 seconds, communicate Errante's
> distinguishing value and why a viewer should choose it. Show the connected public
> explorer, not a standalone logo. Support the pitch with working features; do not
> assert an unverified ranking or exclusive capability.

## Montage sheet

| # | Narration | Visual | In | Out | Dur. |
|---|---|---|---|---|---|
| 1 | Errante connects real NASA images, spectra, and light curves in one public explorer. | 🖼️ Slide 1 | | | |
| 2 | Search the infrared sky and investigate how it changes. | 🎬 D1 | | | |
| 3 | Barnard shifts between seasons. Its flagged core limits brightness measurements. | 🎬 D2 | | | |
| 4 | Inspect brightness measurements and uncertainties in a light curve. | 🎬 D3 | | | |
| 5 | Explore the changing sky with Errante. | 🖼️ Slide 2 | | | |

## Takes

- D1: prepared Barnard search results and context map. Select the saved sequence.
- D2: Barnard's real D2 season difference, S2 minus scaled S0, selected in Compare seasons.
  Prepare the calculation before recording. Show the orange/cyan dipole with dates,
  detector, flux scale and limitations. This is a processed difference, not a raw frame
  or a new parallax measurement; do not exaggerate displacement or erase caveats.
  The narration names the flagged core explicitly. Both the full image and its
  flagged-core warning must remain inside the recording frame.
- D3: the real precomputed R Draconis light curve, loaded before the shot. Include axes,
  measurement errors and the adjacent limitations. A shot change is an editorial cut,
  not a claim that archive jobs complete instantly.

## Cards

- Slide 1: Errante, registered team name, confirmed members and challenge.
- Slide 2: public app URL, team/members, data source and synthetic-voice attribution.
- After confirming identities or changing credits/URL in course.yaml, run scaffold.py cards
  for this video, then export slides again. Do not add generated NASA logos or imagery.

## Review before delivery

- Measure rows 1–2 with the selected English voice: the distinguishing value should
  be clear by approximately 10 seconds. Shorten or rephrase the opening if needed;
  this is an editorial target, separate from the strict 30-second total cap.
- Listen to the English voice and SPHEREx pronunciation; no subtitles are requested.
- Confirm public-output terms for the chosen narration source (see reference/voice.md),
  retain the explicit AI voice credit on the closing card/in metadata/description if
  synthetic, and declare it in the submission form. Do not mark rights reviewed by assumption.
- Check that all frames are real observations and no unreviewed physical claim is added.
- If replacing the target with Barnard, retain "predicted from catalog, not a measurement".
  Its small image shift must not be exaggerated. Do not describe a catalog track as a detection.
- Temperatures, if shown, are conditional color-temperature estimates, not stellar Teff.
  RW Aur's identity and saturation caveats must remain visible if used instead.
- Inspect contact sheets and watch/listen to the full final MP4. Verify an anonymous hosted
  link separately after an explicitly authorized upload. Automated checks cannot replace this.

## Differences with the docs

| Documentation or proposed shot | Verified behavior in the deployed product | Consequence for the edit |
|---|---|---|
| Search / playback / light curve | Verify before recording | Replace unavailable shots honestly; do not simulate a result. |
