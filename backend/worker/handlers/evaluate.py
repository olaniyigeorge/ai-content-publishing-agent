from datetime import UTC, datetime

import claude.service as claude_service
from app.config import get_settings
from claude.outputs import require_fields
from claude.quality_guards import check_article, is_ungroundable
from db.client import get_supabase
from shared.enums import (
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

    # Deterministic check, independent of the model's self-assessment: a
    # rubric "pass" can't override a hard length/structure violation
    # (EDGE_CASES.md-style guard — see claude/quality_guards.py).
    guard = check_article(draft["body_markdown"])
    passed = result["overall_status"] == "pass" and not guard["violations"]
    revision_notes = list(result["recommended_changes"])
    if guard["violations"]:
        revision_notes = [f"[hard guard] {v}" for v in guard["violations"]] + revision_notes

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
                "unsupported_claims": result["unsupported_claims"],
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
