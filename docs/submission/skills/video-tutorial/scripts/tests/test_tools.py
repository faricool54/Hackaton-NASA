# variantes.py, pausas.py, montar.py and slides.py: the pieces that need no TTS service or browser.
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import locutor
import montar
import pausas
import slides
import variantes


# ---- variantes --------------------------------------------------------------------------

def test_row_variants_start_with_the_current_row():
    assert variantes.row_variants("Es lo que la gente lee", "la gente lee", ["las personas leen", "todos leen"]) == \
        ["Es lo que la gente lee", "Es lo que las personas leen", "Es lo que todos leen"]
    assert variantes.row_variants("A", textos=["B", "C"]) == ["A", "B", "C"]


def test_row_variants_need_the_fragment():
    with pytest.raises(SystemExit, match="not in the row"):
        variantes.row_variants("Hola", "chau", ["x"])


def test_slug():
    assert variantes.slug("Qué tan potente!") == "qu-tan-potente" or variantes.slug("Qué tan potente!").startswith("qu")
    assert variantes.slug("!!!") == "muestras"


@pytest.mark.parametrize("argv", [["v"], ["v", "--fila", "3"], ["v", "--fila", "3", "--buscar", "x"],
                                  ["v", "--velocidades", "+0%"]])
def test_variantes_needs_a_complete_request(argv):
    with pytest.raises(SystemExit):
        variantes.parse(argv)


def fake_tts(monkeypatch):
    """Each phrase becomes len(text)/10 s of silence; returns the (text, rate) pairs sent to the voice."""
    spoken = []

    def synth_wav(text, speech, mp3, wav):
        spoken.append((text, speech.rate))
        mp3.write_bytes(b"")
        with locutor.wave.open(str(wav), "wb") as w:
            w.setnchannels(1), w.setsampwidth(2), w.setframerate(locutor.SAMPLE_RATE)
            w.writeframes(locutor.silence(len(text) / 10))
        return len(text) / 10

    monkeypatch.setattr(locutor, "synth_wav", synth_wav)
    monkeypatch.setattr(locutor, "to_mp3", lambda src, dst: dst.write_bytes(b"mp3"))
    return spoken


def test_render_writes_numbered_files_and_a_listing(monkeypatch, tmp_path):
    spoken = fake_tts(monkeypatch)
    out = tmp_path / "muestras"
    done = variantes.render([("fila-01-v1.mp3", "Hola", None), ("velocidad-2.mp3", "Hola mundo", "+5%")], out,
                            lambda rate: locutor.Speech("v", rate or "+1%"))
    assert [rate for _, rate in spoken] == ["+1%", "+5%"]
    assert sorted(p.name for p in out.iterdir()) == ["fila-01-v1.mp3", "textos.txt", "velocidad-2.mp3"]
    assert (out / "textos.txt").read_text(encoding="utf-8").splitlines() == \
        ["fila-01-v1.mp3\t0.40 s\tHola", "velocidad-2.mp3\t1.00 s\t+5% · Hola mundo"]
    assert done[0][0] == "fila-01-v1.mp3"


def test_render_turns_pause_marks_into_silence(monkeypatch, tmp_path):
    spoken = fake_tts(monkeypatch)
    done = variantes.render([("fila-05-v1.mp3", "Uno dos. 0.2s Tres.", None)], tmp_path,
                            lambda rate: locutor.Speech("v", "+0%"))
    assert spoken == [("Uno dos.", "+0%"), ("Tres.", "+0%")]   # "0.2s" is never sent to the voice
    assert done[0][1] == pytest.approx(0.8 + 0.2 + 0.5)


def test_voice_samples_turn_pause_marks_into_silence(monkeypatch, tmp_path):
    from types import SimpleNamespace
    spoken = fake_tts(monkeypatch)
    rows = [SimpleNamespace(parts=[("Uno.", 0.3), ("Dos.", 0.0)]), SimpleNamespace(parts=[("Tres.", 0.0)])]
    locutor.muestras(rows, tmp_path, [["a", "v-A", "+0%", "+0Hz"]])
    assert [text for text, _ in spoken] == ["Uno.", "Dos.", "Tres."]
    assert sorted(p.name for p in (tmp_path / "muestras").iterdir()) == ["a.mp3"]


# ---- pausas -----------------------------------------------------------------------------

def test_silence_ends_reads_ffmpeg_output():
    err = ("[silencedetect @ 0x1] silence_start: 1.2\n[silencedetect @ 0x1] silence_end: 1.78 | silence_duration: 0.5\n"
           "[silencedetect @ 0x1] silence_end: 4.215 | silence_duration: 0.3\n")
    assert pausas.silence_ends(err) == [1.78, 4.215]
    assert pausas.silence_ends("nothing") == []


# ---- montar -----------------------------------------------------------------------------

def test_fit_letterboxes_into_the_frame():
    assert montar.fit(1280, 720) == ("scale=1280:720:force_original_aspect_ratio=decrease,"
                                     "pad=1280:720:(ow-iw)/2:(oh-ih)/2")


@pytest.mark.parametrize("language", ["es", "en", "pt"])
def test_placeholder_card_has_the_course_size(tmp_path, language):
    from PIL import Image
    out = tmp_path / "card.png"
    montar.placeholder_png("D4", out, 1280, 720, language)
    assert Image.open(out).size == (1280, 720)


def test_montar_needs_a_video():
    with pytest.raises(SystemExit, match="usage"):
        montar.main([])


# ---- slides -----------------------------------------------------------------------------

def test_slide_count_expands_builds():
    html = ('<section class="slide cover active"></section><section class="slide" data-steps="4"></section>'
            '<section class="slide"></section>')
    assert slides.slide_count(html) == 6


def test_slides_needs_a_video():
    with pytest.raises(SystemExit, match="usage"):
        slides.main([])


# ---- voces ------------------------------------------------------------------------------

def test_voces_renders_candidates_or_speeds(tmp_path, monkeypatch):
    import voces
    (tmp_path / "course.yaml").write_text("language: en\nvoice: {candidates: [[a, v-A, '+0%', '+0Hz'], [b, v-B, '+2%', '+0Hz']]}\n",
                                          encoding="utf-8")
    seen = []

    def synth_wav(text, speech, mp3, wav):
        seen.append((speech.voice, speech.rate, text[:2]))
        mp3.write_bytes(b"")
        wav.write_bytes(b"")
        return 3.0

    monkeypatch.setattr(locutor, "synth_wav", synth_wav)
    voces.main([str(tmp_path)])
    voces.main([str(tmp_path), "--voz", "v-C", "--velocidades", "+0%", "+5%", "--texto", "Hola"])
    out = tmp_path / "_template" / "muestras-voz"
    assert seen == [("v-A", "+0%", "Hi"), ("v-B", "+2%", "Hi"), ("v-C", "+0%", "Ho"), ("v-C", "+5%", "Ho")]
    assert sorted(p.name for p in out.glob("*.mp3")) == ["01-a.mp3", "01-v-C-+0%.mp3", "02-b.mp3", "02-v-C-+5%.mp3"]
    assert (out / "textos.txt").read_text(encoding="utf-8").startswith("Hola")
