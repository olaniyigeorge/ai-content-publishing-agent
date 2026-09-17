"""Atomic next-version allocation for article_drafts, shared by every path
that inserts a new draft version (worker.handlers.generate.handle_generate,
draft_service.manual_edit_draft).

TESTING_FINDINGS.md, 2026-09-17: computing `version = parent["version"] + 1`
from the *source* draft's own version number breaks the moment the source
isn't the newest version for that (content_request_id, option_label) — e.g.
explicitly regenerating from an older version (V4) while a newer version
(V5) already exists recomputes V5 again and crashes on
article_drafts_version_unique. Versions are immutable snapshots identified
by (content_request_id, option_label, version); the next version must
always be the highest version number that actually exists for that pair,
never derived from whichever draft was chosen as the regeneration source.

`insert_draft_version` also retries on a unique-constraint race (two
regenerations against the same content_request_id + option_label landing at
the same moment) instead of letting the second one crash — the unique
constraint stays the backstop, this loop is what makes hitting it
survivable rather than fatal.
"""

from postgrest.exceptions import APIError

UNIQUE_VIOLATION = "23505"
MAX_INSERT_ATTEMPTS = 5


def _next_version(db, content_request_id: str, option_label: str) -> int:
    rows = (
        db.table("article_drafts")
        .select("version")
        .eq("content_request_id", content_request_id)
        .eq("option_label", option_label)
        .order("version", desc=True)
        .limit(1)
        .execute()
        .data
    )
    return (rows[0]["version"] + 1) if rows else 1


def insert_draft_version(db, fields: dict) -> dict:
    """Insert a new article_drafts row, allocating its version number from
    the current max for `fields["content_request_id"]` +
    `fields["option_label"]`. `fields` must not include `version`."""
    last_error: APIError | None = None
    for _ in range(MAX_INSERT_ATTEMPTS):
        version = _next_version(db, fields["content_request_id"], fields["option_label"])
        try:
            return db.table("article_drafts").insert({**fields, "version": version}).execute().data[0]
        except APIError as exc:
            if exc.code != UNIQUE_VIOLATION:
                raise
            last_error = exc
            continue
    raise last_error
