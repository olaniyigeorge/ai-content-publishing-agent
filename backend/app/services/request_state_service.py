from datetime import UTC, datetime

from db.client import get_supabase
from shared.enums import AdaptationStatus, RequestStatus
from shared.errors import NotFound
from shared.models import (
    ArticleDraftOut,
    ChannelAdaptationOut,
    ContentRequestDetail,
    ContentRequestOut,
    EvaluationOut,
    HumanReviewOut,
    IntakeAttachmentOut,
    PublishingQueueOut,
    SourceOut,
    StageEventOut,
)


def list_content_requests() -> list[ContentRequestOut]:
    rows = get_supabase().table("content_requests").select("*").order("created_at", desc=True).execute().data
    return [ContentRequestOut(**r) for r in rows]


def get_content_request_detail(request_id: str) -> ContentRequestDetail:
    db = get_supabase()
    request_rows = db.table("content_requests").select("*").eq("id", request_id).execute().data
    if not request_rows:
        raise NotFound(f"content request {request_id} not found")
    request_row = request_rows[0]

    attachments = db.table("intake_attachments").select("*").eq("content_request_id", request_id).execute().data
    sources = db.table("sources").select("*").eq("content_request_id", request_id).execute().data
    drafts = (
        db.table("article_drafts")
        .select("*")
        .eq("content_request_id", request_id)
        .order("option_label")
        .order("version")
        .execute()
        .data
    )
    draft_ids = [d["id"] for d in drafts]
    evaluations = (
        db.table("evaluations").select("*").in_("article_draft_id", draft_ids).execute().data if draft_ids else []
    )
    human_reviews = db.table("human_reviews").select("*").eq("content_request_id", request_id).execute().data
    adaptations = db.table("channel_adaptations").select("*").eq("content_request_id", request_id).execute().data
    adaptation_ids = [a["id"] for a in adaptations]
    queue_items = (
        db.table("publishing_queue").select("*").in_("channel_adaptation_id", adaptation_ids).execute().data
        if adaptation_ids
        else []
    )
    # Denormalize channel/content/title onto each queue row — same shape as
    # publishing.py's _enrich(), reusing the adaptations/drafts already
    # fetched for this request instead of re-querying by id.
    adaptations_by_id = {a["id"]: a for a in adaptations}
    drafts_by_id = {d["id"]: d for d in drafts}
    enriched_queue_items = []
    for row in queue_items:
        adaptation = adaptations_by_id.get(row["channel_adaptation_id"])
        draft = drafts_by_id.get(adaptation["article_draft_id"]) if adaptation else None
        formatting_check = (adaptation or {}).get("formatting_check") or {}
        violations = formatting_check.get("violations")
        enriched_queue_items.append(
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
    stage_events = (
        db.table("stage_events")
        .select("*")
        .eq("content_request_id", request_id)
        .order("created_at")
        .execute()
        .data
    )

    return ContentRequestDetail(
        request=ContentRequestOut(**request_row),
        attachments=[IntakeAttachmentOut(**a) for a in attachments],
        sources=[SourceOut(**s) for s in sources],
        drafts=[ArticleDraftOut(**d) for d in drafts],
        evaluations=[EvaluationOut(**e) for e in evaluations],
        human_reviews=[HumanReviewOut(**h) for h in human_reviews],
        adaptations=[ChannelAdaptationOut(**a) for a in adaptations],
        publishing_queue=[PublishingQueueOut(**q) for q in enriched_queue_items],
        stage_events=[StageEventOut(**e) for e in stage_events],
    )


def maybe_finalize_request_status(request_id: str) -> None:
    """Once every non-failed channel_adaptation for a request has been
    published, the request itself never otherwise moves off `queued`
    (adapt.py only sets it once, when adaptations are created) — call this
    after a publish job succeeds to move the request to its terminal state.
    """
    db = get_supabase()
    adaptations = db.table("channel_adaptations").select("status").eq("content_request_id", request_id).execute().data
    if not adaptations:
        return

    statuses = {a["status"] for a in adaptations}
    still_pending = statuses - {AdaptationStatus.PUBLISHED.value, AdaptationStatus.FAILED.value}
    if still_pending:
        return
    if AdaptationStatus.PUBLISHED.value not in statuses:
        return

    db.table("content_requests").update(
        {"status": RequestStatus.PUBLISHED.value, "updated_at": datetime.now(UTC).isoformat()}
    ).eq("id", request_id).execute()
