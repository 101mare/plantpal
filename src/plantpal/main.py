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
from .db import init_db
from .deps import client_ip, set_auth_cookies
from .errors import install_exception_handlers
from .logging_setup import configure_logging, get_logger
from .routes import register_all
from .spa import mount_spa


def _start_scheduler(app: FastAPI):
    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    from apscheduler.triggers.cron import CronTrigger

    settings = app.state.settings
    scheduler = AsyncIOScheduler(timezone="Europe/Berlin")

    async def _digest_job():
        # hourly: each run serves users whose chosen reminder_hour == the current Berlin hour
        await reminder_service.run_hourly_reminders(app.state.db, settings)

    async def _housekeeping_job():
        await housekeeping_service.run_housekeeping(app.state.db, settings)

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

    register_all(app)
    mount_spa(app, settings.STATIC_DIR)
    return app
