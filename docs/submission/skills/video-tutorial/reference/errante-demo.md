# Errante: English 30-second final demo

Use this mode for the NASA Space Apps submission, not for a training course. The
user selected **English narration, no subtitles**. Keep the general tutorial mode
available for other work. The provided project submission guide is the rules source;
check the current project docs before a future event rather than assuming rules persist.

## Create the production folder

Run `scaffold.py demo <folder>` (optionally `--base-url URL`) in a separate production
folder. It creates one video, a short English script, real-UI take definitions and
two dark Errante cards. It performs no network requests or publishing. It refuses
to replace an existing course.yaml. Existing projects can copy the profile settings
from `templates/errante-demo/course.yaml` without overwriting their own files.

The configured URL is the team's public deployment at the time of adaptation. Verify
it before filming; update it if the domain changes. Confirm the registered team name
and accepted member names in `delivery.team` / `delivery.members`; do not invent names
or assume the product name is the registered team. These fields are intentionally
empty until confirmed. The strict final check rejects missing/placeholder identities.

## Narrative and capture

Use roughly 4–5 short scenes: identity/problem, sky search, dated real observations,
one scientific product, and a readable closing/source card. The supplied ~50-word
English script is a starting point, not a measured promise of duration. Listen to
the voice and pronunciation, then use the **measured** narration to pace every shot.
`en-US-JennyNeural` is the initial English voice; other English voices or human English
narration are supported. Do not switch the voice back to Spanish or add subtitles.

**First ~10 seconds:** explain what makes Errante different and why it is a strong
choice. Lead with its demonstrated value: a public explorer connecting real NASA
images, spectra and light curves so viewers can investigate a changing infrared sky.
Use the first two narration rows for this promise and begin showing the application
early. Keep team/challenge identity visible without spending the entire opening on
a logo. Measure those rows with the selected voice and shorten them if the benefit
arrives too late. The 10-second opening is an approximate editorial target, not a
second hard duration limit. Do not replace evidence with an unverified "best", "only"
or discovery claim; the remaining shots must demonstrate the opening's promise.

- Budget **28–29 seconds total**, including titles, silence, credits and audio padding.
  The absolute cap is 30 seconds with no extra 0.5-second allowance. The existing
  0.5-second audio alignment tolerance is a separate check. Shorten text or shot holds;
  do not clip the narration with `-t 30`, speed up the science, or inflate playback motion.
- Use prepared, real curated observations and published light curves. Load images,
  products and the context map off camera. If an async job is shown through a cut,
  make the omitted wait clear; never imply instant archive computation.
- The default shots use R Draconis, one available detector and its published light curve.
  Verify selectors and available products against the deployed UI. Start recording only
  after real images have loaded. A failed image, error panel or empty chart is not a shot.
- The sky map is a **context coadd**, not temporal evidence. Preserve dates, wavelength,
  source/quality labels and relevant warnings. An absent quality flag is not "clean".
- For Barnard, retain the app's "predicted from catalog, not a measurement" label. Its
  small native-pixel displacement is not a newly measured detection. Do not exaggerate it.
- If using spectra/3D instead, preserve catalog versus SPHEREx attribution. Conditional
  color temperature is not stellar effective temperature. Keep RW Aur identity and
  saturation caveats. Do not invent radii, composition or future trajectories from images.
- Inspect a short real take first: encoded 30 fps does not guarantee 30 distinct captured
  WebGL frames per second. Check playback, readable labels and framing, then record the rest.
  The supplied takes keep the browser recording for their measured duration: a short blink
  padded with its last still frame is not equivalent to a full moving-image shot.

The app is public: no login is needed. The default write guard allows reads only.
Do not trigger production jobs just to obtain footage when existing observations suffice.
If a chosen scientific endpoint needs POST, allow only that endpoint when it is in scope.

## Cards, credits and final build

After changing team, members, URL or credits, run:

```text
scaffold.py cards <video>
slides.py <video>
locutor.py <video> --sync
grabar.py <video>
montar.py <video>
verificar.py <video> --final
```

The profile enables strict final checks by default. `montar.py` runs them after
rendering and must not report success if they fail. `--draft` permits a preview;
`montar.py <video> --draft --placeholder` is explicitly not a final delivery.

Credits from `delivery.credits` and `delivery.ai_audio_credit` appear on the closing
card, in the generated `descripcion.md` and in MP4 comment metadata. The English
audio stream is tagged `eng`. A pre-existing description is preserved: update its
credits when settings change. Keep the description's source/AI declarations when
uploading. The remaining project's AI/code/source inventory still needs team review.
Complete the submission form's AI-use field explicitly; a local metadata check does
not fill the form. Check `voice.md` for the separate review of public-output terms
before using a generated voice in the published demo. The default engine is not a
claim that voice-output rights have been cleared.

Real application captures and telescope observation products are not AI-generated
astronomical imagery. If generative images/video are introduced later, the supplied
guide requires a visible AI watermark; this profile does not generate those assets.
Do not generate or modify NASA logos/mission branding. Plain-text source attribution
and Errante's own visual identity suffice.

The verifier checks exact MP4 movie/track presentation duration, narration provenance,
render dimensions/fps, build/input hashes, description credits and actual embedded tags.
Unknown/corrupt duration is an error, not a pass. English settings/voice are checked;
the program cannot establish spoken language, truth, readable credits or image quality
by itself. Watch and listen to the entire output and inspect contact sheets.

Hosting is a separate action. After an authorized upload, check the **video link**
without login in a private session and another device/session. A local MP4 passing
verification does not prove that the hosted link is public. Do not publish as part
of merely adapting the skill or preparing assets.
