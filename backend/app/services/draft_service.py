"""Rewrite-with-AI for an existing draft: enqueues a targeted `generate` job
seeded with revision instructions, producing a new draft version rather than
mutating the existing row (mirrors the evaluate->generate revision loop and
the human `revise_requested` path in review_service.py).
"""

from db.client import get_supabase
from shared.enums import JobReferenceType, JobType, RequestStatus
from shared.errors import NotFound


def rewrite_draft(draft_id: str, instructions: str | None) -> dict:
    db = get_supabase()
    rows = db.table("article_drafts").select("*").eq("id", draft_id).execute().data
    if not rows:
        raise NotFound(f"article draft {draft_id} not found")
    draft = rows[0]

    job_row = (
        db.table("jobs")
        .insert(
            {
                "job_type": JobType.GENERATE.value,
                "reference_type": JobReferenceType.ARTICLE_DRAFT.value,
                "reference_id": draft_id,
                "payload": {"revision_instructions": instructions or "Rewrite and improve this draft."},
            }
        )
        .execute()
        .data[0]
    )
    db.table("content_requests").update({"status": RequestStatus.REVISING.value}).eq(
        "id", draft["content_request_id"]
    ).execute()
    return {"job_id": job_row["id"], "status": "queued"}
