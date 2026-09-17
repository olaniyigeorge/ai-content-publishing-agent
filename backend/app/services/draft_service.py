"""Rewrite-with-AI for an existing draft: enqueues a targeted `generate` job
seeded with revision instructions, producing a new draft version rather than
mutating the existing row (mirrors the evaluate->generate revision loop and
the human `revise_requested` path in review_service.py).
"""

from datetime import UTC, datetime

from app.services.draft_versioning import insert_draft_version
from app.services.evaluation_context import with_evaluation_context
from app.services.gap_fill_gate import maybe_queue_gap_fill_research
from app.services.job_guard import has_pending_revision
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

    # TESTING_FINDINGS.md, 2026-09-16: without this, a rewrite requested
    # while the automatic evaluate->generate loop already has a revision of
    # this same draft in flight produces two `generate` jobs racing to
    # create the same next version number — the second one crashes on
    # article_drafts_version_unique instead of failing cleanly.
    if has_pending_revision(draft_id):
        raise ValidationFailure(
            "this draft already has a revision in progress — wait for it to finish before requesting another rewrite"
        )

    # A human's rewrite instructions ("make it punchier") are additive, not a
    # replacement for the reasoning the last evaluation already surfaced —
    # without this, a vague instruction regenerates blind on nothing but
    # that one line, dropping unsupported-claims/feedback context a prior
    # evaluation cycle already spent finding.
    full_instructions = with_evaluation_context(
        instructions or "Rewrite and improve this draft.", draft_id, db=db
    )

    request_row = db.table("content_requests").select("*").eq("id", draft["content_request_id"]).execute().data[0]
    gap_fill_job = maybe_queue_gap_fill_research(
        draft=draft, request_row=request_row, revision_instructions=full_instructions, db=db
    )
    if gap_fill_job:
        # This draft has no real source material — rewriting the wording
        # can't fix that, so search for real sources first (worker/handlers/
        # research.py's gap-fill path) and let it re-queue `generate` itself
        # once it has something to ground the rewrite in.
        return {"job_id": gap_fill_job["id"], "status": "researching"}

    job_row = (
        db.table("jobs")
        .insert(
            {
                "job_type": JobType.GENERATE.value,
                "reference_type": JobReferenceType.ARTICLE_DRAFT.value,
                "reference_id": draft_id,
                "payload": {"revision_instructions": full_instructions},
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

    new_draft = insert_draft_version(
        db,
        {
            "content_request_id": parent["content_request_id"],
            "content_plan_id": parent["content_plan_id"],
            "option_label": parent["option_label"],
            "parent_draft_id": parent["id"],
            "title": (title or "").strip() or parent["title"],
            "body_markdown": body,
            "source_ids_used": parent["source_ids_used"],
            "status": DraftStatus.EVALUATED.value,
        },
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
                "source_version": parent["version"],
                "edited_by": "human",
            },
        }
    ).execute()

    db.table("content_requests").update(
        {"status": RequestStatus.IN_REVIEW.value, "updated_at": datetime.now(UTC).isoformat()}
    ).eq("id", parent["content_request_id"]).execute()

    return new_draft
