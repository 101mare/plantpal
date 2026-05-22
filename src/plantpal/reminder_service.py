"""Daily email-digest reminders: idempotent, DST-safe, with reboot catch-up.

Idempotency is doubly guarded: ``users.reminder_last_sent_date`` plus a
``reminder_send_log`` row UNIQUE per (user, date, channel). The cron can fire
twice on a DST day or after a reboot and each user still gets exactly one mail.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from datetime import date, timedelta

import aiosqlite

from . import email_service, plant_service
from .config import Settings
from .time_utils import now_berlin, to_iso, today_berlin

# Injectable sender (real one hits Resend; tests pass a fake).
Sender = Callable[[Settings, str, list[dict]], Awaitable[object]]


async def _due_users(db: aiosqlite.Connection) -> list[aiosqlite.Row]:
    async with db.execute(
        "SELECT * FROM users WHERE email_reminders_enabled = 1 AND status = 'active' "
        "AND reminder_channel IN ('email', 'both')"
    ) as cur:
        return list(await cur.fetchall())


async def _already_sent(db: aiosqlite.Connection, user_id: int, date_str: str) -> bool:
    async with db.execute(
        "SELECT 1 FROM reminder_send_log "
        "WHERE user_id = ? AND reminder_date = ? AND channel = 'email' AND status = 'sent'",
        (user_id, date_str),
    ) as cur:
        return await cur.fetchone() is not None


# A 'sending' row older than this is treated as a crashed run and may be reclaimed.
_STALE_SENDING = timedelta(hours=1)


async def _claim(db: aiosqlite.Connection, user_id: int, date_str: str) -> bool:
    """Atomically claim (user, date) for sending. True if we may send.

    Inserts a 'sending' row, or re-claims a prior 'failed' row (retry) or a *stale*
    'sending' row (a previous run crashed between claim and mark). A fresh 'sending'
    row (another run in progress) or a 'sent' row yields rowcount 0 → we skip.
    """
    now = now_berlin()
    stale_before = to_iso(now - _STALE_SENDING)
    cur = await db.execute(
        "INSERT INTO reminder_send_log "
        "(user_id, reminder_date, channel, status, created_at) "
        "VALUES (?, ?, 'email', 'sending', ?) "
        "ON CONFLICT(user_id, reminder_date, channel) "
        "DO UPDATE SET status = 'sending', created_at = excluded.created_at "
        "WHERE reminder_send_log.status = 'failed' "
        "   OR (reminder_send_log.status = 'sending' AND reminder_send_log.created_at < ?)",
        (user_id, date_str, to_iso(now), stale_before),
    )
    await db.commit()
    return cur.rowcount == 1


async def _mark(
    db: aiosqlite.Connection, user_id: int, date_str: str, status: str, error: str | None = None
) -> None:
    await db.execute(
        "UPDATE reminder_send_log SET status = ?, error_message = ? "
        "WHERE user_id = ? AND reminder_date = ? AND channel = 'email'",
        (status, error, user_id, date_str),
    )
    await db.commit()


async def thirsty_for_digest(
    db: aiosqlite.Connection, user_id: int, target_date: date
) -> list[dict]:
    rows = await plant_service.list_plants(db, user_id)
    out = []
    for r in rows:
        is_thirsty, overdue = plant_service.thirsty_state(
            r["last_watered_at"], r["interval_days"], target_date
        )
        if is_thirsty:
            out.append({"name": r["name"], "days_overdue": overdue})
    return out


async def send_user_digest(
    db: aiosqlite.Connection,
    settings: Settings,
    user: aiosqlite.Row,
    target_date: date,
    sender: Sender | None = None,
) -> str:
    """Send one user's digest. Returns 'sent' | 'skipped' | 'failed'. Idempotent."""
    send = sender or email_service.send_daily_digest
    date_str = target_date.isoformat()
    if await _already_sent(db, user["id"], date_str):
        return "skipped"
    plants = await thirsty_for_digest(db, user["id"], target_date)
    if not plants:
        return "skipped"  # no "nothing to do" spam
    if not await _claim(db, user["id"], date_str):
        return "skipped"  # a concurrent run already owns this (user, date)
    try:
        await send(settings, user["email"], plants)
    except Exception as exc:  # noqa: BLE001 — log + retry next run, never crash the cron
        await _mark(db, user["id"], date_str, "failed", str(exc)[:200])
        return "failed"
    await _mark(db, user["id"], date_str, "sent")
    await db.execute(
        "UPDATE users SET reminder_last_sent_date = ? WHERE id = ?", (date_str, user["id"])
    )
    await db.commit()
    return "sent"


async def run_daily_reminders(
    db: aiosqlite.Connection,
    settings: Settings,
    target_date: date | None = None,
    sender: Sender | None = None,
) -> dict[str, int]:
    """Send digests to all due users for ``target_date`` (default: today Berlin)."""
    target_date = target_date or today_berlin()
    results = {"sent": 0, "skipped": 0, "failed": 0}
    delay = 1.0 / settings.RESEND_RATE_PER_SEC if settings.RESEND_RATE_PER_SEC else 0
    for i, user in enumerate(await _due_users(db)):
        if delay and i > 0:
            await asyncio.sleep(delay)  # pace sends to respect the Resend rate limit
        outcome = await send_user_digest(db, settings, user, target_date, sender)
        results[outcome] += 1
    return results


async def catch_up_missed(
    db: aiosqlite.Connection, settings: Settings, now=None, sender: Sender | None = None
) -> dict[str, int]:
    """On startup, send any reminder that the scheduled run missed (e.g. Pi reboot)."""
    moment = now or now_berlin()
    if moment.hour < settings.REMINDER_HOUR_BERLIN:
        target = moment.date() - timedelta(days=1)
    else:
        target = moment.date()
    return await run_daily_reminders(db, settings, target, sender)
