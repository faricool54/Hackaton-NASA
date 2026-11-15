# The testing stage of a video: checks that every piece the montage needs is there and
# consistent with the script, and that the rendered video matches the narration. Run it
# after any change and before telling the user a video is ready.
#
#   python verificar.py <video> [--placeholder] [--out file.mp4]
#
# --placeholder   a take not recorded yet is a warning instead of an error (draft montage).
# Exits 1 when there is any error; warnings are reported for the user to decide.

import json
import re
import subprocess
import sys
from fractions import Fraction
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import guion
from course import Course
import delivery

MAX_STILL_S = 13.0          # golden rule: no still on screen longer than this
DURATION_TOLERANCE_S = 0.5  # montage length vs measured narration
TRIM_TOLERANCE_S = 0.3      # the same tolerance montar.py warns with
SCRIPT_EDIT_GRACE_S = 5.0   # locutor.py --sync rewrites the script right after timings.json

DURATION_RE = re.compile(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)")
VIDEO_RE = re.compile(r"Video:.*?,\s*(\d{2,5})x(\d{2,5})[\s,\[].*?,\s*(\d+(?:\.\d+)?)\s*fps")


@dataclass
class Finding:
    level: str      # "error" | "warning"
    message: str


def probe(path):
    """Duration (s), width, height and fps of a media file, read from ffmpeg's banner."""
    import imageio_ffmpeg
    err = subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-i", str(path)], capture_output=True).stderr
    return parse_probe(err.decode("utf-8", "replace"))


def parse_probe(text):
    info = {"duration": None, "width": None, "height": None, "fps": None}
    m = DURATION_RE.search(text)
    if m:
        info["duration"] = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))
    m = VIDEO_RE.search(text)
    if m:
        info["width"], info["height"], info["fps"] = int(m.group(1)), int(m.group(2)), float(m.group(3))
    return info


def long_stills(rows, trows, limit=MAX_STILL_S):
    """[(first_row, last_row, slide, seconds)] for slides held past the limit, joining
    consecutive rows that show the same slide, since on screen they are one still."""
    out, run = [], None
    for row, t in zip(rows, trows):
        ref = row.visual.ref if row.visual.kind == "slide" else None
        if run and ref is not None and ref == run[2]:
            run = (run[0], row.num, ref, run[3] + t["visual_dur"])
            continue
        if run and run[3] > limit:
            out.append(run)
        run = (row.num, row.num, ref, t["visual_dur"]) if ref is not None else None
    if run and run[3] > limit:
        out.append(run)
    return [(a, b, ref, round(s, 2)) for a, b, ref, s in out]


def check(video_dir, course, placeholder=False, out=None, final=None):
    """All findings for one video, in pipeline order."""
    found = []
    error = lambda msg: found.append(Finding("error", msg))
    warn = lambda msg: found.append(Finding("warning", msg))
    cfg = course["delivery"]
    final = cfg["final"] if final is None else final
    if final and placeholder:
        error("final delivery cannot use --placeholder; use --draft to review a draft")
    if final and cfg["required_language"]:
        if not course["language"].startswith(cfg["required_language"]):
            error(f"delivery requires narration in {cfg['required_language']}")
        if cfg["required_language"] == "en" and not delivery.is_english_voice(course.voice["name"], course.voice["engine"]):
            error("delivery requires an English narration voice in course.yaml")
    if final and cfg["require_identity"]:
        for key in ("team", "members", "challenge"):
            value = cfg[key]
            values = value if isinstance(value, list) else [value]
            if not values or any(not str(v).strip() or re.search(r"TODO|\[.*\]|<.*>", str(v), re.I) for v in values):
                error(f"delivery.{key} must contain confirmed names, with no placeholders")
    if final and course.voice["engine"] != "human" and not cfg["ai_audio_credit"].strip():
        error("delivery.ai_audio_credit is required for synthetic narration")

    try:
        guion_path = guion.find_vigente(video_dir)
        rows = guion.parse_montage(guion_path)
    except SystemExit as e:
        error(f"script: {e}")
        return found

    for row in rows:
        v = row.visual
        if v.kind == "slide":
            slide = video_dir / "assets" / "slides" / f"slide-{int(v.ref):02d}.png"
            if not slide.exists():
                error(f"row {row.num}: slide-{int(v.ref):02d}.png missing (run slides.py)")
            elif final and (video_dir / "presentacion.html").exists() and (
                    video_dir / "presentacion.html").stat().st_mtime > slide.stat().st_mtime:
                error(f"row {row.num}: slide export is older than the deck; run slides.py again")
        elif not (video_dir / "grabaciones" / f"{v.ref}.mp4").exists():
            (warn if placeholder else error)(f"row {row.num}: take {v.ref} not recorded")

    timings_path = video_dir / "locucion" / "timings.json"
    if not timings_path.exists():
        error("narration: timings.json missing (run locutor.py)")
        return found
    data = json.loads(timings_path.read_text(encoding="utf-8"))
    trows = data["rows"]
    if [r.num for r in rows] != [t["row"] for t in trows]:
        error("narration: the script's rows changed since locutor.py ran; generate it again")
        return found
    rate = guion.video_rate(guion_path, course.voice["rate"])
    audio = video_dir / "locucion" / "locucion.wav"
    if not audio.is_file():
        error("narration: locucion.wav missing (run locutor.py)")
    if final:
        if data.get("source_signature") != delivery.narration_signature(rows, course, rate):
            error("narration: text, voice or pacing changed; regenerate with locutor.py")
        if audio.is_file() and data.get("audio_sha256") != delivery.sha256(audio):
            error("narration: audio changed since locutor.py ran; regenerate it")
    if data.get("rate") not in (None, rate):
        error(f"narration: generated at {data['rate']}, the script asks for {rate}; generate it again")
    if guion_path.stat().st_mtime > timings_path.stat().st_mtime + SCRIPT_EDIT_GRACE_S:
        warn("narration: the script was edited after locutor.py ran; regenerate it if a line changed")

    for first, last, ref, seconds in long_stills(rows, trows):
        span = f"row {first}" if first == last else f"rows {first}-{last}"
        warn(f"{span}: slide {ref} stays {seconds:.1f} s on screen (over {MAX_STILL_S:.0f} s); "
             "split the row or cut to a take")

    for row, t in zip(rows, trows):
        v = row.visual
        take = video_dir / "grabaciones" / f"{v.ref}.mp4"
        if v.kind != "demo" or not take.exists():
            continue
        start = v.trim[0] if v.trim else 0.0
        if v.trim and abs((v.trim[1] - v.trim[0]) - t["visual_dur"]) > TRIM_TOLERANCE_S:
            warn(f"row {row.num}: trim of {v.ref} lasts {v.trim[1] - v.trim[0]:.1f} s, "
                 f"the row {t['visual_dur']:.1f} s")
        length = probe(take)["duration"] or 0.0
        if length < start + t["visual_dur"] - TRIM_TOLERANCE_S:
            (error if final else warn)(f"row {row.num}: take {v.ref} is {length:.1f} s and the row needs it until "
                 f"{start + t['visual_dur']:.1f} s; its last frame will be held")

    video = Path(out) if out else course.publish_dir / video_dir.name / f"{video_dir.name}.mp4"
    if not video.exists():
        (error if final else warn)(f"montage: {video.name} not built yet (run montar.py)")
        return found
    info = probe(video)
    if info["duration"] is None or abs(info["duration"] - data["total"]) > DURATION_TOLERANCE_S:
        error(f"montage: {video.name} lasts {info['duration']} s, the narration {data['total']:.1f} s")
    if (info["width"], info["height"]) != (course.width, course.height):
        error(f"montage: {info['width']}x{info['height']}, the course is {course.width}x{course.height}")
    if info["fps"] is None or abs(info["fps"] - course.fps) > 0.01:
        error(f"montage: {info['fps']} fps, the course is {course.fps}")
    if cfg["max_duration_seconds"] is not None:
        try:
            limit = Fraction(str(cfg["max_duration_seconds"]))
            if limit <= 0:
                raise ValueError("duration limit must be positive")
            exact = delivery.mp4_duration(video)
            if exact > limit:
                error(f"montage: {float(exact):.6f} s exceeds the strict {float(limit):g} s limit; "
                      "shorten the script, pauses or shots; do not cut off speech")
            elif cfg["target_duration_seconds"] is not None and exact > Fraction(str(cfg["target_duration_seconds"])):
                warn(f"montage: {float(exact):.3f} s is within the limit but above the target margin")
        except (OSError, ValueError, ZeroDivisionError) as exc:
            error(f"montage: cannot verify exact duration: {exc}")
    if final:
        for message in delivery.manifest_errors(video, video_dir, course, rows):
            error(f"final: {message}")
        description_path = video.parent / "descripcion.md"
        description = description_path.read_text(encoding="utf-8") if description_path.is_file() else ""
        required = [*cfg["credits"]]
        if course.voice["engine"] != "human":
            required.append(cfg["ai_audio_credit"])
        if not description:
            error("final: descripcion.md missing next to the video")
        elif any(credit not in description for credit in required):
            error("final: source/AI credits missing from descripcion.md")
        try:
            tags = read_metadata(video)
            for key, value in delivery.metadata(course).items():
                if tags.get(key) != value:
                    error(f"final: required {key} metadata missing or incorrect")
        except (OSError, ValueError, subprocess.CalledProcessError) as exc:
            error(f"final: cannot read MP4 metadata: {exc}")
    inputs = [timings_path, *(video_dir / "assets" / "slides").glob("slide-*.png"),
              *(video_dir / "grabaciones").glob("*.mp4")]
    newer = sorted(p.name for p in inputs if p.stat().st_mtime > video.stat().st_mtime)
    if newer:
        (error if final else warn)(f"montage: older than {', '.join(newer)}; rebuild it with montar.py")
    return found


def read_metadata(path):
    """Read actual container tags, including multiline credits, through bundled FFmpeg."""
    import imageio_ffmpeg
    result = subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-v", "error", "-i", str(path),
                             "-f", "ffmetadata", "-"], capture_output=True, check=True)
    raw = result.stdout.decode("utf-8")
    # A backslash escapes a newline in the FFmetadata format.
    lines = re.split(r"(?<!\\)\n", raw)
    tags = {}
    for line in lines:
        if line.startswith("["):
            break  # only global/container tags
        if not line or line.startswith((";", "#")) or "=" not in line:
            continue
        key, value = re.split(r"(?<!\\)=", line, maxsplit=1)
        tags[key.lower()] = re.sub(r"\\(.)", r"\1", value, flags=re.DOTALL).strip()
    return tags


def main(argv=None):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    args = sys.argv[1:] if argv is None else argv
    if not args or args[0].startswith("--"):
        raise SystemExit("usage: verificar.py <video> [--final | --draft] [--placeholder] [--out file.mp4]")
    course = Course.load(args[0])
    video_dir = course.resolve_video(args[0])
    if "--final" in args and "--draft" in args:
        raise SystemExit("choose --final or --draft")
    final = True if "--final" in args else False if "--draft" in args else None
    found = check(video_dir, course, "--placeholder" in args, guion.flag_value(args, "--out"), final)
    for f in found:
        print(f"{f.level.upper():7} {f.message}")
    errors = sum(f.level == "error" for f in found)
    warnings = len(found) - errors
    print(f"{'FAILED' if errors else 'OK'}  {video_dir.name}: {errors} errors, {warnings} warnings")
    if errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
