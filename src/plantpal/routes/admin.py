"""Admin routes: single-use invite creation (admins are quota-exempt)."""

from __future__ import annotations

from datetime import timedelta

from fastapi import APIRouter, Depends

from .. import auth_service
from ..deps import get_db, require_admin, require_csrf, settings_dep
from ..models import InviteCreateRequest, InviteResponse
from ..rate_limit import check_rate_limit, key_user
from ..time_utils import now_berlin, to_iso

router = APIRouter()


@router.post("/api/admin/invites", status_code=201)
async def create_invite(
    body: InviteCreateRequest,
    admin=Depends(require_admin),
    _csrf=Depends(require_csrf),
    db=Depends(get_db),
    settings=Depends(settings_dep),
):
    await check_rate_limit(db, key_user(admin.id, "invite"), settings.RL_INVITE_MUTATION)
    raw = await auth_service.create_invite(
        db, settings, admin.id, body.email_hint, body.max_uses, body.expires_in_days
    )
    ttl = (
        body.expires_in_days if body.expires_in_days is not None else settings.INVITE_TOKEN_TTL_DAYS
    )
    return InviteResponse(
        invite_url=auth_service.register_url(settings, raw),
        expires_at=to_iso(now_berlin() + timedelta(days=ttl)),
        max_uses=body.max_uses,
        used_count=0,
    ).model_dump()
