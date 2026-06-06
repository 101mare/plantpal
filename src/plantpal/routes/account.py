"""Account routes: user invites, email change, settings, stats, account delete + export."""

from __future__ import annotations

import contextlib
from datetime import timedelta

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import JSONResponse, RedirectResponse

from .. import account_export_service, auth_service, email_service, image_service, plant_service
from ..deps import (
    clear_auth_cookies,
    client_ip,
    current_user,
    get_db,
    require_csrf,
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
)
from ..rate_limit import check_rate_limit, key_ip, key_user
from ..time_utils import now_berlin, to_iso, today_berlin

router = APIRouter()


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
