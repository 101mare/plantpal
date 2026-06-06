"""FastAPI app factory: lifespan, scheduler, middleware, exception handlers, SPA.

Routes live in ``routes/`` (per-domain routers); shared dependencies in ``deps``.
A DB connection and Settings live on ``app.state``; in tests they are injected, in
production the lifespan opens the DB, starts the APScheduler digest job, and runs
reboot catch-up.
"""

from __future__ import annotations

import time
from contextlib import asynccontextmanager

import aiosqlite
from fastapi import FastAPI, Request

from . import housekeeping_service, reminder_service
from .config import Settings, get_settings
from .db import connect, init_db
from .deps import client_ip, set_auth_cookies
from .errors import install_exception_handlers
from .logging_setup import configure_logging, get_logger
from .routes import register_all
from .spa import mount_spa

# Conservative CSP: same-origin only, but allow inline styles (React style props),
# plus data:/blob: images (uploaded photos + client-side preview URLs). No inline
# scripts — the Vite bundle and the N1 interstitial both load JS/forms externally.
_CSP = (
    "default-src 'self'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'; "
    "object-src 'none'; img-src 'self' data: blob:; style-src 'self' 'unsafe-inline'; "
    "script-src 'self'; font-src 'self' data:; connect-src 'self'"
)


class BodySizeLimitMiddleware:
    """Reject over-large request bodies before they are buffered into memory (C5).

    The single Uvicorn worker buffers the whole body for JSON/multipart parsing, so an
    unauthenticated multi-GB upload is a trivial OOM-DoS. Two paths:

    * Declared Content-Length over the cap → reject immediately, body never read (fast path,
      which is what every browser/fetch client hits).
    * No Content-Length (chunked) → buffer up to the cap and reject cleanly if exceeded, then
      replay the buffered body to the app. Buffering is bounded by ``max_bytes`` so it is still
      OOM-safe. (We can't simply raise mid-read: FastAPI's body parser wraps any exception from
      ``receive`` into a generic 400, so the 413 would never reach this middleware.)

    Pure-ASGI and outside the BaseHTTPMiddleware layers so a rejection never has to start the app.
    """

    def __init__(self, app, max_bytes: int) -> None:
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        for name, value in scope.get("headers", ()):
            if name == b"content-length":
                try:
                    declared = int(value)
                except ValueError:
                    break
                if declared > self.max_bytes:
                    await self._reject(send)
                    return
                # Declared and within the cap → stream through untouched, no buffering.
                await self.app(scope, receive, send)
                return

        # No Content-Length: buffer (bounded by max_bytes), reject if it overflows, else replay.
        chunks = bytearray()
        done = False
        while not done:
            message = await receive()
            if message["type"] == "http.request":
                chunks.extend(message.get("body", b""))
                if len(chunks) > self.max_bytes:
                    await self._reject(send)
                    return
                done = not message.get("more_body", False)
            else:  # http.disconnect or other — stop reading the body
                done = True

        delivered = False

        async def replay():
            nonlocal delivered
            if not delivered:
                delivered = True
                return {"type": "http.request", "body": bytes(chunks), "more_body": False}
            return await receive()

        await self.app(scope, replay, send)

    async def _reject(self, send) -> None:
        body = b'{"error":{"code":"payload_too_large","message":"Request body too large."}}'
        await send(
            {
                "type": "http.response.start",
                "status": 413,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(body)).encode()),
                ],
            }
        )
        await send({"type": "http.response.body", "body": body})


class SecurityHeadersMiddleware:
    """Attach defensive response headers to every response (N13).

    Pure-ASGI so it also decorates short-circuited responses (e.g. the 413 above) and
    error pages. HSTS is sent only in production (behind the TLS-terminating tunnel the
    origin scheme is plain http, so we key off APP_ENV, not the request scheme).
    """

    def __init__(self, app, settings: Settings) -> None:
        self.app = app
        self._headers: list[tuple[bytes, bytes]] = [
            (b"x-content-type-options", b"nosniff"),
            (b"x-frame-options", b"DENY"),
            (b"referrer-policy", b"no-referrer"),
            (b"permissions-policy", b"geolocation=(), microphone=(), camera=()"),
            (b"content-security-policy", _CSP.encode()),
        ]
        if settings.is_production:
            self._headers.append(
                (b"strict-transport-security", b"max-age=63072000; includeSubDomains")
            )

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_with_headers(message):
            if message["type"] == "http.response.start":
                headers = message.setdefault("headers", [])
                present = {k.lower() for k, _ in headers}
                headers.extend((k, v) for k, v in self._headers if k not in present)
            await send(message)

        await self.app(scope, receive, send_with_headers)


def _start_scheduler(app: FastAPI):
    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    from apscheduler.triggers.cron import CronTrigger

    settings = app.state.settings
    scheduler = AsyncIOScheduler(timezone="Europe/Berlin")

    async def _digest_job():
        # hourly: each run serves users whose chosen reminder_hour == the current Berlin hour.
        # Own connection per run so the two cron jobs never interleave on one shared
        # connection's transaction — e.g. a slow digest (Resend stall) still running at 03:30
        # when housekeeping fires would otherwise corrupt each other's tx (C1).
        conn = await connect(settings)
        try:
            await reminder_service.run_hourly_reminders(conn, settings)
        finally:
            await conn.close()

    async def _housekeeping_job():
        conn = await connect(settings)
        try:
            await housekeeping_service.run_housekeeping(conn, settings)
        finally:
            await conn.close()

    scheduler.add_job(
        _digest_job,
        CronTrigger(minute=0, timezone="Europe/Berlin"),  # every hour on the hour
        id="daily_digest",
    )
    scheduler.add_job(
        _housekeeping_job,
        CronTrigger(
            hour=settings.HK_HOUR_BERLIN,
            minute=settings.HK_MINUTE_BERLIN,
            timezone="Europe/Berlin",
        ),
        id="daily_housekeeping",
    )
    scheduler.start()
    return scheduler


def create_app(settings: Settings | None = None, db: aiosqlite.Connection | None = None) -> FastAPI:
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        configure_logging(settings)
        if settings.APP_ENV == "production":
            settings.validate_runtime()  # fail fast on unsafe/contradictory prod config
        own_db = app.state.db is None
        if own_db:
            app.state.db = await init_db(settings)
        if settings.APP_ENV != "test":
            app.state.scheduler = _start_scheduler(app)
            await reminder_service.catch_up_missed(app.state.db, settings)
            if settings.HK_RUN_ON_STARTUP:
                await housekeeping_service.run_housekeeping(app.state.db, settings)
        try:
            yield
        finally:
            sched = getattr(app.state, "scheduler", None)
            if sched:
                sched.shutdown(wait=False)
            if own_db:
                await app.state.db.close()

    app = FastAPI(title="PlantPal", lifespan=lifespan)
    app.state.settings = settings
    app.state.db = db
    app.state.scheduler = None
    install_exception_handlers(app)

    @app.middleware("http")
    async def _renew_cookie(request: Request, call_next):
        response = await call_next(request)
        token = getattr(request.state, "renew_session_token", None)
        if token:
            set_auth_cookies(response, request.app.state.settings, token)
        return response

    @app.middleware("http")
    async def _request_log(request: Request, call_next):
        start = time.monotonic()
        response = await call_next(request)
        route = request.scope.get("route")
        get_logger("plantpal.request").info(
            "request",
            method=request.method,
            path=getattr(route, "path", request.url.path),  # low-cardinality template, not raw IDs
            status=response.status_code,
            duration_ms=round((time.monotonic() - start) * 1000, 1),
            ip_hash=client_ip(request),
        )
        return response

    # Pure-ASGI guards, added last so they wrap the BaseHTTPMiddleware layers above.
    # add_middleware inserts at position 0, so SecurityHeaders ends up outermost and
    # decorates even the 413 that BodySizeLimit short-circuits.
    max_body_bytes = settings.MAX_REQUEST_BODY_MB * 1024 * 1024
    app.add_middleware(BodySizeLimitMiddleware, max_bytes=max_body_bytes)
    app.add_middleware(SecurityHeadersMiddleware, settings=settings)

    register_all(app)
    mount_spa(app, settings.STATIC_DIR)
    return app
