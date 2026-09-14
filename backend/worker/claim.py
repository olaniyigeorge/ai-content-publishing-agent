"""Atomic claim queries via the `claim_pending_job` / `claim_pending_queue_item`
Postgres functions (alembic/versions/0002_claim_functions.py) — this is what
makes it safe to run more than one worker process without double-processing
a row (EDGE_CASES.md #60)."""

from db.client import get_supabase


def claim_job() -> dict | None:
    rows = get_supabase().rpc("claim_pending_job", {}).execute().data
    return rows[0] if rows else None


def claim_queue_item() -> dict | None:
    rows = get_supabase().rpc("claim_pending_queue_item", {}).execute().data
    return rows[0] if rows else None
