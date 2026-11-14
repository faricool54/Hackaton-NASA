"""Live checks against real services. Run with: ERRANTE_NETWORK_TESTS=1 pytest -m network

Expected numbers verified live on 2026-11-14 (docs/DATA.md §3.0). IRSA can be down for hours
(2026-11-14 afternoon: SIA ~90% HTTP 502, TAP 502 or hanging): when BOTH services fail at the
transport level the IRSA tests skip with the reason; any other failure (parsing, counts) fails.
"""

import os
import time
from collections import Counter

import pytest
import requests

pytestmark = [
    pytest.mark.network,
    pytest.mark.skipif(os.environ.get("ERRANTE_NETWORK_TESTS") != "1", reason="set ERRANTE_NETWORK_TESTS=1"),
]

BARNARD = (269.44623, 4.76870)
WISE_0855 = (133.75980, -7.24219)


def _live(fn, *args, **kwargs):
    from errante.data.irsa import SearchError

    try:
        return fn(*args, **kwargs)
    except SearchError as e:
        if e.is_outage:
            pytest.skip(f"IRSA outage (SIA and TAP down): {e}")
        raise


def test_s3_has_dr1_weeks():
    from errante.data.s3 import list_weeks

    weeks = list_weeks("dr1")
    assert weeks and weeks[0].startswith("2025W")


def test_irsa_finds_frames_for_barnards_star():
    from errante.data.epochs import group_seasons
    from errante.data.irsa import search_frames_report

    t0 = time.monotonic()
    rep = _live(search_frames_report, *BARNARD, use_cache=False)
    elapsed = time.monotonic() - t0
    frames = rep.result.frames
    print(f"Barnard: {len(frames)} frames via {rep.service} in {elapsed:.1f} s; errors={rep.errors}")
    assert len(frames) > 300  # 358 on 2026-11-14: dr1 239 + qr3 119
    releases = Counter(f.release for f in frames)
    assert releases["dr1"] > 200 and releases["qr3"] > 100
    assert {f.detector for f in frames} == {1, 2, 3, 4, 5, 6}
    seasons = group_seasons(frames)
    assert len(seasons) >= 3  # MJD ~60903-60949, 61110-61165, 61269-61306
    assert seasons[0][0].mjd < 60950 and seasons[1][0].mjd > 61100
    keys = [(f.obs_id, f.detector) for f in frames]
    assert len(keys) == len(set(keys))
    assert all(f.irsa_uri == f"ibe/data/spherex/{f.s3_key}" for f in frames)


def test_wise_0855_is_dr1_only_with_time_filter():
    from errante.data.irsa import search_frames

    res = _live(search_frames, *WISE_0855, use_cache=False)
    assert len(res.frames) >= 250  # 258 on 2026-11-14, all DR1
    assert {f.release for f in res.frames} == {"dr1"}
    later = _live(search_frames, *WISE_0855, mjd_min=60900, detectors=[5, 6], use_cache=False)
    assert later.frames and all(f.mjd >= 60900 - 0.01 and f.detector in (5, 6) for f in later.frames)


def test_tap_fallback_matches_sia_for_barnard():
    from errante.data import irsa

    t0 = time.monotonic()
    try:
        rows = irsa._search_tap(*BARNARD, irsa.MIN_RADIUS_DEG, None, None, ("spherex_dr1", "spherex_qr3"))
    except (requests.Timeout, requests.ConnectionError) as e:
        pytest.skip(f"IRSA TAP unreachable: {e}")
    except requests.HTTPError as e:
        if e.response is not None and e.response.status_code >= 500:
            pytest.skip(f"IRSA TAP outage: {e}")
        raise
    print(f"TAP: {len(rows)} rows in {time.monotonic() - t0:.1f} s")
    deduped, _ = irsa.dedupe_rows(rows)
    assert len(deduped) > 300
    assert Counter(r.collection for r in deduped).keys() == {"spherex_dr1", "spherex_qr3"}


def test_search_key_is_readable_on_s3():
    from errante import settings
    from errante.data.irsa import search_frames

    res = _live(search_frames, *BARNARD, detectors=[1])
    assert res.frames
    key = res.frames[0].s3_key
    r = requests.get(f"{settings.S3_HTTPS}/{key}", headers={"Range": "bytes=0-2879"}, timeout=60)
    assert r.status_code == 206 and r.content.startswith(b"SIMPLE  =")
