"""Errante final cut (v4) takes, recorded on 08dfb85. Recheck selectors before filming.

D0 is the hook: the app's real false-colour season blink, expanded to the whole window, under an animated
title overlay and a slow push-in (movement requested by the team). D1 starts a REAL click-style build
(POST /api/jobs, allowed by the write guard); D2-D4 reopen the same position, so they show that build's
real result. The wait is cut and the measured build time is shown on screen. No synthetic images.
"""
import asyncio
import json
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import parse_qs, urlparse

# Hook background: the field built on camera for v3 (job 7aa7d11f, 76.73297, +30.23697).
HOOK_URL = "/?ra=76.73297&dec=30.23697&fov=0.25&detector=all&job=7aa7d11f851c45b3bdd599343d1428fe#/"
# 6" east of Gaia DR3 156328460158131584 (76.73197, +30.23697): fresh parameters, so D1 starts a new job
# (the server reuses a ready job with identical parameters for 15 minutes).
RA, DEC = 76.73397, 30.23697
STAR_ID = "156328460158131584"
SELECTED_URL = f"/?ra={RA}&dec={DEC}&fov=0.25#/"
MAP_CENTER = (730, 564)       # the sky map iframe spans page x 0-1460, y 48-1080 at 1920x1080
HOVER_START = (560, 760)
BUILD_TIMEOUT_MS = 300000

HOOK_JS = r"""([title, tag, sub]) => {
  const css = document.createElement('style');
  css.className = '__vt-annotation';
  css.textContent = `
  @keyframes vtTitle {from {opacity:0; transform:translateY(28px) scale(.97); letter-spacing:.55em}
                      to {opacity:1; transform:none; letter-spacing:.30em}}
  @keyframes vtRise {from {opacity:0; transform:translateY(16px)} to {opacity:1; transform:none}}
  @keyframes vtPush {from {transform:scale(1)} to {transform:scale(1.07)}}
  @keyframes vtGlow {0%,100% {opacity:.55} 50% {opacity:.9}}
  .vt-hook {position:fixed; inset:0; z-index:2147483646; pointer-events:none;
    display:flex; flex-direction:column; justify-content:flex-end; align-items:center; padding-bottom:96px;
    font-family:'Segoe UI Variable Display','Segoe UI',Inter,system-ui,sans-serif;
    background:
      linear-gradient(180deg, rgba(3,6,18,.55) 0%, rgba(3,6,18,0) 22%, rgba(3,6,18,0) 48%, rgba(3,6,18,.92) 84%),
      radial-gradient(ellipse at 50% 42%, rgba(0,0,0,0) 52%, rgba(0,0,0,.6) 100%);}
  .vt-hook .rule {width:520px; height:2px; margin:0 0 26px;
    background:linear-gradient(90deg,transparent,#7dd3fc,#c084fc,transparent); animation:vtGlow 2.4s ease-in-out infinite, vtRise .8s ease-out .2s both}
  .vt-hook h1 {margin:0; padding-left:.30em; font-size:124px; line-height:1; font-weight:800; letter-spacing:.30em;
    background:linear-gradient(92deg,#7dd3fc 0%,#a5b4fc 40%,#c084fc 70%,#f9a8d4 100%);
    -webkit-background-clip:text; background-clip:text; color:transparent;
    filter:drop-shadow(0 8px 34px rgba(125,211,252,.35)); animation:vtTitle 1.2s cubic-bezier(.16,.8,.24,1) .15s both}
  .vt-hook p {margin:22px 0 0; color:#f1f5f9; font-size:44px; font-weight:500; letter-spacing:.01em;
    text-shadow:0 2px 18px rgba(0,0,0,.6); animation:vtRise .9s ease-out .9s both}
  .vt-hook small {margin-top:20px; color:#a5b4fc; font-size:22px; font-weight:600; letter-spacing:.22em;
    text-transform:uppercase; animation:vtRise .9s ease-out 1.6s both}`;
  document.head.appendChild(css);
  for (const el of document.body.children) {
    if (el.tagName === 'SCRIPT' || el.tagName === 'STYLE') continue;
    el.style.transformOrigin = '50% 42%';
    el.style.animation = 'vtPush 10s cubic-bezier(.2,.6,.3,1) both';
  }
  const d = document.createElement('div');
  d.className = 'vt-hook __vt-annotation';
  d.innerHTML = `<div class="rule"></div><h1>${title}</h1><p>${tag}</p><small>${sub}</small>`;
  document.body.appendChild(d);
}"""


def _timings():
    timings = Path(__file__).parent / "locucion/timings.json"
    if not timings.exists():
        raise RuntimeError("Run locutor.py before recording the demo")
    return json.loads(timings.read_text(encoding="utf-8"))


def phrase_dur(ref):
    rows = [r for r in _timings()["rows"] if r["visual"]["kind"] == "demo" and r["visual"]["ref"] == ref]
    if not rows:
        raise RuntimeError(f"No narration timing for {ref}; update tomas.py after changing the script")
    return rows[0]["phrase_dur"]


async def hold_measured(t, ref):
    """Keep recording real frames for the measured shot, instead of freezing its last frame."""
    ends = [max(row["visual_dur"], (row["visual"].get("trim") or [0, 0])[1])
            for row in _timings()["rows"]
            if row["visual"]["kind"] == "demo" and row["visual"]["ref"] == ref]
    if not ends:
        raise RuntimeError(f"No narration timing for {ref}; update tomas.py after changing the script")
    await t.at(max(ends) + 0.5)


async def move_xy(t, x, y, duration_s=0.6):
    """Eased cursor path to page coordinates (the map is a canvas inside an iframe, no locator)."""
    await t.start()
    x0, y0 = t._pos
    steps = max(1, round(duration_s * 60))
    for i in range(1, steps + 1):
        k = i / steps
        k = k * k * (3 - 2 * k)  # smoothstep
        await t.page.mouse.move(x0 + (x - x0) * k, y0 + (y - y0) * k)
        await asyncio.sleep(duration_s / steps)
    t._pos = (x, y)


def build_button(t):
    return t.page.get_by_role("button", name="Build SPHEREx sequence", exact=True).first


def color_button(t):
    return t.page.get_by_role("button", name="Color · detectors", exact=True).first


def dock_tab(t, name):
    return t.page.get_by_role("tab", name=re.compile(rf"^{re.escape(name)}\b")).first


def star_card(t):
    return t.page.locator(".mp-card--gaia").filter(has_text=STAR_ID).first


async def center_of(locator):
    box = await locator.bounding_box()
    return box["x"] + box["width"] / 2, box["y"] + box["height"] / 2


async def wait_map(t):
    await t.page.locator('select[aria-label="Map wavelength"]:not([disabled])').wait_for(
        state="attached", timeout=45000)


async def open_selected(t):
    await t.goto(SELECTED_URL)
    await build_button(t).wait_for(state="visible", timeout=45000)
    await wait_map(t)


async def wait_blink(t, timeout_ms=BUILD_TIMEOUT_MS):
    await t.page.locator('img[alt^="SPHEREx frame"]').first.wait_for(state="attached", timeout=timeout_ms)
    await t.page.wait_for_function("""() => {
        const imgs = [...document.querySelectorAll('img[alt^="SPHEREx frame"]')];
        return imgs.length > 0 && imgs.every(i => i.complete && i.naturalWidth > 0);
    }""", timeout=120000)


async def built_field(t, color=True):
    """Off camera: reopen the position and join/reuse the build, then show its blink (colour preloaded)."""
    await open_selected(t)
    await build_button(t).click()
    await wait_blink(t)
    await asyncio.sleep(2)
    await color_button(t).click()
    await asyncio.sleep(4)
    if not color:
        await t.page.get_by_role("button", name="B/W", exact=True).first.click()
        await asyncio.sleep(1)


async def build_seconds(t):
    """Measured duration of the job behind the current page (job id from the URL, times from the API)."""
    job = parse_qs(urlparse(t.page.url).query).get("job", [None])[0]
    if not job:
        raise RuntimeError(f"no job id in {t.page.url}")
    resp = await t.page.request.get(f"{t.base_url}/api/jobs/{job}")
    data = await resp.json()
    start = datetime.fromisoformat(data["created_at"].replace("Z", "+00:00"))
    end = datetime.fromisoformat(data["updated_at"].replace("Z", "+00:00"))
    return job, round((end - start).total_seconds())


async def map_fov_arcmin(t):
    text = await t.page.frame_locator("iframe.sky-map-frame").locator("body").inner_text()
    m = re.search(r"(\d+(?:\.\d+)?)\s*([°'′])\s*[x×]", text)
    if not m:
        return None
    value = float(m.group(1))
    return value * 60 if m.group(2) == "°" else value


async def zoom_for_gaia(t, target_arcmin=18):
    """Wider views ask VizieR for bright Gaia stars and that query failed on e89ab45: zoom in first."""
    await t.page.mouse.move(*MAP_CENTER)
    for _ in range(14):
        fov = await map_fov_arcmin(t)
        if fov is not None and fov <= target_arcmin:
            break
        await t.page.mouse.wheel(0, -120)
        await asyncio.sleep(0.6)
    await asyncio.sleep(6)


async def find_star(t, timeout_s=60):
    """Spiral hover search around the map center until the card of STAR_ID shows; returns its position."""
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout_s
    while loop.time() < deadline:
        for r in range(0, 37, 3):
            pts = [(0, 0)] if r == 0 else (
                [(dx, dy) for dx in range(-r, r + 1, 3) for dy in (-r, r)]
                + [(dx, dy) for dy in range(-r + 3, r, 3) for dx in (-r, r)])
            for dx, dy in pts:
                x, y = MAP_CENTER[0] + dx, MAP_CENTER[1] + dy
                await t.page.mouse.move(x, y)
                await asyncio.sleep(0.1)
                card = star_card(t)
                if await card.count() and await card.is_visible():
                    return x, y
        await t.page.mouse.move(*HOVER_START)
        await asyncio.sleep(3)
    raise RuntimeError(f"Gaia DR3 {STAR_ID} card never showed near the map center")


async def load_object_card(t):
    """Off camera: Object tab, wait for the catalog answer (Retry if a service did not answer)."""
    await dock_tab(t, "Object").click()
    matched = t.page.get_by_text(re.compile(r"Matched to one Gaia DR3 source", re.I)).first
    for _ in range(4):
        try:
            await matched.wait_for(state="visible", timeout=25000)
            return
        except Exception:
            retry = t.page.get_by_role("button", name="Retry").first
            if await retry.count():
                await retry.click()
    raise RuntimeError("Object card never matched the clicked Gaia DR3 source")


async def selected_star(t):
    """Off camera: built field, zoomed, star found, clicked, Object answered (warms the server cache)."""
    await built_field(t)
    await zoom_for_gaia(t)
    pos = await find_star(t)
    await t.page.mouse.click(*pos)
    await t.page.locator(".mp-card--gaia.mp-card--pinned").first.wait_for(state="visible", timeout=10000)
    await load_object_card(t)
    return pos


async def d0(t):
    await t.goto(HOOK_URL)
    await wait_blink(t)
    await asyncio.sleep(2)
    await color_button(t).click()
    await asyncio.sleep(3)
    await t.page.get_by_role("button", name=re.compile("^Expand")).first.click()
    await asyncio.sleep(3)
    t._pos = (1960, 1100)  # cursor parked off screen for the hook
    await t.start()
    await t.page.evaluate(HOOK_JS, ["ERRANTE", "Watch the infrared sky change.",
                                    "Real NASA SPHEREx images · false color"])
    await hold_measured(t, "D0")


async def d1(t):
    await open_selected(t)
    build = build_button(t)
    await asyncio.sleep(2)
    t._pos = MAP_CENTER  # the cursor rests on the picked point (the crosshair)
    await t.start(ready=build)
    await t.at(0.4)
    await t.click(build, duration_s=0.6, settle=False)
    # A reused (already built) job would skip this state: then the take is not a real build start.
    await t.page.get_by_text("Preparing SPHEREx observations").first.wait_for(timeout=10000)
    await hold_measured(t, "D1")


async def d2(t):
    await built_field(t, color=False)
    job, secs = await build_seconds(t)
    label = f"Edited cut: this build took {secs // 60} min {secs % 60:02d} s"
    print(f"D2 cut label: {label} (job {job})")
    image = t.page.locator('img[alt^="SPHEREx frame"]').first
    t._pos = (await center_of(color_button(t)))[0] - 160, 760
    await t.start()
    await t.label(image, label, side="left")
    await t.at(0.5)
    await t.click(color_button(t), duration_s=0.5, settle=False)
    await hold_measured(t, "D2")


async def d3(t):
    await selected_star(t)  # warm the lookup once, then start again from the unselected field
    await built_field(t)
    await zoom_for_gaia(t)
    pos = await find_star(t)
    await t.page.mouse.move(*HOVER_START)
    await asyncio.sleep(1.5)
    t._pos = HOVER_START
    await t.start()
    await t.at(0.1)
    await move_xy(t, *pos, duration_s=0.5)
    await star_card(t).wait_for(state="visible", timeout=5000)
    await t.at(1.3)
    await t.page.mouse.click(*t._pos)
    await t.at(1.8)
    await t.click(dock_tab(t, "Object"), duration_s=0.4, settle=False)
    await t.page.get_by_text("Distance").first.wait_for(state="visible", timeout=8000)
    await t.zoom_to(t.page.get_by_text("Distance").first, scale=1.55, duration_s=0.7)
    await hold_measured(t, "D3")


async def d4(t):
    await selected_star(t)
    await dock_tab(t, "3D").click()
    await t.page.get_by_text("3D MODEL · NOT AN IMAGE").first.wait_for(state="visible", timeout=45000)
    await asyncio.sleep(3)
    await load_object_card(t)
    t._pos = await center_of(dock_tab(t, "Object"))
    await asyncio.sleep(1.0)
    await t.start()
    await t.at(0.1)
    await t.click(dock_tab(t, "3D"), duration_s=0.4, settle=False)
    badge = t.page.get_by_text("3D MODEL · NOT AN IMAGE").first
    await badge.wait_for(state="visible", timeout=10000)
    await asyncio.sleep(0.3)
    await t.zoom_to(badge, scale=1.6, duration_s=0.7)
    await hold_measured(t, "D4")


TOMAS = {"D0": d0, "D1": d1, "D2": d2, "D3": d3, "D4": d4}
