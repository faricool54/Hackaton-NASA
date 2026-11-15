"""Read SPHEREx Level-2 multi-extension FITS files (WS1).

Layout verified on real DR1 and QR3 files and on IRSA IBE cutouts (2026-11-14, docs/DATA.md §2/§3.0).
Always address HDUs by EXTNAME, never by index:

  0 PRIMARY   no data
  1 IMAGE     2040x2040 float32 (big-endian, uncompressed), MJy/sr, zodiacal light NOT subtracted
  2 FLAGS     2040x2040 int32 bitmask. Full files: CompImageHDU, RICE_1, ZTILE1=2040 ZTILE2=1 (one tile per row).
              IBE cutouts: plain, uncompressed ImageHDU. astropy reads both transparently.
  3 VARIANCE  float32, (MJy/sr)^2
  4 ZODI      float32, MJy/sr zodiacal model (subtract it yourself: IMAGE - ZODI)
  5 EPSF      effective-PSF table (451 rows in D3, ~3.9 MB; IBE cutouts include it whole). Older QR files: 'PSF'.
  6 WCS-WAVE  per-pixel wavelength lookup table (last HDU of the file, 5760 B), see below.

IMAGE header (useful keys): OBSID, DETECTOR (1-3 SWIR, 4-6 MWIR), BUNIT, PSF_FWHM, OMEGA_MEDIAN, DETCOORD.
Celestial WCS: CTYPE = RA---TAN-SIP -> ``astropy.wcs.WCS(full IMAGE header)`` (SIP is applied, as it must be).
The byte where IMAGE data starts depends on the header length (28800 in D1/D2, 25920 in D3-D6 files we read):
parse the header, never hardcode it.

Time (verified on DR1 + QR3 headers): ``MJD-OBS`` == ``MJD-BEG`` is the START of the exposure, ``MJD-AVG`` the
midpoint (== (MJD-OBS + MJD-END) / 2), ``MJD-END`` the end; ``DATE-OBS``/``DATE-AVG``/``DATE-END`` are the ISO
versions. ``XPOSURE`` (113.58 s) is the integration time, slightly shorter than MJD-END - MJD-OBS (115.1 s).
``DATE`` is the FILE creation date, not the observation date: never use it. SIA2 ``(t_min + t_max) / 2``
equals MJD-AVG to ~1e-6 d. ``read_spherex`` uses :func:`mid_exposure_mjd`.

Wavelength (``WCS-WAVE`` + alternate WCS ``W`` of the IMAGE header): SPHEREx has a linear variable filter, so each
pixel sees a different wavelength. ``WCS-WAVE`` holds one row with columns ``X`` (nX nodes), ``Y`` (nY nodes) and
``VALUES`` with ``TDIM3 = (2, nX, nY)`` (numpy shape ``(nY, nX, 2)``: ``[..., 0]`` = central wavelength,
``[..., 1]`` = bandwidth, both in um). The nodes are 1-based pixel coordinates of the FULL 2040x2040 DETECTOR.
The grid depends on the detector (D1 9x9, D2 11x11, D3 9x14, D4 13x20, D5 11x11, D6 9x9): it is read from the
file, never assumed. Near the detector edges the table goes 10-25 nm beyond the nominal band and beyond SIA
``em_min``/``em_max`` (e.g. D2 table 1.086-1.668 um vs SIA 1.103-1.650 um). The IMAGE header maps array pixels to table coordinates with ``CTYPEiW = 'WAVE-TAB'``
(FITS Paper III -TAB): ``psi_i = CDELTiW * (p_i - CRPIXiW) + CRVALiW`` with ``p_i`` the 1-based pixel. In a full
file ``CRPIXiW = CRVALiW = 1`` (identity); an IBE cutout keeps the table untouched and shifts ``CRPIXiW`` (and
``CRPIXi``, ``CRPIXiA``) by the cutout origin, e.g. ``CRPIX1W = -1604`` for a cutout whose first column is
0-based detector column 1605. Interpolation is bilinear (multilinear -TAB lookup).

Sub-image convention (IBE cutouts AND our own S3-range "patches"): a sub-image whose pixel [0, 0] is the 0-based
detector pixel (x0, y0) must carry the parent's IMAGE header with ``CRPIXi``, ``CRPIXiA`` and ``CRPIXiW`` all
decreased by x0 (i=1) / y0 (i=2) and the parent's ``WCS-WAVE`` HDU copied verbatim. :func:`detector_pixel`
uses the ``W`` keys; if they are missing it falls back to the ``A`` keys (0-based detector pixels, linear); a
header with neither is accepted only when its array covers the whole table (a full detector frame).

The IRSA tutorial computes the same thing with ``WCS(header, fobj=hdul, key="W")`` and ``wcs.sip = None``
(:func:`spectral_wcs`). Disabling SIP matters: astropy attaches the celestial SIP polynomials to every alternate
WCS (``A`` and ``W`` too) and that shifts the wavelength by up to ~15 nm in D3. The default path here is our own
bilinear lookup (:func:`wavelength_from_table`), which matches the tutorial to < 1e-12 um on real data, needs no
HDUList, and is what a browser can reproduce from a 5760-byte Range read of the file tail.
"""

from __future__ import annotations

import logging
import math
import warnings
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import numpy.typing as npt
from astropy.io import fits
from astropy.wcs import WCS, FITSFixedWarning

log = logging.getLogger(__name__)

WAVE_EXTNAME = "WCS-WAVE"
SIP_KEY_PREFIXES = ("A_", "B_", "AP_", "BP_")


@dataclass(frozen=True, eq=False)
class WaveTable:
    """The ``WCS-WAVE`` lookup table of one detector.

    ``x_nodes``/``y_nodes`` are 1-based FULL-detector pixel coordinates; ``wavelength``/``bandwidth`` [um] have
    shape ``(len(y_nodes), len(x_nodes))``.
    """

    x_nodes: np.ndarray
    y_nodes: np.ndarray
    wavelength: np.ndarray
    bandwidth: np.ndarray

    @classmethod
    def from_hdu(cls, hdu: fits.BinTableHDU) -> WaveTable:
        """Parse a ``WCS-WAVE`` HDU. The grid shape comes from the columns (``TDIM``), never assumed."""
        row = hdu.data[0]
        x_nodes = np.asarray(row["X"], dtype=float).ravel()
        y_nodes = np.asarray(row["Y"], dtype=float).ravel()
        values = np.asarray(row["VALUES"], dtype=float)  # astropy applies TDIM '(2,nX,nY)' -> (nY, nX, 2)
        expected = (len(y_nodes), len(x_nodes), 2)
        if values.ndim == 1 and values.size == math.prod(expected):  # TDIM lost: Paper III order (2, nX, nY)
            values = values.reshape(expected)
        if values.shape != expected:
            raise ValueError(f"{WAVE_EXTNAME}: VALUES shape {values.shape} != {expected} from X/Y (check TDIM)")
        if np.any(np.diff(x_nodes) <= 0) or np.any(np.diff(y_nodes) <= 0):
            raise ValueError(f"{WAVE_EXTNAME}: X/Y nodes must be strictly increasing")
        return cls(x_nodes, y_nodes, values[..., 0].copy(), values[..., 1].copy())

    @property
    def shape(self) -> tuple[int, int]:
        """(nX, nY), the same order as ``TDIM`` (e.g. (9, 14) for D3)."""
        return len(self.x_nodes), len(self.y_nodes)

    def at_detector(self, px: npt.ArrayLike, py: npt.ArrayLike) -> tuple[np.ndarray, np.ndarray]:
        """Bilinear (wavelength, bandwidth) [um] at 1-based detector pixel coordinates.

        Within half a pixel outside the outermost nodes the edge cell is extrapolated linearly (the same as
        astropy/wcslib); further out the result is NaN.
        """
        px = np.asarray(px, dtype=float)
        py = np.asarray(py, dtype=float)
        tx, i = _cell(self.x_nodes, px)
        ty, j = _cell(self.y_nodes, py)
        lam = _bilinear(self.wavelength, i, j, tx, ty)
        bw = _bilinear(self.bandwidth, i, j, tx, ty)
        outside = (
            (px < self.x_nodes[0] - 0.5)
            | (px > self.x_nodes[-1] + 0.5)
            | (py < self.y_nodes[0] - 0.5)
            | (py > self.y_nodes[-1] + 0.5)
            | ~np.isfinite(px)
            | ~np.isfinite(py)
        )
        return np.where(outside, np.nan, lam), np.where(outside, np.nan, bw)


def _cell(nodes: np.ndarray, p: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    safe = np.where(np.isfinite(p), p, nodes[0])
    i = np.clip(np.searchsorted(nodes, safe, side="right") - 1, 0, len(nodes) - 2)
    return (safe - nodes[i]) / (nodes[i + 1] - nodes[i]), i


def _bilinear(v: np.ndarray, i: np.ndarray, j: np.ndarray, tx: np.ndarray, ty: np.ndarray) -> np.ndarray:
    return (
        v[j, i] * (1 - tx) * (1 - ty)
        + v[j, i + 1] * tx * (1 - ty)
        + v[j + 1, i] * (1 - tx) * ty
        + v[j + 1, i + 1] * tx * ty
    )


def _as_table(wave: fits.BinTableHDU | WaveTable) -> WaveTable:
    return wave if isinstance(wave, WaveTable) else WaveTable.from_hdu(wave)


def _linear_alt(header: fits.Header, key: str) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray] | None:
    """(CRPIX, CDELT, CRVAL, PC) of a 2-axis linear alternate WCS, or None if its CRPIX cards are missing."""
    if f"CRPIX1{key}" not in header or f"CRPIX2{key}" not in header:
        return None
    crpix = np.array([float(header[f"CRPIX{i}{key}"]) for i in (1, 2)])
    cdelt = np.array([float(header.get(f"CDELT{i}{key}", 1.0)) for i in (1, 2)])
    crval = np.array([float(header.get(f"CRVAL{i}{key}", 0.0)) for i in (1, 2)])
    pc = np.array([[float(header.get(f"PC{i}_{j}{key}", 1.0 if i == j else 0.0)) for j in (1, 2)] for i in (1, 2)])
    return crpix, cdelt, crval, pc


def detector_pixel(
    header: fits.Header, x: npt.ArrayLike, y: npt.ArrayLike, table: WaveTable | None = None
) -> tuple[np.ndarray, np.ndarray]:
    """0-based (x=column, y=row) pixel of THIS array -> 1-based pixel of the full detector (the table frame).

    Uses the ``W`` alternate WCS (``WAVE-TAB``) of the IMAGE header; falls back to ``A`` (0-based detector
    pixels). Without either, the array must be a full frame (NAXISn equal to the last table node).
    """
    x, y = np.broadcast_arrays(np.asarray(x, dtype=float), np.asarray(y, dtype=float))
    p = np.stack([x + 1.0, y + 1.0])  # FITS 1-based
    mapped: dict[str, np.ndarray] = {}
    for key, offset in (("W", 0.0), ("A", 1.0)):
        alt = _linear_alt(header, key)
        if alt is None:
            continue
        crpix, cdelt, crval, pc = alt
        d = p - crpix.reshape((2,) + (1,) * x.ndim)
        inter = np.einsum("ij,j...->i...", pc, d) * cdelt.reshape((2,) + (1,) * x.ndim)
        mapped[key] = inter + crval.reshape((2,) + (1,) * x.ndim) + offset
    if "W" in mapped and "A" in mapped and not np.allclose(mapped["W"], mapped["A"], rtol=0, atol=1e-6):
        # A sub-image writer that shifted CRPIXn/CRPIXnA but forgot CRPIXnW (or vice versa) would otherwise
        # yield a wrong wavelength silently (118 nm off in a measured D3 case).
        raise ValueError(
            "Inconsistent sub-image header: the 'W' and 'A' alternate WCSs place this array at different detector "
            "pixels (CRPIXnW and CRPIXnA must be shifted together, see errante.data.fits_io)."
        )
    if mapped:
        out = mapped.get("W", mapped.get("A"))
        return out[0], out[1]
    if table is not None and (header.get("NAXIS1"), header.get("NAXIS2")) == (
        int(table.x_nodes[-1]),
        int(table.y_nodes[-1]),
    ):
        return p[0], p[1]
    raise ValueError(
        "Cannot place this array on the detector: the IMAGE header has neither CRPIXnW nor CRPIXnA "
        "and the array is not a full frame (see the sub-image convention in errante.data.fits_io)."
    )


def wavelength_from_table(
    wave: fits.BinTableHDU | WaveTable,
    header: fits.Header,
    x: npt.ArrayLike,
    y: npt.ArrayLike,
) -> tuple[np.ndarray, np.ndarray]:
    """Central wavelength and bandwidth [um] at 0-based array pixel(s) (x=column, y=row). Pure, vectorized.

    ``wave`` is the ``WCS-WAVE`` HDU (or a parsed :class:`WaveTable`), ``header`` the IMAGE header of the same
    file: a full frame, an IBE cutout or a patch following the sub-image convention (module docstring).
    Returns NaN for pixels more than half a pixel off the detector.
    """
    table = _as_table(wave)
    px, py = detector_pixel(header, x, y, table)
    return table.at_detector(px, py)


def spectral_wcs(header: fits.Header, wave: fits.BinTableHDU | fits.HDUList) -> WCS:
    """The IRSA-tutorial spectral WCS: ``WCS(header, fobj=..., key='W')`` with SIP disabled.

    Kept to cross-check :func:`wavelength_from_table`; ``pixel_to_world_values(x, y)`` returns (um, um).
    """
    hdr = header.copy()
    for k in [k for k in hdr if k.startswith(SIP_KEY_PREFIXES)]:
        del hdr[k]  # astropy would otherwise attach the celestial SIP to the 'W' WCS (and log about it)
    fobj = wave if isinstance(wave, fits.HDUList) else fits.HDUList([fits.PrimaryHDU(), wave])
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", FITSFixedWarning)
        sw = WCS(hdr, fobj=fobj, key="W")
    sw.sip = None
    return sw


def celestial_wcs(header: fits.Header) -> WCS:
    """Primary RA/Dec WCS (TAN-SIP) of an IMAGE header, without astropy's 'datfix' chatter."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", FITSFixedWarning)
        return WCS(header)


def _sky_to_array_pixel(wcs: WCS, header: fits.Header, ra: float, dec: float) -> tuple[float, float] | None:
    """0-based array pixel of (ra, dec), or None if it is off the array.

    Far from the field the iterative SIP inversion may not converge (astropy warns and returns its last guess),
    so the result is accepted only if it maps back to (ra, dec) within 1 arcsec.
    """
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")  # expected non-convergence / NaN warnings for off-field positions
        x, y = (float(v) for v in wcs.world_to_pixel_values(ra, dec))
        if not (math.isfinite(x) and math.isfinite(y)):
            return None
        nx, ny = int(header.get("NAXIS1", 0)), int(header.get("NAXIS2", 0))
        if not (-0.5 <= x <= nx - 0.5 and -0.5 <= y <= ny - 0.5):
            return None
        ra2, dec2 = (float(v) for v in wcs.pixel_to_world_values(x, y))
    if _separation_deg(ra, dec, ra2, dec2) > 1 / 3600:
        return None
    return x, y


def _separation_deg(ra1: float, dec1: float, ra2: float, dec2: float) -> float:
    r1, d1, r2, d2 = map(math.radians, (ra1, dec1, ra2, dec2))
    s = math.sin((d2 - d1) / 2) ** 2 + math.cos(d1) * math.cos(d2) * math.sin((r2 - r1) / 2) ** 2
    return math.degrees(2 * math.asin(min(1.0, math.sqrt(s))))


def wavelength_at(source: str | Path | fits.HDUList, ra: float, dec: float) -> tuple[float, float] | None:
    """Central wavelength and bandwidth [um] seen at sky position (ra, dec) [deg, ICRS] in one file.

    ``source`` is a path or an open HDUList of a full L2 file, an IBE cutout or a patch (module docstring).
    Returns None if (ra, dec) falls outside this file's pixel array. Use the position of the object AT THIS
    EPOCH (propagate proper motion): along the detector y axis the wavelength changes by 0.19 (D1), 0.28 (D2),
    0.39 (D3), 0.70 (D4), 0.31 (D5) and 0.30 (D6) nm per pixel.
    """
    if isinstance(source, fits.HDUList):
        return _wavelength_at_hdul(source, ra, dec)
    with fits.open(source, memmap=True, lazy_load_hdus=True) as hdul:
        return _wavelength_at_hdul(hdul, ra, dec)


def _wavelength_at_hdul(hdul: fits.HDUList, ra: float, dec: float) -> tuple[float, float] | None:
    header = hdul["IMAGE"].header
    pix = _sky_to_array_pixel(celestial_wcs(header), header, ra, dec)
    if pix is None:
        return None
    lam, bw = wavelength_from_table(hdul[WAVE_EXTNAME], header, *pix)
    if not (np.isfinite(lam) and np.isfinite(bw)):
        return None
    return float(lam), float(bw)


def mid_exposure_mjd(header: fits.Header) -> tuple[float, str]:
    """Mid-exposure MJD and the rule used to get it.

    Order: ``MJD-AVG``; else ``(MJD-OBS + MJD-END) / 2``; else ``MJD-OBS + XPOSURE / 2 / 86400`` (~0.8 s earlier
    than MJD-AVG on real files, because XPOSURE < MJD-END - MJD-OBS); else ``MJD-OBS`` (start, up to ~1 min off).
    """
    if "MJD-AVG" in header:
        return float(header["MJD-AVG"]), "MJD-AVG"
    start = float(header["MJD-OBS"])
    if "MJD-END" in header:
        return (start + float(header["MJD-END"])) / 2, "(MJD-OBS+MJD-END)/2"
    if "XPOSURE" in header:
        return start + float(header["XPOSURE"]) / 2 / 86400, "MJD-OBS+XPOSURE/2"
    return start, "MJD-OBS"


@dataclass
class SpherexImage:
    data: np.ndarray  # MJy/sr, FITS orientation (row 0 = bottom)
    flags: np.ndarray | None
    variance: np.ndarray | None
    zodi: np.ndarray | None
    wcs: WCS
    header: fits.Header
    obs_id: str
    detector: int
    mjd: float  # MID-exposure MJD (see mid_exposure_mjd); the start is extra['mjd_obs']
    date_obs: str  # ISO UTC of the SAME instant as ``mjd`` (DATE-AVG); the start (DATE-OBS) is extra['date_beg']
    source: str = ""
    extra: dict = field(default_factory=dict)
    wave: WaveTable | None = None  # WCS-WAVE table (None if the file has no WCS-WAVE HDU)

    @property
    def data_minus_zodi(self) -> np.ndarray:
        return self.data - self.zodi if self.zodi is not None else self.data

    def wavelength_at(self, ra: float, dec: float) -> tuple[float, float] | None:
        """(wavelength, bandwidth) [um] at (ra, dec), or None if outside the array / no WCS-WAVE table."""
        if self.wave is None:
            return None
        pix = _sky_to_array_pixel(self.wcs, self.header, ra, dec)
        if pix is None:
            return None
        lam, bw = wavelength_from_table(self.wave, self.header, *pix)
        return (float(lam), float(bw)) if np.isfinite(lam) and np.isfinite(bw) else None


def _maybe(hdul: fits.HDUList, name: str) -> np.ndarray | None:
    try:
        return np.asarray(hdul[name].data)
    except KeyError:
        return None


_MJD_EPOCH = datetime(1858, 11, 17)


def mid_exposure_date(header: fits.Header, mjd: float, mjd_source: str) -> str:
    """ISO UTC string of the same instant as ``mjd`` (from :func:`mid_exposure_mjd`).

    ``DATE-AVG`` when ``mjd`` came from ``MJD-AVG``; ``DATE-OBS`` when only the start is known; otherwise
    computed from ``mjd`` (millisecond precision, like the headers).
    """
    if mjd_source == "MJD-AVG" and "DATE-AVG" in header:
        return str(header["DATE-AVG"])
    if mjd_source == "MJD-OBS" and "DATE-OBS" in header:
        return str(header["DATE-OBS"])
    return (_MJD_EPOCH + timedelta(milliseconds=round(mjd * 86_400_000))).isoformat(timespec="milliseconds")


def read_spherex(path: str | Path, with_planes: bool = True) -> SpherexImage:
    """Read a full file, an IRSA cutout or a patch (same HDU names, smaller arrays).

    ``mjd`` is the MID-exposure time (``MJD-AVG``, see :func:`mid_exposure_mjd`) and ``date_obs`` the ISO string
    of that same instant (``DATE-AVG``). ``extra`` keeps the raw ``mjd_obs`` and ``date_beg`` (start),
    ``mjd_end``, ``date_avg``, ``xposure_s`` and ``mjd_source`` (the rule that was used). A ``WCS-WAVE`` table
    that cannot be parsed leaves ``wave=None`` (reason in ``extra['wave_error']``) instead of failing the read.
    """
    with fits.open(path, memmap=False) as hdul:
        hdr = hdul["IMAGE"].header
        mjd, mjd_source = mid_exposure_mjd(hdr)
        wave_error = None
        try:
            wave = WaveTable.from_hdu(hdul[WAVE_EXTNAME])
        except KeyError:
            wave = None
        except Exception as e:  # one odd file must not abort a whole field build (astropy raises VerifyError on
            # an unparsable card and AttributeError on a _CorruptedHDU, not only ValueError: review 2026-11-15)
            wave, wave_error = None, f"{type(e).__name__}: {e}"
            log.warning("%s: unusable %s table (%s); wavelength lookup disabled", path, WAVE_EXTNAME, wave_error)
        extra = {
            "mjd_obs": float(hdr["MJD-OBS"]) if "MJD-OBS" in hdr else None,
            "mjd_end": float(hdr["MJD-END"]) if "MJD-END" in hdr else None,
            "date_beg": str(hdr["DATE-OBS"]) if "DATE-OBS" in hdr else None,
            "date_avg": str(hdr["DATE-AVG"]) if "DATE-AVG" in hdr else None,
            "xposure_s": float(hdr["XPOSURE"]) if "XPOSURE" in hdr else None,
            "mjd_source": mjd_source,
        }
        if wave_error:
            extra["wave_error"] = wave_error
        img = SpherexImage(
            data=np.asarray(hdul["IMAGE"].data, dtype=np.float32),
            flags=_maybe(hdul, "FLAGS") if with_planes else None,
            variance=_maybe(hdul, "VARIANCE") if with_planes else None,
            zodi=_maybe(hdul, "ZODI") if with_planes else None,
            wcs=celestial_wcs(hdr),
            header=hdr.copy(),
            obs_id=str(hdr.get("OBSID", "")),
            detector=int(hdr.get("DETECTOR", 0)),
            mjd=mjd,
            date_obs=mid_exposure_date(hdr, mjd, mjd_source),
            source=str(path),
            extra=extra,
            wave=wave,
        )
    return img
