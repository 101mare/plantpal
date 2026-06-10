"""Serve the built React SPA with a history-API fallback to index.html."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

# Vite emits content-hashed filenames under /assets (index-B7bKHIXp.js) — safe to cache
# "forever"; a new build changes the hash, never the content behind a URL. Fonts/sprites/
# backgrounds under stable names get a day so a poster swap shows up promptly.
_IMMUTABLE = "public, max-age=31536000, immutable"
_DAILY = "public, max-age=86400"


class _CachedStaticFiles(StaticFiles):
    """StaticFiles with a long-lived immutable Cache-Control (content-hashed assets only)."""

    def file_response(self, *args, **kwargs):  # type: ignore[override]
        resp = super().file_response(*args, **kwargs)
        resp.headers["Cache-Control"] = _IMMUTABLE
        return resp


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
        app.mount("/assets", _CachedStaticFiles(directory=assets), name="assets")

    root_resolved = root.resolve()

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa_fallback(full_path: str) -> FileResponse:
        # Defense-in-depth: resolve and confirm the candidate stays within the static root
        # before serving it, so no normalized path can escape via traversal (SEC-04).
        candidate = (root / full_path).resolve()
        if full_path and candidate.is_file() and candidate.is_relative_to(root_resolved):
            # Stable-name statics (sprites, fonts, backgrounds, icons): cache a day.
            # index.html itself must stay revalidated so deploys show up immediately.
            return FileResponse(candidate, headers={"Cache-Control": _DAILY})
        return FileResponse(index, headers={"Cache-Control": "no-cache"})

    return None
