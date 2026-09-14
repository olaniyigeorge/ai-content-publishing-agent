from datetime import datetime, timezone

from db.client import get_supabase
from shared.enums import JobReferenceType, JobType, PipelineStage, RequestStatus, StageEventStatus
from shared.errors import ValidationFailure
from shared.models import ContentRequestCreate, ContentRequestOut

MIN_IDEA_LENGTH = 3  # EDGE_CASES.md #4 — reject a bare single character, not a genuine single-word idea


def create_content_request(body: ContentRequestCreate, submitted_by_user_id: str) -> ContentRequestOut:
    """EDGE_CASES.md #1: reject if there's neither a raw idea nor any
    attachment — the pipeline must never run on nothing."""
    has_idea = bool(body.raw_idea and body.raw_idea.strip())
    has_attachments = len(body.attachments) > 0

    if not has_idea and not has_attachments:
        raise ValidationFailure("a content request needs a raw idea, a source URL, or another attachment")
    if has_idea and len(body.raw_idea.strip()) < MIN_IDEA_LENGTH:
        raise ValidationFailure("raw_idea is too short to be a usable content idea")
    if not body.target_audience or not body.target_audience.strip():
        raise ValidationFailure("target_audience is required")

    for attachment in body.attachments:
        if attachment.type == "url" and not attachment.url:
            raise ValidationFailure("a 'url' attachment must include a url")
        if attachment.type != "url" and not attachment.storage_path:
            raise ValidationFailure(f"a '{attachment.type}' attachment must include a storage_path")

    db = get_supabase()
    now = datetime.now(timezone.utc).isoformat()
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
        attachment_rows.append(
            db.table("intake_attachments")
            .insert(
                {
                    "content_request_id": request_id,
                    "type": attachment.type.value,
                    "url": attachment.url,
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

    request_row["status"] = RequestStatus.RESEARCHING.value
    return ContentRequestOut(**request_row)
