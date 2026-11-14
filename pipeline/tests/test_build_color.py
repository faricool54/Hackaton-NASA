"""WS2: build_field writes false-color season composites (Field.composites) after choosing the final frames."""

import json

import numpy as np
from PIL import Image
from test_build_robust import SEASON_0, SEASON_1, config, frame, install_archive, note

from errante import build
from errante.build import build_field
from errante.cli import main
from errante.imaging import color
from errante.models import SkyField
from errante.products import ProductStore

# Per season: D1 0.95 (blue), D2 1.25 (J), D3 1.68 (H, published) and D3 2.17 (Ks, pool only), D6 4.70 (red).
WAVELENGTHS = [("d1", 1, 0.95), ("j2", 2, 1.25), ("h3", 3, 1.68), ("k3", 3, 2.17), ("r6", 6, 4.70)]


def archive(monkeypatch):
    frames = [
        frame(f"{tag}_{s}", start + 0.1 * i, det=det, lam=lam, seed=10 * s + i)
        for s, start in enumerate((SEASON_0, SEASON_1))
        for i, (tag, det, lam) in enumerate(WAVELENGTHS)
    ]
    return install_archive(monkeypatch, frames)


def test_build_writes_detector_and_jhk_composites_from_final_frames_and_pool(monkeypatch, tmp_path):
    _, fetched = archive(monkeypatch)
    # 8 published frames = one per (season, detector); the pool (10) also holds the Ks exposures.
    field = build_field(config(max_frames=8), tmp_path)

    published = {f.id for f in field.frames}
    assert len(fetched) == 10 and len(published) == 8
    assert {"k3_0D3", "k3_1D3"}.isdisjoint(published)  # D3 shows the H exposures (same colour every season)
    by_id = {c.id: c for c in field.composites}
    assert sorted(by_id) == ["detectors_S0", "detectors_S1", "jhk_S0", "jhk_S1"]

    det = by_id["detectors_S1"]
    assert [ch.detector for ch in det.channels] == [6, 3, 1]
    assert [ch.frame_ids for ch in det.channels] == [["r6_1D6"], ["h3_1D3"], ["d1_1D1"]]
    assert all(set(ch.frame_ids) <= published for ch in det.channels)

    jhk = by_id["jhk_S0"]
    assert [ch.frame_ids for ch in jhk.channels] == [["k3_0D3"], ["h3_0D3"], ["j2_0D2"]]
    assert [ch.wavelength_um for ch in jhk.channels] == [2.17, 1.68, 1.25]

    fdir = ProductStore(tmp_path).field_dir("t-field")
    for comp in field.composites:
        with Image.open(fdir / comp.image) as png:
            assert png.mode in ("RGB", "RGBA") and png.size == (field.grid.width_px, field.grid.height_px)
    assert note(field, "False-color composites: ").count("(infrared, not true color)") == 1

    stored = SkyField.model_validate_json((fdir / "field.json").read_text(encoding="utf-8"))
    assert stored.composites == field.composites
    assert main(["validate", "--dir", str(tmp_path)]) == 0


def test_composites_use_the_variance_plane_on_the_grid(monkeypatch, tmp_path):
    archive(monkeypatch)
    seen = []
    real = color.write_composites

    def spy(field_dir, final, pool):
        seen.extend(final)
        return real(field_dir, final, pool)

    monkeypatch.setattr(color, "write_composites", spy)
    build_field(config(max_frames=8), tmp_path)
    assert seen and all(f.variance is not None and f.variance.shape == f.data.shape for f in seen)
    assert all(f.wavelength_um is not None for f in seen)


def test_a_composite_failure_does_not_block_the_published_field(monkeypatch, tmp_path):
    archive(monkeypatch)

    def broken(*args, **kwargs):
        raise RuntimeError("colour went wrong")

    monkeypatch.setattr(color, "write_composites", broken)
    field = build_field(config(max_frames=8), tmp_path)
    assert len(field.frames) == 8 and field.composites == []
    assert note(field, "False-color composites: ") == (
        "False-color composites: not built (RuntimeError: colour went wrong)."
    )
    assert ProductStore(tmp_path).read_field("t-field").frames


def test_a_field_without_the_needed_detectors_has_no_composites_and_says_why(monkeypatch, tmp_path):
    frames = [frame(f"o{s}", start, det=2, lam=1.4, seed=s) for s, start in enumerate((SEASON_0, SEASON_1))]
    install_archive(monkeypatch, frames)
    field = build_field(config(max_frames=4), tmp_path)
    assert field.composites == []
    text = note(field, "False-color composites: ")
    assert text.startswith("False-color composites: none built") and "detectors S0" in text and "jhk S1" in text


def test_rebuild_with_fewer_seasons_removes_stale_composite_pngs(monkeypatch, tmp_path):
    archive(monkeypatch)
    build_field(config(max_frames=8), tmp_path)
    fdir = ProductStore(tmp_path).field_dir("t-field")
    assert (fdir / "color" / "detectors_S1.png").exists()

    only_season_0 = [frame(f"{tag}_0", SEASON_0 + 0.1 * i, det=det, lam=lam, seed=i)
                     for i, (tag, det, lam) in enumerate(WAVELENGTHS)]  # fmt: skip
    install_archive(monkeypatch, only_season_0)
    monkeypatch.setattr(build, "load_field_configs", lambda: {"t-field": config(max_frames=8)})
    assert main(["build", "t-field", "--out", str(tmp_path)]) == 0
    stored = json.loads((fdir / "field.json").read_text(encoding="utf-8"))
    assert [c["id"] for c in stored["composites"]] == ["detectors_S0", "jhk_S0"]
    assert sorted(p.name for p in (fdir / "color").iterdir()) == ["detectors_S0.png", "jhk_S0.png"]
    assert np.isfinite(stored["composites"][0]["mjd_min"])


def _jhk_archive(monkeypatch):
    """Two seasons; the frame nearest each season's middle (ranked first) is never at J, H or Ks."""
    frames = []
    for s, base in enumerate((SEASON_0, SEASON_1)):
        frames += [
            frame(f"S{s}_D1", base + 1, det=1, lam=0.9, seed=10 * s + 1),
            frame(f"S{s}_D6", base + 1, det=6, lam=4.7, seed=10 * s + 2),
            frame(f"S{s}_D2_mid", base + 1, det=2, lam=1.45, seed=10 * s + 3),
            frame(f"S{s}_D2_J", base, det=2, lam=1.25, seed=10 * s + 4),
            frame(f"S{s}_D2_H", base + 2, det=2, lam=1.63, seed=10 * s + 5),
            frame(f"S{s}_D3_mid", base + 1, det=3, lam=2.0, seed=10 * s + 6),
            frame(f"S{s}_D3_K", base + 2, det=3, lam=2.17, seed=10 * s + 7),
        ]
    return install_archive(monkeypatch, frames)


def test_jhk_topup_downloads_the_missing_bands_without_changing_the_blink_frames(monkeypatch, tmp_path):
    _jhk_archive(monkeypatch)
    plain = build_field(config(4), tmp_path / "plain")
    assert [c for c in plain.composites if c.mode == "jhk"] == []
    _, fetched = _jhk_archive(monkeypatch)
    topped = build_field(config(4), tmp_path / "topped", jhk_topup=True)
    jhk = [c for c in topped.composites if c.mode == "jhk"]
    assert sorted(c.season for c in jhk) == [0, 1]
    assert {f"S{s}_D2_J" for s in (0, 1)} <= set(fetched) and {f"S{s}_D3_K" for s in (0, 1)} <= set(fetched)
    assert [f.id for f in topped.frames] == [f.id for f in plain.frames]  # the blink is unchanged


def test_cli_build_tops_up_jhk_unless_asked_not_to(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(build, "build_field", lambda cfg, out, **kw: calls.append(kw["jhk_topup"]))
    assert main(["build", "wise-0855", "--out", str(tmp_path)]) == 0
    assert main(["build", "wise-0855", "--out", str(tmp_path), "--no-jhk-topup"]) == 0
    assert calls == [True, False]


def test_jhk_topup_is_counted_apart_from_the_blink_downloads(monkeypatch, tmp_path):
    _jhk_archive(monkeypatch)
    plain = build_field(config(4), tmp_path / "plain")
    _jhk_archive(monkeypatch)
    topped = build_field(config(4), tmp_path / "topped", jhk_topup=True)
    head = "Frame selection: downloaded "
    assert note(topped, head).split(" candidate")[0] == note(plain, head).split(" candidate")[0]
    assert "more D2/D3 frame(s) only to find J/H/Ks wavelengths" in note(topped, head)
    assert "J/H/Ks" not in note(plain, head)


def test_a_failed_jhk_topup_keeps_the_field_and_says_why(monkeypatch, tmp_path):
    _jhk_archive(monkeypatch)

    def broken(*args, **kwargs):
        raise RuntimeError("archive hiccup")

    monkeypatch.setattr(build, "_jhk_topup", broken)
    field = build_field(config(4), tmp_path, jhk_topup=True)
    assert len(field.frames) == 4  # the blink is published as usual
    assert ProductStore(tmp_path).read_field("t-field").frames
    assert note(field, "Frame selection: ").endswith("J/H/Ks top-up: not run (RuntimeError: archive hiccup).")


def test_jhk_topup_skips_seasons_without_a_final_frame(monkeypatch, tmp_path):
    _, fetched = _jhk_archive(monkeypatch)
    calls = []
    real = build._jhk_topup

    def spy(cfg, grid, ranked, vetted, final, tried):
        calls.append(sorted({f.mjd < SEASON_1 for f in final}))
        return real(cfg, grid, ranked, vetted, final[:1], tried)  # pretend only the first season is shown

    monkeypatch.setattr(build, "_jhk_topup", spy)
    build_field(config(4), tmp_path, jhk_topup=True)
    assert calls == [[False, True]]
    assert "S0_D2_J" in fetched and "S1_D2_J" not in fetched
