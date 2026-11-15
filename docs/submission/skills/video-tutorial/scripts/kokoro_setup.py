# Installs Kokoro (local neural TTS) in its own virtual environment, outside the course folders,
# so the skill's own dependencies stay light. Idempotent: run it again to check or repair.
#
#   python kokoro_setup.py            # creates <data root>/kokoro and installs kokoro + soundfile
#   python kokoro_setup.py --check    # only reports
#
# Also needs espeak-ng on PATH (Kokoro's phonemizer): brew install espeak-ng / apt install espeak-ng.
# The first synthesis downloads the model (~330 MB) into the Hugging Face cache.

import shutil
import subprocess
import sys
import venv
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from course import kokoro_default_python

PACKAGES = ["kokoro>=0.9", "soundfile"]


def installed(python):
    return Path(python).exists() and subprocess.run(
        [str(python), "-c", "import kokoro, soundfile"], capture_output=True).returncode == 0


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    python = kokoro_default_python()
    ok = installed(python)
    espeak = shutil.which("espeak-ng")
    print(f"kokoro python: {python}  {'OK' if ok else 'MISSING'}")
    print(f"espeak-ng:     {espeak or 'MISSING (brew install espeak-ng / apt install espeak-ng)'}")
    if "--check" in argv or (ok and espeak):
        return 0 if (ok and espeak) else 1
    if not ok:
        venv_dir = python.parents[1]
        if not python.exists():
            print(f"creating venv {venv_dir}")
            venv.EnvBuilder(with_pip=True, clear=False).create(venv_dir)
        print("installing " + " ".join(PACKAGES) + " (torch included: a few minutes, ~1 GB)")
        r = subprocess.run([str(python), "-m", "pip", "install", "-q", *PACKAGES])
        if r.returncode != 0:
            raise SystemExit("pip install failed")
        print("kokoro installed")
    return 0 if espeak else 1


if __name__ == "__main__":
    sys.exit(main())
