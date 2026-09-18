"""Shared by every path that can queue a `generate` job against an existing
draft (rewrite_draft, submit_review's revise_requested branch, a discarded
source's regeneration) — carries the most recent evaluation's actual
reasoning (feedback, unsupported claims, recommended changes) into the next
generate call, so a human- or system-triggered regeneration builds on what
was already found instead of generating blind on nothing but a one-line
instruction."""

from db.client import get_supabase


def latest_evaluation_context(draft_id: str, db=None) -> str | None:
    """Every field here is joined onto one line with newlines removed, into
    one run-on paragraph — both hard for a human reviewer to read in the UI
    (article_drafts.revision_instructions is shown pre-wrap, so it renders
    exactly as written) and, per direct observation across several test
    requests, harder for the model to reliably act on than the same content
    with real section breaks (TESTING_FINDINGS2.md, 2026-09-18). Headed,
    line-broken sections fix both without changing what information is
    carried."""
    db = db or get_supabase()
    rows = (
        db.table("evaluations")
        .select("*")
        .eq("article_draft_id", draft_id)
        .order("created_at", desc=True)
        .limit(1)
        .execute()
        .data
    )
    if not rows:
        return None
    evaluation = rows[0]
    parts = [f"Prior evaluation feedback:\n{evaluation['feedback']}"]
    if evaluation.get("unsupported_claims"):
        claims = "\n".join(f"- {c}" for c in evaluation["unsupported_claims"])
        parts.append(f"Previously flagged unsupported/overstated claims:\n{claims}")
    if evaluation.get("revision_instructions"):
        # Already bulleted/line-broken by worker/handlers/evaluate.py — pass
        # through as-is rather than reformatting it a second time here.
        parts.append(f"Previously recommended changes:\n{evaluation['revision_instructions']}")
    return "\n\n".join(parts)


def with_evaluation_context(instructions: str, draft_id: str, db=None) -> str:
    context = latest_evaluation_context(draft_id, db=db)
    return f"{instructions}\n\n{context}" if context else instructions
