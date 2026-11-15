# ${name}

A video course made with the **video-tutorial** Claude Code skill. Each video comes from a script with a
*montage sheet*: one row is one narration phrase plus one visual (a slide or a screen take). Slides, voice,
recording and the edit are all generated from it.

Talk to Claude in plain language, inside this folder. These are the typical requests at each stage.

## 1. Start a video

> let's build the script, deck and slides for a video about *X*
> new video "03 - Permissions": how they are requested and who approves them

## 2. Script

> lines 5 to 8: we won't cover *X* yet, drop that sentence
> move line 8 to the top, we'll start with that
> line 3: give me options

Wording options come as numbered audio samples, to pick by ear.

## 3. Slides

> slide 2: change the subtitle to something about *X*
> slide 4: split it in two, one for A and one for B
> slide 6: add a flow diagram to explain *X*

## 4. Narration

> line 8: I don't like how it says "team", give me options
> line 5: add a pause after "Identity"
> make this video 1.05x faster

Pronunciation fixes go to the course dictionary (`course.yaml`) and apply to every video.

## 5. Screen takes

> let's record every scene in the deck
> the take on line 9 runs long, make it 1.5 s shorter
> when it says "the Save button", put a red box around it
> on take 4, an arrow pointing at the left menu
> blur the person's name on take 2

**Annotations you can ask for on a take:** a box around an element or a whole area, an arrow pointing at an
element from one side, a blur over an element or a single word, a spotlight that dims everything else, a short
text label, numbered steps, a zoom into one area, and the cursor's path (where it hovers, clicks or types).
Say when each appears and goes away.
None is added unless you ask.

## 6. Edit and publish

> rebuild the edit
> slide 4 goes by too fast, keep it 2 s longer
> it's ready to publish

The final video and its description land in `${publish}/`. Uploading, sending or posting is always confirmed
with you first.
