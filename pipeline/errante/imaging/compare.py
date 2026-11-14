"""Season coadds and flux-matched season differences (WS2-7, challenge C02/C03).

Why: the five targets move 1-2 SPHEREx pixels over the whole baseline, which
is hard to see by blinking single exposures. Subtracting an earlier season
from a later one turns a moving star into a +/- DIPOLE (bright where it is
now, dark where it was), while static field stars cancel.

How (per detector, never across detectors):
1. Coadd the frames of each (season, detector) on the common grid. Each frame
   gets ONE weight, 1 / its median VARIANCE (per-pixel weights would include
   the stars' own Poisson noise and bias bright stars low); bad and
   display-repaired pixels (saturated cores, detector defects) are skipped;
   each frame's sky level is removed first. The coadd variance is propagated.
2. Each exposure samples another wavelength (linear variable filter), so a
   static star's flux differs between seasons. ``flux_scale`` fits
   ``late ~ s * early`` on FIELD STARS ONLY: one aperture ratio per star,
   sigma-clipped median, with the target (the field centre) excluded. On a
   real Barnard's Star field a pixel-level fit followed the target's own halo.
3. ``late - s * early``; variance ``var_late + s^2 var_early``.

Limitation: a coadd holds only the field's selected frames (a few per season
and detector), which sample different wavelengths in each season. A target
whose colour differs from the field stars (e.g. a red dwarf) can then leave a
same-sign residual: that is NOT evidence of variability unless the
wavelengths are matched (needs WS1 ``wavelength_at``).

Display products are written by ``compare_field``. ``compare/compare.json``
is PROVISIONAL and not part of the data contract: showing these layers in the
web app needs an additive ``contract:`` PR.
"""

from __future__ import annotations

import json
import math
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
from PIL import Image

from ..detect.difference import StarScale, star_flux_scale
from ..models import FrameRef, SkyField
from .render import field_stretches, save_png

COMPARE_DIR = "compare"
# The target sits at the field centre; its halo must not set the flux scale.
TARGET_EXCLUDE_FRACTION = 0.15  # of the grid size
MIN_TARGET_EXCLUDE_PX = 8.0

LIMITATIONS = [
    "Each coadd uses only the field's selected frames (a few per season and detector); they sample different "
    "wavelengths in each season. A same-sign residual on a star whose colour differs from the field stars "
    "(e.g. a red dwarf) is not evidence of variability unless the wavelengths are matched.",
    "The flux scale is fitted on field stars outside a circle around the field centre (the target); with fewer "
    "than 5 usable stars s = 1 and the difference also shows the wavelength change.",
    "Saturated cores and detector defects carry no valid data (grey checkerboard).",
]


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
    frame_ids: list[str]  # frames that contributed at least one pixel
    mjds: list[float]
    data: np.ndarray
    variance: np.ndarray
    coverage: np.ndarray  # number of frames contributing to each pixel
    skipped: list[str] = field(default_factory=list)  # frames with no usable pixel

    @property
    def id(self) -> str:
        return f"D{self.detector}_S{self.season}"


@dataclass
class Difference:
    late: Coadd
    early: Coadd
    scale: StarScale
    data: np.ndarray
    variance: np.ndarray
    notes: list[str] = field(default_factory=list)

    @property
    def id(self) -> str:
        return f"D{self.late.detector}_S{self.late.season}-S{self.early.season}"

    @property
    def has_overlap(self) -> bool:
        return bool(np.isfinite(self.data).any())


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
    """Weighted mean of ``frames`` (one detector): one weight per frame, sky removed, variance propagated."""
    if not frames:
        raise ValueError("coadd needs at least one frame")
    if len({f.detector for f in frames}) != 1:
        raise ValueError("coadd frames of a single detector only")
    shape = frames[0].data.shape
    total = np.zeros(shape)
    weight = np.zeros(shape)
    var_sum = np.zeros(shape)
    coverage = np.zeros(shape, dtype=np.int16)
    used: list[GridFrame] = []
    skipped: list[str] = []
    for f in frames:
        ok = _usable(f.data, f.bad, f.variance)
        if not ok.any():
            skipped.append(f.frame_id)
            continue
        sky = float(np.median(f.data[ok]))
        if f.variance is not None:
            pixel_var = f.variance
            w = 1.0 / float(np.median(f.variance[ok]))  # background noise of this frame
        else:  # no VARIANCE plane: the frame's own robust noise
            sigma = _robust_sigma(f.data[ok]) or 1.0
            pixel_var = np.full(shape, sigma**2)
            w = 1.0 / sigma**2
        total += np.where(ok, f.data - sky, 0.0) * w
        weight += np.where(ok, w, 0.0)
        var_sum += np.where(ok, pixel_var, 0.0) * w**2
        coverage += ok
        used.append(f)
    with np.errstate(invalid="ignore", divide="ignore"):
        data = np.where(weight > 0, total / weight, np.nan)
        variance = np.where(weight > 0, var_sum / weight**2, np.nan)
    return Coadd(
        detector=frames[0].detector,
        season=season,
        frame_ids=[f.frame_id for f in used],
        mjds=[f.mjd for f in used],
        data=data.astype(np.float32),
        variance=variance.astype(np.float32),
        coverage=coverage,
        skipped=skipped,
    )


def target_exclusion(shape: tuple[int, int]) -> tuple[float, float, float]:
    """(x, y, radius) of the circle around the field centre left out of the flux-scale fit."""
    h, w = shape
    return ((w - 1) / 2, (h - 1) / 2, max(MIN_TARGET_EXCLUDE_PX, TARGET_EXCLUDE_FRACTION * min(h, w)))


def flux_scale(late: Coadd, early: Coadd, exclude: tuple[float, float, float] | None = None) -> StarScale:
    """``s`` with ``late ~ s * early`` from field-star aperture ratios (target excluded)."""
    sigma = float(np.sqrt(np.nanmedian(early.variance))) if np.isfinite(early.variance).any() else float("nan")
    if not math.isfinite(sigma) or sigma <= 0:
        sigma = _robust_sigma(early.data)
    if not math.isfinite(sigma) or sigma <= 0:
        return StarScale(1.0, 0, False)
    exclude = target_exclusion(early.data.shape) if exclude is None else exclude
    return star_flux_scale(late.data.astype(np.float64), early.data.astype(np.float64), sigma, exclude=exclude)


def difference(late: Coadd, early: Coadd) -> Difference:
    """``late - s * early`` with propagated variance (same detector)."""
    if late.detector != early.detector:
        raise ValueError("difference needs coadds of the same detector")
    scale = flux_scale(late, early)
    data = late.data - scale.scale * early.data
    variance = late.variance + scale.scale**2 * early.variance
    diff = Difference(late, early, scale, data.astype(np.float32), variance.astype(np.float32))
    if not diff.has_overlap:
        diff.notes.append("The two seasons share no valid pixel; nothing to compare.")
    elif not scale.fitted:
        diff.notes.append(
            f"Flux scale not fitted (only {scale.n_stars} usable field stars); s = 1, so the wavelength change "
            "between seasons is not corrected."
        )
    return diff


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
    coadds = [coadd(fs, season) for (_, season), fs in sorted(groups.items())]
    coadds = [c for c in coadds if c.frame_ids]  # a season whose frames had no usable pixel
    diffs = []
    for det in sorted({c.detector for c in coadds}):
        mine = sorted((c for c in coadds if c.detector == det), key=lambda c: c.season)
        for i, early in enumerate(mine):
            for late in mine[i + 1 :]:
                diffs.append(difference(late, early))
    return coadds, diffs


def _finite_or_none(x: float) -> float | None:
    return float(x) if math.isfinite(x) else None


def _clear_previous(out: Path) -> None:
    """A re-run must not leave PNGs of coadds/differences that no longer exist."""
    for pattern in ("coadd_*.png", "diff_*.png", "compare.json"):
        for old in out.glob(pattern):
            old.unlink()


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
    _clear_previous(out)
    stretches = field_stretches(
        [c.data for c in coadds], [c.detector for c in coadds], [~np.isfinite(c.data) for c in coadds]
    )
    meta: dict = {
        "format": "errante-compare/0 (provisional; not part of the data contract)",
        "field_id": field.id,
        "field_built_at": field.provenance.built_at.isoformat(),
        "field_frame_ids": [f.id for f in field.frames],
        "built_at": datetime.now(UTC).isoformat(),
        "method": (
            "Per detector: weighted coadd of the field's frames in each season (one weight per frame from its "
            "background variance; sky removed; bad and display-repaired pixels excluded). Difference = later - "
            "s * earlier, with s the sigma-clipped median of field-star aperture ratios (target at the field "
            "centre excluded), which cancels the wavelength change between exposures for typical field stars. "
            "Units MJy/sr (IMAGE - ZODI). A moving star appears as an orange/cyan dipole; static stars cancel."
        ),
        "limitations": LIMITATIONS,
        "colors": {
            "positive": "orange: brighter in the later season",
            "negative": "cyan: brighter in the earlier season",
            "no_data": "grey checkerboard: no valid data (off the cutout or saturated core)",
        },
        "coadds": [],
        "differences": [],
        "skipped": [],
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
                "n_frames": len(c.frame_ids),
                "frame_ids": c.frame_ids,
                "skipped_frame_ids": c.skipped,
                "image": rel,
                "stretch": st.model_dump(),
                "valid_fraction": float(np.isfinite(c.data).mean()),
            }
        )
    for d in diffs:
        if not d.has_overlap:
            meta["skipped"].append({"id": d.id, "reason": d.notes[0]})
            continue
        rel = f"{COMPARE_DIR}/diff_{d.id}.png"
        limit = difference_limit(d)
        Image.fromarray(diverging_rgba(d.data, limit)).save(field_dir / rel, optimize=True)
        meta["differences"].append(
            {
                "id": d.id,
                "detector": d.late.detector,
                "later": d.late.id,
                "earlier": d.early.id,
                "flux_scale": d.scale.scale,
                "flux_scale_fitted": d.scale.fitted,
                "flux_scale_stars": d.scale.n_stars,
                "limit_mjy_sr": limit,
                "noise_mjy_sr": _finite_or_none(float(np.sqrt(np.nanmedian(d.variance)))),
                "image": rel,
                "notes": d.notes,
            }
        )
    (out / "compare.json").write_text(json.dumps(meta, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    return meta


def load_from_cutouts(field: SkyField) -> Callable[[list[FrameRef]], list[GridFrame | None]]:
    """Loader for ``compare_field``: WS1 cutouts (cached) -> reprojected GridFrames."""
    from ..data import cutouts, fits_io
    from .reproject import reproject_to_grid, reproject_variance

    def load(refs: list[FrameRef]) -> list[GridFrame | None]:
        size = field.size_deg * 60 * 1.5  # same cutout size as build_field
        paths = cutouts.fetch_cutouts(refs, field.center.ra, field.center.dec, size_arcmin=size)
        if len(paths) != len(refs):
            raise RuntimeError(f"fetch_cutouts returned {len(paths)} paths for {len(refs)} frames")
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
