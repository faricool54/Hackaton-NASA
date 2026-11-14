"""FastAPI app (WS4). Serves the product tree + live endpoints.

    uvicorn errante_api.main:app --reload        (or: make api)

GET /api/health                       status + which dataset is served
GET /api/manifest                     Manifest
GET /api/fields/{id}                  SkyField ("Field" in the schema)
GET /api/fields/{id}/candidates       CandidateList
GET /api/fields/{id}/known            KnownObjectList
GET /api/search?ra=&dec=              SearchResult      (live IRSA, WS1)   501 until done
GET /api/known-objects?ra=&dec=&mjd=  list[KnownObject] (live JPL, WS3)    501 until done
GET /api/resolve-name?name=           ResolvedRegion    (Sesame/CfA proxy)
POST /api/jobs                        JobStatusResponse (submit RA/Dec build job)
GET  /api/jobs/{id}                   JobStatusResponse (poll job status)
GET /data/...                         static files (frame PNGs, thumbnails)
"""

from __future__ import annotations

import logging
import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from errante import __version__
from errante.models import SCHEMA_VERSION
from errante.products import ProductStore

from .live_service import LiveService
from .routes import jobs, live, products, resolve
from .settings import Settings
from .store import PublicProductStore

log = logging.getLogger(__name__)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings.from_env()

    # Job engine: only start when explicitly enabled via env var so the
    # default dev server doesn't spin up background threads unexpectedly.
    _enable_jobs = os.environ.get("ERRANTE_ENABLE_JOBS", "").lower() in ("1", "true", "yes")

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
        if _enable_jobs:
            from .jobs.engine import JobEngine

            engine = JobEngine.from_env()
            engine.start()
            app.state.job_engine = engine
            log.info("job engine started")
        else:
            app.state.job_engine = None
        try:
            yield
        finally:
            if _enable_jobs and getattr(app.state, "job_engine", None) is not None:
                app.state.job_engine.stop()
                log.info("job engine stopped")
            app.state.live.close()

    app = FastAPI(
        title="Errante API",
        version=__version__,
        description="SPHEREx moving-object explorer",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET"],
        allow_headers=["*"],
    )
    app.state.store = PublicProductStore(settings.data_dir)
    app.state.live = LiveService(settings)

    @app.get("/api/health")
    def health() -> dict:
        store: ProductStore = app.state.store
        has_manifest = store.manifest_path.exists()
        engine = getattr(app.state, "job_engine", None)
        return {
            "status": "ok" if has_manifest else "no-data",
            "version": __version__,
            "schema_version": SCHEMA_VERSION,
            "data_dir": "configured",
            "synthetic": store.read_manifest().synthetic if has_manifest else None,
            "job_engine": "running" if (engine is not None and engine.is_running) else "disabled",
        }

    app.include_router(products.router, prefix="/api")
    app.include_router(live.router, prefix="/api")
    app.include_router(resolve.router, prefix="/api")
    app.include_router(jobs.router, prefix="/api")
    if settings.data_dir.exists():
        app.mount("/data", StaticFiles(directory=settings.data_dir), name="data")
    return app


app = create_app()
