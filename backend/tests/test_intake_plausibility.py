"""The Claude-backed second layer behind intake_guards.py's free checks —
catches near-misses that beat the deterministic gibberish heuristic (one
vowel + a few whitespace-separated tokens sails through it, see
EDGE_CASES.md) before a research/plan/draft/evaluate run gets spent on it.
Fails open on any error, since this is a cost-saving pre-check, not a
correctness guarantee — a Claude/network hiccup must never block a real
submission.
"""

import app.services.intake_service as intake_service
from app.services.intake_service import create_content_request
from shared.errors import ValidationFailure
from shared.models import ContentRequestCreate

import pytest

USER_ID = "00000000-0000-0000-0000-000000000099"


def test_near_miss_gibberish_that_passes_deterministic_checks_is_rejected(fake_db, monkeypatch):
    monkeypatch.setattr(
        intake_service.claude_service,
        "check_intake_plausibility",
        lambda **kw: {"plausible": False, "reason": "no discernible topic — reads as random text"},
    )
    # Three whitespace-separated tokens, each containing a vowel — passes
    # intake_guards.py's word-count and no-vowel checks, but is still gibberish.
    body = ContentRequestCreate(raw_idea="hsvnosv fownvor sfnovo", target_audience="cnrvo cwnovrw fcowrn")
    with pytest.raises(ValidationFailure, match="no discernible topic"):
        create_content_request(body, submitted_by_user_id=USER_ID)
    assert fake_db.table("content_requests").select("*").execute().data == []


def test_plausible_idea_proceeds_to_research(fake_db, monkeypatch):
    monkeypatch.setattr(
        intake_service.claude_service,
        "check_intake_plausibility",
        lambda **kw: {"plausible": True, "reason": "a real topic about remote work productivity"},
    )
    body = ContentRequestCreate(raw_idea="remote team productivity tips", target_audience="SaaS marketers")
    out = create_content_request(body, submitted_by_user_id=USER_ID)
    assert out.status == "researching"


def test_check_failure_fails_open_and_does_not_block_submission(fake_db, monkeypatch):
    def _boom(**kw):
        raise RuntimeError("simulated API/network failure")

    monkeypatch.setattr(intake_service.claude_service, "check_intake_plausibility", _boom)
    body = ContentRequestCreate(raw_idea="remote team productivity tips", target_audience="SaaS marketers")
    out = create_content_request(body, submitted_by_user_id=USER_ID)
    assert out.status == "researching"


def test_missing_fields_in_response_fails_open(fake_db, monkeypatch):
    monkeypatch.setattr(
        intake_service.claude_service,
        "check_intake_plausibility",
        lambda **kw: {"plausible": True},  # missing "reason"
    )
    body = ContentRequestCreate(raw_idea="remote team productivity tips", target_audience="SaaS marketers")
    out = create_content_request(body, submitted_by_user_id=USER_ID)
    assert out.status == "researching"
