# The command-line entry points end to end, on a tiny synthetic course: real ffmpeg, a fake
# TTS (a tone per phrase, so no network), and headless Chrome for the slides when available.
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import locutor
import montar
import pausas
import slides
import variantes


def test_locutor_builds_the_track_syncs_the_script_and_reports_changes(course, capsys):
    video, spoken = course
    locutor.main([str(video), "--sync"])
    assert spoken[0] == ("Hola, este es el cúrso.", "+5%")   # course respellings, video rate
    timings = json.loads((video / "locucion" / "timings.json").read_text(encoding="utf-8"))
    assert [r["row"] for r in timings["rows"]] == [1, 2] and timings["rate"] == "+5%"
    assert "| 0:00.2 |" in (video / "guion-v1.md").read_text(encoding="utf-8")
    locutor.main([str(video)])
    assert "changed rows: none" in capsys.readouterr().out
    assert (video / "locucion" / "timings.prev.json").exists()


def test_montar_cuts_slides_and_placeholders_to_the_measured_audio(course):
    from PIL import Image
    video, _ = course
    locutor.main([str(video)])
    (video / "assets" / "slides").mkdir(parents=True)
    Image.new("RGB", (1920, 1080), "white").save(video / "assets" / "slides" / "slide-01.png")
    with pytest.raises(SystemExit, match="missing take"):
        montar.main([str(video)])
    montar.main([str(video), "--placeholder"])
    out = video.parent.parent / "export" / "01 - Intro" / "01 - Intro.mp4"
    import subprocess
    info = subprocess.run([montar.ffmpeg_exe(), "-i", str(out)], capture_output=True).stderr.decode()
    assert "640x360" in info and "30 fps" in info


def test_montar_refuses_a_script_that_changed_since_the_narration(course):
    video, _ = course
    locutor.main([str(video)])
    script = video / "guion-v1.md"
    script.write_text(script.read_text(encoding="utf-8").replace("| 2 |", "| 3 |"), encoding="utf-8")
    with pytest.raises(SystemExit, match="changed since"):
        montar.main([str(video), "--placeholder"])


def test_pausas_finds_the_marked_pause(course, capsys):
    video, _ = course
    locutor.main([str(video)])
    pausas.main([str(video), "--filas", "1"])
    out = capsys.readouterr().out
    first = float(out.split("]: ")[1].split()[0])
    assert first == pytest.approx(0.05 * len("Hola, este es el curso.") + 0.4, abs=0.05)


def test_variantes_renders_numbered_options(course, capsys):
    video, spoken = course
    variantes.main([str(video), "--fila", "2", "--buscar", "la toma", "--opciones", "una toma", "--nombre", "t"])
    folder = video / "locucion" / "muestras" / "t"
    assert sorted(p.name for p in folder.iterdir()) == ["fila-02-v1.mp3", "fila-02-v2.mp3", "textos.txt"]
    variantes.main([str(video), "--filas", "1,2", "--velocidades", "+0%", "+10%"])
    assert [rate for _, rate in spoken[-4:]] == ["+0%", "+0%", "+10%", "+10%"]   # two phrases around the 0.4s pause
    assert not any("0.4s" in text for text, _ in spoken)


def test_slides_exports_one_png_per_slide(course):
    if slides.find_browser() is None:
        pytest.skip("no Chrome or Edge")
    from PIL import Image
    video, _ = course
    stale = video / "assets" / "slides" / "slide-09.png"
    stale.parent.mkdir(parents=True)
    stale.write_bytes(b"old")
    slides.main([str(video)])
    pngs = sorted(p.name for p in (video / "assets" / "slides").iterdir())
    assert pngs == ["slide-01.png"] and Image.open(video / "assets" / "slides" / "slide-01.png").size == (640, 360)
