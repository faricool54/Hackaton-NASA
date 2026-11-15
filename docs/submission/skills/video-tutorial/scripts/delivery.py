"""Delivery limits, narration provenance and reproducible montage manifests.

MP4 movie/track presentation durations are rational values, not FFmpeg's rounded
banner. Reading only atom headers avoids loading large mdat payloads into memory.
"""
import hashlib
import json
import struct
from fractions import Fraction
from pathlib import Path


def sha256(path):
    with Path(path).open("rb") as src:
        return hashlib.file_digest(src, "sha256").hexdigest()


def mp4_duration(path):
    """Exact maximum movie/track presentation duration. Reject unknown/corrupt MP4s."""
    durations = []
    with Path(path).open("rb") as src:
        def boxes(start, end):
            pos = start
            while pos < end:
                src.seek(pos)
                head = src.read(8)
                if len(head) != 8:
                    raise ValueError("truncated MP4 atom")
                size, kind = struct.unpack(">I4s", head)
                header = 8
                if size == 1:
                    extended = src.read(8)
                    if len(extended) != 8:
                        raise ValueError("truncated extended MP4 atom")
                    size, header = struct.unpack(">Q", extended)[0], 16
                elif size == 0:
                    size = end - pos
                if size < header or pos + size > end:
                    raise ValueError("invalid MP4 atom size")
                yield kind, pos + header, pos + size
                pos += size

        def header_duration(start, end, track=False):
            src.seek(start)
            data = src.read(min(40, end - start))
            if not data or data[0] not in (0, 1):
                raise ValueError("unknown MP4 timing header")
            version = data[0]
            offset = (28 if version else 20) if track else (20 if version else 12)
            count = 8 if version else 4
            need = offset + count if track else offset + 4 + count
            if len(data) < need:
                raise ValueError("truncated MP4 timing header")
            if track:
                return int.from_bytes(data[offset:offset + count], "big")
            scale = int.from_bytes(data[offset:offset + 4], "big")
            ticks = int.from_bytes(data[offset + 4:offset + 4 + count], "big")
            if not scale or ticks == (1 << (count * 8)) - 1:
                raise ValueError("unknown MP4 duration")
            return scale, ticks

        for kind, start, end in boxes(0, Path(path).stat().st_size):
            if kind != b"moov":
                continue
            movie = list(boxes(start, end))
            mvhd = next(((a, b) for k, a, b in movie if k == b"mvhd"), None)
            if mvhd is None:
                raise ValueError("MP4 movie has no timing header")
            scale, ticks = header_duration(*mvhd)
            durations.append(Fraction(ticks, scale))
            for k, a, b in movie:
                if k == b"trak":
                    for child, c, d in boxes(a, b):
                        if child == b"tkhd":
                            durations.append(Fraction(header_duration(c, d, track=True), scale))
    if not durations or max(durations) <= 0:
        raise ValueError("no positive MP4 presentation duration")
    return max(durations)


def narration_signature(rows, course, rate=None, voice_name=None):
    voice = course.voice
    payload = {
        "rows": [(r.num, r.locucion) for r in rows],
        "language": course["language"], "engine": voice["engine"],
        "voice": voice_name or voice["name"], "rate": rate or voice["rate"],
        "pitch": voice["pitch"], "pronunciation": voice["pronunciation"], "pacing": voice["pacing"],
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def is_english_voice(name, engine):
    return engine == "human" or name.lower().startswith(("en-", "af_", "am_", "bf_", "bm_"))


def metadata(course):
    cfg = course["delivery"]
    tags = dict(cfg["metadata"])
    credits = list(cfg["credits"])
    if course.voice["engine"] != "human" and cfg["ai_audio_credit"]:
        credits.append(cfg["ai_audio_credit"])
    tags["comment"] = "\n".join(filter(None, [tags.get("comment", ""), *credits]))
    tags["language"] = "eng" if course["language"].startswith("en") else course["language"]
    return {k: str(v) for k, v in tags.items() if str(v).strip()}


def description(course):
    cfg = course["delivery"]
    credits = list(cfg["credits"])
    if course.voice["engine"] != "human" and cfg["ai_audio_credit"]:
        credits.append(cfg["ai_audio_credit"])
    return (f"# {course['name']}\n\n{cfg['description']}\n\n"
            f"Team: {cfg['team']}\n\nMembers: {', '.join(cfg['members'])}\n\n"
            f"Challenge: {cfg['challenge']}\n\nApp: {course.recording['base_url']}\n\n"
            + "\n".join(f"- {c}" for c in credits) + "\n")


def build_inputs(video_dir, course, rows):
    import guion
    paths = [course.root / "course.yaml", guion.find_vigente(video_dir),
             video_dir / "locucion/timings.json", video_dir / "locucion/locucion.wav"]
    paths += [p for p in (video_dir / "presentacion.html", video_dir / "tomas.py") if p.exists()]
    for row in rows:
        v = row.visual
        paths.append(video_dir / (f"assets/slides/slide-{int(v.ref):02d}.png" if v.kind == "slide"
                                  else f"grabaciones/{v.ref}.mp4"))
    return {str(p.resolve()): sha256(p) for p in paths if p.is_file()}


def manifest_path(out):
    return Path(out).with_suffix(".manifest.json")


def write_manifest(out, inputs, placeholder):
    manifest_path(out).write_text(json.dumps({
        "version": 1, "placeholder": placeholder, "output_sha256": sha256(out), "inputs": inputs,
    }, indent=2), encoding="utf-8")


def manifest_errors(out, video_dir, course, rows):
    path = manifest_path(out)
    if not path.exists():
        return ["build manifest missing; rebuild with montar.py"]
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return ["invalid build manifest; rebuild with montar.py"]
        errors = []
        if data.get("version") != 1:
            errors.append("unknown build manifest version")
        if data.get("placeholder"):
            errors.append("montage was built in placeholder mode; rebuild without --placeholder")
        if data.get("output_sha256") != sha256(out):
            errors.append("montage changed after building; rebuild")
        current = build_inputs(video_dir, course, rows)
        if data.get("inputs") != current:
            errors.append("montage inputs changed after building; rebuild")
        return errors
    except (OSError, ValueError, TypeError):
        return ["invalid build manifest; rebuild with montar.py"]
