"""Small SPHEREx L2 patches read straight from the public S3 bucket with HTTP Range (WS1).

Why: an IRSA (IBE) cutout always carries the whole EPSF table (~4 MB, 4-15 s, frequent
503s), while the planes we need are stored uncompressed in the L2 file, so a 5' patch
is ~49 rows x 8160 B per plane, read in well under a second from S3 (which, unlike
IRSA, also sends CORS headers).

How (verified on real DR1 files, 2026-11-14; see docs/DATA.md §2-§3):
  1. HDU directory: walk the headers with Range reads (2880-byte blocks parsed with
     ``fits.Header.fromstring``); data size = |BITPIX|/8 * GCOUNT * (PCOUNT + prod NAXISn),
     padded to 2880. Header sizes vary per file (IMAGE data starts at byte 25920 in one
     DR1 file, 28800 in another), so offsets are never hard-coded. The directory (all
     headers + the small WCS-WAVE HDU, ~80 KB) is cached as JSON under CACHE_DIR.
  2. Box: the same rule the IRSA cutout service uses (checked on 5 real cutouts, incl.
     clipped ones): n = round(size / pixel_scale) per axis, first pixel ceil(xc - n/2)
     (0-based, center from the full TAN-SIP WCS), clipped to 0..NAXIS-1. Empty -> NoOverlap
     (where IBE answers HTTP 422).
  3. IMAGE / VARIANCE / ZODI (float32 big-endian, uncompressed): one Range request per
     plane for rows y0..y1, then the columns are sliced in memory.
  4. FLAGS: BINTABLE tile-compressed with RICE_1 and one tile per row (ZTILE1=2040,
     ZTILE2=1). Read the row descriptors for y0..y1, then the heap slice they point to,
     wrap both in a minimal compressed HDU in memory and let astropy decompress it.
     If that fails the patch has ``flags=None`` and ``extra['flags'] == 'unavailable'``
     (unknown is NOT clean).
  5. Header: the IMAGE header with NAXISn updated and EVERY CRPIXn<key> shifted by the box
     offset, exactly like an IRSA cutout (primary TAN-SIP, alternate 'A' = 0-based detector
     pixels, alternate 'W' = WAVE-TAB lookup). IRSA writes no LTV1/LTV2; we add
     PATCH_X0/PATCH_Y0 (0-based offset of the patch in the detector) for convenience.

``fetch_patches`` has the same signature and aligned output as ``cutouts.fetch_cutouts``
and writes small MEF files (IMAGE, FLAGS if known, VARIANCE, ZODI, WCS-WAVE; no EPSF)
that ``fits_io.read_spherex`` opens, so build.py can switch with one line.
"""

from __future__ import annotations

import base64
import hashlib
import io
import json
import math
import os
import re
import threading
import time
import uuid
import warnings
from collections import OrderedDict
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import requests
from astropy.io import fits
from astropy.wcs import WCS, FITSFixedWarning
from astropy.wcs.utils import proj_plane_pixel_scales

from .. import settings
from ..models import FrameRef
from .cutouts import TRANSIENT_BODY_ERRORS, FetchError, KeyedLocks, NoOverlap, fetch_report
from .fits_io import SpherexImage
from .s3 import irsa_uri_to_s3_key

__all__ = [
    "FetchError",
    "HduDirectory",
    "HduInfo",
    "NoOverlap",
    "RangeReader",
    "fetch_patch",
    "fetch_patches",
    "fetch_patches_report",
    "hdu_directory",
    "patch_box",
    "patch_path",
    "read_patch",
    "read_range",
    "write_patch_fits",
]

BLOCK = 2880
CARD = 80
MAX_PARALLEL_S3 = int(os.environ.get("ERRANTE_MAX_PARALLEL_S3", "16"))
"""S3 is not IRSA: 16 parallel Range readers are fine (measured; IRSA needs <= 6-8)."""
DIR_CACHE_VERSION = 1
RANGE_RETRIES = 4
MAX_HEADER_BYTES = 360 * BLOCK
"""~1 MB. Real L2 headers are <= ~30 KB; a header with no END card within this is corrupt."""
REPLACE_RETRIES = 5
"""os.replace attempts: on Windows it fails while another thread/process has the target open."""

RangeReader = Callable[[str, int, int], bytes]
"""``reader(s3_key, start, stop) -> bytes[start:stop]`` of the object (shorter at EOF, b"" past it)."""

_DTYPES = {8: ">u1", 16: ">i2", 32: ">i4", 64: ">i8", -32: ">f4", -64: ">f8"}
_CRPIX = re.compile(r"^CRPIX([12])([A-Z]?)$")
_TFORM_P = re.compile(r"^1?([PQ])[A-Z](\(\d+\))?$")
_CONTENT_RANGE = re.compile(r"^bytes\s+(\d+)-(\d+)/(\d+|\*)$")
_TRANSIENT = (requests.ConnectionError, requests.Timeout, *TRANSIENT_BODY_ERRORS)
"""Network failures worth retrying. A body cut after the 206 status line raises
ChunkedEncodingError, which is NOT a ConnectionError: it must be listed explicitly."""


def _pad(n: int) -> int:
    return -(-n // BLOCK) * BLOCK


# --- HTTP Range reader --------------------------------------------------------

_session_lock = threading.Lock()
_SESSION: requests.Session | None = None


def _session() -> requests.Session:
    """One pooled session shared by all threads: keep-alive connections survive short-lived pools."""
    global _SESSION
    with _session_lock:
        if _SESSION is None:
            s = requests.Session()
            adapter = requests.adapters.HTTPAdapter(pool_connections=4, pool_maxsize=64)
            s.mount("https://", adapter)
            s.mount("http://", adapter)
            _SESSION = s
        return _SESSION


def _content_range(value: str | None) -> tuple[int | None, int | None]:
    """(first byte, total object size) of a Content-Range header; None where unknown."""
    m = _CONTENT_RANGE.match((value or "").strip())
    if not m:
        return None, None
    return int(m[1]), None if m[3] == "*" else int(m[3])


def read_range(key: str, start: int, stop: int) -> bytes:
    """Bytes [start, stop) of ``s3://nasa-irsa-spherex/<key>`` via anonymous HTTPS Range.

    Retries 5xx/429, timeouts, dropped connections and bodies cut mid-transfer with
    backoff; returns b"" past the end of the object (416) and a short read only at EOF.
    Refuses a 200 (whole-object) answer instead of silently downloading 60+ MB, and a 206
    for a range that does not start at ``start``.
    """
    if stop <= start:
        return b""
    url = f"{settings.S3_HTTPS}/{key.lstrip('/')}"
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
                    first, total = _content_range(r.headers.get("Content-Range"))
                    if first is not None and first != start:
                        last = OSError(f"asked for bytes from {start}, got {r.headers.get('Content-Range')}")
                        continue
                    data = r.content
                    if len(data) == stop - start or (total is not None and start + len(data) == total):
                        return data
                    last = OSError(f"short read: {len(data)} of {stop - start} bytes")
                elif r.status_code == 200:
                    raise OSError(f"server ignored the Range header for {url}")
                elif r.status_code >= 500 or r.status_code == 429:
                    last = requests.HTTPError(f"HTTP {r.status_code} for {url}", response=r)
                else:
                    r.raise_for_status()  # 403/404: retrying won't help
                    raise OSError(f"unexpected HTTP {r.status_code} for {url}")
        except _TRANSIENT as e:
            last = e
    raise OSError(f"S3 range read failed after {RANGE_RETRIES} attempts: {key} [{start}:{stop})") from last


class _CountingReader:
    """Wraps a RangeReader to count requests and bytes (thread-safe)."""

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


def _resolve(reader: RangeReader | None) -> RangeReader:
    return reader if reader is not None else read_range  # looked up at call time: monkeypatchable


# --- HDU directory ------------------------------------------------------------


@dataclass(frozen=True)
class HduInfo:
    index: int
    name: str
    header_offset: int
    data_offset: int
    data_size: int  # bytes, before padding to 2880
    header: fits.Header

    @property
    def end(self) -> int:
        return self.data_offset + _pad(self.data_size)


@dataclass(frozen=True)
class HduDirectory:
    key: str
    hdus: tuple[HduInfo, ...]
    wcs_wave: bytes = b""  # raw WCS-WAVE HDU (header + padded data), b"" if the file has none

    def get(self, name: str) -> HduInfo | None:
        return next((h for h in self.hdus if h.name == name), None)

    def __getitem__(self, name: str) -> HduInfo:
        info = self.get(name)
        if info is None:
            raise KeyError(f"{name} not in {self.key}")
        return info

    @property
    def primary(self) -> fits.Header:
        return self.hdus[0].header

    def to_json(self) -> dict:
        return {
            "version": DIR_CACHE_VERSION,
            "key": self.key,
            "hdus": [
                {
                    "name": h.name,
                    "header_offset": h.header_offset,
                    "data_offset": h.data_offset,
                    "data_size": h.data_size,
                    "header": h.header.tostring(),
                }
                for h in self.hdus
            ],
            "wcs_wave_b64": base64.b64encode(self.wcs_wave).decode("ascii"),
        }

    @classmethod
    def from_json(cls, d: dict) -> HduDirectory:
        hdus = tuple(
            HduInfo(
                i, h["name"], h["header_offset"], h["data_offset"], h["data_size"], fits.Header.fromstring(h["header"])
            )
            for i, h in enumerate(d["hdus"])
        )
        return cls(d["key"], hdus, base64.b64decode(d["wcs_wave_b64"]))


def _find_end(buf: bytes) -> int | None:
    for i in range(0, len(buf) - CARD + 1, CARD):
        if buf[i : i + 3] == b"END" and not buf[i + 3 : i + CARD].strip():
            return i
    return None


def _read_header(
    key: str, offset: int, reader: RangeReader, chunk: int, buf: bytes = b""
) -> tuple[fits.Header, int, bytes] | None:
    """(header, header length incl. padding, raw bytes from ``offset``) or None at EOF.

    ``buf`` = bytes already read starting at ``offset`` (saves a request when the
    previous read reached this far). Gives up after MAX_HEADER_BYTES without an END card.
    """
    while True:
        end = _find_end(buf)
        if end is not None:
            hlen = _pad(end + CARD)
            if len(buf) >= hlen:
                return fits.Header.fromstring(buf[:hlen].decode("ascii")), hlen, buf
        elif len(buf) >= MAX_HEADER_BYTES:
            raise ValueError(f"no END card in the first {len(buf)} bytes of the header at byte {offset} of {key}")
        want = min(chunk, max(BLOCK, MAX_HEADER_BYTES - len(buf)))
        more = reader(key, offset + len(buf), offset + len(buf) + want)
        if not more:
            if not buf:
                return None
            raise ValueError(f"truncated FITS header (no END card) at byte {offset} of {key}")
        buf += more
        chunk = max(chunk, len(buf))


def _data_size(h: fits.Header) -> int:
    naxis = int(h.get("NAXIS", 0))
    if naxis == 0:
        return 0
    n = 1
    for i in range(1, naxis + 1):
        n *= int(h[f"NAXIS{i}"])
    return abs(int(h["BITPIX"])) // 8 * int(h.get("GCOUNT", 1)) * (int(h.get("PCOUNT", 0)) + n)


def _walk(key: str, reader: RangeReader) -> HduDirectory:
    hdus: list[HduInfo] = []
    wcs_wave = b""
    offset = 0
    carry = b""  # bytes already read from `offset` on
    while True:
        # The first read (12 blocks) covers PRIMARY + the ~23-29 KB IMAGE header.
        got = _read_header(key, offset, reader, BLOCK * (12 if offset == 0 else 8), carry)
        if got is None:
            break
        hdr, hlen, raw = got
        if offset == 0 and not raw.startswith(b"SIMPLE  ="):
            raise ValueError(f"{key} is not a FITS file")
        size = _data_size(hdr)
        name = str(hdr.get("EXTNAME", "PRIMARY" if offset == 0 else f"HDU{len(hdus)}")).strip()
        info = HduInfo(len(hdus), name, offset, offset + hlen, size, hdr)
        hdus.append(info)
        if name == "WCS-WAVE":  # tiny and last in every L2 file seen: keep its bytes, stop walking
            want = hlen + _pad(size)
            if len(raw) < want:
                raw += reader(key, offset + len(raw), offset + want)
            wcs_wave = raw[:want].ljust(want, b"\0")
            break
        carry = raw[info.end - offset :]  # empty unless this read already reached the next header
        offset = info.end
    if not hdus:
        raise ValueError(f"empty object: {key}")
    return HduDirectory(key, tuple(hdus), wcs_wave)


_mem: OrderedDict[tuple[str, str], HduDirectory] = OrderedDict()
_mem_lock = threading.Lock()
_MEM_MAX = 128
"""Each directory holds ~0.4 MB of parsed astropy Headers: 128 is ~50 MB in a long-lived
process. Evicted entries come back from the disk cache (one JSON read, no network)."""
_dir_locks = KeyedLocks()
_patch_locks = KeyedLocks()


def _dir_cache_path(key: str) -> Path:
    h = hashlib.sha256(key.encode()).hexdigest()[:24]
    return settings.CACHE_DIR / "s3range" / "dir" / h[:2] / f"{h}.json"


def _atomic_write(path: Path, data: bytes, *, best_effort: bool = False) -> bool:
    """Write ``data`` to ``path`` via a unique temp file + os.replace (readers never see a partial file).

    On Windows os.replace raises PermissionError while another thread or process has
    ``path`` open or is replacing it: retried briefly, then raised, unless ``best_effort``
    (optional caches), where any OSError just returns False. The temp file never survives.
    """
    tmp = path.with_name(f"{path.name}.{uuid.uuid4().hex[:8]}.part")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp.write_bytes(data)
        for attempt in range(REPLACE_RETRIES):
            try:
                os.replace(tmp, path)
                return True
            except PermissionError:
                if attempt == REPLACE_RETRIES - 1:
                    raise
                time.sleep(0.05 * (attempt + 1))
    except OSError:
        if best_effort:
            return False
        raise
    finally:
        try:
            tmp.unlink(missing_ok=True)  # nothing left after a successful replace
        except OSError:
            pass
    return False


def _cached_directory(mkey: tuple[str, str], key: str) -> HduDirectory | None:
    with _mem_lock:
        if mkey in _mem:
            _mem.move_to_end(mkey)
            return _mem[mkey]
    try:
        d = json.loads(_dir_cache_path(key).read_text(encoding="ascii"))
        if d.get("version") == DIR_CACHE_VERSION and d.get("key") == key:
            directory = HduDirectory.from_json(d)
            _remember(mkey, directory)
            return directory
    except (ValueError, KeyError, OSError):
        pass  # missing, corrupt or unreadable cache entry: (re)build it
    return None


def hdu_directory(key: str, reader: RangeReader | None = None, use_cache: bool = True) -> HduDirectory:
    """Headers and byte offsets of every HDU of an S3 object (memory + disk cached by key).

    Thread-safe: concurrent calls for one key walk the file once and share the result.
    The disk cache is best effort: failing to write it never fails the read.
    """
    if not use_cache:
        return _walk(key, _resolve(reader))
    mkey = (str(settings.CACHE_DIR), key)
    hit = _cached_directory(mkey, key)
    if hit is not None:
        return hit
    with _dir_locks.hold(mkey):
        hit = _cached_directory(mkey, key)  # another thread may have walked it while we waited
        if hit is not None:
            return hit
        directory = _walk(key, _resolve(reader))
        _atomic_write(_dir_cache_path(key), json.dumps(directory.to_json()).encode("ascii"), best_effort=True)
        _remember(mkey, directory)
        return directory


def _remember(mkey: tuple[str, str], directory: HduDirectory) -> None:
    with _mem_lock:
        _mem[mkey] = directory
        _mem.move_to_end(mkey)
        while len(_mem) > _MEM_MAX:
            _mem.popitem(last=False)


# --- geometry -----------------------------------------------------------------


def _celestial_wcs(header: fits.Header) -> WCS:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", FITSFixedWarning)
        return WCS(header)


def patch_box(header: fits.Header, ra: float, dec: float, size_arcmin: float) -> tuple[int, int, int, int]:
    """0-based inclusive pixel box (x0, x1, y0, y1) of a ``size_arcmin`` patch centred on (ra, dec).

    Same rule as the IRSA cutout service (verified on real cutouts, docs at module top),
    using the full TAN-SIP WCS of ``header``. Raises :class:`NoOverlap` if the box misses
    the detector or (ra, dec) cannot be projected onto it.

    (ra, dec) are first rounded to 7 decimals, exactly as ``cutouts.cutout_url`` sends them
    to IBE, so a center within ~1e-4 px of a box-edge tie breaks the same way (verified
    live on 3 tie cases, see tests).
    """
    if size_arcmin <= 0:
        raise ValueError("size_arcmin must be > 0")
    ra, dec = float(f"{ra:.7f}"), float(f"{dec:.7f}")
    wcs = _celestial_wcs(header)
    nx_full, ny_full = int(header["NAXIS1"]), int(header["NAXIS2"])
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        try:
            xc, yc = wcs.all_world2pix([[ra, dec]], 0, quiet=True)[0]
            back = wcs.all_pix2world([[xc, yc]], 0)[0]
        except Exception as e:  # noqa: BLE001  (astropy raises several types for unprojectable points)
            raise NoOverlap(f"({ra}, {dec}) cannot be projected onto this detector: {e}") from e
    scales = proj_plane_pixel_scales(wcs) * 3600.0  # arcsec/pixel along x, y
    if not (np.isfinite(xc) and np.isfinite(yc) and np.all(np.isfinite(back))):
        raise NoOverlap(f"({ra}, {dec}) cannot be projected onto this detector")
    # SIP inversion can "converge" to nonsense far off the detector: check the round trip.
    cosd = math.cos(math.radians(dec))
    dra = ((back[0] - ra + 180.0) % 360.0 - 180.0) * cosd
    if math.hypot(dra, back[1] - dec) * 3600.0 > 0.5 * float(scales.min()):
        raise NoOverlap(f"({ra}, {dec}) is too far from this detector for its WCS")
    box = []
    for c, scale, n_full in ((xc, scales[0], nx_full), (yc, scales[1], ny_full)):
        n = max(1, math.floor(size_arcmin * 60.0 / scale + 0.5))
        lo = math.ceil(c - n / 2.0)
        hi = lo + n - 1
        lo, hi = max(lo, 0), min(hi, n_full - 1)
        if lo > hi:
            raise NoOverlap(f"{size_arcmin}' box at ({ra}, {dec}) misses the detector (center pixel {c:.1f})")
        box += [lo, hi]
    return box[0], box[1], box[2], box[3]


def _shift_header(h: fits.Header, x0: int, y0: int, nx: int, ny: int) -> fits.Header:
    """Header of a sub-image: NAXISn updated, every CRPIXn<key> shifted like an IRSA cutout."""
    out = h.copy()
    out["NAXIS1"] = nx
    out["NAXIS2"] = ny
    for k in list(out.keys()):
        m = _CRPIX.match(k)
        if m:
            out[k] = float(out[k]) - (x0 if m[1] == "1" else y0)
    for k in ("CHECKSUM", "DATASUM"):
        out.remove(k, ignore_missing=True, remove_all=True)
    return out


def _mid_mjd(h: fits.Header) -> float:
    """Mid-exposure MJD: MJD-AVG, else MJD-OBS + XPOSURE/2 (MJD-OBS is the START)."""
    if "MJD-AVG" in h:
        return float(h["MJD-AVG"])
    if "XPOSURE" in h:
        return float(h["MJD-OBS"]) + float(h["XPOSURE"]) / 2.0 / 86400.0
    return float(h["MJD-OBS"])


# --- pixel reads --------------------------------------------------------------


def _read_rows(key: str, info: HduInfo, x0: int, x1: int, y0: int, y1: int, reader: RangeReader) -> np.ndarray:
    h = info.header
    if str(h.get("XTENSION", "IMAGE")).strip() != "IMAGE" or int(h["NAXIS"]) != 2:
        raise ValueError(f"{info.name} is not an uncompressed 2-D image")
    dt = np.dtype(_DTYPES[int(h["BITPIX"])])
    nx_full = int(h["NAXIS1"])
    row = nx_full * dt.itemsize
    buf = reader(key, info.data_offset + y0 * row, info.data_offset + (y1 + 1) * row)
    if len(buf) != (y1 - y0 + 1) * row:
        raise OSError(f"short read for {info.name} rows {y0}..{y1} of {key}")
    arr = np.frombuffer(buf, dtype=dt).reshape(y1 - y0 + 1, nx_full)[:, x0 : x1 + 1]
    arr = arr.astype(dt.newbyteorder("="))
    bscale, bzero = float(h.get("BSCALE", 1.0)), float(h.get("BZERO", 0.0))
    if (bscale, bzero) != (1.0, 0.0):
        arr = arr * bscale + bzero
    return arr


def _read_flags(
    key: str, info: HduInfo, x0: int, x1: int, y0: int, y1: int, reader: RangeReader
) -> tuple[np.ndarray, fits.Header]:
    """FLAGS rows y0..y1, columns x0..x1 (int32) and the image-style header of the full plane."""
    h = info.header
    if str(h.get("XTENSION", "")).strip() == "IMAGE":  # not compressed in some future release
        return _read_rows(key, info, x0, x1, y0, y1, reader).astype(np.int32), h
    if not h.get("ZIMAGE", False) or int(h.get("ZNAXIS", 0)) != 2 or int(h.get("TFIELDS", 0)) != 1:
        raise ValueError("FLAGS is not a 2-D tile-compressed image with one column")
    if int(h.get("ZTILE2", 0)) != 1 or int(h.get("ZTILE1", 0)) != int(h["ZNAXIS1"]):
        raise ValueError(f"FLAGS tiles are not one row each (ZTILE1={h.get('ZTILE1')}, ZTILE2={h.get('ZTILE2')})")
    m = _TFORM_P.match(str(h["TFORM1"]).strip().upper())
    if not m:
        raise ValueError(f"unexpected FLAGS TFORM1={h['TFORM1']!r}")
    ddt = np.dtype(">i4" if m[1] == "P" else ">i8")
    dsize = 2 * ddt.itemsize
    if int(h["NAXIS1"]) != dsize:
        raise ValueError(f"FLAGS row is {h['NAXIS1']} bytes, expected a {dsize}-byte descriptor")
    ny = y1 - y0 + 1
    raw_desc = reader(key, info.data_offset + y0 * dsize, info.data_offset + (y1 + 1) * dsize)
    if len(raw_desc) != ny * dsize:
        raise OSError(f"short read for FLAGS descriptors of {key}")
    desc = np.frombuffer(raw_desc, dtype=ddt).reshape(ny, 2).astype(np.int64)
    counts, offsets = desc[:, 0], desc[:, 1]
    theap = int(h.get("THEAP", int(h["NAXIS1"]) * int(h["NAXIS2"])))
    lo, hi = int(offsets.min()), int((offsets + counts).max())
    heap = reader(key, info.data_offset + theap + lo, info.data_offset + theap + hi)
    if len(heap) != hi - lo:
        raise OSError(f"short read for FLAGS heap of {key}")
    # Minimal compressed HDU holding only these rows; astropy does the RICE_1 decoding.
    mini = h.copy()
    mini["NAXIS2"] = ny
    mini["ZNAXIS2"] = ny
    mini["PCOUNT"] = hi - lo
    for k in ("THEAP", "CHECKSUM", "DATASUM", "ZHECKSUM", "ZDATASUM"):
        mini.remove(k, ignore_missing=True, remove_all=True)
    table = np.empty((ny, 2), dtype=ddt)
    table[:, 0] = counts
    table[:, 1] = offsets - lo
    body = table.tobytes() + heap
    blob = (
        fits.PrimaryHDU().header.tostring().encode("ascii")
        + mini.tostring().encode("ascii")
        + body
        + b"\0" * (_pad(len(body)) - len(body))
    )
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        with fits.open(io.BytesIO(blob), memmap=False) as hl:
            hdu = hl[1]
            if not isinstance(hdu, fits.CompImageHDU):
                raise ValueError("astropy did not recognise the FLAGS rows as a compressed image")
            rows = np.asarray(hdu.data)
            image_header = fits.Header(hdu.header)
    if rows.shape != (ny, int(h["ZNAXIS1"])):
        raise ValueError(f"decompressed FLAGS rows have shape {rows.shape}")
    image_header["NAXIS2"] = int(h["ZNAXIS2"])  # describe the full plane; _shift_header crops it
    return rows[:, x0 : x1 + 1].astype(np.int32), image_header


def read_patch(
    s3_key: str,
    ra: float,
    dec: float,
    size_arcmin: float,
    with_flags: bool = True,
    *,
    with_planes: bool = True,
    reader: RangeReader | None = None,
) -> SpherexImage:
    """A ``size_arcmin`` patch of one L2 file around (ra, dec), read with HTTP Range from S3.

    Same pixels, box and WCS as the IRSA cutout of that file (minus the EPSF table).
    ``with_planes=False`` skips VARIANCE and ZODI (IMAGE only: ~0.4 MB at 5').
    ``mjd`` is mid-exposure (MJD-AVG). ``extra`` holds the S3 key, the 0-based inclusive
    ``bbox`` (x0, x1, y0, y1), ``flags`` ('ok' | 'unavailable' | 'skipped'), the bytes and
    requests used, and what ``write_patch_fits`` needs (plane headers, WCS-WAVE bytes).
    Raises :class:`NoOverlap` when the box misses the detector.
    """
    t0 = time.perf_counter()
    rd = _CountingReader(_resolve(reader))
    d = hdu_directory(s3_key, reader=rd)
    img_info = d["IMAGE"]
    x0, x1, y0, y1 = patch_box(img_info.header, ra, dec, size_arcmin)
    nx, ny = x1 - x0 + 1, y1 - y0 + 1

    def flags_job() -> tuple[np.ndarray, fits.Header] | Exception:
        info = d.get("FLAGS")
        if info is None:
            return ValueError("no FLAGS HDU in the file")
        try:
            return _read_flags(s3_key, info, x0, x1, y0, y1, rd)
        except (ValueError, KeyError) as e:  # format surprises -> 'unavailable'; I/O errors propagate
            return e

    # One Range request per plane, all in flight at once (latency-bound on slow links).
    jobs: dict[str, Callable[[], object]] = {"IMAGE": lambda: _read_rows(s3_key, img_info, x0, x1, y0, y1, rd)}
    for name in ("VARIANCE", "ZODI") if with_planes else ():
        info = d.get(name)
        if info is not None:
            jobs[name] = lambda info=info: _read_rows(s3_key, info, x0, x1, y0, y1, rd)
    if with_flags:
        jobs["FLAGS"] = flags_job
    with ThreadPoolExecutor(max_workers=len(jobs)) as pool:
        futures = {name: pool.submit(fn) for name, fn in jobs.items()}
        out = {name: fut.result() for name, fut in futures.items()}

    plane_headers = {
        name: _shift_header(d[name].header, x0, y0, nx, ny) for name in ("VARIANCE", "ZODI") if name in out
    }
    flags: np.ndarray | None = None
    extra: dict = {"flags": "skipped"}
    if with_flags:
        got = out["FLAGS"]
        if isinstance(got, Exception):
            extra.update(flags="unavailable", flags_error=f"{type(got).__name__}: {got}")
        else:
            flags, fh = got
            plane_headers["FLAGS"] = _shift_header(fh, x0, y0, nx, ny)
            extra["flags"] = "ok"
    data = np.asarray(out["IMAGE"], dtype=np.float32)
    planes = {name: out.get(name) for name in ("VARIANCE", "ZODI")}

    hdr = _shift_header(img_info.header, x0, y0, nx, ny)
    hdr["PATCH_X0"] = (x0, "0-based detector column of patch pixel 0")
    hdr["PATCH_Y0"] = (y0, "0-based detector row of patch pixel 0")
    hdr["PATCHSRC"] = ("s3range", "read with HTTP Range from the S3 L2 file")
    if extra["flags"] != "ok":
        hdr["PATCHFLG"] = (extra["flags"], "FLAGS not in this patch: unknown, NOT clean")
    extra.update(
        s3_key=s3_key,
        bbox=(x0, x1, y0, y1),
        bytes=rd.bytes,
        requests=rd.requests,
        seconds=time.perf_counter() - t0,
        mjd_obs=float(hdr["MJD-OBS"]) if "MJD-OBS" in hdr else None,
        plane_headers=plane_headers,
        primary_header=d.primary,
        wcs_wave=d.wcs_wave,
    )
    return SpherexImage(
        data=data,
        flags=flags,
        variance=None if planes["VARIANCE"] is None else np.asarray(planes["VARIANCE"], dtype=np.float32),
        zodi=None if planes["ZODI"] is None else np.asarray(planes["ZODI"], dtype=np.float32),
        wcs=_celestial_wcs(hdr),
        header=hdr,
        obs_id=str(hdr.get("OBSID", "")),
        detector=int(hdr.get("DETECTOR", 0)),
        mjd=_mid_mjd(hdr),
        date_obs=str(hdr.get("DATE-OBS", "")),
        source=f"{settings.S3_HTTPS}/{s3_key}",
        extra=extra,
    )


# --- writing and batch fetching -----------------------------------------------


def _plane_header(img: SpherexImage, name: str) -> fits.Header:
    stored = img.extra.get("plane_headers", {}).get(name)
    if stored is not None:
        return stored
    h = img.header.copy()  # same pixel grid and WCS as IMAGE
    h.remove("BUNIT", ignore_missing=True)
    return h


def write_patch_fits(img: SpherexImage, path: str | Path) -> Path:
    """Write a small MEF (PRIMARY, IMAGE, FLAGS if known, VARIANCE, ZODI, WCS-WAVE) atomically.

    The layout matches an IRSA cutout without EPSF, so ``fits_io.read_spherex`` reads it.
    WCS-WAVE is copied byte for byte from the original file when available.
    """
    path = Path(path)
    primary = img.extra.get("primary_header")
    hdus: list[fits.hdu.base.ExtensionHDU | fits.PrimaryHDU] = [
        fits.PrimaryHDU(header=primary.copy() if primary is not None else None)
    ]

    def plane(name: str, arr: np.ndarray, dtype: str, header: fits.Header) -> fits.ImageHDU:
        h = header.copy()
        for k in ("XTENSION", "BITPIX", "NAXIS", "NAXIS1", "NAXIS2", "PCOUNT", "GCOUNT"):
            h.remove(k, ignore_missing=True)
        return fits.ImageHDU(data=np.ascontiguousarray(arr, dtype=dtype), header=h, name=name)

    hdus.append(plane("IMAGE", img.data, ">f4", img.header))
    if img.flags is not None:
        hdus.append(plane("FLAGS", img.flags, ">i4", _plane_header(img, "FLAGS")))
    if img.variance is not None:
        hdus.append(plane("VARIANCE", img.variance, ">f4", _plane_header(img, "VARIANCE")))
    if img.zodi is not None:
        hdus.append(plane("ZODI", img.zodi, ">f4", _plane_header(img, "ZODI")))
    buf = io.BytesIO()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", fits.verify.VerifyWarning)
        fits.HDUList(hdus).writeto(buf, output_verify="silentfix")
    raw = buf.getvalue()
    wcs_wave = img.extra.get("wcs_wave") or b""
    if wcs_wave and len(wcs_wave) % BLOCK == 0 and wcs_wave.startswith(b"XTENSION="):
        raw += wcs_wave
    _atomic_write(path, raw)
    return path


def _frame_key(frame: FrameRef) -> str:
    if frame.s3_key:
        return frame.s3_key.lstrip("/")
    if frame.irsa_uri:
        return irsa_uri_to_s3_key(frame.irsa_uri)
    raise ValueError(f"FrameRef {frame.obs_id}D{frame.detector} has neither s3_key nor irsa_uri")


def patch_path(s3_key: str, ra: float, dec: float, size_arcmin: float) -> Path:
    """Disk-cache location of a patch: readable, unique per (key, ra, dec, size)."""
    release = s3_key.lstrip("/").split("/", 1)[0]
    return (
        settings.CACHE_DIR
        / "s3patch"
        / f"{ra:.7f}_{dec:+.7f}_{size_arcmin:g}am"
        / release
        / f"{Path(s3_key).stem}.fits"
    )


def _usable(path: Path) -> bool:
    try:
        return path.stat().st_size > 0
    except OSError:
        return False


def fetch_patch(frame: FrameRef, ra: float, dec: float, size_arcmin: float) -> Path:
    """Patch of one frame as a small MEF on disk (cached); raises NoOverlap/OSError/ValueError.

    Concurrent calls for the same patch (duplicate frames in a batch) read it once.
    """
    key = _frame_key(frame)
    dest = patch_path(key, ra, dec, size_arcmin)
    with _patch_locks.hold(str(dest)):
        if _usable(dest):
            return dest
        img = read_patch(key, ra, dec, size_arcmin)
        try:
            return write_patch_fits(img, dest)
        except OSError:
            if _usable(dest):  # another process wrote this same patch first and still has it open
                return dest
            raise


def fetch_patches_report(
    frames: list[FrameRef], ra: float, dec: float, size_arcmin: float, max_workers: int | None = None
) -> tuple[list[tuple[FrameRef, Path]], list[tuple[FrameRef, str]]]:
    """Fetch every patch; return ([(frame, path)], [(frame, reason)]) without raising (for WS2)."""
    return fetch_report(lambda f: fetch_patch(f, ra, dec, size_arcmin), frames, max_workers or MAX_PARALLEL_S3)


def fetch_patches(frames: list[FrameRef], ra: float, dec: float, size_arcmin: float) -> list[Path]:
    """Drop-in replacement for ``cutouts.fetch_cutouts``: paths aligned 1:1 with ``frames``.

    If any frame fails (no overlap, network...), raises :class:`FetchError` carrying the
    partial results and the failures.
    """
    results, failures = fetch_patches_report(frames, ra, dec, size_arcmin)
    if failures:
        raise FetchError(results, failures)
    return [p for _, p in results]
