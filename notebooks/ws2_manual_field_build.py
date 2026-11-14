"""Build a REAL SPHEREx golden field while WS1's search/cutouts are still stubs (WS2, temporary).

    .venv/Scripts/python notebooks/ws2_manual_field_build.py barnards-star            # Windows
    .venv/bin/python notebooks/ws2_manual_field_build.py barnards-star --max-frames 40

What it does, for a field id from pipeline/errante/config/fields.toml:
1. SIA2 (VOTABLE) on spherex_dr1 and spherex_qr3, in ~60-day TIME windows with
   retries: the DR1 index answered HTTP 502 intermittently on 2026-11-14, and
   one big query failed far more often than small ones.
2. Downloads IBE server-side cutouts (``?center=..&size=..``) into
   data/cache/ws2-manual/ (ignored by git); 503 -> retry, 422 -> no overlap.
3. Runs the real ``errante.build.build_field`` (frame selection per season x
   detector, reprojection, shared stretch) with those two steps plugged in,
   writing to data/products/ (or --out).
4. Prints a registration report from unsaturated field stars.

Delete this script once ``irsa.search_frames`` and ``cutouts.fetch_cutouts``
are implemented by WS1: then ``errante build <id>`` does the same.
Deep collections (*_deep) are not queried: the contract has no release for them yet.
"""

from __future__ import annotations

import argparse
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import requests
from astropy.io.votable import parse

from errante import build, settings
from errante.data import cutouts, fits_io, irsa
from errante.imaging.reproject import reproject_to_grid
from errante.models import FrameRef, SearchResult, SkyCoord

COLLECTIONS = {"spherex_dr1": "dr1", "spherex_qr3": "qr3"}
MISSION_MJD = (60780.0, 61330.0)  # 2025-04 .. 2026-10, covers DR1 + QR3 (docs/DATA.md §3.0)
WINDOW_DAYS = 60.0
CACHE = settings.CACHE_DIR / "ws2-manual"


def _get(url: str, *, ok=lambda r: True, tries: int = 6, timeout: float = 120) -> requests.Response | None:
    for attempt in range(tries):
        try:
            r = requests.get(url, timeout=timeout)
            if r.status_code == 200 and ok(r):
                return r
            if r.status_code in (400, 404, 422):
                return r
            print(f"  HTTP {r.status_code}, retrying: {url[:110]}", file=sys.stderr)
        except requests.RequestException as e:
            print(f"  {type(e).__name__}, retrying: {url[:110]}", file=sys.stderr)
        time.sleep(min(30, 3 * (attempt + 1)))
    return None


def sia_frames(ra: float, dec: float) -> list[FrameRef]:
    refs: list[FrameRef] = []
    for collection, release in COLLECTIONS.items():
        t = MISSION_MJD[0]
        while t < MISSION_MJD[1]:
            url = (
                f"{settings.IRSA_SIA}?COLLECTION={collection}&POS=circle+{ra}+{dec}+0.001"
                f"&TIME={t}+{t + WINDOW_DAYS}&RESPONSEFORMAT=VOTABLE"
            )
            r = _get(url, ok=lambda r: b"VOTABLE" in r.content[:2000])
            if r is None or r.status_code != 200:
                raise RuntimeError(f"SIA failed for {collection} MJD {t}-{t + WINDOW_DAYS}; try again later")
            path = CACHE / f"sia_{collection}_{ra:.5f}_{dec:.5f}_{int(t)}.xml"
            path.write_bytes(r.content)
            refs += _refs_from_votable(path, release)
            t += WINDOW_DAYS
    return refs


def _refs_from_votable(path: Path, release: str) -> list[FrameRef]:
    table = parse(str(path)).get_first_table()
    names = [f.name for f in table.fields]
    out = []
    for row in table.array:
        r = dict(zip(names, row, strict=True))
        key = re.search(r'"key":\s*"([^"]+)"', str(r["cloud_access"]))
        out.append(
            FrameRef(
                obs_id=str(r["obs_id"]),
                detector=int(str(r["energy_bandpassname"]).rsplit("D", 1)[1]),
                mjd=(float(r["t_min"]) + float(r["t_max"])) / 2,
                release=release,
                irsa_uri=str(r["access_url"]).split("irsa.ipac.caltech.edu/", 1)[1],
                s3_key=key.group(1) if key else None,
            )
        )
    return out


def fetch(ref: FrameRef, ra: float, dec: float, size_arcmin: float) -> Path | None:
    dest = CACHE / f"{ref.obs_id}D{ref.detector}_{ra:.4f}_{dec:.4f}_{size_arcmin:g}.fits"
    if dest.exists() and dest.stat().st_size > 0:
        return dest
    r = _get(cutouts.cutout_url(ref.irsa_uri, ra, dec, size_arcmin), ok=lambda r: r.content[:6] == b"SIMPLE")
    if r is None or r.status_code != 200:
        return None  # 422 = no overlap, None after retries = failed download
    dest.write_bytes(r.content)
    return dest


def registration_report(field) -> None:
    """Scatter of unsaturated field-star centroids across all frames (should be << 1 px)."""
    data = {}
    for fr in field.frames:
        path = (
            CACHE
            / f"{fr.obs_id}D{fr.detector}_{field.center.ra:.4f}_{field.center.dec:.4f}_{field.size_deg * 90:g}.fits"
        )
        data[fr.id] = reproject_to_grid(fits_io.read_spherex(path), field.grid)
    z = []
    for d, _ in data.values():
        m = np.nanmedian(d)
        z.append((d - m) / (1.4826 * np.nanmedian(np.abs(d - m))))
    zm = np.nanmedian(np.stack(z), axis=0)
    n = field.grid.width_px
    peaks = [
        (zm[y, x], x, y)
        for y in range(5, n - 5)
        for x in range(5, n - 5)
        if 40 < zm[y, x] < 2000 and zm[y, x] == np.nanmax(zm[y - 2 : y + 3, x - 2 : x + 3])
    ]
    offsets = []
    for _, x, y in sorted(peaks, reverse=True)[:12]:
        pos = []
        for d, bad in data.values():
            if bad[y - 1 : y + 2, x - 1 : x + 2].any():
                continue
            w = np.clip(np.nan_to_num(d[y - 2 : y + 3, x - 2 : x + 3] - np.nanmedian(d)), 0, None)
            yy, xx = np.mgrid[y - 2 : y + 3, x - 2 : x + 3]
            pos.append(((w * xx).sum() / w.sum(), (w * yy).sum() / w.sum()))
        if len(pos) > 2:
            mx, my = np.median(pos, axis=0)
            offsets += [float(np.hypot(px - mx, py - my)) for px, py in pos]
    if offsets:
        print(
            f"registration (field stars): median {np.median(offsets):.3f} px, "
            f"p90 {np.percentile(offsets, 90):.3f} px over {len(offsets)} measurements"
        )


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("field_id")
    ap.add_argument("--max-frames", type=int, default=None)
    ap.add_argument("--out", type=Path, default=settings.PRODUCTS_DIR)
    args = ap.parse_args()

    cfg = build.load_field_configs()[args.field_id]
    if args.max_frames:
        cfg.max_frames = args.max_frames
    CACHE.mkdir(parents=True, exist_ok=True)
    refs = sia_frames(cfg.ra, cfg.dec)
    print(
        f"{len(refs)} frames from SIA (dr1 {sum(r.release == 'dr1' for r in refs)}, qr3 {sum(r.release == 'qr3' for r in refs)})"
    )

    size = cfg.size_deg * 60 * 1.5

    def search(*a, **kw):
        return SearchResult(center=SkyCoord(ra=cfg.ra, dec=cfg.dec), radius_deg=0, frames=refs)

    def fetch_all(frames, *a, **kw):
        with ThreadPoolExecutor(settings.MAX_PARALLEL_DOWNLOADS) as pool:
            return list(pool.map(lambda f: fetch(f, cfg.ra, cfg.dec, size), frames))

    irsa.search_frames = search
    cutouts.fetch_cutouts = fetch_all
    field = build.build_field(cfg, args.out)
    seasons = len(set(build.season_index([f.mjd for f in field.frames])))
    print(f"wrote {args.out / 'fields' / field.id}: {len(field.frames)} frames, {seasons} seasons")
    for note in field.provenance.notes[2:]:
        print("note:", note)
    registration_report(field)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
