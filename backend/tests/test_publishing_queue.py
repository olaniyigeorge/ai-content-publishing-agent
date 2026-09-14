"""Scenario 7 + EDGE_CASES.md #39, #40 — queue transitions and the
dead-letter mirror, exercised through worker.main.process_one_job so the
retry/backoff/dead-letter path is tested end to end without a live DB."""

from worker import main as worker_main
from worker.publishing_adapter import FORCE_FAIL_MARKER

ADAPTATION_ID = "00000000-0000-0000-0000-000000000020"
QUEUE_ID = "00000000-0000-0000-0000-000000000021"
REQUEST_ID = "00000000-0000-0000-0000-000000000022"


def _seed(fake_db, content: str):
    fake_db.table("channel_adaptations").insert(
        {"id": ADAPTATION_ID, "content_request_id": REQUEST_ID, "channel": "linkedin", "content": content}
    ).execute()
    fake_db.table("publishing_queue").insert(
        {"id": QUEUE_ID, "channel_adaptation_id": ADAPTATION_ID, "status": "processing", "attempts": 1, "max_attempts": 3}
    ).execute()


def test_successful_publish_marks_queue_and_adaptation_published(fake_db):
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
    assert queue_row["status"] == "published"
    assert queue_row["last_error"] is None


def test_failed_publish_below_max_attempts_stays_queued_for_retry(fake_db):
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


def test_failed_publish_at_max_attempts_goes_dead_letter(fake_db):
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
