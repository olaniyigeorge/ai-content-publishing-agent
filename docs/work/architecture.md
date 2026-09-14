# Koya Talent — AI Content Research & Publishing Agent
## architecture.md

This document is built incrementally. This pass covers the **Supabase schema** — the backbone every other layer (FastAPI orchestrator, jobs worker, Claude service, Next.js UI) reads and writes against. Route/service layout and the Claude service design come next.

---

## 1. Design principles behind the schema

These map directly back to the architecture review:

1. **No Celery.** A single `jobs` table is the async execution primitive. A polling worker claims pending jobs, executes them, and writes retries/backoff/failure state back to the row. This is what replaces the broker + worker + beat scheduler stack.
2. **Revision history is structural, not incidental.** `article_drafts` is append-only and versioned via `parent_draft_id` — nothing is overwritten. Test scenario 4 ("preserve review history") is a schema requirement, not a UI nicety.
3. **Failure visibility is structural.** `stage_events` is an append-only log every stage writes to on both success and failure. Test scenario 8 depends on this table existing, not on app logs someone has to grep.
4. **Publishing is a queue by default, not a live integration.** `publishing_queue` + `PublishingAdapter` (mock adapter for v1) satisfies test scenario 7's explicit "or saved into a clear publishing queue" clause without betting the timeline on LinkedIn/X API approval.
5. **Source traceability is a first-class relationship, not a text blob.** `article_drafts.source_ids_used` and `sources` are linked so "which sources informed the output" (required by the PRD) is a query, not something you reconstruct by re-reading the article.
6. **No pgvector in v1.** Sources are scoped to one content request at a time; Claude selects/ranks excerpts directly from retrieved text. Add `embedding vector` to `sources` later only if you need cross-request retrieval.

---

## 2. Enum types

```sql
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

-- 'dead_letter' is distinct from a transient failure: it means attempts >= max_attempts
-- and the worker has given up. Kept separate from 'failed' deliberately — see §5.
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
```

---

## 3. Tables

### 3.1 `content_requests` — intake

The root object. Everything else hangs off `content_request_id`.

| Column | Type | Notes |
|---|---|---|
| `id` | uuid pk | `default gen_random_uuid()` |
| `raw_idea` | text | nullable — required if at least one `intake_attachments` row doesn't exist either (see below) |
| `target_audience` | text | required per PRD minimum inputs |
| `supporting_material` | jsonb | free-form notes only now — not URLs/media, those moved out (see below) |
| `status` | `request_status` | current pipeline position — denormalized for fast list views; source of truth for history is `stage_events` |
| `submitted_by` | text | content manager identifier; no auth system assumed for MVP, plain string is fine |
| `created_at` | timestamptz | `default now()` |
| `updated_at` | timestamptz | bump on every status change |

**Fix vs. the earlier draft:** the original had a single nullable `source_url text` column, which can't hold multiple URLs or any image/file. That's wrong given the PRD allows "any supporting material" (plural, and not necessarily a URL). Fixed by pulling this into its own table below. `content_requests` no longer stores URLs directly.

The "at minimum a raw idea or supporting material" rule can't be a single-table `check` anymore since it now spans two tables — enforce it in the intake API handler (reject if `raw_idea` is null and zero `intake_attachments` rows were submitted), and optionally back it with a `before insert` trigger on `intake_attachments`/`content_requests` if you want DB-level enforcement. For MVP scope, app-level validation is enough — a trigger here is complexity you don't need to defend in a review.

### 3.1a `intake_attachments` — multiple URLs and/or media at submission time

One request can now carry several source URLs, an uploaded image, or a mix. This table is what the content manager *submitted*; `sources` (below) is what research *retrieved* — keep those separate, they answer different questions.

| Column | Type | Notes |
|---|---|---|
| `id` | uuid pk | |
| `content_request_id` | uuid fk | `on delete cascade` |
| `type` | `attachment_type` | `url` \| `image` \| `file` |
| `url` | text | nullable — set when `type = 'url'` |
| `storage_path` | text | nullable — Supabase Storage path, set when `type = 'image'` or `'file'` |
| `description` | text | nullable — content manager's note on why this attachment matters, e.g. "use the stat in this chart" |
| `created_at` | timestamptz | |

`check ((type = 'url' and url is not null) or (type != 'url' and storage_path is not null))` — a URL attachment must have a URL, a media attachment must have a storage path.

Images aren't scraped like URLs — they're either passed to Claude as vision input during research/planning (e.g., "here's a chart the content manager wants referenced") or just kept as context for the human reviewer. `sources.intake_attachment_id` (added below) traces a scraped source back to the URL attachment that produced it.

### 3.2 `sources` — research / evidence

| Column | Type | Notes |
|---|---|---|
| `id` | uuid pk | |
| `content_request_id` | uuid fk → `content_requests.id` | `on delete cascade` |
| `intake_attachment_id` | uuid fk → `intake_attachments.id` | nullable — set when this source came from a submitted URL, null when found via `web_search` |
| `url` | text | |
| `title` | text | nullable, from scrape metadata |
| `raw_content` | text | full scraped/retrieved text |
| `excerpt_selected` | text | nullable — the excerpt Claude judged relevant, set during content planning |
| `relevance_notes` | text | nullable — Claude's stated reason this source/excerpt matters; this is what powers "make it clear which sources informed the output" |
| `retrieval_method` | `source_retrieval_method` | |
| `status` | `source_status` | `retrieved` → `selected`/`discarded` after the planning step |
| `retrieved_at` | timestamptz | |
| `created_at` | timestamptz | |

### 3.3 `content_plans`

One plan per request (regenerate-in-place is fine here — plans aren't the thing test scenario 4 asks you to preserve history for, drafts are).

| Column | Type | Notes |
|---|---|---|
| `id` | uuid pk | |
| `content_request_id` | uuid fk | `on delete cascade` |
| `outline` | jsonb | structured: sections, key points, which `source_id`s map to which section |
| `target_keywords` | text[] | SEO best-practices input |
| `created_at` | timestamptz | |

### 3.4 `article_drafts` — versioned, the revision-loop backbone

This is the table that makes test scenario 4 real. "Article options" (plural, per PRD) are distinct `option_label` lineages; each lineage can have multiple `version`s as it's revised.

| Column | Type | Notes |
|---|---|---|
| `id` | uuid pk | |
| `content_request_id` | uuid fk | `on delete cascade` |
| `content_plan_id` | uuid fk | nullable |
| `option_label` | text | e.g. `"A"`, `"B"` — distinguishes parallel article options |
| `version` | int | starts at 1, increments per revision within an `option_label` lineage |
| `parent_draft_id` | uuid fk → `article_drafts.id` | nullable, self-referencing — null for v1 of an option, points to the prior version otherwise |
| `title` | text | |
| `body_markdown` | text | |
| `source_ids_used` | uuid[] | array of `sources.id` — traceability |
| `status` | `draft_status` | |
| `created_at` | timestamptz | |

`unique (content_request_id, option_label, version)` — prevents accidental duplicate versions.

### 3.5 `evaluations`

One row per evaluation pass against a specific draft version.

| Column | Type | Notes |
|---|---|---|
| `id` | uuid pk | |
| `article_draft_id` | uuid fk | `on delete cascade` |
| `rubric_scores` | jsonb | per-criterion scores, keyed to `content-evaluation-rubric.md` |
| `overall_score` | numeric | |
| `passed_threshold` | boolean | drives whether a revision job is enqueued |
| `feedback` | text | Claude's evaluation notes |
| `revision_instructions` | text | nullable — fed as input when generating the next draft version |
| `evaluated_by` | `evaluated_by` | `ai` by default; supports a human override path later without a schema change |
| `created_at` | timestamptz | |

### 3.6 `human_reviews` — the approval gate

Test scenario 5: nothing downstream of this table should be reachable without a row here.

| Column | Type | Notes |
|---|---|---|
| `id` | uuid pk | |
| `content_request_id` | uuid fk | |
| `article_draft_id` | uuid fk | the option/version being decided on |
| `reviewer` | text | |
| `decision` | `review_decision` | |
| `notes` | text | nullable |
| `created_at` | timestamptz | |

### 3.7 `channel_adaptations`

| Column | Type | Notes |
|---|---|---|
| `id` | uuid pk | |
| `content_request_id` | uuid fk | |
| `article_draft_id` | uuid fk | the approved draft this was adapted from |
| `channel` | `channel` | `linkedin` \| `x` \| `newsletter` |
| `content` | text | final channel-ready copy — **not** markdown, see note below |
| `content_format` | `content_format` | `plain_text` for `linkedin`/`x`, `html` for `newsletter` |
| `formatting_check` | jsonb | nullable — validated against `channel-formatting-rules.md` (char counts, hashtag rules, etc.) |
| `status` | `adaptation_status` | |
| `created_at` | timestamptz | |
| `updated_at` | timestamptz | |

`unique (article_draft_id, channel)` — one adaptation per channel per approved draft.

**On the markdown question:** `article_drafts.body_markdown` stays markdown — that's the canonical long-form SEO article, meant for a blog/CMS that renders markdown/HTML, so markdown is the right format there. It does *not* carry through to `channel_adaptations.content` unchanged. LinkedIn and X don't render markdown syntax at all — `**bold**` shows up as literal asterisks — so the adaptation step for those two channels must strip markdown and produce plain text (`content_format = 'plain_text'`). Newsletter is the opposite problem: most email clients need HTML, not raw markdown, so that adaptation step should render to `content_format = 'html'`. Practically: the adaptation Claude call takes `body_markdown` as input but is instructed to *emit* the channel-appropriate format directly, not markdown-with-instructions-to-convert-later.

### 3.8 `publishing_queue` — the business-level queue (PRD-required, UI-facing)

| Column | Type | Notes |
|---|---|---|
| `id` | uuid pk | |
| `channel_adaptation_id` | uuid fk | `on delete cascade` |
| `scheduled_for` | timestamptz | nullable — null means "publish as soon as processed" |
| `status` | `queue_status` | |
| `attempts` | int | `default 0` |
| `max_attempts` | int | `default 3` |
| `last_error` | text | nullable |
| `next_attempt_at` | timestamptz | polled by the worker; backoff written here on failure |
| `published_at` | timestamptz | nullable |
| `created_at` | timestamptz | |
| `updated_at` | timestamptz | |

This is what your UI queries directly to show "the publishing queue" — it's a domain object, separate from the generic `jobs` mechanism below, even though a `jobs` row is what actually drives its state transitions.

### 3.9 `jobs` — generic async execution (replaces Celery)

Polymorphic reference so one table drives every async step: research, plan, generate, evaluate, adapt, publish.

| Column | Type | Notes |
|---|---|---|
| `id` | uuid pk | |
| `job_type` | `job_type` | |
| `reference_type` | `job_reference_type` | what `reference_id` points to |
| `reference_id` | uuid | not a real FK (polymorphic) — validate in app code |
| `status` | `job_status` | |
| `attempts` | int | `default 0` |
| `max_attempts` | int | `default 3` |
| `payload` | jsonb | job-specific input |
| `last_error` | text | nullable |
| `next_attempt_at` | timestamptz | worker polls `where status = 'pending' and next_attempt_at <= now()` |
| `created_at` | timestamptz | |
| `updated_at` | timestamptz | |

### 3.10 `stage_events` — append-only pipeline audit log

Every stage writes here on `started`, `succeeded`, and `failed`. This table alone should be enough to answer "what happened to request X" for the Loom video and for test scenario 8.

| Column | Type | Notes |
|---|---|---|
| `id` | uuid pk | |
| `content_request_id` | uuid fk | `on delete cascade` |
| `stage` | `pipeline_stage` | |
| `status` | `stage_event_status` | |
| `detail` | jsonb | nullable — e.g. `{"draft_id": ..., "version": 2}` or `{"source_url": ...}` |
| `error_message` | text | nullable |
| `created_at` | timestamptz | append-only, no updates |

---

## 4. Indexes worth adding up front

```sql
create index on sources (content_request_id);
create index on article_drafts (content_request_id, option_label, version);
create index on evaluations (article_draft_id);
create index on channel_adaptations (content_request_id);
create index on publishing_queue (status, next_attempt_at);
create index on jobs (status, next_attempt_at);
create index on stage_events (content_request_id, created_at);
```

The two `(status, next_attempt_at)` indexes are the ones that matter functionally — they're what the polling worker's claim query hits every cycle.

---

## 5. Retry / dead-letter logic (the Celery/BullMQ equivalent)

This is the part that replaces "just write it to a dead-letter queue" — worked out explicitly since there's no broker doing it for you.

**On every attempt (worker pseudocode, applies to both `jobs` and `publishing_queue`):**

```
row = claim next row where status in ('queued'|'pending') and next_attempt_at <= now()
set status = 'processing', attempts += 1

try:
    execute(row)
    set status = 'published' (queue) / 'succeeded' (jobs), published_at/updated_at = now()
except Exception as err:
    if row.attempts >= row.max_attempts:
        set status = 'dead_letter' (queue) / 'failed' (jobs)
        set last_error = str(err), next_attempt_at = null
    else:
        set status = 'queued' (queue) / 'pending' (jobs)   -- eligible for retry
        set last_error = str(err)
        set next_attempt_at = now() + backoff(row.attempts)  -- e.g. 2^attempts minutes
```

Why `publishing_queue` gets an explicit `dead_letter` status but `jobs` reuses `failed`: `publishing_queue` is the table your UI queries directly — a content manager or you, in the demo, needs to see at a glance "this is permanently stuck, someone has to look at it" vs. "this is mid-retry." `jobs` is an internal execution log nobody but you is reading, so collapsing "exhausted retries" into `failed` (distinguishable from a will-retry state because that state is `pending`, not a separate status) is fine there — one less enum to keep in sync across two tables that don't actually need to agree with each other.

**Backoff**: exponential is enough — `next_attempt_at = now() + interval '1 minute' * power(2, attempts)`. Don't build configurable backoff strategies; it's one line.

**max_attempts = 3** as a sane default for both tables — matches what you'd get for free from Celery's default retry policy, no need to tune it further for an MVP.

---

## 6. What's deliberately not here yet

- **Auth/RLS** — no user table, no row-level security. Fine for an internal-tool MVP with a single `submitted_by` string; flag as a known gap in the one-pager rather than building it speculatively.
- **`embedding vector` columns** — omitted per the earlier call to skip pgvector for v1.
- **Real publishing credentials/tokens table** — not needed while `publishing_queue` is served by a mock adapter. Add a `platform_credentials` table only when/if you wire in a real `LinkedInAdapter`.

---

---

## 7. Example data — one request traced through every table

Same `content_request_id` throughout, so you can follow it end to end. This is the request: a content manager submits an idea plus two source URLs and one chart image, it goes through two draft revisions, gets approved, and gets adapted to three channels — one of which fails publishing until it hits the dead letter state.

### `content_requests`

```json
{
  "id": "c1000000-0000-0000-0000-000000000001",
  "raw_idea": "5 productivity tips for remote SaaS teams, backed by recent research",
  "target_audience": "B2B SaaS marketing managers, mid-career, US-based",
  "supporting_material": { "notes": "Tie in the Gartner hybrid-work stat if possible" },
  "status": "queued",
  "submitted_by": "amaka@koyatalent.com",
  "created_at": "2026-09-10T09:02:11Z",
  "updated_at": "2026-09-10T10:15:12Z"
}
```

### `intake_attachments`

```json
[
  {
    "id": "a1000000-0000-0000-0000-000000000001",
    "content_request_id": "c1000000-0000-0000-0000-000000000001",
    "type": "url",
    "url": "https://hbr.org/2026/06/remote-team-productivity-study",
    "storage_path": null,
    "description": null,
    "created_at": "2026-09-10T09:02:11Z"
  },
  {
    "id": "a1000000-0000-0000-0000-000000000002",
    "content_request_id": "c1000000-0000-0000-0000-000000000001",
    "type": "url",
    "url": "https://gartner.com/reports/hybrid-work-2026",
    "storage_path": null,
    "description": null,
    "created_at": "2026-09-10T09:02:11Z"
  },
  {
    "id": "a1000000-0000-0000-0000-000000000003",
    "content_request_id": "c1000000-0000-0000-0000-000000000001",
    "type": "image",
    "url": null,
    "storage_path": "intake-media/c1000000.../chart.png",
    "description": "Screenshot of Gartner hybrid-work adoption chart — content manager wants this stat referenced",
    "created_at": "2026-09-10T09:02:15Z"
  }
]
```

### `sources`

```json
[
  {
    "id": "s1000000-0000-0000-0000-000000000001",
    "content_request_id": "c1000000-0000-0000-0000-000000000001",
    "intake_attachment_id": "a1000000-0000-0000-0000-000000000001",
    "url": "https://hbr.org/2026/06/remote-team-productivity-study",
    "title": "The Remote Team Productivity Study",
    "raw_content": "<full scraped article text>",
    "excerpt_selected": "Teams with structured async check-ins reported 23% higher self-rated productivity.",
    "relevance_notes": "Primary statistic for the article's core claim about async check-ins.",
    "retrieval_method": "url_provided",
    "status": "selected",
    "retrieved_at": "2026-09-10T09:05:02Z",
    "created_at": "2026-09-10T09:05:02Z"
  },
  {
    "id": "s1000000-0000-0000-0000-000000000002",
    "content_request_id": "c1000000-0000-0000-0000-000000000001",
    "intake_attachment_id": "a1000000-0000-0000-0000-000000000002",
    "url": "https://gartner.com/reports/hybrid-work-2026",
    "title": "Hybrid Work Adoption 2026",
    "raw_content": "<full scraped report text>",
    "excerpt_selected": "68% of B2B SaaS companies adopted a hybrid-first policy as of Q2 2026.",
    "relevance_notes": "Supports audience-relevance framing — the request is specifically about SaaS teams.",
    "retrieval_method": "url_provided",
    "status": "selected",
    "retrieved_at": "2026-09-10T09:05:40Z",
    "created_at": "2026-09-10T09:05:40Z"
  }
]
```

### `content_plans`

```json
{
  "id": "p1000000-0000-0000-0000-000000000001",
  "content_request_id": "c1000000-0000-0000-0000-000000000001",
  "outline": {
    "sections": [
      { "heading": "Why remote productivity is a SaaS-specific problem", "source_ids": ["s1000000-0000-0000-0000-000000000002"] },
      { "heading": "Tip 1: Structured async check-ins", "source_ids": ["s1000000-0000-0000-0000-000000000001"] }
    ]
  },
  "target_keywords": ["remote team productivity", "hybrid work SaaS", "async check-ins"],
  "created_at": "2026-09-10T09:07:00Z"
}
```

### `article_drafts` — two versions of option A, showing the revision lineage

```json
[
  {
    "id": "d1000000-0000-0000-0000-000000000001",
    "content_request_id": "c1000000-0000-0000-0000-000000000001",
    "content_plan_id": "p1000000-0000-0000-0000-000000000001",
    "option_label": "A",
    "version": 1,
    "parent_draft_id": null,
    "title": "5 Productivity Tips for Remote SaaS Teams, Backed by 2026 Research",
    "body_markdown": "## Why remote productivity is a SaaS-specific problem\n\n...",
    "source_ids_used": ["s1000000-0000-0000-0000-000000000001", "s1000000-0000-0000-0000-000000000002"],
    "status": "evaluated",
    "created_at": "2026-09-10T09:12:00Z"
  },
  {
    "id": "d1000000-0000-0000-0000-000000000002",
    "content_request_id": "c1000000-0000-0000-0000-000000000001",
    "content_plan_id": "p1000000-0000-0000-0000-000000000001",
    "option_label": "A",
    "version": 2,
    "parent_draft_id": "d1000000-0000-0000-0000-000000000001",
    "title": "5 Productivity Tips for Remote SaaS Teams, Backed by 2026 Research",
    "body_markdown": "## Why remote productivity is a SaaS-specific problem\n\n<tighter, stat-led rewrite>...",
    "source_ids_used": ["s1000000-0000-0000-0000-000000000001", "s1000000-0000-0000-0000-000000000002"],
    "status": "selected",
    "created_at": "2026-09-10T09:19:00Z"
  }
]
```

### `evaluations` — one per draft version, the second one clears the bar

```json
[
  {
    "id": "e1000000-0000-0000-0000-000000000001",
    "article_draft_id": "d1000000-0000-0000-0000-000000000001",
    "rubric_scores": { "accuracy": 4, "clarity": 3, "seo": 4, "tone_fit": 3 },
    "overall_score": 3.5,
    "passed_threshold": false,
    "feedback": "Intro is generic and doesn't lead with the Gartner stat; tone slightly too casual for the audience.",
    "revision_instructions": "Open with the 68% hybrid-adoption stat; tighten tone to match B2B SaaS marketing manager audience.",
    "evaluated_by": "ai",
    "created_at": "2026-09-10T09:15:00Z"
  },
  {
    "id": "e1000000-0000-0000-0000-000000000002",
    "article_draft_id": "d1000000-0000-0000-0000-000000000002",
    "rubric_scores": { "accuracy": 4, "clarity": 5, "seo": 4, "tone_fit": 5 },
    "overall_score": 4.5,
    "passed_threshold": true,
    "feedback": "Strong open, tone matches audience, every claim traces to a source.",
    "revision_instructions": null,
    "evaluated_by": "ai",
    "created_at": "2026-09-10T09:20:00Z"
  }
]
```

### `human_reviews`

`decision` uses the `review_decision` enum: `approved` (ready to publish as-is) · `rejected` (kill the request/draft) · `revise_requested` (send back into the revision loop, `notes` becomes extra revision instructions) · `option_selected` (when multiple parallel options like A/B were generated, records which lineage the human picked — doesn't imply approval by itself, that option can still go through more revisions).

```json
{
  "id": "h1000000-0000-0000-0000-000000000001",
  "content_request_id": "c1000000-0000-0000-0000-000000000001",
  "article_draft_id": "d1000000-0000-0000-0000-000000000002",
  "reviewer": "amaka@koyatalent.com",
  "decision": "approved",
  "notes": "Good to go, ship as-is.",
  "created_at": "2026-09-10T09:25:00Z"
}
```

### `channel_adaptations` — three channels, two formats

```json
[
  {
    "id": "ch1000000-0000-0000-0000-000000000001",
    "content_request_id": "c1000000-0000-0000-0000-000000000001",
    "article_draft_id": "d1000000-0000-0000-0000-000000000002",
    "channel": "linkedin",
    "content": "Remote SaaS teams are 23% more productive with one simple change: structured async check-ins. Here's what 2026 research says actually works.",
    "content_format": "plain_text",
    "formatting_check": { "char_count": 267, "within_limit": true, "hashtags": 3 },
    "status": "approved",
    "created_at": "2026-09-10T09:27:00Z",
    "updated_at": "2026-09-10T09:27:00Z"
  },
  {
    "id": "ch1000000-0000-0000-0000-000000000002",
    "content_request_id": "c1000000-0000-0000-0000-000000000001",
    "article_draft_id": "d1000000-0000-0000-0000-000000000002",
    "channel": "x",
    "content": "68% of B2B SaaS companies went hybrid-first in 2026. The teams that stayed productive did one thing differently: async check-ins.",
    "content_format": "plain_text",
    "formatting_check": { "char_count": 141, "within_limit": true },
    "status": "approved",
    "created_at": "2026-09-10T09:27:30Z",
    "updated_at": "2026-09-10T09:27:30Z"
  },
  {
    "id": "ch1000000-0000-0000-0000-000000000003",
    "content_request_id": "c1000000-0000-0000-0000-000000000001",
    "article_draft_id": "d1000000-0000-0000-0000-000000000002",
    "channel": "newsletter",
    "content": "<h2>5 Productivity Tips for Remote SaaS Teams</h2><p>New 2026 research shows...</p>",
    "content_format": "html",
    "formatting_check": { "subject_line_length": 42, "within_limit": true },
    "status": "approved",
    "created_at": "2026-09-10T09:28:00Z",
    "updated_at": "2026-09-10T09:28:00Z"
  }
]
```

### `publishing_queue` — one published, one still scheduled, one dead-lettered

```json
[
  {
    "id": "q1000000-0000-0000-0000-000000000001",
    "channel_adaptation_id": "ch1000000-0000-0000-0000-000000000001",
    "scheduled_for": null,
    "status": "published",
    "attempts": 1,
    "max_attempts": 3,
    "last_error": null,
    "next_attempt_at": null,
    "published_at": "2026-09-10T09:30:05Z",
    "created_at": "2026-09-10T09:28:30Z",
    "updated_at": "2026-09-10T09:30:05Z"
  },
  {
    "id": "q1000000-0000-0000-0000-000000000002",
    "channel_adaptation_id": "ch1000000-0000-0000-0000-000000000002",
    "scheduled_for": "2026-09-11T14:00:00Z",
    "status": "queued",
    "attempts": 0,
    "max_attempts": 3,
    "last_error": null,
    "next_attempt_at": "2026-09-11T14:00:00Z",
    "published_at": null,
    "created_at": "2026-09-10T09:28:35Z",
    "updated_at": "2026-09-10T09:28:35Z"
  },
  {
    "id": "q1000000-0000-0000-0000-000000000003",
    "channel_adaptation_id": "ch1000000-0000-0000-0000-000000000003",
    "scheduled_for": null,
    "status": "dead_letter",
    "attempts": 3,
    "max_attempts": 3,
    "last_error": "Mailgun API 502: upstream timeout",
    "next_attempt_at": null,
    "published_at": null,
    "created_at": "2026-09-10T09:28:40Z",
    "updated_at": "2026-09-10T10:15:12Z"
  }
]
```

### `jobs` — the generic worker's-eye view, two of the six `job_type`s shown

The six `job_type`s map 1:1 to every async step in the pipeline: `research` (retrieve + scrape), `plan` (build the outline), `generate` (produce/revise a draft), `evaluate` (score a draft against the rubric), `adapt` (produce the three channel versions), `publish` (send/schedule one `channel_adaptation`). `publish` is its own type rather than folded into `adapt` because it's the one step that talks to an external system and needs independent retry/backoff — an adaptation succeeding and a publish attempt failing are different failure domains and you don't want a publish retry to re-run the Claude adaptation call.

```json
[
  {
    "id": "j1000000-0000-0000-0000-000000000001",
    "job_type": "research",
    "reference_type": "content_request",
    "reference_id": "c1000000-0000-0000-0000-000000000001",
    "status": "succeeded",
    "attempts": 1,
    "max_attempts": 3,
    "payload": { "attachment_ids": ["a1000000-0000-0000-0000-000000000001", "a1000000-0000-0000-0000-000000000002"] },
    "last_error": null,
    "next_attempt_at": null,
    "created_at": "2026-09-10T09:02:20Z",
    "updated_at": "2026-09-10T09:06:00Z"
  },
  {
    "id": "j1000000-0000-0000-0000-000000000002",
    "job_type": "publish",
    "reference_type": "publishing_queue",
    "reference_id": "q1000000-0000-0000-0000-000000000003",
    "status": "failed",
    "attempts": 3,
    "max_attempts": 3,
    "payload": { "channel_adaptation_id": "ch1000000-0000-0000-0000-000000000003" },
    "last_error": "Mailgun API 502: upstream timeout",
    "next_attempt_at": null,
    "created_at": "2026-09-10T09:28:41Z",
    "updated_at": "2026-09-10T10:15:12Z"
  }
]
```

### `stage_events` — the full audit trail for this request, including the one failure

```json
[
  { "id": "se...0001", "content_request_id": "c1000000-0000-0000-0000-000000000001", "stage": "intake", "status": "succeeded", "detail": { "attachments": 3 }, "error_message": null, "created_at": "2026-09-10T09:02:11Z" },
  { "id": "se...0002", "content_request_id": "c1000000-0000-0000-0000-000000000001", "stage": "research", "status": "started", "detail": null, "error_message": null, "created_at": "2026-09-10T09:02:20Z" },
  { "id": "se...0003", "content_request_id": "c1000000-0000-0000-0000-000000000001", "stage": "research", "status": "succeeded", "detail": { "sources_retrieved": 2 }, "error_message": null, "created_at": "2026-09-10T09:06:00Z" },
  { "id": "se...0004", "content_request_id": "c1000000-0000-0000-0000-000000000001", "stage": "generation", "status": "succeeded", "detail": { "draft_id": "d1000000-0000-0000-0000-000000000001", "version": 1 }, "error_message": null, "created_at": "2026-09-10T09:12:00Z" },
  { "id": "se...0005", "content_request_id": "c1000000-0000-0000-0000-000000000001", "stage": "evaluation", "status": "succeeded", "detail": { "draft_id": "d1000000-0000-0000-0000-000000000001", "passed_threshold": false }, "error_message": null, "created_at": "2026-09-10T09:15:00Z" },
  { "id": "se...0006", "content_request_id": "c1000000-0000-0000-0000-000000000001", "stage": "revision", "status": "succeeded", "detail": { "draft_id": "d1000000-0000-0000-0000-000000000002", "version": 2 }, "error_message": null, "created_at": "2026-09-10T09:19:00Z" },
  { "id": "se...0007", "content_request_id": "c1000000-0000-0000-0000-000000000001", "stage": "human_review", "status": "succeeded", "detail": { "decision": "approved" }, "error_message": null, "created_at": "2026-09-10T09:25:00Z" },
  { "id": "se...0008", "content_request_id": "c1000000-0000-0000-0000-000000000001", "stage": "publishing", "status": "failed", "detail": { "channel_adaptation_id": "ch1000000-0000-0000-0000-000000000003", "attempt": 3 }, "error_message": "Mailgun API 502: upstream timeout", "created_at": "2026-09-10T10:15:12Z" }
]
```

This is exactly what your Loom video should walk through: pull `stage_events` for one `content_request_id` and narrate it top to bottom — it's a complete, ordered story of the pipeline including the one deliberate failure, with zero need to grep application logs.

---

*Next section: FastAPI route/service module layout and the Claude service's domain + model-router design.*