"""Real Errante UI shots. Recheck selectors against the deployed version before filming.

Preparation/loading happens off camera. No API writes, fake results, synthetic images,
motion amplification or added annotations. Existing scientific labels stay in frame.
"""
import json
import re
from pathlib import Path


async def hold_measured(t, ref):
    """Keep recording real frames for the measured shot, instead of freezing its last frame."""
    timings = Path(__file__).parent / "locucion/timings.json"
    if not timings.exists():
        raise RuntimeError("Run locutor.py before recording the demo")
    data = json.loads(timings.read_text(encoding="utf-8"))
    ends = [max(row["visual_dur"], (row["visual"].get("trim") or [0, 0])[1])
            for row in data["rows"]
            if row["visual"]["kind"] == "demo" and row["visual"]["ref"] == ref]
    if not ends:
        raise RuntimeError(f"No narration timing for {ref}; update tomas.py after changing the script")
    await t.at(max(ends) + 0.5)


async def d1(t):
    await t.goto("/#/")
    query = t.page.get_by_role("searchbox", name="Search the sky")
    await query.fill("R Draconis")
    match = t.page.get_by_role("button", name=re.compile("R Draconis.*frames", re.I))
    await match.wait_for(state="visible", timeout=30000)
    # A loaded input alone does not establish that the WebGL map is ready.
    await t.page.locator('select[aria-label="Map wavelength"]:not([disabled])').wait_for(timeout=45000)
    await t.start(ready="#sky-query")
    await t.hover(query, hold_s=0.3)
    await t.click(match)
    await hold_measured(t, "D1")


async def prepare_field(t):
    await t.goto("/#/field/r-draconis")
    await t.page.locator(".blink-frame").first.wait_for(timeout=45000)
    detector = t.page.locator(".field-layout .toolbar select").first
    values = await detector.locator("option").evaluate_all("items => items.map(x => x.value).filter(x => x !== 'all')")
    if values:
        await detector.select_option(values[0])
    await t.page.wait_for_function("""() => {
        const imgs = [...document.querySelectorAll('.blink-frame')];
        return imgs.length > 0 && imgs.every(i => i.complete && i.naturalWidth > 0);
    }""", timeout=60000)


async def d2(t):
    await prepare_field(t)
    await t.page.locator(".blink").scroll_into_view_if_needed()
    play = t.page.get_by_role("button", name="Play", exact=True)
    if await play.count():
        await play.click()  # off camera: avoid wasting the shot on setup
    await t.start(ready=".blink-frame")
    await hold_measured(t, "D2")


async def d3(t):
    await prepare_field(t)
    summary = t.page.locator("summary").filter(has_text=re.compile("^Light curve$"))
    await summary.click()  # load the published product before recording
    panel = summary.locator("..")
    await panel.get_by_role("img").wait_for(timeout=45000)
    await panel.scroll_into_view_if_needed()
    await t.start(ready=panel.get_by_role("img"))
    await hold_measured(t, "D3")


TOMAS = {"D1": d1, "D2": d2, "D3": d3}
