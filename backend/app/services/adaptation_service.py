"""Rewrite-with-AI for a single channel adaptation: enqueues an `adapt` job
scoped to one channel (via payload.channel), seeded with the current content
and instructions, producing a new channel_adaptations row rather than
mutating the existing one.
"""

from db.client import get_supabase
from shared.enums import JobReferenceType, JobType
from shared.errors import NotFound


def rewrite_channel_adaptation(adaptation_id: str, instructions: str | None) -> dict:
    db = get_supabase()
    rows = db.table("channel_adaptations").select("*").eq("id", adaptation_id).execute().data
    if not rows:
        raise NotFound(f"channel adaptation {adaptation_id} not found")
    adaptation = rows[0]

    job_row = (
        db.table("jobs")
        .insert(
            {
                "job_type": JobType.ADAPT.value,
                "reference_type": JobReferenceType.ARTICLE_DRAFT.value,
                "reference_id": adaptation["article_draft_id"],
                "payload": {
                    "channel": adaptation["channel"],
                    "instructions": instructions or "Rewrite and improve this channel adaptation.",
                    "previous_content": adaptation["content"],
                },
            }
        )
        .execute()
        .data[0]
    )
    return {"job_id": job_row["id"], "status": "queued"}
