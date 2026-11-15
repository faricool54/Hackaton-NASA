# Creates the pieces of a course from the skill's templates, so the setup wizard and every new
# video start from the same, correct structure.
#
#   python scaffold.py init  <course_dir> --answers answers.yaml [--force]
#   python scaffold.py video <course_dir> "NN - Title"
#   python scaffold.py deck  <course_dir>           # re-applies the design system to _template/
#
# init writes course.yaml (the wizard's answers), CLAUDE.md (the course conventions), README.md
# (how to work on the course), the production and publish folders, and _template/presentacion.html
# with the chosen design system. video creates one video folder from the templates, with the deck's
# example slides (data-guia) removed.

import argparse
import datetime
import html
import re
import shutil
import string
import sys
import tempfile
from pathlib import Path

import yaml

SCRIPTS_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPTS_DIR.resolve()))
from course import CONFIG_NAME, Course

SKILL_DIR = SCRIPTS_DIR.parent
TEMPLATES = SKILL_DIR / "templates"
PRESETS = TEMPLATES / "presets"
VIDEO_NAME_RE = re.compile(r"^(?:[A-Z]{1,4}-)?\d{1,3} - \S.*$")
GUIDE_SECTION_RE = re.compile(r"\n?[ \t]*<section\b[^>]*\bdata-guia\b[^>]*>.*?</section>[ \t]*\n?", re.DOTALL)
GUIDE_COMMENT_RE = re.compile(r"[ \t]*<!-- =+ Example layouts.*?-->[ \t]*\n")
TOKENS_RE = re.compile(r"/\* @tokens:start \*/.*?/\* @tokens:end \*/", re.DOTALL)
FONTS_RE = re.compile(r"/\* @fonts:start \*/.*?/\* @fonts:end \*/", re.DOTALL)


# ---- design system ----------------------------------------------------------------------

def load_preset(deck):
    """The design system a course's deck section asks for: a named preset, or custom over neutral.

    Returns (preset, base_dir): font file names resolve against base_dir unless absolute.
    """
    name = (deck or {}).get("design_system", "neutral")
    if name == "custom":
        base = yaml.safe_load((PRESETS / "neutral" / "preset.yaml").read_text(encoding="utf-8"))
        preset = {"name": "Custom", "tokens": {**base["tokens"], **(deck.get("tokens") or {})},
                  "font": {**base["font"], **(deck.get("font") or {})}}
        return preset, Path.cwd()
    folder = PRESETS / name
    if not (folder / "preset.yaml").is_file():
        raise SystemExit(f"unknown design system: {name} (neutral, rappi or custom)")
    return yaml.safe_load((folder / "preset.yaml").read_text(encoding="utf-8")), folder


def render_tokens(preset):
    t, font = preset["tokens"], preset["font"]
    return ("/* @tokens:start */\n"
            ":root {\n"
            f"  --primary: {t['primary']};\n"
            f"  --primary-container: {t['primary_container']};\n"
            "  --on-primary: #ffffff;\n"
            f"  --on-primary-container: {t['on_primary_container']};\n"
            f"  --font: {font['family']};\n"
            "}\n"
            "[data-theme=\"dark\"] {\n"
            f"  --primary-container: {t['primary_container_dark']};\n"
            f"  --on-primary-container: {t['on_primary_container_dark']};\n"
            "}\n"
            "/* @tokens:end */")


def render_fonts(preset):
    font = preset["font"]
    faces = [f"@font-face {{ font-family: '{font['name']}'; font-weight: {weight}; font-display: block; "
             f"src: url('assets/fonts/{Path(str(file)).name}') format('woff2'); }}"
             for weight, file in sorted((font.get("files") or {}).items(), key=lambda kv: int(kv[0]))]
    return "/* @fonts:start */\n" + "".join(f + "\n" for f in faces) + "/* @fonts:end */"


def apply_design(html, preset):
    html = TOKENS_RE.sub(lambda _: render_tokens(preset), html)
    return FONTS_RE.sub(lambda _: render_fonts(preset), html)


def copy_fonts(preset, base_dir, dest):
    dest.mkdir(parents=True, exist_ok=True)
    for file in (preset["font"].get("files") or {}).values():
        src = Path(str(file))
        src = src if src.is_absolute() else base_dir / "fonts" / src
        if not src.is_file():
            raise SystemExit(f"font file not found: {src}")
        shutil.copyfile(src, dest / src.name)


def strip_guide(html):
    """The deck without its example slides: what a new video starts from."""
    return GUIDE_SECTION_RE.sub("\n", GUIDE_COMMENT_RE.sub("", html))


def write_deck_template(course_dir, deck_cfg):
    preset, base = load_preset(deck_cfg)
    template = course_dir / "_template"
    html = apply_design((TEMPLATES / "deck" / "presentacion.html").read_text(encoding="utf-8"), preset)
    template.mkdir(parents=True, exist_ok=True)
    (template / "presentacion.html").write_text(html, encoding="utf-8")
    copy_fonts(preset, base, template / "assets" / "fonts")
    (template / "assets" / "capturas").mkdir(parents=True, exist_ok=True)
    return preset


# ---- course conventions -----------------------------------------------------------------

def conventions(data, scripts_dir):
    """The values CONVENTIONS.md and README-curso.md are filled with."""
    voice, rec, deck = data["voice"], data["recording"], data["deck"]
    platform = (data.get("sources") or {}).get("platform") or ""
    return {
        "name": data["name"] or "Course",
        "language": data["language"],
        "audience": data["audience"] or "its audience",
        "depth": data["depth"] or "not set",
        "target_duration": data["target_duration"] or "a few minutes",
        "platform_line": f"It covers **{platform}**." if platform else "",
        "production": data["folders"]["production"],
        "publish": data["folders"]["publish"],
        "scripts": str(scripts_dir),
        "voice": ("recorded by a person (experimental): `locucion/humana/fila-NN.wav`" if voice["engine"] == "human"
                  else "edge-tts, with the voice, rate and pronunciation dictionary in `voice` of `course.yaml`"),
        "recording_line": (f"takes are recorded against `{rec['base_url']}` with Playwright; "
                           f"the write guard is {'on' if rec['write_guard']['enabled'] else 'off'}."
                           if rec["enabled"] else "no demo takes; captures come from the user."),
        "deck_line": (f"design system `{deck['design_system']}`, in `_template/presentacion.html`."
                      if deck["enabled"] else "no slides in this course."),
        "date": datetime.date.today().isoformat(),
    }


def render(template_path, values):
    return string.Template(template_path.read_text(encoding="utf-8")).safe_substitute(values)


# ---- commands ---------------------------------------------------------------------------

def init(course_dir, answers_path, force=False):
    course_dir = Path(course_dir)
    course_dir.mkdir(parents=True, exist_ok=True)
    if (course_dir / CONFIG_NAME).exists() and not force:
        raise SystemExit(f"{course_dir / CONFIG_NAME} already exists (pass --force to overwrite)")
    answers = yaml.safe_load(Path(answers_path).read_text(encoding="utf-8")) or {}
    header = ("# course.yaml -- written by video-tutorial scaffold.py. Every key is documented in\n"
              "# the skill's templates/course.yaml; keys left out take the defaults in scripts/course.py.\n\n")
    (course_dir / CONFIG_NAME).write_text(header + yaml.safe_dump(answers, allow_unicode=True, sort_keys=False, default_flow_style=None),
                                          encoding="utf-8")
    course = Course.load(course_dir)
    course.production_dir.mkdir(exist_ok=True)
    course.publish_dir.mkdir(exist_ok=True)
    if course["deck"]["enabled"]:
        write_deck_template(course_dir, course["deck"])
    values = conventions(course.data, SCRIPTS_DIR)
    claude = course_dir / "CLAUDE.md"
    target = claude if not claude.exists() else course_dir / "CLAUDE.video-tutorial.md"
    target.write_text(render(TEMPLATES / "CONVENTIONS.md", values), encoding="utf-8")
    lang = "es" if course["language"].startswith("es") else "en"
    readme = course_dir / "README.md"
    if not readme.exists():
        readme.write_text(render(TEMPLATES / f"README-curso.{lang}.md", values), encoding="utf-8")
    print(f"course ready at {course_dir}")
    if target != claude:
        print(f"CLAUDE.md already existed: the conventions went to {target.name}; merge them into CLAUDE.md")


def new_video(course_dir, name):
    course = Course.load(course_dir)
    if not VIDEO_NAME_RE.match(name):
        raise SystemExit(f'video folders are named "NN - Title" (e.g. "01 - Intro"), got: {name!r}')
    video = course.production_dir / name
    if video.exists():
        raise SystemExit(f"{video} already exists")
    number, title = name.split(" - ", 1)
    lang = "es" if course["language"].startswith("es") else "en"
    values = {"date": datetime.date.today().isoformat(), "number": number, "title": title}
    for sub in ("assets/capturas", "assets/slides", "assets/img", "grabaciones", "locucion"):
        (video / sub).mkdir(parents=True)
    (video / "guion-v1.md").write_text(render(TEMPLATES / f"guion.{lang}.md", values), encoding="utf-8")
    if course["deck"]["enabled"]:
        template = course.root / "_template"
        if not (template / "presentacion.html").exists():
            write_deck_template(course.root, course["deck"])
        html = strip_guide((template / "presentacion.html").read_text(encoding="utf-8"))
        html = re.sub(r"<title>.*?</title>", f"<title>Video {number} · {title}</title>", html, count=1)
        (video / "presentacion.html").write_text(html, encoding="utf-8")
        if (template / "assets" / "fonts").is_dir():
            shutil.copytree(template / "assets" / "fonts", video / "assets" / "fonts")
        background = template / "assets" / "capturas" / "background.png"
        if background.exists():
            shutil.copyfile(background, video / "assets" / "capturas" / "background.png")
    if course.recording["enabled"]:
        shutil.copyfile(TEMPLATES / "tomas.py", video / "tomas.py")
    (course.publish_dir / name).mkdir(parents=True, exist_ok=True)
    print(f"video ready at {video}")


def redo_deck(course_dir):
    course = Course.load(course_dir)
    preset = write_deck_template(course.root, course["deck"])
    print(f"_template/presentacion.html now uses the {preset['name']} design system")


def demo_cards(video_dir):
    course = Course.load(video_dir)
    video = course.resolve_video(str(video_dir))
    cfg = course["delivery"]
    credits = list(cfg["credits"])
    if course.voice["engine"] != "human" and cfg["ai_audio_credit"]:
        credits.append(cfg["ai_audio_credit"])
    values = {"team": html.escape(cfg["team"] or "[CONFIRM REGISTERED TEAM]"),
              "members": html.escape(" · ".join(cfg["members"]) or "[CONFIRM ACCEPTED MEMBERS]"),
              "challenge": html.escape(cfg["challenge"]),
              "app_url": html.escape(course.recording["base_url"]),
              "credits": "<br>".join(html.escape(c) for c in credits)}
    (video / "presentacion.html").write_text(render(TEMPLATES / "errante-demo/cards.html", values), encoding="utf-8")
    print(f"cards refreshed at {video}; export slides again")


def demo(course_dir, base_url=None):
    """A single English 30-second Errante demo; no course wizard or network actions."""
    answers = yaml.safe_load((TEMPLATES / "errante-demo/course.yaml").read_text(encoding="utf-8"))
    if base_url:
        answers["recording"]["base_url"] = base_url
    with tempfile.TemporaryDirectory(prefix="errante-demo-config-") as scratch:
        path = Path(scratch) / "answers.yaml"
        path.write_text(yaml.safe_dump(answers, allow_unicode=True, sort_keys=False), encoding="utf-8")
        init(course_dir, path)
    course = Course.load(course_dir)
    name = "01 - Errante demo"
    new_video(course_dir, name)
    video = course.production_dir / name
    (video / "guion-v1.md").write_text(render(TEMPLATES / "errante-demo/guion.en.md",
                                               {"date": datetime.date.today().isoformat()}), encoding="utf-8")
    shutil.copyfile(TEMPLATES / "errante-demo/tomas.py", video / "tomas.py")
    demo_cards(video)
    print("English narration; no subtitles. Confirm delivery.team/members in course.yaml before final delivery.")


def main(argv=None):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    p = argparse.ArgumentParser(prog="scaffold.py")
    sub = p.add_subparsers(dest="command", required=True)
    a_init = sub.add_parser("init")
    a_init.add_argument("course_dir")
    a_init.add_argument("--answers", required=True)
    a_init.add_argument("--force", action="store_true")
    a_video = sub.add_parser("video")
    a_video.add_argument("course_dir")
    a_video.add_argument("name")
    a_deck = sub.add_parser("deck")
    a_deck.add_argument("course_dir")
    a_demo = sub.add_parser("demo")
    a_demo.add_argument("course_dir")
    a_demo.add_argument("--base-url")
    a_cards = sub.add_parser("cards")
    a_cards.add_argument("video_dir")
    a = p.parse_args(sys.argv[1:] if argv is None else argv)
    if a.command == "init":
        init(a.course_dir, a.answers, a.force)
    elif a.command == "video":
        new_video(a.course_dir, a.name)
    elif a.command == "demo":
        demo(a.course_dir, a.base_url)
    elif a.command == "cards":
        demo_cards(a.video_dir)
    else:
        redo_deck(a.course_dir)


if __name__ == "__main__":
    main()
