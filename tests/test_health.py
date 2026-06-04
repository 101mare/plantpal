"""AK-LOG-1: extended healthcheck (B.6)."""


async def test_health_extended_shape(client):
    body = (await client.get("/api/health")).json()
    assert body["status"] == "ok"
    assert body["db_ok"] is True
    assert body["db_writable"] is True
    assert body["wal_mode"] is True
    assert body["version"] == "3.0.0"


async def test_stats_endpoint_rich_shape(client, db, settings):
    from plantpal import auth_service

    _, raw = await auth_service.bootstrap_admin(db, settings, "a@b.c")
    await client.get(f"/auth/verify?token={raw}")
    body = (await client.get("/api/stats")).json()
    for key in (
        "total_plants",
        "thirsty_count",
        "watering_streak_days",
        "watering_consistency_pct",
        "longest_overdue",
        "avg_interval_days",
        "avg_configured_interval_days",
    ):
        assert key in body
