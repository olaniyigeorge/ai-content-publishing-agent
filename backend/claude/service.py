"""Composes client.py + models.py + prompts/ + outputs.py into one function
per pipeline step. Worker handlers call these, never the Claude SDK or the
prompt builders directly.
"""

from claude.client import structured_chat
from claude.models import HAIKU, model_for
from claude.outputs import (
    ADAPTATION_SCHEMA,
    CLAIM_VERIFICATION_SCHEMA,
    EVALUATION_SCHEMA,
    INTAKE_PLAUSIBILITY_SCHEMA,
    PLAN_SCHEMA,
    SOURCE_SELECTION_SCHEMA,
)
from claude.prompts import adapt as adapt_prompts
from claude.prompts import evaluate as evaluate_prompts
from claude.prompts import generate as generate_prompts
from claude.prompts import intake_check as intake_check_prompts
from claude.prompts import plan as plan_prompts
from claude.prompts import research as research_prompts
from claude.prompts import verify_evidence as verify_evidence_prompts
from shared.enums import JobType


def select_sources(
    *,
    raw_idea: str | None,
    target_audience: str,
    sources: list[dict],
    research_focus: str | None = None,
) -> dict:
    return structured_chat(
        model=model_for(JobType.RESEARCH),
        system=research_prompts.SYSTEM,
        user_message=research_prompts.build_user_message(
            raw_idea=raw_idea, target_audience=target_audience, sources=sources, research_focus=research_focus
        ),
        output_schema=SOURCE_SELECTION_SCHEMA,
        tool_name="select_sources",
    )


def build_plan(*, raw_idea: str | None, target_audience: str, sources: list[dict]) -> dict:
    return structured_chat(
        model=model_for(JobType.PLAN),
        system=plan_prompts.SYSTEM,
        user_message=plan_prompts.build_user_message(
            raw_idea=raw_idea, target_audience=target_audience, sources=sources
        ),
        output_schema=PLAN_SCHEMA,
        tool_name="build_plan",
    )


def generate_draft(
    *,
    raw_idea: str | None,
    target_audience: str,
    outline: dict,
    target_keywords: list[str],
    sources: list[dict],
    revision_instructions: str | None = None,
    previous_body_markdown: str | None = None,
    model: str | None = None,
    evidence_package: list[dict] | None = None,
    claims_to_address: list[dict] | None = None,
) -> str:
    """Returns raw markdown, not structured output — the article itself is the
    artifact; forcing it through a tool-call schema buys nothing here.

    `model` overrides the default GENERATE-step model — used by
    worker/handlers/generate.py to escalate a regeneration to Opus when the
    prior evaluation flagged a fundamental reasoning or source-interpretation
    problem rather than just weak wording (see claude/models.py).

    `evidence_package`/`claims_to_address` come from
    worker/handlers/gather_evidence.py: specific previously-unsupported
    claims that now have verified evidence, and ones that still don't (and
    must be hedged as inference or removed) — see
    claude/prompts/generate.py."""
    from claude.client import chat

    return chat(
        model=model or model_for(JobType.GENERATE),
        system=generate_prompts.SYSTEM,
        user_message=generate_prompts.build_user_message(
            raw_idea=raw_idea,
            target_audience=target_audience,
            outline=outline,
            target_keywords=target_keywords,
            sources=sources,
            revision_instructions=revision_instructions,
            previous_body_markdown=previous_body_markdown,
            evidence_package=evidence_package,
            claims_to_address=claims_to_address,
        ),
        max_tokens=8192,
    )


def evaluate_draft(*, target_audience: str, draft_title: str, draft_body: str, sources: list[dict]) -> dict:
    return structured_chat(
        model=model_for(JobType.EVALUATE),
        system=evaluate_prompts.SYSTEM,
        user_message=evaluate_prompts.build_user_message(
            target_audience=target_audience, draft_title=draft_title, draft_body=draft_body, sources=sources
        ),
        output_schema=EVALUATION_SCHEMA,
        tool_name="evaluate_draft",
    )


def verify_claim_evidence(*, claim_text: str, source_title: str | None, source_url: str, source_content: str) -> dict:
    return structured_chat(
        model=model_for(JobType.GATHER_EVIDENCE),
        system=verify_evidence_prompts.SYSTEM,
        user_message=verify_evidence_prompts.build_user_message(
            claim_text=claim_text, source_title=source_title, source_url=source_url, source_content=source_content
        ),
        output_schema=CLAIM_VERIFICATION_SCHEMA,
        tool_name="verify_claim_evidence",
    )


def check_intake_plausibility(*, raw_idea: str | None, target_audience: str) -> dict:
    """Runs synchronously in the intake API request (not a worker job) —
    HAIKU directly, not model_for(), since this isn't a pipeline step in the
    job_type enum, just a cheap pre-check ahead of one. See
    app/services/intake_service.py for the fail-open handling around this
    call — an API/network error here must never block a real submission."""
    return structured_chat(
        model=HAIKU,
        system=intake_check_prompts.SYSTEM,
        user_message=intake_check_prompts.build_user_message(raw_idea=raw_idea, target_audience=target_audience),
        output_schema=INTAKE_PLAUSIBILITY_SCHEMA,
        tool_name="check_intake_plausibility",
        max_tokens=256,
    )


def adapt_for_channel(
    *,
    channel: str,
    article_title: str,
    article_body_markdown: str,
    target_audience: str,
    revision_instructions: str | None = None,
    previous_content: str | None = None,
) -> dict:
    return structured_chat(
        model=model_for(JobType.ADAPT),
        system=adapt_prompts.SYSTEM_BY_CHANNEL[channel] + adapt_prompts.TONE_GUIDANCE,
        user_message=adapt_prompts.build_user_message(
            article_title=article_title,
            article_body_markdown=article_body_markdown,
            target_audience=target_audience,
            revision_instructions=revision_instructions,
            previous_content=previous_content,
        ),
        output_schema=ADAPTATION_SCHEMA,
        tool_name="adapt_for_channel",
    )
