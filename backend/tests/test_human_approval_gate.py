"""Scenario 5 + EDGE_CASES.md #27, #28, #30."""

import pytest

from app.services.review_service import submit_review
from shared.errors import InvalidStateTransition
from shared.models import HumanReviewIn

REQUEST_ID = "00000000-0000-0000-0000-000000000001"
DRAFT_ID = "00000000-0000-0000-0000-000000000002"


def _seed_evaluated_draft(fake_db, status="evaluated"):
    fake_db.table("content_requests").insert({"id": REQUEST_ID, "status": "in_review"}).execute()
    fake_db.table("article_drafts").insert(
        {"id": DRAFT_ID, "content_request_id": REQUEST_ID, "status": status, "option_label": "A", "version": 1}
    ).execute()


def test_approval_enqueues_adapt_job(fake_db):
    _seed_evaluated_draft(fake_db)
    out = submit_review(
        REQUEST_ID, HumanReviewIn(article_draft_id=DRAFT_ID, decision="approved"), reviewer_user_id="00000000-0000-0000-0000-000000000091"
    )
    assert out.decision == "approved"
    jobs = fake_db.table("jobs").select("*").execute().data
    assert any(j["job_type"] == "adapt" for j in jobs)
    draft = fake_db.table("article_drafts").select("*").eq("id", DRAFT_ID).execute().data[0]
    assert draft["status"] == "selected"


def test_no_review_means_no_adapt_job(fake_db):
    _seed_evaluated_draft(fake_db)
    jobs = fake_db.table("jobs").select("*").execute().data
    assert not any(j["job_type"] == "adapt" for j in jobs)


def test_option_selected_does_not_enqueue_adapt(fake_db):
    _seed_evaluated_draft(fake_db)
    submit_review(
        REQUEST_ID, HumanReviewIn(article_draft_id=DRAFT_ID, decision="option_selected"), reviewer_user_id="00000000-0000-0000-0000-000000000091"
    )
    jobs = fake_db.table("jobs").select("*").execute().data
    assert not any(j["job_type"] == "adapt" for j in jobs)


def test_reviewing_a_draft_not_yet_evaluated_is_rejected(fake_db):
    _seed_evaluated_draft(fake_db, status="draft")
    with pytest.raises(InvalidStateTransition):
        submit_review(REQUEST_ID, HumanReviewIn(article_draft_id=DRAFT_ID, decision="approved"), reviewer_user_id="00000000-0000-0000-0000-000000000091")


def test_second_review_after_a_terminal_decision_is_rejected(fake_db):
    _seed_evaluated_draft(fake_db)
    submit_review(REQUEST_ID, HumanReviewIn(article_draft_id=DRAFT_ID, decision="approved"), reviewer_user_id="00000000-0000-0000-0000-000000000091")
    with pytest.raises(InvalidStateTransition):
        submit_review(REQUEST_ID, HumanReviewIn(article_draft_id=DRAFT_ID, decision="approved"), reviewer_user_id="00000000-0000-0000-0000-000000000092")


def test_revise_requested_enqueues_generate_job_with_notes(fake_db):
    _seed_evaluated_draft(fake_db)
    submit_review(
        REQUEST_ID,
        HumanReviewIn(article_draft_id=DRAFT_ID, decision="revise_requested", notes="lead with the stat"),
        reviewer_user_id="00000000-0000-0000-0000-000000000091",
    )
    jobs = fake_db.table("jobs").select("*").execute().data
    generate_jobs = [j for j in jobs if j["job_type"] == "generate"]
    assert len(generate_jobs) == 1
    assert generate_jobs[0]["payload"]["revision_instructions"] == "lead with the stat"
