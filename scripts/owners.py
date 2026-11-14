#!/usr/bin/env python3
"""Who owns which files, and does my branch only touch mine?  (standard library only)

    python scripts/owners.py                 # check current branch vs origin/main
    python scripts/owners.py --ws ws2        # force the workstream (else from branch name / ERRANTE_WS)
    python scripts/owners.py --base origin/main --files a.py b.ts   # check an explicit list (CI)
    python scripts/owners.py --who path/to/file.py                  # print the owner of a path

The workstream comes from (first match): --ws, $ERRANTE_WS, the branch name prefix
(`ws3/...`, `contract/...`, `chore/...`) or the PR title prefix in $PR_TITLE (`ws3: ...`).

Exit code 1 when a `wsN` branch touches files owned by another workstream or a SHARED file
(contract / coordination). Those changes go in their own PR: `contract/...` or `chore/...`.
This is a guard against agents "fixing things on the way" in someone else's folder;
it is advisory in CI (the coordinator can still merge).
"""

from __future__ import annotations

import argparse
import fnmatch
import os
import re
import subprocess
import sys

# Order matters: first matching pattern wins. Keep in sync with AGENTS.md (ownership table).
OWNERS: list[tuple[str, str]] = [
    # --- contract: only via `contract/...` branches / `contract:` PRs
    ("pipeline/errante/models.py", "contract"),
    ("pipeline/errante/products.py", "contract"),
    ("shared/schema/*", "contract"),
    ("frontend/src/api/types.ts", "contract"),
    ("data/demo/*", "contract"),
    ("pipeline/tests/test_contract.py", "contract"),
    # --- WS1 data
    ("pipeline/errante/data/*", "ws1"),
    ("pipeline/errante/settings.py", "ws1"),
    ("pipeline/tests/test_data_*", "ws1"),
    ("pipeline/tests/fixtures/ws1/*", "ws1"),
    ("pipeline/tests/test_network.py", "ws1"),
    ("data/index/*", "ws1"),
    ("docs/DATA.md", "ws1"),
    # --- WS2 imaging / build
    ("pipeline/errante/imaging/*", "ws2"),
    ("pipeline/errante/detect/*", "ws2"),
    ("pipeline/errante/build.py", "ws2"),
    ("pipeline/errante/synthetic.py", "ws2"),
    ("pipeline/tests/test_imaging_*", "ws2"),
    ("pipeline/tests/test_detect_*", "ws2"),
    ("pipeline/tests/test_build_*", "ws2"),
    ("pipeline/tests/fixtures/ws2/*", "ws2"),
    ("data/products/*", "ws2"),
    ("pipeline/tests/test_synthetic.py", "ws2"),
    ("pipeline/tests/test_grid_motion_flags.py", "ws2"),
    # --- WS3 science / targets
    ("pipeline/errante/science/*", "ws3"),
    ("pipeline/errante/config/*", "ws3"),
    ("pipeline/tests/test_science_*", "ws3"),
    ("pipeline/tests/fixtures/ws3/*", "ws3"),
    ("docs/SCIENCE.md", "ws3"),
    # --- WS4 backend / CI / tooling / deploy
    ("backend/*", "ws4"),
    (".github/*", "ws4"),
    ("Makefile", "ws4"),
    ("scripts/*", "ws4"),
    ("render.yaml", "ws4"),
    ("fly.toml", "ws4"),
    ("railway.json", "ws4"),
    ("Dockerfile", "ws4"),
    # --- WS7 3D systems (branch claude/ecstatic-turing-rcu8jq; must come before frontend/*)
    ("pipeline/errante/systems/*", "ws7"),
    ("pipeline/tests/test_systems.py", "ws7"),
    ("frontend/src/three/*", "ws7"),
    ("frontend/src/components/SystemViewer.tsx", "ws7"),
    ("frontend/src/components/BodyPanel.tsx", "ws7"),
    ("frontend/src/pages/SystemsPage.tsx", "ws7"),
    ("frontend/src/pages/SystemPage.tsx", "ws7"),
    ("docs/VISION_3D.md", "ws7"),
    # --- WS5 frontend
    ("frontend/*", "ws5"),
    # --- WS6 submission
    ("docs/submission/*", "ws6"),
    ("docs/CHALLENGE.md", "ws6"),
    # --- coordination (one person; `chore/...` branches)
    ("tasks/WS1-*", "ws1"),
    ("tasks/WS2-*", "ws2"),
    ("tasks/WS3-*", "ws3"),
    ("tasks/WS4-*", "ws4"),
    ("tasks/WS5-*", "ws5"),
    ("tasks/WS6-*", "ws6"),
    ("tasks/WS7-*", "ws7"),
    ("*", "coordination"),
]

# Files a wsN branch may touch even if owned by someone else (shared, append-only or harmless).
ALWAYS_OK = {"pipeline/errante/cli.py", "pipeline/pyproject.toml", "notebooks/*"}

# What each kind of branch may touch, besides its own files.
EXTRA = {
    "contract": {"contract", "ws3", "ws2"},  # contract PRs regenerate schema/types/demo (synthetic.py)
    "chore": {"coordination", "contract", "ws1", "ws2", "ws3", "ws4", "ws5", "ws6", "ws7"},  # coordinator only
}


def owner_of(path: str) -> str:
    path = path.replace("\\", "/")
    for pattern, owner in OWNERS:
        if fnmatch.fnmatch(path, pattern):
            return owner
    return "coordination"


def detect_ws(explicit: str | None) -> str | None:
    if explicit:
        return explicit.lower()
    if os.environ.get("ERRANTE_WS"):
        return os.environ["ERRANTE_WS"].lower()
    for text in (os.environ.get("PR_TITLE", ""), os.environ.get("GITHUB_HEAD_REF", ""), current_branch()):
        m = re.match(r"^\s*(ws[1-7]|contract|chore)\b", text or "", re.IGNORECASE)
        if m:
            return m.group(1).lower()
    return None


def current_branch() -> str:
    try:
        return subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"], capture_output=True, text=True, check=True
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return ""


def changed_files(base: str) -> list[str]:
    out = subprocess.run(["git", "diff", "--name-only", f"{base}...HEAD"], capture_output=True, text=True, check=False)
    if out.returncode != 0:
        print(f"[!] cannot diff against {base} (run: git fetch origin). Ownership check skipped.")
        return []
    files = out.stdout.split()
    # also uncommitted / staged changes, so agents can check before committing
    for cmd in (
        ["git", "diff", "--name-only"],
        ["git", "diff", "--name-only", "--cached"],
        ["git", "ls-files", "--others", "--exclude-standard"],  # new files agents created
    ):
        files += subprocess.run(cmd, capture_output=True, text=True, check=False).stdout.split()
    return sorted(set(files))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ws", help="ws1..ws7 | contract | chore")
    ap.add_argument("--base", default="origin/main")
    ap.add_argument("--files", nargs="*", help="explicit file list instead of git diff")
    ap.add_argument("--who", help="print the owner of one path and exit")
    args = ap.parse_args()

    if args.who:
        print(owner_of(args.who))
        return 0

    ws = detect_ws(args.ws)
    files = args.files if args.files is not None else changed_files(args.base)
    if not files:
        print("[ok] no changes")
        return 0
    if ws is None:
        print("[!] unknown workstream: name your branch wsN/..., contract/... or chore/... (or set ERRANTE_WS)")
        for f in files:
            print(f"    {owner_of(f):13} {f}")
        return 0

    allowed = {ws} | EXTRA.get(ws, set())
    foreign = [
        (f, owner_of(f))
        for f in files
        if owner_of(f) not in allowed and not any(fnmatch.fnmatch(f, p) for p in ALWAYS_OK)
    ]
    if not foreign:
        print(f"[ok] {len(files)} file(s), all within {ws}")
        return 0
    print(f"[x] branch for {ws} touches files owned by others:")
    for f, owner in foreign:
        print(f"    {owner:13} {f}")
    print(
        "\nMove those changes to their own PR (contract/... for the contract, chore/... for coordination docs)\n"
        "or ask the owner in the team chat. See docs/COLLABORATION.md."
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
