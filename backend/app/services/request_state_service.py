from datetime import UTC, datetime

from app.services.job_guard import has_pending_revision
from app.services.review_service import REVIEWABLE_DRAFT_STATUSES
from db.client import get_supabase
from shared.enums import AdaptationStatus, JobReferenceType, JobType, RequestStatus
from shared.errors import NotFound
from shared.models import (
    ArticleDraftOut,
    ChannelAdaptationOut,
    ClaudeUsageOut,
    ContentRequestDetail,
    ContentRequestOut,
    EvaluationOut,
    HumanReviewOut,
    IntakeAttachmentOut,
    PublishingQueueOut,
    SourceOut,
    SourceOverrideIn,
    StageEventOut,
    UsageModelBreakdown,
    UsageSummaryOut,
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
    usage_rows = (
        db.table("claude_usage")
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
        usage=[ClaudeUsageOut(**u) for u in usage_rows],
    )


def override_source_status(request_id: str, source_id: str, body: SourceOverrideIn) -> SourceOut:
    """A human reviewer's manual selected/discarded call on a source,
    overriding whatever claude_service.select_sources originally decided
    during the research step. Kept separate from that automated pass rather
    than re-running it, since the reviewer's judgment is meant to be final.

    Discarding a source the current draft actually relied on isn't just a
    label change — the draft may still be citing it. Regenerate rather than
    leave a reviewer-rejected source silently still backing the text on
    screen."""
    db = get_supabase()
    rows = db.table("sources").select("*").eq("id", source_id).eq("content_request_id", request_id).execute().data
    if not rows:
        raise NotFound(f"source {source_id} not found on content request {request_id}")

    update = {"status": body.status.value}
    if body.status == "discarded":
        update["discard_reason"] = body.reason or "discarded by reviewer"
    else:
        update["discard_reason"] = None
    updated = db.table("sources").update(update).eq("id", source_id).execute().data[0]

    if body.status == "discarded":
        _regenerate_drafts_using_discarded_source(db, request_id, source_id, body.reason)

    return SourceOut(**updated)


def _regenerate_drafts_using_discarded_source(
    db, request_id: str, source_id: str, reason: str | None
) -> None:
    drafts = (
        db.table("article_drafts")
        .select("*")
        .eq("content_request_id", request_id)
        .in_("status", list(REVIEWABLE_DRAFT_STATUSES))
        .execute()
        .data
    )
    affected = [d for d in drafts if source_id in (d.get("source_ids_used") or [])]
    if not affected:
        return

    now = datetime.now(UTC).isoformat()
    instructions = (
        "A reviewer discarded one of the sources this draft relied on"
        + (f" ({reason})" if reason else "")
        + ". Regenerate without relying on it — if it was the only support for a claim, either "
        "find support in another provided source, hedge the claim as unverified, or drop it "
        "rather than restating it as fact."
    )
    for draft in affected:
        # Same race this guards against elsewhere (TESTING_FINDINGS.md,
        # 2026-09-16): don't queue a second revision if one against this
        # draft is already in flight.
        if has_pending_revision(draft["id"]):
            continue
        db.table("jobs").insert(
            {
                "job_type": JobType.GENERATE.value,
                "reference_type": JobReferenceType.ARTICLE_DRAFT.value,
                "reference_id": draft["id"],
                "payload": {"revision_instructions": instructions},
            }
        ).execute()
        db.table("content_requests").update({"status": RequestStatus.REVISING.value, "updated_at": now}).eq(
            "id", request_id
        ).execute()


def get_usage_summary() -> UsageSummaryOut:
    """Account-wide Claude spend, across every content request — the "and
    total" half of "how many tokens spent on each pass and total". Per-request
    spend is the `usage` list already returned by get_content_request_detail;
    this is the one number that can't be derived from a single request."""
    rows = get_supabase().table("claude_usage").select("model,input_tokens,output_tokens,cost_usd").execute().data

    by_model: dict[str, UsageModelBreakdown] = {}
    for row in rows:
        entry = by_model.setdefault(
            row["model"], UsageModelBreakdown(input_tokens=0, output_tokens=0, cost_usd=0.0, call_count=0)
        )
        entry.input_tokens += row["input_tokens"]
        entry.output_tokens += row["output_tokens"]
        entry.cost_usd += row["cost_usd"]
        entry.call_count += 1

    return UsageSummaryOut(
        total_input_tokens=sum(r["input_tokens"] for r in rows),
        total_output_tokens=sum(r["output_tokens"] for r in rows),
        total_cost_usd=sum(r["cost_usd"] for r in rows),
        call_count=len(rows),
        by_model=by_model,
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
