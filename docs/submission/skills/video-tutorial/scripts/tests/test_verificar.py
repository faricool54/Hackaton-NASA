# The testing stage: verificar.py on the synthetic course, from a bare script to a montage.
import os
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import locutor
import montar
import verificar
from guion import Row, Visual


def levels(found):
    return [(f.level, f.message) for f in found]


def check(video, **kw):
    from course import Course
    return verificar.check(video, Course.load(video), **kw)


def slide_png(video, n=1):
    from PIL import Image
    folder = video / "assets" / "slides"
    folder.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (640, 360), "white").save(folder / f"slide-{n:02d}.png")


def take_mp4(video, ref, seconds):
    folder = video / "grabaciones"
    folder.mkdir(exist_ok=True)
    subprocess.run([montar.ffmpeg_exe(), "-y", "-f", "lavfi", "-i", f"color=c=black:s=640x360:r=30:d={seconds}",
                    "-pix_fmt", "yuv420p", str(folder / f"{ref}.mp4")], capture_output=True, check=True)


def age(path, seconds):
    t = path.stat().st_mtime - seconds
    os.utime(path, (t, t))


def test_parse_probe_reads_duration_size_and_fps():
    banner = ("  Duration: 00:01:02.50, start: 0.000000, bitrate: 900 kb/s\n"
              "  Stream #0:0[0x1](und): Video: h264 (High) (avc1 / 0x31637661), yuv420p(progressive), "
              "1920x1080 [SAR 1:1 DAR 16:9], 850 kb/s, 30 fps, 30 tbr, 15360 tbn (default)\n")
    assert verificar.parse_probe(banner) == {"duration": 62.5, "width": 1920, "height": 1080, "fps": 30.0}
    assert verificar.parse_probe("garbage")["duration"] is None


def test_long_stills_joins_consecutive_rows_of_the_same_slide():
    def row(n, kind, ref):
        return Row(n, "x", [("x", 0.0)], Visual(kind, ref))
    rows = [row(1, "slide", "1"), row(2, "slide", "1"), row(3, "demo", "D1"), row(4, "slide", "2"),
            row(5, "slide", "3")]
    trows = [{"visual_dur": d} for d in (8, 6, 20, 14, 4)]
    assert verificar.long_stills(rows, trows) == [(1, 2, "1", 14.0), (4, 4, "2", 14.0)]


def test_a_missing_script_is_the_only_error(tmp_path):
    (tmp_path / "course.yaml").write_text("language: es\n", encoding="utf-8")
    video = tmp_path / "internal" / "01 - Intro"
    video.mkdir(parents=True)
    found = check(video)
    assert len(found) == 1 and found[0].level == "error" and "script" in found[0].message


def test_before_the_narration_it_lists_missing_assets(course):
    video, _ = course
    found = levels(check(video))
    assert ("error", "row 1: slide-01.png missing (run slides.py)") in found
    assert ("error", "row 2: take D1 not recorded") in found
    assert ("error", "narration: timings.json missing (run locutor.py)") in found


def test_a_draft_with_placeholders_passes_after_the_montage(course, capsys):
    video, _ = course
    locutor.main([str(video)])
    slide_png(video)
    found = levels(check(video, placeholder=True))
    assert ("warning", "row 2: take D1 not recorded") in found
    assert any("not built yet" in m for _, m in found)
    montar.main([str(video), "--placeholder"])
    assert levels(check(video, placeholder=True)) == [("warning", "row 2: take D1 not recorded")]
    verificar.main([str(video), "--placeholder"])
    assert "OK  01 - Intro: 0 errors, 1 warnings" in capsys.readouterr().out


def test_it_fails_when_the_narration_is_out_of_date(course, capsys):
    video, _ = course
    locutor.main([str(video)])
    script = video / "guion-v1.md"
    script.write_text(script.read_text(encoding="utf-8").replace("'+5%'", "'+10%'"), encoding="utf-8")
    found = levels(check(video, placeholder=True))
    assert ("error", "narration: generated at +5%, the script asks for +10%; generate it again") in found
    age(video / "locucion" / "timings.json", 60)
    assert any("edited after locutor.py ran" in m for _, m in levels(check(video, placeholder=True)))
    script.write_text(script.read_text(encoding="utf-8").replace("| 2 |", "| 3 |"), encoding="utf-8")
    assert any("rows changed" in m for _, m in levels(check(video, placeholder=True)))
    with pytest.raises(SystemExit):
        verificar.main([str(video)])
    assert "FAILED" in capsys.readouterr().out


def test_it_flags_long_stills_short_takes_and_a_stale_montage(course):
    video, _ = course
    script = video / "guion-v1.md"
    long_line = "Una frase larga que se queda demasiado tiempo en pantalla " * 5
    script.write_text(script.read_text(encoding="utf-8")
                      .replace("Hola, este es el curso.", long_line)
                      .replace("🎬 D1 |", "🎬 D1 [0:00–0:05] |"), encoding="utf-8")
    locutor.main([str(video)])
    slide_png(video)
    take_mp4(video, "D1", 0.5)
    montar.main([str(video)])
    found = levels(check(video))
    assert any(m.startswith("row 1: slide 1 stays") for _, m in found)
    assert any(m.startswith("row 2: trim of D1 lasts 5.0 s") for _, m in found)
    assert any(m.startswith("row 2: take D1 is 0.5 s") for _, m in found)
    assert not [f for f in found if f[0] == "error"]
    age(video.parent.parent / "export" / "01 - Intro" / "01 - Intro.mp4", 60)
    assert any("older than" in m for _, m in levels(check(video)))


def test_it_fails_a_montage_that_does_not_match_the_course(course, tmp_path):
    video, _ = course
    locutor.main([str(video)])
    slide_png(video)
    out = tmp_path / "wrong.mp4"
    subprocess.run([montar.ffmpeg_exe(), "-y", "-f", "lavfi", "-i", "color=c=black:s=320x180:r=25:d=1",
                    "-pix_fmt", "yuv420p", str(out)], capture_output=True, check=True)
    messages = [m for lvl, m in levels(check(video, placeholder=True, out=out)) if lvl == "error"]
    assert any("lasts" in m for m in messages)
    assert "montage: 320x180, the course is 640x360" in messages
    assert "montage: 25.0 fps, the course is 30" in messages


def test_main_requires_a_video():
    with pytest.raises(SystemExit, match="usage"):
        verificar.main([])
