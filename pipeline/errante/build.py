"""Build a viewable SPHEREx field, then optionally run automatic analysis.

Images and metadata are the challenge's core deliverable. Detection and catalog
matching must not block that deliverable. Use ``errante build <id> --analyze``
to opt into those stages; the image products survive an analysis failure.
"""

from __future__ import annotations

import shutil
import tomllib
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime
from itertools import count
from pathlib import Path

import numpy as np

from . import __version__, settings
from .models import CandidateList, Frame, FrameRef, KnownObjectList, Provenance, SkyCoord, SkyField
from .products import ProductStore

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

GroupKey = tuple[int, int]  # (season, detector)


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


def _reference_wavelength(by_season: dict[int, list[FrameRef]]) -> float | None:
    """Wavelength that every season can match best (minimises the summed mismatch)."""
    known = {s: [r.wavelength_um for r in refs if r.wavelength_um is not None] for s, refs in by_season.items()}
    candidates = sorted({w for ws in known.values() for w in ws})
    if not candidates:
        return None
    return min(candidates, key=lambda c: sum(min(abs(w - c) for w in ws) for ws in known.values() if ws))


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
        target = _reference_wavelength(by_season)
        for season, members in by_season.items():
            mid = (min(r.mjd for r in members) + max(r.mjd for r in members)) / 2

            def rank(r: FrameRef, target=target, mid=mid) -> tuple[float, float, str]:
                dw = abs(r.wavelength_um - target) if target is not None and r.wavelength_um is not None else np.inf
                return (dw, abs(r.mjd - mid), r.obs_id)

            ranked[(season, detector)] = sorted(members, key=rank)

    n_seasons: dict[int, int] = defaultdict(int)
    for _, detector in ranked:
        n_seasons[detector] += 1
    order = sorted(ranked, key=lambda k: (-n_seasons[k[1]], k[1], k[0]))
    return ranked, order


def _round_robin(ranked: dict[GroupKey, list[FrameRef]], order: list[GroupKey], budget: int) -> list[FrameRef]:
    picked: list[FrameRef] = []
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


def _project(refs: list[FrameRef], cfg: FieldConfig, grid) -> tuple[list[_Projected], list[tuple[FrameRef, str]]]:
    """Download (WS1) and reproject (WS2) ``refs``; return (projected, [(ref, reason)])."""
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
            skipped.append((ref, "download failed"))
            continue
        img = fits_io.read_spherex(path)
        data, bad = reproject.reproject_to_grid(img, grid)
        if np.isfinite(data).mean() < MIN_FINITE_FRACTION:
            skipped.append((ref, "target outside the cutout"))
            continue
        obs_id = img.obs_id or ref.obs_id
        projected.append(
            _Projected(ref, f"{obs_id}D{img.detector}", obs_id, img.detector, img.mjd, img.date_obs, data, bad)
        )
    return projected, skipped


def build_field(cfg: FieldConfig, out: Path = settings.PRODUCTS_DIR, *, analyze: bool = False) -> SkyField:
    from .data import irsa
    from .imaging import grid as grid_mod
    from .imaging import render

    store = ProductStore(out)
    grid = grid_mod.make_grid(cfg.ra, cfg.dec, cfg.size_deg)

    # 1. WS1: which frames cover the field? WS2: spread them over seasons x detectors.
    result = irsa.search_frames(cfg.ra, cfg.dec, detectors=cfg.detectors, mjd_min=cfg.mjd_min, mjd_max=cfg.mjd_max)
    ranked, order = plan_frames(result.frames)
    refs = _round_robin(ranked, order, cfg.max_frames) if cfg.max_frames > 0 else []
    if not refs:
        raise ValueError(f"No usable SPHEREx frames for field '{cfg.id}'; no products were published.")

    # 2. WS1 cutouts + WS2 common grid. One retry round: a skipped frame is
    # replaced by the next-ranked frame of its (season, detector) group.
    projected, skipped = _project(refs, cfg, grid)
    if skipped:
        used = {(r.obs_id, r.detector) for r in refs}
        key_of = {(r.obs_id, r.detector): k for k, members in ranked.items() for r in members}
        spares = []
        for ref, _ in skipped:
            key = key_of[(ref.obs_id, ref.detector)]
            spare = next((r for r in ranked[key] if (r.obs_id, r.detector) not in used), None)
            if spare is not None:
                used.add((spare.obs_id, spare.detector))
                spares.append(spare)
        if spares:
            more, still_skipped = _project(spares, cfg, grid)
            projected += more
            skipped += still_skipped
    unique: dict[str, _Projected] = {}
    for p in sorted(projected, key=lambda p: (p.mjd, p.detector)):
        unique.setdefault(p.frame_id, p)
    projected = list(unique.values())
    reasons = "; ".join(f"{r.obs_id}D{r.detector}: {why}" for r, why in skipped)
    if not projected:
        if all(why == "target outside the cutout" for _, why in skipped):
            raise ValueError(
                f"No SPHEREx cutout of field '{cfg.id}' overlaps its grid; no products were published. ({reasons})"
            )
        # Failed downloads are retryable: this is NOT a 'no coverage' answer.
        raise RuntimeError(
            f"Could not obtain any SPHEREx cutout for field '{cfg.id}' ({reasons}); nothing was published."
        )

    # 3. WS2: one contrast per detector, then PNGs.
    stretches = render.field_stretches(
        [p.data for p in projected], [p.detector for p in projected], [p.bad for p in projected]
    )
    frames: list[Frame] = []
    analysis_inputs: list[tuple[str, float, np.ndarray, np.ndarray]] = []
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
                wavelength_um=p.ref.wavelength_um,
                bandwidth_um=None,
                release=p.ref.release,
                image=rel,
                source_uri=p.ref.irsa_uri,
                valid_fraction=float((~p.bad).mean()),
                stretch=stretch,
            )
        )
        if analyze:
            analysis_inputs.append((p.frame_id, p.mjd, p.data, p.bad))
    _write_thumbnail(field_dir, frames)

    notes = [
        "Automatic analysis has not completed."
        if analyze
        else "Automatic detection and catalog matching were not run.",
        "Pixel values and stretch limits are IMAGE - ZODI (SPHEREx zodiacal model subtracted) in MJy/sr; "
        "PNGs use an asinh mapping with the same contrast for every frame of a detector, and transparent "
        "pixels mean no data. Saturated star cores and detector-defect pixels are filled from their neighbours "
        "for display only; they count as invalid in valid_fraction.",
    ]
    if skipped:
        notes.append(f"Skipped {len(skipped)} frame(s): {reasons}")
    sky_field = SkyField(
        id=cfg.id,
        name=cfg.name,
        description=cfg.description,
        tags=cfg.tags,
        center=SkyCoord(ra=cfg.ra, dec=cfg.dec),
        size_deg=cfg.size_deg,
        grid=grid,
        frames=frames,
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
        from .detect import linking, scoring, sources
        from .science import known_objects

        all_sources = []
        for frame_id, mjd, data, bad in analysis_inputs:
            all_sources += sources.find_sources(data, bad, frame_id, mjd)
        tracks = linking.link_tracks(all_sources)
        cands = scoring.score_tracks(tracks, cfg.id)
        known = []
        for fr in frames:
            known += known_objects.objects_in_frame(cfg.ra, cfg.dec, cfg.size_deg, fr.mjd)
        cands = known_objects.crossmatch(cands, known)
        store.write_candidates(CandidateList(field_id=cfg.id, candidates=cands))
        store.write_known(KnownObjectList(field_id=cfg.id, objects=known))
        sky_field.provenance.notes = ["Automatic detection and catalog matching completed.", *notes[1:]]
        store.write_field(sky_field)
        store.rebuild_manifest()
    return sky_field


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
