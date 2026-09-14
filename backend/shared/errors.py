"""Domain errors. Each one carries a message meant to be read directly by a
human debugging a failure — via stage_events.error_message or jobs.last_error
or an HTTP response — not a generic 500.
"""


class DomainError(Exception):
    status_code: int = 500

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class ValidationFailure(DomainError):
    status_code = 422


class NotFound(DomainError):
    status_code = 404


class NotAuthorized(DomainError):
    status_code = 401


class InvalidStateTransition(DomainError):
    """Raised when an action is attempted against a request/draft that isn't
    in a state that allows it (e.g. reviewing a draft that hasn't been
    evaluated yet, or approving twice)."""

    status_code = 409


class ApprovalRequired(DomainError):
    """Raised if something tries to enqueue adaptation/publishing without a
    human_reviews row approving the draft. Should never surface over HTTP in
    normal operation — it's a defense-in-depth check in the service layer."""

    status_code = 409


class ResearchFailure(DomainError):
    status_code = 502


class DraftGenerationFailed(DomainError):
    status_code = 502


class DraftEvaluationFailed(DomainError):
    status_code = 502


class AdaptationFailed(DomainError):
    status_code = 502


class PublishFailed(DomainError):
    status_code = 502
