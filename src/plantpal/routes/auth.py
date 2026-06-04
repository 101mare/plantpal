"""Auth routes: passwordless login (magic link + 6-digit code), register, logout, me."""

from __future__ import annotations

import asyncio
import contextlib
import time

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, RedirectResponse

from .. import auth_service, email_service
from ..deps import (
    clear_auth_cookies,
    client_ip,
    current_user,
    get_db,
    require_csrf,
    set_auth_cookies,
    settings_dep,
)
from ..errors import AppError
from ..models import GenericOk, LoginRequest, RegisterRequest, VerifyCodeRequest
from ..rate_limit import check_rate_limit, key_email, key_ip

router = APIRouter()


@router.post("/auth/request-login")
async def request_login(
    request: Request, body: LoginRequest, db=Depends(get_db), settings=Depends(settings_dep)
):
    start = time.monotonic()
    try:
        await check_rate_limit(
            db,
            key_email(body.email.lower(), "login", settings),
            settings.RL_LOGIN_REQUEST_EMAIL,
        )
        await check_rate_limit(
            db, key_ip(client_ip(request), "login"), settings.RL_LOGIN_REQUEST_IP
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


@router.get("/auth/verify")
async def verify(request: Request, token: str, db=Depends(get_db), settings=Depends(settings_dep)):
    await check_rate_limit(db, key_ip(client_ip(request), "verify"), settings.RL_LOGIN_VERIFY_IP)
    # Browser flow: the user clicked an emailed link, so redirect into the SPA
    # instead of returning raw JSON. Failures land on /login with an error code.
    try:
        session_token, _user = await auth_service.verify_login(db, settings, token)
    except AppError as exc:
        return RedirectResponse(f"/login?error={exc.code}", status_code=303)
    response = RedirectResponse("/", status_code=303)
    set_auth_cookies(response, settings, session_token)
    return response


@router.post("/auth/verify-code")
async def verify_code(
    request: Request, body: VerifyCodeRequest, db=Depends(get_db), settings=Depends(settings_dep)
):
    await check_rate_limit(
        db, key_ip(client_ip(request), "codeverify"), settings.RL_LOGIN_CODE_VERIFY_IP
    )
    await check_rate_limit(
        db,
        key_email(body.email.lower(), "codeverify", settings),
        settings.RL_LOGIN_CODE_VERIFY_EMAIL,
    )
    session_token, _user = await auth_service.verify_login_code(db, settings, body.email, body.code)
    response = JSONResponse({"ok": True})
    set_auth_cookies(response, settings, session_token)
    return response


@router.post("/auth/register")
async def register(
    request: Request, body: RegisterRequest, db=Depends(get_db), settings=Depends(settings_dep)
):
    await check_rate_limit(db, key_ip(client_ip(request), "register"), settings.RL_REGISTER_IP)
    raw, code = await auth_service.register_with_invite(db, settings, body.invite_token, body.email)
    with contextlib.suppress(email_service.EmailUnavailableError):
        await email_service.send_magic_link(
            settings, body.email, auth_service.login_url(settings, raw), code
        )
    return GenericOk(message="Account created. Check your email for a sign-in link.")


@router.post("/auth/logout")
async def logout(
    request: Request,
    _csrf=Depends(require_csrf),
    user=Depends(current_user),
    db=Depends(get_db),
    settings=Depends(settings_dep),
):
    token = request.cookies.get(settings.COOKIE_NAME)
    await auth_service.logout(db, settings, token)
    response = JSONResponse({"ok": True})
    clear_auth_cookies(response, settings)
    return response


@router.get("/api/me")
async def me(user=Depends(current_user)):
    return {"id": user.id, "email": user.email, "is_admin": user.is_admin}
