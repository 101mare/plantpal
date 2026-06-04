"""AK-LOC-*: location/room + grouping (B.3)."""

from plantpal import plant_service as ps
from plantpal.models import PlantCreate, PlantUpdate
from plantpal.time_utils import now_berlin, to_iso


async def _user(db, email="a@b.c"):
    cur = await db.execute(
        "INSERT INTO users (email, created_at) VALUES (?, ?)", (email, to_iso(now_berlin()))
    )
    await db.commit()
    return cur.lastrowid


async def test_location_crud(db):
    uid = await _user(db)
    pid = await ps.create_plant(
        db, uid, PlantCreate(name="M", interval_days=7, location_room="Küche")
    )
    assert (await ps.get_plant(db, uid, pid))["location_room"] == "Küche"
    await ps.update_plant(db, uid, pid, PlantUpdate(location_room="Bad"))
    assert (await ps.get_plant(db, uid, pid))["location_room"] == "Bad"
    await ps.update_plant(db, uid, pid, PlantUpdate(location_room="   "))  # F-LOC-6 trim -> null
    assert (await ps.get_plant(db, uid, pid))["location_room"] is None


async def test_group_by_room(db):
    uid = await _user(db)
    await ps.create_plant(
        db, uid, PlantCreate(name="A", interval_days=7, location_room="Wohnzimmer")
    )
    await ps.create_plant(db, uid, PlantCreate(name="B", interval_days=7, location_room="Bad"))
    await ps.create_plant(db, uid, PlantCreate(name="C", interval_days=7))  # no room
    groups = ps.build_groups(await ps.list_plants(db, uid))
    assert [g.location_room for g in groups] == ["Bad", "Wohnzimmer", None]  # alpha, None last


async def test_room_stats(db):
    uid = await _user(db)
    await ps.create_plant(db, uid, PlantCreate(name="A", interval_days=7, location_room="Bad"))
    await ps.create_plant(db, uid, PlantCreate(name="B", interval_days=7))
    s = await ps.compute_stats(db, uid, by_room=True)
    assert s.rooms is not None
    rooms = {r.location_room: r.total_plants for r in s.rooms}
    assert rooms == {"Bad": 1, None: 1}
