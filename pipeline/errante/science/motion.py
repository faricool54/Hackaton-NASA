"""Motion and rough distance from on-sky rate (implemented; WS3 owns changes).

Near opposition an object's apparent (retrograde) rate is dominated by Earth's
orbital motion, so the rate alone gives a rough heliocentric distance:

    rate ≈ K · (1 − 1/√r) / (r − 1)      K = v_earth / 1 AU ≈ 147.8 "/h

r [AU] heliocentric distance, circular orbits assumed. Valid only near
opposition (solar elongation ≳ 150°); elsewhere it is an order-of-magnitude
estimate. SPHEREx observes near 90° elongation, so WS3 should replace this with
statistical ranging / a parallax fit using the spacecraft position
(X_SC/Y_SC/Z_SC header keys) for anything presented as a result.
"""

from __future__ import annotations

import math

import numpy as np

from ..models import DistanceEstimate, Motion

AU_KM = 1.495978707e8
V_EARTH_KM_S = 29.7847
ARCSEC_PER_RAD = 206264.806
K_ARCSEC_PER_HOUR = V_EARTH_KM_S * 3600 / AU_KM * ARCSEC_PER_RAD  # ≈ 147.8


def opposition_rate_arcsec_per_hour(r_au: float) -> float:
    if r_au <= 1:
        raise ValueError("r must be > 1 AU (outer solar system)")
    return K_ARCSEC_PER_HOUR * (1 - 1 / math.sqrt(r_au)) / (r_au - 1)


def distance_from_opposition_rate(rate_arcsec_per_hour: float) -> DistanceEstimate:
    """Invert ``opposition_rate_arcsec_per_hour`` by bisection (monotonic in r)."""
    lo, hi = 1.0001, 1.0e5
    if rate_arcsec_per_hour >= opposition_rate_arcsec_per_hour(lo):
        r = lo
    elif rate_arcsec_per_hour <= opposition_rate_arcsec_per_hour(hi):
        r = hi
    else:
        for _ in range(200):
            mid = math.sqrt(lo * hi)
            if opposition_rate_arcsec_per_hour(mid) > rate_arcsec_per_hour:
                lo = mid
            else:
                hi = mid
        r = math.sqrt(lo * hi)
    return DistanceEstimate(au_median=r, method="opposition_rate")


def motion_from_detections(mjd, ra_deg, dec_deg) -> Motion:
    """Least-squares linear motion from >= 2 detections (arrays of equal length)."""
    t_h = (np.asarray(mjd, float) - np.min(mjd)) * 24.0
    ra = np.unwrap(np.radians(np.asarray(ra_deg, float)))
    dec = np.radians(np.asarray(dec_deg, float))
    dec0 = np.mean(dec)
    x = np.degrees(ra - ra[0]) * 3600 * math.cos(dec0)  # arcsec, east positive
    y = np.degrees(dec - dec[0]) * 3600  # arcsec, north positive
    if len(t_h) < 2 or np.ptp(t_h) == 0:
        raise ValueError("Need >= 2 detections at different times")
    vx = float(np.polyfit(t_h, x, 1)[0])
    vy = float(np.polyfit(t_h, y, 1)[0])
    pa = math.degrees(math.atan2(vx, vy)) % 360.0
    return Motion(
        rate_arcsec_per_hour=math.hypot(vx, vy),
        position_angle_deg=pa,
        ra_cosdec_rate_arcsec_per_hour=vx,
        dec_rate_arcsec_per_hour=vy,
    )
