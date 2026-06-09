"""v2 Spross evolution: durable, server-side high-water-mark (vitality_stage_max / peak_vitality).

Service-level (matches the test_email_change style): exercises the max-only ratchet + that it is
surfaced via compute_stats and scoped per user. The route is a thin CSRF-guarded wrapper around
bump_spross_progress (mirrors update_settings)."""

from plantpal import plant_service
from plantpal.time_utils import now_berlin, to_iso


async def _user(db, email="u@b.c"):
    cur = await db.execute(
        "INSERT INTO users (email, created_at) VALUES (?, ?)", (email, to_iso(now_berlin()))
    )
    await db.commit()
    return cur.lastrowid


async def test_defaults_are_stage1_peak0(db):
    uid = await _user(db)
    stats = await plant_service.compute_stats(db, uid)
    assert stats.vitality_stage_max == 1
    assert stats.peak_vitality == 0


async def test_bump_raises_and_is_reflected_in_stats(db):
    uid = await _user(db)
    assert await plant_service.bump_spross_progress(db, uid, 4, 55) == (4, 55)
    stats = await plant_service.compute_stats(db, uid)
    assert stats.vitality_stage_max == 4
    assert stats.peak_vitality == 55


async def test_bump_is_max_only_never_downgrades(db):
    uid = await _user(db)
    await plant_service.bump_spross_progress(db, uid, 5, 80)
    # a lower proposal must NOT lower the stored high-water-mark — the cardinal guarantee
    assert await plant_service.bump_spross_progress(db, uid, 2, 10) == (5, 80)


async def test_bump_each_field_ratchets_independently(db):
    uid = await _user(db)
    await plant_service.bump_spross_progress(db, uid, 3, 90)
    # higher stage but lower peak: stage climbs, peak holds
    assert await plant_service.bump_spross_progress(db, uid, 5, 40) == (5, 90)


async def test_bump_is_per_user(db):
    a = await _user(db, "a@b.c")
    b = await _user(db, "b@b.c")
    await plant_service.bump_spross_progress(db, a, 6, 100)
    stats_b = await plant_service.compute_stats(db, b)
    assert stats_b.vitality_stage_max == 1  # B is unaffected
    assert stats_b.peak_vitality == 0
