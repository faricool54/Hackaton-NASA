# Exports every slide of a video's presentacion.html to assets/slides/slide-NN.png at the course
# resolution, in recording mode (?rec), so the deck's own chrome (help line, cursor) never reaches
# the edit and entry animations are not captured mid-fade. Run it again after changing the deck.
#
#   python slides.py <video>

import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from course import Course

BROWSERS = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
]
WHICH = ["google-chrome", "chromium", "chromium-browser", "microsoft-edge"]


def find_browser():
    found = next((b for b in BROWSERS if os.path.exists(b)), None)
    return found or next((p for p in map(shutil.which, WHICH) if p), None)


def slide_count(deck_html):
    """Slides after builds expand: a section with data-steps="N" counts N."""
    sections = re.findall(r'<section class="slide[^>]*>', deck_html)
    return sum(int(m.group(1)) if (m := re.search(r'data-steps="(\d+)"', s)) else 1 for s in sections)


def main(argv=None):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    args = sys.argv[1:] if argv is None else argv
    if not args:
        raise SystemExit("usage: slides.py <video>")
    course = Course.load(args[0])
    video_dir = course.resolve_video(args[0])
    deck = video_dir / "presentacion.html"
    if not deck.exists():
        raise SystemExit(f"missing {deck}")
    browser = find_browser()
    if browser is None:
        raise SystemExit("Chrome or Edge not found")

    count = slide_count(deck.read_text(encoding="utf-8"))
    out = video_dir / "assets" / "slides"
    out.mkdir(parents=True, exist_ok=True)
    for stale in out.glob("slide-*.png"):   # a deck that lost slides must not leave old PNGs behind
        stale.unlink()

    # A throwaway profile, so an already-open browser window is never reused or touched.
    with tempfile.TemporaryDirectory() as profile:
        for n in range(1, count + 1):
            target = out / f"slide-{n:02d}.png"
            subprocess.run(
                [browser, "--headless=new", "--disable-gpu", "--hide-scrollbars",
                 f"--user-data-dir={profile}", f"--window-size={course.width},{course.height}",
                 "--force-device-scale-factor=1", "--virtual-time-budget=2500",
                 f"--screenshot={target}", f"{deck.as_uri()}?rec#{n}"],
                check=True, capture_output=True, timeout=60,
            )
            print(target.name)


if __name__ == "__main__":
    main()
