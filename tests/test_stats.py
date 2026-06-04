"""AK-STAT-*: rich stats (B.2). Waterings inserted relative to today for determinism."""

from datetime import timedelta

import pytest
from pydantic import ValidationError

from plantpal import plant_service as ps
from plantpal.models import PlantCreate
from plantpal.time_utils import now_berlin, to_iso


async def _user(db, email="a@b.c"):
    cur = await db.execute(
        "INSERT INTO users (email, created_at) VALUES (?, ?)", (email, to_iso(now_berlin()))
    )
    await db.commit()
    return cur.lastrowid


async def _plant(db, uid, name="P", interval=7, last_days_ago=0):
    now = now_berlin()
    cur = await db.execute(
        "INSERT INTO plants (user_id, name, interval_days, last_watered_at, created_at) "
        "VALUES (?, ?, ?, ?, ?)",
        (uid, name, interval, to_iso(now - timedelta(days=last_days_ago)), to_iso(now)),
    )
    await db.commit()
    return cur.lastrowid


async def _water_on(db, uid, pid, days_ago):
    d = now_berlin() - timedelta(days=days_ago)
    await db.execute(
        "INSERT INTO waterings (plant_id, user_id, watered_at, created_at) VALUES (?, ?, ?, ?)",
        (pid, uid, to_iso(d), to_iso(d)),
    )
    await db.commit()


async def test_stats_shape_empty(db):
    uid = await _user(db)
    s = await ps.compute_stats(db, uid)
    assert (s.total_plants, s.thirsty_count, s.watering_streak_days) == (0, 0, 0)
    assert s.watering_consistency_pct == 100  # no expected slots -> perfect, no ZeroDivision
    assert s.longest_overdue is None
    assert s.avg_interval_days is None
    assert s.avg_configured_interval_days is None


async def test_streak_consecutive(db):
    uid = await _user(db)
    pid = await _plant(db, uid, interval=1)
    for d in (0, 1, 2):
        await _water_on(db, uid, pid, d)
    assert (await ps.compute_stats(db, uid)).watering_streak_days == 3


async def test_streak_grace_day(db):
    uid = await _user(db)
    pid = await _plant(db, uid, interval=1)
    await _water_on(db, uid, pid, 1)  # only yesterday
    assert (await ps.compute_stats(db, uid)).watering_streak_days >= 1


async def test_streak_zero_on_gap(db):
    uid = await _user(db)
    pid = await _plant(db, uid, interval=1)
    await _water_on(db, uid, pid, 3)  # neither today nor yesterday
    assert (await ps.compute_stats(db, uid)).watering_streak_days == 0


async def test_consistency_full(db):
    uid = await _user(db)
    pid = await _plant(db, uid, interval=10)  # expected floor(30/10)=3
    for d in (0, 9, 19):
        await _water_on(db, uid, pid, d)
    assert (await ps.compute_stats(db, uid)).watering_consistency_pct == 100


async def test_consistency_partial(db):
    uid = await _user(db)
    pid = await _plant(db, uid, interval=10)  # expected 3
    for d in (0, 9):  # only 2 of 3
        await _water_on(db, uid, pid, d)
    assert (await ps.compute_stats(db, uid)).watering_consistency_pct == 67


async def test_longest_overdue(db):
    uid = await _user(db)
    await _plant(db, uid, name="A", interval=3, last_days_ago=8)  # overdue 5
    await _plant(db, uid, name="B", interval=3, last_days_ago=15)  # overdue 12
    s = await ps.compute_stats(db, uid)
    assert s.longest_overdue is not None
    assert s.longest_overdue.days_overdue == 12
    assert s.longest_overdue.name == "B"


async def test_avg_observed_interval(db):
    uid = await _user(db)
    pid = await _plant(db, uid, interval=7)
    for d in (0, 4, 10):  # diffs 6 and 4 -> avg 5.0
        await _water_on(db, uid, pid, d)
    assert (await ps.compute_stats(db, uid)).avg_interval_days == 5.0


async def test_avg_configured_interval(db):
    uid = await _user(db)
    await _plant(db, uid, name="A", interval=7)
    await _plant(db, uid, name="B", interval=14)
    assert (await ps.compute_stats(db, uid)).avg_configured_interval_days == 10.5


def test_location_max_length_rejected():
    with pytest.raises(ValidationError):
        PlantCreate(name="X", interval_days=7, location_room="x" * 81)
