"""Live checks against real services. Run with: ERRANTE_NETWORK_TESTS=1 pytest -m network

Expected numbers verified live on 2026-11-14 (docs/DATA.md §3.0). IRSA can be down for hours
(2026-11-14 afternoon: SIA ~90% HTTP 502, TAP 502 or hanging): when BOTH services fail at the
transport level the IRSA tests skip with the reason; any other failure (parsing, counts) fails.
"""

import math
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
OFFICIAL = ("barnards-star", "eps-indi-b", "wise-0855", "rw-aurigae", "r-draconis")


@pytest.fixture(autouse=True)
def _live_only(monkeypatch):
    """Live checks must reach IRSA: a committed search snapshot would hide an outage behind old data."""
    from errante.data import irsa

    monkeypatch.setattr(irsa, "SNAPSHOT_DIR", None)


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


DR1_LAST_MJD = 61175.0  # WISE 0855's last DR1 season ends at MJD 61174.29; quick releases come after


def test_wise_0855_dr1_coverage_with_time_filter():
    from errante.data.irsa import search_frames

    res = _live(search_frames, *WISE_0855, use_cache=False)
    releases = Counter(f.release for f in res.frames)
    assert releases["dr1"] >= 250  # 258 on 2026-11-14, all DR1 (no QR3 pass over it yet)
    # A later QR3 pass (from ~Nov 2026) may add qr3 frames, but only after the DR1 cut.
    assert all(f.release == "dr1" for f in res.frames if f.mjd < DR1_LAST_MJD)
    later = _live(search_frames, *WISE_0855, mjd_min=60900, detectors=[5, 6], use_cache=False)
    assert later.frames and all(f.mjd >= 60900 - 0.01 and f.detector in (5, 6) for f in later.frames)


def test_tap_fallback_matches_sia_for_barnard():
    from errante.data import irsa

    t0 = time.monotonic()
    cols = ("spherex_dr1", "spherex_qr3")
    try:  # 75 s budget: one full 60 s attempt plus quick retries of fast 502s
        rows, _ = irsa._search_tap(*BARNARD, irsa.MIN_RADIUS_DEG, None, None, cols, deadline=t0 + 75)
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


def test_cli_acceptance_command_prints_search_result(monkeypatch, tmp_path, capsys):
    """WS1-2 acceptance: `errante search --ra 269.4463 --dec 4.7665` prints a valid SearchResult."""
    from errante import settings
    from errante.cli import main as cli_main
    from errante.data.irsa import search_frames
    from errante.models import SearchResult

    monkeypatch.setattr(settings, "CACHE_DIR", tmp_path)
    live = _live(search_frames, 269.4463, 4.7665)  # live query; fills the (temporary) cache
    assert cli_main(["search", "--ra", "269.4463", "--dec", "4.7665"]) == 0
    res = SearchResult.model_validate_json(capsys.readouterr().out)
    assert res == live and len(res.frames) > 300


def test_overflow_is_flagged_and_not_cached(monkeypatch, tmp_path):
    from errante import settings
    from errante.data.irsa import search_frames_report

    monkeypatch.setattr(settings, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(settings, "SIA_MAXREC", 200)
    r_dra = (248.16761083, 66.75497942)  # ~2,500 frames with the deep collections
    rep = _live(search_frames_report, *r_dra, collections=["spherex_dr1_deep", "spherex_qr3_deep"])
    print(f"R Dra deep, MAXREC=200: {len(rep.rows)} rows via {rep.service} in {rep.elapsed_s:.1f} s")
    assert rep.overflow and len(rep.rows) <= 200
    assert not (tmp_path / "queries").exists()


def test_tap_circle_query_is_accepted():
    """IRSA TAP rejects INTERSECTS(CIRCLE(...), p.poly) as unsupported ADQL; build_query puts p.poly first."""
    from errante.data import irsa

    t0 = time.monotonic()
    cols = ("spherex_dr1", "spherex_qr3")
    try:
        rows, _ = irsa._search_tap(*BARNARD, 0.01, 61100.0, 61200.0, cols, deadline=t0 + 75)
    except (requests.Timeout, requests.ConnectionError) as e:
        pytest.skip(f"IRSA TAP unreachable (the query was not rejected): {e}")
    except requests.HTTPError as e:
        if e.response is not None and e.response.status_code >= 500:
            pytest.skip(f"IRSA TAP outage: {e}")
        raise
    # An 'unsupported ADQL' answer raises SearchError above (parse_tap_csv) and fails the test.
    print(f"TAP circle+time: {len(rows)} rows in {time.monotonic() - t0:.1f} s")
    assert rows and all(61100 - 0.01 <= r.ref.mjd <= 61200 + 0.01 for r in rows)
    assert {r.collection for r in rows} <= set(cols)


@pytest.mark.parametrize("field_id", OFFICIAL)
def test_committed_snapshot_matches_live_sia(field_id):
    """The committed snapshot replays live SIA answers: centre point search and an off-centre 0.02 deg circle."""
    from errante.data import irsa

    snap = irsa.load_snapshot(irsa.snapshot_path(field_id, irsa.DEFAULT_SNAPSHOT_DIR))
    last_mjd = max(s.row.ref.mjd for s in snap.rows)
    # Off-centre position ~0.06 deg north-east, still inside the 0.1 deg disk with its 0.02 deg circle.
    ra2 = snap.ra + 0.0424 / math.cos(math.radians(snap.dec))
    probes = [(snap.ra, snap.dec, 0.0), (ra2, snap.dec + 0.0424, 0.02)]
    for ra, dec, radius in probes:
        assert snap.covers(ra, dec, max(radius, irsa.MIN_RADIUS_DEG), snap.collections)
        live = _live(
            irsa.search_frames_report,
            ra,
            dec,
            radius,
            collections=snap.collections,
            use_cache=False,
            use_snapshot=False,
        )
        live_keys = {(f.obs_id, f.detector): f for f in live.result.frames}
        replay = {(r.ref.obs_id, r.ref.detector) for r in snap.frames(ra, dec, max(radius, irsa.MIN_RADIUS_DEG))}
        newer = {k for k in live_keys.keys() - replay if live_keys[k].mjd > last_mjd}
        print(
            f"{field_id} ({ra:.5f}, {dec:.5f}) r={radius}: live {len(live_keys)} replay {len(replay)} newer {len(newer)}"
        )
        assert replay <= live_keys.keys(), sorted(replay - live_keys.keys())[:5]
        assert live_keys.keys() - replay == newer  # only frames published after the snapshot are missing


def test_snapshot_generation_live(tmp_path):
    from errante.data import irsa

    try:
        doc = irsa.fetch_snapshot("barnards-star", *BARNARD, radius_deg=0.05, rounds=2, pause_s=5)
    except irsa.SearchError as e:
        if e.is_outage:
            pytest.skip(f"IRSA SIA outage: {e}")
        raise
    path = irsa.write_snapshot(doc, tmp_path / "barnards-star.json")
    snap = irsa.load_snapshot(path)
    check = doc["provenance"]["point_check"]
    print(f"snapshot r=0.05: {len(snap.rows)} frames, {path.stat().st_size} B, point check {check}")
    assert len(snap.rows) > 350 and doc["provenance"]["queries"][0]["pos"].endswith(" 0.05")
    if "error" not in check:
        assert check["only_live"] == [] and check["only_replayed"] == []


def test_search_key_is_readable_on_s3():
    from errante import settings
    from errante.data.irsa import search_frames

    res = _live(search_frames, *BARNARD, detectors=[1])
    assert res.frames
    key = res.frames[0].s3_key
    r = requests.get(f"{settings.S3_HTTPS}/{key}", headers={"Range": "bytes=0-2879"}, timeout=60)
    assert r.status_code == 206 and r.content.startswith(b"SIMPLE  =")
