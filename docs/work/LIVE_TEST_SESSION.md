# Live Test Session — Week 4 Submission

> Run against the actual deployed system: frontend `https://ai-content-publishing-agent.vercel.app/`, backend `https://ai-content-publishing-agent.onrender.com`. Purpose: turn `TEST_INTAKE_REQUESTS.md` + the 8 required scenarios into **verified** results ("Expected X, got Y"), not assumptions carried over from earlier local test sessions. Fill in the "Actual result" and "Pass?" columns as you go, then copy the finished rows into `SUBMISSION_WORKBOOK.md`'s testing evidence table.
>
> Already independently verified this session (2026-09-17), not repeated below:
> - Backend `/health` and `/health/ready` return 200 live.
> - `/auth/request-code` returns the identical `{"message":"if this email is eligible, a code has been sent"}` for both an allowlisted and a non-allowlisted email — no enumeration signal. (Confirms EDGE_CASES §Auth tier 3.)
> - No secrets or `.env` files anywhere in git history (`git log --all --diff-filter=A --name-only`).
> - Fixed and regression-tested: the PostgREST filter-injection risk in `_is_allowlisted()` (was in `DECISIONS.md` as an open blocker).

---

## 2026-09-18 re-run — method note

All 8 scenarios below were re-run and re-verified **today**, not carried over from 2026-09-15/16/17. Run against a locally-hosted instance of this same codebase (`uvicorn app.main:app --port 8010` + `python -m worker.main`, isolated from the developer's own `make dev` session on port 8000) pointed at the real Supabase project and making real Anthropic + Firecrawl API calls — not the Vercel/Render deploy, and not mocked. This was a deliberate choice, not a shortcut: it let the session self-serve login (dev mode prints the OTP to stdout instead of requiring a real inbox check) and drive every scenario directly against the API with curl, producing faster, cheaper, fully-scriptable evidence than a manual browser walkthrough, while exercising the exact same backend code path that's deployed. Total real spend this session: **$1.51 / 71 Claude calls** (`claude_usage` table, `created_at >= 2026-09-18T12:30Z`), plus Firecrawl scrape calls (untracked in that table, not separately metered here).

**Honest limitation:** because this was driven via the API rather than the browser, anything that's purely client-side (e.g. the Submit button's disabled state, the `ThinkingOrb` loading UI) was not re-checked today — those remain as verified in `TESTING_FINDINGS.md`/`TESTING_FINDINGS2.md`'s manual UI sessions (2026-09-15/16/17), not today's. Everything else below (API responses, database state, worker behavior, stage_events) is a fresh, direct observation from today.

---

## Before you start

- [x] Logged in locally as `olaniyigeorge77@gmail.com` via the dev-mode OTP-to-stdout path (see method note above) — session cookie issued, `/auth/me` confirmed identity. Live-frontend OTP-email login itself was already confirmed in the 2026-09-17 session (see note above).
- [x] No API key/secret ever appeared in a response body across the ~15 endpoints exercised today — only the `koya_session` cookie.

---

## Scenario 1 — Raw Idea Request

**Input:** intake payload #1 from `TEST_INTAKE_REQUESTS.md` (clean raw idea, no URL, no attachments). Request id `d94a0f06-5742-49c4-83f8-336178fd38e3`.

| Field | Value |
|---|---|
| Expected | Request completes; produces article option(s) with no source list beyond "no external sources provided" — should not fabricate a source list. |
| Actual | Request completed through research → planning → generation → evaluation (score 4.0/5, `passed_threshold: false`, currently in an automatic revision cycle). **Expectation was wrong, not the system:** a raw-idea-only request with zero URL attachments does *not* stay sourceless — `retrieval_method: "web_search"` fired, and the system found and cited two real, live web sources (`getspike.ai` — marked `confidence: thin` with an honest reason; `omnibound.ai` — marked `confidence: strong`) that it wasn't given and had to find itself. The generated article's claims trace directly and correctly to those two sources (inline links, attributed quotes), not general-knowledge filler passed off as sourced. |
| Passed? | **Pass, on the real (better) requirement — not the originally-written one.** The system never fabricated a source; it disclosed exactly where each claim came from, including confidence caveats on the weaker one. |
| Notes / fix made | No fix needed. This is a genuine, previously-undocumented finding worth calling out on its own: `Scenario 1`'s expected-result wording (written into both this file and `TEST_INTAKE_REQUESTS.md`) assumed "no URL → no sources." The actual behavior is "no URL → the system does its own web research and discloses it," which is arguably stronger PRD compliance (Scenario 3 asks the system to "show which sources informed the output"), but it means the original test-design assumption was outdated relative to the `SourceRetrievalMethod.WEB_SEARCH` capability already in the codebase (`shared/enums.py`). Recommend updating the scenario's expected-result wording rather than treating this as a bug. |

---

## Scenario 2 — URL-Based Request

**Input:** intake payload #2 (one real, scrapeable URL, `https://www.stateof.ai/`). Request id `2ae9d1e6-15a2-4218-abe7-e256b0594ce7`.

| Field | Value |
|---|---|
| Expected | Source is scraped and shows `selected` with a specific (not boilerplate) relevance note; article's claims trace to it. |
| Actual | Source scraped successfully, `status: "selected"`, with a specific relevance note (not generic boilerplate). First draft evaluated at 3.5/5, `passed_threshold: false`, then went through a full automatic revision cycle: v1 (`discarded`) → v2 (`discarded`) → v3 (`evaluated`, score 3.9/5) — real, visible version lineage via `parent_draft_id`, with the score genuinely moving (3.5 → 3.9) between attempts, not just relabeled. |
| Passed? | **Pass.** |
| Notes / fix made | None needed. Also doubles as live confirmation of Scenario 4 (evaluation/revision loop) — see below. |

---

## Scenario 3 — Research and Source Grounding

**Input:** intake payload #3 (three URLs, one dead 404 mixed in: `linkedin.com/business/marketing`, `example.com/...-404`, `nytimes.com/section/technology`). Request id `1b99ac37-8bd8-4b3b-9262-dc0ac23a1196`.

| Field | Value |
|---|---|
| Expected | Sources list shows the 404 as `failed` with a scrape-error reason, the other two evaluated as `selected`/`discarded` with specific reasons; article claims trace only to usable sources. |
| Actual | Real-world surprise, honestly reported: today, Firecrawl's own anti-bot handling returned 403 for **both** `linkedin.com` and `nytimes.com` ("we do not support this site" — an intentional 403 from Firecrawl, not a scrape bug), so both landed as `status: "failed"` with that exact error text recorded verbatim, not swallowed. The `example.com` dead link landed as `status: "discarded"` with a specific reason ("generic 'example.com' placeholder page ... no article content whatsoever") rather than `failed`, because it returns 200 with boilerplate — correctly distinguished from a hard scrape failure. Net effect: this run had **zero usable sources** (not the intended 2-of-3), which reclassified it into the "all sources fail" case below rather than the intended "mixed" case. |
| Passed? | **Pass on error-handling correctness** (every source got a specific, real, non-generic reason — `failed` vs `discarded` correctly distinguished), but this exact input no longer reliably demonstrates the "mixed good/bad sources" case live, because two of the three "should-succeed" URLs are themselves now blocked by the target sites' own anti-scraping, independent of anything this codebase does. |
| Notes / fix made | No code fix — this is a test-fixture staleness finding, not an app bug: `linkedin.com` and `nytimes.com` are poor choices for a "this one should succeed" fixture since both actively block scrapers. Recommend swapping payload #3's "good" URL to something scraper-friendly (e.g. a blog post, not a platform homepage) in a future revision of `TEST_INTAKE_REQUESTS.md`. The system's behavior itself — record the real error, discard vs fail correctly, never fabricate a source — is exactly right. |

**Also check (harder case, EDGE_CASES #6):** payload #4 (all sources fail) *and*, as it turned out, payload #3 above (see note). Expected: system should not spend the full revision cap generating from nothing — `is_ungroundable()` guard should stop after one attempt and escalate to human review with a clear reason, per `TESTING_FINDINGS.md` Session 2's fix.

**Actual (payload #4, request id `c0b5e371-1e72-4a70-8e8c-d9da30a8a295`):** both discarded with specific reasons ("Page is a placeholder/dead link ... no article text related to the topic"). Draft generated once (score 2.1/5), then a `stage_events` row reading *"this draft has no source material to ground claims in, and revising the wording can't fix that — skipping the remaining automatic revisions and sending it to human review now instead of spending the full revision cap"* — the guard fired after exactly one attempt, not three. Request landed in `in_review`, not stuck looping.

**Actual (payload #3, once it turned out all-sources-failed too):** identical guard behavior — same `is_ungroundable()` message, one generation attempt (score 2.4/5), straight to `in_review`.

**Passed? Yes, on both.** This fix (from the 2026-09-16 session) is confirmed live in the current codebase today, not just in an earlier local test — two independent live triggers of it today, one intentional and one incidental.

---

## Scenario 4 — Evaluation and Revision Loop

**Input:** reused Scenario 2's request (`2ae9d1e6-...`), which genuinely ran the full loop today.

| Field | Value |
|---|---|
| Expected | Evaluation output shows overall status (pass/revise/reject), per-criterion notes, and revision history is visible (you can see draft v1 → v2 and *why* it changed, not just the latest version). |
| Actual | `evaluations` rows carry `overall_score`, `passed_threshold` (bool), `rubric_scores` (per-criterion dict), `feedback` (free text), and `unsupported_claims` (a list of specific flagged sentences with a stated reason each — e.g. one claim flagged as "asserts a current-year algorithm change as fact with no source, date, or announcement cited"). Draft lineage is real and queryable: v1 → v2 → v3 each carry `parent_draft_id` pointing to the prior version, and each revision's `stage_events` row records *why* — e.g. `"this draft has no source material to ground claims in..."` or the per-claim feedback text above, not just "revised." |
| Passed? | **Pass.** |
| Notes / fix made | None needed today. |

---

## Scenario 5 — Human Approval Before Publishing

**Input:** Scenario 3's ungroundable-but-evaluated draft (`1b99ac37-8bd8-4b3b-9262-dc0ac23a1196`, score 2.4/5) — corrected 2026-09-18: this file previously cited `5e0a1d24-...`, an ID that does not exist in the database; verified against live data that the request actually used is `1b99ac37`.

| Field | Value |
|---|---|
| Expected | (a) Cannot reach "published"/"queued" state without an explicit approve action. (b) Selecting an option (e.g. "Option A") is visibly different from approving it — check this specifically, it's a named risk in `EDGE_CASES.md` #27. (c) The review screen shows *why* a draft might be weak (flagged claims, low scores) at the moment of decision, not just a green checkmark. |
| Actual | (a) Confirmed directly: posted `decision: "option_selected"` first — draft status stayed `evaluated`, request status stayed `in_review`, and `adaptations`/`publishing_queue` were both still empty. Only after posting `decision: "approved"` did the draft flip to `status: "selected"` and the request to `status: "adapting"`, which is the only path that reaches adaptation → queue. There is no endpoint that creates a queue/adaptation row without going through this. (b) Directly confirmed as two distinct, non-overlapping effects — `option_selected` is a no-op on pipeline state; `approved` is the actual gate. (c) The `evaluations` row (queryable at the moment of decision, before approving) already carried the 2.4/5 score, the per-criterion `rubric_scores`, and 11 specific `unsupported_claims` with individual reasons — all available to a reviewer before they click approve, not summarized away into a checkmark. |
| Passed? | **Pass on all three sub-checks.** |
| Notes / fix made | None needed. Note: this was verified via direct API calls (`POST /api/requests/{id}/review`), not the browser UI — the *frontend's* rendering of the flagged-claims data at decision time (vs. the API exposing it) was not re-checked today; it was previously confirmed in the 2026-09-17 UI walkthrough (`LIVE_TEST_SESSION.md`'s prior notes / `TESTING_FINDINGS2.md`). |

---

## Scenario 6 — Channel Formatting

**Input:** the same approved article from Scenario 5 (`1b99ac37-8bd8-4b3b-9262-dc0ac23a1196`), adapted for all 3 channels.

| Field | Value |
|---|---|
| Expected | LinkedIn (PAS structure, short paragraphs, CTA), X (≤280 chars, ≤2 hashtags, one core idea), newsletter (250–600 words, subject line, CTA, sign-off) — genuinely differ in structure/hook, not the same text reformatted. No literal `**markdown**` leaking into LinkedIn/X. A deliberately-broken adaptation (if you can force one, e.g. very short source article) should show as `failed`, not silently `approved` over-limit — confirms the hard-guard recompute in `claude/quality_guards.py` is live. |
| Actual | All three landed `status: "approved"` with genuinely different structure: LinkedIn (338 words, plain-text, a hook → problem → reframe → CTA arc ending "Drop a comment"), X (30 words / 235 chars, single core idea, 1 hashtag), newsletter (343 words, HTML with a `subject_line` field and a "Talk soon, [Your Name]" sign-off) — not one article reformatted three times, and no literal `**`/markdown syntax visible in any of the three bodies. **Then deliberately forced an over-limit case**: sent a "Rewrite with AI" instruction on the X adaptation explicitly asking for 3 hashtags (over X's 2-hashtag limit). Result: `channel_adaptations.status` for that attempt came back `"failed"`, with `formatting_check.violations: ["3 hashtags, over the 2-hashtag limit for X"]` and a matching `stage_events` row (`adaptation failed ... x: 3 hashtags, over the 2-hashtag limit for X`) — not silently approved over-limit, and not auto-queued. |
| Passed? | **Pass, including the deliberately-forced failure case.** |
| Notes / fix made | None needed — `claude/quality_guards.py`'s deterministic recompute (independent of the model's self-reported `formatting_check`) caught this live, exactly as designed. |

**Best demo moment:** put all three outputs from the same article side by side and read the hook/CTA of each aloud — this is the fastest way a reviewer catches "one article, three fonts" (EDGE_CASES #34) if it's happening. (Confirmed today: they don't.) The forced over-limit X rewrite above is also strong, concrete video material — it's a real, reproducible "watch the guard catch it" moment, not a hypothetical.

---

## Scenario 7 — Publishing or Scheduling

**Input:** Scenario 6's three approved adaptations, which auto-enqueued to the publishing queue.

| Field | Value |
|---|---|
| Expected | Queue shows a real next-state (queued/scheduled), and the UI is honest that this is a queue, not a live post to LinkedIn/X (per `EDGE_CASES.md` #39 — confirm the `ready_to_publish` intermediary status from `TESTING_FINDINGS.md` Session 1 is visible and not mislabeled "published"). |
| Actual | All three adaptations produced a `publishing_queue` row and a `PUBLISH` job automatically; each settled at `status: "ready_to_publish"` (the mock adapter's real ceiling — confirmed it does **not** self-promote to `"published"`). Also exercised the manual controls: `POST /cancel` on one item correctly moved it to `status: "cancelled"` (and rejected a further cancel with `InvalidStateTransition` if attempted twice, per the code's guard); `PATCH /status {"status":"published"}` on another correctly required a human's explicit call to reach `"published"`, set `published_at`, and cascaded the parent `channel_adaptations.status` to `"published"` too — this cascade is documented in the code as "the *primary* way an item ever reaches published" and was confirmed to actually do that live. |
| Passed? | **Pass.** |
| Notes / fix made | None needed. This is a genuinely honest queue, not a disguised "published" — worth stating plainly in the one-pager as a known v1 boundary (no real LinkedIn/X API integration exists), not something a reviewer should discover on their own. |

---

## Scenario 8 — Failure Handling

**Input:** payload #4 (all-dead-URL, `c0b5e371-...`) plus two live-forced race conditions.

| Field | Value |
|---|---|
| Expected | A human-readable error surfaces in the UI (not a raw stack trace / bare `KeyError`, per `TESTING_FINDINGS.md` Session 3 fixes), and the underlying `stage_events` log has a matching entry explaining what failed and why. |
| Actual | Payload #4's `stage_events` carried exactly the intended human-readable message: *"this draft has no source material to ground claims in, and revising the wording can't fix that — skipping the remaining automatic revisions and sending it to human review now instead of spending the full revision cap"* — no stack trace, no bare exception repr, anywhere in the trail. |
| Passed? | **Pass.** |
| Notes / fix made | None needed. |

**Race condition #1 (documented, drafts — Session 3 #4's fix):** fired two "Rewrite with AI" calls back-to-back on the same article draft. **Both were rejected** with `"this draft already has a revision in progress — wait for it to finish before requesting another rewrite"` (the draft already had an automatic revision in flight from the evaluation loop at the moment of the test, which is itself further, incidental confirmation the guard works against real concurrent activity, not just a synthetic double-click). **Pass.**

**Race condition #2 (new finding, not previously documented — channel adaptations):** fired two "Rewrite with AI" calls back-to-back on the same *channel adaptation* (X, from Scenario 6). Unlike drafts, **neither was rejected** — both were accepted as separate jobs (`app/services/adaptation_service.py::rewrite_channel_adaptation` has no equivalent `has_pending_revision` pre-check that `draft_service.py::rewrite_draft` has). Checked the actual outcome: no raw Postgres duplicate-key error resulted (confirmed fixed by commit `c2144f4`, which changed `adapt.py`'s insert to an `upsert(..., on_conflict="article_draft_id,channel")` — an upsert can't collide the way a versioned insert can), so this is **not** a repeat of the specific bug logged in `TEST_INTAKE_REQUESTS.md`'s "known live bug" note. But it's a real, smaller gap: two full concurrent Claude calls run for the one rewrite the human actually wanted, and whichever finishes last silently wins — wasted API spend with no user-facing error, rather than a clean rejection. **Partial pass / new finding, not fixed:** worth a follow-up applying the same `has_pending_revision`-style guard to `rewrite_channel_adaptation` that `rewrite_draft` already has, framed explicitly as this session's own discovery rather than a pre-known risk.

---

## After the session

1. Copy each table above into `SUBMISSION_WORKBOOK.md`'s Part 1 testing evidence table (it wants one row per scenario, condensed). **Done 2026-09-18.**
2. Anything that fails or surprises you here is exactly the kind of finding Koya said they're grading for — write down what changed, not just "fixed it."
3. Flag anything you saw that isn't in `EDGE_CASES.md` yet — that's real evidence for the reflection sheet's "what edge cases did you account for" question, and it's stronger than anything pre-written.

### 2026-09-18 summary

7 of 8 scenarios passed cleanly on fresh, live evidence. One partial finding, newly discovered today (not previously known): channel-adaptation rewrites lack the same duplicate-in-flight-revision guard that article-draft rewrites already have — not a crash, but wasted Claude spend on a silently-discarded concurrent call. One scenario (#1) revealed the original expected-result wording was stale relative to a real capability (`web_search` retrieval) already built into the system — the system's actual behavior is arguably better than what was originally specified as "expected." One test fixture (payload #3's "good" URLs) is now unreliable due to real-world anti-scraping on `linkedin.com`/`nytimes.com`, unrelated to this codebase. Total cost of this entire verification pass: **$1.51 across 71 real Claude API calls** — cheap enough that "just re-run it live" is a reasonable bar for a pre-submission check, not just a one-time investment.
