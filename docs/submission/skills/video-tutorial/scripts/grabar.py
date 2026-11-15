# Records demo takes and captures of a web app with Playwright, driven by the tomas.py of
# each video and configured by the course's course.yaml (recording section). Claude never
# types credentials: the user signs in once with --login, into a persistent browser profile
# that lives outside the course folder.
#
#   python grabar.py <course-or-video> --login
#   python grabar.py <video> [--tomas D1,D3] [--capturas] [--headed]
#
# <video>/tomas.py exposes TOMAS = {"D1": async_fn, ...} and CAPTURAS = {"name": async_fn, ...}.
# Each fn receives a Toma. Takes go to <video>/grabaciones/Dn.mp4, captures to
# <video>/assets/capturas/<name>.png. With recording.write_guard.enabled, every request to the
# app that is not a read (GET/HEAD) and not in the allow list is aborted and reported; without
# it, a toma that creates or sends something does so for real.
#
# A toma fn sets up off camera, then starts recording:
#
#   async def d1(t):
#       await t.goto("/settings")                      # not recorded yet
#       await t.start(ready="main h1")                 # waits for the page to settle
#       await t.click(t.page.get_by_role("button", name="Save"))
#       await t.hover(".card", hold_s=1.5)
#
# Any action helper starts the recording on its own if start() was not called. Once the fn
# returns, the take keeps running END_HOLD_S (so the last action's repaint is captured), then
# holds its last frame until it covers the longest row that uses it in locucion/timings.json,
# plus HOLD_MARGIN.

import asyncio
import base64
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parent))
from course import Course

HOLD_MARGIN = 0.5      # seconds a take runs past the longest row that shows it
SETTLE_S = 1.3         # drawers and panels finish animating in about this long
END_HOLD_S = 0.8       # the screencast only sends a frame after a repaint: keep recording after the last action
ANNOTATION_COLOR = "#ff0000"
ANNOTATION_WIDTH = 5

CURSOR_SVG = ('<svg xmlns="http://www.w3.org/2000/svg" width="22" height="30" viewBox="0 0 22 30">'
              '<path d="M1 1 L1 24 L7 18.5 L11 28 L15 26.3 L11 17 L19 17 Z" fill="#000" '
              'stroke="#fff" stroke-width="1.5" stroke-linejoin="round"/></svg>')
READ_METHODS = {"GET", "HEAD"}


def profile_root():
    """Where browser profiles live: outside every course folder, since they hold session cookies."""
    base = os.environ.get("LOCALAPPDATA") or (Path.home() / ".local" / "share")
    return Path(base) / "video-tutorial"


@dataclass
class Rec:
    """The recording settings of one course."""
    base_url: str
    profile_dir: Path
    width: int = 1920
    height: int = 1080
    fps: int = 30
    sso_hosts: list = field(default_factory=lambda: ["okta"])
    color_scheme: str = "light"
    local_storage: dict = field(default_factory=dict)
    blur_selectors: list = field(default_factory=list)
    guard: bool = False
    allow: list = field(default_factory=list)

    @classmethod
    def from_course(cls, course):
        r = course.recording
        if not r["base_url"]:
            raise SystemExit("recording.base_url is empty in course.yaml")
        # An absolute profile path reuses an existing signed-in profile (a course migrated to the skill).
        profile = Path(course.profile_name)
        return cls(base_url=r["base_url"].rstrip("/"),
                   profile_dir=profile if profile.is_absolute() else profile_root() / course.profile_name,
                   width=course.width, height=course.height, fps=course.fps, sso_hosts=list(r["sso_hosts"]),
                   color_scheme=r["color_scheme"], local_storage=dict(r["local_storage"]),
                   blur_selectors=list(r["blur_selectors"]), guard=bool(r["write_guard"]["enabled"]),
                   allow=list(r["write_guard"]["allow"]))


def frame_durations(timestamps, end, min_total=0.0, fps=30):
    """How long each screencast frame stays on screen, from its timestamp to the next one.

    The last frame lasts until `end`, and longer if needed to reach `min_total` seconds.
    Out-of-order timestamps never produce a negative duration.
    """
    if not timestamps:
        raise ValueError("no frames recorded")
    durations, prev = [], timestamps[0]
    for ts in timestamps[1:]:
        ts = max(ts, prev)
        durations.append(ts - prev)
        prev = ts
    durations.append(max(end - prev, 1.0 / fps))
    shortfall = min_total - sum(durations)
    if shortfall > 0:
        durations[-1] += shortfall
    return durations


def target_duration(timings, ref, margin=HOLD_MARGIN):
    """Minimum length of take `ref`: the furthest point any montage row shows of it, plus margin.

    A row with a trim needs the take up to the trim end; one without plays it from the
    start for visual_dur. None when no row uses the take, or there are no timings.
    """
    needed = []
    for row in (timings or {}).get("rows", []):
        visual = row.get("visual") or {}
        if visual.get("ref") != ref:
            continue
        trim = visual.get("trim")
        needed.append(trim[1] if trim else row["visual_dur"])
    return max(needed) + margin if needed else None


def is_allowed(method, url, allow):
    """Whether a request may reach the app: reads always; anything else only if `allow` lists it.

    An allow entry is "METHOD /path", matched exactly (trailing slash ignored), or a prefix when it
    ends in "*": "POST /api/search*".
    """
    method = method.upper()
    if method in READ_METHODS:
        return True
    path = urlsplit(url).path.rstrip("/")
    for entry in allow:
        verb, _, pattern = entry.partition(" ")
        if verb.upper() != method:
            continue
        pattern = pattern.strip()
        if pattern.endswith("*") and path.startswith(pattern[:-1]):
            return True
        if path == pattern.rstrip("/"):
            return True
    return False


class Guard:
    """Aborts every request to the app's origin that is not allowed, and keeps the list."""

    def __init__(self, base_url, allow):
        self.origin = urlsplit(base_url).netloc
        self.allow = allow
        self.blocked = []

    async def handle(self, route):
        req = route.request
        if urlsplit(req.url).netloc != self.origin or is_allowed(req.method, req.url, self.allow):
            await route.continue_()
        else:
            self.blocked.append(f"{req.method} {req.url}")
            print(f"BLOCKED {req.method} {req.url}")
            await route.abort("blockedbyclient")


@dataclass
class Args:
    login: bool = False
    video: str = None
    tomas: list = None       # None = every take
    capturas: bool = False
    headed: bool = False


def parse_args(argv):
    """CLI arguments; raises SystemExit with a usage line on anything unexpected."""
    usage = ("usage: grabar.py <course-or-video> --login | grabar.py <video> "
             "[--tomas D1,D3] [--capturas] [--headed]")
    args, rest = Args(), list(argv)
    while rest:
        a = rest.pop(0)
        if a == "--login":
            args.login = True
        elif a == "--capturas":
            args.capturas = True
        elif a == "--headed":
            args.headed = True
        elif a == "--tomas":
            if not rest or rest[0].startswith("--"):
                raise SystemExit(usage)
            args.tomas = [t.strip() for t in rest.pop(0).split(",") if t.strip()]
        elif a.startswith("--") or args.video is not None:
            raise SystemExit(usage)
        else:
            args.video = a
    if args.video is None or (args.login and (args.tomas is not None or args.capturas)):
        raise SystemExit(usage)
    return args


def init_script(blur_selectors=(), local_storage=None):
    """Runs before the app's own scripts on every page: storage values, blur, the drawn cursor."""
    blur_css = (",".join(blur_selectors) + "{filter:blur(6px)!important}") if blur_selectors else ""
    cursor_css = ("#__vt-cursor{position:fixed;left:0;top:0;width:22px;height:30px;"
                  "pointer-events:none;z-index:2147483647;display:none;will-change:transform}")
    return f"""
(() => {{
  try {{
    for (const [k, v] of Object.entries({json.dumps(local_storage or {})})) localStorage.setItem(k, v);
  }} catch (e) {{}}
  const mount = () => {{
    if (document.getElementById('__vt-style')) return;
    const style = document.createElement('style');
    style.id = '__vt-style';
    style.textContent = {json.dumps(blur_css + cursor_css)};
    document.documentElement.appendChild(style);
    const cursor = document.createElement('div');
    cursor.id = '__vt-cursor';
    cursor.innerHTML = {json.dumps(CURSOR_SVG)};
    document.documentElement.appendChild(cursor);
    window.addEventListener('mousemove', (e) => {{
      cursor.style.display = 'block';
      cursor.style.transform = `translate(${{e.clientX}}px, ${{e.clientY}}px)`;
    }}, {{ capture: true, passive: true }});
  }};
  if (document.documentElement) mount();
  else document.addEventListener('DOMContentLoaded', mount);
}})();
"""


# ---- runtime: browser, guard, recorder ------------------------------------------------


def ffmpeg_exe():
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()


def check_reachable(url, timeout=8):
    """Fails fast with a readable message when the host cannot be reached (often a VPN)."""
    try:
        urllib.request.urlopen(urllib.request.Request(url, method="HEAD"), timeout=timeout)
    except urllib.error.HTTPError:
        return  # the server answered: reachable
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise SystemExit(f"{urlsplit(url).netloc} is unreachable ({e}). Is a VPN needed and connected?")


async def open_context(pw, rec, headless, scale=1):
    rec.profile_dir.mkdir(parents=True, exist_ok=True)
    return await pw.chromium.launch_persistent_context(
        str(rec.profile_dir), channel="chrome", headless=headless,
        viewport={"width": rec.width, "height": rec.height}, device_scale_factor=scale,
        color_scheme=rec.color_scheme, args=["--hide-scrollbars"])


class Screencast:
    """Collects CDP screencast frames with their timestamps, acknowledging each one."""

    def __init__(self, cdp, frame_dir, width=1920, height=1080):
        self.cdp, self.frame_dir = cdp, frame_dir
        self.width, self.height = width, height
        self.frames = []          # (path, browser timestamp)
        self.clock_offset = None  # wall clock minus browser clock, from the first frame
        self._acks = set()
        self._stopped = False
        # Decoding and writing ~80 PNGs a second on the event loop would slow the paced helpers.
        self._writer = ThreadPoolExecutor(max_workers=1)

    def _on_frame(self, event):
        if self._stopped:
            return  # frames still in flight when the screencast was stopped
        path = self.frame_dir / f"f{len(self.frames):06d}.png"
        self._writer.submit(lambda data=event["data"]: path.write_bytes(base64.b64decode(data)))
        ts = event["metadata"]["timestamp"]
        if self.clock_offset is None:
            self.clock_offset = time.time() - ts
        self.frames.append((path, ts))
        task = asyncio.ensure_future(
            self.cdp.send("Page.screencastFrameAck", {"sessionId": event["sessionId"]}))
        self._acks.add(task)
        task.add_done_callback(self._acks.discard)

    async def start(self):
        self.cdp.on("Page.screencastFrame", self._on_frame)
        await self.cdp.send("Page.startScreencast", {
            "format": "png", "maxWidth": self.width, "maxHeight": self.height, "everyNthFrame": 1})

    async def stop(self):
        """Stops the screencast; returns the stop time on the browser clock."""
        stop_wall = time.time()
        self._stopped = True
        self.cdp.remove_listener("Page.screencastFrame", self._on_frame)
        await self.cdp.send("Page.stopScreencast")
        if self._acks:
            await asyncio.gather(*self._acks, return_exceptions=True)
        await asyncio.to_thread(self._writer.shutdown, wait=True)
        if not self.frames:
            raise SystemExit("the screencast produced no frames")
        return stop_wall - self.clock_offset


def encode(frames, durations, out, width=1920, height=1080, fps=30):
    """Variable-rate frames to constant-fps h264, through the concat demuxer."""
    listing = frames[0][0].parent / "frames.txt"
    lines = [f"file '{p.as_posix()}'\nduration {d:.6f}\n" for (p, _), d in zip(frames, durations)]
    lines.append(f"file '{frames[-1][0].as_posix()}'\n")  # concat ignores the last duration otherwise
    listing.write_text("".join(lines), encoding="utf-8")
    vf = (f"fps={fps},scale={width}:{height}:force_original_aspect_ratio=decrease,"
          f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,format=yuv420p")
    r = subprocess.run([ffmpeg_exe(), "-y", "-f", "concat", "-safe", "0", "-i", str(listing),
                        "-vf", vf, "-t", f"{sum(durations):.3f}", "-c:v", "libx264",
                        "-preset", "medium", "-crf", "17", "-an", "-movflags", "+faststart",
                        str(out)], capture_output=True)
    if r.returncode != 0:
        raise SystemExit("ffmpeg failed:\n" + r.stderr.decode("utf-8", "replace")[-1500:])


# On-camera annotations share one class, so unhighlight() clears all of them.
_BOX_JS = """([rect, color, width, pad, radius]) => {
  const box = document.createElement('div');
  box.className = '__vt-annotation';
  Object.assign(box.style, {
    position: 'fixed', pointerEvents: 'none', zIndex: 2147483646, boxSizing: 'border-box',
    left: `${rect.left - pad}px`, top: `${rect.top - pad}px`,
    width: `${rect.width + 2 * pad}px`, height: `${rect.height + 2 * pad}px`,
    border: `${width}px solid ${color}`, borderRadius: `${radius}px`,
  });
  document.documentElement.appendChild(box);
}"""

_ARROW_JS = """([rect, side, color, width, length, gap]) => {
  const cx = rect.left + rect.width / 2, cy = rect.top + rect.height / 2;
  const tip = {left: [rect.left - gap, cy], right: [rect.right + gap, cy],
               top: [cx, rect.top - gap], bottom: [cx, rect.bottom + gap]}[side];
  const dir = {left: [-1, 0], right: [1, 0], top: [0, -1], bottom: [0, 1]}[side];
  const tail = [tip[0] + dir[0] * length, tip[1] + dir[1] * length];
  const head = 5 * width, ns = 'http://www.w3.org/2000/svg';
  const svg = document.createElementNS(ns, 'svg');
  svg.setAttribute('class', '__vt-annotation');
  Object.assign(svg.style, {position: 'fixed', left: 0, top: 0, width: '100vw', height: '100vh',
                            pointerEvents: 'none', zIndex: 2147483646, overflow: 'visible'});
  const line = document.createElementNS(ns, 'line');
  const end = [tip[0] + dir[0] * head * 0.8, tip[1] + dir[1] * head * 0.8];
  Object.entries({x1: tail[0], y1: tail[1], x2: end[0], y2: end[1], stroke: color,
                  'stroke-width': width, 'stroke-linecap': 'round'}).forEach(([k, v]) => line.setAttribute(k, v));
  const px = -dir[1], py = dir[0];
  const p = [tip, [tip[0] + dir[0] * head + px * head * 0.6, tip[1] + dir[1] * head + py * head * 0.6],
             [tip[0] + dir[0] * head - px * head * 0.6, tip[1] + dir[1] * head - py * head * 0.6]];
  const poly = document.createElementNS(ns, 'polygon');
  poly.setAttribute('points', p.map(q => q.join(',')).join(' '));
  poly.setAttribute('fill', color);
  svg.append(line, poly);
  document.documentElement.appendChild(svg);
}"""

_SPOTLIGHT_JS = """([rect, pad, radius, dim, fade_s]) => {
  const hole = document.createElement('div');
  hole.className = '__vt-annotation';
  Object.assign(hole.style, {
    position: 'fixed', pointerEvents: 'none', zIndex: 2147483645,
    left: `${rect.left - pad}px`, top: `${rect.top - pad}px`,
    width: `${rect.width + 2 * pad}px`, height: `${rect.height + 2 * pad}px`, borderRadius: `${radius}px`,
    boxShadow: `0 0 0 200vmax rgba(0, 0, 0, ${dim})`, opacity: 0, transition: `opacity ${fade_s}s ease`,
  });
  document.documentElement.appendChild(hole);
  requestAnimationFrame(() => requestAnimationFrame(() => { hole.style.opacity = 1; }));
}"""

_LABEL_JS = """([rect, text, side, color, gap]) => {
  const tag = document.createElement('div');
  tag.className = '__vt-annotation';
  tag.textContent = text;
  Object.assign(tag.style, {
    position: 'fixed', pointerEvents: 'none', zIndex: 2147483646, background: color, color: '#fff',
    font: '600 22px/1.25 system-ui, -apple-system, "Segoe UI", sans-serif', padding: '10px 16px',
    borderRadius: '10px', boxShadow: '0 6px 18px rgba(0,0,0,.25)', maxWidth: '420px', left: 0, top: 0,
  });
  document.documentElement.appendChild(tag);
  const w = tag.offsetWidth, h = tag.offsetHeight;
  const cx = rect.left + rect.width / 2, cy = rect.top + rect.height / 2;
  let [x, y] = {left: [rect.left - gap - w, cy - h / 2], right: [rect.right + gap, cy - h / 2],
                top: [cx - w / 2, rect.top - gap - h], bottom: [cx - w / 2, rect.bottom + gap]}[side];
  x = Math.max(8, Math.min(x, innerWidth - w - 8));
  y = Math.max(8, Math.min(y, innerHeight - h - 8));
  Object.assign(tag.style, {left: `${x}px`, top: `${y}px`});
}"""

_STEP_JS = """([rect, n, side, color, size]) => {
  const badge = document.createElement('div');
  badge.className = '__vt-annotation';
  badge.textContent = n;
  const cx = rect.left + rect.width / 2, cy = rect.top + rect.height / 2, g = 6;
  const [x, y] = {corner: [rect.left - size / 2, rect.top - size / 2], left: [rect.left - size - g, cy - size / 2],
                  right: [rect.right + g, cy - size / 2], top: [cx - size / 2, rect.top - size - g],
                  bottom: [cx - size / 2, rect.bottom + g]}[side];
  Object.assign(badge.style, {
    position: 'fixed', pointerEvents: 'none', zIndex: 2147483646, display: 'grid', placeItems: 'center',
    width: `${size}px`, height: `${size}px`, borderRadius: '50%', background: color, color: '#fff',
    font: `800 ${Math.round(size * 0.55)}px/1 system-ui, -apple-system, "Segoe UI", sans-serif`,
    boxShadow: '0 0 0 3px #fff, 0 4px 12px rgba(0,0,0,.3)',
    left: `${Math.max(4, Math.min(x, innerWidth - size - 4))}px`,
    top: `${Math.max(4, Math.min(y, innerHeight - size - 4))}px`,
  });
  document.documentElement.appendChild(badge);
}"""

# Scales <body> and moves the element toward the middle of the screen, without ever showing
# past the edges of what was on screen. The cursor and annotations live on <html>, so they
# keep their size; boxes drawn after the zoom land on the zoomed elements.
_ZOOM_JS = """([rect, s, duration_s]) => {
  const body = document.body, b = body.getBoundingClientRect(), W = innerWidth, H = innerHeight;
  const clamp = (v, lo, hi) => Math.max(lo, Math.min(v, hi));
  const cx = rect.left + rect.width / 2 - b.left, cy = rect.top + rect.height / 2 - b.top;
  const tx = clamp(W / 2 - b.left - s * cx, W - b.left + s * b.left - s * W, -b.left + s * b.left);
  const ty = clamp(H / 2 - b.top - s * cy, H - b.top + s * b.top - s * H, -b.top + s * b.top);
  body.style.transition = `transform ${duration_s}s ease-in-out`;
  body.style.transformOrigin = '0 0';
  body.style.transform = `translate(${tx}px, ${ty}px) scale(${s})`;
}"""

_RECT_JS = "el => { const r = el.getBoundingClientRect(); return {left: r.left, top: r.top, right: r.right, bottom: r.bottom, width: r.width, height: r.height}; }"


@dataclass
class Toma:
    """What a toma fn drives: the page plus paced, on-camera helpers."""
    page: object
    rec: Rec = None
    screencast: Screencast = None
    _pos: tuple = None
    _frame_dir: Path = None
    started_at: float = None
    log: list = field(default_factory=list)

    def __post_init__(self):
        if self._pos is None:
            w, h = (self.rec.width, self.rec.height) if self.rec else (1920, 1080)
            self._pos = (w / 2, h / 2)

    @property
    def base_url(self):
        return self.rec.base_url if self.rec else ""

    def _loc(self, target):
        return self.page.locator(target) if isinstance(target, str) else target

    async def goto(self, path):
        await self.page.goto(path if path.startswith("http") else self.base_url + path)
        if self.rec and not on_app(self.page.url, self.rec):
            raise SystemExit("the session expired: run  grabar.py <course> --login")
        await self.settle()

    async def settle(self, ready=None):
        """Waits for the network to go quiet, `ready` to show, and animations to finish."""
        try:
            await self.page.wait_for_load_state("networkidle", timeout=15000)
        except Exception:
            pass  # long-lived streams keep the network busy; the explicit waits still apply
        if ready is not None:
            await self._loc(ready).first.wait_for(state="visible", timeout=20000)
        await asyncio.sleep(SETTLE_S)

    async def start(self, ready=None):
        """Starts recording once the page has settled. Idempotent; a no-op for captures."""
        if self.screencast is not None or self._frame_dir is None:
            return
        await self.settle(ready)
        await self.page.mouse.move(*self._pos)
        w, h = (self.rec.width, self.rec.height) if self.rec else (1920, 1080)
        self.screencast = Screencast(await self.page.context.new_cdp_session(self.page), self._frame_dir, w, h)
        await self.screencast.start()
        self.started_at = time.time()

    async def blur_words(self, selector, pattern, px=14):
        """Blurs only the text matching `pattern` (a JS regex source) inside `selector`.

        For a name inside a sentence, where a CSS blur would take the whole element.
        Marks the element __vt-split, so a blur selector can exclude it with :not(.__vt-split).
        """
        await self.page.locator(selector).first.evaluate("""(el, [pattern, px]) => {
          const re = new RegExp(pattern, 'g');
          const walker = document.createTreeWalker(el, NodeFilter.SHOW_TEXT);
          const nodes = [];
          while (walker.nextNode()) nodes.push(walker.currentNode);
          for (const node of nodes) {
            const text = node.textContent, parts = [];
            let last = 0;
            for (const m of text.matchAll(re)) {
              parts.push(document.createTextNode(text.slice(last, m.index)));
              const span = document.createElement('span');
              span.textContent = m[0];
              span.style.filter = `blur(${px}px)`;
              parts.push(span);
              last = m.index + m[0].length;
            }
            if (!parts.length) continue;
            parts.push(document.createTextNode(text.slice(last)));
            node.replaceWith(...parts);
          }
          el.classList.add('__vt-split');
        }""", [pattern, px])

    async def highlight(self, target, color=ANNOTATION_COLOR, width=ANNOTATION_WIDTH, pad=6, radius=10):
        """Draws an unfilled box around one element, on camera. Only where the script asks for one."""
        await self.start()
        rect = await self._loc(target).first.evaluate(_RECT_JS)
        await self.page.evaluate(_BOX_JS, [rect, color, width, pad, radius])

    async def highlight_zone(self, *targets, color=ANNOTATION_COLOR, width=ANNOTATION_WIDTH, pad=6, radius=10):
        """One box around the union of several elements: a whole zone of the page."""
        await self.start()
        rects = [await self._loc(t).first.evaluate(_RECT_JS) for t in targets]
        left, top = min(r["left"] for r in rects), min(r["top"] for r in rects)
        right, bottom = max(r["right"] for r in rects), max(r["bottom"] for r in rects)
        union = {"left": left, "top": top, "width": right - left, "height": bottom - top}
        await self.page.evaluate(_BOX_JS, [union, color, width, pad, radius])

    async def arrow(self, target, side="left", color=ANNOTATION_COLOR, width=ANNOTATION_WIDTH, length=90, gap=10):
        """An arrow pointing at the element from `side` (left, right, top, bottom), on camera."""
        await self.start()
        rect = await self._loc(target).first.evaluate(_RECT_JS)
        await self.page.evaluate(_ARROW_JS, [rect, side, color, width, length, gap])

    async def spotlight(self, target, pad=10, radius=12, dim=0.6, fade_s=0.4):
        """Dims the whole page except one element, on camera."""
        await self.start()
        rect = await self._loc(target).first.evaluate(_RECT_JS)
        await self.page.evaluate(_SPOTLIGHT_JS, [rect, pad, radius, dim, fade_s])

    async def label(self, target, text, side="right", color=ANNOTATION_COLOR, gap=16):
        """A short text tag next to the element (left, right, top, bottom), kept inside the screen."""
        await self.start()
        rect = await self._loc(target).first.evaluate(_RECT_JS)
        await self.page.evaluate(_LABEL_JS, [rect, text, side, color, gap])

    async def steps(self, *targets, start=1, side="corner", color=ANNOTATION_COLOR, size=34):
        """Numbered badges from `start`, on each element's corner or beside it (left, right, top, bottom).

        One call per step reveals them one by one. Beside it suits small text the corner would cover.
        """
        await self.start()
        for n, target in enumerate(targets, start):
            rect = await self._loc(target).first.evaluate(_RECT_JS)
            await self.page.evaluate(_STEP_JS, [rect, n, side, color, size])

    async def zoom_to(self, target, scale=1.6, duration_s=0.8):
        """Zooms the page into the element, on camera. Draw annotations after it, not before."""
        await self.start()
        rect = await self._loc(target).first.evaluate(_RECT_JS)
        await self.page.evaluate(_ZOOM_JS, [rect, scale, duration_s])
        await asyncio.sleep(duration_s)

    async def zoom_out(self, duration_s=0.8):
        """Back to the normal view. Clear annotations drawn while zoomed first (unhighlight)."""
        await self.page.evaluate("d => { document.body.style.transition = `transform ${d}s ease-in-out`;"
                                 " document.body.style.transform = ''; }", duration_s)
        await asyncio.sleep(duration_s)

    async def unhighlight(self):
        """Removes every annotation drawn so far: boxes, arrows, spotlights, labels and step badges."""
        await self.page.evaluate("document.querySelectorAll('.__vt-annotation').forEach(b => b.remove())")

    async def at(self, s):
        """Waits until `s` seconds into the take, to sync an action with the narration.

        Absolute, so a slow page load before it does not push later actions out of sync.
        """
        await self.start()
        delay = self.started_at + s - time.time()
        if delay > 0:
            await asyncio.sleep(delay)
        else:
            print(f"WARNING at({s}): already {-delay:.1f} s late")

    async def wait(self, s):
        await self.start()
        await asyncio.sleep(s)

    async def move_to(self, target, duration_s=0.6):
        """Moves the cursor to the element's center along an eased path.

        While the screencast runs, each step costs a round trip: real paths take ~2x `duration_s`.
        """
        await self.start()
        loc = self._loc(target).first
        await loc.scroll_into_view_if_needed()
        box = await loc.bounding_box()
        if box is None:
            raise SystemExit(f"not visible, cannot move to it: {target}")
        x0, y0 = self._pos
        x1, y1 = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
        steps = max(1, round(duration_s * 60))
        for i in range(1, steps + 1):
            k = i / steps
            k = k * k * (3 - 2 * k)  # smoothstep
            await self.page.mouse.move(x0 + (x1 - x0) * k, y0 + (y1 - y0) * k)
            await asyncio.sleep(duration_s / steps)
        self._pos = (x1, y1)

    async def click(self, target, duration_s=0.6, settle=True):
        await self.move_to(target, duration_s)
        await self.page.mouse.click(*self._pos)
        if settle:
            await asyncio.sleep(SETTLE_S)

    async def hover(self, target, hold_s=1.0, duration_s=0.6):
        await self.move_to(target, duration_s)
        await asyncio.sleep(hold_s)

    async def type_slow(self, target, text, cps=12):
        """Clicks into a field and types at `cps` characters per second (keystrokes slow ~5x on camera)."""
        await self.click(target, settle=False)
        await self.page.keyboard.type(text, delay=1000 / cps)

    async def type_words(self, target, text, word_s=0.16, click=True, lead=""):
        """Types `text` a word at a time: the steady pace keystrokes cannot keep while recording.

        `click=False` types where the caret already is; `lead` goes before the first word.
        """
        if click:
            await self.click(target, settle=False)
        await self.start()
        for k, word in enumerate(text.split(" ")):
            await self.page.keyboard.insert_text((lead if k == 0 else " ") + word)
            await asyncio.sleep(word_s)

    async def scroll(self, px, duration_s=0.8):
        await self.start()
        steps = max(1, round(duration_s * 30))
        for _ in range(steps):
            await self.page.mouse.wheel(0, px / steps)
            await asyncio.sleep(duration_s / steps)


def load_tomas(video_dir):
    path = Path(video_dir) / "tomas.py"
    if not path.exists():
        raise SystemExit(f"missing {path}")
    spec = importlib.util.spec_from_file_location(f"tomas_{abs(hash(str(path)))}", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return getattr(module, "TOMAS", {}), getattr(module, "CAPTURAS", {})


def load_timings(video_dir):
    path = Path(video_dir) / "locucion" / "timings.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


async def record_take(context, rec, ref, fn, out, min_total):
    page = await context.new_page()
    frame_dir = Path(tempfile.mkdtemp(prefix=f"grabar-{ref}-"))
    t = Toma(page, rec, _frame_dir=frame_dir)
    try:
        await fn(t)
        await t.start()                  # a fn with no actions still yields a (held) take
        await asyncio.sleep(END_HOLD_S)  # lets the last action's repaint reach the screencast
        end = await t.screencast.stop()
        durations = frame_durations([ts for _, ts in t.screencast.frames], end, min_total or 0.0, rec.fps)
        out.parent.mkdir(parents=True, exist_ok=True)
        encode(t.screencast.frames, durations, out, rec.width, rec.height, rec.fps)
        n = len(t.screencast.frames)
        active = end - t.screencast.frames[0][1]
        print(f"OK {out.name}  {sum(durations):.1f} s  {n} frames, {n / max(active, 1e-6):.1f} fps captured")
    finally:
        await page.close()
        shutil.rmtree(frame_dir, ignore_errors=True)


async def take_capture(context, rec, name, fn, out):
    page = await context.new_page()
    try:
        t = Toma(page, rec)
        element = await fn(t)  # a capture fn may return a locator to crop the shot to it
        await t.settle()
        await page.evaluate("document.getElementById('__vt-cursor')?.remove()")
        out.parent.mkdir(parents=True, exist_ok=True)
        await (element.first if element is not None else page).screenshot(path=str(out))
        print(f"OK {out.name}")
    finally:
        await page.close()


SIGNIN_PATHS = ("/api/auth/",)   # the app's own sign-in pages (Auth.js): on the app host, but not signed in


def on_app(url, rec):
    """Whether a page has landed on the app itself: its host, not a sign-in host, not its own sign-in page."""
    parts = urlsplit(url)
    if parts.netloc != urlsplit(rec.base_url).netloc or any(sso in parts.netloc for sso in rec.sso_hosts):
        return False
    return not parts.path.startswith(SIGNIN_PATHS)


LOGIN_SETTLED_S = 4      # seconds on the app, without bouncing to SSO, that count as signed in
LOGIN_TIMEOUT_S = 600


async def login(rec):
    """Opens the app for the user to sign in; closes Chrome on its own once they are in.

    Waiting for the user to close the window was fragile: a leftover blank tab kept Chrome alive.
    Closing the context ourselves also flushes the session cookies to the profile.
    """
    from playwright.async_api import async_playwright
    check_reachable(rec.base_url)
    async with async_playwright() as pw:
        context = await open_context(pw, rec, headless=False)
        page = context.pages[0] if context.pages else await context.new_page()
        closed = asyncio.Event()
        context.on("close", lambda _: closed.set())
        await page.goto(rec.base_url)
        print("Sign in in the Chrome window. It closes on its own once you are in the app.")
        settled = 0
        for _ in range(LOGIN_TIMEOUT_S):
            if closed.is_set():
                break
            pages = [p for p in context.pages if not p.is_closed()]
            settled = settled + 1 if pages and any(on_app(p.url, rec) for p in pages) else 0
            if settled >= LOGIN_SETTLED_S:
                await context.close()
                break
            await asyncio.sleep(1)
        else:
            await context.close()
            raise SystemExit(f"no sign-in within {LOGIN_TIMEOUT_S // 60} minutes; run --login again")
    print(f"Signed in. Profile saved in {rec.profile_dir}")


async def record(args, course, rec):
    from playwright.async_api import async_playwright
    video_dir = course.resolve_video(args.video)
    tomas, capturas = load_tomas(video_dir)
    selected = args.tomas if args.tomas is not None else ([] if args.capturas else list(tomas))
    unknown = [r for r in selected if r not in tomas]
    if unknown:
        raise SystemExit(f"not in TOMAS: {', '.join(unknown)}")
    timings = load_timings(video_dir)
    check_reachable(rec.base_url)
    guard = Guard(rec.base_url, rec.allow) if rec.guard else None
    async with async_playwright() as pw:
        # A captures-only run renders at 2x: slides enlarge crops, takes stay at native size.
        scale = 2 if args.capturas and not selected else 1
        context = await open_context(pw, rec, headless=not args.headed, scale=scale)
        await context.add_init_script(init_script(rec.blur_selectors, rec.local_storage))
        if guard:
            await context.route("**/*", guard.handle)
        try:
            for ref in selected:
                target = target_duration(timings, ref)
                if target is None:
                    print(f"WARNING {ref}: no row in timings.json uses it; no minimum length")
                await record_take(context, rec, ref, tomas[ref], video_dir / "grabaciones" / f"{ref}.mp4", target)
            if args.capturas:
                for name, fn in capturas.items():
                    await take_capture(context, rec, name, fn, video_dir / "assets" / "capturas" / f"{name}.png")
        finally:
            await context.close()
    if guard:
        print(f"\n{len(guard.blocked)} request(s) blocked by the write guard" +
              ("".join(f"\n  {line}" for line in guard.blocked) if guard.blocked else "."))


def main(argv=None):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    args = parse_args(sys.argv[1:] if argv is None else argv)
    course = Course.load(args.video)
    rec = Rec.from_course(course)
    asyncio.run(login(rec) if args.login else record(args, course, rec))


if __name__ == "__main__":
    main()
