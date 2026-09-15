from datetime import UTC, datetime

from app.services.intake_guards import (
    validate_attachments,
    validate_raw_idea,
    validate_supporting_material,
    validate_target_audience,
)
from app.services.upload_service import BUCKET
from db.client import get_supabase
from shared.enums import (
    JobReferenceType,
    JobType,
    PipelineStage,
    RequestStatus,
    StageEventStatus,
)
from shared.errors import ValidationFailure
from shared.models import ContentRequestCreate, ContentRequestOut


def create_content_request(body: ContentRequestCreate, submitted_by_user_id: str) -> ContentRequestOut:
    """EDGE_CASES.md #1: reject if there's neither a raw idea nor any
    attachment — the pipeline must never run on nothing. Everything else
    (too short, too long, gibberish, malformed attachments) is enforced by
    app/services/intake_guards.py."""
    has_idea = bool(body.raw_idea and body.raw_idea.strip())
    has_attachments = len(body.attachments) > 0

    if not has_idea and not has_attachments:
        raise ValidationFailure("a content request needs a raw idea, a source URL, or another attachment")
    if has_idea:
        validate_raw_idea(body.raw_idea)
    validate_target_audience(body.target_audience or "")
    validate_supporting_material(body.supporting_material)
    validate_attachments(body.attachments)

    db = get_supabase()
    now = datetime.now(UTC).isoformat()
    request_row = (
        db.table("content_requests")
        .insert(
            {
                "raw_idea": body.raw_idea,
                "target_audience": body.target_audience,
                "supporting_material": body.supporting_material,
                "status": RequestStatus.INTAKE.value,
                "submitted_by_user_id": submitted_by_user_id,
                "updated_at": now,
            }
        )
        .execute()
        .data[0]
    )
    request_id = request_row["id"]

    attachment_rows = []
    for attachment in body.attachments:
        # image/file attachments only carry storage_path from the upload step
        # — resolve the public URL now so the frontend can always just read
        # `url`, regardless of attachment type.
        url = attachment.url
        if not url and attachment.storage_path:
            url = db.storage.from_(BUCKET).get_public_url(attachment.storage_path)
        attachment_rows.append(
            db.table("intake_attachments")
            .insert(
                {
                    "content_request_id": request_id,
                    "type": attachment.type.value,
                    "url": url,
                    "storage_path": attachment.storage_path,
                    "description": attachment.description,
                }
            )
            .execute()
            .data[0]
        )

    db.table("stage_events").insert(
        {
            "content_request_id": request_id,
            "stage": PipelineStage.INTAKE.value,
            "status": StageEventStatus.SUCCEEDED.value,
            "detail": {"attachments": len(attachment_rows), "has_idea": has_idea},
        }
    ).execute()

    url_attachment_ids = [a["id"] for a in attachment_rows if a["type"] == "url"]

    # The request row above already exists. If anything from here on fails
    # (a transient network blip talking to Supabase, say), we must not leave
    # a row sitting at "intake" forever with no job and no explanation — that
    # reads as a live, in-progress request when it's actually dead. Mark it
    # failed with a visible stage event instead of letting the exception
    # propagate past a half-finished request.
    try:
        db.table("jobs").insert(
            {
                "job_type": JobType.RESEARCH.value,
                "reference_type": JobReferenceType.CONTENT_REQUEST.value,
                "reference_id": request_id,
                "payload": {"attachment_ids": url_attachment_ids},
            }
        ).execute()

        db.table("content_requests").update({"status": RequestStatus.RESEARCHING.value, "updated_at": now}).eq(
            "id", request_id
        ).execute()
        db.table("stage_events").insert(
            {
                "content_request_id": request_id,
                "stage": PipelineStage.RESEARCH.value,
                "status": StageEventStatus.STARTED.value,
            }
        ).execute()
    except Exception as exc:  # noqa: BLE001 — see comment above: must not orphan the row
        try:
            db.table("content_requests").update(
                {"status": RequestStatus.FAILED.value, "updated_at": datetime.now(UTC).isoformat()}
            ).eq("id", request_id).execute()
            db.table("stage_events").insert(
                {
                    "content_request_id": request_id,
                    "stage": PipelineStage.RESEARCH.value,
                    "status": StageEventStatus.FAILED.value,
                    "error_message": f"failed to start the research job: {exc}",
                }
            ).execute()
        except Exception:  # noqa: BLE001 — best-effort; the outer raise still surfaces the 500
            pass
        raise

    request_row["status"] = RequestStatus.RESEARCHING.value
    return ContentRequestOut(**request_row)
