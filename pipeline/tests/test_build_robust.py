"""WS2: bad-frame rejection, wavelength-matched selection from a downloaded pool, CLI overrides."""

import dataclasses
import json
from pathlib import Path

import numpy as np
import pytest
from test_build_selection import ref
from test_imaging_reproject import DEC0, RA0, fake_image

from errante import build
from errante.build import MAX_NOISE_RATIO, FieldConfig, build_field, noise_ratio
from errante.cli import main
from errante.data import cutouts, fits_io, irsa
from errante.data.fits_io import SpherexImage
from errante.imaging.flags import FLAG_BITS
from errante.models import FrameRef, SearchResult, SkyCoord
from errante.products import ProductStore

SEASON_0, SEASON_1 = 60903.0, 61110.0  # two Barnard-like seasons, > 30 days apart
STEP = 60.0  # background step [MJy/sr] for unit noise: ~39x, like the real step frames (19.6x and 45.5x)


def noisy(img: SpherexImage, seed: int, step: float = 0.0, sigma: float = 1.0) -> SpherexImage:
    """``img`` with Gaussian noise matching its VARIANCE plane and an optional soft diagonal background step."""
    rng = np.random.default_rng(seed)
    ny, nx = img.data.shape
    yy, xx = np.mgrid[0:ny, 0:nx]
    background = step / (1 + np.exp(-12 * (xx / nx + yy / ny - 1)))  # 0 below the diagonal, `step` above
    data = img.data + rng.normal(0.0, sigma, img.data.shape) + background
    return dataclasses.replace(
        img, data=data.astype(np.float32), variance=np.full(img.data.shape, sigma**2, dtype=np.float32)
    )


def saturated_star(seed: int, **kw) -> SpherexImage:
    """A K~4-like star: NaN OVERFLOW core, bright wings and a halo over ~20 % of the cutout."""
    img = noisy(fake_image(stars=((RA0, DEC0, 2e5),), sigma_px=2.0, **kw), seed)
    halo = fake_image(stars=((RA0, DEC0, 20.0),), sigma_px=6.0, zodi_level=0.0).data
    data = img.data + halo
    core = data > 5e4
    flags = np.where(core, 1 << FLAG_BITS["OVERFLOW"], 0).astype(np.int32)
    return dataclasses.replace(img, data=np.where(core, np.nan, data).astype(np.float32), flags=flags)


def frame(obs: str, mjd: float, det: int = 1, lam: float | None = None, seed: int = 0, step: float = 0.0):
    """(FrameRef, image) of one exposure; the wavelength is only known from the image (WCS-WAVE)."""
    img = noisy(fake_image(obs_id=obs, mjd=mjd, detector=det, rotation_deg=7 * seed), seed, step=step)
    img.wavelength_at = (lambda ra, dec: None) if lam is None else (lambda ra, dec, lam=lam: (lam, 0.03))
    return ref(obs, det, mjd), img


def install_archive(monkeypatch, frames: list[tuple[FrameRef, SpherexImage]]) -> tuple[list[dict], list[str]]:
    """Fake search + downloads; returns (search kwargs, obs_ids fetched in order)."""
    refs = [r for r, _ in frames]
    images = {r.obs_id: img for r, img in frames}
    searched: list[dict] = []
    fetched: list[str] = []

    def search(*args, **kwargs):
        searched.append(kwargs)
        wanted = kwargs.get("detectors")
        return SearchResult(
            center=SkyCoord(ra=RA0, dec=DEC0),
            radius_deg=0,
            frames=[r for r in refs if wanted is None or r.detector in wanted],
        )

    def fetch(batch, *args, **kwargs):
        fetched.extend(f.obs_id for f in batch)
        return [Path(f"{f.obs_id}.fits") for f in batch]

    monkeypatch.setattr(irsa, "search_frames", search)
    monkeypatch.setattr(cutouts, "fetch_cutouts", fetch)
    monkeypatch.setattr(fits_io, "read_spherex", lambda path: images[Path(path).stem])
    return searched, fetched


def config(max_frames: int, **kw) -> FieldConfig:
    return FieldConfig(id="t-field", name="T", ra=RA0, dec=DEC0, size_deg=0.05, max_frames=max_frames, **kw)


def note(field, start: str) -> str:
    return next(n for n in field.provenance.notes if n.startswith(start))


# --- 1. bad-frame rejection -------------------------------------------------------------------------------


def test_noise_ratio_is_about_one_for_pure_noise_and_large_for_a_background_step():
    assert noise_ratio(noisy(fake_image(stars=()), seed=1)) == pytest.approx(1.0, abs=0.1)
    stepped = noise_ratio(noisy(fake_image(stars=()), seed=1, step=STEP))
    assert stepped > 2 * MAX_NOISE_RATIO  # the WISE 0855 D1 step measured 19.6x on its real cutout


def test_noise_ratio_ignores_default_bad_pixels_and_needs_a_variance_plane():
    img = noisy(fake_image(stars=()), seed=2)
    hot = np.zeros(img.data.shape, dtype=bool)
    hot[:, : img.data.shape[1] * 2 // 3] = True  # two thirds of the pixels: far more than a MAD tolerates
    flagged = dataclasses.replace(
        img,
        data=np.where(hot, 1e4, img.data).astype(np.float32),
        flags=np.where(hot, 1 << FLAG_BITS["HOT"], 0).astype(np.int32),
    )
    assert noise_ratio(flagged) == pytest.approx(1.0, abs=0.15)
    assert noise_ratio(dataclasses.replace(img, variance=None)) is None
    assert noise_ratio(dataclasses.replace(img, variance=np.zeros_like(img.variance))) is None


def test_a_saturated_bright_star_frame_is_not_a_bad_frame():
    assert noise_ratio(saturated_star(seed=3)) < MAX_NOISE_RATIO / 3


def test_a_background_step_frame_is_rejected_and_replaced(monkeypatch, tmp_path):
    frames = [
        frame("A0", SEASON_0 + 0.0, seed=1),
        frame("A1", SEASON_0 + 1.0, seed=2, step=STEP),  # nearest the season middle, but broken
        frame("A2", SEASON_0 + 2.0, seed=3),
        frame("B0", SEASON_1 + 0.0, seed=4),
        frame("B1", SEASON_1 + 1.0, seed=5),
        frame("B2", SEASON_1 + 2.0, seed=6),
    ]
    _, fetched = install_archive(monkeypatch, frames)
    field = build_field(config(max_frames=2), tmp_path)

    assert [f.id for f in field.frames] == ["A0D1", "B1D1"]  # one frame per season, never A1
    assert fetched == ["A1", "B1", "A0", "B0", "A2"]  # pool of 2 x max_frames, then A1's replacement
    skipped = note(field, "Skipped 1 frame(s): ")
    assert "A1D1: bad frame: noise " in skipped and "x VARIANCE" in skipped
    ratio = float(skipped.split("noise ")[1].split("x")[0])
    assert ratio > MAX_NOISE_RATIO
    selection = note(field, "Frame selection: ")
    assert "downloaded 5 candidate frame(s)" in selection and "Rejected 1 bad frame(s)" in selection
    fdir = ProductStore(tmp_path).field_dir("t-field")
    assert sorted(p.name for p in (fdir / "frames").iterdir()) == ["A0D1.png", "B1D1.png"]


def test_a_saturated_star_frame_is_kept(monkeypatch, tmp_path):
    star = saturated_star(seed=7, obs_id="S0", mjd=SEASON_0)
    assert np.isnan(star.data).any()  # a real saturated core
    install_archive(monkeypatch, [(ref("S0", 1, SEASON_0), star), frame("S1", SEASON_1, seed=8)])
    field = build_field(config(max_frames=2), tmp_path)
    assert [f.id for f in field.frames] == ["S0D1", "S1D1"]
    assert not any(n.startswith("Skipped") for n in field.provenance.notes)


def test_noise_limits_rise_only_for_a_detector_whose_candidates_all_scatter():
    from errante.build import NOISE_OUTLIER_FACTOR, noise_limits

    limits = noise_limits({1: [1.0, 2.0, 2.5], 3: [30.0, 35.0, 40.0, 73.0], 5: [40.0, 45.0]})
    assert limits[1] == MAX_NOISE_RATIO  # ordinary sky: the absolute limit
    assert limits[3] == pytest.approx(NOISE_OUTLIER_FACTOR * 37.5)  # bright nebula: relative to the median
    assert limits[5] == MAX_NOISE_RATIO  # too few candidates for a median


def test_a_bright_nebula_field_keeps_its_frames(monkeypatch, tmp_path):
    """Live job on the Orion Nebula (2026-11-15): every D3 candidate scattered 29-73x its VARIANCE and all were
    rejected. Extended emission over every frame (here the same soft background step) is not a bad frame."""
    frames = [frame(f"N{i}", SEASON_0 + i, seed=i + 1, step=STEP) for i in range(4)]
    install_archive(monkeypatch, frames)
    field = build_field(config(max_frames=4), tmp_path)
    assert len(field.frames) == 4
    assert "Rejected 0 bad frame(s)" in note(field, "Frame selection: ")


def test_every_frame_rejected_is_a_build_error_with_reasons(monkeypatch, tmp_path):
    install_archive(monkeypatch, [frame("A0", SEASON_0, seed=1, step=STEP), frame("B0", SEASON_1, seed=2, step=STEP)])
    with pytest.raises(ValueError, match="was rejected") as err:
        build_field(config(max_frames=2), tmp_path)
    assert "A0D1: bad frame" in str(err.value) and "B0D1: bad frame" in str(err.value)
    assert not ProductStore(tmp_path).manifest_path.exists()


# --- 2. wavelength-matched selection --------------------------------------------------------------------


def test_wavelength_matched_selection_picks_the_same_colour_in_every_season_from_the_pool(monkeypatch, tmp_path):
    # Per group, by distance to the season middle: *_mid, *_near, *_far. The pool (2 x 4 = 8 of 12) takes
    # *_mid and *_near of every group; the final 4 frames (one per group) match in wavelength per detector.
    frames = [
        frame("a_mid", SEASON_0 + 1.0, 1, 0.80, 1), frame("a_near", SEASON_0 + 0.4, 1, 1.00, 2),
        frame("a_far", SEASON_0 + 2.0, 1, 1.005, 3), frame("a_far2", SEASON_0 + 0.0, 1, 0.70, 4),
        frame("b_mid", SEASON_1 + 1.0, 1, 1.01, 5), frame("b_near", SEASON_1 + 0.4, 1, 0.85, 6),
        frame("b_far", SEASON_1 + 2.0, 1, 0.90, 7), frame("b_far2", SEASON_1 + 0.0, 1, 0.70, 8),
        frame("c_mid", SEASON_0 + 1.0, 2, 1.30, 9), frame("c_near", SEASON_0 + 1.6, 2, 1.50, 10),
        frame("c_far", SEASON_0 + 2.0, 2, 1.40, 11), frame("c_far2", SEASON_0 + 0.0, 2, 1.40, 12),
        frame("d_mid", SEASON_1 + 1.0, 2, 1.52, 13), frame("d_near", SEASON_1 + 1.6, 2, 1.31, 14),
        frame("d_far", SEASON_1 + 2.0, 2, 1.40, 15), frame("d_far2", SEASON_1 + 0.0, 2, 1.40, 16),
    ]  # fmt: skip
    _, fetched = install_archive(monkeypatch, frames)
    field = build_field(config(max_frames=4), tmp_path)

    assert sorted(fetched) == sorted(f"{g}_{k}" for g in "abcd" for k in ("mid", "near"))
    assert sorted(f.obs_id for f in field.frames) == ["a_near", "b_mid", "c_mid", "d_near"]
    for det in (1, 2):
        lams = [f.wavelength_um for f in field.frames if f.detector == det]
        assert max(lams) - min(lams) == pytest.approx(0.01)  # time-only selection: 0.21 (D1) and 0.22 (D2)
    assert "D1 1.000 um, D2 1.300 um" in note(field, "Frame selection: ")
    fdir = ProductStore(tmp_path).field_dir("t-field")
    assert len(list((fdir / "frames").iterdir())) == 4  # only the final frames are rendered


def test_the_reference_wavelength_accounts_for_how_many_frames_each_season_shows(monkeypatch, tmp_path):
    # Two frames per season will be shown. 1.000/1.001 is the best SINGLE match, but then each season's
    # second frame is ~0.15 um away; around 0.82 both frames of both seasons agree within 0.06 um.
    frames = [
        frame("p0", SEASON_0 + 0.0, lam=1.000, seed=1), frame("p1", SEASON_0 + 1.0, lam=0.80, seed=2),
        frame("p2", SEASON_0 + 2.0, lam=0.84, seed=3),
        frame("q0", SEASON_1 + 0.0, lam=1.001, seed=4), frame("q1", SEASON_1 + 1.0, lam=0.82, seed=5),
        frame("q2", SEASON_1 + 2.0, lam=0.86, seed=6),
    ]  # fmt: skip
    install_archive(monkeypatch, frames)
    field = build_field(config(max_frames=4), tmp_path)
    assert sorted(f.obs_id for f in field.frames) == ["p1", "p2", "q1", "q2"]
    lams = [f.wavelength_um for f in field.frames]
    assert max(lams) - min(lams) == pytest.approx(0.06)  # single-match reference: 0.161
    assert "D1 0.820 um" in note(field, "Frame selection: ")


def test_frames_with_unknown_wavelength_rank_last_but_stay_usable(monkeypatch, tmp_path):
    # Season middles: SEASON_0 + 1.25 and SEASON_1 + 1.1. u_mid and x_mid are nearest them.
    frames = [
        frame("u_mid", SEASON_0 + 1.0, lam=None, seed=1), frame("k_near", SEASON_0 + 0.5, lam=1.0, seed=2),
        frame("z_end", SEASON_0 + 2.0, lam=None, seed=3),
        frame("x_mid", SEASON_1 + 1.0, lam=None, seed=4), frame("y_near", SEASON_1 + 0.2, lam=None, seed=5),
        frame("y_end", SEASON_1 + 2.0, lam=None, seed=6),
    ]  # fmt: skip
    install_archive(monkeypatch, frames)
    field = build_field(config(max_frames=2), tmp_path)
    assert [(f.obs_id, f.wavelength_um) for f in field.frames] == [("k_near", 1.0), ("x_mid", None)]


def test_without_any_wavelength_the_selection_is_the_time_based_one(monkeypatch, tmp_path):
    frames = [frame(f"s{s}_{i}", start + i, lam=None, seed=10 * s + i) for s, start in enumerate((SEASON_0, SEASON_1))
              for i in range(3)]  # fmt: skip
    install_archive(monkeypatch, frames)
    field = build_field(config(max_frames=2), tmp_path)
    assert [f.obs_id for f in field.frames] == ["s0_1", "s1_1"]  # nearest each season's middle
    assert "(no wavelength known)" in note(field, "Frame selection: ")


# --- 3. CLI overrides -------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("extra", "expected"),
    [
        ([], {}),
        (["--max-frames", "90"], {"max_frames": 90}),
        (["--detectors", "6", "5", "5", "--max-frames", "90"], {"max_frames": 90, "detectors": [5, 6]}),
    ],
)
def test_cli_overrides_reach_build_field(monkeypatch, tmp_path, extra, expected):
    calls = []
    monkeypatch.setattr(build, "build_field", lambda cfg, out, **kw: calls.append((cfg.id, kw)))
    assert main(["build", "wise-0855", "--out", str(tmp_path), *extra]) == 0
    assert calls == [("wise-0855", {"analyze": False, "overrides": expected, "jhk_topup": True})]


@pytest.mark.parametrize("bad", [["--max-frames", "0"], ["--detectors", "7"], ["--detectors"]])
def test_cli_rejects_invalid_overrides(monkeypatch, tmp_path, bad):
    monkeypatch.setattr(build, "build_field", lambda *a, **kw: pytest.fail("must not build"))
    with pytest.raises(SystemExit) as exit_:
        main(["build", "wise-0855", "--out", str(tmp_path), *bad])
    assert exit_.value.code == 2


def test_cli_overrides_change_the_build_and_are_recorded(monkeypatch, tmp_path):
    frames = [frame(f"o{d}_{s}", start, det=d, seed=d + 3 * s) for d in (1, 5, 6)
              for s, start in enumerate((SEASON_0, SEASON_1))]  # fmt: skip
    searched, _ = install_archive(monkeypatch, frames)
    monkeypatch.setattr(build, "load_field_configs", lambda: {"t-field": config(max_frames=40)})
    assert main(["build", "t-field", "--out", str(tmp_path), "--detectors", "6", "5", "--max-frames", "3"]) == 0

    field = json.loads((ProductStore(tmp_path).field_dir("t-field") / "field.json").read_text(encoding="utf-8"))
    assert searched[0]["detectors"] == [5, 6]
    assert len(field["frames"]) == 3 and {f["detector"] for f in field["frames"]} == {5, 6}
    assert (
        "Built with overrides: detectors=[5, 6] (fields.toml: all), max_frames=3 (fields.toml: 40)."
        in field["provenance"]["notes"]
    )


def test_apply_overrides_rejects_unknown_keys():
    with pytest.raises(ValueError, match="Unknown FieldConfig override"):
        build.apply_overrides(config(max_frames=2), {"colour": "red"})
    cfg = config(max_frames=2)
    assert build.apply_overrides(cfg, {}) == (cfg, None)
