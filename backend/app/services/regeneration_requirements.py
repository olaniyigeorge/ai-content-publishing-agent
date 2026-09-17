"""Converts an evaluator's raw output (free-form feedback strings) into a
structured shape the rest of the regeneration pipeline acts on mechanically,
instead of passing prose straight through as the only signal. This is what
lets worker/handlers/evaluate.py hand worker/handlers/gather_evidence.py an
explicit list of claims to research, rather than a paragraph the next step
would have to re-parse."""

from shared.enums import ClaimType


def build_regeneration_requirements(*, evaluation_result: dict, guard: dict) -> dict:
    unsupported_claims = evaluation_result.get("unsupported_claims") or []
    sections_to_revise = evaluation_result.get("sections_to_revise") or []
    recommended_changes = evaluation_result.get("recommended_changes") or []
    guard_violations = guard.get("violations") or []

    defects = (
        [{"type": "unsupported_claim", "description": c} for c in unsupported_claims]
        + [{"type": "section_weak", "description": s} for s in sections_to_revise]
        + [{"type": "guard_violation", "description": v} for v in guard_violations]
    )
    claims_needing_research = [
        {"claim_text": c, "claim_type": ClaimType.UNSUPPORTED.value} for c in unsupported_claims
    ]
    return {
        "defects": defects,
        "claims_needing_research": claims_needing_research,
        "structural_changes": recommended_changes,
        "feedback": evaluation_result.get("feedback"),
    }
