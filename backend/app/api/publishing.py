from datetime import datetime, timezone

from fastapi import APIRouter, Depends

from auth.deps import get_current_user
from db.client import get_supabase
from shared.enums import QueueStatus
from shared.errors import InvalidStateTransition, NotFound
from shared.models import PublishingQueueOut, PublishingQueueScheduleIn

router = APIRouter(prefix="/api/publishing-queue", tags=["publishing"])


@router.get("", response_model=list[PublishingQueueOut])
def get_queue(user: dict = Depends(get_current_user)) -> list[dict]:
    return get_supabase().table("publishing_queue").select("*").order("created_at", desc=True).execute().data


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
        .update({"scheduled_for": scheduled_for, "next_attempt_at": scheduled_for or datetime.now(timezone.utc).isoformat()})
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
                "next_attempt_at": datetime.now(timezone.utc).isoformat(),
            }
        )
        .eq("id", queue_id)
        .execute()
        .data[0]
    )
