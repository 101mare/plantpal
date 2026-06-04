"""AK-EXP-*: DSGVO data export (B.7)."""

import io
import zipfile

from PIL import Image

from plantpal import account_export_service as ex
from plantpal import image_service
from plantpal import plant_service as ps
from plantpal.models import PlantCreate
from plantpal.time_utils import now_berlin, to_iso


def _png():
    buf = io.BytesIO()
    Image.new("RGB", (40, 40), (80, 160, 100)).save(buf, "PNG")
    return buf.getvalue()


async def _user(db, email="a@b.c"):
    cur = await db.execute(
        "INSERT INTO users (email, created_at) VALUES (?, ?)", (email, to_iso(now_berlin()))
    )
    await db.commit()
    return cur.lastrowid


async def _plant_with_image(db, settings, uid, name="M"):
    pid = await ps.create_plant(db, uid, PlantCreate(name=name, interval_days=7))
    path = await image_service.process_upload(settings, uid, pid, _png(), "image/png")
    await ps.set_image_path(db, uid, pid, path)
    return pid


async def test_export_zip_contents(db, settings):
    uid = await _user(db)
    await _plant_with_image(db, settings, uid, "A")
    zf = zipfile.ZipFile(io.BytesIO(await ex.build_export_zip(db, settings, uid)))
    names = zf.namelist()
    assert "export.json" in names
    assert "README.txt" in names
    assert any(n.startswith("images/") for n in names)


async def test_export_includes_soft_deleted_and_scopes(db, settings):
    uid = await _user(db)
    pid = await ps.create_plant(db, uid, PlantCreate(name="Gone", interval_days=7))
    await ps.soft_delete_plant(db, uid, pid)
    data = await ex.build_export_json(db, uid)
    assert "Gone" in [p["name"] for p in data["plants"]]  # Art. 15: all stored data
    assert any(p["is_active"] is False for p in data["plants"])


async def test_export_no_secrets(db, settings):
    uid = await _user(db)
    await _plant_with_image(db, settings, uid)
    blob = await ex.build_export_zip(db, settings, uid)
    text = zipfile.ZipFile(io.BytesIO(blob)).read("export.json").decode()
    assert "token_hash" not in text
    assert "session_hash" not in text
    assert "RESEND_API_KEY" not in text


async def test_export_user_isolation(db, settings):
    a = await _user(db, "a@b.c")
    b = await _user(db, "b@b.c")
    await ps.create_plant(db, a, PlantCreate(name="ASecret", interval_days=7))
    data_b = await ex.build_export_json(db, b)
    assert all(p["name"] != "ASecret" for p in data_b["plants"])


async def test_export_missing_image_graceful(db, settings):
    uid = await _user(db)
    pid = await ps.create_plant(db, uid, PlantCreate(name="NoImg", interval_days=7))
    await ps.set_image_path(db, uid, pid, f"{uid}/{pid}.png")  # path recorded but file absent
    blob = await ex.build_export_zip(db, settings, uid)  # must not raise on a missing file
    names = zipfile.ZipFile(io.BytesIO(blob)).namelist()
    assert not any(n.startswith("images/") for n in names)  # missing file -> no zip entry
