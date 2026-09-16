"""queue_status: add 'ready_to_publish' — the mock publish adapter (worker/
publishing_adapter.py) doesn't actually reach LinkedIn/X/the email provider,
so it must not claim the honest terminal 'published' state on its own. It now
lands here instead; a human copies the content, actually posts it, and marks
the item 'published' themselves via the existing manual status override
(app/api/publishing.py's PATCH /status, already supported by the frontend's
"Mark as" dropdown) — see EDGE_CASES.md #39.

Revision ID: 0004
Revises: 0003
Create Date: 2026-09-15

"""
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("alter type queue_status add value 'ready_to_publish' after 'processing';")


def downgrade() -> None:
    # Postgres can't drop a single enum value cleanly — no-op (matches this
    # repo's other enum-add migrations' irreversibility in practice).
    pass
