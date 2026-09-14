from datetime import datetime, timezone

import claude.service as claude_service
from app.config import get_settings
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

    passed = result["overall_status"] == "pass"
    evaluation_row = (
        db.table("evaluations")
        .insert(
            {
                "article_draft_id": draft_id,
                "rubric_scores": result["rubric_scores"],
                "overall_score": result["overall_score"],
                "passed_threshold": passed,
                "feedback": result["feedback"],
                "revision_instructions": None
                if passed
                else "; ".join(result["recommended_changes"]) or result["feedback"],
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
            },
        }
    ).execute()

    at_cap = draft["version"] >= settings.max_revisions

    if passed or at_cap or result["overall_status"] == "reject":
        db.table("article_drafts").update({"status": DraftStatus.EVALUATED.value}).eq("id", draft_id).execute()
        db.table("content_requests").update(
            {"status": RequestStatus.IN_REVIEW.value, "updated_at": datetime.now(timezone.utc).isoformat()}
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
        return

    # revise: enqueue another generate job against this draft
    db.table("content_requests").update(
        {"status": RequestStatus.REVISING.value, "updated_at": datetime.now(timezone.utc).isoformat()}
    ).eq("id", request_id).execute()
    db.table("jobs").insert(
        {
            "job_type": JobType.GENERATE.value,
            "reference_type": JobReferenceType.ARTICLE_DRAFT.value,
            "reference_id": draft_id,
            "payload": {"revision_instructions": evaluation_row["revision_instructions"]},
        }
    ).execute()
