from datetime import UTC, datetime

import claude.service as claude_service
from db.client import get_supabase
from shared.enums import (
    JobReferenceType,
    JobType,
    PipelineStage,
    RequestStatus,
    SourceStatus,
    StageEventStatus,
)


def handle_plan(job: dict) -> None:
    db = get_supabase()
    request_id = job["reference_id"]

    request_row = db.table("content_requests").select("*").eq("id", request_id).execute().data[0]
    sources = (
        db.table("sources")
        .select("*")
        .eq("content_request_id", request_id)
        .eq("status", SourceStatus.SELECTED.value)
        .execute()
        .data
    )

    result = claude_service.build_plan(
        raw_idea=request_row["raw_idea"], target_audience=request_row["target_audience"], sources=sources
    )

    plan_row = (
        db.table("content_plans")
        .insert(
            {
                "content_request_id": request_id,
                "outline": result["outline"],
                "target_keywords": result["target_keywords"],
            }
        )
        .execute()
        .data[0]
    )

    db.table("stage_events").insert(
        {
            "content_request_id": request_id,
            "stage": PipelineStage.PLANNING.value,
            "status": StageEventStatus.SUCCEEDED.value,
            "detail": {"content_plan_id": plan_row["id"], "sources_used": len(sources)},
        }
    ).execute()

    db.table("content_requests").update(
        {"status": RequestStatus.DRAFTING.value, "updated_at": datetime.now(UTC).isoformat()}
    ).eq("id", request_id).execute()

    db.table("jobs").insert(
        {
            "job_type": JobType.GENERATE.value,
            "reference_type": JobReferenceType.CONTENT_REQUEST.value,
            "reference_id": request_id,
            "payload": {"content_plan_id": plan_row["id"], "option_label": "A"},
        }
    ).execute()
