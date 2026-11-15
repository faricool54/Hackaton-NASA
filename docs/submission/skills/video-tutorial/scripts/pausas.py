# Prints where each phrase starts inside a row's narration (the end of each silence), so a
# take's t.at() marks can land on the words the voice says. Measured on locucion/fila-NN.wav.
#
#   python pausas.py <video> [--filas 5,7,10]
#
# A comma pause is short: the defaults (-30 dB, 0.12 s) catch commas inside a long sentence.

import argparse
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import guion
from course import Course

SILENCE_END_RE = re.compile(r"silence_end:\s*([0-9.]+)")


def silence_ends(ffmpeg_stderr):
    """Seconds at which each silence ends, i.e. where the next phrase starts."""
    return [float(m) for m in SILENCE_END_RE.findall(ffmpeg_stderr)]


def phrase_starts(wav, noise_db=-30, min_s=0.12):
    import imageio_ffmpeg
    r = subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-i", str(wav), "-af",
                        f"silencedetect=noise={noise_db}dB:d={min_s}", "-f", "null", "-"],
                       capture_output=True)
    return silence_ends(r.stderr.decode("utf-8", "replace"))


def main(argv=None):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    p = argparse.ArgumentParser(prog="pausas.py")
    p.add_argument("video")
    p.add_argument("--filas", help="rows to measure, e.g. 5,7,10 (default: every row)")
    a = p.parse_args(sys.argv[1:] if argv is None else argv)
    course = Course.load(a.video)
    video_dir = course.resolve_video(a.video)
    rows = guion.parse_montage(guion.find_vigente(video_dir))
    wanted = {int(n) for n in a.filas.split(",")} if a.filas else {r.num for r in rows}
    for row in rows:
        if row.num not in wanted:
            continue
        wav = video_dir / "locucion" / f"fila-{row.num:02d}.wav"
        if not wav.exists():
            print(f"fila {row.num:02d}: no audio yet (run locutor.py)")
            continue
        starts = " ".join(f"{s:.2f}" for s in phrase_starts(wav))
        print(f"fila {row.num:02d} [{row.visual.kind} {row.visual.ref}]: {starts}\n   {row.locucion}")


if __name__ == "__main__":
    main()
