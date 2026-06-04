"""AK-M2-*: migration 002_v3.sql schema, defaults, CHECKs, backfill, idempotency."""

import shutil
import sqlite3

import pytest

from plantpal.db import connect, run_migrations
from plantpal.time_utils import now_berlin, to_iso


async def _cols(db, table):
    async with db.execute(f"PRAGMA table_info({table})") as cur:
        return {r["name"] for r in await cur.fetchall()}


async def _tables(db):
    async with db.execute("SELECT name FROM sqlite_master WHERE type='table'") as cur:
        return {r["name"] for r in await cur.fetchall()}


async def test_tracked(db):
    async with db.execute("SELECT filename FROM _migrations") as cur:
        assert "002_v3.sql" in {r["filename"] for r in await cur.fetchall()}


async def test_schema_shape(db):
    assert "location_room" in await _cols(db, "plants")
    assert {"invite_quota", "locale", "reminder_hour", "theme"} <= await _cols(db, "users")
    assert {"max_uses", "used_count"} <= await _cols(db, "invite_tokens")
    assert {"code_hash", "attempt_count"} <= await _cols(db, "login_tokens")
    assert {"code_hash", "attempt_count", "token_hash"} <= await _cols(db, "email_change_requests")
    assert {"waterings", "invite_redemptions", "email_change_requests"} <= await _tables(db)


async def test_user_defaults(db):
    await db.execute(
        "INSERT INTO users (email, created_at) VALUES ('a@b.c', ?)", (to_iso(now_berlin()),)
    )
    await db.commit()
    async with db.execute(
        "SELECT invite_quota, locale, reminder_hour, theme FROM users WHERE email='a@b.c'"
    ) as cur:
        row = await cur.fetchone()
    assert (row["invite_quota"], row["locale"], row["reminder_hour"], row["theme"]) == (
        3,
        "de",
        8,
        "dark",
    )


async def test_checks_enforced(db):
    now = to_iso(now_berlin())
    for col, bad in (("locale", "fr"), ("reminder_hour", 24), ("theme", "blue")):
        with pytest.raises(sqlite3.IntegrityError):
            await db.execute(
                f"INSERT INTO users (email, created_at, {col}) VALUES (?, ?, ?)",
                (f"{col}@b.c", now, bad),
            )
        await db.rollback()


async def test_idempotent(db, migrations_dir):
    assert await run_migrations(db, migrations_dir) == []  # second run is a no-op


async def test_invite_backfill(settings, migrations_dir, tmp_path):
    only001 = tmp_path / "m1"
    only001.mkdir()
    shutil.copy(migrations_dir / "001_initial.sql", only001 / "001_initial.sql")
    conn = await connect(settings)
    try:
        await run_migrations(conn, only001)  # M1 schema only
        now = to_iso(now_berlin())
        await conn.execute("INSERT INTO users (email, created_at) VALUES ('c@b.c', ?)", (now,))
        await conn.execute(
            "INSERT INTO invite_tokens (token_hash, created_by_user_id, created_at, expires_at, "
            "used_at) VALUES ('used',1,?,?,?)",
            (now, now, now),
        )
        await conn.execute(
            "INSERT INTO invite_tokens (token_hash, created_by_user_id, created_at, expires_at) "
            "VALUES ('unused',1,?,?)",
            (now, now),
        )
        await conn.commit()
        await run_migrations(conn, migrations_dir)  # apply 002 -> backfill
        async with conn.execute(
            "SELECT token_hash, used_count FROM invite_tokens ORDER BY token_hash"
        ) as cur:
            rows = {r["token_hash"]: r["used_count"] for r in await cur.fetchall()}
        assert rows == {"unused": 0, "used": 1}
    finally:
        await conn.close()
