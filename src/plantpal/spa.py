"""Serve the built React SPA with a history-API fallback to index.html."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles


def mount_spa(app: FastAPI, static_dir: str) -> None:
    """Mount built frontend assets and a catch-all that returns index.html.

    No-op if the build directory is absent (e.g. backend-only dev / tests).
    """
    root = Path(static_dir)
    index = root / "index.html"
    if not index.exists():
        return

    assets = root / "assets"
    if assets.is_dir():
        app.mount("/assets", StaticFiles(directory=assets), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa_fallback(full_path: str) -> FileResponse:
        candidate = root / full_path
        if full_path and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(index)
