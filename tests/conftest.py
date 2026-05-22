"""Shared pytest fixtures: settings, db (tmp), and an ASGI client."""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path

import aiosqlite
import httpx
import pytest
import pytest_asyncio

from plantpal.config import Settings
from plantpal.db import init_db

PROJECT_ROOT = Path(__file__).resolve().parent.parent
MIGRATIONS_DIR = PROJECT_ROOT / "migrations"


@pytest.fixture
def migrations_dir() -> Path:
    return MIGRATIONS_DIR


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(
        _env_file=None,  # ignore any local .env so tests stay deterministic
        APP_ENV="test",
        BASE_URL="http://testserver",
        DB_PATH=str(tmp_path / "test.db"),
        IMAGE_DIR=str(tmp_path / "images"),
        TOKEN_PEPPER="test-pepper",
        CSRF_SECRET="test-csrf",
        RESEND_API_KEY="",
        AUTH_REQUEST_MIN_MS=0,  # no anti-enumeration padding delay in tests
    )


@pytest_asyncio.fixture
async def db(settings: Settings) -> AsyncIterator[aiosqlite.Connection]:
    conn = await init_db(settings, MIGRATIONS_DIR)
    try:
        yield conn
    finally:
        await conn.close()


@pytest_asyncio.fixture
async def client(settings: Settings, db: aiosqlite.Connection) -> AsyncIterator[httpx.AsyncClient]:
    """ASGI client sharing the test DB (no lifespan: scheduler off in APP_ENV=test)."""
    from plantpal.main import create_app

    app = create_app(settings=settings, db=db)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url=settings.BASE_URL) as c:
        yield c
