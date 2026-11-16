"""Errante build walkthrough takes (faricool54's route after e89ab45, #100). Recheck selectors before filming.

D1 starts a REAL click-style build (POST /api/jobs, allowed by the write guard). D2-D4 reopen the same
position: the server joins the running job or reuses the finished one (15 min reuse window), so they
show the real result of that build. The wait is cut and the cut is stated on screen and in the voice.
Everything else loads off camera; no synthetic images, no speed-ups.
"""
import asyncio
import json
import re
from pathlib import Path

# 3" east of Gaia DR3 156328460158131584 (76.73197, +30.23697: matched, no SIMBAD type, Gaia parallax distance).
# Offset so D1 starts a fresh build: the exact star position was built off camera at 21:58 ART and the server
# reuses a ready job with the same parameters for 15 minutes. The star stays at the center of the field.
RA, DEC = 76.73297, 30.23697
STAR_ID = "156328460158131584"
SELECTED_URL = f"/?ra={RA}&dec={DEC}&fov=0.25#/"
MAP_CENTER = (730, 564)       # the sky map iframe spans page x 0-1460, y 48-1080 at 1920x1080
HOVER_START = (560, 760)
CUT_LABEL = "Edited cut: this build took 1 min 53 s"  # job 7aa7d11f, 01:07:34Z -> 01:09:27Z
BUILD_TIMEOUT_MS = 240000


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


def dock_tab(t, name):
    return t.page.get_by_role("tab", name=re.compile(rf"^{re.escape(name)}\b")).first


def star_card(t):
    return t.page.locator(".mp-card--gaia").filter(has_text=STAR_ID).first


async def center_of(locator):
    box = await locator.bounding_box()
    return box["x"] + box["width"] / 2, box["y"] + box["height"] / 2


async def open_selected(t):
    await t.goto(SELECTED_URL)
    await build_button(t).wait_for(state="visible", timeout=45000)
    await t.page.locator('select[aria-label="Map wavelength"]:not([disabled])').wait_for(
        state="attached", timeout=45000)


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
    color_btn = t.page.get_by_role("button", name="Color · detectors", exact=True).first
    await color_btn.click()
    await asyncio.sleep(4)
    if not color:
        await t.page.get_by_role("button", name="B/W", exact=True).first.click()
        await asyncio.sleep(1)


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
        for r in range(0, 31, 3):
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
    color_btn = t.page.get_by_role("button", name="Color · detectors", exact=True).first
    image = t.page.locator('img[alt^="SPHEREx frame"]').first
    t._pos = (await center_of(color_btn))[0] - 160, 760
    await t.start()
    await t.label(image, CUT_LABEL, side="left")
    await t.at(0.5)
    await t.click(color_btn, duration_s=0.5, settle=False)
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
    await move_xy(t, *pos, duration_s=0.6)
    await star_card(t).wait_for(state="visible", timeout=5000)
    pd = phrase_dur("D3")
    await t.at(max(1.6, 0.42 * pd))
    await t.page.mouse.click(*t._pos)
    await t.at(max(2.3, 0.6 * pd))
    await t.click(dock_tab(t, "Object"), duration_s=0.5, settle=False)
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
    await hold_measured(t, "D4")


TOMAS = {"D1": d1, "D2": d2, "D3": d3, "D4": d4}
