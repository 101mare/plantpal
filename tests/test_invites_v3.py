"""AK-V3-AUTH-1..9: invite chains, quota, multi-use links, redemptions."""

import pytest

from plantpal import auth_service as auth
from plantpal.errors import ConflictError, ForbiddenError, TokenExpiredError
from plantpal.time_utils import now_berlin, to_iso


async def _user(db, email, is_admin=0, quota=3):
    cur = await db.execute(
        "INSERT INTO users (email, is_admin, invite_quota, created_at) VALUES (?, ?, ?, ?)",
        (email, is_admin, quota, to_iso(now_berlin())),
    )
    await db.commit()
    return cur.lastrowid


async def test_user_create_invite(db, settings):
    uid = await _user(db, "a@b.c")
    raw, remaining = await auth.create_user_invite(db, settings, uid, max_uses=3)
    assert raw
    assert remaining == 0  # 3 of 3 consumed
    async with db.execute("SELECT token_hash FROM invite_tokens") as cur:
        assert (await cur.fetchone())["token_hash"] != raw  # only the hash is stored


async def test_quota_blocks_overcommit(db, settings):
    uid = await _user(db, "a@b.c", quota=3)
    await auth.create_user_invite(db, settings, uid, max_uses=3)
    with pytest.raises(ForbiddenError):
        await auth.create_user_invite(db, settings, uid, max_uses=1)


async def test_revoke_frees_quota(db, settings):
    uid = await _user(db, "a@b.c", quota=3)
    await auth.create_user_invite(db, settings, uid, max_uses=3)
    inv_id = (await auth.list_user_invites(db, uid))[0]["id"]
    assert await auth.revoke_invite(db, uid, inv_id) is True
    raw2, _ = await auth.create_user_invite(db, settings, uid, max_uses=3)  # quota freed
    assert raw2


async def test_multi_use_redemption(db, settings):
    admin = await _user(db, "admin@b.c", is_admin=1)
    raw, _ = await auth.create_user_invite(db, settings, admin, max_uses=2)
    await auth.register_with_invite(db, settings, raw, "one@b.c")
    await auth.register_with_invite(db, settings, raw, "two@b.c")
    with pytest.raises(ConflictError):  # exhausted on the 3rd
        await auth.register_with_invite(db, settings, raw, "three@b.c")
    async with db.execute("SELECT used_count, used_at FROM invite_tokens") as cur:
        row = await cur.fetchone()
    assert row["used_count"] == 2
    assert row["used_at"] is not None  # exhausted marker set


async def test_redemptions_recorded(db, settings):
    admin = await _user(db, "admin@b.c", is_admin=1)
    raw, _ = await auth.create_user_invite(db, settings, admin, max_uses=2)
    await auth.register_with_invite(db, settings, raw, "one@b.c")
    await auth.register_with_invite(db, settings, raw, "two@b.c")
    async with db.execute("SELECT COUNT(*) AS n FROM invite_redemptions") as cur:
        assert (await cur.fetchone())["n"] == 2


async def test_expired_invite_rejected(db, settings):
    admin = await _user(db, "admin@b.c", is_admin=1)
    raw = await auth.create_invite(db, settings, admin, max_uses=1)
    await db.execute("UPDATE invite_tokens SET expires_at = '2000-01-01T00:00:00'")
    await db.commit()
    with pytest.raises(TokenExpiredError):
        await auth.register_with_invite(db, settings, raw, "x@b.c")


async def test_revoke_foreign_returns_false(db, settings):
    a = await _user(db, "a@b.c")
    b = await _user(db, "b@b.c")
    await auth.create_user_invite(db, settings, a, max_uses=1)
    inv_id = (await auth.list_user_invites(db, a))[0]["id"]
    assert await auth.revoke_invite(db, b, inv_id) is False  # not owner -> route 404


async def test_admin_unlimited_quota(db, settings):
    admin = await _user(db, "admin@b.c", is_admin=1, quota=3)
    raw, _ = await auth.create_user_invite(db, settings, admin, max_uses=20)  # exceeds quota, ok
    assert raw


async def test_invite_status_derivation(db, settings):
    uid = await _user(db, "a@b.c", quota=10)
    await auth.create_user_invite(db, settings, uid, max_uses=1)
    items = await auth.list_user_invites(db, uid)
    assert items[0]["status"] == "active"
