# Runtime pieces without production: the encoder with real
# ffmpeg, and one end-to-end take against a local page in headless Chrome.

import asyncio
import functools
import http.server
import json
import subprocess
import sys
import threading
import urllib.error
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import grabar


def test_check_reachable_accepts_an_http_error(monkeypatch):
    def answer(*a, **k):
        raise urllib.error.HTTPError("u", 403, "forbidden", None, None)
    monkeypatch.setattr(grabar.urllib.request, "urlopen", answer)
    grabar.check_reachable("https://app.example.com")


def test_check_reachable_explains_the_vpn(monkeypatch):
    def fail(*a, **k):
        raise urllib.error.URLError("getaddrinfo failed")
    monkeypatch.setattr(grabar.urllib.request, "urlopen", fail)
    with pytest.raises(SystemExit, match="VPN"):
        grabar.check_reachable("https://app.example.com")


def test_load_tomas_and_timings(tmp_path):
    (tmp_path / "tomas.py").write_text("async def d1(t): pass\nTOMAS = {'D1': d1}\n", encoding="utf-8")
    tomas, capturas = grabar.load_tomas(tmp_path)
    assert list(tomas) == ["D1"] and capturas == {}
    assert grabar.load_timings(tmp_path) is None
    (tmp_path / "locucion").mkdir()
    (tmp_path / "locucion" / "timings.json").write_text('{"rows": []}', encoding="utf-8")
    assert grabar.load_timings(tmp_path) == {"rows": []}


def test_load_tomas_missing(tmp_path):
    with pytest.raises(SystemExit, match="tomas.py"):
        grabar.load_tomas(tmp_path)


def _probe_duration(path):
    r = subprocess.run([grabar.ffmpeg_exe(), "-i", str(path)], capture_output=True)
    text = r.stderr.decode("utf-8", "replace")
    hms = text.split("Duration: ")[1].split(",")[0]
    h, m, s = hms.split(":")
    return int(h) * 3600 + int(m) * 60 + float(s), text


def test_encode_holds_the_last_frame_at_30_fps(tmp_path):
    from PIL import Image
    frames = []
    for i, color in enumerate(["red", "blue"]):
        p = tmp_path / f"f{i:06d}.png"
        Image.new("RGB", (640, 360), color).save(p)
        frames.append((p, float(i)))
    durations = grabar.frame_durations([ts for _, ts in frames], end=1.2, min_total=2.5)
    out = tmp_path / "D1.mp4"
    grabar.encode(frames, durations, out)
    dur, info = _probe_duration(out)
    assert dur == pytest.approx(2.5, abs=0.05)
    assert "1920x1080" in info and "30 fps" in info and "yuv420p" in info


def _chrome_available():
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as pw:
            pw.chromium.launch(channel="chrome", headless=True).close()
        return True
    except Exception:
        return False


PAGE = """<!doctype html><html><body style="margin:40px;font:20px sans-serif">
<h1>Local</h1><div class="tile-count">1234</div>
<button id="b" onclick="go()">Go</button> <input id="q"><pre id="log"></pre>
<div style="height:2000px"></div>
<script>
async function go() {
  const r = [];
  for (const [m, u, b] of [["GET", "/api/x.json"], ["POST", "/api/agents", "{}"],
                           ["POST", "/api/agents/a1/a2a", '{"method":"tasks/get"}']]) {
    try { r.push(m + " " + u + " " + (await fetch(u, {method: m, body: b})).status) }
    catch (e) { r.push(m + " " + u + " ERR") }
  }
  document.getElementById('log').textContent = r.join("\\n") + "\\nseason=" +
    localStorage.getItem('season') + " theme=" + localStorage.getItem('theme');
}
</script></body></html>"""

TOMAS_PY = """
URL = {url!r}
async def d1(t):
    await t.goto(URL)
    await t.start(ready="#b")
    await t.click("#b")
    await t.type_slow("#q", "hola", cps=20)
    await t.type_words("#q", "y chau", word_s=0.05, click=False, lead=" ")
    await t.highlight("#b")
    await t.highlight_zone("h1", "#b")
    await t.arrow("#q", side="right")
    assert await t.page.locator(".__vt-annotation").count() == 3
    await t.unhighlight()
    assert await t.page.locator(".__vt-annotation").count() == 0
    assert await t.page.locator("#q").input_value() == "hola y chau"
    await t.hover("h1", hold_s=0.2)
    await t.scroll(300, 0.3)
    await t.wait(0.2)
async def portada(t):
    await t.goto(URL)
    await t.click("#b")
    await t.spotlight("#b", fade_s=0.1)
    await t.label("#b", "Acá", side="left")
    await t.steps("h1", "#b")
    await t.steps("#q", start=3)
    assert await t.page.locator(".__vt-annotation").count() == 5
    assert await t.page.locator(".__vt-annotation", has_text="3").count() == 1
    x = await t.page.locator(".__vt-annotation", has_text="Acá").evaluate("e => e.getBoundingClientRect().left")
    assert x >= 8
    await t.zoom_to("#b", scale=2, duration_s=0.1)
    assert "scale(2)" in await t.page.evaluate("document.body.style.transform")
    await t.zoom_out(duration_s=0.1)
    assert await t.page.evaluate("document.body.style.transform") == ""
    await t.unhighlight()
TOMAS = {{"D1": d1}}
CAPTURAS = {{"portada": portada}}
"""


@pytest.fixture
def local_site(tmp_path):
    site = tmp_path / "site"
    (site / "api").mkdir(parents=True)
    (site / "index.html").write_text(PAGE, encoding="utf-8")
    (site / "api" / "x.json").write_text("{}", encoding="utf-8")
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(site))
    handler.log_message = lambda *a: None
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_port}/index.html"
    server.shutdown()


@pytest.mark.skipif(not _chrome_available(), reason="system Chrome not available")
def test_end_to_end_against_a_local_page(tmp_path, local_site, monkeypatch, capsys):
    origin = local_site.rsplit("/", 1)[0]
    (tmp_path / "course.yaml").write_text(json.dumps({"recording": {
        "base_url": origin, "local_storage": {"season": "off", "theme": "light"},
        "write_guard": {"enabled": True, "allow": ["POST /api/agents/a1/a2a"]}}}), encoding="utf-8")
    video = tmp_path / "internal" / "01 - Video"
    (video / "locucion").mkdir(parents=True)
    (video / "tomas.py").write_text(TOMAS_PY.format(url=local_site), encoding="utf-8")
    (video / "locucion" / "timings.json").write_text(json.dumps({"rows": [
        {"visual": {"kind": "demo", "ref": "D1", "trim": None}, "visual_dur": 6.0}]}),
        encoding="utf-8")
    monkeypatch.setattr(grabar, "profile_root", lambda: tmp_path / "profiles")
    monkeypatch.setattr(grabar, "check_reachable", lambda *a, **k: None)

    grabar.main([str(video), "--tomas", "D1", "--capturas"])

    take = video / "grabaciones" / "D1.mp4"
    dur, info = _probe_duration(take)
    assert dur == pytest.approx(6.5, abs=0.1)  # visual_dur + HOLD_MARGIN, the actions are shorter
    assert "1920x1080" in info and "30 fps" in info
    shot = video / "assets" / "capturas" / "portada.png"
    from PIL import Image
    assert Image.open(shot).size == (1920, 1080)
    out = capsys.readouterr().out
    assert f"BLOCKED POST {origin}/api/agents" in out          # the guard, on: an unlisted write
    assert "a2a" not in out.split("blocked by the write guard")[1]   # the allowed one went through
