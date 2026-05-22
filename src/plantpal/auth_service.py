"""Magic-link auth, sessions (sliding + hard-cap), invites, admin bootstrap.

Token security: only keyed hashes are stored in the DB; the plaintext token
lives only in the email link / session cookie. Single-use consumption is
race-safe via a conditional ``UPDATE ... WHERE used_at IS NULL`` + rowcount check.
"""

from __future__ import annotations

import sqlite3
from datetime import timedelta

import aiosqlite

from .config import Settings
from .errors import (
    ConflictError,
    ForbiddenError,
    TokenExpiredError,
    TokenInvalidError,
    TokenUsedError,
)
from .models import SessionUser
from .security import hash_token, new_url_token, normalize_email
from .time_utils import from_iso, now_berlin, to_iso

# --- URL builders ---


def login_url(settings: Settings, raw_token: str) -> str:
    return f"{settings.BASE_URL}/auth/verify?token={raw_token}"


def register_url(settings: Settings, raw_token: str) -> str:
    return f"{settings.BASE_URL}/register?token={raw_token}"


# --- User lookups ---


async def get_user_by_email(db: aiosqlite.Connection, email: str) -> aiosqlite.Row | None:
    async with db.execute(
        "SELECT * FROM users WHERE email = ? COLLATE NOCASE", (normalize_email(email),)
    ) as cur:
        return await cur.fetchone()


async def get_user_by_id(db: aiosqlite.Connection, user_id: int) -> aiosqlite.Row | None:
    async with db.execute("SELECT * FROM users WHERE id = ?", (user_id,)) as cur:
        return await cur.fetchone()


async def _issue_login_token(
    db: aiosqlite.Connection, settings: Settings, user_id: int, email: str
) -> str:
    """Insert a fresh login token (no commit). Returns the plaintext token."""
    raw = new_url_token()
    now = now_berlin()
    expires = now + timedelta(minutes=settings.LOGIN_TOKEN_TTL_MIN)
    await db.execute(
        "INSERT INTO login_tokens (token_hash, email, user_id, created_at, expires_at) "
        "VALUES (?, ?, ?, ?, ?)",
        (hash_token(raw, settings), normalize_email(email), user_id, to_iso(now), to_iso(expires)),
    )
    return raw


# --- Magic-link request ---


async def request_login_link(
    db: aiosqlite.Connection, settings: Settings, email: str
) -> str | None:
    """Create a login token for an existing active user. Returns plaintext token or None.

    Returning None for unknown/disabled users lets the route give a generic
    (enumeration-resistant) response.
    """
    user = await get_user_by_email(db, email)
    if user is None or user["status"] != "active":
        return None
    raw = await _issue_login_token(db, settings, user["id"], email)
    await db.commit()
    return raw


# --- Magic-link verify (race-safe single-use) ---


async def verify_login(
    db: aiosqlite.Connection, settings: Settings, raw_token: str
) -> tuple[str, SessionUser]:
    """Consume a login token and open a session. Returns (session_token, user)."""
    token_hash = hash_token(raw_token, settings)
    now = now_berlin()
    async with db.execute("SELECT * FROM login_tokens WHERE token_hash = ?", (token_hash,)) as cur:
        tok = await cur.fetchone()

    if tok is None:
        raise TokenInvalidError("Invalid sign-in link.")
    if tok["used_at"] is not None:
        raise TokenUsedError("This sign-in link has already been used.")
    if from_iso(tok["expires_at"]) <= now:
        raise TokenExpiredError("This sign-in link has expired.")

    user = await get_user_by_id(db, tok["user_id"])
    if user is None:
        raise TokenInvalidError("user_not_found", code="user_not_found", status_code=404)
    if user["status"] != "active":
        raise ForbiddenError("This account is disabled.", code="user_disabled")

    consumed = await db.execute(
        "UPDATE login_tokens SET used_at = ? WHERE id = ? AND used_at IS NULL AND expires_at > ?",
        (to_iso(now), tok["id"], to_iso(now)),
    )
    if consumed.rowcount != 1:
        await db.rollback()
        raise TokenUsedError("This sign-in link has already been used.")

    raw_session = await _insert_session(db, settings, user["id"])
    await db.execute("UPDATE users SET last_login_at = ? WHERE id = ?", (to_iso(now), user["id"]))
    await db.commit()
    return raw_session, SessionUser(
        id=user["id"], email=user["email"], is_admin=bool(user["is_admin"])
    )


# --- Registration with invite ---


async def register_with_invite(
    db: aiosqlite.Connection, settings: Settings, invite_raw: str, email: str
) -> str:
    """Validate invite, create user, return a plaintext login token for first login."""
    email = normalize_email(email)
    invite_hash = hash_token(invite_raw, settings)
    now = now_berlin()
    async with db.execute(
        "SELECT * FROM invite_tokens WHERE token_hash = ?", (invite_hash,)
    ) as cur:
        inv = await cur.fetchone()

    if inv is None or inv["revoked_at"] is not None:
        raise TokenInvalidError("Invalid invite.")
    if inv["used_at"] is not None:
        raise TokenUsedError("This invite has already been used.")
    if from_iso(inv["expires_at"]) <= now:
        raise TokenExpiredError("This invite has expired.")
    if await get_user_by_email(db, email) is not None:
        raise ConflictError(
            "This email already has an account. Sign in instead.", code="user_exists"
        )

    try:
        cursor = await db.execute(
            "INSERT INTO users (email, is_admin, created_at) VALUES (?, 0, ?)",
            (email, to_iso(now)),
        )
    except sqlite3.IntegrityError as exc:
        # Concurrent registration won the UNIQUE(email) race — surface as a clean 409.
        await db.rollback()
        raise ConflictError(
            "This email already has an account. Sign in instead.", code="user_exists"
        ) from exc
    user_id = cursor.lastrowid

    consumed = await db.execute(
        "UPDATE invite_tokens SET used_at = ?, used_by_user_id = ? "
        "WHERE id = ? AND used_at IS NULL AND revoked_at IS NULL AND expires_at > ?",
        (to_iso(now), user_id, inv["id"], to_iso(now)),
    )
    if consumed.rowcount != 1:
        await db.rollback()
        raise TokenUsedError("This invite has already been used.")

    raw = await _issue_login_token(db, settings, user_id, email)
    await db.commit()
    return raw


# --- Sessions ---


async def _insert_session(db: aiosqlite.Connection, settings: Settings, user_id: int) -> str:
    """Insert a session row (no commit). Returns plaintext session token."""
    raw = new_url_token()
    now = now_berlin()
    soft = now + timedelta(days=settings.SESSION_SOFT_CAP_DAYS)
    hard = now + timedelta(days=settings.SESSION_HARD_CAP_DAYS)
    await db.execute(
        "INSERT INTO sessions "
        "(session_hash, user_id, created_at, expires_at, hard_expires_at, "
        "last_seen_at, renewed_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (
            hash_token(raw, settings),
            user_id,
            to_iso(now),
            to_iso(soft),
            to_iso(hard),
            to_iso(now),
            to_iso(now),
        ),
    )
    return raw


async def create_session(db: aiosqlite.Connection, settings: Settings, user_id: int) -> str:
    raw = await _insert_session(db, settings, user_id)
    await db.commit()
    return raw


async def load_session(
    db: aiosqlite.Connection, settings: Settings, raw_token: str
) -> aiosqlite.Row | None:
    """Return a joined session+user row if the session is valid, else None."""
    now = to_iso(now_berlin())
    async with db.execute(
        "SELECT s.id AS session_id, s.last_seen_at, s.renewed_at, s.hard_expires_at, "
        "       u.id AS user_id, u.email, u.is_admin "
        "FROM sessions s JOIN users u ON u.id = s.user_id "
        "WHERE s.session_hash = ? AND s.revoked_at IS NULL "
        "  AND s.expires_at > ? AND s.hard_expires_at > ? AND u.status = 'active'",
        (hash_token(raw_token, settings), now, now),
    ) as cur:
        return await cur.fetchone()


async def renew_session_if_needed(
    db: aiosqlite.Connection, settings: Settings, session_row: aiosqlite.Row
) -> str | None:
    """Sliding renewal. Returns new expires_at ISO (caller bumps cookie) or None."""
    renewed_at = from_iso(session_row["renewed_at"])
    now = now_berlin()
    if (now - renewed_at) < timedelta(hours=settings.SESSION_RENEW_IF_OLDER_THAN_HOURS):
        return None
    hard = from_iso(session_row["hard_expires_at"])
    new_expires = min(now + timedelta(days=settings.SESSION_SOFT_CAP_DAYS), hard)
    await db.execute(
        "UPDATE sessions SET expires_at = ?, renewed_at = ? WHERE id = ?",
        (to_iso(new_expires), to_iso(now), session_row["session_id"]),
    )
    await db.commit()
    return to_iso(new_expires)


async def touch_last_seen(
    db: aiosqlite.Connection, settings: Settings, session_id: int, last_seen_iso: str
) -> None:
    """Debounced last_seen update — avoids a write on every request."""
    if (now_berlin() - from_iso(last_seen_iso)) < timedelta(
        minutes=settings.SESSION_LAST_SEEN_DEBOUNCE_MIN
    ):
        return
    await db.execute(
        "UPDATE sessions SET last_seen_at = ? WHERE id = ?", (to_iso(now_berlin()), session_id)
    )
    await db.commit()


async def logout(db: aiosqlite.Connection, settings: Settings, raw_token: str) -> None:
    await db.execute(
        "UPDATE sessions SET revoked_at = ? WHERE session_hash = ?",
        (to_iso(now_berlin()), hash_token(raw_token, settings)),
    )
    await db.commit()


async def revoke_user_sessions(db: aiosqlite.Connection, user_id: int) -> int:
    cur = await db.execute(
        "UPDATE sessions SET revoked_at = ? WHERE user_id = ? AND revoked_at IS NULL",
        (to_iso(now_berlin()), user_id),
    )
    await db.commit()
    return cur.rowcount


# --- Invites & admin bootstrap (used by routes + CLI) ---


async def create_invite(
    db: aiosqlite.Connection,
    settings: Settings,
    created_by_user_id: int | None,
    email_hint: str | None = None,
) -> str:
    raw = new_url_token()
    now = now_berlin()
    expires = now + timedelta(days=settings.INVITE_TOKEN_TTL_DAYS)
    await db.execute(
        "INSERT INTO invite_tokens "
        "(token_hash, email_hint, created_by_user_id, created_at, expires_at) "
        "VALUES (?, ?, ?, ?, ?)",
        (hash_token(raw, settings), email_hint, created_by_user_id, to_iso(now), to_iso(expires)),
    )
    await db.commit()
    return raw


async def bootstrap_admin(
    db: aiosqlite.Connection, settings: Settings, email: str, force: bool = False
) -> tuple[int, str]:
    """Create or promote the first admin. Returns (user_id, plaintext login token).

    The whole check-then-write runs under ``BEGIN IMMEDIATE`` so two concurrent
    bootstrap runs can't both pass the "no admin yet" guard and create two admins.
    """
    email = normalize_email(email)
    await db.execute("BEGIN IMMEDIATE")
    try:
        async with db.execute("SELECT COUNT(*) AS n FROM users WHERE is_admin = 1") as cur:
            admin_count = (await cur.fetchone())["n"]
        user = await get_user_by_email(db, email)
        already_admin = user is not None and bool(user["is_admin"])
        if admin_count > 0 and not already_admin and not force:
            raise ConflictError("An admin already exists. Pass force=True to add another.")

        now = now_berlin()
        if user is None:
            cursor = await db.execute(
                "INSERT INTO users (email, is_admin, created_at) VALUES (?, 1, ?)",
                (email, to_iso(now)),
            )
            user_id = cursor.lastrowid
        else:
            user_id = user["id"]
            await db.execute(
                "UPDATE users SET is_admin = 1, status = 'active' WHERE id = ?", (user_id,)
            )
        raw = await _issue_login_token(db, settings, user_id, email)
        await db.execute("COMMIT")
        return user_id, raw
    except BaseException:
        await db.execute("ROLLBACK")
        raise
