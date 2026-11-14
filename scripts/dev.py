#!/usr/bin/env python3
"""Cross-platform task runner (Windows / macOS / Linux). Standard library only.

    python scripts/dev.py <task>          (Windows: py scripts/dev.py <task>)

Same tasks as the Makefile (which just calls this script), so humans and agents
use ONE command on every OS:

    setup          venv (.venv) + pipeline/backend (editable) + frontend deps
    setup-science  + heavy science libs (scipy, photutils, reproject, astroquery, pyvo)
    doctor         show versions / what is missing
    demo           regenerate synthetic demo data (data/demo)
    schema         regenerate shared/schema from pipeline/errante/models.py
    validate       validate data/demo (and data/products if present)
    api            backend on http://localhost:8000 (docs at /docs)
    web            frontend on http://localhost:5173
    test           python + frontend tests
    lint           ruff check + format check
    owners         does this branch only touch files of its workstream? (scripts/owners.py)
    fmt            ruff --fix + ruff format (rewrites files)
    check          EVERYTHING CI runs. Run before every push.

Uses `uv` when it is installed (much faster), otherwise python -m venv + pip.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VENV = ROOT / ".venv"
FRONTEND = ROOT / "frontend"
WINDOWS = os.name == "nt"
BIN = VENV / ("Scripts" if WINDOWS else "bin")
PY_VERSION = "3.12"  # same as CI


def exe(name: str) -> str:
    """Path to a tool inside the venv (adds .exe on Windows)."""
    path = BIN / (f"{name}.exe" if WINDOWS else name)
    if not path.exists():
        sys.exit(f"[x] {path} not found. Run first:  python scripts/dev.py setup")
    return str(path)


def npm() -> str:
    found = shutil.which("npm.cmd" if WINDOWS else "npm") or shutil.which("npm")
    if not found:
        sys.exit("[x] npm not found. Install Node.js 20+ (https://nodejs.org).")
    return found


def run(*cmd: str, cwd: Path = ROOT, env: dict[str, str] | None = None) -> None:
    print(f"\n$ {' '.join(cmd)}" + (f"   (in {cwd.relative_to(ROOT)})" if cwd != ROOT else ""), flush=True)
    result = subprocess.run(cmd, cwd=cwd, env={**os.environ, **(env or {})})
    if result.returncode != 0:
        sys.exit(f"\n[x] failed ({result.returncode}): {' '.join(cmd)}")


def pip_install(*args: str) -> None:
    uv = shutil.which("uv")
    if uv:
        run(uv, "pip", "install", "--python", str(BIN / ("python.exe" if WINDOWS else "python")), *args)
    else:
        run(exe("python"), "-m", "pip", "install", *args)


# --- tasks -------------------------------------------------------------------


def setup_py() -> None:
    if not VENV.exists():
        uv = shutil.which("uv")
        if uv:
            run(uv, "venv", "--python", PY_VERSION, str(VENV))
        else:
            if sys.version_info < (3, 11):  # noqa: UP036 (runs on the system python)
                sys.exit(f"[x] Python >= 3.11 required (this is {sys.version.split()[0]}). Or install uv.")
            run(sys.executable, "-m", "venv", str(VENV))
            run(exe("python"), "-m", "pip", "install", "-U", "pip")
    pip_install("-e", "pipeline[dev]", "-e", "backend[dev]")


def setup_web() -> None:
    run(npm(), "ci", cwd=FRONTEND)


def setup() -> None:
    setup_py()
    setup_web()
    print("\n[ok] setup done. Next:  python scripts/dev.py web   (and/or: api)")


def setup_science() -> None:
    pip_install("-e", "pipeline[dev,science]")


def doctor() -> None:
    def version(cmd: list[str]) -> str:
        try:
            return subprocess.run(cmd, capture_output=True, text=True, check=False).stdout.strip() or "?"
        except OSError:
            return "NOT FOUND"

    print(f"repo      {ROOT}")
    print(f"python    {sys.version.split()[0]} ({sys.executable})")
    print(f"uv        {version(['uv', '--version']) if shutil.which('uv') else 'not installed (optional)'}")
    node = shutil.which("node")
    print(f"node      {version([node, '--version']) if node else 'NOT FOUND (need 20+)'}")
    print(f"venv      {'ok' if (BIN / ('python.exe' if WINDOWS else 'python')).exists() else 'missing -> setup'}")
    print(f"node_mod  {'ok' if (FRONTEND / 'node_modules').exists() else 'missing -> setup'}")
    print(f"products  {'data/products present' if (ROOT / 'data/products/manifest.json').exists() else 'none yet'}")


def demo() -> None:
    run(exe("errante"), "demo", "--out", "data/demo")


def schema() -> None:
    run(exe("errante"), "schema")


def validate() -> None:
    run(exe("errante"), "validate", "--dir", "data/demo")
    if (ROOT / "data/products/manifest.json").exists():
        run(exe("errante"), "validate", "--dir", "data/products")


def api() -> None:
    port = os.environ.get("API_PORT", "8000")  # two agents on one machine: API_PORT=8001
    run(
        exe("uvicorn"),
        "errante_api.main:app",
        "--reload",
        "--reload-dir",
        ".",
        "--reload-dir",
        "../pipeline/errante",
        "--port",
        port,
        cwd=ROOT / "backend",
    )


def web() -> None:
    run(npm(), "run", "dev", cwd=FRONTEND)


def test_py() -> None:
    run(exe("pytest"), "-q", "pipeline/tests", "backend/tests")


def test_web() -> None:
    run(npm(), "test", cwd=FRONTEND)


def test() -> None:
    test_py()
    test_web()


def lint() -> None:
    run(exe("ruff"), "check", "pipeline", "backend", "scripts")
    run(exe("ruff"), "format", "--check", "pipeline", "backend", "scripts")


def fmt() -> None:
    run(exe("ruff"), "check", "--fix", "pipeline", "backend", "scripts")
    run(exe("ruff"), "format", "pipeline", "backend", "scripts")


def owners() -> None:
    run(sys.executable, str(ROOT / "scripts" / "owners.py"))


def check() -> None:
    """Mirror of .github/workflows/ci.yml (+ the ownership guard)."""
    owners()
    lint()
    run(exe("errante"), "schema", "--check")
    validate()
    test_py()
    run(npm(), "run", "typecheck", cwd=FRONTEND)
    test_web()
    run(npm(), "run", "build", cwd=FRONTEND)
    print("\n[ok] check passed - same as CI. OK to push.")


TASKS = {
    "setup": setup,
    "setup-py": setup_py,
    "setup-web": setup_web,
    "setup-science": setup_science,
    "doctor": doctor,
    "demo": demo,
    "schema": schema,
    "validate": validate,
    "api": api,
    "web": web,
    "test": test,
    "test-py": test_py,
    "test-web": test_web,
    "lint": lint,
    "fmt": fmt,
    "owners": owners,
    "check": check,
}


def main() -> None:
    if len(sys.argv) != 2 or sys.argv[1] not in TASKS:
        print(__doc__)
        sys.exit(0 if len(sys.argv) == 1 else 2)
    try:
        TASKS[sys.argv[1]]()
    except KeyboardInterrupt:
        sys.exit(130)


if __name__ == "__main__":
    main()
