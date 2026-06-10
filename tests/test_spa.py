import httpx
from fastapi import FastAPI

from plantpal.spa import mount_spa


async def test_spa_serves_index_assets_and_fallback(tmp_path):
    (tmp_path / "index.html").write_text("<html>plantpal-spa</html>")
    assets = tmp_path / "assets"
    assets.mkdir()
    (assets / "app.js").write_text("console.log('hi')")

    app = FastAPI()
    mount_spa(app, str(tmp_path))
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as c:
        assert "plantpal-spa" in (await c.get("/")).text
        # client-side route → history fallback to index
        assert "plantpal-spa" in (await c.get("/settings")).text
        # real asset is served directly
        r = await c.get("/assets/app.js")
        assert r.status_code == 200
        assert "console.log" in r.text


def test_mount_spa_is_noop_without_build(tmp_path):
    app = FastAPI()
    mount_spa(app, str(tmp_path))  # no index.html present → no routes registered
    assert all(getattr(r, "path", "") != "/{full_path:path}" for r in app.routes)


async def test_spa_cache_headers(tmp_path):
    """Hashed /assets are immutable-cached for a year; stable statics get a day;
    index.html stays no-cache so deploys are visible immediately (Lighthouse TTL)."""
    (tmp_path / "index.html").write_text("<html>plantpal-spa</html>")
    (tmp_path / "wordmark.png").write_bytes(b"\x89PNG fake")
    assets = tmp_path / "assets"
    assets.mkdir()
    (assets / "index-Abc123.js").write_text("console.log('hi')")

    app = FastAPI()
    mount_spa(app, str(tmp_path))
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as c:
        r = await c.get("/assets/index-Abc123.js")
        assert r.headers["cache-control"] == "public, max-age=31536000, immutable"
        r = await c.get("/wordmark.png")
        assert r.headers["cache-control"] == "public, max-age=86400"
        for path in ("/", "/settings"):
            r = await c.get(path)
            assert r.headers["cache-control"] == "no-cache"
