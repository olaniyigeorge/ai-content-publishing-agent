"""Scenario 4 + EDGE_CASES.md #17, #24, #65 — the evaluate->generate loop,
the revision cap, and version lineage, exercised against handle_evaluate
directly with a faked Claude response (no live API call)."""

from app.config import get_settings
from worker.handlers import evaluate as evaluate_handler

REQUEST_ID = "00000000-0000-0000-0000-000000000010"
DRAFT_ID = "00000000-0000-0000-0000-000000000011"


_VALID_BODY = (
    "# A Real Article Title\n\n"
    + "This is a well-formed paragraph of the article body. " * 60
    + "\n\nSee the [source](https://example.com/source) for more.\n"
)


def _seed_draft(fake_db, version=1, body_markdown=_VALID_BODY):
    fake_db.table("content_requests").insert(
        {"id": REQUEST_ID, "status": "evaluating", "target_audience": "SaaS marketers"}
    ).execute()
    fake_db.table("article_drafts").insert(
        {
            "id": DRAFT_ID,
            "content_request_id": REQUEST_ID,
            "title": "Draft",
            "body_markdown": body_markdown,
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


def test_model_claimed_pass_is_overridden_by_hard_length_guard(fake_db, monkeypatch):
    """claude/quality_guards.py: a rubric 'pass' can't rescue a draft that's
    objectively too short / missing an H1 — the model's self-assessment
    isn't trusted on its own."""
    _seed_draft(fake_db, version=1, body_markdown="too short, no heading, no links")
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

    evaluations = fake_db.table("evaluations").select("*").execute().data
    assert evaluations[0]["passed_threshold"] is False
    assert "[hard guard]" in evaluations[0]["revision_instructions"]
    jobs = fake_db.table("jobs").select("*").execute().data
    assert any(j["job_type"] == "generate" for j in jobs)  # sent back for revision, not straight to review
