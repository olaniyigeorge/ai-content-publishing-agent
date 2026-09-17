from datetime import UTC, datetime

import claude.service as claude_service
from claude.quality_guards import check_channel_adaptation, truncate_to_limit
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

    A "rewrite with AI" request (see app/services/adaptation_service.py)
    reuses this same handler, scoped to a single channel via
    payload.channel/instructions/previous_content, so it doesn't re-adapt the
    other two channels or re-run the full-adaptation stage_events/status
    transition below.
    """
    db = get_supabase()
    payload = job.get("payload") or {}
    draft_id = job["reference_id"]
    draft = db.table("article_drafts").select("*").eq("id", draft_id).execute().data[0]
    request_id = draft["content_request_id"]
    request_row = db.table("content_requests").select("*").eq("id", request_id).execute().data[0]

    rewrite_channel = payload.get("channel")
    channels = [rewrite_channel] if rewrite_channel else CHANNELS

    created = []
    failures = []
    for channel in channels:
        try:
            result = claude_service.adapt_for_channel(
                channel=channel,
                article_title=draft["title"],
                article_body_markdown=draft["body_markdown"],
                target_audience=request_row["target_audience"],
                revision_instructions=payload.get("instructions") if rewrite_channel else None,
                previous_content=payload.get("previous_content") if rewrite_channel else None,
            )
        except Exception as exc:  # noqa: BLE001 — recorded, not swallowed
            failures.append({"channel": channel, "error": str(exc)})
            continue

        # Deterministic recheck: formatting_check in `result` is the model's
        # own self-report. Real char/word counts win over whatever it claims
        # (EDGE_CASES.md-style guard — see claude/quality_guards.py).
        content = result["content"]
        guard = check_channel_adaptation(channel=channel, content=content, content_format=result["content_format"])
        formatting_check = {**result["formatting_check"], **guard}

        # Over-limit char-based channels (currently only X) get one
        # deterministic truncation pass instead of being silently dropped.
        if not guard["within_limit"]:
            trimmed = truncate_to_limit(content, channel)
            if trimmed is not None:
                retry_guard = check_channel_adaptation(
                    channel=channel, content=trimmed, content_format=result["content_format"]
                )
                if retry_guard["within_limit"]:
                    content = trimmed
                    guard = retry_guard
                    formatting_check = {**result["formatting_check"], **guard, "auto_trimmed": True}

        adaptation_status = AdaptationStatus.APPROVED.value if guard["within_limit"] else AdaptationStatus.FAILED.value

        adaptation_row = (
            db.table("channel_adaptations")
            .upsert(
                {
                    "content_request_id": request_id,
                    "article_draft_id": draft_id,
                    "channel": channel,
                    "content": content,
                    "content_format": result["content_format"],
                    "formatting_check": formatting_check,
                    "status": adaptation_status,
                },
                on_conflict="article_draft_id,channel",
            )
            .execute()
            .data[0]
        )
        created.append(adaptation_row)

        if not guard["within_limit"]:
            failures.append({"channel": channel, "error": "; ".join(guard["violations"])})
            continue

        queue_row = (
            db.table("publishing_queue")
            .insert(
                {
                    "channel_adaptation_id": adaptation_row["id"],
                    "status": QueueStatus.QUEUED.value,
                    "next_attempt_at": datetime.now(UTC).isoformat(),
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

    if rewrite_channel:
        db.table("stage_events").insert(
            {
                "content_request_id": request_id,
                "stage": PipelineStage.ADAPTATION.value,
                "status": StageEventStatus.SUCCEEDED.value if not failures else StageEventStatus.FAILED.value,
                "detail": {"channel": rewrite_channel, "rewrite": True, "failures": failures},
                "error_message": "; ".join(f"{f['channel']}: {f['error']}" for f in failures) or None,
            }
        ).execute()
        return

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
        {"status": RequestStatus.QUEUED.value, "updated_at": datetime.now(UTC).isoformat()}
    ).eq("id", request_id).execute()
