from __future__ import annotations

import uuid
from io import BytesIO

from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from PIL import Image, ImageOps

MAX_IMAGE_BYTES = 10 * 1024 * 1024  # 10 MB
ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP"}
THUMB_MAX = (300, 300)
MEDIUM_MAX = (800, 800)


class ImageRejected(Exception):
    """Raised when upload fails validation."""


def _reject_svg_html(data: bytes) -> None:
    head = data[:512].lower()
    if b"<svg" in head or head.lstrip().startswith(b"<?xml"):
        raise ImageRejected("svg_not_allowed")
    if b"<!doctype html" in head or b"<html" in head:
        raise ImageRejected("html_not_allowed")


def _open_and_validate(data: bytes) -> Image.Image:
    try:
        probe = Image.open(BytesIO(data))
        probe.verify()
    except Exception as exc:
        raise ImageRejected("invalid_image") from exc

    img = Image.open(BytesIO(data))
    if img.format not in ALLOWED_FORMATS:
        raise ImageRejected("unsupported_format")

    # Fix orientation, then drop EXIF by re-encoding.
    img = ImageOps.exif_transpose(img) or img

    if img.format == "JPEG" and img.mode != "RGB":
        img = img.convert("RGB")
    elif img.mode not in ("RGB", "RGBA"):
        img = img.convert("RGBA" if "A" in img.mode else "RGB")

    return img


def _encode_webp(img: Image.Image, max_size: tuple[int, int] | None, quality: int) -> bytes:
    working = img.copy()
    if max_size is not None:
        working.thumbnail(max_size, Image.LANCZOS)
    buf = BytesIO()
    working.save(buf, format="WEBP", quality=quality, method=4)
    return buf.getvalue()


def process_and_save(*, uploaded_file, product_id) -> dict:
    """
    Validate the upload, generate 3 WebP versions, save them to default
    storage (S3/MinIO/InMemory depending on settings), and return metadata.
    """
    if uploaded_file.size > MAX_IMAGE_BYTES:
        raise ImageRejected("file_too_large")

    data = uploaded_file.read()
    if not data:
        raise ImageRejected("empty_file")

    _reject_svg_html(data)
    img = _open_and_validate(data)

    versions = {
        "original": _encode_webp(img, None, 92),
        "medium": _encode_webp(img, MEDIUM_MAX, 85),
        "thumb": _encode_webp(img, THUMB_MAX, 80),
    }

    image_uuid = uuid.uuid4()
    keys: dict[str, str] = {}
    for name, content in versions.items():
        key = f"products/{product_id}/{image_uuid}_{name}.webp"
        default_storage.save(key, ContentFile(content))
        keys[name] = key

    return {
        "storage_key_original": keys["original"],
        "storage_key_medium": keys["medium"],
        "storage_key_thumb": keys["thumb"],
        "width": img.width,
        "height": img.height,
        "byte_size": sum(len(v) for v in versions.values()),
    }
