"""Shared by every path that can queue a `generate` job against an existing
draft (rewrite_draft, submit_review's revise_requested branch, a discarded
source's regeneration) — carries the most recent evaluation's actual
reasoning (feedback, unsupported claims, recommended changes) into the next
generate call, so a human- or system-triggered regeneration builds on what
was already found instead of generating blind on nothing but a one-line
instruction."""

from db.client import get_supabase


def latest_evaluation_context(draft_id: str, db=None) -> str | None:
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
    parts = [f"Prior evaluation feedback: {evaluation['feedback']}"]
    if evaluation.get("unsupported_claims"):
        parts.append(
            "Previously flagged unsupported/overstated claims: " + "; ".join(evaluation["unsupported_claims"])
        )
    if evaluation.get("revision_instructions"):
        parts.append(f"Previously recommended changes: {evaluation['revision_instructions']}")
    return " ".join(parts)


def with_evaluation_context(instructions: str, draft_id: str, db=None) -> str:
    context = latest_evaluation_context(draft_id, db=db)
    return f"{instructions} {context}" if context else instructions
