"""Reclaim stale `processing` jobs — EDGE_CASES.md #61.

A job whose worker process died mid-handler (OOM, redeploy, SIGKILL) between
claim_pending_job() setting status='processing' and process_one_job's final
UPDATE ... SUCCEEDED/FAILED is left at 'processing' forever — nothing else
ever revisits it. This orphaned row also permanently blocks
job_guard.has_pending_revision for whatever draft it targeted, since that
guard treats any pending/processing row as still in flight.

claim_pending_job() now reclaims any 'processing' row that has been stale
longer than JOB_STALE_SECONDS before it looks for new work: back to 'pending'
(to retry, same as an ordinary failure) if it still has attempts left, or
straight to 'failed' if attempts are already exhausted — either way it stops
sitting in an in-flight status forever. Kept in sync with
app.config.Settings.job_stale_processing_seconds, which is job_guard's
app-layer mirror of the same threshold (used so a stuck row doesn't also
block a draft rewrite while waiting for the worker's next poll).

Revision ID: 0007
Revises: 0006
Create Date: 2026-09-17

"""
from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None

JOB_STALE_SECONDS = 600

FUNCTION_SQL = f"""
create or replace function claim_pending_job()
returns setof jobs
language plpgsql
as $$
declare
  claimed jobs;
begin
  update jobs
  set status = 'failed',
      last_error = coalesce(last_error || ' ', '') || '[reclaimed: stale processing row, attempts exhausted]',
      updated_at = now()
  where status = 'processing'
    and updated_at < now() - interval '{JOB_STALE_SECONDS} seconds'
    and attempts >= max_attempts;

  update jobs
  set status = 'pending',
      next_attempt_at = now(),
      updated_at = now(),
      last_error = coalesce(last_error || ' ', '') || '[reclaimed: stale processing row, retrying]'
  where status = 'processing'
    and updated_at < now() - interval '{JOB_STALE_SECONDS} seconds'
    and attempts < max_attempts;

  select * into claimed
  from jobs
  where status = 'pending' and next_attempt_at <= now()
  order by next_attempt_at
  for update skip locked
  limit 1;

  if claimed.id is null then
    return;
  end if;

  update jobs
  set status = 'processing', attempts = attempts + 1, updated_at = now()
  where id = claimed.id
  returning * into claimed;

  return next claimed;
end;
$$;
"""

PREVIOUS_FUNCTION_SQL = """
create or replace function claim_pending_job()
returns setof jobs
language plpgsql
as $$
declare
  claimed jobs;
begin
  select * into claimed
  from jobs
  where status = 'pending' and next_attempt_at <= now()
  order by next_attempt_at
  for update skip locked
  limit 1;

  if claimed.id is null then
    return;
  end if;

  update jobs
  set status = 'processing', attempts = attempts + 1, updated_at = now()
  where id = claimed.id
  returning * into claimed;

  return next claimed;
end;
$$;
"""


def upgrade() -> None:
    op.execute(FUNCTION_SQL)


def downgrade() -> None:
    op.execute(PREVIOUS_FUNCTION_SQL)
