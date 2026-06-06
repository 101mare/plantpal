"""Health route: liveness + DB-writable + WAL-mode + scheduler/job status for monitoring."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from ..deps import get_db, settings_dep
from ..models import HealthResponse

router = APIRouter()


def _is_local(request: Request) -> bool:
    """True only for a genuinely local peer (Docker healthcheck / debugging).

    Uses the raw socket peer, never CF-Connecting-IP — so traffic arriving through the
    Cloudflare Tunnel can't claim to be local and pull the detailed payload (N18).
    """
    peer = request.client.host if request.client else None
    return peer in ("127.0.0.1", "::1") and "cf-connecting-ip" not in request.headers


@router.get("/api/health")
async def health(request: Request, db=Depends(get_db), settings=Depends(settings_dep)):
    db_ok = True
    wal_mode = False
    try:
        async with db.execute("SELECT 1") as cur:
            await cur.fetchone()
        async with db.execute("PRAGMA journal_mode") as cur:
            row = await cur.fetchone()
        wal_mode = bool(row) and str(row[0]).lower() == "wal"
    except Exception:  # noqa: BLE001
        db_ok = False
    db_writable = db_ok
    if db_ok:
        try:  # no-op write that fails on a read-only / full filesystem
            async with db.execute("PRAGMA user_version") as cur:
                ver = (await cur.fetchone())[0]
            await db.execute(f"PRAGMA user_version = {int(ver)}")  # noqa: S608 — int only
        except Exception:  # noqa: BLE001
            db_writable = False
    status = "ok" if (db_ok and db_writable) else "degraded"

    # Public liveness only — version, scheduler, job and WAL state are a fingerprinting aid,
    # so they're exposed only to a local peer (N18).
    if not _is_local(request):
        return {"status": status}

    scheduler = getattr(request.app.state, "scheduler", None)
    running = bool(scheduler and scheduler.running)
    jobs = None
    if scheduler is not None:
        ids = {j.id for j in scheduler.get_jobs()}
        jobs = {"digest": "daily_digest" in ids, "housekeeping": "daily_housekeeping" in ids}
    reminder_last_run = None
    if db_ok:
        try:  # F-LOG-5: most recent day a reminder digest actually went out (N32)
            async with db.execute("SELECT MAX(reminder_last_sent_date) AS d FROM users") as cur:
                reminder_last_run = (await cur.fetchone())["d"]
        except Exception:  # noqa: BLE001
            reminder_last_run = None
    return HealthResponse(
        status=status,
        db_ok=db_ok,
        scheduler_running=running,
        db_writable=db_writable,
        wal_mode=wal_mode,
        version=settings.APP_VERSION,
        jobs=jobs,
        reminder_last_run=reminder_last_run,
    ).model_dump()
