"""Versions are immutable snapshots: regenerating from an explicitly chosen
older version must not derive its new version number from that source
draft, must not touch any newer sibling version, and must not inherit that
sibling's evaluation. TESTING_FINDINGS.md, 2026-09-17: regenerating from an
approved V4 while V5 already existed crashed with
'duplicate key value violates unique constraint "article_drafts_version_unique"'
because the old code computed `version = source["version"] + 1` — i.e. V5
again — instead of the next version actually free for that
(content_request_id, option_label)."""

import pytest
from postgrest.exceptions import APIError

from app.services.draft_versioning import insert_draft_version
from worker.handlers.generate import handle_generate

REQUEST_ID = "00000000-0000-0000-0000-000000000030"
PLAN_ID = "00000000-0000-0000-0000-000000000031"
V4_ID = "00000000-0000-0000-0000-000000000034"
V5_ID = "00000000-0000-0000-0000-000000000035"


def _seed_lineage(fake_db):
    """V4 (discarded, superseded), V5 (current, being evaluated) — same
    shape a normal V4->V5 revision leaves behind."""
    fake_db.table("content_requests").insert(
        {
            "id": REQUEST_ID,
            "status": "evaluating",
            "raw_idea": "Why SaaS marketers should track activation, not just signups",
            "target_audience": "SaaS marketers",
        }
    ).execute()
    fake_db.table("content_plans").insert(
        {"id": PLAN_ID, "content_request_id": REQUEST_ID, "outline": {}, "target_keywords": []}
    ).execute()
    fake_db.table("article_drafts").insert(
        {
            "id": V4_ID,
            "content_request_id": REQUEST_ID,
            "content_plan_id": PLAN_ID,
            "option_label": "A",
            "version": 4,
            "title": "Draft V4",
            "body_markdown": "# V4\n\nApproved content.",
            "source_ids_used": ["src-1"],
            "status": "discarded",
        }
    ).execute()
    fake_db.table("article_drafts").insert(
        {
            "id": V5_ID,
            "content_request_id": REQUEST_ID,
            "content_plan_id": PLAN_ID,
            "option_label": "A",
            "version": 5,
            "parent_draft_id": V4_ID,
            "title": "Draft V5",
            "body_markdown": "# V5\n\nNewer content, currently under evaluation.",
            "source_ids_used": ["src-1"],
            "status": "draft",
        }
    ).execute()
    fake_db.table("evaluations").insert(
        {
            "article_draft_id": V5_ID,
            "rubric_scores": {"clarity": 3},
            "overall_score": 3.0,
            "passed_threshold": False,
            "feedback": "V5's own evaluation feedback",
            "revision_instructions": "tighten the intro",
        }
    ).execute()


def test_regenerating_from_v4_while_v5_exists_creates_v6_not_v5(fake_db, monkeypatch):
    _seed_lineage(fake_db)
    monkeypatch.setattr(
        "worker.handlers.generate.claude_service.generate_draft",
        lambda **kwargs: "# Draft V6\n\nRegenerated body.",
    )

    job = {
        "reference_type": "article_draft",
        "reference_id": V4_ID,  # explicit source: V4, not the current latest (V5)
        "payload": {"revision_instructions": "regenerate from the approved V4"},
    }
    handle_generate(job)

    drafts = fake_db.table("article_drafts").select("*").eq("content_request_id", REQUEST_ID).execute().data
    versions = {d["version"]: d for d in drafts}
    assert set(versions) == {4, 5, 6}

    v6 = versions[6]
    assert v6["parent_draft_id"] == V4_ID  # lineage: regenerated from V4, not V5
    assert v6["option_label"] == "A"

    v5 = versions[5]
    assert v5["id"] == V5_ID
    assert v5["status"] == "draft"  # V5 stays intact — untouched by regenerating from V4
    assert v5["body_markdown"] == "# V5\n\nNewer content, currently under evaluation."


def test_v6_does_not_inherit_v5s_evaluation(fake_db, monkeypatch):
    _seed_lineage(fake_db)
    monkeypatch.setattr(
        "worker.handlers.generate.claude_service.generate_draft",
        lambda **kwargs: "# Draft V6\n\nRegenerated body.",
    )

    job = {
        "reference_type": "article_draft",
        "reference_id": V4_ID,
        "payload": {"revision_instructions": "regenerate from the approved V4"},
    }
    handle_generate(job)

    drafts = fake_db.table("article_drafts").select("*").eq("content_request_id", REQUEST_ID).execute().data
    v6_id = next(d["id"] for d in drafts if d["version"] == 6)

    v6_evaluations = fake_db.table("evaluations").select("*").eq("article_draft_id", v6_id).execute().data
    assert v6_evaluations == []  # starts fresh — no copy of V5's evaluation row

    v5_evaluations = fake_db.table("evaluations").select("*").eq("article_draft_id", V5_ID).execute().data
    assert len(v5_evaluations) == 1
    assert v5_evaluations[0]["feedback"] == "V5's own evaluation feedback"

    # the follow-up evaluate job targets V6, never V5
    evaluate_jobs = fake_db.table("jobs").select("*").eq("job_type", "evaluate").execute().data
    assert len(evaluate_jobs) == 1
    assert evaluate_jobs[0]["reference_id"] == v6_id


def test_stage_event_records_explicit_source_version(fake_db, monkeypatch):
    _seed_lineage(fake_db)
    monkeypatch.setattr(
        "worker.handlers.generate.claude_service.generate_draft",
        lambda **kwargs: "# Draft V6\n\nRegenerated body.",
    )

    job = {
        "reference_type": "article_draft",
        "reference_id": V4_ID,
        "payload": {"revision_instructions": "regenerate from the approved V4"},
    }
    handle_generate(job)

    events = (
        fake_db.table("stage_events")
        .select("*")
        .eq("content_request_id", REQUEST_ID)
        .eq("stage", "generation")
        .execute()
        .data
    )
    assert len(events) == 1
    assert events[0]["detail"]["version"] == 6
    assert events[0]["detail"]["source_version"] == 4


def test_insert_draft_version_allocates_from_max_not_source_version(fake_db):
    """Direct unit test of the allocator: even when called with a source
    draft's own version far behind the current max for that
    (content_request_id, option_label), it must allocate the next free slot,
    not source_version + 1."""
    _seed_lineage(fake_db)

    new_row = insert_draft_version(
        fake_db,
        {
            "content_request_id": REQUEST_ID,
            "content_plan_id": PLAN_ID,
            "option_label": "A",
            "parent_draft_id": V4_ID,
            "title": "Manually regenerated",
            "body_markdown": "# V6",
            "source_ids_used": [],
            "status": "draft",
        },
    )
    assert new_row["version"] == 6


def test_insert_draft_version_retries_past_a_unique_conflict(fake_db, monkeypatch):
    """Simulates the exact race this allocator exists to survive: the first
    insert attempt loses a race to another writer that landed the same
    version number first. Rather than bubbling up the 23505, it must
    recompute and retry."""
    _seed_lineage(fake_db)

    real_table = fake_db.table
    call_count = {"n": 0}

    class _RacingQuery:
        def __init__(self, inner):
            self._inner = inner

        def __getattr__(self, name):
            return getattr(self._inner, name)

        def insert(self, payload):
            call_count["n"] += 1
            if call_count["n"] == 1:
                # another writer wins the race for version 6 first
                real_table("article_drafts").insert({**payload, "id": "00000000-0000-0000-0000-000000000036"}).execute()
                raise APIError(
                    {
                        "message": 'duplicate key value violates unique constraint "article_drafts_version_unique"',
                        "code": "23505",
                        "hint": None,
                        "details": None,
                    }
                )
            return self._inner.insert(payload)

    def racing_table(name):
        inner = real_table(name)
        return _RacingQuery(inner) if name == "article_drafts" else inner

    monkeypatch.setattr(fake_db, "table", racing_table)

    new_row = insert_draft_version(
        fake_db,
        {
            "content_request_id": REQUEST_ID,
            "content_plan_id": PLAN_ID,
            "option_label": "A",
            "parent_draft_id": V4_ID,
            "title": "Regenerated after losing the race once",
            "body_markdown": "# V7",
            "source_ids_used": [],
            "status": "draft",
        },
    )
    assert new_row["version"] == 7  # recomputed after the race, not stuck retrying 6

    drafts = real_table("article_drafts").select("*").eq("content_request_id", REQUEST_ID).execute().data
    assert sorted(d["version"] for d in drafts) == [4, 5, 6, 7]


def test_rewrite_from_older_version_rejected_while_that_version_has_a_pending_revision(fake_db):
    """Regenerating from V4 explicitly is still subject to the existing
    in-flight guard — clicking rewrite twice on the same source version
    while its own job is still queued is rejected the same way it always
    was, this just confirms the guard is keyed on the chosen source
    draft, not on 'whatever is currently latest'."""
    from app.services.draft_service import rewrite_draft
    from shared.errors import ValidationFailure

    _seed_lineage(fake_db)
    fake_db.table("jobs").insert(
        {
            "job_type": "generate",
            "reference_type": "article_draft",
            "reference_id": V4_ID,
            "status": "pending",
        }
    ).execute()

    with pytest.raises(ValidationFailure, match="already has a revision in progress"):
        rewrite_draft(V4_ID, "regenerate from V4")

    # V5 is a different draft id — regenerating from it is unaffected
    rewrite_draft(V5_ID, "make it punchier")
    jobs = fake_db.table("jobs").select("*").eq("reference_id", V5_ID).execute().data
    assert len(jobs) == 1
