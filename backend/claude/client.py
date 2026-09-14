"""Thin wrapper around the Claude SDK. No business logic here — it's the
boundary. Everything in app/, worker/, and auth/ calls into claude/, never
the Anthropic SDK directly, so model selection stays centralized in
claude/models.py.
"""

import json
from functools import lru_cache
from typing import Any

import anthropic

from app.config import get_settings


@lru_cache
def _client() -> anthropic.Anthropic:
    settings = get_settings()
    return anthropic.Anthropic(api_key=settings.anthropic_api_key)


def chat(
    *,
    model: str,
    system: str,
    user_message: str,
    max_tokens: int = 4096,
) -> str:
    """Plain-text completion. Raises anthropic.APIError on failure — callers
    (worker handlers) catch this and write it to stage_events/jobs.last_error."""
    response = _client().messages.create(
        model=model,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user_message}],
    )
    return "".join(block.text for block in response.content if block.type == "text")


def structured_chat(
    *,
    model: str,
    system: str,
    user_message: str,
    output_schema: dict[str, Any],
    tool_name: str,
    max_tokens: int = 4096,
) -> dict[str, Any]:
    """Structured-output completion. Forces the model to respond via a single
    tool call matching output_schema, and returns the parsed tool input.

    This is what makes the evaluation rubric and the adaptation formatting
    checks a real, parseable data contract instead of prose the worker hopes
    the model followed (per architecture.md §9.2, claude/outputs.py).
    """
    response = _client().messages.create(
        model=model,
        max_tokens=max_tokens,
        system=system,
        tools=[
            {
                "name": tool_name,
                "description": f"Return the {tool_name} result.",
                "input_schema": output_schema,
            }
        ],
        tool_choice={"type": "tool", "name": tool_name},
        messages=[{"role": "user", "content": user_message}],
    )
    for block in response.content:
        if block.type == "tool_use" and block.name == tool_name:
            return block.input
    raise ValueError(
        f"Claude did not return a '{tool_name}' tool call: {json.dumps([b.type for b in response.content])}"
    )
