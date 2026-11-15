"""Live reproductions of the validated WS3 results (R05 variables, C02 spectra) with the pipeline code.

Run: ERRANTE_NETWORK_TESTS=1 pytest -m network pipeline/tests/test_science_validation_network.py
(IRSA SIA + S3 nasa-irsa-spherex; no key). Downloads ~0.1 GB (RW Aur), ~0.85 GB (R Dra), ~0.9 GB (eps Ind B) and
~0.2 GB (WISE 0855) into ERRANTE_CACHE_DIR on a cold cache; a second run reads the cache.

Measured with this code on 2026-11-15 (~04-06 UTC, laptop in Buenos Aires -> S3 us-east-1, cold cache):

* RW Aur D1, aperture r = 3 px, 81 px stamps (56 exposures, 97.5 MB, 5.3 s with cached layouts; 8.7 s fully cold
  with 61 px): 17 clean exposures, 37 saturated, 2 bad pixels (record: 17 clean, 37 of 56 OVERFLOW). Matched pairs
  2025-09-02 -> 2026-09-08: -1.008 and -1.034 mag (record: -1.005 / -1.031, review -1.007 / -1.032); 5 comparison
  stars, robust scatter 0.018 mag, ensemble in the same frames -0.021 / -0.007 mag.
* R Dra wing (DR1 + QR3, 539 exposures, 111 px, IMAGE + FLAGS = 852 MB): 538 exposures with a saturated core,
  450 in the light curve; period 259.1 d (formal +-6.2, visit bootstrap 95 % 240-276 d), next peaks 104 and 150 d;
  peak-to-peak D1-D6 1.21 / 1.05 / 1.28 / 0.61 / 0.62 / 0.94 mag, floors 0.35 / 0.39 / 0.37 / 0.14 / 0.10 / 0.09 mag
  (record, P = 247 d fit: 1.19 / 0.96 / 1.29 / 0.51 / 0.62 / 0.80 and 0.28 / 0.37 / 0.38 / 0.14 / 0.09 / 0.08); control
  6 stars, scatter 0.016-0.117 mag. With the deep collections (900 of 2493 exposures, 1.40 GB, 89 s cold): 266.2 d,
  bootstrap 260-270, alias 146 d. The record (all 2493): 260 d, 95 % 255-265.
* eps Ind B (458 exposures, 80 s cold, 9.5 s cached): SPHEREx / catalog = J 1.02, H 0.99, Ks 1.13 (2MASS
  22041052-5646577), W1 1.16, W2 1.05 (AllWISE J220415.75-564724.4, ccf 'hh00'); shape vs the DR1 cube fixture
  r = 0.86 (single pixel) and 0.78 (r = 2 aperture); 714 season pairs, median |dm| 0.043: not variable.
* WISE 0855 D5/D6 (93 exposures, 11 s cached): W2 window 0.540 +- 0.028 mJy vs AllWISE W2 0.567 mJy (ratio 0.95);
  per-exposure SNR < 10, so variability is "not testable". All six detectors: W1 window 0.19 mJy = 1.9 x AllWISE W1,
  because the Gaia DR3 star 5756956644387831296 (W2 15.05) sits 0.7-1.85 px away (docs/validation/wise-0855.md).
"""

import json
import os
from pathlib import Path

import pytest

from errante.science.spectra import compare_with_cube, compare_with_photometry, position_spectrum
from errante.science.variability import light_curve, matched_pairs

pytestmark = [
    pytest.mark.network,
    pytest.mark.skipif(os.environ.get("ERRANTE_NETWORK_TESTS") != "1", reason="set ERRANTE_NETWORK_TESTS=1"),
]

CUBE = Path(__file__).parent / "fixtures" / "ws1" / "cube_spectra"
J2000 = 51544.5
RW_AUR = (76.95659, 30.40129)  # config/fields.toml (motion 0.004 px over the baseline)
R_DRA = (248.16723, 66.75502)
EPS_IND_B = (331.04414659, -56.7828442, (3981.977, -2466.832, J2000))  # Sesame CfA, J2000 (fields.toml comments)
WISE_0855 = (133.81890825, -7.247048, (-8123.7, 673.2, J2000))
# VizieR CfA, 2026-11-15: 2MASS II/246 22041052-5646577 (JD 2451490.6, Qflg AAA); AllWISE II/328
# J220415.75-564724.4 (ccf 'hh00': halo flags, eps Ind A is 402" away).
EPS_IND_B_MAGS = {
    "2MASS_J": (11.908, 0.022),
    "2MASS_H": (11.306, 0.024),
    "2MASS_Ks": (11.208, 0.021),
    "WISE_W1": (10.718, 0.023),
    "WISE_W2": (9.492, 0.020),
}
WISE_0855_MAGS = {"WISE_W2": (13.704, 0.033)}  # AllWISE J085510.74-071442.5 (docs/validation/wise-0855.md)


def test_rw_aurigae_brightens_about_one_mag_in_d1_at_matched_wavelength():
    lc = light_curve(*RW_AUR, detectors=[1], method="aperture", mjd_max=61300.0)
    assert lc.excluded["saturated"] == 37
    clean = [p for p in lc.points if p.excluded is None or p.excluded in ("lone_bin", "short_bin")]
    assert len(clean) == 17
    s0_s2 = [
        p
        for p in matched_pairs(lc)
        if p["date_a"].startswith("2025-09") and p["date_b"].startswith("2026-09") and p["wavelength_a_um"] < 0.78
    ]
    assert len(s0_s2) == 2
    for p in s0_s2:
        assert -1.10 < p["delta_mag"] < -0.90  # record: -1.005 and -1.031
        assert p["n_ensemble"] >= 2 and abs(p["ensemble_mag"]) < 0.1  # the comparisons did not change
    assert len(lc.comparisons) >= 3 and lc.control[1]["robust_sigma_mag"] < 0.06  # record: 0.046-0.049


def test_r_draconis_wing_light_curve_gives_the_mira_period():
    lc = light_curve(
        *R_DRA, method="wing", collections=["spherex_dr1", "spherex_qr3"], mjd_max=61315.0, n_bootstrap=100
    )
    assert all("saturated_core" in p.flags for p in lc.points)  # saturated everywhere (record: 2488 of 2488)
    assert len(lc.used()) > 300
    pe = lc.period
    assert pe is not None and 250.0 <= pe.period_days <= 270.0
    lo, hi = pe.period_days - 2 * pe.period_err_formal_days, pe.period_days + 2 * pe.period_err_formal_days
    assert lo <= 265.0 and hi >= 255.0  # consistent with the record's 255-265 d
    assert pe.peaks[0][1] > 1.2 * pe.peaks[1][1]  # the period beats its aliases
    for det, amp in pe.amplitude_mag.items():
        assert amp > 4 * lc.control[det]["robust_sigma_mag"]  # far above the comparison stars
    assert pe.amplitude_mag[1] > 0.9 and pe.amplitude_mag[3] > 0.9 and 0.4 < pe.amplitude_mag[4] < 0.8
    json.dumps(lc.to_dict(), allow_nan=False)


def test_eps_ind_b_spectrum_matches_2mass_allwise_and_the_cube_shape():
    ra, dec, pm = EPS_IND_B
    spec = position_spectrum(ra, dec, pm=pm)
    ratio = {c["band"]: c["ratio"] for c in compare_with_photometry(spec, EPS_IND_B_MAGS)}
    assert 0.85 < ratio["2MASS_J"] < 1.2 and 0.85 < ratio["2MASS_H"] < 1.2
    assert 0.9 < ratio["2MASS_Ks"] < 1.3 and 0.9 < ratio["WISE_W1"] < 1.4 and 0.85 < ratio["WISE_W2"] < 1.25
    cube = json.loads((CUBE / "eps-indi-b_ap0.json").read_text())
    assert compare_with_cube(spec, cube)["pearson_r"] > 0.75
    assert spec.variable is False


def test_wise_0855_w2_flux_matches_allwise():
    ra, dec, pm = WISE_0855
    spec = position_spectrum(ra, dec, pm=pm, detectors=[5, 6])
    (w2,) = compare_with_photometry(spec, WISE_0855_MAGS)
    assert w2["spherex"]["n"] >= 30 and 0.7 < w2["ratio"] < 1.3
    assert spec.variable is not True
