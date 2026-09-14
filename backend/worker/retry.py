"""Backoff + dead-letter logic — architecture.md §5. Shared by jobs and
publishing_queue handlers so the retry policy lives in exactly one place.
"""

from datetime import datetime, timedelta, timezone


def backoff_seconds(attempts: int) -> int:
    return 60 * (2**attempts)  # 2^attempts minutes


def next_attempt_at(attempts: int) -> str:
    return (datetime.now(timezone.utc) + timedelta(seconds=backoff_seconds(attempts))).isoformat()


def on_failure(*, attempts: int, max_attempts: int, error: str) -> dict:
    """Returns the field updates to apply to a jobs/publishing_queue row after
    a failed attempt. Caller supplies which status enum values to use for
    'will retry' vs 'exhausted' since jobs and publishing_queue use different
    enums for the exhausted state (`failed` vs `dead_letter`, per §5's
    rationale)."""
    if attempts >= max_attempts:
        return {"exhausted": True, "last_error": error, "next_attempt_at": None}
    return {"exhausted": False, "last_error": error, "next_attempt_at": next_attempt_at(attempts)}
