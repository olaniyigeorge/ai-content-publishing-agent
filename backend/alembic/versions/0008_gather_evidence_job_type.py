"""Evidence-driven regeneration: new job_type/pipeline_stage enum values.

Adds `job_type = 'gather_evidence'` (worker/handlers/gather_evidence.py — the
async job that searches for and verifies real evidence for a draft's
specific unsupported claims before regeneration) and two new
`pipeline_stage` values: `evidence_gathering` (that job's own stage_events)
and `grounding_validation` (the pre-flight grounding check in
worker/handlers/generate.py, run before the expensive per-draft evaluator).

`ALTER TYPE ... ADD VALUE` cannot run inside the transaction block Alembic
wraps migrations in by default — it must run in its own top-level
transaction, hence `autocommit_block()`.

Revision ID: 0008
Revises: 0007
Create Date: 2026-09-17

"""
from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute("alter type job_type add value if not exists 'gather_evidence'")
        op.execute("alter type pipeline_stage add value if not exists 'evidence_gathering'")
        op.execute("alter type pipeline_stage add value if not exists 'grounding_validation'")


def downgrade() -> None:
    # Postgres has no `ALTER TYPE ... DROP VALUE` — removing an enum value
    # requires rebuilding the type (create new, migrate columns, drop old),
    # which isn't worth the risk for a downgrade path that's never expected
    # to run against a database holding real 'gather_evidence' jobs or
    # 'evidence_gathering'/'grounding_validation' stage_events. No-op.
    pass
