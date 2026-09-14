from db.client import get_supabase
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
        publishing_queue=[PublishingQueueOut(**q) for q in queue_items],
        stage_events=[StageEventOut(**e) for e in stage_events],
    )
