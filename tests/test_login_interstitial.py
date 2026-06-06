"""N1: magic-link interstitial — GET confirms, only a same-origin POST sets the cookie.

Defends against login-CSRF / session-fixation: a cross-site navigation can land on the
GET, but it sets no cookie, and the cookie-setting POST is rejected unless it carries a
matching same-origin Origin (which a cross-site auto-submit cannot forge).
"""

from __future__ import annotations

from plantpal import auth_service


async def _issue_link(db, settings, email="admin@b.c") -> str:
    _, raw = await auth_service.bootstrap_admin(db, settings, email)
    return raw


async def test_get_shows_interstitial_without_setting_cookie(client, db, settings):
    raw = await _issue_link(db, settings, "person@example.de")
    r = await client.get(f"/auth/verify?token={raw}")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]
    assert "***@example.de" in r.text  # masked target email is shown
    assert settings.COOKIE_NAME not in r.cookies  # but NO session cookie on the GET
    assert (await client.get("/api/me")).status_code == 401  # GET alone never authenticates


async def test_post_with_matching_origin_logs_in(client, db, settings):
    raw = await _issue_link(db, settings)
    r = await client.post(
        "/auth/verify", data={"token": raw}, headers={"origin": settings.BASE_URL}
    )
    assert r.status_code == 303 and r.headers["location"] == "/"
    assert settings.COOKIE_NAME in r.cookies
    assert (await client.get("/api/me")).status_code == 200


async def test_post_cross_site_origin_rejected_and_token_preserved(client, db, settings):
    raw = await _issue_link(db, settings)
    r = await client.post(
        "/auth/verify", data={"token": raw}, headers={"origin": "https://evil.example"}
    )
    assert r.status_code == 403
    assert (await client.get("/api/me")).status_code == 401  # not signed in
    # the origin check runs BEFORE consumption, so the legit confirm still works afterwards
    r2 = await client.post(
        "/auth/verify", data={"token": raw}, headers={"origin": settings.BASE_URL}
    )
    assert r2.status_code == 303


async def test_post_without_origin_rejected(client, db, settings):
    raw = await _issue_link(db, settings)
    r = await client.post("/auth/verify", data={"token": raw})
    assert r.status_code == 403


async def test_get_invalid_token_redirects_to_login(client, db, settings):
    r = await client.get("/auth/verify?token=bogus-token", follow_redirects=False)
    assert r.status_code == 303
    assert "/login?error=invalid_token" in r.headers["location"]
