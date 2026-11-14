"""Season coadds and flux-matched season differences (WS2-7, challenge C02/C03).

Why: the five targets move 1-2 SPHEREx pixels over the whole baseline, which
is hard to see by blinking single exposures. Subtracting an earlier season
from a later one turns a moving star into a +/- DIPOLE (bright where it is
now, dark where it was), while static stars cancel. Variable stars leave a
same-sign residual instead.

How (per detector, never across detectors):
1. Coadd the frames of each (season, detector) on the common grid, weighting
   every pixel by 1/VARIANCE and skipping bad pixels (saturated cores and
   defects that were only repaired for display). Each frame's sky level is
   removed first.
2. Each exposure samples another wavelength (linear variable filter), so a
   static star's flux differs between seasons. ``flux_scale`` fits
   ``late ~ s * early`` on bright, well-measured pixels of the whole field
   (differential photometry: the field stars set ``s``).
3. ``late - s * early``; variance ``var_late + s^2 var_early``.

Display products are written by ``compare_field``. The metadata file
``compare/compare.json`` is PROVISIONAL and not part of the data contract:
showing these layers in the web app needs an additive ``contract:`` PR.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
from PIL import Image

from ..models import FrameRef, SkyField
from .render import field_stretches, save_png

COMPARE_DIR = "compare"
MIN_SCALE_SNR = 20.0  # pixels used to fit the flux scale must be at least this significant
MIN_SCALE_PIXELS = 20


@dataclass(frozen=True)
class GridFrame:
    """One frame already on the field grid (PNG orientation), physical units."""

    frame_id: str
    detector: int
    mjd: float
    data: np.ndarray  # MJy/sr, IMAGE - ZODI
    bad: np.ndarray  # True = do not use
    variance: np.ndarray | None = None  # (MJy/sr)^2


@dataclass
class Coadd:
    detector: int
    season: int
    frame_ids: list[str]
    mjds: list[float]
    data: np.ndarray
    variance: np.ndarray
    coverage: np.ndarray  # number of frames contributing to each pixel

    @property
    def id(self) -> str:
        return f"D{self.detector}_S{self.season}"


@dataclass
class Difference:
    late: Coadd
    early: Coadd
    scale: float
    scale_pixels: int
    data: np.ndarray
    variance: np.ndarray
    notes: list[str] = field(default_factory=list)

    @property
    def id(self) -> str:
        return f"D{self.late.detector}_S{self.late.season}-S{self.early.season}"


def _usable(data: np.ndarray, bad: np.ndarray, variance: np.ndarray | None = None) -> np.ndarray:
    ok = np.isfinite(data) & ~bad
    if variance is not None:
        ok &= np.isfinite(variance) & (variance > 0)
    return ok


def _robust_sigma(values: np.ndarray) -> float:
    values = values[np.isfinite(values)]
    if values.size == 0:
        return float("nan")
    med = np.median(values)
    return float(1.4826 * np.median(np.abs(values - med)))


def coadd(frames: Sequence[GridFrame], season: int = 0) -> Coadd:
    """Inverse-variance weighted mean of ``frames`` (same detector), sky level removed per frame."""
    if not frames:
        raise ValueError("coadd needs at least one frame")
    if len({f.detector for f in frames}) != 1:
        raise ValueError("coadd frames of a single detector only")
    shape = frames[0].data.shape
    total = np.zeros(shape)
    weight = np.zeros(shape)
    coverage = np.zeros(shape, dtype=np.int16)
    for f in frames:
        ok = _usable(f.data, f.bad, f.variance)
        if not ok.any():
            continue
        sky = float(np.median(f.data[ok]))
        if f.variance is not None:
            w = np.where(ok, 1.0 / np.where(ok, f.variance, 1.0), 0.0)
        else:  # no VARIANCE plane: one weight per frame from its own noise
            sigma = _robust_sigma(f.data[ok]) or 1.0
            w = np.where(ok, 1.0 / sigma**2, 0.0)
        total += np.where(ok, f.data - sky, 0.0) * w
        weight += w
        coverage += ok
    with np.errstate(invalid="ignore", divide="ignore"):
        data = np.where(weight > 0, total / weight, np.nan)
        variance = np.where(weight > 0, 1.0 / weight, np.nan)
    return Coadd(
        detector=frames[0].detector,
        season=season,
        frame_ids=[f.frame_id for f in frames],
        mjds=[f.mjd for f in frames],
        data=data.astype(np.float32),
        variance=variance.astype(np.float32),
        coverage=coverage,
    )


def flux_scale(late: Coadd, early: Coadd, min_snr: float = MIN_SCALE_SNR) -> tuple[float, int]:
    """Robust ``s`` with ``late ~ s * early`` on bright, well-measured pixels of both coadds.

    Returns (s, number of pixels used); (1.0, n) when fewer than
    ``MIN_SCALE_PIXELS`` pixels qualify.
    """
    a, b = late.data, early.data
    ok = np.isfinite(a) & np.isfinite(b) & np.isfinite(early.variance) & (early.variance > 0)
    with np.errstate(invalid="ignore", divide="ignore"):
        snr_b = np.where(ok, b / np.sqrt(np.where(ok, early.variance, 1.0)), 0.0)
        snr_a = np.where(ok, a / np.sqrt(np.where(ok, late.variance, 1.0)), 0.0)
    use = ok & (snr_b >= min_snr) & (snr_a >= min_snr)
    n = int(use.sum())
    if n < MIN_SCALE_PIXELS:
        return 1.0, n
    return float(np.median(a[use] / b[use])), n


def difference(late: Coadd, early: Coadd) -> Difference:
    """``late - s * early`` with propagated variance (same detector)."""
    if late.detector != early.detector:
        raise ValueError("difference needs coadds of the same detector")
    s, n = flux_scale(late, early)
    notes = []
    if n < MIN_SCALE_PIXELS:
        notes.append(f"Flux scale not fitted (only {n} bright pixels); s = 1.")
    data = late.data - s * early.data
    variance = late.variance + s**2 * early.variance
    return Difference(late, early, s, n, data.astype(np.float32), variance.astype(np.float32), notes)


def diverging_rgba(data: np.ndarray, limit: float, softening: float = 0.05) -> np.ndarray:
    """Signed asinh map: black = no change, ORANGE = brighter now, CYAN = brighter before.

    NaN (no valid data in a season: off the cutout, or a saturated core that
    was only repaired for display) is drawn as a grey CHECKERBOARD, not black,
    because black means "no change" in this map.
    """
    x = np.clip(np.nan_to_num(data / limit, nan=0.0), -1.0, 1.0)
    v = np.arcsinh(np.abs(x) / softening) / np.arcsinh(1.0 / softening)
    pos = x > 0
    rgba = np.zeros((*data.shape, 4), dtype=np.uint8)
    rgba[..., 0] = np.where(pos, 255 * v, 40 * v).round()
    rgba[..., 1] = np.where(pos, 150 * v, 200 * v).round()
    rgba[..., 2] = np.where(pos, 30 * v, 255 * v).round()
    nodata = ~np.isfinite(data)
    yy, xx = np.indices(data.shape)
    checker = np.where((yy // 2 + xx // 2) % 2 == 0, 70, 110).astype(np.uint8)
    for ch in range(3):
        rgba[..., ch] = np.where(nodata, checker, rgba[..., ch])
    rgba[..., 3] = 255
    return rgba


def difference_limit(diff: Difference, nsigma: float = 10.0, pct: float = 99.9) -> float:
    """Colour range: the brightest residuals (movers) or ``nsigma`` x the noise, whichever is larger."""
    ok = np.isfinite(diff.data)
    if not ok.any():
        return 1.0
    sigma = _robust_sigma(diff.data[ok])
    bright = float(np.percentile(np.abs(diff.data[ok]), pct))
    return max(bright, nsigma * sigma, 1e-6)


def build_comparisons(
    frames: Sequence[GridFrame], season_of: Callable[[float], int]
) -> tuple[list[Coadd], list[Difference]]:
    """Coadds per (season, detector) and, per detector, every later-minus-earlier season pair."""
    groups: dict[tuple[int, int], list[GridFrame]] = {}
    for f in frames:
        groups.setdefault((f.detector, season_of(f.mjd)), []).append(f)
    coadds = [coadd(fs, season) for (det, season), fs in sorted(groups.items())]
    diffs = []
    for det in sorted({c.detector for c in coadds}):
        mine = sorted((c for c in coadds if c.detector == det), key=lambda c: c.season)
        for i, early in enumerate(mine):
            for late in mine[i + 1 :]:
                diffs.append(difference(late, early))
    return coadds, diffs


def compare_field(
    field: SkyField,
    field_dir: Path,
    load: Callable[[list[FrameRef]], list[GridFrame | None]],
) -> dict:
    """Write season coadds + differences of ``field`` under ``field_dir/compare``; return the metadata.

    ``load`` turns the field's frames (as FrameRefs) into GridFrames, e.g. by
    fetching the cached cutouts and reprojecting them (see the CLI command).
    """
    from ..build import season_index

    refs = [
        FrameRef(obs_id=f.obs_id, detector=f.detector, mjd=f.mjd, release=f.release, irsa_uri=f.source_uri)
        for f in field.frames
    ]
    loaded = [g for g in load(refs) if g is not None]
    if not loaded:
        raise ValueError(f"No frame of field '{field.id}' could be loaded for comparison")
    mjds = [f.mjd for f in field.frames]
    seasons = dict(zip(mjds, season_index(mjds), strict=True))
    coadds, diffs = build_comparisons(loaded, lambda mjd: seasons[mjd])

    out = field_dir / COMPARE_DIR
    out.mkdir(parents=True, exist_ok=True)
    stretches = field_stretches(
        [c.data for c in coadds], [c.detector for c in coadds], [~np.isfinite(c.data) for c in coadds]
    )
    meta = {
        "format": "errante-compare/0 (provisional; not part of the data contract)",
        "field_id": field.id,
        "built_at": datetime.now(UTC).isoformat(),
        "method": (
            "Per detector: inverse-variance coadd of the field's frames in each season (sky level removed, bad "
            "and display-repaired pixels excluded); difference = later - s * earlier, with s fitted on bright "
            "pixels of the whole field to cancel the wavelength change between exposures. Units MJy/sr "
            "(IMAGE - ZODI). Moving stars appear as an orange/cyan dipole; static stars cancel."
        ),
        "colors": {
            "positive": "orange: brighter in the later season",
            "negative": "cyan: brighter in the earlier season",
            "no_data": "grey checkerboard: no valid data (off the cutout or saturated core)",
        },
        "coadds": [],
        "differences": [],
    }
    for c, st in zip(coadds, stretches, strict=True):
        rel = f"{COMPARE_DIR}/coadd_{c.id}.png"
        save_png(c.data, field_dir / rel, st)
        meta["coadds"].append(
            {
                "id": c.id,
                "detector": c.detector,
                "season": c.season,
                "mjd_min": min(c.mjds),
                "mjd_max": max(c.mjds),
                "frame_ids": c.frame_ids,
                "image": rel,
                "stretch": st.model_dump(),
                "valid_fraction": float(np.isfinite(c.data).mean()),
            }
        )
    for d in diffs:
        rel = f"{COMPARE_DIR}/diff_{d.id}.png"
        limit = difference_limit(d)
        Image.fromarray(diverging_rgba(d.data, limit)).save(field_dir / rel, optimize=True)
        meta["differences"].append(
            {
                "id": d.id,
                "detector": d.late.detector,
                "later": d.late.id,
                "earlier": d.early.id,
                "flux_scale": d.scale,
                "flux_scale_pixels": d.scale_pixels,
                "limit_mjy_sr": limit,
                "noise_mjy_sr": float(np.sqrt(np.nanmedian(d.variance))),
                "image": rel,
                "notes": d.notes,
            }
        )
    (out / "compare.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    return meta


def load_from_cutouts(field: SkyField) -> Callable[[list[FrameRef]], list[GridFrame | None]]:
    """Loader for ``compare_field``: WS1 cutouts (cached) -> reprojected GridFrames."""
    from ..data import cutouts, fits_io
    from .reproject import reproject_to_grid, reproject_variance

    def load(refs: list[FrameRef]) -> list[GridFrame | None]:
        size = field.size_deg * 60 * 1.5  # same cutout size as build_field
        paths = cutouts.fetch_cutouts(refs, field.center.ra, field.center.dec, size_arcmin=size)
        out: list[GridFrame | None] = []
        for ref, path in zip(refs, paths, strict=True):
            if path is None:
                out.append(None)
                continue
            img = fits_io.read_spherex(path)
            data, bad = reproject_to_grid(img, field.grid)
            frame_id = f"{ref.obs_id}D{ref.detector}"
            out.append(GridFrame(frame_id, ref.detector, ref.mjd, data, bad, reproject_variance(img, field.grid)))
        return out

    return load
