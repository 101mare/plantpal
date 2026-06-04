"""AK-HK-* / AK-V3-AUTH-29: housekeeping cron (B.4)."""

from datetime import timedelta

from plantpal import housekeeping_service as hk
from plantpal import plant_service as ps
from plantpal.models import PlantCreate
from plantpal.time_utils import now_berlin, to_iso, today_berlin


async def _user(db, email="a@b.c"):
    cur = await db.execute(
        "INSERT INTO users (email, created_at) VALUES (?, ?)", (email, to_iso(now_berlin()))
    )
    await db.commit()
    return cur.lastrowid


async def test_login_tokens_cleaned(db, settings):
    now = now_berlin()
    past, future = to_iso(now - timedelta(hours=1)), to_iso(now + timedelta(hours=1))
    await db.execute(
        "INSERT INTO login_tokens (token_hash, email, created_at, expires_at) VALUES ('h1','a@b.c',?,?)",
        (to_iso(now), past),
    )
    await db.execute(
        "INSERT INTO login_tokens (token_hash, email, created_at, expires_at, used_at) "
        "VALUES ('h2','a@b.c',?,?,?)",
        (to_iso(now), future, to_iso(now)),
    )
    await db.execute(
        "INSERT INTO login_tokens (token_hash, email, created_at, expires_at) VALUES ('h3','a@b.c',?,?)",
        (to_iso(now), future),
    )
    await db.commit()
    counts = await hk.run_housekeeping(db, settings)
    assert counts["login_tokens"] == 2  # expired + used; the fresh one stays
    async with db.execute("SELECT COUNT(*) AS n FROM login_tokens") as cur:
        assert (await cur.fetchone())["n"] == 1


async def test_sessions_cleaned(db, settings):
    uid = await _user(db)
    now = now_berlin()
    base = (
        uid,
        to_iso(now),
        to_iso(now + timedelta(days=1)),
        to_iso(now + timedelta(days=2)),
        to_iso(now),
        to_iso(now),
    )
    await db.execute(
        "INSERT INTO sessions (session_hash, user_id, created_at, expires_at, hard_expires_at, "
        "last_seen_at, renewed_at, revoked_at) VALUES ('s1',?,?,?,?,?,?,?)",
        (*base, to_iso(now)),
    )
    await db.execute(
        "INSERT INTO sessions (session_hash, user_id, created_at, expires_at, hard_expires_at, "
        "last_seen_at, renewed_at) VALUES ('s2',?,?,?,?,?,?)",
        base,
    )
    await db.commit()
    counts = await hk.run_housekeeping(db, settings)
    assert counts["sessions"] == 1  # revoked gone, active stays


async def test_invites_cleaned(db, settings):
    uid = await _user(db)
    now = now_berlin()
    await db.execute(
        "INSERT INTO invite_tokens (token_hash, created_by_user_id, created_at, expires_at) "
        "VALUES ('e',?,?,?)",
        (uid, to_iso(now), to_iso(now - timedelta(days=1))),  # expired
    )
    await db.execute(
        "INSERT INTO invite_tokens (token_hash, created_by_user_id, created_at, expires_at, "
        "max_uses, used_count) VALUES ('x',?,?,?,2,2)",  # exhausted
        (uid, to_iso(now), to_iso(now + timedelta(days=10))),
    )
    await db.execute(
        "INSERT INTO invite_tokens (token_hash, created_by_user_id, created_at, expires_at, "
        "max_uses, used_count) VALUES ('a',?,?,?,5,1)",  # active, remaining
        (uid, to_iso(now), to_iso(now + timedelta(days=10))),
    )
    await db.commit()
    counts = await hk.run_housekeeping(db, settings)
    assert counts["invite_tokens"] == 2
    async with db.execute("SELECT token_hash FROM invite_tokens") as cur:
        assert {r["token_hash"] for r in await cur.fetchall()} == {"a"}


async def test_reminder_log_retention(db, settings):
    uid = await _user(db)
    old = (today_berlin() - timedelta(days=settings.HK_REMINDER_LOG_RETENTION_DAYS + 1)).isoformat()
    recent = today_berlin().isoformat()
    for d in (old, recent):
        await db.execute(
            "INSERT INTO reminder_send_log (user_id, reminder_date, channel, status, created_at) "
            "VALUES (?,?,'email','sent',?)",
            (uid, d, to_iso(now_berlin())),
        )
    await db.commit()
    counts = await hk.run_housekeeping(db, settings)
    assert counts["reminder_send_log"] == 1


async def test_preserves_user_data(db, settings):
    uid = await _user(db)
    pid = await ps.create_plant(db, uid, PlantCreate(name="M", interval_days=7))
    await hk.run_housekeeping(db, settings)
    assert await ps.get_plant(db, uid, pid) is not None
    async with db.execute("SELECT COUNT(*) AS n FROM waterings WHERE plant_id=?", (pid,)) as cur:
        assert (await cur.fetchone())["n"] >= 1  # history preserved
