"""Auth routes: passwordless login (magic link + 6-digit code), register, logout, me."""

from __future__ import annotations

import asyncio
import contextlib
import html
import time

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from .. import auth_service, email_service
from ..config import Settings
from ..deps import (
    clear_auth_cookies,
    client_ip,
    current_user,
    get_db,
    require_csrf,
    require_same_origin_submit,
    set_auth_cookies,
    settings_dep,
)
from ..errors import AppError
from ..models import GenericOk, LoginRequest, RegisterRequest, VerifyCodeRequest
from ..rate_limit import check_rate_limit, key_email, key_ip

router = APIRouter()


def _interstitial_html(masked_email: str, raw_token: str) -> str:
    """Server-rendered confirmation page for the magic link (N1).

    No inline scripts (CSP-safe); the only action is a same-origin POST that the
    SecurityHeaders/origin check then validates before any cookie is set.
    """
    masked = html.escape(masked_email)
    token = html.escape(raw_token)
    return f"""<!doctype html>
<html lang="de">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="robots" content="noindex">
<title>Anmeldung bestätigen · PlantPal</title>
<style>
  :root {{ color-scheme: dark; }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0; min-height: 100dvh; display: grid; place-items: center; padding: 24px;
    font: 16px/1.5 system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
    background: #0d2018; color: #e8efe9;
  }}
  .card {{
    width: 100%; max-width: 380px; background: #142a20; border: 1px solid #21402f;
    border-radius: 18px; padding: 32px 28px; text-align: center;
    box-shadow: 0 10px 40px rgba(0,0,0,.35);
  }}
  .logo {{ font-size: 1.1rem; font-weight: 700; letter-spacing: .02em; margin-bottom: 18px; }}
  h1 {{ font-size: 1.25rem; margin: 0 0 6px; }}
  p {{ margin: 6px 0 0; color: #b8c8bd; }}
  .email {{
    display: block; margin: 14px 0 22px; font-size: 1.05rem;
    font-weight: 600; color: #f3d9a6; word-break: break-all;
  }}
  button {{
    width: 100%; padding: 14px 18px; border: 0; border-radius: 12px; cursor: pointer;
    font-size: 1rem; font-weight: 600; color: #1a130a; background: #e3b878;
    min-height: 48px;
  }}
  button:hover {{ background: #edc587; }}
  .hint {{ margin-top: 18px; font-size: .85rem; color: #8aa092; }}
</style>
</head>
<body>
  <main class="card">
    <div class="logo">🌱 PlantPal</div>
    <h1>Anmeldung bestätigen</h1>
    <p>Du meldest dich an als</p>
    <span class="email">{masked}</span>
    <form method="post" action="/auth/verify">
      <input type="hidden" name="token" value="{token}">
      <button type="submit">Jetzt anmelden</button>
    </form>
    <p class="hint">Gehört diese Adresse nicht dir? Schließe diese Seite einfach.</p>
  </main>
</body>
</html>"""


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
async def verify_interstitial(
    request: Request, token: str, db=Depends(get_db), settings=Depends(settings_dep)
):
    """Show a confirmation page for the magic link — DOES NOT set a cookie (N1).

    Setting the session on this top-level GET enables login-CSRF / session-fixation:
    SameSite=Lax still allows a cross-site navigation to land here, so an attacker could
    silently sign a victim into the attacker's account. We instead require a deliberate
    same-origin POST below before any cookie is set.
    """
    await check_rate_limit(db, key_ip(client_ip(request), "verify"), settings.RL_LOGIN_VERIFY_IP)
    try:
        masked = await auth_service.peek_login_token(db, settings, token)
    except AppError as exc:
        return RedirectResponse(f"/login?error={exc.code}", status_code=303)
    return HTMLResponse(_interstitial_html(masked, token))


@router.post("/auth/verify")
async def verify_confirm(
    request: Request,
    token: str = Form(...),
    db=Depends(get_db),
    settings: Settings = Depends(settings_dep),
):
    """Consume the magic link and open the session — the cookie-setting step (N1).

    Guarded by a strict same-origin Origin check: a cross-site form auto-submit carries a
    foreign Origin and is rejected, so an attacker cannot complete the login in the
    victim's browser. (There is no session yet, hence no double-submit token to fall back
    on — we require Origin *or* Referer to be present and to match.)
    """
    await check_rate_limit(db, key_ip(client_ip(request), "verify"), settings.RL_LOGIN_VERIFY_IP)
    require_same_origin_submit(request, settings)
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
    # This endpoint mints a browser session cookie. Treat it like the magic-link confirm POST:
    # a cross-site page must not be able to log a victim into an attacker-controlled account.
    require_same_origin_submit(request, settings)
    session_token, _user = await auth_service.verify_login_code(db, settings, body.email, body.code)
    payload: dict[str, object] = {"ok": True}
    if body.client == "app":
        # Native shell: session token in the body for Bearer auth (cookies below stay —
        # harmless in the shell, and the web flow is unchanged when client is omitted).
        payload["session_token"] = session_token
    response = JSONResponse(payload)
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
