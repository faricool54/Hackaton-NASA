"""Verify the public app inside a genuinely different-origin iframe (optional Playwright dependency).

Read-only by default. --live-job explicitly submits a real 40-frame coordinate build through the iframe UI.
This verifies WS4 delivery; it does not implement or certify WS5's compact layout.
"""

import argparse
import asyncio
import html
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit


async def check(base, *, browser_path=None, live_job=False, job_id=None, out_dir=None):
    from playwright.async_api import async_playwright

    parsed = urlsplit(base)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc or parsed.username or parsed.password:
        raise ValueError("Expected an HTTP(S) application origin without credentials")
    if parsed.path not in {"", "/"} or parsed.query or parsed.fragment:
        raise ValueError("Expected the application origin without a path, query or fragment")
    base = base.rstrip("/")
    source = base + (f"/?mode=api&job={job_id}#/" if job_id else "/#/field/barnards-star")
    document = (
        '<!doctype html><html lang="en"><meta charset="utf-8"><title>Errante external embed check</title>'
        '<h1>External-origin iframe acceptance</h1><iframe title="Errante embed" '
        f'style="width:100%;height:1050px;border:0" src="{html.escape(source, quote=True)}"></iframe></html>'
    ).encode()

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(document)

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    outer = f"http://127.0.0.1:{server.server_port}"
    if out_dir:
        out_dir.mkdir(parents=True, exist_ok=True)
    try:
        async with async_playwright() as p:
            options = {"executable_path": browser_path} if browser_path else {"channel": "msedge"}
            browser = await p.chromium.launch(
                **options, headless=True, args=["--use-angle=swiftshader", "--enable-unsafe-swiftshader"]
            )
            try:
                page = await browser.new_page(viewport={"width": 1440, "height": 1200})
                await page.goto(outer, wait_until="domcontentloaded")
                iframe = page.frame_locator('iframe[title="Errante embed"]')
                if live_job:
                    await iframe.get_by_role("link", name="Fields", exact=True).click()
                    await iframe.get_by_label("Right ascension", exact=True).fill("269.4474")
                    await iframe.get_by_label("Declination", exact=True).fill("4.7695")
                    await iframe.get_by_label("Field side (degrees)", exact=True).fill("0.03")
                    form = iframe.locator("form").filter(has=iframe.get_by_label("Right ascension", exact=True))
                    await form.locator("select").select_option("2")
                    async with page.expect_response(
                        lambda r: r.url.endswith("/api/jobs") and r.request.method == "POST"
                    ) as response:
                        await iframe.get_by_role("button", name="Build time sequence", exact=True).click()
                    job_id = (await (await response.value).json())["id"]
                if job_id:
                    await (
                        iframe.locator(".job-status strong").filter(has_text="Sequence ready").wait_for(timeout=300000)
                    )
                player = iframe.get_by_label("Time sequence player", exact=True)
                await player.wait_for(timeout=60000)
                await iframe.locator(".blink img").first.evaluate(
                    "async () => { await Promise.all([...document.querySelectorAll('.blink img')].map(i => "
                    "i.decode())); }"
                )
                await player.get_by_role("button", name="Pause", exact=True).click()
                before = await player.get_by_role("slider", name="Frame", exact=True).get_attribute("aria-valuenow")
                await player.get_by_role("button", name="Next frame", exact=True).click()
                after = await player.get_by_role("slider", name="Frame", exact=True).get_attribute("aria-valuenow")
                assert before != after, "Embedded player did not step"
                result = {
                    "parent_origin": outer,
                    "app_origin": base,
                    "cross_origin": True,
                    "loaded_images": await player.locator("img").count(),
                    "stepped": True,
                    "job_id": job_id,
                    "compact_layout": "WS5 follow-up; full application tested",
                }
                if out_dir:
                    await page.screenshot(path=str(out_dir / "iframe-desktop.png"), full_page=True)
                    (out_dir / "iframe-acceptance.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
                return result
            finally:
                await browser.close()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("base")
    parser.add_argument("--browser-path", help="Optional Chromium/Edge executable; defaults to installed Edge")
    parser.add_argument("--live-job", action="store_true")
    parser.add_argument("--job-id", help="Resume a previously completed job in the iframe")
    parser.add_argument("--out-dir", type=Path)
    args = parser.parse_args()
    print(
        json.dumps(
            asyncio.run(
                check(
                    args.base,
                    browser_path=args.browser_path,
                    live_job=args.live_job,
                    job_id=args.job_id,
                    out_dir=args.out_dir,
                )
            ),
            indent=2,
        )
    )
