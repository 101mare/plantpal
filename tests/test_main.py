import io
from datetime import timedelta
from pathlib import Path

from PIL import Image

from plantpal import auth_service, image_service, plant_service
from plantpal.models import PlantCreate
from plantpal.time_utils import now_berlin, to_iso


def _png(w=80, h=80):
    buf = io.BytesIO()
    Image.new("RGB", (w, h), (100, 180, 120)).save(buf, "PNG")
    return buf.getvalue()


async def _make_user(db, email):
    cur = await db.execute(
        "INSERT INTO users (email, created_at) VALUES (?, ?)", (email, to_iso(now_berlin()))
    )
    await db.commit()
    return cur.lastrowid


async def _login(client, db, settings, email="admin@b.c", admin=True):
    """Log a user in via the N1 confirm POST; return the CSRF token from the cookie."""
    if admin:
        _, raw = await auth_service.bootstrap_admin(db, settings, email)
    else:
        await _make_user(db, email)
        raw, _ = await auth_service.request_login_link(db, settings, email)
    resp = await client.post(
        "/auth/verify", data={"token": raw}, headers={"origin": settings.BASE_URL}
    )
    assert resp.status_code == 303  # cookies set on the confirm redirect
    return client.cookies.get(settings.CSRF_COOKIE_NAME)


# --- AK-22 health ---


async def test_health(client):
    r = await client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["db_ok"] is True


# --- auth flow + AK-3 ---


async def test_me_requires_auth(client):
    r = await client.get("/api/me")
    assert r.status_code == 401


async def test_verify_expired_token_redirects_to_login(client, db, settings):
    _, raw = await auth_service.bootstrap_admin(db, settings, "a@b.c")
    await db.execute(
        "UPDATE login_tokens SET expires_at = ?", (to_iso(now_berlin() - timedelta(minutes=1)),)
    )
    await db.commit()
    r = await client.get(f"/auth/verify?token={raw}")
    assert r.status_code == 303
    assert "error=token_expired" in r.headers["location"]


async def test_login_and_me(client, db, settings):
    await _login(client, db, settings, "a@b.c")
    r = await client.get("/api/me")
    assert r.status_code == 200
    assert r.json()["email"] == "a@b.c"


# --- plant CRUD over HTTP + AK-7 water ---


async def test_create_list_water_delete(client, db, settings):
    csrf = await _login(client, db, settings)
    files = {"image": ("p.png", _png(), "image/png")}
    r = await client.post(
        "/api/plants",
        data={"name": "Monstera", "interval_days": "7"},
        files=files,
        headers={"X-CSRF-Token": csrf},
    )
    assert r.status_code == 201
    pid = r.json()["id"]
    assert r.json()["image_url"] == f"/api/plants/{pid}/image"

    r = await client.get("/api/plants")
    assert len(r.json()["items"]) == 1

    # image is served
    r = await client.get(f"/api/plants/{pid}/image")
    assert r.status_code == 200
    assert r.headers["content-type"] == "image/png"

    # backdate → thirsty, then water resets it
    await db.execute(
        "UPDATE plants SET last_watered_at = ? WHERE id = ?", ("2026-01-01T08:00:00", pid)
    )
    await db.commit()
    r = await client.post(f"/api/plants/{pid}/water", headers={"X-CSRF-Token": csrf})
    assert r.status_code == 200
    assert r.json()["is_thirsty"] is False

    r = await client.delete(f"/api/plants/{pid}", headers={"X-CSRF-Token": csrf})
    assert r.status_code == 200
    assert (await client.get("/api/plants")).json()["items"] == []


async def test_create_plant_rolls_back_on_bad_image(client, db, settings):
    csrf = await _login(client, db, settings)
    files = {"image": ("x.txt", b"not an image at all", "text/plain")}
    r = await client.post(
        "/api/plants",
        data={"name": "X", "interval_days": "7"},
        files=files,
        headers={"X-CSRF-Token": csrf},
    )
    assert r.status_code == 415
    # the failed upload must not leave an orphan imageless plant
    assert (await client.get("/api/plants")).json()["items"] == []


async def test_create_plant_honors_image_rate_limit(client, db, settings):
    # N5: create always processes an image, so it must also obey the 5/m image limit.
    csrf = await _login(client, db, settings)
    for i in range(5):  # RL_IMAGE_UPLOAD default = 5/m
        r = await client.post(
            "/api/plants",
            data={"name": f"P{i}", "interval_days": "7"},
            files={"image": ("p.png", _png(), "image/png")},
            headers={"X-CSRF-Token": csrf},
        )
        assert r.status_code == 201, f"create #{i} should pass"
    r = await client.post(
        "/api/plants",
        data={"name": "P6", "interval_days": "7"},
        files={"image": ("p.png", _png(), "image/png")},
        headers={"X-CSRF-Token": csrf},
    )
    assert r.status_code == 429  # 6th create trips the image-upload limit


async def test_account_delete_removes_db_rows_and_images(client, db, settings):
    # C7 (rate-limited delete) happy path + N6 (DB rows first, then best-effort images).
    csrf = await _login(client, db, settings, "del@b.c")
    r = await client.post(
        "/api/plants",
        data={"name": "Cactus", "interval_days": "9"},
        files={"image": ("p.png", _png(), "image/png")},
        headers={"X-CSRF-Token": csrf},
    )
    assert r.status_code == 201
    me = await auth_service.get_user_by_email(db, "del@b.c")
    img_dir = Path(settings.IMAGE_DIR) / str(me["id"])
    assert img_dir.exists()

    r = await client.delete("/api/account", headers={"X-CSRF-Token": csrf})
    assert r.status_code == 200
    assert await auth_service.get_user_by_email(db, "del@b.c") is None  # row gone (cascade)
    assert not img_dir.exists()  # images cleaned up
    assert (await client.get("/api/me")).status_code == 401


# --- AK-21 CSRF ---


async def test_mutation_without_csrf_is_403(client, db, settings):
    await _login(client, db, settings)
    files = {"image": ("p.png", _png(), "image/png")}
    r = await client.post("/api/plants", data={"name": "X", "interval_days": "7"}, files=files)
    assert r.status_code == 403


def test_origin_allowed_dev_tolerates_localhost():
    from plantpal.config import Settings
    from plantpal.deps import origin_allowed

    dev = Settings(APP_ENV="development", BASE_URL="http://localhost:8000")
    assert origin_allowed("http://localhost:8000", dev) is True
    assert origin_allowed("http://localhost:5173", dev) is True  # Vite dev server
    assert origin_allowed("http://127.0.0.1:5173", dev) is True
    assert origin_allowed(None, dev) is True  # falls back to token check
    assert origin_allowed("http://evil.example", dev) is False


def test_origin_allowed_prod_is_strict():
    from plantpal.config import Settings
    from plantpal.deps import origin_allowed

    prod = Settings(APP_ENV="production", BASE_URL="https://plantpal.example.com")
    assert origin_allowed("https://plantpal.example.com", prod) is True
    assert origin_allowed("http://localhost:5173", prod) is False
    assert origin_allowed("https://evil.example", prod) is False


# --- AK-15 isolation ---


async def test_cross_user_plant_is_404(client, db, settings):
    other = await _make_user(db, "other@b.c")
    pid = await plant_service.create_plant(db, other, PlantCreate(name="Secret", interval_days=5))
    await _login(client, db, settings, "me@b.c", admin=True)
    r = await client.get(f"/api/plants/{pid}")
    assert r.status_code == 404


# --- settings + stats ---


async def test_settings_toggle_and_stats(client, db, settings):
    csrf = await _login(client, db, settings)
    r = await client.patch(
        "/api/settings", json={"email_reminders_enabled": False}, headers={"X-CSRF-Token": csrf}
    )
    assert r.status_code == 200
    r = await client.get("/api/settings")
    assert r.json()["email_reminders_enabled"] is False

    r = await client.get("/api/stats")
    body = r.json()
    assert body["total_plants"] == 0
    assert body["thirsty_count"] == 0


# --- admin invite ---


async def test_admin_can_create_invite(client, db, settings):
    csrf = await _login(client, db, settings, "admin@b.c", admin=True)
    r = await client.post(
        "/api/admin/invites", json={"email_hint": "friend@b.c"}, headers={"X-CSRF-Token": csrf}
    )
    assert r.status_code == 201
    assert "/register?token=" in r.json()["invite_url"]


async def test_non_admin_cannot_create_invite(client, db, settings):
    csrf = await _login(client, db, settings, "user@b.c", admin=False)
    r = await client.post("/api/admin/invites", json={}, headers={"X-CSRF-Token": csrf})
    assert r.status_code == 403


# --- AK-19 account delete removes images + logs out ---


async def test_account_delete_removes_everything(client, db, settings):
    csrf = await _login(client, db, settings, "a@b.c", admin=True)
    user = await auth_service.get_user_by_email(db, "a@b.c")
    files = {"image": ("p.png", _png(), "image/png")}
    r = await client.post(
        "/api/plants",
        data={"name": "X", "interval_days": "7"},
        files=files,
        headers={"X-CSRF-Token": csrf},
    )
    pid = r.json()["id"]
    assert image_service.image_file_path(settings, user["id"], pid) is not None

    r = await client.delete("/api/account", headers={"X-CSRF-Token": csrf})
    assert r.status_code == 200
    # images gone
    assert image_service.image_file_path(settings, user["id"], pid) is None
    # session cleared
    assert (await client.get("/api/me")).status_code == 401
    # user gone
    assert await auth_service.get_user_by_email(db, "a@b.c") is None


# --- additional route coverage ---


async def test_request_login_is_generic(client, db, settings):
    # unknown email still returns the same generic 200 (no enumeration)
    r = await client.post("/auth/request-login", json={"email": "ghost@b.c"})
    assert r.status_code == 200
    assert "link has been sent" in r.json()["message"]


async def test_login_request_rate_limited(client, db, settings):
    # AK-18: 4th magic-link request for the same email within the window → 429
    await _make_user(db, "rl@b.c")
    for _ in range(3):
        r = await client.post("/auth/request-login", json={"email": "rl@b.c"})
        assert r.status_code == 200
    r = await client.post("/auth/request-login", json={"email": "rl@b.c"})
    assert r.status_code == 429
    assert "Retry-After" in r.headers


async def test_update_plant_over_http(client, db, settings):
    csrf = await _login(client, db, settings)
    files = {"image": ("p.png", _png(), "image/png")}
    pid = (
        await client.post(
            "/api/plants",
            data={"name": "Aloe", "interval_days": "7"},
            files=files,
            headers={"X-CSRF-Token": csrf},
        )
    ).json()["id"]
    r = await client.patch(
        f"/api/plants/{pid}",
        json={"name": "Aloe Vera", "interval_days": 14},
        headers={"X-CSRF-Token": csrf},
    )
    assert r.status_code == 200
    assert r.json()["name"] == "Aloe Vera"
    assert r.json()["interval_days"] == 14


async def test_replace_image_endpoint(client, db, settings):
    csrf = await _login(client, db, settings)
    files = {"image": ("p.png", _png(), "image/png")}
    pid = (
        await client.post(
            "/api/plants",
            data={"name": "X", "interval_days": "7"},
            files=files,
            headers={"X-CSRF-Token": csrf},
        )
    ).json()["id"]
    new = {"image": ("n.png", _png(120, 120), "image/png")}
    r = await client.post(f"/api/plants/{pid}/image", files=new, headers={"X-CSRF-Token": csrf})
    assert r.status_code == 200
    assert r.json()["image_url"] == f"/api/plants/{pid}/image"


async def test_water_nonexistent_is_404(client, db, settings):
    csrf = await _login(client, db, settings)
    r = await client.post("/api/plants/9999/water", headers={"X-CSRF-Token": csrf})
    assert r.status_code == 404


async def test_delete_nonexistent_is_404(client, db, settings):
    csrf = await _login(client, db, settings)
    r = await client.delete("/api/plants/9999", headers={"X-CSRF-Token": csrf})
    assert r.status_code == 404


async def test_get_image_404_when_missing(client, db, settings):
    csrf = await _login(client, db, settings)
    # create plant directly without image, then request its image
    me = await auth_service.get_user_by_email(db, "admin@b.c")
    pid = await plant_service.create_plant(db, me["id"], PlantCreate(name="X", interval_days=7))
    _ = csrf
    r = await client.get(f"/api/plants/{pid}/image")
    assert r.status_code == 404


async def test_logout_clears_session(client, db, settings):
    csrf = await _login(client, db, settings)
    assert (await client.get("/api/me")).status_code == 200
    r = await client.post("/auth/logout", headers={"X-CSRF-Token": csrf})
    assert r.status_code == 200
    assert (await client.get("/api/me")).status_code == 401


# --- registration flow AK-2 ---


async def test_register_with_invite_flow(client, db, settings):
    # admin creates an invite
    csrf = await _login(client, db, settings, "admin@b.c", admin=True)
    r = await client.post(
        "/api/admin/invites", json={"email_hint": "new@b.c"}, headers={"X-CSRF-Token": csrf}
    )
    token = r.json()["invite_url"].split("token=")[1]
    # new user registers
    r = await client.post("/auth/register", json={"invite_token": token, "email": "new@b.c"})
    assert r.status_code == 200
    assert await auth_service.get_user_by_email(db, "new@b.c") is not None


async def test_create_plant_without_image(client, db, settings):
    """The photo is optional (onboarding: first plant in <30s) — a plant created without
    an image gets image_url=None (the frontend renders the placeholder) and does NOT
    consume the stricter image-upload rate limit."""
    csrf = await _login(client, db, settings)
    r = await client.post(
        "/api/plants",
        data={"name": "Ohne Foto", "interval_days": "7"},
        headers={"X-CSRF-Token": csrf},
    )
    assert r.status_code == 201
    body = r.json()
    assert body["image_url"] is None
    # the image endpoint 404s instead of serving a phantom file
    assert (await client.get(f"/api/plants/{body['id']}/image")).status_code == 404
    # photo can be added later via the existing upload endpoint
    r = await client.post(
        f"/api/plants/{body['id']}/image",
        files={"image": ("p.png", _png(), "image/png")},
        headers={"X-CSRF-Token": csrf},
    )
    assert r.status_code == 200
    r = await client.get("/api/plants")
    assert r.json()["items"][0]["image_url"] == f"/api/plants/{body['id']}/image"


async def test_create_plant_with_empty_image_field(client, db, settings):
    """httpx omits the filename attribute entirely for ("", b"", …) — Starlette parses a
    string form field and FastAPI coerces it to None. The REAL browser wire format
    (filename="" attribute present) is pinned separately with a raw multipart body below."""
    csrf = await _login(client, db, settings)
    r = await client.post(
        "/api/plants",
        data={"name": "Leeres Feld", "interval_days": "3"},
        files={"image": ("", b"", "application/octet-stream")},
        headers={"X-CSRF-Token": csrf},
    )
    assert r.status_code == 201
    assert r.json()["image_url"] is None


async def test_create_plant_nameless_image_part_with_content_rejected(client, db, settings):
    """A nameless multipart part WITH content must never slip past the image pipeline as
    a silent no-image create (Codex P2). Starlette parses such a part as a string form
    field, so the UploadFile validation 422s it — pinned here; the size-guard in the
    route stays as defense in depth for clients that do attach a filenameless file."""
    csrf = await _login(client, db, settings)
    before = len((await client.get("/api/plants")).json()["items"])
    for payload, ctype in [(_png(), "image/png"), (b"definitely not an image", "text/plain")]:
        r = await client.post(
            "/api/plants",
            data={"name": "Anonym", "interval_days": "5"},
            files={"image": ("", payload, ctype)},
            headers={"X-CSRF-Token": csrf},
        )
        assert r.status_code == 422  # rejected at the type boundary, not silently ignored
    assert len((await client.get("/api/plants")).json()["items"]) == before  # no orphans


def _raw_multipart(boundary: str, parts: list[tuple[str, str, bytes, str | None]]) -> bytes:
    """Browser-faithful multipart body: parts = (name, filename_attr|None, content, ctype)."""
    out = bytearray()
    for name, filename, content, ctype in parts:
        out.extend(f"--{boundary}\r\n".encode())
        disp = f'Content-Disposition: form-data; name="{name}"'
        if filename is not None:
            disp += f'; filename="{filename}"'
        out.extend((disp + "\r\n").encode())
        if ctype:
            out.extend(f"Content-Type: {ctype}\r\n".encode())
        out.extend(b"\r\n")
        out.extend(content)
        out.extend(b"\r\n")
    out.extend(f"--{boundary}--\r\n".encode())
    return bytes(out)


async def test_create_plant_browser_empty_picker_raw_multipart(client, db, settings):
    """The GENUINE browser wire format for an unused picker: a part WITH filename=""
    attribute and empty body → Starlette yields UploadFile(filename="", size=0) and the
    has_image guard must treat it as 'no image' (201, placeholder). Pinned with a raw
    body because httpx cannot produce this shape (session-verify finding: a guard
    'mutation' to `image is not None` broke exactly this flagship flow suite-green)."""
    csrf = await _login(client, db, settings)
    b = "----PlantPalBoundary7MA4YWxk"
    body = _raw_multipart(
        b,
        [
            ("name", None, "Browser ohne Foto".encode(), None),
            ("interval_days", None, b"7", None),
            ("image", "", b"", "application/octet-stream"),
        ],
    )
    r = await client.post(
        "/api/plants",
        content=body,
        headers={"content-type": f"multipart/form-data; boundary={b}", "X-CSRF-Token": csrf},
    )
    assert r.status_code == 201, r.text
    assert r.json()["image_url"] is None


async def test_create_plant_nameless_file_with_content_hits_pipeline(client, db, settings):
    """filename="" WITH real bytes is an upload attempt: the size-guard half must route it
    through the image pipeline (valid PNG → processed; never silently dropped)."""
    csrf = await _login(client, db, settings)
    b = "----PlantPalBoundary9XYZ"
    body = _raw_multipart(
        b,
        [
            ("name", None, "Anonymes Foto".encode(), None),
            ("interval_days", None, b"7", None),
            ("image", "", _png(), "image/png"),
        ],
    )
    r = await client.post(
        "/api/plants",
        content=body,
        headers={"content-type": f"multipart/form-data; boundary={b}", "X-CSRF-Token": csrf},
    )
    assert r.status_code == 201, r.text
    assert r.json()["image_url"] is not None  # processed, NOT silently ignored
