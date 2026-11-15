import re
import sys
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import scaffold
from course import Course

ANSWERS = {
    "name": "Curso Demo", "language": "es", "audience": "todo el equipo", "depth": "principiante",
    "target_duration": "1-3 min", "voice": {"rate": "+5%", "pronunciation": {}},
    "recording": {"enabled": True, "base_url": "https://app.example.com"},
    "deck": {"enabled": True, "design_system": "rappi"},
    "sources": {"platform": "Demo Platform", "docs": ["https://docs.example.com"]},
}


@pytest.fixture
def course_dir(tmp_path):
    answers = tmp_path / "answers.yaml"
    answers.write_text(yaml.safe_dump(ANSWERS, allow_unicode=True), encoding="utf-8")
    course = tmp_path / "curso"
    scaffold.init(course, answers)
    return course


def test_init_writes_the_course(course_dir):
    c = Course.load(course_dir)
    assert c["name"] == "Curso Demo" and c.voice["rate"] == "+5%" and c.voice["name"] == "es-MX-DaliaNeural"
    assert (course_dir / "internal").is_dir() and (course_dir / "export").is_dir()
    claude = (course_dir / "CLAUDE.md").read_text(encoding="utf-8")
    assert "# CLAUDE.md — Curso Demo" in claude and "It covers **Demo Platform**." in claude
    assert "${" not in claude and "https://app.example.com" in claude
    readme = (course_dir / "README.md").read_text(encoding="utf-8")
    assert readme.startswith("# Curso Demo") and "recuadro" in readme


def test_init_applies_the_design_system_and_copies_its_fonts(course_dir):
    html = (course_dir / "_template" / "presentacion.html").read_text(encoding="utf-8")
    assert "--primary: #ff441f;" in html and "font-family: 'PP Object Sans'; font-weight: 800" in html
    assert sorted(p.name for p in (course_dir / "_template" / "assets" / "fonts").iterdir()) == [
        "PPObjectSans-Bold.woff2", "PPObjectSans-Heavy.woff2", "PPObjectSans-Medium.woff2", "PPObjectSans-Regular.woff2"]
    assert "data-guia" in html   # the template keeps its example slides


def test_init_refuses_to_overwrite(course_dir, tmp_path):
    with pytest.raises(SystemExit, match="already exists"):
        scaffold.init(course_dir, tmp_path / "answers.yaml")


def test_init_keeps_an_existing_claude_md(tmp_path):
    answers = tmp_path / "a.yaml"
    answers.write_text("name: X\nlanguage: en\n", encoding="utf-8")
    course = tmp_path / "c"
    course.mkdir()
    (course / "CLAUDE.md").write_text("mine", encoding="utf-8")
    scaffold.init(course, answers)
    assert (course / "CLAUDE.md").read_text(encoding="utf-8") == "mine"
    assert (course / "CLAUDE.video-tutorial.md").exists()
    assert "Montage sheet" not in (course / "README.md").read_text(encoding="utf-8")   # the English guide
    assert (course / "README.md").read_text(encoding="utf-8").startswith("# X")


def test_new_video_starts_clean(course_dir):
    scaffold.new_video(course_dir, "01 - Intro")
    video = course_dir / "internal" / "01 - Intro"
    deck = (video / "presentacion.html").read_text(encoding="utf-8")
    assert not re.search(r"<section[^>]*data-guia", deck) and "Example layouts" not in deck
    assert "<title>Video 01 · Intro</title>" in deck
    assert deck.count('<section class="slide') == 1 and "--primary: #ff441f;" in deck
    assert (video / "assets" / "fonts" / "PPObjectSans-Bold.woff2").exists()
    script = (video / "guion-v1.md").read_text(encoding="utf-8")
    assert "vigente: true" in script and "Video 01 · Intro" in script and "## Hoja de montaje" in script
    assert (video / "tomas.py").exists() and (course_dir / "export" / "01 - Intro").is_dir()
    for sub in ("grabaciones", "locucion", "assets/slides", "assets/capturas"):
        assert (video / sub).is_dir()


@pytest.mark.parametrize("name", ["Intro", "1-Intro", "01 Intro", "01 - "])
def test_new_video_needs_a_proper_name(course_dir, name):
    with pytest.raises(SystemExit, match="NN - Title"):
        scaffold.new_video(course_dir, name)


def test_new_video_accepts_prefixed_numbers_and_refuses_duplicates(course_dir):
    scaffold.new_video(course_dir, "TS-01 - VPN")
    with pytest.raises(SystemExit, match="already exists"):
        scaffold.new_video(course_dir, "TS-01 - VPN")


def test_custom_design_system_and_redo(course_dir, tmp_path):
    font = tmp_path / "Brand.woff2"
    font.write_bytes(b"woff2")
    data = yaml.safe_load((course_dir / "course.yaml").read_text(encoding="utf-8"))
    data["deck"] = {"enabled": True, "design_system": "custom", "tokens": {"primary": "#0a7cff"},
                    "font": {"family": "'Brand', sans-serif", "name": "Brand", "files": {400: font.as_posix()}}}
    (course_dir / "course.yaml").write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    scaffold.redo_deck(course_dir)
    html = (course_dir / "_template" / "presentacion.html").read_text(encoding="utf-8")
    assert "--primary: #0a7cff;" in html and "--primary-container: #eef2ff;" in html   # the rest from neutral
    assert "src: url('assets/fonts/Brand.woff2')" in html
    assert (course_dir / "_template" / "assets" / "fonts" / "Brand.woff2").exists()


def test_unknown_design_system_and_missing_font(tmp_path):
    with pytest.raises(SystemExit, match="unknown design system"):
        scaffold.load_preset({"design_system": "nope"})
    preset, base = scaffold.load_preset({"design_system": "custom", "font": {"files": {400: str(tmp_path / "x.woff2")}}})
    with pytest.raises(SystemExit, match="font file not found"):
        scaffold.copy_fonts(preset, base, tmp_path / "out")


def test_neutral_has_no_font_files(tmp_path):
    preset, _ = scaffold.load_preset({"design_system": "neutral"})
    assert scaffold.render_fonts(preset) == "/* @fonts:start */\n/* @fonts:end */"


def test_main_dispatches(tmp_path, capsys):
    answers = tmp_path / "a.yaml"
    answers.write_text("name: Y\ndeck: {enabled: false}\n", encoding="utf-8")
    scaffold.main(["init", str(tmp_path / "c"), "--answers", str(answers)])
    scaffold.main(["video", str(tmp_path / "c"), "01 - A"])
    assert not (tmp_path / "c" / "_template").exists()
    assert not (tmp_path / "c" / "internal" / "01 - A" / "presentacion.html").exists()
    assert "video ready" in capsys.readouterr().out
