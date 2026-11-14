"""Read SPHEREx Level-2 multi-extension FITS files (WS1).

Structure verified on a real DR1 file (docs/DATA.md):
  0 PRIMARY   (no data)
  1 IMAGE     2040x2040 float32, MJy/sr, zodiacal light NOT subtracted
  2 FLAGS     2040x2040 int32 bitmask (RICE tile-compressed, astropy handles it)
  3 VARIANCE  2040x2040 float32, (MJy/sr)^2
  4 ZODI      2040x2040 float32, zodiacal model (subtract it yourself)
  5 EPSF      PSF table   (named 'PSF' in older QR files)
  6 WCS-WAVE  per-pixel wavelength lookup table (9x9 grid in DR1, 11x11 in QR)
Useful IMAGE header keys: MJD-OBS, DATE-OBS, DETECTOR, OBSID, PSF_FWHM, BUNIT,
CTYPE = RA---TAN-SIP (use astropy WCS with the full header).
DATE is the FILE creation date, not the observation date: never use it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from astropy.io import fits
from astropy.wcs import WCS


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
    mjd: float
    date_obs: str
    source: str = ""
    extra: dict = field(default_factory=dict)

    @property
    def data_minus_zodi(self) -> np.ndarray:
        return self.data - self.zodi if self.zodi is not None else self.data


def _maybe(hdul: fits.HDUList, name: str) -> np.ndarray | None:
    try:
        return np.asarray(hdul[name].data)
    except KeyError:
        return None


def read_spherex(path: str | Path, with_planes: bool = True) -> SpherexImage:
    """Read a full file or an IRSA cutout (same HDU layout, smaller arrays)."""
    with fits.open(path, memmap=False) as hdul:
        hdr = hdul["IMAGE"].header
        img = SpherexImage(
            data=np.asarray(hdul["IMAGE"].data, dtype=np.float32),
            flags=_maybe(hdul, "FLAGS") if with_planes else None,
            variance=_maybe(hdul, "VARIANCE") if with_planes else None,
            zodi=_maybe(hdul, "ZODI") if with_planes else None,
            wcs=WCS(hdr),
            header=hdr.copy(),
            obs_id=str(hdr.get("OBSID", "")),
            detector=int(hdr.get("DETECTOR", 0)),
            mjd=float(hdr["MJD-OBS"]),
            date_obs=str(hdr.get("DATE-OBS", "")),
            source=str(path),
        )
    return img


def wavelength_at(path: str | Path, ra: float, dec: float) -> tuple[float, float] | None:
    """Central wavelength and bandwidth [um] at (ra, dec) from the WCS-WAVE table.

    TODO(WS1/WS3): the IRSA tutorial ("Introduction to SPHEREx Spectral Images")
    builds it as ``WCS(header=hdul["IMAGE"].header, fobj=hdul, key="W")``,
    sets ``wcs.sip = None`` and calls ``pixel_to_world(x, y)``. Verify on a real
    file and on a cutout (cutouts shift CRPIX), then implement + test.
    """
    raise NotImplementedError("WS1: wavelength_at")
