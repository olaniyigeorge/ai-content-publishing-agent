"""worker/handlers/plan.py — TESTING_FINDINGS.md, 2026-09-16: a Claude plan
response missing 'target_keywords' used to crash with a bare
KeyError('target_keywords'), surfaced to a human as just that string with no
context. require_fields() turns it into a clear, typed PlanningFailed."""

import pytest

from shared.errors import PlanningFailed
from worker.handlers import plan as plan_handler

REQUEST_ID = "00000000-0000-0000-0000-000000000040"


def _seed_request(fake_db):
    fake_db.table("content_requests").insert(
        {"id": REQUEST_ID, "status": "planning", "raw_idea": "an idea", "target_audience": "marketers"}
    ).execute()


def test_plan_missing_target_keywords_raises_clear_error(fake_db, monkeypatch):
    _seed_request(fake_db)
    monkeypatch.setattr(
        plan_handler.claude_service, "build_plan", lambda **kw: {"outline": {"sections": []}}
    )  # target_keywords omitted

    with pytest.raises(PlanningFailed, match="target_keywords"):
        plan_handler.handle_plan({"reference_id": REQUEST_ID, "payload": {}})

    # no half-written plan row, no downstream generate job enqueued
    assert fake_db.table("content_plans").select("*").execute().data == []
    assert fake_db.table("jobs").select("*").execute().data == []


def test_plan_with_all_fields_succeeds(fake_db, monkeypatch):
    _seed_request(fake_db)
    monkeypatch.setattr(
        plan_handler.claude_service,
        "build_plan",
        lambda **kw: {"outline": {"sections": [{"heading": "Intro", "source_ids": []}]}, "target_keywords": ["kw"]},
    )

    plan_handler.handle_plan({"reference_id": REQUEST_ID, "payload": {}})

    assert len(fake_db.table("content_plans").select("*").execute().data) == 1
    jobs = fake_db.table("jobs").select("*").execute().data
    assert any(j["job_type"] == "generate" for j in jobs)
