"""Plant CRUD (user-scoped), watering, derived thirsty-state, stats, account delete."""

from __future__ import annotations

from datetime import date, timedelta

import aiosqlite

from .models import PlantCreate, PlantResponse, PlantUpdate
from .time_utils import from_iso, now_berlin, to_iso, today_berlin


def thirsty_state(
    last_watered_at: str, interval_days: int, today: date | None = None
) -> tuple[bool, int]:
    """Return (is_thirsty, days_overdue) at day granularity in Berlin time."""
    ref = today or today_berlin()
    due = from_iso(last_watered_at).date() + timedelta(days=interval_days)
    overdue = (ref - due).days
    return overdue >= 0, max(0, overdue)


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
        is_thirsty=is_thirsty,
        days_overdue=days_overdue,
    )


async def create_plant(db: aiosqlite.Connection, user_id: int, data: PlantCreate) -> int:
    """Insert a plant (image_path null until the image is processed). Returns id."""
    now = to_iso(now_berlin())
    cur = await db.execute(
        "INSERT INTO plants (user_id, name, interval_days, last_watered_at, created_at, "
        "notes, water_amount_ml) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (user_id, data.name, data.interval_days, now, now, data.notes, data.water_amount_ml),
    )
    await db.commit()
    return cur.lastrowid


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
    cur = await db.execute(
        "UPDATE plants SET last_watered_at = ? WHERE id = ? AND user_id = ? AND is_active = 1",
        (to_iso(now_berlin()), plant_id, user_id),
    )
    await db.commit()
    if cur.rowcount == 0:
        return None
    return await get_plant(db, user_id, plant_id)


async def hard_delete_plant(db: aiosqlite.Connection, user_id: int, plant_id: int) -> None:
    """Permanently remove a plant row (used to roll back a failed create+upload)."""
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
    """Return (total_active, thirsty_count)."""
    rows = await list_plants(db, user_id)
    today = today_berlin()
    thirsty = sum(
        1 for r in rows if thirsty_state(r["last_watered_at"], r["interval_days"], today)[0]
    )
    return len(rows), thirsty


async def delete_account(db: aiosqlite.Connection, user_id: int) -> None:
    """Hard-delete the user; FK ON DELETE CASCADE removes plants/sessions/tokens.

    NOTE: this only removes DB rows. The caller MUST also call
    ``image_service.delete_user_images(settings, user_id)`` to delete the on-disk
    images (FK cascade cannot touch the filesystem). The account-delete route does this.
    """
    await db.execute("DELETE FROM users WHERE id = ?", (user_id,))
    await db.commit()
