"""Magic-link auth, sessions (sliding + hard-cap), invites, admin bootstrap.

Token security: only keyed hashes are stored in the DB; the plaintext token
lives only in the email link / session cookie. Single-use consumption is
race-safe via a conditional ``UPDATE ... WHERE used_at IS NULL`` + rowcount check.
"""

from __future__ import annotations

import contextlib
import secrets
import sqlite3
from datetime import timedelta

import aiosqlite

from .config import Settings
from .errors import (
    AppError,
    ConflictError,
    ForbiddenError,
    TokenExpiredError,
    TokenInvalidError,
    TokenUsedError,
)
from .models import SessionUser
from .security import constant_time_equal, hash_token, new_url_token, normalize_email
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


def _generate_code() -> str:
    """A zero-padded 6-digit numeric login code (F-AUTH-25)."""
    return f"{secrets.randbelow(1_000_000):06d}"


async def _issue_login_token(
    db: aiosqlite.Connection, settings: Settings, user_id: int, email: str
) -> tuple[str, str]:
    """Insert a fresh login token + 6-digit code (both hashed; no commit). Returns (raw, code)."""
    raw = new_url_token()
    code = _generate_code()
    now = now_berlin()
    expires = now + timedelta(minutes=settings.LOGIN_TOKEN_TTL_MIN)
    await db.execute(
        "INSERT INTO login_tokens (token_hash, code_hash, email, user_id, created_at, expires_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (
            hash_token(raw, settings),
            hash_token(code, settings),
            normalize_email(email),
            user_id,
            to_iso(now),
            to_iso(expires),
        ),
    )
    return raw, code


# --- Magic-link request ---


async def request_login_link(
    db: aiosqlite.Connection, settings: Settings, email: str
) -> tuple[str, str] | None:
    """Create a login token + 6-digit code for an active user. Returns (raw_token, code) or None.

    None for unknown/disabled users lets the route give a generic
    (enumeration-resistant) response.
    """
    user = await get_user_by_email(db, email)
    if user is None or user["status"] != "active":
        return None
    # invalidate older open tokens so only the newest code is valid (F-AUTH-19)
    await db.execute(
        "UPDATE login_tokens SET used_at = ? WHERE email = ? AND used_at IS NULL",
        (to_iso(now_berlin()), normalize_email(email)),
    )
    raw, code = await _issue_login_token(db, settings, user["id"], email)
    await db.commit()
    return raw, code


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


async def peek_login_token(db: aiosqlite.Connection, settings: Settings, raw_token: str) -> str:
    """Validate a login token WITHOUT consuming it; return the target email, masked.

    Backs the N1 interstitial: the magic-link GET must show "sign in as a***@x" and set
    no cookie, so the cookie-setting step can be a deliberate same-origin POST. Raises the
    same errors as ``verify_login`` for invalid/expired/used links / disabled users.
    """
    token_hash = hash_token(raw_token, settings)
    async with db.execute("SELECT * FROM login_tokens WHERE token_hash = ?", (token_hash,)) as cur:
        tok = await cur.fetchone()
    if tok is None:
        raise TokenInvalidError("Invalid sign-in link.")
    if tok["used_at"] is not None:
        raise TokenUsedError("This sign-in link has already been used.")
    if from_iso(tok["expires_at"]) <= now_berlin():
        raise TokenExpiredError("This sign-in link has expired.")
    user = await get_user_by_id(db, tok["user_id"])
    if user is None:
        raise TokenInvalidError("user_not_found", code="user_not_found", status_code=404)
    if user["status"] != "active":
        raise ForbiddenError("This account is disabled.", code="user_disabled")
    return _mask_email(user["email"])


# --- Registration with invite ---


async def register_with_invite(
    db: aiosqlite.Connection, settings: Settings, invite_raw: str, email: str
) -> tuple[str, str]:
    """Validate a multi-use invite, create the user, record the redemption (F-AUTH-16/17).

    Returns (raw_login_token, code). ``used_at`` is set once the link is exhausted
    (``used_count == max_uses``) — backward-compatible with the M1 single-use semantics.
    """
    email = normalize_email(email)
    invite_hash = hash_token(invite_raw, settings)
    now_iso = to_iso(now_berlin())
    async with db.execute(
        "SELECT * FROM invite_tokens WHERE token_hash = ?", (invite_hash,)
    ) as cur:
        inv = await cur.fetchone()

    if inv is None:
        raise TokenInvalidError("Invalid invite.", code="invalid_invite")
    if inv["revoked_at"] is not None:
        raise ConflictError("This invite was revoked.", code="invite_revoked")
    if from_iso(inv["expires_at"]) <= now_berlin():
        raise TokenExpiredError("This invite has expired.", code="invite_expired")
    if inv["used_count"] >= inv["max_uses"]:
        raise ConflictError("This invite is used up.", code="invite_exhausted")
    if await get_user_by_email(db, email) is not None:
        raise ConflictError(
            "This email already has an account. Sign in instead.", code="user_exists"
        )

    try:
        cursor = await db.execute(
            "INSERT INTO users (email, is_admin, created_at) VALUES (?, 0, ?)",
            (email, now_iso),
        )
    except sqlite3.IntegrityError as exc:
        await db.rollback()
        raise ConflictError(
            "This email already has an account. Sign in instead.", code="user_exists"
        ) from exc
    user_id = cursor.lastrowid

    # Atomic consume: only succeeds while a seat is free (race-safe via rowcount).
    consumed = await db.execute(
        "UPDATE invite_tokens SET used_count = used_count + 1, "
        "used_at = CASE WHEN used_count + 1 >= max_uses THEN ? ELSE used_at END, "
        "used_by_user_id = ? "
        "WHERE id = ? AND revoked_at IS NULL AND expires_at > ? AND used_count < max_uses",
        (now_iso, user_id, inv["id"], now_iso),
    )
    if consumed.rowcount != 1:
        await db.rollback()  # lost the last-seat race
        raise ConflictError("This invite is used up.", code="invite_exhausted")
    await db.execute(
        "INSERT INTO invite_redemptions (invite_id, user_id, redeemed_at) VALUES (?, ?, ?)",
        (inv["id"], user_id, now_iso),
    )
    raw, code = await _issue_login_token(db, settings, user_id, email)
    await db.commit()
    return raw, code


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
    max_uses: int = 1,
    expires_in_days: int | None = None,
) -> str:
    """Create an invite (admin/CLI path, no quota check). max_uses=1 = M1 single-use."""
    raw = new_url_token()
    now = now_berlin()
    ttl = expires_in_days if expires_in_days is not None else settings.INVITE_TOKEN_TTL_DAYS
    expires = now + timedelta(days=ttl)
    await db.execute(
        "INSERT INTO invite_tokens (token_hash, email_hint, created_by_user_id, created_at, "
        "expires_at, max_uses, used_count) VALUES (?, ?, ?, ?, ?, ?, 0)",
        (
            hash_token(raw, settings),
            email_hint,
            created_by_user_id,
            to_iso(now),
            to_iso(expires),
            max_uses,
        ),
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
        raw, _code = await _issue_login_token(db, settings, user_id, email)
        await db.execute("COMMIT")
        return user_id, raw
    except BaseException:
        await db.execute("ROLLBACK")
        raise


# --- v3: 6-digit login-code verify (F-AUTH-21..25) ---


async def verify_login_code(
    db: aiosqlite.Connection, settings: Settings, email: str, code: str
) -> tuple[str, SessionUser]:
    """Verify a 6-digit code and open a session. Generic failures (no enumeration).

    The read/attempt-count/consume sequence is serialized with ``BEGIN IMMEDIATE``.
    Without that write lock, parallel wrong-code requests can all read the same
    ``attempt_count`` and then write the same incremented value, undercounting guesses.
    """
    email = normalize_email(email)
    now = now_berlin()

    # Apple App Review (Guideline 2.1): reviewers have no inbox access, so ONE designated
    # account may sign in with a FIXED, non-expiring code from the Review Notes. Active only
    # when BOTH config values are set; the account must exist (CLI-provisioned) and be
    # active. Route-level rate limits still apply; a wrong code falls through to the normal
    # token flow (and fails generically), so this path leaks nothing about the account.
    if (
        settings.REVIEW_ACCOUNT_EMAIL
        and settings.REVIEW_LOGIN_CODE
        and email == normalize_email(settings.REVIEW_ACCOUNT_EMAIL)
        and constant_time_equal(
            hash_token(code, settings), hash_token(settings.REVIEW_LOGIN_CODE, settings)
        )
    ):
        user = await get_user_by_email(db, email)
        if user is not None and user["status"] == "active":
            raw_session = await _insert_session(db, settings, user["id"])
            await db.execute(
                "UPDATE users SET last_login_at = ? WHERE id = ?", (to_iso(now), user["id"])
            )
            await db.commit()
            return raw_session, SessionUser(
                id=user["id"], email=user["email"], is_admin=bool(user["is_admin"])
            )

    code_hash = hash_token(code, settings)
    await db.execute("BEGIN IMMEDIATE")
    try:
        async with db.execute(
            "SELECT * FROM login_tokens "
            "WHERE email = ? AND used_at IS NULL AND code_hash IS NOT NULL "
            "ORDER BY created_at DESC LIMIT 1",
            (email,),
        ) as cur:
            tok = await cur.fetchone()
        if tok is None:
            raise TokenInvalidError("Invalid code.", code="invalid_code")
        if tok["attempt_count"] >= settings.LOGIN_CODE_MAX_ATTEMPTS:
            # Code path is locked, but do NOT burn the row: it also carries the magic-link hash,
            # so burning it would let anyone who knows the email DoS the victim's pending login by
            # spamming wrong codes (N3). The 256-bit link isn't guessable, so it stays valid; only
            # the 6-digit code is refused. A fresh login request supersedes this row anyway.
            raise AppError(
                "Too many attempts. Request a new code.", code="code_locked", status_code=423
            )
        if from_iso(tok["created_at"]) + timedelta(minutes=settings.LOGIN_CODE_TTL_MIN) <= now:
            raise TokenExpiredError("This code has expired.", code="code_expired")
        if not constant_time_equal(code_hash, tok["code_hash"]):
            new_count = tok["attempt_count"] + 1
            bumped = await db.execute(
                "UPDATE login_tokens SET attempt_count = attempt_count + 1 "
                "WHERE id = ? AND used_at IS NULL AND attempt_count < ?",
                (tok["id"], settings.LOGIN_CODE_MAX_ATTEMPTS),
            )
            if bumped.rowcount != 1:
                raise AppError(
                    "Too many attempts. Request a new code.",
                    code="code_locked",
                    status_code=423,
                )
            await db.execute("COMMIT")
            if new_count >= settings.LOGIN_CODE_MAX_ATTEMPTS:
                raise AppError(
                    "Too many attempts. Request a new code.",
                    code="code_locked",
                    status_code=423,
                )
            raise TokenInvalidError("Invalid code.", code="invalid_code")

        user = await get_user_by_id(db, tok["user_id"])
        if user is None:
            raise TokenInvalidError("Invalid code.", code="invalid_code")
        if user["status"] != "active":
            raise ForbiddenError("This account is disabled.", code="user_disabled")
        consumed = await db.execute(
            "UPDATE login_tokens SET used_at = ? "
            "WHERE id = ? AND used_at IS NULL AND expires_at > ? AND attempt_count < ?",
            (to_iso(now), tok["id"], to_iso(now), settings.LOGIN_CODE_MAX_ATTEMPTS),
        )
        if consumed.rowcount != 1:
            raise TokenInvalidError("Invalid code.", code="invalid_code")
        raw_session = await _insert_session(db, settings, user["id"])
        await db.execute(
            "UPDATE users SET last_login_at = ? WHERE id = ?", (to_iso(now), user["id"])
        )
        await db.execute("COMMIT")
        return raw_session, SessionUser(
            id=user["id"], email=user["email"], is_admin=bool(user["is_admin"])
        )
    except BaseException:
        with contextlib.suppress(Exception):
            await db.execute("ROLLBACK")
        raise


# --- v3: User invites with quota (F-AUTH-13..18) ---


async def _consumed_quota(db: aiosqlite.Connection, user_id: int) -> int:
    """Sum of max_uses of the user's open (not revoked, not expired) invites (F-AUTH-14)."""
    async with db.execute(
        "SELECT COALESCE(SUM(max_uses), 0) AS s FROM invite_tokens "
        "WHERE created_by_user_id = ? AND revoked_at IS NULL AND expires_at > ?",
        (user_id, to_iso(now_berlin())),
    ) as cur:
        return (await cur.fetchone())["s"]


async def create_user_invite(
    db: aiosqlite.Connection,
    settings: Settings,
    user_id: int,
    max_uses: int,
    expires_in_days: int | None = None,
) -> tuple[str, int]:
    """User invite with quota enforcement. Returns (raw_token, remaining_quota). Admins exempt.

    Quota check + insert run under ``BEGIN IMMEDIATE`` so two parallel requests cannot both
    pass the check and over-commit the quota (no TOCTOU race).
    """
    await db.execute("BEGIN IMMEDIATE")
    try:
        async with db.execute(
            "SELECT invite_quota, is_admin FROM users WHERE id = ?", (user_id,)
        ) as cur:
            urow = await cur.fetchone()
        quota, is_admin = urow["invite_quota"], bool(urow["is_admin"])
        if not is_admin and await _consumed_quota(db, user_id) + max_uses > quota:
            await db.execute("ROLLBACK")
            raise ForbiddenError(
                "Du hast dein Einladungs-Kontingent erreicht.", code="invite_quota_exceeded"
            )
        raw = new_url_token()
        now = now_berlin()
        ttl = expires_in_days if expires_in_days is not None else settings.INVITE_TOKEN_TTL_DAYS
        await db.execute(
            "INSERT INTO invite_tokens (token_hash, created_by_user_id, created_at, expires_at, "
            "max_uses, used_count) VALUES (?, ?, ?, ?, ?, 0)",
            (
                hash_token(raw, settings),
                user_id,
                to_iso(now),
                to_iso(now + timedelta(days=ttl)),
                max_uses,
            ),
        )
        consumed = await _consumed_quota(db, user_id)  # within the tx, includes the new invite
        await db.execute("COMMIT")
    except BaseException:
        with contextlib.suppress(Exception):
            await db.execute("ROLLBACK")
        raise
    remaining = quota if is_admin else max(0, quota - consumed)
    return raw, remaining


async def list_user_invites(db: aiosqlite.Connection, user_id: int) -> list[dict]:
    """The user's own invites with a derived status (F-AUTH-18). No plaintext tokens."""
    now = now_berlin()
    async with db.execute(
        "SELECT id, max_uses, used_count, expires_at, revoked_at, created_at "
        "FROM invite_tokens WHERE created_by_user_id = ? ORDER BY id DESC",
        (user_id,),
    ) as cur:
        rows = await cur.fetchall()
    out = []
    for r in rows:
        if r["revoked_at"] is not None:
            status = "revoked"
        elif from_iso(r["expires_at"]) <= now:
            status = "expired"
        elif r["used_count"] >= r["max_uses"]:
            status = "exhausted"
        else:
            status = "active"
        out.append(
            {
                "id": r["id"],
                "max_uses": r["max_uses"],
                "used_count": r["used_count"],
                "expires_at": r["expires_at"],
                "revoked_at": r["revoked_at"],
                "created_at": r["created_at"],
                "status": status,
            }
        )
    return out


async def revoke_invite(db: aiosqlite.Connection, user_id: int, invite_id: int) -> bool:
    """Revoke the caller's own invite. False if not found/not owned (route -> 404, no leak)."""
    cur = await db.execute(
        "UPDATE invite_tokens SET revoked_at = ? "
        "WHERE id = ? AND created_by_user_id = ? AND revoked_at IS NULL",
        (to_iso(now_berlin()), invite_id, user_id),
    )
    await db.commit()
    return cur.rowcount > 0


async def set_invite_quota(db: aiosqlite.Connection, email: str, quota: int) -> bool:
    """Admin CLI: set a user's invite quota. False if no such user."""
    cur = await db.execute(
        "UPDATE users SET invite_quota = ? WHERE email = ? COLLATE NOCASE",
        (quota, normalize_email(email)),
    )
    await db.commit()
    return cur.rowcount > 0


# --- v3: Email change (F-AUTH-28..32) ---


def _mask_email(email: str) -> str:
    local, _, domain = email.partition("@")
    return f"{local[0] if local else '?'}***@{domain}"


async def create_email_change(
    db: aiosqlite.Connection, settings: Settings, user_id: int, new_email: str
) -> tuple[str, str, str] | None:
    """Start an email change. Returns (raw_token, code, masked_old_email), or None.

    None means the target address already belongs to someone else: the caller must then
    behave exactly as on success (no error, no mail) so the endpoint can't be used as a
    membership oracle for this invite-only app (N2). Requesting your *own* current address
    still errors — that reveals nothing the caller doesn't already know.
    """
    new_email = normalize_email(new_email)
    user = await get_user_by_id(db, user_id)
    if user is None:
        raise TokenInvalidError("Unknown user.", code="invalid_token")
    if normalize_email(user["email"]) == new_email:
        raise ConflictError("That is already your email.", code="email_taken")
    if await get_user_by_email(db, new_email) is not None:
        return None  # taken by another account → silent no-op, identical response (N2)
    now = now_berlin()
    await db.execute(  # invalidate the user's prior open requests
        "UPDATE email_change_requests SET used_at = ? WHERE user_id = ? AND used_at IS NULL",
        (to_iso(now), user_id),
    )
    raw, code = new_url_token(), _generate_code()
    await db.execute(
        "INSERT INTO email_change_requests "
        "(user_id, new_email, token_hash, code_hash, expires_at, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (
            user_id,
            new_email,
            hash_token(raw, settings),
            hash_token(code, settings),
            to_iso(now + timedelta(minutes=settings.EMAIL_CHANGE_TTL_MIN)),
            to_iso(now),
        ),
    )
    await db.commit()
    return raw, code, _mask_email(user["email"])


async def peek_email_change_token(
    db: aiosqlite.Connection, settings: Settings, raw_token: str
) -> str:
    """Validate an email-change token without consuming it; return the masked target email."""
    now = now_berlin()
    async with db.execute(
        "SELECT * FROM email_change_requests WHERE token_hash = ?",
        (hash_token(raw_token, settings),),
    ) as cur:
        row = await cur.fetchone()
    if row is None or row["used_at"] is not None:
        raise TokenInvalidError("Invalid request.", code="invalid_token")
    if from_iso(row["expires_at"]) <= now:
        raise TokenExpiredError("This request has expired.", code="change_expired")
    return _mask_email(row["new_email"])


async def _apply_email_change(db: aiosqlite.Connection, row: aiosqlite.Row, now) -> str:
    """Consume the request + swap the user's email; invalidate old-address login tokens."""
    consumed = await db.execute(
        "UPDATE email_change_requests SET used_at = ? WHERE id = ? AND used_at IS NULL",
        (to_iso(now), row["id"]),
    )
    if consumed.rowcount != 1:
        await db.rollback()
        raise TokenInvalidError("Invalid request.", code="invalid_code")
    try:
        await db.execute(
            "UPDATE users SET email = ? WHERE id = ?", (row["new_email"], row["user_id"])
        )
    except sqlite3.IntegrityError as exc:  # address taken between request and confirm
        await db.rollback()
        raise ConflictError("This email is taken.", code="email_taken") from exc
    await db.execute(  # old-address magic links/codes die (F-AUTH-31)
        "UPDATE login_tokens SET used_at = ? WHERE user_id = ? AND used_at IS NULL",
        (to_iso(now), row["user_id"]),
    )
    await db.commit()
    return row["new_email"]


async def confirm_email_change_by_token(
    db: aiosqlite.Connection, settings: Settings, raw_token: str
) -> str:
    """Confirm via the emailed link (mailbox possession = proof). Returns the new email."""
    now = now_berlin()
    async with db.execute(
        "SELECT * FROM email_change_requests WHERE token_hash = ?",
        (hash_token(raw_token, settings),),
    ) as cur:
        row = await cur.fetchone()
    if row is None or row["used_at"] is not None:
        raise TokenInvalidError("Invalid request.", code="invalid_token")
    if from_iso(row["expires_at"]) <= now:
        raise TokenExpiredError("This request has expired.", code="change_expired")
    return await _apply_email_change(db, row, now)


async def confirm_email_change_by_code(
    db: aiosqlite.Connection, settings: Settings, user_id: int, code: str
) -> str:
    """Confirm via the 6-digit code (logged-in user). Returns the new email."""
    now = now_berlin()
    code_hash = hash_token(code, settings)
    await db.execute("BEGIN IMMEDIATE")
    try:
        async with db.execute(
            "SELECT * FROM email_change_requests WHERE user_id = ? AND used_at IS NULL "
            "ORDER BY created_at DESC LIMIT 1",
            (user_id,),
        ) as cur:
            row = await cur.fetchone()
        if row is None:
            raise TokenInvalidError("Invalid request.", code="invalid_code")
        if row["attempt_count"] >= settings.EMAIL_CHANGE_MAX_ATTEMPTS:
            raise AppError("Too many attempts.", code="code_locked", status_code=423)
        if from_iso(row["expires_at"]) <= now:
            raise TokenExpiredError("This request has expired.", code="change_expired")
        if not constant_time_equal(code_hash, row["code_hash"]):
            bumped = await db.execute(
                "UPDATE email_change_requests SET attempt_count = attempt_count + 1 "
                "WHERE id = ? AND used_at IS NULL AND attempt_count < ?",
                (row["id"], settings.EMAIL_CHANGE_MAX_ATTEMPTS),
            )
            if bumped.rowcount != 1:
                raise AppError("Too many attempts.", code="code_locked", status_code=423)
            await db.execute("COMMIT")
            raise TokenInvalidError("Invalid code.", code="invalid_code")
        return await _apply_email_change(db, row, now)
    except BaseException:
        with contextlib.suppress(Exception):
            await db.execute("ROLLBACK")
        raise
