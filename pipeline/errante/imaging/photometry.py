"""Forced photometry at a sky position on every SPHEREx exposure -> a 0.75-5 um spectrum (WS2, for WS3-5).

Each SPHEREx exposure sees a different wavelength at a given sky position (linear variable filter), so
measuring one position on all its exposures gives a low-resolution spectrum. This module measures on the
NATIVE pixels of each FITS file (never on PNGs):

- position: the WCS of the file (TAN-SIP); optionally propagated with proper motion to each exposure's epoch;
- flux: circular aperture with exact-ish fractional pixel weights (supersampled), local sky = median of an
  annulus, MJy/sr -> mJy with the pixel solid angle (header OMEGA_MEDIAN, else 6.15" x 6.15");
- aperture correction: curve of growth (small / large aperture) measured on bright, isolated, unflagged field
  stars of the same frame; per-detector median when a frame has too few stars;
- error: VARIANCE plane inside the aperture plus the sky-median uncertainty;
- wavelength and bandwidth at that exact position (WCS-WAVE, ``SpherexImage.wavelength_at``, WS1);
- flags: ``saturated`` (OVERFLOW in the aperture: the flux is a lower limit), ``bad_pixels``, ``edge``
  (aperture not fully covered), ``transient_flag`` (TRANSIENT/OUTLIER: informational), ``no_wavelength``,
  ``aperture_correction_detector_median`` / ``no_aperture_correction``.

Time matters: points of a variable star taken months apart mix variability with spectral shape. Every point
keeps its MJD so the UI/WS3 can split or colour by season (WS3-5: "no mezclar variabilidad temporal con forma
espectral sin advertencia").
"""

from __future__ import annotations

import math
import warnings
from collections import defaultdict
from dataclasses import dataclass, field, replace

import numpy as np

from ..data.fits_io import SpherexImage
from ..models import FrameRef, SpectrumPoint
from .flags import DEFAULT_BAD, bitmask

APERTURE_PX = 2.0  # radius; SPHEREx PSF FWHM ~1.2-2 px
SKY_ANNULUS_PX = (4.0, 7.0)
REFERENCE_APERTURE_PX = 5.0  # "total" aperture for the curve of growth
REFERENCE_ANNULUS_PX = (7.0, 10.0)
SUPERSAMPLE = 5
MIN_SKY_PIXELS = 10
MIN_CORRECTION_STARS = 3
STAR_SNR = 30.0
PIXEL_ARCSEC = 6.15
MJY_PER_MJY = 1e9  # 1 MJy = 1e9 mJy
SATURATED = bitmask(["OVERFLOW"])
TRANSIENT = bitmask(["TRANSIENT", "OUTLIER"])
BAD = bitmask(list(DEFAULT_BAD))
UNUSABLE_FLAGS = frozenset({"saturated", "edge", "bad_pixels", "no_wavelength", "spectral_outlier"})
RELEASE_PREFERENCE = {"dr1": 0, "qr3": 1, "qr2": 2, "synthetic": 3}
SPHEREX_ERA_MJD = 61000.0  # 2025-11, middle of DR1 + QR3


@dataclass(frozen=True)
class ForcedFlux:
    frame_id: str
    obs_id: str
    detector: int
    mjd: float
    release: str | None
    ra: float
    dec: float
    x: float  # 0-based native pixel (FITS orientation)
    y: float
    wavelength_um: float | None
    bandwidth_um: float | None
    flux_mjy: float | None
    flux_err_mjy: float | None
    sky_mjy_sr: float | None
    aperture_correction: float | None
    flags: tuple[str, ...] = ()

    @property
    def usable(self) -> bool:
        """Has a flux and a wavelength; not a lower limit, not partly off the detector or on bad pixels."""
        return (
            self.flux_mjy is not None and self.wavelength_um is not None and not UNUSABLE_FLAGS.intersection(self.flags)
        )


@dataclass
class SpectrumResult:
    ra: float
    dec: float
    points: list[ForcedFlux]
    failures: list[tuple[str, str]] = field(default_factory=list)  # (frame id, reason)
    notes: list[str] = field(default_factory=list)


def pixel_solid_angle_sr(header) -> float:
    omega = header.get("OMEGA_MEDIAN") if header is not None else None
    arcsec2 = float(omega) if omega and float(omega) > 0 else PIXEL_ARCSEC**2
    return arcsec2 * (math.pi / 648000.0) ** 2


def _window(shape: tuple[int, int], x: float, y: float, half: int) -> tuple[slice, slice, np.ndarray, np.ndarray]:
    ny, nx = shape
    x0, x1 = max(0, int(math.floor(x)) - half), min(nx, int(math.floor(x)) + half + 2)
    y0, y1 = max(0, int(math.floor(y)) - half), min(ny, int(math.floor(y)) + half + 2)
    yy, xx = np.mgrid[y0:y1, x0:x1]
    return slice(y0, y1), slice(x0, x1), xx, yy


def aperture_weights(xx: np.ndarray, yy: np.ndarray, x: float, y: float, r: float, n: int = SUPERSAMPLE) -> np.ndarray:
    """Fraction of each pixel (centres xx, yy) inside the circle (x, y, r), by n x n supersampling."""
    offs = (np.arange(n) + 0.5) / n - 0.5
    dx = xx[..., None, None] + offs[None, None, :, None] - x
    dy = yy[..., None, None] + offs[None, None, None, :] - y
    return ((dx**2 + dy**2) <= r**2).mean(axis=(-1, -2))


def _sky(
    data: np.ndarray, usable: np.ndarray, dist: np.ndarray, annulus: tuple[float, float]
) -> tuple[float, float, int]:
    ring = usable & (dist >= annulus[0]) & (dist <= annulus[1])
    values = data[ring]
    if values.size < MIN_SKY_PIXELS:
        return float("nan"), float("nan"), int(values.size)
    med = float(np.median(values))
    return med, float(1.4826 * np.median(np.abs(values - med))), int(values.size)


@dataclass(frozen=True)
class Planes:
    """One image's planes converted once (the photometry calls them dozens of times per frame)."""

    data: np.ndarray  # IMAGE - ZODI, float64, FITS orientation
    flags: np.ndarray  # int64
    variance: np.ndarray | None  # float64
    median: float  # of finite data (sky level of the cutout)
    sigma: float  # robust noise of finite data


def planes(img: SpherexImage) -> Planes:
    data = np.asarray(img.data_minus_zodi, dtype=np.float64)
    flags_plane = np.asarray(img.flags, dtype=np.int64) if img.flags is not None else np.zeros(data.shape, np.int64)
    var = np.asarray(img.variance, dtype=np.float64) if img.variance is not None else None
    finite = data[np.isfinite(data)]
    med = float(np.median(finite)) if finite.size else float("nan")
    sigma = float(1.4826 * np.median(np.abs(finite - med))) if finite.size else float("nan")
    return Planes(data, flags_plane, var, med, sigma)


def aperture_flux(
    pl: Planes, x: float, y: float, r: float, annulus: tuple[float, float]
) -> tuple[float, float, float, set[str]]:
    """(flux, error, sky) in MJy/sr * px on native pixels, plus flags; NaN flux if the sky is not measurable.

    Pixels flagged DEFAULT_BAD (HOT, PERSIST, GHOST, STREAK...) or NaN never enter the sum; the point is then
    flagged (``bad_pixels``/``edge``/``saturated``) and not usable, because the missing part of the PSF is unknown.
    """
    ys, xs, xx, yy = _window(pl.data.shape, x, y, int(math.ceil(annulus[1])) + 1)
    d = pl.data[ys, xs]
    fl = pl.flags[ys, xs]
    var = pl.variance[ys, xs] if pl.variance is not None else None
    dist = np.hypot(xx - x, yy - y)
    bad = (fl & BAD) != 0
    good = np.isfinite(d) & ~bad
    sky, sky_sigma, n_sky = _sky(d, good, dist, annulus)

    w = aperture_weights(xx, yy, x, y, r)
    inside = w > 0
    flags: set[str] = set()
    if w.sum() < 0.97 * np.pi * r**2:  # aperture runs off the array (supersampling noise is < 2 %)
        flags.add("edge")
    if (fl[inside] & SATURATED).any():
        flags.add("saturated")
    if (bad & inside).any():
        flags.add("bad_pixels")
    if (fl[inside] & TRANSIENT).any():
        flags.add("transient_flag")
    if (inside & ~np.isfinite(d) & ~bad).any() and "saturated" not in flags:
        flags.add("edge")
    if not np.isfinite(sky):
        return float("nan"), float("nan"), sky, flags | {"no_sky"}
    use = good & inside
    flux = float(np.sum(np.where(use, (d - sky) * w, 0.0)))
    if var is not None:
        if (use & ~(np.isfinite(var) & (var >= 0))).any():
            return flux, float("nan"), sky, flags | {"no_variance"}
        var_ap = float(np.sum(np.where(use, var * w**2, 0.0)))
    else:
        var_ap = float(np.sum(w[use] ** 2)) * sky_sigma**2
    var_sky = (float(w[use].sum()) ** 2) * (np.pi / 2) * sky_sigma**2 / max(n_sky, 1)
    return flux, math.sqrt(var_ap + var_sky), sky, flags


def _sky_to_pixel(img: SpherexImage, ra: float, dec: float) -> tuple[float, float] | None:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        x, y = (float(v) for v in img.wcs.all_world2pix(ra, dec, 0, quiet=True))
    ny, nx = img.data.shape
    if not (math.isfinite(x) and math.isfinite(y) and -0.5 <= x <= nx - 0.5 and -0.5 <= y <= ny - 0.5):
        return None
    return x, y


def find_correction_stars(
    pl: Planes, exclude: tuple[float, float] | None = None, max_stars: int = 25
) -> list[tuple[int, int]]:
    """Bright, isolated, unflagged local maxima usable for the curve of growth (target excluded)."""
    data, flags_plane = pl.data, pl.flags
    if np.isfinite(data).sum() < 100 or not np.isfinite(pl.median):
        return []
    med = pl.median
    sigma = pl.sigma or 1e-9
    margin = int(REFERENCE_ANNULUS_PX[1]) + 2
    ny, nx = data.shape
    cand = np.argwhere(np.nan_to_num(data - med) >= STAR_SNR * sigma)
    out = []
    for y, x in cand:
        if not (margin <= x < nx - margin and margin <= y < ny - margin):
            continue
        if exclude is not None and math.hypot(x - exclude[0], y - exclude[1]) < 2 * REFERENCE_APERTURE_PX:
            continue
        box = data[y - 3 : y + 4, x - 3 : x + 4]
        if not np.isfinite(box).all() or data[y, x] < box.max():
            continue
        big = flags_plane[y - 6 : y + 7, x - 6 : x + 7]
        if (big & (BAD | SATURATED | TRANSIENT)).any():
            continue
        # isolation: nothing brighter than 20 % of the peak between 3 and 7 px
        yy, xx = np.mgrid[y - 7 : y + 8, x - 7 : x + 8]
        ring = (np.hypot(xx - x, yy - y) > 3) & (np.hypot(xx - x, yy - y) <= 7)
        if np.nanmax(np.where(ring, data[y - 7 : y + 8, x - 7 : x + 8], -np.inf)) - med > 0.2 * (data[y, x] - med):
            continue
        if any(abs(x - ox) <= 2 and abs(y - oy) <= 2 for ox, oy in out):  # flat-topped peak: keep one pixel
            continue
        out.append((int(x), int(y)))
    out.sort(key=lambda p: -data[p[1], p[0]])
    return out[:max_stars]


def _centroid(pl: Planes, x: int, y: int, half: int = 2) -> tuple[float, float]:
    """First-moment centre of a star in a (2*half+1)^2 box (sky-free), so apertures are centred on the star."""
    box = pl.data[y - half : y + half + 1, x - half : x + half + 1]
    w = np.clip(np.nan_to_num(box - pl.median), 0, None)
    if w.sum() <= 0:
        return float(x), float(y)
    yy, xx = np.mgrid[y - half : y + half + 1, x - half : x + half + 1]
    return float((w * xx).sum() / w.sum()), float((w * yy).sum() / w.sum())


def correction_ratios(
    img: SpherexImage | Planes, aperture_px: float = APERTURE_PX, exclude: tuple[float, float] | None = None
) -> list[float]:
    """Total/small aperture flux ratio of each usable field star of this frame (curve-of-growth samples)."""
    pl = img if isinstance(img, Planes) else planes(img)
    ratios = []
    for px, py in find_correction_stars(pl, exclude):
        x, y = _centroid(pl, px, py)
        small, _, _, f1 = aperture_flux(pl, x, y, aperture_px, SKY_ANNULUS_PX)
        total, _, _, f2 = aperture_flux(pl, x, y, REFERENCE_APERTURE_PX, REFERENCE_ANNULUS_PX)
        if f1 or f2 or not (small > 0 and total > 0):
            continue
        ratios.append(total / small)
    return ratios


def aperture_correction(
    img: SpherexImage | Planes, aperture_px: float = APERTURE_PX, exclude: tuple[float, float] | None = None
) -> float | None:
    """Median total/small flux ratio of this frame's field stars; None with fewer than 3 stars."""
    r = np.asarray(correction_ratios(img, aperture_px, exclude))
    if r.size < MIN_CORRECTION_STARS:
        return None
    med = np.median(r)
    mad = 1.4826 * np.median(np.abs(r - med)) or 1e-9
    r = r[np.abs(r - med) <= 3 * mad]
    return float(np.median(r)) if r.size >= MIN_CORRECTION_STARS and 1.0 <= np.median(r) <= 3.0 else None


def measure(
    img: SpherexImage,
    ra: float,
    dec: float,
    *,
    frame_id: str | None = None,
    release: str | None = None,
    aperture_px: float = APERTURE_PX,
    correction: float | None = None,
    pl: Planes | None = None,
) -> ForcedFlux | None:
    """Forced photometry of (ra, dec) on one exposure; None if the position is off this file."""
    pos = _sky_to_pixel(img, ra, dec)
    if pos is None:
        return None
    x, y = pos
    pl = pl or planes(img)
    flux, err, sky, flags = aperture_flux(pl, x, y, aperture_px, SKY_ANNULUS_PX)
    omega = pixel_solid_angle_sr(img.header)
    wave = img.wavelength_at(ra, dec) if hasattr(img, "wavelength_at") else None
    if wave is None:
        flags.add("no_wavelength")
    if correction is None:
        correction = aperture_correction(pl, aperture_px, exclude=(x, y))
    to_mjy = omega * MJY_PER_MJY * (correction if correction is not None else 1.0)
    ok = math.isfinite(flux)
    return ForcedFlux(
        frame_id=frame_id or f"{img.obs_id}D{img.detector}",
        obs_id=img.obs_id,
        detector=img.detector,
        mjd=img.mjd,
        release=release,
        ra=ra,
        dec=dec,
        x=x,
        y=y,
        wavelength_um=wave[0] if wave else None,
        bandwidth_um=wave[1] if wave else None,
        flux_mjy=flux * to_mjy if ok else None,
        flux_err_mjy=err * to_mjy if ok and math.isfinite(err) else None,
        sky_mjy_sr=sky if math.isfinite(sky) else None,
        aperture_correction=correction,
        flags=tuple(sorted(flags)),
    )


def propagate(ra: float, dec: float, pm: tuple[float, float, float] | None, mjd: float) -> tuple[float, float]:
    """Linear proper motion: pm = (pm_ra_cosdec, pm_dec) in mas/yr at reference epoch MJD; no parallax."""
    if pm is None:
        return ra, dec
    if abs(dec) >= 89.99:
        raise ValueError("proper-motion propagation in RA is undefined at the celestial poles")
    pm_ra, pm_dec, epoch = pm
    dt = (mjd - epoch) / 365.25
    return (ra + pm_ra / 3.6e6 / math.cos(math.radians(dec)) * dt) % 360.0, dec + pm_dec / 3.6e6 * dt


def fit_corrections(samples: dict[int, list[tuple[float, float]]]) -> dict[int, tuple[float, float]]:
    """Per detector, aperture correction vs wavelength: corr = a + b * lambda, from (lambda, ratio) star samples.

    The PSF grows with wavelength (and differs between detectors), so one number per frame is too noisy and
    one per detector too coarse. A sigma-clipped straight line over all stars of all exposures of a detector
    is robust; with fewer than 20 samples or a narrow wavelength span the slope is 0 (median only).
    """
    out = {}
    for det, pairs in samples.items():
        lam = np.array([p[0] for p in pairs], dtype=float)
        r = np.array([p[1] for p in pairs], dtype=float)
        keep = np.isfinite(lam) & np.isfinite(r) & (r >= 1.0) & (r <= 3.0)
        lam, r = lam[keep], r[keep]
        if r.size < MIN_CORRECTION_STARS:
            continue
        a, b = float(np.median(r)), 0.0
        if r.size >= 20 and np.ptp(lam) > 0.05 * float(np.median(lam)):
            for _ in range(3):
                b, a = (float(v) for v in np.polyfit(lam, r, 1))
                res = r - (a + b * lam)
                mad = 1.4826 * np.median(np.abs(res - np.median(res))) or 1e-9
                ok = np.abs(res) <= 3 * mad
                if ok.all() or ok.sum() < 20:
                    break
                lam, r = lam[ok], r[ok]
                b, a = (float(v) for v in np.polyfit(lam, r, 1))  # the line of the kept stars
        out[det] = (a, b)
    return out


def _apply_corrections(points: list[ForcedFlux], fits: dict[int, tuple[float, float]]) -> list[ForcedFlux]:
    out = []
    for p in points:
        if p.flux_mjy is None:
            out.append(p)
            continue
        if p.detector not in fits:
            flags = tuple(sorted({*p.flags, "no_aperture_correction"}))
            out.append(replace(p, aperture_correction=None, flags=flags))
            continue
        a, b = fits[p.detector]
        c = min(3.0, max(1.0, a + b * p.wavelength_um if p.wavelength_um is not None else a))
        err = None if p.flux_err_mjy is None else p.flux_err_mjy * c
        out.append(replace(p, flux_mjy=p.flux_mjy * c, flux_err_mjy=err, aperture_correction=c))
    return out


def flag_spectral_outliers(points: list[ForcedFlux], window_um: float = 0.02, nsigma: float = 5.0) -> list[ForcedFlux]:
    """Flag points far from their same-season neighbours at almost the same wavelength (cosmic rays, glitches).

    Neighbours must be in the same season so that a variable star's real changes are not flagged.
    """
    from ..build import season_index

    out = list(points)
    if not points:
        return out
    seasons = np.asarray(season_index([p.mjd for p in points]))
    for season in np.unique(seasons):
        idx = [i for i in np.flatnonzero(seasons == season) if points[i].usable]
        idx.sort(key=lambda i: points[i].wavelength_um)
        lam = np.array([points[i].wavelength_um for i in idx])
        flux = np.array([points[i].flux_mjy for i in idx])
        lo = np.searchsorted(lam, lam - window_um, side="left")
        hi = np.searchsorted(lam, lam + window_um, side="right")
        for k, i in enumerate(idx):
            nb = np.concatenate([flux[lo[k] : k], flux[k + 1 : hi[k]]])
            if nb.size < 3:
                continue
            m = float(np.median(nb))
            scatter = 1.4826 * float(np.median(np.abs(nb - m)))
            p = points[i]
            tol = nsigma * max(scatter, p.flux_err_mjy or 0.0, 0.02 * abs(m))
            if abs(p.flux_mjy - m) > tol:
                out[i] = replace(p, flags=tuple(sorted({*p.flags, "spectral_outlier"})))
    return out


def spectrum_at(
    ra: float,
    dec: float,
    *,
    pm: tuple[float, float, float] | None = None,
    detectors: list[int] | None = None,
    max_frames: int | None = None,
    size_arcmin: float = 6.0,
) -> SpectrumResult:
    """Forced photometry of (ra, dec) on all SPHEREx exposures that cover it (WS1 search + pixels).

    ``pm`` = (pm_ra_cosdec, pm_dec, epoch_mjd) in mas/yr propagates a moving star to each exposure.
    ``max_frames`` keeps that many exposures evenly spread in time (all by default).
    The patch (``size_arcmin``, default 6') holds the field stars used for the aperture correction, fitted
    per detector against wavelength over all exposures (``fit_corrections``).
    """
    from ..data import cutouts, fits_io, irsa

    # A fast mover can be arcminutes away from a J2000 position: search and cut out around where it is in
    # the SPHEREx era (mission midpoint), then propagate per exposure below.
    era_ra, era_dec = propagate(ra, dec, pm, SPHEREX_ERA_MJD)
    found = irsa.search_frames(era_ra, era_dec, detectors=detectors).frames
    unique: dict[tuple[str, int], FrameRef] = {}
    for f in found:
        k = (f.obs_id, f.detector)
        if k not in unique or RELEASE_PREFERENCE.get(f.release, 9) < RELEASE_PREFERENCE.get(unique[k].release, 9):
            unique[k] = f
    refs = sorted(unique.values(), key=lambda f: f.mjd)
    notes = [f"{len(refs)} SPHEREx exposures cover this position."]
    if max_frames and len(refs) > max_frames:
        idx = np.linspace(0, len(refs) - 1, max_frames).round().astype(int)
        refs = [refs[i] for i in sorted(set(idx))]
        notes.append(f"Measured {len(refs)} of them, evenly spread in time (max_frames).")
    if not refs:
        return SpectrumResult(ra, dec, [], [], ["No SPHEREx exposure covers this position."])

    if pm is not None:
        mid = float(np.median([f.mjd for f in refs]))
        era_ra, era_dec = propagate(ra, dec, pm, mid)
    paths, failed = cutouts.fetch_frames_report(refs, era_ra, era_dec, size_arcmin)
    if len(paths) != len(refs):
        raise RuntimeError(f"fetch_frames_report returned {len(paths)} paths for {len(refs)} frames")
    failures = [(f"{f.obs_id}D{f.detector}", why) for f, why in failed]
    points: list[ForcedFlux] = []
    samples: dict[int, list[tuple[float, float]]] = defaultdict(list)
    for ref, path in zip(refs, paths, strict=True):
        if path is None:
            continue
        fid = f"{ref.obs_id}D{ref.detector}"
        try:  # one unreadable or odd file must not abort a 400-exposure spectrum
            img = fits_io.read_spherex(path)
            pl = planes(img)
            r_t, d_t = propagate(ra, dec, pm, img.mjd)
            p = measure(img, r_t, d_t, frame_id=fid, release=ref.release, correction=1.0, pl=pl)
            if p is None:
                failures.append((fid, "position off the downloaded pixels"))
                continue
            if p.wavelength_um is not None:
                samples[p.detector] += [(p.wavelength_um, r) for r in correction_ratios(pl, exclude=(p.x, p.y))]
        except (OSError, KeyError, ValueError, IndexError) as e:
            failures.append((fid, f"{type(e).__name__}: {e}"))
            continue
        points.append(p)
    fits = fit_corrections(samples)
    pooled = fit_corrections({0: [s for det_samples in samples.values() for s in det_samples]}).get(0)
    for det, (a, b) in sorted(fits.items()):
        n = len(samples[det])
        notes.append(f"D{det} aperture correction = {a:.3f} + {b:.3f} * lambda[um] ({n} star samples).")
    missing = sorted({p.detector for p in points} - set(fits))
    if pooled is not None and missing:
        for det in missing:  # too few stars on this detector: use the all-detector fit (PSF grows with lambda)
            fits[det] = pooled
        notes.append(
            f"D{','.join(map(str, missing))}: too few field stars; aperture correction from the all-detector fit "
            f"{pooled[0]:.3f} + {pooled[1]:.3f} * lambda[um]."
        )
    points = flag_spectral_outliers(_apply_corrections(points, fits))
    points.sort(key=lambda p: (p.wavelength_um if p.wavelength_um is not None else 99.0, p.mjd))
    n_ok = sum(p.usable for p in points)
    notes.append(
        f"{n_ok} of {len(points)} measured points are usable (not saturated, not on bad pixels, inside the detector, "
        "with wavelength, consistent with same-season neighbours)."
    )
    if pm is not None:
        notes.append("Position propagated with proper motion to each exposure (no parallax).")
    return SpectrumResult(ra, dec, points, failures, notes)


def to_spectrum_points(result: SpectrumResult) -> list[SpectrumPoint]:
    """Usable points as the existing contract model (Candidate.spectrum); flags/MJD stay in the full result."""
    return [
        SpectrumPoint(
            frame_id=p.frame_id,
            wavelength_um=p.wavelength_um,
            bandwidth_um=p.bandwidth_um,
            flux_mjy=p.flux_mjy,
            flux_err_mjy=p.flux_err_mjy,
        )
        for p in result.points
        if p.usable
    ]
