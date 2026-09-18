from datetime import UTC, datetime

import claude.service as claude_service
from app.config import get_settings
from app.services.regeneration_requirements import build_regeneration_requirements
from claude.models import OPUS
from claude.outputs import require_fields
from claude.quality_guards import SOURCE_GROUNDING_FLOOR, check_article, is_ungroundable
from db.client import get_supabase
from shared.enums import (
    AttachmentType,
    DraftStatus,
    EvaluatedBy,
    JobReferenceType,
    JobType,
    PipelineStage,
    RequestStatus,
    StageEventStatus,
)
from shared.errors import DraftEvaluationFailed


def handle_evaluate(job: dict) -> None:
    """EDGE_CASES.md #24: caps the evaluate->generate loop at
    settings.max_revisions. Past the cap, the draft still goes to human
    review — with passed_threshold=false visible in the evaluation panel —
    rather than looping forever or getting silently stuck."""
    db = get_supabase()
    settings = get_settings()
    draft_id = job["reference_id"]

    draft = db.table("article_drafts").select("*").eq("id", draft_id).execute().data[0]
    request_id = draft["content_request_id"]
    request_row = db.table("content_requests").select("*").eq("id", request_id).execute().data[0]
    sources = db.table("sources").select("*").in_("id", draft["source_ids_used"]).execute().data

    result = claude_service.evaluate_draft(
        target_audience=request_row["target_audience"],
        draft_title=draft["title"],
        draft_body=draft["body_markdown"],
        sources=sources,
    )
    require_fields(
        result,
        ["overall_status", "rubric_scores", "overall_score", "recommended_changes", "feedback"],
        step="evaluation",
        error_cls=DraftEvaluationFailed,
    )
    unsupported_claims = result.get("unsupported_claims") or []
    sections_to_revise = result.get("sections_to_revise") or []

    # Deterministic checks, independent of the model's self-assessment: a
    # rubric "pass" can't override a hard length/structure violation
    # (EDGE_CASES.md-style guard — see claude/quality_guards.py), and it
    # can't override the model's own unsupported_claims list either. The
    # prompt (claude/prompts/evaluate.py) already instructs "if pass, zero
    # unsupported_claims" — but that's a request to the model, not a
    # guarantee. Enforcing it here, not just asking for it, is what stops a
    # confidently-worded "pass" from carrying an unresolved unsupported claim
    # through to a human reviewer as if it were solid.
    guard = check_article(draft["body_markdown"])

    # "Every win carried forward, never a silent regression": compare this
    # draft's score against the immediate parent draft's own most recent
    # evaluation, when one exists. This has to be computed before `passed`
    # below — a regression is now a hard non-pass, exactly like a hard guard
    # violation or an unresolved unsupported claim, not just a badge shown
    # after the fact. Without that, a revision that fixed whatever was
    # flagged but quietly dropped something that already worked could still
    # sail through to human review as a "pass," with only a small warning
    # label to notice — this makes it impossible for that to happen silently:
    # a regression is retried automatically, up to the same revision cap
    # everything else is bounded by.
    score_delta_from_parent = None
    parent_score = None
    if draft.get("parent_draft_id"):
        parent_evals = (
            db.table("evaluations")
            .select("overall_score")
            .eq("article_draft_id", draft["parent_draft_id"])
            .order("created_at", desc=True)
            .limit(1)
            .execute()
            .data
        )
        if parent_evals:
            parent_score = parent_evals[0]["overall_score"]
            score_delta_from_parent = result["overall_score"] - parent_score
    is_regression = score_delta_from_parent is not None and score_delta_from_parent < 0

    passed = (
        result["overall_status"] == "pass"
        and not guard["violations"]
        and not unsupported_claims
        and not is_regression
    )
    revision_notes = list(result["recommended_changes"])
    if guard["violations"]:
        revision_notes = [f"[hard guard] {v}" for v in guard["violations"]] + revision_notes
    if unsupported_claims and result["overall_status"] == "pass":
        revision_notes = [f"[unsupported claim] {c}" for c in unsupported_claims] + revision_notes
    if is_regression:
        # Not just a number for the UI — feed it back into the next
        # revision's own instructions, so the model is explicitly told to go
        # compare against the parent draft and restore whatever it dropped,
        # instead of only chasing the newly flagged issues and drifting
        # further from what worked.
        revision_notes = [
            f"[regression] this revision scored {result['overall_score']:.2f}/5, lower than its parent "
            f"draft's {parent_score:.2f}/5, despite addressing that draft's feedback — compare against the "
            "previous draft and restore any content, structure, or grounded claims this version dropped or "
            "weakened, in addition to the following"
        ] + revision_notes

    evaluation_row = (
        db.table("evaluations")
        .insert(
            {
                "article_draft_id": draft_id,
                "rubric_scores": result["rubric_scores"],
                "overall_score": result["overall_score"],
                "passed_threshold": passed,
                "feedback": result["feedback"],
                # A run-on "; "-joined paragraph was both unreadable in the
                # UI (article_drafts.revision_instructions renders pre-wrap
                # verbatim) and, per direct observation across several test
                # requests, harder for the model to reliably act on than the
                # same content with one recommendation per line
                # (TESTING_FINDINGS2.md, 2026-09-18).
                "revision_instructions": (
                    None if passed else ("\n".join(f"- {note}" for note in revision_notes) or result["feedback"])
                ),
                "unsupported_claims": unsupported_claims,
                "sections_to_revise": sections_to_revise,
                "evaluated_by": EvaluatedBy.AI.value,
                "score_delta_from_parent": score_delta_from_parent,
            }
        )
        .execute()
        .data[0]
    )

    db.table("stage_events").insert(
        {
            "content_request_id": request_id,
            "stage": PipelineStage.EVALUATION.value,
            "status": StageEventStatus.SUCCEEDED.value,
            "detail": {
                "draft_id": draft_id,
                "version": draft["version"],
                "passed_threshold": passed,
                "overall_status": result["overall_status"],
                "unsupported_claims": unsupported_claims,
                "quality_guard": guard,
            },
        }
    ).execute()

    at_cap = draft["version"] >= settings.max_revisions
    # A draft with zero source_ids_used can't be fixed by revising the text —
    # there's no source material to ground it in no matter how it's worded.
    # Stop after this one attempt instead of spending the rest of the
    # revision cap on cycles that were never going to pass (TESTING_FINDINGS.md).
    ungroundable = not passed and is_ungroundable(
        source_ids_used=draft["source_ids_used"], rubric_scores=result["rubric_scores"]
    )
    grounding_score = result["rubric_scores"].get("source_grounding")
    grounding_is_weak = not passed and grounding_score is not None and grounding_score <= SOURCE_GROUNDING_FLOOR
    # Only "no real evidence" cases (zero sources, or every source actually
    # used came back thin) call for searching again — a low score against
    # sources that do exist and aren't thin means the draft just did a poor
    # job grounding in material that's already there, which revising the
    # wording can genuinely fix (test_low_source_grounding_with_real_sources_
    # still_revises_normally).
    has_only_thin_sources = bool(sources) and all(s.get("confidence") == "thin" for s in sources)
    grounding_has_no_real_evidence = ungroundable or (grounding_is_weak and has_only_thin_sources)

    # If nobody gave this request a source URL, the only sources it has ever
    # had are whatever the autonomous web search found — and that search
    # only ever ran once, blind to what the draft actually turned out to need.
    # Before giving up on grounding (or spending the rest of the revision cap
    # revising wording that can't fix a sourcing gap), give it a small,
    # capped number of chances to search again — this time aimed specifically
    # at what the evaluation just flagged.
    has_source_url = any(
        a["type"] == AttachmentType.URL.value
        for a in db.table("intake_attachments").select("type").eq("content_request_id", request_id).execute().data
    )
    can_gap_fill = (
        not passed
        and not at_cap
        and not has_source_url
        and grounding_has_no_real_evidence
        and request_row.get("gap_fill_attempts", 0) < settings.max_gap_fill_attempts
    )

    if can_gap_fill:
        research_focus = "; ".join([*unsupported_claims, result["feedback"]])
        db.table("content_requests").update(
            {
                "gap_fill_attempts": request_row.get("gap_fill_attempts", 0) + 1,
                "status": RequestStatus.RESEARCHING.value,
                "updated_at": datetime.now(UTC).isoformat(),
            }
        ).eq("id", request_id).execute()
        db.table("stage_events").insert(
            {
                "content_request_id": request_id,
                "stage": PipelineStage.RESEARCH.value,
                "status": StageEventStatus.STARTED.value,
                "detail": {
                    "draft_id": draft_id,
                    "version": draft["version"],
                    "reason": "no source URL was given and grounding is empty or thin — searching again, "
                    "this time aimed at what the evaluation flagged, instead of revising wording that can't "
                    "fix a sourcing gap",
                    "research_focus": research_focus,
                },
            }
        ).execute()
        db.table("jobs").insert(
            {
                "job_type": JobType.RESEARCH.value,
                "reference_type": JobReferenceType.CONTENT_REQUEST.value,
                "reference_id": request_id,
                "payload": {
                    "gap_fill_for_draft_id": draft_id,
                    "research_focus": research_focus,
                    "revision_instructions": evaluation_row["revision_instructions"],
                },
            }
        ).execute()
        return

    if passed or at_cap or ungroundable or result["overall_status"] == "reject":
        db.table("article_drafts").update({"status": DraftStatus.EVALUATED.value}).eq("id", draft_id).execute()
        db.table("content_requests").update(
            {"status": RequestStatus.IN_REVIEW.value, "updated_at": datetime.now(UTC).isoformat()}
        ).eq("id", request_id).execute()
        if at_cap and not passed:
            db.table("stage_events").insert(
                {
                    "content_request_id": request_id,
                    "stage": PipelineStage.EVALUATION.value,
                    "status": StageEventStatus.FAILED.value,
                    "detail": {"draft_id": draft_id, "version": draft["version"]},
                    "error_message": (
                        f"revision cap ({settings.max_revisions}) reached without passing evaluation; "
                        "sending to human review as-is"
                    ),
                }
            ).execute()
        elif ungroundable:
            db.table("stage_events").insert(
                {
                    "content_request_id": request_id,
                    "stage": PipelineStage.EVALUATION.value,
                    "status": StageEventStatus.FAILED.value,
                    "detail": {"draft_id": draft_id, "version": draft["version"]},
                    "error_message": (
                        "this draft has no source material to ground claims in, and revising the "
                        "wording can't fix that — skipping the remaining automatic revisions and "
                        "sending it to human review now instead of spending the full revision cap"
                    ),
                }
            ).execute()
        if is_regression:
            # Only reachable here via at_cap/ungroundable/reject — a plain
            # regression alone can no longer reach this block (it's folded
            # into `passed` above, which routes it back to another revision
            # instead). This is what happens when even the revision cap ran
            # out before it recovered.
            db.table("stage_events").insert(
                {
                    "content_request_id": request_id,
                    "stage": PipelineStage.EVALUATION.value,
                    "status": StageEventStatus.FAILED.value,
                    "detail": {
                        "draft_id": draft_id,
                        "version": draft["version"],
                        "score_delta_from_parent": score_delta_from_parent,
                    },
                    "error_message": (
                        f"this version still scored lower than its parent draft ({parent_score:.2f} -> "
                        f"{result['overall_score']:.2f}) after exhausting the available automatic revisions "
                        "— sending to review as-is; check the previous version for anything worth keeping"
                    ),
                }
            ).execute()
        return

    # revise: most revisions are wording problems Sonnet can fix on its own.
    # But specific unsupported claims call for something more mechanical
    # than a reword or a stronger model guessing better — go find real,
    # verified evidence for those exact claims first (worker/handlers/
    # gather_evidence.py), then regenerate with that evidence in hand,
    # escalated to Opus. Weak-but-nonspecific grounding (no named claims to
    # research — grounding_is_weak, as opposed to ungroundable's "no real
    # evidence" case routed to gap-fill above) still escalates straight to
    # Opus, since there's nothing concrete to look up.
    db.table("content_requests").update(
        {"status": RequestStatus.REVISING.value, "updated_at": datetime.now(UTC).isoformat()}
    ).eq("id", request_id).execute()

    if unsupported_claims:
        regeneration_requirements = build_regeneration_requirements(evaluation_result=result, guard=guard)
        db.table("jobs").insert(
            {
                "job_type": JobType.GATHER_EVIDENCE.value,
                "reference_type": JobReferenceType.ARTICLE_DRAFT.value,
                "reference_id": draft_id,
                "payload": {
                    "claims": [c["claim_text"] for c in regeneration_requirements["claims_needing_research"]],
                    "revision_instructions": evaluation_row["revision_instructions"],
                    "regeneration_requirements": regeneration_requirements,
                },
            }
        ).execute()
        return

    generate_payload = {"revision_instructions": evaluation_row["revision_instructions"]}
    if grounding_is_weak:
        generate_payload["escalated_model"] = OPUS
    db.table("jobs").insert(
        {
            "job_type": JobType.GENERATE.value,
            "reference_type": JobReferenceType.ARTICLE_DRAFT.value,
            "reference_id": draft_id,
            "payload": generate_payload,
        }
    ).execute()
