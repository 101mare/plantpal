import io

import pytest
from PIL import Image

from plantpal.errors import PayloadTooLargeError, UnsupportedMediaError
from plantpal.image_service import (
    delete_plant_image,
    delete_user_images,
    image_file_path,
    process_upload,
)


def _img_bytes(fmt="PNG", w=200, h=120, color=(120, 200, 140)):
    buf = io.BytesIO()
    Image.new("RGB", (w, h), color).save(buf, format=fmt)
    return buf.getvalue()


async def test_upload_produces_96x96_png(settings):
    path = await process_upload(settings, 1, 5, _img_bytes("PNG", 200, 120))
    assert path == "1/5.png"
    f = image_file_path(settings, 1, 5)
    assert f is not None
    img = Image.open(f)
    assert img.size == (96, 96)
    assert img.format == "PNG"


async def test_upload_accepts_jpeg_and_webp(settings):
    await process_upload(settings, 1, 1, _img_bytes("JPEG"))
    await process_upload(settings, 1, 2, _img_bytes("WEBP"))
    assert image_file_path(settings, 1, 1) is not None
    assert image_file_path(settings, 1, 2) is not None


async def test_upload_rejects_non_image_magic_bytes(settings):
    with pytest.raises(UnsupportedMediaError):
        await process_upload(settings, 1, 9, b"<html>totally not an image</html>")


async def test_upload_rejects_oversized(settings):
    tiny = settings.model_copy(update={"IMG_MAX_UPLOAD_MB": 1})
    raw = b"x" * (2 * 1024 * 1024)  # 2 MB > 1 MB limit, checked before decode
    with pytest.raises(PayloadTooLargeError):
        await process_upload(tiny, 1, 1, raw)


async def test_upload_center_crops_rectangle(settings):
    # wide rectangle still yields a square thumbnail
    path = await process_upload(settings, 7, 7, _img_bytes("PNG", 400, 100))
    img = Image.open(image_file_path(settings, 7, 7))
    assert img.size == (settings.IMG_SIZE_PX, settings.IMG_SIZE_PX)
    assert path.startswith("7/")


async def test_delete_user_images(settings):
    await process_upload(settings, 3, 1, _img_bytes())
    assert image_file_path(settings, 3, 1) is not None
    await delete_user_images(settings, 3)
    assert image_file_path(settings, 3, 1) is None


def test_storage_path_stays_under_image_dir(settings):
    from plantpal.image_service import _storage_path

    p = _storage_path(settings, 1, 2)
    assert str(p).startswith(str(settings.IMAGE_DIR))
    # IDs are coerced to int, so traversal via crafted values is impossible
    assert p.name == "2.png"


async def test_upload_rejects_oversized_pixel_count(settings):
    # Real bytes under the byte cap but above the pixel cap must be rejected,
    # even though Pillow only warns (not errors) between 1x and 2x MAX_IMAGE_PIXELS.
    small_pixels = settings.model_copy(update={"IMG_MAX_PIXELS": 10_000})  # 100x100
    raw = _img_bytes("PNG", 200, 200)  # 40_000 px > 10_000
    with pytest.raises(UnsupportedMediaError):
        await process_upload(small_pixels, 1, 1, raw)


async def test_upload_ignores_mismatched_declared_mime(settings):
    # N39: the magic-byte sniff is authoritative; a real image declared with the "wrong" or a
    # generic content type (image/jpg, application/octet-stream) is still accepted.
    await process_upload(settings, 1, 1, _img_bytes("PNG", 50, 50), declared_mime="image/jpeg")
    assert image_file_path(settings, 1, 1) is not None
    await process_upload(settings, 1, 2, _img_bytes("JPEG"), declared_mime="application/octet-stream")
    assert image_file_path(settings, 1, 2) is not None


async def test_delete_plant_image_removes_file(settings):
    # N8: soft-delete cleans up the on-disk thumbnail so deleted plants don't leak disk.
    await process_upload(settings, 4, 9, _img_bytes())
    assert image_file_path(settings, 4, 9) is not None
    await delete_plant_image(settings, 4, 9)
    assert image_file_path(settings, 4, 9) is None
    await delete_plant_image(settings, 4, 9)  # idempotent / best-effort, never raises


async def test_output_png_has_no_icc_profile(settings):
    from PIL import Image

    await process_upload(settings, 1, 1, _img_bytes("PNG", 120, 120))
    img = Image.open(image_file_path(settings, 1, 1))
    assert "icc_profile" not in img.info
