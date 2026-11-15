"""Animations and stills of PUBLISHED field products for the demo deck and video (WS2, for WS6).

    python -m errante.imaging.animate --products data/products --out <dir> [--field id] [--detector N]

Per field it writes, from ``fields/<id>/field.json`` and its PNGs only (no FITS, no network):

- ``<id>_blink_D<n>.gif``: the published frames of ONE detector in time order, nearest-neighbour upscaled.
  The detector is the field's entry in ``FIELD_DETECTORS`` (WISE 0855: D5), else the thumbnail's (provenance
  note "thumb.png is a D<n> frame"), else the one with most frames.
  For proper-motion targets a fixed crosshair marks the target position MEASURED in the first frame (a
  centroid of its display grey levels, not a catalog prediction), so the motion shows against it.
- ``<id>_color_detectors.gif`` and ``<id>_color_jhk.gif``: the published false-color season composites.
- ``<id>_compare_D1.png`` and ``.gif``: a two-epoch comparison, for the fields in ``COMPARISON_PAIRS``.
- ``<id>_contact_sheet.png``: every mode on one still, for slides.
- ``animations.json``: what each file shows (frame ids, durations, sizes, caption).

Captions say these are renders of real SPHEREx data and carry the IRSA credit; a synthetic product is captioned
SYNTHETIC DATA instead. No-data pixels are drawn as a dark-grey checkerboard and explained. Pillow only.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from itertools import combinations
from pathlib import Path

import numpy as np
from PIL import Image

from ..build import season_index
from ..models import CompositeChannel, CompositeMode, Frame, SkyField
from ..products import ProductStore
from . import annotate
from .annotate import Caption, plain
from .render import HIGHLIGHT_KNEE, TARGET_RADIUS_PX

SCALE = 6  # 88 px grid -> 528 px
SHEET_SCALE = 3
SHEET_COLUMNS = 6
SHEET_GAP = 10
BLINK_MS = 700
COLOR_MS = 800
COMPARE_MS = 800
MAX_BYTES = 10 * 1024 * 1024
MOTION_TAG = "proper-motion"
# The crosshair is drawn only if the target stands out in the FIRST blink frame's PNG: its brightest valid pixel
# within TARGET_RADIUS_PX of the centre reaches this grey level (217 = 85% of white). Under a highlight roll-off
# that is Stretch.vmax, the field's shared bright end (the knee); under the plain asinh stretch it is ~63% of the
# way from vmin to vmax. One frame, display grey levels only: NOT the thumbnail rule (build._write_thumbnail), which
# takes the median S/N and median prominence (peak / bright end) over every frame of a detector, in MJy/sr.
STANDOUT_GREY = round(HIGHLIGHT_KNEE * 255)
CENTROID_RADIUS_PX = 3.0
CENTROID_ITERATIONS = 5
COMPARISON_DETECTOR = 1
WAVELENGTH_TOLERANCE_UM = 0.01  # fallback comparison pairs this close to the closest wavelength pair qualify
COMPARISON_PAIRS: dict[str, tuple[str, str]] = {"rw-aurigae": ("2025W36_1A_0233_3D1", "2026W37_1A_0234_3D1")}
MODE_LABELS: dict[CompositeMode, str] = {"detectors": "full-range detectors", "jhk": "J/H/Ks-like"}
THUMB_NOTE = re.compile(r"thumb\.png is a D([1-6]) frame")
ROLLOFF_NOTE = re.compile(r"\bD([1-6]): white = vmax \+")  # build._display_note, one per detector with a roll-off
MJD_EPOCH = datetime(1858, 11, 17, tzinfo=UTC)

CROSSHAIR_NOTE = (
    "Cyan crosshair: first-epoch position (target measured in the first frame, not a catalog prediction). "
    "It stays fixed, so the target's motion shows against it."
)
NO_CROSSHAIR_NOTE = (
    "No crosshair: the target does not stand out at the field centre in the first frame at this wavelength "
    "(too faint here, or blended with a field star), so its position could not be measured."
)
WAVELENGTH_NOTE = "Each exposure sees a slightly different wavelength, so brightness can change with it."
CHECKER_NOTE = "Checkerboard: no data."
TICKS_NOTE = "Amber ticks: field centre, the target's catalog position (the field is centred on it)."
FALSE_COLOR_NOTE = "Infrared wavelengths mapped to red, green and blue: not true color."
GIF_PALETTE_NOTE = (
    "Each GIF uses one 256-colour palette: grey frames stay within a few grey levels of the published PNGs, "
    "false-colour frames within a few tens of levels per channel at worst; use the PNGs for exact pixel values."
)
PLAIN_STRETCH = "asinh stretch"
ROLLOFF_STRETCH = "asinh stretch, highlights compressed above vmax"  # a detector listed with "white = vmax + X"
SAME_CONTRAST = "same contrast for every frame of a detector"
COLOR_WHAT = "season composites of IMAGE - ZODI"
SYNTHETIC_NOTE = "SYNTHETIC DATA: simulated frames for development, not SPHEREx observations."


@dataclass(frozen=True)
class DetectorDefault:
    """A field's blink detector, ahead of the thumbnail rule; why; and caption lines for a blink of it."""

    detector: int
    reason: str
    notes: tuple[str, ...]


FIELD_DETECTORS: dict[str, DetectorDefault] = {
    # docs/validation/wise-0855.md: the Y dwarf is seen only in D5/D6 and the centre holds a background star in
    # D1-D4 (where the thumbnail fell back to D1). Per-exposure S/N at its position: 0.8-6.9 over the 12 D5/D6
    # frames of the build analysed there (median 2.1), median 3.6-3.8 over every D5/D6 exposure.
    "wise-0855": DetectorDefault(
        5,
        "where the Y dwarf emits; D1-D4 show a background star at the centre",
        (
            "D5: wavelengths where the Y dwarf emits; at D1-D4 the field centre shows a background star instead.",
            "The target is faint: about 2-5 sigma in a single published frame, so it is hard to see in any one frame.",
        ),
    ),
}


class AnimationError(RuntimeError):
    """An output could not be written within the rules (e.g. over the size limit)."""


@dataclass(frozen=True)
class Output:
    field_id: str
    kind: str  # blink | color_detectors | color_jhk | comparison_png | comparison_gif | contact_sheet
    path: Path
    n_frames: int
    durations_ms: tuple[int, ...]
    width: int
    height: int
    size_bytes: int
    frame_ids: tuple[str, ...]
    caption: str

    def to_json(self) -> dict[str, object]:
        return {
            "field_id": self.field_id,
            "kind": self.kind,
            "file": self.path.name,
            "n_frames": self.n_frames,
            "durations_ms": list(self.durations_ms),
            "width": self.width,
            "height": self.height,
            "size_bytes": self.size_bytes,
            "frame_ids": list(self.frame_ids),
            "caption": self.caption,
        }


@dataclass(frozen=True)
class FieldContext:
    field: SkyField
    field_dir: Path
    detector: int
    reason: str  # why that detector
    frames: tuple[Frame, ...]  # the blink frames, time order
    position: tuple[float, float] | None  # first-epoch target position (grid px, PNG convention)

    @property
    def motion(self) -> bool:
        return MOTION_TAG in self.field.tags

    @property
    def detector_notes(self) -> tuple[str, ...]:
        """The field's ``FIELD_DETECTORS`` caption lines, when the blink shows that detector."""
        default = FIELD_DETECTORS.get(self.field.id)
        return default.notes if default is not None and default.detector == self.detector else ()


# --- selection and measurement -----------------------------------------------------------------------------


def choose_detector(field: SkyField, override: int | None = None) -> tuple[int, str]:
    """(detector, reason): ``override``, else the field's ``FIELD_DETECTORS`` entry (if it has frames there), else
    the thumbnail's detector, else the detector with most frames."""
    counts = Counter(f.detector for f in field.frames)
    if override is not None:
        if not counts[override]:
            raise ValueError(f"{field.id}: no published D{override} frame")
        return override, "chosen by hand"
    default = FIELD_DETECTORS.get(field.id)
    if default is not None and counts[default.detector]:
        return default.detector, default.reason
    for note in field.provenance.notes:
        match = THUMB_NOTE.search(note)
        if match and counts[int(match.group(1))]:
            return int(match.group(1)), "thumbnail detector"
    if not counts:
        raise ValueError(f"{field.id}: no published frame")
    return max(counts, key=lambda d: (counts[d], -d)), "detector with most frames"


def _core_mask(valid: np.ndarray) -> np.ndarray:
    """Valid pixels within ``TARGET_RADIUS_PX`` of the grid centre, where the field puts its target."""
    h, w = valid.shape
    yy, xx = np.indices(valid.shape)
    return valid & (np.hypot(xx - (w - 1) / 2, yy - (h - 1) / 2) <= TARGET_RADIUS_PX)


def measure_target(grey: np.ndarray, valid: np.ndarray) -> tuple[float, float] | None:
    """Centroid (x, y) of the target at the grid centre in display grey levels, or None if it does not stand out.

    Only for drawing a crosshair: the PNG is asinh-stretched, so this is not astrometry. The target must reach
    ``STANDOUT_GREY`` within ``TARGET_RADIUS_PX`` of the centre; a fainter source there may be a field star.
    """
    core = _core_mask(valid)
    if not core.any() or grey[core].max() < STANDOUT_GREY:
        return None
    yy, xx = np.indices(grey.shape)
    sky = float(np.median(grey[valid]))
    iy, ix = np.unravel_index(np.argmax(np.where(core, grey.astype(np.int32), -1)), grey.shape)
    x, y = float(ix), float(iy)
    excess = np.clip(grey.astype(np.float64) - sky, 0.0, None) * valid
    for _ in range(CENTROID_ITERATIONS):
        weights = excess * (np.hypot(xx - x, yy - y) <= CENTROID_RADIUS_PX)
        total = float(weights.sum())
        if total <= 0:
            return None
        x, y = float((weights * xx).sum() / total), float((weights * yy).sum() / total)
    return x, y


def _open(field_dir: Path, rel: str) -> Image.Image:
    path = (field_dir / rel).resolve()
    if not path.is_relative_to(field_dir.resolve()):
        raise ValueError(f"image path {rel!r} points outside {field_dir}")
    with Image.open(path) as im:
        im.load()
        return im.copy()


def _grey_and_valid(img: Image.Image) -> tuple[np.ndarray, np.ndarray]:
    la = np.asarray(img.convert("LA"))
    return la[..., 0], la[..., 1] > 0


def _core_peak(field_dir: Path, frame: Frame) -> float:
    grey, valid = _grey_and_valid(_open(field_dir, frame.image))
    core = _core_mask(valid)
    return float(grey[core].max()) if core.any() else 0.0


def comparison_pair(field: SkyField, field_dir: Path) -> tuple[Frame, Frame] | None:
    """The two D1 frames to compare, for fields in ``COMPARISON_PAIRS`` (None for the others).

    The preferred pair if both frames are published; else, among D1 pairs from different seasons, those within
    ``WAVELENGTH_TOLERANCE_UM`` of the closest wavelength match, and of them the largest change of the target's
    core grey level.
    """
    preferred = COMPARISON_PAIRS.get(field.id)
    if preferred is None:
        return None
    by_id = {f.id: f for f in field.frames}
    if all(fid in by_id for fid in preferred):
        first, second = sorted((by_id[fid] for fid in preferred), key=lambda f: f.mjd)
        return first, second
    d1 = [f for f in field.frames if f.detector == COMPARISON_DETECTOR and f.wavelength_um is not None]
    seasons = dict(zip((f.id for f in d1), season_index([f.mjd for f in d1]), strict=True))
    pairs = [(a, b) for a, b in combinations(d1, 2) if seasons[a.id] != seasons[b.id]]
    if not pairs:
        return None
    gap = {(a.id, b.id): abs(a.wavelength_um - b.wavelength_um) for a, b in pairs}  # type: ignore[operator]
    closest = min(gap.values())
    close = [(a, b) for a, b in pairs if gap[(a.id, b.id)] <= closest + WAVELENGTH_TOLERANCE_UM]
    peaks = {f.id: _core_peak(field_dir, f) for pair in close for f in pair}
    first, second = sorted(max(close, key=lambda p: abs(peaks[p[0].id] - peaks[p[1].id])), key=lambda f: f.mjd)
    return first, second


def field_context(products: Path, field_id: str, detector: int | None = None) -> FieldContext:
    store = ProductStore(products)
    field_dir = store.field_dir(field_id)
    if not (field_dir / "field.json").exists():
        raise FileNotFoundError(f"no published field {field_id!r} under {products}")
    field = store.read_field(field_id)
    det, reason = choose_detector(field, detector)
    frames = tuple(sorted((f for f in field.frames if f.detector == det), key=lambda f: f.mjd))
    position = None
    if MOTION_TAG in field.tags:
        position = measure_target(*_grey_and_valid(_open(field_dir, frames[0].image)))
    return FieldContext(field, field_dir, det, reason, frames, position)


# --- caption text ------------------------------------------------------------------------------------------


def _date(dt: datetime) -> str:
    return f"{dt.astimezone(UTC):%Y-%m-%d %H:%M} UTC"


def _mjd_date(mjd: float) -> str:
    return f"{MJD_EPOCH + timedelta(days=mjd):%Y-%m-%d}"


def _wl(um: float | None, digits: int = 2) -> str:
    return "unknown wavelength" if um is None else f"{um:.{digits}f} µm"


def _title(field: SkyField, what: str) -> str:
    prefix = "SYNTHETIC DATA · " if field.provenance.synthetic else ""
    return plain(f"{prefix}{field.name} · {what}")


def rolloff_detectors(field: SkyField) -> frozenset[int]:
    """Detectors whose PNGs have a highlight roll-off, from the field's display note ("D<n>: white = vmax + X")."""
    return frozenset(int(m.group(1)) for note in field.provenance.notes for m in ROLLOFF_NOTE.finditer(note))


def frames_what(field: SkyField, detectors: Sequence[int]) -> str:
    """What the single-detector frames of ``detectors`` show, with each one's stretch (roll-off or plain asinh)."""
    rolled = rolloff_detectors(field)
    stretch = {d: ROLLOFF_STRETCH if d in rolled else PLAIN_STRETCH for d in sorted(set(detectors))}
    if len(set(stretch.values())) == 1:
        return f"IMAGE - ZODI, {next(iter(stretch.values()))}, {SAME_CONTRAST}"
    per_detector = "; ".join(f"D{d}: {s}" for d, s in stretch.items())
    return f"IMAGE - ZODI ({per_detector}), {SAME_CONTRAST}"


def _data_lines(field: SkyField, what: str) -> tuple[str, ...]:
    if field.provenance.synthetic:
        return (SYNTHETIC_NOTE,)
    scale = f'1 px = {field.grid.pixel_scale_arcsec:.2f}"'
    return (f"Render of real SPHEREx data ({what}); north up, east left; {scale}.", annotate.CREDIT)


def _target_lines(ctx: FieldContext) -> tuple[str, ...]:
    """Caption lines about the target in the blink: the field's detector notes, then the crosshair legend."""
    if not ctx.motion:
        return ctx.detector_notes
    return (*ctx.detector_notes, CROSSHAIR_NOTE if ctx.position is not None else NO_CROSSHAIR_NOTE)


def _frame_line(frame: Frame, digits: int = 2) -> str:
    return f"{_date(frame.date_obs)} (MJD {frame.mjd:.3f}) · wavelength {_wl(frame.wavelength_um, digits)}"


def _capitalized(text: str) -> str:
    return text[:1].upper() + text[1:]


def _channel_text(ch: CompositeChannel) -> str:
    wl = _wl(ch.wavelength_um)
    return f"{ch.color} = D{ch.detector} {wl}" if ch.detector else f"{ch.color} = {wl} (several detectors)"


# --- writers -----------------------------------------------------------------------------------------------


def _with_captions(panels: Sequence[Image.Image], captions: Sequence[Caption]) -> list[Image.Image]:
    """Each panel above its caption bar; all bars share the tallest height so every GIF frame has one size."""
    width = panels[0].width
    height = max(annotate.caption_height(c, width) for c in captions)
    return [annotate.stack([p, annotate.caption_bar(c, width, height)]) for p, c in zip(panels, captions, strict=True)]


def _checked(path: Path, size: int) -> int:
    if size > MAX_BYTES:
        raise AnimationError(f"{path.name} is {size} bytes, over the {MAX_BYTES} byte limit")
    return size


def _gif(
    field_id: str, kind: str, path: Path, images: list[Image.Image], ms: int, ids: Sequence[str], text: str
) -> Output:
    durations = (ms,) * len(images)
    size = _checked(path, annotate.save_gif(path, images, durations, text))
    w, h = images[0].size
    return Output(field_id, kind, path, len(images), durations, w, h, size, tuple(ids), text)


def _png(field_id: str, kind: str, path: Path, image: Image.Image, ids: Sequence[str], text: str) -> Output:
    size = _checked(path, annotate.save_png(path, image, text))
    return Output(field_id, kind, path, 1, (), image.width, image.height, size, tuple(ids), text)


def _panel(ctx: FieldContext, frame: Frame, scale: int, crosshair: bool = True) -> tuple[Image.Image, bool]:
    """The frame upscaled; with the first-epoch crosshair if there is one, else (``crosshair=False``) with ticks
    at the field centre."""
    img, nodata = annotate.upscale_on_checker(_open(ctx.field_dir, frame.image), scale)
    if not crosshair:
        g = ctx.field.grid
        img = annotate.draw_centre_ticks(img, (g.width_px - 1) / 2, (g.height_px - 1) / 2, scale)
    elif ctx.position is not None:
        img = annotate.draw_crosshair(img, *ctx.position, scale)
    return img, nodata


def render_blink(ctx: FieldContext, out: Path) -> Output:
    panels, nodata = zip(*(_panel(ctx, f, SCALE) for f in ctx.frames), strict=True)
    title = _title(ctx.field, f"SPHEREx detector D{ctx.detector}")
    legend = (
        *_target_lines(ctx),
        WAVELENGTH_NOTE,
        *((CHECKER_NOTE,) if any(nodata) else ()),
        *_data_lines(ctx.field, frames_what(ctx.field, [ctx.detector])),
    )
    n = len(ctx.frames)
    lines = [plain(f"{_frame_line(f)} · frame {i}/{n}") for i, f in enumerate(ctx.frames, 1)]
    captions = [Caption(title, (line, *legend)) for line in lines]
    text = "\n".join((title, *lines, *legend))
    path = out / f"{ctx.field.id}_blink_D{ctx.detector}.gif"
    images = _with_captions(panels, captions)
    return _gif(ctx.field.id, "blink", path, images, BLINK_MS, [f.id for f in ctx.frames], text)


def render_color(ctx: FieldContext, out: Path, mode: CompositeMode) -> Output | None:
    comps = sorted((c for c in ctx.field.composites if c.mode == mode), key=lambda c: c.season)
    if not comps:
        return None
    loaded = [annotate.upscale_on_checker(_open(ctx.field_dir, c.image), SCALE) for c in comps]
    title = _title(ctx.field, "False color (infrared)")
    legend = (FALSE_COLOR_NOTE, *((CHECKER_NOTE,) if any(nd for _, nd in loaded) else ()))
    legend += _data_lines(ctx.field, COLOR_WHAT)
    per_comp = [
        (
            f"{_capitalized(MODE_LABELS[mode])}: " + ", ".join(_channel_text(ch) for ch in c.channels),
            f"Observing season S{c.season}: {_mjd_date(c.mjd_min)} to {_mjd_date(c.mjd_max)} (UTC) · {i}/{len(comps)}",
        )
        for i, c in enumerate(comps, 1)
    ]
    captions = [Caption(title, (*lines, *legend)) for lines in per_comp]
    text = "\n".join((title, *(line for lines in per_comp for line in lines), *legend))
    images = _with_captions([img for img, _ in loaded], captions)
    path = out / f"{ctx.field.id}_color_{mode}.gif"
    return _gif(ctx.field.id, f"color_{mode}", path, images, COLOR_MS, [c.id for c in comps], text)


def render_comparison(ctx: FieldContext, out: Path) -> list[Output]:
    pair = comparison_pair(ctx.field, ctx.field_dir)
    if pair is None:
        return []
    loaded = [_panel(ctx, f, SCALE, crosshair=False) for f in pair]
    det = pair[0].detector
    title = _title(ctx.field, f"SPHEREx detector D{det}, two epochs")
    sides = [_frame_line(f, digits=3) for f in pair]
    legend = (
        "Same detector, same contrast and nearly the same wavelength: compare the star at the field centre.",
        TICKS_NOTE,
        *((CHECKER_NOTE,) if any(nd for _, nd in loaded) else ()),
        *_data_lines(ctx.field, frames_what(ctx.field, [det])),
    )
    width = loaded[0][0].width
    labelled = [
        annotate.stack([img, annotate.caption_bar(Caption(f"Epoch {i}", (plain(side),)), width)])
        for i, ((img, _), side) in enumerate(zip(loaded, sides, strict=True), 1)
    ]
    body = annotate.side_by_side(labelled, SHEET_GAP)
    full = Caption(title, (plain(f"Left: {sides[0]}. Right: {sides[1]}."), *legend))
    still = annotate.stack([body, annotate.caption_bar(full, body.width)])
    ids = [f.id for f in pair]
    stem = out / f"{ctx.field.id}_compare_D{det}"
    frames = _with_captions(
        [img for img, _ in loaded],
        [Caption(title, (plain(f"Epoch {i}/2: {s}"), *legend)) for i, s in enumerate(sides, 1)],
    )
    return [
        _png(ctx.field.id, "comparison_png", stem.with_suffix(".png"), still, ids, full.text),
        _gif(ctx.field.id, "comparison_gif", stem.with_suffix(".gif"), frames, COMPARE_MS, ids, full.text),
    ]


# --- contact sheet -----------------------------------------------------------------------------------------


def _tile(image: Image.Image, label: Sequence[str]) -> Image.Image:
    return annotate.stack([image, annotate.caption_bar(Caption("", tuple(plain(x) for x in label)), image.width)])


def _section(heading: str, tiles: Sequence[Image.Image], width: int) -> Image.Image:
    rows = [annotate.side_by_side(tiles[i : i + SHEET_COLUMNS], SHEET_GAP) for i in range(0, len(tiles), SHEET_COLUMNS)]
    bar = annotate.caption_bar(Caption(plain(heading), ()), width)
    return annotate.stack([bar, *rows], SHEET_GAP // 2)


def _sheet_sections(ctx: FieldContext, pair: tuple[Frame, Frame] | None) -> list[tuple[str, list[Image.Image]]]:
    blink = [_tile(_panel(ctx, f, SHEET_SCALE)[0], (_date(f.date_obs), _wl(f.wavelength_um))) for f in ctx.frames]
    sections = [(f"Blink frames · SPHEREx detector D{ctx.detector} ({ctx.reason}) · time order", blink)]
    for mode, label in MODE_LABELS.items():
        comps = sorted((c for c in ctx.field.composites if c.mode == mode), key=lambda c: c.season)
        tiles = [
            _tile(
                annotate.upscale_on_checker(_open(ctx.field_dir, c.image), SHEET_SCALE)[0],
                (f"Season S{c.season}: {_mjd_date(c.mjd_min)} to {_mjd_date(c.mjd_max)}",),
            )
            for c in comps
        ]
        if tiles:
            channels = ", ".join(_channel_text(ch) for ch in comps[0].channels)
            sections.append((f"False color (infrared) · {label} · season S{comps[0].season}: {channels}", tiles))
    if pair is not None:
        tiles = [
            _tile(_panel(ctx, f, SHEET_SCALE, False)[0], (_date(f.date_obs), _wl(f.wavelength_um, 3))) for f in pair
        ]
        sections.append((f"Two-epoch comparison · SPHEREx detector D{pair[0].detector}", tiles))
    return sections


def render_contact_sheet(ctx: FieldContext, out: Path) -> Output:
    pair = comparison_pair(ctx.field, ctx.field_dir)
    sections = _sheet_sections(ctx, pair)
    detectors = [ctx.detector, *(f.detector for f in pair or ())]
    tile_w = ctx.field.grid.width_px * SHEET_SCALE
    columns = min(SHEET_COLUMNS, max(len(tiles) for _, tiles in sections))
    width = columns * tile_w + (columns - 1) * SHEET_GAP
    blocks = [_section(heading, tiles, width) for heading, tiles in sections]
    nodata = any(
        annotate.upscale_on_checker(_open(ctx.field_dir, rel), 1)[1]
        for rel in [f.image for f in ctx.frames] + [c.image for c in ctx.field.composites]
    )
    footer = Caption(
        _title(ctx.field, "SPHEREx contact sheet"),
        (
            *_target_lines(ctx),
            *((TICKS_NOTE,) if pair is not None else ()),
            FALSE_COLOR_NOTE,
            *((CHECKER_NOTE,) if nodata else ()),
            *_data_lines(ctx.field, f"{frames_what(ctx.field, detectors)}; color = {COLOR_WHAT}"),
        ),
    )
    body = annotate.stack([*blocks, annotate.caption_bar(footer, width)], SHEET_GAP)
    margin = Image.new("RGB", (body.width + 2 * SHEET_GAP, body.height + 2 * SHEET_GAP), annotate.BACKGROUND)
    margin.paste(body, (SHEET_GAP, SHEET_GAP))
    text = "\n".join((*(plain(h) for h, _ in sections), footer.text))
    ids = [f.id for f in ctx.frames] + [c.id for c in ctx.field.composites]
    return _png(ctx.field.id, "contact_sheet", out / f"{ctx.field.id}_contact_sheet.png", margin, ids, text)


# --- entry points ------------------------------------------------------------------------------------------


def animate_field(products: Path, field_id: str, out: Path, detector: int | None = None) -> list[Output]:
    """Every animation and still of one published field, written into ``out``."""
    ctx = field_context(Path(products), field_id, detector)
    out = Path(out)
    outputs = [render_blink(ctx, out)]
    outputs += [o for mode in MODE_LABELS if (o := render_color(ctx, out, mode)) is not None]
    outputs += render_comparison(ctx, out)
    outputs.append(render_contact_sheet(ctx, out))
    return outputs


def published_field_ids(products: Path) -> list[str]:
    return sorted(p.parent.name for p in (Path(products) / "fields").glob("*/field.json"))


def write_manifest(out: Path, outputs: Sequence[Output]) -> Path:
    """``animations.json``: every field in ``outputs`` is listed with exactly its new files.

    Older entries of those fields are dropped (e.g. a blink of another detector: its file is left on disk but no
    longer listed). Entries of other fields are kept while their file still exists in ``out``.
    """
    path = Path(out) / "animations.json"
    fields = {o.field_id for o in outputs}
    fresh = {o.path.name for o in outputs}
    kept: list[dict[str, object]] = []
    if path.exists():
        kept = [
            e
            for e in json.loads(path.read_text(encoding="utf-8"))["outputs"]
            if e.get("field_id") not in fields and e["file"] not in fresh and (path.parent / str(e["file"])).is_file()
        ]
    doc = {
        "note": "Renders of published Errante field products: real SPHEREx data unless a caption says SYNTHETIC DATA.",
        "palette_note": GIF_PALETTE_NOTE,
        "credit": annotate.CREDIT,
        "outputs": kept + [o.to_json() for o in outputs],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    return path


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="python -m errante.imaging.animate", description=__doc__.split("\n\n")[0])
    p.add_argument("--products", type=Path, required=True, help="products root (contains fields/<id>/field.json)")
    p.add_argument("--out", type=Path, required=True, help="output directory")
    p.add_argument("--field", action="append", help="field id (repeatable); default: every published field")
    p.add_argument("--detector", type=int, choices=range(1, 7), help="blink detector instead of the default rule")
    return p


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    ids = args.field or published_field_ids(args.products)
    if not ids:
        print(f"error: no published field under {args.products}", file=sys.stderr)
        return 1
    outputs: list[Output] = []
    try:
        for field_id in ids:
            outputs += animate_field(args.products, field_id, args.out, args.detector)
    except (FileNotFoundError, ValueError, AnimationError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    write_manifest(args.out, outputs)
    for o in outputs:
        print(f"{o.path.name}: {o.n_frames} frame(s), {o.width}x{o.height} px, {o.size_bytes / 1024:.0f} KiB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
