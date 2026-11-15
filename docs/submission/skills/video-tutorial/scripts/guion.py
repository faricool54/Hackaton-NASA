# Parses the montage sheet of a script: one row = one narration phrase + one visual.
# The table sits under a "## Hoja de montaje" or "## Montage sheet" heading. Its third
# cell holds exactly one visual: "Slide N" or "D2", with an optional "[m:ss-m:ss]" trim
# for demo takes. A video folder holds versioned scripts (guion-vN.md or script-vN.md);
# the one in use says "vigente: true" (or "current: true") in its frontmatter.

import re
from dataclasses import dataclass
from pathlib import Path

SHEET_HEADINGS = ("Hoja de montaje", "Montage sheet")
SCRIPT_GLOBS = ("guion-v*.md", "script-v*.md")
CURRENT_RE = re.compile(r"^(vigente|current):\s*true\s*$", re.MULTILINE)
SPEED_KEYS = ("velocidad", "speed")   # a per-video narration rate in the frontmatter, e.g. '+5%'

PAUSE_RE = re.compile(r"\b(\d+(?:[.,]\d+)?)s\b")
MAX_PAUSE_S = 9.9   # longer "Ns" tokens are words ("1990s", "los 90s"), not pauses
SLIDE_RE = re.compile(r"\bSlide\s+(\d+)\b")
DEMO_RE = re.compile(r"\bD(\d+[a-z]?)\b")
TRIM_RE = re.compile(r"\[(\d+:\d+(?:\.\d+)?)\s*[-–]\s*(\d+:\d+(?:\.\d+)?)\]")


@dataclass
class Visual:
    kind: str            # "slide" | "demo"
    ref: str             # slide number ("3") or take id ("D3a")
    trim: tuple = None   # demo only: (start_s, end_s) window inside the take
    zoom: bool = False   # slide only: slow zoom, only when the cell says "zoom"


@dataclass
class Row:
    num: int
    locucion: str        # cleaned narration text
    parts: list          # [(text, pause_after_s), ...] split on inline pause marks
    visual: Visual


def find_vigente(video_dir):
    """The script marked vigente: true (or current: true) -- exactly one per video folder."""
    scripts = sorted(p for pattern in SCRIPT_GLOBS for p in Path(video_dir).glob(pattern))
    current = [p for p in scripts if CURRENT_RE.search(p.read_text(encoding="utf-8"))]
    if len(current) != 1:
        raise SystemExit(f"expected exactly one script with vigente: true in {Path(video_dir).name}, "
                         f"found {len(current)}")
    return current[0]


def parse_montage(guion_path):
    """Rows of the hoja de montaje, in order."""
    rows, in_table = [], False
    for line in guion_path.read_text(encoding="utf-8").split("\n"):
        if line.lstrip().startswith("#"):
            in_table = any(h in line for h in SHEET_HEADINGS)
            continue
        if not in_table or not line.strip().startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 6 or not cells[0].isdigit():
            continue  # header, separator or a foreign table
        num = int(cells[0])
        locucion = _clean(cells[1])
        parts = split_pauses(locucion)
        if not parts:
            raise SystemExit(f"row {num}: empty locucion")
        rows.append(Row(num, locucion, parts, _parse_visual(cells[2], num)))
    if not rows:
        raise SystemExit(f"no montage sheet found in {guion_path.name}")
    return rows


def frontmatter_value(guion_path, key, default=None):
    """A scalar from the guion's YAML frontmatter (quotes stripped), or `default` when absent."""
    text = Path(guion_path).read_text(encoding="utf-8")
    m = re.match(r"---\n(.*?)\n---", text, re.DOTALL)
    if m:
        for line in m.group(1).split("\n"):
            k, sep, v = line.partition(":")
            if sep and k.strip() == key:
                return v.strip().strip("'\"") or default
    return default


def video_rate(guion_path, default):
    """The narration rate of one video: its frontmatter speed when set, else the course's."""
    for key in SPEED_KEYS:
        value = frontmatter_value(guion_path, key)
        if value:
            return value
    return default


def flag_value(args, flag, default=None):
    if flag in args:
        i = args.index(flag)
        if i + 1 < len(args):
            return args[i + 1]
    return default


def _clean(text):
    """Strips markdown emphasis so TTS never reads asterisks or backticks."""
    text = re.sub(r"\*+([^*]+)\*+", r"\1", text)
    text = text.replace("`", "")
    return re.sub(r"\s+", " ", text).strip()


def split_pauses(locucion):
    """Splits on inline pause markers (0.2s / 0.3s), keeping each pause length.

    A pause with no text before it (a leading pause, or a row that is only a pause) becomes a
    ("", seconds) part: the row holds its visual in silence for that long. "Ns" tokens longer
    than MAX_PAUSE_S are left in the text, so "1990s" is read, not waited.
    """
    parts, last = [], 0
    for m in PAUSE_RE.finditer(locucion):
        pause = float(m.group(1).replace(",", "."))
        if pause > MAX_PAUSE_S:
            continue
        parts.append((locucion[last:m.start()].strip(), pause))
        last = m.end()
    tail = locucion[last:].strip()
    if tail:
        parts.append((tail, 0.0))
    return parts


def _parse_visual(cell, num):
    tokens = [(m.start(), "slide", m.group(1)) for m in SLIDE_RE.finditer(cell)]
    tokens += [(m.start(), "demo", "D" + m.group(1)) for m in DEMO_RE.finditer(cell)]
    if not tokens:
        raise SystemExit(f"row {num}: no visual in its visual cell: {cell!r}")
    tokens.sort()
    if len(tokens) > 1:
        print(f"WARNING row {num}: more than one visual in its visual cell; using the first")
    _, kind, ref = tokens[0]
    trim = None
    if kind == "demo":
        m = TRIM_RE.search(cell)
        trim = (_ts(m.group(1)), _ts(m.group(2))) if m else None   # none: the take plays from its start
    zoom = kind == "slide" and re.search(r"\bzoom\b", cell, re.IGNORECASE) is not None
    return Visual(kind, ref, trim, zoom)


def _ts(ts):
    m, s = ts.split(":")
    return int(m) * 60 + float(s)
