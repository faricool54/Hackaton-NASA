# Takes and captures of this video, recorded by the skill's grabar.py (see the script's Tomas section).
# Setup before t.start() runs off camera. Pace on-camera actions to the narration with t.at(seconds),
# using the phrase starts that pausas.py prints for the row the take plays under.
#
#   python grabar.py "<video>"                      # every take
#   python grabar.py "<video>" --tomas D1          # one take
#   python grabar.py "<video>" --capturas          # captures only, at 2x
#
# Toma helpers: goto, start(ready=), settle, at, wait, move_to, click, hover, type_slow, type_words,
# scroll, blur_words, and the on-camera annotations highlight, highlight_zone, arrow, spotlight, label,
# steps, zoom_to / zoom_out, unhighlight.
# Anything that writes to the product goes in setup, never on camera, and must be safe to repeat.


async def d1(t):
    await t.goto("/")                    # off camera
    await t.start(ready="main")          # recording starts once the page settles
    await t.at(1.0)                      # 1.0 s into the row: when the voice names the thing
    await t.hover("main h1", hold_s=1.5)


TOMAS = {"D1": d1}


async def background(t):
    """Cover backdrop: a calm screen of the product."""
    await t.goto("/")


CAPTURAS = {"background": background}
