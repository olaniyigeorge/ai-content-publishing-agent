"""Intake asset uploads — images/files a content manager attaches to a
request (chart screenshots, PDFs, etc.) alongside a raw idea or source URL.

Stored in Supabase Storage under a fixed bucket (see BUCKET). The bucket
itself isn't created here — it's provisioned once out-of-band (Supabase
dashboard or `supabase storage` CLI), since bucket creation is an infra
change, not a per-request operation.
"""

import mimetypes
import re
import uuid

from db.client import get_supabase
from shared.errors import ValidationFailure

BUCKET = "content-assets"

MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB

ALLOWED_CONTENT_TYPES = {
    "image/png",
    "image/jpeg",
    "image/webp",
    "image/gif",
    "application/pdf",
    "text/plain",
    "text/csv",
}

_SAFE_NAME_RE = re.compile(r"[^A-Za-z0-9._-]+")


def _sanitize_filename(filename: str) -> str:
    name = filename.strip().replace(" ", "-")
    name = _SAFE_NAME_RE.sub("", name)
    name = re.sub(r"\.{2,}", ".", name).lstrip(".") or "upload"
    return name[-100:]  # keep it short regardless of what the client sent


def upload_intake_asset(*, filename: str, content_type: str | None, data: bytes) -> dict:
    """Returns {"storage_path": str, "url": str, "content_type": str, "size": int}."""
    if len(data) == 0:
        raise ValidationFailure("uploaded file is empty")
    if len(data) > MAX_UPLOAD_BYTES:
        raise ValidationFailure(f"file is too large ({len(data)} bytes, max {MAX_UPLOAD_BYTES})")

    resolved_type = content_type or mimetypes.guess_type(filename)[0] or "application/octet-stream"
    if resolved_type not in ALLOWED_CONTENT_TYPES:
        raise ValidationFailure(
            f"file type '{resolved_type}' isn't supported — allowed: {', '.join(sorted(ALLOWED_CONTENT_TYPES))}"
        )

    storage_path = f"{uuid.uuid4()}/{_sanitize_filename(filename)}"

    db = get_supabase()
    db.storage.from_(BUCKET).upload(
        storage_path,
        data,
        file_options={"content-type": resolved_type},
    )
    public_url = db.storage.from_(BUCKET).get_public_url(storage_path)

    return {
        "storage_path": storage_path,
        "url": public_url,
        "content_type": resolved_type,
        "size": len(data),
    }
