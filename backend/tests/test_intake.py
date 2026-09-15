"""Scenario 1 (raw idea) + scenario 2 (URL-based) + EDGE_CASES.md #1-#4."""

import pytest

from app.services.intake_service import create_content_request
from shared.errors import ValidationFailure
from shared.models import ContentRequestCreate, IntakeAttachmentIn

USER_ID = "00000000-0000-0000-0000-000000000099"


def test_raw_idea_only_request_succeeds(fake_db):
    fake_db.table("users").insert({"id": USER_ID, "email": "a@koyatalent.com"}).execute()
    body = ContentRequestCreate(raw_idea="remote team productivity tips", target_audience="SaaS marketers")
    out = create_content_request(body, submitted_by_user_id=USER_ID)
    assert out.status == "researching"
    jobs = fake_db.table("jobs").select("*").execute().data
    assert len(jobs) == 1 and jobs[0]["job_type"] == "research"


def test_url_attachment_request_is_stored_and_passed_to_research_job(fake_db):
    body = ContentRequestCreate(
        raw_idea="remote team productivity tips",
        target_audience="SaaS marketers",
        attachments=[IntakeAttachmentIn(type="url", url="https://example.com/article")],
    )
    out = create_content_request(body, submitted_by_user_id=USER_ID)
    attachments = (
        fake_db.table("intake_attachments").select("*").eq("content_request_id", str(out.id)).execute().data
    )
    assert len(attachments) == 1 and attachments[0]["url"] == "https://example.com/article"
    job = fake_db.table("jobs").select("*").execute().data[0]
    assert attachments[0]["id"] in job["payload"]["attachment_ids"]


def test_empty_idea_and_no_attachments_is_rejected(fake_db):
    body = ContentRequestCreate(raw_idea=None, target_audience="SaaS marketers")
    with pytest.raises(ValidationFailure):
        create_content_request(body, submitted_by_user_id="u1")


def test_vague_single_character_idea_is_rejected(fake_db):
    body = ContentRequestCreate(raw_idea="x", target_audience="SaaS marketers")
    with pytest.raises(ValidationFailure):
        create_content_request(body, submitted_by_user_id="u1")


def test_missing_target_audience_is_rejected(fake_db):
    body = ContentRequestCreate(raw_idea="a real idea", target_audience="")
    with pytest.raises(ValidationFailure):
        create_content_request(body, submitted_by_user_id="u1")


def test_url_attachment_without_url_is_rejected(fake_db):
    body = ContentRequestCreate(
        raw_idea="a real idea",
        target_audience="SaaS marketers",
        attachments=[IntakeAttachmentIn(type="url", url=None)],
    )
    with pytest.raises(ValidationFailure):
        create_content_request(body, submitted_by_user_id="u1")
