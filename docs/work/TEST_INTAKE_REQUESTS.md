# 10 Test Intake Requests

> Matches the real `POST /api/requests` schema (`ContentRequestCreate` in `backend/shared/models.py`) and the intake validation rules in `backend/app/services/intake_guards.py`. Mostly edge cases, mapped to the 8 required test scenarios and `EDGE_CASES.md` so each one earns its place in the testing evidence table, not just filler.

Fields: `raw_idea` (optional string), `target_audience` (required string), `supporting_material` (optional dict), `attachments` (list of `{type: url|image|file, url?, storage_path?, description?}`, max 10).

Known guardrails these requests are designed to hit: `MIN_IDEA_WORDS = 3`, `MAX_IDEA_LENGTH = 2000`, `MIN_TARGET_AUDIENCE_LENGTH = 3`, `MAX_TARGET_AUDIENCE_LENGTH = 300`, `MAX_ATTACHMENTS = 10`, gibberish/no-vowel/repeated-char heuristics, bare-URL-as-idea rejection.

---

### 1. Clean raw-idea request (happy path baseline) — Scenario 1

```json
{
  "raw_idea": "Why mid-size B2B SaaS companies are moving off generic email marketing tools and building lifecycle campaigns around product usage data",
  "target_audience": "Marketing leads at 50-200 person B2B SaaS companies evaluating martech stacks",
  "supporting_material": null,
  "attachments": []
}
```
**Why:** establishes the baseline — no URL, no attachments, just an idea. Should produce article options with no source grounding claims beyond general knowledge. Use this to confirm the system is honest that there's no external source list when none was given.

---

### 2. URL-based request, single good source — Scenario 2

```json
{
  "raw_idea": "What this year's State of AI report tells marketing teams about where to actually invest",
  "target_audience": "Heads of content and demand gen at agencies",
  "supporting_material": null,
  "attachments": [
    {
      "type": "url",
      "url": "https://www.stateof.ai/",
      "description": "Primary source for the article"
    }
  ]
}
```
**Why:** one real, scrapeable URL. Confirms extraction works and the article actually cites this source, not just general knowledge dressed up as sourced content.

---

### 3. Multi-source request with one dead link mixed in — Scenario 3 / EDGE_CASES #6, #7

```json
{
  "raw_idea": "How LinkedIn's algorithm changes this year should change B2B posting strategy",
  "target_audience": "B2B marketing managers running organic LinkedIn programs",
  "supporting_material": null,
  "attachments": [
    { "type": "url", "url": "https://www.linkedin.com/business/marketing", "description": "Official LinkedIn marketing resource" },
    { "type": "url", "url": "https://example.com/this-page-does-not-exist-404", "description": "Industry roundup on the algorithm change" },
    { "type": "url", "url": "https://www.nytimes.com/section/technology", "description": "General context on platform algorithm shifts" }
  ]
}
```
**Why:** the required "at least one URL fails, one succeeds" test. Watch: does `sources` show the 404 as failed, and does the generated article's claims trace only to the sources that actually returned usable text?

---

### 4. All sources fail — the invisible-failure case — EDGE_CASES #6 (Tier 1 highest-impact)

```json
{
  "raw_idea": "What the latest changes to X's API mean for social media schedulers",
  "target_audience": "Social media managers who rely on third-party scheduling tools",
  "supporting_material": null,
  "attachments": [
    { "type": "url", "url": "https://example.com/dead-link-one-404", "description": "X API changelog" },
    { "type": "url", "url": "https://example.com/dead-link-two-404", "description": "Developer community reaction" }
  ]
}
```
**Why:** the single most important negative test in the whole list. If the pipeline proceeds to generate an article anyway, that's the exact "looks grounded, isn't" failure the edge-cases doc calls the worst-case outcome. Expected: request should visibly stop or flag "no usable sources" before generation, not produce a confident-looking article from nothing.

---

### 5. Vague idea + vague audience — passes validation, should still worry a reviewer — EDGE_CASES #2, #3

```json
{
  "raw_idea": "productivity tips for teams",
  "target_audience": "everyone",
  "supporting_material": null,
  "attachments": []
}
```
**Why:** technically clears `MIN_IDEA_WORDS` (3+ words) and `MIN_TARGET_AUDIENCE_LENGTH`, so intake validation lets it through — but this is the gap between "the system ran successfully" and "the output is useful." Use this to test whether anything downstream (planning, evaluation) flags weak specificity, or whether it silently produces generic filler.

---

### 6. Below the word-count floor — should be rejected at intake, zero cost — EDGE_CASES #1

```json
{
  "raw_idea": "AI marketing",
  "target_audience": "Marketers",
  "supporting_material": null,
  "attachments": []
}
```
**Why:** two words, below `MIN_IDEA_WORDS = 3`. Expected: instant 4xx `ValidationFailure` from `validate_raw_idea`, no pipeline run, no Claude call. This is a pure cost-awareness / "reject before it costs anything" test.

---

### 7. Raw idea is just a bare URL — should be rejected with a specific message — EDGE_CASES #14 / intake_guards `_BARE_URL_RE`

```json
{
  "raw_idea": "https://techcrunch.com/some-article-about-marketing-trends",
  "target_audience": "Content marketers",
  "supporting_material": null,
  "attachments": []
}
```
**Why:** exercises the specific guard that catches someone pasting a URL into the idea field instead of adding it as a source attachment. Expected: rejected with a message telling the user to add it as a source URL attachment, not a generic "invalid input" error.

---

### 8. Gibberish idea (no vowels / mashed keys) — should be rejected as nonsense — EDGE_CASES #4

```json
{
  "raw_idea": "xkcd zzzz qwrty tbh",
  "target_audience": "B2B marketers",
  "supporting_material": null,
  "attachments": []
}
```
**Why:** designed to trip the no-vowel / gibberish heuristic in `_looks_like_gibberish`. Expected: rejected at intake with a "doesn't look like a usable content idea" message, not passed through to a Claude call that would burn cost on nonsense.

---

### 9. Malformed attachment — URL type with no URL, and a non-URL type with no storage_path — EDGE_CASES #52/#63-adjacent (bad payload shape)

```json
{
  "raw_idea": "Why newsletter open rates are dropping industry-wide and what still works",
  "target_audience": "Email marketers at mid-market SaaS companies",
  "supporting_material": null,
  "attachments": [
    { "type": "url", "description": "Forgot to paste the actual link" },
    { "type": "image", "description": "Screenshot of open-rate benchmarks, but the upload never happened" }
  ]
}
```
**Why:** both attachments are structurally invalid per `validate_attachments` (a `url` type needs a `url`; a non-`url` type needs a `storage_path`). Expected: rejected at intake with a clear per-attachment error, not a 500 or a silently-dropped attachment.

---

### 10. Maximal, messy, realistic request — long idea, mixed attachment types, oversized supporting_material, at the attachment cap — EDGE_CASES #48/#56 (large payload) + realistic multi-source case

```json
{
  "raw_idea": "How our client onboarding data shows that personalized welcome sequences outperform generic drip campaigns by a wide margin, and what other agencies can learn from restructuring their first 30 days of lifecycle email around behavioral triggers instead of a fixed calendar schedule",
  "target_audience": "Marketing operations leads and lifecycle marketers at agencies managing multiple client accounts who are deciding whether to invest in a behavioral-trigger email platform versus staying on a calendar-based drip system",
  "supporting_material": {
    "internal_note": "Pulled from Q3 client retention review; do not quote client names in the public article",
    "benchmark_open_rate": "38%",
    "benchmark_click_rate": "6.1%"
  },
  "attachments": [
    { "type": "url", "url": "https://www.hubspot.com/marketing-statistics", "description": "Industry benchmark data on email lifecycle performance" },
    { "type": "url", "url": "https://mailchimp.com/resources/email-marketing-benchmarks/", "description": "Secondary benchmark source, cross-check against HubSpot numbers" },
    { "type": "url", "url": "https://en.wikipedia.org/wiki/PDF", "description": "Background reference, expect mostly boilerplate/nav content" },
    { "type": "image", "storage_path": "uploads/2026/09/onboarding-funnel-chart.png", "description": "Internal chart showing onboarding funnel drop-off by day" },
    { "type": "file", "storage_path": "uploads/2026/09/q3-retention-review.pdf", "description": "Internal PDF report, not for public citation" }
  ]
}
```
**Why:** realistic "this is what an actual content manager submits" case, deliberately stacked: near the idea/audience length ceiling, mixed attachment types (url + image + file) in one request, a source that will likely scrape as mostly-boilerplate rather than useful article text (EDGE_CASES #7), and `supporting_material` containing an internal note the article must *not* leak into public copy. Good end-to-end regression test once the happy path and pure-failure cases above are confirmed.

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
| 8 | Failure handling | #4 (all sources fail), #6/#7/#8/#9 (intake rejections), plus a manually-forced worker/API failure during #10 |

Requests #6, #7, #8, #9 should never reach the pipeline at all — if any of them produces a `content_request` row instead of a 4xx at `POST /api/requests`, that's a validation bug worth flagging before submission.
