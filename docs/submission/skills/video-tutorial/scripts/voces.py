# Voice samples for a course before any video exists: the setup wizard uses them to pick the
# course voice, and its speed, by ear.
#
#   python voces.py <course> [--texto "..."]                          # one sample per voice.candidates
#   python voces.py <course> --voz es-MX-DaliaNeural --velocidades +0% +5% +10%
#
# Candidates may be edge-tts voices (es-MX-DaliaNeural) or Kokoro voices (ef_dora): both render.
#
# Output: <course>/_template/muestras-voz/NN-<label>.mp3 and textos.txt.

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import locutor
from course import Course

SAMPLE_TEXT = {
    "es": ("Hola. En este curso vas a aprender a usar la plataforma paso a paso, sin escribir código. "
           "Empezamos por lo esencial; y después, lo que la hace distinta."),
    "en": ("Hi. In this course you will learn to use the platform step by step, without writing code. "
           "We start with the essentials; then, what makes it different."),
}


def samples(course, voz=None, velocidades=None):
    """[(filename, Speech)]: every candidate voice, or one voice at several rates."""
    v = course.voice
    if velocidades:
        name = voz or v["name"]
        return [(f"{k:02d}-{name}-{rate}.mp3",
                 locutor.Speech(name, rate, v["pitch"], v["pronunciation"], v["kokoro_python"]))
                for k, rate in enumerate(velocidades, start=1)]
    return [(f"{k:02d}-{label}.mp3", locutor.Speech(voice, rate, pitch, v["pronunciation"], v["kokoro_python"]))
            for k, (label, voice, rate, pitch) in enumerate(v["candidates"], start=1)]


def main(argv=None):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    p = argparse.ArgumentParser(prog="voces.py")
    p.add_argument("course")
    p.add_argument("--texto")
    p.add_argument("--voz")
    p.add_argument("--velocidades", nargs="+")
    a = p.parse_args(sys.argv[1:] if argv is None else argv)
    course = Course.load(a.course)
    text = a.texto or SAMPLE_TEXT.get(course["language"][:2], SAMPLE_TEXT["en"])
    out = course.root / "_template" / "muestras-voz"
    out.mkdir(parents=True, exist_ok=True)
    lines = []
    for name, speech in samples(course, a.voz, a.velocidades):
        wav = out / (Path(name).stem + ".wav")
        seconds = locutor.synth_wav(text, speech, out / name, wav)
        wav.unlink()
        lines.append(f"{name}\t{speech.voice}\t{speech.rate}\t{speech.engine}\t{seconds:.2f} s")
        print(lines[-1])
    (out / "textos.txt").write_text(f"{text}\n\n" + "\n".join(lines) + "\n", encoding="utf-8")
    print(f"folder: {out}")


if __name__ == "__main__":
    main()
