"""app/services/upload_service.py — size/type guards for intake asset
uploads (images, PDFs) referenced from IntakeAttachmentIn(type='image'/'file')."""

import pytest

from app.services import upload_service
from shared.errors import ValidationFailure


class _FakeBucket:
    def __init__(self):
        self.uploaded = None

    def upload(self, path, data, file_options=None):
        self.uploaded = (path, data, file_options)
        return {"path": path}

    def get_public_url(self, path):
        return f"https://fake.supabase.co/storage/v1/object/public/intake-media/{path}"


class _FakeStorage:
    def __init__(self):
        self.bucket = _FakeBucket()

    def from_(self, _bucket_name):
        return self.bucket


class _FakeClient:
    def __init__(self):
        self.storage = _FakeStorage()


def test_empty_file_is_rejected():
    with pytest.raises(ValidationFailure, match="empty"):
        upload_service.upload_intake_asset(filename="a.png", content_type="image/png", data=b"")


def test_oversized_file_is_rejected():
    data = b"x" * (upload_service.MAX_UPLOAD_BYTES + 1)
    with pytest.raises(ValidationFailure, match="too large"):
        upload_service.upload_intake_asset(filename="a.png", content_type="image/png", data=data)


def test_disallowed_content_type_is_rejected():
    with pytest.raises(ValidationFailure, match="isn't supported"):
        upload_service.upload_intake_asset(
            filename="script.sh", content_type="application/x-sh", data=b"#!/bin/sh\n"
        )


def test_valid_image_upload_succeeds_and_returns_public_url(monkeypatch):
    fake_client = _FakeClient()
    monkeypatch.setattr(upload_service, "get_supabase", lambda: fake_client)

    result = upload_service.upload_intake_asset(filename="chart.png", content_type="image/png", data=b"\x89PNG...")

    assert result["content_type"] == "image/png"
    assert result["size"] == len(b"\x89PNG...")
    assert result["storage_path"].endswith("chart.png")
    assert result["url"].endswith(result["storage_path"])
    assert fake_client.storage.bucket.uploaded[0] == result["storage_path"]


def test_filename_is_sanitized(monkeypatch):
    fake_client = _FakeClient()
    monkeypatch.setattr(upload_service, "get_supabase", lambda: fake_client)

    result = upload_service.upload_intake_asset(
        filename="../../etc/passwd; rm -rf.png", content_type="image/png", data=b"data"
    )

    assert ".." not in result["storage_path"]
    assert ";" not in result["storage_path"]
