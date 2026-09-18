"""worker/main.py process_one_job — TESTING_FINDINGS2.md, 2026-09-18: a job
that exhausted its retries (e.g. planning failing 3x on the same missing
target_keywords field) left jobs.status FAILED and a FAILED stage_events
row, but content_requests.status was never updated — the request sat at
whatever in-flight status it had (e.g. "planning") forever, with no
terminal state for the UI to show. RequestStatus.FAILED exists for exactly
this; process_one_job must actually set it on exhaustion."""

from worker import main as worker_main

REQUEST_ID = "00000000-0000-0000-0000-000000000070"
JOB_ID = "00000000-0000-0000-0000-000000000071"


def _seed(fake_db, *, attempts: int, max_attempts: int = 3):
    fake_db.table("content_requests").insert(
        {"id": REQUEST_ID, "status": "planning", "raw_idea": "an idea", "target_audience": "marketers"}
    ).execute()
    fake_db.table("jobs").insert(
        {
            "id": JOB_ID,
            "job_type": "plan",
            "reference_type": "content_request",
            "reference_id": REQUEST_ID,
            "payload": {},
            "status": "processing",
            "attempts": attempts,
            "max_attempts": max_attempts,
        }
    ).execute()


def _failing_handler(job):
    raise RuntimeError("boom")


def test_exhausted_job_marks_request_failed(fake_db, monkeypatch):
    _seed(fake_db, attempts=3, max_attempts=3)
    monkeypatch.setitem(worker_main.HANDLERS, "plan", _failing_handler)

    job = fake_db.table("jobs").select("*").execute().data[0]
    worker_main.process_one_job(job)

    request = fake_db.table("content_requests").select("*").eq("id", REQUEST_ID).execute().data[0]
    assert request["status"] == "failed"

    jobs = fake_db.table("jobs").select("*").execute().data
    assert jobs[0]["status"] == "failed"


def test_non_exhausted_job_leaves_request_status_alone(fake_db, monkeypatch):
    _seed(fake_db, attempts=1, max_attempts=3)
    monkeypatch.setitem(worker_main.HANDLERS, "plan", _failing_handler)

    job = fake_db.table("jobs").select("*").execute().data[0]
    worker_main.process_one_job(job)

    request = fake_db.table("content_requests").select("*").eq("id", REQUEST_ID).execute().data[0]
    assert request["status"] == "planning"

    jobs = fake_db.table("jobs").select("*").execute().data
    assert jobs[0]["status"] == "pending"
