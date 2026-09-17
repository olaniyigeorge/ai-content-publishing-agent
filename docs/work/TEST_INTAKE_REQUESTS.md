# 10 Test Intake Requests — Manual UI Walkthrough

> Rewritten for manual testing through the actual `/requests/new` page in the browser, not raw API payloads. Each case below maps to what you can literally type/click on that form: **Content idea** (textarea), **Source URLs** (one input per URL, "+ Add another source URL"), **Target audience** (single-line input), **Attachments** (file upload button — image/pdf/text/csv only), **Supporting notes** (single freeform textarea, becomes `supporting_material.notes`).
>
> Known guardrails these are designed to hit: `MIN_IDEA_WORDS = 3`, `MAX_IDEA_LENGTH = 2000`, `MIN_TARGET_AUDIENCE_LENGTH = 3`, `MAX_TARGET_AUDIENCE_LENGTH = 300`, `MAX_ATTACHMENTS = 10`, gibberish/no-vowel/repeated-char heuristics, bare-URL-as-idea rejection. The UI's own client-side validation (`frontend/lib/intake-validation.ts`) mirrors these — so for cases below expected to fail, check whether the UI blocks the Submit button *before* it even hits the API (client-side catch) versus submitting and getting a 4xx back (server-side catch). Both are worth noting; a case that only the server catches but the UI would otherwise let through silently is a gap worth flagging.

---

### 1. Clean raw-idea request (happy path baseline) — Scenario 1

- **Content idea:** `Why mid-size B2B SaaS companies are moving off generic email marketing tools and building lifecycle campaigns around product usage data`
- **Source URLs:** leave empty
- **Target audience:** `Marketing leads at 50-200 person B2B SaaS companies evaluating martech stacks`
- **Attachments:** none
- **Supporting notes:** leave empty

**Why:** no URL, no attachments, just an idea. Should produce article options with no source-grounding claims beyond general knowledge. Confirm the system is honest that there's no external source list when none was given.

---

### 2. URL-based request, single good source — Scenario 2

- **Content idea:** `What this year's State of AI report tells marketing teams about where to actually invest`
- **Source URLs:** `https://www.stateof.ai/`
- **Target audience:** `Heads of content and demand gen at agencies`
- **Attachments:** none
- **Supporting notes:** leave empty

**Why:** one real, scrapeable URL. Confirms extraction works and the article actually cites this source, not just general knowledge dressed up as sourced content.

---

### 3. Multi-source request with one dead link mixed in — Scenario 3 / EDGE_CASES #6, #7

- **Content idea:** `How LinkedIn's algorithm changes this year should change B2B posting strategy`
- **Source URLs (add 3 fields):**
  1. `https://www.linkedin.com/business/marketing`
  2. `https://example.com/this-page-does-not-exist-404`
  3. `https://www.nytimes.com/section/technology`
- **Target audience:** `B2B marketing managers running organic LinkedIn programs`

**Why:** the required "at least one URL fails, one succeeds" test. Watch: does `sources` show the 404 as failed, and does the generated article's claims trace only to the sources that actually returned usable text?

---

### 4. All sources fail — the invisible-failure case — EDGE_CASES #6 (Tier 1 highest-impact)

- **Content idea:** `What the latest changes to X's API mean for social media schedulers`
- **Source URLs (add 2 fields):**
  1. `https://example.com/dead-link-one-404`
  2. `https://example.com/dead-link-two-404`
- **Target audience:** `Social media managers who rely on third-party scheduling tools`

**Why:** the single most important negative test in the whole list. If the pipeline proceeds to generate an article anyway, that's the exact "looks grounded, isn't" failure the edge-cases doc calls the worst-case outcome. Expected: request should visibly stop or flag "no usable sources" before generation, not produce a confident-looking article from nothing.

---

### 5. Vague idea + vague audience — passes validation, should still worry a reviewer — EDGE_CASES #2, #3

- **Content idea:** `productivity tips for teams`
- **Target audience:** `everyone`

**Why:** technically clears `MIN_IDEA_WORDS` (3+ words) and `MIN_TARGET_AUDIENCE_LENGTH`, so intake validation lets it through — the UI should let you submit this. This is the gap between "the system ran successfully" and "the output is useful." Use this to test whether anything downstream (planning, evaluation) flags weak specificity, or whether it silently produces generic filler.

---

### 6. Below the word-count floor — should be rejected before submit, zero cost — EDGE_CASES #1

- **Content idea:** `AI marketing`
- **Target audience:** `Marketers`

**Why:** two words, below `MIN_IDEA_WORDS = 3`. Expected: the Submit button should be disabled / show an inline validation error the moment you blur the field — this should never reach the API. If it does submit, note that as a client/server validation mismatch bug.

---

### 7. Content idea is just a bare URL — should be rejected with a specific message — EDGE_CASES #14 / intake_guards `_BARE_URL_RE`

- **Content idea:** `https://techcrunch.com/some-article-about-marketing-trends`
- **Target audience:** `Content marketers`

**Why:** exercises the guard that catches someone pasting a URL into the idea field instead of adding it via **Source URLs**. Expected: rejected with a message telling you to add it as a source URL instead, not a generic "invalid input" error.

---

### 8. Gibberish idea (no vowels / mashed keys) — should be rejected as nonsense — EDGE_CASES #4

- **Content idea:** `xkcd zzzz qwrty tbh`
- **Target audience:** `B2B marketers`

**Why:** designed to trip the no-vowel / gibberish heuristic in `_looks_like_gibberish`. Expected: rejected with a "doesn't look like a usable content idea" message, not passed through to a Claude call that would burn cost on nonsense.

---

### 9. Malformed attachment (API-only — not reproducible from the UI)

The UI form structurally can't produce a malformed attachment: a Source URL field is either empty (and gets filtered out before submit) or a valid-looking URL, and a file attachment only exists once `api.uploadAsset` has already succeeded and returned a `storage_path`. So the "URL type with no URL" / "file type with no storage_path" case from the original test set has no manual-UI equivalent — skip it here, or if you want this covered, it needs a direct `curl POST /api/requests` call instead. Worth a line in the submission notes explaining why it's out of scope for the UI pass.

---

### 10. Maximal, messy, realistic request — Scenario 2/3/6/7 regression case

- **Content idea:** `How our client onboarding data shows that personalized welcome sequences outperform generic drip campaigns by a wide margin, and what other agencies can learn from restructuring their first 30 days of lifecycle email around behavioral triggers instead of a fixed calendar schedule`
- **Source URLs (add 3 fields):**
  1. `https://www.hubspot.com/marketing-statistics`
  2. `https://mailchimp.com/resources/email-marketing-benchmarks/`
  3. `https://en.wikipedia.org/wiki/PDF` (expect mostly boilerplate/nav content — good thin-source test)
- **Target audience:** `Marketing operations leads and lifecycle marketers at agencies managing multiple client accounts who are deciding whether to invest in a behavioral-trigger email platform versus staying on a calendar-based drip system`
- **Attachments:** upload one real image (e.g. a screenshot) and one real PDF/text file through the file picker
- **Supporting notes:** `Pulled from Q3 client retention review; do not quote client names in the public article. Benchmark open rate 38%, benchmark click rate 6.1%.`

**Why:** realistic "this is what an actual content manager submits" case — near the idea/audience length ceiling, mixed URL + image + file attachments in one request, a source likely to scrape as mostly-boilerplate (EDGE_CASES #7), and a supporting note containing an internal instruction the article must *not* leak into public copy. Good end-to-end regression test once the happy path and pure-failure cases above are confirmed. Run this one all the way through evaluation → approval → channel adaptation → publishing queue, since it's the best single request to exercise scenarios 4–7 in one pass.

---

## Coverage against the 8 required scenarios

| # | Scenario | Covered by |
| --- | --- | --- |
| 1 | Raw idea request | #1, #5 |
| 2 | URL-based request | #2, #10 |
| 3 | Research and source grounding | #3, #4, #10 |
| 4 | Evaluation and revision loop | run #5 and #10 through evaluation, check it flags vagueness/weak grounding |
| 5 | Human approval | run #2 or #10 to a draft and test the approval gate |
| 6 | Channel formatting | run #2 or #10 through adaptation |
| 7 | Publishing/scheduling | approve output of #2 or #10, push to queue |
| 8 | Failure handling | #4 (all sources fail), #6/#7/#8 (intake rejections in the UI), plus deliberately regenerating a channel adaptation twice in quick succession (see known bug below) |

Requests #6, #7, #8 should never reach the pipeline — if the Submit button lets any of them through and a `content_request` row gets created instead of an inline validation error, that's a client/server validation mismatch worth flagging before submission.

---

## Known live bug to confirm/reference during Scenario 8 (failure handling)

Seen live on 2026-09-17: regenerating channel adaptations after an "x: over 280-character limit" hard-guard failure retried the insert and hit `duplicate key value violates unique constraint "channel_adaptations_unique"` on `(article_draft_id, channel)` — the raw Postgres error surfaced in the pipeline activity log instead of a clean retry. Being fixed separately; when you hit "Rewrite" / regenerate on channel adaptations during testing, check whether this still surfaces a raw DB error or now retries cleanly, and note the result here.
