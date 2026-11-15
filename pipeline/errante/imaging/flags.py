"""SPHEREx Level-2 FLAGS bitmask (WS2).

Bit names were read from the FLAGS HDU header (MSKNnnnn/MSKMnnnn cards) of a
real DR1 file on 2026-11-14 (docs/DATA.md). QR2/QR3 files may differ: when in
doubt call ``bits_from_header(hdr)`` on the file you are processing.

!! Do NOT treat "any bit set" as bad: SOURCE (bit 21) marks ~70 % of pixels
!! (every star). OUTLIER/TRANSIENT can also fire ON A MOVING OBJECT, because it
!! is not where the static sky model expects it. Mask them for star finding,
!! but think twice before masking them for mover finding.
"""

from __future__ import annotations

import numpy as np

FLAG_BITS: dict[str, int] = {
    "TRANSIENT": 0,
    "OVERFLOW": 1,
    "SUR_ERROR": 2,
    "NONFUNC": 6,
    "DICHROIC": 7,
    "MISSING_DATA": 9,
    "HOT": 10,
    "COLD": 11,
    "FULLSAMPLE": 12,
    "PHANMISS": 14,
    "NONLINEAR": 15,
    "PERSIST": 17,
    "OUTLIER": 19,
    "CROSSTALK": 20,
    "SOURCE": 21,
    "GHOST": 22,
    "GHOST_FPA": 23,
    "GHOST_EXT": 24,
    "STREAK": 25,
    "BLOOM": 26,
    "SNOWBALL": 27,  # read 2026-11-14 from dr1 and qr3 FLAGS headers (MSKN0027, docs/DATA.md)
    "HALO": 28,
}

# Pixels whose value cannot be trusted at all.
DEFAULT_BAD = (
    "OVERFLOW", "SUR_ERROR", "NONFUNC", "MISSING_DATA", "HOT", "COLD",
    "PHANMISS", "PERSIST", "GHOST", "GHOST_FPA", "GHOST_EXT", "STREAK", "SNOWBALL",
)  # fmt: skip
# Informational: never mask on these alone.
INFORMATIONAL = ("SOURCE", "FULLSAMPLE", "CROSSTALK", "DICHROIC")
# Could be a real moving object -> keep for mover search, decide per algorithm.
MAYBE_MOVER = ("TRANSIENT", "OUTLIER")


def bitmask(names: tuple[str, ...] | list[str]) -> int:
    return sum(1 << FLAG_BITS[n] for n in names)


def bad_pixel_mask(flags: np.ndarray, bad: tuple[str, ...] = DEFAULT_BAD) -> np.ndarray:
    """Boolean array, True where the pixel should be ignored."""
    return (flags.astype(np.int64) & bitmask(bad)) != 0


def bits_from_header(header) -> dict[str, int]:
    """Read {name: bit} from a FLAGS HDU header (MSKNnnnn = name, plane n)."""
    out: dict[str, int] = {}
    for key in header:
        if key.startswith("MSKN") and key[4:].isdigit() and int(key[4:]) < 32:
            out[str(header[key])] = int(key[4:])
    return out
