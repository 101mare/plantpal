"""AK-V3-AUTH-20..28: email change (request -> verify at new address -> confirm)."""

from datetime import timedelta

import pytest

from plantpal import auth_service as auth
from plantpal.errors import (
    AppError,
    ConflictError,
    TokenExpiredError,
    TokenInvalidError,
    TokenUsedError,
)
from plantpal.time_utils import now_berlin, to_iso


async def _user(db, email):
    cur = await db.execute(
        "INSERT INTO users (email, created_at) VALUES (?, ?)", (email, to_iso(now_berlin()))
    )
    await db.commit()
    return cur.lastrowid


def _wrong(code):
    return "000000" if code != "000000" else "111111"


async def test_change_via_code(db, settings):
    uid = await _user(db, "old@b.c")
    _raw, code, masked = await auth.create_email_change(db, settings, uid, "new@b.c")
    assert "***" in masked  # old address masked in the notice
    assert await auth.confirm_email_change_by_code(db, settings, uid, code) == "new@b.c"
    assert (await auth.get_user_by_id(db, uid))["email"] == "new@b.c"


async def test_change_via_link(db, settings):
    uid = await _user(db, "old@b.c")
    raw, _code, _ = await auth.create_email_change(db, settings, uid, "new@b.c")
    assert await auth.confirm_email_change_by_token(db, settings, raw) == "new@b.c"


async def test_email_taken_on_request(db, settings):
    uid = await _user(db, "old@b.c")
    await _user(db, "taken@b.c")
    with pytest.raises(ConflictError):
        await auth.create_email_change(db, settings, uid, "taken@b.c")


async def test_email_taken_on_confirm(db, settings):
    uid = await _user(db, "old@b.c")
    _raw, code, _ = await auth.create_email_change(db, settings, uid, "new@b.c")
    await _user(db, "new@b.c")  # grabbed between request and confirm
    with pytest.raises(ConflictError):
        await auth.confirm_email_change_by_code(db, settings, uid, code)


async def test_change_ttl(db, settings):
    uid = await _user(db, "old@b.c")
    _raw, code, _ = await auth.create_email_change(db, settings, uid, "new@b.c")
    await db.execute(
        "UPDATE email_change_requests SET expires_at = ?",
        (to_iso(now_berlin() - timedelta(minutes=1)),),
    )
    await db.commit()
    with pytest.raises(TokenExpiredError):
        await auth.confirm_email_change_by_code(db, settings, uid, code)


async def test_change_lockout(db, settings):
    uid = await _user(db, "old@b.c")
    _raw, code, _ = await auth.create_email_change(db, settings, uid, "new@b.c")
    for _ in range(settings.EMAIL_CHANGE_MAX_ATTEMPTS):
        with pytest.raises(TokenInvalidError):
            await auth.confirm_email_change_by_code(db, settings, uid, _wrong(code))
    with pytest.raises(AppError) as exc:
        await auth.confirm_email_change_by_code(db, settings, uid, code)
    assert exc.value.status_code == 423


async def test_old_login_tokens_invalidated(db, settings):
    uid = await _user(db, "old@b.c")
    old_raw, _old_code = await auth.request_login_link(db, settings, "old@b.c")
    _raw, code, _ = await auth.create_email_change(db, settings, uid, "new@b.c")
    await auth.confirm_email_change_by_code(db, settings, uid, code)
    with pytest.raises(TokenUsedError):  # the old-address magic link is dead
        await auth.verify_login(db, settings, old_raw)


async def test_confirm_single_use(db, settings):
    uid = await _user(db, "old@b.c")
    _raw, code, _ = await auth.create_email_change(db, settings, uid, "new@b.c")
    await auth.confirm_email_change_by_code(db, settings, uid, code)
    with pytest.raises(TokenInvalidError):
        await auth.confirm_email_change_by_code(db, settings, uid, code)
