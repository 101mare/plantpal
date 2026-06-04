from datetime import date, datetime, timedelta

import pytest

from plantpal import reminder_service as rs
from plantpal.models import PlantCreate
from plantpal.plant_service import create_plant
from plantpal.time_utils import now_berlin, to_iso


async def _insert_log(db, uid, date_str, status, age_hours=0):
    await db.execute(
        "INSERT INTO reminder_send_log (user_id, reminder_date, channel, status, created_at) "
        "VALUES (?, ?, 'email', ?, ?)",
        (uid, date_str, status, to_iso(now_berlin() - timedelta(hours=age_hours))),
    )
    await db.commit()


TODAY = date(2026, 5, 21)


class FakeSender:
    def __init__(self, fail=False):
        self.calls: list[tuple[str, int]] = []
        self.fail = fail

    async def __call__(self, settings, email, plants):
        if self.fail:
            raise RuntimeError("resend down")
        self.calls.append((email, len(plants)))


@pytest.fixture
def fast_settings(settings):
    # high rate → no real sleep between sends
    return settings.model_copy(update={"RESEND_RATE_PER_SEC": 100000.0})


async def _user(db, email, enabled=1, channel="email"):
    cur = await db.execute(
        "INSERT INTO users (email, email_reminders_enabled, reminder_channel, created_at) "
        "VALUES (?, ?, ?, ?)",
        (email, enabled, channel, to_iso(now_berlin())),
    )
    await db.commit()
    return cur.lastrowid


async def _thirsty_plant(db, uid, interval=3):
    pid = await create_plant(db, uid, PlantCreate(name="Calathea", interval_days=interval))
    await db.execute(
        "UPDATE plants SET last_watered_at = ? WHERE id = ?", ("2026-01-01T08:00:00", pid)
    )
    await db.commit()
    return pid


async def test_digest_sent_for_thirsty(db, fast_settings):
    uid = await _user(db, "a@b.c")
    await _thirsty_plant(db, uid)
    sender = FakeSender()
    res = await rs.run_daily_reminders(db, fast_settings, TODAY, sender)
    assert res["sent"] == 1
    assert sender.calls == [("a@b.c", 1)]


async def test_idempotent_double_run(db, fast_settings):
    uid = await _user(db, "a@b.c")
    await _thirsty_plant(db, uid)
    sender = FakeSender()
    await rs.run_daily_reminders(db, fast_settings, TODAY, sender)
    res2 = await rs.run_daily_reminders(db, fast_settings, TODAY, sender)
    assert res2["sent"] == 0
    assert res2["skipped"] == 1
    assert len(sender.calls) == 1  # exactly one mail despite two runs (DST / reboot safe)


async def test_no_mail_when_nothing_thirsty(db, fast_settings):
    uid = await _user(db, "a@b.c")
    await create_plant(db, uid, PlantCreate(name="Fresh", interval_days=30))  # watered now
    sender = FakeSender()
    res = await rs.run_daily_reminders(db, fast_settings, TODAY, sender)
    assert res["sent"] == 0
    assert sender.calls == []


async def test_toggle_off_excludes_user(db, fast_settings):
    uid = await _user(db, "a@b.c", enabled=0)
    await _thirsty_plant(db, uid)
    sender = FakeSender()
    res = await rs.run_daily_reminders(db, fast_settings, TODAY, sender)
    assert res["sent"] == 0


async def test_instagram_channel_excluded_from_email(db, fast_settings):
    uid = await _user(db, "a@b.c", channel="instagram")
    await _thirsty_plant(db, uid)
    sender = FakeSender()
    res = await rs.run_daily_reminders(db, fast_settings, TODAY, sender)
    assert res["sent"] == 0


async def test_both_channel_included(db, fast_settings):
    uid = await _user(db, "a@b.c", channel="both")
    await _thirsty_plant(db, uid)
    sender = FakeSender()
    res = await rs.run_daily_reminders(db, fast_settings, TODAY, sender)
    assert res["sent"] == 1


async def test_resend_failure_logged_and_retried(db, fast_settings):
    uid = await _user(db, "a@b.c")
    await _thirsty_plant(db, uid)
    failing = FakeSender(fail=True)
    res = await rs.run_daily_reminders(db, fast_settings, TODAY, failing)
    assert res["failed"] == 1
    # reminder_last_sent_date NOT advanced → eligible for retry
    async with db.execute("SELECT reminder_last_sent_date FROM users WHERE id = ?", (uid,)) as cur:
        assert (await cur.fetchone())["reminder_last_sent_date"] is None
    # log shows a failed row
    async with db.execute("SELECT status FROM reminder_send_log WHERE user_id = ?", (uid,)) as cur:
        assert (await cur.fetchone())["status"] == "failed"
    # retry with a working sender succeeds
    ok = FakeSender()
    res2 = await rs.run_daily_reminders(db, fast_settings, TODAY, ok)
    assert res2["sent"] == 1


async def test_catch_up_after_reboot_sends_today(db, fast_settings):
    uid = await _user(db, "a@b.c")
    await _thirsty_plant(db, uid)
    sender = FakeSender()
    # reboot at 09:00 (after the 08:00 run was missed) → target = today
    res = await rs.catch_up_missed(
        db, fast_settings, now=datetime(2026, 5, 21, 9, 0, 0), sender=sender
    )
    assert res["sent"] == 1


async def test_stale_sending_is_reclaimed_after_crash(db, fast_settings):
    """A run that crashed between claim and mark leaves a stale 'sending' row;
    a later run must reclaim it (older than 1h) and actually send."""
    uid = await _user(db, "a@b.c")
    await _thirsty_plant(db, uid)
    await _insert_log(db, uid, TODAY.isoformat(), "sending", age_hours=2)
    sender = FakeSender()
    res = await rs.run_daily_reminders(db, fast_settings, TODAY, sender)
    assert res["sent"] == 1


async def test_fresh_sending_is_not_stolen(db, fast_settings):
    """A fresh 'sending' row (another run in progress) must NOT be reclaimed."""
    uid = await _user(db, "a@b.c")
    await _thirsty_plant(db, uid)
    await _insert_log(db, uid, TODAY.isoformat(), "sending", age_hours=0)
    sender = FakeSender()
    res = await rs.run_daily_reminders(db, fast_settings, TODAY, sender)
    assert res["sent"] == 0
    assert sender.calls == []


async def test_dst_spring_forward_no_duplicate(db, fast_settings):
    """AK-9: on the spring-forward DST day the cron may fire oddly; still one mail."""
    uid = await _user(db, "a@b.c")
    await _thirsty_plant(db, uid)
    sender = FakeSender()
    dst_day = date(2026, 3, 29)  # last Sunday in March (CET→CEST)
    await rs.run_daily_reminders(db, fast_settings, dst_day, sender)
    await rs.run_daily_reminders(db, fast_settings, dst_day, sender)
    assert len(sender.calls) == 1


async def test_dst_fall_back_no_duplicate(db, fast_settings):
    """AK-10: on the fall-back DST day 02:00→03:00 repeats; still one mail."""
    uid = await _user(db, "a@b.c")
    await _thirsty_plant(db, uid)
    sender = FakeSender()
    dst_day = date(2026, 10, 25)  # last Sunday in October (CEST→CET)
    await rs.run_daily_reminders(db, fast_settings, dst_day, sender)
    await rs.run_daily_reminders(db, fast_settings, dst_day, sender)
    assert len(sender.calls) == 1


async def test_catch_up_respects_user_hour(db, fast_settings):
    """v3 (Codex HIGH): catch-up serves only users whose chosen hour has already passed."""
    early = await _user(db, "early@b.c")
    await db.execute("UPDATE users SET reminder_hour = 5 WHERE id = ?", (early,))
    late = await _user(db, "late@b.c")
    await db.execute("UPDATE users SET reminder_hour = 20 WHERE id = ?", (late,))
    await db.commit()
    await _thirsty_plant(db, early)
    await _thirsty_plant(db, late)
    sender = FakeSender()
    # reboot at 06:00 → only the 05:00 user is due; the 20:00 user is not yet
    res = await rs.catch_up_missed(
        db, fast_settings, now=datetime(2026, 5, 21, 6, 0, 0), sender=sender
    )
    assert res["sent"] == 1  # only the early user (hour 5 <= 6)


async def test_hourly_cron_matches_exact_hour(db, fast_settings):
    """v3: the hourly cron serves only users whose reminder_hour equals the current hour."""
    at8 = await _user(db, "at8@b.c")  # default reminder_hour = 8
    at9 = await _user(db, "at9@b.c")
    await db.execute("UPDATE users SET reminder_hour = 9 WHERE id = ?", (at9,))
    await db.commit()
    await _thirsty_plant(db, at8)
    await _thirsty_plant(db, at9)
    sender = FakeSender()
    res = await rs.run_hourly_reminders(
        db, fast_settings, now=datetime(2026, 5, 21, 8, 0, 0), sender=sender
    )
    assert res["sent"] == 1  # only the 08:00 user, not the 09:00 one
