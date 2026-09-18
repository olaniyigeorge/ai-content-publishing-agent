from datetime import UTC, datetime

from fastapi import APIRouter, Depends

from app.services.request_state_service import maybe_finalize_request_status
from auth.deps import get_current_user
from db.client import get_supabase
from shared.enums import QueueStatus
from shared.errors import InvalidStateTransition, NotFound
from shared.models import (
    PublishingQueueOut,
    PublishingQueueScheduleIn,
    PublishingQueueStatusIn,
)

router = APIRouter(prefix="/api/publishing-queue", tags=["publishing"])

# Manual overrides land here from a human who published (or gave up on) a
# channel adaptation outside the automated retry loop — see EDGE_CASES.md #40
# sibling case: there's no way today to tell the system "I posted this myself."
MANUAL_OVERRIDE_STATUSES = {
    QueueStatus.QUEUED.value,
    QueueStatus.READY_TO_PUBLISH.value,
    QueueStatus.PUBLISHED.value,
    QueueStatus.FAILED.value,
    QueueStatus.CANCELLED.value,
}

# Items still waiting on an actual publish attempt — surfaced first in the
# queue view so "what's next" doesn't get buried under already-resolved rows.
WAITING_TO_PUBLISH_STATUSES = {QueueStatus.QUEUED.value, QueueStatus.READY_TO_PUBLISH.value}


def _enrich(queue_rows: list[dict]) -> list[dict]:
    """Denormalize channel/content/title onto each queue row with the same
    manual join-by-id pattern used elsewhere in this codebase (no postgrest
    embedded-resource syntax) — see request_state_service.py."""
    if not queue_rows:
        return []
    db = get_supabase()
    adaptation_ids = list({r["channel_adaptation_id"] for r in queue_rows})
    adaptations = {
        a["id"]: a
        for a in db.table("channel_adaptations").select("*").in_("id", adaptation_ids).execute().data
    }
    draft_ids = list({a["article_draft_id"] for a in adaptations.values()})
    drafts = (
        {d["id"]: d for d in db.table("article_drafts").select("id, title").in_("id", draft_ids).execute().data}
        if draft_ids
        else {}
    )

    enriched = []
    for row in queue_rows:
        adaptation = adaptations.get(row["channel_adaptation_id"])
        draft = drafts.get(adaptation["article_draft_id"]) if adaptation else None
        formatting_check = (adaptation or {}).get("formatting_check") or {}
        violations = formatting_check.get("violations")
        enriched.append(
            {
                **row,
                "content_request_id": adaptation["content_request_id"] if adaptation else None,
                "channel": adaptation["channel"] if adaptation else None,
                "content": adaptation["content"] if adaptation else None,
                "content_format": adaptation["content_format"] if adaptation else None,
                "article_title": draft["title"] if draft else None,
                "failure_reason": "; ".join(violations) if violations else None,
            }
        )
    return enriched


@router.get("", response_model=list[PublishingQueueOut])
def get_queue(user: dict = Depends(get_current_user)) -> list[dict]:
    rows = get_supabase().table("publishing_queue").select("*").order("created_at", desc=True).execute().data
    # Waiting-to-publish items first (newest-first within that group), then
    # everything already resolved or in flight — sort is stable so the
    # created_at ordering from the query above is preserved within each group.
    rows.sort(key=lambda r: r["status"] not in WAITING_TO_PUBLISH_STATUSES)
    return _enrich(rows)


def _get_or_404(queue_id: str) -> dict:
    rows = get_supabase().table("publishing_queue").select("*").eq("id", queue_id).execute().data
    if not rows:
        raise NotFound(f"publishing queue item {queue_id} not found")
    return rows[0]


@router.post("/{queue_id}/schedule", response_model=PublishingQueueOut)
def post_schedule(queue_id: str, body: PublishingQueueScheduleIn, user: dict = Depends(get_current_user)) -> dict:
    item = _get_or_404(queue_id)
    if item["status"] not in (QueueStatus.QUEUED.value,):
        raise InvalidStateTransition(f"cannot schedule an item in status '{item['status']}'")
    scheduled_for = body.scheduled_for.isoformat() if body.scheduled_for else None
    updated = (
        get_supabase()
        .table("publishing_queue")
        .update({"scheduled_for": scheduled_for, "next_attempt_at": scheduled_for or datetime.now(UTC).isoformat()})
        .eq("id", queue_id)
        .execute()
        .data[0]
    )
    return updated


@router.post("/{queue_id}/cancel", response_model=PublishingQueueOut)
def post_cancel(queue_id: str, user: dict = Depends(get_current_user)) -> dict:
    item = _get_or_404(queue_id)
    if item["status"] in (QueueStatus.PUBLISHED.value, QueueStatus.CANCELLED.value):
        raise InvalidStateTransition(f"cannot cancel an item in status '{item['status']}'")
    return get_supabase().table("publishing_queue").update({"status": QueueStatus.CANCELLED.value}).eq(
        "id", queue_id
    ).execute().data[0]


@router.patch("/{queue_id}/status", response_model=PublishingQueueOut)
def patch_status(queue_id: str, body: PublishingQueueStatusIn, user: dict = Depends(get_current_user)) -> dict:
    """Manual status override for a human who posted (or gave up on) a channel
    adaptation outside the automated flow — e.g. they copied the content and
    posted it themselves, or a platform rejected it for a reason the worker
    can't detect. Any -> any among the real QueueStatus values; this is a
    manual correction, not a state-machine transition.

    This is also the *primary* way an item ever reaches 'published': the mock
    publish adapter only ever gets a queue item to 'ready_to_publish'
    (EDGE_CASES.md #39 — it doesn't actually reach the platform), so a human
    confirming here is what makes 'published' true. Confirming it also has to
    cascade to the channel_adaptation and the content_request, which the
    automated path used to do on its own."""
    item = _get_or_404(queue_id)
    new_status = body.status.value
    if new_status not in MANUAL_OVERRIDE_STATUSES:
        raise InvalidStateTransition(f"'{new_status}' is not a manually settable status")
    update = {"status": new_status}
    if new_status == QueueStatus.PUBLISHED.value:
        now = datetime.now(UTC).isoformat()
        update["published_at"] = now
        db = get_supabase()
        adaptation = (
            db.table("channel_adaptations")
            .update({"status": "published", "updated_at": now})
            .eq("id", item["channel_adaptation_id"])
            .execute()
            .data[0]
        )
        maybe_finalize_request_status(adaptation["content_request_id"])
    updated = get_supabase().table("publishing_queue").update(update).eq("id", queue_id).execute().data[0]
    return _enrich([updated])[0]


@router.post("/{queue_id}/retry", response_model=PublishingQueueOut)
def post_retry(queue_id: str, user: dict = Depends(get_current_user)) -> dict:
    """EDGE_CASES.md #40: a dead_letter item must have a visible next action —
    this is it. Manually re-enqueues a dead-lettered item with a reset
    attempt counter."""
    item = _get_or_404(queue_id)
    if item["status"] != QueueStatus.DEAD_LETTER.value:
        raise InvalidStateTransition(f"cannot retry an item in status '{item['status']}' (must be dead_letter)")
    return (
        get_supabase()
        .table("publishing_queue")
        .update(
            {
                "status": QueueStatus.QUEUED.value,
                "attempts": 0,
                "last_error": None,
                "next_attempt_at": datetime.now(UTC).isoformat(),
            }
        )
        .eq("id", queue_id)
        .execute()
        .data[0]
    )
