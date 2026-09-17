"""app/services/request_state_service.py::override_source_status — discarding
a source the current draft actually cites shouldn't just relabel the source
row; the draft may still be presenting content backed by it on screen. This
should trigger a regeneration, not leave a reviewer-rejected source silently
still backing the visible text."""

from app.services import request_state_service
from shared.models import SourceOverrideIn

REQUEST_ID = "00000000-0000-0000-0000-000000000070"
SOURCE_ID = "00000000-0000-0000-0000-000000000071"
DRAFT_ID = "00000000-0000-0000-0000-000000000072"


def _seed(fake_db, *, draft_status="evaluated", source_ids_used=None):
    fake_db.table("content_requests").insert(
        {"id": REQUEST_ID, "target_audience": "marketers", "status": "in_review"}
    ).execute()
    fake_db.table("sources").insert(
        {
            "id": SOURCE_ID,
            "content_request_id": REQUEST_ID,
            "intake_attachment_id": None,
            "url": "https://example.com/a",
            "title": None,
            "excerpt_selected": None,
            "relevance_notes": None,
            "retrieval_method": "web_search",
            "status": "selected",
            "retrieved_at": None,
        }
    ).execute()
    fake_db.table("article_drafts").insert(
        {
            "id": DRAFT_ID,
            "content_request_id": REQUEST_ID,
            "title": "Draft",
            "body_markdown": "body",
            "version": 1,
            "option_label": "A",
            "source_ids_used": source_ids_used if source_ids_used is not None else [SOURCE_ID],
            "status": draft_status,
        }
    ).execute()


def test_discarding_a_source_the_reviewable_draft_used_triggers_regeneration(fake_db):
    _seed(fake_db)

    request_state_service.override_source_status(
        REQUEST_ID, SOURCE_ID, SourceOverrideIn(status="discarded", reason="not trustworthy enough")
    )

    source = fake_db.table("sources").select("*").eq("id", SOURCE_ID).execute().data[0]
    assert source["status"] == "discarded"
    assert source["discard_reason"] == "not trustworthy enough"

    jobs = fake_db.table("jobs").select("*").execute().data
    assert any(
        j["job_type"] == "generate" and j["reference_id"] == DRAFT_ID and j["reference_type"] == "article_draft"
        for j in jobs
    )
    assert "not trustworthy enough" in jobs[0]["payload"]["revision_instructions"]
    request = fake_db.table("content_requests").select("*").eq("id", REQUEST_ID).execute().data[0]
    assert request["status"] == "revising"


def test_discarding_a_source_not_used_by_any_draft_does_not_enqueue_anything(fake_db):
    _seed(fake_db, source_ids_used=["00000000-0000-0000-0000-000000000099"])

    request_state_service.override_source_status(REQUEST_ID, SOURCE_ID, SourceOverrideIn(status="discarded"))

    jobs = fake_db.table("jobs").select("*").execute().data
    assert jobs == []


def test_discarding_a_source_used_only_by_a_non_reviewable_draft_does_not_enqueue(fake_db):
    """The draft is mid-generation (still 'draft' status, not yet
    evaluated) — queuing a second revision against it would race the one
    already in flight, same class of bug job_guard already protects
    against."""
    _seed(fake_db, draft_status="draft")

    request_state_service.override_source_status(REQUEST_ID, SOURCE_ID, SourceOverrideIn(status="discarded"))

    jobs = fake_db.table("jobs").select("*").execute().data
    assert jobs == []


def test_marking_a_source_selected_again_does_not_trigger_regeneration(fake_db):
    _seed(fake_db)
    fake_db.table("sources").update({"status": "discarded", "discard_reason": "x"}).eq("id", SOURCE_ID).execute()

    request_state_service.override_source_status(REQUEST_ID, SOURCE_ID, SourceOverrideIn(status="selected"))

    jobs = fake_db.table("jobs").select("*").execute().data
    assert jobs == []
    source = fake_db.table("sources").select("*").eq("id", SOURCE_ID).execute().data[0]
    assert source["discard_reason"] is None
