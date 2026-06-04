"""Health route: liveness + DB-writable + WAL-mode + scheduler/job status for monitoring."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from ..deps import get_db, settings_dep
from ..models import HealthResponse

router = APIRouter()


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
    scheduler = getattr(request.app.state, "scheduler", None)
    running = bool(scheduler and scheduler.running)
    jobs = None
    if scheduler is not None:
        ids = {j.id for j in scheduler.get_jobs()}
        jobs = {"digest": "daily_digest" in ids, "housekeeping": "daily_housekeeping" in ids}
    return HealthResponse(
        status="ok" if (db_ok and db_writable) else "degraded",
        db_ok=db_ok,
        scheduler_running=running,
        db_writable=db_writable,
        wal_mode=wal_mode,
        version=settings.APP_VERSION,
        jobs=jobs,
    ).model_dump()
