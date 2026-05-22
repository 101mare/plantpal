"""SQLite-backed fixed-window rate limiter.

Survives process restarts (unlike in-memory limiters) — important on a Pi where
the container may restart often. Keyed by IP-hash, user-id, or email.
"""

from __future__ import annotations

import time

import aiosqlite

from .errors import RateLimitError

_UNITS = {"s": 1, "m": 60, "h": 3600}


def parse_rule(rule: str) -> tuple[int, int]:
    """Parse ``"<count>/<n><unit>"`` (e.g. ``"3/h"``, ``"30/m"``) → (limit, window_s)."""
    count_str, _, window_str = rule.partition("/")
    unit = window_str[-1]
    if unit not in _UNITS:
        raise ValueError(f"Bad rate-limit unit in {rule!r}")
    n = int(window_str[:-1]) if len(window_str) > 1 else 1
    return int(count_str), n * _UNITS[unit]


async def check_rate_limit(db: aiosqlite.Connection, key: str, rule: str) -> None:
    """Increment the window counter for ``key``; raise RateLimitError if over limit."""
    limit, window = parse_rule(rule)
    now = int(time.time())
    window_start = (now // window) * window
    expires_at = window_start + window

    await db.execute("DELETE FROM rate_limits WHERE expires_at < ?", (now,))
    await db.execute(
        "INSERT INTO rate_limits (key, window_start, count, expires_at) VALUES (?, ?, 1, ?) "
        "ON CONFLICT(key, window_start) DO UPDATE SET count = count + 1",
        (key, window_start, expires_at),
    )
    async with db.execute(
        "SELECT count FROM rate_limits WHERE key = ? AND window_start = ?", (key, window_start)
    ) as cur:
        row = await cur.fetchone()
    await db.commit()

    if row is not None and row["count"] > limit:
        raise RateLimitError(retry_after=max(1, expires_at - now))


def key_ip(ip_hash: str, scope: str) -> str:
    return f"{scope}:ip:{ip_hash}"


def key_email(email: str, scope: str) -> str:
    return f"{scope}:email:{email}"


def key_user(user_id: int, scope: str) -> str:
    return f"{scope}:user:{user_id}"
