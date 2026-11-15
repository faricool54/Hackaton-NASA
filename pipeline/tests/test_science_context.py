"""Object context (WS3-10): offline replays of responses recorded live on 2026-11-15.

The fixtures in fixtures/ws3/context/ are the raw service answers (Sesame CfA, ESA Gaia TAP, VizieR CfA, NASA
Exoplanet Archive) for the five R05 targets by name and at their fields.toml positions, an empty-sky point
(200.0, +40.1) and 'GJ 699'. Expected values are cross-checked against docs/validation/*.md.
"""

from __future__ import annotations

import json
import os
import shutil
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from errante.models import Fact
from errante.science import context as C

FIXTURES = Path(__file__).parent / "fixtures" / "ws3" / "context"
CLICKS = {
    "barnards-star": (269.44623, 4.76870),
    "eps-indi-b": (331.09665, -56.80066),
    "wise-0855": (133.75980, -7.24219),
    "rw-aurigae": (76.95659, 30.40129),
    "r-draconis": (248.16723, 66.75502),
    "empty-sky": (200.0, 40.1),
}
LABELS = [
    "Effective temperature",
    "Radius",
    "Luminosity",
    "Mass",
    "Distance",
    "Spectral type",
    "Variability type",
    "Variability period",
]


def by_name(name: str, **kw) -> C.ObjectContext:
    return C.object_context(name=name, cache_dir=FIXTURES, offline=True, **kw)


def at(key: str, **kw) -> C.ObjectContext:
    ra, dec = CLICKS[key]
    return C.object_context(ra, dec, cache_dir=FIXTURES, offline=True, **kw)


def facts(ctx: C.ObjectContext) -> dict[str, Fact]:
    return {f.label: f for f in C.physical_parameters(ctx)}


def no_replay_gaps(ctx: C.ObjectContext) -> None:
    gaps = [p for p in ctx.provenance if p.status == "error"]
    assert not gaps, [(p.service, p.note) for p in gaps]


# --- pure functions -------------------------------------------------------------------------------------------


def test_default_epoch_is_the_photometry_epoch():
    from errante.imaging.photometry import SPHEREX_ERA_MJD

    assert C.DEFAULT_EPOCH_MJD == SPHEREX_ERA_MJD


def test_propagation_reproduces_barnard_j2000_from_gaia():
    # Gaia DR3 2016.0 -> J2000 vs SIMBAD J2000 (validation record): only the perspective term (~0.16") remains.
    ra, dec = C.propagate(269.4485025254, 4.7394200511, -801.551, 10362.394, -16.0)
    assert C.separation_arcsec(ra, dec, 269.45207696, 4.69336497) < 0.25


def test_propagation_is_finite_at_the_pole_and_static_without_pm():
    ra, dec = C.propagate(10.0, 89.9999, 5000.0, 0.0, 10.0)
    assert -90.0 <= dec <= 90.0 and 0.0 <= ra < 360.0
    assert C.propagate(10.0, 20.0, None, None, 10.0) == (10.0, 20.0)


def test_display_name_strips_simbad_prefixes():
    assert C.display_name("NAME Barnard's star") == "Barnard's star"
    assert C.display_name("* eps Ind B") == "eps Ind B"
    assert C.display_name("V* RW Aur") == "RW Aur"
    assert C.display_name("{Name} Gl 699") == "Gl 699"


def test_parse_sesame_not_found_and_garbage():
    empty = '<?xml version="1.0"?><Sesame><Target><name>x</name><INFO>*** Nothing found ***</INFO></Target></Sesame>'
    assert C.parse_sesame(empty, "x") is None
    with pytest.raises(ValueError):
        C.parse_sesame("<html>oops", "x")


def test_arguments_are_validated():
    with pytest.raises(ValueError):
        C.object_context(1.0, 2.0, name="x", cache_dir=FIXTURES, offline=True)
    with pytest.raises(ValueError):
        C.object_context(cache_dir=FIXTURES, offline=True)
    with pytest.raises(ValueError):
        C.object_context(1.0, 2.0, radius_arcsec=0, cache_dir=FIXTURES, offline=True)


# --- the five targets by name ---------------------------------------------------------------------------------


def test_barnard_by_name():
    ctx = by_name("Barnard's Star")
    no_replay_gaps(ctx)
    assert ctx.display_name == "Barnard's star" and ctx.object_type == "BY*" and ctx.spectral_type == "M4V"
    g = ctx.gaia.source
    assert ctx.gaia.method == "simbad_crossid" and g.source_id == 4472832130942575872
    assert g.pmra == pytest.approx(-801.551, abs=0.01) and g.pmdec == pytest.approx(10362.394, abs=0.01)
    assert g.parallax == pytest.approx(546.976, abs=0.01)
    assert ctx.sesame_gaia_sep_arcsec < C.SESAME_GAIA_WARN_ARCSEC
    # the SPHEREx-era position is ~100" north of the 2016.0 one
    assert C.separation_arcsec(ctx.ra, ctx.dec, g.ra, g.dec) > 90.0
    assert {p.name for p in ctx.planets} == {"Barnard b", "Barnard c", "Barnard d", "Barnard e"}
    assert all(p.match == "gaia_dr3_id" and p.mass_kind == "Msini" and p.radius_calculated for p in ctx.planets)
    assert ctx.variability.name == "V2500 Oph" and ctx.variability.var_type == "BY"
    j = next(m for m in ctx.photometry if m.band == "J")
    assert j.mission == "2MASS" and j.mag == pytest.approx(5.244) and j.designation.endswith("17574849+0441405")
    f = facts(ctx)
    assert f["Effective temperature"].value.startswith("3100") and "M dwarfs" in f["Effective temperature"].source
    assert "4250" in f["Effective temperature"].source  # GSP-Spec disagreement is reported
    assert f["Mass"].value == "unknown" and not f["Mass"].verified and f["Mass"].unit is None
    assert f["Distance"].value.startswith("1.828") and f["Distance"].verified
    assert "external.gaiaedr3_distance" in f["Distance"].source


def test_eps_ind_b_by_name_never_gets_eps_ind_a_planet():
    ctx = by_name("eps Ind B")
    no_replay_gaps(ctx)
    assert ctx.gaia.source.source_id == 6412596012146801152 and ctx.gaia.method == "simbad_crossid"
    assert ctx.gaia.source.parallax == pytest.approx(270.658, abs=0.01)
    assert ctx.planets == []
    assert ctx.nearby_planet_hosts and ctx.nearby_planet_hosts[0]["hostname"] == "eps Ind A"
    assert any("NOT this object" in w for w in ctx.warnings)
    assert any("RUWE 4.30" in w for w in ctx.warnings)
    assert ctx.variability.name == "CI Ind" and ctx.variability.period_d is None
    f = facts(ctx)
    # no GSP-Phot temperature; the ultracool-dwarf module (ESP-UCD) gives one, flagged as a blend of Ba+Bb
    assert f["Effective temperature"].value == "1417" and "ESP-UCD" in f["Effective temperature"].source
    assert "composite" in f["Effective temperature"].source
    assert f["Radius"].value == "unknown" and f["Variability period"].value == "unknown"
    assert f["Distance"].value.startswith("3.69")
    ks = next(m for m in ctx.photometry if m.band == "Ks")
    w1 = next(m for m in ctx.photometry if m.band == "W1")
    assert ks.mag == pytest.approx(11.208) and w1.mag == pytest.approx(10.718)


def test_wise_0855_by_name_is_not_the_gaia_star_next_to_it():
    ctx = by_name("WISE J085510.83-071442.5")
    no_replay_gaps(ctx)
    assert ctx.object_type == "BD*" and ctx.spectral_type == "Y2"
    assert ctx.gaia.source is None
    # the G = 16.3 field star blended with it in SPHEREx is inside the radius but moves like a background star
    assert [r["source_id"] for r in ctx.gaia.rejected] == [5756956644387831296]
    w = {m.band: m for m in ctx.photometry}
    assert set(w) == {"W1", "W2", "W3", "W4"}  # not in 2MASS (J = 25)
    assert w["W1"].mag == pytest.approx(16.231) and w["W2"].mag == pytest.approx(13.704)
    assert w["W4"].upper_limit and all(m.mission == "WISE" for m in w.values())
    f = facts(ctx)
    assert f["Effective temperature"].value == "unknown" and f["Radius"].value == "unknown"
    assert f["Distance"].value.startswith("2.278") and "SIMBAD parallax 439.0" in f["Distance"].source


def test_rw_aur_by_name_is_ambiguous_between_a_and_b():
    ctx = by_name("RW Aur")
    no_replay_gaps(ctx)
    assert ctx.object_type == "TT*" and ctx.spectral_type == "K1/5e+K5e"
    assert ctx.gaia.method == "nearest_after_propagation" and ctx.gaia.ambiguous
    assert ctx.gaia.source.source_id == 156430817820015232  # nearest to SIMBAD's system position = RW Aur B
    assert any("156430822114424576" in w and "BRIGHTER" in w for w in ctx.warnings)
    f = facts(ctx)
    assert not f["Distance"].verified and "Ambiguous" in f["Distance"].source
    assert f["Effective temperature"].value == "unknown"
    assert f["Variability type"].value.startswith("CTTS/ROT+CTTS")
    assert f["Variability period"].value == "2.64" and "rotation" in f["Variability period"].source


def test_r_dra_by_name():
    ctx = by_name("R Dra")
    no_replay_gaps(ctx)
    assert ctx.gaia.source.source_id == 1648328016354496384 and ctx.gaia.method == "simbad_crossid"
    assert not ctx.gaia.ambiguous  # 19th-magnitude neighbours do not count
    assert ctx.variability.var_type == "M" and ctx.variability.period_d == pytest.approx(246.12)
    assert 1.0 / ctx.gaia.source.lpv_frequency == pytest.approx(247.2, abs=0.1)
    f = facts(ctx)
    assert f["Variability period"].value == "246.1" and "247.2 +/- 6.0" in f["Variability period"].source
    assert f["Effective temperature"].value == "unknown" and f["Radius"].value == "unknown"
    assert f["Distance"].verified and f["Distance"].value == "792 (750-832)"
    # saturated in 2MASS / AllWISE: the quality flags travel with the magnitudes
    q = {m.band: m.quality for m in ctx.photometry}
    assert q["J"] == "D" and q["W1"] == "U"


def test_gj_699_old_position_is_flagged_and_not_matched():
    ctx = by_name("GJ 699")
    no_replay_gaps(ctx)
    assert "VizieR" in ctx.sesame.resolver and ctx.sesame.pm_ra is None
    assert ctx.gaia.source is None and ctx.gaia.candidates  # candidates are listed, none is adopted
    assert any("8.6'" in w for w in ctx.warnings)
    assert all(f.value == "unknown" for f in C.physical_parameters(ctx) if f.label != "Variability type")


# --- clicks ----------------------------------------------------------------------------------------------------


def test_barnard_click_propagates_and_gets_simbad_identity():
    ctx = at("barnards-star")
    no_replay_gaps(ctx)
    g = ctx.gaia.source
    assert g.source_id == 4472832130942575872 and ctx.gaia.method == "nearest_after_propagation"
    assert g.sep_arcsec < 4.0 and not ctx.gaia.ambiguous and not ctx.gaia.loose
    # in 2016 the star was ~100" south of the clicked SPHEREx-era position
    assert C.separation_arcsec(*CLICKS["barnards-star"], g.ra, g.dec) > 90.0
    assert ctx.display_name == "Barnard's star"  # SIMBAD via its Gaia DR3 id
    assert len(ctx.planets) == 4 and facts(ctx)["Distance"].verified


def test_rw_aur_click_names_the_component():
    ctx = at("rw-aurigae")
    no_replay_gaps(ctx)
    assert ctx.main_id == "V* RW Aur B" and ctx.gaia.ambiguous  # SIMBAD cross-id of Gaia DR3 156430817820015232


def test_wise_0855_click_warns_that_the_nearest_gaia_star_may_be_another_object():
    ctx = at("wise-0855")
    no_replay_gaps(ctx)
    assert ctx.gaia.source.source_id == 5756956644387831296 and ctx.gaia.loose
    assert any("may not be the object you clicked" in w for w in ctx.warnings)
    f = facts(ctx)
    assert f["Effective temperature"].value != "unknown" and not f["Effective temperature"].verified


@pytest.mark.parametrize("key", ["eps-indi-b", "r-draconis"])
def test_other_target_clicks_match_the_validated_gaia_ids(key):
    expected = {"eps-indi-b": 6412596012146801152, "r-draconis": 1648328016354496384}[key]
    ctx = at(key)
    no_replay_gaps(ctx)
    assert ctx.gaia.source.source_id == expected and not ctx.gaia.ambiguous


def test_empty_sky_is_all_unknown():
    ctx = at("empty-sky")
    no_replay_gaps(ctx)
    assert ctx.gaia.source is None and ctx.sesame is None and ctx.variability is None
    assert ctx.planets == [] and ctx.photometry == []
    out = C.physical_parameters(ctx)
    assert [f.label for f in out] == LABELS
    assert all(f.value == "unknown" and f.verified is False and f.unit is None for f in out)


# --- output, cache and failures --------------------------------------------------------------------------------


def test_to_dict_is_strict_json_with_contract_facts():
    for ctx in (by_name("Barnard's Star"), at("empty-sky")):
        doc = ctx.to_dict()
        text = json.dumps(doc, allow_nan=False)
        back = json.loads(text)
        assert [Fact.model_validate(f).label for f in back["facts"]] == LABELS
        assert {p["key"] for p in back["parameters"]} >= {"teff", "radius", "distance"}
        assert all(p["retrieved_utc"] for p in back["provenance"] if p["status"] == "ok")
        assert all(m["mission"] in {"2MASS", "WISE"} for m in back["photometry"])


def test_numeric_parameters_for_the_3d_model():
    params = {p.key: p for p in by_name("Barnard's Star").parameters()}
    assert params["teff"].value == pytest.approx(3099.63, abs=0.1)
    assert params["radius"].lower < params["radius"].value < params["radius"].upper
    assert params["mass"].value is None


def test_gaia_falls_back_to_vizier_when_esa_is_unreachable(tmp_path):
    for f in FIXTURES.glob("*.json"):
        if not f.name.startswith("gaia-esa-"):
            shutil.copy(f, tmp_path / f.name)
    ctx = C.object_context(*CLICKS["barnards-star"], cache_dir=tmp_path, offline=True)
    assert ctx.gaia.catalog == C.GAIA_VIZIER_CATALOG and ctx.gaia.source.source_id == 4472832130942575872
    assert any("VizieR CfA" in w for w in ctx.warnings)
    f = facts(ctx)
    assert f["Effective temperature"].value.startswith("3100") and "I/355/gaiadr3" in f["Effective temperature"].source
    assert f["Radius"].value == "unknown" and "VizieR fallback" in f["Radius"].source
    assert f["Distance"].value.startswith("1.828")  # 1/parallax: no Bailer-Jones in the fallback


def test_every_service_down_still_answers_a_click(tmp_path):
    ctx = C.object_context(*CLICKS["barnards-star"], cache_dir=tmp_path, offline=True)
    assert ctx.gaia is None and all(p.status == "error" for p in ctx.provenance)
    assert all(f.value == "unknown" for f in C.physical_parameters(ctx))
    with pytest.raises(C.ContextError):
        C.object_context(name="Barnard's Star", cache_dir=tmp_path, offline=True)


def test_cache_ttl_and_stale_fallback(tmp_path, monkeypatch):
    import requests

    http = C._Http(tmp_path, use_cache=True, offline=False, ttl_s=3600.0, timeout_s=1.0)
    path = http._path("vsx", C.VIZIER_TSV, {"a": "1"})
    old = (datetime.now(UTC) - timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%SZ")
    path.write_text(json.dumps({"retrieved_utc": old, "text": "cached"}), encoding="utf-8")

    def down(*a, **k):
        raise requests.ConnectionError("no route")

    monkeypatch.setattr(requests, "get", down)
    reply = http.get("vsx", C.VIZIER_TSV, {"a": "1"})
    assert reply.ok and reply.stale and reply.text == "cached" and "no route" in reply.error
    fresh = C._Http(tmp_path, use_cache=True, offline=False, ttl_s=1e9, timeout_s=1.0)
    assert fresh.get("vsx", C.VIZIER_TSV, {"a": "1"}).cached
    assert (
        not C._Http(tmp_path, use_cache=False, offline=False, ttl_s=1e9, timeout_s=1.0)
        .get("vsx", C.VIZIER_TSV, {"a": "1"})
        .ok
    )


def test_query_errors_are_not_cached(tmp_path, monkeypatch):
    import requests

    class R:
        status_code = 200
        text = '<INFO name="QUERY_STATUS" value="ERROR">ORA-00904</INFO>'

    monkeypatch.setattr(requests, "get", lambda *a, **k: R())
    http = C._Http(tmp_path, use_cache=True, offline=False, ttl_s=1e9, timeout_s=1.0)
    reply = http.get("exoplanets", C.EXOPLANET_TAP_SYNC, {"query": "x"})
    assert not reply.ok and "query error" in reply.error and not list(tmp_path.iterdir())


def test_cli_object_offline(capsys, monkeypatch, tmp_path):
    from errante import cli, settings

    shutil.copytree(FIXTURES, tmp_path / "context")
    monkeypatch.setattr(settings, "CACHE_DIR", tmp_path)
    assert cli.main(["object", "--name", "R Dra", "--offline", "--json"]) == 0
    doc = json.loads(capsys.readouterr().out)
    assert doc["gaia"]["source"]["source_id"] == 1648328016354496384
    assert cli.main(["object", "--ra", "200.0", "--dec", "40.1", "--offline"]) == 0
    assert "unknown" in capsys.readouterr().out
    assert cli.main(["object", "--ra", "200.0", "--offline"]) == 2


def test_transient_empty_vizier_answer_is_retried_and_never_cached(tmp_path, monkeypatch):
    import requests

    answers = iter(["#RESOURCE=\n#Name:\n", "#Table\tB_vsx_vsx:\nOID\n \n-\n1\n"])

    class R:
        status_code = 200

        def __init__(self, text):
            self.text = text

    monkeypatch.setattr(requests, "get", lambda *a, **k: R(next(answers)))
    http = C._Http(tmp_path, use_cache=True, offline=False, ttl_s=1e9, timeout_s=1.0)
    reply = http.get("vsx", C.VIZIER_TSV, {"b": "2"}, require="#Table")
    assert reply.ok and "#Table" in reply.text  # second attempt
    monkeypatch.setattr(requests, "get", lambda *a, **k: R("#RESOURCE=\n"))
    bad = http.get("vsx", C.VIZIER_TSV, {"c": "3"}, require="#Table")
    assert not bad.ok and "transient" in bad.error
    assert len(list(tmp_path.iterdir())) == 1  # only the good answer was cached


# --- live services (ERRANTE_NETWORK_TESTS=1) -------------------------------------------------------------------

live = pytest.mark.skipif(os.environ.get("ERRANTE_NETWORK_TESTS") != "1", reason="set ERRANTE_NETWORK_TESTS=1")


def _live_http(tmp_path) -> C._Http:
    return C._Http(tmp_path, use_cache=False, offline=False, ttl_s=0.0, timeout_s=60.0)


@pytest.mark.network
@live
def test_live_sesame_cfa(tmp_path):
    info, prov = C._sesame(_live_http(tmp_path), "Barnard's Star")
    assert prov.status == "ok", prov.note
    assert info.is_simbad and info.pm_ra == pytest.approx(-801.551) and info.gaia_dr3_id == 4472832130942575872
    gj, _ = C._sesame(_live_http(tmp_path), "GJ 699")
    assert gj is not None and not gj.is_simbad and gj.pm_ra is None  # the old-epoch VizieR answer


@pytest.mark.network
@live
def test_live_gaia_esa_tap_and_vizier_fallback(tmp_path):
    http = _live_http(tmp_path)
    ra, dec = CLICKS["barnards-star"]
    rows, prov = C.gaia_cone_esa(http, ra, dec, C.DEFAULT_RADIUS_ARCSEC, C.DEFAULT_EPOCH_MJD)
    assert rows is not None, prov.note
    barnard = next(g for g in rows if g.source_id == 4472832130942575872)
    assert C.gaia_details_esa(http, barnard).status == "ok"
    assert barnard.teff_gspphot == pytest.approx(3099.6, abs=1) and barnard.r_med_geo == pytest.approx(1.828, abs=0.01)
    rows, provs = C.gaia_cone_vizier(http, ra, dec, C.DEFAULT_RADIUS_ARCSEC, C.DEFAULT_EPOCH_MJD)
    assert rows is not None, [p.note for p in provs]
    assert 4472832130942575872 in {g.source_id for g in rows}


@pytest.mark.network
@live
def test_live_barnard_full_context(tmp_path):
    ctx = C.object_context(name="Barnard's Star", cache_dir=tmp_path, use_cache=False)
    errors = [(p.service, p.note) for p in ctx.provenance if p.status == "error"]
    assert not errors, errors
    assert ctx.gaia.source.source_id == 4472832130942575872
    assert {p.name for p in ctx.planets} >= {"Barnard b"}  # NASA Exoplanet Archive pscomppars
    assert ctx.variability.name == "V2500 Oph"
    assert {m.mission for m in ctx.photometry} == {"2MASS", "WISE"}


@pytest.mark.network
@live
def test_live_r_dra_vsx_and_wise_0855_allwise(tmp_path):
    rdra = C.object_context(name="R Dra", cache_dir=tmp_path, use_cache=False)
    assert rdra.variability is not None and rdra.variability.period_d == pytest.approx(246.12)
    wise = C.object_context(name="WISE J085510.83-071442.5", cache_dir=tmp_path, use_cache=False)
    assert wise.gaia.source is None
    assert next(m for m in wise.photometry if m.band == "W2").mag == pytest.approx(13.704)
