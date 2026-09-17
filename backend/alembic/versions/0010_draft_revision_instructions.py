"""article_drafts: add revision_instructions.

The actual instructions a `generate` job was seeded with (a content manager's
human_review/rewrite notes, folded together with the prior evaluation's
feedback and unsupported-claims list by app/services/evaluation_context.py)
were only ever visible in the `jobs.payload` row — which the frontend never
reads. A reviewer regenerating a draft had no way to see what the agent was
actually told to do differently this time, short of reading raw job rows in
the database. Storing it directly on the resulting draft makes that visible
on the request detail page next to the version it produced.

Revision ID: 0010
Revises: 0009
Create Date: 2026-09-18

"""
from alembic import op

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("alter table article_drafts add column if not exists revision_instructions text")


def downgrade() -> None:
    op.execute("alter table article_drafts drop column if exists revision_instructions")
