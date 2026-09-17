"""Scenario 7 + EDGE_CASES.md #39, #40 — queue transitions and the
dead-letter mirror, exercised through worker.main.process_one_job so the
retry/backoff/dead-letter path is tested end to end without a live DB."""

from worker import main as worker_main
from worker.publishing_adapter import FORCE_FAIL_MARKER

ADAPTATION_ID = "00000000-0000-0000-0000-000000000020"
QUEUE_ID = "00000000-0000-0000-0000-000000000021"
REQUEST_ID = "00000000-0000-0000-0000-000000000022"


def _seed(fake_db, content: str):
    fake_db.table("content_requests").insert(
        {"id": REQUEST_ID, "status": "queued", "target_audience": "SaaS marketers"}
    ).execute()
    fake_db.table("channel_adaptations").insert(
        {"id": ADAPTATION_ID, "content_request_id": REQUEST_ID, "channel": "linkedin", "content": content, "status": "queued"}
    ).execute()
    fake_db.table("publishing_queue").insert(
        {"id": QUEUE_ID, "channel_adaptation_id": ADAPTATION_ID, "status": "processing", "attempts": 1, "max_attempts": 3}
    ).execute()


def test_successful_publish_marks_queue_ready_to_publish(fake_db):
    """EDGE_CASES.md #39: the publish adapter is a mock — it never actually
    reaches the platform — so a successful mock "send" must land on
    'ready_to_publish', not the honest terminal 'published'. The adaptation
    itself is untouched here too; it only becomes 'published' once a human
    manually confirms via the publishing-queue API (test_publishing_queue_api.py)."""
    _seed(fake_db, content="a normal linkedin post")
    job = {
        "id": "j1",
        "job_type": "publish",
        "reference_type": "publishing_queue",
        "reference_id": QUEUE_ID,
        "attempts": 1,
        "max_attempts": 3,
        "payload": {"channel_adaptation_id": ADAPTATION_ID},
    }
    worker_main.process_one_job(job)

    queue_row = fake_db.table("publishing_queue").select("*").eq("id", QUEUE_ID).execute().data[0]
    assert queue_row["status"] == "ready_to_publish"
    assert queue_row["last_error"] is None
    assert queue_row.get("published_at") is None

    adaptation_row = fake_db.table("channel_adaptations").select("*").eq("id", ADAPTATION_ID).execute().data[0]
    assert adaptation_row["status"] == "queued"


def test_successful_publish_does_not_auto_finalize_request(fake_db):
    """content_requests must not claim 'published' off the mock adapter alone
    — only a human's manual publish confirmation (app/api/publishing.py)
    finalizes the request, since that's the only point a real publish is
    actually asserted to have happened."""
    _seed(fake_db, content="a normal linkedin post")
    job = {
        "id": "j1",
        "job_type": "publish",
        "reference_type": "publishing_queue",
        "reference_id": QUEUE_ID,
        "attempts": 1,
        "max_attempts": 3,
        "payload": {"channel_adaptation_id": ADAPTATION_ID},
    }
    worker_main.process_one_job(job)

    request_row = fake_db.table("content_requests").select("*").eq("id", REQUEST_ID).execute().data[0]
    assert request_row["status"] == "queued"


def test_request_status_not_finalized_while_another_channel_still_pending(fake_db):
    _seed(fake_db, content="a normal linkedin post")
    other_adaptation_id = "00000000-0000-0000-0000-000000000023"
    fake_db.table("channel_adaptations").insert(
        {"id": other_adaptation_id, "content_request_id": REQUEST_ID, "channel": "x", "content": "x post", "status": "queued"}
    ).execute()
    job = {
        "id": "j1",
        "job_type": "publish",
        "reference_type": "publishing_queue",
        "reference_id": QUEUE_ID,
        "attempts": 1,
        "max_attempts": 3,
        "payload": {"channel_adaptation_id": ADAPTATION_ID},
    }
    worker_main.process_one_job(job)

    request_row = fake_db.table("content_requests").select("*").eq("id", REQUEST_ID).execute().data[0]
    assert request_row["status"] == "queued"


def test_failed_publish_below_max_attempts_stays_queued_for_retry(fake_db):
    """A transient failure the worker will retry on its own isn't a hard
    error — the stage_events row for it must say 'retrying', not 'failed',
    so the UI doesn't show a red hard-failure icon for something that's
    still self-healing."""
    _seed(fake_db, content=f"a post {FORCE_FAIL_MARKER}")
    job = {
        "id": "j2",
        "job_type": "publish",
        "reference_type": "publishing_queue",
        "reference_id": QUEUE_ID,
        "attempts": 1,
        "max_attempts": 3,
        "payload": {"channel_adaptation_id": ADAPTATION_ID},
    }
    worker_main.process_one_job(job)

    queue_row = fake_db.table("publishing_queue").select("*").eq("id", QUEUE_ID).execute().data[0]
    assert queue_row["status"] == "queued"
    assert queue_row["last_error"] is not None
    assert queue_row["next_attempt_at"] is not None

    events = fake_db.table("stage_events").select("*").eq("content_request_id", REQUEST_ID).execute().data
    assert events[-1]["status"] == "retrying"
    assert events[-1]["detail"]["will_retry"] is True


def test_failed_publish_at_max_attempts_goes_dead_letter(fake_db):
    """Once attempts are exhausted, this really is a hard failure — the
    stage_events row should say so, unlike the below-cap retry case above."""
    _seed(fake_db, content=f"a post {FORCE_FAIL_MARKER}")
    job = {
        "id": "j3",
        "job_type": "publish",
        "reference_type": "publishing_queue",
        "reference_id": QUEUE_ID,
        "attempts": 3,
        "max_attempts": 3,
        "payload": {"channel_adaptation_id": ADAPTATION_ID},
    }
    worker_main.process_one_job(job)

    queue_row = fake_db.table("publishing_queue").select("*").eq("id", QUEUE_ID).execute().data[0]
    assert queue_row["status"] == "dead_letter"
    assert queue_row["next_attempt_at"] is None

    events = fake_db.table("stage_events").select("*").eq("content_request_id", REQUEST_ID).execute().data
    assert events[-1]["status"] == "failed"
    assert events[-1]["detail"]["will_retry"] is False
