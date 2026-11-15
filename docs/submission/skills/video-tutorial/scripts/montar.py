# Assembles the final video: one segment per montage row -- an exported slide (with a slow
# zoom only when its visual cell says "zoom"), a demo take, or a placeholder card -- cut to
# the durations measured by locutor.py, then muxed with the narration.
#
#   python montar.py <video> [--out file.mp4] [--placeholder]
#
# --placeholder   renders a card for each missing demo take, so a draft can be reviewed
#                 before recording them. Default output: <publish>/<video>/<video>.mp4.

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import guion
import delivery
from course import Course

X264 = ["-c:v", "libx264", "-preset", "medium", "-crf", "17", "-an"]
ZOOM_RATE = 0.00040           # zoom increment per frame, for rows whose visual cell says "zoom"
ZOOM_MAX = 1.12
PLACEHOLDER_TEXT = {"es": ("Toma {ref}", "pendiente de grabar"), "en": ("Take {ref}", "not recorded yet")}
FONT_CANDIDATES = {
    "bold": [r"C:\Windows\Fonts\segoeuib.ttf", "/System/Library/Fonts/Helvetica.ttc",
             "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"],
    "regular": [r"C:\Windows\Fonts\segoeui.ttf", "/System/Library/Fonts/Helvetica.ttc",
                "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"],
}


def ffmpeg_exe():
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()


def run(cmd):
    import subprocess
    r = subprocess.run(cmd, capture_output=True)
    if r.returncode != 0:
        raise SystemExit("ffmpeg failed:\n" + r.stderr.decode("utf-8", "replace")[-1500:])


def fit(w, h):
    """Scales any input into the w x h frame, letterboxed, never stretched."""
    return f"scale={w}:{h}:force_original_aspect_ratio=decrease,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2"


def still_segment(src, dur, out, zoom, w, h, fps):
    """A PNG held for dur seconds; zoompan only when the row asks for it."""
    frames = int(round(dur * fps))
    vf = fit(w, h)
    cmd = [ffmpeg_exe(), "-y"]
    if zoom:
        vf += (f",zoompan=z='min(zoom+{ZOOM_RATE},{ZOOM_MAX})'"
               f":x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={frames}:s={w}x{h}:fps={fps}")
        cmd += ["-i", str(src)]
    else:
        cmd += ["-loop", "1", "-framerate", str(fps), "-i", str(src)]
    vf += ",format=yuv420p"
    run(cmd + ["-vf", vf, "-frames:v", str(frames), "-r", str(fps)] + X264 + [str(out)])


def take_segment(src, trim, dur, out, w, h, fps):
    """A screen-recording take, normalized to the segment parameters."""
    seek = trim[0] if trim else 0.0
    if trim and abs((trim[1] - trim[0]) - dur) > 0.3:
        print(f"WARNING: trim {trim[0]:.1f}-{trim[1]:.1f}s does not match the {dur:.1f}s row")
    # tpad holds the last frame, so a take shorter than its row never shortens the segment.
    vf = f"{fit(w, h)},fps={fps},tpad=stop_mode=clone:stop_duration={dur:.3f},format=yuv420p"
    run([ffmpeg_exe(), "-y", "-ss", f"{seek:.3f}", "-i", str(src), "-vf", vf,
         "-frames:v", str(int(round(dur * fps))), "-r", str(fps)] + X264 + [str(out)])


def _font(kind, size):
    from PIL import ImageFont
    for path in FONT_CANDIDATES[kind]:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default(size)


def placeholder_png(ref, out, w, h, language="es"):
    """A card that stands in for a take not recorded yet."""
    from PIL import Image, ImageDraw
    title, subtitle = PLACEHOLDER_TEXT.get(language[:2], PLACEHOLDER_TEXT["en"])
    img = Image.new("RGB", (w, h), (247, 248, 249))
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, w, max(4, h // 77)], fill=(92, 99, 112))
    scale = h / 1080
    for text, font, y, fill in ((title.format(ref=ref), _font("bold", int(160 * scale)), 0.37, (23, 26, 30)),
                                (subtitle, _font("regular", int(46 * scale)), 0.565, (92, 99, 112))):
        tw = d.textlength(text, font=font)
        d.text(((w - tw) / 2, h * y), text, font=font, fill=fill)
    img.save(out)


def main(argv=None):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    args = sys.argv[1:] if argv is None else argv
    if not args or args[0].startswith("--"):
        raise SystemExit("usage: montar.py <video> [--out file.mp4] [--placeholder]")
    course = Course.load(args[0])
    w, h, fps = course.width, course.height, course.fps
    video_dir = course.resolve_video(args[0])
    placeholder = "--placeholder" in args
    final = course["delivery"]["final"] and "--draft" not in args
    if final and placeholder:
        raise SystemExit("final delivery cannot use --placeholder; add --draft for a draft build")
    rows = guion.parse_montage(guion.find_vigente(video_dir))
    loc_dir = video_dir / "locucion"
    data = json.loads((loc_dir / "timings.json").read_text(encoding="utf-8"))
    trows = data["rows"]
    if [r.num for r in rows] != [t["row"] for t in trows]:
        raise SystemExit("the script changed since locutor.py ran; generate the narration again")
    if final and data.get("source_signature") != delivery.narration_signature(
            rows, course, guion.video_rate(guion.find_vigente(video_dir), course.voice["rate"])):
        raise SystemExit("narration text, voice or pacing changed; regenerate with locutor.py")
    limit = course["delivery"]["max_duration_seconds"]
    if final and limit is not None and data["total"] > float(limit):
        raise SystemExit(f"narration already exceeds {limit} s including pauses; shorten it before mounting")
    inputs = delivery.build_inputs(video_dir, course, rows)

    out = Path(guion.flag_value(args, "--out") or (course.publish_dir / video_dir.name / f"{video_dir.name}.mp4"))
    out.parent.mkdir(parents=True, exist_ok=True)

    tmp = Path(tempfile.mkdtemp(prefix="montar-"))
    segs = []
    for row, t in zip(rows, trows):
        dur = t["visual_dur"]
        seg = tmp / f"seg-{row.num:02d}.mp4"
        if row.visual.kind == "slide":
            img = video_dir / "assets" / "slides" / f"slide-{int(row.visual.ref):02d}.png"
            if not img.exists():
                raise SystemExit(f"missing slide: {img.name} (run slides.py)")
            still_segment(img, dur, seg, row.visual.zoom, w, h, fps)
        else:
            take = video_dir / "grabaciones" / f"{row.visual.ref}.mp4"
            if take.exists():
                take_segment(take, row.visual.trim, dur, seg, w, h, fps)
            elif placeholder:
                card = tmp / f"card-{row.num:02d}.png"
                placeholder_png(row.visual.ref, card, w, h, course["language"])
                still_segment(card, dur, seg, False, w, h, fps)
                print(f"row {row.num:02d}: placeholder for take {row.visual.ref}")
            else:
                raise SystemExit(f"missing take {take.name} (record it, or pass --placeholder)")
        segs.append(seg)
        print(f"row {row.num:02d}  {dur:6.2f} s  {row.visual.kind} {row.visual.ref}")

    listing = tmp / "list.txt"
    listing.write_text("".join(f"file '{s.as_posix()}'\n" for s in segs), encoding="utf-8")
    joined = tmp / "joined.mp4"
    run([ffmpeg_exe(), "-y", "-f", "concat", "-safe", "0", "-i", str(listing), "-c", "copy", str(joined)])

    audio = loc_dir / "locucion.wav"
    tags = []
    for key, value in delivery.metadata(course).items():
        tags += ["-metadata", f"{key}={value}"]
    run([ffmpeg_exe(), "-y", "-i", str(joined), "-i", str(audio), "-c:v", "copy",
         "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2",
         "-metadata:s:a:0", "language=" + ("eng" if course["language"].startswith("en") else course["language"]),
         *tags, "-movflags", "+faststart+use_metadata_tags", str(out)])
    if course["delivery"]["description"] and not (out.parent / "descripcion.md").exists():
        (out.parent / "descripcion.md").write_text(delivery.description(course), encoding="utf-8")
    delivery.write_manifest(out, inputs, placeholder)
    if final:
        import verificar
        findings = verificar.check(video_dir, course, out=out, final=True)
        for finding in findings:
            print(f"{finding.level.upper()}: {finding.message}")
        if any(f.level == "error" for f in findings):
            raise SystemExit("final delivery failed verification; the output is not ready to submit")
    print(f"OK {out.name}  {data['total']:.1f} s of narration")


if __name__ == "__main__":
    main()
