"""Serve an optional built frontend; missing data/API/assets never become HTML."""

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException


class FrontendFiles(StaticFiles):
    async def get_response(self, path, scope):
        try:
            return await super().get_response(path, scope)
        except HTTPException as error:
            # Vite assets and data must fail normally; only browser routes get the SPA.
            if (
                error.status_code != 404
                or path.replace("\\", "/").split("/", 1)[0] in {"api", "data", "assets"}
                or Path(path).suffix
            ):
                raise
            return FileResponse(self.directory / "index.html", headers={"Cache-Control": "no-cache"})


def mount_frontend(app: FastAPI, directory: Path | None) -> None:
    if directory is None:
        return
    root = directory.resolve()
    if not (root / "index.html").is_file():
        raise ValueError("ERRANTE_WEB_DIR must contain a built frontend index.html")
    app.mount("/", FrontendFiles(directory=root, html=True), name="frontend")
