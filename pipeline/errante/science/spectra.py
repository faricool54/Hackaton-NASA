"""SPHEREx spectrum of a chosen sky position, or of a candidate's detections (WS3-5, C02).

Each SPHEREx exposure sees a different wavelength at a given sky position (linear variable filter), so forced
photometry of one position on every exposure is a low-resolution 0.75-5 um spectrum:
  asteroids  -> reflected sunlight (rises toward ~1-2.5 um, 3 um hydration band)
  cold brown dwarfs -> very red, strong CH4 absorption ~3.3 um, bright ~4-5 um
  stars -> Rayleigh-Jeans tail (falls with wavelength)

The photometry is WS2's (``errante.imaging.photometry.spectrum_at``: aperture on the native FITS pixels, MJy/sr ->
mJy with OMEGA_MEDIAN, errors from VARIANCE, aperture correction from field stars per detector, flags). This module
adds what the science needs on top (:func:`position_spectrum`):

- every exposure's date, detector, release, season (gaps > 30 d), saturation and usability;
- per-season grouping, and a VARIABILITY CHECK so time changes are never read as spectral shape without a warning:
  same-detector exposures of different seasons at matched wavelength (|dlambda|/lambda < 1 %) must agree, tested
  separately for every season pair and detector (a source may vary at some wavelengths only);
- reference checks: averages over broadband filter windows against catalog photometry converted to mJy
  (:data:`REFERENCE_BANDS`: 2MASS and WISE zero points with their sources) and a shape comparison against the DR1
  spectral cube (``errante.data.cube.cube_spectrum``, a different product: only the shape is compared).

Saturated exposures (OVERFLOW in the aperture) are lower limits: they are kept in the list, flagged, and never
enter the spectrum. ``color_class`` is not implemented (classification is optional and needs tuning on known stars).
"""

from __future__ import annotations

import math
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass, field

import numpy as np

from ..data.cube import CHANNELS_PER_DETECTOR
from ..data.epochs import SEASON_GAP_DAYS, group_seasons
from ..models import Candidate, SpectrumPoint
from .variability import MAG, mjd_to_iso

MJY_PER_MJY_SR_PER_PIXEL = (6.15 / 206264.806) ** 2 * 1e9  # MJy/sr * px -> mJy (nominal 6.15" px)
MATCH_FRAC = 0.01  # |dlambda|/lambda for "the same wavelength" (validation records)
MIN_PAIR_DAYS = 30.0
VARIATION_MAG = 0.15  # ~3x the comparison-star scatter of the RW Aur record (0.046-0.049 mag)
VARIATION_NSIGMA = 5.0
MIN_PAIR_SNR = 10.0  # below this one pair cannot test 0.15 mag (its own error is >= 0.15 mag)
SATURATED_WARN_FRACTION = 0.5


@dataclass(frozen=True)
class Band:
    """A broadband filter for reference checks: zero-magnitude flux density and the window averaged on SPHEREx."""

    name: str
    system: str
    zero_point_jy: float
    lambda_um: float  # isophotal wavelength
    width_um: float  # bandwidth of the source table: the averaging window is lambda +- width / 2
    source: str

    @property
    def window_um(self) -> tuple[float, float]:
        return self.lambda_um - self.width_um / 2, self.lambda_um + self.width_um / 2


REFERENCE_BANDS: dict[str, Band] = {
    # Verified 2026-11-15 on the 2MASS All-Sky Explanatory Supplement VI.4a, Table 1 (IRSA).
    "2MASS_J": Band("J", "2MASS Vega", 1594.0, 1.235, 0.162, "Cohen, Wheaton & Megeath 2003, AJ 126, 1090"),
    "2MASS_H": Band("H", "2MASS Vega", 1024.0, 1.662, 0.251, "Cohen, Wheaton & Megeath 2003, AJ 126, 1090"),
    "2MASS_Ks": Band("Ks", "2MASS Vega", 666.7, 2.159, 0.262, "Cohen, Wheaton & Megeath 2003, AJ 126, 1090"),
    # Jarrett et al. 2011, ApJ 735, 112, Table 1 (WISE Explanatory Supplement IV.4.h, Table 9, an image there: the
    # zero points were also used in docs/validation/wise-0855.md; the bandwidths are not re-read from the source).
    "WISE_W1": Band("W1", "WISE Vega", 309.540, 3.3526, 0.6626, "Jarrett et al. 2011, ApJ 735, 112"),
    "WISE_W2": Band("W2", "WISE Vega", 171.787, 4.6028, 1.0423, "Jarrett et al. 2011, ApJ 735, 112"),
}


def mag_to_mjy(mag: float, band: str, mag_err: float | None = None) -> tuple[float, float | None]:
    """Catalog Vega magnitude -> flux density [mJy] (``F0 * 10**(-0.4 m)``) and its error."""
    b = REFERENCE_BANDS[band]
    f = b.zero_point_jy * 10 ** (-0.4 * mag) * 1e3
    return f, (f * mag_err / MAG if mag_err is not None else None)


@dataclass
class SpectrumSample:
    """One exposure at the position (usable or not)."""

    frame_id: str
    obs_id: str
    detector: int
    release: str | None
    mjd: float  # mid-exposure
    date: str  # ISO UTC
    season: int  # 0-based, gaps > 30 d
    wavelength_um: float | None
    bandwidth_um: float | None
    flux_mjy: float | None
    flux_err_mjy: float | None
    saturated: bool  # OVERFLOW in the aperture: the flux is a lower limit
    usable: bool  # enters the spectrum
    aperture_correction: float | None
    flags: tuple[str, ...] = ()


@dataclass
class SeasonSummary:
    season: int
    mjd_min: float
    mjd_max: float
    date_min: str
    date_max: str
    n_points: int
    n_usable: int
    n_saturated: int
    detectors: list[int]
    wavelength_min_um: float | None
    wavelength_max_um: float | None


@dataclass
class PositionSpectrum:
    ra: float
    dec: float
    proper_motion: dict | None  # {pm_ra_masyr, pm_dec_masyr, epoch_mjd} used to follow the source
    samples: list[SpectrumSample]
    seasons: list[SeasonSummary]
    season_pairs: list[dict]  # matched-wavelength pairs across seasons (variability check)
    variable: bool | None  # True: flux changed between seasons at matched wavelength; None: not testable
    warnings: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    failures: list[dict] = field(default_factory=list)

    def usable(self, season: int | None = None) -> list[SpectrumSample]:
        return [s for s in self.samples if s.usable and (season is None or s.season == season)]

    def spectrum_points(self, season: int | None = None) -> list[SpectrumPoint]:
        """Usable points as the contract's ``SpectrumPoint`` (mJy), sorted by wavelength; one season or all.
        Mixing seasons of a variable source mixes time and colour: check ``variable``/``warnings`` first."""
        return [
            SpectrumPoint(
                frame_id=s.frame_id,
                wavelength_um=s.wavelength_um,
                bandwidth_um=s.bandwidth_um,
                flux_mjy=s.flux_mjy,
                flux_err_mjy=s.flux_err_mjy,
            )
            for s in sorted(self.usable(season), key=lambda s: (s.wavelength_um, s.mjd))
        ]

    def by_season(self) -> dict[int, list[SpectrumPoint]]:
        return {s.season: self.spectrum_points(s.season) for s in self.seasons}

    def to_dict(self) -> dict:
        """Strict JSON (NaN -> None)."""
        return _json_safe(asdict(self))


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


def season_pairs(
    samples: Sequence[SpectrumSample],
    *,
    max_frac: float = MATCH_FRAC,
    min_dt_days: float = MIN_PAIR_DAYS,
    min_snr: float = MIN_PAIR_SNR,
) -> list[dict]:
    """Usable same-detector exposures of DIFFERENT seasons at matched wavelength, both with flux/error >= ``min_snr``:
    ``delta_mag`` = later - earlier."""

    def snr_ok(s: SpectrumSample) -> bool:
        if not (s.flux_mjy and s.flux_mjy > 0):
            return False
        return s.flux_err_mjy is None or s.flux_mjy >= min_snr * s.flux_err_mjy

    use = sorted((s for s in samples if s.usable and snr_ok(s)), key=lambda s: s.mjd)
    out = []
    for i, a in enumerate(use):
        for b in use[i + 1 :]:
            if b.detector != a.detector or b.season == a.season or b.mjd - a.mjd < min_dt_days:
                continue
            if abs(b.wavelength_um - a.wavelength_um) / (0.5 * (a.wavelength_um + b.wavelength_um)) >= max_frac:
                continue
            err = None
            if a.flux_err_mjy and b.flux_err_mjy:
                err = MAG * math.hypot(a.flux_err_mjy / a.flux_mjy, b.flux_err_mjy / b.flux_mjy)
            out.append(
                {
                    "detector": a.detector,
                    "frame_a": a.frame_id,
                    "frame_b": b.frame_id,
                    "season_a": a.season,
                    "season_b": b.season,
                    "wavelength_a_um": a.wavelength_um,
                    "wavelength_b_um": b.wavelength_um,
                    "delta_mag": -MAG * math.log(b.flux_mjy / a.flux_mjy),
                    "delta_mag_err": err,
                }
            )
    return out


def _variability_verdict(pairs: list[dict], untested: Sequence[int] = ()) -> tuple[bool | None, str]:
    """Tested SEPARATELY for every (season pair, detector): a source often varies in some wavelengths only (a young
    star's extinction changes are ~1 mag at 0.75 um and < 0.1 mag at 4.5 um), so pooling detectors would let the
    many infrared pairs outvote a real change in D1/D2.

    A group (season pair, detector) CHANGED when it has >= 2 pairs, its median dm exceeds 0.15 mag and 5x the median
    statistical error, and more than half of its pairs moved by > 0.15 mag in that direction. Medians and a majority,
    not single pairs: a 1 % wavelength mismatch on a steep spectral feature or a systematic outlier moves single pairs
    by > 0.15 mag even for a constant source (eps Ind B: 74 of 714 pairs, median |dm| 0.03-0.06 mag per detector,
    measured 2026-11-15). A group AGREES when its median |dm| is <= 0.15 mag; anything else (a single pair above
    0.15 mag, or pairs above it that are too noisy or inconsistent) is "not testable".

    ``variable``: True when any group changed; None when none changed but some group is not testable; False only
    when every group agrees (and then only for the detectors and seasons that have pairs). ``untested``: detectors
    with usable points in several seasons but no pair (no matched wavelength or SNR < 10), named in the text."""
    if not pairs:
        return None, ""
    groups: dict[tuple[int, int, int], list[dict]] = {}
    for p in pairs:
        groups.setdefault((p["season_a"], p["season_b"], p["detector"]), []).append(p)
    changed, unclear, single, agree = [], [], [], []
    for (sa, sb, det), ps in sorted(groups.items()):
        dm = np.array([p["delta_mag"] for p in ps], float)
        med, med_abs = float(np.median(dm)), float(np.median(np.abs(dm)))
        errs = [p["delta_mag_err"] for p in ps if p["delta_mag_err"] is not None]
        med_err = float(np.median(errs)) if errs else 0.0
        label = f"S{sa}->S{sb} D{det} median dm {med:+.2f} ({len(ps)} pairs)"
        if med_abs <= VARIATION_MAG:
            agree.append((sa, sb, det))
        elif len(ps) < 2:
            single.append(f"S{sa}->S{sb} D{det} a single pair, dm {med:+.2f}")
        elif (
            abs(med) > VARIATION_MAG
            and abs(med) > VARIATION_NSIGMA * med_err
            and int(np.sum(np.sign(med) * dm > VARIATION_MAG)) > len(ps) / 2
        ):
            changed.append(label)
        else:
            unclear.append(label)
    med = float(np.median([abs(p["delta_mag"]) for p in pairs]))
    n_big = sum(abs(p["delta_mag"]) > VARIATION_MAG for p in pairs)
    dets_ok = sorted({d for _, _, d in agree})
    gap = (
        f" Not tested (usable in several seasons, no matched pair with SNR >= {MIN_PAIR_SNR:g}): "
        f"D{', D'.join(map(str, untested))}."
        if untested
        else ""
    )
    if changed:
        return True, (
            f"The flux changed between seasons at matched wavelength (same detector, |dlambda|/lambda < 1 %): "
            f"{'; '.join(changed)}. Read each season's spectrum separately: combining them mixes variability (or "
            "calibration) with spectral shape."
        )
    if unclear or single:
        return None, (
            f"Variability between seasons is not testable in {'; '.join(unclear + single)}: above {VARIATION_MAG} mag "
            f"but with a single pair, within {VARIATION_NSIGMA:g} times the errors or with pairs that disagree. "
            f"Points from different seasons may mix variability and spectral shape.{gap}"
        )
    return False, (
        f"{len(pairs)} same-detector pairs of different seasons at matched wavelength agree in every season pair and "
        f"detector tested (D{', D'.join(map(str, dets_ok))}): median |dm| <= {VARIATION_MAG} mag in each ({med:.3f} "
        f"mag over all; {n_big} single pairs differ by more, inside groups whose median agrees): no variability above "
        f"~{VARIATION_MAG} mag between seasons in those detectors.{gap}"
    )


def from_spectrum_result(
    result, *, pm: tuple[float, float, float] | None = None, season_gap_days: float = SEASON_GAP_DAYS
) -> PositionSpectrum:
    """:class:`PositionSpectrum` from WS2's ``photometry.SpectrumResult`` (seasons, saturation, variability check)."""
    pts = sorted(result.points, key=lambda p: (p.mjd, p.detector, p.frame_id))
    season_of: dict[int, int] = {}
    groups = group_seasons(pts, season_gap_days) if pts else []
    for k, group in enumerate(groups):
        for p in group:
            season_of[id(p)] = k
    samples = [
        SpectrumSample(
            frame_id=p.frame_id,
            obs_id=p.obs_id,
            detector=int(p.detector),
            release=p.release,
            mjd=float(p.mjd),
            date=mjd_to_iso(p.mjd),
            season=season_of[id(p)],
            wavelength_um=p.wavelength_um,
            bandwidth_um=p.bandwidth_um,
            flux_mjy=p.flux_mjy,
            flux_err_mjy=p.flux_err_mjy,
            saturated="saturated" in p.flags,
            usable=bool(p.usable),
            aperture_correction=p.aperture_correction,
            flags=tuple(p.flags),
        )
        for p in pts
    ]
    seasons = []
    for k in range(len(groups)):
        mine = [s for s in samples if s.season == k]
        lam = [s.wavelength_um for s in mine if s.usable]
        seasons.append(
            SeasonSummary(
                season=k,
                mjd_min=min(s.mjd for s in mine),
                mjd_max=max(s.mjd for s in mine),
                date_min=min(s.date for s in mine),
                date_max=max(s.date for s in mine),
                n_points=len(mine),
                n_usable=sum(s.usable for s in mine),
                n_saturated=sum(s.saturated for s in mine),
                detectors=sorted({s.detector for s in mine}),
                wavelength_min_um=min(lam) if lam else None,
                wavelength_max_um=max(lam) if lam else None,
            )
        )
    pairs = season_pairs(samples)
    paired = {p["detector"] for p in pairs}
    multi = {
        d for d in {s.detector for s in samples} if len({s.season for s in samples if s.usable and s.detector == d}) > 1
    }
    variable, verdict = _variability_verdict(pairs, untested=sorted(multi - paired))
    warnings, notes = [], list(result.notes)
    n_sat = sum(s.saturated for s in samples)
    if samples and n_sat >= SATURATED_WARN_FRACTION * len(samples):
        warnings.append(
            f"The source saturates in {n_sat} of {len(samples)} exposures (OVERFLOW in the aperture): those fluxes are "
            "lower limits and are not in the spectrum; what is left may cover only part of the wavelength range."
        )
    elif n_sat:
        notes.append(f"{n_sat} saturated exposures (lower limits) are listed but not in the spectrum.")
    n_usable = sum(s.usable for s in samples)
    n_raw = sum(1 for s in samples if s.usable and s.aperture_correction is None)
    if n_raw and n_raw < n_usable:
        warnings.append(
            f"{n_raw} of {n_usable} usable points have no aperture correction and the others do: the spectrum mixes "
            "r = 2 px fluxes with corrected ones (a few per cent apart)."
        )
    elif n_raw:
        notes.append(
            f"No aperture correction (too few field stars in the patches): all {n_raw} usable fluxes are r = 2 px "
            "aperture fluxes, a few per cent low (corrections were 1.03-1.10 on eps Ind B's exposures)."
        )
    n_seasons_used = len({s.season for s in samples if s.usable})
    if variable or (variable is None and verdict):
        warnings.append(verdict)
    elif variable is False:
        notes.append(verdict)
    elif n_seasons_used > 1:
        warnings.append(
            f"Usable points come from {n_seasons_used} seasons and no same-detector pair at matched wavelength (with "
            f"SNR >= {MIN_PAIR_SNR:g}) exists to test variability: if the source varies, the combined spectrum mixes "
            "time and spectral shape."
        )
    return PositionSpectrum(
        ra=float(result.ra),
        dec=float(result.dec),
        proper_motion=None if pm is None else {"pm_ra_masyr": pm[0], "pm_dec_masyr": pm[1], "epoch_mjd": pm[2]},
        samples=samples,
        seasons=seasons,
        season_pairs=pairs,
        variable=variable,
        warnings=warnings,
        notes=notes,
        failures=[{"frame_id": f, "reason": r} for f, r in result.failures],
    )


def position_spectrum(
    ra: float,
    dec: float,
    *,
    pm: tuple[float, float, float] | None = None,
    detectors: list[int] | None = None,
    max_frames: int | None = None,
    size_arcmin: float = 6.0,
    season_gap_days: float = SEASON_GAP_DAYS,
) -> PositionSpectrum:
    """Spectrum of (ra, dec) [deg ICRS] from every SPHEREx exposure covering it (WS2 forced photometry).

    ``pm`` = (pm_ra_cosdec, pm_dec [mas/yr], epoch_mjd of ra/dec) follows a moving star (no parallax).
    ``max_frames`` keeps that many exposures evenly spread in time (all by default; each costs a ~6' S3 patch, about
    2 MB: 460 exposures of eps Ind B are ~1 GB). Raises what ``spectrum_at`` raises (archive search errors).
    """
    from ..imaging.photometry import spectrum_at

    res = spectrum_at(ra, dec, pm=pm, detectors=detectors, max_frames=max_frames, size_arcmin=size_arcmin)
    return from_spectrum_result(res, pm=pm, season_gap_days=season_gap_days)


# --- reference checks ----------------------------------------------------------------------------------------


def band_average(
    spectrum: PositionSpectrum, band: str, *, season: int | None = None, min_points: int = 3
) -> dict | None:
    """Plain mean of the usable fluxes [mJy] inside the band's window (no filter-response weighting), with its
    standard error, or None with fewer than ``min_points``. ``coverage`` = wavelength span of the points over the
    window width (SPHEREx stops at 5.0 um: W2 is cut)."""
    lo, hi = REFERENCE_BANDS[band].window_um
    pts = [s for s in spectrum.usable(season) if lo <= s.wavelength_um <= hi]
    if len(pts) < min_points:
        return None
    f = np.array([s.flux_mjy for s in pts])
    lam = [s.wavelength_um for s in pts]
    return {
        "band": band,
        "n": len(pts),
        "mean_mjy": float(f.mean()),
        "sem_mjy": float(f.std(ddof=1) / math.sqrt(len(f))),
        "median_mjy": float(np.median(f)),
        "window_um": [lo, hi],
        "coverage": (max(lam) - min(lam)) / (hi - lo),
    }


def compare_with_photometry(
    spectrum: PositionSpectrum, mags: Mapping[str, float | tuple[float, float]], *, season: int | None = None
) -> list[dict]:
    """SPHEREx band averages against catalog magnitudes (``{'2MASS_J': 11.908 or (11.908, 0.022), ...}``).

    ``ratio`` = SPHEREx / catalog. Expect agreement only to tens of percent: unweighted window average instead of
    the filter response, different epochs (variability, proper motion), and narrow spectral features (a T dwarf's
    CH4 bands inside W1) weigh differently in a narrow-band mean.
    """
    out = []
    for band, m in mags.items():
        mag, err = m if isinstance(m, tuple) else (m, None)
        cat, cat_err = mag_to_mjy(mag, band, err)
        avg = band_average(spectrum, band, season=season)
        b = REFERENCE_BANDS[band]
        out.append(
            {
                "band": band,
                "system": b.system,
                "zero_point_jy": b.zero_point_jy,
                "zero_point_source": b.source,
                "mag": mag,
                "mag_err": err,
                "catalog_mjy": cat,
                "catalog_err_mjy": cat_err,
                "spherex": avg,
                "ratio": avg["mean_mjy"] / cat if avg else None,
            }
        )
    return out


def compare_with_cube(spectrum: PositionSpectrum, cube: Mapping | object, *, season: int | None = None) -> dict:
    """Shape comparison with a DR1 cube spectrum (``CubeSpectrum`` or its ``to_dict()``).

    Different products: the cube is a static coadd in MJy/sr per 12.9" pixel (or an aperture mean) without background
    subtraction or aperture correction. For every valid cube plane the median of our usable points OF THE SAME
    DETECTOR within half its bandwidth is paired with it (detectors overlap in wavelength at their edges, where the
    cube jumps); a straight line ``cube = slope * spherex + offset`` (the offset absorbs the sky the
    cube does not subtract) and the Pearson correlation of the pairs measure the agreement of the SHAPES only.
    """
    d = cube.to_dict() if hasattr(cube, "to_dict") else cube
    lam = np.asarray(d["wavelength_um"], float)
    bw = np.asarray(d["bandwidth_um"], float)
    flux = np.array([np.nan if v is None else v for v in d["flux"]], float)
    valid = np.asarray(d["valid"], bool) & np.isfinite(flux)
    cdet = np.asarray(d["detector"], int) if "detector" in d else np.arange(len(flux)) // CHANNELS_PER_DETECTOR + 1
    pts = spectrum.usable(season)
    pl = np.array([s.wavelength_um for s in pts], float)
    pf = np.array([s.flux_mjy for s in pts], float)
    pd = np.array([s.detector for s in pts], int)
    xs, ys, ks = [], [], []
    for k in np.flatnonzero(valid):
        near = (np.abs(pl - lam[k]) <= bw[k] / 2) & (pd == cdet[k])
        if near.sum() >= 1:
            xs.append(float(np.median(pf[near])))
            ys.append(float(flux[k]))
            ks.append(int(k))
    res = {"n_planes": len(ks), "planes": ks, "spherex_mjy": xs, "cube": ys, "cube_unit": d.get("unit", "MJy/sr")}
    if len(ks) < 5:
        return {**res, "pearson_r": None, "slope": None, "offset": None}
    x, y = np.array(xs), np.array(ys)
    slope, offset = (float(v) for v in np.polyfit(x, y, 1))
    return {**res, "pearson_r": float(np.corrcoef(x, y)[0, 1]), "slope": slope, "offset": offset}


# --- candidates ----------------------------------------------------------------------------------------------


def candidate_spectrum(
    candidate: Candidate,
    wavelengths: dict[str, tuple[float, float]],
    *,
    images: Mapping[str, object] | None = None,
) -> list[SpectrumPoint]:
    """Spectrum points of a candidate from its detections. ``wavelengths[frame_id] = (um, bw_um)`` at the
    detection position (``data.fits_io.wavelength_at``).

    Without ``images`` each detection with a wavelength and a flux becomes a point: the detection's own ``flux_mjy``
    (measured by WS2 on the native frame). With ``images`` (``{frame_id: fits_io.SpherexImage}``) ONE photometry is
    used for every point, as in ``imaging.photometry.spectrum_at``: WS2's forced photometry (``measure``, r = 2 px) at
    the detection position, with the aperture correction fitted per detector against wavelength on the field stars of
    all the given images (``fit_corrections``; the all-detector fit when a detector has too few stars). Detections
    without an image, unusable measurements (saturated, bad pixels, off the detector) and frames whose detector has
    no correction at all are dropped, never mixed in: an uncorrected r = 2 px flux is a few per cent low (the
    corrections were 1.03-1.10 on eps Ind B's exposures, measured 2026-11-15).
    Nothing is invented: a detection without flux or wavelength is skipped. Sorted by wavelength. Detections of a
    moving object are at different times: the spectrum mixes time and colour if the object varies (rotation of an
    asteroid), say so in the UI.
    """
    rows: list[tuple[str, tuple[float, float | None], float, float | None]] = []
    if images is None:
        for det in candidate.detections:
            wave = wavelengths.get(det.frame_id)
            if wave is not None and det.flux_mjy is not None and math.isfinite(det.flux_mjy):
                rows.append((det.frame_id, wave, det.flux_mjy, det.flux_err_mjy))
    else:
        from ..imaging.photometry import correction_ratios, fit_corrections, measure, planes

        measured, samples = [], defaultdict(list)
        for det in candidate.detections:
            img = images.get(det.frame_id)
            if img is None:
                continue
            pl = planes(img)
            p = measure(img, det.position.ra, det.position.dec, frame_id=det.frame_id, correction=1.0, pl=pl)
            if p is None or p.flux_mjy is None or {"saturated", "edge", "bad_pixels"} & set(p.flags):
                continue
            wave = wavelengths.get(det.frame_id)
            if wave is None and p.wavelength_um is not None:
                wave = (p.wavelength_um, p.bandwidth_um)
            if wave is None:
                continue
            samples[p.detector] += [(wave[0], r) for r in correction_ratios(pl, exclude=(p.x, p.y))]
            measured.append((det.frame_id, p, wave))
        fits = fit_corrections(samples)
        pooled = fit_corrections({0: [s for det_samples in samples.values() for s in det_samples]}).get(0)
        for fid, p, wave in measured:
            fit = fits.get(p.detector, pooled)
            if fit is None:
                continue
            c = min(3.0, max(1.0, fit[0] + fit[1] * wave[0]))  # clamped like photometry.spectrum_at
            rows.append((fid, wave, p.flux_mjy * c, None if p.flux_err_mjy is None else p.flux_err_mjy * c))
    out = [
        SpectrumPoint(
            frame_id=fid,
            wavelength_um=float(wave[0]),
            bandwidth_um=None if wave[1] is None else float(wave[1]),
            flux_mjy=float(flux),
            flux_err_mjy=None if err is None or not math.isfinite(err) else float(err),
        )
        for fid, wave, flux, err in rows
        if math.isfinite(flux)
    ]
    return sorted(out, key=lambda p: p.wavelength_um)


def color_class(points: list[SpectrumPoint]) -> str:
    """'star-like' | 'neutral' | 'red' | 'very-red' from 1-2 um vs 4-5 um flux ratio.

    TODO(WS3): simple ratio with thresholds tuned on known stars/asteroids; always
    return it with a caveat note in the UI.
    """
    raise NotImplementedError("WS3: color_class")
