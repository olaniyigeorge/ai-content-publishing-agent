"""Scenario 4 + EDGE_CASES.md #17, #24, #65 — the evaluate->generate loop,
the revision cap, and version lineage, exercised against handle_evaluate
directly with a faked Claude response (no live API call)."""

import pytest

from app.config import get_settings
from shared.errors import DraftEvaluationFailed
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


def test_ungroundable_draft_with_no_source_url_triggers_gap_fill_research(fake_db, monkeypatch):
    """A draft with zero source_ids_used and a floor source_grounding score
    can't be fixed by revising the wording alone — but if nobody gave this
    request a source URL, the system gets one more capped chance to search
    again (aimed at what the evaluation just flagged) before giving up on
    grounding and escalating to a human."""
    settings = get_settings()
    assert settings.max_gap_fill_attempts > 0
    _seed_draft(fake_db, version=1)
    ungroundable_result = {
        "overall_status": "revise",
        "rubric_scores": {"source_grounding": 1, "topic_relevance": 4},
        "overall_score": 2.4,
        "unsupported_claims": ["a claim with no source"],
        "sections_to_revise": ["body"],
        "recommended_changes": ["cite a source"],
        "feedback": "no source material to ground this in",
    }
    monkeypatch.setattr(evaluate_handler.claude_service, "evaluate_draft", lambda **kw: ungroundable_result)

    evaluate_handler.handle_evaluate({"reference_id": DRAFT_ID, "payload": {}})

    jobs = fake_db.table("jobs").select("*").execute().data
    assert not any(j["job_type"] == "generate" for j in jobs)  # not revised directly
    assert any(
        j["job_type"] == "research" and j["payload"].get("gap_fill_for_draft_id") == DRAFT_ID for j in jobs
    )
    draft = fake_db.table("article_drafts").select("*").eq("id", DRAFT_ID).execute().data[0]
    assert draft["status"] == "draft"  # not finalized yet — waiting on the gap-fill search
    request = fake_db.table("content_requests").select("*").eq("id", REQUEST_ID).execute().data[0]
    assert request["gap_fill_attempts"] == 1
    assert request["status"] == "researching"


def test_ungroundable_draft_escalates_once_gap_fill_attempts_are_exhausted(fake_db, monkeypatch):
    """Gap-fill is capped — once a request has already used up its
    attempts, an ungroundable draft goes straight to human review exactly
    as before this feature existed, instead of searching forever."""
    settings = get_settings()
    _seed_draft(fake_db, version=1)
    fake_db.table("content_requests").update({"gap_fill_attempts": settings.max_gap_fill_attempts}).eq(
        "id", REQUEST_ID
    ).execute()
    ungroundable_result = {
        "overall_status": "revise",
        "rubric_scores": {"source_grounding": 1, "topic_relevance": 4},
        "overall_score": 2.4,
        "unsupported_claims": ["a claim with no source"],
        "sections_to_revise": ["body"],
        "recommended_changes": ["cite a source"],
        "feedback": "no source material to ground this in",
    }
    monkeypatch.setattr(evaluate_handler.claude_service, "evaluate_draft", lambda **kw: ungroundable_result)

    evaluate_handler.handle_evaluate({"reference_id": DRAFT_ID, "payload": {}})

    jobs = fake_db.table("jobs").select("*").execute().data
    assert not any(j["job_type"] in ("generate", "research") for j in jobs)  # exhausted, not retried again
    draft = fake_db.table("article_drafts").select("*").eq("id", DRAFT_ID).execute().data[0]
    assert draft["status"] == "evaluated"  # sent to human review, not stuck at "draft"
    events = fake_db.table("stage_events").select("*").eq("content_request_id", REQUEST_ID).execute().data
    assert any(
        e["status"] == "failed" and "can't fix" in (e.get("error_message") or "") for e in events
    )


def test_ungroundable_draft_with_a_source_url_skips_gap_fill_and_escalates(fake_db, monkeypatch):
    """If the content manager already gave a source URL, the explicit-source
    path already ran — searching the open web on top of an explicit source
    that turned out unusable isn't the same recovery, so this still goes
    straight to human review rather than gap-filling."""
    _seed_draft(fake_db, version=1)
    fake_db.table("intake_attachments").insert(
        {"id": "00000000-0000-0000-0000-000000000020", "content_request_id": REQUEST_ID, "type": "url"}
    ).execute()
    ungroundable_result = {
        "overall_status": "revise",
        "rubric_scores": {"source_grounding": 1, "topic_relevance": 4},
        "overall_score": 2.4,
        "unsupported_claims": ["a claim with no source"],
        "sections_to_revise": ["body"],
        "recommended_changes": ["cite a source"],
        "feedback": "no source material to ground this in",
    }
    monkeypatch.setattr(evaluate_handler.claude_service, "evaluate_draft", lambda **kw: ungroundable_result)

    evaluate_handler.handle_evaluate({"reference_id": DRAFT_ID, "payload": {}})

    jobs = fake_db.table("jobs").select("*").execute().data
    assert not any(j["job_type"] in ("generate", "research") for j in jobs)
    draft = fake_db.table("article_drafts").select("*").eq("id", DRAFT_ID).execute().data[0]
    assert draft["status"] == "evaluated"


def test_low_source_grounding_with_real_sources_still_revises_normally(fake_db, monkeypatch):
    """The guard is specifically about *zero* sources — a low score with
    actual source_ids_used means the draft just did a poor job grounding in
    material that does exist, which revising the wording genuinely can fix."""
    fake_db.table("content_requests").insert(
        {"id": REQUEST_ID, "status": "evaluating", "target_audience": "SaaS marketers"}
    ).execute()
    fake_db.table("article_drafts").insert(
        {
            "id": DRAFT_ID,
            "content_request_id": REQUEST_ID,
            "title": "Draft",
            "body_markdown": _VALID_BODY,
            "version": 1,
            "option_label": "A",
            "source_ids_used": ["00000000-0000-0000-0000-000000000099"],
            "status": "draft",
        }
    ).execute()
    low_grounding_result = {
        "overall_status": "revise",
        "rubric_scores": {"source_grounding": 1},
        "overall_score": 2.4,
        "unsupported_claims": ["a claim not tied to the excerpt"],
        "sections_to_revise": ["body"],
        "recommended_changes": ["tie the claim back to the source excerpt"],
        "feedback": "has a source but doesn't use it",
    }
    monkeypatch.setattr(evaluate_handler.claude_service, "evaluate_draft", lambda **kw: low_grounding_result)

    evaluate_handler.handle_evaluate({"reference_id": DRAFT_ID, "payload": {}})

    jobs = fake_db.table("jobs").select("*").execute().data
    assert any(j["job_type"] == "generate" for j in jobs)  # normal revision loop, not short-circuited


def test_thin_only_sources_with_no_source_url_trigger_gap_fill(fake_db, monkeypatch):
    """A draft that DOES have source_ids_used, but every one of them is a
    thin, weak, autonomously-found source (not zero sources — is_ungroundable
    alone wouldn't catch this) should still get a gap-fill search rather than
    just cycling revisions against wording that can't manufacture stronger
    evidence."""
    fake_db.table("content_requests").insert(
        {"id": REQUEST_ID, "status": "evaluating", "target_audience": "SaaS marketers"}
    ).execute()
    fake_db.table("sources").insert(
        {
            "id": "00000000-0000-0000-0000-000000000099",
            "content_request_id": REQUEST_ID,
            "url": "https://example.com/thin-blog-post",
            "retrieval_method": "web_search",
            "status": "selected",
            "confidence": "thin",
            "confidence_reason": "single personal blog post, no data or citations",
        }
    ).execute()
    fake_db.table("article_drafts").insert(
        {
            "id": DRAFT_ID,
            "content_request_id": REQUEST_ID,
            "title": "Draft",
            "body_markdown": _VALID_BODY,
            "version": 1,
            "option_label": "A",
            "source_ids_used": ["00000000-0000-0000-0000-000000000099"],
            "status": "draft",
        }
    ).execute()
    weak_but_present_result = {
        "overall_status": "revise",
        "rubric_scores": {"source_grounding": 2},
        "overall_score": 2.6,
        "unsupported_claims": ["a claim only loosely tied to the thin source"],
        "sections_to_revise": ["body"],
        "recommended_changes": ["find stronger support or hedge the claim"],
        "feedback": "only thin evidence available",
    }
    monkeypatch.setattr(evaluate_handler.claude_service, "evaluate_draft", lambda **kw: weak_but_present_result)

    evaluate_handler.handle_evaluate({"reference_id": DRAFT_ID, "payload": {}})

    jobs = fake_db.table("jobs").select("*").execute().data
    assert any(j["job_type"] == "research" and j["payload"].get("gap_fill_for_draft_id") == DRAFT_ID for j in jobs)
    assert not any(j["job_type"] == "generate" for j in jobs)


def test_model_claimed_pass_is_overridden_by_unsupported_claims(fake_db, monkeypatch):
    """The evaluate prompt asks the model to only say 'pass' when
    unsupported_claims is empty, but that's an instruction, not a
    guarantee — this enforces it server-side so a confidently-worded 'pass'
    can't carry an unresolved unsupported claim through to a human reviewer
    as if the content were fully backed."""
    _seed_draft(fake_db, version=1)
    inconsistent_pass = {
        "overall_status": "pass",
        "rubric_scores": {},
        "overall_score": 4.8,
        "unsupported_claims": ["a stat with no source behind it"],
        "sections_to_revise": [],
        "recommended_changes": [],
        "feedback": "looks great",
    }
    monkeypatch.setattr(evaluate_handler.claude_service, "evaluate_draft", lambda **kw: inconsistent_pass)

    evaluate_handler.handle_evaluate({"reference_id": DRAFT_ID, "payload": {}})

    evaluations = fake_db.table("evaluations").select("*").execute().data
    assert evaluations[0]["passed_threshold"] is False
    assert "[unsupported claim]" in evaluations[0]["revision_instructions"]
    jobs = fake_db.table("jobs").select("*").execute().data
    assert any(j["job_type"] == "generate" for j in jobs)  # sent back for revision, not approved as-is


def test_evaluation_missing_overall_score_raises_clear_error(fake_db, monkeypatch):
    """TESTING_FINDINGS.md, 2026-09-16: a Claude evaluation response missing
    'overall_score' used to crash with a bare KeyError('overall_score'). This
    is exactly that response shape."""
    _seed_draft(fake_db, version=1)
    incomplete_result = {
        "overall_status": "revise",
        "rubric_scores": {},
        "unsupported_claims": [],
        "sections_to_revise": [],
        "recommended_changes": [],
        "feedback": "fine",
    }  # overall_score omitted
    monkeypatch.setattr(evaluate_handler.claude_service, "evaluate_draft", lambda **kw: incomplete_result)

    with pytest.raises(DraftEvaluationFailed, match="overall_score"):
        evaluate_handler.handle_evaluate({"reference_id": DRAFT_ID, "payload": {}})

    # no half-written evaluation row, draft untouched
    assert fake_db.table("evaluations").select("*").execute().data == []


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
