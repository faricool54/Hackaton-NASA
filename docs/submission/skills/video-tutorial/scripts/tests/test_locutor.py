import sys
import wave
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import locutor
from locutor import Speech, changed_rows, looks_truncated, spoken, track_timings

ROW = "x" * 183   # 183 characters read aloud in 12.7 s
SPEECH = Speech("v", "+5%", "+0Hz", {})


def write_wav(path, seconds):
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1), w.setsampwidth(2), w.setframerate(locutor.SAMPLE_RATE)
        w.writeframes(locutor.silence(seconds))


# ---- spoken -----------------------------------------------------------------------------

def test_spoken_respells_in_order_and_by_whole_word():
    pron = {"System prompt": "sístem prómpt", "prompt": "prómpt", "team": "tim"}
    assert spoken("El System prompt y el prompt del team, no teams.", pron) == \
        "El sístem prómpt y el prómpt del tim, no teams."


def test_spoken_is_case_sensitive():
    assert spoken("system prompt", {"System prompt": "x"}) == "system prompt"


# ---- truncation -------------------------------------------------------------------------

def test_a_normally_read_row_is_not_truncated():
    assert not looks_truncated(ROW, 12.74)


def test_a_clipped_row_is_truncated():
    assert looks_truncated(ROW, 0.36) and looks_truncated("Hola", 0.0)


@pytest.mark.parametrize("text, seconds", [("Veamos cómo.", 0.9), ("Sí.", 0.3), ("x" * 170, 10.0)])
def test_short_and_fast_phrases_pass(text, seconds):
    assert not looks_truncated(text, seconds)


@pytest.fixture
def fake_tts(monkeypatch, tmp_path):
    calls = {"synth": [], "lengths": []}
    monkeypatch.setattr(locutor, "synth", lambda text, speech, out: calls["synth"].append(speech))
    monkeypatch.setattr(locutor, "to_wav", lambda src, dst: None)
    monkeypatch.setattr(locutor, "seconds_of", lambda path: calls["lengths"].pop(0))
    return calls, tmp_path / "a.mp3", tmp_path / "a.wav"


def test_a_good_first_take_is_kept(fake_tts):
    calls, mp3, wav = fake_tts
    calls["lengths"] = [12.7]
    assert locutor.synth_wav(ROW, SPEECH, mp3, wav) == 12.7 and len(calls["synth"]) == 1


def test_a_truncated_take_is_requested_again(fake_tts, capsys):
    calls, mp3, wav = fake_tts
    calls["lengths"] = [0.36, 12.7]
    assert locutor.synth_wav(ROW, SPEECH, mp3, wav) == 12.7
    assert len(calls["synth"]) == 2 and calls["synth"][0].rate == "+5%"
    assert "truncated audio (0.36 s for 183 characters), attempt 1/3" in capsys.readouterr().out


def test_it_gives_up_after_the_last_attempt(fake_tts):
    calls, mp3, wav = fake_tts
    calls["lengths"] = [0.36] * locutor.SYNTH_ATTEMPTS
    with pytest.raises(SystemExit, match="truncated audio after 3 attempts"):
        locutor.synth_wav(ROW, SPEECH, mp3, wav)


# ---- rows and the track -----------------------------------------------------------------

def test_build_row_joins_parts_and_pauses(monkeypatch, tmp_path):
    seen = []

    def synth_wav(text, speech, mp3, wav):
        seen.append((text, speech.rate))
        write_wav(wav, 1.0)
        mp3.write_bytes(b"")
        return 1.0

    monkeypatch.setattr(locutor, "synth_wav", synth_wav)
    out = locutor.build_row(SimpleNamespace(num=3, parts=[("Uno.", 0.3), ("Dos.", 0.0)]), SPEECH, tmp_path)
    assert seen == [("Uno.", "+5%"), ("Dos.", "+5%")]
    assert locutor.seconds_of(out) == pytest.approx(2.3)
    assert sorted(p.name for p in tmp_path.iterdir()) == ["fila-03.wav"]


def test_human_rows_are_converted_from_their_recording(monkeypatch, tmp_path):
    (tmp_path / "humana").mkdir()
    (tmp_path / "humana" / "fila-02.m4a").write_bytes(b"x")
    converted = []
    monkeypatch.setattr(locutor, "to_wav", lambda src, dst: converted.append((src.name, dst.name)))
    locutor.build_row_human(SimpleNamespace(num=2), tmp_path)
    assert converted == [("fila-02.m4a", "fila-02.wav")]
    with pytest.raises(SystemExit, match="missing recording"):
        locutor.build_row_human(SimpleNamespace(num=5), tmp_path)


def _built(*durations):
    vis = SimpleNamespace(kind="demo", ref="D1", trim=None)
    return [(SimpleNamespace(num=i + 1, visual=vis), None, d) for i, d in enumerate(durations)]


def test_track_timings_place_cuts_in_the_pauses():
    timings, total = track_timings(_built(2.0, 3.0), {"lead_in": 0.2, "row_gap": 0.4, "tail": 0.6})
    assert [t["phrase_start"] for t in timings] == [0.2, 2.6]
    assert [t["visual_start"] for t in timings] == [0.0, 2.6]
    assert [t["visual_dur"] for t in timings] == [2.6, 3.6]
    assert total == pytest.approx(6.2)


def test_write_track_matches_the_timings(tmp_path):
    rows = []
    for i, d in enumerate([1.0, 2.0]):
        write_wav(tmp_path / f"r{i}.wav", d)
        rows.append((SimpleNamespace(num=i + 1), tmp_path / f"r{i}.wav", d))
    pacing = {"lead_in": 0.2, "row_gap": 0.4, "tail": 0.6}
    locutor.write_track(rows, pacing, tmp_path / "track.wav")
    assert locutor.seconds_of(tmp_path / "track.wav") == pytest.approx(4.2)


def test_changed_rows_reports_moves_and_new_rows():
    before = {"rows": [{"row": 1, "phrase_dur": 5.0}, {"row": 2, "phrase_dur": 3.0}]}
    after = {"rows": [{"row": 1, "phrase_dur": 5.005}, {"row": 2, "phrase_dur": 3.6}, {"row": 3, "phrase_dur": 1.0}]}
    assert changed_rows(before, after) == [(2, 0.6), (3, None)]
    assert changed_rows(None, {"rows": [{"row": 1, "phrase_dur": 1.0}]}) == [(1, None)]


def test_sync_writes_times_and_keeps_line_endings(tmp_path):
    path = tmp_path / "guion-v1.md"
    path.write_bytes("## Hoja de montaje\r\n| 1 | Hola | Slide 1 | | | |\r\n| 2 | Chau | D1 | | | |\r\n".encode())
    locutor.sync(path, [{"row": 1, "phrase_start": 0.2}, {"row": 2, "phrase_start": 3.0}], 5.5)
    text = path.read_bytes().decode()
    assert "| 0:00.2 | 0:03.0 | 2.8 s |\r\n" in text and "| 0:03.0 | 0:05.5 | 2.5 s |" in text


def test_main_needs_a_video():
    with pytest.raises(SystemExit, match="usage"):
        locutor.main([])


def test_silent_parts_write_silence_without_synthesis(monkeypatch, tmp_path):
    monkeypatch.setattr(locutor, "synth_wav", lambda *a: pytest.fail("synthesized a silent part"))
    out = locutor.build_row(SimpleNamespace(num=4, parts=[("", 2.0)]), SPEECH, tmp_path)
    assert locutor.seconds_of(out) == pytest.approx(2.0)
    silent = SimpleNamespace(num=6, parts=[("", 1.5)])
    assert locutor.seconds_of(locutor.build_row_human(silent, tmp_path)) == pytest.approx(1.5)


# ---- Kokoro -----------------------------------------------------------------------------

FAKE_KOKORO = """import json, sys, wave
jobs = json.load(open(sys.argv[sys.argv.index('--jobs') + 1], encoding='utf-8'))
for j in jobs:
    with wave.open(j['out'], 'wb') as w:
        w.setnchannels(1), w.setsampwidth(2), w.setframerate(24000)
        w.writeframes(b'\\x00' * (int(0.1 * len(j['text']) * 24000) * 2))
    print(j['voice'], j['speed'], j['text'])
"""


@pytest.fixture
def fake_kokoro(tmp_path, monkeypatch):
    """A stand-in for the Kokoro venv: a python that writes 0.1 s of silence per character."""
    stub = tmp_path / "kokoro_synth.py"
    stub.write_text(FAKE_KOKORO, encoding="utf-8")
    monkeypatch.setattr(locutor, "KOKORO_SYNTH", stub)
    return Speech("ef_dora", "+5%", "+0Hz", {"team": "tim"}, kokoro_python=sys.executable)


def test_engine_and_speed_come_from_the_voice_and_the_rate():
    assert Speech("ef_dora").engine == "kokoro" and Speech("es-MX-DaliaNeural").engine == "edge-tts"
    assert [locutor.rate_to_speed(r) for r in ("+0%", "+5%", "-10%", "")] == [1.0, 1.05, 0.9, 1.0]


def test_kokoro_renders_every_part_in_one_run_and_respells(fake_kokoro, tmp_path, monkeypatch):
    runs = []
    real_run = locutor.subprocess.run
    monkeypatch.setattr(locutor.subprocess, "run", lambda *a, **k: runs.append(a[0]) or real_run(*a, **k))
    rows = [SimpleNamespace(num=1, parts=[("Hola team.", 0.3), ("Dos.", 0.0)]),
            SimpleNamespace(num=2, parts=[("", 2.0)])]
    locutor.prerender_kokoro(rows, fake_kokoro, tmp_path)
    assert len(runs) == 1 and runs[0][0] == sys.executable
    assert sorted(p.name for p in tmp_path.glob("fila-*.wav")) == ["fila-01-0.wav", "fila-01-1.wav"]
    assert locutor.seconds_of(tmp_path / "fila-01-0.wav") == pytest.approx(0.9)   # "Hola tim." = 9 chars
    monkeypatch.setattr(locutor, "synth_wav", lambda *a: pytest.fail("re-synthesized a prerendered part"))
    out = locutor.build_row(rows[0], fake_kokoro, tmp_path)
    assert locutor.seconds_of(out) == pytest.approx(0.9 + 0.3 + 0.4)
    assert sorted(p.name for p in tmp_path.iterdir()) == ["fila-01.wav", "kokoro_synth.py"]


def test_kokoro_synth_wav_also_writes_the_mp3_callers_expect(fake_kokoro, tmp_path, monkeypatch):
    monkeypatch.setattr(locutor, "run", lambda cmd: Path(cmd[-1]).write_bytes(b"mp3"))   # no ffmpeg needed
    mp3, wav = tmp_path / "v1.mp3", tmp_path / "v1.wav"
    assert locutor.synth_wav("Hola.", fake_kokoro, mp3, wav) == pytest.approx(0.5)
    assert mp3.read_bytes() == b"mp3" and wav.exists()


def test_a_missing_kokoro_venv_is_a_clear_error(tmp_path):
    speech = Speech("ef_dora", kokoro_python=str(tmp_path / "nope" / "python"))
    with pytest.raises(SystemExit, match="kokoro_setup.py"):
        locutor.synth_kokoro([("Hola", tmp_path / "x.wav")], speech)


def test_edge_tts_never_reuses_a_stale_part_wav(monkeypatch, tmp_path):
    write_wav(tmp_path / "fila-03-0.wav", 5.0)   # left behind by a run that died

    def synth_wav(text, speech, mp3, wav):
        write_wav(wav, 1.0)
        mp3.write_bytes(b"")
        return 1.0

    monkeypatch.setattr(locutor, "synth_wav", synth_wav)
    out = locutor.build_row(SimpleNamespace(num=3, parts=[("Uno.", 0.0)]), SPEECH, tmp_path)
    assert locutor.seconds_of(out) == pytest.approx(1.0)
