"""DSGVO data export (B.7, K10): the user's full data as a ZIP.

ZIP = export.json (nested plants[].waterings) + images/<id>.png + README.txt.
Read-only, user-scoped (no cross-user data structurally possible). Missing image
files are skipped gracefully — never a 500.
"""

from __future__ import annotations

import asyncio
import io
import json
import zipfile
from pathlib import Path

import aiosqlite

from .config import Settings
from .image_service import image_file_path
from .time_utils import now_berlin, to_iso


def _row_to_dict(row: aiosqlite.Row) -> dict:
    return {key: row[key] for key in row.keys()}  # noqa: SIM118 — sqlite3.Row needs .keys()


async def build_export_json(db: aiosqlite.Connection, user_id: int) -> dict:
    """Collect the user's complete personal data (K10 schema)."""
    async with db.execute("SELECT * FROM users WHERE id = ?", (user_id,)) as cur:
        user = await cur.fetchone()
    account = {
        "id": user["id"],
        "email": user["email"],
        "is_admin": bool(user["is_admin"]),
        "email_reminders_enabled": bool(user["email_reminders_enabled"]),
        "reminder_channel": user["reminder_channel"],
        "reminder_hour": user["reminder_hour"],
        "locale": user["locale"],
        "theme": user["theme"],
        "created_at": user["created_at"],
        "last_login_at": user["last_login_at"],
    }

    async with db.execute("SELECT * FROM plants WHERE user_id = ? ORDER BY id", (user_id,)) as cur:
        plant_rows = list(await cur.fetchall())
    plants = []
    for p in plant_rows:
        async with db.execute(
            "SELECT id, watered_at, created_at FROM waterings "
            "WHERE plant_id = ? AND user_id = ? ORDER BY watered_at DESC, id DESC",
            (p["id"], user_id),
        ) as cur:
            waterings = [
                {"id": w["id"], "watered_at": w["watered_at"], "created_at": w["created_at"]}
                for w in await cur.fetchall()
            ]
        plants.append(
            {
                "id": p["id"],
                "name": p["name"],
                "interval_days": p["interval_days"],
                "location_room": p["location_room"],
                "notes": p["notes"],
                "water_amount_ml": p["water_amount_ml"],
                "last_watered_at": p["last_watered_at"],
                "created_at": p["created_at"],
                "is_active": bool(p["is_active"]),
                "image_file": f"images/{p['id']}.png" if p["image_path"] else None,
                "waterings": waterings,
            }
        )

    async with db.execute(
        "SELECT id, email_hint, created_at, expires_at, used_at, max_uses, used_count "
        "FROM invite_tokens WHERE created_by_user_id = ? ORDER BY id",
        (user_id,),
    ) as cur:
        invites = [_row_to_dict(r) for r in await cur.fetchall()]

    async with db.execute(
        "SELECT created_at, last_seen_at, expires_at FROM sessions WHERE user_id = ? ORDER BY id",
        (user_id,),
    ) as cur:
        sessions = [_row_to_dict(r) for r in await cur.fetchall()]

    return {
        "export_format_version": 1,
        "generated_at": to_iso(now_berlin()),
        "account": account,
        "plants": plants,
        "invites_created": invites,
        "sessions": sessions,
    }


def _build_zip_sync(data: dict, image_paths: dict[int, Path]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("export.json", json.dumps(data, indent=2, ensure_ascii=False))
        zf.writestr(
            "README.txt",
            "PlantPal Datenexport\n"
            f"Erzeugt: {data['generated_at']}\n\n"
            "Inhalt:\n"
            "- export.json: alle gespeicherten Daten deines Accounts (DSGVO Art. 15/20).\n"
            "- images/<plant_id>.png: die Fotos deiner Pflanzen.\n\n"
            "export.json (export_format_version=1): account, plants[] mit verschachtelter"
            " waterings-Historie, invites_created[], sessions[].\n",
        )
        for pid, path in image_paths.items():
            if path is not None and path.exists():
                zf.write(path, f"images/{pid}.png")
    return buf.getvalue()


async def build_export_zip(db: aiosqlite.Connection, settings: Settings, user_id: int) -> bytes:
    """Full export ZIP bytes; missing image files are dropped gracefully (F-EXP-5)."""
    data = await build_export_json(db, user_id)
    image_paths: dict[int, Path] = {}
    for p in data["plants"]:
        if p["image_file"]:
            path = image_file_path(settings, user_id, p["id"])
            if path is None:
                p["image_file"] = None  # missing on disk -> null, no zip entry
            else:
                image_paths[p["id"]] = path
    return await asyncio.to_thread(_build_zip_sync, data, image_paths)
