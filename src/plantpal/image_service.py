"""Safe async image pipeline: validate → EXIF-rotate → strip → center-crop → resize.

Hardening: magic-byte sniff (not Content-Type), decompression-bomb guard, path-
traversal-proof storage, CPU work off the event loop via ``asyncio.to_thread``.
"""

from __future__ import annotations

import asyncio
import contextlib
import io
import os
import shutil
import uuid
from pathlib import Path

import filetype
from fastapi import UploadFile

from .config import Settings
from .errors import (
    PayloadTooLargeError,
    UnprocessableError,
    UnsupportedMediaError,
)

_ALLOWED_MIME = {"image/jpeg", "image/png", "image/webp"}


def _storage_path(settings: Settings, user_id: int, plant_id: int) -> Path:
    """Build a path that provably stays under IMAGE_DIR (IDs are coerced to int)."""
    base = Path(settings.IMAGE_DIR).resolve()
    target = (base / str(int(user_id)) / f"{int(plant_id)}.png").resolve()
    if not str(target).startswith(str(base) + os.sep):
        raise UnprocessableError("Invalid storage path.")
    return target


async def read_upload_limited(image: UploadFile, settings: Settings) -> bytes:
    """Read an UploadFile in 64 KB chunks, aborting once it exceeds the size cap — so an
    oversized upload is rejected before the whole body is buffered into memory (DoS guard)."""
    max_bytes = settings.IMG_MAX_UPLOAD_MB * 1024 * 1024
    chunks: list[bytes] = []
    total = 0
    while chunk := await image.read(64 * 1024):
        total += len(chunk)
        if total > max_bytes:
            raise PayloadTooLargeError(f"Image exceeds {settings.IMG_MAX_UPLOAD_MB} MB.")
        chunks.append(chunk)
    return b"".join(chunks)


def _process_sync(raw: bytes, size: int, max_pixels: int) -> bytes:
    """Decode, normalize orientation, strip metadata, square-crop, resize → PNG bytes."""
    from PIL import Image, ImageOps

    Image.MAX_IMAGE_PIXELS = max_pixels
    try:
        # First pass: verify integrity (catches truncation).
        Image.open(io.BytesIO(raw)).verify()
        # verify() leaves the image unusable — reopen for real work.
        img = Image.open(io.BytesIO(raw))
        # Explicit pixel guard: Pillow only *errors* above ~2x MAX_IMAGE_PIXELS
        # (it merely warns between 1x and 2x), so check the real dimensions here.
        if img.width * img.height > max_pixels:
            raise UnsupportedMediaError("Image has too many pixels.")
        img = ImageOps.exif_transpose(img)  # honor rotation
        img = img.convert("RGB")  # drop alpha; orientation already applied
        width, height = img.size
        side = min(width, height)
        left = (width - side) // 2
        top = (height - side) // 2
        img = img.crop((left, top, left + side, top + side))
        img = img.resize((size, size), Image.Resampling.LANCZOS)
        img.info.clear()  # strip icc_profile / residual metadata before save
        out = io.BytesIO()
        img.save(out, format="PNG", optimize=True)
        return out.getvalue()
    except Image.DecompressionBombError as exc:
        raise UnsupportedMediaError("Image too large (decompression bomb guard).") from exc
    except UnsupportedMediaError:
        raise
    except (OSError, ValueError) as exc:
        raise UnprocessableError("Could not process image.") from exc


async def process_upload(
    settings: Settings, user_id: int, plant_id: int, raw: bytes, declared_mime: str | None = None
) -> str:
    """Validate + process raw upload bytes, write atomically. Returns relative image path.

    ``declared_mime`` (from the request) is informational only — the real check
    is the magic-byte sniff below.
    """
    max_bytes = settings.IMG_MAX_UPLOAD_MB * 1024 * 1024
    if len(raw) > max_bytes:
        raise PayloadTooLargeError(f"Image exceeds {settings.IMG_MAX_UPLOAD_MB} MB.")

    # Trust the magic-byte sniff, not the client-declared content type. Clients legitimately
    # send image/jpg or application/octet-stream for perfectly valid files, so a strict
    # declared==sniffed check rejected good uploads (N39). declared_mime stays informational;
    # everything is re-encoded to PNG below regardless.
    kind = filetype.guess(raw[:262])
    if kind is None or kind.mime not in _ALLOWED_MIME:
        raise UnsupportedMediaError("Only JPEG, PNG or WebP images are accepted.")

    png_bytes = await asyncio.to_thread(
        _process_sync, raw, settings.IMG_SIZE_PX, settings.IMG_MAX_PIXELS
    )

    target = _storage_path(settings, user_id, plant_id)
    target.parent.mkdir(parents=True, exist_ok=True)
    # Unique temp name so concurrent uploads for the same plant don't clobber each other.
    tmp = target.with_name(f"{target.stem}.{uuid.uuid4().hex}.tmp")
    try:
        await asyncio.to_thread(tmp.write_bytes, png_bytes)
        await asyncio.to_thread(os.replace, tmp, target)  # atomic
    except OSError as exc:
        tmp.unlink(missing_ok=True)
        raise UnprocessableError("Could not store image.") from exc

    base = Path(settings.IMAGE_DIR)
    return str(target.relative_to(base.resolve()))


def image_file_path(settings: Settings, user_id: int, plant_id: int) -> Path | None:
    """Resolve the on-disk PNG for serving; None if absent."""
    path = _storage_path(settings, user_id, plant_id)
    return path if path.exists() else None


async def delete_plant_image(settings: Settings, user_id: int, plant_id: int) -> None:
    """Best-effort removal of one plant's stored image.

    Called on soft-delete so deleted plants don't leak their thumbnail on disk (N8). The
    real DELETE only fires after the client-side 5 s undo window, so there is no
    server-side restore to break. Errors are swallowed — a leftover file is harmless.
    """
    path = _storage_path(settings, user_id, plant_id)
    with contextlib.suppress(OSError):
        await asyncio.to_thread(path.unlink, missing_ok=True)


async def delete_user_images(settings: Settings, user_id: int) -> None:
    """Remove the entire per-user image directory (used on account deletion)."""
    user_dir = Path(settings.IMAGE_DIR).resolve() / str(int(user_id))
    if user_dir.exists():
        await asyncio.to_thread(shutil.rmtree, user_dir, ignore_errors=True)
