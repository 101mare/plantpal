"""Shared FastAPI dependencies + helpers used by the route modules in ``routes/``.

Per-request DB connection, current user, CSRF/origin checks and session cookies all
live here so the route modules can stay thin and import a single, stable surface.
"""

from __future__ import annotations

from fastapi import Depends, Request, Response

from . import auth_service
from .config import Settings
from .db import connect
from .errors import AuthError, CsrfError, ForbiddenError
from .security import create_csrf_token, hash_ip, verify_csrf_token

# --- cookies ---


def set_auth_cookies(response: Response, settings: Settings, session_token: str) -> None:
    max_age = settings.SESSION_SOFT_CAP_DAYS * 86400
    secure = settings.secure_cookies
    response.set_cookie(
        settings.COOKIE_NAME,
        session_token,
        max_age=max_age,
        httponly=True,
        secure=secure,
        samesite="lax",
        path="/",
    )
    response.set_cookie(
        settings.CSRF_COOKIE_NAME,
        create_csrf_token(session_token, settings),
        max_age=max_age,
        httponly=False,
        secure=secure,
        samesite="lax",
        path="/",
    )


def clear_auth_cookies(response: Response, settings: Settings) -> None:
    response.delete_cookie(settings.COOKIE_NAME, path="/")
    response.delete_cookie(settings.CSRF_COOKIE_NAME, path="/")


# --- DB + settings ---


async def get_db(request: Request):
    """Per-request connection in prod (transaction isolation — each request gets its own
    SQLite transaction, so a rollback in one request can't undo another's writes). Tests
    inject one shared connection (APP_ENV=test) and keep the M1 fixture behaviour."""
    app = request.app
    if app.state.settings.APP_ENV == "test":
        yield app.state.db
        return
    conn = await connect(app.state.settings)
    try:
        yield conn
    finally:
        await conn.close()


def settings_dep(request: Request) -> Settings:
    return request.app.state.settings


# --- auth ---


async def current_user(request: Request, db=Depends(get_db)):
    settings = request.app.state.settings
    token = request.cookies.get(settings.COOKIE_NAME)
    if not token:
        raise AuthError("Not signed in.")
    row = await auth_service.load_session(db, settings, token)
    if row is None:
        raise AuthError("Session expired.")
    await auth_service.touch_last_seen(db, settings, row["session_id"], row["last_seen_at"])
    if await auth_service.renew_session_if_needed(db, settings, row):
        request.state.renew_session_token = token  # middleware re-sets the cookie
    return auth_service.SessionUser(
        id=row["user_id"], email=row["email"], is_admin=bool(row["is_admin"])
    )


async def require_admin(user=Depends(current_user)):
    if not user.is_admin:
        raise ForbiddenError("Admin only.")
    return user


# --- CSRF / origin ---


def origin_allowed(candidate: str | None, settings: Settings) -> bool:
    """True if the request's Origin/Referer is acceptable.

    Prod: scheme+host+port must match BASE_URL *exactly* (a substring/startswith check
    would wrongly accept ``https://example.com.evil.tld`` for ``https://example.com``).
    Dev: also accept any localhost origin so a Vite dev server (:5173) talking to the
    backend (:8000) isn't rejected.
    """
    if not candidate:
        return True  # no Origin/Referer → fall back to the double-submit token check
    from urllib.parse import urlparse

    got = urlparse(candidate)
    base = urlparse(settings.BASE_URL)
    if (got.scheme, got.hostname, got.port) == (base.scheme, base.hostname, base.port):
        return True
    if not settings.is_production:
        return got.hostname in ("localhost", "127.0.0.1")
    return False


async def require_csrf(request: Request) -> None:
    settings = request.app.state.settings
    candidate = request.headers.get("origin") or request.headers.get("referer")
    if not origin_allowed(candidate, settings):
        raise CsrfError("Bad origin.")
    if not verify_csrf_token(
        request.headers.get("x-csrf-token"),
        request.cookies.get(settings.CSRF_COOKIE_NAME),
        request.cookies.get(settings.COOKIE_NAME),
        settings,
    ):
        raise CsrfError()


def require_same_origin_submit(request: Request, settings: Settings) -> None:
    """Require an explicit same-origin browser submit before issuing auth state.

    This is for unauthenticated flows that cannot use double-submit CSRF yet but
    would set a session cookie or mutate account state if consumed. Browsers can
    omit ``Origin`` for same-origin form POSTs (Safari/iOS), so ``Referer`` is a
    permitted fallback. Both absent is rejected.
    """
    candidate = request.headers.get("origin") or request.headers.get("referer")
    if not candidate or not origin_allowed(candidate, settings):
        raise CsrfError("Bad origin.")


def client_ip(request: Request) -> str:
    """Hashed client IP for rate-limit keys and request logs.

    Behind the Cloudflare Tunnel ``request.client.host`` is always the cloudflared
    container — identical for every visitor — so per-IP rate-limits would collapse to a
    single global bucket and one attacker could lock everyone out (F-DEP-7). When
    ``TRUST_CF_CONNECTING_IP`` is set we trust ``CF-Connecting-IP`` instead; only the
    tunnel can reach the origin in that deployment, so the header can't be spoofed from
    outside. Turn the flag off for any deployment where the origin is directly reachable.
    """
    settings = request.app.state.settings
    ip = request.client.host if request.client else None
    if settings.TRUST_CF_CONNECTING_IP:
        forwarded = request.headers.get("cf-connecting-ip")
        if forwarded:
            ip = forwarded.strip()
    return hash_ip(ip)
