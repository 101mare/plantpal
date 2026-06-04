"""AK-HIST-*: watering history (B.1)."""

from plantpal import plant_service as ps
from plantpal.models import PlantCreate
from plantpal.time_utils import now_berlin, to_iso


async def _user(db, email="a@b.c"):
    cur = await db.execute(
        "INSERT INTO users (email, created_at) VALUES (?, ?)", (email, to_iso(now_berlin()))
    )
    await db.commit()
    return cur.lastrowid


async def _count(db, pid):
    async with db.execute("SELECT COUNT(*) AS n FROM waterings WHERE plant_id = ?", (pid,)) as cur:
        return (await cur.fetchone())["n"]


async def test_create_backfills_history(db):
    uid = await _user(db)
    pid = await ps.create_plant(db, uid, PlantCreate(name="M", interval_days=7))
    rows = await ps.list_waterings(db, uid, pid)
    assert len(rows) == 1  # F-HIST-3 backfill


async def test_water_writes_history_and_mirrors(db):
    uid = await _user(db)
    pid = await ps.create_plant(db, uid, PlantCreate(name="M", interval_days=7))
    row = await ps.water_plant(db, uid, pid)
    assert await _count(db, pid) == 2  # backfill + this water
    async with db.execute(
        "SELECT MAX(watered_at) AS m FROM waterings WHERE plant_id = ?", (pid,)
    ) as cur:
        assert row["last_watered_at"] == (await cur.fetchone())["m"]  # F-HIST-7 invariant


async def test_history_desc_order(db):
    uid = await _user(db)
    pid = await ps.create_plant(db, uid, PlantCreate(name="M", interval_days=7))
    await ps.water_plant(db, uid, pid)
    times = [r["watered_at"] for r in await ps.list_waterings(db, uid, pid)]
    assert times == sorted(times, reverse=True)


async def test_history_user_scope(db):
    a = await _user(db, "a@b.c")
    b = await _user(db, "b@b.c")
    pid = await ps.create_plant(db, a, PlantCreate(name="M", interval_days=7))
    assert await ps.list_waterings(db, b, pid) is None  # cross-user -> 404


async def test_water_nonexistent_no_orphan_row(db):
    uid = await _user(db)
    assert await ps.water_plant(db, uid, 9999) is None
    async with db.execute("SELECT COUNT(*) AS n FROM waterings") as cur:
        assert (await cur.fetchone())["n"] == 0  # no watering written for a missing plant


async def test_softdelete_keeps_history(db):
    uid = await _user(db)
    pid = await ps.create_plant(db, uid, PlantCreate(name="M", interval_days=7))
    await ps.soft_delete_plant(db, uid, pid)
    assert await ps.list_waterings(db, uid, pid) is None  # endpoint 404
    assert await _count(db, pid) >= 1  # rows survive in DB (undo/export)


async def test_account_delete_cascades_history(db):
    uid = await _user(db)
    pid = await ps.create_plant(db, uid, PlantCreate(name="M", interval_days=7))
    await ps.delete_account(db, uid)
    assert await _count(db, pid) == 0  # FK cascade on user delete
