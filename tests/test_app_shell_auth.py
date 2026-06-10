"""Native-Shell-Auth (Capacitor): App-Origins + Bearer-Token-Pfad, mit PROD-Settings.

Session-Verify-Findings: APP_ENV=test erlaubt jede localhost-Origin (Dev-Fallback), daher
MÜSSEN diese Tests Produktions-Settings bauen — sonst beweisen sie nichts. Der Pfad:
verify-code (client:"app") liefert den Session-Token im Body; alle weiteren Calls laufen
über Authorization: Bearer (CSRF-immun: der Header ist cross-site nicht setzbar, und
current_user gibt ihm Vorrang vor Cookies).
"""

from __future__ import annotations

import httpx
import pytest

from plantpal import auth_service
from plantpal.config import Settings
from plantpal.db import init_db
from plantpal.deps import origin_allowed
from plantpal.main import create_app

APP_ORIGIN = "capacitor://localhost"


def _prod_settings(tmp_path, **overrides) -> Settings:
    base = dict(
        _env_file=None,
        APP_ENV="production",
        BASE_URL="https://getplantpal.com",
        DB_PATH=str(tmp_path / "shell.db"),
        IMAGE_DIR=str(tmp_path / "img"),
        TOKEN_PEPPER="x" * 48,
        CSRF_SECRET="y" * 48,
        RESEND_API_KEY="re_test_key",
        RESEND_FROM_EMAIL="PlantPal <gruss@getplantpal.com>",
        ALLOWED_APP_ORIGINS=APP_ORIGIN,
        REVIEW_ACCOUNT_EMAIL="review@getplantpal.com, review2@getplantpal.com",
        REVIEW_LOGIN_CODE="734291",
    )
    base.update(overrides)
    s = Settings(**base)
    s.validate_runtime()
    return s


def test_origin_allowed_app_origins_prod(tmp_path):
    s = _prod_settings(tmp_path)
    assert origin_allowed(APP_ORIGIN, s) is True
    assert origin_allowed("capacitor://localhost/", s) is True  # normalisiert
    assert origin_allowed("https://localhost", s) is False  # nicht gelistet
    assert origin_allowed("https://evil.example", s) is False
    # Ohne Konfiguration bleibt prod strikt BASE_URL-only:
    bare = _prod_settings(tmp_path, ALLOWED_APP_ORIGINS="")
    assert origin_allowed(APP_ORIGIN, bare) is False


def test_review_login_code_format_enforced(tmp_path):
    with pytest.raises(ValueError, match="6 digits"):
        _prod_settings(tmp_path, REVIEW_LOGIN_CODE="PlantPal2026")
    with pytest.raises(ValueError, match="set together"):
        _prod_settings(tmp_path, REVIEW_LOGIN_CODE="")


async def _shell_client(tmp_path):
    s = _prod_settings(tmp_path)
    db = await init_db(s)
    app = create_app(settings=s, db=db)
    transport = httpx.ASGITransport(app=app)
    client = httpx.AsyncClient(transport=transport, base_url=s.BASE_URL)
    return s, db, client


async def test_shell_bearer_flow_end_to_end(tmp_path):
    """Shell-Origin → Review-Code-Login mit client:"app" → Bearer für GET + Mutation,
    ganz ohne Cookie/CSRF-Header (beides ist der Shell strukturell unmöglich)."""
    s, db, client = await _shell_client(tmp_path)
    try:
        await auth_service.bootstrap_admin(db, s, "review@getplantpal.com")
        r = await client.post(
            "/auth/verify-code",
            json={"email": "review@getplantpal.com", "code": "734291", "client": "app"},
            headers={"origin": APP_ORIGIN},
        )
        assert r.status_code == 200, r.text
        token = r.json()["session_token"]
        assert token

        bearer = {"Authorization": f"Bearer {token}"}
        client.cookies.clear()  # die Shell hat KEINE Cookies — nur der Header zählt
        assert (await client.get("/api/me", headers=bearer)).status_code == 200

        # Mutation ohne X-CSRF-Token: Bearer ist CSRF-immun → 201 statt 403
        r = await client.post(
            "/api/plants",
            data={"name": "Shell-Pflanze", "interval_days": "7"},
            headers={**bearer, "origin": APP_ORIGIN},
        )
        assert r.status_code == 201, r.text

        # CORS-Preflight wird beantwortet (Middleware aktiv, Origin gelistet)
        r = await client.options(
            "/auth/verify-code",
            headers={
                "origin": APP_ORIGIN,
                "access-control-request-method": "POST",
                "access-control-request-headers": "authorization,content-type",
            },
        )
        assert r.status_code == 200
        assert r.headers["access-control-allow-origin"] == APP_ORIGIN
    finally:
        await client.aclose()
        await db.close()


async def test_shell_rejected_without_configured_origin(tmp_path):
    """Ohne ALLOWED_APP_ORIGINS bleibt die Shell ausgesperrt (kein stiller Default)."""
    s = _prod_settings(tmp_path, ALLOWED_APP_ORIGINS="")
    db = await init_db(s)
    app = create_app(settings=s, db=db)
    client = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url=s.BASE_URL)
    try:
        await auth_service.bootstrap_admin(db, s, "review@getplantpal.com")
        r = await client.post(
            "/auth/verify-code",
            json={"email": "review@getplantpal.com", "code": "734291", "client": "app"},
            headers={"origin": APP_ORIGIN},
        )
        assert r.status_code == 403
    finally:
        await client.aclose()
        await db.close()


async def test_web_verify_code_response_has_no_token(tmp_path):
    """Web-Clients (ohne client:"app") bekommen NIE einen Token im Body — Cookie only."""
    s, db, client = await _shell_client(tmp_path)
    try:
        await auth_service.bootstrap_admin(db, s, "review2@getplantpal.com")
        r = await client.post(
            "/auth/verify-code",
            json={"email": "review2@getplantpal.com", "code": "734291"},
            headers={"origin": s.BASE_URL},
        )
        assert r.status_code == 200
        assert "session_token" not in r.json()
    finally:
        await client.aclose()
        await db.close()


async def test_review_code_expiry_disables_path(tmp_path):
    s, db, client = await _shell_client(tmp_path)
    try:
        await auth_service.bootstrap_admin(db, s, "review@getplantpal.com")
        expired = s.model_copy(update={"REVIEW_CODE_EXPIRES_AT": "2020-01-01 00:00:00"})
        with pytest.raises(Exception):
            await auth_service.verify_login_code(
                db, expired, "review@getplantpal.com", "734291"
            )
    finally:
        await client.aclose()
        await db.close()
