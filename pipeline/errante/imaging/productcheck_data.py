"""WS2-8: read a PUBLISHED field (``field.json`` + frame PNGs) and the catalog astrometry for the product check.

Everything here comes from the published product itself (``data/products/fields/<id>/``) or from the values
already written in ``config/fields.toml`` comments (read only, never edited). Nothing is fetched.
"""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image

from ..build import FIELDS_TOML, season_index
from ..models import Frame, SkyField
from .grid import sky_to_png_xy
from .invert import Decoded, decode
from .photometry import propagate

J2000_MJD = 51544.5  # J2000.0 (TT ~ UTC at this precision), the reference epoch of the fields.toml astrometry
ROLLOFF_NOTE = re.compile(r"D(\d): white = vmax \+ ([0-9.eE+-]+) MJy/sr")
_NUM = r"([-+]?\d+(?:\.\d*)?)"
ASTROMETRY_LINE = re.compile(rf"#\s*J2000\s+{_NUM}\s+{_NUM}\s*\|\s*pm\s*\(\s*{_NUM}\s*,\s*{_NUM}\s*\)\s*mas/yr")
PARALLAX = re.compile(rf"plx\s+{_NUM}\s*mas")
FIELD_ID = re.compile(r'^\s*id\s*=\s*"([^"]+)"', re.MULTILINE)


@dataclass(frozen=True)
class Astrometry:
    """Catalog astrometry of a target as written in a ``fields.toml`` comment (ICRS, epoch J2000.0)."""

    ra_deg: float
    dec_deg: float
    pm_ra_cosdec_mas_yr: float
    pm_dec_mas_yr: float
    parallax_mas: float | None
    source: str  # the comment lines the values were read from, verbatim

    def position_at(self, mjd: float) -> tuple[float, float]:
        """Linear proper motion from J2000.0 to ``mjd`` (no parallax): ICRS (ra, dec) in degrees."""
        pm = (self.pm_ra_cosdec_mas_yr, self.pm_dec_mas_yr, J2000_MJD)
        return propagate(self.ra_deg, self.dec_deg, pm, mjd)

    @property
    def total_pm_arcsec_yr(self) -> float:
        return float(np.hypot(self.pm_ra_cosdec_mas_yr, self.pm_dec_mas_yr)) / 1000.0


def catalog_astrometry(path: Path = FIELDS_TOML) -> dict[str, Astrometry]:
    """Field id -> astrometry parsed from the ``# J2000 ra dec | pm (a, b) mas/yr | plx p mas`` comments.

    Fields without such a comment are left out (the report then says "expected: not available").
    """
    text = path.read_text(encoding="utf-8")
    out: dict[str, Astrometry] = {}
    for block in text.split("[[field]]")[1:]:
        ident = FIELD_ID.search(block)
        if ident is None:
            continue
        for line in block.splitlines():
            m = ASTROMETRY_LINE.search(line)
            if m is None:
                continue
            plx = PARALLAX.search(line)
            sources = [s.strip() for s in block.splitlines() if s.strip().startswith("# Source:")]
            out[ident.group(1)] = Astrometry(
                ra_deg=float(m.group(1)),
                dec_deg=float(m.group(2)),
                pm_ra_cosdec_mas_yr=float(m.group(3)),
                pm_dec_mas_yr=float(m.group(4)),
                parallax_mas=float(plx.group(1)) if plx else None,
                source=" / ".join(s.lstrip("#").strip() for s in [line, *sources[:1]]),
            )
            break
    return out


@dataclass(frozen=True)
class PublishedFrame:
    """One published frame: its contract metadata, season and the decoded PNG."""

    meta: Frame
    season: int
    grey: np.ndarray  # uint8 (h, w), PNG orientation
    decoded: Decoded
    highlight: float | None  # roll-off top [MJy/sr] if the detector has one

    @property
    def frame_id(self) -> str:
        return self.meta.id

    @property
    def detector(self) -> int:
        return self.meta.detector

    @property
    def mjd(self) -> float:
        return self.meta.mjd

    @property
    def values(self) -> np.ndarray:
        return self.decoded.values

    @property
    def clipped(self) -> np.ndarray:
        return self.decoded.high_clip


@dataclass(frozen=True)
class LoadedField:
    field: SkyField
    directory: Path
    frames: tuple[PublishedFrame, ...]
    rolloff: dict[int, float]  # detector -> white level above Stretch.vmax [MJy/sr] (build provenance note)
    problems: tuple[str, ...]  # integrity problems found while loading (missing PNG, wrong size, ...)

    @property
    def shape(self) -> tuple[int, int]:
        return self.field.grid.height_px, self.field.grid.width_px

    @property
    def centre_xy(self) -> tuple[float, float]:
        h, w = self.shape
        return (w - 1) / 2, (h - 1) / 2

    def expected_xy(self, astrometry: Astrometry | None, mjd: float) -> tuple[float, float]:
        """Target position on the grid at ``mjd`` (PNG pixels); the field centre without astrometry."""
        if astrometry is None:
            return self.centre_xy
        ra, dec = astrometry.position_at(mjd)
        x, y = sky_to_png_xy(self.field.grid, ra, dec)
        return float(x), float(y)


def read_png(path: Path) -> tuple[np.ndarray, np.ndarray]:
    """(grey uint8, nodata bool) of a published grey (L) or grey+alpha (LA) frame PNG."""
    with Image.open(path) as im:
        mode = im.mode
        arr = np.array(im)
    if mode == "L":
        return arr, np.zeros(arr.shape, bool)
    if mode == "LA":
        return arr[..., 0], arr[..., 1] == 0
    raise ValueError(f"{path.name}: expected an L or LA frame PNG, got mode {mode}")


def rolloff_levels(notes: list[str]) -> dict[int, float]:
    """Detector -> roll-off white level above vmax, from the build's display note (``D1: white = vmax + X``)."""
    out: dict[int, float] = {}
    for note in notes:
        for det, top in ROLLOFF_NOTE.findall(note):
            out[int(det)] = float(top)
    return out


def _load_frame(directory: Path, meta: Frame, season: int, field: SkyField, rolloff: dict[int, float]):
    if meta.stretch is None:
        return None, f"{meta.id}: no stretch in field.json, cannot decode"
    path = directory / meta.image
    if not path.is_file():
        return None, f"{meta.id}: PNG missing ({meta.image})"
    try:
        grey, nodata = read_png(path)
    except (OSError, ValueError) as e:
        return None, f"{meta.id}: unreadable PNG ({e})"
    if grey.shape != (field.grid.height_px, field.grid.width_px):
        return (
            None,
            f"{meta.id}: PNG is {grey.shape[1]}x{grey.shape[0]}, grid is {field.grid.width_px}x{field.grid.height_px}",
        )
    extra = rolloff.get(meta.detector)
    highlight = None if extra is None else meta.stretch.vmax + extra
    frame = PublishedFrame(meta, season, grey, decode(grey, meta.stretch, highlight, nodata), highlight)
    return frame, None


def load_field(directory: Path) -> LoadedField:
    """Read ``directory/field.json`` and decode every frame PNG; problems are collected, not raised."""
    field = SkyField.model_validate_json((directory / "field.json").read_text(encoding="utf-8"))
    rolloff = rolloff_levels(field.provenance.notes)
    seasons = season_index([f.mjd for f in field.frames])
    frames, problems = [], []
    for meta, season in zip(field.frames, seasons, strict=True):
        frame, problem = _load_frame(directory, meta, season, field, rolloff)
        if frame is not None:
            frames.append(frame)
        if problem is not None:
            problems.append(problem)
    return LoadedField(field, directory, tuple(frames), rolloff, tuple(problems))


def discover_fields(products: Path) -> list[Path]:
    """Field directories (``<products>/fields/<id>/field.json``), sorted by id."""
    root = products / "fields"
    if not root.is_dir():
        raise FileNotFoundError(f"no fields/ directory under {products}")
    return sorted(p.parent for p in root.glob("*/field.json"))


def groups(frames: tuple[PublishedFrame, ...] | list[PublishedFrame]) -> dict[tuple[int, int], list[PublishedFrame]]:
    """(season, detector) -> frames, sorted by time."""
    out: dict[tuple[int, int], list[PublishedFrame]] = defaultdict(list)
    for f in sorted(frames, key=lambda f: f.mjd):
        out[(f.season, f.detector)].append(f)
    return dict(sorted(out.items()))
