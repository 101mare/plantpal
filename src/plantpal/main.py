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

from . import (
    account_export_service,
    auth_service,
    email_service,
    housekeeping_service,
    image_service,
    plant_service,
    reminder_service,
)
from .config import Settings, get_settings
from .db import connect, init_db
from .errors import (
    AppError,
    AuthError,
    CsrfError,
    ForbiddenError,
    NotFoundError,
    install_exception_handlers,
)
from .logging_setup import configure_logging, get_logger
from .models import (
    EmailChangeConfirm,
    EmailChangeRequestBody,
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
    VerifyCodeRequest,
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


async def _db(request: Request):
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


def _settings(request: Request) -> Settings:
    return request.app.state.settings


async def current_user(request: Request, db=Depends(_db)):
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


def _origin_allowed(candidate: str | None, settings: Settings) -> bool:
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
            _set_auth_cookies(response, request.app.state.settings, token)
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
            ip_hash=_client_ip(request),
        )
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
                db,
                key_email(body.email.lower(), "login", settings),
                settings.RL_LOGIN_REQUEST_EMAIL,
            )
            await check_rate_limit(
                db, key_ip(_client_ip(request), "login"), settings.RL_LOGIN_REQUEST_IP
            )
            issued = await auth_service.request_login_link(db, settings, body.email)
            if issued:
                raw, code = issued
                # CLI fallback exists; never reveal send status to the caller
                with contextlib.suppress(email_service.EmailUnavailableError):
                    await email_service.send_magic_link(
                        settings, body.email, auth_service.login_url(settings, raw), code
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

    @app.post("/auth/verify-code")
    async def verify_code(
        request: Request, body: VerifyCodeRequest, db=Depends(_db), settings=Depends(_settings)
    ):
        await check_rate_limit(
            db, key_ip(_client_ip(request), "codeverify"), settings.RL_LOGIN_CODE_VERIFY_IP
        )
        await check_rate_limit(
            db,
            key_email(body.email.lower(), "codeverify", settings),
            settings.RL_LOGIN_CODE_VERIFY_EMAIL,
        )
        session_token, _user = await auth_service.verify_login_code(
            db, settings, body.email, body.code
        )
        response = JSONResponse({"ok": True})
        _set_auth_cookies(response, settings, session_token)
        return response

    @app.post("/auth/register")
    async def register(
        request: Request, body: RegisterRequest, db=Depends(_db), settings=Depends(_settings)
    ):
        await check_rate_limit(db, key_ip(_client_ip(request), "register"), settings.RL_REGISTER_IP)
        raw, code = await auth_service.register_with_invite(
            db, settings, body.invite_token, body.email
        )
        with contextlib.suppress(email_service.EmailUnavailableError):
            await email_service.send_magic_link(
                settings, body.email, auth_service.login_url(settings, raw), code
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

    # --- v3: user invites (quota-checked, multi-use) ---
    @app.post("/api/invites", status_code=201)
    async def create_invite_user(
        body: InviteCreateRequest,
        user=Depends(current_user),
        _csrf=Depends(require_csrf),
        db=Depends(_db),
        settings=Depends(_settings),
    ):
        from datetime import timedelta

        from .time_utils import now_berlin, to_iso

        await check_rate_limit(db, key_user(user.id, "invite"), settings.RL_INVITE_MUTATION)
        raw, remaining = await auth_service.create_user_invite(
            db, settings, user.id, body.max_uses, body.expires_in_days
        )
        ttl = body.expires_in_days or settings.INVITE_TOKEN_TTL_DAYS
        return InviteResponse(
            invite_url=auth_service.register_url(settings, raw),
            expires_at=to_iso(now_berlin() + timedelta(days=ttl)),
            max_uses=body.max_uses,
            used_count=0,
            remaining_quota=remaining,
        ).model_dump()

    @app.get("/api/invites")
    async def list_invites(user=Depends(current_user), db=Depends(_db)):
        return {"items": await auth_service.list_user_invites(db, user.id)}

    @app.post("/api/invites/{invite_id}/revoke")
    async def revoke_invite_user(
        invite_id: int,
        user=Depends(current_user),
        _csrf=Depends(require_csrf),
        db=Depends(_db),
        settings=Depends(_settings),
    ):
        await check_rate_limit(db, key_user(user.id, "invite"), settings.RL_INVITE_MUTATION)
        if not await auth_service.revoke_invite(db, user.id, invite_id):
            raise NotFoundError("invite_not_found", code="invite_not_found", status_code=404)
        return GenericOk()

    # --- v3: email change ---
    @app.post("/api/account/email")
    async def request_email_change(
        body: EmailChangeRequestBody,
        user=Depends(current_user),
        _csrf=Depends(require_csrf),
        db=Depends(_db),
        settings=Depends(_settings),
    ):
        await check_rate_limit(db, key_user(user.id, "emailchange"), settings.RL_EMAIL_CHANGE_USER)
        raw, code, _ = await auth_service.create_email_change(db, settings, user.id, body.new_email)
        confirm_url = f"{settings.BASE_URL}/api/account/email/confirm?token={raw}"
        old_email = (await auth_service.get_user_by_id(db, user.id))["email"]
        with contextlib.suppress(email_service.EmailUnavailableError):
            await email_service.send_email_change_verify(
                settings, body.new_email, confirm_url, code
            )
        with contextlib.suppress(email_service.EmailUnavailableError):
            await email_service.send_email_change_notice(
                settings, old_email, auth_service._mask_email(body.new_email)
            )
        return GenericOk()

    @app.get("/api/account/email/confirm")
    async def confirm_email_change_link(
        request: Request, token: str, db=Depends(_db), settings=Depends(_settings)
    ):
        await check_rate_limit(
            db, key_ip(_client_ip(request), "emailconfirm"), settings.RL_LOGIN_VERIFY_IP
        )
        try:
            await auth_service.confirm_email_change_by_token(db, settings, token)
        except AppError as exc:
            return RedirectResponse(f"/settings?email_error={exc.code}", status_code=303)
        return RedirectResponse("/settings?email_changed=1", status_code=303)

    @app.post("/api/account/email/confirm")
    async def confirm_email_change_code(
        body: EmailChangeConfirm,
        user=Depends(current_user),
        _csrf=Depends(require_csrf),
        db=Depends(_db),
        settings=Depends(_settings),
    ):
        await check_rate_limit(db, key_user(user.id, "emailconfirm"), settings.RL_PLANT_MUTATION)
        new_email = await auth_service.confirm_email_change_by_code(
            db, settings, user.id, body.code
        )
        return {"ok": True, "email": new_email}

    # --- plants ---
    @app.get("/api/plants")
    async def list_plants(group_by: str | None = None, user=Depends(current_user), db=Depends(_db)):
        rows = await plant_service.list_plants(db, user.id)
        result: dict = {"items": [plant_service.to_response(r).model_dump() for r in rows]}
        if group_by == "room":
            result["groups"] = [g.model_dump() for g in plant_service.build_groups(rows)]
        return result

    @app.get("/api/plants/{plant_id}/waterings")
    async def list_waterings(plant_id: int, user=Depends(current_user), db=Depends(_db)):
        rows = await plant_service.list_waterings(db, user.id, plant_id)
        if rows is None:
            raise NotFoundError("plant_not_found", code="plant_not_found", status_code=404)
        return {
            "items": [plant_service.watering_to_response(r).model_dump() for r in rows],
            "count": len(rows),
        }

    @app.post("/api/plants", status_code=201)
    async def create_plant(
        request: Request,
        name: str = Form(...),
        interval_days: int = Form(...),
        notes: str | None = Form(None),
        water_amount_ml: int | None = Form(None),
        location_room: str | None = Form(None),
        image: UploadFile = File(...),
        user=Depends(current_user),
        _csrf=Depends(require_csrf),
        db=Depends(_db),
        settings=Depends(_settings),
    ):
        await check_rate_limit(db, key_user(user.id, "plant"), settings.RL_PLANT_MUTATION)
        data = PlantCreate(
            name=name,
            interval_days=interval_days,
            notes=notes,
            water_amount_ml=water_amount_ml,
            location_room=location_room,
        )
        pid = await plant_service.create_plant(db, user.id, data)
        try:
            raw = await image_service.read_upload_limited(image, settings)
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
        raw = await image_service.read_upload_limited(image, settings)
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
            locale=row["locale"],
            reminder_hour=row["reminder_hour"],
            theme=row["theme"],
            invite_quota=row["invite_quota"],
            is_admin=bool(row["is_admin"]),
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
        fields = {k: v for k, v in body.model_dump(exclude_unset=True).items() if v is not None}
        updates: dict = {}
        if "email_reminders_enabled" in fields:
            updates["email_reminders_enabled"] = 1 if fields["email_reminders_enabled"] else 0
        for col in ("locale", "reminder_hour", "theme"):
            if col in fields:
                updates[col] = fields[col]
        if updates:
            assignments = ", ".join(f"{key} = ?" for key in updates)
            await db.execute(
                f"UPDATE users SET {assignments} WHERE id = ?",  # noqa: S608 — fixed-whitelist keys
                (*updates.values(), user.id),
            )
            await db.commit()
        return GenericOk()

    @app.get("/api/stats")
    async def get_stats(by_room: bool = False, user=Depends(current_user), db=Depends(_db)):
        stats = await plant_service.compute_stats(db, user.id, by_room=by_room)
        return stats.model_dump()

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

    @app.get("/api/account/export")
    async def export_account(
        user=Depends(current_user), db=Depends(_db), settings=Depends(_settings)
    ):
        from .time_utils import today_berlin

        await check_rate_limit(db, key_user(user.id, "export"), settings.EXPORT_RATE)
        blob = await account_export_service.build_export_zip(db, settings, user.id)
        filename = f"plantpal-export-{user.id}-{today_berlin().isoformat()}.zip"
        return Response(
            content=blob,
            media_type="application/zip",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    # --- admin ---
    @app.post("/api/admin/invites", status_code=201)
    async def create_invite(
        body: InviteCreateRequest,
        admin=Depends(require_admin),
        _csrf=Depends(require_csrf),
        db=Depends(_db),
        settings=Depends(_settings),
    ):
        await check_rate_limit(db, key_user(admin.id, "invite"), settings.RL_INVITE_MUTATION)
        raw = await auth_service.create_invite(
            db, settings, admin.id, body.email_hint, body.max_uses, body.expires_in_days
        )
        from datetime import timedelta

        from .time_utils import now_berlin, to_iso

        ttl = (
            body.expires_in_days
            if body.expires_in_days is not None
            else settings.INVITE_TOKEN_TTL_DAYS
        )
        expires = to_iso(now_berlin() + timedelta(days=ttl))
        return InviteResponse(
            invite_url=auth_service.register_url(settings, raw),
            expires_at=expires,
            max_uses=body.max_uses,
            used_count=0,
        ).model_dump()

    # --- health ---
    @app.get("/api/health")
    async def health(request: Request, db=Depends(_db), settings=Depends(_settings)):
        db_ok = True
        wal_mode = False
        try:
            async with db.execute("SELECT 1") as cur:
                await cur.fetchone()
            async with db.execute("PRAGMA journal_mode") as cur:
                row = await cur.fetchone()
            wal_mode = bool(row) and str(row[0]).lower() == "wal"
        except Exception:  # noqa: BLE001
            db_ok = False
        db_writable = db_ok
        if db_ok:
            try:  # no-op write that fails on a read-only / full filesystem
                async with db.execute("PRAGMA user_version") as cur:
                    ver = (await cur.fetchone())[0]
                await db.execute(f"PRAGMA user_version = {int(ver)}")  # noqa: S608 — int only
            except Exception:  # noqa: BLE001
                db_writable = False
        scheduler = getattr(request.app.state, "scheduler", None)
        running = bool(scheduler and scheduler.running)
        jobs = None
        if scheduler is not None:
            ids = {j.id for j in scheduler.get_jobs()}
            jobs = {"digest": "daily_digest" in ids, "housekeeping": "daily_housekeeping" in ids}
        return HealthResponse(
            status="ok" if (db_ok and db_writable) else "degraded",
            db_ok=db_ok,
            scheduler_running=running,
            db_writable=db_writable,
            wal_mode=wal_mode,
            version=settings.APP_VERSION,
            jobs=jobs,
        ).model_dump()
