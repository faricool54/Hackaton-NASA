import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from course import Course, find_root


def make_course(tmp_path, text="name: Demo\n"):
    (tmp_path / "course.yaml").write_text(text, encoding="utf-8")
    video = tmp_path / "internal" / "01 - Intro"
    video.mkdir(parents=True)
    return video


def test_root_is_found_from_a_nested_folder(tmp_path):
    video = make_course(tmp_path)
    (video / "locucion").mkdir()
    assert find_root(video / "locucion") == tmp_path


def test_no_course_yaml_explains_the_wizard(tmp_path):
    with pytest.raises(SystemExit, match="setup wizard"):
        find_root(tmp_path)


def test_defaults_fill_what_the_course_leaves_out(tmp_path):
    make_course(tmp_path, "video: {width: 1280}\nvoice: {rate: '+5%', pronunciation: {team: tim}}\n")
    c = Course.load(tmp_path)
    assert (c.width, c.height, c.fps) == (1280, 1080, 30)
    assert c.voice["rate"] == "+5%" and c.voice["name"] == "es-MX-DaliaNeural"
    assert c.voice["pronunciation"] == {"team": "tim"} and c.voice["pacing"]["row_gap"] == 0.4
    assert c["deck"]["enabled"] and c.recording["write_guard"] == {"enabled": False, "allow": []}


def test_an_empty_course_yaml_is_all_defaults(tmp_path):
    make_course(tmp_path, "")
    assert Course.load(tmp_path).fps == 30


def test_folders_and_profile(tmp_path):
    make_course(tmp_path, "folders: {publish: publicado}\nrecording: {profile: mi-perfil}\n")
    c = Course.load(tmp_path)
    assert c.production_dir == tmp_path / "internal" and c.publish_dir == tmp_path / "publicado"
    assert c.profile_name == "mi-perfil"
    (tmp_path / "otro").mkdir()
    make_course(tmp_path / "otro")
    assert Course.load(tmp_path / "otro").profile_name == "otro"


def test_resolve_video_by_path_name_or_production_name(tmp_path, monkeypatch):
    video = make_course(tmp_path)
    c = Course.load(tmp_path)
    assert c.resolve_video(str(video)) == video.resolve()
    assert c.resolve_video("internal/01 - Intro") == video.resolve()
    assert c.resolve_video("01 - Intro") == video.resolve()
    with pytest.raises(SystemExit, match="not found"):
        c.resolve_video("99 - Nada")
