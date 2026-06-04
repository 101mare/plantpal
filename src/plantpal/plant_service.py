"""Plant CRUD (user-scoped), watering history, derived stats, location grouping."""

from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta

import aiosqlite

from .models import (
    LongestOverdue,
    PlantCreate,
    PlantGroup,
    PlantResponse,
    PlantUpdate,
    RoomStats,
    StatsResponse,
    WateringResponse,
)
from .time_utils import from_iso, now_berlin, to_iso, today_berlin


def thirsty_state(
    last_watered_at: str, interval_days: int, today: date | None = None
) -> tuple[bool, int]:
    """Return (is_thirsty, days_overdue) at day granularity in Berlin time."""
    ref = today or today_berlin()
    due = from_iso(last_watered_at).date() + timedelta(days=interval_days)
    overdue = (ref - due).days
    return overdue >= 0, max(0, overdue)


def _normalize_room(value: str | None) -> str | None:
    """Trim location_room; whitespace-only/empty -> None (one canonical 'no room')."""
    if value is None:
        return None
    trimmed = value.strip()
    return trimmed or None


def to_response(row: aiosqlite.Row, today: date | None = None) -> PlantResponse:
    is_thirsty, days_overdue = thirsty_state(row["last_watered_at"], row["interval_days"], today)
    return PlantResponse(
        id=row["id"],
        name=row["name"],
        interval_days=row["interval_days"],
        image_url=f"/api/plants/{row['id']}/image" if row["image_path"] else None,
        last_watered_at=row["last_watered_at"],
        created_at=row["created_at"],
        notes=row["notes"],
        water_amount_ml=row["water_amount_ml"],
        location_room=row["location_room"],
        is_thirsty=is_thirsty,
        days_overdue=days_overdue,
    )


def watering_to_response(row: aiosqlite.Row) -> WateringResponse:
    return WateringResponse(
        id=row["id"], watered_at=row["watered_at"], created_at=row["created_at"]
    )


async def create_plant(db: aiosqlite.Connection, user_id: int, data: PlantCreate) -> int:
    """Insert a plant + a backfill watering row (F-HIST-3), one transaction. Returns id."""
    now = to_iso(now_berlin())
    cur = await db.execute(
        "INSERT INTO plants (user_id, name, interval_days, last_watered_at, created_at, "
        "notes, water_amount_ml, location_room) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (
            user_id,
            data.name,
            data.interval_days,
            now,
            now,
            data.notes,
            data.water_amount_ml,
            _normalize_room(data.location_room),
        ),
    )
    pid = cur.lastrowid
    await db.execute(
        "INSERT INTO waterings (plant_id, user_id, watered_at, created_at) VALUES (?, ?, ?, ?)",
        (pid, user_id, now, now),
    )
    await db.commit()
    return pid


async def get_plant(db: aiosqlite.Connection, user_id: int, plant_id: int) -> aiosqlite.Row | None:
    async with db.execute(
        "SELECT * FROM plants WHERE id = ? AND user_id = ? AND is_active = 1",
        (plant_id, user_id),
    ) as cur:
        return await cur.fetchone()


async def list_plants(db: aiosqlite.Connection, user_id: int) -> list[aiosqlite.Row]:
    """Active plants, thirsty first (most overdue first), then alphabetically."""
    async with db.execute(
        "SELECT * FROM plants WHERE user_id = ? AND is_active = 1", (user_id,)
    ) as cur:
        rows = list(await cur.fetchall())
    today = today_berlin()

    def sort_key(row: aiosqlite.Row):
        _, overdue = thirsty_state(row["last_watered_at"], row["interval_days"], today)
        return (-overdue, row["name"].lower())

    return sorted(rows, key=sort_key)


async def update_plant(
    db: aiosqlite.Connection, user_id: int, plant_id: int, data: PlantUpdate
) -> aiosqlite.Row | None:
    fields = data.model_dump(exclude_unset=True)
    if "location_room" in fields:
        fields["location_room"] = _normalize_room(fields["location_room"])
    if not fields:
        return await get_plant(db, user_id, plant_id)
    assignments = ", ".join(f"{key} = ?" for key in fields)
    values = [*fields.values(), plant_id, user_id]
    cur = await db.execute(
        f"UPDATE plants SET {assignments} WHERE id = ? AND user_id = ? AND is_active = 1",  # noqa: S608
        values,
    )
    await db.commit()
    if cur.rowcount == 0:
        return None
    return await get_plant(db, user_id, plant_id)


async def set_image_path(db: aiosqlite.Connection, user_id: int, plant_id: int, path: str) -> None:
    await db.execute(
        "UPDATE plants SET image_path = ? WHERE id = ? AND user_id = ?",
        (path, plant_id, user_id),
    )
    await db.commit()


async def water_plant(
    db: aiosqlite.Connection, user_id: int, plant_id: int
) -> aiosqlite.Row | None:
    """Append a watering row and mirror plants.last_watered_at (same ts, one tx; F-HIST-2)."""
    now = to_iso(now_berlin())
    cur = await db.execute(
        "UPDATE plants SET last_watered_at = ? WHERE id = ? AND user_id = ? AND is_active = 1",
        (now, plant_id, user_id),
    )
    if cur.rowcount == 0:
        await db.rollback()  # plant absent/foreign/inactive -> no watering row
        return None
    await db.execute(
        "INSERT INTO waterings (plant_id, user_id, watered_at, created_at) VALUES (?, ?, ?, ?)",
        (plant_id, user_id, now, now),
    )
    await db.commit()
    return await get_plant(db, user_id, plant_id)


async def list_waterings(
    db: aiosqlite.Connection, user_id: int, plant_id: int
) -> list[aiosqlite.Row] | None:
    """Watering history of one active, owned plant, newest first. None if plant not found."""
    if await get_plant(db, user_id, plant_id) is None:
        return None
    async with db.execute(
        "SELECT id, watered_at, created_at FROM waterings "
        "WHERE plant_id = ? AND user_id = ? ORDER BY watered_at DESC, id DESC",
        (plant_id, user_id),
    ) as cur:
        return list(await cur.fetchall())


async def hard_delete_plant(db: aiosqlite.Connection, user_id: int, plant_id: int) -> None:
    """Permanently remove a plant row (rolls back a failed create+upload). Cascades waterings."""
    await db.execute("DELETE FROM plants WHERE id = ? AND user_id = ?", (plant_id, user_id))
    await db.commit()


async def soft_delete_plant(db: aiosqlite.Connection, user_id: int, plant_id: int) -> bool:
    cur = await db.execute(
        "UPDATE plants SET is_active = 0 WHERE id = ? AND user_id = ? AND is_active = 1",
        (plant_id, user_id),
    )
    await db.commit()
    return cur.rowcount > 0


async def stats(db: aiosqlite.Connection, user_id: int) -> tuple[int, int]:
    """Return (total_active, thirsty_count). M1 compatibility helper."""
    rows = await list_plants(db, user_id)
    today = today_berlin()
    thirsty = sum(
        1 for r in rows if thirsty_state(r["last_watered_at"], r["interval_days"], today)[0]
    )
    return len(rows), thirsty


# --- Rich stats (B.2) ---


def _watering_streak(all_days: set[date], today: date) -> int:
    """Consecutive calendar days up to today with >=1 watering, with a grace day (F-STAT-3)."""
    if today in all_days:
        cursor = today
    elif (today - timedelta(days=1)) in all_days:
        cursor = today - timedelta(days=1)  # grace: not yet watered today, but yesterday counts
    else:
        return 0
    streak = 0
    while cursor in all_days:
        streak += 1
        cursor -= timedelta(days=1)
    return streak


def _consistency_pct(
    plants: list[aiosqlite.Row], days_by_plant: dict[int, set[date]], today: date
) -> int:
    """Timely waterings vs expected slots over a 30-day window, 0..100 (F-STAT-4)."""
    window_start = today - timedelta(days=29)
    total_expected = 0
    total_fulfilled = 0
    for p in plants:
        expected = 30 // p["interval_days"]  # floor; 0 if interval > 30
        if expected <= 0:
            continue
        days = days_by_plant.get(p["id"], set())
        in_window = sum(1 for d in days if window_start <= d <= today)
        total_expected += expected
        total_fulfilled += min(in_window, expected)
    if total_expected == 0:
        return 100  # nothing was due -> perfect, never divide by zero
    return round(100 * total_fulfilled / total_expected)


async def compute_stats(
    db: aiosqlite.Connection, user_id: int, by_room: bool = False
) -> StatsResponse:
    """Full rich stats, server-derived from active plants + their watering history (B.2)."""
    today = today_berlin()
    async with db.execute(
        "SELECT id, name, interval_days, last_watered_at, location_room "
        "FROM plants WHERE user_id = ? AND is_active = 1",
        (user_id,),
    ) as cur:
        plants = list(await cur.fetchall())
    active_ids = {p["id"] for p in plants}

    async with db.execute(
        "SELECT plant_id, watered_at FROM waterings WHERE user_id = ?", (user_id,)
    ) as cur:
        wrows = [r for r in await cur.fetchall() if r["plant_id"] in active_ids]

    days_by_plant: dict[int, set[date]] = defaultdict(set)
    all_days: set[date] = set()
    for r in wrows:
        d = from_iso(r["watered_at"]).date()
        days_by_plant[r["plant_id"]].add(d)
        all_days.add(d)

    total = len(plants)
    thirsty = sum(
        1 for p in plants if thirsty_state(p["last_watered_at"], p["interval_days"], today)[0]
    )

    # longest overdue (days_overdue > 0); tie-break by name (case-insensitive) ascending
    overdue = []
    for p in plants:
        _, days_overdue = thirsty_state(p["last_watered_at"], p["interval_days"], today)
        if days_overdue > 0:
            overdue.append((days_overdue, p["name"].lower(), p["id"], p["name"]))
    longest = None
    if overdue:
        overdue.sort(key=lambda t: (-t[0], t[1]))
        d, _, pid, name = overdue[0]
        longest = LongestOverdue(plant_id=pid, name=name, days_overdue=d)

    # observed average interval across all active plants (distinct watering days)
    diffs: list[int] = []
    for p in plants:
        days = sorted(days_by_plant.get(p["id"], set()))
        diffs.extend((days[i] - days[i - 1]).days for i in range(1, len(days)))
    avg_interval = round(sum(diffs) / len(diffs), 1) if diffs else None
    avg_configured = round(sum(p["interval_days"] for p in plants) / total, 1) if total else None

    rooms = build_room_stats(plants, today) if by_room else None

    return StatsResponse(
        total_plants=total,
        thirsty_count=thirsty,
        watering_streak_days=_watering_streak(all_days, today),
        watering_consistency_pct=_consistency_pct(plants, days_by_plant, today),
        longest_overdue=longest,
        avg_interval_days=avg_interval,
        avg_configured_interval_days=avg_configured,
        rooms=rooms,
    )


def build_groups(rows: list[aiosqlite.Row]) -> list[PlantGroup]:
    """Partition already-sorted plant rows by room; 'no room' group last (F-LOC-4)."""
    groups: dict[str | None, list[int]] = {}
    for r in rows:
        room = _normalize_room(r["location_room"])
        groups.setdefault(room, []).append(r["id"])
    named = sorted((k for k in groups if k is not None), key=str.lower)
    result = [PlantGroup(location_room=k, plant_ids=groups[k]) for k in named]
    if None in groups:
        result.append(PlantGroup(location_room=None, plant_ids=groups[None]))
    return result


def build_room_stats(rows: list[aiosqlite.Row], today: date) -> list[RoomStats]:
    """Per-room (total, thirsty) aggregate; 'no room' last (F-LOC-5)."""
    agg: dict[str | None, list[int]] = {}
    for r in rows:
        room = _normalize_room(r["location_room"])
        bucket = agg.setdefault(room, [0, 0])
        bucket[0] += 1
        if thirsty_state(r["last_watered_at"], r["interval_days"], today)[0]:
            bucket[1] += 1
    named = sorted((k for k in agg if k is not None), key=str.lower)
    result = [
        RoomStats(location_room=k, total_plants=agg[k][0], thirsty_count=agg[k][1]) for k in named
    ]
    if None in agg:
        result.append(
            RoomStats(location_room=None, total_plants=agg[None][0], thirsty_count=agg[None][1])
        )
    return result


async def delete_account(db: aiosqlite.Connection, user_id: int) -> None:
    """Hard-delete the user; FK ON DELETE CASCADE removes plants/waterings/sessions/tokens.

    NOTE: only removes DB rows. The caller MUST also call
    ``image_service.delete_user_images(settings, user_id)`` for on-disk images.
    """
    await db.execute("DELETE FROM users WHERE id = ?", (user_id,))
    await db.commit()
