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
    GATHER_EVIDENCE = "gather_evidence"
    """Evidence-driven regeneration: given a draft's specific unsupported
    claims, search for and verify real sources before handing the generator
    a verified evidence package — see worker/handlers/gather_evidence.py."""


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
    EVIDENCE_GATHERING = "evidence_gathering"
    GROUNDING_VALIDATION = "grounding_validation"


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


class ClaimType(StrEnum):
    """Not a Postgres enum/column — this classifies entries inside the
    evidence-driven regeneration payloads (jobs.payload's evidence_package /
    claims_to_address), not a persisted row. See
    worker/handlers/gather_evidence.py and claude/grounding_validator.py."""

    SUPPORTED_FACT = "supported_fact"
    """Directly backed by a verified, strong-confidence source excerpt."""
    ATTRIBUTED_CLAIM = "attributed_claim"
    """Backed by evidence, but the evidence itself is an opinion/attributed
    statement (a named person or thin source said X) rather than a settled
    fact — must stay attributed/hedged in the draft, not stated flatly."""
    INFERENCE = "inference"
    """No direct evidence found; acceptable only if rewritten as a clearly
    hedged hypothesis rather than presented as fact."""
    RECOMMENDATION = "recommendation"
    """An actionable suggestion to the reader, not a factual assertion —
    doesn't need source grounding the way a fact claim does."""
    UNSUPPORTED = "unsupported"
    """No evidence found and not (yet) rewritten as inference/hedged —
    must receive evidence, become an inference, or be removed before the
    draft is acceptable (see gather_evidence.py's claims_to_address)."""
