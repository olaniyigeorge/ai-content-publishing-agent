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
from claude import usage

CLIENT_TIMEOUT_SECONDS = 120.0
"""No timeout is set by default: a hung call would block a worker job (and
the whole single-threaded poll loop) indefinitely, never reaching the
retry/backoff logic in worker/retry.py."""


@lru_cache
def _client() -> anthropic.Anthropic:
    settings = get_settings()
    return anthropic.Anthropic(api_key=settings.anthropic_api_key, timeout=CLIENT_TIMEOUT_SECONDS)


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
    usage.record(
        model=model, input_tokens=response.usage.input_tokens, output_tokens=response.usage.output_tokens
    )
    return "".join(block.text for block in response.content if block.type == "text")


MAX_STRUCTURED_REPAIRS = 2
"""A tool's `input_schema.required` is a description of intent to the model,
not a server-enforced contract (the tool isn't declared `strict`) — Claude
can still return a tool call missing a required field (TESTING_FINDINGS2.md,
2026-09-18: 'planning' stuck retrying at the job level, 2/4-minute backoff
between attempts, on the exact same prompt each time, for the same missing
`target_keywords` field). Repairing in-conversation, in the same call, is
both faster (no backoff wait) and more likely to work (the model sees
exactly what it omitted) than relying on worker/retry.py's blind re-run."""


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

    If the tool call is missing a field listed in output_schema['required'],
    this feeds that back to the model and asks it to resubmit, up to
    MAX_STRUCTURED_REPAIRS times, before giving up and returning whatever it
    last got (the caller's own require_fields() check is the final backstop).
    """
    tools = [
        {
            "name": tool_name,
            "description": f"Return the {tool_name} result.",
            "input_schema": output_schema,
        }
    ]
    required = output_schema.get("required", [])
    messages: list[dict[str, Any]] = [{"role": "user", "content": user_message}]

    for repair_attempt in range(MAX_STRUCTURED_REPAIRS + 1):
        response = _client().messages.create(
            model=model,
            max_tokens=max_tokens,
            system=system,
            tools=tools,
            tool_choice={"type": "tool", "name": tool_name},
            messages=messages,
        )
        usage.record(
            model=model, input_tokens=response.usage.input_tokens, output_tokens=response.usage.output_tokens
        )
        tool_use_block = next(
            (block for block in response.content if block.type == "tool_use" and block.name == tool_name), None
        )
        if tool_use_block is None:
            raise ValueError(
                f"Claude did not return a '{tool_name}' tool call: {json.dumps([b.type for b in response.content])}"
            )

        missing = [k for k in required if k not in tool_use_block.input]
        if not missing or repair_attempt == MAX_STRUCTURED_REPAIRS:
            return tool_use_block.input

        messages.append({"role": "assistant", "content": response.content})
        messages.append(
            {
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": tool_use_block.id,
                        "content": (
                            f"Your {tool_name} call was missing required field(s) {missing}. "
                            f"Call {tool_name} again with the complete result, including {missing}."
                        ),
                    }
                ],
            }
        )

    raise AssertionError("unreachable")  # loop always returns or raises above
