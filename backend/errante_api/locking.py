"""OS-backed locks shared by threads and processes (WS4, Codex-assisted)."""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path


class FileLock:
    def __init__(self, path: Path, timeout: float = 10):
        self.path = path
        self.timeout = timeout
        self._fd: int | None = None

    def acquire(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(self.path, os.O_CREAT | os.O_RDWR, 0o600)
        deadline = time.monotonic() + self.timeout
        try:
            while True:
                try:
                    if sys.platform == "win32":
                        import msvcrt

                        os.lseek(fd, 0, os.SEEK_SET)
                        msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
                    else:
                        import fcntl

                        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    self._fd = fd
                    return self
                except OSError:
                    if time.monotonic() >= deadline:
                        raise BlockingIOError(f"Lock is busy: {self.path}") from None
                    time.sleep(0.02)
        except BaseException:
            os.close(fd)
            raise

    def release(self):
        if self._fd is None:
            return
        fd, self._fd = self._fd, None
        try:
            if sys.platform == "win32":
                import msvcrt

                os.lseek(fd, 0, os.SEEK_SET)
                msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(fd, fcntl.LOCK_UN)
        finally:
            os.close(fd)
        # Keep the inode: unlinking a lock file lets waiters lock different files.

    def __enter__(self):
        return self.acquire()

    def __exit__(self, *_):
        self.release()
