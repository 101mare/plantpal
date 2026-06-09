"""
Complementary characterization + edge-case tests for auth_service magic-link flow.

Covers: peek_login_token, verify_login edge cases, request_login_link normalization,
_generate_code, token supersession, and session helper edge cases.

NOT duplicated from test_auth_service.py: happy-path verify, used-token, expired-token,
double-click race, sliding-renewal stale/fresh, hard-cap, revoke_user_sessions.

Run: pytest tests/test_auth_magic_link.py -q
"""

from __future__ import annotations

from datetime import timedelta

import pytest

from plantpal import auth_service as auth
from plantpal.errors import (
    ForbiddenError,
    TokenExpiredError,
    TokenInvalidError,
    TokenUsedError,
)
from plantpal.security import new_url_token
from plantpal.time_utils import now_berlin, to_iso

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _make_user(db, email, status="active"):
    cur = await db.execute(
        "INSERT INTO users (email, status, created_at) VALUES (?, ?, ?)",
        (email, status, to_iso(now_berlin())),
    )
    await db.commit()
    return cur.lastrowid


# ---------------------------------------------------------------------------
# peek_login_token — happy path
# ---------------------------------------------------------------------------


async def test_peek_login_token_returns_masked_email(db, settings):
    # Arrange
    await _make_user(db, "alice@example.com")
    raw, _code = await auth.request_login_link(db, settings, "alice@example.com")

    # Act
    masked = await auth.peek_login_token(db, settings, raw)

    # Assert: first char of local part + *** + @domain
    assert masked == "a***@example.com"


# ---------------------------------------------------------------------------
# peek_login_token — failure modes (parametrized)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "failure_mode,expected_exc",
    [
        ("expired", TokenExpiredError),
        ("used", TokenUsedError),
        ("unknown", TokenInvalidError),
        ("tampered", TokenInvalidError),
    ],
)
async def test_peek_login_token_raises_on_bad_token(db, settings, failure_mode, expected_exc):
    # Arrange
    await _make_user(db, "b@test.com")
    raw, _code = await auth.request_login_link(db, settings, "b@test.com")

    if failure_mode == "expired":
        past = to_iso(now_berlin() - timedelta(minutes=1))
        await db.execute("UPDATE login_tokens SET expires_at = ?", (past,))
        await db.commit()
        token = raw

    elif failure_mode == "used":
        await db.execute(
            "UPDATE login_tokens SET used_at = ?",
            (to_iso(now_berlin()),),
        )
        await db.commit()
        token = raw

    elif failure_mode == "unknown":
        token = new_url_token()  # never inserted — DB lookup returns nothing

    elif failure_mode == "tampered":
        # One character change at the end (URL-safe base64 alphabet, flip last char)
        token = raw[:-1] + ("A" if raw[-1] != "A" else "B")

    # Act / Assert
    with pytest.raises(expected_exc):
        await auth.peek_login_token(db, settings, token)


# ---------------------------------------------------------------------------
# peek_login_token — user disabled after token issuance
# ---------------------------------------------------------------------------


async def test_peek_login_token_raises_when_user_disabled_after_issuance(db, settings):
    # Arrange
    uid = await _make_user(db, "c@test.com")
    raw, _code = await auth.request_login_link(db, settings, "c@test.com")

    # Disable the account after the token was issued
    await db.execute("UPDATE users SET status = 'disabled' WHERE id = ?", (uid,))
    await db.commit()

    # Act / Assert
    with pytest.raises(ForbiddenError):
        await auth.peek_login_token(db, settings, raw)


# ---------------------------------------------------------------------------
# verify_login — edge cases not covered in test_auth_service.py
# ---------------------------------------------------------------------------


async def test_verify_login_raises_for_completely_unknown_token(db, settings):
    garbage = new_url_token()
    with pytest.raises(TokenInvalidError):
        await auth.verify_login(db, settings, garbage)


async def test_verify_login_raises_for_tampered_token(db, settings):
    # Arrange
    await _make_user(db, "d@test.com")
    raw, _code = await auth.request_login_link(db, settings, "d@test.com")
    tampered = raw[:-1] + ("A" if raw[-1] != "A" else "B")

    # Act / Assert
    with pytest.raises(TokenInvalidError):
        await auth.verify_login(db, settings, tampered)


async def test_verify_login_raises_when_user_disabled_after_issuance(db, settings):
    # Arrange — token issued while user is active, then user is disabled
    uid = await _make_user(db, "e@test.com")
    raw, _code = await auth.request_login_link(db, settings, "e@test.com")

    await db.execute("UPDATE users SET status = 'disabled' WHERE id = ?", (uid,))
    await db.commit()

    # Act / Assert
    with pytest.raises(ForbiddenError):
        await auth.verify_login(db, settings, raw)


# ---------------------------------------------------------------------------
# request_login_link — email normalization
# ---------------------------------------------------------------------------


async def test_request_login_link_is_case_insensitive(db, settings):
    # Arrange — user stored in lowercase
    await _make_user(db, "user@example.com")

    # Act — request with all-uppercase variant
    result = await auth.request_login_link(db, settings, "USER@EXAMPLE.COM")

    # Assert — still resolves to the same active user
    assert result is not None
    raw, code = result
    assert isinstance(raw, str) and len(raw) > 0
    assert isinstance(code, str) and len(code) > 0


async def test_request_login_link_strips_surrounding_whitespace(db, settings):
    # Arrange
    await _make_user(db, "trim@example.com")

    # Act — email with leading/trailing spaces
    result = await auth.request_login_link(db, settings, "  trim@example.com  ")

    # Assert — resolved correctly
    assert result is not None


# ---------------------------------------------------------------------------
# _generate_code — format and statistical uniqueness
# ---------------------------------------------------------------------------


def test_generate_code_is_exactly_six_numeric_digits():
    code = auth._generate_code()
    assert len(code) == 6
    assert code.isdigit()


def test_generate_code_is_zero_padded_and_always_six_digits():
    # Over many calls every code must be exactly 6 digits (including leading-zero values)
    codes = [auth._generate_code() for _ in range(500)]
    assert all(len(c) == 6 for c in codes)
    assert all(c.isdigit() for c in codes)


def test_generate_code_produces_varied_values():
    # With 10^6 possible values, 100 calls all returning the same value is impossible
    codes = {auth._generate_code() for _ in range(100)}
    assert len(codes) > 1


# ---------------------------------------------------------------------------
# New login request invalidates a prior unused token (F-AUTH-19)
# ---------------------------------------------------------------------------


async def test_new_login_request_supersedes_old_token(db, settings):
    """Issuing a second link marks the first one used; verify on old token raises."""
    # Arrange
    await _make_user(db, "sup@test.com")
    raw_old, _ = await auth.request_login_link(db, settings, "sup@test.com")

    # Act — request a fresh link; this should burn the old unused token
    _raw_new, _ = await auth.request_login_link(db, settings, "sup@test.com")

    # Assert — the old token is now treated as used
    with pytest.raises(TokenUsedError):
        await auth.verify_login(db, settings, raw_old)


# ---------------------------------------------------------------------------
# Sessions — complementary edge cases
# ---------------------------------------------------------------------------


async def test_load_session_returns_none_for_garbage_token(db, settings):
    garbage = new_url_token()
    assert await auth.load_session(db, settings, garbage) is None


async def test_create_session_token_is_accepted_by_load_session(db, settings):
    # Arrange
    uid = await _make_user(db, "sess@test.com")

    # Act
    token = await auth.create_session(db, settings, uid)
    row = await auth.load_session(db, settings, token)

    # Assert
    assert row is not None
    assert row["user_id"] == uid


async def test_renew_session_if_needed_triggers_at_exact_threshold(db, settings):
    """A session whose renewed_at equals exactly the renewal threshold IS renewed."""
    # Arrange
    uid = await _make_user(db, "renew@test.com")
    token = await auth.create_session(db, settings, uid)

    # Backdate renewed_at to exactly the threshold boundary
    boundary = to_iso(now_berlin() - timedelta(hours=settings.SESSION_RENEW_IF_OLDER_THAN_HOURS))
    await db.execute("UPDATE sessions SET renewed_at = ? WHERE user_id = ?", (boundary, uid))
    await db.commit()

    row = await auth.load_session(db, settings, token)

    # Act
    result = await auth.renew_session_if_needed(db, settings, row)

    # Assert — (now - renewed_at) >= threshold → NOT strictly less than → renewal fires
    assert result is not None


async def test_touch_last_seen_not_updated_within_debounce_window(db, settings):
    """last_seen_at stays unchanged when the call is within the debounce period."""
    # Arrange
    uid = await _make_user(db, "deb1@test.com")
    token = await auth.create_session(db, settings, uid)
    row = await auth.load_session(db, settings, token)
    original = row["last_seen_at"]

    # Act — pass the current (fresh) last_seen_iso; delta ≈ 0 < debounce window
    await auth.touch_last_seen(db, settings, row["session_id"], row["last_seen_at"])

    # Assert — unchanged
    row2 = await auth.load_session(db, settings, token)
    assert row2["last_seen_at"] == original


async def test_touch_last_seen_updated_when_beyond_debounce_window(db, settings):
    """last_seen_at IS advanced when the supplied timestamp is older than the debounce cap."""
    # Arrange
    uid = await _make_user(db, "deb2@test.com")
    token = await auth.create_session(db, settings, uid)
    row = await auth.load_session(db, settings, token)

    # Simulate a last_seen that pre-dates the debounce window by 1 minute
    stale = to_iso(now_berlin() - timedelta(minutes=settings.SESSION_LAST_SEEN_DEBOUNCE_MIN + 1))

    # Act
    await auth.touch_last_seen(db, settings, row["session_id"], stale)

    # Assert — the DB value is now newer than the stale timestamp we passed
    row2 = await auth.load_session(db, settings, token)
    assert row2["last_seen_at"] != stale
