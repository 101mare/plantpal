"""AK-V3-AUTH-10..19: 6-digit login code."""

from datetime import timedelta

import pytest

from plantpal import auth_service as auth
from plantpal.errors import AppError, TokenExpiredError, TokenInvalidError
from plantpal.time_utils import now_berlin, to_iso


async def _user(db, email="a@b.c"):
    cur = await db.execute(
        "INSERT INTO users (email, created_at) VALUES (?, ?)", (email, to_iso(now_berlin()))
    )
    await db.commit()
    return cur.lastrowid


def _wrong(code):
    return "000000" if code != "000000" else "111111"


async def test_code_happy(db, settings):
    await _user(db)
    _raw, code = await auth.request_login_link(db, settings, "a@b.c")
    session_token, user = await auth.verify_login_code(db, settings, "a@b.c", code)
    assert user.email == "a@b.c"
    assert await auth.load_session(db, settings, session_token) is not None


async def test_wrong_code_increments(db, settings):
    await _user(db)
    _raw, code = await auth.request_login_link(db, settings, "a@b.c")
    with pytest.raises(TokenInvalidError):
        await auth.verify_login_code(db, settings, "a@b.c", _wrong(code))
    async with db.execute("SELECT attempt_count FROM login_tokens WHERE used_at IS NULL") as cur:
        assert (await cur.fetchone())["attempt_count"] == 1


async def test_code_lockout_keeps_magic_link_alive(db, settings):
    """N3: locking the 6-digit code path must NOT burn the shared magic link.

    The link and code share one login_tokens row; burning it on code-lockout let anyone who
    knew the email DoS the victim's pending login. The 256-bit link stays valid; only the
    guessable code is refused.
    """
    await _user(db)
    raw, code = await auth.request_login_link(db, settings, "a@b.c")
    # the first MAX-1 wrong codes only increment the counter
    for _ in range(settings.LOGIN_CODE_MAX_ATTEMPTS - 1):
        with pytest.raises(TokenInvalidError):
            await auth.verify_login_code(db, settings, "a@b.c", _wrong(code))
    # the MAX-th wrong code locks the CODE path (423)
    with pytest.raises(AppError) as exc:
        await auth.verify_login_code(db, settings, "a@b.c", _wrong(code))
    assert exc.value.status_code == 423 and exc.value.code == "code_locked"
    # further code attempts stay locked — even the correct code now yields code_locked
    with pytest.raises(AppError) as exc2:
        await auth.verify_login_code(db, settings, "a@b.c", code)
    assert exc2.value.code == "code_locked"
    # ...but the magic link still works (not burned)
    session_token, user = await auth.verify_login(db, settings, raw)
    assert user.email == "a@b.c"
    assert await auth.load_session(db, settings, session_token) is not None


async def test_code_ttl_independent_of_link(db, settings):
    await _user(db)
    _raw, code = await auth.request_login_link(db, settings, "a@b.c")
    old = to_iso(now_berlin() - timedelta(minutes=settings.LOGIN_CODE_TTL_MIN + 1))
    await db.execute("UPDATE login_tokens SET created_at = ? WHERE used_at IS NULL", (old,))
    await db.commit()
    with pytest.raises(TokenExpiredError):
        await auth.verify_login_code(db, settings, "a@b.c", code)


async def test_code_single_use(db, settings):
    await _user(db)
    _raw, code = await auth.request_login_link(db, settings, "a@b.c")
    await auth.verify_login_code(db, settings, "a@b.c", code)
    with pytest.raises(TokenInvalidError):
        await auth.verify_login_code(db, settings, "a@b.c", code)


async def test_no_enumeration(db, settings):
    with pytest.raises(TokenInvalidError) as exc:  # unknown email -> generic invalid_code
        await auth.verify_login_code(db, settings, "ghost@b.c", "123456")
    assert exc.value.code == "invalid_code"


async def test_code_bound_to_email(db, settings):
    await _user(db, "a@b.c")
    await _user(db, "b@b.c")
    _raw, code = await auth.request_login_link(db, settings, "a@b.c")
    with pytest.raises(TokenInvalidError):
        await auth.verify_login_code(db, settings, "b@b.c", code)


async def test_mail_carries_valid_code(db, settings):
    await _user(db)
    _raw, code = await auth.request_login_link(db, settings, "a@b.c")
    assert len(code) == 6 and code.isdigit()
    _, user = await auth.verify_login_code(db, settings, "a@b.c", code)
    assert user.email == "a@b.c"
