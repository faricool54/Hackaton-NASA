"""Offline tests for errante.data.irsa.search_frames (WS1-2).

fixtures/ws1/barnard_sia_dr1_qr3.xml is a real SIA2 VOTable for Barnard's Star (269.44623, 4.76870)
recorded on 2026-11-14 and trimmed to 14 of its 358 rows (header and FIELDs untouched).
fixtures/ws1/barnard_tap_from_sia.csv is NOT a recorded TAP answer: IRSA TAP returned 502 or hung
for the whole session on 2026-11-14, so it holds the same 14 real rows (uri, t_min/t_max,
bandpass, collection) in the CSV layout of ``irsa.build_query``'s SELECT, with planeid left empty.
TODO(WS1): re-record it from a real TAP answer once TAP is back. Tried again 2026-11-14 19:16-19:54 UTC:
every TAP query on the spherex tables hung (the fallback point query 2x200 s, TOP 5 on spherex.plane and
spherex.obscore 240 s, a non-spatial query by artifact uri 2x200 s, even `SELECT TOP 1 planeid FROM
spherex.plane` > 90 s) or got a fast 502, while TAP_SCHEMA answered in 0.5 s. One thing was learnt:
INTERSECTS(CIRCLE(...), p.poly) is rejected at once as unsupported ADQL; INTERSECTS(p.poly, CIRCLE(...)) is not.

Search snapshots: the committed data/index/search/<field-id>.json files (errante snapshot-search, live SIA
2026-11-14) are checked for schema/size and replayed offline; the generator itself is tested on the fixture.
The autouse fixture turns snapshots off, so the older tests keep seeing IRSA failures as errors.
"""

from __future__ import annotations

import json
import math
import time
from pathlib import Path

import pytest
import requests

from errante import settings
from errante.cli import main as cli_main
from errante.data import irsa
from errante.models import FrameRef, SearchResult

FIX = Path(__file__).parent / "fixtures" / "ws1"
SIA_XML = (FIX / "barnard_sia_dr1_qr3.xml").read_bytes()
TAP_CSV = (FIX / "barnard_tap_from_sia.csv").read_bytes()
RA, DEC = 269.44623, 4.76870


class FakeResponse:
    def __init__(self, status: int = 200, content: bytes = b"", headers: dict | None = None):
        self.status_code = status
        self.content = content
        self.headers = headers or {}
        self.text = content.decode("utf-8")

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}", response=self)


class FakeIRSA:
    """Replaces irsa._http. Each service answers from its queue; the last item repeats."""

    def __init__(self, sia=None, tap=None):
        self.queues = {settings.IRSA_SIA: list(sia or []), settings.IRSA_TAP_SYNC: list(tap or [])}
        self.calls: list[dict] = []

    def __call__(self, method, url, *, params=None, data=None, timeout):
        self.calls.append({"method": method, "url": url, "params": params, "data": data, "timeout": timeout})
        queue = self.queues[url]
        if not queue:
            raise AssertionError(f"unexpected request to {url}")
        item = queue.pop(0) if len(queue) > 1 else queue[0]
        if isinstance(item, Exception):
            raise item
        return item

    def count(self, url: str) -> int:
        return sum(c["url"] == url for c in self.calls)


@pytest.fixture(autouse=True)
def _isolated(monkeypatch, tmp_path):
    monkeypatch.setattr(irsa, "SNAPSHOT_DIR", None)  # committed snapshots off unless a test enables them
    monkeypatch.setattr(settings, "CACHE_DIR", tmp_path / "cache")
    monkeypatch.setattr(settings, "IRSA_COLLECTIONS", ("spherex_dr1", "spherex_qr3"))
    monkeypatch.setattr(settings, "SEARCH_ATTEMPTS", 3)
    monkeypatch.setattr(settings, "SEARCH_BACKOFF_S", 0.0)
    monkeypatch.setattr(settings, "QUERY_CACHE_TTL_S", 86400.0)


def install(monkeypatch, sia=None, tap=None) -> FakeIRSA:
    fake = FakeIRSA(sia=sia, tap=tap)
    monkeypatch.setattr(irsa, "_http", fake)
    return fake


def ok(content: bytes) -> FakeResponse:
    return FakeResponse(200, content)


# --------------------------------------------------------------------------- parsing


def test_parse_real_sia_votable():
    rows, overflow = irsa.parse_sia_votable(SIA_XML)
    assert not overflow
    assert len(rows) == 14
    assert {r.collection for r in rows} == {"spherex_dr1", "spherex_qr3"}
    assert {r.ref.detector for r in rows} == {1, 2, 3, 4, 5, 6}
    for r in rows:
        ref = r.ref
        assert ref.irsa_uri == f"ibe/data/spherex/{ref.s3_key}"
        assert ref.s3_key.startswith(f"{ref.release}/level2/")
        assert ref.s3_key.endswith(f"level2_{ref.obs_id}D{ref.detector}_spx_{r.pipeline_version}.fits")
        assert r.collection == f"spherex_{ref.release}"
        assert ref.wavelength_um is None
    row = next(r for r in rows if r.ref.obs_id == "2025W33_2C_0321_1" and r.ref.detector == 6)
    # t_min = 60902.864715, t_max = 60902.866047: mjd is the mid-exposure time
    assert row.ref.mjd == pytest.approx((60902.864715 + 60902.866047) / 2, abs=1e-9)
    assert row.ref.release == "dr1"
    assert row.pipeline_version == "l2b-v27-2026-228"


def test_parse_overflow_and_error_status():
    rows, overflow = irsa.parse_sia_votable(
        SIA_XML.replace(b'"QUERY_STATUS" value="OK"', b'"QUERY_STATUS" value="OVERFLOW"')
    )
    assert overflow and len(rows) == 14
    err = SIA_XML.replace(
        b'<INFO name="QUERY_STATUS" value="OK"/>', b'<INFO name="QUERY_STATUS" value="ERROR">bad POS</INFO>'
    )
    with pytest.raises(irsa.SearchError, match="bad POS"):
        irsa.parse_sia_votable(err)


def test_parse_tap_csv_matches_sia():
    rows = irsa.parse_tap_csv(TAP_CSV.decode())
    sia_rows, _ = irsa.parse_sia_votable(SIA_XML)
    assert len(rows) == 14
    for r in rows:
        assert r.ref.irsa_uri == f"ibe/data/spherex/{r.ref.s3_key}"
        assert r.collection in {"spherex_dr1", "spherex_qr3"}
    by_key = {(r.ref.obs_id, r.ref.detector): r for r in rows}
    assert by_key.keys() == {(r.ref.obs_id, r.ref.detector) for r in sia_rows}
    for r in sia_rows:
        tap = by_key[(r.ref.obs_id, r.ref.detector)]
        assert (tap.ref, tap.collection, tap.pipeline_version) == (r.ref, r.collection, r.pipeline_version)
    with pytest.raises(irsa.SearchError):
        irsa.parse_tap_csv('<?xml version="1.0"?><VOTABLE><INFO name="QUERY_STATUS" value="ERROR">x</INFO></VOTABLE>')


# --------------------------------------------------------------------------- search via SIA


def test_search_frames_via_sia(monkeypatch):
    fake = install(monkeypatch, sia=[ok(SIA_XML)])
    res = irsa.search_frames(RA, DEC)
    assert isinstance(res, SearchResult)
    assert len(res.frames) == 14
    assert [f.mjd for f in res.frames] == sorted(f.mjd for f in res.frames)
    assert res.center.ra == pytest.approx(RA) and res.center.dec == pytest.approx(DEC)
    assert res.radius_deg == pytest.approx(1 / 3600)
    (call,) = fake.calls
    assert call["method"] == "GET" and call["url"] == settings.IRSA_SIA
    params = call["params"]
    assert [v for k, v in params if k == "COLLECTION"] == ["spherex_dr1", "spherex_qr3"]
    assert dict(params)["POS"] == "CIRCLE 269.44623000 4.76870000 0.000277777778"
    assert dict(params)["RESPONSEFORMAT"] == "VOTABLE"
    assert int(dict(params)["MAXREC"]) >= 10000
    assert "TIME" not in dict(params)
    # The model round-trips through JSON (backend response_model).
    SearchResult.model_validate_json(res.model_dump_json())


def test_radius_is_forwarded(monkeypatch):
    fake = install(monkeypatch, sia=[ok(SIA_XML)])
    res = irsa.search_frames(RA, DEC, radius_deg=0.1)
    assert res.radius_deg == pytest.approx(0.1)
    assert dict(fake.calls[0]["params"])["POS"].endswith(" 0.1")


@pytest.mark.parametrize(
    ("mjd_min", "mjd_max", "expected"),
    [
        (61100, 61200, "61100.00000000 61200.00000000"),
        (61200, None, "61200.00000000 100000.00000000"),
        (None, 61000.5, "0.00000000 61000.50000000"),
    ],
)
def test_time_parameter(monkeypatch, mjd_min, mjd_max, expected):
    fake = install(monkeypatch, sia=[ok(SIA_XML)])
    irsa.search_frames(RA, DEC, mjd_min=mjd_min, mjd_max=mjd_max)
    assert dict(fake.calls[0]["params"])["TIME"] == expected


def test_detector_filter_and_signature_used_by_build_and_backend(monkeypatch):
    fake = install(monkeypatch, sia=[ok(SIA_XML)])
    # backend/errante_api/routes/live.py
    res = irsa.search_frames(RA, DEC, detectors=[1, 4])
    assert {f.detector for f in res.frames} == {1, 4}
    assert len(res.frames) == 4
    # build.py: detectors=None + MJD bounds (cached search, filtered afterwards)
    res2 = irsa.search_frames(RA, DEC, detectors=None, mjd_min=None, mjd_max=None)
    assert len(res2.frames) == 14
    assert fake.count(settings.IRSA_SIA) == 1  # detectors do not change the cache key


def test_dedupe_end_to_end(monkeypatch):
    # Duplicate one real row as if it also came from QR2: DR1 must win.
    text = SIA_XML.decode()
    start = text.index("<TR>")
    end = text.index("</TR>", start) + len("</TR>")
    row = text[start:end]
    assert "spherex/dr1/" in row
    dup = row.replace("spherex/dr1/", "spherex/qr2/").replace("&quot;dr1/", "&quot;qr2/")
    dup = dup.replace("spherex_dr1", "spherex_qr2")
    install(monkeypatch, sia=[ok((text[:start] + dup + row + text[end:]).encode())])
    rep = irsa.search_frames_report(RA, DEC)
    assert len(rep.result.frames) == 14
    assert rep.n_duplicates == 1
    keys = [(f.obs_id, f.detector) for f in rep.result.frames]
    assert len(keys) == len(set(keys))
    assert all(f.release in {"dr1", "qr3"} for f in rep.result.frames)


def _row(obs_id: str, det: int, mjd: float, release: str, version: str, collection: str = "") -> irsa.ArchiveRow:
    key = f"{release}/level2/{obs_id[:10]}/{version}/{det}/level2_{obs_id}D{det}_spx_{version}.fits"
    ref = FrameRef(
        obs_id=obs_id, detector=det, mjd=mjd, release=release, irsa_uri=f"ibe/data/spherex/{key}", s3_key=key
    )
    return irsa.ArchiveRow(ref=ref, collection=collection or f"spherex_{release}", pipeline_version=version)


def test_dedupe_prefers_data_release_then_newer_pipeline():
    rows = [
        _row("2025W33_2C_0321_1", 3, 60902.87, "qr2", "l2b-v20-2025-300"),
        _row("2025W33_2C_0321_1", 3, 60902.87, "dr1", "l2b-v27-2026-228"),
        _row("2026W33_2A_0594_4", 6, 61268.63, "qr3", "l2b-v27-2026-241"),
        _row("2026W33_2A_0594_4", 6, 61268.63, "qr3", "l2b-v27-2026-250"),
        _row("2025W34_2B_0090_4", 2, 60908.98, "dr1", "l2b-v27-2026-229"),
    ]
    out, n_dup = irsa.dedupe_rows(rows)
    assert n_dup == 2
    assert [(r.ref.obs_id, r.ref.release, r.pipeline_version) for r in out] == [
        ("2025W33_2C_0321_1", "dr1", "l2b-v27-2026-228"),
        ("2025W34_2B_0090_4", "dr1", "l2b-v27-2026-229"),
        ("2026W33_2A_0594_4", "qr3", "l2b-v27-2026-250"),
    ]


def test_skips_rows_that_are_not_level2_frames(monkeypatch):
    text = SIA_XML.decode()
    start = text.index("<TR>")
    end = text.index("</TR>", start) + len("</TR>")
    row = text[start:end]
    junk = row.replace("level2_", "cube_")
    rows, _ = irsa.parse_sia_votable((text[:start] + junk + text[end:]).encode())
    assert len(rows) == 13


# --------------------------------------------------------------------------- retries and TAP fallback


def test_retries_5xx_then_succeeds(monkeypatch):
    # SIA twice, then TAP, then SIA again (2026-11-15: IRSA answered SIA and TAP with intermittent fast 502s).
    fake = install(monkeypatch, sia=[FakeResponse(503), FakeResponse(502), ok(SIA_XML)], tap=[FakeResponse(502)])
    rep = irsa.search_frames_report(RA, DEC)
    assert rep.service == "sia" and len(rep.result.frames) == 14
    assert [c["url"] for c in fake.calls] == [settings.IRSA_SIA] * 2 + [settings.IRSA_TAP_SYNC, settings.IRSA_SIA]
    assert [e.split(":")[0] for e in rep.retries] == ["sia 1/3", "sia 2/3", "tap 1/3"]
    assert rep.errors == []  # SIA answered on a retry: a complete answer, not a fallback (no `partial` downstream)


def test_falls_back_to_tap_when_sia_keeps_failing(monkeypatch):
    fake = install(monkeypatch, sia=[FakeResponse(502)], tap=[ok(TAP_CSV)])
    rep = irsa.search_frames_report(RA, DEC, mjd_min=60000, mjd_max=62000)
    assert rep.service == "tap"
    assert rep.result.frames
    assert rep.errors and rep.errors[0].startswith("sia 1/3: HTTPError: HTTP 502")
    assert fake.count(settings.IRSA_SIA) == 2  # SIA, SIA, then TAP answered
    tap = next(c for c in fake.calls if c["url"] == settings.IRSA_TAP_SYNC)
    assert tap["method"] == "POST" and tap["data"]["FORMAT"] == "csv" and tap["data"]["LANG"] == "ADQL"
    query = tap["data"]["QUERY"]
    assert "CONTAINS(POINT('ICRS', 269.44623000, 4.76870000), p.poly)" in query
    assert "p.time_bounds_upper" in query
    assert "o.collection IN ('spherex_dr1', 'spherex_qr3')" in query
    assert "p.time_bounds_upper >= 60000.00000000 AND p.time_bounds_lower <= 62000.00000000" in query


@pytest.mark.parametrize(
    "bad_sia",
    [
        FakeResponse(200, b"<html><body>Service temporarily unavailable</body></html>"),
        FakeResponse(400, b"bad request"),
        requests.ConnectionError("connection reset"),
    ],
)
def test_falls_back_to_tap_on_bad_sia_answers(monkeypatch, bad_sia):
    fake = install(monkeypatch, sia=[bad_sia], tap=[ok(TAP_CSV)])
    rep = irsa.search_frames_report(RA, DEC)
    assert rep.service == "tap" and rep.result.frames
    if isinstance(bad_sia, FakeResponse) and bad_sia.status_code == 400:
        assert fake.count(settings.IRSA_SIA) == 1  # 4xx is not retried


def test_tap_radius_uses_intersects():
    q = irsa.build_query(RA, DEC, radius_deg=0.05, collections=["spherex_dr1"])
    # Column first: IRSA TAP rejects INTERSECTS(CIRCLE(...), p.poly) as "unsupported ADQL" (live, 2026-11-14).
    assert "INTERSECTS(p.poly, CIRCLE('ICRS', 269.44623000, 4.76870000, 0.05))" in q
    assert "INTERSECTS(CIRCLE" not in q
    # Old call form still works.
    assert "p.energy_bandpassname = 'SPHEREx-D3'" in irsa.build_query(RA, DEC, 3)


def _cause_chain(err: BaseException) -> list[BaseException]:
    out = []
    while err is not None:
        out.append(err)
        err = err.__cause__
    return out


def test_timeout_reaches_cause_chain(monkeypatch):
    fake = install(monkeypatch, sia=[requests.ReadTimeout("sia slow")], tap=[requests.ReadTimeout("tap slow")])
    with pytest.raises(irsa.SearchError) as exc:
        irsa.search_frames(RA, DEC)
    assert any(isinstance(e, requests.Timeout) for e in _cause_chain(exc.value))
    # A timeout switches service; a service that timed out twice is not asked again (not SEARCH_ATTEMPTS times).
    assert fake.count(settings.IRSA_SIA) == 2 and fake.count(settings.IRSA_TAP_SYNC) == 2
    assert [c["url"] for c in fake.calls] == [settings.IRSA_SIA, settings.IRSA_TAP_SYNC] * 2


def test_both_services_down_is_not_a_timeout(monkeypatch):
    install(monkeypatch, sia=[FakeResponse(502)], tap=[FakeResponse(503)])
    with pytest.raises(irsa.SearchError, match="after 6 attempt.*sia 1/3: HTTPError.*tap 1/3: HTTPError") as exc:
        irsa.search_frames(RA, DEC)
    chain = _cause_chain(exc.value)
    assert not any(isinstance(e, (requests.Timeout, TimeoutError)) for e in chain)
    assert isinstance(chain[1], requests.HTTPError) and chain[1].response.status_code == 503  # the last error
    assert exc.value.is_outage and len(exc.value.failures) == 6  # SEARCH_ATTEMPTS (3) per service


def test_parse_failure_is_not_an_outage(monkeypatch):
    install(monkeypatch, sia=[ok(b"<html>not a votable</html>")], tap=[FakeResponse(502)])
    with pytest.raises(irsa.SearchError) as exc:
        irsa.search_frames(RA, DEC)
    assert not exc.value.is_outage


# --------------------------------------------------------------------------- cache


def test_cache_hit_skips_network(monkeypatch):
    fake = install(monkeypatch, sia=[ok(SIA_XML)])
    first = irsa.search_frames_report(RA, DEC)
    second = irsa.search_frames_report(RA, DEC)
    assert not first.from_cache and second.from_cache
    assert second.service == "sia"
    assert second.result == first.result
    assert fake.count(settings.IRSA_SIA) == 1
    files = list((settings.CACHE_DIR / "queries").glob("search_*.json"))
    assert len(files) == 1
    doc = json.loads(files[0].read_text(encoding="utf-8"))
    assert doc["format"] == irsa.CACHE_FORMAT and len(doc["rows"]) == 14


def test_cache_expires_and_can_be_bypassed(monkeypatch):
    fake = install(monkeypatch, sia=[ok(SIA_XML)])
    irsa.search_frames(RA, DEC)
    (path,) = (settings.CACHE_DIR / "queries").glob("search_*.json")
    doc = json.loads(path.read_text(encoding="utf-8"))
    doc["created"] = time.time() - 2 * 86400
    path.write_text(json.dumps(doc), encoding="utf-8")
    irsa.search_frames(RA, DEC)
    assert fake.count(settings.IRSA_SIA) == 2
    irsa.search_frames(RA, DEC, use_cache=False)
    assert fake.count(settings.IRSA_SIA) == 3
    path.write_text("{not json", encoding="utf-8")  # a corrupt entry is ignored, not fatal
    irsa.search_frames(RA, DEC)
    assert fake.count(settings.IRSA_SIA) == 4


def test_expired_cache_is_served_when_irsa_is_down(monkeypatch):
    install(monkeypatch, sia=[ok(SIA_XML)])
    irsa.search_frames(RA, DEC)
    (path,) = (settings.CACHE_DIR / "queries").glob("search_*.json")
    doc = json.loads(path.read_text(encoding="utf-8"))
    doc["created"] = time.time() - 3 * 86400
    path.write_text(json.dumps(doc), encoding="utf-8")
    install(monkeypatch, sia=[FakeResponse(502)], tap=[requests.ReadTimeout("tap slow")])
    rep = irsa.search_frames_report(RA, DEC, detectors=[3])
    assert rep.stale and rep.from_cache and rep.service == "sia"
    assert {f.detector for f in rep.result.frames} == {3} and len(rep.result.frames) == 3
    assert "IRSA frame search failed" in rep.errors[0]
    # Without a cache entry the failure propagates.
    with pytest.raises(irsa.SearchError):
        irsa.search_frames(RA, DEC, use_cache=False)


def test_cache_key_includes_collections_and_time(monkeypatch):
    fake = install(monkeypatch, sia=[ok(SIA_XML)])
    irsa.search_frames(RA, DEC)
    irsa.search_frames(RA, DEC, collections=["spherex_dr1", "spherex_qr3", "spherex_dr1_deep"])
    irsa.search_frames(RA, DEC, mjd_min=61000)
    irsa.search_frames(RA, DEC, collections="spherex_qr3,spherex_dr1")  # same set, other order: cached
    assert fake.count(settings.IRSA_SIA) == 3
    deep_call = fake.calls[1]["params"]
    assert [v for k, v in deep_call if k == "COLLECTION"] == ["spherex_dr1", "spherex_dr1_deep", "spherex_qr3"]


def test_collections_from_settings(monkeypatch):
    monkeypatch.setattr(settings, "IRSA_COLLECTIONS", ("spherex_qr3",))
    fake = install(monkeypatch, sia=[ok(SIA_XML)])
    irsa.search_frames(RA, DEC)
    assert [v for k, v in fake.calls[0]["params"] if k == "COLLECTION"] == ["spherex_qr3"]


def test_empty_answer_is_not_cached(monkeypatch):
    text = SIA_XML.decode()
    empty = text[: text.index("<TABLEDATA>") + len("<TABLEDATA>")] + text[text.index("</TABLEDATA>") :]
    fake = install(monkeypatch, sia=[ok(empty.encode())])
    assert irsa.search_frames(RA, DEC).frames == []
    assert irsa.search_frames(RA, DEC).frames == []
    assert fake.count(settings.IRSA_SIA) == 2


def test_cache_disabled_with_ttl_zero(monkeypatch):
    monkeypatch.setattr(settings, "QUERY_CACHE_TTL_S", 0.0)
    fake = install(monkeypatch, sia=[ok(SIA_XML)])
    irsa.search_frames(RA, DEC)
    irsa.search_frames(RA, DEC)
    assert fake.count(settings.IRSA_SIA) == 2
    assert not (settings.CACHE_DIR / "queries").exists()


# --------------------------------------------------------------------------- validation and CLI


@pytest.mark.parametrize(
    "kwargs",
    [
        {"dec": 91.0},
        {"detectors": [0]},
        {"detectors": [7]},
        {"mjd_min": 61200, "mjd_max": 61100},
        {"radius_deg": -1.0},
        {"collections": ["spherex_dr1; DROP"]},
        {"collections": []},
    ],
)
def test_invalid_arguments(monkeypatch, kwargs):
    install(monkeypatch)
    args = {"ra": RA, "dec": DEC} | kwargs
    with pytest.raises(ValueError):
        irsa.search_frames(args.pop("ra"), args.pop("dec"), **args)


def test_cli_default_output_is_a_search_result(monkeypatch, capsys):
    # WS1-2 acceptance: `errante search --ra 269.4463 --dec 4.7665` prints a valid SearchResult (stdout only).
    install(monkeypatch, sia=[ok(SIA_XML)])
    assert cli_main(["search", "--ra", "269.4463", "--dec", "4.7665"]) == 0
    captured = capsys.readouterr()
    res = SearchResult.model_validate_json(captured.out)
    assert len(res.frames) == 14
    assert "14 frames via SIA" in captured.err  # diagnostics never pollute the JSON

    assert (
        cli_main(["search", "--ra", str(RA), "--dec", str(DEC), "--radius", "0.01", "--detector", "6", "--json"]) == 0
    )
    res = SearchResult.model_validate_json(capsys.readouterr().out)
    assert {f.detector for f in res.frames} == {6}

    with pytest.raises(SystemExit):  # --json and --summary are exclusive
        cli_main(["search", "--ra", str(RA), "--dec", str(DEC), "--json", "--summary"])
    capsys.readouterr()

    install(monkeypatch, sia=[FakeResponse(502)], tap=[FakeResponse(502)])
    assert cli_main(["search", "--ra", "1", "--dec", "1", "--no-cache"]) == 2
    captured = capsys.readouterr()
    assert "Search failed" in captured.err and captured.out == ""


def test_cli_summary(monkeypatch, capsys):
    install(monkeypatch, sia=[ok(SIA_XML)])
    assert cli_main(["search", "--ra", str(RA), "--dec", str(DEC), "--radius", "0.01", "--summary"]) == 0
    out = capsys.readouterr().out
    assert "14 frames" in out and "via SIA" in out
    assert "by collection: spherex_dr1: 10, spherex_qr3: 4" in out
    assert "by detector:   D1: 2, D2: 2, D3: 3, D4: 2, D5: 2, D6: 3" in out
    # Trimmed fixture: in-season gaps exceed 30 d, so the CLI lists 5 "seasons" here.
    assert "1. MJD 60902.87-60914.21" in out and "5. MJD 61305.63-61305.63" in out


# --------------------------------------------------------------------------- review regressions


def _empty_votable() -> bytes:
    text = SIA_XML.decode()
    return (text[: text.index("<TABLEDATA>") + len("<TABLEDATA>")] + text[text.index("</TABLEDATA>") :]).encode()


def _overflow_votable() -> bytes:
    return SIA_XML.replace(b'"QUERY_STATUS" value="OK"', b'"QUERY_STATUS" value="OVERFLOW"')


def test_truncated_result_is_not_cached_so_a_bigger_maxrec_reaches_irsa(monkeypatch):
    calls: list[int] = []

    def fake_http(method, url, *, params=None, data=None, timeout):
        maxrec = int(dict(params)["MAXREC"])
        calls.append(maxrec)
        return ok(_overflow_votable() if maxrec < 1000 else SIA_XML)

    monkeypatch.setattr(irsa, "_http", fake_http)
    monkeypatch.setattr(settings, "SIA_MAXREC", 200)
    first = irsa.search_frames_report(RA, DEC)
    assert first.overflow and not first.from_cache
    assert not (settings.CACHE_DIR / "queries").exists()
    monkeypatch.setattr(settings, "SIA_MAXREC", 50000)
    second = irsa.search_frames_report(RA, DEC)
    assert not second.overflow and not second.from_cache
    assert calls == [200, 50000]
    # A truncated entry left by an older version is not served as a fresh hit either.
    (path,) = (settings.CACHE_DIR / "queries").glob("search_*.json")
    doc = json.loads(path.read_text(encoding="utf-8"))
    path.write_text(json.dumps(doc | {"overflow": True}), encoding="utf-8")
    third = irsa.search_frames_report(RA, DEC)
    assert not third.from_cache and calls == [200, 50000, 50000]


@pytest.mark.parametrize("content", ["null", "[]", '"text"', "42"])
def test_cache_entry_that_is_not_an_object_is_ignored(monkeypatch, content):
    fake = install(monkeypatch, sia=[ok(SIA_XML)])
    irsa.search_frames(RA, DEC)
    (path,) = (settings.CACHE_DIR / "queries").glob("search_*.json")
    path.write_text(content, encoding="utf-8")
    assert len(irsa.search_frames(RA, DEC).frames) == 14
    assert fake.count(settings.IRSA_SIA) == 2


@pytest.mark.parametrize(("ra", "expected"), [(-1e-17, 0.0), (-0.0, 0.0), (360.0, 0.0), (725.5, 5.5), (-0.5, 359.5)])
def test_ra_wraps_into_0_360(monkeypatch, ra, expected):
    # -1e-17 % 360.0 == 360.0 in float arithmetic: it used to query IRSA and then fail in SkyCoord.
    fake = install(monkeypatch, sia=[ok(_empty_votable())])
    res = irsa.search_frames(ra, DEC)
    assert res.center.ra == pytest.approx(expected) and 0.0 <= res.center.ra < 360.0
    assert dict(fake.calls[0]["params"])["POS"].startswith(f"CIRCLE {expected:.8f} ")


def test_sia_timeout_then_tap_error_surfaces_as_timeout(monkeypatch):
    # Backend: a Timeout anywhere in __cause__ -> 504. SIA timed out, TAP answered 502.
    install(monkeypatch, sia=[requests.ReadTimeout("sia slow")], tap=[FakeResponse(502)])
    with pytest.raises(irsa.SearchError) as exc:
        irsa.search_frames(RA, DEC)
    assert isinstance(exc.value.__cause__, requests.Timeout)
    assert exc.value.is_outage
    # SIA hang -> TAP 502 -> SIA hang (2nd timeout: SIA done) -> TAP 502 -> TAP 502 (3rd: TAP done).
    rt, he = requests.ReadTimeout, requests.HTTPError
    assert [type(e) for e in exc.value.failures] == [rt, he, rt, he, he]


class FakeClock:
    """Replaces irsa.time: monotonic() and sleep() are simulated, time() is real (cache ages)."""

    def __init__(self):
        self.now = 1000.0

    def monotonic(self) -> float:
        return self.now

    def sleep(self, s: float) -> None:
        self.now += s

    @staticmethod
    def time() -> float:
        return time.time()


def _hanging_http(clock: FakeClock, calls: list, sia_status: int | None = None):
    """SIA/TAP that hang for the whole timeout, or SIA that answers ``sia_status`` at once."""

    def fake_http(method, url, *, params=None, data=None, timeout):
        calls.append((url, timeout))
        if url == settings.IRSA_SIA and sia_status is not None:
            return FakeResponse(sia_status)
        clock.now += timeout
        raise requests.ReadTimeout(f"{url} hung {timeout} s")

    return fake_http


@pytest.mark.parametrize("sia_status", [None, 502])
def test_deadline_bounds_a_dead_irsa(monkeypatch, sia_status):
    clock = FakeClock()
    calls: list = []
    monkeypatch.setattr(irsa, "time", clock)
    monkeypatch.setattr(irsa, "_http", _hanging_http(clock, calls, sia_status))
    monkeypatch.setattr(settings, "SEARCH_ATTEMPTS", 4)
    monkeypatch.setattr(settings, "SEARCH_BACKOFF_S", 1.0)
    monkeypatch.setattr(settings, "SIA_TIMEOUT_S", 30.0)
    monkeypatch.setattr(settings, "TAP_TIMEOUT_S", 60.0)
    monkeypatch.setattr(settings, "SEARCH_DEADLINE_S", 60.0)
    t0 = clock.now
    with pytest.raises(irsa.SearchError) as exc:
        irsa.search_frames(RA, DEC)
    assert clock.now - t0 <= 60.0  # was ~128 s (SIA 502 + TAP hang) or ~182 s (both hang)
    assert isinstance(exc.value.__cause__, requests.Timeout)
    assert any(url == settings.IRSA_TAP_SYNC for url, _ in calls)  # TAP still got its turn
    assert all(timeout <= 60.0 for _, timeout in calls)

    # SEARCH_DEADLINE_S = 0 disables the budget (old behaviour: 2 timeouts per service).
    calls.clear()
    monkeypatch.setattr(settings, "SEARCH_DEADLINE_S", 0.0)
    t0 = clock.now
    with pytest.raises(irsa.SearchError):
        irsa.search_frames(RA, DEC)
    assert clock.now - t0 > 120.0


def test_deadline_already_spent_raises_timeout(monkeypatch):
    clock = FakeClock()
    monkeypatch.setattr(irsa, "time", clock)
    fake = install(monkeypatch, sia=[ok(SIA_XML)])
    with pytest.raises(requests.Timeout):
        irsa._fetch("GET", settings.IRSA_SIA, timeout=30, deadline=clock.now + 1.0)
    assert fake.calls == []


def test_callers_deadline_caps_the_search_budget(monkeypatch):
    """``deadline_s`` (point_series' budget for the WHOLE call) caps SEARCH_DEADLINE_S; with no time left IRSA is
    not asked: a fresh cached answer still answers, else SearchError with a timeout cause (backend: 504)."""
    clock = FakeClock()
    calls: list = []
    monkeypatch.setattr(irsa, "time", clock)
    monkeypatch.setattr(irsa, "_http", _hanging_http(clock, calls))
    monkeypatch.setattr(settings, "SEARCH_ATTEMPTS", 4)
    monkeypatch.setattr(settings, "SEARCH_BACKOFF_S", 1.0)
    monkeypatch.setattr(settings, "SEARCH_DEADLINE_S", 60.0)
    t0 = clock.now
    with pytest.raises(irsa.SearchError) as exc:
        irsa.search_frames_report(RA, DEC, deadline_s=10.0)
    assert clock.now - t0 <= 10.0 and calls and all(timeout <= 10.0 for _, timeout in calls)
    assert isinstance(exc.value.__cause__, requests.Timeout)
    calls.clear()
    with pytest.raises(irsa.SearchError) as exc:
        irsa.search_frames_report(RA, DEC, deadline_s=0.0)
    assert calls == [] and isinstance(exc.value.__cause__, requests.Timeout)  # nothing sent
    fake = install(monkeypatch, sia=[ok(SIA_XML)])
    first = irsa.search_frames_report(RA, DEC)
    again = irsa.search_frames_report(RA, DEC, deadline_s=0.0)
    assert again.from_cache and again.result.frames == first.result.frames and fake.count(settings.IRSA_SIA) == 1
    with pytest.raises(ValueError):
        irsa.search_frames_report(RA, DEC, deadline_s=float("nan"))


def _slow_sia_http(clock: FakeClock, calls: list, sia_s: float):
    """SIA that answers SIA_XML after ``sia_s`` (a timeout if given less); TAP hangs for the whole timeout."""

    def fake_http(method, url, *, params=None, data=None, timeout):
        calls.append((url, timeout))
        if url == settings.IRSA_SIA and timeout >= sia_s:
            clock.now += sia_s
            return ok(SIA_XML)
        clock.now += timeout
        raise requests.ReadTimeout(f"{url} gave up after {timeout} s")

    return fake_http


def test_a_short_callers_deadline_is_all_sia(monkeypatch):
    """Review 2026-11-15: a caller's 5 s gave SIA only half (2.5 s), so a cold search that SIA answers in 3 s failed
    with a timeout (504) while TAP (8-19 s) could never use the other half. SIA now gets all of a budget up to
    _SIA_MIN_S, and half of a longer one, so a hung SIA still leaves TAP its turn."""
    clock, calls = FakeClock(), []
    monkeypatch.setattr(irsa, "time", clock)
    monkeypatch.setattr(irsa, "_http", _slow_sia_http(clock, calls, sia_s=3.0))
    for name, value in {
        "SIA_TIMEOUT_S": 30.0,
        "TAP_TIMEOUT_S": 60.0,
        "SEARCH_ATTEMPTS": 4,
        "SEARCH_BACKOFF_S": 1.0,
    }.items():
        monkeypatch.setattr(settings, name, value)
    monkeypatch.setattr(settings, "SEARCH_DEADLINE_S", 60.0)
    rep = irsa.search_frames_report(RA, DEC, deadline_s=5.0, use_cache=False)
    assert rep.service == "sia" and rep.result.frames and calls == [(settings.IRSA_SIA, 5.0)]

    # A hung SIA under a long budget: SIA half (30 s), TAP the rest, as before.
    calls.clear()
    monkeypatch.setattr(irsa, "_http", _slow_sia_http(clock, calls, sia_s=1e9))
    t0 = clock.now
    with pytest.raises(irsa.SearchError):
        irsa.search_frames_report(RA, DEC, use_cache=False)
    assert clock.now - t0 <= 60.0
    sia_time = sum(t for url, t in calls if url == settings.IRSA_SIA)
    assert sia_time <= 30.0 and any(url == settings.IRSA_TAP_SYNC for url, _ in calls)

    assert irsa.sia_budget(5.0) == 5.0 and irsa.sia_budget(14.0) == 10.0
    assert irsa.sia_budget(20.0) == 10.0 and irsa.sia_budget(60.0) == 30.0 and irsa.sia_budget(-1.0) == 0.0


def test_unknown_collection_is_reported(monkeypatch, caplog):
    install(monkeypatch, sia=[ok(_empty_votable())])
    with caplog.at_level("WARNING", logger="errante.data.irsa"):
        rep = irsa.search_frames_report(RA, DEC, collections=["spherex_dr9"])
    assert rep.result.frames == []
    assert len(rep.warnings) == 1 and "spherex_dr9" in rep.warnings[0]
    assert "spherex_dr9" in caplog.text and "No SPHEREx frames" in caplog.text
    # Known names (verified or configured) do not warn.
    install(monkeypatch, sia=[ok(SIA_XML)])
    assert irsa.search_frames_report(RA, DEC, collections=["spherex_qr3_deep", "spherex_dr1"]).warnings == []


def test_cli_prints_collection_warning(monkeypatch, capsys):
    install(monkeypatch, sia=[ok(_empty_votable())])
    assert cli_main(["search", "--ra", str(RA), "--dec", str(DEC), "--collections", "spherex_dr9"]) == 0
    captured = capsys.readouterr()
    assert SearchResult.model_validate_json(captured.out).frames == []
    assert "unknown IRSA collection 'spherex_dr9'" in captured.err


def test_tap_sends_maxrec_and_flags_truncation(monkeypatch):
    monkeypatch.setattr(settings, "SIA_MAXREC", 14)  # the TAP fixture has 14 rows
    fake = install(monkeypatch, sia=[FakeResponse(502)], tap=[ok(TAP_CSV)])
    rep = irsa.search_frames_report(RA, DEC)
    assert rep.service == "tap" and rep.overflow
    tap = next(c for c in fake.calls if c["url"] == settings.IRSA_TAP_SYNC)
    assert tap["data"]["MAXREC"] == "14"
    assert not (settings.CACHE_DIR / "queries").exists()  # truncated: not cached


def test_tap_queries_run_one_at_a_time(monkeypatch):
    import threading

    active = 0
    peak = 0
    guard = threading.Lock()

    def slow_tap(method, url, *, params=None, data=None, timeout):
        nonlocal active, peak
        with guard:
            active += 1
            peak = max(peak, active)
        time.sleep(0.15)
        with guard:
            active -= 1
        return ok(TAP_CSV)

    monkeypatch.setattr(irsa, "_http", slow_tap)
    results: list = []
    threads = [
        threading.Thread(
            target=lambda: results.append(irsa._search_tap(RA, DEC, irsa.MIN_RADIUS_DEG, None, None, ("spherex_dr1",)))
        )
        for _ in range(3)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=10)
    assert len(results) == 3 and all(len(rows) == 14 for rows, _ in results)
    assert peak == 1


# --------------------------------------------------------------------------- search snapshots (IRSA outage)

OFFICIAL = ("barnards-star", "eps-indi-b", "wise-0855", "rw-aurigae", "r-draconis")
SNAPSHOT_MAX_BYTES = 200_000  # per committed file (gzip-free JSON)
IRSA_DOWN = {"sia": [FakeResponse(502)], "tap": [requests.ReadTimeout("tap hangs")]}


def _make_snapshot(monkeypatch, directory: Path, radius_deg: float = 0.1, field_id: str = "barnards-star") -> Path:
    """A snapshot generated from the real SIA fixture (14 Barnard frames) through fetch_snapshot."""
    install(monkeypatch, sia=[ok(SIA_XML)])
    doc = irsa.fetch_snapshot(
        field_id, RA, DEC, name="Barnard's Star", radius_deg=radius_deg, rounds=1, pause_s=0, tile_radius_deg=10.0
    )
    return irsa.write_snapshot(doc, irsa.snapshot_path(field_id, directory))


@pytest.fixture
def snapdir(monkeypatch, tmp_path) -> Path:
    directory = tmp_path / "snapshots"
    _make_snapshot(monkeypatch, directory)
    monkeypatch.setattr(irsa, "SNAPSHOT_DIR", directory)
    return directory


def _unit(ra: float, dec: float):
    import numpy as np

    r, d = np.radians(ra), np.radians(dec)
    return np.array([np.cos(d) * np.cos(r), np.cos(d) * np.sin(r), np.sin(d)])


def _inside_convex(footprint, ra: float, dec: float) -> bool:
    """Independent check: a point is inside a convex spherical polygon iff it is on one side of every edge plane."""
    import numpy as np

    vs = [_unit(footprint[i], footprint[i + 1]) for i in range(0, len(footprint), 2)]
    p = _unit(ra, dec)
    signs = [np.sign(np.dot(np.cross(vs[i], vs[(i + 1) % len(vs)]), p)) for i in range(len(vs))]
    return all(s > 0 for s in signs) or all(s < 0 for s in signs)


def test_fetch_snapshot_document(monkeypatch, tmp_path):
    fake = install(monkeypatch, sia=[ok(SIA_XML)])
    doc = irsa.fetch_snapshot("barnards-star", RA, DEC, name="Barnard's Star", rounds=1, pause_s=0)
    assert doc["kind"] == irsa.SNAPSHOT_KIND and doc["format"] == irsa.SNAPSHOT_FORMAT
    assert doc["columns"] == list(irsa.SNAPSHOT_COLUMNS)
    assert doc["center"] == {"ra": RA, "dec": DEC} and doc["radius_deg"] == irsa.SNAPSHOT_RADIUS_DEG
    assert doc["collections"] == ["spherex_dr1", "spherex_qr3"]
    prov = doc["provenance"]
    assert prov["service"] == "sia" and prov["url"] == settings.IRSA_SIA
    # 0.1 deg is covered by 7 SIA circles of 0.055 deg (the fake answers the same 14 rows to each).
    assert len(prov["queries"]) == 7 and prov["rows_returned"] == 7 * 14
    assert prov["rows"] == prov["distinct_files"] == len(doc["rows"]) == 14
    assert prov["rows_by_collection"] == {"spherex_dr1": 10, "spherex_qr3": 4}
    assert sum(prov["rows_by_detector"].values()) == 14 and prov["duplicate_rows"] == 0
    assert prov["rows_outside_disk"] == prov["rows_without_footprint"] == 0
    assert prov["queried_utc"] == prov["queries"][0]["queried_utc"] and prov["queried_utc"].endswith("Z")
    assert prov["mjd_range"][0] < prov["mjd_range"][1]
    # The centre point search is run live too and matches the offline replay.
    check = prov["point_check"]
    assert check["rows_live"] == check["rows_replayed"] == 14 and not check["only_live"] and not check["only_replayed"]
    sia = [dict(c["params"])["POS"] for c in fake.calls]
    assert sia[0] == "CIRCLE 269.44623000 4.76870000 0.055" and len(sia) == 8
    assert all(pos.endswith(" 0.055") for pos in sia[:7])
    assert sia[7] == "CIRCLE 269.44623000 4.76870000 0.000277777778"
    assert [q["pos"] for q in prov["queries"]] == sia[:7]
    key = "dr1/level2/2025W33_2C/l2b-v27-2026-228/6/level2_2025W33_2C_0321_1D6_spx_l2b-v27-2026-228.fits"
    _, t_min, t_max, ci, footprint = next(r for r in doc["rows"] if r[0] == key)
    assert (t_min, t_max, doc["collections"][ci]) == (60902.864715, 60902.866047, "spherex_dr1")
    assert footprint == [266.698183, 5.47247, 270.177338, 5.149486, 269.997314, 1.660075, 266.501171, 1.990435]

    # Written with one row per line, and read back to the same FrameRefs as the SIA answer.
    path = irsa.write_snapshot(doc, tmp_path / "barnards-star.json")
    text = path.read_text(encoding="utf-8")
    assert text.count("\n    [") == 14 and "\r" not in text
    snap = irsa.load_snapshot(path)
    sia_rows, _ = irsa.parse_sia_votable(SIA_XML)
    assert [s.row for s in snap.rows] == irsa.dedupe_rows(sia_rows)[0]
    assert snap.queried_utc == prov["queried_utc"] and snap.service == "sia"


def test_fetch_snapshot_refuses_truncated_answers_and_dead_irsa(monkeypatch):
    install(monkeypatch, sia=[ok(_overflow_votable())])
    with pytest.raises(irsa.SearchError, match="truncated"):
        irsa.fetch_snapshot("barnards-star", RA, DEC, rounds=1, pause_s=0)
    fake = install(monkeypatch, sia=[FakeResponse(502)])
    with pytest.raises(irsa.SearchError, match="after 2 rounds") as exc:
        irsa.fetch_snapshot("barnards-star", RA, DEC, rounds=2, pause_s=0)
    assert exc.value.is_outage
    assert fake.count(settings.IRSA_SIA) == 2 * settings.SEARCH_ATTEMPTS
    with pytest.raises(ValueError):
        irsa.fetch_snapshot("../evil", RA, DEC)


def test_snapshot_point_check_failure_is_recorded(monkeypatch):
    # The radius query answers, the point query does not: the snapshot is still valid, the check says why.
    install(monkeypatch, sia=[ok(SIA_XML), FakeResponse(502)])
    doc = irsa.fetch_snapshot("barnards-star", RA, DEC, rounds=1, pause_s=0, tile_radius_deg=10.0)
    assert len(doc["rows"]) == 14
    assert "error" in doc["provenance"]["point_check"] and doc["provenance"]["point_check"]["rows_replayed"] == 14


def test_snapshot_never_used_while_irsa_answers(monkeypatch, snapdir):
    fake = install(monkeypatch, sia=[ok(SIA_XML)])
    rep = irsa.search_frames_report(RA, DEC)
    assert rep.service == "sia" and not rep.stale and not rep.from_cache and rep.warnings == []
    assert fake.count(settings.IRSA_TAP_SYNC) == 0
    # TAP answering after SIA failed is a live answer too.
    install(monkeypatch, sia=[FakeResponse(502)], tap=[ok(TAP_CSV)])
    rep = irsa.search_frames_report(RA, DEC, use_cache=False)
    assert rep.service == "tap" and not rep.stale


def test_snapshot_answers_when_sia_and_tap_fail(monkeypatch, snapdir, caplog):
    install(monkeypatch, **IRSA_DOWN)
    with caplog.at_level("WARNING", logger="errante.data.irsa"):
        rep = irsa.search_frames_report(RA, DEC)
    assert rep.service == "snapshot" and rep.stale and rep.from_cache and not rep.overflow
    assert len(rep.result.frames) == 14
    sia_rows, _ = irsa.parse_sia_votable(SIA_XML)
    assert rep.result.frames == [r.ref for r in irsa.dedupe_rows(sia_rows)[0]]
    assert rep.errors and "IRSA frame search failed" in rep.errors[0]
    (note,) = rep.warnings
    assert "committed search snapshot 'barnards-star'" in note and "SIA answer of 20" in note
    assert "frames published after that date are missing" in note
    assert "committed search snapshot" in caplog.text
    assert not (settings.CACHE_DIR / "queries").exists()  # a snapshot answer is never cached
    # build.py and the backend call search_frames (SearchResult only): same frames.
    assert irsa.search_frames(RA, DEC) == rep.result


def test_snapshot_applies_detector_mjd_and_collection_filters(monkeypatch, snapdir):
    install(monkeypatch, sia=[ok(SIA_XML)])
    every = irsa.search_frames(RA, DEC, use_cache=False)
    install(monkeypatch, **IRSA_DOWN)
    rep = irsa.search_frames_report(RA, DEC, detectors=[3, 6], mjd_min=61100, mjd_max=61300)
    expected = [f for f in every.frames if f.detector in (3, 6) and 61100 <= f.mjd <= 61300]
    assert rep.service == "snapshot" and rep.result.frames == expected and len(expected) == 4
    # Overlap semantics like SIA TIME: a bound inside an exposure keeps it.
    first = every.frames[0]
    rep = irsa.search_frames_report(RA, DEC, mjd_min=first.mjd, mjd_max=first.mjd)
    assert {(f.obs_id, f.detector) for f in rep.result.frames} == {
        (f.obs_id, f.detector) for f in every.frames if f.obs_id == first.obs_id
    }
    # A subset of the snapshotted collections is served; a collection it lacks is not.
    rep = irsa.search_frames_report(RA, DEC, collections=["spherex_qr3"])
    assert (
        rep.service == "snapshot" and {f.release for f in rep.result.frames} == {"qr3"} and len(rep.result.frames) == 4
    )
    with pytest.raises(irsa.SearchError):
        irsa.search_frames(RA, DEC, collections=["spherex_dr1", "spherex_dr1_deep"])


def test_snapshot_not_used_far_away_or_beyond_its_disk(monkeypatch, snapdir):
    install(monkeypatch, sia=[requests.ReadTimeout("sia slow")], tap=[FakeResponse(502)])
    with pytest.raises(irsa.SearchError) as exc:
        irsa.search_frames(RA + 1.0, DEC)  # 1 deg away: no snapshot covers it
    assert isinstance(exc.value.__cause__, requests.Timeout) and exc.value.is_outage  # the original error
    # Inside the 0.1 deg disk: served. A search circle that pokes out of it: not served.
    assert irsa.search_frames_report(RA, DEC + 0.09).service == "snapshot"
    assert irsa.search_frames_report(RA, DEC + 0.05, radius_deg=0.04).service == "snapshot"
    with pytest.raises(irsa.SearchError):
        irsa.search_frames(RA, DEC + 0.05, radius_deg=0.06)
    with pytest.raises(irsa.SearchError):
        irsa.search_frames(RA, DEC + 0.11)


def test_snapshot_replay_follows_the_footprints(monkeypatch, tmp_path):
    # A wide (2 deg) snapshot of the 14 fixture frames, queried 1 deg away: only frames covering the point.
    directory = tmp_path / "wide"
    _make_snapshot(monkeypatch, directory, radius_deg=2.0)
    monkeypatch.setattr(irsa, "SNAPSHOT_DIR", directory)
    snap = irsa.load_snapshot(irsa.snapshot_path("barnards-star", directory))
    install(monkeypatch, **IRSA_DOWN)
    seen = set()
    for dra, ddec in [(1.0, 0.0), (-1.0, 0.0), (0.0, 1.0), (0.0, -1.0), (0.7, 0.7), (-1.2, -1.2)]:
        ra, dec = RA + dra, DEC + ddec
        rep = irsa.search_frames_report(ra, dec)
        expected = {(s.row.ref.obs_id, s.row.ref.detector) for s in snap.rows if _inside_convex(s.footprint, ra, dec)}
        assert {(f.obs_id, f.detector) for f in rep.result.frames} == expected
        seen.add(len(expected))
    assert min(seen) < 14 and max(seen) > 0  # the footprints really select frames


def _expired_cached_search(monkeypatch) -> None:
    """A real (fixture) SIA answer for (RA, DEC) in the search cache, 3 days old (TTL: 1 day)."""
    install(monkeypatch, sia=[ok(SIA_XML)])
    irsa.search_frames(RA, DEC, detectors=None)
    (path,) = (settings.CACHE_DIR / "queries").glob("search_*.json")
    doc = json.loads(path.read_text(encoding="utf-8"))
    doc["created"] = time.time() - 3 * 86400
    path.write_text(json.dumps(doc), encoding="utf-8")


def test_stale_cache_beats_snapshot_and_no_cache_means_no_snapshot(monkeypatch, snapdir):
    _expired_cached_search(monkeypatch)
    install(monkeypatch, **IRSA_DOWN)
    rep = irsa.search_frames_report(RA, DEC)
    assert rep.stale and rep.service == "sia" and rep.warnings == []  # the expired cache, not the snapshot
    # use_cache=False (CLI --no-cache, live checks): live or nothing, unless the snapshot is asked for.
    with pytest.raises(irsa.SearchError):
        irsa.search_frames_report(RA, DEC, use_cache=False)
    assert irsa.search_frames_report(RA, DEC, use_cache=False, use_snapshot=True).service == "snapshot"
    with pytest.raises(irsa.SearchError):
        irsa.search_frames_report(RA, DEC, use_snapshot=False, mjd_min=1)  # no cache for this key either


# The shipped settings.py defaults (the autouse fixture makes retries instant) and the backend's default
# ERRANTE_API_TIMEOUT_S (errante_api.settings.Settings.live_timeout_s): the backend answers HTTP 504 after it.
SHIPPED_BUDGET = {
    "SEARCH_ATTEMPTS": 4,
    "SEARCH_BACKOFF_S": 0.5,
    "SIA_TIMEOUT_S": 45.0,
    "TAP_TIMEOUT_S": 60.0,
    "SEARCH_DEADLINE_S": 60.0,
    "SEARCH_FALLBACK_DEADLINE_S": 20.0,
}
API_TIMEOUT_S = 30.0


def _outage_http(clock: FakeClock, calls: list, sia, tap):
    """IRSA down: each service hangs until its read timeout ('hang') or answers that HTTP status at once."""

    def fake_http(method, url, *, params=None, data=None, timeout):
        calls.append((url, timeout))
        mode = sia if url == settings.IRSA_SIA else tap
        if mode == "hang":
            clock.now += timeout
            raise requests.ReadTimeout(f"{url} hung {timeout} s")
        return FakeResponse(mode)

    return fake_http


def _outage(monkeypatch, sia, tap) -> tuple[FakeClock, list]:
    for name, value in SHIPPED_BUDGET.items():
        monkeypatch.setattr(settings, name, value)
    clock, calls = FakeClock(), []
    monkeypatch.setattr(irsa, "time", clock)
    monkeypatch.setattr(irsa, "_http", _outage_http(clock, calls, sia, tap))
    return clock, calls


# 2026-11-14: SIA answered bursts of fast 502s or hung; TAP hung on every spherex query for hours.
@pytest.mark.parametrize(("sia", "tap"), [(502, "hang"), ("hang", "hang"), ("hang", 502)])
@pytest.mark.parametrize("fallback", ["snapshot", "expired cache"])
def test_fallback_answers_before_the_api_gives_up(monkeypatch, snapdir, sia, tap, fallback):
    # Review 2026-11-14: SIA 502 + TAP hang used the whole 60 s SEARCH_DEADLINE_S before the snapshot
    # answered, so /api/search (30 s) returned 504. With a fallback in hand the search budget is capped.
    if fallback == "expired cache":
        monkeypatch.setattr(irsa, "SNAPSHOT_DIR", None)
        _expired_cached_search(monkeypatch)
    clock, calls = _outage(monkeypatch, sia, tap)
    t0 = clock.now
    rep = irsa.search_frames_report(RA, DEC)
    assert rep.stale and rep.service == ("snapshot" if fallback == "snapshot" else "sia")
    assert len(rep.result.frames) == 14
    assert clock.now - t0 <= settings.SEARCH_FALLBACK_DEADLINE_S < API_TIMEOUT_S - 5
    assert {url for url, _ in calls} == {settings.IRSA_SIA, settings.IRSA_TAP_SYNC}  # IRSA still got its chance


def test_fallback_budget_applies_only_with_a_fallback(monkeypatch, snapdir):
    clock, _ = _outage(monkeypatch, 502, "hang")
    # Far from every snapshot and nothing cached: IRSA keeps the whole SEARCH_DEADLINE_S.
    t0 = clock.now
    with pytest.raises(irsa.SearchError):
        irsa.search_frames(RA + 1.0, DEC)
    assert 50.0 < clock.now - t0 <= 60.0
    # use_cache=False (live checks) never falls back, so it is not capped either.
    t0 = clock.now
    with pytest.raises(irsa.SearchError):
        irsa.search_frames(RA, DEC, use_cache=False)
    assert 50.0 < clock.now - t0 <= 60.0
    # SEARCH_FALLBACK_DEADLINE_S = 0 switches the cap off; a smaller SEARCH_DEADLINE_S wins over it.
    monkeypatch.setattr(settings, "SEARCH_FALLBACK_DEADLINE_S", 0.0)
    t0 = clock.now
    assert irsa.search_frames_report(RA, DEC).service == "snapshot"
    assert 50.0 < clock.now - t0 <= 60.0
    monkeypatch.setattr(settings, "SEARCH_FALLBACK_DEADLINE_S", 20.0)
    monkeypatch.setattr(settings, "SEARCH_DEADLINE_S", 12.0)
    t0 = clock.now
    assert irsa.search_frames_report(RA, DEC).service == "snapshot"
    assert clock.now - t0 <= 12.0


def test_shipped_search_budget_fits_the_backend_timeout():
    import dataclasses
    import os

    env = {"SIA_TIMEOUT_S": "ERRANTE_SIA_TIMEOUT_S", "TAP_TIMEOUT_S": "ERRANTE_TAP_TIMEOUT_S"}
    env |= {"SEARCH_DEADLINE_S": "ERRANTE_SEARCH_DEADLINE_S"}
    env |= {"SEARCH_FALLBACK_DEADLINE_S": "ERRANTE_SEARCH_FALLBACK_DEADLINE_S"}
    for name, var in env.items():  # SHIPPED_BUDGET mirrors settings.py (unless this shell overrides it)
        if var not in os.environ:
            assert getattr(settings, name) == SHIPPED_BUDGET[name], name
    api = pytest.importorskip("errante_api.settings")
    (field,) = [f for f in dataclasses.fields(api.Settings) if f.name == "live_timeout_s"]
    assert field.default == API_TIMEOUT_S  # if WS4 lowers it, lower SEARCH_FALLBACK_DEADLINE_S too


def _with_qr3_copy(xml: bytes) -> bytes:
    """The SIA fixture plus a qr3 copy of its first (dr1) row: one obs_id + detector in two collections."""
    start = xml.index(b"<TR>")
    end = xml.index(b"</TR>", start) + len(b"</TR>")
    row = xml[start:end]
    assert row.count(b"dr1/level2/") == 2 and row.count(b"spherex_dr1") == 2  # obs_collection, publisher DID
    copy = row.replace(b"dr1/level2/", b"qr3/level2/").replace(b"spherex_dr1", b"spherex_qr3")
    return xml[:end] + b"\n" + copy + xml[end:]


def test_snapshot_keeps_every_collection_row(monkeypatch, tmp_path):
    # Review 2026-11-14: the snapshot was deduplicated over dr1+qr3 (DR1 wins) BEFORE the replay filtered by
    # collection, so a qr3-only search during an outage lost frames that live SIA on qr3 returns.
    xml = _with_qr3_copy(SIA_XML)
    install(monkeypatch, sia=[ok(xml)])
    live_both = irsa.search_frames_report(RA, DEC, use_cache=False)
    assert live_both.n_duplicates == 1 and len(live_both.result.frames) == 14
    doc = irsa.fetch_snapshot("barnards-star", RA, DEC, rounds=1, pause_s=0, tile_radius_deg=10.0)
    assert len(doc["rows"]) == doc["provenance"]["rows"] == 15 and doc["provenance"]["duplicate_rows"] == 1
    check = doc["provenance"]["point_check"]
    assert check["rows_live"] == check["rows_replayed"] == 14 and not check["only_live"]
    directory = tmp_path / "dup"
    irsa.write_snapshot(doc, irsa.snapshot_path("barnards-star", directory))
    monkeypatch.setattr(irsa, "SNAPSHOT_DIR", directory)
    install(monkeypatch, **IRSA_DOWN)
    rep = irsa.search_frames_report(RA, DEC)
    assert rep.service == "snapshot" and rep.result.frames == live_both.result.frames and rep.n_duplicates == 1
    rep = irsa.search_frames_report(RA, DEC, collections=["spherex_qr3"])
    assert rep.service == "snapshot" and len(rep.result.frames) == 5 and rep.n_duplicates == 0
    (dup,) = [f for f in rep.result.frames if (f.obs_id, f.detector) == ("2025W33_2C_0321_1", 6)]
    assert dup.release == "qr3" and dup.s3_key.startswith("qr3/level2/")


def test_missing_snapshot_dir_is_logged_once(monkeypatch, tmp_path, caplog):
    # A deploy that does not ship data/index/search (or a non-editable install) silently lost the fallback.
    missing = tmp_path / "not-shipped"
    monkeypatch.setattr(irsa, "SNAPSHOT_DIR", missing)
    install(monkeypatch, **IRSA_DOWN)
    with caplog.at_level("WARNING", logger="errante.data.irsa"):
        for _ in range(3):
            with pytest.raises(irsa.SearchError):
                irsa.search_frames(RA, DEC)
    assert caplog.text.count(f"Search snapshot directory {missing} does not exist") == 1
    assert "ERRANTE_SEARCH_SNAPSHOTS" in caplog.text
    caplog.clear()
    monkeypatch.setattr(irsa, "SNAPSHOT_DIR", None)  # switched off on purpose: nothing to report
    with caplog.at_level("WARNING", logger="errante.data.irsa"), pytest.raises(irsa.SearchError):
        irsa.search_frames(RA, DEC)
    assert "Search snapshot directory" not in caplog.text


def test_cli_search_labels_a_snapshot_answer(monkeypatch, snapdir, capsys):
    install(monkeypatch, **IRSA_DOWN)
    assert cli_main(["search", "--ra", str(RA), "--dec", str(DEC)]) == 0
    err = capsys.readouterr().err
    assert "14 frames via committed SNAPSHOT (IRSA unavailable)" in err and "EXPIRED" not in err
    assert "WARNING: IRSA unavailable: frames come from the committed search snapshot 'barnards-star'" in err


def test_broken_snapshot_files_are_ignored(monkeypatch, snapdir, caplog):
    (snapdir / "corrupt.json").write_text("{not json", encoding="utf-8")
    good = json.loads((snapdir / "barnards-star.json").read_text(encoding="utf-8"))
    (snapdir / "future.json").write_text(json.dumps(good | {"format": 99}), encoding="utf-8")
    (snapdir / "notes.json").write_text(json.dumps({"hello": "world"}), encoding="utf-8")
    bad_row = good | {"rows": [["not/a/level2/key.fits", 1.0, 2.0, 0, [0, 0, 1, 0, 1, 1]]]}
    (snapdir / "bad-row.json").write_text(json.dumps(bad_row), encoding="utf-8")
    install(monkeypatch, **IRSA_DOWN)
    with caplog.at_level("WARNING", logger="errante.data.irsa"):
        rep = irsa.search_frames_report(RA, DEC)
    assert rep.service == "snapshot" and len(rep.result.frames) == 14
    assert [s.path.name for s in irsa.list_snapshots(snapdir)] == ["barnards-star.json"]
    for name in ("corrupt.json", "future.json", "notes.json", "bad-row.json"):
        assert name in caplog.text


def test_snapshot_dir_from_environment(monkeypatch, tmp_path):
    monkeypatch.setenv("ERRANTE_SEARCH_SNAPSHOTS", "0")
    assert irsa._snapshot_dir_from_env() is None
    monkeypatch.setenv("ERRANTE_SEARCH_SNAPSHOTS", str(tmp_path))
    assert irsa._snapshot_dir_from_env() == tmp_path.resolve()
    monkeypatch.delenv("ERRANTE_SEARCH_SNAPSHOTS")
    assert irsa._snapshot_dir_from_env() == irsa.DEFAULT_SNAPSHOT_DIR == settings.REPO_ROOT / "data/index/search"


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("POLYGON ICRS 1 2 3 4 5 6 1 2", (1.0, 2.0, 3.0, 4.0, 5.0, 6.0)),
        ("polygon 1 2 3 4 5 6", (1.0, 2.0, 3.0, 4.0, 5.0, 6.0)),
        ("POLYGON ICRS 1.23456789 2 3 4 5 6 7 8", (1.234568, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0)),
        ("POLYGON ICRS 1 2 3 4", None),
        ("POLYGON ICRS 1 2 3 4 5", None),
        ("CIRCLE ICRS 1 2 3", None),
        ("POLYGON ICRS 1 2 3 4 5 6 UNION", None),
        ("", None),
        (None, None),
    ],
)
def test_parse_s_region(text, expected):
    assert irsa.parse_s_region(text) == expected


@pytest.mark.parametrize(("ra", "dec"), [(RA, DEC), (0.01, -56.8), (248.16723, 66.75502), (123.0, 89.95)])
def test_snapshot_tiles_cover_the_disk(ra, dec):
    import random

    tiles = irsa.snapshot_tiles(ra, dec, 0.1)
    assert len(tiles) == 7 and tiles[0] == (round(ra, 8), round(dec, 8))
    assert all(irsa.angular_separation_deg(ra, dec, t_ra, t_dec) < 0.1 for t_ra, t_dec in tiles)
    rng = random.Random(42)
    for _ in range(2000):  # random points of the disk (gnomonic offsets), each within a tile radius of a tile
        r, a = 0.1 * math.sqrt(rng.random()), rng.uniform(0, 2 * math.pi)
        p_ra, p_dec = _offset(ra, dec, r, a)
        assert min(irsa.angular_separation_deg(p_ra, p_dec, t_ra, t_dec) for t_ra, t_dec in tiles) <= 0.055 + 1e-9
    assert irsa.snapshot_tiles(ra, dec, 0.05) == [(ra, dec)]
    assert len(irsa.snapshot_tiles(ra, dec, 0.2)) == 31  # lattice rings at 0, 0.095, 0.165, 0.19, 0.252 deg


def _offset(ra: float, dec: float, dist_deg: float, bearing: float) -> tuple[float, float]:
    d0, delta = math.radians(dec), math.radians(dist_deg)
    d = math.asin(math.sin(d0) * math.cos(delta) + math.cos(d0) * math.sin(delta) * math.cos(bearing))
    a = math.radians(ra) + math.atan2(
        math.sin(bearing) * math.sin(delta) * math.cos(d0), math.cos(delta) - math.sin(d0) * math.sin(d)
    )
    return math.degrees(a) % 360.0, math.degrees(d)


def test_footprint_geometry():
    square = (359.5, -0.5, 0.5, -0.5, 0.5, 0.5, 359.5, 0.5)  # 1 deg box across RA = 0
    assert irsa.footprint_hits(square, 0.0, 0.0)
    assert irsa.footprint_hits(square, 359.6, 0.4) and irsa.footprint_hits(square, 0.4, -0.4)
    assert not irsa.footprint_hits(square, 0.6, 0.0) and not irsa.footprint_hits(square, 180.0, 0.0)
    # A circle that reaches an edge touches the polygon (edge at RA 0.5, 0.1 deg away).
    assert not irsa.footprint_hits(square, 0.6, 0.0, radius_deg=0.09)
    assert irsa.footprint_hits(square, 0.6, 0.0, radius_deg=0.11)
    # Edges are great circles: near the pole they bulge poleward of the straight RA/Dec line.
    polar = (0.0, 80.0, 90.0, 80.0, 180.0, 80.0, 270.0, 80.0)  # contains the pole
    assert irsa.footprint_hits(polar, 123.0, 89.9) and irsa.footprint_hits(polar, 45.0, 85.0)
    north_edge = (10.0, 60.0, 50.0, 60.0, 50.0, 55.0, 10.0, 55.0)
    assert irsa.footprint_hits(north_edge, 30.0, 61.0)  # above dec 60 at mid RA, still inside
    assert not irsa.footprint_hits(north_edge, 30.0, 62.5)
    assert irsa.angular_separation_deg(359.9, 0.0, 0.1, 0.0) == pytest.approx(0.2)
    assert irsa.angular_separation_deg(10.0, 89.0, 190.0, 89.0) == pytest.approx(2.0)


@pytest.mark.parametrize("field_id", OFFICIAL)
def test_committed_snapshot_files(field_id):
    from errante.build import load_field_configs

    cfg = load_field_configs()[field_id]
    path = irsa.snapshot_path(field_id, irsa.DEFAULT_SNAPSHOT_DIR)
    assert path.exists(), f"missing {path}: run `errante snapshot-search {field_id}`"
    assert path.stat().st_size < SNAPSHOT_MAX_BYTES
    doc = json.loads(path.read_text(encoding="utf-8"))
    snap = irsa.load_snapshot(path)
    prov = doc["provenance"]
    assert snap.field_id == field_id and snap.name == cfg.name
    assert snap.collections == ("spherex_dr1", "spherex_qr3")  # wide survey only (no deep fields)
    assert snap.service == "sia" and prov["url"] == settings.IRSA_SIA
    assert prov["queried_utc"].startswith("2026-") and prov["queried_utc"].endswith("Z")
    assert prov["rows"] == len(doc["rows"]) == len(snap.rows) and prov["rows_without_footprint"] == 0
    assert sum(prov["rows_by_collection"].values()) == sum(prov["rows_by_detector"].values()) == len(snap.rows)
    # One row per S3 file; an (obs_id, detector) in two collections is deduplicated by the replay. The files
    # committed on 2026-11-14 were deduplicated when written ('duplicates_removed': 0 in all five, same rows).
    assert len({s.row.ref.s3_key for s in snap.rows}) == len(snap.rows)
    keys = [(s.row.ref.obs_id, s.row.ref.detector) for s in snap.rows]
    assert len(keys) - len(set(keys)) == prov.get("duplicate_rows", prov.get("duplicates_removed"))
    assert all(s.row.ref.irsa_uri == f"ibe/data/spherex/{s.row.ref.s3_key}" for s in snap.rows)
    assert all(s.t_min <= s.row.ref.mjd <= s.t_max for s in snap.rows)
    # The field centre in fields.toml (what build.py searches) is inside the disk, with margin for clicks.
    assert snap.covers(cfg.ra, cfg.dec, irsa.MIN_RADIUS_DEG, ("spherex_dr1", "spherex_qr3"))
    assert irsa.angular_separation_deg(snap.ra, snap.dec, cfg.ra, cfg.dec) < snap.radius_deg / 2
    # The replay at the centre equals the live point search recorded at generation time.
    check = prov["point_check"]
    replay = snap.frames(snap.ra, snap.dec, irsa.MIN_RADIUS_DEG)
    assert "error" not in check and check["rows_live"] == check["rows_replayed"] == len(replay) > 200
    assert check["only_live"] == [] and check["only_replayed"] == []


def test_committed_snapshots_keep_build_and_backend_working_offline(monkeypatch):
    from errante.build import load_field_configs

    monkeypatch.setattr(irsa, "SNAPSHOT_DIR", irsa.DEFAULT_SNAPSHOT_DIR)
    install(monkeypatch, **IRSA_DOWN)
    cfgs = load_field_configs()
    for fid in OFFICIAL:
        cfg = cfgs[fid]
        rep = irsa.search_frames_report(
            cfg.ra, cfg.dec, detectors=cfg.detectors, mjd_min=cfg.mjd_min, mjd_max=cfg.mjd_max
        )
        assert rep.service == "snapshot" and rep.stale and fid in rep.warnings[0]
        assert len(rep.result.frames) > 200 and {f.detector for f in rep.result.frames} == {1, 2, 3, 4, 5, 6}
    # A deep-field search is not covered by the wide-survey snapshots.
    with pytest.raises(irsa.SearchError):
        irsa.search_frames(
            cfgs["r-draconis"].ra, cfgs["r-draconis"].dec, collections=irsa.settings.IRSA_DEEP_COLLECTIONS
        )


def test_cli_snapshot_search(monkeypatch, tmp_path, capsys):
    install(monkeypatch, sia=[ok(SIA_XML)])
    out = tmp_path / "snaps"
    argv = ["snapshot-search", "barnards-star", "--out", str(out), "--rounds", "1", "--pause", "0"]
    assert cli_main(argv) == 0
    captured = capsys.readouterr()
    assert "barnards-star: 14 frames within 0.1 deg (spherex_dr1, spherex_qr3) via SIA" in captured.out
    assert "point check OK" in captured.out
    assert irsa.load_snapshot(out / "barnards-star.json").field_id == "barnards-star"

    assert cli_main(["snapshot-search", "--out", str(out)]) == 2  # neither an id nor --all
    assert cli_main(["snapshot-search", "barnards-star", "--all", "--out", str(out)]) == 2
    assert cli_main(["snapshot-search", "no-such-field", "--out", str(out)]) == 2
    capsys.readouterr()

    # --all walks the five official targets; IRSA down -> nothing written, exit 1.
    fake = install(monkeypatch, sia=[FakeResponse(502)])
    assert cli_main(["snapshot-search", "--all", "--out", str(tmp_path / "none"), "--rounds", "1", "--pause", "0"]) == 1
    err = capsys.readouterr().err
    assert all(f"{fid}: snapshot NOT written" in err for fid in OFFICIAL)
    assert not (tmp_path / "none").exists()
    assert fake.count(settings.IRSA_SIA) == 5 * settings.SEARCH_ATTEMPTS


@pytest.mark.parametrize("point_answer", ["502", "empty"])
def test_cli_snapshot_search_exits_1_when_the_point_check_fails(monkeypatch, tmp_path, capsys, point_answer):
    # Review 2026-11-14: the file was written with exit 0 although test_committed_snapshot_files rejects it.
    point = FakeResponse(502) if point_answer == "502" else ok(_empty_votable())
    install(monkeypatch, sia=[ok(SIA_XML)] * 7 + [point])  # 7 tiles answer, the centre point search does not
    out = tmp_path / "snaps"
    argv = ["snapshot-search", "barnards-star", "--out", str(out), "--rounds", "1", "--pause", "0"]
    assert cli_main(argv) == 1
    err = capsys.readouterr().err
    assert ("point check NOT run" if point_answer == "502" else "WARNING point check: live 0 vs replayed 14") in err
    assert "barnards-star.json fails CI (test_committed_snapshot_files)" in err
    assert irsa.load_snapshot(out / "barnards-star.json").field_id == "barnards-star"  # written, for inspection


# --------------------------------------------------------------------------- retries on a flaky IRSA (2026-11-15)
# On the VM every map-click Time build failed in ~30 s: "SIA search failed (ReadTimeout ... read timeout=12.45);
# falling back to TAP", then "tap: ReadTimeout ... / HTTPError: HTTP 502". From a laptop SIA and TAP answered
# intermittently (some requests a fast 502, others fine). One try per service is not enough for that.


class FlakyIRSA:
    """Scripted SIA/TAP on a FakeClock. Each item: an HTTP status (answers at once; 200 = the fixture), 'hang'
    (uses the whole timeout, then ReadTimeout), or a float (answers 200 after that many seconds, a timeout if
    given less). The last item of a queue repeats. Records (url, start, timeout) and every sleep."""

    def __init__(self, clock: FakeClock, sia, tap):
        self.clock = clock
        self.queues = {settings.IRSA_SIA: list(sia), settings.IRSA_TAP_SYNC: list(tap)}
        self.calls: list[tuple[str, float, float]] = []

    def __call__(self, method, url, *, params=None, data=None, timeout):
        self.calls.append((url, self.clock.now, timeout))
        queue = self.queues[url]
        item = queue.pop(0) if len(queue) > 1 else queue[0]
        body = SIA_XML if url == settings.IRSA_SIA else TAP_CSV
        if isinstance(item, FakeResponse):
            return item
        if item == "hang" or (isinstance(item, float) and item > timeout):
            self.clock.now += timeout
            raise requests.ReadTimeout(f"{url} read timeout={timeout:.2f}")
        if isinstance(item, float):
            self.clock.now += item
            return ok(body)
        return ok(body) if item == 200 else FakeResponse(item)

    def services(self) -> list[str]:
        return ["sia" if url == settings.IRSA_SIA else "tap" for url, _, _ in self.calls]


def _flaky(monkeypatch, sia, tap, *, budget: float = 60.0, attempts: int = 4, backoff: float = 0.5):
    clock = FakeClock()
    sleeps: list[float] = []

    def sleep(s: float) -> None:
        sleeps.append(s)
        clock.now += s

    clock.sleep = sleep
    monkeypatch.setattr(irsa, "time", clock)
    fake = FlakyIRSA(clock, sia, tap)
    monkeypatch.setattr(irsa, "_http", fake)
    for name, value in {
        "SEARCH_ATTEMPTS": attempts,
        "SEARCH_BACKOFF_S": backoff,
        "SIA_TIMEOUT_S": 30.0,
        "TAP_TIMEOUT_S": 60.0,
        "SEARCH_DEADLINE_S": budget,
    }.items():
        monkeypatch.setattr(settings, name, value)
    return clock, fake, sleeps


def test_vm_failure_2026_11_15_now_answers(monkeypatch):
    """The VM's 25 s budget (ERRANTE_SEARCH_DEADLINE_S in the image): SIA hung 12.45 s, TAP answered 502. Before, that
    was the end (SearchError); now SIA gets another try in what is left and answers."""
    clock, fake, _ = _flaky(monkeypatch, sia=["hang", 200], tap=[502], budget=25.0)
    t0 = clock.now
    rep = irsa.search_frames_report(RA, DEC, use_cache=False)
    assert rep.service == "sia" and len(rep.result.frames) == 14
    assert fake.services() == ["sia", "tap", "sia"]
    assert fake.calls[0][2] == pytest.approx(12.5)  # half of the 25 s budget, as on the VM (12.45)
    assert [e.split(":")[0] for e in rep.retries] == ["sia 1/4", "tap 1/4"]
    assert rep.errors == []
    assert clock.now - t0 <= 25.0


def test_retry_that_answers_is_not_a_fallback(monkeypatch):
    """SIA 502 then SIA 200 (IRSA, 2026-11-15): the history goes to ``retries``; ``errors`` stays empty, so
    point_series' search["errors"] is empty and lightcurve_build does not mark the light curve partial."""
    clock, fake, _ = _flaky(monkeypatch, sia=[502, 200], tap=[])
    rep = irsa.search_frames_report(RA, DEC, use_cache=False)
    assert rep.service == "sia" and fake.services() == ["sia", "sia"]
    assert rep.errors == [] and not rep.stale
    assert len(rep.retries) == 1 and rep.retries[0].startswith("sia 1/4: HTTPError: HTTP 502")


def test_502_then_success_on_both_services(monkeypatch):
    clock, fake, _ = _flaky(monkeypatch, sia=[502, 502, 502, 200], tap=[502, 200])
    rep = irsa.search_frames_report(RA, DEC, use_cache=False)
    assert rep.service == "tap" and rep.result.frames  # SIA, SIA, TAP (502), SIA (502), TAP answers
    # TAP answered: a real fallback, so ``errors`` keeps why (SIA's failures); ``retries`` keeps everything.
    assert [e.split(":")[0] for e in rep.errors] == ["sia 1/4", "sia 2/4", "sia 3/4"]
    assert [e.split(":")[0] for e in rep.retries] == ["sia 1/4", "sia 2/4", "tap 1/4", "sia 3/4"]
    assert fake.services() == ["sia", "sia", "tap", "sia", "tap"]


def test_timeout_then_success(monkeypatch):
    clock, fake, sleeps = _flaky(monkeypatch, sia=["hang", 3.0], tap=["hang"], budget=120.0)
    t0 = clock.now
    rep = irsa.search_frames_report(RA, DEC, use_cache=False)
    assert rep.service == "sia" and rep.result.frames
    assert fake.services() == ["sia", "tap", "sia"]  # a timeout switches service at once
    assert sleeps == []  # no backoff after a timeout: the attempt already waited
    assert [t for _, _, t in fake.calls] == [30.0, 60.0, 15.0]  # SIA 30 s, TAP 60 s, SIA half of the 30 s left
    assert clock.now - t0 == pytest.approx(93.0)


def test_all_attempts_fail_reports_the_history(monkeypatch, caplog):
    clock, fake, sleeps = _flaky(monkeypatch, sia=[502], tap=[503], budget=120.0)
    with caplog.at_level("WARNING", logger="errante.data.irsa"), pytest.raises(irsa.SearchError) as exc:
        irsa.search_frames_report(RA, DEC, use_cache=False)
    order = ["sia", "sia", "tap", "sia", "tap", "sia", "tap", "tap"]
    assert fake.services() == order  # SEARCH_ATTEMPTS (4) per service, alternated after SIA's quick second try
    err = exc.value
    assert len(err.failures) == 8 and err.is_outage
    assert isinstance(err.__cause__, requests.HTTPError) and err.__cause__.response.status_code == 503
    msg = str(err)
    assert msg.startswith("IRSA frame search failed after 8 attempt(s) in ")
    for service, n in (("sia", 1), ("sia", 4), ("tap", 1), ("tap", 4)):
        assert f"{service} {n}/4: HTTPError: HTTP" in msg
    # Backoff: 0.5 s x 1, 2, 4, 8 capped at 4 s, plus up to 25 % jitter.
    base = [0.5, 1.0, 2.0, 4.0, 4.0, 4.0, 4.0]
    assert len(sleeps) == 7 and all(b <= s <= 1.25 * b for s, b in zip(sleeps, base, strict=True))
    logged = [r.getMessage() for r in caplog.records]
    assert any(
        m.startswith("SIA attempt 2/4 failed after 0.0 s: HTTPError: HTTP 502") and "TAP (1/4)" in m for m in logged
    )
    assert any("TAP attempt 4/4 failed" in m and "giving up (no attempts left)" in m for m in logged)


@pytest.mark.parametrize("budget", [25.0, 60.0, 120.0])
@pytest.mark.parametrize(
    ("sia", "tap"),
    [
        (["hang"], ["hang"]),
        ([502], ["hang"]),
        (["hang"], [502]),
        ([502, "hang", 502, 40.0], [503, 70.0]),
        ([28.0], [55.0]),
    ],
)
def test_no_attempt_outlives_the_deadline(monkeypatch, budget, sia, tap):
    clock, fake, _ = _flaky(monkeypatch, sia=sia, tap=tap, budget=budget)
    t0 = clock.now
    deadline = t0 + budget
    try:
        rep = irsa.search_frames_report(RA, DEC, use_cache=False)
    except irsa.SearchError as e:
        assert e.is_outage and {"sia", "tap"} <= set(fake.services())  # both services got a turn
    else:  # a slow answer that fits its attempt (SIA 28 s < 30 s)
        assert rep.result.frames and rep.service in {"sia", "tap"}
    assert fake.calls and clock.now - t0 <= budget + 1e-9
    for _, start, timeout in fake.calls:
        assert start <= deadline - irsa._MIN_ATTEMPT_S + 1e-9  # no attempt starts in the last 2 s
        assert 0 < timeout <= deadline - start + 1e-9  # nor waits past the deadline


def test_4xx_and_bad_answers_are_not_retried(monkeypatch):
    clock, fake, _ = _flaky(monkeypatch, sia=[400], tap=[502, 200])
    rep = irsa.search_frames_report(RA, DEC, use_cache=False)
    assert rep.service == "tap" and fake.services() == ["sia", "tap", "tap"]  # SIA dropped after its 400
    install(monkeypatch, sia=[ok(b"<html>not a votable</html>")], tap=[FakeResponse(404)])
    with pytest.raises(irsa.SearchError) as exc:
        irsa.search_frames_report(RA, DEC, use_cache=False)
    assert len(exc.value.failures) == 2 and not exc.value.is_outage  # one try each: retrying will not help


def test_retry_after_is_honoured(monkeypatch):
    busy = FakeResponse(429, headers={"Retry-After": "3"})
    clock, fake, sleeps = _flaky(monkeypatch, sia=[busy, 200], tap=[502])
    rep = irsa.search_frames_report(RA, DEC, use_cache=False)
    assert rep.service == "sia" and fake.services() == ["sia", "sia"] and sleeps == [pytest.approx(3.0)]


def test_supervised_job_gets_its_own_search_budget(tmp_path):
    """The jobs child inherits the API's ERRANTE_SEARCH_DEADLINE_S=25 from the image; ERRANTE_JOB_SUPERVISED=1 (set by
    backend/errante_api/jobs/supervisor.py) switches it to ERRANTE_JOB_SEARCH_DEADLINE_S (120 s by default)."""
    import os
    import subprocess
    import sys

    code = "from errante import settings; print(settings.SEARCH_DEADLINE_S)"
    pipeline = str(Path(irsa.__file__).resolve().parents[2])

    def deadline(**env) -> float:
        full = {k: v for k, v in os.environ.items() if not k.startswith("ERRANTE_")}
        full |= {"PYTHONPATH": pipeline, "ERRANTE_SEARCH_DEADLINE_S": "25", **env}
        out = subprocess.run([sys.executable, "-B", "-c", code], env=full, capture_output=True, text=True, check=True)
        return float(out.stdout.strip())

    assert deadline() == 25.0  # the API process keeps its short budget
    assert deadline(ERRANTE_JOB_SUPERVISED="1") == 120.0
    assert deadline(ERRANTE_JOB_SUPERVISED="1", ERRANTE_JOB_SEARCH_DEADLINE_S="90") == 90.0
    # Only raised, never lowered: lightcurve_build.run_bounded sets its own 180 s, and 0 stays unbounded.
    assert deadline(ERRANTE_JOB_SUPERVISED="1", ERRANTE_SEARCH_DEADLINE_S="180") == 180.0
    assert deadline(ERRANTE_JOB_SUPERVISED="1", ERRANTE_SEARCH_DEADLINE_S="0") == 0.0
