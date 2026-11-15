# A tiny synthetic course shared by the end-to-end tests: one video with a slide row and a
# take row, and a fake TTS (a tone per phrase, so no network).
import math
import struct
import sys
import wave
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import locutor

SCRIPT = """---
vigente: true
velocidad: '+5%'
---
## Hoja de montaje

| # | Locución | Imagen | Entra | Sale | Dur. |
|---|---|---|---|---|---|
| 1 | Hola, este es el curso. 0.4s Empezamos. | 🖼️ Slide 1 | | | |
| 2 | Y esta es la toma. | 🎬 D1 | | | |
"""

DECK = """<!doctype html><html><head><style>
body{margin:0;background:#fff}.slide{display:none;width:100vw;height:100vh}.slide.active{display:block}
</style></head><body><section class="slide active"><h1>Uno</h1></section>
<script>const s=[...document.querySelectorAll('.slide')];
const n=(parseInt(location.hash.slice(1),10)||1)-1;s.forEach((x,k)=>x.classList.toggle('active',k===n));</script>
</body></html>"""


def tone_wav(path, seconds, rate=locutor.SAMPLE_RATE):
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1), w.setsampwidth(2), w.setframerate(rate)
        w.writeframes(b"".join(struct.pack("<h", int(8000 * math.sin(i / 8))) for i in range(int(seconds * rate))))


@pytest.fixture
def course(tmp_path, monkeypatch):
    (tmp_path / "course.yaml").write_text(
        "language: es\nvideo: {width: 640, height: 360, fps: 30}\nvoice: {pronunciation: {curso: cúrso}}\n",
        encoding="utf-8")
    video = tmp_path / "internal" / "01 - Intro"
    video.mkdir(parents=True)
    (video / "guion-v1.md").write_text(SCRIPT, encoding="utf-8")
    (video / "presentacion.html").write_text(DECK, encoding="utf-8")
    spoken = []

    def fake_synth_wav(text, speech, mp3, wav):
        spoken.append((locutor.spoken(text, speech.pronunciation), speech.rate))
        tone_wav(wav, 0.05 * len(text))
        mp3.write_bytes(b"")
        return locutor.seconds_of(wav)

    monkeypatch.setattr(locutor, "synth_wav", fake_synth_wav)
    return video, spoken
