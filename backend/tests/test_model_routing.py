"""Per-step model routing (claude/models.py) and the escalate-to-Opus path
for regenerations that follow a fundamental reasoning/source-interpretation
failure (worker/handlers/evaluate.py), not just weak wording."""

from claude.models import HAIKU, MODEL_FOR_STEP, OPUS, SONNET, model_for
from claude.pricing import PRICE_PER_MILLION_USD, cost_usd
from shared.enums import JobType
from worker.handlers import evaluate as evaluate_handler

REQUEST_ID = "00000000-0000-0000-0000-000000000040"
DRAFT_ID = "00000000-0000-0000-0000-000000000041"
SOURCE_ID = "00000000-0000-0000-0000-000000000042"

_VALID_BODY = (
    "# A Real Article Title\n\n"
    + "This is a well-formed paragraph of the article body. " * 60
    + "\n\nSee the [source](https://example.com/source) for more.\n"
)


def test_step_routing_matches_the_agreed_tiering():
    assert model_for(JobType.RESEARCH) == SONNET
    assert model_for(JobType.PLAN) == SONNET
    assert model_for(JobType.GENERATE) == SONNET
    assert model_for(JobType.EVALUATE) == OPUS
    assert model_for(JobType.ADAPT) == HAIKU
    assert set(MODEL_FOR_STEP) == set(JobType) - {JobType.PUBLISH}


def test_opus_has_a_pricing_entry_so_usage_isnt_recorded_as_free():
    assert OPUS in PRICE_PER_MILLION_USD
    cost = cost_usd(model=OPUS, input_tokens=1_000_000, output_tokens=1_000_000)
    assert cost == PRICE_PER_MILLION_USD[OPUS]["input"] + PRICE_PER_MILLION_USD[OPUS]["output"]
    assert cost > 0


def _seed_draft(fake_db, *, source_ids_used, version=1):
    fake_db.table("content_requests").insert(
        {"id": REQUEST_ID, "status": "evaluating", "target_audience": "SaaS marketers"}
    ).execute()
    if source_ids_used:
        fake_db.table("sources").insert(
            {
                "id": SOURCE_ID,
                "content_request_id": REQUEST_ID,
                "url": "https://example.com/real-source",
                "retrieval_method": "url_provided",
                "status": "selected",
                "confidence": "strong",
            }
        ).execute()
    fake_db.table("article_drafts").insert(
        {
            "id": DRAFT_ID,
            "content_request_id": REQUEST_ID,
            "title": "Draft",
            "body_markdown": _VALID_BODY,
            "version": version,
            "option_label": "A",
            "source_ids_used": source_ids_used,
            "status": "draft",
        }
    ).execute()


def test_unsupported_claims_route_to_evidence_gathering_not_a_direct_generate(fake_db, monkeypatch):
    """Unsupported claims get evidence-driven regeneration
    (worker/handlers/gather_evidence.py), not a direct reword — the Opus
    escalation now happens on the generate job gather_evidence itself
    enqueues (see tests/test_evidence_pipeline.py), not here."""
    _seed_draft(fake_db, source_ids_used=[SOURCE_ID])
    result = {
        "overall_status": "revise",
        "rubric_scores": {"source_grounding": 4, "topic_relevance": 4},
        "overall_score": 3.2,
        "unsupported_claims": ["a stat with no real backing"],
        "sections_to_revise": ["intro"],
        "recommended_changes": ["cut the unsupported stat"],
        "feedback": "overstated a claim the sources don't support",
    }
    monkeypatch.setattr(evaluate_handler.claude_service, "evaluate_draft", lambda **kw: result)

    evaluate_handler.handle_evaluate({"reference_id": DRAFT_ID, "payload": {}})

    jobs = fake_db.table("jobs").select("*").execute().data
    assert not any(j["job_type"] == "generate" for j in jobs)
    gather_jobs = [j for j in jobs if j["job_type"] == "gather_evidence"]
    assert len(gather_jobs) == 1
    assert gather_jobs[0]["payload"]["claims"] == ["a stat with no real backing"]


def test_weak_grounding_on_real_non_thin_sources_escalates_to_opus(fake_db, monkeypatch):
    """grounding_is_weak (real, non-thin sources, low grounding score) is a
    misinterpretation of material that was actually there — distinct from
    `ungroundable` (no real evidence at all), which instead triggers gap-fill
    research, never a generate job, and so never reaches this escalation."""
    _seed_draft(fake_db, source_ids_used=[SOURCE_ID])
    result = {
        "overall_status": "revise",
        "rubric_scores": {"source_grounding": 1, "topic_relevance": 4},
        "overall_score": 2.6,
        "unsupported_claims": [],
        "sections_to_revise": ["body"],
        "recommended_changes": ["ground the middle section in the provided source"],
        "feedback": "barely engages with the source material provided",
    }
    monkeypatch.setattr(evaluate_handler.claude_service, "evaluate_draft", lambda **kw: result)

    evaluate_handler.handle_evaluate({"reference_id": DRAFT_ID, "payload": {}})

    jobs = fake_db.table("jobs").select("*").eq("job_type", "generate").execute().data
    assert len(jobs) == 1
    assert jobs[0]["payload"]["escalated_model"] == OPUS


def test_ordinary_wording_revision_does_not_escalate(fake_db, monkeypatch):
    _seed_draft(fake_db, source_ids_used=[SOURCE_ID])
    result = {
        "overall_status": "revise",
        "rubric_scores": {"source_grounding": 4, "topic_relevance": 3},
        "overall_score": 3.4,
        "unsupported_claims": [],
        "sections_to_revise": ["conclusion"],
        "recommended_changes": ["tighten the closing paragraph"],
        "feedback": "well-grounded, just needs tighter wording",
    }
    monkeypatch.setattr(evaluate_handler.claude_service, "evaluate_draft", lambda **kw: result)

    evaluate_handler.handle_evaluate({"reference_id": DRAFT_ID, "payload": {}})

    jobs = fake_db.table("jobs").select("*").eq("job_type", "generate").execute().data
    assert len(jobs) == 1
    assert "escalated_model" not in jobs[0]["payload"]


def test_generate_handler_honors_an_escalated_model_override(fake_db, monkeypatch):
    fake_db.table("content_requests").insert(
        {
            "id": REQUEST_ID,
            "status": "revising",
            "raw_idea": "why grounding matters",
            "target_audience": "SaaS marketers",
        }
    ).execute()
    plan_id = "00000000-0000-0000-0000-000000000043"
    fake_db.table("content_plans").insert(
        {"id": plan_id, "content_request_id": REQUEST_ID, "outline": {}, "target_keywords": []}
    ).execute()
    fake_db.table("article_drafts").insert(
        {
            "id": DRAFT_ID,
            "content_request_id": REQUEST_ID,
            "content_plan_id": plan_id,
            "option_label": "A",
            "version": 2,
            "title": "Draft",
            "body_markdown": _VALID_BODY,
            "source_ids_used": [],
            "status": "draft",
        }
    ).execute()

    seen_models = []

    def fake_generate_draft(**kwargs):
        seen_models.append(kwargs.get("model"))
        return "# Escalated regeneration\n\nBody."

    monkeypatch.setattr("worker.handlers.generate.claude_service.generate_draft", fake_generate_draft)

    from worker.handlers.generate import handle_generate

    handle_generate(
        {
            "reference_type": "article_draft",
            "reference_id": DRAFT_ID,
            "payload": {"revision_instructions": "fix it", "escalated_model": OPUS},
        }
    )

    assert seen_models == [OPUS]
    events = (
        fake_db.table("stage_events")
        .select("*")
        .eq("content_request_id", REQUEST_ID)
        .eq("stage", "generation")
        .execute()
        .data
    )
    assert events[0]["detail"]["model"] == OPUS
    assert events[0]["detail"]["escalated"] is True
