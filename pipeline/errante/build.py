"""Build a viewable SPHEREx field, then optionally run automatic analysis.

Images and metadata are the challenge's core deliverable. Detection and catalog
matching must not block that deliverable. Use ``errante build <id> --analyze``
to opt into those stages; the image products survive an analysis failure.
"""

from __future__ import annotations

import dataclasses
import logging
import shutil
import tomllib
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from itertools import count
from pathlib import Path
from typing import Any, TypeVar

import numpy as np

from . import __version__, settings
from .models import CandidateList, Composite, Frame, FrameRef, KnownObjectList, Provenance, SkyCoord, SkyField
from .products import ProductStore

log = logging.getLogger(__name__)

FIELDS_TOML = Path(__file__).parent / "config" / "fields.toml"

# SPHEREx revisits a position in blocks of days to weeks, ~6 months apart
# (docs/DATA.md §3.0: "temporadas = bloques separados > 30 días").
SEASON_GAP_DAYS = 30.0
# Near the ecliptic poles coverage is almost continuous (R Draconis: one
# 394-day block). Cap a "season" so frame selection samples the whole span;
# the all-sky seasons of the five targets last 19-55 days and stay whole.
MAX_SEASON_DAYS = 60.0
# When the same exposure is listed in several releases, keep the most final one.
RELEASE_PREFERENCE = {"dr1": 0, "qr3": 1, "qr2": 2, "synthetic": 3}
# Frames whose reprojected grid is mostly empty (target near a detector edge)
# are left out of the blink (they are replaced by another frame if possible).
MIN_FINITE_FRACTION = 0.5
# The wavelength a frame sees at the target (linear variable filter) is only
# known once the file is read (WCS-WAVE), so the build downloads up to
# POOL_FACTOR x max_frames candidates and keeps the best-matching max_frames.
POOL_FACTOR = 2
# A frame whose IMAGE - ZODI robust scatter (1.4826 * MAD) exceeds this many
# times the noise its VARIANCE plane predicts carries a background artefact.
# Measured 2026-11-14 on the 200 golden frames of the five targets (40 each,
# 13.5' cutouts): good frames 1.04-8.6x (median 1.9x, 99th percentile 8.6x,
# the worst being R Draconis' own saturated halo in D1); the two frames with a
# large background step were 19.6x (WISE 0855, 2025W19_1B_0241_4D1) and 45.5x
# (eps Indi B, 2025W17_4B_0468_1D1).
MAX_NOISE_RATIO = 15.0
MAD_TO_SIGMA = 1.4826
DOWNLOAD_FAILED = "download failed"
OUTSIDE_CUTOUT = "target outside the cutout"
BAD_FRAME = "bad frame"
# A frame whose field stars sit more than imaging.register.MAX_OFFSET_PX (0.5 px) from their position in the
# other frames of its detector has a wrong archive WCS: the blink would show a false jump of the whole field.
# Measured 2026-11-14 on the 1460 vetted candidates of the seven configured fields: good frames 0.00-0.19 px
# (median 0.03 px); the one outlier is 2026W38_1A_0162_3D6 (RW Aurigae) at 1.34 px, the WCS error that
# docs/validation/rw-aurigae.md found against Gaia (-1.21 to -1.36 px in x).
MISREGISTERED = "misregistered frame"

GroupKey = tuple[int, int]  # (season, detector)
_T = TypeVar("_T")


@dataclass
class FieldConfig:
    id: str
    name: str
    ra: float
    dec: float
    size_deg: float = 0.25
    description: str = ""
    tags: list[str] = field(default_factory=list)
    detectors: list[int] | None = None
    mjd_min: float | None = None
    mjd_max: float | None = None
    max_frames: int = 40
    track_object: str | None = None  # JPL designation: re-center on its ephemeris (WS3)


def load_field_configs(path: Path = FIELDS_TOML) -> dict[str, FieldConfig]:
    raw = tomllib.loads(path.read_text(encoding="utf-8"))
    return {f["id"]: FieldConfig(**f) for f in raw.get("field", [])}


def apply_overrides(cfg: FieldConfig, overrides: Mapping[str, Any] | None) -> tuple[FieldConfig, str | None]:
    """``cfg`` with ``overrides`` applied (e.g. from ``errante build --max-frames``) and a provenance note.

    Returns ``(cfg, None)`` unchanged when there is nothing to override. Unknown keys raise ``ValueError``.
    """
    if not overrides:
        return cfg, None
    known = {f.name for f in dataclasses.fields(FieldConfig)}
    unknown = sorted(set(overrides) - known)
    if unknown:
        raise ValueError(f"Unknown FieldConfig override(s): {unknown}")

    def shown(value: Any) -> str:
        return "all" if value is None else str(value)

    changes = ", ".join(f"{k}={shown(v)} (fields.toml: {shown(getattr(cfg, k))})" for k, v in sorted(overrides.items()))
    return dataclasses.replace(cfg, **overrides), f"Built with overrides: {changes}."


def season_index(
    mjds: list[float], gap_days: float = SEASON_GAP_DAYS, max_span_days: float = MAX_SEASON_DAYS
) -> list[int]:
    """0-based season of each MJD.

    A new season starts after a gap > ``gap_days`` or once the current season
    already spans more than ``max_span_days`` (continuous deep-field coverage
    becomes consecutive ~2-month bins).
    """
    order = sorted(range(len(mjds)), key=lambda i: mjds[i])
    seasons = [0] * len(mjds)
    current, start, prev = 0, None, None
    for i in order:
        if prev is not None and (mjds[i] - prev > gap_days or mjds[i] - start > max_span_days):
            current += 1
            start = None
        if start is None:
            start = mjds[i]
        seasons[i] = current
        prev = mjds[i]
    return seasons


def _reference_wavelength(
    by_season: Mapping[int, Sequence[float | None]], per_season: Mapping[int, int] | None = None
) -> float | None:
    """Wavelength that every season can match best (minimises the summed mismatch).

    ``by_season`` maps a season to the wavelengths of its frames (None = unknown). ``per_season`` says
    how many frames each season will show (default 1): a season's mismatch is summed over its that-many
    closest frames, so a reference that only one frame per season can match does not win when two or
    three are shown (real eps Indi B pool: D3 spread 651 -> 525 nm, D6 477 -> 405 nm).
    """
    known = {s: [w for w in ws if w is not None] for s, ws in by_season.items()}
    candidates = sorted({w for ws in known.values() for w in ws})
    if not candidates:
        return None
    take = per_season or {}

    def mismatch(c: float) -> float:
        return sum(sum(sorted(abs(w - c) for w in ws)[: take.get(s, 1)]) for s, ws in known.items())

    return min(candidates, key=mismatch)


def _rank(
    wavelength: float | None, target: float | None, mjd: float, mid: float, obs_id: str
) -> tuple[float, float, str]:
    """Sort key inside a (season, detector) group: wavelength match, then season middle; unknown last."""
    dw = abs(wavelength - target) if target is not None and wavelength is not None else np.inf
    return (dw, abs(mjd - mid), obs_id)


def _middle(mjds: Sequence[float]) -> float:
    return (min(mjds) + max(mjds)) / 2


def _group_order(keys: Sequence[GroupKey]) -> list[GroupKey]:
    """Group visiting order: detectors covering more seasons first, then by detector and season."""
    n_seasons: dict[int, int] = defaultdict(int)
    for _, detector in keys:
        n_seasons[detector] += 1
    return sorted(keys, key=lambda k: (-n_seasons[k[1]], k[1], k[0]))


def plan_frames(
    refs: list[FrameRef], gap_days: float = SEASON_GAP_DAYS
) -> tuple[dict[GroupKey, list[FrameRef]], list[GroupKey]]:
    """Rank every candidate frame inside its (season, detector) group.

    Returns ``(ranked, order)``: ``ranked[key]`` best-first, and ``order`` the
    group visiting order (detectors covering more seasons first). Duplicate
    exposures (same obs_id + detector in several releases) keep the most final
    release. Inside a group, frames closest to a per-detector reference
    wavelength come first (each exposure sees another wavelength through the
    linear variable filter, so a star changes brightness without being
    variable: docs/SCIENCE.md §0.4); without wavelengths, frames nearest the
    middle of the season come first.
    """
    unique: dict[tuple[str, int], FrameRef] = {}
    for ref in refs:
        key = (ref.obs_id, ref.detector)
        kept = unique.get(key)
        if kept is None or RELEASE_PREFERENCE.get(ref.release, 9) < RELEASE_PREFERENCE.get(kept.release, 9):
            unique[key] = ref
    pool = list(unique.values())
    groups: dict[GroupKey, list[FrameRef]] = defaultdict(list)
    for ref, season in zip(pool, season_index([r.mjd for r in pool], gap_days), strict=True):
        groups[(season, ref.detector)].append(ref)

    ranked: dict[GroupKey, list[FrameRef]] = {}
    for detector in sorted({d for _, d in groups}):
        by_season = {s: g for (s, d), g in groups.items() if d == detector}
        target = _reference_wavelength({s: [r.wavelength_um for r in g] for s, g in by_season.items()})
        for season, members in by_season.items():
            mid = _middle([r.mjd for r in members])
            ranked[(season, detector)] = sorted(
                members, key=lambda r, mid=mid: _rank(r.wavelength_um, target, r.mjd, mid, r.obs_id)
            )
    return ranked, _group_order(list(ranked))


def _round_robin(ranked: Mapping[GroupKey, Sequence[_T]], order: list[GroupKey], budget: int) -> list[_T]:
    picked: list[_T] = []
    for depth in count():
        added = False
        for key in order:
            if depth < len(ranked[key]) and len(picked) < budget:
                picked.append(ranked[key][depth])
                added = True
        if not added or len(picked) >= budget:
            break
    return picked


def select_frames(refs: list[FrameRef], max_frames: int, gap_days: float = SEASON_GAP_DAYS) -> list[FrameRef]:
    """Pick at most ``max_frames`` frames spread over every season x detector (WS2).

    Keeping the first N frames by time shows a single season, where nothing
    moves. Instead the budget is filled round-robin over ``plan_frames``
    groups, so every (season, detector) gets one frame before any gets a
    second. Returned by time.
    """
    if max_frames <= 0:
        return []
    ranked, order = plan_frames(refs, gap_days)
    return sorted(_round_robin(ranked, order, max_frames), key=lambda r: (r.mjd, r.detector))


@dataclass
class _Projected:
    ref: FrameRef
    frame_id: str
    obs_id: str
    detector: int
    mjd: float
    date_obs: str
    data: np.ndarray
    bad: np.ndarray
    wavelength_um: float | None = None
    bandwidth_um: float | None = None
    variance: np.ndarray | None = None  # VARIANCE on the grid (false-color coadd weights)


def _wavelength_at_centre(img, cfg: FieldConfig) -> tuple[float | None, float | None]:
    """(wavelength, bandwidth) [um] at the field centre from the frame's WCS-WAVE table (WS1).

    The contract defines ``Frame.wavelength_um`` at the field centre. For the
    five targets the centre is the target at the mean epoch of its frames; a
    mover is at most ~1-2 px away at any epoch (D3 changes ~0.4 nm per px, far
    below the ~10-40 nm bandwidth). None when the file has no WCS-WAVE table.
    """
    lookup = getattr(img, "wavelength_at", None)  # test doubles may not have it
    found = lookup(cfg.ra, cfg.dec) if lookup is not None else None
    return found if found is not None else (None, None)


def noise_ratio(img) -> float | None:
    """Robust scatter of IMAGE - ZODI in units of the noise its VARIANCE plane predicts.

    ``1.4826 * MAD(IMAGE - ZODI) / sqrt(median(VARIANCE))`` over the native
    pixels that are finite, have VARIANCE > 0 and carry no
    ``imaging.flags.DEFAULT_BAD`` bit. Stars, even a saturated one with a
    large halo, barely move it (the MAD ignores whatever touches less than
    about half of the pixels); a background step or ramp across the cutout
    inflates it. A step that splits the cutout far from half and half is
    under-measured. None without a VARIANCE plane (or with no usable pixel).
    """
    from .imaging.flags import DEFAULT_BAD, bad_pixel_mask

    variance = getattr(img, "variance", None)  # test doubles may not have it
    if variance is None:
        return None
    pixels = np.asarray(img.data_minus_zodi, dtype=np.float64)
    variance = np.asarray(variance, dtype=np.float64)
    if pixels.shape != variance.shape:
        return None
    usable = np.isfinite(pixels) & np.isfinite(variance) & (variance > 0)
    flags = getattr(img, "flags", None)
    if flags is not None and np.shape(flags) == pixels.shape:
        usable &= ~bad_pixel_mask(np.asarray(flags), DEFAULT_BAD)
    if not usable.any():
        return None
    values = pixels[usable]
    sigma = MAD_TO_SIGMA * float(np.median(np.abs(values - np.median(values))))
    return sigma / float(np.sqrt(np.median(variance[usable])))


def _project(refs: list[FrameRef], cfg: FieldConfig, grid) -> tuple[list[_Projected], list[tuple[FrameRef, str]]]:
    """Download (WS1), vet and reproject (WS2) ``refs``; return (projected, [(ref, reason)])."""
    from .data import cutouts, fits_io
    from .imaging import reproject

    paths = cutouts.fetch_cutouts(refs, cfg.ra, cfg.dec, size_arcmin=cfg.size_deg * 60 * 1.5)
    if len(paths) != len(refs):
        raise RuntimeError(
            f"fetch_cutouts returned {len(paths)} paths for {len(refs)} frames; "
            "expected one path (or None for a failed download) per frame, in order"
        )
    projected: list[_Projected] = []
    skipped: list[tuple[FrameRef, str]] = []
    for ref, path in zip(refs, paths, strict=True):
        if path is None:
            skipped.append((ref, DOWNLOAD_FAILED))
            continue
        img = fits_io.read_spherex(path)
        ratio = noise_ratio(img)
        if ratio is not None and ratio > MAX_NOISE_RATIO:
            skipped.append((ref, f"{BAD_FRAME}: noise {ratio:.1f}x VARIANCE"))
            continue
        data, bad = reproject.reproject_to_grid(img, grid)
        if np.isfinite(data).mean() < MIN_FINITE_FRACTION:
            skipped.append((ref, OUTSIDE_CUTOUT))
            continue
        obs_id = img.obs_id or ref.obs_id
        wavelength, bandwidth = _wavelength_at_centre(img, cfg)
        variance = reproject.reproject_variance(img, grid) if getattr(img, "variance", None) is not None else None
        projected.append(
            _Projected(
                ref,
                f"{obs_id}D{img.detector}",
                obs_id,
                img.detector,
                img.mjd,
                img.date_obs,
                data,
                bad,
                wavelength if wavelength is not None else ref.wavelength_um,
                bandwidth,
                variance,
            )  # fmt: skip
        )
    return projected, skipped


@dataclass
class _Selection:
    frames: list[_Projected]  # final frames, by time
    skipped: list[tuple[FrameRef, str]]
    n_downloaded: int  # candidate cutouts obtained (pool + replacements)
    reference_um: dict[int, float | None]  # per-detector reference wavelength
    pool: list[_Projected] = field(default_factory=list)  # every vetted, projected candidate (final included)
    n_topup: int = 0  # extra D2/D3 cutouts obtained for the J/H/Ks composites only
    topup_note: str = ""  # why the J/H/Ks top-up did not run, if it failed
    registration_note: str = ""  # what the per-frame registration check measured and rejected


@dataclass
class _RegistrationCheck:
    n_frames: int = 0
    offsets: list[float] = field(default_factory=list)  # registration error of every checked frame that was kept
    rejected: list[tuple[_Projected, float]] = field(default_factory=list)  # (frame, offset px)

    def note(self) -> str:
        from .imaging.register import MAX_OFFSET_PX, MIN_FRAMES, MIN_STARS

        n_unchecked = self.n_frames - len(self.offsets) - len(self.rejected)
        kept = (
            f" (kept frames: median {float(np.median(self.offsets)):.2f} px, max {max(self.offsets):.2f} px)"
            if self.offsets
            else ""
        )
        text = (
            "Registration check: each candidate's field stars were compared with their median position in the "
            f"other frames of the same detector; {len(self.offsets) + len(self.rejected)} of {self.n_frames} "
            f"candidate frame(s) checked{kept}, {n_unchecked} not checkable (fewer than {MIN_FRAMES} frames of "
            f"their detector or {MIN_STARS} measurable field stars, e.g. around a saturated target)."
        )
        if self.rejected:
            listed = ", ".join(f"{p.frame_id} ({off:.2f} px)" for p, off in self.rejected)
            text += (
                f" Rejected {len(self.rejected)} misregistered frame(s) whose stars are off by more than "
                f"{MAX_OFFSET_PX:g} px (archive WCS error; they would fake a jump of the whole field): {listed}."
            )
        return text


def _drop_misregistered(
    frames: list[_Projected], check: _RegistrationCheck, judged: set[str] | None = None
) -> list[_Projected]:
    """``frames`` without the misregistered ones among ``judged`` (default: all), see ``imaging.register``.

    Every frame of ``frames`` serves as reference (the consensus star positions of its detector), but only
    the ``judged`` ones are counted in ``check`` and may be dropped: the J/H/Ks top-up judges its new frames
    against the whole pool without touching the frames already chosen.
    """
    from .imaging import register

    found = register.registrations(frames)
    out = []
    for p in frames:
        if judged is not None and p.frame_id not in judged:
            out.append(p)
            continue
        check.n_frames += 1
        r = found.get(p.frame_id)
        if r is not None and r.offset > register.MAX_OFFSET_PX:
            check.rejected.append((p, r.offset))
            continue
        if r is not None:
            check.offsets.append(r.offset)
        out.append(p)
    return out


def _key_of(ranked: Mapping[GroupKey, list[FrameRef]]) -> dict[tuple[str, int], GroupKey]:
    return {(r.obs_id, r.detector): k for k, members in ranked.items() for r in members}


def _spares(
    ranked: Mapping[GroupKey, list[FrameRef]], used_refs: list[FrameRef], skipped: list[tuple[FrameRef, str]]
) -> list[FrameRef]:
    """Next unused frame of the (season, detector) group of every skipped frame."""
    used = {(r.obs_id, r.detector) for r in used_refs}
    key_of = _key_of(ranked)
    spares = []
    for ref, _ in skipped:
        key = key_of[(ref.obs_id, ref.detector)]
        spare = next((r for r in ranked[key] if (r.obs_id, r.detector) not in used), None)
        if spare is not None:
            used.add((spare.obs_id, spare.detector))
            spares.append(spare)
    return spares


def _pick_final(
    projected: list[_Projected], ranked: Mapping[GroupKey, list[FrameRef]], max_frames: int
) -> tuple[list[_Projected], dict[int, float | None]]:
    """Keep ``max_frames`` of the projected pool: same colour across seasons, spread round-robin.

    Per detector, the reference is the measured wavelength every season can
    match best with the number of frames round-robin will give it
    (``_reference_wavelength``); each (season, detector) group is ranked by
    ``|wavelength - reference|`` then distance to the season middle, frames
    with an unknown wavelength last. Returned by time, with the reference of
    every detector that keeps frames.
    """
    key_of = _key_of(ranked)
    groups: dict[GroupKey, list[_Projected]] = defaultdict(list)
    for p in projected:
        groups[key_of[(p.ref.obs_id, p.ref.detector)]].append(p)
    order = _group_order(list(groups))
    quota = Counter(_round_robin({k: [k] * len(g) for k, g in groups.items()}, order, max_frames))
    references: dict[int, float | None] = {}
    chosen: dict[GroupKey, list[_Projected]] = {}
    for detector in sorted({d for _, d in groups}):
        by_season = {s: g for (s, d), g in groups.items() if d == detector}
        target = _reference_wavelength(
            {s: [p.wavelength_um for p in g] for s, g in by_season.items()},
            {s: quota[(s, detector)] for s in by_season},
        )
        if any(quota[(s, detector)] for s in by_season):
            references[detector] = target
        for season, members in by_season.items():
            mid = _middle([r.mjd for r in ranked[(season, detector)]])
            chosen[(season, detector)] = sorted(
                members, key=lambda p, mid=mid: _rank(p.wavelength_um, target, p.mjd, mid, p.ref.obs_id)
            )
    final = _round_robin(chosen, order, max_frames)
    return sorted(final, key=lambda p: (p.mjd, p.detector)), references


JHK_TOPUP_PER_SEASON = 24  # extra D2/D3 cutouts per season at most, to find J/H/Ks wavelengths


def _jhk_topup(
    cfg: FieldConfig,
    grid,
    ranked: Mapping[GroupKey, list[FrameRef]],
    vetted: list[_Projected],
    final: list[_Projected],
    tried: set[tuple[str, int]],
) -> tuple[list[_Projected], list[tuple[FrameRef, str]], int]:
    """Download more D2/D3 frames of the seasons whose pool misses J, H or Ks (2MASS-like composites).

    The pool is ranked toward each detector's reference wavelength, so the J (1.25), H (1.65) and
    Ks (2.17 um) wavelengths the ``jhk`` composite needs are often never downloaded (real fields:
    3 of 17 seasons had them). A wavelength is only known after download, so the untried frames of the
    relevant (season, D2/D3) groups are fetched, at most ``JHK_TOPUP_PER_SEASON`` per season. They join
    the pool for the composites only: the blink frames do not change. Seasons without a final frame are
    skipped, since composites are only made for the seasons the blink shows.
    """
    from .imaging.color import JHK_BANDS, JHK_TOLERANCE_UM

    key_of = _key_of(ranked)
    seasons = sorted({key_of[(p.ref.obs_id, p.ref.detector)][0] for p in final})
    wanted_detectors = {"J": (2,), "H": (2, 3), "Ks": (3,)}
    extra: list[FrameRef] = []
    for season in seasons:
        have = [
            p.wavelength_um
            for p in vetted
            if p.wavelength_um is not None and key_of[(p.ref.obs_id, p.ref.detector)][0] == season
        ]
        missing = [
            band for band, target in JHK_BANDS.values() if not any(abs(w - target) <= JHK_TOLERANCE_UM for w in have)
        ]
        if not missing:
            continue
        detectors = sorted({d for band in missing for d in wanted_detectors[band]})
        candidates = [r for d in detectors for r in ranked.get((season, d), []) if (r.obs_id, r.detector) not in tried]
        extra += candidates[:JHK_TOPUP_PER_SEASON]
    if not extra:
        return [], [], 0
    more, skipped = _project(extra, cfg, grid)
    return more, skipped, len(extra)


def _select_and_project(cfg: FieldConfig, grid, refs: list[FrameRef], *, jhk_topup: bool = False) -> _Selection:
    """Plan, download a candidate pool (one replacement round), reject bad frames, pick the final frames."""
    ranked, order = plan_frames(refs)
    available = sum(len(members) for members in ranked.values())
    pool = _round_robin(ranked, order, min(POOL_FACTOR * cfg.max_frames, available)) if cfg.max_frames > 0 else []
    if not pool:
        raise ValueError(f"No usable SPHEREx frames for field '{cfg.id}'; no products were published.")

    # WS1 cutouts + WS2 common grid. One retry round: a skipped frame is
    # replaced by the next-ranked frame of its (season, detector) group.
    projected, skipped = _project(pool, cfg, grid)
    n_tried = len(pool)
    spares = _spares(ranked, pool, skipped) if skipped else []
    if spares:
        more, still_skipped = _project(spares, cfg, grid)
        projected += more
        skipped += still_skipped
        n_tried += len(spares)
    unique: dict[str, _Projected] = {}
    for p in sorted(projected, key=lambda p: (p.mjd, p.detector)):
        unique.setdefault(p.frame_id, p)
    check = _RegistrationCheck()
    vetted = _drop_misregistered(list(unique.values()), check)
    skipped += [(p.ref, f"{MISREGISTERED}: field stars {off:.2f} px off the other frames") for p, off in check.rejected]
    final, references = _pick_final(vetted, ranked, cfg.max_frames)
    n_downloaded = n_tried - sum(why == DOWNLOAD_FAILED for _, why in skipped)
    n_topup, topup_note = 0, ""
    if jhk_topup:
        tried = {(r.obs_id, r.detector) for r in [*pool, *spares]}
        try:
            more, more_skipped, n_more = _jhk_topup(cfg, grid, ranked, vetted, final, tried)
        except Exception as e:  # a colour extra: never lose the blink frames over it
            log.warning("J/H/Ks top-up failed for %s: %r", cfg.id, e)
            topup_note = f"J/H/Ks top-up: not run ({type(e).__name__}: {e})."
        else:
            known = {p.frame_id for p in vetted}
            new = [p for p in more if p.frame_id not in known]
            # composites only; the final frames are unchanged. Judge the new frames against the whole pool.
            vetted = _drop_misregistered(vetted + new, check, judged={p.frame_id for p in new})
            n_topup = n_more - sum(why == DOWNLOAD_FAILED for _, why in more_skipped)
    return _Selection(final, skipped, n_downloaded, references, vetted, n_topup, topup_note, check.note())


def _skip_reasons(skipped: list[tuple[FrameRef, str]]) -> str:
    return "; ".join(f"{r.obs_id}D{r.detector}: {why}" for r, why in skipped)


def _raise_nothing_usable(cfg: FieldConfig, skipped: list[tuple[FrameRef, str]]) -> None:
    reasons = _skip_reasons(skipped)
    if all(why == OUTSIDE_CUTOUT for _, why in skipped):
        raise ValueError(
            f"No SPHEREx cutout of field '{cfg.id}' overlaps its grid; no products were published. ({reasons})"
        )
    if all(why != DOWNLOAD_FAILED for _, why in skipped):
        raise ValueError(
            f"Every SPHEREx frame of field '{cfg.id}' was rejected; no products were published. ({reasons})"
        )
    # Failed downloads are retryable: this is NOT a 'no coverage' answer.
    raise RuntimeError(f"Could not obtain any SPHEREx cutout for field '{cfg.id}' ({reasons}); nothing was published.")


def _selection_note(sel: _Selection, max_frames: int) -> str:
    n_bad = sum(why.startswith(BAD_FRAME) for _, why in sel.skipped)
    refs = ", ".join(f"D{d} {w:.3f} um" for d, w in sorted(sel.reference_um.items()) if w is not None)
    return (
        f"Frame selection: downloaded {sel.n_downloaded} candidate frame(s) (up to {POOL_FACTOR} x "
        f"max_frames={max_frames}) and kept {len(sel.frames)}, spread round-robin over seasons x detectors; "
        "inside each (season, detector) the frames whose wavelength at the field centre is closest to a "
        f"per-detector reference ({refs or 'no wavelength known'}) come first, then those nearest the season "
        f"middle; frames without a known wavelength rank last. Rejected {n_bad} bad frame(s) whose "
        f"IMAGE - ZODI robust scatter exceeds {MAX_NOISE_RATIO:g}x the noise of their VARIANCE plane "
        "(background steps)."
        + (
            f" Downloaded {sel.n_topup} more D2/D3 frame(s) only to find J/H/Ks wavelengths for the "
            "false-color composites; they are not blink frames."
            if sel.n_topup
            else ""
        )
        + (f" {sel.topup_note}" if sel.topup_note else "")
    )


def _render(cfg: FieldConfig, store: ProductStore, projected: list[_Projected]) -> list[Frame]:
    """WS2: one contrast per detector, then one PNG per final frame and the thumbnail."""
    from .imaging import render

    stretches = render.field_stretches(
        [p.data for p in projected], [p.detector for p in projected], [p.bad for p in projected]
    )
    frames: list[Frame] = []
    field_dir = store.field_dir(cfg.id)
    for p, stretch in zip(projected, stretches, strict=True):
        rel = f"frames/{p.frame_id}.png"
        render.save_png(p.data, field_dir / rel, stretch)
        frames.append(
            Frame(
                id=p.frame_id,
                obs_id=p.obs_id,
                detector=p.detector,
                mjd=p.mjd,
                date_obs=datetime.fromisoformat(p.date_obs).replace(tzinfo=UTC),
                wavelength_um=p.wavelength_um,
                bandwidth_um=p.bandwidth_um,
                release=p.ref.release,
                image=rel,
                source_uri=p.ref.irsa_uri,
                valid_fraction=float((~p.bad).mean()),
                stretch=stretch,
            )
        )
    _write_thumbnail(field_dir, frames)
    return frames


def _grid_frame(p: _Projected):
    from .imaging.compare import GridFrame

    return GridFrame(p.frame_id, p.detector, p.mjd, p.data, p.bad, p.variance, p.wavelength_um)


def _composites(field_dir: Path, sel: _Selection) -> tuple[list[Composite], str]:
    """WS2: false-color season composites (``color/``) of the final frames and the vetted pool.

    A display extra: if it fails, the field is still published without composites and the
    reason is recorded in the provenance notes.
    """
    from .imaging import color

    try:
        return color.write_composites(
            field_dir, [_grid_frame(p) for p in sel.frames], [_grid_frame(p) for p in sel.pool]
        )
    except Exception as e:  # the frames are already rendered; never lose them over a colour picture
        log.warning("False-color composites failed for %s: %r", field_dir.name, e)
        return [], f"False-color composites: not built ({type(e).__name__}: {e})."


def build_field(
    cfg: FieldConfig,
    out: Path = settings.PRODUCTS_DIR,
    *,
    analyze: bool = False,
    overrides: Mapping[str, Any] | None = None,
    jhk_topup: bool = False,
) -> SkyField:
    """Search, select, download, vet, reproject and render a field; optionally analyse it.

    ``overrides`` replaces FieldConfig values (``errante build --max-frames/--detectors``) and is
    recorded in the provenance notes. ``jhk_topup`` downloads extra D2/D3 frames so the J/H/Ks
    false-color composite exists in more seasons (on for ``errante build``, off for API jobs).
    """
    from .data import irsa
    from .imaging import grid as grid_mod

    cfg, override_note = apply_overrides(cfg, overrides)
    store = ProductStore(out)
    grid = grid_mod.make_grid(cfg.ra, cfg.dec, cfg.size_deg)

    # 1. WS1: which frames cover the field? WS2: spread a candidate pool over seasons x detectors,
    # download and vet it, then keep the frames that match in wavelength across seasons.
    result = irsa.search_frames(cfg.ra, cfg.dec, detectors=cfg.detectors, mjd_min=cfg.mjd_min, mjd_max=cfg.mjd_max)
    sel = _select_and_project(cfg, grid, result.frames, jhk_topup=jhk_topup)
    if not sel.frames:
        _raise_nothing_usable(cfg, sel.skipped)

    # 2. WS2: PNGs of the final frames only, then the false-color season composites.
    frames = _render(cfg, store, sel.frames)
    composites, color_note = _composites(store.field_dir(cfg.id), sel)
    notes = [
        "Automatic analysis has not completed."
        if analyze
        else "Automatic detection and catalog matching were not run.",
        "Pixel values and stretch limits are IMAGE - ZODI (SPHEREx zodiacal model subtracted) in MJy/sr; "
        "PNGs use an asinh mapping with the same contrast for every frame of a detector, and transparent "
        "pixels mean no data. Saturated star cores and detector-defect pixels are filled from their neighbours "
        "for display only; they count as invalid in valid_fraction.",
        _selection_note(sel, cfg.max_frames),
        *([sel.registration_note] if sel.registration_note else []),
        color_note,
    ]
    if sel.skipped:
        notes.append(f"Skipped {len(sel.skipped)} frame(s): {_skip_reasons(sel.skipped)}")
    if override_note:
        notes.append(override_note)
    sky_field = SkyField(
        id=cfg.id,
        name=cfg.name,
        description=cfg.description,
        tags=cfg.tags,
        center=SkyCoord(ra=cfg.ra, dec=cfg.dec),
        size_deg=cfg.size_deg,
        grid=grid,
        frames=frames,
        composites=composites,
        provenance=Provenance(
            pipeline_version=__version__,
            built_at=datetime.now(UTC),
            synthetic=any(f.release == "synthetic" for f in frames),
            data_releases=sorted({f.release for f in frames}),
            notes=notes,
        ),
    )
    store.write_field(sky_field)
    store.write_candidates(CandidateList(field_id=cfg.id, candidates=[]))
    store.write_known(KnownObjectList(field_id=cfg.id, objects=[]))
    store.rebuild_manifest()

    if analyze:
        _analyze(cfg, store, sky_field, sel.frames, notes)
    return sky_field


def _analyze(
    cfg: FieldConfig, store: ProductStore, sky_field: SkyField, projected: list[_Projected], notes: list[str]
) -> None:
    """Opt-in detection, linking, scoring and catalog matching (the viewable field is already written)."""
    from .detect import linking, scoring, sources
    from .science import known_objects

    all_sources = []
    for p in projected:
        all_sources += sources.find_sources(p.data, p.bad, p.frame_id, p.mjd)
    tracks = linking.link_tracks(all_sources)
    cands = scoring.score_tracks(tracks, cfg.id)
    known = []
    for fr in sky_field.frames:
        known += known_objects.objects_in_frame(cfg.ra, cfg.dec, cfg.size_deg, fr.mjd)
    cands = known_objects.crossmatch(cands, known)
    store.write_candidates(CandidateList(field_id=cfg.id, candidates=cands))
    store.write_known(KnownObjectList(field_id=cfg.id, objects=known))
    sky_field.provenance.notes = ["Automatic detection and catalog matching completed.", *notes[1:]]
    store.write_field(sky_field)
    store.rebuild_manifest()


def _write_thumbnail(field_dir: Path, frames: list[Frame]) -> None:
    """thumb.png = the middle epoch of the detector that covers the most seasons."""
    if not frames:
        return
    by_detector: dict[int, list[Frame]] = defaultdict(list)
    for fr in frames:
        by_detector[fr.detector].append(fr)

    def coverage(det: int) -> tuple[int, int, int]:
        mjds = [f.mjd for f in by_detector[det]]
        return (max(season_index(mjds)) + 1, len(mjds), -det)

    best = sorted(by_detector[max(by_detector, key=coverage)], key=lambda f: f.mjd)
    chosen = best[len(best) // 2]
    shutil.copyfile(field_dir / chosen.image, field_dir / "thumb.png")
