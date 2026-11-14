"""Build real products for one field: archive -> cutouts -> grid -> PNGs -> candidates.

This is the integration point between workstreams. Each stage calls a function
owned by one WS; while a stage raises NotImplementedError the build stops there
with a clear message. Run with:  errante build <field-id>   (fields in config/fields.toml)
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

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


def build_field(cfg: FieldConfig, out: Path = settings.PRODUCTS_DIR) -> SkyField:
    from .data import cutouts, fits_io, irsa
    from .detect import linking, scoring, sources
    from .imaging import grid as grid_mod
    from .imaging import render, reproject
    from .science import known_objects

    store = ProductStore(out)
    grid = grid_mod.make_grid(cfg.ra, cfg.dec, cfg.size_deg)

    # 1. WS1: which frames cover the field?
    result = irsa.search_frames(cfg.ra, cfg.dec, detectors=cfg.detectors, mjd_min=cfg.mjd_min, mjd_max=cfg.mjd_max)
    refs = result.frames[: cfg.max_frames]
    # 2. WS1: download cutouts (a bit bigger than the field so reprojection has margins)
    paths = cutouts.fetch_cutouts(refs, cfg.ra, cfg.dec, size_arcmin=cfg.size_deg * 60 * 1.5)

    frames: list[Frame] = []
    all_sources = []
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
        # 4. WS2: sources per frame
        all_sources += sources.find_sources(data, bad, frame_id, img.mjd)

    # 5. WS2: link + score
    tracks = linking.link_tracks(all_sources)
    cands = scoring.score_tracks(tracks, cfg.id)
    # 6. WS3: known objects + cross-match
    known = []
    for fr in frames:
        known += known_objects.objects_in_frame(cfg.ra, cfg.dec, cfg.size_deg, fr.mjd)
    cands = known_objects.crossmatch(cands, known)

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
        ),
    )
    store.write_field(sky_field)
    store.write_candidates(CandidateList(field_id=cfg.id, candidates=cands))
    store.write_known(KnownObjectList(field_id=cfg.id, objects=known))
    store.rebuild_manifest()
    return sky_field
