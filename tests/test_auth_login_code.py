"""
Characterisation + edge-case tests for the 6-digit login-code flow.

Coverage:
- verify_login_code (service): happy path, wrong codes, expiry, max-attempts lockout,
  unknown email, case-insensitive email, whitespace-trimmed email, single-use, disabled user
- request_login_link / POST /auth/request-login: anti-enumeration (identical 200 body)
- POST /auth/verify-code (HTTP): IP and per-email rate-limit → 429

Run:
    cd /home/kipoc/Schreibtisch/projects/plantpal
    source .venv/bin/activate
    python -m pytest tests/test_auth_login_code.py -v
"""

from __future__ import annotations

from datetime import timedelta

import httpx
import pytest
import pytest_asyncio

from plantpal import auth_service
from plantpal.errors import AppError, ForbiddenError, TokenExpiredError, TokenInvalidError
from plantpal.time_utils import now_berlin, to_iso

# ---------------------------------------------------------------------------
# Shared helper
# ---------------------------------------------------------------------------


async def _make_user(db, email: str, *, is_admin: int = 0, status: str = "active") -> int:
    cur = await db.execute(
        "INSERT INTO users (email, is_admin, status, created_at) VALUES (?, ?, ?, ?)",
        (email, is_admin, status, to_iso(now_berlin())),
    )
    await db.commit()
    return cur.lastrowid


# ---------------------------------------------------------------------------
# Fixture: client with tight rate-limit windows for RL tests
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def client_tight_rl(settings, db):
    """ASGI client with IP+email code-verify limits of '2/m' for rate-limit tests."""
    from plantpal.main import create_app

    tight = settings.model_copy(
        update={
            "RL_LOGIN_CODE_VERIFY_IP": "2/m",
            "RL_LOGIN_CODE_VERIFY_EMAIL": "2/m",
        }
    )
    app = create_app(settings=tight, db=db)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url=tight.BASE_URL) as c:
        yield c


# ---------------------------------------------------------------------------
# Service-level: verify_login_code — happy path
# ---------------------------------------------------------------------------


async def test_verify_login_code_happy(db, settings):
    """Correct code opens a valid session and returns the matching user."""
    # Arrange
    await _make_user(db, "alice@b.c")
    _, code = await auth_service.request_login_link(db, settings, "alice@b.c")

    # Act
    session_token, user = await auth_service.verify_login_code(db, settings, "alice@b.c", code)

    # Assert
    assert session_token is not None
    assert user.email == "alice@b.c"
    assert await auth_service.load_session(db, settings, session_token) is not None


# ---------------------------------------------------------------------------
# Service-level: verify_login_code — wrong code variants
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("bad_code", ["000000", "999999", "123456"])
async def test_verify_login_code_wrong_code_rejected(db, settings, bad_code):
    """Any code that does not match the issued one is rejected with TokenInvalidError."""
    await _make_user(db, "bob@b.c")
    _, actual_code = await auth_service.request_login_link(db, settings, "bob@b.c")
    if bad_code == actual_code:
        pytest.skip("Generated code collided with test fixture value — rerun")

    with pytest.raises(TokenInvalidError):
        await auth_service.verify_login_code(db, settings, "bob@b.c", bad_code)


# ---------------------------------------------------------------------------
# Service-level: verify_login_code — expiry
# ---------------------------------------------------------------------------


async def test_verify_login_code_expired(db, settings):
    """Codes whose created_at is older than LOGIN_CODE_TTL_MIN are rejected."""
    await _make_user(db, "carol@b.c")
    _, code = await auth_service.request_login_link(db, settings, "carol@b.c")

    # Backdate created_at so the window has elapsed
    stale = to_iso(now_berlin() - timedelta(minutes=settings.LOGIN_CODE_TTL_MIN + 1))
    await db.execute("UPDATE login_tokens SET created_at = ?", (stale,))
    await db.commit()

    with pytest.raises(TokenExpiredError):
        await auth_service.verify_login_code(db, settings, "carol@b.c", code)


# ---------------------------------------------------------------------------
# Service-level: verify_login_code — max-attempts lockout
# ---------------------------------------------------------------------------


async def test_verify_login_code_max_attempts_locks_correct_code(db, settings):
    """After LOGIN_CODE_MAX_ATTEMPTS wrong guesses even the correct code is refused."""
    await _make_user(db, "dave@b.c")
    _, code = await auth_service.request_login_link(db, settings, "dave@b.c")
    wrong = "000000" if code != "000000" else "111111"

    # Exhaust all allowed attempts (last iteration raises code_locked itself)
    for _ in range(settings.LOGIN_CODE_MAX_ATTEMPTS):
        with pytest.raises((TokenInvalidError, AppError)):
            await auth_service.verify_login_code(db, settings, "dave@b.c", wrong)

    # The correct code must also be rejected — the token is now locked
    with pytest.raises(AppError) as exc_info:
        await auth_service.verify_login_code(db, settings, "dave@b.c", code)
    assert exc_info.value.code == "code_locked"


# ---------------------------------------------------------------------------
# Service-level: verify_login_code — unknown email
# ---------------------------------------------------------------------------


async def test_verify_login_code_unknown_email(db, settings):
    """No pending token for an unknown email → TokenInvalidError (no user enumeration)."""
    with pytest.raises(TokenInvalidError):
        await auth_service.verify_login_code(db, settings, "ghost@x.y", "000000")


# ---------------------------------------------------------------------------
# Service-level: verify_login_code — email normalisation
# ---------------------------------------------------------------------------


async def test_verify_login_code_email_case_insensitive(db, settings):
    """Email input is normalised to lowercase so case variants resolve the same token."""
    await _make_user(db, "eve@b.c")
    _, code = await auth_service.request_login_link(db, settings, "eve@b.c")

    session_token, user = await auth_service.verify_login_code(db, settings, "EVE@B.C", code)

    assert user.email == "eve@b.c"
    assert await auth_service.load_session(db, settings, session_token) is not None


async def test_verify_login_code_email_whitespace_trimmed(db, settings):
    """Leading/trailing whitespace in the email input is stripped before lookup."""
    await _make_user(db, "frank@b.c")
    _, code = await auth_service.request_login_link(db, settings, "frank@b.c")

    session_token, user = await auth_service.verify_login_code(db, settings, "  frank@b.c  ", code)

    assert user.email == "frank@b.c"
    assert await auth_service.load_session(db, settings, session_token) is not None


# ---------------------------------------------------------------------------
# Service-level: verify_login_code — single-use
# ---------------------------------------------------------------------------


async def test_verify_login_code_single_use(db, settings):
    """A code cannot be consumed twice; the second call raises TokenInvalidError."""
    await _make_user(db, "grace@b.c")
    _, code = await auth_service.request_login_link(db, settings, "grace@b.c")

    # First use succeeds
    await auth_service.verify_login_code(db, settings, "grace@b.c", code)

    # Second use: the token row now has used_at set, so the WHERE clause finds nothing
    with pytest.raises(TokenInvalidError):
        await auth_service.verify_login_code(db, settings, "grace@b.c", code)


# ---------------------------------------------------------------------------
# Service-level: verify_login_code — disabled user
# ---------------------------------------------------------------------------


async def test_verify_login_code_disabled_user(db, settings):
    """A code issued while the account was active is rejected if the account is later disabled."""
    await _make_user(db, "henry@b.c", status="active")
    _, code = await auth_service.request_login_link(db, settings, "henry@b.c")

    # Disable the account between issuance and verification
    await db.execute("UPDATE users SET status = 'disabled' WHERE email = 'henry@b.c'")
    await db.commit()

    with pytest.raises(ForbiddenError) as exc_info:
        await auth_service.verify_login_code(db, settings, "henry@b.c", code)
    assert exc_info.value.code == "user_disabled"


# ---------------------------------------------------------------------------
# Anti-enumeration: POST /auth/request-login identical HTTP responses
# ---------------------------------------------------------------------------


async def test_request_login_http_same_body_known_vs_unknown(client, db, settings):
    """Known and unknown emails receive the exact same 200 body (no existence leak)."""
    await _make_user(db, "known@b.c")

    r_known = await client.post("/auth/request-login", json={"email": "known@b.c"})
    r_unknown = await client.post("/auth/request-login", json={"email": "nobody@x.y"})

    assert r_known.status_code == 200
    assert r_unknown.status_code == 200
    assert r_known.json() == r_unknown.json()


async def test_request_login_http_same_body_disabled_vs_active(client, db, settings):
    """A disabled account and an active account return an identical 200 body (no status leak)."""
    await _make_user(db, "live@b.c", status="active")
    await _make_user(db, "gone@b.c", status="disabled")

    r_live = await client.post("/auth/request-login", json={"email": "live@b.c"})
    r_gone = await client.post("/auth/request-login", json={"email": "gone@b.c"})

    assert r_live.status_code == 200
    assert r_gone.status_code == 200
    assert r_live.json() == r_gone.json()


# ---------------------------------------------------------------------------
# Rate limits: POST /auth/verify-code
# ---------------------------------------------------------------------------


async def test_verify_code_ip_rate_limit_yields_429(client_tight_rl, db, settings):
    """Exceeding RL_LOGIN_CODE_VERIFY_IP (2/m) returns 429 with a Retry-After header.

    All requests share the same source IP (ASGI test transport sets a fixed client.host),
    so the IP bucket fills up after 2 allowed requests.
    """
    await _make_user(db, "rl_ip@b.c")

    # Two requests are within the limit (count ≤ 2 passes; count 3 is > 2)
    for _ in range(2):
        await client_tight_rl.post(
            "/auth/verify-code", json={"email": "rl_ip@b.c", "code": "000000"}
        )

    # Third request must be rejected by the IP bucket
    r = await client_tight_rl.post(
        "/auth/verify-code", json={"email": "rl_ip@b.c", "code": "000000"}
    )
    assert r.status_code == 429
    assert "Retry-After" in r.headers


async def test_verify_code_email_rate_limit_yields_429(client_tight_rl, db, settings):
    """Exceeding RL_LOGIN_CODE_VERIFY_EMAIL (2/m) returns 429 on the per-email bucket.

    Different CF-Connecting-IP headers are used so each request gets its own IP bucket
    (count=1, well below limit=2), ensuring only the shared email bucket overflows.
    TRUST_CF_CONNECTING_IP defaults to True, so the header is honoured by client_ip().
    """
    await _make_user(db, "rl_email@b.c")

    # Two requests from distinct IPs — email bucket accumulates, IP buckets stay at 1
    for i in range(2):
        await client_tight_rl.post(
            "/auth/verify-code",
            json={"email": "rl_email@b.c", "code": "000000"},
            headers={"cf-connecting-ip": f"10.0.0.{i}"},
        )

    # Third request from yet another IP — IP bucket=1, email bucket=3 > 2 → 429
    r = await client_tight_rl.post(
        "/auth/verify-code",
        json={"email": "rl_email@b.c", "code": "000000"},
        headers={"cf-connecting-ip": "10.0.0.99"},
    )
    assert r.status_code == 429
    assert "Retry-After" in r.headers
