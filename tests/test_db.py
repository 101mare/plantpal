import aiosqlite

from plantpal.db import _split_statements, applied_migrations, init_db, run_migrations


async def test_migrations_create_tables(db: aiosqlite.Connection):
    async with db.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name") as cur:
        names = {row["name"] for row in await cur.fetchall()}
    for expected in {
        "users",
        "invite_tokens",
        "login_tokens",
        "sessions",
        "plants",
        "reminder_send_log",
        "rate_limits",
        "_migrations",
    }:
        assert expected in names


async def test_migrations_are_idempotent(settings, migrations_dir):
    conn = await init_db(settings, migrations_dir)
    # Second run applies nothing new.
    newly = await run_migrations(conn, migrations_dir)
    assert newly == []
    done = await applied_migrations(conn)
    assert "001_initial.sql" in done
    await conn.close()


async def test_foreign_keys_enabled(db: aiosqlite.Connection):
    async with db.execute("PRAGMA foreign_keys") as cur:
        row = await cur.fetchone()
    assert row[0] == 1


async def test_wal_mode(db: aiosqlite.Connection):
    async with db.execute("PRAGMA journal_mode") as cur:
        row = await cur.fetchone()
    assert row[0].lower() == "wal"


def test_split_statements_is_quote_and_comment_aware():
    # C3: a ; or -- inside a string literal must not corrupt the split, and line/block
    # comments are stripped.
    sql = """
    CREATE TABLE t (a TEXT);
    INSERT INTO t VALUES ('semi ; and -- dash stay literal');
    -- a real line comment; ignored
    /* a block; comment -- ignored */
    INSERT INTO t VALUES ('it''s escaped');
    """
    stmts = _split_statements(sql)
    assert stmts == [
        "CREATE TABLE t (a TEXT)",
        "INSERT INTO t VALUES ('semi ; and -- dash stay literal')",
        "INSERT INTO t VALUES ('it''s escaped')",
    ]


async def test_split_statements_executes_tricky_literals(db: aiosqlite.Connection):
    # End-to-end: the split statements run and preserve the literal contents verbatim.
    for stmt in _split_statements(
        "CREATE TABLE q (v TEXT); INSERT INTO q VALUES ('a;b -- c'); INSERT INTO q VALUES ('x''y');"
    ):
        await db.execute(stmt)
    await db.commit()
    async with db.execute("SELECT v FROM q ORDER BY rowid") as cur:
        rows = [r["v"] for r in await cur.fetchall()]
    assert rows == ["a;b -- c", "x'y"]


async def test_fk_cascade_on_user_delete(db: aiosqlite.Connection):
    await db.execute(
        "INSERT INTO users (email, created_at) VALUES (?, ?)", ("a@b.c", "2026-01-01T00:00:00")
    )
    await db.execute(
        "INSERT INTO plants (user_id, name, interval_days, last_watered_at, created_at) "
        "VALUES (1, 'Fern', 7, '2026-01-01T00:00:00', '2026-01-01T00:00:00')"
    )
    await db.commit()
    await db.execute("DELETE FROM users WHERE id = 1")
    await db.commit()
    async with db.execute("SELECT COUNT(*) AS n FROM plants") as cur:
        row = await cur.fetchone()
    assert row["n"] == 0
