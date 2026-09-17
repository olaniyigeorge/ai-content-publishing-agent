"""Rewrite-with-AI for an existing draft or channel adaptation: a new
targeted job is enqueued seeded with the current content + instructions,
producing a new version rather than mutating the existing row."""

import pytest

from app.services.adaptation_service import rewrite_channel_adaptation
from app.services.draft_service import rewrite_draft
from shared.errors import ValidationFailure
from worker.handlers import adapt as adapt_handler

REQUEST_ID = "00000000-0000-0000-0000-000000000020"
DRAFT_ID = "00000000-0000-0000-0000-000000000021"
ADAPTATION_ID = "00000000-0000-0000-0000-000000000022"


def _seed_draft(fake_db):
    fake_db.table("content_requests").insert(
        {"id": REQUEST_ID, "status": "queued", "target_audience": "SaaS marketers"}
    ).execute()
    fake_db.table("article_drafts").insert(
        {
            "id": DRAFT_ID,
            "content_request_id": REQUEST_ID,
            "title": "Draft",
            "body_markdown": "# Draft\n\nBody.",
            "version": 1,
            "option_label": "A",
            "source_ids_used": [],
            "status": "evaluated",
        }
    ).execute()


def _seed_adaptation(fake_db):
    _seed_draft(fake_db)
    fake_db.table("channel_adaptations").insert(
        {
            "id": ADAPTATION_ID,
            "content_request_id": REQUEST_ID,
            "article_draft_id": DRAFT_ID,
            "channel": "x",
            "content": "old post",
            "content_format": "plain_text",
            "formatting_check": {},
            "status": "approved",
        }
    ).execute()


def test_rewrite_draft_enqueues_generate_job_and_marks_revising(fake_db):
    _seed_draft(fake_db)

    out = rewrite_draft(DRAFT_ID, "make it punchier")

    jobs = fake_db.table("jobs").select("*").execute().data
    assert len(jobs) == 1
    job = jobs[0]
    assert job["job_type"] == "generate"
    assert job["reference_type"] == "article_draft"
    assert job["reference_id"] == DRAFT_ID
    assert job["payload"]["revision_instructions"] == "make it punchier"
    assert out["job_id"] == job["id"]

    request = fake_db.table("content_requests").select("*").eq("id", REQUEST_ID).execute().data[0]
    assert request["status"] == "revising"


def test_rewrite_draft_carries_forward_the_last_evaluation_reasoning(fake_db):
    """A human's rewrite instruction is additive to the prior evaluation's
    actual findings, not a replacement for them — otherwise a short note
    like "make it punchier" regenerates with no memory of what evaluation
    already flagged as unsupported."""
    _seed_draft(fake_db)
    fake_db.table("evaluations").insert(
        {
            "article_draft_id": DRAFT_ID,
            "rubric_scores": {},
            "overall_score": 2.4,
            "passed_threshold": False,
            "feedback": "leans too hard on one stat",
            "revision_instructions": "cite a second source for the stat",
            "unsupported_claims": ["the 40% figure has no source"],
        }
    ).execute()

    rewrite_draft(DRAFT_ID, "make it punchier")

    job = fake_db.table("jobs").select("*").execute().data[0]
    instructions = job["payload"]["revision_instructions"]
    assert instructions.startswith("make it punchier")
    assert "leans too hard on one stat" in instructions
    assert "40% figure has no source" in instructions
    assert "cite a second source" in instructions


def test_rewrite_draft_without_instructions_uses_default(fake_db):
    _seed_draft(fake_db)
    rewrite_draft(DRAFT_ID, None)
    job = fake_db.table("jobs").select("*").execute().data[0]
    assert "Rewrite" in job["payload"]["revision_instructions"]


def test_rewrite_draft_rejects_when_a_revision_is_already_in_flight(fake_db):
    """TESTING_FINDINGS.md, 2026-09-16: this is the exact race that produced
    'duplicate key value violates unique constraint "article_drafts_version_unique"'
    in manual testing — a rewrite requested while the automatic evaluate loop
    already had a generate job pending for this draft. Both would have
    computed the same next version number; this rejects the second one
    up front instead of letting them race in the database."""
    _seed_draft(fake_db)
    fake_db.table("jobs").insert(
        {
            "job_type": "generate",
            "reference_type": "article_draft",
            "reference_id": DRAFT_ID,
            "status": "pending",
        }
    ).execute()

    with pytest.raises(ValidationFailure, match="already has a revision in progress"):
        rewrite_draft(DRAFT_ID, "make it punchier")

    jobs = fake_db.table("jobs").select("*").execute().data
    assert len(jobs) == 1  # no second job was enqueued


def test_rewrite_draft_allowed_once_prior_revision_job_finished(fake_db):
    _seed_draft(fake_db)
    fake_db.table("jobs").insert(
        {
            "job_type": "generate",
            "reference_type": "article_draft",
            "reference_id": DRAFT_ID,
            "status": "succeeded",
        }
    ).execute()

    rewrite_draft(DRAFT_ID, "make it punchier")  # should not raise

    jobs = fake_db.table("jobs").select("*").execute().data
    assert len(jobs) == 2  # the finished job, plus the new one just enqueued


def test_rewrite_channel_adaptation_enqueues_scoped_adapt_job(fake_db):
    _seed_adaptation(fake_db)

    out = rewrite_channel_adaptation(ADAPTATION_ID, "shorten it")

    jobs = fake_db.table("jobs").select("*").execute().data
    assert len(jobs) == 1
    job = jobs[0]
    assert job["job_type"] == "adapt"
    assert job["reference_type"] == "article_draft"
    assert job["reference_id"] == DRAFT_ID
    assert job["payload"]["channel"] == "x"
    assert job["payload"]["instructions"] == "shorten it"
    assert job["payload"]["previous_content"] == "old post"
    assert out["job_id"] == job["id"]


def test_handle_adapt_rewrite_only_touches_requested_channel(fake_db, monkeypatch):
    """A scoped rewrite job must not re-adapt the other channels, must not
    reset content_requests.status, and must record the resulting content as a
    new channel_adaptations row."""
    _seed_adaptation(fake_db)
    fake_db.table("content_requests").update({"status": "queued"}).eq("id", REQUEST_ID).execute()

    calls = []

    def fake_adapt_for_channel(**kwargs):
        calls.append(kwargs["channel"])
        return {
            "content": "new shorter post",
            "content_format": "plain_text",
            "formatting_check": {"char_count": 16, "within_limit": True, "hashtag_count": 0},
        }

    monkeypatch.setattr(adapt_handler.claude_service, "adapt_for_channel", fake_adapt_for_channel)
    monkeypatch.setattr(
        adapt_handler,
        "check_channel_adaptation",
        lambda **kw: {"within_limit": True, "violations": []},
    )

    job = {
        "reference_id": DRAFT_ID,
        "payload": {"channel": "x", "instructions": "shorten it", "previous_content": "old post"},
    }
    adapt_handler.handle_adapt(job)

    assert calls == ["x"]  # only the requested channel was touched

    adaptations = fake_db.table("channel_adaptations").select("*").eq("channel", "x").execute().data
    assert len(adaptations) == 2  # original + the new rewritten version
    assert any(a["content"] == "new shorter post" for a in adaptations)

    request = fake_db.table("content_requests").select("*").eq("id", REQUEST_ID).execute().data[0]
    assert request["status"] == "queued"  # untouched by the scoped rewrite

    events = fake_db.table("stage_events").select("*").eq("content_request_id", REQUEST_ID).execute().data
    assert any(e["detail"].get("rewrite") is True and e["detail"].get("channel") == "x" for e in events)
