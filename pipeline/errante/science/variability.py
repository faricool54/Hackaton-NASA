"""Light curves of one sky position from every SPHEREx exposure (WS3-9, R05: RW Aurigae and R Draconis).

SPHEREx has a linear variable filter: each exposure measures the target at ANOTHER wavelength, and a star's
spectrum is not flat, so single-exposure brightnesses "blink" even for a constant star (docs/SCIENCE.md §0.4).
Same detector does NOT mean same wavelength. Brightness is therefore only compared WITHIN narrow wavelength bins
of one detector (``lambda_bin_frac``, default 1 %: the |dlambda|/lambda < 1 % rule of the validation records), as a
relative magnitude ``-2.5 log10(F / bin geometric mean)`` (i.e. minus the bin's mean magnitude). Bins with one point
carry no time information and are dropped; so are bins spanning less than ``min_bin_span_days`` (default 30 d, as
in the R Dra review), whose points stay listed with ``excluded='short_bin'``.

Two measurement methods, both validated offline on the real FITS (docs/validation/rw-aurigae.md and
docs/validation/r-draconis.md; numbers there):

* ``aperture`` (RW Aurigae, D1): circular aperture r = 3 px on IMAGE (minus ZODI when read), local sky = median of
  a 6-10 px annulus, error from VARIANCE plus the sky term. It is WS2's ``imaging.photometry.aperture_flux``, not a
  new photometry. Exposures with OVERFLOW in the aperture (saturated: the flux is a lower limit), DEFAULT_BAD
  pixels, an aperture off the stamp, no sky, no FLAGS or no wavelength are EXCLUDED and counted by reason.
* ``wing`` (R Draconis, saturated in 2488 of 2488 exposures): the unsaturated PSF wing, 20 %-trimmed mean of a
  12-20 px annulus (DEFAULT_BAD, BLOOM, NONLINEAR, TRANSIENT and OUTLIER pixels masked) minus the median of a
  40-55 px annulus, in MJy/sr. Only RELATIVE within one detector and wavelength bin: the wing fraction depends on
  wavelength and detector (the review found the 8-12/12-20 px ratio stable to <= 0.07 mag, focal-plane position not
  modelled). Its statistical error is tiny next to the empirical floor (0.08-0.38 mag per detector for R Dra).

Comparison stars (control): bright, unsaturated, isolated field stars found in the stamps themselves
(:func:`find_field_stars` on 5 exposures per detector spread in time, merged on the sky, kept when found at least
twice; >= 10 px from the target, >= 30 px for ``wing`` so they are off its variable halo), fixed in RA/Dec, measured
with the APERTURE method in the same exposures (also for ``wing``: a faint star's wing is noise, as the R Dra record
shows) and binned at their own wavelength. Their per-point scatter is the empirical systematic floor of single points
(``control``, with their exclusions counted per detector); their per-frame median relative magnitude is an optional
zero point (``LightCurvePoint.zero_point_mag``, not applied). Each comparison is checked per exposure exactly like the
target (saturation, bad pixels, edge). Because the comparisons are measured with an aperture, ``scatter_over_control``
is only given for the ``aperture`` method (WS3 review LC24).
:func:`matched_pairs` reproduces the RW Aur method (same detector, |dlambda|/lambda < 1 %, frames far apart in time,
with the comparison ensemble measured in the SAME two frames and, since the review's LC28, only from comparisons whose
own two wavelengths also match). With the ``aperture`` method the floor for such pairs is not the per-point control
but the comparisons' own matched-pair scatter (:func:`comparison_pair_scatter`, in the notes): 1.4-1.9x larger on the
real products (LC26). With ``wing`` it is NOT a floor for the target's pairs: the comparisons are aperture
measurements and the wing has its own floor (R Dra D1: ``floor_mag`` 0.35 mag per exposure against a comparison pair
scatter of 0.030 mag).
Known limits of the 1 % match (LC28, not corrected): where the spectrum is steep a 1 % bin is wide (in R Dra D1 the
wavelength slope within a bin explains ~0.14 of the 0.29 mag residual), and in D5/D6 a 1 % bin is wider than the
linear-variable-filter channel.

Period: :func:`estimate_period` fits, on a frequency grid, per-bin offsets plus a sinusoid with free amplitude and
phase per detector (weighted least squares with a per-detector error floor such that chi2/dof = 1, as in the R Dra
review; the floors are evaluated at the reported period). The grid always has a best period, even for noise, so the
estimate is tested like the R Dra record: the visit epochs are permuted (100 times by default), the grid refitted, and
the result is ``significant`` only when ``false_alarm`` = (1 + k) / (1 + n) <= 1 %, k being the permutations that
peak as high. That establishes time-correlated variability, NOT a period: a trend or a step also beats shuffled
epochs, at the long end of the grid (LC7). So the test is not run, and the best period stays an untested candidate,
when it lies within one grid step of the search range's ends or covers fewer than 1.5 cycles of the baseline (see
``MIN_PERIOD_CYCLES`` for why 1.5 and not the review's 2). The guard is partial: a weak trend or step can still pass
at a shorter period, so 'significant' keeps meaning variability, not periodicity. It is a quick estimate, not a periodogram analysis: Miras are not sinusoids, seasonal gaps make aliases (the returned
``peaks`` list them; R Dra has one at ~144 d), formal errors exclude model error and the bootstrap interval is
conditional on the chosen peak. Confirm against an independent contemporaneous light curve (e.g. AAVSO) and catalog
periods (Gaia DR3 ``vari_long_period_variable``).

Data: WS1 ``data.point.point_series`` stamps (S3 Range reads of whole detector rows, so the cost grows with the box
side: ~``box_px`` x 8 KB per plane). Defaults: ``aperture`` reads IMAGE + VARIANCE + FLAGS in an 81 px box (8.3',
room for comparison stars, like the 8' patches of the RW Aur record), ``wing`` IMAGE + FLAGS in a 111 px box (the
55 px background annulus). ZODI is not read: the local background annulus removes the zodiacal light (smooth on
arcminute scales), and it saves a quarter of the bytes. Runtime measured live 2026-11-15 (laptop in Buenos Aires ->
S3 us-east-1, 48 requests in flight): RW Aur D1, 56 exposures: 8.7 s fully cold with 61 px stamps (1.4 MB each),
5.3 s with 81 px (1.7 MB each, file layouts cached); R Dra wing, 900 of its 2493 exposures (deep collections
included): 89 s cold (74 s reading 1.40 GB, 15 s measuring); a cached series costs only the measuring (~1-15 s).
Not for a live 30 s API call on R Dra: use ``max_frames``/``deadline_s`` or precompute.
"""

from __future__ import annotations

import math
import time
import warnings
from collections import Counter, defaultdict
from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta

import numpy as np

from ..data.epochs import SEASON_GAP_DAYS, VISIT_GAP_HOURS, group_seasons
from ..imaging import photometry
from ..imaging.flags import DEFAULT_BAD, bitmask

METHODS = ("aperture", "wing")
APERTURE_PX = 3.0
APERTURE_ANNULUS_PX = (6.0, 10.0)
WING_ANNULUS_PX = (12.0, 20.0)
WING_BACKGROUND_PX = (40.0, 55.0)
WING_TRIM = 0.2
WING_MASK = bitmask([*DEFAULT_BAD, "BLOOM", "NONLINEAR", "TRANSIENT", "OUTLIER"])
BAD = bitmask(list(DEFAULT_BAD))
OVERFLOW = bitmask(["OVERFLOW"])
CORE_PX = 3.0  # radius checked for a saturated core (informational for ``wing``)
MIN_WING_COVERAGE = 0.9  # fraction of the wing annulus inside the stamp
MIN_WING_GOOD = 0.5  # fraction of the in-stamp wing pixels left after masking
MIN_BACKGROUND_COVERAGE = 0.5
DEFAULT_BOX_PX = {"aperture": 81, "wing": 2 * math.ceil(WING_BACKGROUND_PX[1]) + 1}  # 8.3' (room for comparisons)
DEFAULT_PLANES = {"aperture": ("IMAGE", "VARIANCE", "FLAGS"), "wing": ("IMAGE", "FLAGS")}
LAMBDA_BIN_FRAC = 0.01
MIN_BIN_SPAN_DAYS = 30.0
N_COMPARISON = 8
COMPARISON_MIN_SEP_PX = {"aperture": 10.0, "wing": 30.0}
# wing: closer stars sit on the target's bright, variable halo (R Dra, measured 2026-11-15: comparison scatter
# 0.07-0.4 mag at 21-25 px against 0.01-0.12 mag at >= 31 px)
COMPARISON_MIN_FOUND = 2  # a star picked in one reference exposure only was often an artefact or a faint source
COMPARISON_MATCH_PX = 1.5
COMPARISON_REFS_PER_DETECTOR = 5
COMPARISON_SNR = 30.0
PIXEL_ARCSEC = photometry.PIXEL_ARCSEC
MIN_PAIR_DT_DAYS = 30.0  # matched pairs: frames at least this far apart
MIN_PERIOD_POINTS = 30
PERIOD_RANGE_DAYS = (20.0, 800.0)
OVERSAMPLE = 20
MIN_PERIOD_CYCLES = 1.5  # a best period covering fewer cycles of the baseline is not tested (trend or partial cycle)
# Deliberately 1.5, not the 2 cycles the WS3 review's LC7 row asks for. Measured 2026-11-15 on R Dra's real sampling
# (450 points over 426 d, noise = its floors): no strong (0.5-1 mag) trend, parabola, fade, step or partial sinusoid
# (600-3000 d) had its best period at 1.5-2 cycles; they peak at <= 1.22 cycles, mostly the 800 d edge, except a few
# partial sinusoids caught near a turning point, which land on noise peaks beyond 2 cycles where neither value helps.
# 2 would only add 2 of 30 weak (0.3 mag) partial sinusoids that came out significant at 1.5-2 cycles, and it would
# leave untested R Dra's own catalog period (GCVS 245.6 d, Gaia DR3 247.2 d: 1.72-1.73 cycles; best here 261.9 d,
# 1.63), which the review itself expects to read "variability significant". Weak trends also pass at > 2 cycles
# (0.2 mag steps: 2 of 30 at 3.0-3.8), so no value makes 'significant' mean periodic: the caveat says so.
FLOOR_ITERATIONS = 5  # extra floor evaluations at the refined period, until it moves by < 1 fine-grid step
# (R Dra 2026-11-15: floors at 239.0 -> 259.1 -> 261.7 -> 261.9 d, settled after 3)
N_PERMUTATIONS = 100  # visit permutations for the period's false-alarm probability
# false_alarm = (1 + k) / (1 + n), k = permutations whose highest peak reaches the observed one; significant when it is
# <= 1 %: with n = 100 only k = 0 passes, and 1/101 is then the smallest value 100 permutations can give, not a
# measured probability nor an upper bound on it (the true one can be higher); n >= 99 is needed to pass at all
PERIOD_FALSE_ALARM = 0.01
SATURATION_SEASON_RANGE = 0.3  # spread of the saturated fraction between seasons that gets a censoring note
SATURATION_SEASON_MIN = 5  # exposures a season needs to enter that comparison
MAG = 2.5 / math.log(10.0)  # 1.0857: sigma_mag = MAG * sigma_F / F
UNITS = {"aperture": "mJy (r = 3 px aperture, no aperture correction)", "wing": "MJy/sr (PSF wing - background)"}
EXCLUDE_ORDER = (
    "no_flags",
    "saturated",
    "edge",
    "bad_pixels",
    "no_sky",
    "no_variance",
    "no_wavelength",
    "non_positive",
)
QUALITY_REASONS = frozenset(EXCLUDE_ORDER)
BIN_REASONS = frozenset({"lone_bin", "short_bin"})
PERIOD_CAVEAT = (
    "Quick sinusoid-grid estimate (per-detector amplitude and phase, per-wavelength-bin offsets). The best grid period "
    "of pure noise is still a number. 'significant' (visit-permutation false-alarm probability <= 1 %) means "
    "time-correlated variability: the sinusoid fits the data better than the same visits with shuffled epochs. It does "
    "not by itself establish a period (a trend or a step also passes), so the test is not run when the best period is "
    "at the edge of the search range or covers fewer than 1.5 cycles of the baseline (a weak trend can still pass at "
    "a shorter period). Seasonal gaps make aliases (see "
    "the other peaks), real light curves are not sinusoids, the formal error ignores model error and the bootstrap "
    "interval is conditional on the chosen peak: confirm with an independent contemporaneous light curve and catalog "
    "periods before quoting it."
)


# --- records -------------------------------------------------------------------------------------------------


@dataclass(eq=False)
class Exposure:
    """One stamp ready to measure: the image (``fits_io.SpherexImage``) plus what the archive said about it."""

    image: object  # fits_io.SpherexImage (data/flags/variance/zodi/wcs/header/obs_id/detector/mjd/wavelength_at)
    frame_id: str
    release: str
    wavelength_um: float | None  # at the target (PointSample.wavelength_um)
    bandwidth_um: float | None

    @property
    def mjd(self) -> float:
        return float(self.image.mjd)


@dataclass
class LightCurvePoint:
    frame_id: str
    obs_id: str
    detector: int
    release: str
    mjd: float  # mid-exposure (MJD-AVG)
    date: str  # ISO UTC of ``mjd``
    season: int  # 0-based, gaps > 30 d (data.epochs.group_seasons)
    wavelength_um: float | None
    bandwidth_um: float | None
    flux: float | None  # in LightCurve.unit
    flux_err: float | None
    bin: int | None = None  # index in LightCurve.bins
    rel_mag: float | None = None  # relative to the bin's mean magnitude (negative = brighter)
    rel_mag_err: float | None = None  # statistical (VARIANCE); add the control floor for the total
    zero_point_mag: float | None = None  # median comparison rel_mag in this exposure (>= 2 stars), not applied
    flags: tuple[str, ...] = ()
    excluded: str | None = None  # why it is not in the light curve (None = it is)


@dataclass
class WavelengthBin:
    index: int
    detector: int
    lambda_min_um: float
    lambda_max_um: float
    n_points: int
    mjd_min: float
    mjd_max: float
    mean_mag: float  # -2.5 log10 of the bin's geometric-mean flux (in LightCurve.unit)


@dataclass
class ComparisonStar:
    id: str
    ra: float
    dec: float
    found_in: int  # reference exposures where it was picked as a bright isolated star
    frame_ids: list[str] = field(default_factory=list)
    detectors: list[int] = field(default_factory=list)
    wavelength_um: list[float | None] = field(default_factory=list)
    flux_mjy: list[float | None] = field(default_factory=list)
    flux_err_mjy: list[float | None] = field(default_factory=list)
    rel_mag: list[float | None] = field(default_factory=list)
    excluded: list[str | None] = field(default_factory=list)


@dataclass
class PeriodEstimate:
    period_days: float
    delta_chi2: float  # chi2(no signal) - chi2(sinusoid) at the best period, with the floors below
    period_err_formal_days: float | None  # half width where delta_chi2 drops by 1 (statistical only)
    bootstrap_95_days: tuple[float, float] | None  # 2.5-97.5 % of the best period resampling visits
    peaks: list[tuple[float, float]]  # (period, delta_chi2) of the highest local maxima, best first
    amplitude_mag: dict[int, float]  # peak-to-peak of the fitted sinusoid per detector
    floor_mag: dict[int, float]  # per-detector error floor added in quadrature (chi2/dof = 1 at period_days)
    n_points: int
    baseline_days: float
    period_range_days: tuple[float, float]
    false_alarm: float | None = None  # (1 + k) / (1 + n) of the visit permutations (None: not run)
    n_permutations: int = 0  # permutations actually run (0 when the test was skipped)
    significant: bool | None = None  # false_alarm <= PERIOD_FALSE_ALARM; None when untested
    caveat: str = PERIOD_CAVEAT
    # Not serialised (the contract has no key for them; LightCurve.to_dict drops them): they reach the product
    # through period_note() and the caveat.
    untested_reason: str | None = None  # why the permutation test was skipped (edge of the grid, < 1.5 cycles)
    amplitude_err_mag: dict[int, float] = field(default_factory=dict)  # 1 sigma of amplitude_mag (fit covariance)


PERIOD_PRIVATE_FIELDS = ("untested_reason", "amplitude_err_mag")


@dataclass
class LightCurve:
    ra: float
    dec: float
    method: str
    unit: str
    lambda_bin_frac: float
    min_bin_span_days: float
    points: list[LightCurvePoint]
    bins: list[WavelengthBin]
    comparisons: list[ComparisonStar]
    control: dict[int, dict]  # per detector: comparison per-point scatter (the empirical floor) and exclusions
    summary: dict[int, dict]  # per detector: target points, scatter, range, exclusions (scatter_over_control: aperture)
    excluded: dict[str, int]  # reason -> exposures
    period: PeriodEstimate | None = None
    notes: list[str] = field(default_factory=list)
    failures: list[dict] = field(default_factory=list)
    search: dict = field(default_factory=dict)
    timings: dict = field(default_factory=dict)

    def used(self) -> list[LightCurvePoint]:
        """Points in the light curve (with a relative magnitude)."""
        return [p for p in self.points if p.rel_mag is not None]

    def to_dict(self) -> dict:
        """Strict-JSON dict (NaN/inf -> None, tuples -> lists, int keys -> str) with exactly the contract's keys."""
        d = asdict(self)
        if d["period"] is not None:
            for k in PERIOD_PRIVATE_FIELDS:
                d["period"].pop(k, None)
        return _json_safe(d)


def _json_safe(v):
    if isinstance(v, float):
        return v if math.isfinite(v) else None
    if isinstance(v, (np.floating, np.integer)):
        return _json_safe(v.item())
    if isinstance(v, dict):
        return {str(k): _json_safe(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [_json_safe(x) for x in v]
    return v


def mjd_to_iso(mjd: float) -> str:
    """ISO UTC (seconds) of an MJD, ignoring leap seconds (< 1 min)."""
    return (datetime(1858, 11, 17) + timedelta(days=float(mjd))).isoformat(timespec="seconds") + "Z"


# --- measurement ---------------------------------------------------------------------------------------------


def sky_to_pixel(img, ra, dec) -> tuple[np.ndarray, np.ndarray]:
    """0-based (x, y) on the stamp (numpy column, row) of sky positions (arrays allowed); NaN when undefined."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        x, y = img.wcs.all_world2pix(np.atleast_1d(ra), np.atleast_1d(dec), 0, quiet=True)
    return np.asarray(x, float), np.asarray(y, float)


def _window(shape, x: float, y: float, half: int):
    ny, nx = shape
    x0, x1 = max(0, int(math.floor(x)) - half), min(nx, int(math.floor(x)) + half + 2)
    y0, y1 = max(0, int(math.floor(y)) - half), min(ny, int(math.floor(y)) + half + 2)
    yy, xx = np.mgrid[y0:y1, x0:x1]
    return slice(y0, y1), slice(x0, x1), xx, yy


def _on_stamp(pl: photometry.Planes, x: float, y: float) -> bool:
    ny, nx = pl.data.shape
    return math.isfinite(x) and math.isfinite(y) and -0.5 <= x <= nx - 0.5 and -0.5 <= y <= ny - 0.5


def trimmed_mean(values: np.ndarray, trim: float) -> float:
    """Mean of the values left after dropping the ``trim`` fraction at each end."""
    v = np.sort(np.asarray(values, float))
    k = int(math.floor(trim * v.size))
    v = v[k : v.size - k] if v.size - 2 * k > 0 else v
    return float(v.mean())


def aperture_measure(pl: photometry.Planes, x: float, y: float) -> tuple[float, float, set[str]]:
    """Aperture flux (MJy/sr * px), error and flags at (x, y): WS2's aperture_flux with the RW Aur radii."""
    if not _on_stamp(pl, x, y):
        return float("nan"), float("nan"), {"edge"}
    flux, err, _sky, flags = photometry.aperture_flux(pl, x, y, APERTURE_PX, APERTURE_ANNULUS_PX)
    return flux, err, set(flags)


def wing_measure(
    pl: photometry.Planes,
    x: float,
    y: float,
    wing: tuple[float, float] = WING_ANNULUS_PX,
    background: tuple[float, float] = WING_BACKGROUND_PX,
    trim: float = WING_TRIM,
) -> tuple[float, float, set[str]]:
    """PSF-wing surface brightness (MJy/sr) at (x, y): trimmed mean of the wing annulus minus the background median.

    Flags: ``edge`` (wing annulus < 90 % inside the stamp), ``bad_pixels`` (< 50 % of it left after masking),
    ``no_sky`` (background annulus < 50 % inside or usable), ``saturated_core`` (OVERFLOW within 3 px:
    informational, the reason to use the wing), ``non_positive``.
    """
    flags: set[str] = set()
    if not _on_stamp(pl, x, y):
        return float("nan"), float("nan"), {"edge"}
    ys, xs, xx, yy = _window(pl.data.shape, x, y, int(math.ceil(background[1])) + 1)
    d, fl = pl.data[ys, xs], pl.flags[ys, xs]
    var = pl.variance[ys, xs] if pl.variance is not None else None
    dist = np.hypot(xx - x, yy - y)
    finite = np.isfinite(d)
    if ((fl & OVERFLOW) != 0)[dist <= CORE_PX].any():
        flags.add("saturated_core")
    ring = (dist >= wing[0]) & (dist <= wing[1])
    expected = _ring_pixels(wing)
    if ring.sum() < MIN_WING_COVERAGE * expected:
        return float("nan"), float("nan"), flags | {"edge"}
    use = ring & finite & ((fl & WING_MASK) == 0)
    if use.sum() < MIN_WING_GOOD * ring.sum():
        return float("nan"), float("nan"), flags | {"bad_pixels"}
    bg_ring = (dist >= background[0]) & (dist <= background[1])
    bg_use = bg_ring & finite & ((fl & BAD) == 0)
    if bg_use.sum() < MIN_BACKGROUND_COVERAGE * _ring_pixels(background):
        return float("nan"), float("nan"), flags | {"no_sky"}
    bg_vals = d[bg_use]
    bg = float(np.median(bg_vals))
    bg_sigma = float(1.4826 * np.median(np.abs(bg_vals - bg)))
    vals = d[use]
    n = int(vals.size)
    tm = trimmed_mean(vals, trim)
    if var is not None and np.isfinite(var[use]).all():
        err_wing = math.sqrt(float(np.sum(np.clip(var[use], 0, None)))) / n
    else:  # no VARIANCE plane read: background pixel noise (the wing's own photon noise is not included)
        err_wing = bg_sigma / math.sqrt(n)
    err_wing *= 1.0 / math.sqrt(1.0 - 2.0 * trim)  # trimming throws away data (approximate)
    err_bg = 1.2533 * bg_sigma / math.sqrt(bg_vals.size)
    flux = tm - bg
    if not flux > 0:
        flags.add("non_positive")
    return flux, math.hypot(err_wing, err_bg), flags


def _ring_pixels(annulus: tuple[float, float]) -> float:
    return math.pi * (annulus[1] ** 2 - annulus[0] ** 2)


def _quality(flags: set[str], wavelength: float | None, has_flags: bool) -> str | None:
    if not has_flags:
        return "no_flags"
    for reason in EXCLUDE_ORDER:
        if reason in flags:
            return reason
    if wavelength is None:
        return "no_wavelength"
    return None


def _to_mjy(img) -> float:
    return photometry.pixel_solid_angle_sr(img.header) * photometry.MJY_PER_MJY


# --- comparison stars ----------------------------------------------------------------------------------------


def find_field_stars(
    pl: photometry.Planes,
    exclude: tuple[float, float] | None = None,
    *,
    snr: float = COMPARISON_SNR,
    min_sep_px: float = COMPARISON_MIN_SEP_PX["aperture"],
    margin_px: int | None = None,
) -> list[tuple[int, int, float]]:
    """(x, y, snr) of bright, unsaturated, isolated stars on one stamp, brightest first.

    A local maximum (7 x 7) at least ``snr`` robust sigmas above the stamp median, ``margin_px`` from the stamp edge
    (default: the aperture method's sky annulus + 2 px), ``min_sep_px`` from ``exclude`` (the target), with no
    DEFAULT_BAD pixel (OVERFLOW included) within the r = 3 px aperture, and nothing brighter than 20 % of the
    peak 3-7 px away. Looser than WS2's ``find_correction_stars`` (no flag at all in 13 x 13 px), which keeps
    almost no star in crowded or busy fields: each comparison is still checked per exposure like the target.
    """
    data, flags_plane = pl.data, pl.flags
    if not np.isfinite(pl.median) or not pl.sigma:
        return []
    margin = int(margin_px if margin_px is not None else math.ceil(APERTURE_ANNULUS_PX[1]) + 2)
    ny, nx = data.shape
    out: list[tuple[int, int, float]] = []
    yy, xx = np.mgrid[-7:8, -7:8]
    rr = np.hypot(xx, yy)
    core = rr <= APERTURE_PX
    ring = (rr > 3) & (rr <= 7)
    for y, x in np.argwhere(np.nan_to_num(data - pl.median) >= snr * pl.sigma):
        if not (margin <= x < nx - margin and margin <= y < ny - margin and 7 <= x < nx - 7 and 7 <= y < ny - 7):
            continue
        if exclude is not None and math.hypot(x - exclude[0], y - exclude[1]) < min_sep_px:
            continue
        box = data[y - 3 : y + 4, x - 3 : x + 4]
        if not np.isfinite(box).all() or data[y, x] < box.max():
            continue
        win = data[y - 7 : y + 8, x - 7 : x + 8]
        if (flags_plane[y - 7 : y + 8, x - 7 : x + 8][core] & BAD).any():
            continue
        peak = data[y, x] - pl.median
        if np.nanmax(np.where(ring, win, -np.inf)) - pl.median > 0.2 * peak:
            continue
        if any(abs(x - ox) <= 2 and abs(y - oy) <= 2 for ox, oy, _ in out):
            continue
        out.append((int(x), int(y), float(peak / pl.sigma)))
    out.sort(key=lambda s: -s[2])
    return out


def find_comparison_stars(
    exposures: Sequence[Exposure],
    ra: float,
    dec: float,
    *,
    max_stars: int = N_COMPARISON,
    refs_per_detector: int = COMPARISON_REFS_PER_DETECTOR,
    min_sep_px: float = COMPARISON_MIN_SEP_PX["aperture"],
    min_found: int = COMPARISON_MIN_FOUND,
    planes_cache: dict | None = None,
) -> list[tuple[float, float, int]]:
    """(ra, dec, times found) of field stars (:func:`find_field_stars`) merged on the sky over a few exposures
    per detector, spread in time, kept when found in at least ``min_found`` of them (or in every one, when fewer
    were looked at). Stars found in more exposures come first, then brighter ones."""
    by_det: dict[int, list[Exposure]] = defaultdict(list)
    for e in exposures:
        by_det[int(e.image.detector)].append(e)
    clusters: list[dict] = []  # ra, dec (running mean), n, snr
    n_refs = 0
    match_deg = COMPARISON_MATCH_PX * PIXEL_ARCSEC / 3600.0
    cosd = math.cos(math.radians(dec))
    for det in sorted(by_det):
        exps = sorted(by_det[det], key=lambda e: e.image.mjd)
        idx = sorted({round(v) for v in np.linspace(0, len(exps) - 1, min(refs_per_detector, len(exps)))})
        for i in idx:
            e = exps[i]
            if e.image.flags is None:
                continue
            pl = _planes(e, planes_cache)
            n_refs += 1
            xt, yt = sky_to_pixel(e.image, ra, dec)
            exclude = (float(xt[0]), float(yt[0])) if np.isfinite(xt[0]) else None
            peaks = find_field_stars(pl, exclude=exclude, min_sep_px=min_sep_px)[: 3 * max_stars]
            if not peaks:
                continue
            px = np.array([p[0] for p in peaks], float)
            py = np.array([p[1] for p in peaks], float)
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                sra, sdec = e.image.wcs.all_pix2world(px, py, 0)
            snr = [p[2] for p in peaks]
            for r_, d_, s_ in zip(np.atleast_1d(sra), np.atleast_1d(sdec), snr, strict=True):
                for c in clusters:
                    if math.hypot((r_ - c["ra"]) * cosd, d_ - c["dec"]) < match_deg:
                        c["ra"] += (r_ - c["ra"]) / (c["n"] + 1)
                        c["dec"] += (d_ - c["dec"]) / (c["n"] + 1)
                        c["n"] += 1
                        c["snr"] = max(c["snr"], float(s_))
                        break
                else:
                    clusters.append({"ra": float(r_), "dec": float(d_), "n": 1, "snr": float(s_)})
    min_sep_deg = min_sep_px * PIXEL_ARCSEC / 3600.0
    need = min(min_found, n_refs)
    keep = [c for c in clusters if c["n"] >= need and math.hypot((c["ra"] - ra) * cosd, c["dec"] - dec) >= min_sep_deg]
    keep.sort(key=lambda c: (-c["n"], -c["snr"]))
    return [(c["ra"] % 360.0, c["dec"], c["n"]) for c in keep[:max_stars]]


def _planes(e: Exposure, cache: dict | None) -> photometry.Planes:
    if cache is None:
        return photometry.planes(e.image)
    key = id(e)
    if key not in cache:
        cache[key] = photometry.planes(e.image)
    return cache[key]


# --- binning -------------------------------------------------------------------------------------------------


def wavelength_bins(wavelengths: Sequence[float], frac: float = LAMBDA_BIN_FRAC) -> list[int]:
    """Bin label of each wavelength: sorted greedily, a bin holds wavelengths within ``(1 + frac)`` of its first.

    Two wavelengths less than ``frac`` apart can still land in neighbouring bins (fixed edges):
    :func:`matched_pairs` compares exposures pairwise instead. The width is a compromise, not corrected for (WS3
    review LC28): with 1 % the spectral slope inside a bin still adds scatter where the spectrum is steep (R Dra D1:
    ~0.14 of its 0.29 mag residual), and in D5/D6 1 % is wider than the linear-variable-filter channel.
    """
    if not frac > 0:
        raise ValueError(f"lambda_bin_frac must be > 0, got {frac}")
    lam = np.asarray(wavelengths, float)
    labels = [-1] * lam.size
    current, start = -1, None
    for i in np.argsort(lam, kind="stable"):
        if start is None or lam[i] > start * (1.0 + frac):
            current += 1
            start = lam[i]
        labels[int(i)] = current
    return labels


def _relative(
    items: list[dict], frac: float, min_span_days: float
) -> tuple[list[tuple[int, list[int], float]], dict[int, str]]:
    """Bins of usable items (``flux`` > 0 and ``excluded`` None) per detector.

    Returns [(detector, item indices, mean magnitude)] for the kept bins and {item index: 'lone_bin'|'short_bin'}.
    Each item gets ``rel_mag``/``rel_mag_err`` when its bin is kept.
    """
    by_det: dict[int, list[int]] = defaultdict(list)
    for i, it in enumerate(items):
        if it["excluded"] is None:
            by_det[it["detector"]].append(i)
    kept, dropped = [], {}
    for det in sorted(by_det):
        idx = by_det[det]
        labels = wavelength_bins([items[i]["wavelength_um"] for i in idx], frac)
        groups: dict[int, list[int]] = defaultdict(list)
        for i, lab in zip(idx, labels, strict=True):
            groups[lab].append(i)
        for lab in sorted(groups):
            members = sorted(groups[lab], key=lambda i: items[i]["mjd"])
            if len(members) < 2:
                dropped.update(dict.fromkeys(members, "lone_bin"))
                continue
            mjds = [items[i]["mjd"] for i in members]
            if max(mjds) - min(mjds) < min_span_days:
                dropped.update(dict.fromkeys(members, "short_bin"))
                continue
            mags = np.array([-MAG * math.log(items[i]["flux"]) for i in members])
            mean = float(mags.mean())
            for i, m in zip(members, mags, strict=True):
                items[i]["rel_mag"] = float(m - mean)
                err = items[i]["flux_err"]
                items[i]["rel_mag_err"] = (
                    MAG * err / items[i]["flux"] if err is not None and math.isfinite(err) else None
                )
            kept.append((det, members, mean))
    return kept, dropped


def _robust(values: Sequence[float]) -> dict:
    v = np.asarray([x for x in values if x is not None and math.isfinite(x)], float)
    if v.size == 0:
        return {"n": 0}
    med = float(np.median(v))
    return {
        "n": int(v.size),
        "median_mag": med,
        "robust_sigma_mag": float(1.4826 * np.median(np.abs(v - med))),
        "p95_abs_mag": float(np.percentile(np.abs(v - med), 95)),
        "max_abs_mag": float(np.max(np.abs(v - med))),
        "p5_to_p95_mag": float(np.percentile(v, 95) - np.percentile(v, 5)),
    }


# --- the light curve -----------------------------------------------------------------------------------------


def light_curve_from_exposures(
    exposures: Sequence[Exposure],
    ra: float,
    dec: float,
    *,
    method: str = "aperture",
    lambda_bin_frac: float = LAMBDA_BIN_FRAC,
    min_bin_span_days: float = MIN_BIN_SPAN_DAYS,
    n_comparison: int = N_COMPARISON,
    period: bool | None = None,
    period_range_days: tuple[float, float] = PERIOD_RANGE_DAYS,
    n_bootstrap: int = 0,
    n_permutations: int = N_PERMUTATIONS,
    comparison_stars: Sequence[tuple[float, float]] | None = None,
) -> LightCurve:
    """Measure the target (and the comparison stars) on every exposure and build the binned light curve.

    ``comparison_stars`` (ra, dec) overrides the automatic choice (``n_comparison = 0`` disables them).
    ``period``: None = estimate when there are >= 30 points over >= 2 x the shortest period tried; the estimate is
    tested with ``n_permutations`` visit permutations and labelled ``significant`` or not, unless its best period is
    at the edge of the grid or covers < 1.5 cycles (then untested; see :func:`estimate_period` and the notes).
    The notes also carry what the contract has no field for: the comparisons' matched-pair scatter, the amplitude
    errors and, when it changes between seasons, the saturated fraction per season.
    """
    if method not in METHODS:
        raise ValueError(f"method must be one of {METHODS}, got {method!r}")
    if not lambda_bin_frac > 0:
        raise ValueError(f"lambda_bin_frac must be > 0, got {lambda_bin_frac}")
    exps = sorted(exposures, key=lambda e: (e.image.mjd, e.image.detector, e.frame_id))
    season_of: dict[int, int] = {}
    for k, group in enumerate(group_seasons(exps, SEASON_GAP_DAYS) if exps else []):
        for e in group:
            season_of[id(e)] = k
    cache: dict = {}
    measure: Callable = aperture_measure if method == "aperture" else wing_measure

    items: list[dict] = []
    for e in exps:
        img = e.image
        pl = _planes(e, cache)
        x, y = sky_to_pixel(img, ra, dec)
        flux, err, flags = measure(pl, float(x[0]), float(y[0]))
        has_flags = img.flags is not None
        reason = _quality(flags, e.wavelength_um, has_flags)
        scale = _to_mjy(img) if method == "aperture" else 1.0
        ok = math.isfinite(flux)
        if reason is None and not (ok and flux > 0):
            reason = "non_positive"
        items.append(
            {
                "e": e,
                "detector": int(img.detector),
                "mjd": float(img.mjd),
                "wavelength_um": e.wavelength_um,
                "flux": flux * scale if ok else None,
                "flux_err": err * scale if ok and math.isfinite(err) else None,
                "flags": tuple(sorted(flags)),
                "excluded": reason,
                "rel_mag": None,
                "rel_mag_err": None,
            }
        )
    kept, dropped = _relative(items, lambda_bin_frac, min_bin_span_days)
    for i, why in dropped.items():
        items[i]["excluded"] = why

    # comparison stars, measured with the aperture method in the same exposures, binned at their own wavelength
    if comparison_stars is None:
        found = (
            find_comparison_stars(
                exps, ra, dec, max_stars=n_comparison, min_sep_px=COMPARISON_MIN_SEP_PX[method], planes_cache=cache
            )
            if n_comparison
            else []
        )
    else:
        found = [(float(r), float(d), 0) for r, d in comparison_stars]
    comparisons: list[ComparisonStar] = []
    comp_items: list[list[dict]] = []
    for k, (cra, cdec, n_found) in enumerate(found):
        star = ComparisonStar(id=f"C{k + 1}", ra=cra, dec=cdec, found_in=n_found)
        rows = []
        for e in exps:
            img = e.image
            x, y = sky_to_pixel(img, cra, cdec)
            flux, err, flags = aperture_measure(_planes(e, cache), float(x[0]), float(y[0]))
            wave = img.wavelength_at(cra, cdec)  # None without a WCS-WAVE table or off the array
            lam = wave[0] if wave else None
            reason = _quality(flags, lam, img.flags is not None)
            scale = _to_mjy(img)
            ok = math.isfinite(flux)
            rows.append(
                {
                    "frame_id": e.frame_id,
                    "detector": int(img.detector),
                    "mjd": float(img.mjd),
                    "wavelength_um": lam,
                    "flux": flux * scale if ok else None,
                    "flux_err": err * scale if ok and math.isfinite(err) else None,
                    "excluded": reason if reason or (ok and flux > 0) else "non_positive",
                    "rel_mag": None,
                    "rel_mag_err": None,
                }
            )
        ckept, cdropped = _relative(rows, lambda_bin_frac, min_bin_span_days)
        for _det, members, _mean in ckept:
            if len(members) < 3:  # same rule as the target's scatter summary (LC24): one difference, not two samples
                for i in members:
                    rows[i]["two_point_bin"] = True
        for i, why in cdropped.items():
            rows[i]["excluded"] = why
        for r in rows:
            star.frame_ids.append(r["frame_id"])
            star.detectors.append(r["detector"])
            star.wavelength_um.append(r["wavelength_um"])
            star.flux_mjy.append(r["flux"])
            star.flux_err_mjy.append(r["flux_err"])
            star.rel_mag.append(r["rel_mag"])
            star.excluded.append(r["excluded"])
        comparisons.append(star)
        comp_items.append(rows)

    # per-exposure zero point from >= 2 comparisons
    zp_by_frame: dict[str, float] = {}
    for j, e in enumerate(exps):
        vals = [rows[j]["rel_mag"] for rows in comp_items if rows[j]["rel_mag"] is not None]
        if len(vals) >= 2:
            zp_by_frame[e.frame_id] = float(np.median(vals))

    bins: list[WavelengthBin] = []
    bin_of: dict[int, int] = {}
    for det, members, mean in kept:
        lam = [items[i]["wavelength_um"] for i in members]
        mjds = [items[i]["mjd"] for i in members]
        b = WavelengthBin(len(bins), det, min(lam), max(lam), len(members), min(mjds), max(mjds), mean)
        for i in members:
            bin_of[i] = b.index
        bins.append(b)

    points = []
    for i, it in enumerate(items):
        e = it["e"]
        points.append(
            LightCurvePoint(
                frame_id=e.frame_id,
                obs_id=str(e.image.obs_id),
                detector=it["detector"],
                release=e.release,
                mjd=it["mjd"],
                date=mjd_to_iso(it["mjd"]),
                season=season_of.get(id(e), 0),
                wavelength_um=e.wavelength_um,
                bandwidth_um=e.bandwidth_um,
                flux=it["flux"],
                flux_err=it["flux_err"],
                bin=bin_of.get(i),
                rel_mag=it["rel_mag"],
                rel_mag_err=it["rel_mag_err"],
                zero_point_mag=zp_by_frame.get(e.frame_id),
                flags=it["flags"],
                excluded=it["excluded"],
            )
        )

    excluded = dict(Counter(p.excluded for p in points if p.excluded))
    control: dict[int, dict] = {}
    for det in sorted({p.detector for p in points}):
        rows_det = [r for rows in comp_items for r in rows if r["detector"] == det]
        stats = _robust([r["rel_mag"] for r in rows_det if not r.get("two_point_bin")])
        stats["n_stars"] = sum(
            any(r["detector"] == det and r["rel_mag"] is not None for r in rows) for rows in comp_items
        )
        stats["excluded"] = dict(Counter(r["excluded"] for r in rows_det if r["excluded"]))  # comparison measurements
        control[det] = stats
    summary: dict[int, dict] = {}
    for det in sorted({p.detector for p in points}):
        mine = [p for p in points if p.detector == det]
        # A two-point bin forces +/- half of ONE difference: two correlated endpoints are not
        # an exposure-scatter estimate (LC24). Keep both for playback and matched-pair analysis.
        scatter_bins = {b.index for b in bins if b.detector == det and b.n_points >= 3}
        stats = _robust([p.rel_mag for p in mine if p.rel_mag is not None and p.bin in scatter_bins])
        stats["n_exposures"] = len(mine)
        stats["n_bins"] = sum(1 for b in bins if b.detector == det)
        stats["excluded"] = dict(Counter(p.excluded for p in mine if p.excluded))
        floor = control.get(det, {}).get("robust_sigma_mag")
        stats["scatter_over_control"] = None
        if method == "wing":  # wing scatter over aperture scatter: not a defined ratio (WS3 review LC24)
            stats["scatter_over_control"] = None
        elif floor and stats.get("robust_sigma_mag") is not None:
            stats["scatter_over_control"] = stats["robust_sigma_mag"] / floor if floor > 0 else None
        summary[det] = stats

    lc = LightCurve(
        ra=float(ra),
        dec=float(dec),
        method=method,
        unit=UNITS[method],
        lambda_bin_frac=lambda_bin_frac,
        min_bin_span_days=min_bin_span_days,
        points=points,
        bins=bins,
        comparisons=comparisons,
        control=control,
        summary=summary,
        excluded=excluded,
    )
    lc.notes = _notes(lc)
    used = lc.used()
    if used:
        baseline = max(p.mjd for p in used) - min(p.mjd for p in used)
        auto = len(used) >= MIN_PERIOD_POINTS and baseline >= 2 * period_range_days[0]
        if period or (period is None and auto):
            lc.period = estimate_period(
                lc, period_range_days=period_range_days, n_bootstrap=n_bootstrap, n_permutations=n_permutations
            )
            if lc.period is not None:
                lc.notes.append(period_note(lc.period))
    return lc


def period_note(pe: PeriodEstimate) -> str:
    """One line for the notes and the CLI: what the permutation test says, the best period as a candidate only, and
    the fitted amplitudes with their 1 sigma errors (the contract has no field for those)."""
    amps = ", ".join(
        f"D{d} {a:.2f}" + (f"±{pe.amplitude_err_mag[d]:.2f}" if d in pe.amplitude_err_mag else "")
        for d, a in sorted(pe.amplitude_mag.items())
    )
    amps = (
        f" Fitted peak-to-peak amplitudes (mag, 1 sigma from the fit covariance at that period): {amps}."
        if amps
        else ""
    )
    if pe.significant:
        return (
            f"Significant time-correlated variability; best period {pe.period_days:.1f} d. Visit-permutation "
            f"false-alarm probability {false_alarm_text(pe)}. A candidate period from a quick sinusoid fit, not a "
            f"confirmed one: check the aliases, the caveat and catalog periods.{amps}"
        )
    if pe.significant is False:
        n = pe.n_permutations
        min_n = math.ceil(1.0 / PERIOD_FALSE_ALARM) - 1  # 99: the fewest permutations whose 1/(n+1) can pass
        if n < min_n and _exceedances(pe) == 0:  # not beaten by any permutation, but too few of them to pass
            return (
                f"No significant period: {n} visit permutations cannot reach a false-alarm probability <= "
                f"{PERIOD_FALSE_ALARM:.0%} (the smallest value they can give is 1/{n + 1}; at least {min_n} are "
                f"needed), although none of them reached the peak of the best sinusoid ({pe.period_days:.1f} d). "
                f"Untested in practice: do not quote it as a period.{amps}"
            )
        few = f", which needs at least {min_n} permutations" if n < min_n else ""
        return (
            f"No significant period: the best sinusoid ({pe.period_days:.1f} d) is matched by shuffled visit epochs. "
            f"Visit-permutation false-alarm probability {false_alarm_text(pe)}; significant needs <= "
            f"{PERIOD_FALSE_ALARM:.0%}{few}. Do not quote it as a period.{amps}"
        )
    why = pe.untested_reason or "no permutations run"
    return f"Best sinusoid {pe.period_days:.1f} d, NOT tested for significance ({why}): not a period.{amps}"


def _exceedances(pe: PeriodEstimate) -> int:
    """k, the permutations that reached the observed peak, back from false_alarm = (1 + k) / (1 + n)."""
    return max(int(round(pe.false_alarm * (pe.n_permutations + 1))) - 1, 0)


def false_alarm_text(pe: PeriodEstimate) -> str:
    """The permutation result with its counts. When no permutation reached the peak, (1 + 0) / (1 + n) = 1/(n+1) is
    the smallest value n permutations can give: not a measured probability, nor an upper bound on it."""
    if pe.false_alarm is None or pe.n_permutations <= 0:
        return "not tested"
    n = pe.n_permutations
    k = _exceedances(pe)
    if k == 0:
        return f"1/{n + 1} (0 of {n} permutations reached the peak; the smallest value {n} permutations can give)"
    return f"{pe.false_alarm:.3f} ({k} of {n} permutations reached the peak)"


def _saturation_by_season(lc: LightCurve) -> dict[int, tuple[int, int]]:
    """Season -> (saturated exposures, exposures), for seasons with >= SATURATION_SEASON_MIN exposures."""
    counts: dict[int, list[int]] = defaultdict(lambda: [0, 0])
    for p in lc.points:
        counts[p.season][0] += p.excluded == "saturated"
        counts[p.season][1] += 1
    return {s: (a, n) for s, (a, n) in sorted(counts.items()) if n >= SATURATION_SEASON_MIN}


def _notes(lc: LightCurve) -> list[str]:
    n_used = len(lc.used())
    notes = [
        f"{n_used} of {len(lc.points)} exposures in the light curve ({lc.method} method, {len(lc.bins)} wavelength bins "
        f"of {lc.lambda_bin_frac:.1%} per detector, bins spanning >= {lc.min_bin_span_days:g} d).",
        "Relative magnitudes: each point against the mean magnitude of its own detector and wavelength bin; the same "
        "detector does not mean the same wavelength (linear variable filter).",
    ]
    n_two = sum(b.n_points for b in lc.bins if b.n_points == 2)
    if n_two:
        notes.append(
            f"Scatter summaries exclude {n_two} endpoints in two-exposure wavelength bins: each pair is only one "
            "independent difference (the comparison-star control uses the same rule). These exposures remain in the "
            "curve and matched-pair analysis."
            + (
                " Use the comparison-star matched-pair scatter as the aperture-pair noise floor."
                if lc.method == "aperture" and lc.comparisons
                else ""
            )
        )
    if lc.excluded:
        notes.append("Excluded exposures: " + ", ".join(f"{k} {v}" for k, v in sorted(lc.excluded.items())) + ".")
    sat = lc.excluded.get("saturated", 0)
    if lc.method == "aperture" and sat:
        notes.append(
            f"{sat} exposures are saturated (OVERFLOW in the aperture: lower limits) and excluded; for a star saturated "
            "everywhere use method='wing' (relative brightness of the unsaturated PSF wing)."
        )
    seasons = _saturation_by_season(lc)
    frac = [a / n for a, n in seasons.values()]
    if sat and len(frac) >= 2 and max(frac) - min(frac) >= SATURATION_SEASON_RANGE:
        notes.append(
            "Saturated exposures by season: "
            + ", ".join(f"S{s} {a}/{n}" for s, (a, n) in seasons.items())
            + ". The saturated fraction changes strongly between seasons, so bright states may be preferentially "
            "excluded: the light curve under-represents the brightest epochs."
        )
    if lc.method == "wing":
        n_core = sum(1 for p in lc.points if "saturated_core" in p.flags)
        notes.append(
            f"Wing photometry ({WING_ANNULUS_PX[0]:g}-{WING_ANNULUS_PX[1]:g} px minus {WING_BACKGROUND_PX[0]:g}-"
            f"{WING_BACKGROUND_PX[1]:g} px, MJy/sr): RELATIVE brightness only; {n_core} exposures have a saturated core."
        )
    if lc.comparisons:
        ctl = ", ".join(
            f"D{d} {c['robust_sigma_mag']:.3f}" for d, c in sorted(lc.control.items()) if c.get("robust_sigma_mag")
        )
        notes.append(
            f"Control: {len(lc.comparisons)} comparison stars measured with the aperture method in the same exposures; "
            f"robust scatter (mag) {ctl or 'not measurable'}."
        )
        pairs = ", ".join(
            f"D{d} {s['robust_sigma_mag']:.3f} mag ({s['n']} pairs)"
            for d, s in comparison_pair_scatter(lc).items()
            if s["n"] >= 2
        )
        rule = f"same detector, |dlambda|/lambda < {lc.lambda_bin_frac:.1%}, >= {MIN_PAIR_DT_DAYS:g} d apart"
        if lc.method == "wing":  # aperture pairs of the comparisons say nothing about the wing's own floor (LC26)
            notes.append(
                f"Comparison-star matched-pair scatter (their own aperture pairs: {rule}): "
                f"{pairs or 'no comparison pairs'}. It is NOT the floor of the target's wing pairs: wing photometry "
                "has its own, separate per-exposure floor (the period's floor_mag when a period is fitted)."
            )
        else:
            notes.append(
                f"Comparison-star matched-pair scatter (the empirical floor for the target's matched-wavelength pairs: "
                f"{rule}): {pairs or 'no comparison pairs'}."
            )
        if lc.method == "wing":
            notes.append(
                "scatter_over_control is not given for wing photometry: the comparison stars are measured with "
                "aperture photometry, so the ratio of the target's wing scatter to theirs is not defined."
            )
    else:
        notes.append("No comparison star available: the systematic floor of this light curve is not measured.")
    return notes


# --- matched pairs (the RW Aurigae method) -------------------------------------------------------------------


def _matched(lam_a: float, lam_b: float, frac: float) -> bool:
    """|dlambda| / mean lambda < frac."""
    return abs(lam_b - lam_a) / (0.5 * (lam_a + lam_b)) < frac


def _usable(why: str | None, flux: float | None, lam: float | None) -> bool:
    """Passed the quality cuts (bin drops allowed: pairs do not need a bin), positive flux, known wavelength."""
    return (why is None or why in BIN_REASONS) and flux is not None and flux > 0 and lam is not None


def matched_pairs(
    lc: LightCurve, *, max_frac: float = LAMBDA_BIN_FRAC, min_dt_days: float = MIN_PAIR_DT_DAYS
) -> list[dict]:
    """Same-detector exposure pairs at matched wavelength (|dlambda|/lambda < ``max_frac``) at least ``min_dt_days``
    apart, from every point that passed the quality cuts (whatever its bin). ``delta_mag`` = later - earlier
    (negative = brighter later); ``delta_mag_err`` is statistical only. With the ``aperture`` method the floor for a
    pair is the comparisons' own matched-pair scatter (:func:`comparison_pair_scatter`, in the notes); with ``wing``
    it is not (aperture comparisons): the wing has its own floor (R Dra: ``floor_mag`` 0.35-0.40 mag per exposure in
    D1-D3 against 0.03-0.04 mag for the comparisons' pairs; comparable in D5/D6, where the comparisons are faint).

    ``ensemble_mag`` is the median change of the comparison stars measured in the SAME two exposures whose own two
    wavelengths also match (|dlambda|/lambda < ``max_frac``; ``n_ensemble`` stars, None when none qualifies): a
    comparison sits elsewhere on the linear variable filter, so the target's match does not make its match (WS3 review
    LC28: median 0.5-0.9 %, up to 2.3 %, before this cut). ``delta_mag_corrected`` = ``delta_mag`` - ``ensemble_mag``.
    Limits of the 1 % match itself (LC28, not corrected): wide where the spectrum is steep (R Dra D1) and wider than
    the linear-variable-filter channel in D5/D6.
    """
    pts = [p for p in lc.points if _usable(p.excluded, p.flux, p.wavelength_um)]
    comp = [
        {
            fid: (f, lam)
            for fid, f, lam, why in zip(c.frame_ids, c.flux_mjy, c.wavelength_um, c.excluded, strict=True)
            if _usable(why, f, lam)
        }
        for c in lc.comparisons
    ]
    out = []
    by_det: dict[int, list[LightCurvePoint]] = defaultdict(list)
    for p in pts:
        by_det[p.detector].append(p)
    for det in sorted(by_det):
        mine = sorted(by_det[det], key=lambda p: p.mjd)
        for i, a in enumerate(mine):
            for b in mine[i + 1 :]:
                if b.mjd - a.mjd < min_dt_days or not _matched(a.wavelength_um, b.wavelength_um, max_frac):
                    continue
                dm = -MAG * math.log(b.flux / a.flux)
                err = None
                if a.flux_err is not None and b.flux_err is not None:
                    err = MAG * math.hypot(a.flux_err / a.flux, b.flux_err / b.flux)
                ens = [
                    -MAG * math.log(c[b.frame_id][0] / c[a.frame_id][0])
                    for c in comp
                    if a.frame_id in c and b.frame_id in c and _matched(c[a.frame_id][1], c[b.frame_id][1], max_frac)
                ]
                ens_mag = float(np.median(ens)) if ens else None
                out.append(
                    {
                        "detector": det,
                        "frame_a": a.frame_id,
                        "frame_b": b.frame_id,
                        "mjd_a": a.mjd,
                        "mjd_b": b.mjd,
                        "date_a": a.date,
                        "date_b": b.date,
                        "season_a": a.season,
                        "season_b": b.season,
                        "wavelength_a_um": a.wavelength_um,
                        "wavelength_b_um": b.wavelength_um,
                        "delta_mag": dm,
                        "delta_mag_err": err,
                        "ensemble_mag": ens_mag,
                        "n_ensemble": len(ens),
                        "delta_mag_corrected": dm - ens_mag if ens_mag is not None else None,
                    }
                )
    return out


def comparison_pair_scatter(
    lc: LightCurve, *, max_frac: float | None = None, min_dt_days: float = MIN_PAIR_DT_DAYS
) -> dict[int, dict]:
    """Per detector, robust statistics (:func:`_robust`, ``n`` = pairs) of the comparison stars' OWN matched-pair
    changes, with :func:`matched_pairs`' criteria: same star and detector, |dlambda|/lambda < ``max_frac`` (default
    ``lc.lambda_bin_frac``) at the star's own wavelength, >= ``min_dt_days`` apart; ``delta`` = later - earlier.

    For the ``aperture`` method this, not the per-point ``control``, is the empirical floor of a target pair: on the
    real products it is 1.4-1.9x the per-point control (RW Aur D1: 0.033 against 0.018 mag; WS3 review LC26). It is
    NOT the floor of ``wing`` pairs: the comparisons are always aperture measurements, and the wing has its own floor
    (R Dra D1: ``floor_mag`` 0.35 mag per exposure against 0.030 mag here)."""
    frac = lc.lambda_bin_frac if max_frac is None else max_frac
    mjd = {p.frame_id: p.mjd for p in lc.points}
    deltas: dict[int, list[float]] = defaultdict(list)
    for c in lc.comparisons:
        by_det: dict[int, list[tuple[float, float, float]]] = defaultdict(list)
        for fid, det, lam, f, why in zip(
            c.frame_ids, c.detectors, c.wavelength_um, c.flux_mjy, c.excluded, strict=True
        ):
            if fid in mjd and _usable(why, f, lam):
                by_det[int(det)].append((mjd[fid], lam, f))
        for det, ms in by_det.items():
            ms.sort()
            for i, (ta, la, fa) in enumerate(ms):
                for tb, lb, fb in ms[i + 1 :]:
                    if tb - ta >= min_dt_days and _matched(la, lb, frac):
                        deltas[det].append(-MAG * math.log(fb / fa))
    return {d: _robust(deltas[d]) for d in sorted(deltas)}


# --- period --------------------------------------------------------------------------------------------------


def _fit_grid(t, y, w, bins, dets, freqs, chunk: int = 256, normal: bool = False):
    """Delta chi2 of per-detector sinusoids after per-bin offsets, for every frequency (Frisch-Waugh-Lovell:
    residualise against bin means, then a 2x2 solve per detector). Returns (dchi2[nf], coefficients[nf, ndet, 2]),
    plus with ``normal`` the 2x2 normal matrices (a11, a12, a22)[nf, ndet], whose inverse is the coefficients'
    covariance (bins never span detectors, so the per-detector blocks are exact).
    Vectorised over frequencies in chunks of ``chunk`` (memory ~ chunk x points)."""
    n = len(t)
    nb = int(bins.max()) + 1
    member = np.zeros((n, nb))
    member[np.arange(n), bins] = 1.0
    wsum = member.T @ w
    udets, det_idx = np.unique(dets, return_inverse=True)
    det_member = np.zeros((n, len(udets)))
    det_member[np.arange(n), det_idx] = 1.0

    def resid(v):  # v: (..., n) minus its weighted mean per bin
        return v - ((v * w) @ member / wsum)[..., bins]

    yr = resid(y)
    freqs = np.asarray(freqs, float)
    dchi2 = np.zeros(len(freqs))
    coef = np.zeros((len(freqs), len(udets), 2))
    mats = np.zeros((3, len(freqs), len(udets)))
    for lo in range(0, len(freqs), chunk):
        f = freqs[lo : lo + chunk]
        ph = 2.0 * math.pi * f[:, None] * t[None, :]
        s, c = resid(np.sin(ph)), resid(np.cos(ph))
        ws, wc = w * s, w * c
        a11, a12, a22 = (ws * s) @ det_member, (ws * c) @ det_member, (wc * c) @ det_member
        b1, b2 = (ws * yr) @ det_member, (wc * yr) @ det_member
        det = a11 * a22 - a12 * a12
        ok = det > 1e-12 * np.maximum(a11 * a22, 1e-300)
        safe = np.where(ok, det, 1.0)
        p = np.where(ok, (a22 * b1 - a12 * b2) / safe, 0.0)
        q = np.where(ok, (a11 * b2 - a12 * b1) / safe, 0.0)
        dchi2[lo : lo + len(f)] = np.sum(p * b1 + q * b2, axis=1)
        coef[lo : lo + len(f), :, 0], coef[lo : lo + len(f), :, 1] = p, q
        mats[:, lo : lo + len(f)] = a11, a12, a22
    if normal:
        return dchi2, coef, mats
    return dchi2, coef


def _amplitudes(udets, coef, mats) -> tuple[dict[int, float], dict[int, float]]:
    """Peak-to-peak amplitude 2 sqrt(p^2 + q^2) per detector and its 1 sigma error, propagated from the covariance
    of (p, q) = inverse 2x2 normal matrix (the weights include the floors, so chi2/dof = 1: no rescaling)."""
    amp, err = {}, {}
    for j, d in enumerate(udets):
        p, q = (float(v) for v in coef[j])
        a11, a12, a22 = (float(m[j]) for m in mats)
        r = math.hypot(p, q)
        amp[int(d)] = 2.0 * r
        det = a11 * a22 - a12 * a12
        if r > 0 and det > 0:
            var = (p * p * a22 - 2.0 * p * q * a12 + q * q * a11) / det / (r * r)
            err[int(d)] = 2.0 * math.sqrt(max(var, 0.0))
    return amp, err


def _permutation_false_alarm(t, y, w, bins, dets, freqs, observed: float, n: int, rng) -> float:
    """Visit-permutation false-alarm probability of the highest grid peak (the R Dra record's significance test):
    every visit keeps its points and their internal time offsets but takes the epoch of another visit, the grid is
    refitted and its highest delta chi2 compared with the observed one. (1 + exceedances) / (1 + n); the weights stay
    those of the observed fit."""
    visits = _visit_groups(t)
    starts = np.array([t[v].min() for v in visits])
    exceed = 0
    for _ in range(n):
        perm = rng.permutation(len(visits))
        tp = np.empty_like(t)
        for i, v in enumerate(visits):
            tp[v] = t[v] - starts[i] + starts[perm[i]]
        d, _ = _fit_grid(tp, y, w, bins, dets, freqs)
        exceed += bool(d.max() >= observed)
    return (1 + exceed) / (1 + n)


def _floors(t, y, sig, bins, dets, f) -> dict[int, float]:
    """Per-detector floor (mag) such that chi2/dof = 1 for bin offsets + the sinusoid at frequency f."""
    floors: dict[int, float] = {}
    out = dict.fromkeys(np.unique(dets).tolist(), 0.0)
    for _ in range(3):  # the fit depends on the weights: iterate a few times
        w = 1.0 / (sig**2 + np.array([out[d] for d in dets]) ** 2)
        _, coef = _fit_grid(t, y, w, bins, dets, np.array([f]))
        model = np.zeros_like(y)
        for j, d in enumerate(np.unique(dets)):
            m = dets == d
            model[m] = coef[0, j, 0] * np.sin(2 * math.pi * f * t[m]) + coef[0, j, 1] * np.cos(2 * math.pi * f * t[m])
        r = y - model
        nb = int(bins.max()) + 1
        wsum = np.bincount(bins, weights=w, minlength=nb)
        r = r - (np.bincount(bins, weights=w * r, minlength=nb) / wsum)[bins]
        for d in np.unique(dets):
            m = dets == d
            nbin = len(np.unique(bins[m]))
            dof = max(int(m.sum()) - nbin - 2, 1)
            lo, hi = 0.0, 5.0
            if np.sum(r[m] ** 2 / sig[m] ** 2) / dof <= 1.0:
                floors[int(d)] = 0.0
                continue
            for _ in range(60):  # bisection on the floor
                mid = 0.5 * (lo + hi)
                if np.sum(r[m] ** 2 / (sig[m] ** 2 + mid**2)) / dof > 1.0:
                    lo = mid
                else:
                    hi = mid
            floors[int(d)] = hi
        out = floors
    return out


def estimate_period(
    lc: LightCurve,
    *,
    period_range_days: tuple[float, float] = PERIOD_RANGE_DAYS,
    oversample: int = OVERSAMPLE,
    n_peaks: int = 4,
    n_bootstrap: int = 0,
    n_permutations: int = N_PERMUTATIONS,
    seed: int = 1,
) -> PeriodEstimate | None:
    """Best sinusoid period of the light curve's points (see the module docstring); None with too few points.

    The per-detector floors (chi2/dof = 1) are first evaluated at the statistical-only best period, then again at
    the refined best period until it moves by less than one fine-grid step (at most ``FLOOR_ITERATIONS`` times), so
    the reported floors, amplitudes and delta chi2 refer to the reported period (WS3 review LC27). This can move the
    period within its flat peak: R Dra's went from 259.1 to 261.9 d (delta chi2 0.3 apart; D6's floor fell from
    0.091 to 0.075 mag and D6 alone prefers ~265 d).

    ``n_permutations`` visit permutations give ``false_alarm`` = (1 + k) / (1 + n), k permutations peaking as high
    (how often the same visits, bins and errors with shuffled epochs fit as well), and ``significant`` (<= 1 %; at
    least 99 permutations are needed to reach it). That tests time-correlated variability, not periodicity: a trend
    peaks at the long end of the grid and passes (LC7). So the test is skipped (``false_alarm`` None,
    ``n_permutations`` 0, ``significant`` None, the reason in ``untested_reason``, the caveat and :func:`period_note`)
    when the best period lies within one grid step of either end of ``period_range_days`` or covers fewer than
    ``MIN_PERIOD_CYCLES`` cycles of the baseline; the period stays an untested candidate. Without permutations
    (``n_permutations=0``) ``significant`` is None as well."""
    used = [p for p in lc.used() if p.rel_mag_err is not None and p.rel_mag_err > 0]
    if len(used) < 10:
        return None
    t = np.array([p.mjd for p in used])
    t0 = float(t.min())
    t = t - t0
    y = np.array([p.rel_mag for p in used])
    sig = np.array([p.rel_mag_err for p in used])
    bins = np.unique([p.bin for p in used], return_inverse=True)[1]
    dets = np.array([p.detector for p in used])
    baseline = float(t.max())
    pmin, pmax = period_range_days
    if not (0 < pmin < pmax):
        raise ValueError(f"invalid period range {period_range_days}")
    df = 1.0 / (max(baseline, pmin) * oversample)
    freqs = np.arange(1.0 / pmax, 1.0 / pmin + df, df)

    w = 1.0 / sig**2
    d0, _ = _fit_grid(t, y, w, bins, dets, freqs)
    f_floor = float(freqs[int(np.argmax(d0))])  # statistical-only best: the first guess for the floors
    for _ in range(1 + FLOOR_ITERATIONS):
        floor = _floors(t, y, sig, bins, dets, f_floor)
        w = 1.0 / (sig**2 + np.array([floor[int(d)] for d in dets]) ** 2)
        dchi2, _ = _fit_grid(t, y, w, bins, dets, freqs)
        k = int(np.argmax(dchi2))
        # refine around the peak
        fine = np.linspace(freqs[max(k - 1, 0)], freqs[min(k + 1, len(freqs) - 1)], 201)
        dfine, _ = _fit_grid(t, y, w, bins, dets, fine)
        kb = int(np.argmax(dfine))
        f_best = float(fine[kb])
        settled = abs(f_best - f_floor) <= abs(float(fine[1] - fine[0]))
        f_floor = f_best
        if settled:  # the floors were evaluated at the reported period
            break
    best = float(dfine[kb])
    within = fine[dfine >= best - 1.0]
    err = None
    if within.size >= 2 and 0 < kb < len(fine) - 1:
        err = 0.5 * (1.0 / within.min() - 1.0 / within.max())
    _, coef, mats = _fit_grid(t, y, w, bins, dets, np.array([f_best]), normal=True)
    amp, amp_err = _amplitudes(np.unique(dets), coef[0], mats[:, 0])
    peaks = []
    for i in range(1, len(dchi2) - 1):
        if dchi2[i] >= dchi2[i - 1] and dchi2[i] >= dchi2[i + 1]:
            peaks.append((float(1.0 / freqs[i]), float(dchi2[i])))
    peaks.sort(key=lambda p: -p[1])
    peaks = [(1.0 / f_best, best)] + [p for p in peaks if abs(p[0] - 1.0 / f_best) > 0.02 / f_best][: n_peaks - 1]

    untested = _period_guard(f_best, df, baseline, pmin, pmax)
    fap = None
    if n_permutations > 0 and untested is None:
        rng_perm = np.random.default_rng([seed, 1])
        fap = _permutation_false_alarm(t, y, w, bins, dets, freqs, float(dchi2[k]), n_permutations, rng_perm)

    boot = None
    if n_bootstrap > 0:
        rng = np.random.default_rng(seed)
        visits = _visit_groups(t)
        lo_f, hi_f = f_best * 0.8, f_best * 1.25
        local = freqs[(freqs >= lo_f) & (freqs <= hi_f)]
        local = np.linspace(local.min(), local.max(), 300) if local.size else np.array([f_best])
        best_p = []
        for _ in range(n_bootstrap):
            pick = rng.integers(0, len(visits), len(visits))
            idx = np.concatenate([visits[i] for i in pick])
            bins_b = np.unique(bins[idx], return_inverse=True)[1]
            db, _ = _fit_grid(t[idx], y[idx], w[idx], bins_b, dets[idx], local)
            best_p.append(1.0 / float(local[int(np.argmax(db))]))
        boot = (float(np.percentile(best_p, 2.5)), float(np.percentile(best_p, 97.5)))
    return PeriodEstimate(
        period_days=1.0 / f_best,
        delta_chi2=best,
        period_err_formal_days=err,
        bootstrap_95_days=boot,
        peaks=peaks,
        amplitude_mag=amp,
        floor_mag=floor,
        n_points=len(used),
        baseline_days=baseline,
        period_range_days=(float(pmin), float(pmax)),
        false_alarm=fap,
        n_permutations=max(int(n_permutations), 0) if fap is not None else 0,
        significant=None if fap is None else fap <= PERIOD_FALSE_ALARM,
        caveat=PERIOD_CAVEAT if untested is None else f"Not tested for significance: {untested}. {PERIOD_CAVEAT}",
        untested_reason=untested,
        amplitude_err_mag=amp_err,
    )


def _period_guard(f_best: float, df: float, baseline: float, pmin: float, pmax: float) -> str | None:
    """Why a best period must not be tested (None: it may): within one grid step of either end of the search range,
    or fewer than MIN_PERIOD_CYCLES cycles over the baseline (WS3 review LC7: a 0.6 mag trend on R Dra's sampling
    peaked at the 800 d edge with false alarm 1/101)."""
    reasons = []
    tol = df * (1.0 + 1e-9)
    if f_best - 1.0 / pmax <= tol or 1.0 / pmin - f_best <= tol:
        reasons.append(f"best period at the edge of the {pmin:g}-{pmax:g} d search range")
    if 1.0 / f_best > baseline / MIN_PERIOD_CYCLES:
        reasons.append(
            f"it covers fewer than {MIN_PERIOD_CYCLES:g} cycles of the {baseline:.0f} d baseline: consistent with a "
            "trend or an incomplete cycle, not a measured period"
        )
    return "; ".join(reasons) or None


def _visit_groups(t: np.ndarray, gap_days: float = VISIT_GAP_HOURS / 24.0) -> list[np.ndarray]:
    order = np.argsort(t)
    groups, cur = [], [order[0]]
    for a, b in zip(order[:-1], order[1:], strict=True):
        if t[b] - t[a] > gap_days:
            groups.append(np.array(cur))
            cur = []
        cur.append(b)
    groups.append(np.array(cur))
    return groups


# --- from the archive ----------------------------------------------------------------------------------------


def exposures_from_series(series) -> tuple[list[Exposure], list[dict]]:
    """WS1 ``PointSeries`` samples as :class:`Exposure` (``data.point.to_spherex_image``); failures listed."""
    from ..data.point import to_spherex_image

    out, failures = [], []
    for s in series.samples:
        fid = f"{s.obs_id}D{s.detector}"
        try:
            img = to_spherex_image(s)
        except (OSError, ValueError, KeyError) as e:
            failures.append({"frame_id": fid, "reason": f"{type(e).__name__}: {e}"})
            continue
        out.append(Exposure(img, fid, s.release, s.wavelength_um, s.bandwidth_um))
    return out, failures


def light_curve(
    ra: float,
    dec: float,
    *,
    detectors: Sequence[int] | None = None,
    lambda_bin_frac: float = LAMBDA_BIN_FRAC,
    method: str = "aperture",
    collections: Sequence[str] | str | None = None,
    deadline_s: float | None = None,
    box_px: int | None = None,
    max_frames: int | None = None,
    mjd_min: float | None = None,
    mjd_max: float | None = None,
    min_bin_span_days: float = MIN_BIN_SPAN_DAYS,
    n_comparison: int = N_COMPARISON,
    period: bool | None = None,
    period_range_days: tuple[float, float] = PERIOD_RANGE_DAYS,
    n_bootstrap: int = 0,
    n_permutations: int = N_PERMUTATIONS,
    use_cache: bool = True,
) -> LightCurve:
    """Light curve of the FIXED position (ra, dec) [deg ICRS] from every SPHEREx exposure covering it.

    Stamps come from WS1 ``point_series`` (``collections`` default DR1 + QR3; deep fields opt-in, e.g.
    ``['spherex_dr1', 'spherex_qr3', 'spherex_dr1_deep', 'spherex_qr3_deep']`` for R Dra; ``max_frames`` caps
    the series spread over detectors and visits; ``deadline_s`` bounds the whole read). A moving star must be
    followed with its proper motion: this function does not (the variables RW Aur and R Dra move < 0.01 px).
    """
    from ..data.point import point_series

    if method not in METHODS:
        raise ValueError(f"method must be one of {METHODS}, got {method!r}")
    box = int(box_px or DEFAULT_BOX_PX[method])
    need = 2 * math.ceil((APERTURE_ANNULUS_PX if method == "aperture" else WING_BACKGROUND_PX)[1]) + 1
    if box < need:
        raise ValueError(f"box_px must be >= {need} for the {method} method, got {box}")
    t0 = time.perf_counter()
    series = point_series(
        ra,
        dec,
        box_px=box,
        detectors=detectors,
        mjd_min=mjd_min,
        mjd_max=mjd_max,
        collections=collections,
        max_frames=max_frames,
        planes=DEFAULT_PLANES[method],
        deadline_s=deadline_s,
        use_cache=use_cache,
    )
    t1 = time.perf_counter()
    exposures, failures = exposures_from_series(series)
    lc = light_curve_from_exposures(
        exposures,
        ra,
        dec,
        method=method,
        lambda_bin_frac=lambda_bin_frac,
        min_bin_span_days=min_bin_span_days,
        n_comparison=n_comparison,
        period=period,
        period_range_days=period_range_days,
        n_bootstrap=n_bootstrap,
        n_permutations=n_permutations,
    )
    lc.failures = [{"frame_id": f"{f.obs_id}D{f.detector}", "reason": why} for f, why in series.failures] + failures
    lc.search = dict(series.search)
    lc.timings = {
        "series_s": round(t1 - t0, 3),
        "measure_s": round(time.perf_counter() - t1, 3),
        "box_px": box,
        "planes": list(DEFAULT_PLANES[method]),
        **{k: series.timings.get(k) for k in ("from_cache", "frames", "samples", "timed_out", "bytes", "requests")},
    }
    if series.timings.get("timed_out"):
        lc.notes.append(
            f"{series.timings['timed_out']} exposures were not read within the {deadline_s} s deadline: the light "
            "curve is partial (spread over every season)."
        )
    return lc
