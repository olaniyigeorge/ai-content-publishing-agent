"""Every `create type ... as enum` from architecture.md §2, as Python enums.

This is the single source of truth for enum values. `app/`, `worker/`, and
`auth/` all import from here so the API and the worker can't drift apart on
what a status value can be.
"""

from enum import StrEnum


class RequestStatus(StrEnum):
    INTAKE = "intake"
    RESEARCHING = "researching"
    PLANNING = "planning"
    DRAFTING = "drafting"
    EVALUATING = "evaluating"
    REVISING = "revising"
    IN_REVIEW = "in_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    ADAPTING = "adapting"
    QUEUED = "queued"
    PUBLISHED = "published"
    FAILED = "failed"


class AttachmentType(StrEnum):
    URL = "url"
    IMAGE = "image"
    FILE = "file"


class SourceRetrievalMethod(StrEnum):
    URL_PROVIDED = "url_provided"
    WEB_SEARCH = "web_search"


class SourceStatus(StrEnum):
    RETRIEVED = "retrieved"
    FAILED = "failed"
    SELECTED = "selected"
    DISCARDED = "discarded"


class SourceConfidence(StrEnum):
    """Independent of status: a `selected` source can still be `thin` —
    real, usable evidence that's weak (single low-authority source,
    outdated, tangential) rather than solidly grounded. Never hidden from
    the reviewer; see claude/prompts/research.py."""

    STRONG = "strong"
    THIN = "thin"


class DraftStatus(StrEnum):
    DRAFT = "draft"
    EVALUATED = "evaluated"
    REVISED = "revised"
    SELECTED = "selected"
    DISCARDED = "discarded"


class EvaluatedBy(StrEnum):
    AI = "ai"
    HUMAN = "human"


class ReviewDecision(StrEnum):
    APPROVED = "approved"
    REJECTED = "rejected"
    REVISE_REQUESTED = "revise_requested"
    OPTION_SELECTED = "option_selected"


class Channel(StrEnum):
    LINKEDIN = "linkedin"
    X = "x"
    NEWSLETTER = "newsletter"


class ContentFormat(StrEnum):
    PLAIN_TEXT = "plain_text"
    HTML = "html"


class AdaptationStatus(StrEnum):
    DRAFT = "draft"
    APPROVED = "approved"
    QUEUED = "queued"
    PUBLISHED = "published"
    FAILED = "failed"


class QueueStatus(StrEnum):
    QUEUED = "queued"
    PROCESSING = "processing"
    READY_TO_PUBLISH = "ready_to_publish"
    PUBLISHED = "published"
    FAILED = "failed"
    DEAD_LETTER = "dead_letter"
    CANCELLED = "cancelled"


class JobType(StrEnum):
    RESEARCH = "research"
    PLAN = "plan"
    GENERATE = "generate"
    EVALUATE = "evaluate"
    ADAPT = "adapt"
    PUBLISH = "publish"


class JobReferenceType(StrEnum):
    CONTENT_REQUEST = "content_request"
    ARTICLE_DRAFT = "article_draft"
    PUBLISHING_QUEUE = "publishing_queue"


class JobStatus(StrEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class PipelineStage(StrEnum):
    INTAKE = "intake"
    RESEARCH = "research"
    RETRIEVAL = "retrieval"
    PLANNING = "planning"
    GENERATION = "generation"
    EVALUATION = "evaluation"
    REVISION = "revision"
    HUMAN_REVIEW = "human_review"
    ADAPTATION = "adaptation"
    PUBLISHING_QUEUE = "publishing_queue"
    PUBLISHING = "publishing"


class StageEventStatus(StrEnum):
    STARTED = "started"
    SUCCEEDED = "succeeded"
    RETRYING = "retrying"
    """A job attempt failed but the worker will automatically retry it —
    distinct from FAILED so the UI doesn't show a hard red error for
    something that's still self-healing (see worker/main.py)."""
    FAILED = "failed"


class AccessRuleType(StrEnum):
    EMAIL = "email"
    DOMAIN = "domain"
