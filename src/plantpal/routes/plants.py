"""Plant routes: list (optionally grouped), CRUD, watering, image upload + serve."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import FileResponse

from .. import image_service, plant_service
from ..deps import current_user, get_db, require_csrf, settings_dep
from ..errors import AppError, NotFoundError
from ..models import GenericOk, PlantCreate, PlantUpdate
from ..rate_limit import check_rate_limit, key_user

router = APIRouter()


@router.get("/api/plants")
async def list_plants(group_by: str | None = None, user=Depends(current_user), db=Depends(get_db)):
    rows = await plant_service.list_plants(db, user.id)
    result: dict = {"items": [plant_service.to_response(r).model_dump() for r in rows]}
    if group_by == "room":
        result["groups"] = [g.model_dump() for g in plant_service.build_groups(rows)]
    return result


@router.get("/api/plants/{plant_id}/waterings")
async def list_waterings(plant_id: int, user=Depends(current_user), db=Depends(get_db)):
    rows = await plant_service.list_waterings(db, user.id, plant_id)
    if rows is None:
        raise NotFoundError("plant_not_found", code="plant_not_found", status_code=404)
    return {
        "items": [plant_service.watering_to_response(r).model_dump() for r in rows],
        "count": len(rows),
    }


@router.post("/api/plants", status_code=201)
async def create_plant(
    request: Request,
    name: str = Form(...),
    interval_days: int = Form(...),
    notes: str | None = Form(None),
    water_amount_ml: int | None = Form(None),
    location_room: str | None = Form(None),
    image: UploadFile = File(...),
    user=Depends(current_user),
    _csrf=Depends(require_csrf),
    db=Depends(get_db),
    settings=Depends(settings_dep),
):
    await check_rate_limit(db, key_user(user.id, "plant"), settings.RL_PLANT_MUTATION)
    # create always processes an image, so it must also honor the (stricter) image-upload
    # limit — otherwise it's a 30/m bypass of the 5/m CPU-heavy image pipeline (N5).
    await check_rate_limit(db, key_user(user.id, "image"), settings.RL_IMAGE_UPLOAD)
    data = PlantCreate(
        name=name,
        interval_days=interval_days,
        notes=notes,
        water_amount_ml=water_amount_ml,
        location_room=location_room,
    )
    pid = await plant_service.create_plant(db, user.id, data)
    try:
        raw = await image_service.read_upload_limited(image, settings)
        path = await image_service.process_upload(settings, user.id, pid, raw, image.content_type)
    except AppError:
        # roll back the just-created row so a failed upload leaves no orphan plant
        await plant_service.hard_delete_plant(db, user.id, pid)
        raise
    await plant_service.set_image_path(db, user.id, pid, path)
    row = await plant_service.get_plant(db, user.id, pid)
    return plant_service.to_response(row).model_dump()


@router.get("/api/plants/{plant_id}")
async def get_plant(plant_id: int, user=Depends(current_user), db=Depends(get_db)):
    row = await plant_service.get_plant(db, user.id, plant_id)
    if row is None:
        raise NotFoundError("plant_not_found", code="plant_not_found", status_code=404)
    return plant_service.to_response(row).model_dump()


@router.patch("/api/plants/{plant_id}")
async def update_plant(
    plant_id: int,
    body: PlantUpdate,
    user=Depends(current_user),
    _csrf=Depends(require_csrf),
    db=Depends(get_db),
    settings=Depends(settings_dep),
):
    await check_rate_limit(db, key_user(user.id, "plant"), settings.RL_PLANT_MUTATION)
    row = await plant_service.update_plant(db, user.id, plant_id, body)
    if row is None:
        raise NotFoundError("plant_not_found", code="plant_not_found", status_code=404)
    return plant_service.to_response(row).model_dump()


@router.delete("/api/plants/{plant_id}")
async def delete_plant(
    plant_id: int,
    user=Depends(current_user),
    _csrf=Depends(require_csrf),
    db=Depends(get_db),
    settings=Depends(settings_dep),
):
    await check_rate_limit(db, key_user(user.id, "plant"), settings.RL_PLANT_MUTATION)
    if not await plant_service.soft_delete_plant(db, user.id, plant_id):
        raise NotFoundError("plant_not_found", code="plant_not_found", status_code=404)
    await image_service.delete_plant_image(settings, user.id, plant_id)  # avoid disk leak (N8)
    return GenericOk()


@router.post("/api/plants/{plant_id}/water")
async def water_plant(
    plant_id: int,
    user=Depends(current_user),
    _csrf=Depends(require_csrf),
    db=Depends(get_db),
    settings=Depends(settings_dep),
):
    await check_rate_limit(db, key_user(user.id, "plant"), settings.RL_PLANT_MUTATION)
    row = await plant_service.water_plant(db, user.id, plant_id)
    if row is None:
        raise NotFoundError("plant_not_found", code="plant_not_found", status_code=404)
    return plant_service.to_response(row).model_dump()


@router.post("/api/plants/{plant_id}/image")
async def upload_image(
    plant_id: int,
    image: UploadFile = File(...),
    user=Depends(current_user),
    _csrf=Depends(require_csrf),
    db=Depends(get_db),
    settings=Depends(settings_dep),
):
    await check_rate_limit(db, key_user(user.id, "image"), settings.RL_IMAGE_UPLOAD)
    if await plant_service.get_plant(db, user.id, plant_id) is None:
        raise NotFoundError("plant_not_found", code="plant_not_found", status_code=404)
    raw = await image_service.read_upload_limited(image, settings)
    path = await image_service.process_upload(settings, user.id, plant_id, raw, image.content_type)
    await plant_service.set_image_path(db, user.id, plant_id, path)
    return {"image_url": f"/api/plants/{plant_id}/image"}


@router.get("/api/plants/{plant_id}/image")
async def get_image(
    plant_id: int, user=Depends(current_user), db=Depends(get_db), settings=Depends(settings_dep)
):
    if await plant_service.get_plant(db, user.id, plant_id) is None:
        raise NotFoundError("image_not_found", code="image_not_found", status_code=404)
    path = image_service.image_file_path(settings, user.id, plant_id)
    if path is None:
        raise NotFoundError("image_not_found", code="image_not_found", status_code=404)
    return FileResponse(path, media_type="image/png")
