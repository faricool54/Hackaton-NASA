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
    await query.fill("Barnard")
    match = t.page.get_by_role("button", name=re.compile("Barnard.*frames", re.I))
    await match.wait_for(state="visible", timeout=30000)
    # A loaded input alone does not establish that the WebGL map is ready.
    await t.page.locator('select[aria-label="Map wavelength"]:not([disabled])').wait_for(state="attached", timeout=45000)
    await t.start(ready="#sky-query")
    await t.hover(query, hold_s=0.3)
    await t.click(match)
    await hold_measured(t, "D1")


async def prepare_field(t, field_id="r-draconis", detector_value=None):
    await t.goto(f"/#/field/{field_id}")
    await t.page.locator(".blink-frame").first.wait_for(timeout=45000)
    detector = t.page.locator(".field-layout .toolbar select").first
    values = await detector.locator("option").evaluate_all("items => items.map(x => x.value).filter(x => x !== 'all')")
    if detector_value is not None:
        await detector.select_option(str(detector_value))
    elif values:
        await detector.select_option(values[0])
    await t.page.wait_for_function("""() => {
        const imgs = [...document.querySelectorAll('.blink-frame')];
        return imgs.length > 0 && imgs.every(i => i.complete && i.naturalWidth > 0);
    }""", timeout=60000)


async def d2(t):
    await prepare_field(t, "barnards-star", detector_value=2)
    summary = t.page.locator("summary").filter(has_text=re.compile("^Compare seasons"))
    await summary.click()
    panel = summary.locator("..")
    await panel.get_by_label(re.compile("^Comparison detector")).select_option("2")
    await panel.get_by_role("button", name="Build comparisons", exact=True).click()
    products = panel.get_by_label(re.compile("^Comparison product"))
    await products.wait_for(timeout=90000)
    await products.select_option("D2_S2-S0")
    image = panel.locator(".comparison-image")
    await image.wait_for(timeout=30000)
    await t.page.wait_for_function("""() => {
        const img = document.querySelector('.comparison-image');
        return img && img.complete && img.naturalWidth > 0;
    }""", timeout=30000)
    # Put the real image, its dates and the nearby quality warning in the frame;
    # merely revealing the selector can leave the entire difference below the fold.
    await image.evaluate("""img => window.scrollTo({
        top: Math.max(0, img.getBoundingClientRect().top + window.scrollY - 100),
        behavior: 'instant'
    })""")
    await t.start(ready=image)
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
