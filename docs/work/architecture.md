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

create type access_rule_type as enum ('email', 'domain');
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
| `submitted_by_user_id` | uuid fk → `users.id` | see §6 — was a free-text string, now a real FK now that auth exists |
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
| `reviewer_user_id` | uuid fk → `users.id` | see §6 — was free text, now a real FK |
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

## 6. Minimal auth — allowlisted email + OTP

"Production ready" doesn't mean "build an auth platform" here — it means don't ship something a security review would flag in five minutes. The shape you brought (allowlist decoupled from authentication, OTP as proof of email ownership, opaque server-side sessions instead of JWTs) is the right call for this system: single backend, short-lived sessions, no third-party services consuming tokens. I'd keep it essentially as designed, with three refinements and one architecture decision to make explicit.

**Refinements to the design as given:**

1. **Don't make the allowlist check observably distinguishable.** The flow as sketched has a visible fork — `Allowed` → generate code, `Not allowed` → reject — and if those two paths return different responses (or even just different response times), an attacker can enumerate your allowlist by trying emails. `POST /auth/request-code` should return the same generic `200 { "message": "if this email is eligible, a code has been sent" }` on both paths. Do the real branching silently server-side; log the rejection, don't surface it.
2. **Rate limiting doesn't need Redis.** The design doc mentions rate-limiting by IP + email as a bullet without saying how — given the "no Celery/Redis" stance already set for this project, do it off the `login_attempts` table itself: reject a new code request if N rows for that email (or IP, logged alongside) were created in the trailing window. One query, no new infra.
3. **Explicit OTP consumption.** Add `consumed_at` to the attempts table and check it on verify — "invalidate after use" needs a field to invalidate, otherwise a still-unexpired code stays valid for replay within its 10-minute window even after a successful login.

**Architecture decision worth flagging:** this is a fully custom, DB-level session system, independent of Supabase Auth. Supabase Row-Level-Security policies key off `auth.uid()` from Supabase's own JWTs — they don't see these custom `sessions` rows at all. Given the existing design (Next.js never talks to Supabase directly, FastAPI is the only thing holding the service-role key), that's fine: access control lives entirely in a FastAPI dependency that looks up the session cookie on every protected route, not at the database layer. This only breaks if the frontend ever needs to query Supabase directly (e.g. realtime subscriptions) — confirm that's not planned, because if it is, you'd need to either bridge this session into something RLS can evaluate, or restrict direct reads to fields that are safe for any allowlisted user to see regardless of role.

### 6.1 `access_rules`

| Column | Type | Notes |
|---|---|---|
| `id` | uuid pk | |
| `type` | `access_rule_type` | `email` \| `domain` |
| `value` | text | normalized lowercase — full email for `email`, bare domain (no `@`) for `domain` |
| `enabled` | boolean | `default true` |
| `created_at` | timestamptz | |
| `expires_at` | timestamptz | nullable — e.g. time-box an external reviewer's access |

### 6.2 `users`

| Column | Type | Notes |
|---|---|---|
| `id` | uuid pk | |
| `email` | text | `unique`, normalized lowercase |
| `created_at` | timestamptz | |
| `last_login_at` | timestamptz | nullable |

Upserted the moment an email clears the allowlist check at request-code time — not deferred until first successful verification — so `content_requests.submitted_by_user_id` and `human_reviews.reviewer_user_id` always have a valid row to point at once any session exists.

### 6.3 `login_attempts`

| Column | Type | Notes |
|---|---|---|
| `id` | uuid pk | |
| `user_id` | uuid fk → `users.id` | |
| `code_hash` | text | never store the raw code |
| `expires_at` | timestamptz | ~10 minutes out |
| `attempts` | int | `default 0` |
| `max_attempts` | int | `default 5` |
| `consumed_at` | timestamptz | nullable — set on successful verification; a consumed row can't be verified again even if still unexpired |
| `created_at` | timestamptz | |

### 6.4 `sessions`

| Column | Type | Notes |
|---|---|---|
| `id` | uuid pk | `default gen_random_uuid()` — this is the opaque token itself, given directly to the browser as an HttpOnly/Secure/SameSite cookie; 122 bits of entropy is not guessable, no need to hash it server-side for an MVP |
| `user_id` | uuid fk → `users.id` | |
| `expires_at` | timestamptz | `now() + 1 hour` |
| `created_at` | timestamptz | |

Logout = delete the row. No `revoked_at` needed — deletion is simpler and gives you immediate revocation, which is the property you actually want.

**Endpoints** — keeping exactly what was proposed, no additions needed: `POST /auth/request-code`, `POST /auth/verify-code`, `POST /auth/logout`, `GET /auth/me`, plus admin CRUD on `access_rules`. Full FastAPI route/dependency layout comes in the next section as planned.

---

## 7. What's deliberately not here yet

- **Auth/RLS** — no longer a gap, see §6. Supabase RLS itself is still intentionally unused — see the architecture decision in §6 for why that's fine as long as Next.js only talks to FastAPI, never Supabase directly.
- **`embedding vector` columns** — omitted per the earlier call to skip pgvector for v1.
- **Real publishing credentials/tokens table** — not needed while `publishing_queue` is served by a mock adapter. Add a `platform_credentials` table only when/if you wire in a real `LinkedInAdapter`.

---

## 8. Example data — one request traced through every table

Same `content_request_id` throughout, so you can follow it end to end. Starts with `amaka@koyatalent.com` authenticating, then the request goes through intake, two draft revisions, gets approved, and gets adapted to three channels — one of which fails publishing until it hits the dead letter state.

### `access_rules`

```json
[
  { "id": "ar1000000-0000-0000-0000-000000000001", "type": "domain", "value": "koyatalent.com", "enabled": true, "created_at": "2026-08-01T08:00:00Z", "expires_at": null }
]
```

### `users`

```json
{
  "id": "u1000000-0000-0000-0000-000000000001",
  "email": "amaka@koyatalent.com",
  "created_at": "2026-09-10T09:01:12Z",
  "last_login_at": "2026-09-10T09:01:40Z"
}
```

### `login_attempts`

```json
{
  "id": "la100000-0000-0000-0000-000000000001",
  "user_id": "u1000000-0000-0000-0000-000000000001",
  "code_hash": "$2b$12$KIXQ...truncated",
  "expires_at": "2026-09-10T09:11:12Z",
  "attempts": 1,
  "max_attempts": 5,
  "consumed_at": "2026-09-10T09:01:40Z",
  "created_at": "2026-09-10T09:01:12Z"
}
```

### `sessions`

```json
{
  "id": "6f3a2b1c-8d4e-4a91-9c2f-7e1b0d5a3c44",
  "user_id": "u1000000-0000-0000-0000-000000000001",
  "expires_at": "2026-09-10T10:01:40Z",
  "created_at": "2026-09-10T09:01:40Z"
}
```

### `content_requests`

```json
{
  "id": "c1000000-0000-0000-0000-000000000001",
  "raw_idea": "5 productivity tips for remote SaaS teams, backed by recent research",
  "target_audience": "B2B SaaS marketing managers, mid-career, US-based",
  "supporting_material": { "notes": "Tie in the Gartner hybrid-work stat if possible" },
  "status": "queued",
  "submitted_by_user_id": "u1000000-0000-0000-0000-000000000001",
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
  "reviewer_user_id": "u1000000-0000-0000-0000-000000000001",
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

## 9. Project structure — backend + frontend

This is the concrete filesystem layout. Everything here traces back to a decision in §1–§8; nothing here is arbitrary. No n8n anywhere in the system — the async layer is a polling worker against the `jobs` table (§1, §5), and the whole pipeline is FastAPI + Claude service + Next.js.

### 9.1 Top-level repository

```
koya-content-agent/
├── backend/
│   ├── app/                    # FastAPI orchestrator (the HTTP layer + API routes)
│   ├── worker/                # polling worker — claims jobs, executes, writes state back
│   ├── claude/               # Claude service + model router — the only place Claude is called
│   ├── supabase/             # Supabase client init + typed repository helpers (optional, see note)
│   ├── shared/              # types/enums that both app and worker import (single source of truth)
│   ├── auth/               # OTP + session handling — the allowlist/OTP flow from §6
│   ├── tests/
│   ├── alembic/            # migrations — schema §3 lives here as SQL, not in a doc
│   ├── scripts/            # one-shot bootstraps: seed example data, wipe a request, etc.
│   ├── Dockerfile
│   ├── pyproject.toml
│   └── .env.example
├── frontend/
│   ├── app/                 # Next.js App Router pages — requests list, detail, review, queue
│   ├── components/         # request cards, draft viewer, channel output blocks, queue items
│   ├── lib/               # Supabase JS client (anon only), API helpers, formatting-rule validators
│   ├── hooks/             # SWR/useState wrappers over the backend API
│   ├── tests/
│   ├── Dockerfile
│   ├── package.json
│   └── .env.example
├── docs/
│   ├── provided/          # PRD + assets — never edited by us
│   └── work/             # architecture.md, submission workbook, project summary — ours
├── .gitignore
└── README.md
```

### 9.2 What lives where, and why

**`backend/shared/` — the one place enums and domain types are defined**

`content_requests` status, `request_status` enum, `job_type`, `review_decision`, `channel`, `access_rule_type`, etc. All of it. Both `app/`, `worker/`, and `auth/` import from here, so there is exactly one definition of each enum. If the schema adds a new status, you change it in one file and both sides pick it up. This is what keeps the "source of truth for history is `stage_events`" rule from becoming a lie in code — the worker and the API can't quietly disagree on what `request_status` values exist.

Concrete files:
- `shared/enums.py` — every `create type ... as enum` from §2, as Python `enum.StrEnum` or `typing.Literal` as appropriate
- `shared/models.py` — Pydantic v2 models for the request/response shapes the API surface uses (content request intake, draft with sources, evaluation result, channel adaptation, publishing queue item, auth request/response). These are the *contract* — the DB rows in §3 are internal; the Pydantic models are what the frontend and the worker talk to.
- `shared/errors.py` — domain error classes (`ResearchFailure`, `DraftEvaluationFailed`, `ApprovalRequired`, `NotAuthorized`, etc.) that map to meaningful HTTP responses and to the `stage_events.error_message` / `jobs.last_error` text. Not generic 500s — each one says what failed and why, which is the §5 production-skill requirement.

**`backend/claude/` — Claude service + model router, the only place Claude is called**

This is the module that owns every Claude API call in the system. Nothing in `app/`, `worker/`, or `auth/` imports the Claude SDK directly — they call into `claude/`. The reason: model selection (the Week 2+ reflection question) is a decision made in one place. If you later decide `generate` drafts use a different model than `evaluate` drafts, or you add a cheaper model for `adapt`, you change it in `claude/` and nowhere else.

Concrete files:
- `claude/client.py` — thin wrapper around the Claude SDK/API. Holds the API key from env, exposes a single `chat(...)`-style function that takes a model, messages, system prompt, and optional structured-output schema. No business logic here — it's the boundary.
- `claude/models.py` — the model router. Defines which Claude model is used for which pipeline step, with the rationale recorded as a comment (this is what the reflection sheet's model-choice question will point at). For v1, one model is fine, but the router exists so the choice is explicit rather than implicit-in-each-call.
- `claude/prompts/` — one file per pipeline step that has a system prompt + user-message template: `research.py`, `plan.py`, `generate.py`, `evaluate.py`, `adapt.py`. Each exports a function that takes the step's inputs (source text, plan outline, draft to evaluate, etc.) and returns the prompt payload. Prompts are code, not strings inline in the worker — that's what makes "which source informed this output" and "the evaluation rubric is actually applied" testable and reviewable rather than hidden in a worker function.
- `claude/outputs.py` — the structured-output schemas (JSON schema) for steps that need deterministic shape: evaluation output (must include pass/revise/reject + per-criterion scores + unsupported claims + sections to revise + recommended changes + final status, per §3.5 and the rubric), adaptation output (channel-ready copy with formatting metadata). These schemas are the guarantee that the evaluation loop and the formatting check are real, not prose the worker hopes the model followed.

**`backend/app/` — FastAPI orchestrator**

The HTTP layer. It owns intake, the list/detail UI endpoints, the human-review decision endpoint, the publishing-queue management endpoints, and the auth endpoints. It does *not* execute pipeline steps — it enqueues `jobs` rows and returns, except for the few steps that are synchronous-by-nature at intake time (validate the intake, write `content_requests` + `intake_attachments`, write the first `stage_events` row, enqueue the `research` job).

Concrete files:
- `app/main.py` — FastAPI app, lifespan (opens Supabase client, sets up the session cookie dependency), middleware, exception handlers that map `shared/errors.py` to HTTP responses.
- `app/api/` — route modules:
    - `intake.py` — `POST /api/requests` (create content request + attachments), `GET /api/requests`, `GET /api/requests/{id}`. Returns the request with its current status and a summary of where it is in the pipeline (derived from `stage_events`, not just the denormalized `status` column — the denormalized column is for fast list views, the detail view shows the real trail).
    - `requests.py` — detail endpoint that returns the full request state: current status, sources, plans, drafts with versions, evaluations, human reviews, adaptations. This is the endpoint the frontend detail page hits, and it's the one that demonstrates source traceability (§3.5's `source_ids_used` + `sources.relevance_notes`) and the evaluation loop (§3.4 + §3.5) in one call.
    - `reviews.py` — `POST /api/requests/{id}/review` — the human approval gate. Validates that the request is in a state where a review is allowed, writes `human_reviews`, updates `article_drafts.status` to `selected`/`discarded` based on decision, and — only on `approved` — enqueues the `adapt` job. Nothing downstream of this endpoint runs without a row here (test scenario 5 in code, not just in intent).
    - `publishing.py` — `GET /api/publishing-queue`, `POST /api/publishing-queue/{id}/schedule`, `POST /api/publishing-queue/{id}/cancel`, `POST /api/publishing-queue/{id}/retry` (manually re-enqueue a dead_letter item). This is the UI-facing queue management — the `publishing_queue` table is the domain object, these endpoints are how a human interacts with it.
- `app/services/` — thin orchestrator functions that the routes call, kept separate from route handlers so they're testable without HTTP:
    - `intake_service.py` — validate + persist a content request + attachments, write first `stage_events` row, enqueue `research` job.
    - `request_state_service.py` — assemble the full request detail object from the tables in §3 (this is the join logic that makes the detail endpoint not a N+1 problem).
    - `review_service.py` — the approval-gate logic: check current state, persist review, transition state, conditionally enqueue `adapt`.
- `app/deps.py` — dependency-injection helpers: Supabase client, Claude service instance, config, session lookup. Keeps `main.py` readable and makes testing swap in mocks.
- `app/config.py` — env-based config (Supabase URL/keys, Claude API key, worker settings like poll interval and max_attempts). No hardcoded values. This is the §5 security requirement in code: credentials come from env, never from the repo.

**`backend/auth/` — the OTP + session system from §6**

This module owns the allowlist check, OTP generation/hashing, rate limiting off `login_attempts`, and session create/delete. It's separate from `app/` so the auth flow is cohesive and testable without the rest of the API.

Concrete files:
- `auth/endpoints.py` — the four auth routes: `POST /auth/request-code`, `POST /auth/verify-code`, `POST /auth/logout`, `GET /auth/me`, plus admin CRUD on `access_rules`. The `request-code` endpoint returns the same generic response whether the email is allowlisted or not (§6 refinement 1); the real allowlist check happens silently server-side.
- `auth/service.py` — the core logic: check `access_rules` for the email/domain, rate-limit off `login_attempts` by email + IP (§6 refinement 2), generate + hash the OTP, upsert the `users` row (§6.2 — upserted at request-code time, not first verify), create the `login_attempts` row with `code_hash` + `expires_at`, on verify check `consumed_at` is null and the code matches and it's not expired (§6 refinement 3), create the `sessions` row, return the opaque session token as an HttpOnly/Secure/SameSite cookie.
- `auth/deps.py` — the FastAPI dependency that looks up the session cookie on every protected route and returns the `users` row or raises `NotAuthorized`. This is the access-control gate for all non-auth endpoints — it's what makes the system require a valid session without Supabase RLS (§6 architecture decision).
- `auth/models.py` — Pydantic models for the auth request/response shapes (`RequestCodeRequest`, `VerifyCodeRequest`, `VerifyCodeResponse`, `MeResponse`).

**`backend/worker/` — polling worker, the Celery replacement**

One process, one loop. Claims pending `jobs` rows and `publishing_queue` rows, executes the relevant step, writes state back with retry/backoff per §5. This is the module that makes test scenarios 4, 7, and 8 real at runtime — it's what actually runs the evaluation loop, what retries a failed publish, and what writes `stage_events` rows so the failure trail exists.

Concrete files:
- `worker/main.py` — the loop. Polls `jobs` where `status = 'pending' and next_attempt_at <= now()`, claims one, dispatches to the right handler by `job_type`, on completion writes `succeeded`/`failed` + `stage_events` rows. Separate poll loop for `publishing_queue` rows where `status in ('queued', 'processing') and next_attempt_at <= now()`. Sleep interval from config. This is the whole worker — no scheduler, no broker, no beat.
- `worker/handlers/` — one file per `job_type` from §2:
    - `research.py` — retrieve the URL attachments for the request, scrape/fetch them (Firecrawl or Crawl4AI or direct HTTP — the handler owns the tool choice, §3.2's `retrieval_method` records which), write `sources` rows with `raw_content` + `retrieved_at` + `status = 'retrieved'`, then write `sources` `status = 'selected'` only after planning selects them (research itself doesn't select — it retrieves; selection is the planning step's job, per §3.2's status flow).
    - `plan.py` — takes the retrieved `sources`, calls Claude `plan` prompt, writes `content_plans.outline` + `target_keywords`, writes a `stage_events` row for `planning`, enqueues the `generate` job.
    - `generate.py` — takes a plan + sources, calls Claude `generate` prompt with the SEO best-practices rules embedded in the prompt (not as a separate doc the worker hopes the model read), writes a new `article_drafts` row (version 1 of a new `option_label`, or a revised version if `revision_instructions` were passed in the payload), writes `stage_events` for `generation`.
    - `evaluate.py` — takes a draft, calls Claude `evaluate` prompt with the rubric from §3.5 embedded, parses the structured-output response into `evaluations.rubric_scores` + `overall_score` + `passed_threshold` + `feedback` + `revision_instructions`, writes the row. If `passed_threshold` is false, enqueues another `generate` job with `revision_instructions` in the payload — that's the revision loop (test scenario 4) at the worker level, not a UI nicety. If true, the draft is eligible for human review (the worker does *not* auto-approve — it just makes it reviewable).
    - `adapt.py` — takes the approved draft (the one the human approved, per `human_reviews.decision = 'approved'` or `option_selected` + subsequent approval), calls Claude `adapt` prompt once per channel, writes one `channel_adaptations` row per channel with the channel-appropriate format (plain_text for LinkedIn/X, html for newsletter, per §3.7's markdown note), writes `formatting_check` metadata, writes `stage_events` for `adaptation`. Then enqueues a `publish` job per adaptation.
    - `publish.py` — takes a `publishing_queue` row + its `channel_adaptation`, calls the publishing adapter, writes `publishing_queue.status = 'published'` + `published_at` on success, or retries/backoff per §5 on failure, or dead-letters on exhaustion. For v1 this is the mock adapter (§3.8 + §7 — no real LinkedIn/X/Mailgun credentials yet), so `publish` writes `published` deterministically in dev and the dead-letter path is demonstrable by forcing a failure in the mock.
- `worker/retry.py` — the backoff + dead-letter logic from §5, as a reusable function both `jobs` and `publishing_queue` handlers call. One place for the retry policy.
- `worker/claim.py` — the `SELECT ... FOR UPDATE SKIP LOCKED` claim query, so two worker processes (if you run more than one) don't both pick up the same row. Relevant if you ever scale the worker; for v1 one process is fine, but the claim query is correct regardless.

**`backend/supabase/` — Supabase client + optional typed helpers**

- `supabase/client.py` — initializes the Supabase Python client from env, exposes it as a singleton. This is the boundary with Supabase; everything else imports from here. The backend uses the service-role key (held in env, never committed); the frontend uses only the anon key.
- `supabase/repos/` — *optional.* If you want typed repository functions (e.g. `create_content_request`, `list_requests`, `claim_job`) that encapsulate the SQL rather than inlining it in services, this is where they live. For v1 you can inline the queries in `app/services/` and `worker/handlers/` and skip this layer entirely — it's a cleanliness improvement, not a requirement. The schema in §3 is what matters; how you access it is an implementation detail.

**`backend/tests/` — what to test, mapped to the 8 required scenarios**

- `tests/test_intake.py` — raw idea request (scenario 1) and URL-based request (scenario 2): submit a request with only a raw idea, assert a `research` job is enqueued and `stage_events` has an `intake` + `research` row; submit with a source URL attachment, assert the URL is stored in `intake_attachments` and the `research` job payload includes it.
- `tests/test_source_grounding.py` — scenario 3: after research, assert `sources` rows exist with `raw_content` + `status = 'retrieved'`, and that a generated draft's `source_ids_used` points to real `sources.id`s. This is the test that says "the system shows which sources informed the output" — it's not a UI assertion, it's a data assertion.
- `tests/test_evaluation_loop.py` — scenario 4: generate a weak draft (or use the example data from §8 where version 1 fails), assert an `evaluations` row with `passed_threshold = false` + `revision_instructions` is written, assert a second `generate` job is enqueued with those instructions, assert version 2 of the draft is created with `parent_draft_id` pointing to version 1, assert the second evaluation clears the bar. This is the test that says "preserve review history" — the lineage in `article_drafts` + the two `evaluations` rows are the evidence.
- `tests/test_human_approval_gate.py` — scenario 5: assert that without a `human_reviews` row, no `adapt` job is enqueued and no `channel_adaptations` rows exist. Submit a review with `decision = 'approved'`, assert the `adapt` job is enqueued. This is the gate in code.
- `tests/test_channel_formatting.py` — scenario 6: after adaptation, assert `channel_adaptations.content` for LinkedIn/X is plain_text (no markdown syntax) and for newsletter is html, and that `formatting_check` has the expected metadata (char counts, etc.). This is the test that says "follows the formatting rules" — it's a format assertion on the stored output.
- `tests/test_publishing_queue.py` — scenario 7: assert a `publishing_queue` row is created per adaptation with `status = 'queued'`, assert the worker transitions it to `published` (mock), assert a scheduled item has `scheduled_for` set and `next_attempt_at` in the future.
- `tests/test_failure_handling.py` — scenario 8: force a failure at each stage (e.g. mock the Claude client to raise, mock the scraper to raise, mock the publish adapter to raise), assert the corresponding `stage_events` row has `status = 'failed'` + `error_message`, assert the `jobs`/`publishing_queue` row has `last_error` set and is in a retry state or dead_letter, assert the request `status` reflects the failure. This is the test that says "the failure is clear enough to debug" — it's an assertion on the error trail, not on a log file.
- `tests/test_auth.py` — the auth flow: request code for an allowlisted email, verify with the correct code, assert a session cookie is set and `GET /auth/me` returns the user; request code for a non-allowlisted email, assert the same generic response as for an allowlisted email (§6 refinement 1); attempt to access a protected endpoint without a session, assert 401. This tests that the allowlist is not enumerable and that the session gate works.

**`backend/alembic/` — migrations**

The schema in §3 is the spec; `alembic/` is where it becomes real and versioned. `alembic/versions/` gets one migration per schema change. This is what makes the schema reviewable and deployable rather than a doc that drifts from the actual DB. The example data in §8 is a separate `scripts/seed_example_data.py` that inserts the §8 rows — not a migration, because example data isn't schema.

**`backend/scripts/` — one-shot tooling**

- `scripts/seed_example_data.py` — inserts the §8 example request through every table (including the auth rows: `access_rules`, `users`, `login_attempts`, `sessions`), so you can run the worker against known data and watch the pipeline trace in `stage_events`. This is what makes the Loom video reproducible — you seed, you run, you show the trail.
- `scripts/wipe_request.py` — given a `content_request_id`, cascade-deletes it (honors the `on delete cascade` in §3). Useful during development when a run goes sideways and you want a clean slate without dropping the whole DB.
- `scripts/print_stage_events.py` — given a `content_request_id`, prints the `stage_events` trail in order. This is the command you run to produce the narrative for the Loom video and for test scenario 8 — it's the same data the UI shows, just to the terminal.

### 9.3 Frontend — Next.js App Router

The frontend is the content manager's interface to the backend. It does not execute pipeline steps — it submits requests, views state, reviews drafts, and manages the publishing queue. The worker is the only thing that executes. The frontend talks to Supabase only via the anon key (for Storage uploads of intake images — if you use Supabase Storage for `intake_attachments` media); everything else goes through the FastAPI backend, which is the only thing holding the service-role key.

```
frontend/
├── app/
│   ├── layout.tsx
│   ├── page.tsx                 # landing — list of content requests, "new request" CTA
│   ├── requests/
│   │   ├── page.tsx            # list view — requests with current status, last stage event
│   │   └── [id]/
│   │       └── page.tsx        # detail view — full request state: sources, drafts, evaluations, adaptations
│   ├── review/
│   │   └── [id]/page.tsx       # human review screen — draft viewer, rubric scores, approve/reject/revise/selector
│   ├── queue/
│   │   └── page.tsx            # publishing queue — queued/scheduled/published/dead_letter items, schedule/retry/cancel
│   ├── new-request/
│   │   └── page.tsx            # intake form — raw idea, target audience, attachments (URLs + image upload)
│   └── auth/
│       ├── login/page.tsx      # OTP flow: email input → code sent → code input → session
│       └── layout.tsx
├── components/
│   ├── request-list.tsx
│   ├── request-card.tsx
│   ├── source-list.tsx         # sources with relevance_notes — the "which sources informed this" view
│   ├── draft-viewer.tsx        # renders body_markdown, shows version lineage, evaluation scores
│   ├── evaluation-panel.tsx    # rubric scores + feedback + unsupported claims + recommended changes
│   ├── channel-output.tsx      # per-channel adapted copy, with format badge (plain_text / html)
│   ├── publishing-queue-table.tsx
│   ├── publishing-queue-item.tsx
│   └── intake-form.tsx
├── lib/
│   ├── supabase.ts             # Supabase JS client from env — anon key only, used for Storage uploads if needed
│   ├── api.ts                   # typed fetch wrappers over the backend API endpoints
│   └── formatting-check.ts     # client-side formatting validators mirroring channel-formatting-rules.md (char counts, hashtag counts, word count for newsletter) — these are the same checks the backend writes into channel_adaptations.formatting_check, surfaced in the UI for the human reviewer
├── hooks/
│   ├── use-requests.ts
│   ├── use-request-detail.ts
│   ├── use-review.ts
│   └── use-publishing-queue.ts
├── tests/
│   ├── component-tests/        # rendering tests for the key UI components
│   └── e2e/                    # a few Playwright/Cypress flows: submit a request, watch it progress, approve, see the queue
├── Dockerfile
├── package.json
└── .env.example                # NEXT_PUBLIC_BACKEND_URL, SUPABASE_URL, SUPABASE_ANON_KEY
```

**What the frontend owns, concretely:**
- The OTP login flow (§6) — the `auth/login` page is where the content manager enters their email, gets a code, and verifies it. The allowlist check is invisible (§6 refinement 1) — the UI just says "if this email is eligible, a code has been sent" whether it is or not.
- The intake form (scenario 1 + 2 from the user's side — the user sees the form, the backend tests the intake).
- The request list and detail view — the detail view is where source traceability (§3.5's `source_ids_used` + `sources.relevance_notes`) and the evaluation loop (§3.4 + §3.5) become visible to a human. This is the screen you show in the Loom video's happy path.
- The review screen — this is where the human approval gate (scenario 5) is exercised. The Review button is disabled unless the request is in a reviewable state (the backend enforces this; the frontend reflects it). The rubric scores, feedback, unsupported claims, and recommended changes from `evaluations` are displayed here — this is what makes the evaluation loop visible, not just real.
- The publishing queue view — this is where scenario 7 (queue) and scenario 8 (failure visibility) are visible. A dead_letter item shows `last_error` in the UI — that's the failure visibility requirement at the human layer.

**What the frontend does NOT own:**
- Pipeline execution (the worker does).
- Claude calls (the Claude service does).
- Schema or data correctness (the backend + DB do).
- The formatting rules themselves (those live in `lib/formatting-check.ts` as validators and in the Claude adaptation prompt — the frontend just displays the result).
- Auth token handling — the session cookie is HttpOnly, so the frontend never sees the token; it just sends it automatically with every request and the backend's `auth/deps.py` looks it up.

### 9.4 Shared contract between backend and frontend

The Pydantic models in `backend/shared/models.py` are the source of truth for the API contract. The frontend's `lib/api.ts` types should be generated or hand-written to match — if you hand-write them, keep them close to the Pydantic models so they don't drift. The cleanest approach for a project this size: have the backend expose the FastAPI auto-generated OpenAPI spec (available at `/docs` by default), and generate the frontend types from it. That way the contract is machine-checked, not hoped-for. If that's too much for v1, hand-write the types and assert in a test that the backend's JSON shapes match — but don't skip the assertion entirely, because a drifted contract is what makes "the system shows which sources informed the output" silently false in the UI.

### 9.5 Env and config — the security boundary

Both `backend/.env.example` and `frontend/.env.example` exist. The real `.env` files are gitignored. The Claude API key, Supabase service role key (backend only — never exposed to the frontend), and Supabase anon key (frontend only) all come from env. The frontend only ever gets the anon key and calls the backend's public API routes — it never talks to Supabase directly with a service key, and it never has a Claude API key. The session cookie is HttpOnly/Secure/SameSite, so the frontend never has access to the session token either. This is the §5 security requirement: no hardcoded keys, no secrets in the repo, no credentials exposed to the browser. The submission checklist asks "are there any keys in the repo, the video, or the front-end?" — with this structure the answer is "no" by construction, not by carefulness.

### 9.6 What this structure makes easy

- **Source traceability (PRD requirement, test scenario 3):** `requests/[id]` detail page shows `source-list.tsx` rendering each `sources` row with its `relevance_notes` — that's "which sources informed the output" at the human layer, backed by the `source_ids_used` array on the draft at the data layer.
- **Evaluation loop visibility (test scenario 4):** `evaluation-panel.tsx` renders the `evaluations` row for the current draft — scores, feedback, unsupported claims, recommended changes. The revision lineage is `draft-viewer.tsx` showing version 1 → version 2 with `parent_draft_id` as the link.
- **Human approval gate (test scenario 5):** `review/[id]` is the only place a human can approve/reject/revise. The backend enforces that nothing downstream runs without a `human_reviews` row; the frontend just exposes the decision.
- **Publishing queue (test scenario 7):** `queue/page.tsx` is the UI-facing queue from `publishing_queue` — queued, scheduled, published, dead_letter. Schedule/retry/cancel are backend endpoints the queue page calls.
- **Failure visibility (test scenario 8):** `stage_events` is rendered in the detail view as a timeline — every stage, started/succeeded/failed, with `error_message` on failures. A dead_letter queue item shows `last_error`. The failure is visible in the UI, not just in logs.
- **Auth (§6):** `auth/login` is the OTP flow; every protected page + API route goes through `auth/deps.py` session lookup; the allowlist is not enumerable because `request-code` returns the same response either way. The session is opaque and server-side — no JWTs, no third-party consumers.
- **Reproducible demo (Loom video):** `scripts/seed_example_data.py` inserts the §8 request (including auth rows), the worker runs it, `scripts/print_stage_events.py` prints the trail, and the frontend detail page shows it. Same data, same story, every time.

### 9.7 What this structure deliberately defers

- **Supabase RLS:** intentionally unused (§6 architecture decision). Access control is the FastAPI session dependency, not RLS policies. This only needs revisiting if the frontend ever needs to query Supabase directly for something other than Storage uploads — confirm that's not planned.
- **Real publishing:** mock adapter for v1. The `publishing_queue` + `publishing` job type + retry/backoff/dead-letter structure is real; the actual LinkedIn/X/newsletter send is a stub that writes `published` deterministically. This satisfies scenario 7's "or saved into a clear publishing queue" without depending on platform API approval. If you want to demonstrate a real failure path, the mock adapter has a "force failure" mode for the Loom video.
- **pgvector / cross-request retrieval:** deferred per §6. Sources are scoped to one request at a time; the Claude service selects excerpts directly from retrieved text. If you need cross-request search later, add an `embedding vector` column to `sources` and a retrieval step that queries it — but that's a v2 concern, not v1.
- **Configurable backoff / advanced retry policies:** exponential backoff with `max_attempts = 3` is enough for v1. Don't build a retry-strategies abstraction — it's one line in `worker/retry.py` and the §5 design doesn't call for more.

---

*End of architecture.md.*
