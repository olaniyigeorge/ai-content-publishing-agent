"""Classifies raw Anthropic SDK exceptions for the worker's failure path
(worker/main.py) — turns `str(exc)` (a dumped SDK error like
`Error code: 400 - {'type': 'error', 'error': {...}}`) into a message a
human can actually act on, and tells the retry policy (worker/retry.py)
whether retrying can ever succeed.

anthropic.APIStatusError subclasses by status code: 400 BadRequestError,
401 AuthenticationError, 403 PermissionDeniedError, 404 NotFoundError,
409 ConflictError, 413 RequestTooLargeError, 422 UnprocessableEntityError,
429 RateLimitError, 5xx InternalServerError/ServiceUnavailableError/etc.
Only 429 and 5xx are worth retrying — every other 4xx will fail identically
on every attempt (bad request shape, bad/expired key, insufficient credits,
...), so burning the retry budget on those just delays a fix the user has
to make anyway.
"""

import anthropic


def is_retryable(exc: Exception) -> bool:
    if isinstance(exc, anthropic.APIStatusError):
        return exc.status_code == 429 or exc.status_code >= 500
    # Not an Anthropic status error (network blip, our own bug, etc.) —
    # keep the old assume-transient behavior rather than guessing wrong.
    return True


def _status_error_detail(exc: anthropic.APIStatusError) -> str:
    body = exc.body if isinstance(exc.body, dict) else {}
    return body.get("error", {}).get("message") or str(exc)


def friendly_message(exc: Exception) -> str:
    """A message safe to show a user in the pipeline timeline — no raw SDK
    repr, no request_id noise. Callers should still log/store str(exc)
    somewhere developer-facing (jobs.last_error) alongside this."""
    if not isinstance(exc, anthropic.APIStatusError):
        return str(exc)

    detail = _status_error_detail(exc)
    if exc.status_code == 400 and "credit balance" in detail.lower():
        return (
            "The Anthropic account this app uses has run out of API credit. "
            "Add credit in the Anthropic console, then retry this step — it will not "
            "succeed on its own."
        )
    if exc.status_code in (401, 403):
        return "The Anthropic API key is invalid, missing, or not authorized — this will not resolve on its own."
    if exc.status_code == 429:
        return "Anthropic's API rate limit was hit — this will retry automatically."
    if exc.status_code >= 500:
        return "Anthropic's API had a temporary problem on their end — this will retry automatically."
    return f"Anthropic API rejected the request ({exc.status_code}): {detail}"
