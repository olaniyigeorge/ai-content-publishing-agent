"""sources.discard_reason — TESTING_FINDINGS.md, 2026-09-16: a source shown
as 'discarded' or 'failed' in the UI gave no indication of *why*, so a human
reviewing the request couldn't tell a blocked/paywalled URL from a JS-shell
scrape from an outright 404 without digging into stage_events. This column
carries that reason (the scrape error message, or the model's stated reason
a retrieved page had no usable article text) straight onto the source row.

Also starts writing a `sources` row for a URL that failed to scrape at all
(worker/handlers/research.py) — previously that case was only recorded in
stage_events.detail.failures and never appeared in the Sources list at all,
so a failed URL was invisible on the one screen a reviewer actually looks at.

Revision ID: 0005
Revises: 0004
Create Date: 2026-09-16

"""
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("alter table sources add column discard_reason text;")


def downgrade() -> None:
    op.execute("alter table sources drop column if exists discard_reason;")
