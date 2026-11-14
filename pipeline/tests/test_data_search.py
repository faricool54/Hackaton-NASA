"""Offline tests for errante.data.irsa.search_frames (WS1-2).

fixtures/ws1/barnard_sia_dr1_qr3.xml is a real SIA2 VOTable for Barnard's Star (269.44623, 4.76870)
recorded on 2026-11-14 and trimmed to 14 of its 358 rows (header and FIELDs untouched).
fixtures/ws1/barnard_tap_from_sia.csv is NOT a recorded TAP answer: IRSA TAP returned 502 or hung
for the whole session on 2026-11-14, so it holds the same 14 real rows (uri, t_min/t_max,
bandpass, collection) in the CSV layout of ``irsa.build_query``'s SELECT, with planeid left empty.
TODO(WS1): re-record it from a real TAP answer once TAP is back.
"""

from __future__ import annotations

import json
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
    fake = install(monkeypatch, sia=[FakeResponse(503), FakeResponse(502), ok(SIA_XML)])
    rep = irsa.search_frames_report(RA, DEC)
    assert rep.service == "sia" and len(rep.result.frames) == 14
    assert fake.count(settings.IRSA_SIA) == 3


def test_falls_back_to_tap_when_sia_keeps_failing(monkeypatch):
    fake = install(monkeypatch, sia=[FakeResponse(502)], tap=[ok(TAP_CSV)])
    rep = irsa.search_frames_report(RA, DEC, mjd_min=60000, mjd_max=62000)
    assert rep.service == "tap"
    assert rep.result.frames
    assert rep.errors and rep.errors[0].startswith("sia: HTTPError")
    assert fake.count(settings.IRSA_SIA) == settings.SEARCH_ATTEMPTS
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
    assert "INTERSECTS(CIRCLE('ICRS', 269.44623000, 4.76870000, 0.05), p.poly)" in q
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
    # A timeout is retried once, not SEARCH_ATTEMPTS times.
    assert fake.count(settings.IRSA_SIA) == 2 and fake.count(settings.IRSA_TAP_SYNC) == 2


def test_both_services_down_is_not_a_timeout(monkeypatch):
    install(monkeypatch, sia=[FakeResponse(502)], tap=[FakeResponse(503)])
    with pytest.raises(irsa.SearchError, match="sia: HTTPError.*tap: HTTPError") as exc:
        irsa.search_frames(RA, DEC)
    chain = _cause_chain(exc.value)
    assert not any(isinstance(e, (requests.Timeout, TimeoutError)) for e in chain)
    assert isinstance(chain[1], requests.HTTPError)
    assert exc.value.is_outage and len(exc.value.failures) == 2


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


def test_cli_search_summary_and_json(monkeypatch, capsys):
    install(monkeypatch, sia=[ok(SIA_XML)])
    assert cli_main(["search", "--ra", str(RA), "--dec", str(DEC), "--radius", "0.01"]) == 0
    out = capsys.readouterr().out
    assert "14 frames" in out and "via SIA" in out
    assert "by collection: spherex_dr1: 10, spherex_qr3: 4" in out
    assert "by detector:   D1: 2, D2: 2, D3: 3, D4: 2, D5: 2, D6: 3" in out
    # Trimmed fixture: in-season gaps exceed 30 d, so the CLI lists 5 "seasons" here.
    assert "1. MJD 60902.87-60914.21" in out and "5. MJD 61305.63-61305.63" in out

    assert (
        cli_main(["search", "--ra", str(RA), "--dec", str(DEC), "--radius", "0.01", "--detector", "6", "--json"]) == 0
    )
    res = SearchResult.model_validate_json(capsys.readouterr().out)
    assert {f.detector for f in res.frames} == {6}

    install(monkeypatch, sia=[FakeResponse(502)], tap=[FakeResponse(502)])
    assert cli_main(["search", "--ra", "1", "--dec", "1", "--no-cache"]) == 2
    assert "Search failed" in capsys.readouterr().err
