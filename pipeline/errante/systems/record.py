"""Record the frozen WS3 object-context snapshots listed in ``targets.toml`` (WS7, dev only).

The build never runs this: ``systems.measured`` reads the JSON files in ``inputs/objects/`` only, so a WS3
change to its queries or formatting cannot change the published 3D systems until someone re-records here
(``errante systems --record <slug|all>``) and reviews the diff.

Two sources:

- default: replay the WS3 fixtures (``pipeline/tests/fixtures/ws3/context``, raw service answers recorded
  live by WS3) with ``object_context(name=..., offline=True)``. No network; reproducible.
- ``live=True``: query the archives into an empty temporary cache. Refused when a service answers with an
  error or when the Gaia astrophysical parameters did not come from the ESA archive (the VizieR fallback has
  no FLAME, Bailer-Jones or LPV values), so a snapshot taken during an outage is never committed by accident.
"""

from __future__ import annotations

import hashlib
import json
import tempfile
from datetime import UTC, datetime
from pathlib import Path

from .. import settings

FIXTURES_DIR = settings.REPO_ROOT / "pipeline" / "tests" / "fixtures" / "ws3" / "context"
SNAPSHOT_SCHEMA = 1
_GAIA_KEYS = (
    "source_id",
    "ra",
    "dec",
    "ref_epoch",
    "pmra",
    "pmra_error",
    "pmdec",
    "pmdec_error",
    "parallax",
    "parallax_error",
    "radial_velocity",
    "radial_velocity_error",
    "ruwe",
    "phot_g_mean_mag",
    "details_from",
)
_PLANET_KEYS = (
    "name",
    "letter",
    "match",
    "period_d",
    "semi_major_axis_au",
    "eccentricity",
    "inclination_deg",
    "mass_earth",
    "mass_kind",
    "radius_earth",
    "radius_calculated",
    "reference",
    "controversial",
)


class RecordError(RuntimeError):
    """The snapshot was not written (service error, fallback source, or no fixtures)."""


def _rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(settings.REPO_ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def _context_with_files(name: str, cache_dir: Path, offline: bool):
    """Run WS3 ``object_context`` and list the cache files it read (spy on the WS3 cache-path helper)."""
    from ..science import context as C

    read: list[Path] = []
    original = C._Http._path

    def spy(self, service, url, params):  # noqa: ANN001 - mirrors the private WS3 signature
        path = original(self, service, url, params)
        read.append(path)
        return path

    C._Http._path = spy
    try:
        ctx = C.object_context(name=name, cache_dir=cache_dir, offline=offline)
    finally:
        C._Http._path = original
    return ctx, sorted({p for p in read if p.is_file()})


def snapshot_document(slug: str, query: str, *, live: bool = False, fixtures: Path = FIXTURES_DIR) -> dict:
    """Build the snapshot document for one registry entry (see module docstring)."""
    from ..science import context as C

    if live:
        tmp = Path(tempfile.mkdtemp(prefix=f"errante-record-{slug}-"))
        ctx, files = _context_with_files(query, tmp, offline=False)
        errors = [p for p in ctx.provenance if p.status == "error"]
        if errors:
            raise RecordError(f"{slug}: service errors {[(p.service, p.note) for p in errors]}; not recorded")
        details = ctx.gaia.source.details_from if ctx.gaia and ctx.gaia.source else None
        if details is not None and "ESA" not in details:
            raise RecordError(
                f"{slug}: Gaia parameters from {details!r} (fallback, no FLAME/Bailer-Jones); not recorded"
            )
        how = f"live archives via errante.science.context.object_context(name={query!r}) into a fresh cache"
        cache_label = "temporary cache (live)"
    else:
        if not fixtures.is_dir():
            raise RecordError(f"WS3 fixtures not found at {fixtures}")
        ctx, files = _context_with_files(query, fixtures, offline=True)
        how = (
            f"offline replay of the WS3 fixtures: errante.science.context.object_context(name={query!r}, offline=True)"
        )
        cache_label = _rel(fixtures)
    doc = ctx.to_dict()
    gaia = doc.get("gaia") or {}
    source = gaia.get("source") or None
    stamps = sorted(p["retrieved_utc"] for p in doc["provenance"] if p.get("retrieved_utc"))
    return {
        "schema": SNAPSHOT_SCHEMA,
        "slug": slug,
        "query": {"name": query, "epoch_mjd": doc["epoch_mjd"], "radius_arcsec": doc["query"]["radius_arcsec"]},
        "recorded_utc": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "origin": {
            "kind": "live" if live else "ws3-fixtures",
            "how": how,
            "cache_dir": cache_label,
            "retrieved_utc": [stamps[0], stamps[-1]] if stamps else None,
            "files": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in files},
            "services": [
                {k: p.get(k) for k in ("service", "catalog", "status", "retrieved_utc", "cached", "note")}
                for p in doc["provenance"]
            ],
            "note": "Catalog values (Gaia DR3, SIMBAD, AAVSO VSX, NASA Exoplanet Archive): not measured by SPHEREx.",
        },
        "identity": {
            "display_name": doc.get("display_name"),
            "main_id": doc.get("main_id"),
            "object_type": doc.get("object_type"),
            "object_type_label": doc.get("object_type_label"),
            "spectral_type": doc.get("spectral_type"),
            "match": C.identity_match(ctx),
            "identity_uncertain": doc.get("identity_uncertain"),
            "gaia_source_id": str(source["source_id"]) if source else None,
            "gaia_method": gaia.get("method"),
            "gaia_ambiguous": gaia.get("ambiguous"),
            "gaia_loose": gaia.get("loose"),
        },
        "gaia": None
        if source is None
        else {k: (str(source[k]) if k == "source_id" else source.get(k)) for k in _GAIA_KEYS},
        "variability": doc.get("variability"),
        "planets": [{k: p.get(k) for k in _PLANET_KEYS} for p in doc.get("planets", [])],
        "nearby_planet_hosts": doc.get("nearby_planet_hosts", []),
        "warnings": doc.get("warnings", []),
        "facts": doc["facts"],
        "parameters": {p["key"]: {k: v for k, v in p.items() if k != "key"} for p in doc["parameters"]},
    }


def write_snapshot(doc: dict, objects_dir: Path) -> Path:
    objects_dir.mkdir(parents=True, exist_ok=True)
    path = objects_dir / f"{doc['slug']}.json"
    with path.open("w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(doc, indent=1, ensure_ascii=False) + "\n")
    return path


def record(slugs: list[str] | None = None, *, live: bool = False, objects_dir: Path | None = None) -> list[Path]:
    """Re-record the registry snapshots (all when ``slugs`` is None). Returns the written paths."""
    from .measured import OBJECTS_DIR, load_registry

    queries = load_registry().snapshots
    unknown = sorted(set(slugs or []) - set(queries))
    if unknown:
        raise RecordError(f"not in targets.toml [snapshots]: {unknown}")
    out = objects_dir or OBJECTS_DIR
    todo = list(slugs or sorted(queries))
    if not live:
        # A snapshot recorded live has no WS3 fixtures to replay: 'all' skips it, naming it is an error.
        live_only = [s for s in todo if committed_origin_kind(s, OBJECTS_DIR) == "live"]
        if slugs and live_only:
            raise RecordError(f"recorded live, no WS3 fixtures to replay offline (use --live): {live_only}")
        todo = [s for s in todo if s not in live_only]
    return [write_snapshot(snapshot_document(s, queries[s], live=live), out) for s in todo]


def committed_origin_kind(slug: str, objects_dir: Path) -> str | None:
    """origin.kind of the committed snapshot ('ws3-fixtures' or 'live'), or None when there is none yet."""
    path = objects_dir / f"{slug}.json"
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8")).get("origin", {}).get("kind")
