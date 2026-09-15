"""API-level tests for the publishing-queue list/status endpoints — the list
response used to be bare `publishing_queue` rows with no channel, content, or
title, which made the publishing queue page unusable (EDGE_CASES / UX
feedback: "what is the essence of a publishing queue page if I can't see the
channel, the post title, ... and flip the status"). These cover the join-based
enrichment in app/api/publishing.py and the new manual status override."""

from fastapi.testclient import TestClient

from app.main import app
from auth.deps import get_current_user

ADAPTATION_ID = "00000000-0000-0000-0000-000000000030"
DRAFT_ID = "00000000-0000-0000-0000-000000000031"
QUEUE_ID = "00000000-0000-0000-0000-000000000032"
REQUEST_ID = "00000000-0000-0000-0000-000000000033"


def _seed(fake_db):
    fake_db.table("content_requests").insert(
        {"id": REQUEST_ID, "status": "queued", "target_audience": "SaaS marketers"}
    ).execute()
    fake_db.table("article_drafts").insert(
        {"id": DRAFT_ID, "content_request_id": REQUEST_ID, "title": "Why observability matters"}
    ).execute()
    fake_db.table("channel_adaptations").insert(
        {
            "id": ADAPTATION_ID,
            "content_request_id": REQUEST_ID,
            "article_draft_id": DRAFT_ID,
            "channel": "x",
            "content": "a normal x post",
            "content_format": "plain_text",
            "formatting_check": {"within_limit": True},
            "status": "approved",
        }
    ).execute()
    fake_db.table("publishing_queue").insert(
        {
            "id": QUEUE_ID,
            "channel_adaptation_id": ADAPTATION_ID,
            "status": "queued",
            "attempts": 0,
            "max_attempts": 3,
            "scheduled_for": None,
            "last_error": None,
            "next_attempt_at": None,
            "published_at": None,
            "updated_at": "2026-09-15T00:00:00+00:00",
        }
    ).execute()


def _client():
    app.dependency_overrides[get_current_user] = lambda: {"id": "00000000-0000-0000-0000-0000000000ff"}
    client = TestClient(app)
    return client


def test_list_queue_is_enriched_with_channel_title_and_content(fake_db):
    _seed(fake_db)
    client = _client()
    try:
        resp = client.get("/api/publishing-queue")
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    assert resp.status_code == 200
    row = resp.json()[0]
    assert row["channel"] == "x"
    assert row["content"] == "a normal x post"
    assert row["article_title"] == "Why observability matters"
    assert row["content_request_id"] == REQUEST_ID
    assert row["failure_reason"] is None


def test_patch_status_manually_marks_published(fake_db):
    _seed(fake_db)
    client = _client()
    try:
        resp = client.patch(f"/api/publishing-queue/{QUEUE_ID}/status", json={"status": "published"})
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "published"
    assert body["published_at"] is not None

    row = fake_db.table("publishing_queue").select("*").eq("id", QUEUE_ID).execute().data[0]
    assert row["status"] == "published"


def test_patch_status_rejects_unknown_status(fake_db):
    _seed(fake_db)
    client = _client()
    try:
        resp = client.patch(f"/api/publishing-queue/{QUEUE_ID}/status", json={"status": "processing"})
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    assert resp.status_code == 409
