"""WS2-8: caveats of the product check, written from the numbers of the same report.

Each caveat is one sentence built from a field's section of ``report.json``, so ``report.md``, ``report.json`` and
any text copied from them carry the same numbers. Where a FITS validation record (``docs/validation/<id>.md``) has a
number that changes how a PNG number reads, it is quoted with its record. Those records analysed the fields as
built by #17, whose frame selection partly differs from the rebuilt fields checked here, so only their all-frames
FITS numbers are quoted.
"""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass

from .productcheck_motion import MIN_TARGET_SNR

OFF_SIGMA = 3.0  # a season pair whose 2-D residual reaches this many sigmas is called off the catalog motion
LENGTH_AGREES_SIGMA = 2.0  # |shift - expected| below this many sigmas: the length agrees
WEAK_SCATTER_FRAMES = 5  # a frame-scatter uncertainty from fewer per-frame centroids per season is weak
VISIBLE_FRACTION = 0.5  # target at >= MIN_TARGET_SNR in fewer frames than this: the blink cannot show its motion
MISREGISTERED = re.compile(r"(\S+D\d): misregistered frame: field stars ([0-9.]+) px")


@dataclass(frozen=True)
class FitsShift:
    """A season shift measured in the FITS by a validation record, over all its frames."""

    record: str
    method: str  # how the record measured it, as written there
    season_a: int
    season_b: int
    length_px: tuple[float, float]  # range over the record's original analysis and its review
    pa_deg: tuple[float, float]
    expected: str  # the record's expected value, as written there
    note: str = ""  # may use {catalog_dpa}: |PA - expected PA| of the matching PNG shift


@dataclass(frozen=True)
class OrientationOffset:
    """A season observed with the detector rotated 180 deg, and the record's FITS offset of that season."""

    record: str
    season: int
    reference: tuple[int, int]  # the two seasons with the other orientation
    fits_east_arcsec: tuple[float, float]  # range of season - mean(reference) in E over the record's estimators
    fits_named: str
    parallax: str


# Seasons with the same patch orientation, per the FITS validation records (rotated ~180 deg between groups).
ORIENTATION_GROUPS: dict[str, tuple[tuple[int, ...], ...]] = {
    "barnards-star": ((0, 2), (1,)),  # docs/validation/barnards-star.md: S1 has the detector rotated 180 deg
    "eps-indi-b": ((0, 2), (1, 3)),  # docs/validation/eps-indi-b.md: patch rotated ~180 deg between S0/S2 and S1/S3
}
FITS_SHIFTS: dict[str, FitsShift] = {
    "barnards-star": FitsShift(
        "docs/validation/barnards-star.md",
        "the 358 exposures covering it, proper motion + parallax",
        0,
        2,
        (1.655, 1.665),
        (354.1, 355.4),
        "1.665 px at PA 355.7 deg",
    ),
    "eps-indi-b": FitsShift(
        "docs/validation/eps-indi-b.md",
        "all frames, same detector in both seasons, proper motion + parallax",
        0,
        3,
        (1.026, 1.031),
        (126.5, 126.7),
        "1.028-1.030 px at PA 125.8-125.9 deg",
        "With parallax the record expects PA 125.8-125.9 deg against 121.8 deg from the proper motion alone (the "
        "expected value of this check), so about 4 deg of the {catalog_dpa:.1f} deg PA difference against the "
        "catalog is the parallax this check ignores.",
    ),
}
ORIENTATION_OFFSETS: dict[str, OrientationOffset] = {
    "barnards-star": OrientationOffset(
        "docs/validation/barnards-star.md",
        1,
        (0, 2),
        (-0.66, 1.35),
        '+0.63" gcS, +1.22" rp, -0.66" satc',
        'the record gives +0.546" E in S1 against -0.504" and -0.477" E in S0 and S2',
    ),
}
RECORD_NOTES: dict[str, tuple[str, ...]] = {
    "wise-0855": (
        "docs/validation/wise-0855.md (FITS): with all 93 D5/D6 exposures the motion is measured, S0->S2 8.51 +- "
        '0.39" (1.38 +- 0.06 px) at PA 278.5 +- 2.6 deg against 8.03" (1.31 px) at PA 274.6 deg expected; the record '
        "also finds that the blink of the build it analysed (12 D5/D6 frames, 2 per season x detector) does not show "
        "the object convincingly.",
    ),
    "eps-indi-b": (
        "docs/validation/eps-indi-b.md also finds a Dec residual that alternates between S0/S2 and S1/S3 (~0.01-0.025 "
        "px in the FITS), with the patch rotated ~180 deg between them (INFERRED there: an orientation-dependent "
        "centroid or WCS systematic).",
    ),
    "rw-aurigae": (
        "docs/validation/rw-aurigae.md (FITS): in 2026W38_1A_0162_3D6 four Gaia stars fall -1.21 to -1.36 px off in x "
        "although its header says FINAST = 0 ('good'); the neighbouring exposures are < 0.1 px off.",
    ),
}


def _dets(ds) -> str:
    return ",".join(f"D{d}" for d in ds)


def _pair(s: dict) -> str:
    return f"S{s['season_a']}->S{s['season_b']}"


def _dpa(pa: float, reference: float) -> float:
    """Signed PA difference in (-180, 180] deg."""
    return (pa - reference + 180.0) % 360.0 - 180.0


def _has_position(g: dict, estimator: str) -> bool:
    return g["coadd_status"] == "ok" if estimator == "core" else g["n_plateaus"] > 0


def weak_uncertainty(m: dict) -> list[str]:
    """The headline uncertainty comes from the scatter of very few per-frame centroids (one detector)."""
    h = m["headline"]
    if h is None or h["uncertainty_from"] != "frames":
        return []
    det = h["detectors"][0]
    key = "n_core_frames" if h["estimator"] == "core" else "n_plateaus"
    n = {(g["season"], g["detector"]): g[key] for g in m["groups"]}
    na, nb = n[(h["season_a"], det)], n[(h["season_b"], det)]
    if min(na, nb) >= WEAK_SCATTER_FRAMES:
        return []
    against = "" if h["expected_px"] is None else f" against {h['expected_px']:.3f} px expected"
    sigma = "" if h["residual_sigma"] is None else f" ({h['residual_sigma']:.1f} sigma residual)"
    return [
        f"{_pair(h)} rests on one detector (D{det}): its uncertainty is the scatter (ddof=1) of only {na} per-frame "
        f"{h['estimator']} centroids in S{h['season_a']} and {nb} in S{h['season_b']}, divided by sqrt(n), so "
        f"{h['shift_px']:.3f} +- {h['sigma_px']:.3f} px{against}{sigma} is a weak constraint."
    ]


def lost_seasons(m: dict) -> list[str]:
    """Seasons where no target detector gives a position for the headline estimator."""
    h = m["headline"]
    if h is None:
        return []
    by_season = defaultdict(list)
    for g in m["groups"]:
        if g["detector"] in m["target_detectors"]:
            by_season[g["season"]].append(g)
    out = []
    for season, gs in sorted(by_season.items()):
        if any(_has_position(g, h["estimator"]) for g in gs):
            continue
        what = "; ".join(
            f"D{g['detector']} {g['coadd_status']}" + ("" if g["coadd_snr"] is None else f", S/N {g['coadd_snr']:.1f}")
            for g in gs
        )
        out.append(
            f"S{season} gives no {h['estimator']} position on {_dets(m['target_detectors'])} (coadd {what}; a "
            f"position needs S/N >= {MIN_TARGET_SNR:g}), so no season shift uses S{season}."
        )
    return out


def blink_visibility(m: dict) -> list[str]:
    """A faint target: too few frames where it reaches the detection threshold for the blink to show it move."""
    h = m["headline"]
    if h is None or h["estimator"] != "core":
        return []
    frames = [p for p in m["frames"] if p["detector"] in m["target_detectors"]]
    ok = [p for p in frames if p["core_status"] == "ok"]
    if not frames or len(ok) >= VISIBLE_FRACTION * len(frames):
        return []
    where = ", ".join(f"S{s} D{d}" for s, d in sorted({(p["season"], p["detector"]) for p in ok})) or "none"
    step = "" if h["expected_px"] is None else f"; the expected {_pair(h)} step is {h['expected_px']:.3f} px"
    return [
        f"The target reaches {MIN_TARGET_SNR:g} pixel sigmas in only {len(ok)} of {len(frames)} frames of "
        f"{_dets(m['target_detectors'])} ({where}), so the published blink cannot show its motion{step}."
    ]


def direction(m: dict) -> list[str]:
    """The headline shift is off the catalog in 2-D: say whether that is the length or the direction."""
    h = m["headline"]
    if h is None or h["residual_sigma"] is None or h["residual_sigma"] < OFF_SIGMA or not h["sigma_px"]:
        return []
    dpa = abs(_dpa(h["pa_deg"], h["expected_pa_deg"]))
    length_sigma = abs(h["shift_px"] - h["expected_px"]) / h["sigma_px"]
    length = (
        f"the length agrees ({h['shift_px']:.3f} +- {h['sigma_px']:.3f} vs {h['expected_px']:.3f} px expected, "
        f"{length_sigma:.1f} sigma) but"
        if length_sigma < LENGTH_AGREES_SIGMA
        else f"the length ({h['shift_px']:.3f} +- {h['sigma_px']:.3f} vs {h['expected_px']:.3f} px) differs and"
    )
    return [
        f"{_pair(h)}: {length} the 2-D residual is {h['residual_px']:.3f} px ({h['residual_sigma']:.1f} sigma) and "
        f"the PA is {dpa:.1f} deg off ({h['pa_deg']:.1f} vs {h['expected_pa_deg']:.1f} deg)."
    ]


def pair_consistency(field_id: str, m: dict) -> list[str]:
    """Raw season pairs of the headline estimator: which ones are off the catalog motion by >= OFF_SIGMA."""
    h = m["headline"]
    if h is None:
        return []
    raw = [
        s
        for s in m["shifts"]
        if not s["registration_corrected"] and s["estimator"] == h["estimator"] and s["residual_sigma"] is not None
    ]
    if len(raw) < 2 or all(s["residual_sigma"] < OFF_SIGMA for s in raw):
        return []

    def listing(pairs: list[dict]) -> str:
        return ", ".join(f"{_pair(s)} {s['residual_px']:.3f} px ({s['residual_sigma']:.1f} sigma)" for s in pairs)

    groups = ORIENTATION_GROUPS.get(field_id)
    if groups is None:
        off = [s for s in raw if s["residual_sigma"] >= OFF_SIGMA]
        within = [s for s in raw if s["residual_sigma"] < OFF_SIGMA]
        split = f"off by >= {OFF_SIGMA:g} sigma: {listing(off)}; within: {listing(within) or 'none'}"
    else:
        same = [s for s in raw if any(s["season_a"] in g and s["season_b"] in g for g in groups)]
        across = [s for s in raw if s not in same]
        orient = " vs ".join("/".join(f"S{x}" for x in g) for g in groups)
        split = (
            f"same orientation ({orient}, per the record): {listing(same) or 'none'}; "
            f"across orientations: {listing(across) or 'none'}"
        )
    return [
        f"Season pairs ({h['estimator']}, raw), residual against the catalog motion: {split}. The uncertainty "
        "(scatter between detectors, or frames, / sqrt(n)) leaves out an offset shared by a whole season "
        "(orientation, parallax, display), so it understates the error of a single season pair."
    ]


def fits_shift(field_id: str, m: dict) -> list[str]:
    ref = FITS_SHIFTS.get(field_id)
    if ref is None:
        return []
    match = [
        s
        for s in m["shifts"]
        if not s["registration_corrected"] and (s["season_a"], s["season_b"]) == (ref.season_a, ref.season_b)
    ]
    match = [s for s in match if s["estimator"] == m["headline"]["estimator"]] if m["headline"] else []
    if not match:
        return []
    s = match[0]
    dl = (s["shift_px"] - ref.length_px[1], s["shift_px"] - ref.length_px[0])
    dpa = tuple(_dpa(s["pa_deg"], pa) for pa in (ref.pa_deg[1], ref.pa_deg[0]))
    sentence = (
        f"{ref.record} (FITS, {ref.method}): {_pair(s)} {ref.length_px[0]:.3f}-{ref.length_px[1]:.3f} px at PA "
        f"{ref.pa_deg[0]:.1f}-{ref.pa_deg[1]:.1f} deg (original analysis and review) against {ref.expected} expected. "
        f"These PNGs ({s['estimator']}): {s['shift_px']:.3f} +- {s['sigma_px']:.3f} px at PA {s['pa_deg']:.1f} deg, "
        f"i.e. {dl[0]:+.3f} to {dl[1]:+.3f} px and {dpa[0]:+.1f} to {dpa[1]:+.1f} deg from the FITS."
    )
    if not ref.note or s["expected_pa_deg"] is None:
        return [sentence]
    return [sentence, ref.note.format(catalog_dpa=abs(_dpa(s["pa_deg"], s["expected_pa_deg"])))]


def _season_offset(m: dict, season: int, estimator: str) -> tuple[float, float] | None:
    """Mean (measured - expected) PNG offset (dx, dy) of a season over the target detectors."""
    pts = []
    for g in m["groups"]:
        if g["season"] != season or g["detector"] not in m["target_detectors"] or not _has_position(g, estimator):
            continue
        x, y = (g["coadd_x"], g["coadd_y"]) if estimator == "core" else (g["plateau_x"], g["plateau_y"])
        pts.append((x - g["expected_x"], y - g["expected_y"]))
    if not pts:
        return None
    return sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts)


def orientation_offset(field_id: str, m: dict) -> list[str]:
    ref = ORIENTATION_OFFSETS.get(field_id)
    if ref is None or m["headline"] is None:
        return []
    est = m["headline"]["estimator"]
    offsets = [_season_offset(m, s, est) for s in (ref.season, *ref.reference)]
    if any(o is None for o in offsets):
        return []
    (sx, sy), (ax, ay), (bx, by) = offsets
    dx, dy = sx - (ax + bx) / 2, sy - (ay + by) / 2
    scale = m["pixel_scale_arcsec"]
    east, north = -dx * scale + 0.0, -dy * scale + 0.0  # PNG +x = west, +y = south; + 0.0: no "-0.00"
    lo, hi = ref.fits_east_arcsec
    return [
        f"S{ref.season} has the detector rotated 180 deg ({ref.record}). On these PNGs the S{ref.season} {est} "
        f'centroid sits {east:+.2f}" E, {north:+.2f}" N ({-dx:+.3f} px E) from the mean of '
        f"S{ref.reference[0]} and S{ref.reference[1]}, relative to the proper-motion-only expected track (parallax "
        f"ignored here; {ref.parallax}). In the FITS the record's S{ref.season} - mean(S{ref.reference[0]}, "
        f'S{ref.reference[1]}) offset in E ranges from {lo:+.2f}" to {hi:+.2f}" depending on the estimator '
        f"({ref.fits_named}): it takes both signs, so no agreement in direction with it is claimed."
    ]


def _frame_parts(fid: str) -> tuple[str, str, int]:
    """(obs_id = exposure, observation sequence, detector) of a frame id ``<obs_id>D<n>``."""
    obs, det = fid[: fid.rindex("D")], int(fid[fid.rindex("D") + 1 :])
    return obs, obs.rsplit("_", 1)[0], det


def _display_anomaly(fid: str, v: dict | None) -> str:
    """What sets this frame apart in the brightness check: its white disc, and the blink pairs that rest on it."""
    me = None if v is None else next((c for c in v["levels"] if c["frame_id"] == fid), None)
    if me is None:
        return ""
    det = me["detector"]
    others = [c["plateau_area"] for c in v["levels"] if c["detector"] == det and c["frame_id"] != fid]
    parts = []
    if others and not min(others) <= me["plateau_area"] <= max(others):
        parts.append(
            f"white disc {me['plateau_area']} px against {min(others)}-{max(others)} px in the other "
            f"{len(others)} D{det} frames"
        )
    visible = [p for p in v["pairs"] if p["blink_visible"] and p["detector"] == det]
    mine = [p for p in visible if fid in (p["earlier"], p["later"])]
    if mine and len(mine) == len(visible):
        which = f"the only D{det} pair" if len(visible) == 1 else f"all {len(visible)} D{det} pairs"
        parts.append(f"it is in {which} whose blink shows a change, so that change rests on this one frame")
    elif mine:
        parts.append(f"it is in {len(mine)} of the {len(visible)} D{det} pairs whose blink shows a change")
    return "; ".join(parts)


def _registration(fid: str, reg: dict) -> str:
    px = reg["per_frame_px"].get(fid)
    if px is None:
        return "PNG registration not checkable"
    return f"PNG registration {px:.3f} px" + (", the field's largest" if fid == reg["worst_frame"] else "")


def misregistered_neighbours(section: dict) -> list[str]:
    """Published frames of the same exposure / observation sequence as a frame the build rejected as misregistered."""
    s = section["summary"]
    reg = s["png_registration"]
    out = []
    for fid, px in (m for note in s["skipped_note"] for m in MISREGISTERED.findall(note)):
        obs, seq, det = _frame_parts(fid)
        same_exposure = [f for f in reg["per_frame_px"] if _frame_parts(f)[0] == obs]
        same_detector = [f for f in reg["per_frame_px"] if _frame_parts(f)[1:] == (seq, det) and f not in same_exposure]
        if not same_exposure and not same_detector:
            continue
        listed = [f"{f} ({_registration(f, reg)})" for f in sorted(same_exposure)]
        groups = [f"the same exposure {obs}: " + ", ".join(listed)] if listed else []
        listed = [f"{f} ({_registration(f, reg)})" for f in sorted(same_detector)]
        groups += [f"other exposures of the sequence {seq} on D{det}: " + ", ".join(listed)] if listed else []
        sizes = [reg["per_frame_px"][f] for f in same_exposure + same_detector]
        fine = all(x is not None and x <= reg["threshold_px"] for x in sizes)
        own = f"Their own registration is within {reg['threshold_px']} px, but" if fine else "Also"
        out.append(
            f"{fid} was rejected by the build as misregistered (field stars {px} px off). Published frames from "
            f"{'; '.join(groups)}. {own} treat them with caution: they come from the same observation sequence as "
            "a rejected frame."
        )
        for f in sorted(same_exposure + same_detector):
            anomaly = _display_anomaly(f, section["variable"])
            if anomaly:
                out.append(f"{f}: {anomaly}.")
    return out


def field_caveats(section: dict) -> list[str]:
    """Every caveat of one field section (JSON-ready), in reading order; empty when none applies."""
    fid, m = section["id"], section["motion"]
    out = []
    if m is not None and m["headline"] is not None:
        out += weak_uncertainty(m) + lost_seasons(m) + blink_visibility(m) + direction(m)
        out += pair_consistency(fid, m) + fits_shift(fid, m) + orientation_offset(fid, m)
    out += misregistered_neighbours(section)
    return out + list(RECORD_NOTES.get(fid, ()))
