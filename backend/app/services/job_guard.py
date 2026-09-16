"""Pre-enqueue checks shared by every path that can queue a `generate` job
against an existing article draft (rewrite_draft, submit_review's
revise_requested branch). TESTING_FINDINGS.md, 2026-09-16: a human clicking
"Rewrite with AI" on a draft that the automatic evaluate->generate loop had
already re-queued a revision for produced two `generate` jobs against the
same parent draft. Both compute `version = parent.version + 1` from the same
unchanged parent row, so the second one always loses to the
`article_drafts_version_unique` constraint — and because neither job's
target (the parent) ever changes, the worker's normal retry/backoff can't
self-heal it; it just fails identically every attempt until dead-lettered.
Rejecting the second enqueue attempt up front is the actual fix.
"""

from db.client import get_supabase
from shared.enums import JobReferenceType, JobStatus, JobType

IN_FLIGHT_STATUSES = [JobStatus.PENDING.value, JobStatus.PROCESSING.value]


def has_pending_revision(draft_id: str) -> bool:
    db = get_supabase()
    rows = (
        db.table("jobs")
        .select("id")
        .eq("job_type", JobType.GENERATE.value)
        .eq("reference_type", JobReferenceType.ARTICLE_DRAFT.value)
        .eq("reference_id", draft_id)
        .in_("status", IN_FLIGHT_STATUSES)
        .execute()
        .data
    )
    return bool(rows)
