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
GET /data/...                         static files (frame PNGs, thumbnails)
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from errante import __version__
from errante.models import SCHEMA_VERSION
from errante.products import ProductStore

from .routes import live, products, resolve
from .settings import Settings


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings.from_env()
    app = FastAPI(
        title="Errante API",
        version=__version__,
        description="SPHEREx moving-object explorer",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET"],
        allow_headers=["*"],
    )
    app.state.store = ProductStore(settings.data_dir)

    @app.get("/api/health")
    def health() -> dict:
        store: ProductStore = app.state.store
        has_manifest = store.manifest_path.exists()
        return {
            "status": "ok" if has_manifest else "no-data",
            "version": __version__,
            "schema_version": SCHEMA_VERSION,
            "data_dir": str(store.root),
            "synthetic": store.read_manifest().synthetic if has_manifest else None,
        }

    app.include_router(products.router, prefix="/api")
    app.include_router(live.router, prefix="/api")
    app.include_router(resolve.router, prefix="/api")
    if settings.data_dir.exists():
        app.mount("/data", StaticFiles(directory=settings.data_dir), name="data")
    return app


app = create_app()
