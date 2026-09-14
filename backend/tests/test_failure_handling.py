"""Scenario 8 + EDGE_CASES.md #16, #24, #58, #60 (retry/backoff/dead-letter,
the revision cap, and the atomic claim function's SQL shape)."""

from worker.retry import backoff_seconds, on_failure


def test_backoff_grows_exponentially():
    assert backoff_seconds(0) == 60
    assert backoff_seconds(1) == 120
    assert backoff_seconds(2) == 240


def test_on_failure_retries_below_max_attempts():
    outcome = on_failure(attempts=1, max_attempts=3, error="boom")
    assert outcome["exhausted"] is False
    assert outcome["next_attempt_at"] is not None
    assert outcome["last_error"] == "boom"


def test_on_failure_exhausts_at_max_attempts():
    outcome = on_failure(attempts=3, max_attempts=3, error="boom")
    assert outcome["exhausted"] is True
    assert outcome["next_attempt_at"] is None


def test_claim_functions_use_for_update_skip_locked():
    """EDGE_CASES.md #60: two workers must not claim the same row. This is a
    smoke check that the migration actually uses the locking clause — a
    regression here (e.g. someone rewrites the function without it) would
    silently reintroduce duplicate job pickup."""
    import importlib.util
    import os

    path = os.path.join(
        os.path.dirname(__file__), "..", "alembic", "versions", "0002_claim_functions.py"
    )
    spec = importlib.util.spec_from_file_location("claim_functions_migration", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    sql = module.FUNCTIONS_SQL.lower()
    assert "for update skip locked" in sql
    assert sql.count("for update skip locked") == 2  # jobs + publishing_queue
