"""The approval gate (test scenario 5). Nothing downstream of this module
runs without a human_reviews row — adapt is enqueued only on `approved`, and
only from here.
"""

from datetime import UTC, datetime

from app.services.evaluation_context import with_evaluation_context
from app.services.gap_fill_gate import maybe_queue_gap_fill_research
from app.services.job_guard import has_pending_revision
from db.client import get_supabase
from shared.enums import (
    DraftStatus,
    JobReferenceType,
    JobType,
    PipelineStage,
    RequestStatus,
    ReviewDecision,
    StageEventStatus,
)
from shared.errors import InvalidStateTransition, NotFound
from shared.models import HumanReviewIn, HumanReviewOut

REVIEWABLE_DRAFT_STATUSES = {DraftStatus.EVALUATED.value, DraftStatus.REVISED.value}


def submit_review(content_request_id: str, body: HumanReviewIn, reviewer_user_id: str) -> HumanReviewOut:
    db = get_supabase()

    draft_rows = db.table("article_drafts").select("*").eq("id", str(body.article_draft_id)).execute().data
    if not draft_rows:
        raise NotFound(f"article draft {body.article_draft_id} not found")
    draft = draft_rows[0]

    if draft["content_request_id"] != content_request_id:
        raise NotFound(f"article draft {body.article_draft_id} does not belong to request {content_request_id}")

    # EDGE_CASES.md #28: reject a decision on a draft that's not in a
    # reviewable state (still being generated/revised, never evaluated).
    if draft["status"] not in REVIEWABLE_DRAFT_STATUSES:
        raise InvalidStateTransition(
            f"draft {draft['id']} is in status '{draft['status']}', not reviewable "
            f"(must be one of {sorted(REVIEWABLE_DRAFT_STATUSES)})"
        )

    # EDGE_CASES.md #30: two humans reviewing the same request/draft
    # concurrently — first write wins, second is rejected as invalid state,
    # not silently overwritten.
    existing_terminal = (
        db.table("human_reviews")
        .select("id, decision")
        .eq("article_draft_id", str(body.article_draft_id))
        .in_("decision", [ReviewDecision.APPROVED.value, ReviewDecision.REJECTED.value])
        .execute()
        .data
    )
    if existing_terminal:
        raise InvalidStateTransition(f"draft {draft['id']} already has a terminal review decision")

    review_row = (
        db.table("human_reviews")
        .insert(
            {
                "content_request_id": content_request_id,
                "article_draft_id": str(body.article_draft_id),
                "reviewer_user_id": reviewer_user_id,
                "decision": body.decision.value,
                "notes": body.notes,
            }
        )
        .execute()
        .data[0]
    )

    now = datetime.now(UTC).isoformat()
    db.table("stage_events").insert(
        {
            "content_request_id": content_request_id,
            "stage": PipelineStage.HUMAN_REVIEW.value,
            "status": StageEventStatus.SUCCEEDED.value,
            "detail": {"decision": body.decision.value, "article_draft_id": str(body.article_draft_id)},
        }
    ).execute()

    if body.decision == ReviewDecision.APPROVED:
        db.table("article_drafts").update({"status": DraftStatus.SELECTED.value}).eq("id", draft["id"]).execute()
        db.table("content_requests").update({"status": RequestStatus.APPROVED.value, "updated_at": now}).eq(
            "id", content_request_id
        ).execute()
        db.table("jobs").insert(
            {
                "job_type": JobType.ADAPT.value,
                "reference_type": JobReferenceType.ARTICLE_DRAFT.value,
                "reference_id": draft["id"],
                "payload": {"content_request_id": content_request_id},
            }
        ).execute()
        db.table("content_requests").update({"status": RequestStatus.ADAPTING.value, "updated_at": now}).eq(
            "id", content_request_id
        ).execute()
    elif body.decision == ReviewDecision.REJECTED:
        db.table("article_drafts").update({"status": DraftStatus.DISCARDED.value}).eq("id", draft["id"]).execute()
        db.table("content_requests").update({"status": RequestStatus.REJECTED.value, "updated_at": now}).eq(
            "id", content_request_id
        ).execute()
    elif body.decision == ReviewDecision.REVISE_REQUESTED:
        # Same race guarded in draft_service.rewrite_draft — a reviewable
        # draft shouldn't normally have an in-flight revision already, but
        # this is cheap insurance against the same version-collision crash.
        if has_pending_revision(draft["id"]):
            raise InvalidStateTransition(
                f"draft {draft['id']} already has a revision in progress — wait for it to finish first"
            )
        # Same reasoning as draft_service.rewrite_draft: the reviewer's own
        # notes are additive to the last evaluation's actual findings, not a
        # replacement for them — otherwise a short note like "fix this"
        # regenerates with no memory of what the evaluation already flagged.
        instructions = with_evaluation_context(
            body.notes or "Address the reviewer's feedback.", draft["id"], db=db
        )
        gap_fill_job = maybe_queue_gap_fill_research(
            draft=draft,
            request_row=db.table("content_requests").select("*").eq("id", content_request_id).execute().data[0],
            revision_instructions=instructions,
            db=db,
        )
        if not gap_fill_job:
            # Only reached when this draft has real source material (or the
            # gap-fill budget is spent) — otherwise a search for real sources
            # was just queued instead, and it'll re-queue `generate` itself.
            db.table("jobs").insert(
                {
                    "job_type": JobType.GENERATE.value,
                    "reference_type": JobReferenceType.ARTICLE_DRAFT.value,
                    "reference_id": draft["id"],
                    "payload": {"revision_instructions": instructions},
                }
            ).execute()
            db.table("content_requests").update({"status": RequestStatus.REVISING.value, "updated_at": now}).eq(
                "id", content_request_id
            ).execute()
    # OPTION_SELECTED: records which lineage the human picked; does not by
    # itself imply approval (EDGE_CASES.md #27) — no downstream job enqueued.

    return HumanReviewOut(**review_row)
