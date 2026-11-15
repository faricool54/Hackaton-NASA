import asyncio
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import grabar
from course import Course
from grabar import Guard, Rec, frame_durations, init_script, is_allowed, parse_args, target_duration

APP = "https://app.example.com"


# ---- frame_durations --------------------------------------------------------------------

def test_irregular_timestamps():
    d = frame_durations([10.0, 10.1, 10.5, 12.0], end=13.0)
    assert d == pytest.approx([0.1, 0.4, 1.5, 1.0])


def test_single_frame_lasts_until_end():
    assert frame_durations([5.0], end=7.5) == pytest.approx([2.5])


@pytest.mark.parametrize("fps", [30, 60])
def test_last_frame_never_shorter_than_one_video_frame(fps):
    assert frame_durations([5.0], end=5.0, fps=fps) == pytest.approx([1 / fps])


def test_hold_extends_last_frame_to_min_total():
    d = frame_durations([0.0, 1.0], end=2.0, min_total=5.5)
    assert d == pytest.approx([1.0, 4.5])


def test_hold_does_not_shorten_a_longer_take():
    assert sum(frame_durations([0.0, 1.0], end=8.0, min_total=3.0)) == pytest.approx(8.0)


def test_out_of_order_timestamps_never_go_negative():
    d = frame_durations([1.0, 0.9, 1.2], end=1.5)
    assert all(x >= 0 for x in d) and sum(d) == pytest.approx(0.5)


def test_no_frames_is_an_error():
    with pytest.raises(ValueError):
        frame_durations([], end=1.0)


# ---- target_duration --------------------------------------------------------------------

def _row(ref, dur, kind="demo", trim=None):
    return {"visual": {"kind": kind, "ref": ref, "trim": trim}, "visual_dur": dur}


TIMINGS = {"rows": [_row("1", 5.0, kind="slide"), _row("D1", 7.25), _row("D2", 4.0, trim=[3.0, 7.0]), _row("D2", 6.0)]}


def test_present_ref():
    assert target_duration(TIMINGS, "D1") == pytest.approx(7.75)


def test_ref_in_several_rows_takes_the_furthest_point():
    assert target_duration(TIMINGS, "D2") == pytest.approx(7.5)


def test_custom_margin_and_missing_ref():
    assert target_duration(TIMINGS, "D1", margin=0) == pytest.approx(7.25)
    assert target_duration(TIMINGS, "D9") is None


@pytest.mark.parametrize("timings", [None, {}, {"rows": []}])
def test_no_timings(timings):
    assert target_duration(timings, "D1") is None


# ---- parse_args -------------------------------------------------------------------------

def test_login_takes_the_course_or_a_video():
    a = parse_args(["courses/devex", "--login"])
    assert a.login and a.video == "courses/devex"


def test_video_defaults():
    a = parse_args(["internal/03 - Intro"])
    assert a.video == "internal/03 - Intro" and a.tomas is None and not a.capturas and not a.headed


def test_video_with_options():
    a = parse_args(["internal/03", "--tomas", "D1, D3,", "--capturas", "--headed"])
    assert a.tomas == ["D1", "D3"] and a.capturas and a.headed


@pytest.mark.parametrize("argv", [
    [], ["--login"], ["internal/03", "internal/04"], ["internal/03", "--tomas"],
    ["internal/03", "--tomas", "--capturas"], ["internal/03", "--unknown"], ["--capturas"],
    ["internal/03", "--login", "--tomas", "D1"],
])
def test_bad_args(argv):
    with pytest.raises(SystemExit):
        parse_args(argv)


# ---- init script ------------------------------------------------------------------------

def test_init_script_carries_blur_selectors_and_storage_values():
    js = init_script(['.name', 'aside[data-x="y"]'], {"theme": "light", "season": "off"})
    for sel in ['.name', 'aside[data-x="y"]']:
        assert json.dumps(sel)[1:-1] in js
    assert '"theme": "light"' in js and '"season": "off"' in js
    assert "pointer-events:none" in js and "filter:blur(6px)" in js


def test_init_script_without_selectors_blurs_nothing():
    js = init_script()
    assert "filter:blur" not in js and "{}" in js


# ---- write guard ------------------------------------------------------------------------

@pytest.mark.parametrize("method", ["GET", "HEAD", "get"])
def test_reads_always_pass(method):
    assert is_allowed(method, f"{APP}/api/anything", [])


@pytest.mark.parametrize("method, url, allow, ok", [
    ("POST", f"{APP}/api/search", ["POST /api/search"], True),
    ("POST", f"{APP}/api/search/", ["POST /api/search"], True),
    ("POST", f"{APP}/api/search?q=1", ["POST /api/search"], True),
    ("POST", f"{APP}/api/search/deep", ["POST /api/search*"], True),
    ("post", f"{APP}/api/search", ["POST /api/search"], True),
    ("POST", f"{APP}/api/agents", ["POST /api/search*"], False),
    ("PUT", f"{APP}/api/search", ["POST /api/search"], False),
    ("DELETE", f"{APP}/api/x", [], False),
])
def test_writes_need_an_allow_entry(method, url, allow, ok):
    assert is_allowed(method, url, allow) is ok


class FakeRoute:
    def __init__(self, method, url):
        self.request = SimpleNamespace(method=method, url=url, post_data=None)
        self.outcome = None

    async def continue_(self):
        self.outcome = "continued"

    async def abort(self, reason):
        self.outcome = reason


def test_guard_blocks_app_writes_and_ignores_other_hosts():
    guard = Guard(APP, ["POST /api/ok"])
    routes = [FakeRoute("GET", f"{APP}/api/x"), FakeRoute("POST", f"{APP}/api/ok"),
              FakeRoute("POST", f"{APP}/api/agents"), FakeRoute("POST", "https://analytics.example.org/e")]
    for r in routes:
        asyncio.run(guard.handle(r))
    assert [r.outcome for r in routes] == ["continued", "continued", "blockedbyclient", "continued"]
    assert guard.blocked == [f"POST {APP}/api/agents"]


# ---- Rec from course.yaml ---------------------------------------------------------------

def _course(tmp_path, recording):
    (tmp_path / "course.yaml").write_text(json.dumps({"video": {"width": 1280, "height": 720}, "recording": recording}),
                                          encoding="utf-8")
    return Course.load(tmp_path)


def test_rec_from_course(tmp_path, monkeypatch):
    monkeypatch.setattr(grabar, "profile_root", lambda: tmp_path / "profiles")
    rec = Rec.from_course(_course(tmp_path, {"base_url": APP + "/", "blur_selectors": [".x"],
                                             "write_guard": {"enabled": True, "allow": ["POST /a"]}}))
    assert rec.base_url == APP and rec.width == 1280 and rec.height == 720
    assert rec.profile_dir == tmp_path / "profiles" / tmp_path.name
    assert rec.blur_selectors == [".x"] and rec.guard and rec.allow == ["POST /a"]
    assert rec.sso_hosts == ["okta"] and rec.color_scheme == "light"


def test_rec_needs_a_base_url(tmp_path):
    with pytest.raises(SystemExit, match="base_url"):
        Rec.from_course(_course(tmp_path, {}))


def test_profiles_live_outside_the_course(monkeypatch, tmp_path):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    assert grabar.profile_root() == tmp_path / "video-tutorial"


# ---- login ------------------------------------------------------------------------------

@pytest.mark.parametrize("url, ok", [
    (f"{APP}/home", True), (f"{APP}/", True), ("https://acme.okta.com/login", False),
    ("about:blank", False), ("https://other.example.com/", False),
    (f"{APP}/api/auth/signin?callbackUrl=%2F", False),   # the app's own Auth.js sign-in page
])
def test_on_app_tells_the_app_from_sign_in_pages(url, ok, tmp_path):
    rec = Rec(base_url=APP, profile_dir=tmp_path)
    assert grabar.on_app(url, rec) is ok
