"""claude/errors.py — classifying a raw Anthropic SDK exception into a
retry decision and a message safe to show a user, instead of dumping
`str(exc)` (e.g. "Error code: 400 - {'type': 'error', ...}") straight into
stage_events.error_message, which is what the pipeline timeline used to do.
"""

import anthropic
import httpx
import pytest

from claude.errors import friendly_message, is_retryable

REQUEST = httpx.Request("POST", "https://api.anthropic.com/v1/messages")


def _status_error(cls, status_code: int, body: dict):
    response = httpx.Response(status_code, request=REQUEST, json=body)
    return cls(f"Error code: {status_code} - {body}", response=response, body=body)


def _credit_balance_error():
    body = {
        "type": "error",
        "error": {
            "type": "invalid_request_error",
            "message": "Your credit balance is too low to access the Anthropic API. Please go to "
            "Plans & Billing to upgrade or purchase credits.",
        },
    }
    return _status_error(anthropic.BadRequestError, 400, body)


@pytest.mark.parametrize(
    "cls,status_code",
    [
        (anthropic.RateLimitError, 429),
        (anthropic.InternalServerError, 500),
        (anthropic.ServiceUnavailableError, 503),
        (anthropic.OverloadedError, 529),
    ],
)
def test_transient_status_errors_are_retryable(cls, status_code):
    exc = _status_error(cls, status_code, {"type": "error", "error": {"type": "x", "message": "temporary"}})
    assert is_retryable(exc) is True


@pytest.mark.parametrize(
    "cls,status_code",
    [
        (anthropic.BadRequestError, 400),
        (anthropic.AuthenticationError, 401),
        (anthropic.PermissionDeniedError, 403),
        (anthropic.NotFoundError, 404),
        (anthropic.UnprocessableEntityError, 422),
    ],
)
def test_permanent_status_errors_are_not_retryable(cls, status_code):
    exc = _status_error(cls, status_code, {"type": "error", "error": {"type": "x", "message": "permanent"}})
    assert is_retryable(exc) is False


def test_non_anthropic_exception_defaults_to_retryable():
    assert is_retryable(RuntimeError("some other failure")) is True


def test_credit_balance_error_gets_a_specific_actionable_message():
    message = friendly_message(_credit_balance_error())
    assert "credit balance" not in message.lower()  # not the raw SDK dump
    assert "credit" in message.lower()
    assert "{" not in message  # no raw dict/repr leaking through


def test_auth_error_gets_a_specific_message():
    exc = _status_error(anthropic.AuthenticationError, 401, {"type": "error", "error": {"message": "invalid key"}})
    message = friendly_message(exc)
    assert "api key" in message.lower()
    assert "{" not in message


def test_rate_limit_error_message_mentions_automatic_retry():
    exc = _status_error(anthropic.RateLimitError, 429, {"type": "error", "error": {"message": "rate limited"}})
    assert "retry automatically" in friendly_message(exc).lower()


def test_non_anthropic_exception_message_falls_back_to_str():
    assert friendly_message(RuntimeError("plain failure")) == "plain failure"
