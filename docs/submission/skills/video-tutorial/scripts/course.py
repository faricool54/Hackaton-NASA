# The course configuration: course.yaml at the course root, merged over DEFAULTS.
# Every script finds the root by walking up from the folder it is given, so a course
# can live anywhere and nothing about a particular course is hardcoded in the skill.

import copy
import os
import sys
from pathlib import Path

import yaml

CONFIG_NAME = "course.yaml"

DEFAULTS = {
    "name": "",
    "language": "es",
    "audience": "",
    "depth": "",
    "target_duration": "",
    "delivery": {
        "final": False,
        "max_duration_seconds": None,
        "target_duration_seconds": None,
        "required_language": "",
        "require_identity": False,
        "team": "", "members": [], "challenge": "",
        "description": "", "credits": [],
        "ai_audio_credit": "",
        "metadata": {},
    },
    "video": {"width": 1920, "height": 1080, "fps": 30},
    "folders": {"production": "internal", "publish": "export"},
    "voice": {
        "engine": "edge-tts",          # edge-tts | human (experimental: measures fila-NN.wav recorded by a person)
        "name": "es-MX-DaliaNeural",   # an edge-tts voice, or a Kokoro one (ef_dora, em_alex...): told apart by name
        "rate": "+0%",                 # edge-tts rate; Kokoro reads it as a speed multiplier (+5% -> 1.05)
        "pitch": "+0Hz",
        "kokoro_python": "",           # the Python with kokoro installed; default: the venv kokoro_setup.py makes
        # Rendered by locutor.py --muestras / voces.py: [label, voice, rate, pitch]. Engines may mix.
        "candidates": [
            ["dalia", "es-MX-DaliaNeural", "+0%", "+0Hz"],
            ["jorge", "es-MX-JorgeNeural", "+0%", "+0Hz"],
            ["salome", "es-CO-SalomeNeural", "+0%", "+0Hz"],
            ["gonzalo", "es-CO-GonzaloNeural", "+0%", "+0Hz"],
        ],
        # Spoken respellings, applied only to the text sent to TTS. Keys may be phrases; matching is
        # case-sensitive and runs in order, so a phrase must come before the single word it contains.
        "pronunciation": {},
        "pacing": {"lead_in": 0.2, "row_gap": 0.4, "tail": 0.6},
    },
    "recording": {
        "enabled": False,
        "base_url": "",
        "sso_hosts": ["okta"],          # a redirect to one of these means the saved session expired
        "profile": "",                  # browser profile folder name; defaults to the course folder's name
        "color_scheme": "light",
        "local_storage": {},            # set before the app's own scripts on every page (theme, season...)
        "blur_selectors": [],           # real names, teams, figures: blurred in every take and capture
        "write_guard": {"enabled": False, "allow": []},   # allow: ["POST /api/path", ...]
    },
    "deck": {"enabled": True, "design_system": "neutral"},
}


def data_root():
    """Where the skill keeps what belongs to no course: browser profiles, the Kokoro venv."""
    base = os.environ.get("LOCALAPPDATA") or (Path.home() / ".local" / "share")
    return Path(base) / "video-tutorial"


def kokoro_default_python():
    """The interpreter of the Kokoro venv kokoro_setup.py creates."""
    bin_dir = "Scripts" if sys.platform == "win32" else "bin"
    exe = "python.exe" if sys.platform == "win32" else "python"
    return data_root() / "kokoro" / bin_dir / exe


def _merge(base, override):
    out = copy.deepcopy(base)
    for key, value in (override or {}).items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _merge(out[key], value)
        else:
            out[key] = value
    return out


def find_root(start):
    """The nearest folder at or above `start` that holds course.yaml."""
    start = Path(start).resolve()
    for folder in [start, *start.parents]:
        if (folder / CONFIG_NAME).is_file():
            return folder
    raise SystemExit(f"no {CONFIG_NAME} found at or above {start}. "
                     "Run the setup wizard first (ask Claude to set up a new course).")


class Course:
    """A course root and its configuration, with the defaults filled in."""

    def __init__(self, root, data):
        self.root = Path(root)
        self.data = data

    @classmethod
    def load(cls, start="."):
        root = find_root(start)
        raw = yaml.safe_load((root / CONFIG_NAME).read_text(encoding="utf-8")) or {}
        return cls(root, _merge(DEFAULTS, raw))

    def __getitem__(self, key):
        return self.data[key]

    @property
    def width(self):
        return int(self.data["video"]["width"])

    @property
    def height(self):
        return int(self.data["video"]["height"])

    @property
    def fps(self):
        return int(self.data["video"]["fps"])

    @property
    def voice(self):
        return self.data["voice"]

    @property
    def recording(self):
        return self.data["recording"]

    @property
    def production_dir(self):
        return self.root / self.data["folders"]["production"]

    @property
    def publish_dir(self):
        return self.root / self.data["folders"]["publish"]

    @property
    def profile_name(self):
        return self.recording["profile"] or self.root.name

    def resolve_video(self, arg):
        """A video folder, given as a path or by name inside the production folder."""
        for candidate in (Path(arg), self.root / arg, self.production_dir / arg):
            if candidate.is_dir():
                return candidate.resolve()
        raise SystemExit(f"video folder not found: {arg}")
