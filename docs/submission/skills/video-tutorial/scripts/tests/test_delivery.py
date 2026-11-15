"""Strict delivery boundaries, real muxed metadata and changed-input regressions."""
import json
import struct
import sys
from fractions import Fraction
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import delivery
import guion
import locutor
import montar
import scaffold
import verificar
from course import Course


def update_config(video, **updates):
    path = video.parent.parent / "course.yaml"
    cfg = yaml.safe_load(path.read_text(encoding="utf-8"))
    cfg.update(updates)
    path.write_text(yaml.safe_dump(cfg), encoding="utf-8")


@pytest.fixture
def final_video(course):
    video, _ = course
    update_config(video, name="Demo", language="en", voice={"name": "en-US-JennyNeural"}, delivery={
        "final": True, "max_duration_seconds": 30, "target_duration_seconds": 29,
        "required_language": "en", "require_identity": True,
        "team": "Test team", "members": ["Test person"], "challenge": "Planet X and SPHEREx",
        "description": "Test demo of real observations.", "credits": ["Data: NASA SPHEREx / IRSA."],
        "ai_audio_credit": "AI-generated narration: Microsoft Edge TTS.",
        "metadata": {"title": "Test demo", "artist": "Test team"},
    })
    script = video / "guion-v1.md"
    script.write_text(script.read_text(encoding="utf-8").replace("Hola, este es el curso.", "Meet the demo.")
                      .replace("Empezamos.", "Start here.").replace("Y esta es la toma.", "Real observations."), encoding="utf-8")
    locutor.main([str(video), "--sync"])
    from PIL import Image
    slides = video / "assets/slides"
    slides.mkdir(parents=True)
    Image.new("RGB", (640, 360), "white").save(slides / "slide-01.png")
    (video / "grabaciones").mkdir()
    montar.run([montar.ffmpeg_exe(), "-y", "-f", "lavfi", "-i", "color=c=blue:s=640x360:r=30:d=4",
                "-pix_fmt", "yuv420p", str(video / "grabaciones/D1.mp4")])
    return video


def output(video):
    return video.parent.parent / "export" / video.name / f"{video.name}.mp4"


def errors(video, **kwargs):
    return [f.message for f in verificar.check(video, Course.load(video), **kwargs) if f.level == "error"]


def movie(path, milliseconds, version=0, track_ms=None, mdat=b""):
    def atom(kind, payload):
        return struct.pack(">I4s", 8 + len(payload), kind) + payload
    prefix = bytes([version, 0, 0, 0])
    if version:
        mvhd = prefix + bytes(16) + struct.pack(">IQ", 1000, milliseconds)
        tkhd = prefix + bytes(24) + struct.pack(">Q", track_ms or milliseconds)
    else:
        mvhd = prefix + bytes(8) + struct.pack(">II", 1000, milliseconds)
        tkhd = prefix + bytes(16) + struct.pack(">I", track_ms or milliseconds)
    path.write_bytes(atom(b"mdat", mdat) + atom(b"moov", atom(b"mvhd", mvhd)
                                              + atom(b"trak", atom(b"tkhd", tkhd))))


@pytest.mark.parametrize("version", [0, 1])
def test_exact_duration_catches_one_millisecond_over_and_longer_track(tmp_path, version):
    path = tmp_path / "edge.mp4"
    movie(path, 30000, version, track_ms=30001, mdat=b"irrelevant payload")
    assert delivery.mp4_duration(path) == Fraction(30001, 1000)
    movie(path, 30000, version)
    assert delivery.mp4_duration(path) == 30


@pytest.mark.parametrize("data", [b"", b"broken", struct.pack(">I4s", 100, b"moov")])
def test_unknown_or_corrupt_duration_never_passes(tmp_path, data):
    path = tmp_path / "broken.mp4"
    path.write_bytes(data)
    with pytest.raises(ValueError):
        delivery.mp4_duration(path)


def test_final_build_embeds_credits_and_english_and_verifies(final_video):
    video = final_video
    montar.main([str(video)])
    assert errors(video) == []
    tags = verificar.read_metadata(output(video))
    assert tags["language"] == "eng"
    assert "NASA SPHEREx" in tags["comment"] and "AI-generated narration" in tags["comment"]
    assert delivery.mp4_duration(output(video)) < 30
    description = (output(video).parent / "descripcion.md").read_text(encoding="utf-8")
    assert "AI-generated narration" in description and "Test person" in description


def test_final_rejects_missing_output_and_placeholder_mode(final_video):
    assert any("not built yet" in e for e in errors(final_video))
    with pytest.raises(SystemExit, match="cannot use --placeholder"):
        montar.main([str(final_video), "--placeholder"])
    assert any("cannot use --placeholder" in e for e in errors(final_video, placeholder=True))


def test_30_second_limit_has_no_alignment_tolerance(final_video, monkeypatch, tmp_path):
    out = tmp_path / "30.001.mp4"
    movie(out, 30001)
    monkeypatch.setattr(verificar, "probe", lambda _: {"duration": 30.0, "width": 640, "height": 360, "fps": 30.0})
    assert any("strict 30 s limit" in e for e in errors(final_video, out=out, final=False))
    movie(out, 30000)
    assert not any("strict 30 s limit" in e for e in errors(final_video, out=out, final=False))


def test_actual_mp4_over_limit_is_rejected_even_with_longer_audio(final_video, tmp_path):
    out = tmp_path / "long-audio.mp4"
    montar.run([montar.ffmpeg_exe(), "-y", "-f", "lavfi", "-i", "color=s=160x90:r=30:d=29",
                "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo:d=30.01",
                "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
                "-c:a", "aac", str(out)])
    assert delivery.mp4_duration(out) > 30
    assert any("strict 30 s limit" in e for e in errors(final_video, out=out, final=False))


def test_placeholder_build_cannot_be_approved_as_final_later(final_video):
    montar.main([str(final_video), "--draft", "--placeholder"])
    assert any("built in placeholder mode" in e for e in errors(final_video))


def test_actual_metadata_removal_is_detected(final_video, tmp_path):
    montar.main([str(final_video)])
    stripped = tmp_path / "no-tags.mp4"
    montar.run([montar.ffmpeg_exe(), "-y", "-i", str(output(final_video)),
                "-map_metadata", "-1", "-c", "copy", str(stripped)])
    assert any("metadata missing or incorrect" in e for e in errors(final_video, out=stripped))


def test_build_manifest_catches_content_changes_even_with_preserved_timestamp(final_video):
    import os
    video = final_video
    montar.main([str(video)])
    take = video / "grabaciones/D1.mp4"
    stat = take.stat()
    with take.open("ab") as stream:
        stream.write(b"changed")
    os.utime(take, ns=(stat.st_atime_ns, stat.st_mtime_ns))
    assert any("inputs changed" in e for e in errors(video))


def test_changed_narration_requires_regeneration_before_mounting(final_video):
    video = final_video
    script = video / "guion-v1.md"
    script.write_text(script.read_text(encoding="utf-8").replace("Real observations.", "A different claim."), encoding="utf-8")
    with pytest.raises(SystemExit, match="regenerate with locutor.py"):
        montar.main([str(video)])


def test_final_rejects_missing_credits_metadata_and_wrong_language(final_video):
    video = final_video
    montar.main([str(video)])
    (output(video).parent / "descripcion.md").write_text("No credits here.", encoding="utf-8")
    assert any("credits missing" in e for e in errors(video))
    cfg = Course.load(video).data
    cfg["voice"]["name"] = "es-MX-DaliaNeural"
    cfg["delivery"]["members"] = []
    cfg["delivery"]["ai_audio_credit"] = ""
    (video.parent.parent / "course.yaml").write_text(yaml.safe_dump(cfg), encoding="utf-8")
    found = errors(video)
    assert any("English narration voice" in e for e in found)
    assert any("delivery.members" in e for e in found)
    assert any("ai_audio_credit is required" in e for e in found)


def test_stale_deck_must_be_exported_again(final_video):
    import os
    deck = final_video / "presentacion.html"
    slide = final_video / "assets/slides/slide-01.png"
    os.utime(deck, (slide.stat().st_mtime + 1, slide.stat().st_mtime + 1))
    assert any("slide export is older" in e for e in errors(final_video))


def test_final_rejects_a_take_that_would_freeze_to_fill_the_shot(final_video):
    montar.run([montar.ffmpeg_exe(), "-y", "-f", "lavfi", "-i", "color=s=640x360:r=30:d=0.1",
                "-pix_fmt", "yuv420p", str(final_video / "grabaciones/D1.mp4")])
    assert any("last frame will be held" in e for e in errors(final_video))


def test_demo_scaffold_uses_real_english_profile_and_preserves_existing_course(tmp_path):
    root = tmp_path / "demo"
    scaffold.demo(root, "https://demo.example")
    course = Course.load(root)
    video = course.production_dir / "01 - Errante demo"
    assert course["language"] == "en" and course.voice["name"].startswith("en-")
    assert course["delivery"]["max_duration_seconds"] == 30 and course["delivery"]["final"]
    assert len(guion.parse_montage(guion.find_vigente(video))) == 5
    assert course.recording["base_url"] == "https://demo.example"
    assert any("delivery.members" in e for e in errors(video))
    cfg = course.data
    cfg["delivery"].update(team="Team <One>", members=["Ada & Bob"])
    (root / "course.yaml").write_text(yaml.safe_dump(cfg), encoding="utf-8")
    scaffold.demo_cards(video)
    card = (video / "presentacion.html").read_text(encoding="utf-8")
    assert "Team &lt;One&gt;" in card and "Ada &amp; Bob" in card and "AI-generated English" in card
    before = (root / "course.yaml").read_bytes()
    with pytest.raises(SystemExit, match="already exists"):
        scaffold.demo(root)
    assert (root / "course.yaml").read_bytes() == before
