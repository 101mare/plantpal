"""N18 (health detail gated to local) + N32 (reminder_last_run populated)."""

from __future__ import annotations

from plantpal.time_utils import now_berlin, to_iso


async def test_health_public_is_liveness_only(client):
    # Traffic arriving via the Cloudflare Tunnel (CF-Connecting-IP present) is not "local":
    # it must get a minimal liveness payload, no version/scheduler/job/WAL fingerprint (N18).
    r = await client.get("/api/health", headers={"cf-connecting-ip": "203.0.113.1"})
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


async def test_health_local_is_detailed(client):
    # ASGITransport's peer is 127.0.0.1 → local → full payload (Docker healthcheck path).
    body = (await client.get("/api/health")).json()
    assert body["db_ok"] is True
    assert body["wal_mode"] is True
    assert body["version"]
    assert "jobs" in body


async def test_health_reports_reminder_last_run(client, db):
    # N32: reminder_last_run reflects the most recent digest day (was always null before).
    await db.execute(
        "INSERT INTO users (email, reminder_last_sent_date, created_at) VALUES (?, ?, ?)",
        ("u@b.c", "2026-06-05", to_iso(now_berlin())),
    )
    await db.commit()
    body = (await client.get("/api/health")).json()
    assert body["reminder_last_run"] == "2026-06-05"


async def test_health_reminder_last_run_null_when_none_sent(client):
    body = (await client.get("/api/health")).json()
    assert body["reminder_last_run"] is None
