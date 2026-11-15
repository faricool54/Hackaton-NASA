"""Deploy a committed revision to the existing team VM with each operator's own gcloud login."""

from __future__ import annotations

import argparse
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def gcloud_command(executable: str | None) -> list[str]:
    found = executable or shutil.which("gcloud") or shutil.which("gcloud.cmd")
    if not found:
        raise SystemExit("Install Google Cloud CLI or run this command in Cloud Shell; run gcloud auth login first.")
    path = Path(found).resolve()
    # Windows batch wrappers need shell expansion; call the SDK's Python entry point directly instead.
    entry = path.parent.parent / "lib" / "gcloud.py"
    if path.suffix.lower() in {".cmd", ".ps1"} and entry.is_file():
        bundled = path.parent.parent / "platform" / "bundledpython" / "python.exe"
        return [str(bundled) if bundled.is_file() else sys.executable, str(entry)]
    return [str(path)]


def remote_command(revision: str, archive: str, domain: str) -> str:
    if not re.fullmatch(r"[a-f0-9]{40}", revision):
        raise ValueError("Expected a Git commit SHA")
    if not re.fullmatch(r"[a-z0-9][a-z0-9.-]{0,251}[a-z0-9]", domain):
        raise ValueError("Expected a DNS hostname without scheme, port or path")
    if archive != f"errante-release-{revision}.tar.gz":
        raise ValueError("Unexpected release archive name")
    destination = f"/opt/errante/releases/{revision}"
    script = (
        f"set -eu; mkdir -p {destination}; "
        f"tar -xzf /opt/errante/uploads/{archive} -C {destination}; cd {destination}; "
        f"ERRANTE_DOMAIN={shlex.quote(domain)} docker compose -p errante -f backend/deploy/compose.yaml "
        "--profile https up --build -d; "
        f"printf '%s\\n' {revision} > /opt/errante/current-revision"
    )
    # Upload into root-owned storage; the flock serializes teammates' deployments.
    return (
        "set -eu; sudo install -d -m 0755 /opt/errante/uploads; "
        f"sudo install -m 0600 {shlex.quote(archive)} /opt/errante/uploads/{archive}; "
        f"sudo flock -w 600 /opt/errante/deploy.lock bash -c {shlex.quote(script)}"
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", default="project-4c470287-a034-43da-bf6")
    parser.add_argument("--zone", default="us-east1-b")
    parser.add_argument("--instance", default="errante")
    parser.add_argument("--domain", default="errante.34-148-242-13.sslip.io")
    parser.add_argument(
        "--ref", default="HEAD", help="Committed revision; fetch and use origin/main for a team release"
    )
    parser.add_argument("--gcloud", help="Optional path to the gcloud executable")
    args = parser.parse_args(argv)
    revision = subprocess.check_output(
        ["git", "rev-parse", "--verify", "--end-of-options", args.ref + "^{commit}"], cwd=ROOT, text=True
    ).strip()
    archive = f"errante-release-{revision}.tar.gz"
    command = remote_command(revision, archive, args.domain)
    cli = gcloud_command(args.gcloud)
    flags = ["--project", args.project, "--zone", args.zone, "--quiet"]
    with tempfile.TemporaryDirectory(prefix="errante-deploy-") as name:
        path = Path(name) / archive
        subprocess.run(["git", "archive", "--format=tar.gz", "-o", str(path), revision], cwd=ROOT, check=True)
        subprocess.run([*cli, "compute", "scp", str(path), f"{args.instance}:{archive}", *flags], check=True)
        subprocess.run([*cli, "compute", "ssh", args.instance, *flags, "--command", command], check=True)
    print(f"Deployed {revision}. Verify https://{args.domain} with scripts/smoke_delivery.py --live-job.")


if __name__ == "__main__":
    main()
