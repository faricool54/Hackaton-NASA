"""Bounded archive calls and validated TTL cache (WS4; assisted by OpenAI Codex).

A request deadline does not kill Python threads. Admission remains occupied
until the underlying call actually finishes, so repeated timeouts cannot spawn
unbounded work. WS1/WS3 must also set transport timeouts inside their clients.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import threading
import time
from collections import OrderedDict
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import TypeVar

import requests
from fastapi import HTTPException
from pydantic import TypeAdapter

from errante import __version__
from errante import settings as core
from errante.models import SCHEMA_VERSION

from .settings import Settings

T = TypeVar("T")
log = logging.getLogger(__name__)


class LiveService:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._pool = ThreadPoolExecutor(max_workers=settings.live_max_concurrent, thread_name_prefix="archive")
        self._slots = threading.BoundedSemaphore(settings.live_max_concurrent)
        self._lock = threading.Lock()
        self._memory: OrderedDict[str, tuple[float, object]] = OrderedDict()

    def close(self) -> None:
        self._pool.shutdown(wait=False, cancel_futures=True)

    def _path(self, key: str) -> Path:
        return self.settings.live_cache_dir / f"{key}.json"

    def _read(self, key: str, adapter: TypeAdapter[T]) -> T | None:
        now = time.time()
        with self._lock:
            entry = self._memory.get(key)
            if entry and entry[0] > now:
                self._memory.move_to_end(key)
                return adapter.validate_python(entry[1])
            self._memory.pop(key, None)
        try:
            entry = json.loads(self._path(key).read_text(encoding="utf-8"))
            json.dumps(entry, allow_nan=False)
            # Recompute TTL too: reducing the configured TTL invalidates old entries.
            if not 0 <= now - entry["created_at"] < self.settings.live_cache_ttl_s:
                return None
            result = adapter.validate_python(entry["value"])
            self._remember(key, entry["created_at"] + self.settings.live_cache_ttl_s, entry["value"])
            return result
        except (OSError, ValueError, TypeError, KeyError):
            return None

    def _remember(self, key: str, expires: float, value: object) -> None:
        with self._lock:
            self._memory[key] = (expires, value)
            self._memory.move_to_end(key)
            while len(self._memory) > self.settings.live_cache_entries:
                self._memory.popitem(last=False)

    def _write(self, key: str, value: T, adapter: TypeAdapter[T]) -> None:
        created = time.time()
        payload = adapter.dump_python(value, mode="json")
        serialized = json.dumps({"created_at": created, "value": payload}, allow_nan=False)
        self._remember(key, created + self.settings.live_cache_ttl_s, payload)
        temporary: Path | None = None
        try:
            root = self.settings.live_cache_dir
            root.mkdir(parents=True, exist_ok=True)
            with NamedTemporaryFile(mode="w", encoding="utf-8", dir=root, suffix=".tmp", delete=False) as f:
                temporary = Path(f.name)
                f.write(serialized)
            os.replace(temporary, self._path(key))
            # Bound disk usage as well as the in-memory entry count.
            with self._lock:
                files = sorted(root.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
                for old in files[self.settings.live_cache_entries :]:
                    old.unlink(missing_ok=True)
        except OSError:
            log.warning("Unable to persist archive cache", exc_info=True)
        finally:
            if temporary is not None:
                try:
                    temporary.unlink(missing_ok=True)
                except OSError:
                    log.warning("Unable to remove temporary archive cache file")

    async def call(self, operation: str, parameters: dict, function: Callable[[], T], adapter: TypeAdapter[T]) -> T:
        identity = {
            "operation": operation,
            "parameters": parameters,
            "schema": SCHEMA_VERSION,
            "pipeline": __version__,
            "sources": [core.IRSA_SIA, core.IRSA_TAP_SYNC, core.JPL_SBIDENT, core.SKYBOT_CONESEARCH],
            "collections": list(core.IRSA_COLLECTIONS),
        }
        key = hashlib.sha256(json.dumps(identity, sort_keys=True, allow_nan=False).encode()).hexdigest()
        cached = self._read(key, adapter)
        if cached is not None:
            return cached
        if not self._slots.acquire(blocking=False):
            raise HTTPException(503, "Archive capacity is busy; retry later.", headers={"Retry-After": "2"})

        def run() -> T:
            result = adapter.validate_python(function())
            self._write(key, result, adapter)
            return result

        try:
            future = self._pool.submit(run)
        except RuntimeError as error:
            self._slots.release()
            raise HTTPException(503, "Archive service is shutting down.") from error
        future.add_done_callback(lambda _: self._slots.release())
        try:
            return await asyncio.wait_for(asyncio.wrap_future(future), timeout=self.settings.live_timeout_s)
        except NotImplementedError as error:
            raise HTTPException(501, "Archive integration is not implemented yet.") from error
        except (TimeoutError, requests.Timeout) as error:
            raise HTTPException(504, "Archive request timed out; retry later.") from error
        except Exception as error:
            # WS1 retries may wrap a transport timeout; preserve that distinction.
            cause = error.__cause__
            while cause is not None:
                if isinstance(cause, (TimeoutError, requests.Timeout)):
                    raise HTTPException(504, "Archive request timed out; retry later.") from error
                cause = cause.__cause__
            log.exception("Archive operation %s failed", operation)
            raise HTTPException(502, "Archive returned an invalid response or could not be reached.") from error
