"""v3: `python -m plantpal.cli backup` writes a consistent SQLite copy (K5)."""

import sqlite3

from plantpal.cli import _backup


def test_backup_copies_db(tmp_path):
    src = str(tmp_path / "src.db")
    conn = sqlite3.connect(src)
    conn.execute("CREATE TABLE t (x INTEGER)")
    conn.execute("INSERT INTO t VALUES (42)")
    conn.commit()
    conn.close()

    out = str(tmp_path / "backup.db")
    assert _backup(out, db_path=src) == 0

    bk = sqlite3.connect(out)
    try:
        assert bk.execute("SELECT x FROM t").fetchone()[0] == 42
    finally:
        bk.close()
