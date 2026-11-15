"""Catalog context of a position or a name for the object card (GET /api/object, contract 0.5.0, C05).

The science lives in WS3 (``errante.science.context``): this module only bounds it. The lookup runs off the event
loop in a dedicated LiveService (bounded workers, single-flight, validated memory + disk cache) and WS3 keeps its
own raw-response disk cache (``context_cache_dir``). Each HTTP call to a catalog has a transport timeout
(``object_service_timeout_s``) and the whole lookup a deadline (``object_deadline_s``) below
``ERRANTE_API_TIMEOUT_S``. When the deadline passes, the lookup keeps running in the background (Python threads
cannot be killed) and the endpoint answers with a PARTIAL result replayed offline from what already reached the
WS3 disk cache: services that had not answered are reported as unanswered (unknown, not negative). Partial
results are never served from the API cache, so a retry gets the full context once the lookup has finished.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
from dataclasses import replace
from pathlib import Path

from fastapi import HTTPException
from pydantic import TypeAdapter

from errante.models import ObjectContextResponse

from .live_service import LiveService
from .settings import Settings

log = logging.getLogger(__name__)
_adapter = TypeAdapter(ObjectContextResponse)


def deadlines(settings: Settings) -> tuple[float, float, float]:
    """(lookup deadline, offline replay bound, per-request transport timeout) [s], all below the API timeout."""
    from errante.science import context as C

    total = settings.live_timeout_s
    derived = total - min(5.0, 0.2 * total)
    deadline = settings.object_deadline_s or derived
    if not deadline < total:
        log.warning("ERRANTE_OBJECT_DEADLINE_S must stay below ERRANTE_API_TIMEOUT_S; using %.1f s", derived)
        deadline = derived
    replay = 0.8 * (total - deadline)
    service = settings.object_service_timeout_s or min(C.CONTEXT_TIMEOUT_S, max(1.0, deadline / 2))
    return deadline, replay, min(service, deadline)


class ObjectService:
    def __init__(self, settings: Settings):
        from errante.science import context as C

        self.settings = settings
        self.deadline_s, self.replay_s, self.service_timeout_s = deadlines(settings)
        self.cache_dir = settings.context_cache_dir
        # Results change with the WS3 matching rules: the module's content is part of the cache identity.
        self._revision = hashlib.sha256(Path(C.__file__).read_bytes()).hexdigest()[:16]
        self._live = LiveService(
            replace(
                settings,
                live_cache_dir=settings.live_cache_dir / "object-context",
                live_timeout_s=self.deadline_s,
                live_max_concurrent=settings.object_max_concurrent,
            )
        )

    def close(self) -> None:
        self._live.close()

    def _lookup(self, query: dict, *, offline: bool):
        from errante.science import context as C

        return C.object_context(
            query["ra"],
            query["dec"],
            name=query["name"],
            epoch_mjd=query["epoch_mjd"],
            radius_arcsec=query["radius_arcsec"],
            cache_dir=self.cache_dir,
            timeout_s=self.service_timeout_s,
            offline=offline,
        )

    async def describe(
        self,
        *,
        ra: float | None = None,
        dec: float | None = None,
        name: str | None = None,
        epoch_mjd: float | None = None,
        radius_arcsec: float | None = None,
    ) -> ObjectContextResponse:
        from errante.science import context as C

        query = {
            "ra": ra,
            "dec": dec,
            "name": name,
            "epoch_mjd": C.DEFAULT_EPOCH_MJD if epoch_mjd is None else float(epoch_mjd),
            "radius_arcsec": C.DEFAULT_RADIUS_ARCSEC if radius_arcsec is None else float(radius_arcsec),
        }

        def run() -> ObjectContextResponse:
            try:
                ctx = self._lookup(query, offline=False)
            except C.ContextError as error:
                raise _name_error(error, name) from error
            return C.to_response(ctx)

        try:
            return await self._live.call(
                "object-context",
                {**query, "context_revision": self._revision},
                run,
                _adapter,
                cache_validator=lambda r: not r.partial,  # a gap is retried, never served from the API cache
            )
        except HTTPException as error:
            if error.status_code != 504:
                raise
        # Deadline: answer with what already reached the WS3 disk cache (offline replay, local files only).
        try:
            ctx = await asyncio.wait_for(
                asyncio.to_thread(self._lookup, query, offline=True), timeout=max(0.2, self.replay_s)
            )
        except C.ContextError as error:
            if error.not_found:
                raise _name_error(error, name) from error
            raise HTTPException(
                504, f"The name could not be resolved within {self.deadline_s:.0f} s; retry later."
            ) from error
        except Exception as error:  # noqa: BLE001 - a failed replay leaves the plain deadline error
            log.warning("Offline replay of the object context failed", exc_info=True)
            raise HTTPException(504, "Catalog lookup timed out; retry later.") from error
        return C.to_response(ctx, replay_deadline_s=self.deadline_s)


def _name_error(error, name: str | None) -> HTTPException:
    if getattr(error, "not_found", False):
        return HTTPException(404, f"Name not found by SIMBAD/Sesame (CfA): {name!r}.")
    return HTTPException(502, "The name resolver (Sesame at CfA) could not be reached; retry later.")
