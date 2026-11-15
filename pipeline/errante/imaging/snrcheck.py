"""Does a season coadd gain the SNR its weights promise? (WS2-10, challenge C02/C03).

``compare.coadd`` averages the frames of one (season, detector) with ONE weight per frame, w_i = 1 / median
VARIANCE. For a source of flux F_i and aperture noise sigma_i in frame i, that weighted mean has

    F_c = sum(w_i F_i) / sum(w_i),   sigma_c = sqrt(sum(w_i^2 sigma_i^2)) / sum(w_i)

so the EXPECTED coadd SNR for the weights used is sum(w_i F_i) / sqrt(sum(w_i^2 sigma_i^2)). With
inverse-variance weights (w_i = 1 / sigma_i^2) it is sqrt(sum SNR_i^2); with equal noise and flux, sqrt(N) x SNR.

Per (field, detector, season) with >= 2 usable frames, this module measures field stars (not the target)
in every single frame and in the coadd: 5x5 px aperture sum above the median of a 4-7 px sky ring, with
three noise estimates:

- ``variance``: propagated VARIANCE (aperture sum + sky-median term). On reprojected frames this is
  optimistic: bilinear reprojection makes the per-pixel variance up to 4x smaller and neighbouring
  pixels correlated, and summing per-pixel variances ignores that correlation.
- ``annulus``: robust per-pixel scatter of the star's own sky ring, as if pixels were independent.
  It sees background structure but not pixel correlation.
- ``blank``: robust scatter of the same aperture measured on star-free positions of the same image
  (the same positions in every frame and in the coadd). It includes correlated noise and the sky
  subtraction, so it is the honest one; it is background-only (no source Poisson noise).

Ratio = measured coadd SNR / expected coadd SNR (1 = the coadd gains what its weights promise). Flux
consistency = coadd flux / weighted mean of the single-frame fluxes (should be ~1: the coadd is linear).

Stars: isolated local maxima of the coadd >= ``MIN_PEAK_SNR`` x its robust pixel noise above the local
sky, no other peak >= ``NEIGHBOUR_SNR`` within ``ISOLATION_PX``, at least ``EDGE_MARGIN_PX`` from the grid
edge, outside ``compare.target_exclusion`` (the target and its halo), and with every aperture pixel
usable (finite, not flagged, positive variance) in every frame: saturated or flagged cores are out.
"Stable" is NOT verified against a catalogue: a star's flux may change between frames because each
exposure samples another wavelength, which the expected SNR accounts for (it uses each frame's flux).

Run offline on built fields (cached cutouts, ``ERRANTE_CACHE_DIR``)::

    python -m errante.imaging.snrcheck [--field id ...] --out <dir>
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import warnings
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

from ..detect.difference import APERTURE_HALF, SKY_ANNULUS, find_stars
from .compare import Coadd, GridFrame, coadd, target_exclusion

MAD_TO_SIGMA = 1.4826
MEDIAN_VARIANCE_FACTOR = math.pi / 2  # variance of the median of n Gaussian values ~ (pi/2) sigma^2 / n
MIN_PEAK_SNR = 10.0  # star peak above its local sky, in robust pixel sigmas of the coadd
NEIGHBOUR_SNR = 5.0  # any other peak this bright within ISOLATION_PX makes a star non-isolated
ISOLATION_PX = SKY_ANNULUS[1]  # no neighbour inside the sky ring
EDGE_MARGIN_PX = math.ceil(SKY_ANNULUS[1]) + 1  # the whole sky ring stays on the grid
MIN_RING_FRACTION = 0.5  # of the sky-ring pixels must be finite
SOURCE_MASK_SIGMAS = 3.0  # blank apertures avoid coadd pixels this far above the sky (dilated)
SOURCE_MASK_GROW_PX = APERTURE_HALF + 1
MIN_BLANK_APERTURES = 10
MIN_FRAMES = 2
LOW_RATIO = 0.8  # a group whose median ratio is below this gains well below expectation
FLUX_TOLERANCE = 0.1  # |flux consistency - 1| above this is flagged
STATIC_TOLERANCE = 0.15  # a static-sky model "explains" a low gain when it predicts the coadd noise this well
METHODS = ("variance", "annulus", "blank")
REPORT_JSON = "snr_report.json"
REPORT_MD = "snr_report.md"

_K = math.ceil(SKY_ANNULUS[1])
_DY, _DX = np.mgrid[-_K : _K + 1, -_K : _K + 1]
_RING = (np.hypot(_DX, _DY) >= SKY_ANNULUS[0]) & (np.hypot(_DX, _DY) <= SKY_ANNULUS[1])
RING_DY, RING_DX = _DY[_RING], _DX[_RING]
N_APERTURE = (2 * APERTURE_HALF + 1) ** 2


@dataclass(frozen=True)
class Measure:
    """Aperture flux above the local sky ring and its noise (MJy/sr x px) by the variance/annulus methods."""

    flux: float
    sigma_variance: float  # NaN without a VARIANCE plane
    sigma_annulus: float


def robust_sigma(values: np.ndarray) -> float:
    values = np.asarray(values, dtype=np.float64)
    values = values[np.isfinite(values)]
    if values.size < 2:
        return float("nan")
    return float(MAD_TO_SIGMA * np.median(np.abs(values - np.median(values))))


def independent_sigma(pixel_sigma: float, n_ring: int) -> float:
    """Aperture noise for independent pixels of noise ``pixel_sigma``: sum of N_APERTURE pixels minus N x ring median."""
    return pixel_sigma * math.sqrt(N_APERTURE + N_APERTURE**2 * MEDIAN_VARIANCE_FACTOR / n_ring)


def measure(data: np.ndarray, variance: np.ndarray | None, x: int, y: int) -> Measure | None:
    """5x5 aperture at (x, y) above the 4-7 px ring median; None if a box pixel or most of the ring is missing."""
    h = APERTURE_HALF
    ny, nx = data.shape
    if not (_K <= x < nx - _K and _K <= y < ny - _K):
        return None
    box = data[y - h : y + h + 1, x - h : x + h + 1].astype(np.float64)
    ring = data[y + RING_DY, x + RING_DX].astype(np.float64)
    ok = np.isfinite(ring)
    if not np.isfinite(box).all() or ok.sum() < MIN_RING_FRACTION * ring.size:
        return None
    ring = ring[ok]
    flux = float(box.sum() - N_APERTURE * np.median(ring))
    sigma_var = float("nan")
    if variance is not None:
        vbox = variance[y - h : y + h + 1, x - h : x + h + 1].astype(np.float64)
        vring = variance[y + RING_DY, x + RING_DX].astype(np.float64)[ok]
        if np.isfinite(vbox).all() and np.isfinite(vring).all():
            sky_var = MEDIAN_VARIANCE_FACTOR * float(vring.mean()) / ring.size
            sigma_var = math.sqrt(float(vbox.sum()) + N_APERTURE**2 * sky_var)
    return Measure(flux, sigma_var, independent_sigma(robust_sigma(ring), int(ring.size)))


def expected_snr(fluxes: Sequence[float], sigmas: Sequence[float], weights: Sequence[float]) -> float:
    """SNR of the weighted mean of independent measurements: sum(w F) / sqrt(sum(w^2 sigma^2))."""
    f, s, w = (np.asarray(v, dtype=np.float64) for v in (fluxes, sigmas, weights))
    return float((w * f).sum() / math.sqrt(float((w**2 * s**2).sum())))


def _grow(mask: np.ndarray, r: int) -> np.ndarray:
    out = mask.copy()
    padded = np.pad(mask, r)
    ny, nx = mask.shape
    for dy in range(-r, r + 1):
        for dx in range(-r, r + 1):
            out |= padded[r + dy : r + dy + ny, r + dx : r + dx + nx]
    return out


def _usable_box(frame: GridFrame, x: int, y: int) -> bool:
    h = APERTURE_HALF
    sl = (slice(y - h, y + h + 1), slice(x - h, x + h + 1))
    ok = np.isfinite(frame.data[sl]) & ~frame.bad[sl]
    if frame.variance is not None:
        ok &= np.isfinite(frame.variance[sl]) & (frame.variance[sl] > 0)
    return bool(ok.all())


def _in_target(x: int, y: int, exclude: tuple[float, float, float]) -> bool:
    return math.hypot(x - exclude[0], y - exclude[1]) < exclude[2]


def blank_positions(
    c: Coadd, frames: Sequence[GridFrame], exclude: tuple[float, float, float]
) -> list[tuple[int, int]]:
    """Non-overlapping aperture centres free of coadd sources, outside the target circle, usable in every frame."""
    data = c.data.astype(np.float64)
    sky_free = data - np.nanmedian(data)
    sigma = robust_sigma(sky_free)
    with np.errstate(invalid="ignore"):
        sources = _grow(~np.isfinite(sky_free) | (sky_free > SOURCE_MASK_SIGMAS * sigma), SOURCE_MASK_GROW_PX)
    step = 2 * APERTURE_HALF + 1
    ny, nx = data.shape
    out = []
    for y in range(EDGE_MARGIN_PX, ny - EDGE_MARGIN_PX, step):
        for x in range(EDGE_MARGIN_PX, nx - EDGE_MARGIN_PX, step):
            if sources[y, x] or _in_target(x, y, exclude):
                continue
            if all(_usable_box(f, x, y) for f in frames):
                out.append((x, y))
    return out


def blank_measures(data: np.ndarray, positions: Sequence[tuple[int, int]]) -> tuple[np.ndarray, np.ndarray]:
    """(aperture flux, independent-pixel noise prediction) at each blank position; NaN where it cannot be measured."""
    ms = [measure(data, None, x, y) for x, y in positions]
    flux = np.array([m.flux if m else np.nan for m in ms], dtype=np.float64)
    indep = np.array([m.sigma_annulus if m else np.nan for m in ms], dtype=np.float64)
    return flux, indep


def blank_noise(data: np.ndarray, positions: Sequence[tuple[int, int]]) -> tuple[float, float]:
    """(robust scatter of the aperture flux at blank ``positions``, median independent-pixel prediction there)."""
    flux, indep = blank_measures(data, positions)
    if np.isfinite(flux).sum() < MIN_BLANK_APERTURES:
        return float("nan"), float("nan")
    return robust_sigma(flux), float(np.nanmedian(indep))


def random_noise_scale(fluxes: np.ndarray, weights: Sequence[float]) -> float:
    """k with random aperture noise variance k / w_i in frame i, from pairwise differences at the same blank positions.

    Static sky structure (faint sources, background) is the same in every frame and cancels in b_i - b_j,
    whose variance is then k (1/w_i + 1/w_j): the frame noise ratio is taken from the weights (VARIANCE).
    Median over pairs; NaN with fewer than ``MIN_BLANK_APERTURES`` common positions.
    """
    ks = []
    for i in range(len(weights)):
        for j in range(i + 1, len(weights)):
            d = fluxes[i] - fluxes[j]
            if np.isfinite(d).sum() >= MIN_BLANK_APERTURES:
                ks.append(robust_sigma(d) ** 2 / (1 / weights[i] + 1 / weights[j]))
    return float(np.median(ks)) if ks else float("nan")


def select_stars(c: Coadd, frames: Sequence[GridFrame], exclude: tuple[float, float, float]) -> list[tuple[int, int]]:
    """Isolated, unflagged, unsaturated field stars of the coadd (see the module docstring)."""
    data = c.data.astype(np.float64)
    sigma = robust_sigma(data)
    if not (math.isfinite(sigma) and sigma > 0):
        return []
    peaks = find_stars(data, sigma, min_snr=NEIGHBOUR_SNR)
    ny, nx = data.shape
    out = []
    for x, y in find_stars(data, sigma, min_snr=MIN_PEAK_SNR, exclude=exclude):
        if not (EDGE_MARGIN_PX <= x < nx - EDGE_MARGIN_PX and EDGE_MARGIN_PX <= y < ny - EDGE_MARGIN_PX):
            continue
        if any(0 < math.hypot(px - x, py - y) <= ISOLATION_PX for px, py in peaks):
            continue
        h = APERTURE_HALF
        if not (c.coverage[y - h : y + h + 1, x - h : x + h + 1] == len(frames)).all():
            continue
        if all(_usable_box(f, x, y) for f in frames):
            out.append((x, y))
    return out


def _snr_block(fluxes: list[float], sigmas: list[float], flux_c: float, sigma_c: float, weights: list[float]) -> dict:
    single = [f / s for f, s in zip(fluxes, sigmas, strict=True)]
    median_single = float(np.median(single))
    snr_c = flux_c / sigma_c
    expected = expected_snr(fluxes, sigmas, weights)
    return {
        "single": single,
        "coadd": snr_c,
        "expected": expected,
        "gain_measured": snr_c / median_single,
        "gain_expected": expected / median_single,
        "gain_ivw_ideal": math.sqrt(sum(s * s for s in single)) / median_single,
        "ratio": snr_c / expected,
    }


def _star(frames: Sequence[GridFrame], c: Coadd, x: int, y: int, blank: dict) -> dict | None:
    singles = [measure(f.data, f.variance, x, y) for f in frames]
    mc = measure(c.data, c.variance, x, y)
    if mc is None or mc.flux <= 0 or any(m is None or m.flux <= 0 for m in singles):
        return None
    fluxes = [m.flux for m in singles]
    w = c.weights
    out = {
        "x": x,
        "y": y,
        "flux_single": fluxes,
        "flux_coadd": mc.flux,
        "flux_consistency": mc.flux / (sum(wi * fi for wi, fi in zip(w, fluxes, strict=True)) / sum(w)),
        "snr": {},
    }
    noises = {
        "variance": ([m.sigma_variance for m in singles], mc.sigma_variance),
        "annulus": ([m.sigma_annulus for m in singles], mc.sigma_annulus),
        "blank": (blank["single_sigma"], blank["coadd_sigma"]),
    }
    for name, (sig, sig_c) in noises.items():
        if all(math.isfinite(s) and s > 0 for s in [*sig, sig_c]):
            out["snr"][name] = _snr_block(fluxes, list(sig), mc.flux, sig_c, w)
    return out


def _median(values: list[float]) -> float | None:
    vals = [v for v in values if v is not None and math.isfinite(v)]
    return float(np.median(vals)) if vals else None


def _method_summary(stars: list[dict], name: str) -> dict:
    blocks = [s["snr"][name] for s in stars if name in s["snr"]]
    ratios = [b["ratio"] for b in blocks]
    return {
        "n_stars": len(blocks),
        "median_single_snr": _median([float(np.median(b["single"])) for b in blocks]),
        "median_coadd_snr": _median([b["coadd"] for b in blocks]),
        "median_gain_measured": _median([b["gain_measured"] for b in blocks]),
        "median_gain_expected": _median([b["gain_expected"] for b in blocks]),
        "median_ratio": _median(ratios),
        "ratio_p16": float(np.percentile(ratios, 16)) if ratios else None,
        "ratio_p84": float(np.percentile(ratios, 84)) if ratios else None,
    }


def _blank_block(frames: Sequence[GridFrame], c: Coadd, positions: list[tuple[int, int]]) -> dict:
    single = [blank_noise(f.data, positions) for f in frames]
    sig_c, indep_c = blank_noise(c.data, positions)
    sig = [s for s, _ in single]
    w = np.asarray(c.weights, dtype=np.float64)
    finite = all(math.isfinite(s) for s in [*sig, sig_c])
    expected = float(math.sqrt(float((w**2 * np.square(sig)).sum())) / w.sum()) if finite else float("nan")
    k = random_noise_scale(np.array([blank_measures(f.data, positions)[0] for f in frames]), c.weights)
    static_var, with_static, random_fraction = float("nan"), float("nan"), float("nan")
    if finite and math.isfinite(k):
        static_var = max(0.0, float(np.median([s**2 - k / wi for s, wi in zip(sig, w, strict=True)])))
        with_static = math.sqrt(static_var + k / float(w.sum()))
        random_fraction = float(np.median([math.sqrt(k / wi) / s for s, wi in zip(sig, w, strict=True)]))
    return {
        "n_positions": len(positions),
        "single_sigma": sig,
        "coadd_sigma": sig_c,
        "expected_coadd_sigma": expected,
        "noise_ratio": expected / sig_c if finite else float("nan"),  # 1 = sky noise drops as the weights promise
        "correlation_single": [s / i for s, i in single],  # blank scatter / independent-pixel prediction
        "correlation_coadd": sig_c / indep_c,
        # random (frame-to-frame) part of the blank noise from pairwise differences; the rest is static sky
        "random_fraction_single": random_fraction,  # random sigma / total blank sigma, median over frames
        "static_sigma": math.sqrt(static_var) if math.isfinite(static_var) else float("nan"),
        "expected_coadd_sigma_with_static": with_static,  # static part does not average down
        "noise_ratio_with_static": with_static / sig_c if math.isfinite(with_static) else float("nan"),
    }


def _flags(group: dict) -> list[str]:
    out = []
    ratio = group["methods"]["blank"]["median_ratio"]
    if group["methods"]["blank"]["n_stars"] < 3:
        out.append(f"only {group['methods']['blank']['n_stars']} usable star(s): the medians are noisy")
    if ratio is not None and ratio < LOW_RATIO:
        why = "unexplained"
        b = group["blank"]
        corr_s, corr_c = _median(b["correlation_single"]), b["correlation_coadd"]
        static_ok = (
            b["noise_ratio_with_static"] is not None and abs(b["noise_ratio_with_static"] - 1) <= STATIC_TOLERANCE
        )
        if b["noise_ratio"] < LOW_RATIO and static_ok:
            why = (
                f"static sky structure: only {b['random_fraction_single']:.0%} of the single-frame blank noise "
                "changes between frames, the rest (faint sources, background) is the same in every frame and does "
                f"not average down; with that static part the expected coadd noise matches "
                f"(ratio {b['noise_ratio_with_static']:.2f})"
            )
        elif b["noise_ratio"] < LOW_RATIO:
            why = "the blank-sky noise itself drops less than expected and a static-sky model does not explain it"
        elif corr_s and math.isfinite(corr_c) and corr_c > 1.2 * corr_s:
            why = "the coadd's pixel correlation is higher than in the single frames"
        out.append(f"gain well below expectation (blank-noise ratio {ratio:.2f}): {why}")
    flux = group["median_flux_consistency"]
    if flux is not None and abs(flux - 1) > FLUX_TOLERANCE:
        out.append(f"coadd flux differs from the weighted mean of single fluxes (median {flux:.3f})")
    return out


def check_group(frames: Sequence[GridFrame], season: int) -> dict | None:
    """Single-frame vs coadd photometry of one (season, detector); None with fewer than ``MIN_FRAMES`` usable frames."""
    c = coadd(frames, season)
    used = [f for f in frames if f.frame_id in set(c.frame_ids)]
    if len(used) < MIN_FRAMES:
        return None
    exclude = target_exclusion(c.data.astype(np.float64))
    blank = _blank_block(used, c, blank_positions(c, used, exclude))
    stars = [s for x, y in select_stars(c, used, exclude) if (s := _star(used, c, x, y, blank)) is not None]
    group = {
        "id": c.id,
        "detector": c.detector,
        "season": season,
        "n_frames": len(used),
        "frame_ids": c.frame_ids,
        "weights": c.weights,
        "target_exclude_px": round(exclude[2], 2),
        "blank": blank,
        "median_flux_consistency": _median([s["flux_consistency"] for s in stars]),
        "methods": {m: _method_summary(stars, m) for m in METHODS},
        "stars": stars,
    }
    group["flags"] = _flags(group)
    return group


def check_frames(frames: Sequence[GridFrame], season_of: dict[str, int]) -> list[dict]:
    """``check_group`` for every (detector, season) of ``frames`` (``season_of``: frame_id -> season)."""
    groups: dict[tuple[int, int], list[GridFrame]] = {}
    for f in frames:
        groups.setdefault((f.detector, season_of[f.frame_id]), []).append(f)
    out = []
    for (_, season), fs in sorted(groups.items()):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            g = check_group(fs, season)
        if g is not None:
            out.append(g)
    return out


def summarise(fields: list[dict]) -> dict:
    """Median ratio and spread over all stars (per method), flux consistency, sky-noise ratio, flagged groups."""
    groups = [g for f in fields for g in f["groups"]]
    stars = [s for g in groups for s in g["stars"]]
    out: dict = {"n_groups": len(groups), "n_stars": len(stars), "methods": {}}
    for name in METHODS:
        ratios = [s["snr"][name]["ratio"] for s in stars if name in s["snr"]]
        gains = [(s["snr"][name]["gain_measured"], s["snr"][name]["gain_expected"]) for s in stars if name in s["snr"]]
        out["methods"][name] = {
            "n_stars": len(ratios),
            "median_ratio": _median(ratios),
            "ratio_p16": float(np.percentile(ratios, 16)) if ratios else None,
            "ratio_p84": float(np.percentile(ratios, 84)) if ratios else None,
            "median_gain_measured": _median([m for m, _ in gains]),
            "median_gain_expected": _median([e for _, e in gains]),
        }
    flux = [s["flux_consistency"] for s in stars]
    out["flux_consistency"] = {
        "median": _median(flux),
        "p16": float(np.percentile(flux, 16)) if flux else None,
        "p84": float(np.percentile(flux, 84)) if flux else None,
    }
    out["blank_noise_ratio_median"] = _median([g["blank"]["noise_ratio"] for g in groups])
    out["blank_noise_ratio_with_static_median"] = _median([g["blank"]["noise_ratio_with_static"] for g in groups])
    out["random_fraction_single_median"] = _median([g["blank"]["random_fraction_single"] for g in groups])
    out["correlation_single_median"] = _median([c for g in groups for c in g["blank"]["correlation_single"]])
    out["correlation_coadd_median"] = _median([g["blank"]["correlation_coadd"] for g in groups])
    out["flagged"] = [
        {"field_id": f["field_id"], "group": g["id"], "flags": g["flags"]}
        for f in fields
        for g in f["groups"]
        if g["flags"]
    ]
    return out


def _clean(value):
    """NaN/inf -> None for strict JSON, recursively."""
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, dict):
        return {k: _clean(v) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [_clean(v) for v in value]
    return value


def check_field(field, load) -> dict:
    """``check_frames`` on a built field; ``load`` as for ``compare.compare_field`` (e.g. ``load_from_cutouts``)."""
    from ..build import season_index
    from ..models import FrameRef

    refs = [
        FrameRef(obs_id=f.obs_id, detector=f.detector, mjd=f.mjd, release=f.release, irsa_uri=f.source_uri)
        for f in field.frames
    ]
    seasons = season_index([f.mjd for f in field.frames])
    loaded = load(refs)
    frames = [g for g in loaded if g is not None]
    season_of = {g.frame_id: s for g, s in zip(loaded, seasons, strict=True) if g is not None}
    return {
        "field_id": field.id,
        "n_frames_loaded": len(frames),
        "n_frames_field": len(field.frames),
        "groups": check_frames(frames, season_of),
    }


METHOD_TEXT = [
    "Per (field, detector, season) with >= 2 usable frames, the season coadd is rebuilt with `compare.coadd` "
    "(one weight per frame, w_i = 1 / median VARIANCE; sky removed per frame; flagged pixels left out).",
    "Field stars: isolated local maxima of the coadd >= 10 robust pixel sigmas above their local sky ring, no other "
    "peak >= 5 sigma within 7 px, >= 8 px from the grid edge, outside the target circle of "
    "`compare.target_exclusion`, every 5x5 aperture pixel usable (finite, unflagged, positive variance) in every "
    "frame and covered by all frames in the coadd (saturated or flagged cores are out).",
    "Flux: 5x5 px aperture sum minus 25 x the median of the 4-7 px sky ring, in every single frame and in the coadd.",
    "Noise, three ways: `variance` = propagated VARIANCE (sum over the aperture + sky-median term); `annulus` = "
    "robust scatter of the star's sky ring, pixels taken as independent; `blank` = robust scatter of the same "
    "aperture on star-free, non-overlapping positions of the same image (identical positions in each frame and "
    "the coadd), which includes pixel correlation and sky subtraction.",
    "Expected coadd SNR for the weights used: sum(w_i F_i) / sqrt(sum(w_i^2 sigma_i^2)) with each frame's flux "
    "and noise (inverse-variance weights reduce this to sqrt(sum SNR_i^2); equal noise and flux to sqrt(N) SNR). "
    "Gain = SNR / median single-frame SNR. Ratio = measured / expected coadd SNR. Flux consistency = coadd flux / "
    "weighted mean of the single-frame fluxes.",
    "Sky-noise ratio (per group): expected / measured blank-aperture noise of the coadd. Correlation factor: "
    "blank-aperture scatter / the prediction for independent pixels of the same per-pixel scatter.",
    "Static vs random sky: the difference of two frames at the same blank positions cancels what is the same in "
    "every frame (faint sources, background structure), so its scatter gives the random noise, k / w_i in frame "
    "i (noise ratio between frames from the weights). Static variance = single-frame blank variance - k / w_i "
    "(median over frames). 'With static' = expected coadd noise sqrt(static + k / sum w) / measured.",
]
LIMITS_TEXT = [
    "Two or three frames per (season, detector): each group's medians rest on few frames, so single groups "
    "scatter; the all-star median is the meaningful number.",
    "Stars are not checked against a catalogue for variability. Each frame samples another wavelength (linear "
    "variable filter), so a star's flux changes between frames; the expected SNR uses each frame's own flux, so "
    "the test does not need constant fluxes, but a flux consistency far from 1 would show a non-linear step.",
    "The `variance` noise of reprojected frames is optimistic: bilinear reprojection makes the per-pixel variance "
    "up to 4x smaller and neighbouring pixels correlated. Its ratio is mostly a check that the coadd propagates "
    "VARIANCE as the weights say, not an independent test. The `blank` noise is the honest one, but it is "
    "background-only: it leaves out the star's own Poisson noise, so its SNRs are upper limits for bright stars.",
    "Blank positions avoid coadd pixels > 3 sigma (grown by 3 px); fainter, unresolved sources stay in the "
    "background. Static structure does not average down, so a sky-noise ratio below 1 is a property of the sky, "
    "not a bug of the coadd.",
    "The static/random split assumes the static sky is identical in every frame; frames of one season sample "
    "slightly different wavelengths, so part of the static structure leaks into the differences and the random "
    "part is an upper limit.",
    "Golden fields only (the five official targets, cached cutouts as built). Results do not cover other fields.",
]


def _fmt(v, nd: int = 2) -> str:
    return "-" if v is None or (isinstance(v, float) and not math.isfinite(v)) else f"{v:.{nd}f}"


def _group_row(field_id: str, g: dict) -> str:
    b, a, v = (g["methods"][m] for m in ("blank", "annulus", "variance"))
    return (
        f"| {field_id} | {g['id']} | {g['n_frames']} | {b['n_stars']} | {_fmt(b['median_single_snr'], 1)} | "
        f"{_fmt(b['median_coadd_snr'], 1)} | {_fmt(b['median_gain_measured'])} | {_fmt(b['median_gain_expected'])} | "
        f"{_fmt(b['median_ratio'])} | {_fmt(a['median_ratio'])} | {_fmt(v['median_ratio'])} | "
        f"{_fmt(g['median_flux_consistency'], 3)} | {_fmt(g['blank']['noise_ratio'])} | "
        f"{_fmt(g['blank']['noise_ratio_with_static'])} | {_fmt(g['blank']['random_fraction_single'])} |"
    )


def render_markdown(report: dict) -> str:
    s = report["summary"]
    lines = [
        "# Coadd SNR check (WS2-10)",
        "",
        f"Built {report['built_at']} by `python -m errante.imaging.snrcheck`. PROVISIONAL, not part of the data "
        "contract. Numbers come from the cached SPHEREx cutouts of the built golden fields.",
        "",
        "## Method",
        "",
        *[f"- {t}" for t in METHOD_TEXT],
        "",
        "## Summary (all stars)",
        "",
        f"{s['n_stars']} stars in {s['n_groups']} (field, detector, season) groups.",
        "",
        "| noise | stars | median gain measured | median gain expected | median ratio | ratio p16-p84 |",
        "|---|---|---|---|---|---|",
    ]
    for name in METHODS:
        m = s["methods"][name]
        lines.append(
            f"| {name} | {m['n_stars']} | {_fmt(m['median_gain_measured'])} | {_fmt(m['median_gain_expected'])} | "
            f"{_fmt(m['median_ratio'])} | {_fmt(m['ratio_p16'])}-{_fmt(m['ratio_p84'])} |"
        )
    fc = s["flux_consistency"]
    lines += [
        "",
        f"- Flux consistency (coadd / weighted mean of singles): median {_fmt(fc['median'], 3)}, "
        f"p16-p84 {_fmt(fc['p16'], 3)}-{_fmt(fc['p84'], 3)}.",
        f"- Sky-noise ratio (expected / measured blank-aperture noise of the coadd), median over groups: "
        f"{_fmt(s['blank_noise_ratio_median'])}; with a static-sky part that does not average down: "
        f"{_fmt(s['blank_noise_ratio_with_static_median'])}.",
        f"- Random (frame-to-frame) part of the single-frame blank noise, median over groups: "
        f"{_fmt(s['random_fraction_single_median'])} (from pairwise frame differences at the blank positions).",
        f"- Correlation factor (blank scatter / independent-pixel prediction): single frames "
        f"{_fmt(s['correlation_single_median'])}, coadds {_fmt(s['correlation_coadd_median'])}.",
        "",
        "## Per group (SNR, gains and first ratio from the `blank` noise)",
        "",
        "| field | group | N | stars | single SNR | coadd SNR | gain meas. | gain exp. | ratio blank | "
        "ratio annulus | ratio variance | flux cons. | sky-noise ratio | with static | random frac. |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|",
        *[_group_row(f["field_id"], g) for f in report["fields"] for g in f["groups"]],
        "",
        "## Flagged groups",
        "",
        *([f"- {x['field_id']} {x['group']}: {'; '.join(x['flags'])}" for x in s["flagged"]] or ["- none"]),
        "",
        "## Limits",
        "",
        *[f"- {t}" for t in LIMITS_TEXT],
        "",
    ]
    return "\n".join(lines)


def write_report(fields: list[dict], out: Path) -> dict:
    """Write ``out/snr_report.json`` and ``out/snr_report.md``; return the report."""
    report = {
        "format": "errante-snrcheck/0 (provisional; not part of the data contract)",
        "built_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "method": METHOD_TEXT,
        "limitations": LIMITS_TEXT,
        "summary": summarise(fields),
        "fields": fields,
    }
    report = _clean(report)
    out.mkdir(parents=True, exist_ok=True)
    (out / REPORT_JSON).write_text(json.dumps(report, indent=1, allow_nan=False) + "\n", encoding="utf-8")
    (out / REPORT_MD).write_text(render_markdown(report), encoding="utf-8")
    return report


def main(argv: Sequence[str] | None = None) -> int:
    from ..products import ProductStore
    from .compare import load_from_cutouts

    parser = argparse.ArgumentParser(prog="python -m errante.imaging.snrcheck", description=__doc__.splitlines()[0])
    parser.add_argument("--field", action="append", help="field id (repeatable; default: every built field)")
    parser.add_argument("--dir", default="data/products", help="product directory with fields/<id>/field.json")
    parser.add_argument("--out", required=True, help="directory for snr_report.md and snr_report.json")
    args = parser.parse_args(argv)
    store = ProductStore(Path(args.dir))
    ids = args.field or sorted(p.name for p in (Path(args.dir) / "fields").iterdir() if (p / "field.json").exists())
    fields = []
    for fid in ids:
        if not store.has_field(fid):
            print(f"No built field '{fid}' in {args.dir}", file=sys.stderr)
            return 2
        field = store.read_field(fid)
        fields.append(check_field(field, load_from_cutouts(field)))
    report = write_report(fields, Path(args.out))
    s = report["summary"]["methods"]["blank"]
    print(
        f"{report['summary']['n_stars']} stars in {report['summary']['n_groups']} groups; blank-noise median ratio "
        f"{_fmt(s['median_ratio'])} (p16-p84 {_fmt(s['ratio_p16'])}-{_fmt(s['ratio_p84'])}); report in {args.out}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
