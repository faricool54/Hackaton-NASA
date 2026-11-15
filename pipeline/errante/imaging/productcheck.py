"""WS2-8 (R05): versioned check of the PUBLISHED products of each target, from field.json + the PNGs alone.

    python -m errante.imaging.productcheck --products data/products --out <dir>

For every field under ``<products>/fields/`` it decodes each frame PNG back to approximate MJy/sr
(``invert``: the frame's asinh Stretch and, where the build used one, the highlight roll-off) and writes
``<out>/report.md``, ``<out>/report.json`` and small PNG figures:

- every field: frames per season x detector, wavelength coverage, the build's registration note and a
  re-measurement of the field-star registration on the PNGs, composites, integrity of the files;
- proper-motion targets (tag ``proper-motion``): target centroids per season x detector and the shift between
  seasons against the catalog proper motion written in ``config/fields.toml`` comments (``productcheck_motion``);
- variable targets (tag ``variable``): the target's core per frame, clipped/saturated cores and brightness
  ratios at matched wavelength, with field-star controls (``productcheck_variable``).

It is a display-level check on 8-bit PNGs, NOT science photometry or astrometry: it says what the published
blink shows and whether that agrees with the FITS-based validation records (docs/validation/).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np

from .. import __version__
from ..build import FIELDS_TOML
from . import register
from .productcheck_caveats import field_caveats
from .productcheck_data import Astrometry, LoadedField, catalog_astrometry, discover_fields, groups, load_field
from .productcheck_json import astrometry_json, motion_json, rounded, variable_json
from .productcheck_motion import analyse_motion
from .productcheck_variable import analyse_variable

log = logging.getLogger(__name__)

MJD_UNIX_EPOCH = 40587.0
# Detectors where the target itself is seen, when the team's FITS validation found it limited to some.
TARGET_DETECTORS: dict[str, tuple[tuple[int, ...], str]] = {
    "wise-0855": (
        (5, 6),
        "docs/validation/wise-0855.md: FITS forced photometry finds WISE 0855 only in D5/D6; in D1-D4 the source "
        "at its position is the blended background star Gaia DR3 5756956644387831296 (shown in the per-detector "
        "table, left out of the combined shift).",
    ),
}


def mjd_to_date(mjd: float) -> str:
    return (datetime(1970, 1, 1, tzinfo=UTC) + timedelta(days=mjd - MJD_UNIX_EPOCH)).strftime("%Y-%m-%d")


def field_kind(loaded: LoadedField) -> str:
    tags = set(loaded.field.tags)
    if "proper-motion" in tags:
        return "motion"
    if "variable" in tags:
        return "variable"
    return "other"


@dataclass(frozen=True)
class _RegFrame:
    frame_id: str
    detector: int
    data: np.ndarray
    bad: np.ndarray


def png_registration(loaded: LoadedField) -> tuple[dict[str, tuple[float, float] | None], dict]:
    """Field-star registration of every frame re-measured on the decoded PNGs (``register.registrations``)."""
    frames = [_RegFrame(f.frame_id, f.detector, f.values, f.clipped | ~np.isfinite(f.values)) for f in loaded.frames]
    report = register.registrations(frames)
    offsets = {fid: (r.dx, r.dy) if r is not None else None for fid, r in report.frames.items()}
    sizes = {fid: math.hypot(*o) for fid, o in offsets.items() if o is not None}
    worst = max(sizes, key=sizes.get) if sizes else None
    summary = {
        "checked": len(sizes),
        "of": len(frames),
        "median_px": rounded(float(np.median(list(sizes.values()))) if sizes else None),
        "max_px": rounded(sizes[worst] if worst else None),
        "worst_frame": worst,
        "over_threshold": sorted(fid for fid, s in sizes.items() if s > register.MAX_OFFSET_PX),
        "threshold_px": register.MAX_OFFSET_PX,
        "inconsistent": report.inconsistent,
        "per_frame_px": {f.frame_id: rounded(sizes.get(f.frame_id)) for f in frames},  # None: not checkable
    }
    return offsets, summary


def _notes(loaded: LoadedField, prefix: str) -> list[str]:
    return [n for n in loaded.field.provenance.notes if n.startswith(prefix)]


def _composites(loaded: LoadedField) -> dict:
    items = []
    for c in loaded.field.composites:
        path = loaded.directory / c.image
        ok = path.is_file()
        items.append(
            {
                "id": c.id,
                "mode": c.mode,
                "season": c.season,
                "image_ok": ok,
                "channels": [
                    {
                        "color": ch.color,
                        "detector": ch.detector,
                        "wavelength_um": rounded(ch.wavelength_um),
                        "n": len(ch.frame_ids),
                    }
                    for ch in c.channels
                ],
            }
        )
    return {"count": len(items), "missing_images": [i["id"] for i in items if not i["image_ok"]], "items": items}


def field_summary(loaded: LoadedField, registration: dict) -> dict:
    frames = loaded.frames
    seasons = []
    for s in sorted({f.season for f in frames}):
        mjds = [f.mjd for f in frames if f.season == s]
        seasons.append(
            {
                "season": s,
                "n_frames": len(mjds),
                "mjd_min": rounded(min(mjds)),
                "mjd_max": rounded(max(mjds)),
                "date_min": mjd_to_date(min(mjds)),
                "date_max": mjd_to_date(max(mjds)),
            }
        )
    counts = [{"season": s, "detector": d, "n": len(m)} for (s, d), m in groups(frames).items()]
    wavelengths = []
    for d in sorted({f.detector for f in frames}):
        wl = [f.meta.wavelength_um for f in frames if f.detector == d and f.meta.wavelength_um is not None]
        wavelengths.append(
            {
                "detector": d,
                "n": len(wl),
                "min_um": rounded(min(wl), 4) if wl else None,
                "max_um": rounded(max(wl), 4) if wl else None,
            }
        )
    return {
        "n_frames": len(loaded.field.frames),
        "n_decoded": len(frames),
        "problems": list(loaded.problems),
        "grid": f'{loaded.field.grid.width_px}x{loaded.field.grid.height_px} px at {loaded.field.grid.pixel_scale_arcsec}"/px',
        "releases": list(loaded.field.provenance.data_releases),
        "seasons": seasons,
        "counts": counts,
        "wavelengths": wavelengths,
        "rolloff": {str(d): v for d, v in sorted(loaded.rolloff.items())},
        "registration_note": _notes(loaded, "Registration check:"),
        "skipped_note": _notes(loaded, "Skipped"),
        "png_registration": registration,
        "composites": _composites(loaded),
        "thumb_ok": (loaded.directory / "thumb.png").is_file(),
        "field_json_sha256": hashlib.sha256((loaded.directory / "field.json").read_bytes()).hexdigest(),
    }


def check_field(directory: Path, out: Path, astrometry: Mapping[str, Astrometry]) -> dict:
    """Load, measure and draw one field; returns its JSON-ready section of the report."""
    from .productcheck_figures import brightness_figure, track_figure

    loaded = load_field(directory)
    fid = loaded.field.id
    kind = field_kind(loaded)
    astro = astrometry.get(fid)
    offsets, registration = png_registration(loaded)
    section = {
        "id": fid,
        "name": loaded.field.name,
        "kind": kind,
        "synthetic": loaded.field.provenance.synthetic,
        "built_at": loaded.field.provenance.built_at.isoformat(),
        "pipeline_version": loaded.field.provenance.pipeline_version,
        "summary": field_summary(loaded, registration),
        "astrometry": astrometry_json(astro),
        "motion": None,
        "variable": None,
        "figures": [],
    }
    if kind == "motion":
        detectors, note = TARGET_DETECTORS.get(fid, (None, None))
        result = analyse_motion(loaded, astro, offsets, detectors)
        section["motion"] = motion_json(result, loaded, astro, note)
        section["figures"].append(track_figure(loaded, result, out / f"{fid}_track.png"))
    elif kind == "variable":
        vresult = analyse_variable(loaded, astro)
        section["variable"] = variable_json(vresult)
        section["figures"].append(brightness_figure(loaded, vresult, out / f"{fid}_brightness.png"))
    section["caveats"] = field_caveats(section)
    return section


def run_check(products: Path, out: Path, astrometry: Mapping[str, Astrometry] | None = None) -> dict:
    """Check every field under ``products``; writes report.json, report.md and figures into ``out``."""
    from .productcheck_report import render_markdown

    out.mkdir(parents=True, exist_ok=True)
    astro = catalog_astrometry(FIELDS_TOML) if astrometry is None else astrometry
    fields = [check_field(d, out, astro) for d in discover_fields(products)]
    report = {
        "tool": "errante.imaging.productcheck",
        "pipeline_version": __version__,
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "products": products.as_posix(),
        "fields": fields,
    }
    (out / "report.json").write_text(
        json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8", newline="\n"
    )
    (out / "report.md").write_text(render_markdown(report), encoding="utf-8", newline="\n")
    return report


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m errante.imaging.productcheck", description=__doc__.split("\n")[0])
    parser.add_argument("--products", type=Path, default=Path("data/products"), help="products root (fields/<id>/)")
    parser.add_argument("--out", type=Path, required=True, help="output directory for report.md/json and figures")
    parser.add_argument(
        "--fields-toml", type=Path, default=FIELDS_TOML, help="catalog astrometry (comments, read only)"
    )
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    try:
        report = run_check(args.products, args.out, catalog_astrometry(args.fields_toml))
    except (FileNotFoundError, ValueError) as e:
        log.error("product check failed: %s", e)
        return 1
    log.info("checked %d field(s) -> %s", len(report["fields"]), (args.out / "report.md").as_posix())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
