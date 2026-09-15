"""Composes client.py + models.py + prompts/ + outputs.py into one function
per pipeline step. Worker handlers call these, never the Claude SDK or the
prompt builders directly.
"""

from claude.client import structured_chat
from claude.models import model_for
from claude.outputs import (
    ADAPTATION_SCHEMA,
    EVALUATION_SCHEMA,
    PLAN_SCHEMA,
    SOURCE_SELECTION_SCHEMA,
)
from claude.prompts import adapt as adapt_prompts
from claude.prompts import evaluate as evaluate_prompts
from claude.prompts import generate as generate_prompts
from claude.prompts import plan as plan_prompts
from claude.prompts import research as research_prompts
from shared.enums import JobType


def select_sources(*, raw_idea: str | None, target_audience: str, sources: list[dict]) -> dict:
    return structured_chat(
        model=model_for(JobType.RESEARCH),
        system=research_prompts.SYSTEM,
        user_message=research_prompts.build_user_message(
            raw_idea=raw_idea, target_audience=target_audience, sources=sources
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
) -> str:
    """Returns raw markdown, not structured output — the article itself is the
    artifact; forcing it through a tool-call schema buys nothing here."""
    from claude.client import chat

    return chat(
        model=model_for(JobType.GENERATE),
        system=generate_prompts.SYSTEM,
        user_message=generate_prompts.build_user_message(
            raw_idea=raw_idea,
            target_audience=target_audience,
            outline=outline,
            target_keywords=target_keywords,
            sources=sources,
            revision_instructions=revision_instructions,
            previous_body_markdown=previous_body_markdown,
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
