"""Drawing helpers for the demo animations and stills (WS2, ``imaging/animate.py``).

Fonts, caption bars, the no-data checkerboard, the first-epoch crosshair, a palette shared by every frame of a
GIF and writers that embed the caption text in the file itself (GIF comment, PNG ``Description``), so a file
copied into a deck or video project still says what it shows. Pillow only.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from PIL.PngImagePlugin import PngInfo

CREDIT = "SPHEREx data: NASA/JPL-Caltech/IPAC (IRSA)"

BACKGROUND = (14, 16, 22)  # caption bars and sheet background
TEXT = (236, 238, 242)
MUTED = (168, 174, 188)
ACCENT = (0, 214, 255)  # the first-epoch crosshair (cyan, absent from the grey frames)
CENTRE_TICK = (255, 184, 64)  # field-centre ticks (amber)
CHECKER_LEVELS = (52, 84)  # dark-grey no-data checkerboard, darker than any star
CHECKER_CELL = 3  # output pixels per checkerboard square

TITLE_SIZE = 18
BODY_SIZE = 14
PADDING = 10
LINE_GAP = 4
ANNOTATION_COLORS = (ACCENT, CENTRE_TICK)  # get their own palette entries in a GIF when they are drawn
PALETTE_KMEANS = 3  # k-means refinement passes of the GIF palette (max-coverage start)
MARK_INNER_PX = 3.0  # crosshair/tick arms run from this many grid pixels off the centre...
MARK_OUTER_PX = 6.0  # ...to this many, so the star itself (and a saturated halo) stays visible

# Arial (Windows) and DejaVu/Liberation (Linux) carry the micro sign; Pillow's bundled font is the fallback.
_FONTS = {False: ("arial.ttf", "DejaVuSans.ttf", "LiberationSans-Regular.ttf", "Arial.ttf")}
_FONTS[True] = ("arialbd.ttf", "DejaVuSans-Bold.ttf", "LiberationSans-Bold.ttf", "Arial Bold.ttf")


@dataclass(frozen=True)
class Caption:
    """A bold title plus body lines; ``text`` is what gets embedded in the file."""

    title: str
    lines: tuple[str, ...]

    @property
    def text(self) -> str:
        return "\n".join((self.title, *self.lines))


def plain(text: str) -> str:
    """Characters every caption font can draw (the minus sign of 'WISE 0855−0714' becomes '-')."""
    return text.replace("−", "-").replace("–", "-").replace("′", "'").replace("″", '"')


@lru_cache(maxsize=8)
def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for name in _FONTS[bold]:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    try:
        return ImageFont.load_default(size=size)
    except TypeError:  # Pillow < 10.1 has no scalable default font
        return ImageFont.load_default()


def wrap(text: str, fnt: ImageFont.FreeTypeFont | ImageFont.ImageFont, width: int) -> list[str]:
    """Greedy word wrap of ``text`` to ``width`` pixels (a single over-long word keeps its own line)."""
    lines: list[str] = []
    current = ""
    for word in text.split():
        candidate = f"{current} {word}".strip()
        if current and fnt.getlength(candidate) > width:
            lines.append(current)
            current = word
        else:
            current = candidate
    if current:
        lines.append(current)
    return lines


def _layout(caption: Caption, width: int) -> list[tuple[str, bool]]:
    inner = width - 2 * PADDING
    rows = [(line, True) for line in wrap(caption.title, font(TITLE_SIZE, True), inner)]
    for line in caption.lines:
        rows += [(part, False) for part in wrap(line, font(BODY_SIZE), inner)]
    return rows


def _row_height(bold: bool) -> int:
    return (TITLE_SIZE if bold else BODY_SIZE) + LINE_GAP + (2 if bold else 0)


def caption_height(caption: Caption, width: int) -> int:
    return 2 * PADDING + sum(_row_height(bold) for _, bold in _layout(caption, width))


def caption_bar(caption: Caption, width: int, height: int | None = None) -> Image.Image:
    """The caption drawn on a dark bar ``width`` wide (``height`` lets every frame of a GIF share one size)."""
    bar = Image.new("RGB", (width, height or caption_height(caption, width)), BACKGROUND)
    draw = ImageDraw.Draw(bar)
    y = PADDING
    for line, bold in _layout(caption, width):
        draw.text((PADDING, y), line, fill=TEXT if bold else MUTED, font=font(TITLE_SIZE if bold else BODY_SIZE, bold))
        y += _row_height(bold)
    return bar


def upscale_on_checker(img: Image.Image, scale: int) -> tuple[Image.Image, bool]:
    """Nearest-neighbour ``scale`` x upscale to RGB, transparent (no-data) pixels on a dark-grey checkerboard.

    Returns the image and whether it had any no-data pixel (so the caption can explain the checkerboard).
    """
    rgba = img.convert("RGBA").resize((img.width * scale, img.height * scale), Image.Resampling.NEAREST)
    arr = np.asarray(rgba).astype(np.float32)
    alpha = arr[..., 3:] / 255.0
    yy, xx = np.indices(arr.shape[:2])
    checker = np.where((yy // CHECKER_CELL + xx // CHECKER_CELL) % 2 == 0, *CHECKER_LEVELS).astype(np.float32)
    out = arr[..., :3] * alpha + checker[..., None] * (1.0 - alpha)
    return Image.fromarray(out.round().astype(np.uint8), "RGB"), bool((alpha < 1.0).any())


def _arms(
    img: Image.Image, x: float, y: float, scale: int, directions: Sequence[tuple[int, int]], color: tuple[int, ...]
) -> Image.Image:
    out = img.copy()
    draw = ImageDraw.Draw(out)
    cx, cy = (x + 0.5) * scale, (y + 0.5) * scale
    inner, outer, width = MARK_INNER_PX * scale, MARK_OUTER_PX * scale, max(1, scale // 3)
    for dx, dy in directions:
        draw.line([(cx + dx * inner, cy + dy * inner), (cx + dx * outer, cy + dy * outer)], fill=color, width=width)
    return out


def draw_crosshair(img: Image.Image, x: float, y: float, scale: int) -> Image.Image:
    """A copy of ``img`` with a thin cyan crosshair centred on grid pixel (x, y) (PNG convention, 0-based).

    The four arms leave a gap of ``MARK_INNER_PX`` grid pixels around the centre so the star stays visible.
    """
    return _arms(img, x, y, scale, ((1, 0), (-1, 0), (0, 1), (0, -1)), ACCENT)


def draw_centre_ticks(img: Image.Image, x: float, y: float, scale: int) -> Image.Image:
    """A copy of ``img`` with two amber ticks (left and above) pointing at grid pixel (x, y)."""
    return _arms(img, x, y, scale, ((-1, 0), (0, -1)), CENTRE_TICK)


def stack(images: Sequence[Image.Image], gap: int = 0) -> Image.Image:
    """Images one above the other on the background colour, left-aligned."""
    width = max(im.width for im in images)
    out = Image.new("RGB", (width, sum(im.height for im in images) + gap * (len(images) - 1)), BACKGROUND)
    y = 0
    for im in images:
        out.paste(im, (0, y))
        y += im.height + gap
    return out


def side_by_side(images: Sequence[Image.Image], gap: int) -> Image.Image:
    """Images left to right on the background colour, top-aligned."""
    out = Image.new("RGB", (sum(im.width for im in images) + gap * (len(images) - 1), max(im.height for im in images)))
    out.paste(BACKGROUND, (0, 0, out.width, out.height))
    x = 0
    for im in images:
        out.paste(im, (x, 0))
        x += im.width + gap
    return out


def _has_color(arr: np.ndarray, color: tuple[int, ...]) -> bool:
    return bool(np.all(arr == np.asarray(color, np.uint8), axis=-1).any())


def shared_palette(frames: Sequence[Image.Image]) -> list[Image.Image]:
    """The frames as "P" images on ONE palette (no colour flicker between frames, no dithering noise).

    Max-coverage + k-means palette: on the real false-colour composites median cut was off by up to ~90 levels
    in a channel (99.9th percentile), this by ~30 at most. Annotation colours that are drawn get their own entries
    (a few cyan crosshair pixels are never merged into grey); unused ones take no entry, so no data pixel is ever
    mapped to an annotation colour.
    """
    rgb = [f.convert("RGB") for f in frames]
    arrays = [np.asarray(f) for f in rgb]
    reserved = [c for c in ANNOTATION_COLORS if any(_has_color(a, c) for a in arrays)]
    n_free = 256 - len(reserved)
    quantized = stack(rgb).quantize(colors=n_free, method=Image.Quantize.MAXCOVERAGE, kmeans=PALETTE_KMEANS)
    adaptive = quantized.getpalette() or []
    colors = [c for rgb_color in reserved for c in rgb_color] + list(adaptive[: 3 * n_free])
    palette = Image.new("P", (1, 1))
    palette.putpalette(colors + [0] * (768 - len(colors)))
    return [f.quantize(palette=palette, dither=Image.Dither.NONE) for f in rgb]


def save_gif(path: Path, frames: Sequence[Image.Image], durations_ms: Sequence[int], caption: str) -> int:
    """Looping GIF with ``caption`` as its comment; returns the file size in bytes."""
    if not frames or len(frames) != len(durations_ms):
        raise ValueError("a GIF needs at least one frame and one duration per frame")
    path.parent.mkdir(parents=True, exist_ok=True)
    first, *rest = shared_palette(frames)
    first.save(
        path,
        save_all=True,
        append_images=rest,
        duration=list(durations_ms),
        loop=0,
        disposal=1,
        optimize=False,
        comment=caption.encode("utf-8"),
    )
    return path.stat().st_size


def save_png(path: Path, image: Image.Image, caption: str) -> int:
    """PNG with ``caption`` in its ``Description`` text chunk; returns the file size in bytes."""
    path.parent.mkdir(parents=True, exist_ok=True)
    info = PngInfo()
    info.add_itxt("Description", caption)
    image.save(path, pnginfo=info, optimize=True)
    return path.stat().st_size
