from datetime import UTC, datetime

import claude.service as claude_service
from app.config import get_settings
from app.services.draft_versioning import insert_draft_version
from claude.grounding_validator import validate_grounding
from claude.models import model_for
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
        revision_instructions = None
        previous_body_markdown = None
        escalated_model = None
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
        revision_instructions = payload.get("revision_instructions")
        previous_body_markdown = parent["body_markdown"]
        escalated_model = payload.get("escalated_model")
        plan = db.table("content_plans").select("*").eq("id", content_plan_id).execute().data[0]
        outline, target_keywords = plan["outline"], plan["target_keywords"]

    evidence_package = payload.get("evidence_package") or []
    claims_to_address = payload.get("claims_to_address") or []

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
        model=escalated_model,
        evidence_package=evidence_package,
        claims_to_address=claims_to_address,
    )
    title = body_markdown.lstrip().split("\n", 1)[0].lstrip("#").strip() or f"{request_row['raw_idea'] or 'Untitled'}"

    draft_row = insert_draft_version(
        db,
        {
            "content_request_id": request_id,
            "content_plan_id": content_plan_id,
            "option_label": option_label,
            "parent_draft_id": parent_draft_id,
            "title": title,
            "body_markdown": body_markdown,
            "source_ids_used": [s["id"] for s in sources],
            "status": DraftStatus.DRAFT.value,
            "revision_instructions": revision_instructions,
        },
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
            "detail": {
                "draft_id": draft_row["id"],
                "version": draft_row["version"],
                "option_label": option_label,
                "source_version": parent["version"] if parent_draft_id else None,
                "model": escalated_model or model_for(JobType.GENERATE),
                "escalated": escalated_model is not None,
            },
        }
    ).execute()

    # Pre-flight grounding validator (before the expensive evaluator): a
    # cheap, deterministic gate catching fabricated URLs, unsupported trend/
    # causal claims, and stats that drifted from what their cited source
    # actually says. Failing this doesn't need Opus's judgment to detect —
    # regenerate directly instead of spending an evaluate call on a draft
    # that's mechanically broken, unless the revision cap is already spent.
    grounding = validate_grounding(body_markdown=body_markdown, sources=sources)
    at_cap = draft_row["version"] >= get_settings().max_revisions

    if not grounding["passed"] and not at_cap:
        db.table("stage_events").insert(
            {
                "content_request_id": request_id,
                "stage": PipelineStage.GROUNDING_VALIDATION.value,
                "status": StageEventStatus.FAILED.value,
                "detail": {"draft_id": draft_row["id"], "version": draft_row["version"]},
                "error_message": "; ".join(grounding["violations"]),
            }
        ).execute()
        db.table("content_requests").update(
            {"status": RequestStatus.REVISING.value, "updated_at": datetime.now(UTC).isoformat()}
        ).eq("id", request_id).execute()
        db.table("jobs").insert(
            {
                "job_type": JobType.GENERATE.value,
                "reference_type": JobReferenceType.ARTICLE_DRAFT.value,
                "reference_id": draft_row["id"],
                "payload": {
                    "revision_instructions": (
                        "The pre-flight grounding check found problems that must be fixed before this goes to "
                        "evaluation:\n" + "\n".join(f"- {v}" for v in grounding["violations"])
                    ),
                    "evidence_package": evidence_package,
                    "claims_to_address": claims_to_address,
                    "escalated_model": escalated_model,
                },
            }
        ).execute()
        return

    if not grounding["passed"]:
        # At cap with unresolved grounding issues: don't loop forever —
        # still send it to the real evaluator so the human reviewer sees
        # actual evaluation feedback, same as the existing at-cap behavior
        # in worker/handlers/evaluate.py.
        db.table("stage_events").insert(
            {
                "content_request_id": request_id,
                "stage": PipelineStage.GROUNDING_VALIDATION.value,
                "status": StageEventStatus.FAILED.value,
                "detail": {"draft_id": draft_row["id"], "version": draft_row["version"], "at_cap": True},
                "error_message": (
                    "revision cap reached with unresolved grounding issues; sending to evaluation anyway: "
                    + "; ".join(grounding["violations"])
                ),
            }
        ).execute()

    db.table("content_requests").update(
        {"status": RequestStatus.EVALUATING.value, "updated_at": datetime.now(UTC).isoformat()}
    ).eq("id", request_id).execute()

    db.table("jobs").insert(
        {
            "job_type": JobType.EVALUATE.value,
            "reference_type": JobReferenceType.ARTICLE_DRAFT.value,
            "reference_id": draft_row["id"],
            "payload": {},
        }
    ).execute()
