"""WS2-8: caveats of the product check (imaging/productcheck_caveats.py), on small report sections.

The numbers below are those of the real report (data/products, 2026-11-15) so the sentences can be read against it.
"""

import json

import pytest
from test_imaging_productcheck import write_mover

from errante.imaging import productcheck, productcheck_caveats
from errante.imaging.productcheck_caveats import (
    blink_visibility,
    direction,
    field_caveats,
    fits_shift,
    lost_seasons,
    misregistered_neighbours,
    orientation_offset,
    pair_consistency,
    weak_uncertainty,
)


def _shift(a, b, *, est="core", shift=1.0, sigma=0.05, pa=120.0, exp=1.0, epa=120.0, res=0.0, rs=0.0, **kw):
    s = {
        "estimator": est,
        "registration_corrected": False,
        "season_a": a,
        "season_b": b,
        "detectors": [1, 2],
        "shift_px": shift,
        "sigma_px": sigma,
        "pa_deg": pa,
        "uncertainty_from": "detectors",
        "expected_px": exp,
        "expected_pa_deg": epa,
        "residual_px": res,
        "residual_sigma": rs,
    }
    return {**s, **kw}


def _group(season, det, *, status="ok", x=10.0, y=10.0, snr=50.0, n_core=2, plateau=None):
    return {
        "season": season,
        "detector": det,
        "expected_x": 10.0,
        "expected_y": 10.0,
        "coadd_status": status,
        "coadd_x": x if status == "ok" else None,
        "coadd_y": y if status == "ok" else None,
        "coadd_snr": snr,
        "n_core_frames": n_core,
        "n_plateaus": 0 if plateau is None else 2,
        "plateau_x": None if plateau is None else plateau[0],
        "plateau_y": None if plateau is None else plateau[1],
    }


def _motion(shifts, groups, *, frames=(), dets=(1, 2), headline=None):
    return {
        "target_detectors": list(dets),
        "pixel_scale_arcsec": 6.15,
        "frames": list(frames),
        "groups": groups,
        "shifts": shifts,
        "headline": headline if headline is not None else shifts[0],
    }


WISE_HEADLINE = _shift(
    1, 2, shift=0.834, sigma=0.159, pa=279.2, exp=0.516, epa=274.7, res=0.321, rs=2.0, uncertainty_from="frames"
)
WISE_HEADLINE["detectors"] = [5]
WISE_GROUPS = [
    _group(0, 5, status="faint", snr=3.1, n_core=0),
    _group(0, 6, status="faint", snr=2.8, n_core=0),
    _group(1, 5, snr=6.6),
    _group(1, 6, status="faint", snr=4.1, n_core=0),
    _group(2, 5, snr=9.5),
    _group(2, 6, status="faint", snr=3.1, n_core=0),
]


def _wise_frames(n_ok: int) -> list[dict]:
    keys = [(s, d) for s in (0, 1, 2) for d in (5, 6) for _ in range(2)]
    order = sorted(range(len(keys)), key=lambda i: (keys[i][1] != 5 or keys[i][0] == 0, i))
    ok = set(order[:n_ok])
    return [{"season": s, "detector": d, "core_status": "ok" if i in ok else "faint"} for i, (s, d) in enumerate(keys)]


def test_a_one_detector_shift_names_how_few_frames_its_uncertainty_rests_on():
    m = _motion([WISE_HEADLINE], WISE_GROUPS, dets=(5, 6))
    (caveat,) = weak_uncertainty(m)
    assert "scatter (ddof=1) of only 2 per-frame core centroids in S1 and 2 in S2" in caveat
    assert "0.834 +- 0.159 px against 0.516 px expected (2.0 sigma residual) is a weak constraint" in caveat
    assert weak_uncertainty(_motion([_shift(0, 1)], WISE_GROUPS)) == []  # scatter between detectors


def test_a_season_without_any_position_is_named_with_its_coadd_snr():
    (caveat,) = lost_seasons(_motion([WISE_HEADLINE], WISE_GROUPS, dets=(5, 6)))
    assert caveat.startswith("S0 gives no core position on D5,D6 (coadd D5 faint, S/N 3.1; D6 faint, S/N 2.8;")
    assert "no season shift uses S0" in caveat


def test_the_blink_cannot_show_a_target_seen_in_too_few_frames():
    (caveat,) = blink_visibility(_motion([WISE_HEADLINE], WISE_GROUPS, frames=_wise_frames(4), dets=(5, 6)))
    assert "only 4 of 12 frames of D5,D6 (S1 D5, S2 D5)" in caveat
    assert "the published blink cannot show its motion; the expected S1->S2 step is 0.516 px" in caveat
    assert blink_visibility(_motion([WISE_HEADLINE], WISE_GROUPS, frames=_wise_frames(8), dets=(5, 6))) == []


def test_an_off_shift_says_whether_the_length_or_the_direction_disagrees():
    eps = _shift(0, 3, shift=1.067, sigma=0.035, pa=130.6, exp=1.058, epa=121.8, res=0.163, rs=4.7)
    assert direction(_motion([eps], [])) == [
        "S0->S3: the length agrees (1.067 +- 0.035 vs 1.058 px expected, 0.3 sigma) but the 2-D residual is "
        "0.163 px (4.7 sigma) and the PA is 8.8 deg off (130.6 vs 121.8 deg)."
    ]
    wrapped = _shift(0, 1, shift=2.0, sigma=0.1, pa=359.0, exp=1.0, epa=1.0, res=1.0, rs=10.0)
    (caveat,) = direction(_motion([wrapped], []))
    assert "the length (2.000 +- 0.100 vs 1.000 px) differs" in caveat and "PA is 2.0 deg off" in caveat
    assert direction(_motion([WISE_HEADLINE], [])) == []  # 2.0 sigma: no caveat


def test_season_pairs_are_split_by_the_orientation_groups_of_the_record():
    shifts = [
        _shift(0, 1, res=0.183, rs=6.7),
        _shift(0, 2, res=0.037, rs=2.5),
        _shift(1, 3, res=0.026, rs=1.0),
        _shift(0, 1, res=0.145, rs=6.8, registration_corrected=True),  # corrected: left out
    ]
    (caveat,) = pair_consistency("eps-indi-b", _motion(shifts, []))
    assert "same orientation (S0/S2 vs S1/S3, per the record): S0->S2 0.037 px (2.5 sigma), S1->S3 0.026 px" in caveat
    assert "across orientations: S0->S1 0.183 px (6.7 sigma)." in caveat and "6.8" not in caveat
    (plain,) = pair_consistency("other", _motion(shifts, []))
    assert "off by >= 3 sigma: S0->S1 0.183 px (6.7 sigma); within: S0->S2" in plain
    assert pair_consistency("other", _motion(shifts[1:3], [])) == []  # nothing off


def test_the_fits_shift_of_the_record_is_compared_with_the_png_one():
    eps = _shift(0, 3, shift=1.067, sigma=0.035, pa=130.6, exp=1.058, epa=121.8, res=0.163, rs=4.7)
    sentence, note = fits_shift("eps-indi-b", _motion([eps], []))
    assert "S0->S3 1.026-1.031 px at PA 126.5-126.7 deg (original analysis and review)" in sentence
    assert "i.e. +0.036 to +0.041 px and +3.9 to +4.1 deg from the FITS." in sentence
    assert "about 4 deg of the 8.8 deg PA difference" in note
    assert fits_shift("wise-0855", _motion([eps], [])) == []


def test_the_rotated_season_offset_is_given_without_claiming_a_direction():
    groups = [
        _group(s, d, status="clipped", plateau=(10.0 + dx, 10.0))
        for s, dx in ((0, 0.1), (1, -0.3), (2, 0.1))
        for d in (1, 2)
    ]
    head = _shift(0, 2, est="plateau")
    (caveat,) = orientation_offset("barnards-star", _motion([head], groups))
    assert '+2.46" E, +0.00" N (+0.400 px E) from the mean of S0 and S2' in caveat  # -x = east
    assert 'ranges from -0.66" to +1.35"' in caveat and "no agreement in direction with it is claimed" in caveat
    assert orientation_offset("eps-indi-b", _motion([head], groups)) == []


RW_SECTION = {
    "id": "rw-aurigae",
    "motion": None,
    "summary": {
        "skipped_note": [
            "Skipped 1 frame(s): 2026W38_1A_0162_3D6: misregistered frame: field stars 1.34 px off their consensus"
        ],
        "png_registration": {
            "threshold_px": 0.5,
            "worst_frame": "2026W38_1A_0162_2D6",
            "per_frame_px": {
                "2026W38_1A_0162_3D3": 0.041,
                "2026W38_1A_0162_1D6": 0.079,
                "2026W38_1A_0162_2D6": 0.138,
                "2026W38_1A_0162_2D3": 0.05,  # other exposure, other detector: not listed
                "2025W38_1A_0538_2D6": 0.03,
            },
        },
    },
    "variable": {
        "levels": [
            {"frame_id": "2025W38_1A_0538_2D6", "detector": 6, "plateau_area": 30},
            {"frame_id": "2026W38_1A_0162_1D6", "detector": 6, "plateau_area": 26},
            {"frame_id": "2026W38_1A_0162_2D6", "detector": 6, "plateau_area": 20},
            {"frame_id": "2026W38_1A_0162_3D3", "detector": 3, "plateau_area": 9},
        ],
        "pairs": [
            {"detector": 6, "earlier": "2025W38_1A_0538_2D6", "later": "2026W38_1A_0162_2D6", "blink_visible": True},
            {"detector": 6, "earlier": "2025W38_1A_0538_2D6", "later": "2026W38_1A_0162_1D6", "blink_visible": False},
        ],
    },
}


def test_frames_of_a_rejected_frames_sequence_are_flagged_with_their_own_registration():
    first, anomaly = misregistered_neighbours(RW_SECTION)
    assert first.startswith("2026W38_1A_0162_3D6 was rejected by the build as misregistered (field stars 1.34 px")
    assert "the same exposure 2026W38_1A_0162_3: 2026W38_1A_0162_3D3 (PNG registration 0.041 px)" in first
    assert "on D6: 2026W38_1A_0162_1D6 (PNG registration 0.079 px), 2026W38_1A_0162_2D6 (PNG registration " in first
    assert "0.138 px, the field's largest)" in first and "_2D3" not in first
    assert "within 0.5 px, but treat them with caution" in first
    assert anomaly == (
        "2026W38_1A_0162_2D6: white disc 20 px against 26-30 px in the other 2 D6 frames; it is in the only D6 pair "
        "whose blink shows a change, so that change rests on this one frame."
    )
    clean = {**RW_SECTION, "summary": {**RW_SECTION["summary"], "skipped_note": []}}
    assert misregistered_neighbours(clean) == []


def test_field_caveats_end_with_the_record_notes():
    caveats = field_caveats(RW_SECTION)
    assert len(caveats) == 3 and caveats[-1].startswith("docs/validation/rw-aurigae.md (FITS)")
    assert (
        field_caveats({**RW_SECTION, "id": "r-draconis", "summary": {**RW_SECTION["summary"], "skipped_note": []}})
        == []
    )


def test_report_json_and_md_carry_the_same_caveats(tmp_path, monkeypatch):
    _, astro = write_mover(tmp_path / "products")
    note = 'Synthetic record note: 1.234 px at PA 56.7 deg (6.15"/px).'
    monkeypatch.setitem(productcheck_caveats.RECORD_NOTES, "syn-mover", (note,))
    productcheck.run_check(tmp_path / "products", tmp_path / "out", {"syn-mover": astro})
    field = json.loads((tmp_path / "out" / "report.json").read_text(encoding="utf-8"))["fields"][0]
    md = (tmp_path / "out" / "report.md").read_text(encoding="utf-8")
    assert field["caveats"] and field["caveats"][-1] == note
    assert all(f"- {c}" in md for c in field["caveats"])
    assert "| Caveats |" in md and "**Caveats (read the key result with these):**" in md
    assert set(field["summary"]["png_registration"]["per_frame_px"]) == {
        f["frame_id"] for f in field["motion"]["frames"]
    }


@pytest.mark.parametrize("pa, ref, expected", [(130.6, 121.8, 8.8), (1.0, 359.0, 2.0), (359.0, 1.0, -2.0)])
def test_pa_differences_wrap_around_north(pa, ref, expected):
    assert productcheck_caveats._dpa(pa, ref) == pytest.approx(expected)
