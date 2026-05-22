from datetime import date

from plantpal import plant_service as ps
from plantpal.models import PlantCreate, PlantUpdate
from plantpal.time_utils import now_berlin, to_iso


async def _make_user(db, email):
    cur = await db.execute(
        "INSERT INTO users (email, created_at) VALUES (?, ?)", (email, to_iso(now_berlin()))
    )
    await db.commit()
    return cur.lastrowid


# --- thirsty mechanic (PRD F-THIRST) ---


def test_thirsty_state_core():
    today = date(2026, 5, 21)
    assert ps.thirsty_state("2026-05-21T08:00:00", 7, today) == (False, 0)  # watered today
    assert ps.thirsty_state("2026-05-18T08:00:00", 7, today) == (False, 0)  # 3 days ago
    assert ps.thirsty_state("2026-05-14T08:00:00", 7, today) == (True, 0)  # due exactly today
    assert ps.thirsty_state("2026-05-11T08:00:00", 7, today) == (True, 3)  # 3 days overdue


# --- CRUD + scope ---


async def test_create_and_get(db):
    uid = await _make_user(db, "a@b.c")
    pid = await ps.create_plant(db, uid, PlantCreate(name="Monstera", interval_days=7))
    row = await ps.get_plant(db, uid, pid)
    assert row["name"] == "Monstera"
    assert row["image_path"] is None  # set later by image upload


async def test_user_scope_isolation(db):
    a = await _make_user(db, "a@b.c")
    b = await _make_user(db, "b@b.c")
    pid = await ps.create_plant(db, a, PlantCreate(name="Fern", interval_days=5))
    assert await ps.get_plant(db, b, pid) is None  # B cannot see A's plant
    assert await ps.get_plant(db, a, pid) is not None


async def test_update_plant(db):
    uid = await _make_user(db, "a@b.c")
    pid = await ps.create_plant(db, uid, PlantCreate(name="Aloe", interval_days=10))
    row = await ps.update_plant(db, uid, pid, PlantUpdate(name="Aloe Vera", notes="sunny"))
    assert row["name"] == "Aloe Vera"
    assert row["notes"] == "sunny"
    assert row["interval_days"] == 10  # unchanged


async def test_update_foreign_plant_returns_none(db):
    a = await _make_user(db, "a@b.c")
    b = await _make_user(db, "b@b.c")
    pid = await ps.create_plant(db, a, PlantCreate(name="X", interval_days=3))
    assert await ps.update_plant(db, b, pid, PlantUpdate(name="hijack")) is None


async def test_water_resets_thirsty(db):
    uid = await _make_user(db, "a@b.c")
    pid = await ps.create_plant(db, uid, PlantCreate(name="Calathea", interval_days=3))
    # backdate so it is thirsty
    await db.execute(
        "UPDATE plants SET last_watered_at = ? WHERE id = ?", ("2026-01-01T08:00:00", pid)
    )
    await db.commit()
    row = await ps.get_plant(db, uid, pid)
    assert ps.thirsty_state(row["last_watered_at"], row["interval_days"])[0] is True
    watered = await ps.water_plant(db, uid, pid)
    assert ps.thirsty_state(watered["last_watered_at"], watered["interval_days"])[0] is False


async def test_soft_delete_hides_plant(db):
    uid = await _make_user(db, "a@b.c")
    pid = await ps.create_plant(db, uid, PlantCreate(name="Ficus", interval_days=7))
    assert await ps.soft_delete_plant(db, uid, pid) is True
    assert await ps.get_plant(db, uid, pid) is None
    assert await ps.list_plants(db, uid) == []


async def test_list_sorts_thirsty_first(db):
    uid = await _make_user(db, "a@b.c")
    fresh = await ps.create_plant(db, uid, PlantCreate(name="Zed", interval_days=7))
    thirsty = await ps.create_plant(db, uid, PlantCreate(name="Aloe", interval_days=2))
    await db.execute(
        "UPDATE plants SET last_watered_at = ? WHERE id = ?", ("2026-01-01T08:00:00", thirsty)
    )
    await db.commit()
    rows = await ps.list_plants(db, uid)
    assert rows[0]["id"] == thirsty  # most overdue first despite alphabetical Z<A
    assert rows[1]["id"] == fresh


async def test_stats(db):
    uid = await _make_user(db, "a@b.c")
    await ps.create_plant(db, uid, PlantCreate(name="A", interval_days=7))
    t = await ps.create_plant(db, uid, PlantCreate(name="B", interval_days=2))
    await db.execute("UPDATE plants SET last_watered_at = ? WHERE id = ?", ("2026-01-01", t))
    await db.commit()
    total, thirsty = await ps.stats(db, uid)
    assert total == 2
    assert thirsty == 1


async def test_delete_account_cascades(db):
    uid = await _make_user(db, "a@b.c")
    await ps.create_plant(db, uid, PlantCreate(name="A", interval_days=7))
    await ps.delete_account(db, uid)
    async with db.execute("SELECT COUNT(*) AS n FROM plants WHERE user_id = ?", (uid,)) as cur:
        assert (await cur.fetchone())["n"] == 0
    async with db.execute("SELECT COUNT(*) AS n FROM users WHERE id = ?", (uid,)) as cur:
        assert (await cur.fetchone())["n"] == 0


async def test_to_response_image_url(db):
    uid = await _make_user(db, "a@b.c")
    pid = await ps.create_plant(db, uid, PlantCreate(name="A", interval_days=7))
    row = await ps.get_plant(db, uid, pid)
    assert ps.to_response(row).image_url is None  # no image yet
    await ps.set_image_path(db, uid, pid, f"{uid}/{pid}.png")
    row = await ps.get_plant(db, uid, pid)
    assert ps.to_response(row).image_url == f"/api/plants/{pid}/image"
