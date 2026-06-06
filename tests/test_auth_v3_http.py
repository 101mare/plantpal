"""HTTP coverage for v3 auth endpoints: verify-code, invites, email-change."""

from plantpal import auth_service
from plantpal.time_utils import now_berlin, to_iso


async def _make_user(db, email, quota=3):
    await db.execute(
        "INSERT INTO users (email, invite_quota, created_at) VALUES (?, ?, ?)",
        (email, quota, to_iso(now_berlin())),
    )
    await db.commit()


async def _login(client, db, settings, email="admin@b.c"):
    _, raw = await auth_service.bootstrap_admin(db, settings, email)
    await client.post("/auth/verify", data={"token": raw}, headers={"origin": settings.BASE_URL})
    return client.cookies.get(settings.CSRF_COOKIE_NAME)


async def test_verify_code_http_happy(client, db, settings):
    await _make_user(db, "u@b.c")
    _raw, code = await auth_service.request_login_link(db, settings, "u@b.c")
    r = await client.post("/auth/verify-code", json={"email": "u@b.c", "code": code})
    assert r.status_code == 200
    assert (await client.get("/api/me")).status_code == 200


async def test_verify_code_http_wrong(client, db, settings):
    await _make_user(db, "u@b.c")
    await auth_service.request_login_link(db, settings, "u@b.c")
    r = await client.post("/auth/verify-code", json={"email": "u@b.c", "code": "000000"})
    assert r.status_code == 400


async def test_invites_http_flow(client, db, settings):
    csrf = await _login(client, db, settings)
    r = await client.post("/api/invites", json={"max_uses": 2}, headers={"X-CSRF-Token": csrf})
    assert r.status_code == 201
    assert "/register?token=" in r.json()["invite_url"]
    r = await client.get("/api/invites")
    assert len(r.json()["items"]) == 1
    inv_id = r.json()["items"][0]["id"]
    r = await client.post(f"/api/invites/{inv_id}/revoke", headers={"X-CSRF-Token": csrf})
    assert r.status_code == 200
    r = await client.post("/api/invites/9999/revoke", headers={"X-CSRF-Token": csrf})
    assert r.status_code == 404  # foreign/unknown


async def test_invite_quota_http(client, db, settings):
    await _make_user(db, "u@b.c", quota=3)
    _raw, code = await auth_service.request_login_link(db, settings, "u@b.c")
    await client.post("/auth/verify-code", json={"email": "u@b.c", "code": code})
    csrf = client.cookies.get(settings.CSRF_COOKIE_NAME)
    r = await client.post("/api/invites", json={"max_uses": 3}, headers={"X-CSRF-Token": csrf})
    assert r.status_code == 201
    r = await client.post("/api/invites", json={"max_uses": 1}, headers={"X-CSRF-Token": csrf})
    assert r.status_code == 403  # quota exceeded


async def test_email_change_http_code(client, db, settings):
    csrf = await _login(client, db, settings)
    r = await client.post(
        "/api/account/email", json={"new_email": "new@b.c"}, headers={"X-CSRF-Token": csrf}
    )
    assert r.status_code == 200
    # confirm with a service-created change (code is not retrievable from the HTTP request)
    me = await auth_service.get_user_by_email(db, "admin@b.c")
    _raw, code, _ = await auth_service.create_email_change(db, settings, me["id"], "new2@b.c")
    r = await client.post(
        "/api/account/email/confirm", json={"code": code}, headers={"X-CSRF-Token": csrf}
    )
    assert r.status_code == 200
    assert r.json()["email"] == "new2@b.c"


async def test_email_change_http_link(client, db, settings):
    await _login(client, db, settings)
    me = await auth_service.get_user_by_email(db, "admin@b.c")
    raw, _code, _ = await auth_service.create_email_change(db, settings, me["id"], "new3@b.c")
    r = await client.get(f"/api/account/email/confirm?token={raw}", follow_redirects=False)
    assert r.status_code == 303
    assert "email_changed=1" in r.headers["location"]


async def test_stats_by_room_http(client, db, settings):
    await _login(client, db, settings)
    r = await client.get("/api/stats?by_room=true")
    assert r.status_code == 200
    assert "rooms" in r.json()
