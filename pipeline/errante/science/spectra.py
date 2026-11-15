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
  same-detector exposures of different seasons at matched wavelength (|dlambda|/lambda < 1 %) must agree;
- reference checks: averages over broadband filter windows against catalog photometry converted to mJy
  (:data:`REFERENCE_BANDS`: 2MASS and WISE zero points with their sources) and a shape comparison against the DR1
  spectral cube (``errante.data.cube.cube_spectrum``, a different product: only the shape is compared).

Saturated exposures (OVERFLOW in the aperture) are lower limits: they are kept in the list, flagged, and never
enter the spectrum. ``color_class`` is not implemented (classification is optional and needs tuning on known stars).
"""

from __future__ import annotations

import math
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


def _variability_verdict(pairs: list[dict]) -> tuple[bool | None, str]:
    """Variable when, for some pair of seasons (>= 2 pairs), the MEDIAN |dm| exceeds 0.15 mag and 5x the median
    statistical error. Medians, not single pairs: a 1 % wavelength mismatch on a steep spectral feature or a
    systematic outlier moves single pairs by > 0.15 mag even for a constant source (eps Ind B: 74 of 714 pairs,
    median |dm| 0.03-0.06 mag per detector, measured 2026-11-15). A pair of seasons with a single pair above
    0.15 mag is "not testable", never "variable" nor "constant"."""
    if not pairs:
        return None, ""
    groups: dict[tuple[int, int], list[dict]] = {}
    for p in pairs:
        groups.setdefault((p["season_a"], p["season_b"]), []).append(p)
    changed, unclear, single, agree = [], [], [], 0
    for (sa, sb), ps in sorted(groups.items()):
        med_abs = float(np.median([abs(p["delta_mag"]) for p in ps]))
        if len(ps) < 2:
            if med_abs > VARIATION_MAG:
                single.append(f"S{sa}->S{sb} a single pair, dm {ps[0]['delta_mag']:+.2f}")
            continue
        errs = [p["delta_mag_err"] for p in ps if p["delta_mag_err"] is not None]
        med_err = float(np.median(errs)) if errs else 0.0
        label = f"S{sa}->S{sb} median dm {float(np.median([p['delta_mag'] for p in ps])):+.2f} ({len(ps)} pairs)"
        if med_abs > VARIATION_MAG and med_abs > VARIATION_NSIGMA * med_err:
            changed.append(label)
        elif med_abs > VARIATION_MAG:
            unclear.append(label)
        else:
            agree += 1
    med = float(np.median([abs(p["delta_mag"]) for p in pairs]))
    n_big = sum(abs(p["delta_mag"]) > VARIATION_MAG for p in pairs)
    if changed:
        return True, (
            f"The flux changed between seasons at matched wavelength (same detector, |dlambda|/lambda < 1 %): "
            f"{'; '.join(changed)}. Read each season's spectrum separately: combining them mixes variability (or "
            "calibration) with spectral shape."
        )
    if unclear or (single and not agree):
        return None, (
            f"Variability between seasons is not testable: {'; '.join(unclear + single)} exceed {VARIATION_MAG} mag, "
            f"but within {VARIATION_NSIGMA:g} times the errors or with a single pair. Points from different seasons "
            "may mix variability and spectral shape."
        )
    extra = f" Not tested (single pairs): {'; '.join(single)}." if single else ""
    return False, (
        f"{len(pairs)} same-detector pairs of different seasons at matched wavelength agree (median |dm| {med:.3f} "
        f"mag; {n_big} single pairs differ by > {VARIATION_MAG} mag, expected from steep spectral features and "
        f"systematics): no variability above ~{VARIATION_MAG} mag between seasons.{extra}"
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
    variable, verdict = _variability_verdict(pairs)
    warnings, notes = [], list(result.notes)
    n_sat = sum(s.saturated for s in samples)
    if samples and n_sat >= SATURATED_WARN_FRACTION * len(samples):
        warnings.append(
            f"The source saturates in {n_sat} of {len(samples)} exposures (OVERFLOW in the aperture): those fluxes are "
            "lower limits and are not in the spectrum; what is left may cover only part of the wavelength range."
        )
    elif n_sat:
        notes.append(f"{n_sat} saturated exposures (lower limits) are listed but not in the spectrum.")
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

    Each detection becomes a point when it has a wavelength and a flux: the detection's own ``flux_mjy`` (measured
    by WS2 on the native frame), or, when ``images[frame_id]`` (a ``fits_io.SpherexImage``) is given, WS2's forced
    photometry (``imaging.photometry.measure``) at the detection position, whose unusable points (saturated, bad
    pixels, off the detector) are dropped. Nothing is invented: a detection without flux or wavelength is skipped.
    Sorted by wavelength. Detections of a moving object are at different times: the spectrum mixes time and colour
    if the object varies (rotation of an asteroid), say so in the UI.
    """
    out = []
    for det in candidate.detections:
        wave = wavelengths.get(det.frame_id)
        flux, err = det.flux_mjy, det.flux_err_mjy
        if images is not None and det.frame_id in images:
            from ..imaging.photometry import measure

            p = measure(images[det.frame_id], det.position.ra, det.position.dec, frame_id=det.frame_id)
            if p is None or not (p.flux_mjy is not None and not ({"saturated", "edge", "bad_pixels"} & set(p.flags))):
                continue
            flux, err = p.flux_mjy, p.flux_err_mjy
            if wave is None and p.wavelength_um is not None:
                wave = (p.wavelength_um, p.bandwidth_um)
        if wave is None or flux is None or not math.isfinite(flux):
            continue
        out.append(
            SpectrumPoint(
                frame_id=det.frame_id,
                wavelength_um=float(wave[0]),
                bandwidth_um=None if wave[1] is None else float(wave[1]),
                flux_mjy=float(flux),
                flux_err_mjy=None if err is None or not math.isfinite(err) else float(err),
            )
        )
    return sorted(out, key=lambda p: p.wavelength_um)


def color_class(points: list[SpectrumPoint]) -> str:
    """'star-like' | 'neutral' | 'red' | 'very-red' from 1-2 um vs 4-5 um flux ratio.

    TODO(WS3): simple ratio with thresholds tuned on known stars/asteroids; always
    return it with a caveat note in the UI.
    """
    raise NotImplementedError("WS3: color_class")
