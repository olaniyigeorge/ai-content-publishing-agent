from datetime import UTC, datetime

import claude.service as claude_service
from app.config import get_settings
from claude.outputs import require_fields
from claude.quality_guards import SOURCE_GROUNDING_FLOOR, check_article, is_ungroundable
from db.client import get_supabase
from shared.enums import (
    AttachmentType,
    DraftStatus,
    EvaluatedBy,
    JobReferenceType,
    JobType,
    PipelineStage,
    RequestStatus,
    StageEventStatus,
)
from shared.errors import DraftEvaluationFailed


def handle_evaluate(job: dict) -> None:
    """EDGE_CASES.md #24: caps the evaluate->generate loop at
    settings.max_revisions. Past the cap, the draft still goes to human
    review — with passed_threshold=false visible in the evaluation panel —
    rather than looping forever or getting silently stuck."""
    db = get_supabase()
    settings = get_settings()
    draft_id = job["reference_id"]

    draft = db.table("article_drafts").select("*").eq("id", draft_id).execute().data[0]
    request_id = draft["content_request_id"]
    request_row = db.table("content_requests").select("*").eq("id", request_id).execute().data[0]
    sources = db.table("sources").select("*").in_("id", draft["source_ids_used"]).execute().data

    result = claude_service.evaluate_draft(
        target_audience=request_row["target_audience"],
        draft_title=draft["title"],
        draft_body=draft["body_markdown"],
        sources=sources,
    )
    require_fields(
        result,
        ["overall_status", "rubric_scores", "overall_score", "recommended_changes", "feedback"],
        step="evaluation",
        error_cls=DraftEvaluationFailed,
    )
    unsupported_claims = result.get("unsupported_claims") or []
    sections_to_revise = result.get("sections_to_revise") or []

    # Deterministic checks, independent of the model's self-assessment: a
    # rubric "pass" can't override a hard length/structure violation
    # (EDGE_CASES.md-style guard — see claude/quality_guards.py), and it
    # can't override the model's own unsupported_claims list either. The
    # prompt (claude/prompts/evaluate.py) already instructs "if pass, zero
    # unsupported_claims" — but that's a request to the model, not a
    # guarantee. Enforcing it here, not just asking for it, is what stops a
    # confidently-worded "pass" from carrying an unresolved unsupported claim
    # through to a human reviewer as if it were solid.
    guard = check_article(draft["body_markdown"])
    passed = result["overall_status"] == "pass" and not guard["violations"] and not unsupported_claims
    revision_notes = list(result["recommended_changes"])
    if guard["violations"]:
        revision_notes = [f"[hard guard] {v}" for v in guard["violations"]] + revision_notes
    if unsupported_claims and result["overall_status"] == "pass":
        revision_notes = [f"[unsupported claim] {c}" for c in unsupported_claims] + revision_notes

    evaluation_row = (
        db.table("evaluations")
        .insert(
            {
                "article_draft_id": draft_id,
                "rubric_scores": result["rubric_scores"],
                "overall_score": result["overall_score"],
                "passed_threshold": passed,
                "feedback": result["feedback"],
                "revision_instructions": None if passed else ("; ".join(revision_notes) or result["feedback"]),
                "unsupported_claims": unsupported_claims,
                "sections_to_revise": sections_to_revise,
                "evaluated_by": EvaluatedBy.AI.value,
            }
        )
        .execute()
        .data[0]
    )

    db.table("stage_events").insert(
        {
            "content_request_id": request_id,
            "stage": PipelineStage.EVALUATION.value,
            "status": StageEventStatus.SUCCEEDED.value,
            "detail": {
                "draft_id": draft_id,
                "version": draft["version"],
                "passed_threshold": passed,
                "overall_status": result["overall_status"],
                "unsupported_claims": unsupported_claims,
                "quality_guard": guard,
            },
        }
    ).execute()

    at_cap = draft["version"] >= settings.max_revisions
    # A draft with zero source_ids_used can't be fixed by revising the text —
    # there's no source material to ground it in no matter how it's worded.
    # Stop after this one attempt instead of spending the rest of the
    # revision cap on cycles that were never going to pass (TESTING_FINDINGS.md).
    ungroundable = not passed and is_ungroundable(
        source_ids_used=draft["source_ids_used"], rubric_scores=result["rubric_scores"]
    )
    grounding_score = result["rubric_scores"].get("source_grounding")
    grounding_is_weak = not passed and grounding_score is not None and grounding_score <= SOURCE_GROUNDING_FLOOR
    # Only "no real evidence" cases (zero sources, or every source actually
    # used came back thin) call for searching again — a low score against
    # sources that do exist and aren't thin means the draft just did a poor
    # job grounding in material that's already there, which revising the
    # wording can genuinely fix (test_low_source_grounding_with_real_sources_
    # still_revises_normally).
    has_only_thin_sources = bool(sources) and all(s.get("confidence") == "thin" for s in sources)
    grounding_has_no_real_evidence = ungroundable or (grounding_is_weak and has_only_thin_sources)

    # If nobody gave this request a source URL, the only sources it has ever
    # had are whatever the autonomous web search found — and that search
    # only ever ran once, blind to what the draft actually turned out to need.
    # Before giving up on grounding (or spending the rest of the revision cap
    # revising wording that can't fix a sourcing gap), give it a small,
    # capped number of chances to search again — this time aimed specifically
    # at what the evaluation just flagged.
    has_source_url = any(
        a["type"] == AttachmentType.URL.value
        for a in db.table("intake_attachments").select("type").eq("content_request_id", request_id).execute().data
    )
    can_gap_fill = (
        not passed
        and not at_cap
        and not has_source_url
        and grounding_has_no_real_evidence
        and request_row.get("gap_fill_attempts", 0) < settings.max_gap_fill_attempts
    )

    if can_gap_fill:
        research_focus = "; ".join([*unsupported_claims, result["feedback"]])
        db.table("content_requests").update(
            {
                "gap_fill_attempts": request_row.get("gap_fill_attempts", 0) + 1,
                "status": RequestStatus.RESEARCHING.value,
                "updated_at": datetime.now(UTC).isoformat(),
            }
        ).eq("id", request_id).execute()
        db.table("stage_events").insert(
            {
                "content_request_id": request_id,
                "stage": PipelineStage.RESEARCH.value,
                "status": StageEventStatus.STARTED.value,
                "detail": {
                    "draft_id": draft_id,
                    "version": draft["version"],
                    "reason": "no source URL was given and grounding is empty or thin — searching again, "
                    "this time aimed at what the evaluation flagged, instead of revising wording that can't "
                    "fix a sourcing gap",
                    "research_focus": research_focus,
                },
            }
        ).execute()
        db.table("jobs").insert(
            {
                "job_type": JobType.RESEARCH.value,
                "reference_type": JobReferenceType.CONTENT_REQUEST.value,
                "reference_id": request_id,
                "payload": {
                    "gap_fill_for_draft_id": draft_id,
                    "research_focus": research_focus,
                    "revision_instructions": evaluation_row["revision_instructions"],
                },
            }
        ).execute()
        return

    if passed or at_cap or ungroundable or result["overall_status"] == "reject":
        db.table("article_drafts").update({"status": DraftStatus.EVALUATED.value}).eq("id", draft_id).execute()
        db.table("content_requests").update(
            {"status": RequestStatus.IN_REVIEW.value, "updated_at": datetime.now(UTC).isoformat()}
        ).eq("id", request_id).execute()
        if at_cap and not passed:
            db.table("stage_events").insert(
                {
                    "content_request_id": request_id,
                    "stage": PipelineStage.EVALUATION.value,
                    "status": StageEventStatus.FAILED.value,
                    "detail": {"draft_id": draft_id, "version": draft["version"]},
                    "error_message": (
                        f"revision cap ({settings.max_revisions}) reached without passing evaluation; "
                        "sending to human review as-is"
                    ),
                }
            ).execute()
        elif ungroundable:
            db.table("stage_events").insert(
                {
                    "content_request_id": request_id,
                    "stage": PipelineStage.EVALUATION.value,
                    "status": StageEventStatus.FAILED.value,
                    "detail": {"draft_id": draft_id, "version": draft["version"]},
                    "error_message": (
                        "this draft has no source material to ground claims in, and revising the "
                        "wording can't fix that — skipping the remaining automatic revisions and "
                        "sending it to human review now instead of spending the full revision cap"
                    ),
                }
            ).execute()
        return

    # revise: enqueue another generate job against this draft
    db.table("content_requests").update(
        {"status": RequestStatus.REVISING.value, "updated_at": datetime.now(UTC).isoformat()}
    ).eq("id", request_id).execute()
    db.table("jobs").insert(
        {
            "job_type": JobType.GENERATE.value,
            "reference_type": JobReferenceType.ARTICLE_DRAFT.value,
            "reference_id": draft_id,
            "payload": {"revision_instructions": evaluation_row["revision_instructions"]},
        }
    ).execute()
