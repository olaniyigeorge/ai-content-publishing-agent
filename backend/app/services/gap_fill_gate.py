"""Shared by every human-triggered path that can regenerate an existing
draft (draft_service.rewrite_draft, review_service.submit_review's
revise_requested branch): mirrors worker/handlers/evaluate.py's automatic
`can_gap_fill` check, so a human asking to "rewrite this with real sources"
doesn't fall into the exact trap the automatic evaluate->generate loop was
built to avoid.

Without this, a rewrite/revise request against a draft with zero source
material goes straight to `generate` with nothing but free-text instructions
to ground it in — the model has no search tool, so it either invents
plausible-looking citations (caught after the fact by
claude/grounding_validator.py) or hedges everything into mush, and each
regeneration attempt burns part of the revision cap without ever fixing the
actual gap: there was never any source material to write from
(TESTING_FINDINGS.md, 2026-09-17 — the "why is the result degrading" report).
"""

from datetime import UTC, datetime

from app.config import get_settings
from db.client import get_supabase
from shared.enums import (
    AttachmentType,
    JobReferenceType,
    JobType,
    PipelineStage,
    RequestStatus,
    StageEventStatus,
)


def maybe_queue_gap_fill_research(*, draft: dict, request_row: dict, revision_instructions: str, db=None) -> dict | None:
    """If this draft has no real source material, no source URL was ever
    given (a URL that failed to scrape isn't "no material" — that's a
    different failure), and the gap-fill budget isn't spent, queues a
    `research` job aimed at the rewrite instructions and returns the queued
    job row. Returns None if a gap fill isn't called for — the caller should
    fall through to its normal `generate` enqueue in that case."""
    db = db or get_supabase()

    if draft.get("source_ids_used"):
        return None
    if request_row.get("gap_fill_attempts", 0) >= get_settings().max_gap_fill_attempts:
        return None
    has_source_url = any(
        a["type"] == AttachmentType.URL.value
        for a in db.table("intake_attachments")
        .select("type")
        .eq("content_request_id", request_row["id"])
        .execute()
        .data
    )
    if has_source_url:
        return None

    now = datetime.now(UTC).isoformat()
    db.table("content_requests").update(
        {
            "gap_fill_attempts": request_row.get("gap_fill_attempts", 0) + 1,
            "status": RequestStatus.RESEARCHING.value,
            "updated_at": now,
        }
    ).eq("id", request_row["id"]).execute()
    db.table("stage_events").insert(
        {
            "content_request_id": request_row["id"],
            "stage": PipelineStage.RESEARCH.value,
            "status": StageEventStatus.STARTED.value,
            "detail": {
                "draft_id": draft["id"],
                "version": draft["version"],
                "reason": "this draft has no source material and no source URL was given — searching for "
                "real sources before rewriting, instead of regenerating text with nothing to ground it in",
                "research_focus": revision_instructions,
            },
        }
    ).execute()
    return (
        db.table("jobs")
        .insert(
            {
                "job_type": JobType.RESEARCH.value,
                "reference_type": JobReferenceType.CONTENT_REQUEST.value,
                "reference_id": request_row["id"],
                "payload": {
                    "gap_fill_for_draft_id": draft["id"],
                    "research_focus": revision_instructions,
                    "revision_instructions": revision_instructions,
                },
            }
        )
        .execute()
        .data[0]
    )
