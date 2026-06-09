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
    r = await client.post(
        "/auth/verify-code",
        json={"email": "u@b.c", "code": code},
        headers={"origin": settings.BASE_URL},
    )
    assert r.status_code == 200
    assert (await client.get("/api/me")).status_code == 200


async def test_verify_code_http_wrong(client, db, settings):
    await _make_user(db, "u@b.c")
    await auth_service.request_login_link(db, settings, "u@b.c")
    r = await client.post(
        "/auth/verify-code",
        json={"email": "u@b.c", "code": "000000"},
        headers={"origin": settings.BASE_URL},
    )
    assert r.status_code == 400


async def test_verify_code_rejects_cross_site_origin_and_preserves_code(client, db, settings):
    await _make_user(db, "u@b.c")
    _raw, code = await auth_service.request_login_link(db, settings, "u@b.c")
    r = await client.post(
        "/auth/verify-code",
        json={"email": "u@b.c", "code": code},
        headers={"origin": "https://evil.example"},
    )
    assert r.status_code == 403
    assert (await client.get("/api/me")).status_code == 401
    r2 = await client.post(
        "/auth/verify-code",
        json={"email": "u@b.c", "code": code},
        headers={"origin": settings.BASE_URL},
    )
    assert r2.status_code == 200


async def test_verify_confirm_accepts_referer_without_origin(client, db, settings):
    """Safari/iOS omit Origin on a same-origin form POST — Referer must be honored."""
    _, raw = await auth_service.bootstrap_admin(db, settings, "safari@b.c")
    r = await client.post(
        "/auth/verify",
        data={"token": raw},
        headers={"referer": f"{settings.BASE_URL}/auth/verify?token=x"},
    )
    assert r.status_code in (200, 303)  # cookie set regardless of redirect-following
    assert (await client.get("/api/me")).status_code == 200


async def test_verify_confirm_rejects_without_origin_or_referer(client, db, settings):
    _, raw = await auth_service.bootstrap_admin(db, settings, "noheaders@b.c")
    r = await client.post("/auth/verify", data={"token": raw})
    assert r.status_code == 403


async def test_verify_confirm_rejects_cross_site_referer(client, db, settings):
    """A cross-site auto-submit carries a foreign Referer (and always an Origin) — reject."""
    _, raw = await auth_service.bootstrap_admin(db, settings, "evil@b.c")
    r = await client.post(
        "/auth/verify", data={"token": raw}, headers={"referer": "https://evil.example/x"}
    )
    assert r.status_code == 403


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
    await client.post(
        "/auth/verify-code",
        json={"email": "u@b.c", "code": code},
        headers={"origin": settings.BASE_URL},
    )
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
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]
    assert (await auth_service.get_user_by_id(db, me["id"]))["email"] == "admin@b.c"
    r = await client.post(
        "/api/account/email/confirm-link",
        data={"token": raw},
        headers={"origin": settings.BASE_URL},
    )
    assert r.status_code == 303
    assert "email_changed=1" in r.headers["location"]
    assert (await auth_service.get_user_by_id(db, me["id"]))["email"] == "new3@b.c"


async def test_email_change_link_rejects_cross_site_post_and_preserves_token(client, db, settings):
    await _login(client, db, settings)
    me = await auth_service.get_user_by_email(db, "admin@b.c")
    raw, _code, _ = await auth_service.create_email_change(db, settings, me["id"], "new4@b.c")
    r = await client.post(
        "/api/account/email/confirm-link",
        data={"token": raw},
        headers={"origin": "https://evil.example"},
    )
    assert r.status_code == 403
    assert (await auth_service.get_user_by_id(db, me["id"]))["email"] == "admin@b.c"
    r2 = await client.post(
        "/api/account/email/confirm-link",
        data={"token": raw},
        headers={"referer": f"{settings.BASE_URL}/api/account/email/confirm?token=x"},
    )
    assert r2.status_code == 303
    assert (await auth_service.get_user_by_id(db, me["id"]))["email"] == "new4@b.c"


async def test_stats_by_room_http(client, db, settings):
    await _login(client, db, settings)
    r = await client.get("/api/stats?by_room=true")
    assert r.status_code == 200
    assert "rooms" in r.json()
