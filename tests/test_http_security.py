"""C5 (request-body size cap) + N13 (security response headers)."""

from __future__ import annotations

from pathlib import Path

import httpx

from plantpal.config import Settings
from plantpal.db import init_db
from plantpal.main import create_app

MIGRATIONS_DIR = Path(__file__).resolve().parent.parent / "migrations"


# --- C5: body-size limit --------------------------------------------------------


async def test_oversized_body_rejected_with_413(client):
    big = b'{"email":"' + b"a" * (13 * 1024 * 1024) + b'"}'  # > 12 MB default cap
    r = await client.post(
        "/auth/request-login", content=big, headers={"content-type": "application/json"}
    )
    assert r.status_code == 413
    assert r.json()["error"]["code"] == "payload_too_large"


async def test_normal_body_passes(client):
    r = await client.post("/auth/request-login", json={"email": "nobody@example.de"})
    assert r.status_code == 200  # generic enumeration-safe ok


async def test_oversized_chunked_body_rejected_with_413(client):
    # No Content-Length (streamed/chunked): the middleware buffers up to the cap and must still
    # return a clean 413 with our error contract — not let FastAPI's parser turn it into a 400.
    async def gen():
        chunk = b"a" * (1024 * 1024)
        for _ in range(13):  # 13 MB streamed, > 12 MB cap, sent without Content-Length
            yield chunk

    r = await client.post(
        "/auth/request-login", content=gen(), headers={"content-type": "application/json"}
    )
    assert r.status_code == 413
    assert r.json()["error"]["code"] == "payload_too_large"


async def test_chunked_body_within_cap_passes(client):
    # A streamed body under the cap is buffered + replayed intact, so the route still parses it.
    async def gen():
        yield b'{"email":"streamed@example.de"}'

    r = await client.post(
        "/auth/request-login", content=gen(), headers={"content-type": "application/json"}
    )
    assert r.status_code == 200


async def test_413_still_carries_security_headers(client):
    big = b'{"email":"' + b"a" * (13 * 1024 * 1024) + b'"}'
    r = await client.post(
        "/auth/request-login", content=big, headers={"content-type": "application/json"}
    )
    assert r.status_code == 413
    # SecurityHeaders sits outside BodySizeLimit, so even the short-circuit is decorated.
    assert r.headers["x-content-type-options"] == "nosniff"


# --- N13: security headers ------------------------------------------------------


async def test_security_headers_present(client):
    r = await client.get("/api/health")
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["x-frame-options"] == "DENY"
    assert r.headers["referrer-policy"] == "no-referrer"
    assert "geolocation=()" in r.headers["permissions-policy"]
    csp = r.headers["content-security-policy"]
    assert "default-src 'self'" in csp
    assert "frame-ancestors 'none'" in csp
    assert "object-src 'none'" in csp
    # HSTS must NOT be sent outside production (dev/test is plain http).
    assert "strict-transport-security" not in r.headers


async def test_hsts_only_in_production(tmp_path):
    settings = Settings(
        _env_file=None,
        APP_ENV="production",
        BASE_URL="https://x.example",
        DB_PATH=str(tmp_path / "p.db"),
        IMAGE_DIR=str(tmp_path / "img"),
        TOKEN_PEPPER="p" * 48,
        CSRF_SECRET="c" * 48,
        RESEND_API_KEY="re_x",
        RESEND_FROM_EMAIL="PlantPal <noreply@x.example>",
    )
    db = await init_db(settings, MIGRATIONS_DIR)
    try:
        app = create_app(settings=settings, db=db)
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="https://x.example") as c:
            r = await c.get("/")  # SPA fallback — no DB needed, middleware still applies
            assert r.headers["strict-transport-security"] == "max-age=63072000; includeSubDomains"
    finally:
        await db.close()
