// Mirrors backend/shared/enums.py and backend/shared/models.py — keep in sync
// with the API contract by hand (no codegen wired up yet, see DECISIONS.md).

export type RequestStatus =
  | "intake"
  | "researching"
  | "planning"
  | "drafting"
  | "evaluating"
  | "revising"
  | "in_review"
  | "approved"
  | "rejected"
  | "adapting"
  | "queued"
  | "published"
  | "failed";

export type AttachmentType = "url" | "image" | "file";
export type SourceRetrievalMethod = "url_provided" | "web_search";
export type SourceStatus = "retrieved" | "failed" | "selected" | "discarded";
export type DraftStatus = "draft" | "evaluated" | "revised" | "selected" | "discarded";
export type EvaluatedBy = "ai" | "human";
export type ReviewDecision = "approved" | "rejected" | "revise_requested" | "option_selected";
export type Channel = "linkedin" | "x" | "newsletter";
export type ContentFormat = "plain_text" | "html";
export type AdaptationStatus = "draft" | "approved" | "queued" | "published" | "failed";
export type QueueStatus = "queued" | "processing" | "published" | "failed" | "dead_letter" | "cancelled";
export type StageEventStatus = "started" | "succeeded" | "failed";

export interface MeResponse {
  id: string;
  email: string;
  last_login_at: string | null;
}

export interface IntakeAttachmentIn {
  type: AttachmentType;
  url?: string | null;
  storage_path?: string | null;
  description?: string | null;
}

export interface IntakeAttachmentOut extends IntakeAttachmentIn {
  id: string;
  content_request_id: string;
  created_at: string;
}

export interface ContentRequestCreate {
  raw_idea?: string | null;
  target_audience: string;
  supporting_material?: Record<string, unknown> | null;
  attachments: IntakeAttachmentIn[];
}

export interface ContentRequestOut {
  id: string;
  raw_idea: string | null;
  target_audience: string;
  supporting_material: Record<string, unknown> | null;
  status: RequestStatus;
  submitted_by_user_id: string;
  created_at: string;
  updated_at: string;
}

export interface SourceOut {
  id: string;
  content_request_id: string;
  intake_attachment_id: string | null;
  url: string;
  title: string | null;
  excerpt_selected: string | null;
  relevance_notes: string | null;
  retrieval_method: SourceRetrievalMethod;
  status: SourceStatus;
  retrieved_at: string | null;
  created_at: string;
}

export interface ArticleDraftOut {
  id: string;
  content_request_id: string;
  content_plan_id: string | null;
  option_label: string;
  version: number;
  parent_draft_id: string | null;
  title: string;
  body_markdown: string;
  source_ids_used: string[];
  status: DraftStatus;
  created_at: string;
}

export interface EvaluationOut {
  id: string;
  article_draft_id: string;
  rubric_scores: Record<string, unknown>;
  overall_score: number;
  passed_threshold: boolean;
  feedback: string;
  revision_instructions: string | null;
  evaluated_by: EvaluatedBy;
  created_at: string;
}

export interface HumanReviewOut {
  id: string;
  content_request_id: string;
  article_draft_id: string;
  decision: ReviewDecision;
  notes: string | null;
  reviewer_user_id: string;
  created_at: string;
}

export interface ChannelAdaptationOut {
  id: string;
  content_request_id: string;
  article_draft_id: string;
  channel: Channel;
  content: string;
  content_format: ContentFormat;
  formatting_check: Record<string, unknown> | null;
  status: AdaptationStatus;
  created_at: string;
  updated_at: string;
}

export interface PublishingQueueOut {
  id: string;
  channel_adaptation_id: string;
  scheduled_for: string | null;
  status: QueueStatus;
  attempts: number;
  max_attempts: number;
  last_error: string | null;
  next_attempt_at: string | null;
  published_at: string | null;
  created_at: string;
  updated_at: string;
  content_request_id: string | null;
  channel: Channel | null;
  content: string | null;
  content_format: ContentFormat | null;
  article_title: string | null;
  failure_reason: string | null;
}

export interface StageEventOut {
  id: string;
  content_request_id: string;
  stage: string;
  status: StageEventStatus;
  detail: Record<string, unknown> | null;
  error_message: string | null;
  created_at: string;
}

export interface RewriteAccepted {
  job_id: string;
  status: string;
}

export interface ContentRequestDetail {
  request: ContentRequestOut;
  attachments: IntakeAttachmentOut[];
  sources: SourceOut[];
  drafts: ArticleDraftOut[];
  evaluations: EvaluationOut[];
  human_reviews: HumanReviewOut[];
  adaptations: ChannelAdaptationOut[];
  publishing_queue: PublishingQueueOut[];
  stage_events: StageEventOut[];
}
