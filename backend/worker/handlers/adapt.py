from datetime import datetime, timezone

import claude.service as claude_service
from db.client import get_supabase
from shared.enums import (
    AdaptationStatus,
    Channel,
    JobReferenceType,
    JobType,
    PipelineStage,
    QueueStatus,
    RequestStatus,
    StageEventStatus,
)

CHANNELS = [Channel.LINKEDIN.value, Channel.X.value, Channel.NEWSLETTER.value]


def handle_adapt(job: dict) -> None:
    """EDGE_CASES.md #34: each channel gets its own Claude call with a
    channel-specific system prompt (claude/prompts/adapt.py), so the three
    outputs are structurally different, not the same text three times.
    EDGE_CASES.md #37: a per-channel failure is caught and recorded — it does
    not silently drop that channel's adaptation.
    """
    db = get_supabase()
    draft_id = job["reference_id"]
    draft = db.table("article_drafts").select("*").eq("id", draft_id).execute().data[0]
    request_id = draft["content_request_id"]
    request_row = db.table("content_requests").select("*").eq("id", request_id).execute().data[0]

    created = []
    failures = []
    for channel in CHANNELS:
        try:
            result = claude_service.adapt_for_channel(
                channel=channel,
                article_title=draft["title"],
                article_body_markdown=draft["body_markdown"],
                target_audience=request_row["target_audience"],
            )
        except Exception as exc:  # noqa: BLE001 — recorded, not swallowed
            failures.append({"channel": channel, "error": str(exc)})
            continue

        adaptation_row = (
            db.table("channel_adaptations")
            .insert(
                {
                    "content_request_id": request_id,
                    "article_draft_id": draft_id,
                    "channel": channel,
                    "content": result["content"],
                    "content_format": result["content_format"],
                    "formatting_check": result["formatting_check"],
                    "status": AdaptationStatus.APPROVED.value,
                }
            )
            .execute()
            .data[0]
        )
        created.append(adaptation_row)

        queue_row = (
            db.table("publishing_queue")
            .insert(
                {
                    "channel_adaptation_id": adaptation_row["id"],
                    "status": QueueStatus.QUEUED.value,
                    "next_attempt_at": datetime.now(timezone.utc).isoformat(),
                }
            )
            .execute()
            .data[0]
        )
        db.table("jobs").insert(
            {
                "job_type": JobType.PUBLISH.value,
                "reference_type": JobReferenceType.PUBLISHING_QUEUE.value,
                "reference_id": queue_row["id"],
                "payload": {"channel_adaptation_id": adaptation_row["id"]},
            }
        ).execute()

    db.table("stage_events").insert(
        {
            "content_request_id": request_id,
            "stage": PipelineStage.ADAPTATION.value,
            "status": StageEventStatus.SUCCEEDED.value if not failures else StageEventStatus.FAILED.value,
            "detail": {"channels_adapted": [c["channel"] for c in created], "failures": failures},
            "error_message": "; ".join(f"{f['channel']}: {f['error']}" for f in failures) or None,
        }
    ).execute()

    db.table("content_requests").update(
        {"status": RequestStatus.QUEUED.value, "updated_at": datetime.now(timezone.utc).isoformat()}
    ).eq("id", request_id).execute()
