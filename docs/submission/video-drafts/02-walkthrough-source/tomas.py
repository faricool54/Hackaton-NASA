"""Errante walkthrough takes (fari's route, #100). Recheck selectors against the deployed version before filming.

Preparation/loading happens off camera: frames, Gaia markers, the catalog lookup and the 3D model
are loaded before each take starts. No synthetic images, motion amplification or annotations.
The write guard stays on: selecting a star triggers POST /api/spectra, which is blocked and not shown.
"""
import asyncio
import json
from pathlib import Path

# The sky map iframe spans page x 0-1460, y 48-1080 at 1920x1080; a target chip centers the map on
# the target, so Barnard's Gaia DR3 marker (predicted for the median frame date) sits at the center.
MAP_CENTER = (730, 564)
HOVER_START = (560, 760)  # cursor start for D2, lower-left of the star, away from where its card opens
BARNARD_GAIA_ID = "4472832130942575872"


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


def barnard_chip(t):
    return t.page.locator("button.sx-target").filter(has_text="Barnard").first


def gaia_card(t):
    return t.page.locator(".mp-card--gaia").filter(has_text=BARNARD_GAIA_ID).first


def dock_tab(t, name):
    return t.page.get_by_role("tab", name=name, exact=True).first


async def open_home(t):
    await t.goto("/#/")
    await barnard_chip(t).wait_for(state="visible", timeout=30000)
    # A loaded input alone does not establish that the WebGL map is ready.
    await t.page.locator('select[aria-label="Map wavelength"]:not([disabled])').wait_for(
        state="attached", timeout=45000)


async def wait_blink(t):
    await t.page.locator('img[alt^="SPHEREx frame"]').first.wait_for(state="attached", timeout=45000)
    await t.page.wait_for_function("""() => {
        const imgs = [...document.querySelectorAll('img[alt^="SPHEREx frame"]')];
        return imgs.length > 0 && imgs.every(i => i.complete && i.naturalWidth > 0);
    }""", timeout=90000)


async def wait_gaia_hover(t, timeout_s=40):
    """Gaia markers load a few seconds after the zoom: hover the center until Barnard's card shows."""
    x, y = MAP_CENTER
    offsets = [(0, 0), (2, -2), (-2, 2), (3, 3), (-3, -3)]
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout_s
    while loop.time() < deadline:
        for dx, dy in offsets:
            await t.page.mouse.move(HOVER_START[0], HOVER_START[1])
            await asyncio.sleep(0.2)
            await t.page.mouse.move(x + dx, y + dy)
            try:
                await gaia_card(t).wait_for(state="visible", timeout=2000)
                return x + dx, y + dy
            except Exception:
                continue
    raise RuntimeError("Barnard's Gaia DR3 card never showed at the map center")


async def select_barnard_star(t):
    """Off camera: Barnard chip, frames loaded, Gaia star hovered and clicked (selected)."""
    await open_home(t)
    await barnard_chip(t).click()
    await wait_blink(t)
    pos = await wait_gaia_hover(t)
    await t.page.mouse.click(*pos)
    await t.page.locator(".mp-card--gaia.mp-card--pinned").first.wait_for(state="visible", timeout=10000)
    return pos


async def load_object_card(t):
    """Off camera: open Object and make sure the catalog lookup answered (Retry if a service did not)."""
    await dock_tab(t, "Object").click()
    matched = t.page.get_by_text("Matched to one Gaia DR3 source").first
    for _ in range(4):
        try:
            await matched.wait_for(state="visible", timeout=25000)
            return
        except Exception:
            retry = t.page.get_by_role("button", name="Retry").first
            if await retry.count():
                await retry.click()
    raise RuntimeError("Object card never matched Barnard's Gaia DR3 source")


async def d1(t):
    await open_home(t)
    # Preload the real frames off camera, then come back to the home view.
    await barnard_chip(t).click()
    await wait_blink(t)
    await open_home(t)
    chip = barnard_chip(t)
    # Start with the cursor just below-right of the chip, so the click lands early and the blink fills the row.
    box = await chip.bounding_box()
    t._pos = (box["x"] + box["width"] / 2 + 90, box["y"] + box["height"] / 2 + 110)
    await t.start(ready=chip)
    await t.at(0.2)
    await t.click(chip, duration_s=0.35, settle=False)
    await hold_measured(t, "D1")


async def d2(t):
    await open_home(t)
    await barnard_chip(t).click()
    await wait_blink(t)
    await wait_gaia_hover(t)
    await t.page.mouse.move(*HOVER_START)
    await asyncio.sleep(1.0)
    t._pos = HOVER_START
    await t.start()
    await t.at(0.1)
    await move_xy(t, *MAP_CENTER, duration_s=0.6)
    await gaia_card(t).wait_for(state="visible", timeout=5000)
    await t.at(max(1.9, 0.6 * phrase_dur("D2")))
    await t.page.mouse.click(*t._pos)
    await hold_measured(t, "D2")


async def d3(t):
    t._pos = await select_barnard_star(t)
    await load_object_card(t)
    await dock_tab(t, "Time").click()
    await wait_blink(t)
    await asyncio.sleep(1.0)
    await t.start()
    await t.at(0.1)
    await t.click(dock_tab(t, "Object"), duration_s=0.5, settle=False)
    await hold_measured(t, "D3")


async def d4(t):
    await select_barnard_star(t)
    await load_object_card(t)
    # Load the 3D model once off camera, then return to Object (where D3 ended).
    await dock_tab(t, "3D").click()
    await t.page.get_by_text("3D MODEL · NOT AN IMAGE").first.wait_for(state="visible", timeout=45000)
    await asyncio.sleep(3.0)
    await load_object_card(t)
    box = await dock_tab(t, "Object").bounding_box()
    t._pos = (box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
    await asyncio.sleep(1.0)
    await t.start()
    await t.at(0.1)
    await t.click(dock_tab(t, "3D"), duration_s=0.4, settle=False)
    await hold_measured(t, "D4")


TOMAS = {"D1": d1, "D2": d2, "D3": d3, "D4": d4}
