"""WS2-10: the coadd SNR check pins the expected gain on synthetic frames with known noise."""

import json
import math

import numpy as np
import pytest

from errante.imaging import snrcheck
from errante.imaging.compare import GridFrame

N_SIDE = 96
STAR_FLUX = 400.0  # MJy/sr x px; peak ~100 x the unit noise
PSF_SIGMA = 0.8


def _star_model(n: int = N_SIDE) -> tuple[np.ndarray, list[tuple[int, int]]]:
    yy, xx = np.indices((n, n))
    c = (n - 1) / 2
    stars = [(x, y) for x in range(14, n - 13, 17) for y in range(14, n - 13, 17) if math.hypot(x - c, y - c) > 20]
    model = np.zeros((n, n))
    for x, y in stars:
        model += (
            STAR_FLUX * np.exp(-((xx - x) ** 2 + (yy - y) ** 2) / (2 * PSF_SIGMA**2)) / (2 * math.pi * PSF_SIGMA**2)
        )
    return model, stars


def _frames(sigmas, *, static=0.0, smooth=False, seed=3) -> list[GridFrame]:
    """Frames of one detector: same stars, white noise of ``sigmas`` (2x2-averaged = correlated if ``smooth``)."""
    rng = np.random.default_rng(seed)
    model, _ = _star_model()
    static_sky = static * rng.standard_normal((N_SIDE, N_SIDE))
    out = []
    for i, s in enumerate(sigmas):
        raw = s * rng.standard_normal((N_SIDE + 1, N_SIDE + 1))
        if smooth:  # half-pixel bilinear shift: per-pixel variance / 4, neighbours correlated
            noise, var = (raw[:-1, :-1] + raw[1:, :-1] + raw[:-1, 1:] + raw[1:, 1:]) / 4, s**2 / 4
        else:
            noise, var = raw[:-1, :-1], s**2
        data = 5.0 + model + static_sky + noise
        out.append(
            GridFrame(
                f"f{i}",
                1,
                60000.0 + i,
                data.astype(np.float32),
                np.zeros((N_SIDE, N_SIDE), dtype=bool),
                np.full((N_SIDE, N_SIDE), var, dtype=np.float32),
            )
        )
    return out


def _median(group: dict, method: str, key: str) -> float:
    return float(np.median([s["snr"][method][key] for s in group["stars"]]))


def test_expected_snr_is_quadrature_sum_for_inverse_variance_weights():
    fluxes, sigmas = [10.0, 10.0, 10.0], [1.0, 2.0, 3.0]
    weights = [1 / s**2 for s in sigmas]
    quadrature = math.sqrt(sum((f / s) ** 2 for f, s in zip(fluxes, sigmas, strict=True)))
    assert snrcheck.expected_snr(fluxes, sigmas, weights) == pytest.approx(quadrature)


def test_expected_snr_uses_each_frame_flux_and_the_weights_used():
    # fluxes change between frames (another wavelength per exposure): sum(w F) / sqrt(sum(w^2 sigma^2))
    fluxes, sigmas, weights = [10.0, 12.0, 8.0], [1.0, 2.0, 3.0], [1.0, 0.5, 0.5]
    expected = (10 + 6 + 4) / math.sqrt(1 + 0.25 * 4 + 0.25 * 9)
    assert snrcheck.expected_snr(fluxes, sigmas, weights) == pytest.approx(expected)


def test_expected_snr_is_sqrt_n_for_equal_noise_and_flux():
    assert snrcheck.expected_snr([5.0] * 4, [2.0] * 4, [0.25] * 4) == pytest.approx(math.sqrt(4) * 2.5)


def test_equal_noise_gain_is_sqrt_n():
    group = snrcheck.check_group(_frames([1.0] * 4), season=0)
    assert group is not None and group["n_frames"] == 4
    _, stars = _star_model()
    assert len(group["stars"]) >= 0.8 * len(stars)
    for method in snrcheck.METHODS:
        assert _median(group, method, "gain_expected") == pytest.approx(2.0, abs=0.1)
        assert _median(group, method, "ratio") == pytest.approx(1.0, abs=0.15)
    assert _median(group, "variance", "ratio") == pytest.approx(1.0, abs=0.03)
    assert group["median_flux_consistency"] == pytest.approx(1.0, abs=0.01)
    assert group["blank"]["noise_ratio"] == pytest.approx(1.0, abs=0.15)
    assert not any("below expectation" in f for f in group["flags"])


def test_unequal_noise_gain_follows_inverse_variance_weights():
    group = snrcheck.check_group(_frames([1.0, 2.0]), season=0)
    assert group["weights"] == pytest.approx([1.0, 0.25], rel=1e-5)
    # sqrt(SNR^2 + (SNR/2)^2) / median(SNR, SNR/2) = 1.118 / 0.75
    assert _median(group, "variance", "gain_expected") == pytest.approx(math.sqrt(1.25) / 0.75, abs=0.05)
    assert _median(group, "variance", "gain_ivw_ideal") == pytest.approx(math.sqrt(1.25) / 0.75, abs=0.05)
    for method in snrcheck.METHODS:
        assert _median(group, method, "ratio") == pytest.approx(1.0, abs=0.15)
    assert group["median_flux_consistency"] == pytest.approx(1.0, abs=0.01)


def test_static_sky_explains_a_low_gain():
    group = snrcheck.check_group(_frames([1.0] * 4, static=1.0), season=0)
    blank = group["blank"]
    assert blank["noise_ratio"] < snrcheck.LOW_RATIO  # static structure does not average down
    assert blank["noise_ratio_with_static"] == pytest.approx(1.0, abs=0.15)
    assert blank["random_fraction_single"] == pytest.approx(math.sqrt(0.5), abs=0.1)
    assert any("static sky structure" in f for f in group["flags"])


def test_correlated_noise_is_seen_by_blank_apertures_only():
    white = snrcheck.check_group(_frames([1.0] * 3), season=0)["blank"]
    smooth = snrcheck.check_group(_frames([1.0] * 3, smooth=True), season=0)
    assert np.median(white["correlation_single"]) == pytest.approx(1.0, abs=0.15)
    assert np.median(smooth["blank"]["correlation_single"]) > 1.5
    # the propagated VARIANCE then overstates the SNR, the blank apertures do not
    stars = smooth["stars"]
    snr_var = np.median([np.median(s["snr"]["variance"]["single"]) for s in stars])
    snr_blank = np.median([np.median(s["snr"]["blank"]["single"]) for s in stars])
    assert snr_var > 1.5 * snr_blank


def test_flagged_core_excludes_the_star():
    frames = _frames([1.0] * 2)
    _, stars = _star_model()
    x, y = stars[0]
    bad = frames[1].bad.copy()
    bad[y, x] = True
    frames[1] = GridFrame("f1", 1, frames[1].mjd, frames[1].data, bad, frames[1].variance)
    group = snrcheck.check_group(frames, season=0)
    assert (x, y) not in {(s["x"], s["y"]) for s in group["stars"]}
    assert len(group["stars"]) > 5


def test_single_frame_group_is_skipped():
    assert snrcheck.check_group(_frames([1.0]), season=0) is None


def test_report_is_strict_json_and_markdown(tmp_path):
    frames = _frames([1.0, 1.0, 2.0])
    fields = [{"field_id": "synthetic", "groups": snrcheck.check_frames(frames, {f.frame_id: 0 for f in frames})}]
    report = snrcheck.write_report(fields, tmp_path)
    loaded = json.loads((tmp_path / snrcheck.REPORT_JSON).read_text(encoding="utf-8"))
    assert loaded["summary"]["n_groups"] == 1
    assert report["summary"]["methods"]["blank"]["median_ratio"] == pytest.approx(1.0, abs=0.15)
    md = (tmp_path / snrcheck.REPORT_MD).read_text(encoding="utf-8")
    assert "## Limits" in md and "| synthetic | D1_S0 | 3 |" in md
