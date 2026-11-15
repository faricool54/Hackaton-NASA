"""Demo animations and stills of published field products (WS2, for WS6's deck/video).

Every test runs on a tiny product written here (16 x 16 px PNGs): what matters is frame counts, sizes, durations,
the caption text embedded in each file and that synthetic fields are never captioned as real SPHEREx data.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from errante.imaging import animate, annotate
from errante.models import Composite, CompositeChannel, Frame, Grid, Provenance, SkyCoord, SkyField, Stretch

N = 16
MJD0 = 61000.0
MJD_EPOCH = datetime(1858, 11, 17, tzinfo=UTC)
CENTRE = (N - 1) / 2


def _star(x: float, y: float, peak: float = 255.0, sigma: float = 1.0, sky: float = 20.0) -> np.ndarray:
    yy, xx = np.indices((N, N))
    img = sky + (peak - sky) * np.exp(-((xx - x) ** 2 + (yy - y) ** 2) / (2 * sigma**2))
    return np.clip(img, 0, 255).round().astype(np.uint8)


def _frame(fid: str, det: int, mjd: float, wl: float) -> Frame:
    return Frame(
        id=fid,
        obs_id=fid[:-2],
        detector=det,
        mjd=mjd,
        date_obs=MJD_EPOCH + timedelta(days=mjd),
        wavelength_um=wl,
        bandwidth_um=0.02,
        release="dr1",
        image=f"frames/{fid}.png",
        stretch=Stretch(vmin=0.0, vmax=1.0),
    )


def _channel(color: str, det: int | None, wl: float, fid: str) -> CompositeChannel:
    return CompositeChannel(color=color, detector=det, wavelength_um=wl, frame_ids=[fid])


def _composite(mode: str, season: int, mjd: float) -> Composite:
    if mode == "detectors":
        chans = [_channel("red", 6, 4.6, "a"), _channel("green", 3, 1.8, "b"), _channel("blue", 1, 0.9, "c")]
    else:
        chans = [_channel("red", 3, 2.17, "a"), _channel("green", None, 1.65, "b"), _channel("blue", 2, 1.24, "c")]
    return Composite(
        id=f"{mode}_S{season}",
        mode=mode,
        season=season,
        mjd_min=mjd,
        mjd_max=mjd + 10,
        image=f"color/{mode}_S{season}.png",
        channels=chans,
    )


# (id, detector, day offset, wavelength, star x offset from the centre); D5 moves +1 px per season.
FRAMES = [
    ("2025W01_1A_0001_1D5", 5, 0.0, 4.30, 0.0),
    ("2025W30_1A_0002_1D5", 5, 200.0, 4.31, 1.0),
    ("2026W05_1A_0003_1D5", 5, 400.0, 4.32, 2.0),
    ("2025W01_1A_0004_1D2", 2, 0.5, 1.50, 0.0),
    ("2025W30_1A_0005_1D2", 2, 200.5, 1.52, 0.0),
    ("2026W05_1A_0006_1D2", 2, 400.5, 1.51, 0.0),
    ("2026W05_1A_0007_1D2", 2, 401.0, 1.60, 0.0),
    ("2025W01_1A_0008_1D1", 1, 0.2, 0.764, 0.0),
    ("2025W30_1A_0009_1D1", 1, 200.2, 0.900, 0.0),
    ("2026W05_1A_0010_1D1", 1, 400.2, 0.771, 0.0),
]
NODATA_FRAME = "2025W30_1A_0002_1D5"  # its left columns are transparent (no data)


def write_product(
    root: Path,
    field_id: str = "test-mover",
    synthetic: bool = False,
    thumb_detector: int | None = 5,
    tags: tuple[str, ...] = ("proper-motion",),
    skip: tuple[str, ...] = (),
    rolloff: tuple[int, ...] = (),
) -> Path:
    """A tiny published product: 10 frames over 3 seasons, 2 detector composites and 1 J/H/Ks composite.

    ``rolloff``: detectors the display note lists with a highlight roll-off, as build._display_note words it.
    """
    fdir = root / "fields" / field_id
    (fdir / "frames").mkdir(parents=True)
    (fdir / "color").mkdir()
    frames = []
    for fid, det, day, wl, dx in FRAMES:
        if fid in skip:
            continue
        frames.append(_frame(fid, det, MJD0 + day, wl))
        grey = _star(CENTRE + dx, CENTRE, peak=320)  # core clipped at white, like a bright target
        if fid == NODATA_FRAME:
            alpha = np.full((N, N), 255, np.uint8)
            alpha[:, :3] = 0
            Image.fromarray(np.dstack([grey, alpha])).save(fdir / "frames" / f"{fid}.png")
        else:
            Image.fromarray(grey).save(fdir / "frames" / f"{fid}.png")
    comps = [_composite("detectors", 0, MJD0), _composite("detectors", 1, MJD0 + 200), _composite("jhk", 0, MJD0)]
    for c in comps:
        rgb = np.dstack([_star(CENTRE, CENTRE, 200), _star(CENTRE, CENTRE, 150), _star(CENTRE, CENTRE, 100)])
        Image.fromarray(rgb).save(fdir / c.image)
    note = "Pixel values are IMAGE - ZODI."
    if rolloff:
        whites = "; ".join(f"D{d}: white = vmax + 3.5 MJy/sr" for d in rolloff)
        note += f" Highlight roll-off where the target at the centre outshines the field's bright end ({whites})."
    note += f" thumb.png is a D{thumb_detector} frame." if thumb_detector else ""
    field = SkyField(
        id=field_id,
        name="Test Star−1",
        tags=list(tags),
        center=SkyCoord(ra=10.0, dec=5.0),
        size_deg=0.03,
        grid=Grid(center=SkyCoord(ra=10.0, dec=5.0), width_px=N, height_px=N, pixel_scale_arcsec=6.15, wcs={}),
        frames=frames,
        provenance=Provenance(
            pipeline_version="test", built_at=datetime(2026, 11, 15, tzinfo=UTC), synthetic=synthetic, notes=[note]
        ),
        composites=comps,
    )
    (fdir / "field.json").write_text(field.model_dump_json(indent=2), encoding="utf-8")
    return root


def _gif_comment(path: Path) -> str:
    with Image.open(path) as im:
        return im.info["comment"].decode("utf-8")


def _png_description(path: Path) -> str:
    with Image.open(path) as im:
        return im.text["Description"]


def _durations(path: Path) -> list[int]:
    out = []
    with Image.open(path) as im:
        for i in range(im.n_frames):
            im.seek(i)
            out.append(im.info["duration"])
    return out


def _field(root: Path, field_id: str = "test-mover") -> SkyField:
    return SkyField.model_validate_json((root / "fields" / field_id / "field.json").read_text(encoding="utf-8"))


# --- detector choice and target measurement ----------------------------------------------------------------


def test_detector_comes_from_the_thumbnail_note(tmp_path):
    field = _field(write_product(tmp_path))
    assert animate.choose_detector(field) == (5, "thumbnail detector")


def test_detector_falls_back_to_the_one_with_most_frames(tmp_path):
    field = _field(write_product(tmp_path, thumb_detector=None))
    assert animate.choose_detector(field) == (2, "detector with most frames")


def test_detector_override_wins_and_must_have_frames(tmp_path):
    field = _field(write_product(tmp_path))
    assert animate.choose_detector(field, override=1) == (1, "chosen by hand")
    with pytest.raises(ValueError, match="no published D4 frame"):
        animate.choose_detector(field, override=4)


def test_target_measured_to_a_fraction_of_a_pixel():
    grey = _star(CENTRE + 0.6, CENTRE - 0.4, peak=250, sigma=1.2)
    x, y = animate.measure_target(grey, np.ones_like(grey, bool))
    assert abs(x - (CENTRE + 0.6)) < 0.3 and abs(y - (CENTRE - 0.4)) < 0.3


def test_saturated_flat_core_is_measured_at_its_centre():
    grey = _star(CENTRE, CENTRE, peak=600, sigma=1.5)  # clipped to a 255 plateau
    x, y = animate.measure_target(grey, np.ones_like(grey, bool))
    assert abs(x - CENTRE) < 0.2 and abs(y - CENTRE) < 0.2


def test_target_that_does_not_stand_out_gets_no_position():
    grey = _star(CENTRE, CENTRE, peak=150)  # a field star at the centre, not as bright as the field's bright end
    assert animate.measure_target(grey, np.ones_like(grey, bool)) is None


# --- drawing helpers ---------------------------------------------------------------------------------------


def test_no_data_pixels_are_drawn_as_a_dark_checkerboard():
    grey = np.full((4, 4), 200, np.uint8)
    alpha = np.full((4, 4), 255, np.uint8)
    alpha[0, 0] = 0
    img, has_nodata = annotate.upscale_on_checker(Image.fromarray(np.dstack([grey, alpha]), "LA"), 6)
    assert has_nodata and img.size == (24, 24) and img.mode == "RGB"
    block = np.asarray(img)[:6, :6, 0]
    assert set(np.unique(block)) == set(annotate.CHECKER_LEVELS)
    assert np.all(np.asarray(img)[6:, 6:] == 200)


def test_opaque_image_reports_no_missing_data():
    img, has_nodata = annotate.upscale_on_checker(Image.fromarray(np.full((4, 4), 9, np.uint8)), 3)
    assert not has_nodata and img.size == (12, 12)


def test_gif_palette_never_turns_data_pixels_into_annotation_colours():
    near_amber = np.zeros((8, 8, 3), np.uint8)
    near_amber[...] = (250, 180, 70)
    near_amber[::2, ::2] = (5, 210, 250)  # and near the crosshair cyan
    (quantized,) = annotate.shared_palette([Image.fromarray(near_amber)])
    rgb = np.asarray(quantized.convert("RGB"))
    for colour in annotate.ANNOTATION_COLORS:
        assert not np.all(rgb == np.array(colour), axis=-1).any()
    assert np.abs(rgb.astype(int) - near_amber).max() <= 2


def test_drawn_annotation_colour_keeps_its_exact_palette_entry():
    grey = Image.fromarray(np.tile(np.arange(256, dtype=np.uint8), (64, 1))).convert("RGB")
    marked = annotate.draw_crosshair(grey, 100.0, 30.0, 1)
    (quantized,) = annotate.shared_palette([marked])
    rgb = np.asarray(quantized.convert("RGB"))
    assert (
        np.all(rgb == np.array(annotate.ACCENT), axis=-1).sum()
        == np.all(np.asarray(marked) == np.array(annotate.ACCENT), axis=-1).sum()
    )


def test_long_caption_lines_are_wrapped_to_the_width():
    font = annotate.font(14)
    lines = annotate.wrap("word " * 80, font, 200)
    assert len(lines) > 3 and all(font.getlength(line) <= 200 for line in lines)


# --- products ----------------------------------------------------------------------------------------------


def test_blink_gif_has_one_frame_per_detector_exposure_and_captions(tmp_path):
    root = write_product(tmp_path / "products")
    outs = animate.animate_field(root, "test-mover", tmp_path / "out")
    blink = next(o for o in outs if o.kind == "blink")
    assert blink.path.name == "test-mover_blink_D5.gif"
    with Image.open(blink.path) as im:
        assert im.n_frames == 3
        assert im.size[0] == N * animate.SCALE and im.size[1] > N * animate.SCALE
    assert all(500 <= d <= 800 for d in _durations(blink.path))
    text = _gif_comment(blink.path)
    for expected in (
        "Test Star-1",
        "D5",
        "4.30 µm",
        "UTC",
        "first-epoch position",
        "Checkerboard: no data",
        "real SPHEREx data",
        annotate.CREDIT,
    ):
        assert expected in text
    assert blink.frame_ids == ("2025W01_1A_0001_1D5", "2025W30_1A_0002_1D5", "2026W05_1A_0003_1D5")


def test_crosshair_stays_at_the_first_epoch_position(tmp_path):
    root = write_product(tmp_path / "products")
    blink = next(o for o in animate.animate_field(root, "test-mover", tmp_path / "out") if o.kind == "blink")
    s = animate.SCALE
    cx = round((CENTRE + 0.5) * s)
    with Image.open(blink.path) as im:
        for i in range(im.n_frames):
            im.seek(i)
            rgb = np.asarray(im.convert("RGB")).astype(int)
            column = rgb[: N * s, cx - 1 : cx + 1]
            accent = np.all(np.abs(column - np.array(annotate.ACCENT)) < 30, axis=-1)
            assert accent.sum() > 2 * s  # the vertical arms of the crosshair are there in every frame


def test_variable_field_has_no_crosshair_legend(tmp_path):
    root = write_product(tmp_path / "products", tags=("variable",))
    blink = next(o for o in animate.animate_field(root, "test-mover", tmp_path / "out") if o.kind == "blink")
    assert "crosshair" not in _gif_comment(blink.path).lower()


def test_target_that_does_not_stand_out_is_explained_instead_of_marked(tmp_path):
    root = write_product(tmp_path / "products")
    fdir = root / "fields" / "test-mover" / "frames"
    Image.fromarray(_star(CENTRE, CENTRE, peak=120)).save(fdir / "2025W01_1A_0001_1D5.png")
    blink = next(o for o in animate.animate_field(root, "test-mover", tmp_path / "out") if o.kind == "blink")
    text = _gif_comment(blink.path)
    assert "first-epoch position" not in text and "No crosshair" in text


def test_synthetic_product_is_never_captioned_as_real(tmp_path):
    root = write_product(tmp_path / "products", synthetic=True)
    for out in animate.animate_field(root, "test-mover", tmp_path / "out"):
        text = _gif_comment(out.path) if out.path.suffix == ".gif" else _png_description(out.path)
        assert "SYNTHETIC DATA" in text and "real SPHEREx" not in text and annotate.CREDIT not in text


def test_color_gifs_have_one_frame_per_season_and_channel_captions(tmp_path):
    root = write_product(tmp_path / "products")
    outs = {o.kind: o for o in animate.animate_field(root, "test-mover", tmp_path / "out")}
    det, jhk = outs["color_detectors"], outs["color_jhk"]
    assert det.path.name == "test-mover_color_detectors.gif" and jhk.path.name == "test-mover_color_jhk.gif"
    with Image.open(det.path) as im:
        assert im.n_frames == 2
    with Image.open(jhk.path) as im:
        assert im.n_frames == 1
    text = _gif_comment(det.path)
    for expected in ("False color (infrared)", "red = D6 4.60 µm", "green = D3 1.80 µm", "blue = D1 0.90 µm"):
        assert expected in text
    assert "season S0: 2025-" in text or "season S0: 2026-" in text
    assert "J/H/Ks-like: red = D3 2.17 µm, green = 1.65 µm (several detectors)" in _gif_comment(jhk.path)


def test_contact_sheet_is_a_png_with_every_mode(tmp_path):
    root = write_product(tmp_path / "products")
    sheet = next(o for o in animate.animate_field(root, "test-mover", tmp_path / "out") if o.kind == "contact_sheet")
    assert sheet.path.name == "test-mover_contact_sheet.png"
    text = _png_description(sheet.path)
    assert "Blink frames" in text and "full-range detectors" in text and "J/H/Ks-like" in text
    assert annotate.CREDIT in text
    with Image.open(sheet.path) as im:
        assert im.mode == "RGB" and im.size[0] > N * animate.SHEET_SCALE


def test_comparison_uses_the_preferred_pair_when_published(tmp_path, monkeypatch):
    monkeypatch.setitem(animate.COMPARISON_PAIRS, "test-var", ("2025W01_1A_0008_1D1", "2026W05_1A_0010_1D1"))
    root = write_product(tmp_path / "products", field_id="test-var", tags=("variable",))
    outs = {o.kind: o for o in animate.animate_field(root, "test-var", tmp_path / "out")}
    still, gif = outs["comparison_png"], outs["comparison_gif"]
    assert still.frame_ids == gif.frame_ids == ("2025W01_1A_0008_1D1", "2026W05_1A_0010_1D1")
    with Image.open(gif.path) as im:
        assert im.n_frames == 2
    with Image.open(still.path) as im:
        assert im.size[0] > 2 * N * animate.SCALE
    text = _png_description(still.path)
    assert "0.764 µm" in text and "0.771 µm" in text and "2025-" in text and "2026-" in text
    assert "Amber ticks: field centre" in text
    with Image.open(still.path) as im:
        rgb = np.asarray(im.convert("RGB")).astype(int)
    assert np.all(np.abs(rgb - np.array(annotate.CENTRE_TICK)) < 30, axis=-1).sum() > 4 * animate.SCALE


def test_comparison_falls_back_to_the_closest_wavelength_pair_across_seasons(tmp_path, monkeypatch):
    monkeypatch.setitem(animate.COMPARISON_PAIRS, "test-var", ("2025W01_1A_0008_1D1", "missing_D1"))
    root = write_product(tmp_path / "products", field_id="test-var", tags=("variable",))
    first, second = animate.comparison_pair(_field(root, "test-var"), root / "fields" / "test-var")
    assert (first.id, second.id) == ("2025W01_1A_0008_1D1", "2026W05_1A_0010_1D1")


def test_fields_without_a_comparison_entry_get_none(tmp_path):
    root = write_product(tmp_path / "products")
    kinds = {o.kind for o in animate.animate_field(root, "test-mover", tmp_path / "out")}
    assert kinds == {"blink", "color_detectors", "color_jhk", "contact_sheet"}


def test_cli_writes_every_file_under_the_size_limit_and_a_manifest(tmp_path):
    root = write_product(tmp_path / "products")
    out = tmp_path / "out"
    assert animate.main(["--products", str(root), "--out", str(out)]) == 0
    manifest = json.loads((out / "animations.json").read_text(encoding="utf-8"))
    files = [entry["file"] for entry in manifest["outputs"]]
    assert "test-mover_blink_D5.gif" in files and "test-mover_contact_sheet.png" in files
    for entry in manifest["outputs"]:
        path = out / entry["file"]
        assert path.stat().st_size == entry["size_bytes"] < animate.MAX_BYTES
        assert entry["caption"]


def test_cli_reports_an_unknown_field(tmp_path, capsys):
    root = write_product(tmp_path / "products")
    assert animate.main(["--products", str(root), "--out", str(tmp_path / "out"), "--field", "nope"]) == 1
    assert "nope" in capsys.readouterr().err


def _manifest_files(out: Path) -> list[str]:
    return [e["file"] for e in json.loads((out / "animations.json").read_text(encoding="utf-8"))["outputs"]]


def test_regenerated_field_drops_its_old_manifest_entries(tmp_path):
    root = write_product(tmp_path / "products")
    write_product(root, field_id="other-star", tags=("variable",))
    out = tmp_path / "out"
    assert animate.main(["--products", str(root), "--out", str(out)]) == 0
    assert animate.main(["--products", str(root), "--out", str(out), "--field", "test-mover", "--detector", "2"]) == 0
    files = _manifest_files(out)
    assert "test-mover_blink_D2.gif" in files and "test-mover_blink_D5.gif" not in files  # not rewritten: dropped
    assert "other-star_blink_D5.gif" in files and "other-star_contact_sheet.png" in files  # other field: kept
    assert len(files) == len(set(files))
    assert len([f for f in files if f.startswith("test-mover_")]) == 4  # exactly this run's outputs


def test_manifest_drops_entries_of_other_fields_whose_file_is_gone(tmp_path):
    root = write_product(tmp_path / "products")
    write_product(root, field_id="other-star", tags=("variable",))
    out = tmp_path / "out"
    assert animate.main(["--products", str(root), "--out", str(out)]) == 0
    (out / "other-star_color_jhk.gif").unlink()
    assert animate.main(["--products", str(root), "--out", str(out), "--field", "test-mover"]) == 0
    files = _manifest_files(out)
    assert "other-star_color_jhk.gif" not in files and "other-star_blink_D5.gif" in files


# --- stretch wording and per-field detector ----------------------------------------------------------------


def test_rolloff_detector_is_captioned_as_compressed_highlights(tmp_path):
    root = write_product(tmp_path / "products", rolloff=(2, 5))
    assert animate.rolloff_detectors(_field(root)) == {2, 5}
    blink = next(o for o in animate.animate_field(root, "test-mover", tmp_path / "out") if o.kind == "blink")
    assert "asinh stretch, highlights compressed above vmax, same contrast" in _gif_comment(blink.path)


def test_plain_stretch_caption_without_a_rolloff(tmp_path):
    root = write_product(tmp_path / "products", rolloff=(2,))
    blink = next(o for o in animate.animate_field(root, "test-mover", tmp_path / "out") if o.kind == "blink")
    text = _gif_comment(blink.path)
    assert "IMAGE - ZODI, asinh stretch, same contrast" in text and "highlights compressed" not in text


def test_comparison_and_sheet_name_the_stretch_of_each_detector(tmp_path, monkeypatch):
    monkeypatch.setitem(animate.COMPARISON_PAIRS, "test-var", ("2025W01_1A_0008_1D1", "2026W05_1A_0010_1D1"))
    root = write_product(tmp_path / "products", field_id="test-var", tags=("variable",), rolloff=(1,))
    outs = {o.kind: o for o in animate.animate_field(root, "test-var", tmp_path / "out")}
    assert "IMAGE - ZODI, asinh stretch, highlights compressed above vmax" in _png_description(
        outs["comparison_png"].path
    )
    assert "highlights compressed above vmax" in _gif_comment(outs["comparison_gif"].path)
    assert "highlights compressed" not in _gif_comment(outs["blink"].path)  # D5: plain
    sheet = _png_description(outs["contact_sheet"].path)
    assert "(D1: asinh stretch, highlights compressed above vmax; D5: asinh stretch)" in sheet


def test_field_default_detector_comes_before_the_thumbnail(tmp_path, monkeypatch):
    default = animate.DetectorDefault(2, "where the target emits", ("The target is faint in D2.",))
    monkeypatch.setitem(animate.FIELD_DETECTORS, "test-mover", default)
    root = write_product(tmp_path / "products")
    assert animate.choose_detector(_field(root)) == (2, "where the target emits")
    assert animate.choose_detector(_field(root), override=5) == (5, "chosen by hand")
    outs = {o.kind: o for o in animate.animate_field(root, "test-mover", tmp_path / "out")}
    assert outs["blink"].path.name == "test-mover_blink_D2.gif"
    assert "The target is faint in D2." in _gif_comment(outs["blink"].path)
    sheet = _png_description(outs["contact_sheet"].path)
    assert "where the target emits" in sheet and "The target is faint in D2." in sheet


def test_field_default_notes_only_caption_a_blink_of_that_detector(tmp_path, monkeypatch):
    default = animate.DetectorDefault(2, "where the target emits", ("The target is faint in D2.",))
    monkeypatch.setitem(animate.FIELD_DETECTORS, "test-mover", default)
    root = write_product(tmp_path / "products")
    blink = next(o for o in animate.animate_field(root, "test-mover", tmp_path / "out", 5) if o.kind == "blink")
    assert "faint in D2" not in _gif_comment(blink.path)


def test_field_default_without_frames_falls_back_to_the_thumbnail(tmp_path, monkeypatch):
    monkeypatch.setitem(animate.FIELD_DETECTORS, "test-mover", animate.DetectorDefault(4, "x", ()))
    assert animate.choose_detector(_field(write_product(tmp_path))) == (5, "thumbnail detector")


def test_wise_0855_blinks_in_d5_and_says_it_is_faint():
    default = animate.FIELD_DETECTORS["wise-0855"]
    assert default.detector == 5
    assert any("2-5 sigma" in line and "single published frame" in line for line in default.notes)
