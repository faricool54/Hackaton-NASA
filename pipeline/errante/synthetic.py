"""Synthetic demo dataset (implemented) so every workstream can start NOW.

Writes a complete, contract-valid product tree (manifest, fields, frame PNGs,
candidates, known objects) with fake stars and fake movers. EVERYTHING here is
flagged ``synthetic=True`` and the UI must show a "SYNTHETIC DATA" badge.

    errante demo --out data/demo
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
from astropy.time import Time

from . import __version__
from .imaging.grid import make_grid, png_xy_to_sky
from .imaging.render import save_png
from .models import (
    Candidate,
    CandidateKind,
    CandidateList,
    CandidateStatus,
    Detection,
    Frame,
    KnownMatch,
    KnownObject,
    KnownObjectList,
    KnownObjectPosition,
    ObjectType,
    Provenance,
    SkyCoord,
    SkyField,
    SpectrumPoint,
)
from .products import ProductStore
from .science.motion import distance_from_opposition_rate, motion_from_detections

# Approximate SPHEREx detector bands [um] and resolving power (docs/DATA.md).
BANDS = {1: (0.75, 1.11, 41), 2: (1.11, 1.64, 41), 3: (1.64, 2.42, 41),
         4: (2.42, 3.82, 35), 5: (3.82, 4.42, 110), 6: (4.42, 5.00, 130)}  # fmt: skip
PSF_FWHM_PX = 1.2


@dataclass
class MoverSpec:
    name: str
    kind: CandidateKind
    status: CandidateStatus
    object_type: ObjectType
    x0: float  # PNG px at the first frame
    y0: float
    vx_px_per_hour: float
    vy_px_per_hour: float
    amp: float  # peak surface brightness at 1 um [MJy/sr]
    sed_slope: float = 1.0  # brightness ∝ (λ/1um)^-slope ; negative = red
    known_designation: str | None = None  # also listed in known.json
    only_frames: tuple[int, ...] | None = None  # e.g. an artifact in one frame
    notes: tuple[str, ...] = ()


@dataclass
class DemoFieldSpec:
    id: str
    name: str
    description: str
    tags: list[str]
    ra: float
    dec: float
    size_deg: float
    mjds: list[float]
    detectors: list[int]
    movers: list[MoverSpec]
    n_stars: int = 120
    seed: int = 1
    extra_notes: list[str] = field(default_factory=list)


def add_gaussian(img: np.ndarray, x: float, y: float, amp: float, fwhm_px: float = PSF_FWHM_PX) -> None:
    """Add a circular Gaussian (in place) at PNG-convention (x, y)."""
    sigma = fwhm_px / 2.3548
    r = int(np.ceil(4 * sigma)) + 1
    h, w = img.shape
    x0, x1 = max(int(x) - r, 0), min(int(x) + r + 1, w)
    y0, y1 = max(int(y) - r, 0), min(int(y) + r + 1, h)
    if x0 >= x1 or y0 >= y1:
        return
    yy, xx = np.mgrid[y0:y1, x0:x1]
    img[y0:y1, x0:x1] += amp * np.exp(-((xx - x) ** 2 + (yy - y) ** 2) / (2 * sigma**2))


def _wavelength(rng: np.random.Generator, det: int) -> tuple[float, float]:
    lo, hi, r = BANDS[det]
    wl = float(rng.uniform(lo, hi))
    return wl, wl / r


DEMO_FIELDS: list[DemoFieldSpec] = [
    DemoFieldSpec(
        id="demo-ecliptic",
        name="Demo · ecliptic field",
        description="Synthetic field near the ecliptic: a fast asteroid, a slow distant object and one artifact.",
        tags=["synthetic", "ecliptic"],
        ra=150.0,
        dec=11.0,
        size_deg=0.25,
        # Two visits one day apart, 3 exposures each, same detector (D2).
        mjds=[60810.10, 60810.1833, 60810.2667, 60811.10, 60811.1833, 60811.2667],
        detectors=[2, 2, 2, 2, 2, 2],
        movers=[
            MoverSpec(
                "SYN-AST-1",
                "moving",
                "known",
                "asteroid",
                20,
                40,
                4.1,
                0.6,
                3.0,
                known_designation="SYN 2026 AA",
                notes=('Fake main-belt asteroid (~25"/h).',),
            ),
            MoverSpec(
                "SYN-TNO-1",
                "moving",
                "unconfirmed",
                "tno",
                70,
                100,
                -0.45,
                -0.22,
                1.2,
                notes=('Fake slow mover (~3"/h, Kuiper-belt-like). Unconfirmed ≠ discovery.',),
            ),
            MoverSpec(
                "SYN-ART-1",
                "moving",
                "artifact",
                "unknown",
                110,
                20,
                0.0,
                0.0,
                6.0,
                only_frames=(3,),
                notes=("Appears in a single frame: cosmic-ray-like artifact, rejected.",),
            ),
        ],
        seed=7,
    ),
    DemoFieldSpec(
        id="demo-nep-deep",
        name="Demo · north ecliptic pole deep field",
        description="Synthetic deep field with 8 frames over one year and all six detectors.",
        tags=["synthetic", "deep-field"],
        ra=270.0,
        dec=66.56,
        size_deg=0.2,
        mjds=[60810.0, 60810.07, 60900.0, 60900.07, 60990.0, 60990.07, 61080.0, 61080.07],
        detectors=[1, 4, 2, 5, 3, 6, 2, 5],
        movers=[
            MoverSpec(
                "SYN-BD-1",
                "proper_motion",
                "unconfirmed",
                "brown_dwarf",
                40,
                80,
                0.0023,
                -0.0011,
                1.5,
                sed_slope=-1.5,
                notes=(
                    'Fake nearby brown dwarf; proper motion EXAGGERATED (~120"/yr) to be visible.',
                    "Very red: brighter at 4-5 um than at 1-2 um.",
                ),
            ),
        ],
        n_stars=90,
        seed=11,
    ),
]


def build_demo_field(spec: DemoFieldSpec, store: ProductStore) -> SkyField:
    rng = np.random.default_rng(spec.seed)
    grid = make_grid(spec.ra, spec.dec, spec.size_deg)
    w, h = grid.width_px, grid.height_px
    fdir = store.field_dir(spec.id)
    if fdir.exists():
        shutil.rmtree(fdir)

    # Static stars: position, brightness at 1 um, spectral slope.
    sx, sy = rng.uniform(0, w, spec.n_stars), rng.uniform(0, h, spec.n_stars)
    samp = 0.5 * (rng.pareto(1.2, spec.n_stars) + 1)
    sslope = rng.uniform(0.8, 2.0, spec.n_stars)

    t0 = spec.mjds[0]
    frames: list[Frame] = []
    tracks: dict[str, list[Detection]] = {m.name: [] for m in spec.movers}
    spectra: dict[str, list[SpectrumPoint]] = {m.name: [] for m in spec.movers}
    known_pos: dict[str, list[KnownObjectPosition]] = {m.name: [] for m in spec.movers if m.known_designation}

    for i, (mjd, det) in enumerate(zip(spec.mjds, spec.detectors, strict=True)):
        wl, bw = _wavelength(rng, det)
        frame_id = f"SYN{i:02d}D{det}"
        bg = 0.2 + 0.05 * wl
        img = rng.normal(bg, 0.03 + 0.005 * wl, size=(h, w)).astype(np.float64)
        for x, y, a, s in zip(sx, sy, samp, sslope, strict=True):
            add_gaussian(img, x, y, a * wl**-s)
        dt_h = (mjd - t0) * 24.0
        for m in spec.movers:
            if m.only_frames is not None and i not in m.only_frames:
                continue
            x, y = m.x0 + m.vx_px_per_hour * dt_h, m.y0 + m.vy_px_per_hour * dt_h
            if not (0 <= x < w and 0 <= y < h):
                continue
            amp = m.amp * wl**-m.sed_slope
            add_gaussian(img, x, y, amp)
            mx, my = x + rng.normal(0, 0.15), y + rng.normal(0, 0.15)
            ra, dec = png_xy_to_sky(grid, mx, my)
            flux_mjy = amp * 2 * np.pi * (PSF_FWHM_PX / 2.3548) ** 2 * 0.889  # MJy/sr·px -> mJy
            tracks[m.name].append(
                Detection(
                    frame_id=frame_id,
                    mjd=mjd,
                    position=SkyCoord(ra=float(ra), dec=float(dec)),
                    x=float(mx),
                    y=float(my),
                    flux_mjy=round(float(flux_mjy), 4),
                    flux_err_mjy=0.05,
                    snr=round(float(amp / 0.05), 1),
                )
            )
            spectra[m.name].append(
                SpectrumPoint(
                    frame_id=frame_id,
                    wavelength_um=round(wl, 4),
                    bandwidth_um=round(bw, 4),
                    flux_mjy=round(float(flux_mjy), 4),
                    flux_err_mjy=0.05,
                )
            )
            if m.name in known_pos:
                kra, kdec = png_xy_to_sky(grid, x + 0.8, y - 0.5)  # "ephemeris" slightly off
                known_pos[m.name].append(
                    KnownObjectPosition(
                        frame_id=frame_id,
                        mjd=mjd,
                        position=SkyCoord(ra=float(kra), dec=float(kdec)),
                        x=x + 0.8,
                        y=y - 0.5,
                    )
                )

        rel = f"frames/{frame_id}.png"
        stretch = save_png(img, fdir / rel)
        if i == 0:
            shutil.copy(fdir / rel, fdir / "thumb.png")
        frames.append(
            Frame(
                id=frame_id,
                obs_id=f"SYNTHETIC_{i:04d}",
                detector=det,
                mjd=mjd,
                date_obs=Time(mjd, format="mjd").to_datetime(timezone=UTC),
                wavelength_um=round(wl, 4),
                bandwidth_um=round(bw, 4),
                release="synthetic",
                image=rel,
                source_uri=None,
                valid_fraction=1.0,
                stretch=stretch,
            )
        )

    candidates: list[Candidate] = []
    known_objects: list[KnownObject] = []
    for m in spec.movers:
        dets = tracks[m.name]
        if not dets:
            continue
        motion = distance = None
        if len(dets) >= 2:
            motion = motion_from_detections(
                [d.mjd for d in dets], [d.position.ra for d in dets], [d.position.dec for d in dets]
            )
            if m.kind == "moving" and m.status != "artifact":
                distance = distance_from_opposition_rate(motion.rate_arcsec_per_hour)
        match = None
        if m.known_designation:
            match = KnownMatch(
                designation=m.known_designation,
                name=None,
                object_type=m.object_type,
                source="synthetic",
                separation_arcsec=5.6,
            )
            known_objects.append(
                KnownObject(
                    designation=m.known_designation,
                    object_type=m.object_type,
                    source="synthetic",
                    vmag=17.8,
                    positions=known_pos[m.name],
                )
            )
        score = {"known": 0.95, "unconfirmed": 0.7, "artifact": 0.1, "injected": 0.9}[m.status]
        candidates.append(
            Candidate(
                id=m.name,
                field_id=spec.id,
                kind=m.kind,
                status=m.status,
                score=score,
                detections=dets,
                motion=motion,
                distance=distance,
                known_match=match,
                spectrum=spectra[m.name],
                notes=["SYNTHETIC", *m.notes],
            )
        )

    sky_field = SkyField(
        id=spec.id,
        name=spec.name,
        description=spec.description,
        tags=spec.tags,
        center=SkyCoord(ra=spec.ra, dec=spec.dec),
        size_deg=spec.size_deg,
        grid=grid,
        frames=frames,
        provenance=Provenance(
            pipeline_version=__version__,
            built_at=datetime.now(UTC),
            synthetic=True,
            data_releases=["synthetic"],
            notes=["SYNTHETIC DATA generated by errante.synthetic — NOT SPHEREx.", *spec.extra_notes],
        ),
    )
    store.write_field(sky_field)
    store.write_candidates(CandidateList(field_id=spec.id, candidates=candidates))
    store.write_known(KnownObjectList(field_id=spec.id, objects=known_objects))
    return sky_field


def build_demo(out: Path) -> Path:
    from .systems.build import write_systems
    from .systems.catalog import demo_systems

    store = ProductStore(out)
    for spec in DEMO_FIELDS:
        build_demo_field(spec, store)
    write_systems(store, demo_systems())
    store.rebuild_manifest()
    return out
