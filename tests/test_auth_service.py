import asyncio
from datetime import timedelta

import aiosqlite
import pytest

from plantpal import auth_service as auth
from plantpal.db import connect
from plantpal.errors import ConflictError, TokenExpiredError, TokenUsedError
from plantpal.time_utils import now_berlin, to_iso


async def _make_user(db, email, is_admin=0, status="active"):
    cur = await db.execute(
        "INSERT INTO users (email, is_admin, status, created_at) VALUES (?, ?, ?, ?)",
        (email, is_admin, status, to_iso(now_berlin())),
    )
    await db.commit()
    return cur.lastrowid


# --- request login ---


async def test_request_login_returns_token_for_active_user(db, settings):
    await _make_user(db, "a@b.c")
    raw = await auth.request_login_link(db, settings, "a@b.c")
    assert raw is not None


async def test_request_login_returns_none_for_unknown(db, settings):
    assert await auth.request_login_link(db, settings, "nobody@x.y") is None


async def test_request_login_returns_none_for_disabled(db, settings):
    await _make_user(db, "d@b.c", status="disabled")
    assert await auth.request_login_link(db, settings, "d@b.c") is None


# --- verify (happy + edge) ---


async def test_verify_login_happy(db, settings):
    await _make_user(db, "a@b.c")
    raw = await auth.request_login_link(db, settings, "a@b.c")
    session_token, user = await auth.verify_login(db, settings, raw)
    assert user.email == "a@b.c"
    assert await auth.load_session(db, settings, session_token) is not None


async def test_verify_login_rejects_used_token(db, settings):
    await _make_user(db, "a@b.c")
    raw = await auth.request_login_link(db, settings, "a@b.c")
    await auth.verify_login(db, settings, raw)
    with pytest.raises(TokenUsedError):
        await auth.verify_login(db, settings, raw)


async def test_verify_login_rejects_expired(db, settings):
    await _make_user(db, "a@b.c")
    raw = await auth.request_login_link(db, settings, "a@b.c")
    past = to_iso(now_berlin() - timedelta(minutes=1))
    await db.execute("UPDATE login_tokens SET expires_at = ?", (past,))
    await db.commit()
    with pytest.raises(TokenExpiredError):
        await auth.verify_login(db, settings, raw)


async def test_verify_login_double_click_race(db, settings, tmp_path):
    """Two concurrent verifies on separate connections: exactly one wins."""
    await _make_user(db, "a@b.c")
    raw = await auth.request_login_link(db, settings, "a@b.c")
    conn2 = await connect(settings)
    try:
        results = await asyncio.gather(
            auth.verify_login(db, settings, raw),
            auth.verify_login(conn2, settings, raw),
            return_exceptions=True,
        )
    finally:
        await conn2.close()
    successes = [r for r in results if not isinstance(r, Exception)]
    failures = [r for r in results if isinstance(r, Exception)]
    assert len(successes) == 1
    assert len(failures) == 1
    assert isinstance(failures[0], TokenUsedError)


# --- register with invite ---


async def test_register_with_invite_happy(db, settings):
    admin = await _make_user(db, "admin@b.c", is_admin=1)
    invite = await auth.create_invite(db, settings, admin, "new@b.c")
    raw = await auth.register_with_invite(db, settings, invite, "new@b.c")
    # the returned login token logs the new user in
    _, user = await auth.verify_login(db, settings, raw)
    assert user.email == "new@b.c"
    assert user.is_admin is False


async def test_register_rejects_used_invite(db, settings):
    admin = await _make_user(db, "admin@b.c", is_admin=1)
    invite = await auth.create_invite(db, settings, admin, None)
    await auth.register_with_invite(db, settings, invite, "one@b.c")
    with pytest.raises(TokenUsedError):
        await auth.register_with_invite(db, settings, invite, "two@b.c")


async def test_register_rejects_existing_email(db, settings):
    admin = await _make_user(db, "admin@b.c", is_admin=1)
    await _make_user(db, "dup@b.c")
    invite = await auth.create_invite(db, settings, admin, None)
    with pytest.raises(ConflictError):
        await auth.register_with_invite(db, settings, invite, "dup@b.c")


# --- sessions ---


async def test_logout_invalidates_session(db, settings):
    uid = await _make_user(db, "a@b.c")
    token = await auth.create_session(db, settings, uid)
    assert await auth.load_session(db, settings, token) is not None
    await auth.logout(db, settings, token)
    assert await auth.load_session(db, settings, token) is None


async def test_sliding_renewal_extends_when_stale(db, settings):
    uid = await _make_user(db, "a@b.c")
    token = await auth.create_session(db, settings, uid)
    stale = to_iso(now_berlin() - timedelta(days=2))
    await db.execute("UPDATE sessions SET renewed_at = ? WHERE user_id = ?", (stale, uid))
    await db.commit()
    row = await auth.load_session(db, settings, token)
    assert await auth.renew_session_if_needed(db, settings, row) is not None


async def test_sliding_renewal_skips_when_fresh(db, settings):
    uid = await _make_user(db, "a@b.c")
    token = await auth.create_session(db, settings, uid)
    row = await auth.load_session(db, settings, token)
    assert await auth.renew_session_if_needed(db, settings, row) is None


async def test_hard_cap_blocks_load(db, settings):
    uid = await _make_user(db, "a@b.c")
    token = await auth.create_session(db, settings, uid)
    past = to_iso(now_berlin() - timedelta(days=1))
    await db.execute("UPDATE sessions SET hard_expires_at = ? WHERE user_id = ?", (past, uid))
    await db.commit()
    assert await auth.load_session(db, settings, token) is None


# --- bootstrap admin ---


async def test_bootstrap_admin_creates_first(db, settings):
    user_id, raw = await auth.bootstrap_admin(db, settings, "admin@b.c")
    _, user = await auth.verify_login(db, settings, raw)
    assert user.is_admin is True
    assert user.id == user_id


async def test_bootstrap_admin_refuses_second_without_force(db, settings):
    await auth.bootstrap_admin(db, settings, "admin1@b.c")
    with pytest.raises(ConflictError):
        await auth.bootstrap_admin(db, settings, "admin2@b.c")


async def test_bootstrap_admin_force_allows_second(db, settings):
    await auth.bootstrap_admin(db, settings, "admin1@b.c")
    user_id, _ = await auth.bootstrap_admin(db, settings, "admin2@b.c", force=True)
    assert user_id is not None


async def test_revoke_user_sessions(db: aiosqlite.Connection, settings):
    uid = await _make_user(db, "a@b.c")
    t1 = await auth.create_session(db, settings, uid)
    t2 = await auth.create_session(db, settings, uid)
    n = await auth.revoke_user_sessions(db, uid)
    assert n == 2
    assert await auth.load_session(db, settings, t1) is None
    assert await auth.load_session(db, settings, t2) is None
