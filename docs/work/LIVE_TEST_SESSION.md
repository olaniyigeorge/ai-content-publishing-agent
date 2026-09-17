# Live Test Session — Week 4 Submission

> Run against the actual deployed system: frontend `https://ai-content-publishing-agent.vercel.app/`, backend `https://ai-content-publishing-agent.onrender.com`. Purpose: turn `TEST_INTAKE_REQUESTS.md` + the 8 required scenarios into **verified** results ("Expected X, got Y"), not assumptions carried over from earlier local test sessions. Fill in the "Actual result" and "Pass?" columns as you go, then copy the finished rows into `SUBMISSION_WORKBOOK.md`'s testing evidence table.
>
> Already independently verified this session (2026-09-17), not repeated below:
> - Backend `/health` and `/health/ready` return 200 live.
> - `/auth/request-code` returns the identical `{"message":"if this email is eligible, a code has been sent"}` for both an allowlisted and a non-allowlisted email — no enumeration signal. (Confirms EDGE_CASES §Auth tier 3.)
> - No secrets or `.env` files anywhere in git history (`git log --all --diff-filter=A --name-only`).
> - Fixed and regression-tested: the PostgREST filter-injection risk in `_is_allowlisted()` (was in `DECISIONS.md` as an open blocker).

---

## Before you start

- [ ] Log in at the live frontend with `olaniyigeorge77@gmail.com`, confirm the OTP email arrives and login completes.
- [ ] Keep the browser network tab open once, glance for any API key/secret visible in requests or responses (should be none — session cookie only).

---

## Scenario 1 — Raw Idea Request

**Input:** intake payload #1 from `TEST_INTAKE_REQUESTS.md` (clean raw idea, no URL, no attachments).

| Field | Value |
|---|---|
| Expected | Request completes; produces article option(s) with no source list beyond "no external sources provided" — should not fabricate a source list. |
| Actual | |
| Passed? | |
| Notes / fix made | |

---

## Scenario 2 — URL-Based Request

**Input:** intake payload #2 (one real, scrapeable URL).

| Field | Value |
|---|---|
| Expected | Source is scraped and shows `selected` with a specific (not boilerplate) relevance note; article's claims trace to it. |
| Actual | |
| Passed? | |
| Notes / fix made | |

---

## Scenario 3 — Research and Source Grounding

**Input:** intake payload #3 (three URLs, one dead 404 mixed in).

| Field | Value |
|---|---|
| Expected | Sources list shows the 404 as `failed` with a scrape-error reason, the other two evaluated as `selected`/`discarded` with specific reasons; article claims trace only to usable sources. |
| Actual | |
| Passed? | |
| Notes / fix made | |

**Also check (harder case, EDGE_CASES #6):** payload #4 (all sources fail). Expected: system should not spend the full revision cap generating from nothing — `is_ungroundable()` guard should stop after one attempt and escalate to human review with a clear reason, per `TESTING_FINDINGS.md` Session 2's fix. Confirm this fix is live in production, not just in the earlier local test.

---

## Scenario 4 — Evaluation and Revision Loop

**Input:** payload #5 (vague idea/audience — passes intake, should still get flagged downstream) or reuse a request from Scenario 3.

| Field | Value |
|---|---|
| Expected | Evaluation output shows overall status (pass/revise/reject), per-criterion notes, and revision history is visible (you can see draft v1 → v2 and *why* it changed, not just the latest version). |
| Actual | |
| Passed? | |
| Notes / fix made | |

---

## Scenario 5 — Human Approval Before Publishing

**Input:** any request with a draft ready for review.

| Field | Value |
|---|---|
| Expected | (a) Cannot reach "published"/"queued" state without an explicit approve action. (b) Selecting an option (e.g. "Option A") is visibly different from approving it — check this specifically, it's a named risk in `EDGE_CASES.md` #27. (c) The review screen shows *why* a draft might be weak (flagged claims, low scores) at the moment of decision, not just a green checkmark. |
| Actual | |
| Passed? | |
| Notes / fix made | |

---

## Scenario 6 — Channel Formatting

**Input:** an approved article, adapted for all 3 channels.

| Field | Value |
|---|---|
| Expected | LinkedIn (PAS structure, short paragraphs, CTA), X (≤280 chars, ≤2 hashtags, one core idea), newsletter (250–600 words, subject line, CTA, sign-off) — genuinely differ in structure/hook, not the same text reformatted. No literal `**markdown**` leaking into LinkedIn/X. A deliberately-broken adaptation (if you can force one, e.g. very short source article) should show as `failed`, not silently `approved` over-limit — confirms the hard-guard recompute in `claude/quality_guards.py` is live. |
| Actual | |
| Passed? | |
| Notes / fix made | |

**Best demo moment:** put all three outputs from the same article side by side and read the hook/CTA of each aloud — this is the fastest way a reviewer catches "one article, three fonts" (EDGE_CASES #34) if it's happening.

---

## Scenario 7 — Publishing or Scheduling

**Input:** an approved piece, moved to the publishing queue.

| Field | Value |
|---|---|
| Expected | Queue shows a real next-state (queued/scheduled), and the UI is honest that this is a queue, not a live post to LinkedIn/X (per `EDGE_CASES.md` #39 — confirm the `ready_to_publish` intermediary status from `TESTING_FINDINGS.md` Session 1 is visible and not mislabeled "published"). |
| Actual | |
| Passed? | |
| Notes / fix made | |

---

## Scenario 8 — Failure Handling

**Input:** deliberately break something live — easiest reliable trigger: submit payload #4 (all-dead-URL) again, or submit a URL you know will 404/timeout.

| Field | Value |
|---|---|
| Expected | A human-readable error surfaces in the UI (not a raw stack trace / bare `KeyError`, per `TESTING_FINDINGS.md` Session 3 fixes), and the underlying `stage_events` log has a matching entry explaining what failed and why. |
| Actual | |
| Passed? | |
| Notes / fix made | |

**Stretch (only if time allows, good video material):** open two browser tabs, log in as the same user, and try to trigger "Rewrite with AI" twice on the same draft in quick succession — expected: the second one is rejected with "this draft already has a revision in progress" rather than racing (the fix from `TESTING_FINDINGS.md` Session 3 #4).

---

## After the session

1. Copy each table above into `SUBMISSION_WORKBOOK.md`'s Part 1 testing evidence table (it wants one row per scenario, condensed).
2. Anything that fails or surprises you here is exactly the kind of finding Koya said they're grading for — write down what changed, not just "fixed it."
3. Flag anything you saw that isn't in `EDGE_CASES.md` yet — that's real evidence for the reflection sheet's "what edge cases did you account for" question, and it's stronger than anything pre-written.
