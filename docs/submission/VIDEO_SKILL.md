# Reusable video skill

The complete adapted skill is in [`skills/video-tutorial/`](skills/video-tutorial/).
It includes instructions, Python scripts, tests, templates and the English Errante
demo profile. Virtual environments, caches, login profiles and generated footage
are excluded. This is production tooling, not the submitted demo video.
Only neutral/custom design options are supported. The distributable contains no
third-party corporate preset or bundled font binaries; the default uses system fonts.

## Download or use with an agent

Clone this repository, or use GitHub **Code → Download ZIP**, extract it and copy
`docs/submission/skills/video-tutorial/` wherever you keep local skills. Copy the
whole folder: `SKILL.md` depends on the adjacent scripts, references and templates.

For Codex, place that folder in your local skills directory, normally
`~/.codex/skills/video-tutorial/`, and start a new session. You can also point your
agent directly at the downloaded `SKILL.md`, without installing it globally.

The [Errante production guide](skills/video-tutorial/reference/errante-demo.md)
describes the profile and the remaining human checks.

## Run the tools directly

From the downloaded skill folder, use Python 3.11+ and install dependencies into a local virtual
environment. On Windows:

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe scripts/scaffold.py demo ..\errante-video-production
```

On macOS/Linux, use `python3 -m venv .venv` and `.venv/bin/python` for subsequent
commands. FFmpeg is provided by `imageio-ffmpeg`. The recorder retains its original
system-Chrome requirement; this import adds no alternative-browser support.
Kokoro is optional and unnecessary for the default English Edge TTS voice.

Keep the generated production folder outside the repository. Confirm the team and
accepted members, deployment URL, scientific labels and available UI before filming.
The profile uses **English narration without subtitles**, a 28–29-second target and
a strict **30-second maximum on the actual final MP4**. In approximately the first
10 seconds, state Errante's demonstrated distinguishing value; later shots must
show the promised features. Do not claim an unsupported ranking or exclusivity.

The final verifier checks current narration/build inputs, source and synthetic-voice
credits, metadata and exact MP4 duration. These checks do not establish scientific
validity, human approval or anonymous access to a hosted video. Watch and listen to
the output, then verify the hosted link separately after an authorized upload.

For tests, install `pytest` in the skill environment and run
`python -m pytest scripts/tests -q`. Browser tests may be skipped when their required
browser is unavailable.

## Provenance and AI assistance

The original `video-tutorial` folder was supplied by the user. OpenAI Codex adapted
the short-demo instructions, English script, cards, delivery checks and regression
tests on November 15, 2026 at the user's request. After review of the initial import
(#118), the premature merge was reverted and a clean replacement was prepared without
the third-party corporate preset or commercial fonts. The replacement does not replay
the original import commit; its proposed commits contain no font binaries. The earlier
merge/revert remain in repository history.
See [component metadata](skills/video-tutorial/ai-usage.json).
No final narrated video was produced or uploaded by this import. Original asset
rights, the wider source/AI inventory and human review remain team responsibilities.
Generated narration requires an explicit disclosure in the final video, description,
metadata and the submission form. See [voice publication notes](skills/video-tutorial/reference/voice.md)
for checked source links and the remaining review of service/output terms. Package
availability and a permissive code license do not clear voice-output rights.
