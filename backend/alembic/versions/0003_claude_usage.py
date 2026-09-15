"""claude_usage — per-call token/cost log (claude/usage.py)

Tracks input/output tokens and a computed USD cost for every Claude API
call, attributed to the content request and job that triggered it, so the
UI can show token/cost spend per request and in total (no schema change
needed later — this is additive, nothing else reads or writes this table).

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-15

"""
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None

TABLES_SQL = """
create table claude_usage (
  id uuid primary key default gen_random_uuid(),
  content_request_id uuid references content_requests(id) on delete cascade,
  job_id uuid references jobs(id) on delete set null,
  job_type job_type,
  model text not null,
  input_tokens int not null,
  output_tokens int not null,
  cost_usd numeric not null,
  created_at timestamptz not null default now()
);
"""

INDEXES_SQL = """
create index on claude_usage (content_request_id);
create index on claude_usage (created_at);
"""


def upgrade() -> None:
    op.execute(TABLES_SQL)
    op.execute(INDEXES_SQL)


def downgrade() -> None:
    op.execute("drop table if exists claude_usage;")
