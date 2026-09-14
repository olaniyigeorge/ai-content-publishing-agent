"""atomic claim functions for jobs + publishing_queue (worker/claim.py)

Supabase's REST layer (PostgREST) has no client-side `SELECT ... FOR UPDATE
SKIP LOCKED` — it can only be expressed as a server-side function, called via
RPC. This is what prevents two worker processes claiming the same row
(EDGE_CASES.md #60).

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-14

"""
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

FUNCTIONS_SQL = """
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

create or replace function claim_pending_queue_item()
returns setof publishing_queue
language plpgsql
as $$
declare
  claimed publishing_queue;
begin
  select * into claimed
  from publishing_queue
  where status = 'queued' and (next_attempt_at is null or next_attempt_at <= now())
  order by created_at
  for update skip locked
  limit 1;

  if claimed.id is null then
    return;
  end if;

  update publishing_queue
  set status = 'processing', attempts = attempts + 1, updated_at = now()
  where id = claimed.id
  returning * into claimed;

  return next claimed;
end;
$$;
"""


def upgrade() -> None:
    op.execute(FUNCTIONS_SQL)


def downgrade() -> None:
    op.execute("""
        drop function if exists claim_pending_job();
        drop function if exists claim_pending_queue_item();
    """)
