"""FastAPI app: auth, plants, settings, admin, health + SPA serving.

Routes live here (flat, per project convention). A DB connection and Settings
live on ``app.state``; in tests they are injected, in production the lifespan
opens the DB, starts the APScheduler digest job, and runs reboot catch-up.
"""

from __future__ import annotations

import asyncio
import contextlib
import time
from contextlib import asynccontextmanager

import aiosqlite
from fastapi import Depends, FastAPI, File, Form, Request, Response, UploadFile
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from pydantic import ValidationError

from . import auth_service, email_service, image_service, plant_service, reminder_service
from .config import Settings, get_settings
from .db import init_db
from .errors import (
    AppError,
    AuthError,
    CsrfError,
    ForbiddenError,
    NotFoundError,
    install_exception_handlers,
)
from .models import (
    GenericOk,
    HealthResponse,
    InviteCreateRequest,
    InviteResponse,
    LoginRequest,
    PlantCreate,
    PlantUpdate,
    RegisterRequest,
    SettingsResponse,
    SettingsUpdate,
    StatsResponse,
)
from .rate_limit import check_rate_limit, key_email, key_ip, key_user
from .security import create_csrf_token, hash_ip, verify_csrf_token
from .spa import mount_spa

# --- cookie helpers ---


def _set_auth_cookies(response: Response, settings: Settings, session_token: str) -> None:
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


def _clear_auth_cookies(response: Response, settings: Settings) -> None:
    response.delete_cookie(settings.COOKIE_NAME, path="/")
    response.delete_cookie(settings.CSRF_COOKIE_NAME, path="/")


# --- dependencies ---


def _db(request: Request) -> aiosqlite.Connection:
    return request.app.state.db


def _settings(request: Request) -> Settings:
    return request.app.state.settings


async def current_user(request: Request):
    settings = request.app.state.settings
    db = request.app.state.db
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


def _origin_allowed(candidate: str | None, settings: Settings) -> bool:
    """True if the request's Origin/Referer is acceptable.

    Prod: must match BASE_URL. Dev: also accept any localhost origin so a Vite
    dev server (:5173) talking to the backend (:8000) isn't rejected.
    """
    if not candidate:
        return True  # no Origin/Referer → fall back to the double-submit token check
    cleaned = candidate.rstrip("/")
    if cleaned.startswith(settings.BASE_URL.rstrip("/")):
        return True
    if not settings.is_production:
        from urllib.parse import urlparse

        return urlparse(cleaned).hostname in ("localhost", "127.0.0.1")
    return False


async def require_csrf(request: Request) -> None:
    settings = request.app.state.settings
    candidate = request.headers.get("origin") or request.headers.get("referer")
    if not _origin_allowed(candidate, settings):
        raise CsrfError("Bad origin.")
    if not verify_csrf_token(
        request.headers.get("x-csrf-token"),
        request.cookies.get(settings.CSRF_COOKIE_NAME),
        request.cookies.get(settings.COOKIE_NAME),
        settings,
    ):
        raise CsrfError()


def _client_ip(request: Request) -> str:
    return hash_ip(request.client.host if request.client else None)


# --- scheduler ---


def _start_scheduler(app: FastAPI):
    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    from apscheduler.triggers.cron import CronTrigger

    settings = app.state.settings
    scheduler = AsyncIOScheduler(timezone="Europe/Berlin")

    async def _job():
        await reminder_service.run_daily_reminders(app.state.db, settings)

    scheduler.add_job(
        _job,
        CronTrigger(hour=settings.REMINDER_HOUR_BERLIN, minute=0, timezone="Europe/Berlin"),
        id="daily_digest",
    )
    scheduler.start()
    return scheduler


def create_app(settings: Settings | None = None, db: aiosqlite.Connection | None = None) -> FastAPI:
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if settings.APP_ENV == "production":
            settings.validate_runtime()  # fail fast on unsafe/contradictory prod config
        own_db = app.state.db is None
        if own_db:
            app.state.db = await init_db(settings)
        if settings.APP_ENV != "test":
            app.state.scheduler = _start_scheduler(app)
            await reminder_service.catch_up_missed(app.state.db, settings)
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

    @app.exception_handler(ValidationError)
    async def _on_validation(_: Request, exc: ValidationError):
        return JSONResponse(
            status_code=422,
            content={"error": {"code": "validation_error", "message": exc.errors()[0]["msg"]}},
        )

    @app.middleware("http")
    async def _renew_cookie(request: Request, call_next):
        response = await call_next(request)
        token = getattr(request.state, "renew_session_token", None)
        if token:
            _set_auth_cookies(response, request.app.state.settings, token)
        return response

    _register_routes(app)
    mount_spa(app, settings.STATIC_DIR)
    return app


def _register_routes(app: FastAPI) -> None:  # noqa: C901 — flat route table by design
    # --- auth ---
    @app.post("/auth/request-login")
    async def request_login(
        request: Request, body: LoginRequest, db=Depends(_db), settings=Depends(_settings)
    ):
        start = time.monotonic()
        try:
            await check_rate_limit(
                db, key_email(body.email.lower(), "login"), settings.RL_LOGIN_REQUEST_EMAIL
            )
            await check_rate_limit(
                db, key_ip(_client_ip(request), "login"), settings.RL_LOGIN_REQUEST_IP
            )
            raw = await auth_service.request_login_link(db, settings, body.email)
            if raw:
                # CLI fallback exists; never reveal send status to the caller
                with contextlib.suppress(email_service.EmailUnavailableError):
                    await email_service.send_magic_link(
                        settings, body.email, auth_service.login_url(settings, raw)
                    )
        finally:
            elapsed_ms = (time.monotonic() - start) * 1000
            if elapsed_ms < settings.AUTH_REQUEST_MIN_MS:
                await asyncio.sleep((settings.AUTH_REQUEST_MIN_MS - elapsed_ms) / 1000)
        return GenericOk(message="If this email can sign in, a link has been sent.")

    @app.get("/auth/verify")
    async def verify(request: Request, token: str, db=Depends(_db), settings=Depends(_settings)):
        await check_rate_limit(
            db, key_ip(_client_ip(request), "verify"), settings.RL_LOGIN_VERIFY_IP
        )
        # Browser flow: the user clicked an emailed link, so redirect into the SPA
        # instead of returning raw JSON. Failures land on /login with an error code.
        try:
            session_token, _user = await auth_service.verify_login(db, settings, token)
        except AppError as exc:
            return RedirectResponse(f"/login?error={exc.code}", status_code=303)
        response = RedirectResponse("/", status_code=303)
        _set_auth_cookies(response, settings, session_token)
        return response

    @app.post("/auth/register")
    async def register(
        request: Request, body: RegisterRequest, db=Depends(_db), settings=Depends(_settings)
    ):
        await check_rate_limit(db, key_ip(_client_ip(request), "register"), settings.RL_REGISTER_IP)
        raw = await auth_service.register_with_invite(db, settings, body.invite_token, body.email)
        with contextlib.suppress(email_service.EmailUnavailableError):
            await email_service.send_magic_link(
                settings, body.email, auth_service.login_url(settings, raw)
            )
        return GenericOk(message="Account created. Check your email for a sign-in link.")

    @app.post("/auth/logout")
    async def logout(
        request: Request,
        _csrf=Depends(require_csrf),
        user=Depends(current_user),
        db=Depends(_db),
        settings=Depends(_settings),
    ):
        token = request.cookies.get(settings.COOKIE_NAME)
        await auth_service.logout(db, settings, token)
        response = JSONResponse({"ok": True})
        _clear_auth_cookies(response, settings)
        return response

    @app.get("/api/me")
    async def me(user=Depends(current_user)):
        return {"id": user.id, "email": user.email, "is_admin": user.is_admin}

    # --- plants ---
    @app.get("/api/plants")
    async def list_plants(user=Depends(current_user), db=Depends(_db)):
        rows = await plant_service.list_plants(db, user.id)
        return {"items": [plant_service.to_response(r).model_dump() for r in rows]}

    @app.post("/api/plants", status_code=201)
    async def create_plant(
        request: Request,
        name: str = Form(...),
        interval_days: int = Form(...),
        notes: str | None = Form(None),
        water_amount_ml: int | None = Form(None),
        image: UploadFile = File(...),
        user=Depends(current_user),
        _csrf=Depends(require_csrf),
        db=Depends(_db),
        settings=Depends(_settings),
    ):
        await check_rate_limit(db, key_user(user.id, "plant"), settings.RL_PLANT_MUTATION)
        data = PlantCreate(
            name=name, interval_days=interval_days, notes=notes, water_amount_ml=water_amount_ml
        )
        pid = await plant_service.create_plant(db, user.id, data)
        try:
            raw = await image.read()
            path = await image_service.process_upload(
                settings, user.id, pid, raw, image.content_type
            )
        except AppError:
            # roll back the just-created row so a failed upload leaves no orphan plant
            await plant_service.hard_delete_plant(db, user.id, pid)
            raise
        await plant_service.set_image_path(db, user.id, pid, path)
        row = await plant_service.get_plant(db, user.id, pid)
        return plant_service.to_response(row).model_dump()

    @app.get("/api/plants/{plant_id}")
    async def get_plant(plant_id: int, user=Depends(current_user), db=Depends(_db)):
        row = await plant_service.get_plant(db, user.id, plant_id)
        if row is None:
            raise NotFoundError("plant_not_found", code="plant_not_found", status_code=404)
        return plant_service.to_response(row).model_dump()

    @app.patch("/api/plants/{plant_id}")
    async def update_plant(
        plant_id: int,
        body: PlantUpdate,
        user=Depends(current_user),
        _csrf=Depends(require_csrf),
        db=Depends(_db),
        settings=Depends(_settings),
    ):
        await check_rate_limit(db, key_user(user.id, "plant"), settings.RL_PLANT_MUTATION)
        row = await plant_service.update_plant(db, user.id, plant_id, body)
        if row is None:
            raise NotFoundError("plant_not_found", code="plant_not_found", status_code=404)
        return plant_service.to_response(row).model_dump()

    @app.delete("/api/plants/{plant_id}")
    async def delete_plant(
        plant_id: int,
        user=Depends(current_user),
        _csrf=Depends(require_csrf),
        db=Depends(_db),
        settings=Depends(_settings),
    ):
        await check_rate_limit(db, key_user(user.id, "plant"), settings.RL_PLANT_MUTATION)
        if not await plant_service.soft_delete_plant(db, user.id, plant_id):
            raise NotFoundError("plant_not_found", code="plant_not_found", status_code=404)
        return GenericOk()

    @app.post("/api/plants/{plant_id}/water")
    async def water_plant(
        plant_id: int,
        user=Depends(current_user),
        _csrf=Depends(require_csrf),
        db=Depends(_db),
        settings=Depends(_settings),
    ):
        await check_rate_limit(db, key_user(user.id, "plant"), settings.RL_PLANT_MUTATION)
        row = await plant_service.water_plant(db, user.id, plant_id)
        if row is None:
            raise NotFoundError("plant_not_found", code="plant_not_found", status_code=404)
        return plant_service.to_response(row).model_dump()

    @app.post("/api/plants/{plant_id}/image")
    async def upload_image(
        plant_id: int,
        image: UploadFile = File(...),
        user=Depends(current_user),
        _csrf=Depends(require_csrf),
        db=Depends(_db),
        settings=Depends(_settings),
    ):
        await check_rate_limit(db, key_user(user.id, "image"), settings.RL_IMAGE_UPLOAD)
        if await plant_service.get_plant(db, user.id, plant_id) is None:
            raise NotFoundError("plant_not_found", code="plant_not_found", status_code=404)
        raw = await image.read()
        path = await image_service.process_upload(
            settings, user.id, plant_id, raw, image.content_type
        )
        await plant_service.set_image_path(db, user.id, plant_id, path)
        return {"image_url": f"/api/plants/{plant_id}/image"}

    @app.get("/api/plants/{plant_id}/image")
    async def get_image(
        plant_id: int, user=Depends(current_user), db=Depends(_db), settings=Depends(_settings)
    ):
        if await plant_service.get_plant(db, user.id, plant_id) is None:
            raise NotFoundError("image_not_found", code="image_not_found", status_code=404)
        path = image_service.image_file_path(settings, user.id, plant_id)
        if path is None:
            raise NotFoundError("image_not_found", code="image_not_found", status_code=404)
        return FileResponse(path, media_type="image/png")

    # --- settings / stats / account ---
    @app.get("/api/settings")
    async def get_user_settings(request: Request, user=Depends(current_user), db=Depends(_db)):
        row = await auth_service.get_user_by_id(db, user.id)
        return SettingsResponse(
            email=row["email"],
            email_reminders_enabled=bool(row["email_reminders_enabled"]),
            reminder_channel=row["reminder_channel"],
        ).model_dump()

    @app.patch("/api/settings")
    async def update_user_settings(
        body: SettingsUpdate,
        user=Depends(current_user),
        _csrf=Depends(require_csrf),
        db=Depends(_db),
        settings=Depends(_settings),
    ):
        await check_rate_limit(db, key_user(user.id, "settings"), settings.RL_PLANT_MUTATION)
        await db.execute(
            "UPDATE users SET email_reminders_enabled = ? WHERE id = ?",
            (1 if body.email_reminders_enabled else 0, user.id),
        )
        await db.commit()
        return GenericOk()

    @app.get("/api/stats")
    async def get_stats(user=Depends(current_user), db=Depends(_db)):
        total, thirsty = await plant_service.stats(db, user.id)
        return StatsResponse(total_plants=total, thirsty_count=thirsty).model_dump()

    @app.delete("/api/account")
    async def delete_account(
        request: Request,
        user=Depends(current_user),
        _csrf=Depends(require_csrf),
        db=Depends(_db),
        settings=Depends(_settings),
    ):
        await image_service.delete_user_images(settings, user.id)
        await plant_service.delete_account(db, user.id)
        response = JSONResponse({"ok": True})
        _clear_auth_cookies(response, settings)
        return response

    # --- admin ---
    @app.post("/api/admin/invites", status_code=201)
    async def create_invite(
        body: InviteCreateRequest,
        admin=Depends(require_admin),
        _csrf=Depends(require_csrf),
        db=Depends(_db),
        settings=Depends(_settings),
    ):
        raw = await auth_service.create_invite(db, settings, admin.id, body.email_hint)
        from datetime import timedelta

        from .time_utils import now_berlin, to_iso

        expires = to_iso(now_berlin() + timedelta(days=settings.INVITE_TOKEN_TTL_DAYS))
        return InviteResponse(
            invite_url=auth_service.register_url(settings, raw), expires_at=expires
        ).model_dump()

    # --- health ---
    @app.get("/api/health")
    async def health(request: Request, db=Depends(_db)):
        db_ok = True
        try:
            async with db.execute("SELECT 1") as cur:
                await cur.fetchone()
        except Exception:  # noqa: BLE001
            db_ok = False
        scheduler = getattr(request.app.state, "scheduler", None)
        return HealthResponse(
            status="ok" if db_ok else "degraded",
            db_ok=db_ok,
            scheduler_running=bool(scheduler and scheduler.running),
        ).model_dump()
