"""Every SPHEREx exposure of one sky point, as small stamps read straight from S3 (WS1).

Feeds the spectrum tab, light curves and the time video for ANY clicked point (docs/VISION.md).
:func:`point_series` finds every L2 frame covering (ra, dec) with ``irsa.search_frames_report`` (no 40-frame
cap; deep collections are opt-in through ``collections``) and reads, for each frame, a ``box_px`` x ``box_px``
stamp of IMAGE, VARIANCE, ZODI and FLAGS with HTTP Range requests, plus the wavelength and bandwidth that
the frame measured AT (ra, dec) (WCS-WAVE). It returns clean, documented samples; photometry, spectra and
light curves are WS2/WS3 work.

Why it is fast (layout verified live on 897 DR1+QR3 files at Barnard's Star and R Dra, 2026-11-14):

* S3 answers ~180 ms per request and this machine tops out at ~100-170 requests/s with 32-48 threads but
  ~15 MB/s, so the REQUEST count dominates: one request costs as much as ~100 KB of transfer.
* Every L2 file has the same header lengths per detector: PRIMARY 2880 B, IMAGE 25920 (D1/D2) or 23040
  (D3-D6), FLAGS 17280, VARIANCE 11520, ZODI 11520; only the FLAGS heap size (PCOUNT) varies per file.
  Those lengths are used as HINTS to read several headers per request; every hint is CHECKED against the
  headers actually read (and learned per detector), and a wrong hint only costs extra requests, never
  wrong pixels.
* Round 1 (2 parallel requests): PRIMARY+IMAGE header, and FLAGS header + all 2040 row descriptors
  (16 KB) at the offset the hints predict. Round 2 (<= 6 parallel requests): IMAGE stamp rows, the FLAGS
  heap of those rows, the VARIANCE header, VARIANCE rows, the ZODI header and ZODI rows (the VARIANCE and
  ZODI row reads are placed by the hints, with one block of slack, then checked against their headers).
  Regions closer than :data:`MERGE_GAP` are fetched in one request, so stamps near the top/bottom of the
  detector need fewer.
* The WCS-WAVE table is identical in every file of one detector that names the same
  ``HISTORY [CALIB] spectral_wcs <id>`` calibration (897 files, 6 ids): it is read once (a 5760-byte
  suffix Range of one file) and cached by (detector, id).
* The verified per-file layout (offsets, reduced IMAGE header, FLAGS descriptors) is cached, so a second
  point on the same frames needs ONE round of <= 4 requests per frame; the whole series is cached too
  (npz + json), so asking for the same point again is instant.
* CPU matters as much as the network (one GIL): headers are scanned as raw cards and only the few cards
  needed are parsed, WCS() gets only the celestial cards, FLAGS rows go through astropy's RICE_1 codec
  directly (falling back to its compressed-HDU path), and s3range's session loads the CA bundle once.

Measured live 2026-11-14 (Buenos Aires, 48 concurrent requests, 11-px stamps, fresh cache):
Barnard's Star 358 frames: 3.4 s SIA + 15.1 s of reads (7.97 requests, 413 KB, 42 ms per frame, 2 rounds);
layouts cached 7.9 s (4 requests, 291 KB per frame, 1 round); series cached 0.04 s. R Dra DR1+QR3 539 frames:
4.3 s + 23.3 s. The previous path (HDU walk + ``read_patch`` + a FITS per frame) took 53.8 s for Barnard.

Stamps are bit-identical to the same pixels of ``s3range.read_patch`` and of the full file (tests). They
are in native detector orientation (NOT north-up; MWIR frames are flipped in x, ``DETCOORD='sky'``, per
docs/RECON_SPHEREX.md §2.4), numpy order ``[row, column]`` with row 0 = detector row ``y0``. (ra, dec) is a
FIXED position: propagate proper motion yourself (Barnard's Star moves ~1.7 px per year) or use a box large
enough. Bright stars saturate: Barnard's and R Dra's central pixels are often NaN with OVERFLOW (bit 1) set.
"""

from __future__ import annotations

import base64
import hashlib
import io as _io
import json
import logging
import math
import os
import re
import threading
import time
import warnings
import zlib
from collections import Counter, OrderedDict
from collections.abc import Iterable, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from astropy.io import fits
from astropy.wcs import WCS, FITSFixedWarning

from .. import settings
from ..models import FrameRef
from . import fits_io, irsa, s3range
from .cutouts import KeyedLocks, NoOverlap
from .epochs import VISIT_GAP_HOURS, _pick_spread

log = logging.getLogger(__name__)

__all__ = [
    "PLANES",
    "NoOverlap",
    "PointSample",
    "PointSeries",
    "point_series",
    "read_point_sample",
    "select_frames",
]

PLANES = ("IMAGE", "VARIANCE", "ZODI", "FLAGS")
"""Planes read for every stamp (IMAGE is always read)."""
BLOCK = s3range.BLOCK
CARD = s3range.CARD
MERGE_GAP = int(os.environ.get("ERRANTE_POINT_MERGE_GAP", "160000"))
"""Byte regions of one file closer than this are fetched in ONE request (one request ~ 100-150 KB of transfer)."""
MAX_PARALLEL = int(os.environ.get("ERRANTE_POINT_MAX_PARALLEL", "48"))
"""Concurrent S3 requests of a series (32 -> 48 helped; 64 gave multi-second request tails in a benchmark)."""
SERIES_FORMAT = 1
LAYOUT_FORMAT = 1
LAYOUT_TTL_S = float(os.environ.get("ERRANTE_POINT_LAYOUT_TTL_S", str(7 * 86400)))
"""Cached per-file layouts older than this are re-read (S3 objects were rewritten on 2026-11-11)."""
SERIES_TTL_S = float(os.environ.get("ERRANTE_POINT_TTL_S", str(settings.QUERY_CACHE_TTL_S)))
"""A cached series is reused for this long (new QR3 weeks appear weekly). 0 disables the series cache."""
MAX_BOX_PX = 255
_WAVE_TAIL = 2 * BLOCK  # WCS-WAVE = last 5760 B of every L2 file seen (DATA.md §2, RECON §2.4)
_SWCS = re.compile(r"\[CALIB\]\s+spectral_wcs\s+([0-9A-Za-z_.-]+)")
# Cards kept from the IMAGE header. _CEL_CARD: the celestial TAN-SIP WCS only (WCS() on it is ~3x faster than
# on the full 276-card header and gives the same pixels: tested on a real DR1 header). _ALT_CARD: the 'A'
# (0-based detector pixel) and 'W' (WAVE-TAB) alternates that fits_io.wavelength_from_table uses.
_CEL_CARD = re.compile(
    r"^(WCSAXES|CTYPE[12]|CUNIT[12]|CRPIX[12]|CRVAL[12]|CDELT[12]|CROTA[12]|CD[12]_[12]|PC[12]_[12]|PV[12]_\d+"
    r"|LONPOLE|LATPOLE|RADESYS|EQUINOX|MJDREF|NAXIS[12]?)$|^(A|B|AP|BP)_(ORDER|\d+_\d+)$"
)
_ALT_CARD = re.compile(
    r"^(WCSAXES|WCSNAME|CTYPE[12]|CUNIT[12]|CNAME[12]|CRPIX[12]|CRVAL[12]|CDELT[12]|CD[12]_[12]|PC[12]_[12]"
    r"|PV[12]_\d+|PS[12]_\d+|LONPOLE|LATPOLE)[A-Z]$"
)
META_KEYS = (
    "OBSID",
    "DETECTOR",
    "EXPIDN",
    "DATE-OBS",
    "DATE-AVG",
    "DATE-END",
    "MJD-OBS",
    "MJD-AVG",
    "MJD-END",
    "XPOSURE",
    "TELAPSE",
    "BUNIT",
    "OMEGA_MEDIAN",
    "OMEGA_STDDEV",
    "PSF_FWHM",
    "SPS_EPA",
    "L2DQAFLG",
    "PXSRCMSK",
    "DETCOORD",
    "HE_AIRGLOW_CONT",
    "AURORA_CONT",
    "SHUTTLE_GLOW_CONT",
    "X_SC",
    "Y_SC",
    "Z_SC",
    "VX_SC",
    "VY_SC",
    "VZ_SC",
)
"""IMAGE header values copied to ``PointSample.meta`` (when present)."""
_FLAGS_CARD = re.compile(r"^(XTENSION|BITPIX|NAXIS\d*|PCOUNT|GCOUNT|TFIELDS|TTYPE1|TFORM1|TDIM1|THEAP|EXTNAME|Z.+)$")


# --- byte bookkeeping ---------------------------------------------------------------------------------------


class _Segments:
    """Bytes already read from one S3 object, as merged non-overlapping (start, bytes) parts."""

    def __init__(self) -> None:
        self.parts: list[tuple[int, bytes]] = []

    def add(self, start: int, data: bytes) -> None:
        if not data:
            return
        end = start + len(data)
        lo, hi, keep, touching = start, end, [], []
        for s, d in self.parts:
            if s + len(d) < start or s > end:
                keep.append((s, d))
            else:
                touching.append((s, d))
                lo, hi = min(lo, s), max(hi, s + len(d))
        buf = bytearray(hi - lo)
        for s, d in touching:
            buf[s - lo : s - lo + len(d)] = d
        buf[start - lo : end - lo] = data
        keep.append((lo, bytes(buf)))
        self.parts = sorted(keep)

    def covers(self, start: int, stop: int) -> bool:
        return any(s <= start and stop <= s + len(d) for s, d in self.parts)

    def get(self, start: int, stop: int) -> bytes | None:
        for s, d in self.parts:
            if s <= start and stop <= s + len(d):
                return d[start - s : stop - s]
        return None

    def from_(self, start: int) -> bytes:
        """The contiguous bytes known from ``start`` on (b"" if none)."""
        for s, d in self.parts:
            if s <= start < s + len(d):
                return d[start - s :]
        return b""


class _Stats:
    """Requests and bytes spent on one frame (only touched by that frame's thread)."""

    __slots__ = ("bytes", "requests", "rounds")

    def __init__(self) -> None:
        self.requests = 0
        self.bytes = 0
        self.rounds = 0


def _coalesce(regions: Iterable[tuple[int, int]], gap: int) -> list[tuple[int, int]]:
    out: list[list[int]] = []
    for a, b in sorted((max(0, a), b) for a, b in regions if b > max(0, a)):
        if out and a - out[-1][1] <= gap:
            out[-1][1] = max(out[-1][1], b)
        else:
            out.append([a, b])
    return [(a, b) for a, b in out]


class _IO:
    """Issues the Range requests of a frame: missing regions coalesced, then fetched in parallel."""

    def __init__(self, pool: ThreadPoolExecutor | None = None, gap: int | None = None):
        self.pool = pool
        self.gap = MERGE_GAP if gap is None else gap

    def fetch(self, key: str, seg: _Segments, regions: Iterable[tuple[int, int]], stats: _Stats) -> None:
        plan = _coalesce([r for r in regions if not seg.covers(max(0, r[0]), r[1])], self.gap)
        if not plan:
            return
        stats.rounds += 1

        def one(a: int, b: int) -> tuple[int, bytes]:
            return a, s3range.read_range(key, a, b)  # looked up at call time: monkeypatchable

        if len(plan) == 1 or self.pool is None:
            results = [one(a, b) for a, b in plan]
        else:
            futures = [self.pool.submit(one, a, b) for a, b in plan]
            results = [f.result() for f in futures]
        for a, data in results:
            stats.requests += 1
            stats.bytes += len(data)
            seg.add(a, data)

    def tail(self, key: str, nbytes: int, stats: _Stats) -> tuple[bytes, int]:
        data, size = s3range.read_tail(key, nbytes)
        stats.requests += 1
        stats.bytes += len(data)
        return data, size


def _bytes(key: str, start: int, stop: int, io: _IO, seg: _Segments, stats: _Stats) -> bytes:
    data = seg.get(start, stop)
    if data is None:
        io.fetch(key, seg, [(start, stop)], stats)
        data = seg.get(start, stop)
    if data is None:
        raise OSError(f"short read for bytes [{start}, {stop}) of {key}")
    return data


class _RawHeader:
    """A header as raw 80-byte cards. Only the few cards a caller needs are ever parsed by astropy
    (parsing whole 23 KB L2 headers was the main CPU cost of a cold read)."""

    __slots__ = ("cards", "length")

    def __init__(self, raw: bytes, end: int, length: int):
        self.cards = [raw[i : i + CARD] for i in range(0, end, CARD)]
        self.length = length  # bytes incl. the END card and padding

    @staticmethod
    def keyword(card: bytes) -> str:
        kw = card[:8].rstrip().decode("ascii", "replace")
        if kw == "HIERARCH" and b"=" in card:
            return card[9 : card.index(b"=")].strip().decode("ascii", "replace")
        return kw

    def text(self, keep) -> str:
        """The cards whose keyword passes ``keep``, concatenated (a header string without END)."""
        return "".join(c.decode("ascii", "replace") for c in self.cards if keep(self.keyword(c)))

    def header(self, keep) -> fits.Header:
        return fits.Header.fromstring(self.text(keep))

    def grep(self, pattern: re.Pattern) -> list[str]:
        return [m.group(1) for c in self.cards for m in [pattern.search(c.decode("ascii", "replace"))] if m]


_STRUCT = frozenset(
    {"SIMPLE", "XTENSION", "BITPIX", "NAXIS", "NAXIS1", "NAXIS2", "PCOUNT", "GCOUNT", "EXTNAME", "BSCALE", "BZERO"}
    | {"BUNIT", "TFIELDS", "TFORM1", "THEAP"}
)


def _header_at(
    key: str, offset: int, io: _IO, seg: _Segments, stats: _Stats, extname: str | None
) -> tuple[_RawHeader, fits.Header]:
    """The header that starts at ``offset`` (fetching more while its END card is missing): raw cards plus a
    small astropy Header of the structural keywords. Raises ValueError if no header starts there or its
    EXTNAME is not ``extname``."""
    chunk = 4 * BLOCK
    while True:
        buf = seg.from_(offset)
        if len(buf) >= 9 and not (buf.startswith(b"SIMPLE  =") or buf.startswith(b"XTENSION=")):
            raise ValueError(f"no FITS header at byte {offset} of {key} (starts with {buf[:16]!r})")
        end = s3range._find_end(buf)
        if end is not None and len(buf) >= s3range.padded(end + CARD):
            raw = _RawHeader(buf, end, s3range.padded(end + CARD))
            h = raw.header(_STRUCT.__contains__)
            if extname is not None:
                name = str(h.get("EXTNAME", "")).strip().upper()
                if name != extname:
                    raise ValueError(f"expected HDU {extname} at byte {offset} of {key}, found {name or '?'}")
            return raw, h
        if len(buf) >= s3range.MAX_HEADER_BYTES:
            raise ValueError(f"no END card in the first {len(buf)} bytes of the header at byte {offset} of {key}")
        before = len(buf)
        io.fetch(key, seg, [(offset + before, offset + before + chunk)], stats)
        if len(seg.from_(offset)) <= before:
            raise ValueError(f"truncated FITS header at byte {offset} of {key}")
        chunk *= 2


# --- per-file layout ---------------------------------------------------------------------------------------


@dataclass(frozen=True)
class _Plane:
    """An uncompressed 2-D image plane: where its data starts and how to decode it."""

    offset: int
    bitpix: int
    nx: int
    ny: int
    bscale: float = 1.0
    bzero: float = 0.0
    bunit: str = ""

    @classmethod
    def from_header(cls, h: fits.Header, offset: int) -> _Plane:
        if int(h.get("NAXIS", 0)) != 2 or int(h["BITPIX"]) not in s3range._DTYPES:
            raise ValueError(f"{h.get('EXTNAME', '?')} is not a 2-D image (NAXIS={h.get('NAXIS')})")
        if str(h.get("XTENSION", "IMAGE")).strip() != "IMAGE":
            raise ValueError(f"{h.get('EXTNAME', '?')} is not an uncompressed image")
        return cls(
            offset,
            int(h["BITPIX"]),
            int(h["NAXIS1"]),
            int(h["NAXIS2"]),
            float(h.get("BSCALE", 1.0)),
            float(h.get("BZERO", 0.0)),
            str(h.get("BUNIT", "")).strip(),
        )

    @property
    def itemsize(self) -> int:
        return abs(self.bitpix) // 8

    @property
    def row_bytes(self) -> int:
        return self.nx * self.itemsize

    @property
    def size(self) -> int:
        return self.ny * self.row_bytes

    def region(self, box: tuple[int, int, int, int], slack: int = 0) -> tuple[int, int]:
        """Bytes [start, stop) holding rows y0..y1, columns x0..x1 (``slack`` extra bytes on each side)."""
        x0, x1, y0, y1 = box
        start = self.offset + y0 * self.row_bytes + x0 * self.itemsize
        stop = self.offset + y1 * self.row_bytes + (x1 + 1) * self.itemsize
        return start - slack, stop + slack

    def extract(self, buf: bytes, box: tuple[int, int, int, int]) -> np.ndarray:
        """The (ny, nx) stamp from the bytes of :meth:`region` (no slack)."""
        x0, x1, y0, y1 = box
        dt = np.dtype(s3range._DTYPES[self.bitpix])
        arr = np.ndarray((y1 - y0 + 1, x1 - x0 + 1), dtype=dt, buffer=buf, strides=(self.row_bytes, self.itemsize))
        out = arr.astype(dt.newbyteorder("="))
        if (self.bscale, self.bzero) != (1.0, 0.0):
            out = out * self.bscale + self.bzero
        return out

    def to_json(self) -> dict:
        return {k: getattr(self, k) for k in ("offset", "bitpix", "nx", "ny", "bscale", "bzero", "bunit")}


@dataclass(frozen=True, eq=False)
class _Flags:
    """How to read FLAGS rows: RICE row tiles (header + heap + descriptors), a plain image, or not at all."""

    header: str = ""  # compressed-HDU cards (_FLAGS_CARD) as text, for astropy's slow path
    heap: int = 0  # absolute byte offset of the heap
    desc: np.ndarray | None = None  # (NAXIS2, 2) int64 (count, heap offset) per row
    plane: _Plane | None = None  # uncompressed FLAGS
    rice: tuple[int, int, int] | None = None  # (blocksize, bytepix, tilesize) when the fast decoder applies
    error: str = ""  # why FLAGS cannot be read (unknown, NOT clean)

    def heap_region(self, y0: int, y1: int) -> tuple[int, int]:
        rows = self.desc[y0 : y1 + 1]
        return self.heap + int(rows[:, 1].min()), self.heap + int((rows[:, 0] + rows[:, 1]).max())

    def decode(self, y0: int, y1: int, heap: bytes, heap_lo: int) -> np.ndarray:
        """Rows y0..y1 (all columns, int32) from the heap bytes starting at heap offset ``heap_lo``."""
        rows = self.desc[y0 : y1 + 1]
        if self.rice is not None:
            try:
                return _rice_rows(self.rice, rows, heap, heap_lo)
            except Exception as e:  # noqa: BLE001  (private astropy codec: fall back to the public path)
                log.debug("fast RICE decode failed (%s); using astropy's compressed HDU", e)
        return s3range.decode_flag_rows(fits.Header.fromstring(self.header), rows, heap, heap_lo)[0]

    def to_json(self) -> dict:
        return {
            "header": self.header,
            "heap": self.heap,
            "desc": None if self.desc is None else base64.b64encode(self.desc.astype("<i8").tobytes()).decode(),
            "plane": None if self.plane is None else self.plane.to_json(),
            "rice": None if self.rice is None else list(self.rice),
            "error": self.error,
        }

    @classmethod
    def from_json(cls, d: dict) -> _Flags:
        desc = None
        if d.get("desc"):
            desc = np.frombuffer(base64.b64decode(d["desc"]), dtype="<i8").reshape(-1, 2).astype(np.int64)
        return cls(
            header=str(d.get("header") or ""),
            heap=int(d.get("heap", 0)),
            desc=desc,
            plane=None if d.get("plane") is None else _Plane(**d["plane"]),
            rice=None if d.get("rice") is None else tuple(int(v) for v in d["rice"]),
            error=str(d.get("error", "")),
        )


def _rice_settings(h: fits.Header) -> tuple[int, int, int] | None:
    """(blocksize, bytepix, tilesize) if astropy's RICE_1 codec alone reproduces the pixels, else None."""
    if str(h.get("ZCMPTYPE", "")).strip().upper() != "RICE_1" or int(h.get("ZBITPIX", 0)) not in (8, 16, 32):
        return None
    if any(k in h for k in ("ZSCALE", "ZZERO", "ZBLANK", "BSCALE", "BZERO", "ZQUANTIZ")):
        return None
    params = {str(h[f"ZNAME{i}"]).strip().upper(): h.get(f"ZVAL{i}") for i in range(1, 10) if f"ZNAME{i}" in h}
    blocksize = int(params.get("BLOCKSIZE", 32))
    bytepix = int(params.get("BYTEPIX", int(h["ZBITPIX"]) // 8))
    if bytepix != int(h["ZBITPIX"]) // 8:
        return None
    return blocksize, bytepix, int(h["ZTILE1"])


def _rice_rows(rice: tuple[int, int, int], rows: np.ndarray, heap: bytes, heap_lo: int) -> np.ndarray:
    from astropy.io.fits.hdu.compressed._codecs import Rice1  # private: any failure -> astropy HDU path

    blocksize, bytepix, tilesize = rice
    codec = Rice1(blocksize=blocksize, bytepix=bytepix, tilesize=tilesize)
    out = np.empty((len(rows), tilesize), dtype=np.int32)
    for i, (count, offset) in enumerate(rows):
        start = int(offset) - heap_lo
        if start < 0 or start + int(count) > len(heap):
            raise ValueError("FLAGS heap slice outside the bytes read")
        out[i] = codec.decode(heap[start : start + int(count)])
    return out


@dataclass(eq=False)
class _Layout:
    """Everything needed to cut a stamp from one L2 file, verified against its own headers."""

    key: str
    wcs_text: str  # celestial TAN-SIP cards of the IMAGE header (WCS() on the full header is ~3x slower)
    aux_text: str  # 'A'/'W' alternate WCS cards + META_KEYS of the IMAGE header
    image: _Plane
    flags: _Flags
    var_header: int  # absolute offset of the VARIANCE header (= end of the FLAGS HDU)
    variance: _Plane | None = None
    zodi: _Plane | None = None
    wave_id: str = ""
    lengths: dict = field(default_factory=dict)  # verified header lengths (for the hints)
    _wcs: WCS | None = None
    _aux: fits.Header | None = None

    @property
    def wcs(self) -> WCS:
        if self._wcs is None:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", FITSFixedWarning)
                self._wcs = WCS(fits.Header.fromstring(self.wcs_text))
        return self._wcs

    @property
    def aux(self) -> fits.Header:
        if self._aux is None:
            self._aux = fits.Header.fromstring(self.aux_text)
        return self._aux

    def to_bytes(self) -> bytes:
        doc = {
            "format": LAYOUT_FORMAT,
            "key": self.key,
            "created": time.time(),
            "wcs": self.wcs_text,
            "aux": self.aux_text,
            "image": self.image.to_json(),
            "flags": self.flags.to_json(),
            "var_header": self.var_header,
            "variance": None if self.variance is None else self.variance.to_json(),
            "zodi": None if self.zodi is None else self.zodi.to_json(),
            "wave_id": self.wave_id,
            "lengths": self.lengths,
        }
        return zlib.compress(json.dumps(doc, separators=(",", ":")).encode("ascii"), 6)

    @classmethod
    def from_bytes(cls, raw: bytes, key: str) -> _Layout | None:
        doc = json.loads(zlib.decompress(raw).decode("ascii"))
        if doc.get("format") != LAYOUT_FORMAT or doc.get("key") != key:
            return None
        if LAYOUT_TTL_S > 0 and time.time() - float(doc.get("created", 0)) > LAYOUT_TTL_S:
            return None
        return cls(
            key=key,
            wcs_text=doc["wcs"],
            aux_text=doc["aux"],
            image=_Plane(**doc["image"]),
            flags=_Flags.from_json(doc["flags"]),
            var_header=int(doc["var_header"]),
            variance=None if doc.get("variance") is None else _Plane(**doc["variance"]),
            zodi=None if doc.get("zodi") is None else _Plane(**doc["zodi"]),
            wave_id=str(doc.get("wave_id", "")),
            lengths=dict(doc.get("lengths") or {}),
        )


def _image_texts(raw: _RawHeader) -> tuple[str, str]:
    """(celestial WCS cards, alternate-WCS + META cards) of an IMAGE header."""
    return raw.text(_CEL_CARD.match), raw.text(lambda k: bool(_ALT_CARD.match(k)) or k in META_KEYS)


def _wave_id(raw: _RawHeader, detector: int, key: str) -> str:
    """'D<det>_<spectral_wcs calibration id>' from the IMAGE HISTORY, or a per-file id when it is missing."""
    ids = raw.grep(_SWCS)
    if not ids:
        return "file_" + hashlib.sha256(key.encode()).hexdigest()[:24]
    return f"D{int(detector)}_{ids[-1]}"


def _flags_from_header(
    raw: _RawHeader, h: fits.Header, data_at: int, key: str, io: _IO, seg: _Segments, stats: _Stats
) -> _Flags:
    """FLAGS reading recipe from its header; reads the row descriptors (all rows, ~16 KB) if needed."""
    if str(h.get("XTENSION", "")).strip() == "IMAGE":
        return _Flags(plane=_Plane.from_header(h, data_at))
    full = raw.header(_FLAGS_CARD.match)
    try:
        ddt = s3range.flag_descriptor_dtype(full)
    except (ValueError, KeyError) as e:
        return _Flags(error=f"{type(e).__name__}: {e}")
    nbytes = int(full["NAXIS1"]) * int(full["NAXIS2"])
    desc = np.frombuffer(_bytes(key, data_at, data_at + nbytes, io, seg, stats), dtype=ddt)
    return _Flags(
        header=raw.text(_FLAGS_CARD.match),
        heap=data_at + int(full.get("THEAP", nbytes)),
        desc=desc.reshape(-1, 2).astype(np.int64),
        rice=_rice_settings(full),
    )


# Layout hints: header lengths seen on 897 real DR1+QR3 files (2026-11-14). Checked on every read.
@dataclass(frozen=True)
class _Hints:
    primary: int = BLOCK
    image: int = 8 * BLOCK
    image_data: int = 2040 * 2040 * 4
    flags: int = 6 * BLOCK
    flags_table: int = 2040 * 8
    variance: int = 4 * BLOCK
    zodi: int = 4 * BLOCK


_DEFAULT_HINTS = {d: _Hints(image=(9 if d in (1, 2) else 8) * BLOCK) for d in range(1, 7)}
_learned: dict[int, _Hints] = {}
_hints_lock = threading.Lock()


def _hints(detector: int) -> _Hints:
    with _hints_lock:
        return _learned.get(detector) or _DEFAULT_HINTS.get(detector) or _Hints()


def _learn(detector: int, lengths: dict) -> None:
    if not set(_Hints.__dataclass_fields__) <= set(lengths):
        return
    with _hints_lock:
        _learned[detector] = _Hints(**{k: int(lengths[k]) for k in _Hints.__dataclass_fields__})


# Memory + disk caches of layouts (by S3 key) and wavelength tables (by wave id).
_layout_mem: OrderedDict[tuple[str, str], _Layout] = OrderedDict()
_layout_lock = threading.Lock()
_LAYOUT_MEM_MAX = 1024
_wave_mem: dict[tuple[str, str], fits_io.WaveTable] = {}
_wave_locks = KeyedLocks()


def _layout_path(key: str) -> Path:
    h = hashlib.sha256(key.encode()).hexdigest()[:24]
    return settings.CACHE_DIR / "point" / "layout" / h[:2] / f"{h}.json.z"


def _cached_layout(key: str) -> _Layout | None:
    mkey = (str(settings.CACHE_DIR), key)
    with _layout_lock:
        hit = _layout_mem.get(mkey)
        if hit is not None:
            _layout_mem.move_to_end(mkey)
            return hit
    try:
        layout = _Layout.from_bytes(_layout_path(key).read_bytes(), key)
    except (OSError, ValueError, KeyError, TypeError, zlib.error):
        return None
    if layout is not None:
        _remember_layout(layout, write=False)
    return layout


def _remember_layout(layout: _Layout, write: bool = True) -> None:
    mkey = (str(settings.CACHE_DIR), layout.key)
    with _layout_lock:
        _layout_mem[mkey] = layout
        _layout_mem.move_to_end(mkey)
        while len(_layout_mem) > _LAYOUT_MEM_MAX:
            _layout_mem.popitem(last=False)
    if write:
        s3range._atomic_write(_layout_path(layout.key), layout.to_bytes(), best_effort=True)


def _read_front(key: str, detector: int, io: _IO, seg: _Segments, stats: _Stats) -> _Layout:
    """Round 1 of a cold read: PRIMARY + IMAGE header and FLAGS header + row descriptors (hint-placed)."""
    h = _hints(detector)
    img_end = h.primary + h.image
    flags_at = img_end + s3range.padded(h.image_data)
    io.fetch(
        key,
        seg,
        [(0, img_end + BLOCK), (flags_at - BLOCK, flags_at + h.flags + h.flags_table + BLOCK)],
        stats,
    )
    if not seg.from_(0)[:9] == b"SIMPLE  =":
        raise ValueError(f"{key} is not a FITS file")
    praw, prim = _header_at(key, 0, io, seg, stats, None)
    ih_at = praw.length + s3range.padded(s3range.data_size(prim))
    iraw, ih = _header_at(key, ih_at, io, seg, stats, "IMAGE")
    image = _Plane.from_header(ih, ih_at + iraw.length)
    fh_at = image.offset + s3range.padded(s3range.data_size(ih))
    fraw, fh = _header_at(key, fh_at, io, seg, stats, "FLAGS")
    f_data = fh_at + fraw.length
    flags = _flags_from_header(fraw, fh, f_data, key, io, seg, stats)
    lengths = {
        "primary": praw.length,
        "image": iraw.length,
        "image_data": s3range.data_size(ih),
        "flags": fraw.length,
        "flags_table": int(fh.get("NAXIS1", 0)) * int(fh.get("NAXIS2", 0)),
    }
    wcs_text, aux_text = _image_texts(iraw)
    return _Layout(
        key=key,
        wcs_text=wcs_text,
        aux_text=aux_text,
        image=image,
        flags=flags,
        var_header=f_data + s3range.padded(s3range.data_size(fh)),
        wave_id=_wave_id(iraw, detector, key),
        lengths=lengths,
    )


def _raw(h: fits.Header) -> _RawHeader:
    text = h.tostring().encode("ascii")
    end = s3range._find_end(text)
    return _RawHeader(text, len(text) if end is None else end, len(text))


def _layout_from_directory(d: s3range.HduDirectory, io: _IO, seg: _Segments, stats: _Stats) -> _Layout:
    """A layout from an s3range HDU directory (already cached by a field build, or walked as a fallback)."""
    names = [x.name for x in d.hdus]
    for name in ("IMAGE", "FLAGS", "VARIANCE", "ZODI"):
        if name not in names:
            raise ValueError(f"{d.key} has no {name} HDU (HDUs: {names})")
    img, fl, var, zod = d["IMAGE"], d["FLAGS"], d["VARIANCE"], d["ZODI"]
    if names.index("VARIANCE") != names.index("FLAGS") + 1:
        raise ValueError(f"unexpected HDU order in {d.key}: {names}")
    iraw = _raw(img.header)
    wcs_text, aux_text = _image_texts(iraw)
    return _Layout(
        key=d.key,
        wcs_text=wcs_text,
        aux_text=aux_text,
        image=_Plane.from_header(img.header, img.data_offset),
        flags=_flags_from_header(_raw(fl.header), fl.header, fl.data_offset, d.key, io, seg, stats),
        var_header=var.header_offset,
        variance=_Plane.from_header(var.header, var.data_offset),
        zodi=_Plane.from_header(zod.header, zod.data_offset),
        wave_id=_wave_id(iraw, int(img.header.get("DETECTOR", 0)), d.key),
    )


# --- wavelength tables -------------------------------------------------------------------------------------


def _wave_path(wave_id: str) -> Path:
    return settings.CACHE_DIR / "point" / "wave" / f"{re.sub(r'[^0-9A-Za-z_.-]', '_', wave_id)}.fits"


def _wave_hdu_in_tail(tail: bytes) -> bytes | None:
    """The WCS-WAVE HDU bytes if it is the last HDU and fully inside ``tail`` (which ends at EOF)."""
    for off in range(len(tail) - BLOCK, -1, -BLOCK):
        if tail[off : off + 9] != b"XTENSION=":
            continue
        try:
            got = s3range.parse_header(tail[off:])
        except ValueError:
            continue
        if got is None:
            continue
        h, hlen = got
        if str(h.get("EXTNAME", "")).strip() == fits_io.WAVE_EXTNAME:
            if off + hlen + s3range.padded(s3range.data_size(h)) == len(tail):
                return tail[off:]
            return None
    return None


def _wave_from_hdu_bytes(raw: bytes) -> fits_io.WaveTable:
    blob = fits.PrimaryHDU().header.tostring().encode("ascii") + raw
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        with fits.open(_io.BytesIO(blob), memmap=False) as hl:
            return fits_io.WaveTable.from_hdu(hl[fits_io.WAVE_EXTNAME])


def _wave_table(layout: _Layout, io: _IO, stats: _Stats) -> fits_io.WaveTable:
    """The WCS-WAVE table of a file: memory, disk (by wave id), a cached s3range directory, or a suffix read."""
    mkey = (str(settings.CACHE_DIR), layout.wave_id)
    table = _wave_mem.get(mkey)
    if table is not None:
        return table
    with _wave_locks.hold(mkey):
        table = _wave_mem.get(mkey)
        if table is not None:
            return table
        path = _wave_path(layout.wave_id)
        try:
            table = _wave_from_hdu_bytes(path.read_bytes()[BLOCK:])
        except (OSError, ValueError, KeyError, TypeError, IndexError):
            table = None  # not cached on disk (or unreadable): read it from the file
        if table is None:
            d = s3range.cached_directory(layout.key)
            raw = d.wcs_wave if d is not None and d.wcs_wave else None
            nbytes = _WAVE_TAIL
            while raw is None:
                tail, size = io.tail(layout.key, nbytes, stats)
                raw = _wave_hdu_in_tail(tail)
                if raw is None and (len(tail) >= size or nbytes >= 64 * BLOCK):
                    raise ValueError(f"no {fits_io.WAVE_EXTNAME} HDU at the end of {layout.key}")
                nbytes *= 4
            table = _wave_from_hdu_bytes(raw)
            s3range._atomic_write(path, fits.PrimaryHDU().header.tostring().encode("ascii") + raw, best_effort=True)
        _wave_mem[mkey] = table
        return table


# --- one stamp ---------------------------------------------------------------------------------------------


@dataclass(eq=False)
class PointSample:
    """One exposure at the point: a small stamp of every plane plus where the point falls in it.

    Arrays are float32 (IMAGE/VARIANCE/ZODI, BUNIT ``MJy/sr`` and ``(MJy/sr)^2``) and int32 (FLAGS), numpy
    ``[row, column]`` in native detector orientation (not north-up); stamp pixel [0, 0] is the 0-based
    detector pixel (``x0``, ``y0``). Stamps are ``box_px`` square unless clipped at a detector edge.
    ``x``/``y`` are the 0-based sub-pixel position of (ra, dec) in the stamp (full TAN-SIP WCS); pixel
    ``[i, j]`` covers ``x`` in ``[j - 0.5, j + 0.5)``. ``mjd`` is MID-exposure (``MJD-AVG``).
    ``wavelength_um``/``bandwidth_um`` are what THIS exposure measured at (ra, dec) (linear variable filter:
    the wavelength changes by 0.2-0.7 nm per pixel along y). ``flags`` is None when FLAGS could not be read
    (unknown, NOT clean); then ``core_flags`` is None too. ``core_flags`` ORs the FLAGS bits of the
    ``core_px`` x ``core_px`` pixels around the point; bit 21 (SOURCE) marks every catalogued star and is
    NOT a defect (docs/DATA.md §2). Saturated cores are NaN with OVERFLOW (bit 1) set.
    """

    frame: FrameRef  # the archive frame, with ``wavelength_um`` set to the value at the point
    obs_id: str
    detector: int
    release: str
    mjd: float
    wavelength_um: float | None
    bandwidth_um: float | None
    image: np.ndarray
    variance: np.ndarray | None
    zodi: np.ndarray | None
    flags: np.ndarray | None
    x: float
    y: float
    x0: int
    y0: int
    core_flags: int | None
    nan_fraction: float
    bunit: str = ""
    omega_arcsec2: float | None = None  # OMEGA_MEDIAN: median pixel solid angle (MJy/sr x sr -> MJy)
    mjd_source: str = "MJD-AVG"
    meta: dict = field(default_factory=dict)  # selected IMAGE header values (META_KEYS) + notes
    io: dict = field(default_factory=dict)  # requests, bytes, rounds, seconds, layout source

    @property
    def shape(self) -> tuple[int, int]:
        return self.image.shape

    @property
    def x_detector(self) -> float:
        """0-based detector column of (ra, dec)."""
        return self.x0 + self.x

    @property
    def y_detector(self) -> float:
        return self.y0 + self.y

    @property
    def center_pixel(self) -> tuple[int, int]:
        """(row, column) of the stamp pixel that contains (ra, dec)."""
        return math.floor(self.y + 0.5), math.floor(self.x + 0.5)


def _box(xc: float, yc: float, n: int, nx: int, ny: int) -> tuple[int, int, int, int]:
    """``n`` x ``n`` pixels centred on the pixel holding (xc, yc) (IBE rule ``ceil(c - n/2)``), clipped."""
    out = []
    for c, full in ((xc, nx), (yc, ny)):
        lo = math.ceil(c - n / 2.0)
        hi = lo + n - 1
        out += [max(lo, 0), min(hi, full - 1)]
    return out[0], out[1], out[2], out[3]


def _meta(h: fits.Header) -> dict:
    out = {}
    for k in META_KEYS:
        if k in h:
            v = h[k]
            out[k] = v if isinstance(v, (bool, int, float, str)) else str(v)
    return out


def read_point_sample(
    frame: FrameRef,
    ra: float,
    dec: float,
    box_px: int = 11,
    *,
    planes: Sequence[str] = PLANES,
    core_px: int = 3,
    io: _IO | None = None,
) -> PointSample:
    """Stamp of one frame around (ra, dec). Raises :class:`NoOverlap` if the point is off the detector.

    Network and format errors propagate (``point_series`` turns them into per-frame failures).
    """
    t0 = time.perf_counter()
    io = io or _IO()
    stats = _Stats()
    seg = _Segments()
    key = s3range._frame_key(frame)
    want = set(planes) | {"IMAGE"}

    layout = _cached_layout(key)
    source = "cached"
    if layout is None:
        d = s3range.cached_directory(key)
        if d is not None:
            layout, source = _layout_from_directory(d, io, seg, stats), "directory"
        else:
            try:
                layout, source = _read_front(key, frame.detector, io, seg, stats), "cold"
            except ValueError as e:  # an unexpected HDU order or header: walk the file like read_patch does
                log.info("speculative layout failed for %s (%s); walking its HDUs", key, e)
                d = s3range.hdu_directory(key)
                layout, source = _layout_from_directory(d, io, seg, stats), "walk"

    pix = fits_io._sky_to_array_pixel(layout.wcs, {"NAXIS1": layout.image.nx, "NAXIS2": layout.image.ny}, ra, dec)
    if pix is None:
        raise NoOverlap(f"({ra}, {dec}) is not on {frame.obs_id}D{frame.detector}")
    xf, yf = pix
    box = _box(xf, yf, box_px, layout.image.nx, layout.image.ny)
    x0, x1, y0, y1 = box

    # Round 2: everything at once; VARIANCE/ZODI placed by the hints when their headers are not known yet.
    fl = layout.flags
    use_heap = "FLAGS" in want and fl.desc is not None and not fl.error
    regions = [layout.image.region(box)]
    if "FLAGS" in want and fl.plane is not None:
        regions.append(fl.plane.region(box))
    if use_heap:
        regions.append(fl.heap_region(y0, y1))
    need_var, need_zodi = "VARIANCE" in want, "ZODI" in want
    unknown = (need_var or need_zodi) and (layout.variance is None or layout.zodi is None)
    if unknown:
        h = _hints(frame.detector)
        vh = layout.var_header
        regions.append((vh, vh + h.variance + BLOCK))
        guess_v = _Plane(vh + h.variance, layout.image.bitpix, layout.image.nx, layout.image.ny)
        if need_var:
            regions.append(guess_v.region(box, slack=BLOCK))
        if need_zodi:
            zh = guess_v.offset + s3range.padded(guess_v.size)
            regions.append((zh - BLOCK, zh + h.zodi + BLOCK))
            guess_z = _Plane(zh + h.zodi, guess_v.bitpix, guess_v.nx, guess_v.ny)
            regions.append(guess_z.region(box, slack=2 * BLOCK))
    else:
        for name, plane in (("VARIANCE", layout.variance), ("ZODI", layout.zodi)):
            if name in want and plane is not None:
                regions.append(plane.region(box))
    io.fetch(key, seg, regions, stats)

    if unknown:  # check the hints against the real headers (a miss only costs requests)
        try:
            vraw, vhdr = _header_at(key, layout.var_header, io, seg, stats, "VARIANCE")
            variance = _Plane.from_header(vhdr, layout.var_header + vraw.length)
            zh_at = variance.offset + s3range.padded(s3range.data_size(vhdr))
            zraw, zhdr = _header_at(key, zh_at, io, seg, stats, "ZODI")
            layout.variance, layout.zodi = variance, _Plane.from_header(zhdr, zh_at + zraw.length)
            layout.lengths.update(variance=vraw.length, zodi=zraw.length)
            _learn(frame.detector, layout.lengths)
        except ValueError as e:  # unexpected HDU order or header: walk the file like read_patch does
            log.info("VARIANCE/ZODI not where expected in %s (%s); walking its HDUs", key, e)
            layout, source = _layout_from_directory(s3range.hdu_directory(key), io, seg, stats), "walk"
            fl = layout.flags
            use_heap = "FLAGS" in want and fl.desc is not None and not fl.error
    if source != "cached" or unknown:
        _remember_layout(layout)

    # Extract every plane (fetching, in one more round, whatever a wrong hint left out).
    targets: dict[str, tuple[_Plane, tuple[int, int]]] = {"IMAGE": (layout.image, layout.image.region(box))}
    for name, plane in (("VARIANCE", layout.variance), ("ZODI", layout.zodi), ("FLAGS", fl.plane)):
        if name in want and plane is not None:
            targets[name] = (plane, plane.region(box))
    heap_region = fl.heap_region(y0, y1) if use_heap else None
    io.fetch(key, seg, [r for _, r in targets.values()] + ([heap_region] if heap_region else []), stats)
    arrays = {name: plane.extract(_bytes(key, *r, io, seg, stats), box) for name, (plane, r) in targets.items()}

    meta = _meta(layout.aux)
    flags_arr: np.ndarray | None = arrays.pop("FLAGS", None)
    if flags_arr is not None:
        flags_arr = flags_arr.astype(np.int32)
    elif heap_region is not None:
        heap = _bytes(key, *heap_region, io, seg, stats)
        try:
            flags_arr = fl.decode(y0, y1, heap, heap_region[0] - fl.heap)[:, x0 : x1 + 1]
        except ValueError as e:
            meta["flags_error"] = f"{type(e).__name__}: {e}"
    elif "FLAGS" in want and fl.error:
        meta["flags_error"] = fl.error

    # Wavelength at the point (bilinear WCS-WAVE lookup at the full-detector pixel).
    lam = bw = None
    try:
        table = _wave_table(layout, io, stats)
        lv, bv = fits_io.wavelength_from_table(table, layout.aux, xf, yf)
        if np.isfinite(lv) and np.isfinite(bv):
            lam, bw = float(lv), float(bv)
    except (OSError, ValueError, KeyError, TypeError, IndexError) as e:
        meta["wave_error"] = f"{type(e).__name__}: {e}"
    if lam is None and "wave_error" not in meta:
        meta["wave_error"] = "outside the WCS-WAVE table"

    image = arrays["IMAGE"].astype(np.float32, copy=False)
    core = None
    if flags_arr is not None:
        half = max(0, int(core_px) // 2)
        cy, cx = math.floor(yf + 0.5) - y0, math.floor(xf + 0.5) - x0
        block = flags_arr[max(cy - half, 0) : cy + half + 1, max(cx - half, 0) : cx + half + 1]
        core = int(np.bitwise_or.reduce(block.astype(np.uint32).ravel())) if block.size else 0
    mjd, mjd_source = fits_io.mid_exposure_mjd(layout.aux)
    omega = meta.get("OMEGA_MEDIAN")
    return PointSample(
        frame=frame.model_copy(update={"wavelength_um": lam}),
        obs_id=frame.obs_id,
        detector=frame.detector,
        release=frame.release,
        mjd=mjd,
        wavelength_um=lam,
        bandwidth_um=bw,
        image=image,
        variance=None if "VARIANCE" not in arrays else arrays["VARIANCE"].astype(np.float32, copy=False),
        zodi=None if "ZODI" not in arrays else arrays["ZODI"].astype(np.float32, copy=False),
        flags=flags_arr,
        x=xf - x0,
        y=yf - y0,
        x0=x0,
        y0=y0,
        core_flags=core,
        nan_fraction=float(np.isnan(image).mean()) if image.size else 1.0,
        bunit=layout.image.bunit or str(meta.get("BUNIT", "")),
        omega_arcsec2=float(omega) if isinstance(omega, (int, float)) and not isinstance(omega, bool) else None,
        mjd_source=mjd_source,
        meta=meta,
        io={
            "requests": stats.requests,
            "bytes": stats.bytes,
            "rounds": stats.rounds,
            "seconds": round(time.perf_counter() - t0, 4),
            "layout": source,
        },
    )


# --- the series --------------------------------------------------------------------------------------------


@dataclass(eq=False)
class PointSeries:
    """Every exposure at (ra, dec): ``samples`` sorted by (mjd, detector), plus what failed and why.

    ``failures`` lists (frame, "<ExceptionType>: <message>"); ``NoOverlap`` there means the archive footprint
    touched the point but the pixel is off the detector (seen up to ~7 px). ``search`` says how the frame
    list was obtained (service, cache, stale, overflow...), ``timings`` what the read cost.
    """

    ra: float
    dec: float
    box_px: int
    samples: list[PointSample]
    failures: list[tuple[FrameRef, str]]
    search: dict = field(default_factory=dict)
    timings: dict = field(default_factory=dict)
    selection: dict = field(default_factory=dict)
    core_px: int = 3
    planes: tuple[str, ...] = PLANES

    def summary_rows(self) -> list[dict]:
        """One JSON-safe dict of scalars per sample (no arrays)."""
        rows = []
        for s in self.samples:
            r, c = s.center_pixel
            r, c = min(max(r, 0), s.shape[0] - 1), min(max(c, 0), s.shape[1] - 1)
            rows.append(
                {
                    "obs_id": s.obs_id,
                    "detector": s.detector,
                    "release": s.release,
                    "mjd": s.mjd,
                    "wavelength_um": s.wavelength_um,
                    "bandwidth_um": s.bandwidth_um,
                    "x": round(s.x, 4),
                    "y": round(s.y, 4),
                    "x0": s.x0,
                    "y0": s.y0,
                    "shape": list(s.shape),
                    "center_value": _finite_or_none(s.image[r, c]) if s.image.size else None,
                    "core_flags": s.core_flags,
                    "nan_fraction": round(s.nan_fraction, 4),
                    "s3_key": s.frame.s3_key,
                }
            )
        return rows

    def save(self, path: str | Path, *, best_effort: bool = False) -> tuple[Path, Path]:
        """Write ``<path>.npz`` (stacked stamps, ragged-safe) and ``<path>.json`` (everything else)."""
        npz_path = Path(path)
        if npz_path.suffix != ".npz":
            npz_path = npz_path.with_name(npz_path.name + ".npz")
        json_path = npz_path.with_suffix(".json")
        n = len(self.samples)

        def flat(name: str, dtype: str, fill) -> np.ndarray:
            parts = []
            for s in self.samples:
                arr = getattr(s, name)
                parts.append(np.full(s.shape, fill, dtype=dtype) if arr is None else np.asarray(arr, dtype=dtype))
            return np.concatenate([p.ravel() for p in parts]) if parts else np.zeros(0, dtype=dtype)

        arrays = {
            "shape": np.array([s.shape for s in self.samples], dtype=np.int32).reshape(n, 2),
            "mjd": np.array([s.mjd for s in self.samples], dtype=np.float64),
            "wavelength_um": np.array([_nan(s.wavelength_um) for s in self.samples], dtype=np.float64),
            "bandwidth_um": np.array([_nan(s.bandwidth_um) for s in self.samples], dtype=np.float64),
            "detector": np.array([s.detector for s in self.samples], dtype=np.int8),
            "x": np.array([s.x for s in self.samples], dtype=np.float64),
            "y": np.array([s.y for s in self.samples], dtype=np.float64),
            "x0": np.array([s.x0 for s in self.samples], dtype=np.int32),
            "y0": np.array([s.y0 for s in self.samples], dtype=np.int32),
            "core_flags": np.array([-1 if s.core_flags is None else s.core_flags for s in self.samples], np.int64),
            "nan_fraction": np.array([s.nan_fraction for s in self.samples], dtype=np.float32),
            "has": np.array(
                [[s.variance is not None, s.zodi is not None, s.flags is not None] for s in self.samples], dtype=bool
            ).reshape(n, 3),
            "image": flat("image", "f4", np.nan),
            "variance": flat("variance", "f4", np.nan),
            "zodi": flat("zodi", "f4", np.nan),
            "flags": flat("flags", "i4", 0),
        }
        buf = _io.BytesIO()
        np.savez_compressed(buf, **arrays)
        doc = {
            "format": SERIES_FORMAT,
            "created": time.time(),
            "ra": self.ra,
            "dec": self.dec,
            "box_px": self.box_px,
            "core_px": self.core_px,
            "planes": list(self.planes),
            "selection": self.selection,
            "search": self.search,
            "timings": self.timings,
            "failures": [{"frame": f.model_dump(), "reason": r} for f, r in self.failures],
            "samples": [
                {
                    "frame": s.frame.model_dump(),
                    "bunit": s.bunit,
                    "omega_arcsec2": s.omega_arcsec2,
                    "mjd_source": s.mjd_source,
                    "meta": s.meta,
                    "io": s.io,
                }
                for s in self.samples
            ],
        }
        ok1 = s3range._atomic_write(npz_path, buf.getvalue(), best_effort=best_effort)
        ok2 = s3range._atomic_write(json_path, json.dumps(doc, indent=1).encode("utf-8"), best_effort=best_effort)
        if best_effort and not (ok1 and ok2):
            log.warning("could not write the point-series cache %s", npz_path)
        return npz_path, json_path

    @classmethod
    def load(cls, path: str | Path) -> PointSeries:
        """Read what :meth:`save` wrote (``path`` = the .npz or the .json)."""
        p = Path(path)
        npz_path = p if p.suffix == ".npz" else p.with_suffix(".npz")
        doc = json.loads(npz_path.with_suffix(".json").read_text(encoding="utf-8"))
        if doc.get("format") != SERIES_FORMAT:
            raise ValueError(f"unsupported point-series format {doc.get('format')!r} in {npz_path}")
        with np.load(npz_path, allow_pickle=False) as z:
            a = {k: z[k] for k in z.files}
        samples: list[PointSample] = []
        start = 0
        for i, extra in enumerate(doc["samples"]):
            ny, nx = (int(v) for v in a["shape"][i])
            sl = slice(start, start + ny * nx)
            start += ny * nx
            has_var, has_zodi, has_flags = (bool(v) for v in a["has"][i])
            frame = FrameRef.model_validate(extra["frame"])
            samples.append(
                PointSample(
                    frame=frame,
                    obs_id=frame.obs_id,
                    detector=frame.detector,
                    release=frame.release,
                    mjd=float(a["mjd"][i]),
                    wavelength_um=_none(a["wavelength_um"][i]),
                    bandwidth_um=_none(a["bandwidth_um"][i]),
                    image=a["image"][sl].reshape(ny, nx),
                    variance=a["variance"][sl].reshape(ny, nx) if has_var else None,
                    zodi=a["zodi"][sl].reshape(ny, nx) if has_zodi else None,
                    flags=a["flags"][sl].reshape(ny, nx) if has_flags else None,
                    x=float(a["x"][i]),
                    y=float(a["y"][i]),
                    x0=int(a["x0"][i]),
                    y0=int(a["y0"][i]),
                    core_flags=None if int(a["core_flags"][i]) < 0 else int(a["core_flags"][i]),
                    nan_fraction=float(a["nan_fraction"][i]),
                    bunit=extra.get("bunit", ""),
                    omega_arcsec2=extra.get("omega_arcsec2"),
                    mjd_source=extra.get("mjd_source", "MJD-AVG"),
                    meta=extra.get("meta", {}),
                    io=extra.get("io", {}),
                )
            )
        return cls(
            ra=float(doc["ra"]),
            dec=float(doc["dec"]),
            box_px=int(doc["box_px"]),
            samples=samples,
            failures=[(FrameRef.model_validate(f["frame"]), f["reason"]) for f in doc.get("failures", [])],
            search=doc.get("search", {}),
            timings=doc.get("timings", {}),
            selection=doc.get("selection", {}),
            core_px=int(doc.get("core_px", 3)),
            planes=tuple(doc.get("planes", PLANES)),
        )


def _nan(v: float | None) -> float:
    return np.nan if v is None else float(v)


def _none(v) -> float | None:
    v = float(v)
    return v if math.isfinite(v) else None


def _finite_or_none(v) -> float | None:
    v = float(v)
    return v if math.isfinite(v) else None


def select_frames(frames: Sequence[FrameRef], max_frames: int | None) -> list[FrameRef]:
    """At most ``max_frames`` frames spread over detectors and visits (all of them when they fit).

    Every detector gets one frame first (when ``max_frames`` allows: every band stays in the spectrum),
    the rest goes in proportion to each detector's frames; within a detector the picks are one per visit,
    evenly over time (``epochs._pick_spread``), so a capped series still spans the whole baseline instead
    of its first weeks.
    """
    frames = list(frames)
    if max_frames is None or len(frames) <= max_frames:
        return frames
    if max_frames < 1:
        raise ValueError("max_frames must be >= 1")
    by_det: dict[int, list[FrameRef]] = {}
    for f in sorted(frames, key=lambda f: (f.mjd, f.detector)):
        by_det.setdefault(f.detector, []).append(f)
    dets = sorted(by_det)
    quota = dict.fromkeys(dets, 1 if max_frames >= len(dets) else 0)
    for _ in range(max_frames - sum(quota.values())):
        spare = [d for d in dets if quota[d] < len(by_det[d])]
        if not spare:
            break
        d = max(spare, key=lambda d: (max_frames * len(by_det[d]) / len(frames) - quota[d], -d))
        quota[d] += 1
    picked = [f for d in dets for f in _pick_spread(by_det[d], quota[d], VISIT_GAP_HOURS)]
    return sorted(picked, key=lambda f: (f.mjd, f.detector, f.obs_id))


def _series_path(ident: dict) -> Path:
    h = hashlib.sha256(json.dumps(ident, sort_keys=True).encode()).hexdigest()[:24]
    return settings.CACHE_DIR / "point" / "series" / f"{ident['ra']:.7f}_{ident['dec']:+.7f}_b{ident['box']}_{h}.npz"


def _load_cached_series(path: Path) -> PointSeries | None:
    try:
        doc = json.loads(path.with_suffix(".json").read_text(encoding="utf-8"))
        if doc.get("format") != SERIES_FORMAT or time.time() - float(doc.get("created", 0)) > SERIES_TTL_S:
            return None
        return PointSeries.load(path)
    except (OSError, ValueError, KeyError, TypeError, zlib.error):
        return None


def point_series(
    ra: float,
    dec: float,
    *,
    box_px: int = 11,
    detectors: Sequence[int] | None = None,
    mjd_min: float | None = None,
    mjd_max: float | None = None,
    collections: Sequence[str] | str | None = None,
    max_frames: int | None = None,
    max_workers: int | None = None,
    planes: Sequence[str] = PLANES,
    core_px: int = 3,
    frames: Sequence[FrameRef] | None = None,
    use_cache: bool = True,
) -> PointSeries:
    """Stamps of EVERY SPHEREx exposure covering (ra, dec) [deg, ICRS], read from S3 in parallel.

    Frames come from ``irsa.search_frames_report`` (point search; ``collections`` defaults to
    ``settings.IRSA_COLLECTIONS`` = DR1 + QR3, deep fields via ``collections=['spherex_dr1_deep', ...]``),
    filtered by ``detectors`` and the ``mjd_min``/``mjd_max`` exposure overlap, then capped to
    ``max_frames`` with :func:`select_frames`; or pass ``frames`` to skip the search. ``planes`` picks
    which planes to read (IMAGE always). ``max_workers`` = concurrent S3 requests (default
    ``ERRANTE_POINT_MAX_PARALLEL`` = 48). One failing frame never aborts the series: it lands in
    ``failures``. Raises ``irsa.SearchError`` when the archive search fails and nothing is cached.

    The result is cached (npz + json under CACHE_DIR/point/series) per (ra, dec, box, selection) for
    ``ERRANTE_POINT_TTL_S`` (default: the query-cache TTL, 1 day) unless a frame failed for a reason other
    than ``NoOverlap`` or the search was stale/truncated; ``use_cache=False`` skips both reading and writing.
    """
    t0 = time.perf_counter()
    ra, dec = float(ra), float(dec)
    if not (math.isfinite(ra) and math.isfinite(dec) and -90.0 <= dec <= 90.0):
        raise ValueError(f"Invalid position ra={ra}, dec={dec}")
    ra %= 360.0
    if not (isinstance(box_px, (int, np.integer)) and 1 <= int(box_px) <= MAX_BOX_PX):
        raise ValueError(f"box_px must be an integer in 1..{MAX_BOX_PX}, got {box_px!r}")
    box_px = int(box_px)
    if not (1 <= int(core_px) <= box_px):
        raise ValueError(f"core_px must be in 1..box_px, got {core_px}")
    planes = tuple(dict.fromkeys(["IMAGE", *planes]))
    if not set(planes) <= set(PLANES):
        raise ValueError(f"planes must be among {PLANES}, got {planes}")
    if max_frames is not None and max_frames < 1:
        raise ValueError("max_frames must be >= 1")
    dets = sorted({int(d) for d in detectors}) if detectors else None
    if dets and not set(dets) <= set(range(1, 7)):
        raise ValueError(f"detectors must be 1-6, got {dets}")
    cols = list(irsa.normalize_collections(collections))
    selection = {
        "detectors": dets,
        "mjd_min": mjd_min,
        "mjd_max": mjd_max,
        "collections": cols,
        "max_frames": max_frames,
    }
    ident = {
        "format": SERIES_FORMAT,
        "ra": round(ra, 7),
        "dec": round(dec, 7),
        "box": box_px,
        "core": int(core_px),
        "planes": sorted(planes),
        **selection,
    }
    if frames is not None:
        keys = "\n".join(sorted(s3range._frame_key(f) for f in frames))
        ident["frames"] = hashlib.sha256(keys.encode()).hexdigest()[:24]
        ident["collections"] = None
        selection["collections"] = None
    cache_path = _series_path(ident)
    cache_on = use_cache and SERIES_TTL_S > 0
    if cache_on:
        hit = _load_cached_series(cache_path)
        if hit is not None:
            hit.timings = {**hit.timings, "from_cache": True, "total_s": round(time.perf_counter() - t0, 4)}
            return hit

    search: dict
    if frames is None:
        rep = irsa.search_frames_report(ra, dec, 0.0, dets, mjd_min, mjd_max, collections=cols)
        all_frames = list(rep.result.frames)
        search = {
            "service": rep.service,
            "from_cache": rep.from_cache,
            "stale": rep.stale,
            "overflow": rep.overflow,
            "collections": list(rep.collections),
            "n_found": len(all_frames),
            "n_duplicates": rep.n_duplicates,
            "elapsed_s": round(rep.elapsed_s, 3),
            "errors": list(rep.errors),
            "warnings": list(rep.warnings),
        }
    else:
        all_frames = [f for f in frames if not dets or f.detector in dets]
        search = {
            "service": "given",
            "from_cache": False,
            "stale": False,
            "overflow": False,
            "n_found": len(all_frames),
        }
    chosen = select_frames(all_frames, max_frames)
    search["n_selected"] = len(chosen)
    t_search = time.perf_counter() - t0

    workers = max(1, min(int(max_workers or MAX_PARALLEL), 64))
    samples: list[PointSample] = []
    failures: list[tuple[FrameRef, str]] = []
    t1 = time.perf_counter()
    if chosen:
        frame_workers = max(1, min(len(chosen), max(4, workers * 2 // 3)))
        with (
            ThreadPoolExecutor(workers, thread_name_prefix="point-io") as io_pool,
            ThreadPoolExecutor(frame_workers, thread_name_prefix="point-frame") as frame_pool,
        ):
            io = _IO(io_pool)
            futures = [
                frame_pool.submit(read_point_sample, f, ra, dec, box_px, planes=planes, core_px=core_px, io=io)
                for f in chosen
            ]
            for f, fut in zip(chosen, futures, strict=True):
                try:
                    samples.append(fut.result())
                except Exception as e:  # noqa: BLE001  (one bad frame never aborts the series)
                    failures.append((f, f"{type(e).__name__}: {e}"))
    t_fetch = time.perf_counter() - t1
    samples.sort(key=lambda s: (s.mjd, s.detector, s.obs_id))

    n_req = sum(s.io.get("requests", 0) for s in samples)
    n_bytes = sum(s.io.get("bytes", 0) for s in samples)
    no_overlap = sum(1 for _, r in failures if r.startswith("NoOverlap"))
    timings = {
        "from_cache": False,
        "search_s": round(t_search, 3),
        "fetch_s": round(t_fetch, 3),
        "total_s": round(time.perf_counter() - t0, 3),
        "frames": len(chosen),
        "samples": len(samples),
        "failures": len(failures),
        "no_overlap": no_overlap,
        "requests": n_req,
        "bytes": n_bytes,
        "requests_per_frame": round(n_req / len(samples), 2) if samples else None,
        "bytes_per_frame": round(n_bytes / len(samples)) if samples else None,
        "max_rounds": max((s.io.get("rounds", 0) for s in samples), default=0),
        "layouts": dict(Counter(s.io.get("layout", "?") for s in samples)),
        "workers": workers,
    }
    if len(failures) > no_overlap:
        log.warning(
            "point_series(%.5f, %.5f): %d of %d frames failed", ra, dec, len(failures) - no_overlap, len(chosen)
        )
    if no_overlap:  # the archive footprint touched the point, the pixel is off the detector: expected, rare
        log.info("point_series(%.5f, %.5f): %d frames do not cover the pixel", ra, dec, no_overlap)
    series = PointSeries(
        ra=ra,
        dec=dec,
        box_px=box_px,
        samples=samples,
        failures=failures,
        search=search,
        timings=timings,
        selection=selection,
        core_px=int(core_px),
        planes=planes,
    )
    if cache_on and no_overlap == len(failures) and not search.get("stale") and not search.get("overflow"):
        series.save(cache_path, best_effort=True)
    return series
