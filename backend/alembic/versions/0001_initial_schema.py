"""initial schema — architecture.md §2-§6

Revision ID: 0001
Revises:
Create Date: 2026-09-14

"""
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

ENUMS_SQL = """
create type request_status as enum (
  'intake', 'researching', 'planning', 'drafting', 'evaluating',
  'revising', 'in_review', 'approved', 'rejected', 'adapting',
  'queued', 'published', 'failed'
);

create type attachment_type as enum ('url', 'image', 'file');
create type source_retrieval_method as enum ('url_provided', 'web_search');
create type source_status as enum ('retrieved', 'failed', 'selected', 'discarded');

create type draft_status as enum ('draft', 'evaluated', 'revised', 'selected', 'discarded');
create type evaluated_by as enum ('ai', 'human');

create type review_decision as enum ('approved', 'rejected', 'revise_requested', 'option_selected');

create type channel as enum ('linkedin', 'x', 'newsletter');
create type content_format as enum ('plain_text', 'html');
create type adaptation_status as enum ('draft', 'approved', 'queued', 'published', 'failed');

create type queue_status as enum ('queued', 'processing', 'published', 'failed', 'dead_letter', 'cancelled');

create type job_type as enum ('research', 'plan', 'generate', 'evaluate', 'adapt', 'publish');
create type job_reference_type as enum ('content_request', 'article_draft', 'publishing_queue');
create type job_status as enum ('pending', 'processing', 'succeeded', 'failed');

create type pipeline_stage as enum (
  'intake', 'research', 'retrieval', 'planning', 'generation',
  'evaluation', 'revision', 'human_review', 'adaptation',
  'publishing_queue', 'publishing'
);
create type stage_event_status as enum ('started', 'succeeded', 'failed');

create type access_rule_type as enum ('email', 'domain');
"""

TABLES_SQL = """
create extension if not exists pgcrypto;

-- §6 auth tables (created first: content_requests FKs into users)
create table access_rules (
  id uuid primary key default gen_random_uuid(),
  type access_rule_type not null,
  value text not null,
  enabled boolean not null default true,
  created_at timestamptz not null default now(),
  expires_at timestamptz
);

create table users (
  id uuid primary key default gen_random_uuid(),
  email text not null unique,
  created_at timestamptz not null default now(),
  last_login_at timestamptz
);

create table login_attempts (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references users(id) on delete cascade,
  code_hash text not null,
  expires_at timestamptz not null,
  attempts int not null default 0,
  max_attempts int not null default 5,
  consumed_at timestamptz,
  created_at timestamptz not null default now()
);

create table sessions (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references users(id) on delete cascade,
  expires_at timestamptz not null,
  created_at timestamptz not null default now()
);

-- §3.1 content_requests
create table content_requests (
  id uuid primary key default gen_random_uuid(),
  raw_idea text,
  target_audience text not null,
  supporting_material jsonb,
  status request_status not null default 'intake',
  submitted_by_user_id uuid not null references users(id),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

-- §3.1a intake_attachments
create table intake_attachments (
  id uuid primary key default gen_random_uuid(),
  content_request_id uuid not null references content_requests(id) on delete cascade,
  type attachment_type not null,
  url text,
  storage_path text,
  description text,
  created_at timestamptz not null default now(),
  constraint intake_attachments_shape check (
    (type = 'url' and url is not null) or (type != 'url' and storage_path is not null)
  )
);

-- §3.2 sources
create table sources (
  id uuid primary key default gen_random_uuid(),
  content_request_id uuid not null references content_requests(id) on delete cascade,
  intake_attachment_id uuid references intake_attachments(id),
  url text not null,
  title text,
  raw_content text,
  excerpt_selected text,
  relevance_notes text,
  retrieval_method source_retrieval_method not null,
  status source_status not null default 'retrieved',
  retrieved_at timestamptz,
  created_at timestamptz not null default now()
);

-- §3.3 content_plans
create table content_plans (
  id uuid primary key default gen_random_uuid(),
  content_request_id uuid not null references content_requests(id) on delete cascade,
  outline jsonb not null,
  target_keywords text[] not null default '{}',
  created_at timestamptz not null default now()
);

-- §3.4 article_drafts
create table article_drafts (
  id uuid primary key default gen_random_uuid(),
  content_request_id uuid not null references content_requests(id) on delete cascade,
  content_plan_id uuid references content_plans(id),
  option_label text not null,
  version int not null default 1,
  parent_draft_id uuid references article_drafts(id),
  title text not null,
  body_markdown text not null,
  source_ids_used uuid[] not null default '{}',
  status draft_status not null default 'draft',
  created_at timestamptz not null default now(),
  constraint article_drafts_version_unique unique (content_request_id, option_label, version)
);

-- §3.5 evaluations
create table evaluations (
  id uuid primary key default gen_random_uuid(),
  article_draft_id uuid not null references article_drafts(id) on delete cascade,
  rubric_scores jsonb not null,
  overall_score numeric not null,
  passed_threshold boolean not null,
  feedback text not null,
  revision_instructions text,
  evaluated_by evaluated_by not null default 'ai',
  created_at timestamptz not null default now()
);

-- §3.6 human_reviews
create table human_reviews (
  id uuid primary key default gen_random_uuid(),
  content_request_id uuid not null references content_requests(id) on delete cascade,
  article_draft_id uuid not null references article_drafts(id),
  reviewer_user_id uuid not null references users(id),
  decision review_decision not null,
  notes text,
  created_at timestamptz not null default now()
);

-- §3.7 channel_adaptations
create table channel_adaptations (
  id uuid primary key default gen_random_uuid(),
  content_request_id uuid not null references content_requests(id) on delete cascade,
  article_draft_id uuid not null references article_drafts(id),
  channel channel not null,
  content text not null,
  content_format content_format not null,
  formatting_check jsonb,
  status adaptation_status not null default 'draft',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint channel_adaptations_unique unique (article_draft_id, channel)
);

-- §3.8 publishing_queue
create table publishing_queue (
  id uuid primary key default gen_random_uuid(),
  channel_adaptation_id uuid not null references channel_adaptations(id) on delete cascade,
  scheduled_for timestamptz,
  status queue_status not null default 'queued',
  attempts int not null default 0,
  max_attempts int not null default 3,
  last_error text,
  next_attempt_at timestamptz,
  published_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

-- §3.9 jobs
create table jobs (
  id uuid primary key default gen_random_uuid(),
  job_type job_type not null,
  reference_type job_reference_type not null,
  reference_id uuid not null,
  status job_status not null default 'pending',
  attempts int not null default 0,
  max_attempts int not null default 3,
  payload jsonb not null default '{}',
  last_error text,
  next_attempt_at timestamptz not null default now(),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

-- §3.10 stage_events
create table stage_events (
  id uuid primary key default gen_random_uuid(),
  content_request_id uuid not null references content_requests(id) on delete cascade,
  stage pipeline_stage not null,
  status stage_event_status not null,
  detail jsonb,
  error_message text,
  created_at timestamptz not null default now()
);
"""

INDEXES_SQL = """
create index on sources (content_request_id);
create index on article_drafts (content_request_id, option_label, version);
create index on evaluations (article_draft_id);
create index on channel_adaptations (content_request_id);
create index on publishing_queue (status, next_attempt_at);
create index on jobs (status, next_attempt_at);
create index on stage_events (content_request_id, created_at);
create index on login_attempts (user_id, created_at);
create index on access_rules (type, value);
"""


def upgrade() -> None:
    op.execute(ENUMS_SQL)
    op.execute(TABLES_SQL)
    op.execute(INDEXES_SQL)


def downgrade() -> None:
    op.execute("""
        drop table if exists stage_events;
        drop table if exists jobs;
        drop table if exists publishing_queue;
        drop table if exists channel_adaptations;
        drop table if exists human_reviews;
        drop table if exists evaluations;
        drop table if exists article_drafts;
        drop table if exists content_plans;
        drop table if exists sources;
        drop table if exists intake_attachments;
        drop table if exists content_requests;
        drop table if exists sessions;
        drop table if exists login_attempts;
        drop table if exists users;
        drop table if exists access_rules;

        drop type if exists access_rule_type;
        drop type if exists stage_event_status;
        drop type if exists pipeline_stage;
        drop type if exists job_status;
        drop type if exists job_reference_type;
        drop type if exists job_type;
        drop type if exists queue_status;
        drop type if exists adaptation_status;
        drop type if exists content_format;
        drop type if exists channel;
        drop type if exists review_decision;
        drop type if exists evaluated_by;
        drop type if exists draft_status;
        drop type if exists source_status;
        drop type if exists source_retrieval_method;
        drop type if exists attachment_type;
        drop type if exists request_status;
    """)
