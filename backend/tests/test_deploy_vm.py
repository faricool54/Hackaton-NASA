"""Deployment helper boundaries; no credentials, network or resource creation."""

import runpy
import shlex
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
HELPER = runpy.run_path(str(ROOT / "scripts/deploy_vm.py"))


def test_remote_deploy_uses_root_owned_archive_lock_and_stable_volume_project():
    revision = "a" * 40
    archive = f"errante-release-{revision}.tar.gz"
    command = HELPER["remote_command"](revision, archive, "errante.example.org")
    assert "sudo install -m 0600" in command and "/opt/errante/uploads/" in command
    assert "sudo flock -w 600 /opt/errante/deploy.lock" in command
    # Verify the complete script survives the SSH/bash quoting layer, including printf's literal newline escape.
    script = shlex.split(command)[-1]
    assert "docker compose -p errante" in script and "ERRANTE_DOMAIN=errante.example.org" in script
    assert f"/opt/errante/releases/{revision}" in script and "current-revision" in script
    assert "down" not in script and "prune" not in script


@pytest.mark.parametrize("domain", ["https://example.org", "site;whoami", "example.org\nother", "example.org/path"])
def test_remote_domain_cannot_inject_shell_or_caddy_config(domain):
    revision = "b" * 40
    with pytest.raises(ValueError):
        HELPER["remote_command"](revision, f"errante-release-{revision}.tar.gz", domain)


def test_windows_sdk_wrapper_uses_python_without_a_command_shell(tmp_path):
    sdk = tmp_path / "Cloud SDK with spaces"
    wrapper = sdk / "bin/gcloud.cmd"
    wrapper.parent.mkdir(parents=True)
    wrapper.touch()
    entry = sdk / "lib/gcloud.py"
    entry.parent.mkdir()
    entry.touch()
    interpreter = sdk / "platform/bundledpython/python.exe"
    interpreter.parent.mkdir(parents=True)
    interpreter.touch()
    assert HELPER["gcloud_command"](str(wrapper)) == [str(interpreter), str(entry)]
