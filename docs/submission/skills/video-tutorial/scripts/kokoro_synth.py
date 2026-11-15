# Synthesizes narration with Kokoro (local neural TTS). Runs under the Python that has kokoro
# installed (kokoro_setup.py creates it); locutor.py calls it as a subprocess with a jobs file:
#
#   python kokoro_synth.py --jobs jobs.json
#
# jobs.json: [{"text": "...", "voice": "ef_dora", "speed": 1.0, "out": "/path/fila-01-0.wav"}, ...]
# One model load for every job. Each wav is mono, 16-bit, 24 kHz: the format locutor.py works in.
# The language comes from the voice's first letter (e = Spanish, a = American English, b = British,
# p = Brazilian Portuguese, f, i, h, j, z), which is how Kokoro names its voices.

import argparse
import json
import os
import sys
import warnings

SAMPLE_RATE = 24000


def main(argv=None):
    p = argparse.ArgumentParser(prog="kokoro_synth.py")
    p.add_argument("--jobs", required=True, help="JSON list of {text, voice, speed, out}")
    a = p.parse_args(argv)
    jobs = json.loads(open(a.jobs, encoding="utf-8").read())
    os.environ.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")   # Apple Silicon: fall back to CPU per op
    warnings.filterwarnings("ignore")
    import numpy as np
    import soundfile as sf
    from kokoro import KPipeline

    pipelines = {}
    for job in jobs:
        lang = job["voice"][0]
        if lang not in pipelines:
            pipelines[lang] = KPipeline(lang_code=lang, repo_id="hexgrad/Kokoro-82M")
        chunks = [np.asarray(audio) for _, _, audio in
                  pipelines[lang](job["text"], voice=job["voice"], speed=float(job.get("speed", 1.0)))]
        audio = np.concatenate(chunks) if chunks else np.zeros(SAMPLE_RATE // 10, dtype=np.float32)
        sf.write(job["out"], audio, SAMPLE_RATE, subtype="PCM_16")
        print(f"{os.path.basename(job['out'])}  {len(audio) / SAMPLE_RATE:.2f} s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
