"""WS2-7 follow-up: season differences stay readable for faint targets (WISE 0855) and say what they cannot show."""

import numpy as np
import pytest
from test_imaging_compare import N, _field, _loader, frame, scene

from errante.imaging.compare import (
    DIFF_SOFTENING,
    FAINT_TARGET_RATIO,
    _robust_sigma,
    coadd,
    compare_field,
    core_coverage,
    difference,
    difference_limit,
    display_scale,
    diverging_rgba,
)

C = (N - 1) / 2
VARIABLE_FIELD_STAR = (40, 6, 40.0)  # brightens by 40 between seasons: sigma-clipped out of the flux scale


def _pair(target_amp: float, extra_late=(VARIABLE_FIELD_STAR,), seed=20):
    """Target at the field centre moving 1 px north, plus (by default) a strongly variable field star."""
    target_early = [(C, C + 1, target_amp)] if target_amp else []
    target_late = [(C, C, target_amp)] if target_amp else []
    early = coadd([frame("e", 5, 60900.0, scene(seed=seed, extra=target_early))])
    late = coadd([frame("l", 5, 61270.0, scene(seed=seed + 1, extra=[*target_late, *extra_late]))])
    return difference(late, early)


def _region_max(d) -> float:
    yy, xx = np.indices(d.data.shape)
    inside = np.isfinite(d.data) & (np.hypot(xx - C, yy - C) <= d.target_exclude_px)
    return float(np.abs(d.data[inside]).max())


def _field_limit(d, nsigma=10.0) -> float:
    ok = np.isfinite(d.data)
    return max(float(np.percentile(np.abs(d.data[ok]), 99.9)), nsigma * _robust_sigma(d.data[ok]))


def test_a_faint_target_takes_the_limit_from_its_region_and_says_so():
    d = _pair(target_amp=3.0)
    sigma = _robust_sigma(d.data[np.isfinite(d.data)])
    scale = display_scale(d)
    assert scale.rule == "target_region"
    assert scale.field_limit == pytest.approx(_field_limit(d))
    assert scale.limit == pytest.approx(_region_max(d)) and scale.limit > 10 * sigma
    assert scale.field_limit >= FAINT_TARGET_RATIO * scale.limit
    assert difference_limit(d) == scale.limit
    (note,) = scale.notes
    assert "display limit set from the target region" in note and "field-star residuals clip" in note
    assert "the largest residual within 8 px of the field centre" in note
    # the dipole reads much brighter than with the field limit, while the variable field star saturates
    y_now = int(C)
    shown = diverging_rgba(d.data, scale.limit, scale.softening)[y_now, int(C), 0]
    before = diverging_rgba(d.data, scale.field_limit, DIFF_SOFTENING)[y_now, int(C), 0]
    assert shown > before + 40
    assert diverging_rgba(d.data, scale.limit, scale.softening)[6, 40, 0] == 255


def test_a_bright_target_keeps_the_field_limit():
    d = _pair(target_amp=80.0)
    scale = display_scale(d)
    assert scale.rule == "field" and scale.limit == pytest.approx(_field_limit(d))
    assert scale.target_limit is not None and scale.field_limit < FAINT_TARGET_RATIO * scale.target_limit
    assert not any("target region" in n for n in scale.notes)


def test_without_a_target_signal_the_limit_never_goes_below_nsigma_noise():
    d = _pair(target_amp=0.0)
    sigma = _robust_sigma(d.data[np.isfinite(d.data)])
    scale = display_scale(d)
    assert scale.rule == "target_region" and scale.limit == pytest.approx(10 * sigma)
    assert display_scale(d, nsigma=20).limit == pytest.approx(20 * sigma)
    (note,) = scale.notes
    assert "10 x the noise: no residual within 8 px of the field centre is brighter" in note


def test_a_field_without_bright_residuals_keeps_the_field_limit():
    d = _pair(target_amp=3.0, extra_late=())  # nothing in the field brighter than the target
    assert display_scale(d).rule == "field"


def test_the_noise_stays_dark_whatever_the_limit():
    faint = display_scale(_pair(target_amp=0.0))  # limit = 10 x noise
    sigma = faint.limit / 10
    assert faint.softening == pytest.approx(3 * sigma / faint.limit)  # 0.3
    noise_px = np.array([[sigma]])
    assert diverging_rgba(noise_px, faint.limit, faint.softening)[0, 0, 0] < 60
    assert diverging_rgba(noise_px, faint.limit, DIFF_SOFTENING)[0, 0, 0] > 90  # the old fixed softening
    bright = display_scale(_pair(target_amp=80.0, extra_late=()))  # limit >> 60 x noise
    assert bright.softening == DIFF_SOFTENING


def test_an_unscaled_difference_says_so_first():
    from test_imaging_compare import STARS

    early = coadd([frame("e", 4, 60900.0, scene(stars=STARS[:2], seed=5))])
    late = coadd([frame("l", 4, 61270.0, scene(stars=STARS[:2], scale=0.5, seed=6))])
    d = difference(late, early)
    assert not d.scale.fitted
    assert d.notes[0].startswith("Unscaled difference (s = 1)")
    assert "not fitted" in d.notes[0] and "8-px circle" in d.notes[0]
    fitted = difference(coadd([frame("l", 4, 61270.0, scene(seed=6))]), coadd([frame("e", 4, 60900.0, scene(seed=5))]))
    assert fitted.scale.fitted and not any("Unscaled" in n for n in fitted.notes)


def test_coadd_exports_one_weight_per_contributing_frame_in_frame_order():
    empty = frame("empty", 2, 1.5, np.full((N, N), np.nan, np.float32))
    c = coadd([frame("a", 2, 1.0, scene(seed=1), var=1.0), empty, frame("b", 2, 2.0, scene(seed=2), var=4.0)])
    assert c.frame_ids == ["a", "b"] and c.skipped == ["empty"]
    assert c.weights == pytest.approx([1.0, 0.25])  # 1 / median VARIANCE of the frame's usable pixels


def test_coadd_weight_without_variance_is_the_inverse_robust_noise():
    data = scene(seed=3)
    g = frame("a", 2, 1.0, data)
    no_var = type(g)(g.frame_id, g.detector, g.mjd, g.data, g.bad, None)
    c = coadd([no_var])
    assert c.weights == pytest.approx([1 / _robust_sigma(data) ** 2])


def _saturated(img: np.ndarray, rows=slice(22, 26), cols=slice(22, 26)):
    data, bad = img.copy(), np.zeros(img.shape, bool)
    data[rows, cols] = np.nan
    bad[rows, cols] = True
    return data, bad


def test_a_saturated_target_core_is_not_a_brightness_measurement():
    data, bad = _saturated(scene(seed=7, extra=[(C, C, 500.0)]))
    early = coadd([frame("e", 2, 60900.0, data, bad=bad)])
    late = coadd([frame("l", 2, 61270.0, scene(seed=8, extra=[(C, C, 600.0)]))])
    assert core_coverage(early).no_data == 12 and core_coverage(early).pixels == 12  # 4x4 block minus corners
    assert core_coverage(late).no_data == 0 and not core_coverage(late).flagged
    d = difference(late, early)
    assert d.target_core_flagged
    (note,) = [n for n in d.notes if "core" in n]
    assert "saturated or flagged" in note and "D2_S0" in note and "not a brightness measurement" in note


def test_a_target_core_flagged_in_some_frames_says_fewer_frames():
    bad = np.zeros((N, N), bool)
    bad[23, 23] = True  # one core pixel flagged in one of the two early frames
    early = coadd([frame("e1", 3, 60900.0, scene(seed=9), bad=bad), frame("e2", 3, 60901.0, scene(seed=10))])
    late = coadd([frame("l", 3, 61270.0, scene(seed=11))])
    cov = core_coverage(early)
    assert (cov.no_data, cov.fewer_frames) == (0, 1) and cov.flagged
    d = difference(late, early)
    (note,) = [n for n in d.notes if "core" in n]
    assert "fewer frames" in note and "D3_S0" in note and "not a clean brightness measurement" in note


def test_a_clean_target_core_adds_no_note():
    d = _pair(target_amp=3.0)
    assert not d.target_core_flagged and not any("core" in n for n in d.notes)


# Keys that backend/errante_api/science_ops.py reads from compare_field's metadata: they must keep their meaning.
SCIENCE_OPS_COADD_KEYS = {"id", "detector", "season", "image", "valid_fraction", "frame_ids", "skipped_frame_ids"}
SCIENCE_OPS_DIFF_KEYS = {
    "id", "detector", "earlier", "later", "image", "flux_scale", "flux_scale_fitted", "flux_scale_stars",
    "noise_mjy_sr", "limit_mjy_sr", "target_exclude_px", "notes",
}  # fmt: skip


def test_compare_field_keeps_the_science_api_keys_and_adds_the_new_ones(tmp_path):
    fld = _field([("A", 2, 60908.0), ("B", 2, 60910.0), ("C", 2, 61116.0)])
    meta = compare_field(fld, tmp_path, _loader)
    assert {"method", "limitations", "skipped", "coadds", "differences"} <= meta.keys()
    assert "weights_definition" in meta and "display" in meta
    for c in meta["coadds"]:
        assert SCIENCE_OPS_COADD_KEYS <= c.keys()
        assert len(c["weights"]) == len(c["frame_ids"]) == c["n_frames"]
        assert c["weights"] == pytest.approx([1 / 0.0025] * c["n_frames"])  # _loader frames: VARIANCE 0.0025
        assert c["core_no_data_px"] == 0 and c["core_fewer_frames_px"] == 0
    (d,) = meta["differences"]
    assert SCIENCE_OPS_DIFF_KEYS <= d.keys()
    assert d["limit_rule"] in {"field", "target_region"} and d["target_core_flagged"] is False
    assert d["limit_mjy_sr"] == (d["field_limit_mjy_sr"] if d["limit_rule"] == "field" else d["target_limit_mjy_sr"])
    assert DIFF_SOFTENING <= d["display_softening"] <= 1.0


def test_compare_field_draws_a_faint_target_with_the_target_region_limit(tmp_path):
    fld = _field([("A", 5, 60908.0), ("B", 5, 61116.0)])

    def load(refs):
        return [
            frame("AD5", 5, refs[0].mjd, scene(seed=20, extra=[(C, C + 1, 3.0)])),
            frame("BD5", 5, refs[1].mjd, scene(seed=21, extra=[(C, C, 3.0), VARIABLE_FIELD_STAR])),
        ]

    meta = compare_field(fld, tmp_path, load)
    (d,) = meta["differences"]
    assert d["limit_rule"] == "target_region" and d["limit_mjy_sr"] == d["target_limit_mjy_sr"]
    assert d["field_limit_mjy_sr"] >= FAINT_TARGET_RATIO * d["limit_mjy_sr"]
    assert any("display limit set from the target region" in n for n in d["notes"])
