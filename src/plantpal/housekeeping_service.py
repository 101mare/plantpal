"""Daily DB-hygiene cron (B.4): delete expired/consumed transient rows.

Never touches users / plants / waterings / images. Each category is isolated:
a failure in one is logged and does not abort the others.
"""

from __future__ import annotations

import time
from datetime import timedelta

import aiosqlite
import structlog

from .config import Settings
from .time_utils import now_berlin, to_iso, today_berlin

log = structlog.get_logger("plantpal.housekeeping")


async def run_housekeeping(
    db: aiosqlite.Connection, settings: Settings, now=None
) -> dict[str, int]:
    """Delete expired/consumed transient rows. Returns per-category deleted counts."""
    moment = now or now_berlin()
    now_iso = to_iso(moment)
    counts: dict[str, int] = {}

    async def _delete(category: str, sql: str, params: tuple) -> None:
        try:
            cur = await db.execute(sql, params)
            await db.commit()
            counts[category] = cur.rowcount
        except Exception as exc:  # noqa: BLE001 — isolate per-category failures
            await db.rollback()
            counts[category] = -1
            log.error("housekeeping_error", category=category, error=str(exc)[:200])

    # (a) login tokens: expired or already consumed (magic links + codes)
    await _delete(
        "login_tokens",
        "DELETE FROM login_tokens WHERE expires_at < ? OR used_at IS NOT NULL",
        (now_iso,),
    )
    # (b) invite tokens: expired, revoked, or fully exhausted (cascades invite_redemptions, K6)
    await _delete(
        "invite_tokens",
        "DELETE FROM invite_tokens "
        "WHERE expires_at < ? OR revoked_at IS NOT NULL OR used_count >= max_uses",
        (now_iso,),
    )
    # (c) sessions: revoked or hard-expired (finally dead)
    await _delete(
        "sessions",
        "DELETE FROM sessions WHERE revoked_at IS NOT NULL OR hard_expires_at < ?",
        (now_iso,),
    )
    # (d) email-change requests: used or expired
    await _delete(
        "email_change_requests",
        "DELETE FROM email_change_requests WHERE used_at IS NOT NULL OR expires_at < ?",
        (now_iso,),
    )
    # (e) reminder send log: older than retention
    cutoff = (today_berlin() - timedelta(days=settings.HK_REMINDER_LOG_RETENTION_DAYS)).isoformat()
    await _delete(
        "reminder_send_log",
        "DELETE FROM reminder_send_log WHERE reminder_date < ?",
        (cutoff,),
    )
    # (f) rate limits: expired (numeric epoch comparison, like M1)
    await _delete(
        "rate_limits",
        "DELETE FROM rate_limits WHERE expires_at < ?",
        (int(time.time()),),
    )

    log.info("housekeeping_done", **{k: v for k, v in counts.items() if v != 0})
    return counts
