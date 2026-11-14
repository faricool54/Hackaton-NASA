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
# When the same exposure is listed in several releases, keep the most final one.
RELEASE_PREFERENCE = {"dr1": 0, "qr3": 1, "qr2": 2, "synthetic": 3}
# Frames whose reprojected grid is almost empty (target at a detector edge)
# are useless in the blink.
MIN_FINITE_FRACTION = 0.2


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


def season_index(mjds: list[float], gap_days: float = SEASON_GAP_DAYS) -> list[int]:
    """0-based season of each MJD: a new season starts after a gap > ``gap_days``."""
    order = sorted(range(len(mjds)), key=lambda i: mjds[i])
    seasons = [0] * len(mjds)
    current = 0
    for prev, i in zip([None, *order], order, strict=False):
        if prev is not None and mjds[i] - mjds[prev] > gap_days:
            current += 1
        seasons[i] = current
    return seasons


def _reference_wavelength(by_season: dict[int, list[FrameRef]]) -> float | None:
    """Wavelength that every season can match best (minimises the summed mismatch)."""
    known = {s: [r.wavelength_um for r in refs if r.wavelength_um is not None] for s, refs in by_season.items()}
    candidates = sorted({w for ws in known.values() for w in ws})
    if not candidates:
        return None
    return min(candidates, key=lambda c: sum(min(abs(w - c) for w in ws) for ws in known.values() if ws))


def select_frames(refs: list[FrameRef], max_frames: int, gap_days: float = SEASON_GAP_DAYS) -> list[FrameRef]:
    """Pick at most ``max_frames`` frames spread over every season x detector (WS2).

    Keeping the first N frames by time shows a single season, where nothing
    moves. Instead: drop duplicate exposures (same obs_id + detector), split
    the epochs into seasons, and fill the budget round-robin so every
    (season, detector) group gets one frame before any gets a second. Inside a
    group, frames closest to a per-detector reference wavelength come first
    (each exposure sees another wavelength through the linear variable filter,
    so a star changes brightness without being variable: docs/SCIENCE.md §0.4);
    without wavelengths, frames nearest the middle of the season come first.
    Detectors that cover more seasons are filled first. Returned by time.
    """
    unique: dict[tuple[str, int], FrameRef] = {}
    for ref in refs:
        key = (ref.obs_id, ref.detector)
        kept = unique.get(key)
        if kept is None or RELEASE_PREFERENCE.get(ref.release, 9) < RELEASE_PREFERENCE.get(kept.release, 9):
            unique[key] = ref
    pool = list(unique.values())
    if max_frames <= 0 or not pool:
        return []

    seasons = season_index([r.mjd for r in pool], gap_days)
    groups: dict[tuple[int, int], list[FrameRef]] = defaultdict(list)
    for ref, season in zip(pool, seasons, strict=True):
        groups[(season, ref.detector)].append(ref)

    ranked: dict[tuple[int, int], list[FrameRef]] = {}
    for detector in sorted({d for _, d in groups}):
        by_season = {s: g for (s, d), g in groups.items() if d == detector}
        target = _reference_wavelength(by_season)
        for season, members in by_season.items():
            mid = (min(r.mjd for r in members) + max(r.mjd for r in members)) / 2

            def rank(r: FrameRef, target=target, mid=mid) -> tuple[float, float, str]:
                dw = abs(r.wavelength_um - target) if target is not None and r.wavelength_um is not None else np.inf
                return (dw, abs(r.mjd - mid), r.obs_id)

            ranked[(season, detector)] = sorted(members, key=rank)

    n_seasons = defaultdict(int)
    for _, detector in ranked:
        n_seasons[detector] += 1
    order = sorted(ranked, key=lambda k: (-n_seasons[k[1]], k[1], k[0]))

    picked: list[FrameRef] = []
    for depth in count():
        added = False
        for key in order:
            if depth < len(ranked[key]) and len(picked) < max_frames:
                picked.append(ranked[key][depth])
                added = True
        if not added or len(picked) >= max_frames:
            break
    return sorted(picked, key=lambda r: (r.mjd, r.detector))


def build_field(cfg: FieldConfig, out: Path = settings.PRODUCTS_DIR, *, analyze: bool = False) -> SkyField:
    from .data import cutouts, fits_io, irsa
    from .imaging import grid as grid_mod
    from .imaging import render, reproject

    store = ProductStore(out)
    grid = grid_mod.make_grid(cfg.ra, cfg.dec, cfg.size_deg)

    # 1. WS1: which frames cover the field? WS2: spread them over seasons x detectors.
    result = irsa.search_frames(cfg.ra, cfg.dec, detectors=cfg.detectors, mjd_min=cfg.mjd_min, mjd_max=cfg.mjd_max)
    refs = select_frames(result.frames, cfg.max_frames)
    if not refs:
        raise ValueError(f"No usable SPHEREx frames for field '{cfg.id}'; no products were published.")
    # 2. WS1: download cutouts (a bit bigger than the field so reprojection has margins)
    paths = cutouts.fetch_cutouts(refs, cfg.ra, cfg.dec, size_arcmin=cfg.size_deg * 60 * 1.5)

    # 3. WS2: every frame onto the common grid first, so the stretch can be shared per detector.
    projected = []
    skipped: list[str] = []
    seen_ids: set[str] = set()
    for ref, path in zip(refs, paths, strict=True):
        if path is None:  # download failed and was reported by WS1
            skipped.append(f"{ref.obs_id}D{ref.detector}: no cutout")
            continue
        img = fits_io.read_spherex(path)
        data, bad = reproject.reproject_to_grid(img, grid)
        frame_id = f"{img.obs_id or ref.obs_id}D{img.detector}"
        if frame_id in seen_ids:
            continue
        if np.isfinite(data).mean() < MIN_FINITE_FRACTION:
            skipped.append(f"{frame_id}: target outside the cutout")
            continue
        seen_ids.add(frame_id)
        projected.append((ref, img, frame_id, data, bad))
    if not projected:
        raise ValueError(f"No SPHEREx cutout of field '{cfg.id}' overlaps its grid; no products were published.")

    stretches = render.field_stretches([p[3] for p in projected], [p[1].detector for p in projected])
    frames: list[Frame] = []
    analysis_inputs: list[tuple[str, float, np.ndarray, np.ndarray]] = []
    field_dir = store.field_dir(cfg.id)
    for (ref, img, frame_id, data, bad), stretch in zip(projected, stretches, strict=True):
        rel = f"frames/{frame_id}.png"
        render.save_png(data, field_dir / rel, stretch)
        frames.append(
            Frame(
                id=frame_id,
                obs_id=img.obs_id or ref.obs_id,
                detector=img.detector,
                mjd=img.mjd,
                date_obs=datetime.fromisoformat(img.date_obs).replace(tzinfo=UTC),
                wavelength_um=ref.wavelength_um,
                bandwidth_um=None,
                release=ref.release,
                image=rel,
                source_uri=ref.irsa_uri,
                valid_fraction=float((~bad).mean()),
                stretch=stretch,
            )
        )
        if analyze:
            analysis_inputs.append((frame_id, img.mjd, data, bad))
    _write_thumbnail(field_dir, frames)

    notes = [
        "Automatic analysis has not completed." if analyze else "Automatic detection and catalog matching were not run."
    ]
    if skipped:
        notes.append(f"Skipped {len(skipped)} selected frame(s): " + "; ".join(skipped))
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
            synthetic=False,
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
