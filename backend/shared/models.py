"""Pydantic v2 models — the API contract between backend and frontend.

DB rows (architecture.md §3) are internal; these are what the frontend and
tests talk to.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from shared.enums import (
    AdaptationStatus,
    AttachmentType,
    Channel,
    ContentFormat,
    DraftStatus,
    EvaluatedBy,
    JobType,
    QueueStatus,
    RequestStatus,
    ReviewDecision,
    SourceRetrievalMethod,
    SourceStatus,
    StageEventStatus,
)

# ---- Intake ----------------------------------------------------------------


class IntakeAttachmentIn(BaseModel):
    type: AttachmentType
    url: str | None = None
    storage_path: str | None = None
    description: str | None = None


class ContentRequestCreate(BaseModel):
    raw_idea: str | None = None
    target_audience: str
    supporting_material: dict | None = None
    attachments: list[IntakeAttachmentIn] = []


class IntakeAttachmentOut(IntakeAttachmentIn):
    id: UUID
    content_request_id: UUID
    created_at: datetime


class ContentRequestOut(BaseModel):
    id: UUID
    raw_idea: str | None
    target_audience: str
    supporting_material: dict | None
    status: RequestStatus
    submitted_by_user_id: UUID
    created_at: datetime
    updated_at: datetime


# ---- Sources ----------------------------------------------------------------


class SourceOut(BaseModel):
    id: UUID
    content_request_id: UUID
    intake_attachment_id: UUID | None
    url: str
    title: str | None
    excerpt_selected: str | None
    relevance_notes: str | None
    discard_reason: str | None
    retrieval_method: SourceRetrievalMethod
    status: SourceStatus
    retrieved_at: datetime | None
    created_at: datetime


# ---- Drafts / evaluations ---------------------------------------------------


class ArticleDraftOut(BaseModel):
    id: UUID
    content_request_id: UUID
    content_plan_id: UUID | None
    option_label: str
    version: int
    parent_draft_id: UUID | None
    title: str
    body_markdown: str
    source_ids_used: list[UUID]
    status: DraftStatus
    created_at: datetime


class EvaluationOut(BaseModel):
    id: UUID
    article_draft_id: UUID
    rubric_scores: dict
    overall_score: float
    passed_threshold: bool
    feedback: str
    revision_instructions: str | None
    evaluated_by: EvaluatedBy
    created_at: datetime


# ---- Human review ------------------------------------------------------------


class HumanReviewIn(BaseModel):
    article_draft_id: UUID
    decision: ReviewDecision
    notes: str | None = None


class HumanReviewOut(HumanReviewIn):
    id: UUID
    content_request_id: UUID
    reviewer_user_id: UUID
    created_at: datetime


# ---- Channel adaptations -----------------------------------------------------


class ChannelAdaptationOut(BaseModel):
    id: UUID
    content_request_id: UUID
    article_draft_id: UUID
    channel: Channel
    content: str
    content_format: ContentFormat
    formatting_check: dict | None
    status: AdaptationStatus
    created_at: datetime
    updated_at: datetime


# ---- Publishing queue ---------------------------------------------------------


class PublishingQueueOut(BaseModel):
    id: UUID
    channel_adaptation_id: UUID
    scheduled_for: datetime | None
    status: QueueStatus
    attempts: int
    max_attempts: int
    last_error: str | None
    next_attempt_at: datetime | None
    published_at: datetime | None
    created_at: datetime
    updated_at: datetime
    # Denormalized from channel_adaptations / article_drafts / content_requests
    # so the publishing-queue list view doesn't need N follow-up requests just
    # to show what a row actually is.
    content_request_id: UUID | None = None
    channel: Channel | None = None
    content: str | None = None
    content_format: ContentFormat | None = None
    article_title: str | None = None
    failure_reason: str | None = None


class PublishingQueueScheduleIn(BaseModel):
    scheduled_for: datetime | None = None


class PublishingQueueStatusIn(BaseModel):
    status: QueueStatus


# ---- Rewrite (regenerate with AI) ----------------------------------------------


class DraftRewriteIn(BaseModel):
    instructions: str | None = None


class DraftManualEditIn(BaseModel):
    title: str | None = None
    body_markdown: str


class ChannelAdaptationRewriteIn(BaseModel):
    instructions: str | None = None


class RewriteAccepted(BaseModel):
    job_id: UUID
    status: str = "queued"


# ---- Stage events -------------------------------------------------------------


class StageEventOut(BaseModel):
    id: UUID
    content_request_id: UUID
    stage: str
    status: StageEventStatus
    detail: dict | None
    error_message: str | None
    created_at: datetime


# ---- Claude usage / cost -----------------------------------------------------


class ClaudeUsageOut(BaseModel):
    id: UUID
    content_request_id: UUID | None
    job_id: UUID | None
    job_type: JobType | None
    model: str
    input_tokens: int
    output_tokens: int
    cost_usd: float
    created_at: datetime


class UsageModelBreakdown(BaseModel):
    input_tokens: int
    output_tokens: int
    cost_usd: float
    call_count: int


class UsageSummaryOut(BaseModel):
    total_input_tokens: int
    total_output_tokens: int
    total_cost_usd: float
    call_count: int
    by_model: dict[str, UsageModelBreakdown] = {}


# ---- Full request detail -------------------------------------------------------


class ContentRequestDetail(BaseModel):
    request: ContentRequestOut
    attachments: list[IntakeAttachmentOut]
    sources: list[SourceOut]
    drafts: list[ArticleDraftOut]
    evaluations: list[EvaluationOut]
    human_reviews: list[HumanReviewOut]
    adaptations: list[ChannelAdaptationOut]
    publishing_queue: list[PublishingQueueOut]
    stage_events: list[StageEventOut]
    usage: list[ClaudeUsageOut]
