"""Complementary tests for auth_service invite functions and /api/invites HTTP endpoints.

Coverage:
- create_user_invite: quota enforcement, custom max_uses, expiry, admin exemption
- _consumed_quota: correct counting, revoked/expired exclusion
- list_user_invites: per-user isolation, response shape
- revoke_invite: own vs. other user, blocks registration after revoke
- register_with_invite edges: expired invite, max_uses exhaustion, email normalization,
  used_count increment
- set_invite_quota: known/unknown user
- HTTP /api/invites: CSRF protection, revoke endpoint, status reflected after revoke

Run: pytest tests/test_auth_invites.py -v
"""

from __future__ import annotations

from datetime import timedelta

import pytest

from plantpal import auth_service
from plantpal.errors import ConflictError, ForbiddenError, TokenExpiredError
from plantpal.time_utils import from_iso, now_berlin, to_iso

# ---------------------------------------------------------------------------
# Local helpers (intentionally different signatures from test_auth_v3_http.py
# and test_auth_service.py helpers so they are not confused with those)
# ---------------------------------------------------------------------------


async def _insert_user(db, email, *, quota=3, is_admin=0):
    """Direct INSERT — bypasses bootstrap_admin so we can set quota freely."""
    cur = await db.execute(
        "INSERT INTO users (email, invite_quota, is_admin, created_at) VALUES (?, ?, ?, ?)",
        (email, quota, is_admin, to_iso(now_berlin())),
    )
    await db.commit()
    return cur.lastrowid


async def _http_login(client, db, settings, email="admin@b.c"):
    """Bootstrap admin, consume magic link, return CSRF token."""
    _, raw = await auth_service.bootstrap_admin(db, settings, email)
    await client.post("/auth/verify", data={"token": raw}, headers={"origin": settings.BASE_URL})
    return client.cookies.get(settings.CSRF_COOKIE_NAME)


# ===========================================================================
# create_user_invite
# ===========================================================================


async def test_create_user_invite_within_quota_succeeds(db, settings):
    # Arrange
    uid = await _insert_user(db, "u@b.c", quota=3)

    # Act
    raw, remaining = await auth_service.create_user_invite(db, settings, uid, max_uses=2)

    # Assert
    assert raw is not None and len(raw) > 10
    assert remaining == 1  # 3 quota − 2 consumed


async def test_create_user_invite_exceeding_quota_raises(db, settings):
    uid = await _insert_user(db, "u@b.c", quota=2)

    with pytest.raises(ForbiddenError) as exc_info:
        await auth_service.create_user_invite(db, settings, uid, max_uses=3)

    assert exc_info.value.code == "invite_quota_exceeded"


async def test_create_user_invite_respects_custom_max_uses(db, settings):
    uid = await _insert_user(db, "u@b.c", quota=10)

    await auth_service.create_user_invite(db, settings, uid, max_uses=5)

    invites = await auth_service.list_user_invites(db, uid)
    assert invites[0]["max_uses"] == 5


async def test_create_user_invite_expiry_within_one_minute_of_ttl(db, settings):
    uid = await _insert_user(db, "u@b.c", quota=5)

    await auth_service.create_user_invite(db, settings, uid, max_uses=1)

    invites = await auth_service.list_user_invites(db, uid)
    actual_expiry = from_iso(invites[0]["expires_at"])
    expected_expiry = now_berlin() + timedelta(days=settings.INVITE_TOKEN_TTL_DAYS)
    assert abs((actual_expiry - expected_expiry).total_seconds()) < 60


async def test_create_user_invite_admin_exempt_from_quota(db, settings):
    """Admin with quota=1 must not be refused when requesting max_uses=5."""
    uid = await _insert_user(db, "admin@b.c", quota=1, is_admin=1)

    # Would raise ForbiddenError for a regular user (5 > 1)
    raw, remaining = await auth_service.create_user_invite(db, settings, uid, max_uses=5)

    assert raw is not None
    # For admins the code returns quota, not quota-consumed
    assert remaining == 1


# ===========================================================================
# _consumed_quota
# ===========================================================================


async def test_consumed_quota_sums_active_invites(db, settings):
    uid = await _insert_user(db, "u@b.c", quota=20)
    await auth_service.create_user_invite(db, settings, uid, max_uses=2)
    await auth_service.create_user_invite(db, settings, uid, max_uses=3)

    consumed = await auth_service._consumed_quota(db, uid)

    assert consumed == 5  # 2 + 3


async def test_consumed_quota_excludes_revoked_invites(db, settings):
    uid = await _insert_user(db, "u@b.c", quota=10)
    await auth_service.create_user_invite(db, settings, uid, max_uses=3)
    invites = await auth_service.list_user_invites(db, uid)
    await auth_service.revoke_invite(db, uid, invites[0]["id"])

    consumed = await auth_service._consumed_quota(db, uid)

    assert consumed == 0


async def test_consumed_quota_excludes_expired_invites(db, settings):
    uid = await _insert_user(db, "u@b.c", quota=10)
    await auth_service.create_user_invite(db, settings, uid, max_uses=3)
    # Manually expire the invite row
    past = to_iso(now_berlin() - timedelta(days=1))
    await db.execute("UPDATE invite_tokens SET expires_at = ?", (past,))
    await db.commit()

    consumed = await auth_service._consumed_quota(db, uid)

    assert consumed == 0


# ===========================================================================
# list_user_invites
# ===========================================================================


async def test_list_user_invites_only_returns_own_invites(db, settings):
    uid1 = await _insert_user(db, "u1@b.c", quota=5)
    uid2 = await _insert_user(db, "u2@b.c", quota=5)
    await auth_service.create_user_invite(db, settings, uid1, max_uses=1)
    await auth_service.create_user_invite(db, settings, uid2, max_uses=1)

    invites1 = await auth_service.list_user_invites(db, uid1)
    invites2 = await auth_service.list_user_invites(db, uid2)

    assert len(invites1) == 1
    assert len(invites2) == 1
    assert invites1[0]["id"] != invites2[0]["id"]


async def test_list_user_invites_shape_and_active_status(db, settings):
    uid = await _insert_user(db, "u@b.c", quota=5)
    await auth_service.create_user_invite(db, settings, uid, max_uses=2)

    invites = await auth_service.list_user_invites(db, uid)
    item = invites[0]

    required_fields = (
        "id",
        "max_uses",
        "used_count",
        "expires_at",
        "revoked_at",
        "created_at",
        "status",
    )
    for field in required_fields:
        assert field in item, f"Missing field: {field}"

    assert item["status"] == "active"
    assert item["used_count"] == 0
    assert item["max_uses"] == 2
    assert item["revoked_at"] is None


# ===========================================================================
# revoke_invite
# ===========================================================================


async def test_revoke_own_invite_returns_true(db, settings):
    uid = await _insert_user(db, "u@b.c", quota=5)
    await auth_service.create_user_invite(db, settings, uid, max_uses=1)
    invites = await auth_service.list_user_invites(db, uid)

    result = await auth_service.revoke_invite(db, uid, invites[0]["id"])

    assert result is True


async def test_revoke_another_users_invite_returns_false(db, settings):
    uid1 = await _insert_user(db, "u1@b.c", quota=5)
    uid2 = await _insert_user(db, "u2@b.c", quota=5)
    await auth_service.create_user_invite(db, settings, uid1, max_uses=1)
    invites_of_uid1 = await auth_service.list_user_invites(db, uid1)

    result = await auth_service.revoke_invite(db, uid2, invites_of_uid1[0]["id"])

    assert result is False
    # Original invite must still be intact
    invites_after = await auth_service.list_user_invites(db, uid1)
    assert invites_after[0]["status"] == "active"


async def test_revoked_invite_blocks_registration(db, settings):
    uid = await _insert_user(db, "u@b.c", quota=5)
    raw, _ = await auth_service.create_user_invite(db, settings, uid, max_uses=3)
    invites = await auth_service.list_user_invites(db, uid)
    await auth_service.revoke_invite(db, uid, invites[0]["id"])

    with pytest.raises(ConflictError) as exc_info:
        await auth_service.register_with_invite(db, settings, raw, "new@b.c")

    assert exc_info.value.code == "invite_revoked"


# ===========================================================================
# register_with_invite — complementary edge cases
# ===========================================================================


async def test_register_with_expired_invite_raises(db, settings):
    uid = await _insert_user(db, "u@b.c", quota=5)
    raw, _ = await auth_service.create_user_invite(db, settings, uid, max_uses=1)
    past = to_iso(now_berlin() - timedelta(days=1))
    await db.execute("UPDATE invite_tokens SET expires_at = ?", (past,))
    await db.commit()

    with pytest.raises(TokenExpiredError):
        await auth_service.register_with_invite(db, settings, raw, "new@b.c")


@pytest.mark.parametrize("n", [1, 2])
async def test_register_with_invite_allows_n_uses_then_rejects(db, settings, n):
    """max_uses=n: first n registrations succeed; the n+1th raises invite_exhausted."""
    uid = await _insert_user(db, "u@b.c", quota=20)
    raw, _ = await auth_service.create_user_invite(db, settings, uid, max_uses=n)

    for i in range(n):
        await auth_service.register_with_invite(db, settings, raw, f"user{i}@b.c")

    with pytest.raises(ConflictError) as exc_info:
        await auth_service.register_with_invite(db, settings, raw, "extra@b.c")

    assert exc_info.value.code == "invite_exhausted"


async def test_register_normalizes_email_uppercase_and_whitespace(db, settings):
    uid = await _insert_user(db, "u@b.c", quota=5)
    raw, _ = await auth_service.create_user_invite(db, settings, uid, max_uses=1)

    await auth_service.register_with_invite(db, settings, raw, "  NEW@Example.COM  ")

    user = await auth_service.get_user_by_email(db, "new@example.com")
    assert user is not None
    assert user["email"] == "new@example.com"


async def test_register_with_invite_increments_used_count(db, settings):
    uid = await _insert_user(db, "u@b.c", quota=5)
    raw, _ = await auth_service.create_user_invite(db, settings, uid, max_uses=3)

    await auth_service.register_with_invite(db, settings, raw, "r1@b.c")

    invites = await auth_service.list_user_invites(db, uid)
    assert invites[0]["used_count"] == 1


# ===========================================================================
# set_invite_quota
# ===========================================================================


@pytest.mark.parametrize(
    "target_email,expected",
    [
        ("known@b.c", True),
        ("nobody@x.y", False),
    ],
)
async def test_set_invite_quota(db, settings, target_email, expected):
    await _insert_user(db, "known@b.c", quota=3)

    result = await auth_service.set_invite_quota(db, target_email, 10)

    assert result is expected


# ===========================================================================
# HTTP /api/invites
# ===========================================================================


async def test_create_invite_without_csrf_header_returns_403(client, db, settings):
    """POST /api/invites with a valid session but no X-CSRF-Token must be rejected."""
    await _http_login(client, db, settings)

    r = await client.post("/api/invites", json={"max_uses": 1})  # no CSRF header

    assert r.status_code == 403


async def test_revoke_via_http_updates_status_to_revoked(client, db, settings):
    csrf = await _http_login(client, db, settings)

    # Create
    r = await client.post("/api/invites", json={"max_uses": 1}, headers={"X-CSRF-Token": csrf})
    assert r.status_code == 201

    # List to get the id
    r = await client.get("/api/invites")
    inv_id = r.json()["items"][0]["id"]

    # Revoke
    r = await client.post(f"/api/invites/{inv_id}/revoke", headers={"X-CSRF-Token": csrf})
    assert r.status_code == 200

    # List again — status must be "revoked"
    r = await client.get("/api/invites")
    assert r.json()["items"][0]["status"] == "revoked"


async def test_create_invite_response_shape(client, db, settings):
    """POST /api/invites response must carry invite_url, expires_at, max_uses, used_count."""
    csrf = await _http_login(client, db, settings)

    r = await client.post("/api/invites", json={"max_uses": 2}, headers={"X-CSRF-Token": csrf})

    assert r.status_code == 201
    body = r.json()
    assert "invite_url" in body
    assert "/register?token=" in body["invite_url"]
    assert body["max_uses"] == 2
    assert body["used_count"] == 0
    assert "expires_at" in body
