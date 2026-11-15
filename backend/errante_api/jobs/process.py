"""Owned process termination and bounded output; never kill an unverified saved PID."""

from __future__ import annotations

import os
import signal
import sys
import threading
from pathlib import Path

import psutil


def tree_bytes(root: Path) -> int:
    total = 0
    for path in root.rglob("*"):
        try:
            if path.is_file() and not path.is_symlink():
                total += path.stat().st_size
        except FileNotFoundError:
            pass
    return total


def kill_tree(proc, grace: float = 2) -> None:
    try:
        parent = psutil.Process(proc.pid)
        if sys.platform == "win32" and parent.pid != os.getpid():
            # A Windows venv launcher can spawn Python AFTER a children() snapshot,
            # leaving an orphan holding stdout/log files open. Freeze each parent
            # before discovering its children so no late launch escapes termination.
            children = []
            pending = [parent]
            while pending:
                member = pending.pop()
                try:
                    member.suspend()
                    born = member.children()
                    children.extend(born)
                    pending.extend(born)
                except psutil.NoSuchProcess:
                    pass
        else:
            # The watchdog cannot suspend itself; POSIX also kills the launch session below.
            children = parent.children(recursive=True)
        for child in reversed(children):
            try:
                child.terminate()
            except psutil.NoSuchProcess:
                pass
        _, alive = psutil.wait_procs(children, timeout=grace)
        for child in alive:
            try:
                child.kill()
            except psutil.NoSuchProcess:
                pass
        _, alive = psutil.wait_procs(alive, timeout=grace)
        # POSIX descendants are reaped by their parent/init, not by this process.
        # A zombie has exited and cannot be killed again; still stop its parent.
        if any(_executing(child) for child in alive):
            raise RuntimeError("Unable to terminate owned build processes")
        if parent.pid == os.getpid():
            parent.kill()  # Owner watchdog: descendants are already gone.
        parent.terminate()
        try:
            parent.wait(timeout=grace)
        except psutil.TimeoutExpired:
            parent.kill()
            parent.wait(timeout=grace)
    except psutil.NoSuchProcess:
        pass
    # A new POSIX session belongs to this launch, including descendants whose
    # parent exited during termination. Database-recovered PIDs are verified first.
    if sys.platform != "win32":
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass


def _executing(process) -> bool:
    try:
        return process.is_running() and process.status() != psutil.STATUS_ZOMBIE
    except psutil.NoSuchProcess:
        return False


def stop_saved_child(pid: int | None, request_path: Path) -> None:
    if pid is None:
        return
    try:
        process = psutil.Process(pid)
        command = process.cmdline()
        if "errante_api.jobs.child" not in command or str(request_path) not in command:
            return  # The old PID was reused by an unrelated process.
        kill_tree(process)
    except psutil.NoSuchProcess:
        pass
    # AccessDenied is deliberately fatal: don't start another build without
    # establishing whether the old one is still running.


def collect_log(proc, path: Path, limit: int) -> threading.Thread:
    def drain():
        marker = b"\n[output truncated]\n"
        remaining = max(0, limit - len(marker))
        truncated = False
        with path.open("wb") as stream:
            while block := proc.stdout.read(65536):
                stream.write(block[:remaining])
                if len(block) > remaining:
                    truncated = True
                remaining = max(0, remaining - len(block))
            if truncated:
                stream.write(marker)
        proc.stdout.close()

    thread = threading.Thread(target=drain, name="build-output", daemon=True)
    thread.start()
    return thread
