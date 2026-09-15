from datetime import UTC, datetime

from app.services.request_state_service import maybe_finalize_request_status
from db.client import get_supabase
from worker.publishing_adapter import publish


def handle_publish(job: dict) -> None:
    """Performs the actual (mocked) publish call. Raises on failure — the
    generic dispatcher in worker/main.py owns retry/backoff/dead-letter for
    every job_type, including mirroring state into publishing_queue for this
    one (architecture.md §5's mechanism, simplified to route through the
    single `jobs` retry loop rather than a second poll loop against
    publishing_queue directly — see BUILD_LOG.md for the note)."""
    db = get_supabase()
    queue_id = job["reference_id"]
    queue_row = db.table("publishing_queue").select("*").eq("id", queue_id).execute().data[0]
    adaptation = (
        db.table("channel_adaptations").select("*").eq("id", queue_row["channel_adaptation_id"]).execute().data[0]
    )

    publish(adaptation["channel"], adaptation["content"])  # raises PublishFailure on failure

    now = datetime.now(UTC).isoformat()
    db.table("publishing_queue").update(
        {"status": "published", "published_at": now, "updated_at": now, "last_error": None}
    ).eq("id", queue_id).execute()
    db.table("channel_adaptations").update({"status": "published", "updated_at": now}).eq(
        "id", adaptation["id"]
    ).execute()

    maybe_finalize_request_status(adaptation["content_request_id"])
