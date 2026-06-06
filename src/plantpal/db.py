"""SQLite connection lifecycle, PRAGMAs, and a numbered-migration runner."""

from __future__ import annotations

from pathlib import Path

import aiosqlite

from .config import Settings
from .time_utils import now_berlin, to_iso


def _default_migrations_dir() -> Path:
    """Repo layout puts migrations next to src/. When the package is pip-installed
    (Docker), that relative path is gone, so fall back to ``<cwd>/migrations``."""
    repo_relative = Path(__file__).resolve().parent.parent.parent / "migrations"
    return repo_relative if repo_relative.is_dir() else Path.cwd() / "migrations"


MIGRATIONS_DIR = _default_migrations_dir()

_PRAGMAS = (
    "PRAGMA foreign_keys = ON;",
    "PRAGMA journal_mode = WAL;",
    "PRAGMA busy_timeout = 5000;",
    "PRAGMA synchronous = NORMAL;",
)


async def connect(settings: Settings) -> aiosqlite.Connection:
    """Open a connection with PRAGMAs applied and Row factory set."""
    Path(settings.DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    conn = await aiosqlite.connect(settings.DB_PATH)
    conn.row_factory = aiosqlite.Row
    for pragma in _PRAGMAS:
        await conn.execute(pragma)
    await conn.commit()
    return conn


async def _ensure_migrations_table(db: aiosqlite.Connection) -> None:
    await db.execute(
        "CREATE TABLE IF NOT EXISTS _migrations ("
        "  filename TEXT PRIMARY KEY,"
        "  applied_at TEXT NOT NULL"
        ")"
    )
    await db.commit()


async def applied_migrations(db: aiosqlite.Connection) -> set[str]:
    await _ensure_migrations_table(db)
    async with db.execute("SELECT filename FROM _migrations") as cur:
        rows = await cur.fetchall()
    return {row["filename"] for row in rows}


def _split_statements(sql: str) -> list[str]:
    """Split a migration script into statements — quote- and comment-aware.

    Handles single/double-quoted string literals (incl. ``''``/``""`` escapes), ``--`` line
    comments and ``/* */`` block comments, so a ``;`` or ``--`` inside a literal no longer
    corrupts the split (C3). No trigger/``BEGIN..END`` support — our schema has none.
    """
    statements: list[str] = []
    buf: list[str] = []
    quote: str | None = None
    i, n = 0, len(sql)
    while i < n:
        ch = sql[i]
        nxt = sql[i + 1] if i + 1 < n else ""
        if quote is not None:  # inside a string literal
            buf.append(ch)
            if ch == quote:
                if nxt == quote:  # doubled quote = escaped quote, stays inside
                    buf.append(nxt)
                    i += 2
                    continue
                quote = None
            i += 1
        elif ch in ("'", '"'):  # string opens
            quote = ch
            buf.append(ch)
            i += 1
        elif ch == "-" and nxt == "-":  # line comment → skip to end of line
            j = sql.find("\n", i)
            i = n if j == -1 else j
        elif ch == "/" and nxt == "*":  # block comment → skip to */
            j = sql.find("*/", i + 2)
            i = n if j == -1 else j + 2
        elif ch == ";":  # statement boundary
            stmt = "".join(buf).strip()
            if stmt:
                statements.append(stmt)
            buf = []
            i += 1
        else:
            buf.append(ch)
            i += 1
    tail = "".join(buf).strip()
    if tail:
        statements.append(tail)
    return statements


async def run_migrations(db: aiosqlite.Connection, migrations_dir: Path | None = None) -> list[str]:
    """Apply not-yet-applied numbered ``*.sql`` files atomically. Idempotent.

    Per migration, every statement plus the ``_migrations`` marker is executed in
    the implicit transaction and committed once at the end — so a crash mid-migration
    rolls back fully, never leaving a partial schema without its marker. Run migrations
    from a single worker on startup (documented in README) to avoid a concurrent race.
    """
    directory = migrations_dir or MIGRATIONS_DIR
    done = await applied_migrations(db)
    newly: list[str] = []
    for path in sorted(directory.glob("*.sql")):
        if path.name in done:
            continue
        try:
            for statement in _split_statements(path.read_text(encoding="utf-8")):
                await db.execute(statement)
            await db.execute(
                "INSERT INTO _migrations (filename, applied_at) VALUES (?, ?)",
                (path.name, to_iso(now_berlin())),
            )
            await db.commit()  # atomic: all DDL + marker, or nothing
            newly.append(path.name)
        except Exception:
            await db.rollback()
            raise
    return newly


async def init_db(settings: Settings, migrations_dir: Path | None = None) -> aiosqlite.Connection:
    """Connect and bring schema up to date. Safe to call repeatedly."""
    conn = await connect(settings)
    await run_migrations(conn, migrations_dir)
    return conn
