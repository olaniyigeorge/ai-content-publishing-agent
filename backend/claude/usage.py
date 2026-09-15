"""Per-call token/cost logging for every Claude request made through
claude/client.py. Attribution (which content request, which job/pipeline
step) is threaded through a contextvar rather than a parameter on every
service.py function — the worker sets it once per job (worker/main.py)
around the handler call, and client.py reads it when a response comes back.
This keeps model-selection call sites (claude/service.py) free of
bookkeeping args that have nothing to do with what they're asking Claude to
do.
"""

import contextlib
import logging
from contextvars import ContextVar
from typing import TypedDict

from claude.pricing import cost_usd
from db.client import get_supabase

logger = logging.getLogger(__name__)


class UsageContext(TypedDict):
    content_request_id: str | None
    job_id: str | None
    job_type: str | None


_CURRENT: ContextVar[UsageContext | None] = ContextVar("claude_usage_context", default=None)


@contextlib.contextmanager
def usage_context(*, content_request_id: str | None, job_id: str | None, job_type: str | None):
    token = _CURRENT.set({"content_request_id": content_request_id, "job_id": job_id, "job_type": job_type})
    try:
        yield
    finally:
        _CURRENT.reset(token)


def record(*, model: str, input_tokens: int, output_tokens: int) -> None:
    """Best-effort: a logging failure must never take down the Claude call it
    was logging (EDGE_CASES.md-style — the pipeline step already succeeded by
    the time this runs)."""
    ctx = _CURRENT.get() or UsageContext(content_request_id=None, job_id=None, job_type=None)
    try:
        get_supabase().table("claude_usage").insert(
            {
                "content_request_id": ctx["content_request_id"],
                "job_id": ctx["job_id"],
                "job_type": ctx["job_type"],
                "model": model,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "cost_usd": cost_usd(model=model, input_tokens=input_tokens, output_tokens=output_tokens),
            }
        ).execute()
    except Exception:
        logger.exception("failed to record claude usage for job %s", ctx.get("job_id"))
