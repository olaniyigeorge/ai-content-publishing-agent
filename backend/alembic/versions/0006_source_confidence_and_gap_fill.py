"""Thin/weak-evidence visibility + gap-fill research.

Previously a source was only ever `selected` (treated as solid grounding)
or `discarded` (not used at all) — nothing distinguished "this is real,
well-supported evidence" from "this is the only thing we found, and it's
thin." A thin source got either fully trusted (misleading) or discarded
outright (losing evidence a human might still want to see and decide on).

Adds `sources.confidence` ('strong' default, or 'thin') and
`confidence_reason` so a thin-but-real source can still be cited and shown
to the reviewer honestly, instead of being dressed up as solid fact or
thrown away.

Also adds `evaluations.unsupported_claims` / `sections_to_revise` — these
were already produced by the evaluator (claude/outputs.py's
EVALUATION_SCHEMA) but only ever landed in `stage_events.detail`, which a
reviewer doesn't look at on the actual review screen. Promoting them onto
the evaluations row itself is what makes "which claims aren't backed"
visible without digging through logs.

`content_requests.gap_fill_attempts` bounds a new behavior: when a request
has no user-supplied source URL and a draft's grounding comes back thin or
empty, the system now gets a small, capped number of chances to run one
more targeted web search — informed by the evaluation feedback and the
original request — before giving up and escalating to a human.

Revision ID: 0006
Revises: 0005
Create Date: 2026-09-18

"""
from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("alter table sources add column confidence text not null default 'strong';")
    op.execute("alter table sources add column confidence_reason text;")
    op.execute(
        "alter table evaluations add column unsupported_claims jsonb not null default '[]'::jsonb;"
    )
    op.execute(
        "alter table evaluations add column sections_to_revise jsonb not null default '[]'::jsonb;"
    )
    op.execute(
        "alter table content_requests add column gap_fill_attempts integer not null default 0;"
    )


def downgrade() -> None:
    op.execute("alter table sources drop column if exists confidence;")
    op.execute("alter table sources drop column if exists confidence_reason;")
    op.execute("alter table evaluations drop column if exists unsupported_claims;")
    op.execute("alter table evaluations drop column if exists sections_to_revise;")
    op.execute("alter table content_requests drop column if exists gap_fill_attempts;")
