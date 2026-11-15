"""WS2-8: ``report.md`` of the product check, rendered from the same dict that is written as ``report.json``."""

from __future__ import annotations

from collections.abc import Iterable

from .productcheck_measure import APERTURE_RADIUS
from .productcheck_motion import MAX_TARGET_OFFSET_PX, MIN_TARGET_SNR
from .productcheck_variable import (
    BLINK_MIN_DISC_CHANGE,
    BLINK_MIN_DISC_PX,
    BLINK_MIN_GREY,
    HYPOTHESIS_TOLERANCE,
    MATCH_TOLERANCE,
)

METHOD = [
    "**Decoding.** Each frame PNG is mapped back to approximate MJy/sr (`IMAGE - ZODI`) by inverting "
    "`render.to_uint8` with the frame's `Stretch` from `field.json` (asinh, softening 0.1) and, on detectors "
    "whose build note gives a highlight roll-off (`D<n>: white = vmax + X MJy/sr`), the logarithmic roll-off "
    "above `vmax`. Values come back at the centre of their grey level; grey 255 (white) is a lower bound and "
    "grey 0 an upper bound. Transparent pixels are no data.",
    "**Proper motion.** Per frame, a flux-weighted centroid in a 5x5 px box (PSF FWHM ~1.2-2 px) recentred from "
    f"the expected position, accepted if its peak is >= {MIN_TARGET_SNR:g} pixel sigmas above a 4-7 px sky ring "
    f"and it lands within {MAX_TARGET_OFFSET_PX:g} px of the expected position. A box with a white pixel is "
    "refused (core clipped: saturated or above the display range); for those frames the centroid of the "
    "connected white region (white plateau) is reported as a separate, indicative estimator. Per season x "
    "detector the core centroid is re-measured on the mean of the group's frames. The shift between two "
    "seasons is taken per detector and averaged; its uncertainty is the scatter between detectors / sqrt(n) "
    "(with one detector: the scatter of its frames). 'Registration-corrected' subtracts each group's mean "
    "field-star offset re-measured on the same PNGs. Expected = catalog proper motion from the `fields.toml` "
    "comments over the same mean epochs, linear from J2000.0, parallax ignored.",
    f"**Variability.** Per frame, the target's sum above a 5-8 px sky ring in an r = {APERTURE_RADIUS:g} px disc "
    "(the aperture of docs/validation/rw-aurigae.md), its peak grey level, white pixels in the 2.5 px core and "
    "the size of the white disc. Brightness is compared only between frames of the same detector whose "
    f"wavelengths at the target agree within {100 * MATCH_TOLERANCE:g} % (SPHEREx's linear variable filter), and "
    "each pair is checked against the median ratio of the unclipped field stars (>= 20 sigma) measured the same "
    f"way in the same two frames. 'Blink shows a change' = peak grey differs by >= {BLINK_MIN_GREY} levels, or, "
    f"when both cores are white, the white disc changes size by >= {100 * BLINK_MIN_DISC_CHANGE:g} % and >= "
    f"{BLINK_MIN_DISC_PX} px (the disc also depends on the sub-pixel position and the PSF; it is a display "
    "proxy, not a flux).",
    "**Registration.** The build's note is quoted; the field-star registration is then re-measured on the decoded "
    "PNGs with `imaging.register.registrations` (consensus of all frames, target circle excluded).",
]

LIMITS = [
    "Display level only: 8-bit PNGs of reprojected (bilinear) frames, not the native FITS pixels, no PSF fit, "
    "no flux calibration, no VARIANCE plane, no per-pixel flags. Fluxes, errors and astrometry for science come "
    "from the FITS (docs/validation/*.md).",
    "Quantisation: one grey level is ~0.1 % of the stretch range near the sky and ~1 % near white; in the "
    "roll-off it is ~6 % of the value. Values given are level centres.",
    "White (clipped) pixels are bounds. The PNG does not say which pixels were flagged: saturated NaN cores and "
    "detector defects were filled from their neighbours for display (build note), so a white or flat core may be "
    "display fill. Which detectors have unflagged target cores comes only from the build's roll-off note.",
    "White-plateau centroids follow an isophote at the display limit: they move with the star but depend on the "
    "saturated area, the display fill and 1-px quantisation, and in S1 of Barnard's Star the detector is rotated "
    "180 deg (docs/validation/barnards-star.md): treat them as indicative.",
    "Parallax is ignored in the expected shift (its amplitude is given per target). Expected values use the "
    "catalog proper motion as written in `config/fields.toml` comments; nothing was queried.",
    f"The {100 * HYPOTHESIS_TOLERANCE:g} % tolerance used to confirm a stated ratio covers grey-level quantisation "
    "and the pixel aperture on reprojected PNGs; it is not a photometric error bar.",
]


CONTROL_NOTE = (
    "Control: the same measurement on the other detectors, where the source at the target position is not the "
    "target (raw, no registration correction):"
)
PAIRS_NOTE = (
    "Matched-wavelength pairs (ratio = later / earlier of the r = 3 px sums; bound 'lower'/'upper' = one side "
    "clipped, 'none' = both cores white or no data: no ratio):"
)
GROUP_HEADER = ["Season", "Det", "Frames", "Mean MJD", "Expected x, y", "Coadd core centroid", "White plateau (n)"]
DETECTOR_HEADER = [
    "Det",
    "Frames",
    "Core white",
    "Roll-off",
    "Matched pairs",
    "Pairs with a ratio",
    "Blink shows a change",
]
LEVEL_HEADER = [
    "Det",
    "Season",
    "Frame",
    "lambda [um]",
    "Status",
    "Sum [MJy/sr px]",
    "Peak grey",
    "White in core",
    "White disc [px]",
]
PAIR_HEADER = ["Det", "Frames", "lambda [um]", "dl/l [%]", "Ratio", "Bound", "dm [mag]", "Field stars (n)", "Blink"]


def _fmt(x, nd: int = 3, unit: str = "") -> str:
    if x is None:
        return "n/a"
    if isinstance(x, float):
        return f"{x:.{nd}f}{unit}"
    return f"{x}{unit}"


def _pm(value, sigma, nd: int = 3, unit: str = "") -> str:
    if value is None:
        return "n/a"
    if sigma is None:
        return f"{value:.{nd}f}{unit} (no uncertainty: one measurement)"
    return f"{value:.{nd}f} +- {sigma:.{nd}f}{unit}"


def _table(header: list[str], rows: Iterable[list]) -> list[str]:
    out = ["| " + " | ".join(header) + " |", "|" + "|".join("---" for _ in header) + "|"]
    out += ["| " + " | ".join(_fmt(c) if not isinstance(c, str) else c for c in row) + " |" for row in rows]
    return out


def _dets(ds: list[int]) -> str:
    return ",".join(f"D{d}" for d in ds)


def shift_sentence(s: dict) -> str:
    base = (
        f"S{s['season_a']}->S{s['season_b']} ({_dets(s['detectors'])}, {s['estimator']} estimator, "
        f'{s["dt_days"]:.0f} d): {_pm(s["shift_px"], s["sigma_px"])} px = {_pm(s["shift_arcsec"], s["sigma_arcsec"], 2)}" '
        f"at PA {s['pa_deg']:.1f} deg"
    )
    if s["expected_px"] is None:
        return base + "; expected: not available"
    return (
        base
        + f'; expected {s["expected_px"]:.3f} px = {s["expected_arcsec"]:.2f}" at PA {s["expected_pa_deg"]:.1f} deg'
    )


def key_result(f: dict) -> str:
    if f["motion"] is not None:
        h = f["motion"]["headline"]
        return shift_sentence(h) if h else "no season shift measurable on the PNGs"
    if f["variable"] is not None:
        v = f["variable"]
        parts = [f"{h['earlier']} -> {h['later']}: {h['verdict']} ({h['note']})" for h in v["hypotheses"]]
        valued = sum(d["pairs_with_value"] for d in v["per_detector"])
        n_pairs = sum(d["n_pairs"] for d in v["per_detector"])
        blink = sum(d["blink_visible_pairs"] for d in v["per_detector"])
        clipped = [f"D{d['detector']}" for d in v["per_detector"] if d["clipped_core"] == d["n_frames"]]
        parts.append(
            f"{n_pairs} matched pair(s), {valued} with a measurable ratio, {blink} with a change visible in the blink"
        )
        if clipped:
            parts.append(f"core white in every frame of {','.join(clipped)}")
        return "; ".join(parts)
    return "field summary only"


def _summary_section(fields: list[dict]) -> list[str]:
    rows = []
    for f in fields:
        s = f["summary"]
        label = f["name"] + (" (SYNTHETIC)" if f["synthetic"] else "")
        rows.append(
            [
                label,
                f["kind"],
                f["built_at"][:16].replace("T", " "),
                str(s["n_frames"]),
                str(len(s["seasons"])),
                key_result(f),
            ]
        )
    return [
        "## Summary",
        "",
        *_table(["Target", "Check", "Built (UTC)", "Frames", "Seasons", "Key result (display level)"], rows),
        "",
    ]


def _field_block(f: dict) -> list[str]:
    s = f["summary"]
    dets = sorted({c["detector"] for c in s["counts"]})
    by = {(c["season"], c["detector"]): c["n"] for c in s["counts"]}
    rows = [
        [
            f"S{z['season']} {z['date_min']}..{z['date_max']}",
            *[str(by.get((z["season"], d), 0)) for d in dets],
            str(z["n_frames"]),
        ]
        for z in s["seasons"]
    ]
    out = [
        "### Field",
        "",
        f"Built {f['built_at']} by pipeline {f['pipeline_version']}; releases {', '.join(s['releases'])}; grid {s['grid']}; "
        f"{s['n_decoded']} of {s['n_frames']} frame PNGs decoded; field.json sha256 {s['field_json_sha256'][:12]}.",
        "",
        *_table(["Season", *[f"D{d}" for d in dets], "All"], rows),
        "",
    ]
    wl = "; ".join(
        f"D{w['detector']} {_fmt(w['min_um'], 3)}-{_fmt(w['max_um'], 3)} um ({w['n']})" for w in s["wavelengths"]
    )
    out.append(f"- Wavelength at the field centre per detector: {wl}.")
    roll = ", ".join(f"D{d} (white = vmax + {v:g} MJy/sr)" for d, v in s["rolloff"].items()) or "none"
    out.append(f"- Highlight roll-off (target core unflagged in most frames, per the build): {roll}.")
    for note in s["registration_note"]:
        out.append(f'- Build registration note: "{note}"')
    for note in s["skipped_note"]:
        out.append(f'- Build skip note: "{note}"')
    r = s["png_registration"]
    over = ", ".join(r["over_threshold"]) or "none"
    out.append(
        f"- Registration re-measured on the PNGs: {r['checked']} of {r['of']} frames checkable, median "
        f"{_fmt(r['median_px'])} px, max {_fmt(r['max_px'])} px ({r['worst_frame'] or 'n/a'}); over "
        f"{r['threshold_px']} px: {over}" + (" (consensus inconsistent)" if r["inconsistent"] else "") + "."
    )
    c = s["composites"]
    ids = ", ".join(i["id"] for i in c["items"]) or "none"
    missing = ", ".join(c["missing_images"]) or "none missing"
    out.append(f"- False-colour composites: {c['count']} ({ids}); images: {missing}.")
    problems = "; ".join(s["problems"]) or "none"
    out.append(f"- Integrity: problems: {problems}; thumb.png {'present' if s['thumb_ok'] else 'MISSING'}.")
    return [*out, ""]


def _shift_table(shifts: list[dict]) -> list[str]:
    rows = [
        [
            f"S{s['season_a']}->S{s['season_b']}",
            s["estimator"],
            "yes" if s["registration_corrected"] else "no",
            _dets(s["detectors"]),
            _fmt(s["dt_days"], 0),
            _pm(s["shift_px"], s["sigma_px"]),
            _pm(s["shift_arcsec"], s["sigma_arcsec"], 2),
            _fmt(s["pa_deg"], 1),
            _fmt(s["expected_px"]),
            _fmt(s["expected_arcsec"], 2),
            _fmt(s["expected_pa_deg"], 1),
            f"{_fmt(s['residual_px'])} ({_fmt(s['residual_sigma'], 1)})",
            s["uncertainty_from"],
        ]
        for s in shifts
    ]
    return _table(
        [
            "Seasons",
            "Estimator",
            "Reg. corr.",
            "Detectors",
            "dt [d]",
            "Shift [px]",
            'Shift ["]',
            "PA [deg]",
            "Expected [px]",
            'Expected ["]',
            "Exp. PA",
            "Residual [px] (sigma, 2-D)",
            "Uncert. from",
        ],
        rows,
    )


def _astrometry_lines(m: dict, a: dict | None) -> list[str]:
    if a is None:
        return ["- Catalog astrometry: not available in `fields.toml` comments, so expected: not available."]
    return [
        f"- Catalog astrometry (`fields.toml` comment, J2000.0): pm ({a['pm_ra_cosdec_mas_yr']:+}, "
        f'{a["pm_dec_mas_yr"]:+}) mas/yr = {a["total_pm_arcsec_yr"]:.3f}"/yr; read from: "{a["source"]}".',
        f"- Parallax ignored: amplitude {_fmt(m['parallax_amplitude_px'])} px, so between two seasons the expected "
        f"shift can be off by up to {_fmt(m['parallax_max_difference_px'])} px (most on short baselines).",
    ]


def _group_row(g: dict) -> list[str]:
    coadd = g["coadd_status"]
    if coadd == "ok":
        coadd += f" {_fmt(g['coadd_x'], 2)}, {_fmt(g['coadd_y'], 2)} (S/N {_fmt(g['coadd_snr'], 0)})"
    plateau = f"{_fmt(g['plateau_x'], 2)}, {_fmt(g['plateau_y'], 2)} ({g['n_plateaus']})" if g["n_plateaus"] else "-"
    expected = f"{_fmt(g['expected_x'], 2)}, {_fmt(g['expected_y'], 2)}"
    return [f"S{g['season']}", f"D{g['detector']}", str(g["n_frames"]), _fmt(g["mjd"], 2), expected, coadd, plateau]


def _motion_block(f: dict) -> list[str]:
    m = f["motion"]
    out = ["### Proper motion on the PNGs", "", *_astrometry_lines(m, f["astrometry"])]
    if m["target_detector_note"]:
        out.append(f"- Combined shift uses {_dets(m['target_detectors'])} only: {m['target_detector_note']}")
    counts = ", ".join(f"{k} {v}" for k, v in m["core_status_counts"].items())
    out += [
        f"- Per-frame core centroid status ({_dets(m['target_detectors'])}): {counts}; white-plateau centroid in "
        f"{m['plateau_frames']} frame(s); the single white core pixel that sets the detector's roll-off top was "
        f"used as a value in: {', '.join(m['rolloff_top_frames']) or 'none'}.",
        "",
        *_shift_table(m["shifts"]),
    ]
    if m["other_detector_shifts"]:
        out += ["", CONTROL_NOTE, "", *_shift_table(m["other_detector_shifts"])]
    out += ["", "Per season x detector (PNG pixels, x right = west, y down = south):", ""]
    out += _table(GROUP_HEADER, [_group_row(g) for g in m["groups"]])
    return [*out, ""]


def _detector_row(d: dict) -> list[str]:
    counts = [d["n_frames"], d["clipped_core"], "yes" if d["rolloff"] else "no", d["n_pairs"], d["pairs_with_value"]]
    return [f"D{d['detector']}", *[str(c) for c in counts], str(d["blink_visible_pairs"])]


def _level_row(c: dict) -> list[str]:
    return [
        f"D{c['detector']}",
        f"S{c['season']}",
        c["frame_id"],
        _fmt(c["wavelength_um"], 4),
        c["status"],
        _pm(c["aperture"], c["aperture_sigma"], 1),
        _fmt(c["peak_grey"]),
        _fmt(c["core_clipped"]),
        _fmt(c["plateau_area"]),
    ]


def _pair_row(p: dict) -> list[str]:
    return [
        f"D{p['detector']}",
        f"{p['earlier']} -> {p['later']}",
        f"{_fmt(p['wavelength_a_um'], 4)} -> {_fmt(p['wavelength_b_um'], 4)}",
        _fmt(p["dlambda_pct"], 2),
        _pm(p["ratio"], p["ratio_sigma"]),
        p["bound"],
        _fmt(p["delta_mag"]),
        f"{_fmt(p['controls_median'])} +- {_fmt(p['controls_scatter'])} ({_fmt(p['controls_n'])})",
        ("yes: " if p["blink_visible"] else "no: ") + p["blink_note"],
    ]


def _variable_block(f: dict) -> list[str]:
    v = f["variable"]
    out = ["### Brightness on the PNGs", "", *_table(DETECTOR_HEADER, [_detector_row(d) for d in v["per_detector"]])]
    out += ["", "Per frame (r = 3 px sum above the local sky; 'clipped_core' sums are lower bounds):", ""]
    out += _table(LEVEL_HEADER, [_level_row(c) for c in v["levels"]])
    out += ["", PAIRS_NOTE, "", *_table(PAIR_HEADER, [_pair_row(p) for p in v["pairs"]])]
    for h in v["hypotheses"]:
        out += [
            "",
            f"- Hypothesis {h['earlier']} -> {h['later']} ~{h['expected_ratio']:g}x ({h['source']}): "
            f"**{h['verdict']}** - {h['note']}.",
        ]
    return [*out, ""]


def render_markdown(report: dict) -> str:
    fields = report["fields"]
    out = [
        "# Published product check (WS2-8, R05)",
        "",
        f"Generated {report['generated_at']} by `python -m errante.imaging.productcheck` (pipeline "
        f"{report['pipeline_version']}) on `{report['products']}`. Machine-readable: `report.json`.",
        "",
        "> A display-level check of what the published blink shows, read from `field.json` and the 8-bit PNGs. "
        "It is not science photometry or astrometry; the validation records in `docs/validation/` measure the FITS.",
        "",
        *_summary_section(fields),
        "## Method",
        "",
        *[f"- {m}" for m in METHOD],
        "",
        "## Limits",
        "",
        *[f"- {m}" for m in LIMITS],
        "",
    ]
    for f in fields:
        title = f"## {f['name']} (`{f['id']}`)" + (" - SYNTHETIC DATA" if f["synthetic"] else "")
        out += [title, "", f"**Key result (display level):** {key_result(f)}.", ""]
        out += _field_block(f)
        if f["motion"] is not None:
            out += _motion_block(f)
        if f["variable"] is not None:
            out += _variable_block(f)
        out += [f"![{name}]({name})" for name in f["figures"]] + [""]
    return "\n".join(out).rstrip() + "\n"
