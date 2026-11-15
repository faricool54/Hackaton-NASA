"""WS2-8: small PNG figures of the product check, drawn with Pillow (matplotlib is not a pipeline dependency).

- ``track_figure``: per season, the mean of the season's decoded frames (target detectors) around the target,
  with per-frame and per-detector centroids and the expected position; a last panel zooms on the season track.
- ``brightness_figure``: per detector, the target's brightness per frame against the wavelength at the
  target, one colour per season, so a change at matched wavelength shows as a vertical gap. Detectors whose
  target core is white in every frame show the size of the white disc instead (a display-only proxy).

Every figure says on its face that it is a display-level reading of the published PNGs.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from .productcheck_data import LoadedField
from .productcheck_motion import MotionResult
from .productcheck_variable import CoreLevel, VariableResult

DETECTOR_COLORS = {
    1: (68, 119, 170),
    2: (102, 204, 238),
    3: (34, 136, 51),
    4: (204, 187, 68),
    5: (238, 102, 119),
    6: (170, 51, 119),
}  # Paul Tol "bright", colour-blind safe
SEASON_COLORS = [(0, 119, 187), (238, 119, 51), (0, 153, 136), (204, 51, 17), (51, 34, 136), (136, 136, 136)]
EXPECTED_COLOR = (255, 255, 255)
MEASURED_COLOR = (255, 170, 60)
BACKGROUND = (250, 250, 250)
INK = (30, 30, 30)
CROP_HALF = 5  # grid px around the target (11 x 11 px crop)
ZOOM = 26  # figure px per grid px
MIN_TRACK_SPAN_PX = 2.0  # grid px shown across the track panel at least
DISPLAY_SOFTENING = 0.1
DISCLAIMER = "Display-level check on the published 8-bit PNGs (decoded stretch), not science astrometry/photometry."
_ASCII = str.maketrans({"−": "-", "′": "'", "″": '"', "–": "-", "—": "-"})


def _font(size: int) -> ImageFont.ImageFont:
    try:
        return ImageFont.load_default(size=size)
    except (TypeError, OSError):  # Pillow without FreeType
        return ImageFont.load_default()


def _text(s: str) -> str:
    """The default font has no glyph for some typographic characters (e.g. the minus in 'WISE 0855-0714')."""
    return s.translate(_ASCII)


def _ring(d: ImageDraw.ImageDraw, xy: tuple[float, float], r: float, color, width: int = 2) -> None:
    d.ellipse([xy[0] - r, xy[1] - r, xy[0] + r, xy[1] + r], outline=color, width=width)


def _dot(d: ImageDraw.ImageDraw, xy: tuple[float, float], r: float, color) -> None:
    d.ellipse([xy[0] - r, xy[1] - r, xy[0] + r, xy[1] + r], fill=color, outline=(0, 0, 0))


def _cross(d: ImageDraw.ImageDraw, xy: tuple[float, float], r: float, color) -> None:
    for w, c in ((5, (0, 0, 0)), (3, color)):
        d.line([xy[0] - r, xy[1] - r, xy[0] + r, xy[1] + r], fill=c, width=w)
        d.line([xy[0] - r, xy[1] + r, xy[0] + r, xy[1] - r], fill=c, width=w)


def _square(d: ImageDraw.ImageDraw, xy: tuple[float, float], r: float, color) -> None:
    d.rectangle([xy[0] - r, xy[1] - r, xy[0] + r, xy[1] + r], outline=color, width=2)


def _triangle(d: ImageDraw.ImageDraw, xy: tuple[float, float], r: float, color) -> None:
    x, y = xy
    d.polygon([(x, y - r - 1), (x - r, y + r - 1), (x + r, y + r - 1)], outline=color, width=2)


def _swatches(d: ImageDraw.ImageDraw, x: int, y: int, items: list[tuple[str, tuple]], font) -> None:
    for label, color in items:
        _dot(d, (x + 5, y + 7), 5, color)
        d.text((x + 14, y), label, fill=INK, font=font)
        x += 22 + int(d.textlength(label, font=font))


# --- motion -------------------------------------------------------------------------------------------------


def _season_image(loaded: LoadedField, season: int, detectors: tuple[int, ...], x0: int, y0: int) -> Image.Image:
    """Mean stretch fraction of the season's frames (target detectors) on the crop, asinh grey, upscaled."""
    n = 2 * CROP_HALF + 1
    tiles = []
    for f in loaded.frames:
        if f.season != season or f.detector not in detectors or f.meta.stretch is None:
            continue
        s = f.meta.stretch
        tiles.append((f.values[y0 : y0 + n, x0 : x0 + n] - s.vmin) / (s.vmax - s.vmin))
    x = np.nanmean(np.stack(tiles), axis=0) if tiles else np.zeros((n, n))
    x = np.clip(np.nan_to_num(x, nan=0.0), 0.0, 1.0)
    grey = (np.arcsinh(x / DISPLAY_SOFTENING) / np.arcsinh(1.0 / DISPLAY_SOFTENING) * 255).astype(np.uint8)
    return Image.fromarray(grey).convert("RGB").resize((n * ZOOM, n * ZOOM), Image.NEAREST)


def _season_panel(loaded: LoadedField, m: MotionResult, season: int, x0: int, y0: int) -> Image.Image:
    img = _season_image(loaded, season, m.target_detectors, x0, y0)
    d = ImageDraw.Draw(img)

    def to(x: float, y: float) -> tuple[float, float]:
        return (x - x0 + 0.5) * ZOOM, (y - y0 + 0.5) * ZOOM

    for g in m.groups:
        if g.season != season or g.detector not in m.target_detectors:
            continue
        _ring(d, to(*g.expected), 8, (0, 0, 0), width=4)  # dark halo: visible on a white (saturated) core
        _ring(d, to(*g.expected), 8, EXPECTED_COLOR)
        if g.coadd.status == "ok":
            _cross(d, to(g.coadd.x, g.coadd.y), 6, DETECTOR_COLORS.get(g.detector, INK))
    for p in m.frames:
        if p.season != season or p.detector not in m.target_detectors:
            continue
        color = DETECTOR_COLORS.get(p.detector, INK)
        if p.core.status == "ok":
            _dot(d, to(p.core.x, p.core.y), 3, color)
        elif p.plateau is not None:
            _square(d, to(p.plateau.x, p.plateau.y), 4, color)
    return img


def _season_means(m: MotionResult, estimator: str) -> dict[int, tuple[float, float, float, float]]:
    """season -> (measured x, y, expected x, y): means over the target detectors measured in that season."""
    out = {}
    for s in sorted({g.season for g in m.groups}):
        gs = [g for g in m.groups if g.season == s and g.detector in m.target_detectors]
        pos = [(g.position(estimator), g.expected) for g in gs if g.position(estimator) is not None]
        if pos:
            meas = np.mean([p for p, _ in pos], axis=0)
            exp = np.mean([e for _, e in pos], axis=0)
            out[s] = (float(meas[0]), float(meas[1]), float(exp[0]), float(exp[1]))
    return out


def _track_panel(m: MotionResult, estimator: str, size: int, font) -> Image.Image:
    """Season means (measured, orange) and expected positions (white rings) on a 0.5-px grid."""
    img = Image.new("RGB", (size, size), (20, 20, 24))
    d = ImageDraw.Draw(img)
    means = _season_means(m, estimator)
    if not means:
        d.text((10, size // 2), "no season measurable", fill=(230, 230, 230), font=font)
        return img
    pts = np.array([means[s] for s in sorted(means)])
    allxy = np.vstack([pts[:, :2], pts[:, 2:]])
    cx, cy = allxy.mean(axis=0)
    span = max(MIN_TRACK_SPAN_PX, 1.4 * float(np.ptp(allxy, axis=0).max()))
    scale = size / span

    def to(x: float, y: float) -> tuple[float, float]:
        return size / 2 + (x - cx) * scale, size / 2 + (y - cy) * scale

    for k in np.arange(np.floor((cx - span / 2) * 2) / 2, cx + span / 2, 0.5):
        d.line([to(k, cy)[0], 0, to(k, cy)[0], size], fill=(60, 60, 70))
    for k in np.arange(np.floor((cy - span / 2) * 2) / 2, cy + span / 2, 0.5):
        d.line([0, to(cx, k)[1], size, to(cx, k)[1]], fill=(60, 60, 70))
    exp = [to(p[2], p[3]) for p in pts]
    meas = [to(p[0], p[1]) for p in pts]
    if len(pts) > 1:
        d.line(exp, fill=EXPECTED_COLOR, width=1)
        d.line(meas, fill=MEASURED_COLOR, width=2)
    for s, e, q in zip(sorted(means), exp, meas, strict=True):
        _ring(d, e, 6, EXPECTED_COLOR)
        _dot(d, q, 5, MEASURED_COLOR)
        d.text((q[0] + 8, q[1] - 6), f"S{s}", fill=(255, 220, 160), font=font)
    d.text((6, 4), f"season means ({estimator}); grid 0.5 px", fill=(230, 230, 230), font=font)
    return img


TRACK_LEGEND = (
    "white ring = expected position (catalog proper motion, fields.toml; no parallax) | dot = per-frame core "
    "centroid | cross = season x detector coadd centroid | square = white-plateau centroid (clipped core)"
)


def _crop_origin(loaded: LoadedField, m: MotionResult) -> tuple[int, int]:
    """Top-left grid pixel of the crop around the mean expected position."""
    ex = float(np.mean([p.expected[0] for p in m.frames])) if m.frames else loaded.centre_xy[0]
    ey = float(np.mean([p.expected[1] for p in m.frames])) if m.frames else loaded.centre_xy[1]
    h, w = loaded.shape
    x0 = int(np.clip(round(ex) - CROP_HALF, 0, w - 2 * CROP_HALF - 1))
    y0 = int(np.clip(round(ey) - CROP_HALF, 0, h - 2 * CROP_HALF - 1))
    return x0, y0


def _track_legend(d: ImageDraw.ImageDraw, loaded: LoadedField, m: MotionResult, x: int, y: int, font) -> None:
    d.text((x, y), TRACK_LEGEND, fill=INK, font=font)
    scale = (2 * CROP_HALF + 1) * loaded.field.grid.pixel_scale_arcsec
    line = f'crop {2 * CROP_HALF + 1} px = {scale:.0f}", north up, east left; detectors drawn:'
    d.text((x, y + 18), line, fill=INK, font=font)
    drawn = [(f"D{k}", DETECTOR_COLORS[k]) for k in m.target_detectors if k in DETECTOR_COLORS]
    _swatches(d, x + int(d.textlength(line, font=font)) + 8, y + 18, drawn, font)


def track_figure(loaded: LoadedField, m: MotionResult, path: Path) -> str:
    """Season panels + track panel; returns the file name."""
    seasons = sorted({g.season for g in m.groups})
    x0, y0 = _crop_origin(loaded, m)
    panel = (2 * CROP_HALF + 1) * ZOOM
    pad, top = 10, 52
    width = pad + (len(seasons) + 1) * (panel + pad)
    fig = Image.new("RGB", (max(width, 900), top + panel + 100), BACKGROUND)
    d = ImageDraw.Draw(fig)
    big, small = _font(15), _font(12)
    d.text((pad, 6), _text(f"{loaded.field.name}: target centroids on the published PNGs"), fill=INK, font=big)
    d.text((pad, 28), DISCLAIMER, fill=(120, 40, 40), font=small)
    estimator = "core" if any(s.estimator == "core" for s in m.shifts) else "plateau"
    for i, s in enumerate(seasons):
        x = pad + i * (panel + pad)
        fig.paste(_season_panel(loaded, m, s, x0, y0), (x, top))
        n = sum(1 for p in m.frames if p.season == s and p.detector in m.target_detectors)
        d.text((x, top + panel + 4), f"S{s}: mean of {n} frame(s)", fill=INK, font=small)
    fig.paste(_track_panel(m, estimator, panel, small), (pad + len(seasons) * (panel + pad), top))
    _track_legend(d, loaded, m, pad, top + panel + 24, small)
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.save(path, optimize=True)
    return path.name


# --- variability --------------------------------------------------------------------------------------------


def _metric(levels: list[CoreLevel]) -> tuple[str, dict[str, float]]:
    """('sum' | 'disc', frame_id -> y): the r = 3 px sum unless every core is white, then the white-disc area."""
    if any(c.status in ("measured", "measured_at_top") for c in levels):
        return "sum", {c.frame_id: c.aperture.total for c in levels if c.aperture is not None}
    return "disc", {c.frame_id: float(c.plateau_area) for c in levels if c.plateau_area}


def _nice_ticks(vmax: float, n: int = 4) -> list[float]:
    raw = vmax / n if vmax > 0 else 1.0
    mag = 10 ** np.floor(np.log10(raw))
    step = next(m * mag for m in (1, 2, 2.5, 5, 10) if m * mag >= raw)
    return [k * step for k in range(int(vmax // step) + 1)]


def _detector_panel(v: VariableResult, det: int, size: tuple[int, int], fonts, rolloff: bool) -> Image.Image:
    w, h = size
    img = Image.new("RGB", size, (255, 255, 255))
    d = ImageDraw.Draw(img)
    small, tiny = fonts
    box = (52, 24, w - 12, h - 28)
    d.rectangle(box, outline=(150, 150, 150), width=1)
    levels = [c for c in v.levels if c.detector == det and c.wavelength_um]
    metric, ys = _metric(levels)
    what = "r = 3 px sum [MJy/sr px]" if metric == "sum" else "white disc [px] (core white in every frame)"
    d.text((box[0], 4), f"D{det}{' (roll-off)' if rolloff else ''}: {what}", fill=INK, font=small)
    pts = [c for c in levels if c.frame_id in ys]
    if not pts:
        d.text((box[0] + 10, h // 2), "no usable target pixels", fill=INK, font=small)
        return img
    lmin, lmax = min(c.wavelength_um for c in pts), max(c.wavelength_um for c in pts)
    lpad = max(0.05 * (lmax - lmin), 0.005)
    l0, l1 = lmin - lpad, lmax + lpad
    vmax = max(ys.values()) * 1.15

    def to(lam: float, val: float) -> tuple[float, float]:
        return box[0] + (lam - l0) / (l1 - l0) * (box[2] - box[0]), box[3] - val / vmax * (box[3] - box[1])

    for t in _nice_ticks(vmax):
        y = to(l0, t)[1]
        d.line([box[0] - 4, y, box[0], y], fill=(120, 120, 120))
        d.text((6, y - 6), f"{t:g}", fill=INK, font=tiny)
    for lam in (l0 + lpad, l1 - lpad):
        d.text((to(lam, 0)[0] - 14, box[3] + 4), f"{lam:.3f}", fill=INK, font=tiny)
    d.text(((box[0] + box[2]) // 2 - 50, box[3] + 14), "wavelength at the target [um]", fill=(90, 90, 90), font=tiny)
    for p in v.pairs:
        if p.detector == det and p.earlier.frame_id in ys and p.later.frame_id in ys:
            d.line(
                [to(p.earlier.wavelength_um, ys[p.earlier.frame_id]), to(p.later.wavelength_um, ys[p.later.frame_id])],
                fill=(170, 170, 190),
                width=1,
            )
    for c in pts:
        xy = to(c.wavelength_um, ys[c.frame_id])
        color = SEASON_COLORS[c.season % len(SEASON_COLORS)]
        if metric == "sum" and c.lower_bound:
            _triangle(d, xy, 5, color)
        else:
            _dot(d, xy, 4, color)
    return img


def brightness_figure(loaded: LoadedField, v: VariableResult, path: Path) -> str:
    """One panel per detector, brightness against wavelength coloured by season; returns the file name."""
    dets = sorted({c.detector for c in v.levels})
    cols, pw, ph, pad, top = 3, 340, 220, 10, 52
    rows = max(1, (len(dets) + cols - 1) // cols)
    fig = Image.new("RGB", (pad + cols * (pw + pad), top + rows * (ph + pad) + 52), BACKGROUND)
    d = ImageDraw.Draw(fig)
    big, small, tiny = _font(15), _font(12), _font(10)
    d.text(
        (pad, 6), _text(f"{loaded.field.name}: target brightness per frame on the published PNGs"), fill=INK, font=big
    )
    d.text((pad, 28), DISCLAIMER, fill=(120, 40, 40), font=small)
    for i, det in enumerate(dets):
        panel = _detector_panel(v, det, (pw, ph), (small, tiny), det in loaded.rolloff)
        fig.paste(panel, (pad + (i % cols) * (pw + pad), top + (i // cols) * (ph + pad)))
    foot = top + rows * (ph + pad) + 4
    seasons = sorted({c.season for c in v.levels})
    _swatches(d, pad, foot, [(f"S{s}", SEASON_COLORS[s % len(SEASON_COLORS)]) for s in seasons], small)
    d.text(
        (pad, foot + 20),
        "dot = measured | triangle = lower bound (white pixels in the aperture) | grey line = "
        "matched-wavelength pair (|dl|/l <= 1 %): a vertical gap at the same wavelength is a brightness change",
        fill=INK,
        font=small,
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.save(path, optimize=True)
    return path.name
