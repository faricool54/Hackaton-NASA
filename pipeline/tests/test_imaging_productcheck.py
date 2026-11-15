"""WS2-8: the published-product check (imaging/productcheck*.py) on tiny SYNTHETIC products.

The products are written the way the build writes them (field.json + 8-bit PNGs through render.save_png, the
roll-off announced in the provenance note), with a mover of known shift and a variable of known brightness
change, so the check must recover both from the PNGs alone.
"""

import json
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pytest

from errante.imaging import productcheck, productcheck_variable, render
from errante.imaging.grid import make_grid, sky_to_png_xy
from errante.imaging.productcheck_data import Astrometry, catalog_astrometry, load_field, rolloff_levels
from errante.imaging.productcheck_measure import Aperture, flux_centroid, plateau
from errante.models import Frame, Provenance, SkyCoord, SkyField, Stretch

RA, DEC = 150.0, 10.0
SKY, NOISE = 0.1, 0.05
STRETCH_WIDTH = 2.1  # vmax - vmin, as field_stretches would give (2 sigma below the sky to 40 sigma above)
PSF_SIGMA = 0.7  # px
SEASON_MJD = (60000.0, 60200.0)
SHIFT_PX = (0.5, -1.0)  # mover: +x = west, -y = north between the two seasons
FIELD_STARS = [
    (6.3, 7.1, 1.4),
    (33.2, 6.4, 1.2),
    (8.1, 31.7, 1.6),
    (31.6, 33.3, 1.3),
    (20.4, 4.2, 1.5),
    (4.6, 20.3, 1.25),
    (35.1, 19.6, 1.45),
    (19.2, 35.5, 1.35),
]
VARIABLE_ROLLOFF = 20.0  # MJy/sr above vmax, announced as 'D1: white = vmax + 20 MJy/sr'


def _grid():
    return make_grid(RA, DEC, 40 * 6.15 / 3600)


def _mover_astrometry(grid) -> Astrometry:
    """pm that moves the target by SHIFT_PX between the seasons and puts it at the centre mid-way."""
    years = (SEASON_MJD[1] - SEASON_MJD[0]) / 365.25
    east, north = -SHIFT_PX[0] * 6.15, -SHIFT_PX[1] * 6.15  # arcsec
    pm_ra, pm_dec = east / years * 1000, north / years * 1000
    mid_years = ((SEASON_MJD[0] + SEASON_MJD[1]) / 2 - 51544.5) / 365.25
    dec0 = DEC - pm_dec / 3.6e6 * mid_years
    ra0 = RA - pm_ra / 3.6e6 / np.cos(np.radians(DEC)) * mid_years
    return Astrometry(ra0, dec0, pm_ra, pm_dec, None, "synthetic test astrometry")


def _image(shape, sources, seed) -> np.ndarray:
    rng = np.random.default_rng(seed)
    yy, xx = np.indices(shape)
    img = SKY + rng.normal(0.0, NOISE, shape)
    for x, y, amp in sources:
        img += amp * np.exp(-((xx - x) ** 2 + (yy - y) ** 2) / (2 * PSF_SIGMA**2))
    return img


def _frame(fid: str, det: int, mjd: float, wl: float, stretch: Stretch) -> Frame:
    return Frame(
        id=fid,
        obs_id=fid.split("D")[0],
        detector=det,
        mjd=mjd,
        date_obs=datetime(2023, 1, 1, tzinfo=UTC),
        wavelength_um=wl,
        release="synthetic",
        image=f"frames/{fid}.png",
        stretch=stretch,
    )


def _write_field(root: Path, fid: str, tags: list[str], frames: list[tuple[Frame, np.ndarray, float | None]], notes):
    grid = _grid()
    field_dir = root / "fields" / fid
    for meta, img, highlight in frames:
        render.save_png(img, field_dir / meta.image, meta.stretch, highlight)
    sky = SkyField(
        id=fid,
        name=f"Synthetic {fid}",
        tags=tags,
        center=SkyCoord(ra=RA, dec=DEC),
        size_deg=0.0683,
        grid=grid,
        frames=[f for f, _, _ in frames],
        provenance=Provenance(
            pipeline_version="test", built_at=datetime(2026, 11, 15, tzinfo=UTC), synthetic=True, notes=notes
        ),
    )
    (field_dir / "field.json").write_text(sky.model_dump_json(indent=1), encoding="utf-8")
    return field_dir


def write_mover(root: Path, saturated: bool = False) -> tuple[Path, Astrometry]:
    grid = _grid()
    astro = _mover_astrometry(grid)
    shape = (grid.height_px, grid.width_px)
    frames = []
    for season, mjd0 in enumerate(SEASON_MJD):
        for det in (1, 2):
            for k in range(2):
                mjd = mjd0 + 0.5 * k + 0.1 * det
                x, y = sky_to_png_xy(grid, *astro.position_at(mjd))
                amp = 40.0 if saturated else 1.8  # 1.8 stays under vmax: an unclipped core
                img = _image(shape, [*FIELD_STARS, (float(x), float(y), amp)], seed=100 * season + 10 * det + k)
                stretch = Stretch(vmin=SKY - 2 * NOISE, vmax=SKY - 2 * NOISE + STRETCH_WIDTH)
                frames.append((_frame(f"SYN_{season}_{k}D{det}", det, mjd, 1.0 + det, stretch), img, None))
    return _write_field(root, "syn-mover", ["proper-motion"], frames, ["Synthetic mover for tests."]), astro


def write_variable(root: Path) -> Path:
    shape = (_grid().height_px, _grid().width_px)
    centre = ((shape[1] - 1) / 2, (shape[0] - 1) / 2)
    stretch = Stretch(vmin=SKY - 2 * NOISE, vmax=SKY - 2 * NOISE + STRETCH_WIDTH)
    rolloff_top = stretch.vmax + VARIABLE_ROLLOFF
    frames = []
    # D1: unclipped core in the roll-off, 2.5x brighter in season 1 at matched wavelength (0.750 vs 0.753 um).
    for season, (amp, wl) in enumerate([(4.0, 0.750), (10.0, 0.753)]):
        img = _image(shape, [*FIELD_STARS, (*centre, amp)], seed=7 + season)
        frames.append((_frame(f"VAR_{season}_0D1", 1, SEASON_MJD[season], wl, stretch), img, rolloff_top))
    img = _image(shape, [*FIELD_STARS, (*centre, 6.0)], seed=9)  # unmatched wavelength: no pair
    frames.append((_frame("VAR_1_1D1", 1, SEASON_MJD[1] + 1, 0.900, stretch), img, rolloff_top))
    # D2: saturated core (white in both seasons), the white disc shrinks.
    for season, amp in enumerate([60.0, 20.0]):
        img = _image(shape, [*FIELD_STARS, (*centre, amp)], seed=20 + season)
        frames.append((_frame(f"VAR_{season}_0D2", 2, SEASON_MJD[season] + 0.2, 1.200, stretch), img, None))
    note = f"Display note (D1: white = vmax + {VARIABLE_ROLLOFF:.3g} MJy/sr)."
    return _write_field(root, "syn-variable", ["variable"], frames, [note])


def test_rolloff_levels_are_read_from_the_build_note():
    note = "... (D1: white = vmax + 53.4 MJy/sr; D5: white = vmax + 22 MJy/sr). thumb.png is a D5 frame."
    assert rolloff_levels([note]) == {1: 53.4, 5: 22.0}


def test_catalog_astrometry_is_read_from_the_fields_toml_comments_only():
    astro = catalog_astrometry()
    b = astro["barnards-star"]
    assert (b.pm_ra_cosdec_mas_yr, b.pm_dec_mas_yr, b.parallax_mas) == (-801.551, 10362.394, 546.976)
    assert astro["wise-0855"].pm_ra_cosdec_mas_yr == -8123.7
    assert "nep-deep" not in astro  # no astrometry comment -> "expected: not available"


def test_flux_centroid_refuses_clipped_boxes_and_plateau_finds_the_white_region():
    img = _image((20, 20), [(9.3, 10.6, 2.0)], seed=1)
    clipped = np.zeros(img.shape, bool)
    c = flux_centroid(img, clipped, 9.0, 10.0, NOISE, 5.0)
    assert c.status == "ok" and c.x == pytest.approx(9.3, abs=0.1) and c.y == pytest.approx(10.6, abs=0.1)
    clipped[10:12, 9:11] = True
    assert flux_centroid(img, clipped, 9.0, 10.0, NOISE, 5.0).status == "clipped"
    assert flux_centroid(img, np.zeros(img.shape, bool), 9.0, 10.0, float("nan"), 5.0).status == "no_data"
    p = plateau(clipped, 9.0, 10.0)
    assert (p.x, p.y, p.area) == (9.5, 10.5, 4)
    assert flux_centroid(_image((20, 20), [], seed=2), np.zeros((20, 20), bool), 9, 10, NOISE, 5.0).status == "faint"


def test_the_known_shift_of_a_mover_is_recovered_from_the_pngs(tmp_path):
    field_dir, astro = write_mover(tmp_path / "products")
    report = productcheck.run_check(tmp_path / "products", tmp_path / "out", {"syn-mover": astro})
    m = report["fields"][0]["motion"]
    head = m["headline"]
    assert head["estimator"] == "core" and head["detectors"] == [1, 2]
    assert head["expected_px"] == pytest.approx(np.hypot(*SHIFT_PX), abs=0.01)
    assert head["dx_px"] == pytest.approx(SHIFT_PX[0], abs=0.1) and head["dy_px"] == pytest.approx(SHIFT_PX[1], abs=0.1)
    assert head["sigma_px"] is not None and head["residual_px"] < 0.1
    assert head["pa_deg"] == pytest.approx(head["expected_pa_deg"], abs=6.0)
    corrected = [s for s in m["shifts"] if s["registration_corrected"]]
    assert corrected and corrected[0]["shift_px"] == pytest.approx(head["shift_px"], abs=0.05)
    summary = report["fields"][0]["summary"]
    assert summary["png_registration"]["checked"] == 8 and summary["png_registration"]["max_px"] < 0.1
    assert (tmp_path / "out" / "syn-mover_track.png").is_file()


def test_a_saturated_mover_falls_back_to_the_white_plateau_and_says_so(tmp_path):
    _, astro = write_mover(tmp_path / "products", saturated=True)
    report = productcheck.run_check(tmp_path / "products", tmp_path / "out", {"syn-mover": astro})
    m = report["fields"][0]["motion"]
    assert m["core_status_counts"] == {"clipped": 8} and m["plateau_frames"] == 8
    head = m["headline"]
    assert head["estimator"] == "plateau"
    assert head["shift_px"] == pytest.approx(np.hypot(*SHIFT_PX), abs=0.35)  # indicative only


def test_without_catalog_astrometry_the_expected_shift_is_not_available(tmp_path):
    write_mover(tmp_path / "products")
    report = productcheck.run_check(tmp_path / "products", tmp_path / "out", {})
    m = report["fields"][0]["motion"]
    assert m["expected_available"] is False and m["headline"]["expected_px"] is None
    assert "expected: not available" in (tmp_path / "out" / "report.md").read_text(encoding="utf-8")


def test_a_known_brightness_change_is_recovered_at_matched_wavelength(tmp_path, monkeypatch):
    write_variable(tmp_path / "products")
    hyps = {
        "syn-variable": (
            productcheck_variable.Hypothesis("VAR_0_0D1", "VAR_1_0D1", 2.5, "test"),
            productcheck_variable.Hypothesis("VAR_0_0D1", "VAR_1_0D1", 1.5, "wrong on purpose"),
            productcheck_variable.Hypothesis("VAR_0_0D2", "VAR_1_0D2", 3.0, "both white"),
        )
    }
    monkeypatch.setattr(productcheck_variable, "HYPOTHESES", hyps)
    report = productcheck.run_check(tmp_path / "products", tmp_path / "out", {})
    v = report["fields"][0]["variable"]
    d1 = [p for p in v["pairs"] if p["detector"] == 1]
    assert len(d1) == 1 and d1[0]["bound"] == "value"  # the 0.900 um frame has no partner
    assert d1[0]["ratio"] == pytest.approx(2.5, rel=0.06)
    assert d1[0]["controls_median"] == pytest.approx(1.0, abs=0.03) and d1[0]["blink_visible"]
    d2 = [p for p in v["pairs"] if p["detector"] == 2]
    assert d2[0]["bound"] == "none" and d2[0]["ratio"] is None  # two lower bounds: no ratio
    assert d2[0]["blink_visible"] and "white disc" in d2[0]["blink_note"]
    assert [h["verdict"] for h in v["hypotheses"]] == ["confirmed", "refuted", "undetermined"]
    assert {c["status"] for c in v["levels"] if c["detector"] == 2} == {"clipped_core"}


def test_the_cli_writes_report_md_json_and_figures(tmp_path):
    write_variable(tmp_path / "products")
    toml = tmp_path / "fields.toml"
    toml.write_text(
        '[[field]]\nid = "syn-variable"\n# J2000 150.0 +10.0 | pm (+1.0, -2.0) mas/yr | plx 3.0 mas\n', encoding="utf-8"
    )
    out = tmp_path / "out"
    code = productcheck.main(["--products", str(tmp_path / "products"), "--out", str(out), "--fields-toml", str(toml)])
    assert code == 0
    data = json.loads((out / "report.json").read_text(encoding="utf-8"))
    field = data["fields"][0]
    assert field["synthetic"] and field["astrometry"]["pm_dec_mas_yr"] == -2.0
    md = (out / "report.md").read_text(encoding="utf-8")
    assert "SYNTHETIC DATA" in md and "not science" in md and "syn-variable_brightness.png" in md
    assert (out / "syn-variable_brightness.png").is_file()
    assert productcheck.main(["--products", str(tmp_path / "missing"), "--out", str(out)]) == 1


def test_integrity_problems_are_reported_not_raised(tmp_path):
    field_dir = write_variable(tmp_path / "products")
    (field_dir / "frames" / "VAR_1_1D1.png").unlink()
    loaded = load_field(field_dir)
    assert len(loaded.frames) == 4 and any("PNG missing" in p for p in loaded.problems)


def _level(fid: str, season: int, *, area: int = 0, core: int = 0, peak: float = 10.0, clipped: int = 0):
    ap = Aperture(
        total=10 * peak, sigma=1.0, n_pixels=29, n_clipped=clipped, sky=0.1, peak=peak, peak_grey=250, flat_top=1
    )
    return productcheck_variable.CoreLevel(
        fid, season, 1, 60000.0 + 200 * season, 0.75, (19.5, 19.5), ap, core, area, rolloff=True
    )


def test_a_white_disc_counts_as_a_blink_change_only_when_it_changes_clearly():
    small = productcheck_variable._blink(_level("a", 0, area=4, core=4), _level("b", 1, area=5, core=5))
    large = productcheck_variable._blink(_level("a", 0, area=28, core=16), _level("b", 1, area=16, core=16))
    assert small[0] is False and "4 -> 5 px" in small[1]
    assert large[0] is True and "28 -> 16 px" in large[1]


def test_the_single_white_pixel_that_sets_the_roll_off_top_is_a_value_not_a_bound():
    levels = [_level("a", 0, peak=25.0), _level("b", 0, peak=40.0), _level("c", 1, peak=60.0, clipped=1, core=1)]
    marked = productcheck_variable.mark_rolloff_tops(levels, {1: 53.4})
    assert [c.at_rolloff_top for c in marked] == [False, False, True] and not marked[2].lower_bound
    two_white = [*levels[:2], _level("c", 1, peak=60.0, clipped=2, core=2)]
    assert not any(c.at_rolloff_top for c in productcheck_variable.mark_rolloff_tops(two_white, {1: 53.4}))
    capped = [*levels[:2], _level("c", 1, peak=500.0, clipped=1, core=1)]  # top > 4x the median peak: capped
    assert not any(c.at_rolloff_top for c in productcheck_variable.mark_rolloff_tops(capped, {1: 53.4}))
    assert not any(c.at_rolloff_top for c in productcheck_variable.mark_rolloff_tops(levels, {}))
