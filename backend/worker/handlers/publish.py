from datetime import UTC, datetime

from db.client import get_supabase
from worker.publishing_adapter import publish


def handle_publish(job: dict) -> None:
    """Performs the actual (mocked) publish call. Raises on failure — the
    generic dispatcher in worker/main.py owns retry/backoff/dead-letter for
    every job_type, including mirroring state into publishing_queue for this
    one (architecture.md §5's mechanism, simplified to route through the
    single `jobs` retry loop rather than a second poll loop against
    publishing_queue directly — see BUILD_LOG.md for the note).

    EDGE_CASES.md #39: this adapter is a mock — it never actually reaches
    LinkedIn/X/an email provider. Writing 'published' here would claim a real
    delivery that didn't happen, so success lands on 'ready_to_publish'
    instead: the content is prepared and the mock "send" step succeeded, but
    a human still has to copy it out and post it themselves, then confirm
    with the manual 'published' override (app/api/publishing.py) — which is
    also what finalizes the content_request via maybe_finalize_request_status."""
    db = get_supabase()
    queue_id = job["reference_id"]
    queue_row = db.table("publishing_queue").select("*").eq("id", queue_id).execute().data[0]
    adaptation = (
        db.table("channel_adaptations").select("*").eq("id", queue_row["channel_adaptation_id"]).execute().data[0]
    )

    publish(adaptation["channel"], adaptation["content"])  # raises PublishFailure on failure

    now = datetime.now(UTC).isoformat()
    db.table("publishing_queue").update(
        {"status": "ready_to_publish", "updated_at": now, "last_error": None}
    ).eq("id", queue_id).execute()
