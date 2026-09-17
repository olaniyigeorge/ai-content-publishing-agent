"""stage_event_status: add missing 'retrying' value.

`shared.enums.StageEventStatus.RETRYING` has existed in the Python enum
since the "amber not red for recoverable errors" change (worker/main.py's
process_one_job distinguishes a transient failure the worker will retry
from a truly exhausted one) — but the corresponding Postgres `stage_event_
status` type was never actually altered to add it. Every job retry has
therefore been crashing with `invalid input value for enum
stage_event_status: "retrying"` (code 22P02) — and because that insert
happens inside process_one_job's own except-block, the exception escapes
uncaught and kills the whole worker process, not just that one job attempt.

Revision ID: 0009
Revises: 0008
Create Date: 2026-09-17

"""
from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute("alter type stage_event_status add value if not exists 'retrying'")


def downgrade() -> None:
    # No `ALTER TYPE ... DROP VALUE` in Postgres — see 0008's downgrade note.
    pass
