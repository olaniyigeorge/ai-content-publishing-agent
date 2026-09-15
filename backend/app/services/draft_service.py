"""Rewrite-with-AI for an existing draft: enqueues a targeted `generate` job
seeded with revision instructions, producing a new draft version rather than
mutating the existing row (mirrors the evaluate->generate revision loop and
the human `revise_requested` path in review_service.py).
"""

from datetime import UTC, datetime

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
from shared.errors import NotFound, ValidationFailure

MAX_RUBRIC_SCORE = 5.0


def rewrite_draft(draft_id: str, instructions: str | None) -> dict:
    db = get_supabase()
    rows = db.table("article_drafts").select("*").eq("id", draft_id).execute().data
    if not rows:
        raise NotFound(f"article draft {draft_id} not found")
    draft = rows[0]

    job_row = (
        db.table("jobs")
        .insert(
            {
                "job_type": JobType.GENERATE.value,
                "reference_type": JobReferenceType.ARTICLE_DRAFT.value,
                "reference_id": draft_id,
                "payload": {"revision_instructions": instructions or "Rewrite and improve this draft."},
            }
        )
        .execute()
        .data[0]
    )
    db.table("content_requests").update({"status": RequestStatus.REVISING.value}).eq(
        "id", draft["content_request_id"]
    ).execute()
    return {"job_id": job_row["id"], "status": "queued"}


EDITABLE_DRAFT_STATUSES = {DraftStatus.EVALUATED.value, DraftStatus.REVISED.value}


def manual_edit_draft(draft_id: str, title: str | None, body_markdown: str) -> dict:
    """A human directly rewrites the option under review — e.g. hand-pasting
    the parts of other options they liked — instead of asking Claude to. No
    Claude call, no job: this is synchronous, same versioning shape as
    handle_generate (new version, parent discarded), but the evaluation row
    it produces is marked evaluated_by=human rather than run through
    claude_service.evaluate_draft, per architecture.md §3.5's evaluated_by
    design ("supports a human override path later without a schema change").
    Only allowed on a draft currently up for review — editing a discarded or
    already-decided version would silently resurrect stale content."""
    body = (body_markdown or "").strip()
    if not body:
        raise ValidationFailure("body_markdown must not be empty")

    db = get_supabase()
    rows = db.table("article_drafts").select("*").eq("id", draft_id).execute().data
    if not rows:
        raise NotFound(f"article draft {draft_id} not found")
    parent = rows[0]
    if parent["status"] not in EDITABLE_DRAFT_STATUSES:
        raise ValidationFailure(
            f"draft {draft_id} is '{parent['status']}' and isn't currently up for review — only a draft "
            "awaiting a decision can be manually edited"
        )

    new_draft = (
        db.table("article_drafts")
        .insert(
            {
                "content_request_id": parent["content_request_id"],
                "content_plan_id": parent["content_plan_id"],
                "option_label": parent["option_label"],
                "version": parent["version"] + 1,
                "parent_draft_id": parent["id"],
                "title": (title or "").strip() or parent["title"],
                "body_markdown": body,
                "source_ids_used": parent["source_ids_used"],
                "status": DraftStatus.EVALUATED.value,
            }
        )
        .execute()
        .data[0]
    )
    db.table("article_drafts").update({"status": DraftStatus.DISCARDED.value}).eq("id", parent["id"]).execute()

    db.table("evaluations").insert(
        {
            "article_draft_id": new_draft["id"],
            "rubric_scores": {},
            "overall_score": MAX_RUBRIC_SCORE,
            "passed_threshold": True,
            "feedback": "Manually edited by a reviewer — not scored by the automatic evaluator.",
            "revision_instructions": None,
            "evaluated_by": EvaluatedBy.HUMAN.value,
        }
    ).execute()

    db.table("stage_events").insert(
        {
            "content_request_id": parent["content_request_id"],
            "stage": PipelineStage.GENERATION.value,
            "status": StageEventStatus.SUCCEEDED.value,
            "detail": {
                "draft_id": new_draft["id"],
                "version": new_draft["version"],
                "option_label": new_draft["option_label"],
                "edited_by": "human",
            },
        }
    ).execute()

    db.table("content_requests").update(
        {"status": RequestStatus.IN_REVIEW.value, "updated_at": datetime.now(UTC).isoformat()}
    ).eq("id", parent["content_request_id"]).execute()

    return new_draft
