# Renders numbered audio variants of a montage row, at the video's narration rate, so the
# user can pick by ear. v1 is always the row as it is today. Nothing in the script changes:
# the pick is applied afterwards (to the script for a rewrite, to course.yaml's pronunciation
# dictionary for a respelling).
#
#   python variantes.py <video> --fila 9 --buscar "qué tan" --opciones "qué tán" "cuán" [--nombre que-tan]
#   python variantes.py <video> --fila 12 --textos "Otra redacción completa" "Y otra más"
#   python variantes.py <video> --filas 1,2,3 --velocidades +0% +5% +10%
#
# Output: <video>/locucion/muestras/<nombre>/fila-NN-vK.mp3 (or velocidad-K.mp3) and textos.txt.

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import guion
import locutor
from course import Course


def parse(argv):
    p = argparse.ArgumentParser(prog="variantes.py")
    p.add_argument("video")
    p.add_argument("--fila", type=int, help="the row to vary")
    p.add_argument("--buscar", help="the fragment of the row to replace in each option")
    p.add_argument("--opciones", nargs="+", help="replacements for --buscar, one per variant")
    p.add_argument("--textos", nargs="+", help="whole-row texts, one per variant")
    p.add_argument("--filas", help="rows read together for --velocidades, e.g. 1,2,3")
    p.add_argument("--velocidades", nargs="+", help="narration rates to compare, e.g. +0%% +5%%")
    p.add_argument("--nombre", help="folder name under locucion/muestras/")
    a = p.parse_args(argv)
    if a.velocidades:
        if not a.filas:
            p.error("--velocidades needs --filas")
    elif a.fila is None or not (a.textos or (a.buscar and a.opciones)):
        p.error("give --fila with --buscar/--opciones or --textos, or --filas with --velocidades")
    return a


def row_variants(text, buscar=None, opciones=None, textos=None):
    """[current, variant 2, ...]: the row as it is, then each replacement or whole text."""
    if textos:
        return [text, *textos]
    if buscar not in text:
        raise SystemExit(f"{buscar!r} is not in the row: {text}")
    return [text, *(text.replace(buscar, o) for o in opciones)]


def slug(text, limit=24):
    keep = "".join(c.lower() if c.isalnum() else "-" for c in text)
    return "-".join(filter(None, keep.split("-")))[:limit] or "muestras"


def render(items, out_dir, speech_for):
    """Renders [(filename, text, rate)] and writes textos.txt. Returns [(filename, seconds, text)]."""
    out_dir.mkdir(parents=True, exist_ok=True)
    done = []
    for name, text, rate in items:
        mp3, wav = out_dir / name, out_dir / (Path(name).stem + ".wav")
        seconds = locutor.synth_parts(guion.split_pauses(text), speech_for(rate), wav)
        locutor.to_mp3(wav, mp3)
        wav.unlink()
        done.append((name, seconds, text if rate is None else f"{rate} · {text}"))
    (out_dir / "textos.txt").write_text("".join(f"{n}\t{s:.2f} s\t{t}\n" for n, s, t in done), encoding="utf-8")
    return done


def main(argv=None):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    a = parse(sys.argv[1:] if argv is None else argv)
    course = Course.load(a.video)
    video_dir = course.resolve_video(a.video)
    script = guion.find_vigente(video_dir)
    rows = {r.num: r for r in guion.parse_montage(script)}
    voice = course.voice
    base_rate = guion.video_rate(script, voice["rate"])

    def speech_for(rate):
        return locutor.Speech(voice["name"], rate or base_rate, voice["pitch"], voice["pronunciation"],
                              voice["kokoro_python"])

    if a.velocidades:
        nums = [int(n) for n in a.filas.split(",")]
        text = " ".join(rows[n].locucion for n in nums)
        items = [(f"velocidad-{k}.mp3", text, rate) for k, rate in enumerate(a.velocidades, start=1)]
        out_dir = video_dir / "locucion" / "muestras" / (a.nombre or "velocidad")
    else:
        if a.fila not in rows:
            raise SystemExit(f"row {a.fila} is not in the montage sheet")
        texts = row_variants(rows[a.fila].locucion, a.buscar, a.opciones, a.textos)
        items = [(f"fila-{a.fila:02d}-v{k}.mp3", t, None) for k, t in enumerate(texts, start=1)]
        out_dir = video_dir / "locucion" / "muestras" / (a.nombre or slug(a.buscar or f"fila-{a.fila}"))

    for name, seconds, text in render(items, out_dir, speech_for):
        print(f"{name}  {seconds:5.2f} s  {text}")
    print(f"folder: {out_dir}")


if __name__ == "__main__":
    main()
