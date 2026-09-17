"""evaluations: add score_delta_from_parent.

Confirms/enforces the "carry every win forward, never silently regress"
guarantee a content manager should be able to trust across a draft's
revision lineage: worker/handlers/evaluate.py now looks up the immediate
parent draft's own most recent evaluation score and records the delta here
whenever one exists. A negative delta means this revision — despite fixing
whatever it was asked to fix — scored lower overall than the version it
replaced, which the request detail page surfaces as a visible warning
instead of a silent, easy-to-miss regression buried in a score number.

Revision ID: 0011
Revises: 0010
Create Date: 2026-09-18

"""
from alembic import op

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("alter table evaluations add column if not exists score_delta_from_parent numeric")


def downgrade() -> None:
    op.execute("alter table evaluations drop column if exists score_delta_from_parent")
