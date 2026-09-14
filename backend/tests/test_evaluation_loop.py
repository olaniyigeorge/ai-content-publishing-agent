"""Scenario 4 + EDGE_CASES.md #17, #24, #65 — the evaluate->generate loop,
the revision cap, and version lineage, exercised against handle_evaluate
directly with a faked Claude response (no live API call)."""

from app.config import get_settings
from worker.handlers import evaluate as evaluate_handler

REQUEST_ID = "00000000-0000-0000-0000-000000000010"
DRAFT_ID = "00000000-0000-0000-0000-000000000011"


def _seed_draft(fake_db, version=1):
    fake_db.table("content_requests").insert(
        {"id": REQUEST_ID, "status": "evaluating", "target_audience": "SaaS marketers"}
    ).execute()
    fake_db.table("article_drafts").insert(
        {
            "id": DRAFT_ID,
            "content_request_id": REQUEST_ID,
            "title": "Draft",
            "body_markdown": "body",
            "version": version,
            "option_label": "A",
            "source_ids_used": [],
            "status": "draft",
        }
    ).execute()


def _fail_result():
    return {
        "overall_status": "revise",
        "rubric_scores": {},
        "overall_score": 2.0,
        "unsupported_claims": ["invented stat"],
        "sections_to_revise": ["intro"],
        "recommended_changes": ["lead with a real stat"],
        "feedback": "weak",
    }


def test_failing_evaluation_below_cap_enqueues_another_generate(fake_db, monkeypatch):
    _seed_draft(fake_db, version=1)
    monkeypatch.setattr(evaluate_handler.claude_service, "evaluate_draft", lambda **kw: _fail_result())

    job = {"reference_id": DRAFT_ID, "payload": {}}
    evaluate_handler.handle_evaluate(job)

    jobs = fake_db.table("jobs").select("*").execute().data
    assert any(j["job_type"] == "generate" for j in jobs)
    draft = fake_db.table("article_drafts").select("*").eq("id", DRAFT_ID).execute().data[0]
    assert draft["status"] == "draft"  # not yet marked evaluated — still cycling


def test_failing_evaluation_at_cap_stops_the_loop_and_goes_to_review(fake_db, monkeypatch):
    settings = get_settings()
    _seed_draft(fake_db, version=settings.max_revisions)
    monkeypatch.setattr(evaluate_handler.claude_service, "evaluate_draft", lambda **kw: _fail_result())

    job = {"reference_id": DRAFT_ID, "payload": {}}
    evaluate_handler.handle_evaluate(job)

    jobs = fake_db.table("jobs").select("*").execute().data
    assert not any(j["job_type"] == "generate" for j in jobs)  # loop stopped, no infinite cycling
    draft = fake_db.table("article_drafts").select("*").eq("id", DRAFT_ID).execute().data[0]
    assert draft["status"] == "evaluated"  # still reaches human review, flagged as failed
    events = fake_db.table("stage_events").select("*").eq("content_request_id", REQUEST_ID).execute().data
    assert any(e["status"] == "failed" and "cap" in (e.get("error_message") or "") for e in events)


def test_passing_evaluation_marks_draft_evaluated_no_further_generate(fake_db, monkeypatch):
    _seed_draft(fake_db, version=2)
    pass_result = {
        "overall_status": "pass",
        "rubric_scores": {},
        "overall_score": 4.8,
        "unsupported_claims": [],
        "sections_to_revise": [],
        "recommended_changes": [],
        "feedback": "great",
    }
    monkeypatch.setattr(evaluate_handler.claude_service, "evaluate_draft", lambda **kw: pass_result)

    evaluate_handler.handle_evaluate({"reference_id": DRAFT_ID, "payload": {}})

    jobs = fake_db.table("jobs").select("*").execute().data
    assert not any(j["job_type"] == "generate" for j in jobs)
    draft = fake_db.table("article_drafts").select("*").eq("id", DRAFT_ID).execute().data[0]
    assert draft["status"] == "evaluated"
