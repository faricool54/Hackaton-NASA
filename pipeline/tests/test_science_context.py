"""Object context (WS3-10): offline replays of responses recorded live on 2026-11-15.

The fixtures in fixtures/ws3/context/ are the raw service answers (Sesame CfA, ESA Gaia TAP, VizieR CfA, NASA
Exoplanet Archive) for the five R05 targets by name and at their fields.toml positions, an empty-sky point
(200.0, +40.1), 'GJ 699', the quasar 3C 273 by name, the M87 core by position and a click 5.5" from R Dra.
Expected values are cross-checked against docs/validation/*.md.
"""

from __future__ import annotations

import json
import os
import re
import shutil
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import urlsplit

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
    # review cases (2026-11-15): one SPHEREx pixel from R Dra, nearest Gaia source a G = 19.4 star; M87 core
    "r-dra-offset": (248.16723, 66.75502 + 5.5 / 3600),
    "m87-core": (187.70593, 12.39112),
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
    # ~402" apart at J2000 (fields.toml), ~405" at 2016.0; not the ~344" a track minimum vs a 2016 position gives
    assert 395.0 < ctx.nearby_planet_hosts[0]["sep_arcsec"] < 410.0
    assert any("NOT this object" in w and '(~404" at 2016.0)' in w for w in ctx.warnings)
    assert any("RUWE 4.30" in w for w in ctx.warnings)
    assert ctx.variability.name == "CI Ind" and ctx.variability.period_d is None
    f = facts(ctx)
    # no GSP-Phot temperature; the ultracool-dwarf module (ESP-UCD) gives one with its uncertainty (98 K, ESA TAP),
    # flagged as a blend of Ba+Bb
    teff = f["Effective temperature"]
    assert teff.value == "1417 (1319-1515)" and "ESP-UCD" in teff.source and "+/- 98 K" in teff.source
    assert "no uncertainty" not in teff.source and "composite" in teff.source
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
    # by name: SIMBAD is the named object and VSX's entry carries its name, so both stay verified
    assert f["Variability type"].verified and f["Spectral type"].verified
    assert ctx.identity_uncertain and all(m.identity_uncertain for m in ctx.photometry)
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
    # review 2026-11-15: values reached through the ambiguous match (SIMBAD by Gaia id, VSX by position) are not
    # verified and say why
    f = facts(ctx)
    for label in ("Spectral type", "Variability type", "Variability period"):
        assert f[label].value != "unknown" and not f[label].verified, label
        assert "ambiguous or distant Gaia match" in f[label].source, label
    assert ctx.identity_uncertain and ctx.photometry and all(m.identity_uncertain for m in ctx.photometry)


def test_wise_0855_click_warns_that_the_nearest_gaia_star_may_be_another_object():
    ctx = at("wise-0855")
    no_replay_gaps(ctx)
    assert ctx.gaia.source.source_id == 5756956644387831296 and ctx.gaia.loose
    assert any("may not be the object you clicked" in w for w in ctx.warnings)
    f = facts(ctx)
    assert f["Effective temperature"].value != "unknown" and not f["Effective temperature"].verified
    # the field star's 2MASS/AllWISE magnitudes carry the identity flag
    assert ctx.photometry and all(m.identity_uncertain for m in ctx.photometry)


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
    assert not any("could not be reached" in (f.source or "") for f in out)  # genuine negatives here


# --- review regressions (2026-11-15) ---------------------------------------------------------------------------


def test_quasar_by_name_gets_no_stellar_parameters():
    # 3C 273: Gaia DR3 3700386905605055360, parallax -0.016 +/- 0.021 mas; GSP-Phot gave 9880 K and Bailer-Jones
    # 17119 pc, both marked verified before the fix
    ctx = by_name("3C 273")
    no_replay_gaps(ctx)
    assert ctx.object_type == "BLL" and ctx.gaia.source.source_id == 3700386905605055360
    assert ctx.gaia.source.classprob_dsc_combmod_quasar == pytest.approx(0.848, abs=0.001)
    f = facts(ctx)
    for label in ("Effective temperature", "Radius", "Luminosity", "Mass", "Distance"):
        assert f[label].value == "unknown" and not f[label].verified, label
        assert "extragalactic" in f[label].source, label
    assert f["Variability type"].value.startswith("AGN") and f["Variability type"].verified  # VSX is fine
    assert any("extragalactic" in w for w in ctx.warnings)
    params = {p.key: p for p in ctx.parameters()}
    assert params["distance"].value is None and params["teff"].value is None  # nothing for the 3D model


def test_prior_only_distance_is_not_shown():
    # M87 core by position: no SIMBAD entry for its Gaia id, parallax -1.47 +/- 0.43 mas; Bailer-Jones gives 5941 pc
    # from the prior alone
    ctx = at("m87-core")
    no_replay_gaps(ctx)
    g = ctx.gaia.source
    assert g.source_id == 3907709439453756032 and g.r_med_geo is not None
    assert g.classprob_dsc_combmod_galaxy > 0.99
    f = facts(ctx)
    assert f["Distance"].value == "unknown" and "not significant" in f["Distance"].source
    assert f["Spectral type"].source == "No SIMBAD entry for Gaia DR3 3907709439453756032."
    assert any("likely galaxy" in w for w in ctx.warnings)


def test_low_snr_parallax_distance_is_shown_but_not_verified():
    ctx = by_name("Barnard's Star")
    g = ctx.gaia.source
    g.parallax_error = g.parallax / 3.0
    dist = facts(ctx)["Distance"]
    assert dist.value.startswith("1.828") and not dist.verified and "S/N = 3.0" in dist.source
    g.parallax_error = g.parallax / 0.5  # S/N 0.5: the Bailer-Jones value would be the prior alone
    assert "SIMBAD parallax" in facts(ctx)["Distance"].source  # SIMBAD's significant parallax is used instead
    ctx.sesame.plx_mas = None
    dist = facts(ctx)["Distance"]
    assert dist.value == "unknown" and "S/N 0.5) is not significant" in dist.source


def test_click_next_to_a_bright_star_adopts_the_star_that_fills_the_pixel():
    # 5.5" from R Dra (G = 6.37); the nearest Gaia source is Gaia DR3 1648328016354504064 (G = 19.44, 1.7"). Before
    # the fix the card named that star and gave it R Dra's Mira variability, verified.
    ctx = at("r-dra-offset")
    no_replay_gaps(ctx)
    assert ctx.gaia.method == "brightest_within_radius" and ctx.gaia.source.source_id == 1648328016354496384
    assert ctx.display_name == "R Dra" and ctx.gaia.loose and not ctx.gaia.ambiguous
    assert any("1648328016354504064" in w and "dominates the SPHEREx pixel" in w for w in ctx.warnings)
    f = facts(ctx)
    assert f["Variability type"].value.startswith("M ") and f["Variability period"].value == "246.1"
    assert not any(x.verified for x in f.values())  # 5.5" from the click: identity not verified
    assert all(m.identity_uncertain for m in ctx.photometry)


def _src(sid: int, ddec_arcsec: float, g: float) -> C.GaiaSource:
    return C.GaiaSource(source_id=sid, ra=100.0, dec=20.0 + ddec_arcsec / 3600.0, phot_g_mean_mag=g)


def test_ambiguity_warning_names_the_brightest_rival(monkeypatch):
    # nearest G = 14.0 at 1"; rivals G = 13.5 at 3" (nearest brighter) and G = 12.0 at 6" (brightest); none is
    # 2.5 mag brighter than the nearest, so the nearest is kept and the match is ambiguous
    sources = [_src(1, 1.0, 14.0), _src(2, 3.0, 13.5), _src(3, 6.0, 12.0)]
    monkeypatch.setattr(C, "gaia_cone_esa", lambda *a, **k: (sources, C.Provenance("gaia-esa", "x", "u")))
    warnings, provenance = [], []
    match = C._gaia_match(None, 100.0, 20.0, 8.0, C.GAIA_DR3_EPOCH_MJD, None, None, warnings, provenance)
    assert match.source.source_id == 1 and match.ambiguous and match.method == "nearest_after_propagation"
    text = next(w for w in warnings if "BRIGHTER" in w)
    assert "Gaia DR3 3, G = 12.00" in text and "Gaia DR3 2," not in text


def test_vsx_outage_is_not_reported_as_not_variable(tmp_path):
    for f in FIXTURES.glob("*.json"):
        if not f.name.startswith("vsx-"):
            shutil.copy(f, tmp_path / f.name)
    ctx = C.object_context(name="R Dra", cache_dir=tmp_path, offline=True)  # a Mira
    f = facts(ctx)
    assert f["Variability type"].value == "unknown" and "could not be reached" in f["Variability type"].source
    assert "not catalogued" not in f["Variability type"].source
    # the Gaia long-period-variable period is still there, with a note that VSX was not checked
    assert (
        f["Variability period"].value.startswith("247.2")
        and "VSX could not be reached" in f["Variability period"].source
    )
    assert any(w.startswith("AAVSO VSX could not be reached") for w in ctx.warnings)


def test_exoplanet_box_near_a_pole_avoids_the_waf_blocked_literal():
    # the archive's Cloudflare WAF answers 'where 1=1 and ...' with HTTP 403 (2026-11-15); 'ra >= 0' passes
    assert C._ra_box(0.0, 180.0) == "ra >= 0"
    assert C._ra_box(359.0, 2.0) == "(ra >= 357.000000 OR ra <= 1.000000)"
    assert C._ra_box(100.0, 1.0) == "ra BETWEEN 99.000000 AND 101.000000"


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
    f = facts(ctx)
    assert all(x.value == "unknown" for x in f.values())
    # review 2026-11-15: an outage is never reported as a catalog negative
    for label in ("Effective temperature", "Radius", "Distance", "Variability type", "Variability period"):
        assert "could not be reached" in f[label].source, label
    text = " ".join(x.source for x in f.values())
    assert "No Gaia DR3 counterpart" not in text and "not catalogued" not in text and "No parallax" not in text
    for label in ("AAVSO VSX", "NASA Exoplanet Archive", "2MASS", "AllWISE"):
        assert any(w.startswith(label) and "not a negative result" in w for w in ctx.warnings), label
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
    assert cli.main(["object", "--ra", "133.75980", "--dec", "-7.24219", "--offline"]) == 0
    assert "IDENTITY UNCERTAIN" in capsys.readouterr().out  # field star's 2MASS/AllWISE at the WISE 0855 click
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


def test_a_host_that_did_not_accept_a_connection_is_skipped_for_a_while(tmp_path, monkeypatch):
    import requests

    calls = []

    def unreachable(url, *a, **k):
        calls.append(url)
        raise requests.exceptions.ConnectTimeout("connect timeout")

    monkeypatch.setattr(C, "_DOWN_HOSTS", {})
    monkeypatch.setattr(requests, "get", unreachable)
    http = C._Http(tmp_path, use_cache=True, offline=False, ttl_s=1e9, timeout_s=1.0)
    first = http.get("gaia-esa", C.GAIA_TAP_SYNC, {"q": "1"})
    second = http.get("gaia-esa", C.GAIA_TAP_SYNC, {"q": "2"})  # another query to the same host: not attempted
    assert not first.ok and "ConnectTimeout" in first.error and len(calls) == 1
    assert not second.ok and second.error.startswith("skipped: gea.esac.esa.int") and len(calls) == 1
    other = http.get("vsx", C.VIZIER_TSV, {"q": "3"})  # other hosts are unaffected
    assert not other.ok and len(calls) == 2
    # the skip ends after the back-off, and an answer clears it
    monkeypatch.setattr(C, "CONTEXT_HOST_BACKOFF_S", 0.0)

    class R:
        status_code, text = 200, "source_id\n1\n"

    monkeypatch.setattr(requests, "get", lambda *a, **k: R())
    assert http.get("gaia-esa", C.GAIA_TAP_SYNC, {"q": "2"}, require="source_id").ok
    assert "gea.esac.esa.int" not in C._DOWN_HOSTS
    C._DOWN_HOSTS.clear()
    # a read timeout (slow server, connection accepted) or a refused connection does not trip it
    monkeypatch.setattr(C, "CONTEXT_HOST_BACKOFF_S", 120.0)
    for error in (requests.exceptions.ReadTimeout("slow"), requests.ConnectionError("refused")):
        monkeypatch.setattr(requests, "get", lambda *a, e=error, **k: (_ for _ in ()).throw(e))
        assert not http.get("gaia-esa", C.GAIA_TAP_SYNC, {"q": "4"}).ok and C._DOWN_HOSTS == {}


def test_one_dropped_connection_to_cfa_does_not_block_the_name_resolver(tmp_path, monkeypatch):
    # Regression (review 2026-11-15): Sesame, the VizieR Gaia fallback, VSX, 2MASS and AllWISE share the CfA host.
    # Backing it off after one ConnectTimeout made every name lookup fail (502) for 120 s without a network call.
    import requests

    calls = []

    def first_cfa_call_times_out(url, *a, **k):
        calls.append(url)
        if len(calls) == 1:
            raise requests.exceptions.ConnectTimeout("connect timeout")
        raise requests.exceptions.ReadTimeout("slow")  # a later call reached the network (not retried)

    monkeypatch.setattr(C, "_DOWN_HOSTS", {})
    monkeypatch.setattr(requests, "get", first_cfa_call_times_out)
    http = C._Http(tmp_path, use_cache=True, offline=False, ttl_s=1e9, timeout_s=1.0)
    assert not http.get("vsx", C.VIZIER_TSV, {"q": "1"}).ok and len(calls) == 1
    assert C._DOWN_HOSTS == {}
    sesame = http.get("sesame", C.SESAME_URL + "SNV?R%20Dra")
    assert len(calls) == 2 and not sesame.error.startswith("skipped")  # attempted, not skipped
    assert urlsplit(C.SESAME_URL).netloc not in C.BACKOFF_HOSTS
    assert urlsplit(C.GAIA_TAP_SYNC).netloc in C.BACKOFF_HOSTS  # the one host with a fallback (VizieR CfA)


def test_a_name_whose_gaia_lookups_all_failed_reports_no_gaia_answer_not_a_negative(tmp_path):
    # Regression (review 2026-11-15): the UI read match 'name' + no Gaia id as "no Gaia DR3 counterpart". When no
    # Gaia service answered, the response must say so: n_gaia_within_radius null, gaia-* errors, a warning.
    for f in FIXTURES.glob("*.json"):
        if not f.name.startswith("gaia-"):
            shutil.copy(f, tmp_path / f.name)
    for name in ("Barnard's Star", "eps Ind B", "R Dra"):
        doc = _response_json(C.object_context(name=name, cache_dir=tmp_path, offline=True))
        ident = doc["identity"]
        assert ident["match"] == "name" and ident["gaia_source_id"] is None
        assert ident["n_gaia_within_radius"] is None  # no cone answered: unknown (WISE 0855 by name gives 0)
        gaia = [p for p in doc["provenance"] if p["service"].startswith("gaia")]
        assert gaia and all(p["status"] == "error" for p in gaia) and doc["partial"]
        assert any(w.startswith("Gaia DR3 unreachable") for w in doc["warnings"])
    wise = _response_json(by_name("WISE J085510.83-071442.5"))["identity"]
    assert wise["gaia_source_id"] is None and wise["n_gaia_within_radius"] is not None  # answered: a real negative


# --- contract adapter: ObjectContext -> models.ObjectContextResponse (GET /api/object) -------------------------


def _response_json(ctx: C.ObjectContext, **kw) -> dict:
    import jsonschema

    from errante import settings

    doc = C.to_response(ctx, **kw).model_dump(mode="json")
    schema = json.loads((settings.REPO_ROOT / "shared/schema/ObjectContextResponse.schema.json").read_text())
    jsonschema.validate(doc, schema)
    json.dumps(doc, allow_nan=False)
    return doc


def test_response_for_barnard_by_name_keeps_identity_facts_and_other_missions_apart():
    doc = _response_json(by_name("Barnard's Star"))
    ident = doc["identity"]
    assert ident["match"] == "name" and not ident["identity_uncertain"] and ident["display_name"] == "Barnard's star"
    assert ident["gaia_source_id"] == "4472832130942575872" and ident["gaia_method"] == "simbad_crossid"
    assert ident["resolver"] == C.SESAME_CATALOG and ident["spectral_type"] == "M4V"
    assert doc["query"]["name"] == "Barnard's Star" and doc["query"]["ra"] is None
    assert doc["position"]["source"] == "Gaia DR3 propagated to the epoch" and doc["position"]["epoch_mjd"] == 61000.0
    assert [f["label"] for f in doc["facts"]] == LABELS
    mass = next(f for f in doc["facts"] if f["label"] == "Mass")
    assert mass["value"] == "unknown" and not mass["verified"]
    assert [p["name"] for p in doc["planets"]] == ["Barnard d", "Barnard b", "Barnard c", "Barnard e"]
    assert all(p["radius_calculated"] and p["mass_kind"] == "Msini" for p in doc["planets"])
    assert doc["variability"]["name"] == "V2500 Oph" and doc["variability"]["source"].startswith(C.VSX_CATALOG)
    assert {m["mission"] for m in doc["photometry"]} == {"2MASS", "WISE"}
    assert all(m["other_mission"] is True for m in doc["photometry"])
    assert not doc["partial"] and doc["synthetic"] is False and "not SPHEREx" in doc["note"]


@pytest.mark.parametrize(
    "case, match, uncertain",
    [
        (("click", "barnards-star"), "matched", False),
        (("click", "eps-indi-b"), "matched", False),
        (("click", "wise-0855"), "loose", True),
        (("click", "empty-sky"), "none", False),
        (("name", "RW Aur"), "ambiguous", True),
        (("name", "R Dra"), "name", False),
        (("name", "GJ 699"), "none", True),  # resolved by VizieR (local), not SIMBAD: no identification
    ],
)
def test_response_match_status(case, match, uncertain):
    kind, value = case
    doc = _response_json(at(value) if kind == "click" else by_name(value))
    assert doc["identity"]["match"] == match and doc["identity"]["identity_uncertain"] is uncertain
    if uncertain:
        assert all(m["identity_uncertain"] for m in doc["photometry"])


def test_response_never_attaches_a_neighbours_planet():
    doc = _response_json(at("eps-indi-b"))
    assert doc["planets"] == [] and doc["identity"]["display_name"] == "eps Ind B"
    assert [h["hostname"] for h in doc["nearby_planet_hosts"]] == ["eps Ind A"]
    assert doc["nearby_planet_hosts"][0]["planets"] == ["eps Ind A b"]


def test_response_for_empty_sky_is_unknown_not_partial():
    doc = _response_json(at("empty-sky"))
    assert doc["identity"]["gaia_source_id"] is None and doc["identity"]["display_name"] is None
    assert all(f["value"] == "unknown" for f in doc["facts"]) and doc["photometry"] == []
    assert not doc["partial"] and {p["status"] for p in doc["provenance"]} == {"no_match"}


def test_response_with_every_service_down_is_partial_and_unavailable(tmp_path):
    doc = _response_json(C.object_context(*CLICKS["barnards-star"], cache_dir=tmp_path, offline=True))
    assert doc["identity"]["match"] == "unavailable" and doc["identity"]["identity_uncertain"]
    assert doc["partial"] and all(p["status"] == "error" for p in doc["provenance"])


def test_replay_after_a_deadline_reports_pending_services_and_stale_entries(tmp_path):
    # A lookup cut by the API deadline: Sesame and Gaia answered (one Gaia answer is 30 days old), the rest not yet.
    for f in FIXTURES.glob("*.json"):
        if f.name.startswith(("sesame-", "gaia-esa-")):
            shutil.copy(f, tmp_path / f.name)
    old = (datetime.now(UTC) - timedelta(days=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
    for f in tmp_path.glob("gaia-esa-*.json"):
        entry = json.loads(f.read_text(encoding="utf-8"))
        entry["retrieved_utc"] = old
        f.write_text(json.dumps(entry), encoding="utf-8")
    ctx = C.object_context(name="Barnard's Star", cache_dir=tmp_path, offline=True)
    doc = _response_json(ctx, replay_deadline_s=24)
    assert doc["partial"] and doc["warnings"][0].startswith("Partial result") and "24 s" in doc["warnings"][0]
    assert C.OFFLINE_MISS not in json.dumps(doc)
    status = {p["service"]: p for p in doc["provenance"]}
    assert status["vsx"]["status"] == "error" and "API deadline" in status["vsx"]["note"]
    assert any(p["service"] == "gaia-esa" and p["stale"] for p in doc["provenance"])
    assert doc["identity"]["match"] == "name"  # what did answer is still used
    variability = next(f for f in doc["facts"] if f["label"] == "Variability type")
    assert variability["value"] == "unknown" and "not a negative result" in variability["source"]
    # a complete replay is not partial and adds no deadline warning
    full = _response_json(by_name("Barnard's Star"), replay_deadline_s=24)
    assert not full["partial"] and not any("Partial result" in w for w in full["warnings"])


def test_context_error_says_whether_the_name_is_unknown(tmp_path):
    http = C._Http(tmp_path, use_cache=True, offline=True, ttl_s=1e9, timeout_s=1.0)
    nothing = '<?xml version="1.0"?><Sesame><Target><name>zz</name><INFO>*** Nothing found ***</INFO></Target></Sesame>'
    path = http._path("sesame", C.SESAME_URL + "SNV?" + "zz", None)
    path.write_text(json.dumps({"retrieved_utc": "2026-11-15T00:00:00Z", "text": nothing}), encoding="utf-8")
    with pytest.raises(C.ContextError) as unknown:
        C.object_context(name="zz", cache_dir=tmp_path, offline=True)
    assert unknown.value.not_found
    with pytest.raises(C.ContextError) as unreachable:
        C.object_context(name="not recorded", cache_dir=tmp_path, offline=True)
    assert not unreachable.value.not_found


# --- live services (ERRANTE_NETWORK_TESTS=1) -------------------------------------------------------------------
# VizieR CfA sometimes answers an empty RESOURCE even after the client's own retry: on 2026-11-15 a first run failed
# 2 of 4 live tests and an immediate re-run passed. So these tests retry, and a service that still does not answer
# SKIPS the test (an outage is not a code failure); a rejected query (HTTP 4xx, TAP query error, name not found)
# still FAILS it.

live = pytest.mark.skipif(os.environ.get("ERRANTE_NETWORK_TESTS") != "1", reason="set ERRANTE_NETWORK_TESTS=1")
LIVE_ATTEMPTS = 3


def _live_http(tmp_path) -> C._Http:
    return C._Http(tmp_path, use_cache=False, offline=False, ttl_s=0.0, timeout_s=60.0)


def _hard(note: str | None) -> bool:
    note = note or ""
    return note.startswith("query error") or "name not found" in note or re.match(r"HTTP 4\d\d", note) is not None


def _retry(call, errors_of):
    """call() until errors_of(result) is empty; fail on a rejected query, skip if the service never answered."""
    errors: list = []
    for _ in range(LIVE_ATTEMPTS):
        result = call()
        errors = errors_of(result)
        if not errors:
            return result
        hard = [e for e in errors if _hard(e[1])]
        assert not hard, hard
    pytest.skip(f"service did not answer after {LIVE_ATTEMPTS} attempts: {errors}")


def _live_ctx(tmp_path, *args, **kw) -> C.ObjectContext:
    def call():
        try:
            return C.object_context(*args, cache_dir=tmp_path, use_cache=False, **kw)
        except C.ContextError as e:  # Sesame down (transient) or name not found (hard)
            return e

    def errors_of(r):
        if isinstance(r, Exception):
            return [("sesame", str(r))]
        return [(p.service, p.note) for p in r.provenance if p.status == "error"]

    return _retry(call, errors_of)


def _prov_errors(prov: C.Provenance) -> list:
    return [(prov.service, prov.note)] if prov.status == "error" else []


@pytest.mark.network
@live
def test_live_sesame_cfa(tmp_path):
    info, prov = _retry(lambda: C._sesame(_live_http(tmp_path), "Barnard's Star"), lambda r: _prov_errors(r[1]))
    assert prov.status == "ok", prov.note
    assert info.is_simbad and info.pm_ra == pytest.approx(-801.551) and info.gaia_dr3_id == 4472832130942575872
    gj, _ = _retry(lambda: C._sesame(_live_http(tmp_path), "GJ 699"), lambda r: _prov_errors(r[1]))
    assert gj is not None and not gj.is_simbad and gj.pm_ra is None  # the old-epoch VizieR answer


@pytest.mark.network
@live
def test_live_gaia_esa_tap_and_vizier_fallback(tmp_path):
    http = _live_http(tmp_path)
    ra, dec = CLICKS["barnards-star"]
    rows, prov = _retry(
        lambda: C.gaia_cone_esa(http, ra, dec, C.DEFAULT_RADIUS_ARCSEC, C.DEFAULT_EPOCH_MJD),
        lambda r: _prov_errors(r[1]) if r[0] is None else [],
    )
    barnard = next(g for g in rows if g.source_id == 4472832130942575872)
    assert _retry(lambda: C.gaia_details_esa(http, barnard), _prov_errors).status == "ok"
    assert barnard.teff_gspphot == pytest.approx(3099.6, abs=1) and barnard.r_med_geo == pytest.approx(1.828, abs=0.01)
    # columns added after the review: ESP-UCD uncertainty (eps Ind B) and DSC class probabilities (3C 273)
    eps_b, qso = C.GaiaSource(6412596012146801152, 0.0, 0.0), C.GaiaSource(3700386905605055360, 0.0, 0.0)
    for g in (eps_b, qso):
        assert _retry(lambda g=g: C.gaia_details_esa(http, g), _prov_errors).status == "ok"
    assert eps_b.teff_espucd_uncertainty == pytest.approx(98.12, abs=0.01)
    assert qso.classprob_dsc_combmod_quasar == pytest.approx(0.848, abs=0.001)
    rows, provs = _retry(
        lambda: C.gaia_cone_vizier(http, ra, dec, C.DEFAULT_RADIUS_ARCSEC, C.DEFAULT_EPOCH_MJD),
        lambda r: [(p.service, p.note) for p in r[1] if p.status == "error"],
    )
    assert 4472832130942575872 in {g.source_id for g in rows}


@pytest.mark.network
@live
def test_live_barnard_full_context(tmp_path):
    ctx = _live_ctx(tmp_path, name="Barnard's Star")
    assert ctx.gaia.source.source_id == 4472832130942575872
    assert {p.name for p in ctx.planets} >= {"Barnard b"}  # NASA Exoplanet Archive pscomppars
    assert ctx.variability.name == "V2500 Oph"
    assert {m.mission for m in ctx.photometry} == {"2MASS", "WISE"}


@pytest.mark.network
@live
def test_live_r_dra_vsx_and_wise_0855_allwise(tmp_path):
    rdra = _live_ctx(tmp_path, name="R Dra")
    assert rdra.variability is not None and rdra.variability.period_d == pytest.approx(246.12)
    wise = _live_ctx(tmp_path, name="WISE J085510.83-071442.5")
    assert wise.gaia.source is None
    assert next(m for m in wise.photometry if m.band == "W2").mag == pytest.approx(13.704)


@pytest.mark.network
@live
def test_live_exoplanet_archive_box_at_the_pole(tmp_path):
    # with the old 'where 1=1 and ...' clause the archive's WAF answered HTTP 403 (a hard failure here)
    track = C.Track(0.0, 89.99, C.GAIA_DR3_EPOCH_MJD)
    planets, hosts, prov = _retry(
        lambda: C._planets(_live_http(tmp_path), track, None, [], C.DEFAULT_RADIUS_ARCSEC),
        lambda r: _prov_errors(r[2]),
    )
    assert prov.status in {"ok", "no_match"}
