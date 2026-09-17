"""EDGE_CASES.md #61: a `processing` job row left behind by a worker that
died mid-handler (OOM, redeploy, SIGKILL) must not permanently block
has_pending_revision — only a job that's genuinely still running (recently
claimed) should count as in flight. A `pending` row always blocks, since
it's genuinely queued even mid-backoff."""

from datetime import UTC, datetime, timedelta

from app.config import get_settings
from app.services.job_guard import has_pending_revision

DRAFT_ID = "00000000-0000-0000-0000-000000000050"


def _iso(dt) -> str:
    return dt.isoformat()


def test_recent_processing_job_blocks(fake_db):
    fake_db.table("jobs").insert(
        {
            "job_type": "generate",
            "reference_type": "article_draft",
            "reference_id": DRAFT_ID,
            "status": "processing",
            "updated_at": _iso(datetime.now(UTC)),
        }
    ).execute()

    assert has_pending_revision(DRAFT_ID) is True


def test_stale_processing_job_does_not_block(fake_db):
    """The exact bug this guards against: a worker crashed mid-handler and
    left this row at 'processing' forever. Once it's older than the stale
    threshold, it must stop blocking future rewrites of this draft."""
    settings = get_settings()
    stale_at = datetime.now(UTC) - timedelta(seconds=settings.job_stale_processing_seconds + 60)
    fake_db.table("jobs").insert(
        {
            "job_type": "generate",
            "reference_type": "article_draft",
            "reference_id": DRAFT_ID,
            "status": "processing",
            "updated_at": _iso(stale_at),
        }
    ).execute()

    assert has_pending_revision(DRAFT_ID) is False


def test_pending_job_blocks_regardless_of_age(fake_db):
    """A pending row is genuinely queued (even mid-backoff it will run) —
    only 'processing' gets the staleness check."""
    settings = get_settings()
    old_at = datetime.now(UTC) - timedelta(seconds=settings.job_stale_processing_seconds + 3600)
    fake_db.table("jobs").insert(
        {
            "job_type": "generate",
            "reference_type": "article_draft",
            "reference_id": DRAFT_ID,
            "status": "pending",
            "updated_at": _iso(old_at),
        }
    ).execute()

    assert has_pending_revision(DRAFT_ID) is True


def test_no_jobs_does_not_block(fake_db):
    assert has_pending_revision(DRAFT_ID) is False


def test_succeeded_job_does_not_block(fake_db):
    fake_db.table("jobs").insert(
        {
            "job_type": "generate",
            "reference_type": "article_draft",
            "reference_id": DRAFT_ID,
            "status": "succeeded",
            "updated_at": _iso(datetime.now(UTC)),
        }
    ).execute()

    assert has_pending_revision(DRAFT_ID) is False
