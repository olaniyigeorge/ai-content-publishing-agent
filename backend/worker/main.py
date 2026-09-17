"""The polling worker — the Celery replacement (architecture.md §1, §5, §9.2).

One process, one loop. Claims pending `jobs` rows via the atomic
`claim_pending_job` function (worker/claim.py — prevents EDGE_CASES.md #60,
two workers picking up the same row), dispatches to the right handler by
job_type, and on failure applies the shared backoff/dead-letter policy
(worker/retry.py) so nothing fails silently (EDGE_CASES.md #58/#61/#63).
"""

import time
import traceback

from app.config import get_settings
from claude.usage import usage_context
from db.client import get_supabase
from shared.enums import (
    JobReferenceType,
    JobStatus,
    JobType,
    PipelineStage,
    QueueStatus,
    StageEventStatus,
)
from worker.claim import claim_job
from worker.handlers.adapt import handle_adapt
from worker.handlers.evaluate import handle_evaluate
from worker.handlers.gather_evidence import handle_gather_evidence
from worker.handlers.generate import handle_generate
from worker.handlers.plan import handle_plan
from worker.handlers.publish import handle_publish
from worker.handlers.research import handle_research
from worker.retry import on_failure

HANDLERS = {
    JobType.RESEARCH.value: handle_research,
    JobType.PLAN.value: handle_plan,
    JobType.GENERATE.value: handle_generate,
    JobType.EVALUATE.value: handle_evaluate,
    JobType.ADAPT.value: handle_adapt,
    JobType.PUBLISH.value: handle_publish,
    JobType.GATHER_EVIDENCE.value: handle_gather_evidence,
}

# job_type -> pipeline_stage, used only for the failure stage_events row
# (each handler already writes its own stage_events row on success).
STAGE_FOR_JOB_TYPE = {
    JobType.RESEARCH.value: PipelineStage.RESEARCH.value,
    JobType.PLAN.value: PipelineStage.PLANNING.value,
    JobType.GENERATE.value: PipelineStage.GENERATION.value,
    JobType.EVALUATE.value: PipelineStage.EVALUATION.value,
    JobType.ADAPT.value: PipelineStage.ADAPTATION.value,
    JobType.PUBLISH.value: PipelineStage.PUBLISHING.value,
    JobType.GATHER_EVIDENCE.value: PipelineStage.EVIDENCE_GATHERING.value,
}


def _resolve_request_id(job: dict) -> str | None:
    """EDGE_CASES.md #59: a job whose referenced row was deleted must fail
    with a clear error, not crash — this returns None rather than raising so
    the caller can still write a stage_events-less failure to jobs.last_error
    when there's truly nothing to attach the event to."""
    db = get_supabase()
    ref_type, ref_id = job["reference_type"], job["reference_id"]
    try:
        if ref_type == JobReferenceType.CONTENT_REQUEST.value:
            return ref_id
        if ref_type == JobReferenceType.ARTICLE_DRAFT.value:
            rows = db.table("article_drafts").select("content_request_id").eq("id", ref_id).execute().data
            return rows[0]["content_request_id"] if rows else None
        if ref_type == JobReferenceType.PUBLISHING_QUEUE.value:
            queue_rows = db.table("publishing_queue").select("channel_adaptation_id").eq("id", ref_id).execute().data
            if not queue_rows:
                return None
            adaptation_rows = (
                db.table("channel_adaptations")
                .select("content_request_id")
                .eq("id", queue_rows[0]["channel_adaptation_id"])
                .execute()
                .data
            )
            return adaptation_rows[0]["content_request_id"] if adaptation_rows else None
    except Exception:  # noqa: BLE001 — resolution itself failing is still "can't find it"
        return None
    return None


def _mirror_publish_failure(job: dict, exhausted: bool, error: str, next_attempt_at: str | None) -> None:
    db = get_supabase()
    queue_id = job["reference_id"]
    db.table("publishing_queue").update(
        {
            "status": QueueStatus.DEAD_LETTER.value if exhausted else QueueStatus.QUEUED.value,
            "last_error": error,
            "next_attempt_at": next_attempt_at,
        }
    ).eq("id", queue_id).execute()


def process_one_job(job: dict) -> None:
    db = get_supabase()
    handler = HANDLERS[job["job_type"]]
    request_id = _resolve_request_id(job)
    try:
        with usage_context(content_request_id=request_id, job_id=job["id"], job_type=job["job_type"]):
            handler(job)
        db.table("jobs").update({"status": JobStatus.SUCCEEDED.value}).eq("id", job["id"]).execute()
    except Exception as exc:  # noqa: BLE001 — every failure must be captured, not crash the loop
        error = f"{exc}\n{traceback.format_exc(limit=3)}"
        outcome = on_failure(attempts=job["attempts"], max_attempts=job["max_attempts"], error=str(exc))
        db.table("jobs").update(
            {
                "status": JobStatus.FAILED.value if outcome["exhausted"] else JobStatus.PENDING.value,
                "last_error": error,
                "next_attempt_at": outcome["next_attempt_at"],
            }
        ).eq("id", job["id"]).execute()

        if request_id:
            # A transient failure the worker will retry isn't the same as a
            # dead end — the previous version marked every attempt FAILED
            # (hard red error in the UI) even when the job was about to
            # succeed on retry 2. Only an exhausted job is a real failure.
            db.table("stage_events").insert(
                {
                    "content_request_id": request_id,
                    "stage": STAGE_FOR_JOB_TYPE.get(job["job_type"], PipelineStage.PUBLISHING.value),
                    "status": StageEventStatus.FAILED.value
                    if outcome["exhausted"]
                    else StageEventStatus.RETRYING.value,
                    "detail": {
                        "job_id": job["id"],
                        "attempts": job["attempts"],
                        "max_attempts": job["max_attempts"],
                        "will_retry": not outcome["exhausted"],
                        "next_attempt_at": outcome["next_attempt_at"],
                    },
                    "error_message": str(exc),
                }
            ).execute()

        if job["job_type"] == JobType.PUBLISH.value:
            _mirror_publish_failure(job, outcome["exhausted"], str(exc), outcome["next_attempt_at"])


def run_forever() -> None:
    """EDGE_CASES.md #58: if Supabase is unreachable (or, as during initial
    setup, migrations haven't been applied yet), claim_job() itself can
    raise. That must not kill the whole worker process — a crashed worker is
    a *more* silent failure than a per-job one, since nothing gets written
    to jobs.last_error or stage_events at all. Log and back off instead."""
    settings = get_settings()
    print(f"worker starting, poll interval {settings.worker_poll_interval_seconds}s")
    while True:
        try:
            job = claim_job()
        except Exception as exc:  # noqa: BLE001
            print(f"claim_job() failed: {exc} — retrying in {settings.worker_poll_interval_seconds}s")
            time.sleep(settings.worker_poll_interval_seconds)
            continue
        if job is None:
            time.sleep(settings.worker_poll_interval_seconds)
            continue
        print(f"processing job {job['id']} ({job['job_type']}), attempt {job['attempts']}")
        try:
            process_one_job(job)
        except Exception as exc:  # noqa: BLE001 — process_one_job's OWN failure-handling code
            # (e.g. an insert hitting a DB constraint) must not kill the loop
            # either — that's a worse silent failure than one stuck job,
            # since it takes every other in-flight request down with it.
            print(f"process_one_job({job['id']}) failed outside its own handling: {exc}")


if __name__ == "__main__":
    run_forever()
