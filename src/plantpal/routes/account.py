"""Account routes: user invites, email change, settings, stats, account delete + export."""

from __future__ import annotations

import contextlib
import html
from datetime import timedelta

from fastapi import APIRouter, Depends, Form, Request, Response
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from .. import account_export_service, auth_service, email_service, image_service, plant_service
from ..deps import (
    clear_auth_cookies,
    client_ip,
    current_user,
    get_db,
    require_csrf,
    require_same_origin_submit,
    settings_dep,
)
from ..errors import AppError, NotFoundError
from ..models import (
    EmailChangeConfirm,
    EmailChangeRequestBody,
    GenericOk,
    InviteCreateRequest,
    InviteResponse,
    SettingsResponse,
    SettingsUpdate,
    SprossProgressUpdate,
)
from ..rate_limit import check_rate_limit, key_ip, key_user
from ..time_utils import now_berlin, to_iso, today_berlin

router = APIRouter()


def _email_change_confirm_html(masked_new_email: str, raw_token: str) -> str:
    """Server-rendered confirmation page for email-change links.

    The emailed GET link is intentionally read-only so link scanners and previews cannot
    consume the token. The state-changing step is the same-origin POST below.
    """
    masked = html.escape(masked_new_email)
    token = html.escape(raw_token)
    return f"""<!doctype html>
<html lang="de">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="robots" content="noindex">
<title>Email bestätigen · PlantPal</title>
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
  .logo {{ font-size: 1.1rem; font-weight: 700; margin-bottom: 18px; }}
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
    <div class="logo">PlantPal</div>
    <h1>Email bestätigen</h1>
    <p>Neue Adresse</p>
    <span class="email">{masked}</span>
    <form method="post" action="/api/account/email/confirm-link">
      <input type="hidden" name="token" value="{token}">
      <button type="submit">Adresse übernehmen</button>
    </form>
    <p class="hint">Warst du das nicht? Schließe diese Seite einfach.</p>
  </main>
</body>
</html>"""


# --- user invites (quota-checked, multi-use) ---


@router.post("/api/invites", status_code=201)
async def create_invite_user(
    body: InviteCreateRequest,
    user=Depends(current_user),
    _csrf=Depends(require_csrf),
    db=Depends(get_db),
    settings=Depends(settings_dep),
):
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


@router.get("/api/invites")
async def list_invites(user=Depends(current_user), db=Depends(get_db)):
    return {"items": await auth_service.list_user_invites(db, user.id)}


@router.post("/api/invites/{invite_id}/revoke")
async def revoke_invite_user(
    invite_id: int,
    user=Depends(current_user),
    _csrf=Depends(require_csrf),
    db=Depends(get_db),
    settings=Depends(settings_dep),
):
    await check_rate_limit(db, key_user(user.id, "invite"), settings.RL_INVITE_MUTATION)
    if not await auth_service.revoke_invite(db, user.id, invite_id):
        raise NotFoundError("invite_not_found", code="invite_not_found", status_code=404)
    return GenericOk()


# --- email change ---


@router.post("/api/account/email")
async def request_email_change(
    body: EmailChangeRequestBody,
    user=Depends(current_user),
    _csrf=Depends(require_csrf),
    db=Depends(get_db),
    settings=Depends(settings_dep),
):
    await check_rate_limit(db, key_user(user.id, "emailchange"), settings.RL_EMAIL_CHANGE_USER)
    result = await auth_service.create_email_change(db, settings, user.id, body.new_email)
    # result is None when the target address is already taken — stay completely silent so the
    # response is indistinguishable from success and leaks no membership info (N2).
    if result is not None:
        raw, code, _ = result
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


@router.get("/api/account/email/confirm")
async def confirm_email_change_link(
    request: Request, token: str, db=Depends(get_db), settings=Depends(settings_dep)
):
    await check_rate_limit(
        db, key_ip(client_ip(request), "emailconfirm"), settings.RL_LOGIN_VERIFY_IP
    )
    try:
        masked_new_email = await auth_service.peek_email_change_token(db, settings, token)
    except AppError as exc:
        return RedirectResponse(f"/settings?email_error={exc.code}", status_code=303)
    return HTMLResponse(_email_change_confirm_html(masked_new_email, token))


@router.post("/api/account/email/confirm-link")
async def confirm_email_change_link_post(
    request: Request,
    token: str = Form(...),
    db=Depends(get_db),
    settings=Depends(settings_dep),
):
    await check_rate_limit(
        db, key_ip(client_ip(request), "emailconfirm"), settings.RL_LOGIN_VERIFY_IP
    )
    require_same_origin_submit(request, settings)
    try:
        await auth_service.confirm_email_change_by_token(db, settings, token)
    except AppError as exc:
        return RedirectResponse(f"/settings?email_error={exc.code}", status_code=303)
    return RedirectResponse("/settings?email_changed=1", status_code=303)


@router.post("/api/account/email/confirm")
async def confirm_email_change_code(
    body: EmailChangeConfirm,
    user=Depends(current_user),
    _csrf=Depends(require_csrf),
    db=Depends(get_db),
    settings=Depends(settings_dep),
):
    await check_rate_limit(db, key_user(user.id, "emailconfirm"), settings.RL_PLANT_MUTATION)
    new_email = await auth_service.confirm_email_change_by_code(db, settings, user.id, body.code)
    return {"ok": True, "email": new_email}


# --- settings / stats ---


@router.get("/api/settings")
async def get_user_settings(request: Request, user=Depends(current_user), db=Depends(get_db)):
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


@router.patch("/api/settings")
async def update_user_settings(
    body: SettingsUpdate,
    user=Depends(current_user),
    _csrf=Depends(require_csrf),
    db=Depends(get_db),
    settings=Depends(settings_dep),
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


@router.get("/api/stats")
async def get_stats(by_room: bool = False, user=Depends(current_user), db=Depends(get_db)):
    stats = await plant_service.compute_stats(db, user.id, by_room=by_room)
    return stats.model_dump()


@router.post("/api/spross/progress")
async def update_spross_progress(
    body: SprossProgressUpdate,
    user=Depends(current_user),
    _csrf=Depends(require_csrf),
    db=Depends(get_db),
    settings=Depends(settings_dep),
):
    """Durable high-water-mark for the mascot's evolution stage. The server applies max(), so this
    only ever raises the stored stage/peak — making "the stage never downgrades" true across
    devices / cleared storage, which a localStorage-only client cannot guarantee."""
    await check_rate_limit(db, key_user(user.id, "spross"), settings.RL_PLANT_MUTATION)
    stage_max, peak = await plant_service.bump_spross_progress(
        db, user.id, body.stage_max, body.peak_vitality
    )
    return {"vitality_stage_max": stage_max, "peak_vitality": peak}


# --- account: delete + export ---


@router.delete("/api/account")
async def delete_account(
    request: Request,
    user=Depends(current_user),
    _csrf=Depends(require_csrf),
    db=Depends(get_db),
    settings=Depends(settings_dep),
):
    await check_rate_limit(db, key_user(user.id, "account"), settings.RL_PLANT_MUTATION)  # C7
    # DB rows first, then images: a crash between steps must not leave an account whose rows
    # are gone-but-present pointing at already-deleted image files (N6). Images are a
    # best-effort cleanup; an orphaned file is harmless, an orphaned account row is not.
    await plant_service.delete_account(db, user.id)
    await image_service.delete_user_images(settings, user.id)
    response = JSONResponse({"ok": True})
    clear_auth_cookies(response, settings)
    return response


@router.get("/api/account/export")
async def export_account(
    user=Depends(current_user), db=Depends(get_db), settings=Depends(settings_dep)
):
    await check_rate_limit(db, key_user(user.id, "export"), settings.EXPORT_RATE)
    blob = await account_export_service.build_export_zip(db, settings, user.id)
    filename = f"plantpal-export-{user.id}-{today_berlin().isoformat()}.zip"
    return Response(
        content=blob,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
