"""Public acquisition/interpretation notes; no scientific measurements are changed here."""

from datetime import datetime
from importlib.metadata import PackageNotFoundError, version


def acquisition_notes(search, timings, *, box_px, planes, deadline_s):
    service = search.get("service", "unknown")
    service = service if service in {"sia", "tap", "snapshot", "given"} else "unknown"
    notes = [
        f"Archive search service: {service}; from_cache={bool(search.get('from_cache'))}; "
        f"stale={bool(search.get('stale'))}.",
        f"Input stamps: box_px={box_px}; planes={','.join(planes)}.",
    ]
    if service == "snapshot":
        # WS1's warning carries the actual query date. Do not publish arbitrary error/warning text.
        dates = []
        for warning in search.get("warnings", []):
            if " answer of " not in warning:
                continue
            try:
                dates.append(datetime.fromisoformat(warning.split(" answer of ", 1)[1].split(")", 1)[0]).isoformat())
            except ValueError:
                continue
        notes.append("Search snapshot query date: " + (", ".join(sorted(set(dates))) or "unavailable") + ".")
    timed_out = timings.get("timed_out", 0) or 0
    if timed_out:
        notes.append(
            f"{int(timed_out)} exposures were not read within the {deadline_s:g} s archive deadline; partial data."
        )
    versions = []
    for package in ("errante", "numpy", "astropy", "scipy", "photutils", "pydantic"):
        try:
            versions.append(f"{package}={version(package)}")
        except PackageNotFoundError:
            versions.append(f"{package}=not-installed")
    notes.append("Effective package versions: " + ", ".join(versions) + ".")
    return notes


def target_notes(target_id, params, curve):
    """Selection counts and dates describe this product, never a larger offline validation dataset."""
    notes = []
    if target_id == "rw-aurigae":
        saturated = curve.excluded.get("saturated", 0)
        notes.extend(
            [
                "RW Aur A+BC is unresolved (about 1.5 arcsec separation); this is the blended system, not A alone.",
                f"{saturated} saturated exposures (lower limits) are excluded, preferentially removing bright states. "
                "This is not a complete brightness history.",
                "Uncorrected aperture flux (r = 3 px); no aperture correction. D1 is selected because D2-D6 "
                "saturate at this position. No period is inferred from these sparse usable measurements.",
            ]
        )
    if target_id == "r-draconis" and set(params.collections) <= {"spherex_dr1", "spherex_qr3"}:
        notes.append(
            "R Draconis: wide survey only (DR1+QR3); deep collections are excluded. "
            "The larger offline validation record includes deep observations; its exposure count and "
            "period interval do not describe this product."
        )
    if curve.points:
        dates = sorted(str(p.date)[:10] for p in curve.points)
        notes.append(f"Measured exposures: {len(curve.points)}; observation dates {dates[0]} to {dates[-1]} UTC.")
    return notes
