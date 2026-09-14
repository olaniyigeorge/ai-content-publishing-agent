from datetime import datetime, timezone

import claude.service as claude_service
from db.client import get_supabase
from shared.enums import (
    DraftStatus,
    JobReferenceType,
    JobType,
    PipelineStage,
    RequestStatus,
    SourceStatus,
    StageEventStatus,
)


def handle_generate(job: dict) -> None:
    db = get_supabase()
    payload = job["payload"]

    if job["reference_type"] == JobReferenceType.CONTENT_REQUEST.value:
        request_id = job["reference_id"]
        content_plan_id = payload["content_plan_id"]
        option_label = payload.get("option_label", "A")
        parent_draft_id = None
        version = 1
        revision_instructions = None
        previous_body_markdown = None
        plan = db.table("content_plans").select("*").eq("id", content_plan_id).execute().data[0]
        outline, target_keywords = plan["outline"], plan["target_keywords"]
    else:
        # reference_type == ARTICLE_DRAFT: a revision, either from the
        # evaluate->generate loop or a human's revise_requested decision.
        parent = db.table("article_drafts").select("*").eq("id", job["reference_id"]).execute().data[0]
        request_id = parent["content_request_id"]
        content_plan_id = parent["content_plan_id"]
        option_label = parent["option_label"]
        parent_draft_id = parent["id"]
        version = parent["version"] + 1
        revision_instructions = payload.get("revision_instructions")
        previous_body_markdown = parent["body_markdown"]
        plan = db.table("content_plans").select("*").eq("id", content_plan_id).execute().data[0]
        outline, target_keywords = plan["outline"], plan["target_keywords"]

    request_row = db.table("content_requests").select("*").eq("id", request_id).execute().data[0]
    sources = (
        db.table("sources")
        .select("*")
        .eq("content_request_id", request_id)
        .eq("status", SourceStatus.SELECTED.value)
        .execute()
        .data
    )

    body_markdown = claude_service.generate_draft(
        raw_idea=request_row["raw_idea"],
        target_audience=request_row["target_audience"],
        outline=outline,
        target_keywords=target_keywords,
        sources=sources,
        revision_instructions=revision_instructions,
        previous_body_markdown=previous_body_markdown,
    )
    title = body_markdown.lstrip().split("\n", 1)[0].lstrip("#").strip() or f"{request_row['raw_idea'] or 'Untitled'}"

    draft_row = (
        db.table("article_drafts")
        .insert(
            {
                "content_request_id": request_id,
                "content_plan_id": content_plan_id,
                "option_label": option_label,
                "version": version,
                "parent_draft_id": parent_draft_id,
                "title": title,
                "body_markdown": body_markdown,
                "source_ids_used": [s["id"] for s in sources],
                "status": DraftStatus.DRAFT.value,
            }
        )
        .execute()
        .data[0]
    )

    if parent_draft_id:
        db.table("article_drafts").update({"status": DraftStatus.DISCARDED.value}).eq(
            "id", parent_draft_id
        ).execute()

    db.table("stage_events").insert(
        {
            "content_request_id": request_id,
            "stage": PipelineStage.GENERATION.value,
            "status": StageEventStatus.SUCCEEDED.value,
            "detail": {"draft_id": draft_row["id"], "version": version, "option_label": option_label},
        }
    ).execute()

    db.table("content_requests").update(
        {"status": RequestStatus.EVALUATING.value, "updated_at": datetime.now(timezone.utc).isoformat()}
    ).eq("id", request_id).execute()

    db.table("jobs").insert(
        {
            "job_type": JobType.EVALUATE.value,
            "reference_type": JobReferenceType.ARTICLE_DRAFT.value,
            "reference_id": draft_row["id"],
            "payload": {},
        }
    ).execute()
