"""Fast SPHEREx spectrum of any sky position from the DR1 all-sky HiPS FITS cube on S3 (WS1).

The SPHEREx DR1 all-sky cube is a static coadd published as 12 288 HiPS tiles (HEALPix
order 5, NESTED), one 320 909 760-byte FITS file per tile. Each tile holds 102 planes of
512x512 pixels (one plane per spectral channel, 0.75-5.0 um, 12.88"/px), so the spectrum of
one sky pixel is 102 floats spread 1 MiB apart. This module reads exactly those bytes with
HTTP Range requests (S3 serves Range + CORS; no IRSA query service is involved), so it works
when IRSA SIA/TAP are down: ~1 s on open connections, ~3 s cold (measured from Buenos Aires).

Layout of a tile (identical in all 47 tiles walked on 2026-11-14; see DR1_LAYOUT):

  HDU 0  PRIMARY            NAXIS=0; MJD-BEG/MJD-END of the inputs, BLANKCH='D3:17,D4:01'
  HDU 1  IMAGE              float32 (102, 512, 512), BUNIT='MJy/sr', zodiacal light already removed
  HDU 2  NHITS              int32   (102, 512, 512), input samples per pixel (0 <=> IMAGE is NaN)
  HDU 3  FLAGS              int32   (102, 512, 512), uncompressed, same MSKNnnnn bits as L2
  HDU 4  SPECTRAL_CHANNELS  table: DETECTOR, SUBCHAN, WAVELENGTH, WL_MIN, WL_MAX, R, R_STD, BANDWIDTH
  HDU 5  WCS-WAVE           table: PLANE (1..102), WAVELENGTHS, BANDWIDTHS [um]

The celestial WCS is ``RA---HPX``/``DEC--HPX`` (H=4, K=3, PC rotated 45 deg): the HEALPix
projection, in which every HEALPix pixel is a square. It cannot be used blindly: for tiles
that straddle the x = +-180 deg seam of the projection plane (e.g. Npix 6912 at RA=180),
wcslib's world->pixel lands ~65 000 px away and its pixel->world gives NaN for half the tile.
We therefore map (ra, dec) -> (tile, pixel) with HEALPix itself (pure numpy, below):

  * tile  = NESTED index at order 5 (``ang2pix_nest``);
  * pixel = NESTED (face, ix, iy) at order 5 + log2(512) = 14; inside the tile
    ``x = iy & 511`` (FITS axis 1, column) and ``y = 511 - (ix & 511)`` (FITS axis 2, row),
    both 0-based. Checked against the tiles' own HPX WCS on 17 tiles covering all 12 base
    faces (4000 points each, 0 mismatches) and on 80 isolated Gaia stars (G 10.5-12.5) in 10
    fields incl. both poles and the RA=0/180 seams: the predicted pixel is the brightest in 88 %
    of star-planes, flux centroid 0.15 px (median) from the star.

Planes 50 and 51 (D3 channel 17 and D4 channel 1, the dichroic channels) are all-NaN on
purpose (``BLANKCH`` in the primary header, and the HiPS ``properties``). Plane k belongs to
detector ``k // 17 + 1``, channel ``k % 17 + 1`` (checked against SPECTRAL_CHANNELS).
Saturated stars (Barnard's Star, R Dra, ...) are NaN holes with NHITS = 0: the coadd rejects
their core samples, so their spectrum at the star's pixel is mostly invalid.

Caching: tile headers (HDU directory + WCS-WAVE bytes, ~40 KB) under ``CACHE_DIR/cube/dir`` and
finished spectra under ``CACHE_DIR/cube/spectra`` (a fixed release: entries never expire). A cold
tile is read *speculatively*: its headers and the pixels at the offsets of :data:`DR1_LAYOUT` are
requested in one parallel round and the pixels are kept only if the headers match that layout.
If S3 fails, the same bytes are read from the IRSA HiPS copy (byte-identical, verified).
"""

from __future__ import annotations

import hashlib
import io
import json
import math
import os
import re
import threading
import time
import warnings
from collections import OrderedDict
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import requests
from astropy.io import fits

from .. import settings
from . import s3range
from .cutouts import TRANSIENT_BODY_ERRORS, KeyedLocks
from .s3range import HduDirectory, HduInfo, RangeReader

__all__ = [
    "BLANK_PLANES",
    "CUBE_ORDER",
    "CUBE_PREFIX",
    "DR1_LAYOUT",
    "N_PLANES",
    "TILE_WIDTH",
    "CubeSpectrum",
    "CubeTile",
    "TilePixel",
    "ang2pix_nest",
    "blank_planes",
    "cube_spectrum",
    "cube_tile",
    "irsa_url_for_key",
    "layout_of",
    "pix2ang_nest",
    "read_url_range",
    "sky_to_tile_pixel",
    "tile_directory",
    "tile_key",
    "tile_pixel_to_sky",
    "wavelength_table",
]

CUBE_PREFIX = os.environ.get("ERRANTE_CUBE_PREFIX", "dr1/hips5_cube/hips_20261026").strip("/")
"""S3 prefix of the DR1 cube release (key = <prefix>/Norder5/Dir<d>/Npix<n>_cube.fits)."""
IRSA_CUBE_BASE = os.environ.get(
    "ERRANTE_CUBE_IRSA_BASE", f"{settings.IRSA_BASE}/data/hips/SPHEREx/spherex_allsky_cube"
).rstrip("/")
"""IRSA copy of the same FITS tiles (byte-identical to S3, Range + CORS). Used as fallback."""
CUBE_ORDER = 5
TILE_WIDTH = 512
N_PLANES = 102
BLANK_PLANES = (50, 51)
"""Default when the primary header has no BLANKCH card: D3 ch17 and D4 ch1 (dichroic)."""
CHANNELS_PER_DETECTOR = 17
MAX_APERTURE_PX = 10
CUBE_PARALLEL = int(os.environ.get("ERRANTE_CUBE_PARALLEL", "32"))
"""Concurrent Range requests for one spectrum (102 planes x up to 3 extensions). Measured from a
Windows laptop in Buenos Aires (2026-11-14): each round of requests on open connections takes
~0.2-0.25 s, but opening a connection costs ~65 ms *serialised* (64 new connections: ~4.2 s, 16:
~1.5 s) and S3 closes idle keep-alive connections in < 20 s. So sporadic clicks pay the connection
cost again: 32 balances it (~2.5-3 s cold vs ~0.9 s on warm connections; 64: ~4.4 s / ~0.5 s).
Near S3 (the deploy host) both terms are much smaller. The shared S3 session pools 64 connections."""
RESULT_CACHE_VERSION = 1
RANGE_RETRIES = 4
FITS_BLOCK = 2880

_DTYPES = {8: ">u1", 16: ">i2", 32: ">i4", 64: ">i8", -32: ">f4", -64: ">f8"}
_BLANKCH = re.compile(r"D(\d)\s*:\s*(\d+)")


# --- HEALPix (NESTED), pure numpy ---------------------------------------------------
# Port of the nested branches of healpix_cxx loc2pix / pix2loc (Gorski et al. 2005).

_JRLL = np.array([2, 2, 2, 2, 3, 3, 3, 3, 4, 4, 4, 4], dtype=np.int64)
_JPLL = np.array([1, 3, 5, 7, 0, 2, 4, 6, 1, 3, 5, 7], dtype=np.int64)


def _check_order(order: int) -> int:
    order = int(order)
    if not 0 <= order <= 29:
        raise ValueError(f"HEALPix order must be in 0..29, got {order}")
    return order


def _spread_bits(v: np.ndarray) -> np.ndarray:
    """Interleave zeros: bit i of v -> bit 2i (v < 2**30)."""
    v = np.asarray(v, dtype=np.int64)
    out = np.zeros_like(v)
    for b in range(30):
        out |= ((v >> b) & 1) << (2 * b)
    return out


def _compress_bits(v: np.ndarray) -> np.ndarray:
    """Inverse of :func:`_spread_bits`: bit 2i of v -> bit i."""
    v = np.asarray(v, dtype=np.int64)
    out = np.zeros_like(v)
    for b in range(30):
        out |= ((v >> (2 * b)) & 1) << b
    return out


def _ang2xyf(order: int, ra, dec) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """(ix, iy, face) of the NESTED pixel containing (ra, dec) [deg] at ``order``."""
    nside = 1 << order
    ra = np.asarray(ra, dtype=np.float64)
    dec = np.asarray(dec, dtype=np.float64)
    if np.any(~np.isfinite(ra)) or np.any(~np.isfinite(dec)) or np.any(np.abs(dec) > 90.0):
        raise ValueError("ra/dec must be finite and |dec| <= 90")
    z = np.sin(np.radians(dec))
    za = np.abs(z)
    tt = np.mod(np.mod(ra, 360.0) / 90.0, 4.0)  # in [0, 4)

    # Equatorial region (|z| <= 2/3)
    t1 = nside * (0.5 + tt)
    t2 = nside * (z * 0.75)
    jp = np.floor(t1 - t2).astype(np.int64)  # ascending edge line index
    jm = np.floor(t1 + t2).astype(np.int64)  # descending edge line index
    ifp = jp >> order
    ifm = jm >> order
    face_eq = np.where(ifp == ifm, ifp | 4, np.where(ifp < ifm, ifp, ifm + 8))
    ix_eq = jm & (nside - 1)
    iy_eq = nside - (jp & (nside - 1)) - 1

    # Polar caps (|z| > 2/3); near the poles use cos(dec) to keep precision.
    ntt = np.minimum(3, np.floor(tt).astype(np.int64))
    tp = tt - ntt
    sth = np.cos(np.radians(dec))
    with np.errstate(invalid="ignore", divide="ignore"):
        tmp = np.where(za < 0.99, nside * np.sqrt(3.0 * (1.0 - za)), nside * sth / np.sqrt((1.0 + za) / 3.0))
    jp2 = np.minimum(np.floor(tp * tmp).astype(np.int64), nside - 1)
    jm2 = np.minimum(np.floor((1.0 - tp) * tmp).astype(np.int64), nside - 1)
    north = z >= 0
    face_po = np.where(north, ntt, ntt + 8)
    ix_po = np.where(north, nside - jm2 - 1, jp2)
    iy_po = np.where(north, nside - jp2 - 1, jm2)

    eq = za <= 2.0 / 3.0
    return np.where(eq, ix_eq, ix_po), np.where(eq, iy_eq, iy_po), np.where(eq, face_eq, face_po)


def _xyf2nest(order: int, ix, iy, face) -> np.ndarray:
    return (np.asarray(face, dtype=np.int64) << (2 * order)) + _spread_bits(ix) + (_spread_bits(iy) << 1)


def _nest2xyf(order: int, ipix) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    ipix = np.asarray(ipix, dtype=np.int64)
    npface = 1 << (2 * order)
    if np.any(ipix < 0) or np.any(ipix >= 12 * npface):
        raise ValueError(f"NESTED pixel out of range for order {order}")
    face = ipix >> (2 * order)
    sub = ipix & (npface - 1)
    return _compress_bits(sub), _compress_bits(sub >> 1), face


def _xyf2ang(order: int, ix, iy, face) -> tuple[np.ndarray, np.ndarray]:
    """(ra, dec) [deg] of the centre of NESTED pixel (ix, iy, face) at ``order``."""
    nside = 1 << order
    npix = 12 * nside * nside
    fact2 = 4.0 / npix
    fact1 = (nside << 1) * fact2
    ix = np.asarray(ix, dtype=np.int64)
    iy = np.asarray(iy, dtype=np.int64)
    face = np.asarray(face, dtype=np.int64)
    jr = (_JRLL[face] << order) - ix - iy - 1
    north = jr < nside
    south = jr > 3 * nside
    nr = np.where(north, jr, np.where(south, 4 * nside - jr, nside))
    tmp_cap = (nr * nr) * fact2
    z = np.where(north, 1.0 - tmp_cap, np.where(south, tmp_cap - 1.0, (2 * nside - jr) * fact1))
    sth = np.where(north | south, np.sqrt(np.clip(tmp_cap * (2.0 - tmp_cap), 0.0, None)), np.sqrt(1.0 - z * z))
    t = _JPLL[face] * nr + ix - iy
    t = np.where(t < 0, t + 8 * nr, t)
    with np.errstate(invalid="ignore", divide="ignore"):
        phi = np.where(nr == nside, 0.75 * (np.pi / 2) * t * fact1, (0.5 * (np.pi / 2) * t) / np.maximum(nr, 1))
    dec = np.degrees(np.arctan2(z, sth))
    ra = np.mod(np.degrees(phi), 360.0)
    return ra, dec


def ang2pix_nest(order: int, ra, dec):
    """HEALPix NESTED index of (ra, dec) [deg, ICRS] at ``order`` (int for scalars, else array)."""
    order = _check_order(order)
    pix = _xyf2nest(order, *_ang2xyf(order, ra, dec))
    return int(pix) if pix.ndim == 0 else pix


def pix2ang_nest(order: int, ipix) -> tuple:
    """(ra, dec) [deg] of the centre of NESTED pixel ``ipix`` at ``order``."""
    order = _check_order(order)
    ra, dec = _xyf2ang(order, *_nest2xyf(order, ipix))
    if np.ndim(ra) == 0:
        return float(ra), float(dec)
    return ra, dec


# --- HiPS tile geometry ---------------------------------------------------------------


@dataclass(frozen=True)
class TilePixel:
    """A pixel of a HiPS FITS tile: ``x`` = column (FITS axis 1), ``y`` = row (FITS axis 2), 0-based.

    Reading ``data[k, y, x]`` of the tile's (planes, rows, columns) array gives plane k.
    FITS 1-based pixel coordinates are (x + 1, y + 1).
    """

    order: int
    npix: int
    x: int
    y: int
    width: int = TILE_WIDTH


def _tile_bits(width: int) -> int:
    width = int(width)
    if width <= 0 or width & (width - 1):
        raise ValueError(f"tile width must be a power of 2, got {width}")
    return width.bit_length() - 1


def sky_to_tile_pixel(ra: float, dec: float, order: int = CUBE_ORDER, width: int = TILE_WIDTH) -> TilePixel:
    """Tile (NESTED index at ``order``) and in-tile pixel containing (ra, dec) [deg].

    HiPS FITS convention (checked against the tiles' HPX WCS, see module docs):
    x = iy & (w-1), y = (w-1) - (ix & (w-1)), with (ix, iy, face) at order + log2(w).
    """
    order = _check_order(order)
    bits = _tile_bits(width)
    porder = _check_order(order + bits)
    ix, iy, face = (int(v) for v in _ang2xyf(porder, float(ra), float(dec)))
    npix = int(_xyf2nest(order, ix >> bits, iy >> bits, face))
    w = 1 << bits
    return TilePixel(order, npix, iy & (w - 1), (w - 1) - (ix & (w - 1)), w)


def tile_pixel_to_sky(npix: int, x, y, order: int = CUBE_ORDER, width: int = TILE_WIDTH):
    """(ra, dec) [deg] of the centre of in-tile pixel(s) (x, y) (ints or int arrays) of tile ``npix``."""
    order = _check_order(order)
    bits = _tile_bits(width)
    porder = _check_order(order + bits)
    w = 1 << bits
    x = np.asarray(x, dtype=np.int64)
    y = np.asarray(y, dtype=np.int64)
    if np.any((x < 0) | (x >= w) | (y < 0) | (y >= w)):
        raise ValueError(f"pixel outside a {w}x{w} tile")
    tx, ty, face = (int(v) for v in _nest2xyf(order, int(npix)))
    ix = (tx << bits) | ((w - 1) - y)
    iy = (ty << bits) | x
    ra, dec = _xyf2ang(porder, ix, iy, np.full(np.shape(ix), face))
    if np.ndim(ra) == 0:
        return float(ra), float(dec)
    return ra, dec


def tile_key(npix: int, order: int = CUBE_ORDER) -> str:
    """S3 key of a cube tile: ``<CUBE_PREFIX>/Norder<o>/Dir<10000*(n//10000)>/Npix<n>_cube.fits``."""
    npix = int(npix)
    return f"{CUBE_PREFIX}/Norder{order}/Dir{(npix // 10000) * 10000}/Npix{npix}_cube.fits"


def irsa_url_for_key(key: str) -> str:
    """IRSA HiPS URL holding the same bytes as the S3 cube tile ``key``."""
    key = key.lstrip("/")
    if not key.startswith(CUBE_PREFIX + "/"):
        raise ValueError(f"not a cube tile key: {key}")
    return f"{IRSA_CUBE_BASE}/{key[len(CUBE_PREFIX) + 1 :]}"


@dataclass(frozen=True)
class CubeTile:
    order: int
    npix: int
    key: str

    @property
    def url(self) -> str:
        return f"{settings.S3_HTTPS}/{self.key}"

    @property
    def irsa_url(self) -> str:
        return irsa_url_for_key(self.key)

    def to_dict(self) -> dict:
        return {"order": self.order, "npix": self.npix, "url": self.url, "key": self.key, "irsa_url": self.irsa_url}


def cube_tile(npix: int, order: int = CUBE_ORDER) -> CubeTile:
    return CubeTile(order, int(npix), tile_key(npix, order))


# --- HTTP Range on any URL (IRSA fallback) -------------------------------------------

_session_lock = threading.Lock()
_SESSION: requests.Session | None = None


def _session() -> requests.Session:
    global _SESSION
    with _session_lock:
        if _SESSION is None:
            s = requests.Session()
            adapter = requests.adapters.HTTPAdapter(pool_connections=2, pool_maxsize=64)
            s.mount("https://", adapter)
            s.mount("http://", adapter)
            _SESSION = s
        return _SESSION


def read_url_range(url: str, start: int, stop: int) -> bytes:
    """Bytes [start, stop) of ``url`` with an HTTP Range request (retries 5xx/429/network errors).

    Refuses a 200 answer (the server ignored Range: a cube tile is 321 MB).
    """
    if stop <= start:
        return b""
    last: Exception | None = None
    for attempt in range(RANGE_RETRIES):
        if attempt:
            time.sleep(0.5 * 2 ** (attempt - 1))
        try:
            with _session().get(
                url, headers={"Range": f"bytes={start}-{stop - 1}"}, stream=True, timeout=settings.HTTP_TIMEOUT_S
            ) as r:
                if r.status_code == 416:
                    return b""
                if r.status_code == 206:
                    data = r.content
                    if len(data) == stop - start:
                        return data
                    last = OSError(f"short read: {len(data)} of {stop - start} bytes from {url}")
                elif r.status_code == 200:
                    raise OSError(f"server ignored the Range header for {url}")
                elif r.status_code >= 500 or r.status_code == 429:
                    last = requests.HTTPError(f"HTTP {r.status_code} for {url}", response=r)
                else:
                    r.raise_for_status()
                    raise OSError(f"unexpected HTTP {r.status_code} for {url}")
        except (requests.ConnectionError, requests.Timeout, *TRANSIENT_BODY_ERRORS) as e:
            last = e
    raise OSError(f"range read failed after {RANGE_RETRIES} attempts: {url} [{start}:{stop})") from last


def _irsa_reader(key: str, start: int, stop: int) -> bytes:
    return read_url_range(irsa_url_for_key(key), start, stop)


# --- tile headers ---------------------------------------------------------------------


Layout = tuple[tuple[str, int, int, int, int, tuple[int, ...]], ...]
"""Per HDU: (EXTNAME, header offset, data offset, data size [B], BITPIX, (NAXIS1, NAXIS2, ...))."""

DR1_LAYOUT: Layout = (
    ("PRIMARY", 0, 2880, 0, 8, ()),
    ("IMAGE", 2880, 8640, 106954752, -32, (512, 512, 102)),
    ("NHITS", 106966080, 106971840, 106954752, 32, (512, 512, 102)),
    ("FLAGS", 213929280, 213940800, 106954752, 32, (512, 512, 102)),
    ("SPECTRAL_CHANNELS", 320898240, 320901120, 2856, 8, (28, 102)),
    ("WCS-WAVE", 320904000, 320906880, 1224, 8, (1224, 1)),
)
"""Byte layout shared by all 47 DR1 cube tiles walked on 2026-11-14 (incl. Npix 0, 12287, both polar
caps and the RA=180 seam). Only used to *speculate* on a tile whose headers are not cached yet: its
headers and pixels are then requested in one parallel round, and the pixels are kept only if the
headers actually read match this layout exactly (otherwise the file is walked header by header)."""

SPECULATE = os.environ.get("ERRANTE_CUBE_SPECULATE", "1") != "0"
_MERGE_GAP = 64 * 1024
"""Header ranges closer than this are fetched in one request (the tail: SPECTRAL_CHANNELS + WCS-WAVE)."""


def _pad(n: int) -> int:
    return -(-n // FITS_BLOCK) * FITS_BLOCK


def _data_size(h: fits.Header) -> int:
    naxis = int(h.get("NAXIS", 0))
    if naxis == 0:
        return 0
    n = 1
    for i in range(1, naxis + 1):
        n *= int(h[f"NAXIS{i}"])
    return abs(int(h["BITPIX"])) // 8 * int(h.get("GCOUNT", 1)) * (int(h.get("PCOUNT", 0)) + n)


def layout_of(d: HduDirectory) -> Layout:
    """The :data:`Layout` tuple of a directory (what the speculation compares)."""
    out = []
    for h in d.hdus:
        naxis = int(h.header.get("NAXIS", 0))
        axes = tuple(int(h.header.get(f"NAXIS{i}", 0)) for i in range(1, naxis + 1))
        out.append((h.name, h.header_offset, h.data_offset, h.data_size, int(h.header.get("BITPIX", 8)), axes))
    return tuple(out)


def _check_cube(d: HduDirectory) -> HduDirectory:
    img = d["IMAGE"].header
    shape = tuple(int(img.get(f"NAXIS{i}", 0)) for i in (1, 2, 3))
    if int(img.get("NAXIS", 0)) != 3 or shape[0] != shape[1] or shape[0] & (shape[0] - 1):
        raise ValueError(f"{d.key}: IMAGE is not a (planes, w, w) cube with w a power of 2: NAXIS={shape}")
    for name in ("NHITS", "FLAGS"):
        info = d.get(name)
        if info is not None and tuple(int(info.header.get(f"NAXIS{i}", 0)) for i in (1, 2, 3)) != shape:
            raise ValueError(f"{d.key}: {name} shape differs from IMAGE")
    return d


_dirs: OrderedDict[tuple[str, str], HduDirectory] = OrderedDict()
_dirs_lock = threading.Lock()
_DIRS_MAX = 256
_dir_locks = KeyedLocks()


def _dir_path(key: str) -> Path:
    h = hashlib.sha256(key.encode()).hexdigest()[:24]
    return settings.CACHE_DIR / "cube" / "dir" / h[:2] / f"{h}.json"


def _cached_directory(key: str) -> HduDirectory | None:
    """Memory, then disk; never touches the network."""
    mkey = (str(settings.CACHE_DIR), key)
    with _dirs_lock:
        if mkey in _dirs:
            _dirs.move_to_end(mkey)
            return _dirs[mkey]
    try:
        d = HduDirectory.from_json(json.loads(_dir_path(key).read_text(encoding="ascii")))
    except (OSError, ValueError, KeyError, TypeError):
        return None
    if d.key != key:
        return None
    _remember_directory(d, write=False)
    return d


def _remember_directory(d: HduDirectory, *, write: bool = True) -> None:
    mkey = (str(settings.CACHE_DIR), d.key)
    with _dirs_lock:
        _dirs[mkey] = d
        _dirs.move_to_end(mkey)
        while len(_dirs) > _DIRS_MAX:
            _dirs.popitem(last=False)
    if write:
        _write_json(_dir_path(d.key), d.to_json())


def tile_directory(key: str, reader: RangeReader | None = None, use_cache: bool = True) -> HduDirectory:
    """HDU directory (headers + byte offsets + WCS-WAVE bytes) of a cube tile, cached by key.

    A tile of a fixed release never changes, so the cache (memory + ``CACHE_DIR/cube/dir``) has no
    expiry. A miss walks the file header by header with ``s3range.hdu_directory`` (4 sequential
    Range requests, ~92 KB). Raises ValueError if the file is not a (planes, w, w) cube.
    """
    if use_cache:
        hit = _cached_directory(key)
        if hit is not None:
            return hit
    with _dir_locks.hold((str(settings.CACHE_DIR), key)):
        if use_cache:
            hit = _cached_directory(key)
            if hit is not None:
                return hit
        d = _check_cube(s3range.hdu_directory(key, reader=reader or s3range.read_range, use_cache=False))
        if use_cache:
            _remember_directory(d)
        return d


def _template_infos(layout: Layout) -> dict[str, HduInfo]:
    """Minimal HduInfo per HDU of a layout: enough for :func:`_read_span` (offsets, BITPIX, NAXISn)."""
    out = {}
    for i, (name, hoff, doff, size, bitpix, axes) in enumerate(layout):
        h = fits.Header()
        h["BITPIX"] = bitpix
        h["NAXIS"] = len(axes)
        for j, n in enumerate(axes, 1):
            h[f"NAXIS{j}"] = n
        out[name] = HduInfo(i, name, hoff, doff, size, h)
    return out


def _header_chunks(layout: Layout) -> list[tuple[int, int]]:
    """Byte ranges covering every header (and the data of the small trailing tables), merged."""
    spans = []
    for _name, hoff, doff, size, _, _ in layout:
        end = doff + _pad(size) if size <= _MERGE_GAP else doff
        spans.append((hoff, end))
    spans.sort()
    merged: list[list[int]] = []
    for a, b in spans:
        if merged and a - merged[-1][1] <= _MERGE_GAP and (b - merged[-1][0]) <= 4 * _MERGE_GAP:
            merged[-1][1] = max(merged[-1][1], b)
        else:
            merged.append([a, b])
    return [(a, b) for a, b in merged]


def _directory_from_chunks(key: str, layout: Layout, chunks: dict[tuple[int, int], bytes]) -> HduDirectory | None:
    """Rebuild the HDU directory from speculatively read ranges; None unless it matches ``layout`` exactly."""

    def grab(start: int, stop: int) -> bytes | None:
        for (a, b), buf in chunks.items():
            if a <= start and stop <= b and len(buf) == b - a:
                return buf[start - a : stop - a]
        return None

    hdus: list[HduInfo] = []
    wcs_wave = b""
    for i, (name, hoff, doff, size, _, _) in enumerate(layout):
        raw = grab(hoff, doff)
        if raw is None or not raw.startswith(b"SIMPLE  =" if i == 0 else b"XTENSION="):
            return None
        try:
            h = fits.Header.fromstring(raw.decode("ascii"))
        except (UnicodeDecodeError, ValueError):
            return None
        end = next(
            (j for j in range(0, len(raw) - 79, 80) if raw[j : j + 3] == b"END" and not raw[j + 3 : j + 80].strip()),
            None,
        )
        if end is None or _pad(end + 80) != doff - hoff or _data_size(h) != size:
            return None
        hname = str(h.get("EXTNAME", "PRIMARY" if i == 0 else f"HDU{i}")).strip()
        if hname != name:
            return None
        hdus.append(HduInfo(i, name, hoff, doff, size, h))
        if name == "WCS-WAVE":
            tail = grab(hoff, doff + _pad(size))
            if tail is None:
                return None
            wcs_wave = tail
    d = HduDirectory(key, tuple(hdus), wcs_wave)
    scaled = any(
        (float(h.header.get("BSCALE", 1.0)), float(h.header.get("BZERO", 0.0))) != (1.0, 0.0)
        for h in hdus
        if h.name in ("IMAGE", "NHITS", "FLAGS")
    )  # the template pixels were decoded without scaling
    return d if layout_of(d) == layout and not scaled else None


def wavelength_table(directory: HduDirectory) -> tuple[np.ndarray, np.ndarray]:
    """(wavelength_um, bandwidth_um) per plane, ordered by plane, from the tile's WCS-WAVE table."""
    if not directory.wcs_wave:
        raise ValueError(f"{directory.key}: no WCS-WAVE extension")
    blob = fits.PrimaryHDU().header.tostring().encode("ascii") + directory.wcs_wave
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        with fits.open(io.BytesIO(blob), memmap=False) as hl:
            row = hl[1].data[0]
            plane = np.ravel(np.asarray(row["PLANE"], dtype=np.int64))
            wl = np.ravel(np.asarray(row["WAVELENGTHS"], dtype=np.float64))
            bw = np.ravel(np.asarray(row["BANDWIDTHS"], dtype=np.float64))
    n = int(directory["IMAGE"].header["NAXIS3"])
    if not (len(plane) == len(wl) == len(bw) == n) or sorted(plane.tolist()) != list(range(1, n + 1)):
        raise ValueError(f"{directory.key}: WCS-WAVE does not list planes 1..{n}")
    order = np.argsort(plane)
    return wl[order], bw[order]


def blank_planes(primary: fits.Header, n_planes: int = N_PLANES) -> tuple[int, ...]:
    """0-based planes written as all-NaN, from ``BLANKCH`` (e.g. 'D3:17,D4:01' -> (50, 51))."""
    raw = primary.get("BLANKCH")
    if raw is None:
        return tuple(k for k in BLANK_PLANES if k < n_planes)
    out = []
    for det, ch in _BLANKCH.findall(str(raw)):
        k = CHANNELS_PER_DETECTOR * (int(det) - 1) + int(ch) - 1
        if 0 <= k < n_planes:
            out.append(k)
    return tuple(sorted(set(out)))


# --- pixel reads ----------------------------------------------------------------------


class _Counter:
    def __init__(self, reader: RangeReader):
        self.reader = reader
        self.requests = 0
        self.bytes = 0
        self._lock = threading.Lock()

    def __call__(self, key: str, start: int, stop: int) -> bytes:
        data = self.reader(key, start, stop)
        with self._lock:
            self.requests += 1
            self.bytes += len(data)
        return data


def _read_span(
    key: str, info: HduInfo, plane: int, x0: int, x1: int, y0: int, y1: int, reader: RangeReader
) -> np.ndarray:
    """Pixels [y0..y1, x0..x1] of ``plane`` with ONE Range request (from (x0, y0) to (x1, y1))."""
    h = info.header
    dt = np.dtype(_DTYPES[int(h["BITPIX"])])
    w = int(h["NAXIS1"])
    first = (plane * int(h["NAXIS2"]) + y0) * w + x0
    count = (y1 - y0) * w + (x1 - x0 + 1)
    start = info.data_offset + first * dt.itemsize
    buf = reader(key, start, start + count * dt.itemsize)
    if len(buf) != count * dt.itemsize:
        raise OSError(f"short read for {info.name} plane {plane} of {key}")
    flat = np.frombuffer(buf, dtype=dt)
    rows = [flat[r * w : r * w + (x1 - x0 + 1)] for r in range(y1 - y0 + 1)]
    arr = np.stack(rows).astype(dt.newbyteorder("="))
    bscale, bzero = float(h.get("BSCALE", 1.0)), float(h.get("BZERO", 0.0))
    if (bscale, bzero) != (1.0, 0.0):
        arr = arr * bscale + bzero
    return arr


def _aperture(x: int, y: int, r: int, w: int) -> tuple[int, int, int, int, np.ndarray, bool]:
    """Box (x0, x1, y0, y1) clipped to the tile, circular mask inside it, and whether it was clipped."""
    x0, x1, y0, y1 = max(x - r, 0), min(x + r, w - 1), max(y - r, 0), min(y + r, w - 1)
    yy, xx = np.mgrid[y0 : y1 + 1, x0 : x1 + 1]
    mask = (xx - x) ** 2 + (yy - y) ** 2 <= r * r + 1e-9
    full = int(sum(1 for dy in range(-r, r + 1) for dx in range(-r, r + 1) if dx * dx + dy * dy <= r * r + 1e-9))
    return x0, x1, y0, y1, mask, int(mask.sum()) < full


# --- result ---------------------------------------------------------------------------


def _nan_to_none(a) -> list:
    return [None if (isinstance(v, float) and not math.isfinite(v)) else v for v in np.asarray(a).tolist()]


@dataclass
class CubeSpectrum:
    """Spectrum of one sky position from the SPHEREx DR1 all-sky cube (static coadd, no time axis).

    ``flux[k]`` is the plane-k value of the pixel containing (ra, dec) in ``unit`` (BUNIT,
    MJy/sr), or, with ``aperture_px > 0``, the mean over the pixels within that radius whose
    value is finite and NHITS > 0 (no background subtraction). ``valid[k]`` is False for
    blank planes (50, 51), NaN values and pixels with no input data. Integrated flux
    density of an aperture: ``flux * n_used * pixel_sr * 1e6`` Jy (HEALPix pixels are
    equal-area; still no background subtraction or aperture correction).
    """

    ra: float
    dec: float
    wavelength_um: np.ndarray
    bandwidth_um: np.ndarray
    flux: np.ndarray
    valid: np.ndarray
    unit: str
    tile: CubeTile
    pixel: tuple[int, int]
    pixel_center: tuple[float, float]
    aperture_px: int
    n_pixels: int
    n_used: np.ndarray
    nhits: np.ndarray | None = None
    flags: np.ndarray | None = None
    clipped: bool = False
    blank_planes: tuple[int, ...] = BLANK_PLANES
    tile_width: int = TILE_WIDTH
    mjd_range: tuple[float | None, float | None] = (None, None)
    source: str = "s3"
    timings: dict = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)

    @property
    def detector(self) -> np.ndarray:
        return np.arange(len(self.flux)) // CHANNELS_PER_DETECTOR + 1

    @property
    def channel(self) -> np.ndarray:
        return np.arange(len(self.flux)) % CHANNELS_PER_DETECTOR + 1

    @property
    def pixel_scale_arcsec(self) -> float:
        return math.degrees(math.sqrt(self.pixel_sr)) * 3600.0

    @property
    def pixel_sr(self) -> float:
        """Solid angle of one cube pixel (HEALPix pixels are equal-area): 4 pi / (12 * 4**order)."""
        return 4.0 * math.pi / (12 * 4 ** (self.tile.order + _tile_bits(self.tile_width)))

    def to_dict(self) -> dict:
        """JSON-friendly dict (NaN -> None)."""
        return {
            "ra": self.ra,
            "dec": self.dec,
            "product": "SPHEREx DR1 all-sky spectral cube (HiPS FITS tiles)",
            "release": CUBE_PREFIX,
            "unit": self.unit,
            "wavelength_um": [round(float(v), 6) for v in self.wavelength_um],
            "bandwidth_um": [round(float(v), 6) for v in self.bandwidth_um],
            "flux": _nan_to_none(self.flux.astype(float)),
            "valid": [bool(v) for v in self.valid],
            "n_used": [int(v) for v in self.n_used],
            "nhits": None if self.nhits is None else [int(v) for v in self.nhits],
            "flags": None if self.flags is None else [int(v) for v in self.flags],
            "detector": [int(v) for v in self.detector],
            "channel": [int(v) for v in self.channel],
            "blank_planes": list(self.blank_planes),
            "tile": {**self.tile.to_dict(), "width": self.tile_width},
            "pixel": {"x": self.pixel[0], "y": self.pixel[1], "convention": "0-based column, row of the FITS tile"},
            "pixel_center": {"ra": self.pixel_center[0], "dec": self.pixel_center[1]},
            "pixel_scale_arcsec": round(self.pixel_scale_arcsec, 4),
            "pixel_sr": self.pixel_sr,
            "aperture_px": self.aperture_px,
            "n_pixels": self.n_pixels,
            "clipped": self.clipped,
            "mjd_range": list(self.mjd_range),
            "source": self.source,
            "timings": self.timings,
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, d: dict) -> CubeSpectrum:
        t = d["tile"]
        return cls(
            ra=float(d["ra"]),
            dec=float(d["dec"]),
            wavelength_um=np.asarray(d["wavelength_um"], dtype=float),
            bandwidth_um=np.asarray(d["bandwidth_um"], dtype=float),
            flux=np.asarray([np.nan if v is None else v for v in d["flux"]], dtype=float),
            valid=np.asarray(d["valid"], dtype=bool),
            unit=d["unit"],
            tile=CubeTile(int(t["order"]), int(t["npix"]), t["key"]),
            pixel=(int(d["pixel"]["x"]), int(d["pixel"]["y"])),
            pixel_center=(float(d["pixel_center"]["ra"]), float(d["pixel_center"]["dec"])),
            aperture_px=int(d["aperture_px"]),
            n_pixels=int(d["n_pixels"]),
            n_used=np.asarray(d["n_used"], dtype=int),
            nhits=None if d.get("nhits") is None else np.asarray(d["nhits"], dtype=int),
            flags=None if d.get("flags") is None else np.asarray(d["flags"], dtype=int),
            clipped=bool(d.get("clipped", False)),
            blank_planes=tuple(d.get("blank_planes", BLANK_PLANES)),
            tile_width=int(t.get("width", TILE_WIDTH)),
            mjd_range=tuple(d.get("mjd_range", (None, None))),
            source=d.get("source", "s3"),
            timings=dict(d.get("timings", {})),
            notes=list(d.get("notes", [])),
        )


# --- result cache ---------------------------------------------------------------------


def _result_path(key: str, x: int, y: int, aperture_px: int, with_nhits: bool, with_flags: bool) -> Path:
    ident = f"v{RESULT_CACHE_VERSION}|{key}|{x}|{y}|{aperture_px}|{int(with_nhits)}|{int(with_flags)}"
    h = hashlib.sha256(ident.encode()).hexdigest()[:24]
    return settings.CACHE_DIR / "cube" / "spectra" / h[:2] / f"{h}.json"


def _write_json(path: Path, payload: dict) -> None:
    """Best-effort atomic write (unique temp file + os.replace); a cache failure never fails a read."""
    tmp = path.with_name(f"{path.name}.{os.getpid()}.{threading.get_ident()}.part")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp.write_text(json.dumps(payload), encoding="utf-8")
        os.replace(tmp, path)
    except OSError:
        pass
    finally:
        try:
            tmp.unlink(missing_ok=True)
        except OSError:
            pass


def _load_result(path: Path) -> CubeSpectrum | None:
    try:
        return CubeSpectrum.from_dict(json.loads(path.read_text(encoding="utf-8")))
    except (OSError, ValueError, KeyError, TypeError):
        return None


# --- main entry point -----------------------------------------------------------------


def cube_spectrum(
    ra: float,
    dec: float,
    *,
    aperture_px: int = 0,
    with_nhits: bool = False,
    with_flags: bool = False,
    use_cache: bool = True,
    reader: RangeReader | None = None,
    fallback: bool = True,
) -> CubeSpectrum:
    """SPHEREx DR1 spectrum (102 planes, 0.75-5 um) at (ra, dec) [deg, ICRS] from the all-sky cube.

    Reads only the needed bytes of one cube tile with HTTP Range: its headers once (cached on
    disk), then the pixel (or a ``aperture_px``-radius disc, clipped at the tile edge) in each
    of the 102 planes, one request per plane and extension, in parallel. ``with_nhits`` also
    reads the number of input samples per plane and pixel (twice the requests; NaN <=> NHITS == 0
    on 3.55 M pixel-planes checked, so it adds the count, not validity); ``with_flags`` reads the
    coadded FLAGS bits of the centre pixel. ``reader`` replaces the S3 Range reader
    (tests); with the default reader, an S3 failure is retried once against the byte-identical
    IRSA copy when ``fallback`` is true. Raises ValueError for bad input, OSError when no
    copy of the tile can be read.
    """
    t0 = time.perf_counter()
    ra, dec = float(ra), float(dec)
    if not (math.isfinite(ra) and math.isfinite(dec)) or abs(dec) > 90.0:
        raise ValueError(f"invalid position ({ra}, {dec})")
    ra %= 360.0
    aperture_px = int(aperture_px)
    if not 0 <= aperture_px <= MAX_APERTURE_PX:
        raise ValueError(f"aperture_px must be in 0..{MAX_APERTURE_PX}")

    tp = sky_to_tile_pixel(ra, dec, CUBE_ORDER, TILE_WIDTH)
    tile = cube_tile(tp.npix, CUBE_ORDER)
    rpath = _result_path(tile.key, tp.x, tp.y, aperture_px, with_nhits, with_flags)
    if use_cache:
        hit = _load_result(rpath)
        if hit is not None:
            hit.ra, hit.dec = ra, dec
            hit.timings = {**hit.timings, "from_cache": True, "total_s": round(time.perf_counter() - t0, 4)}
            return hit

    attempts: list[tuple[str, RangeReader]] = [("custom", reader) if reader is not None else ("s3", s3range.read_range)]
    if reader is None and fallback:
        attempts.append(("irsa", _irsa_reader))
    errors: list[str] = []
    for source, rd in attempts:
        try:
            spec = _cube_spectrum_from(tile, tp, ra, dec, aperture_px, with_nhits, with_flags, rd, t0)
        except OSError as e:
            errors.append(f"{source}: {e}")
            continue
        spec.source = source
        if errors:
            spec.notes.append(f"read from {source} after: {'; '.join(errors)}")
        if use_cache:
            _write_json(rpath, spec.to_dict())
        return spec
    raise OSError(f"cube tile {tile.npix} unreadable: {'; '.join(errors)}")


def _pixel_jobs(
    key: str,
    infos: dict[str, HduInfo],
    n: int,
    blanks: tuple[int, ...],
    box: tuple[int, int, int, int],
    centre: tuple[int, int],
    with_nhits: bool,
    with_flags: bool,
    reader: RangeReader,
) -> dict[tuple[str, int], Callable[[], np.ndarray]]:
    """One Range request per (extension, plane): IMAGE and NHITS over the aperture box, FLAGS at the centre."""
    jobs: dict[tuple[str, int], Callable[[], np.ndarray]] = {}
    for name in ("IMAGE", "NHITS", "FLAGS"):
        info = infos.get(name)
        if info is None or (name == "NHITS" and not with_nhits) or (name == "FLAGS" and not with_flags):
            continue
        bx = box if name != "FLAGS" else (centre[0], centre[0], centre[1], centre[1])
        for k in range(n):
            if name == "IMAGE" or k not in blanks:
                jobs[(name, k)] = lambda info=info, k=k, bx=bx: _read_span(key, info, k, *bx, reader)
    return jobs


def _run(jobs: dict) -> dict:
    if not jobs:
        return {}
    with ThreadPoolExecutor(max_workers=max(1, min(CUBE_PARALLEL, len(jobs)))) as pool:
        futures = {name: pool.submit(fn) for name, fn in jobs.items()}
        return {name: f.result() for name, f in futures.items()}


def _cube_spectrum_from(
    tile: CubeTile,
    tp: TilePixel,
    ra: float,
    dec: float,
    aperture_px: int,
    with_nhits: bool,
    with_flags: bool,
    reader: RangeReader,
    t0: float,
) -> CubeSpectrum:
    rd = _Counter(reader)
    got: dict = {}
    d = _cached_directory(tile.key)
    mode = "cached-headers"
    header_requests = 0
    if d is None and SPECULATE:
        # Cold tile: request the headers AND the pixels at the template offsets in one parallel
        # round; keep the pixels only if the headers read back match the template exactly.
        mode = "speculative"
        tinfos = _template_infos(DR1_LAYOUT)
        tw, tn = int(tinfos["IMAGE"].header["NAXIS1"]), int(tinfos["IMAGE"].header["NAXIS3"])
        x0, x1, y0, y1, _, _ = _aperture(tp.x, tp.y, aperture_px, tw)
        jobs: dict = {}
        if tw == tp.width:
            jobs = _pixel_jobs(
                tile.key, tinfos, tn, BLANK_PLANES, (x0, x1, y0, y1), (tp.x, tp.y), with_nhits, with_flags, rd
            )
        chunks = _header_chunks(DR1_LAYOUT)
        header_requests = len(chunks)
        for a, b in chunks:
            jobs[("HEADER", a, b)] = lambda a=a, b=b: rd(tile.key, a, b)
        out = _run(jobs)
        spec_dir = _directory_from_chunks(
            tile.key, DR1_LAYOUT, {(k[1], k[2]): v for k, v in out.items() if k[0] == "HEADER"}
        )
        if spec_dir is not None:
            d = _check_cube(spec_dir)
            _remember_directory(d)
            got = {k: v for k, v in out.items() if k[0] != "HEADER"}
        else:
            mode = "speculation-missed"
    t_header = time.perf_counter()
    if d is None:
        before = rd.requests
        d = tile_directory(tile.key, reader=rd)
        header_requests += rd.requests - before
        if mode == "cached-headers":
            mode = "walk"
        t_header = time.perf_counter()

    img = d["IMAGE"]
    w = int(img.header["NAXIS1"])
    n = int(img.header["NAXIS3"])
    if w != tp.width:
        raise ValueError(f"{tile.key}: tile width {w}, expected {tp.width}")
    wl, bw = wavelength_table(d)
    blanks = blank_planes(d.primary, n)
    x0, x1, y0, y1, mask, clipped = _aperture(tp.x, tp.y, aperture_px, w)
    cy, cx = tp.y - y0, tp.x - x0
    infos = {name: d[name] for name in ("IMAGE", "NHITS", "FLAGS") if d.get(name) is not None}
    needed = _pixel_jobs(tile.key, infos, n, blanks, (x0, x1, y0, y1), (tp.x, tp.y), with_nhits, with_flags, rd)
    got = {k: v for k, v in got.items() if k in needed}
    got.update(_run({k: fn for k, fn in needed.items() if k not in got}))
    t_pixels = time.perf_counter()

    flux = np.full(n, np.nan)
    n_used = np.zeros(n, dtype=int)
    nhits = np.zeros(n, dtype=int) if with_nhits and "NHITS" in infos else None
    flags = np.zeros(n, dtype=int) if with_flags and "FLAGS" in infos else None
    for k in range(n):
        vals = got[("IMAGE", k)].astype(float)
        good = mask & np.isfinite(vals)
        hits = got.get(("NHITS", k))
        if hits is not None:
            good &= hits > 0
            nhits[k] = int(hits[cy, cx])
        if ("FLAGS", k) in got:
            flags[k] = int(got[("FLAGS", k)][0, 0])
        n_used[k] = int(good.sum())
        if k in blanks:
            continue
        if aperture_px and n_used[k]:
            flux[k] = float(vals[good].mean())
        elif not aperture_px and good[cy, cx]:
            flux[k] = float(vals[cy, cx])
    valid = np.isfinite(flux)
    valid[list(blanks)] = False
    flux[~valid] = np.nan

    notes = ["Static DR1 coadd (mean over the survey): no time information; use the L2 exposures for variability."]
    core_lost = [k for k in range(n) if k not in blanks and not np.isfinite(got[("IMAGE", k)][cy, cx])]
    if core_lost:
        notes.append(
            f"{len(core_lost)} planes have no input samples at the centre pixel (NaN, NHITS = 0): typical of a "
            "saturated bright star, whose core the coadd rejects."
            + (
                " Those planes are invalid; an aperture (aperture_px > 0) averages the pixels around it."
                if not aperture_px
                else ""
            )
        )
    if clipped:
        notes.append("Aperture clipped at the tile edge (neighbouring tiles are not read).")
    mjd = (d.primary.get("MJD-BEG"), d.primary.get("MJD-END"))
    t1 = time.perf_counter()
    return CubeSpectrum(
        ra=ra,
        dec=dec,
        wavelength_um=wl,
        bandwidth_um=bw,
        flux=flux,
        valid=valid,
        unit=str(img.header.get("BUNIT", "")).strip(),
        tile=tile,
        pixel=(tp.x, tp.y),
        pixel_center=tile_pixel_to_sky(tile.npix, tp.x, tp.y, tile.order, w),
        aperture_px=aperture_px,
        n_pixels=int(mask.sum()),
        n_used=n_used,
        nhits=nhits,
        flags=flags,
        clipped=clipped,
        blank_planes=blanks,
        tile_width=w,
        mjd_range=(None if mjd[0] is None else float(mjd[0]), None if mjd[1] is None else float(mjd[1])),
        timings={
            "mode": mode,
            "header_s": round(t_header - t0, 4),
            "pixels_s": round(t_pixels - t_header, 4),
            "total_s": round(t1 - t0, 4),
            "header_requests": header_requests,
            "pixel_requests": rd.requests - header_requests,
            "bytes": rd.bytes,
            "from_cache": False,
        },
        notes=notes,
    )
