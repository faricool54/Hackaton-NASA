"""Build a viewable SPHEREx field, then optionally run automatic analysis.

Images and metadata are the challenge's core deliverable. Detection and catalog
matching must not block that deliverable. Use ``errante build <id> --analyze``
to opt into those stages; the image products survive an analysis failure.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

from . import __version__, settings
from .models import CandidateList, Frame, KnownObjectList, Provenance, SkyCoord, SkyField
from .products import ProductStore

FIELDS_TOML = Path(__file__).parent / "config" / "fields.toml"


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


def build_field(cfg: FieldConfig, out: Path = settings.PRODUCTS_DIR, *, analyze: bool = False) -> SkyField:
    from .data import cutouts, fits_io, irsa
    from .imaging import grid as grid_mod
    from .imaging import render, reproject

    store = ProductStore(out)
    grid = grid_mod.make_grid(cfg.ra, cfg.dec, cfg.size_deg)

    # 1. WS1: which frames cover the field?
    result = irsa.search_frames(cfg.ra, cfg.dec, detectors=cfg.detectors, mjd_min=cfg.mjd_min, mjd_max=cfg.mjd_max)
    refs = result.frames[: cfg.max_frames]
    if not refs:
        raise ValueError(f"No usable SPHEREx frames for field '{cfg.id}'; no products were published.")
    # 2. WS1: download cutouts (a bit bigger than the field so reprojection has margins)
    paths = cutouts.fetch_cutouts(refs, cfg.ra, cfg.dec, size_arcmin=cfg.size_deg * 60 * 1.5)

    frames: list[Frame] = []
    analysis_inputs: list[tuple[str, float, np.ndarray, np.ndarray]] = []
    for ref, path in zip(refs, paths, strict=True):
        img = fits_io.read_spherex(path)
        # 3. WS2: common grid + PNG
        data, bad = reproject.reproject_to_grid(img, grid)
        frame_id = path.stem.removeprefix("level2_")
        rel = f"frames/{frame_id}.png"
        stretch = render.save_png(data, store.field_dir(cfg.id) / rel)
        frames.append(
            Frame(
                id=frame_id,
                obs_id=img.obs_id,
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
            notes=[
                "Automatic analysis has not completed."
                if analyze
                else "Automatic detection and catalog matching were not run."
            ],
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
        sky_field.provenance.notes = ["Automatic detection and catalog matching completed."]
        store.write_field(sky_field)
        store.rebuild_manifest()
    return sky_field
