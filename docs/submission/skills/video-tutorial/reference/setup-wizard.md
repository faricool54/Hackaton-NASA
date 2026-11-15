# Setup wizard

For the English 30-second Errante / NASA Space Apps demo, use `errante-demo.md`
and `scaffold.py demo <folder>` directly. Do not repeat the course wizard for choices
the user already supplied. The general wizard below remains for other courses.

Run it when there is no `course.yaml`, or when the user asks to set up a new course. It ends with a working
course folder and the user knowing how to drive it.

How to run it:
- Speak the user's language. Ask with **AskUserQuestion**, one block at a time, at most 4 questions per call.
  Put the recommended option first and mark it "(Recommended)".
- Never ask what you can find out: list the connected MCP servers, look for docs in the repo, read the URL the
  user gave.
- Keep the answers in an `answers.yaml` (scratch file) with the same schema as `templates/course.yaml`. Only
  write keys that differ from the defaults.
- After each block, say in one line what you will set up, then move on.

## Block 0 · The course

- **Folder** where the course will live (it may be inside an existing project). The folder name becomes the
  browser profile name for recordings.
- **Name** of the course, and **language** of the narration and slides (`es`, `en`, `pt`…).

## Block 1 · Content

1. **Subject.** Is it about a platform or product? Which one? → `sources.platform`.
2. **Sources.** Docs, specs, wikis, repos, URLs; MCP servers that can answer questions about the product; whether
   you may explore the product in the browser (built-in browser, or the user's Chrome). → `sources.docs`,
   `sources.notes`. Remind the user: scripts are verified against the product itself, not only its docs.
3. **Slides?** If yes, the **design system**:
   - *Neutral* — an indigo accent and the system font. (Recommended when there is no brand.)
   - *Custom* — ask for the accent color (hex), and optionally a font: family name plus local `.woff2` files.
     Use only assets with established rights for the intended use and redistribution;
     the skill itself bundles no font files or third-party corporate presets.
     Derive the light container color (a ~10 % tint of the accent) and dark-mode values yourself.
   → `deck.enabled`, `deck.design_system`, `deck.tokens`, `deck.font`.
4. **Screen footage.** Live takes recorded automatically (Playwright drives the product), screenshots only, or
   none. If takes:
   - `recording.base_url` — the product's URL.
   - SSO: which login host appears when the session expires (Okta by default) → `recording.sso_hosts`.
   - Does it need a VPN? (Only to explain errors later.)
   - **Write guard** — recommend **on** when recording against production: every request that is not a read is
     blocked unless allowed. Takes that must create something do it in setup, idempotently.
   - What must never be readable on screen (people, teams, figures) → `recording.blur_selectors`, filled when
     the first capture is checked.
5. **Audience and shape.** Audience (technical, product, everyone), depth of concepts, typical video length,
   resolution (1920×1080 recommended; 1280×720; vertical 1080×1920). → `audience`, `depth`,
   `target_duration`, `video`.

## Block 2 · Voice

1. **AI voice or a person?** A person (`voice.engine: human`) is experimental: they record each row as
   `locucion/humana/fila-NN.wav` and the pipeline measures and joins them.
2. **AI voice.** Set `voice.candidates` to 3–4 neural voices in the course language — es: `es-MX-DaliaNeural`,
   `es-MX-JorgeNeural`, `es-CO-SalomeNeural`, `es-CO-GonzaloNeural`; en: `en-US-JennyNeural`,
   `en-US-GuyNeural`, `en-US-AriaNeural`; pt: `pt-BR-FranciscaNeural`, `pt-BR-AntonioNeural`.
   Offer the **Kokoro** voices too (local, offline; English terms inside Spanish keep an English accent) —
   es: `ef_dora`, `em_alex`, `em_santa`; en: `af_heart`, `am_adam`; pt: `pf_dora`, `pm_alex` — if the user
   wants to hear them, add one or two to the candidates and run `kokoro_setup.py` in Block 3.
   After `scaffold.py init`, run `voces.py <course>`, send the samples (SendUserFile) and let the user pick by
   ear → `voice.name`. The engine follows from the name; see `reference/voice.md`.
3. **Speed.** `voces.py <course> --voz <picked> --velocidades +0% +5% +10%`, the user picks → `voice.rate`.
   One voice and one speed for the whole course; a single video may override its speed later.
4. **Pronunciation dictionary** starts empty. Tell the user it grows as they listen: "line 8: I don't like how
   it says X, give me options".

## Block 3 · Install and check

**You do this, not the user.** Nobody should have to type a command to start a course: run the checks, install
what is missing, and tell the user in one line what you installed.

- Python 3.10+ (`py --version` on Windows, `python3 --version` elsewhere). If it is missing, that is the one
  thing the user installs: point them to python.org and wait.
- `python -m pip install edge-tts imageio-ffmpeg playwright pillow pyyaml` — only the packages that fail to import.
- Chrome or Edge: `slides.find_browser()` must find one (no browser download; Playwright uses the system Chrome).
- If a Kokoro voice is among the candidates: `python kokoro_setup.py` (its own venv, ~1 GB, a few minutes)
  and `espeak-ng` on PATH.
- If recording: `grabar.py <course> --login` opens Chrome — **the user signs in**; Claude never types
  credentials. It closes on its own once they are in the app. An unreachable host usually means the VPN is off.

## Installing the skill itself

If the user asks you to install this skill for them ("install the video-tutorial skill from <folder or repo>"):
clone or locate the folder, then link it as `~/.claude/skills/video-tutorial` — a junction on Windows
(`New-Item -ItemType Junction`, no admin rights needed), a symlink elsewhere — and tell them to start a new
Claude Code session so it is picked up.

## Write the course

1. `python scaffold.py init <course> --answers answers.yaml` → `course.yaml`, `CLAUDE.md` (conventions),
   `README.md` (how to work on the course), `internal/`, `export/`, `_template/presentacion.html`.
2. Voice samples (Block 2), then update `voice.name` / `voice.rate` in `course.yaml`.
3. If there are slides: `python slides.py <course>/_template` exports the template's example slides — send two
   or three so the user approves the design system. A change → edit `deck` in `course.yaml`, then
   `scaffold.py deck <course>`.
4. If recording: after the first video exists, record its `background` capture (`grabar.py <video> --capturas`)
   and check the blur together.

## Close: teach the skill

Show the user, briefly, how to work from here — it is also in the course `README.md`:

- **The pipeline**: script → deck → slides → narration → takes → montage, and that everything after the script
  is regenerated, so they only ask for changes.
- **Typical requests per stage**, with examples:
  - *Start*: "let's build the script, deck and slides for a video about X".
  - *Script*: "lines 5 to 8: we won't cover X yet, drop that"; "move line 8 to the top".
  - *Slides*: "slide 2: change the subtitle"; "slide 4: split it in two"; "slide 6: add a flow diagram".
  - *Narration*: "line 8: I don't like how it says 'team', give me options"; "add a pause after X";
    "make this video 1.05x faster".
  - *Takes*: "record every take"; "this take runs long, make it 1.5 s shorter".
  - *Montage*: "slide 4 goes too fast, keep it 2 s longer"; "rebuild the montage".
- **Annotations on a take** — they exist only if asked for: a **box** around an element or a whole area, an
  **arrow** pointing at an element from one side, a **blur** over an element or a single word, a **spotlight**
  that dims everything else, a text **label**, numbered **steps**, a **zoom** into one area, and the **cursor's
  path**, each tied to the moment the voice says something ("when it says 'Save', box the button").
- **Nothing is fixed**: every answer can be changed or extended later by asking (more docs, another voice or
  speed, another design, another URL or blur list).
- **Safety**: they sign in themselves; production writes are reported; nothing is uploaded or sent without
  their OK.

Offer the visual guide: `guia.html` in this skill's folder — open it in the built-in browser, or publish it as
a private Artifact only if they ask. Then suggest the first request: "let's build the script, deck and slides
for a video about …".
