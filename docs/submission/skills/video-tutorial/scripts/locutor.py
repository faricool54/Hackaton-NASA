# Generates the narration of one video: one wav per montage row, the full track
# (locucion.wav) and timings.json with the measured durations. The audio is the
# only timing source of truth -- montar.py cuts to these measurements.
#
#   python locutor.py <video> [--voice es-XX-Name] [--muestras] [--sync]
#
# --muestras   one sample per candidate voice in course.yaml, reading the first two rows, under locucion/muestras/
# --sync       writes the measured in/out/duration back into the script's montage sheet
#
# voice.engine: human (experimental) synthesizes nothing: a person records each row as
# locucion/humana/fila-NN.wav (any format) and this script measures and joins them.
#
# Two AI engines, told apart by the voice's name: edge-tts (es-MX-DaliaNeural: Microsoft neural
# voices, free, online) and Kokoro (ef_dora, em_alex: local, offline, runs in the venv that
# kokoro_setup.py creates, called through kokoro_synth.py). One voice per course either way.

import asyncio
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import wave
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import guion
from course import Course, kokoro_default_python

KOKORO_VOICE_RE = re.compile(r"^[a-z]{2}_[a-z]+$")   # ef_dora, em_alex, af_heart...
KOKORO_SYNTH = Path(__file__).resolve().parent / "kokoro_synth.py"

SAMPLE_RATE = 24000  # edge-tts output rate, kept end to end until the final mux

# Neural voices read 5-17 characters per second. edge-tts can return a clipped file
# without any error (183 characters once came back as 0.36 s), so audio read faster
# than this is taken as truncated and requested again.
MAX_CHARS_PER_S = 30
SYNTH_ATTEMPTS = 3


@dataclass
class Speech:
    """How the text is spoken: the voice, its rate and pitch, and the course's respellings."""
    voice: str
    rate: str = "+0%"
    pitch: str = "+0Hz"
    pronunciation: dict = field(default_factory=dict)
    kokoro_python: str = ""          # voice.kokoro_python; empty: the venv kokoro_setup.py creates

    @property
    def engine(self):
        return "kokoro" if KOKORO_VOICE_RE.match(self.voice) else "edge-tts"

    @property
    def speed(self):
        return rate_to_speed(self.rate)


def rate_to_speed(rate):
    """edge-tts rate ('+5%', '-10%') as Kokoro's speed multiplier (1.05, 0.9)."""
    return round(1.0 + float(str(rate).strip().rstrip("%") or 0) / 100.0, 3)


def ffmpeg_exe():
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()


def run(cmd):
    import subprocess
    r = subprocess.run(cmd, capture_output=True)
    if r.returncode != 0:
        raise SystemExit("ffmpeg failed:\n" + r.stderr.decode("utf-8", "replace")[-1500:])


def spoken(text, pronunciation):
    """The text as the voice should say it: respelled per the course's pronunciation dictionary, in order."""
    for word, respelling in pronunciation.items():
        text = re.sub(rf"\b{re.escape(word)}\b", respelling, text)
    return text


def synth(text, speech, out_mp3):
    """edge-tts only: Kokoro goes through synth_wav, which writes the wav itself."""
    import edge_tts
    asyncio.run(edge_tts.Communicate(spoken(text, speech.pronunciation), speech.voice,
                                     rate=speech.rate, pitch=speech.pitch).save(str(out_mp3)))


def kokoro_python(speech):
    python = Path(speech.kokoro_python) if speech.kokoro_python else kokoro_default_python()
    if not python.exists():
        raise SystemExit(f"Kokoro is not installed ({python} missing): run  kokoro_setup.py  "
                         "or set voice.kokoro_python in course.yaml")
    return python


def synth_kokoro(jobs, speech):
    """Renders [(text, out_wav)] in one kokoro_synth.py run (one model load), respelled like edge-tts."""
    if not jobs:
        return
    payload = [{"text": spoken(text, speech.pronunciation), "voice": speech.voice,
                "speed": speech.speed, "out": str(out)} for text, out in jobs]
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False)
    try:
        r = subprocess.run([str(kokoro_python(speech)), str(KOKORO_SYNTH), "--jobs", f.name],
                           capture_output=True, env={**os.environ, "PYTORCH_ENABLE_MPS_FALLBACK": "1"})
    finally:
        Path(f.name).unlink()
    if r.returncode != 0:
        raise SystemExit("kokoro_synth.py failed:\n" + r.stderr.decode("utf-8", "replace")[-1500:])


def to_wav(src, dst):
    run([ffmpeg_exe(), "-y", "-i", str(src), "-ar", str(SAMPLE_RATE), "-ac", "1",
         "-c:a", "pcm_s16le", str(dst)])


def to_mp3(src, dst):
    run([ffmpeg_exe(), "-y", "-i", str(src), "-q:a", "2", str(dst)])


def looks_truncated(text, seconds):
    """Whether `seconds` of audio are too short to hold `text` read aloud."""
    return len(text) / max(seconds, 1e-6) > MAX_CHARS_PER_S


def synth_wav(text, speech, mp3, wav):
    """synth + to_wav, asking again while the audio comes back truncated. Returns the wav's length.

    Kokoro writes the wav itself (local, never clipped) and the mp3 is encoded from it, so every
    caller gets both files whichever the engine.
    """
    if speech.engine == "kokoro":
        synth_kokoro([(text, wav)], speech)
        run([ffmpeg_exe(), "-y", "-i", str(wav), str(mp3)])
        return seconds_of(wav)
    for attempt in range(1, SYNTH_ATTEMPTS + 1):
        synth(text, speech, mp3)
        to_wav(mp3, wav)
        seconds = seconds_of(wav)
        if not looks_truncated(text, seconds):
            return seconds
        print(f"WARNING truncated audio ({seconds:.2f} s for {len(text)} characters), "
              f"attempt {attempt}/{SYNTH_ATTEMPTS}: {text[:60]}")
    raise SystemExit(f"edge-tts kept returning truncated audio after {SYNTH_ATTEMPTS} attempts: {text[:80]}")


def frames_of(path):
    with wave.open(str(path), "rb") as w:
        return w.readframes(w.getnframes())


def seconds_of(path):
    with wave.open(str(path), "rb") as w:
        return w.getnframes() / w.getframerate()


def silence(seconds):
    return b"\x00" * (int(round(seconds * SAMPLE_RATE)) * 2)  # mono s16


def synth_parts(parts, speech, out):
    """Speaks [(text, pause_after_s)] into one wav, with silence where the pauses are marked, so a
    pause mark is never read aloud. A part with no text is a silent hold. Returns the wav's length."""
    with wave.open(str(out), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SAMPLE_RATE)
        for i, (text, pause) in enumerate(parts):
            if text:
                mp3 = out.with_name(f"{out.stem}-{i}.mp3")
                wav = out.with_name(f"{out.stem}-{i}.wav")
                prerendered = speech is not None and speech.engine == "kokoro" and wav.exists()
                if not prerendered:    # prerender_kokoro leaves Kokoro parts there; anything else is stale
                    synth_wav(text, speech, mp3, wav)
                w.writeframes(frames_of(wav))
                mp3.unlink(missing_ok=True)
                wav.unlink()
            if pause:
                w.writeframes(silence(pause))
    return seconds_of(out)


def build_row(row, speech, loc_dir):
    """One row's narration: parts joined with their marked pauses -> fila-NN.wav."""
    out = loc_dir / f"fila-{row.num:02d}.wav"
    synth_parts(row.parts, speech, out)
    return out


def part_wavs(rows, loc_dir):
    """[(text, fila-NN-i.wav)] for every spoken part, the files build_row reads."""
    return [(text, loc_dir / f"fila-{row.num:02d}-{i}.wav")
            for row in rows for i, (text, _) in enumerate(row.parts) if text]


def prerender_kokoro(rows, speech, loc_dir):
    """Every spoken part in one Kokoro run, so the model loads once instead of once per phrase."""
    synth_kokoro(part_wavs(rows, loc_dir), speech)


def is_silent(row):
    """A row whose narration is only pauses (e.g. "3s"): the visual holds, nobody speaks."""
    return not any(text for text, _ in getattr(row, "parts", [("spoken", 0.0)]))


def build_row_human(row, loc_dir):
    """A row a person recorded (locucion/humana/fila-NN.*), converted to the track's format -> fila-NN.wav."""
    if is_silent(row):
        return build_row(row, None, loc_dir)   # nothing to record: silence only
    found = sorted((loc_dir / "humana").glob(f"fila-{row.num:02d}.*"))
    if not found:
        raise SystemExit(f"row {row.num}: missing recording locucion/humana/fila-{row.num:02d}.wav")
    out = loc_dir / f"fila-{row.num:02d}.wav"
    to_wav(found[0], out)
    return out


def muestras(rows, loc_dir, candidates, kokoro_python=""):
    """One sample per candidate voice (edge-tts or Kokoro), reading the first two rows."""
    out_dir = loc_dir / "muestras"
    out_dir.mkdir(parents=True, exist_ok=True)
    parts = [part for r in rows[:2] for part in r.parts]   # pause marks become silence, never read aloud
    for label, voice, rate, pitch in candidates:
        out, wav = out_dir / f"{label}.mp3", out_dir / f"{label}.wav"
        synth_parts(parts, Speech(voice, rate, pitch, kokoro_python=kokoro_python), wav)
        to_mp3(wav, out)
        wav.unlink()
        print(f"muestra {out.name}  {voice} {rate} {pitch}")


def changed_rows(before, after, tolerance=0.01):
    """[(row, delta_s)] for rows whose phrase length moved, comparing two timings.json payloads."""
    old = {t["row"]: t["phrase_dur"] for t in (before or {}).get("rows", [])}
    out = []
    for t in after["rows"]:
        prev = old.get(t["row"])
        if prev is None or abs(t["phrase_dur"] - prev) > tolerance:
            out.append((t["row"], None if prev is None else round(t["phrase_dur"] - prev, 3)))
    return out


def track_timings(built, pacing):
    """Joins the rows into one track: lead-in + rows separated by the row gap + tail.

    Each row's visual spans from its phrase start to the next phrase start, so the cut
    lands inside the pause, never on a word. Returns (timings, total_seconds).
    """
    timings, clock = [], pacing["lead_in"]
    for i, (row, _, d) in enumerate(built):
        start = clock
        gap = pacing["row_gap"] if i < len(built) - 1 else pacing["tail"]
        clock += d + gap
        extra = pacing["lead_in"] if i == 0 else 0.0
        timings.append({
            "row": row.num,
            "phrase_start": round(start, 3),
            "phrase_dur": round(d, 3),
            "visual": {"kind": row.visual.kind, "ref": row.visual.ref, "trim": row.visual.trim},
            "visual_start": round(start - extra, 3),
            "visual_dur": round(d + gap + extra, 3),
        })
    return timings, clock


def write_track(built, pacing, out):
    with wave.open(str(out), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SAMPLE_RATE)
        w.writeframes(silence(pacing["lead_in"]))
        for i, (_, f, _) in enumerate(built):
            w.writeframes(frames_of(f))
            w.writeframes(silence(pacing["row_gap"] if i < len(built) - 1 else pacing["tail"]))


def sync(guion_path, timings, total):
    """Writes the measured in/out/duration back into the script's montage sheet."""
    starts = {t["row"]: t["phrase_start"] for t in timings}
    nums = sorted(starts)
    with open(guion_path, encoding="utf-8", newline="") as f:   # newline="": a CRLF file stays CRLF
        lines = f.read().split("\n")
    in_table = False
    for i, raw in enumerate(lines):
        eol = "\r" if raw.endswith("\r") else ""
        line = raw.rstrip("\r")
        if line.lstrip().startswith("#"):
            in_table = any(h in line for h in guion.SHEET_HEADINGS)
            continue
        if not in_table or not line.strip().startswith("|"):
            continue
        cells = line.split("|")
        if len(cells) < 8 or not cells[1].strip().isdigit():
            continue
        num = int(cells[1].strip())
        if num not in starts:
            continue
        sale = starts[nums[nums.index(num) + 1]] if num != nums[-1] else total
        entra = starts[num]
        fmt = lambda t: f"{int(t // 60)}:{t % 60:04.1f}"
        lines[i] = ("|" + cells[1] + "|" + cells[2] + "|" + cells[3]
                    + f"| {fmt(entra)} | {fmt(sale)} | {sale - entra:.1f} s |" + eol)
    guion_path.write_text("\n".join(lines), encoding="utf-8", newline="")


def main(argv=None):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    args = sys.argv[1:] if argv is None else argv
    if not args or args[0].startswith("--"):
        raise SystemExit("usage: locutor.py <video> [--voice es-XX-Name] [--muestras] [--sync]")
    course = Course.load(args[0])
    video_dir = course.resolve_video(args[0])
    guion_path = guion.find_vigente(video_dir)
    rows = guion.parse_montage(guion_path)
    loc_dir = video_dir / "locucion"
    loc_dir.mkdir(exist_ok=True)
    voice = course.voice

    if "--muestras" in args:
        muestras(rows, loc_dir, voice["candidates"], voice["kokoro_python"])
        return

    speech = Speech(guion.flag_value(args, "--voice", voice["name"]),
                    guion.video_rate(guion_path, voice["rate"]), voice["pitch"], voice["pronunciation"],
                    voice["kokoro_python"])
    human = voice["engine"] == "human"
    if not human and speech.engine == "kokoro":
        prerender_kokoro(rows, speech, loc_dir)
    built = []
    for row in rows:
        f = build_row_human(row, loc_dir) if human else build_row(row, speech, loc_dir)
        d = seconds_of(f)
        built.append((row, f, d))
        print(f"fila {row.num:02d}  {d:6.2f} s  {row.visual.kind} {row.visual.ref}")

    timings, total = track_timings(built, voice["pacing"])
    write_track(built, voice["pacing"], loc_dir / "locucion.wav")
    timings_path = loc_dir / "timings.json"
    before = json.loads(timings_path.read_text(encoding="utf-8")) if timings_path.exists() else None
    if before is not None:
        shutil.copyfile(timings_path, loc_dir / "timings.prev.json")
    after = {"voice": "human" if human else speech.voice, "rate": speech.rate, "total": round(total, 3),
             "rows": timings}
    from delivery import narration_signature, sha256
    after["source_signature"] = narration_signature(rows, course, speech.rate,
                                                    voice["name"] if human else speech.voice)
    after["audio_sha256"] = sha256(loc_dir / "locucion.wav")
    timings_path.write_text(json.dumps(after, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"locucion.wav  {total:.1f} s  ({int(total // 60)}:{total % 60:04.1f})  voice {after['voice']} "
          f"rate {speech.rate}")
    if before is not None:
        moved = changed_rows(before, after)
        print("changed rows: " + (", ".join(f"{n} ({'new' if d is None else f'{d:+.2f} s'})" for n, d in moved)
                                  if moved else "none"))

    if "--sync" in args:
        sync(guion_path, timings, total)
        print("script synced with the measured times")


if __name__ == "__main__":
    main()
