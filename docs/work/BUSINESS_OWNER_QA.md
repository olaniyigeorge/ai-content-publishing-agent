# Business Owner / Founder Q&A — What They'll Ask and What They Need to See

> Built from `EDGE_CASES.md`, `SUBMISSION_WORKBOOK.md` (production-readiness guide), and the PRD. Framed as: what would a Koya Talent content-team owner or founder actually interrogate before trusting this to touch their brand's LinkedIn/X/newsletter, and where in the system does the answer live.

---

## 1. "Will this ever publish something wrong, embarrassing, or false under our name?"

This is the question underneath every other question. The honest answer has to be layered, not a flat "no":

- **It can't publish without a human clicking approve.** (Scenario 5 — human review is a real gate, not advisory.) Confirm: does the approve/reject/select-option endpoint reject decisions on a request that isn't in a reviewable state? (EDGE_CASES #28.)
- **But a human can approve something bad if the UI hides the problems.** The founder will ask: *when I'm looking at the approval screen, can I see unsupported claims, failed evaluation criteria, or flagged issues right there* — or do I have to trust that "it passed evaluation" means it's fine? (EDGE_CASES #26.) If the UI only shows a green checkmark and not *why*, that's a gap they'll find in five minutes of clicking around.
- **What happens if I select "Option A" without hitting approve?** Does the system ever treat a selection as a publish-readiness signal? (EDGE_CASES #27 — this is a real trap: `option_selected` must never be conflated with `approved`.)

**What to show them:** the review screen with a genuinely flawed draft (weak source grounding or a borderline SEO miss) and prove the flaw is visible at the moment of decision, not buried in a log they'd never open.

---

## 2. "What happens when a source is a paywall, a dead link, or garbage — does the article just get written anyway?"

This is the #1 way the system could quietly produce ungrounded content while looking complete (EDGE_CASES #6, #7 — Tier 1, "high" because the failure is invisible).

- If every URL fails to retrieve, does the pipeline stop and say so, or does it proceed to generate an article "grounded" in nothing?
- If a page scrapes successfully but returns nav/ads/a JS shell instead of article text, does the system know the difference between "we have a source" and "we have usable content from a source"?
- Where does the human see this — a banner on the request, a `sources` table with a status column, or nothing?

**What to show them:** a request where one URL fails and one succeeds — the sources list should visibly show one failed/unusable and the article should trace its claims only to the one that worked.

---

## 3. "Can I actually trust that every claim in the article came from somewhere real?"

Founders who've been burned by AI content ask this directly. The PRD's own requirement is "stay grounded in reviewed source material" and "make it clear which sources informed the output" — this is graded, not optional.

- Is `source_ids_used` ever empty on a published article? (EDGE_CASES #43.)
- Are the "why this source matters" notes specific, or boilerplate like "this source is relevant"? (EDGE_CASES #44 — a founder will read two or three of these and know immediately if they're templated.)
- Does the evaluation step actually catch a hallucinated claim, or does the rubric only check surface things (keyword present, length okay) while missing "this stat isn't in any source"? (EDGE_CASES #11, #17 — this is called out as the single most dangerous failure mode: a false-positive evaluation that defeats the whole revision loop.)

**What to show them:** click a claim in the sample article, show the exact source excerpt it traces to.

---

## 4. "If the AI gets stuck in a loop revising forever, does that burn my Claude budget with nothing to show for it?"

Cost-awareness is graded explicitly, and it's a real founder question: *what stops this from running away from me financially?*

- Is there a hard cap on revision cycles? What happens when the cap is hit — does the request die silently, or does it surface the best-available draft with a warning the human can act on? (EDGE_CASES #24, #25 — "unbreakable workflows.")
- Does the system distinguish a permanent failure (bad URL, 404) from a transient one before retrying — or does it burn a retry (and a Claude call) on something that will never succeed? (EDGE_CASES #62.)
- Which Claude model runs which step, and why the expensive model isn't used everywhere? (This is graded directly under Critical Thinking — "it was the default" is called out by name as an unacceptable answer.)

**What to show them:** the model router / `claude/models.py`-equivalent and a one-line justification per step (e.g., cheap model for formatting checks, stronger model for generation/evaluation).

---

## 5. "If something breaks at 2am, will anyone know, or will it just... not happen?"

This is graded as its own skill ("Error Handling & Failure Visibility") and it's the question that separates a demo from something a business can actually run unattended.

- Does every stage (research, generation, evaluation, adaptation, publishing) write a clear, human-readable error somewhere the UI actually shows — not just a stack trace in a server log the content manager can't access? (EDGE_CASES #52, #58.)
- If the worker crashes mid-job, does the row get stuck in "processing" forever, or is there a way to reclaim/timeout it? (EDGE_CASES #61 — if not handled, a single crash silently stalls the whole pipeline for that request with no way to recover it.)
- If two workers pick up the same job (a real risk with polling workers), do we get duplicate drafts/evaluations, or does the claim query prevent it? (EDGE_CASES #60.)

**What to show them:** deliberately break something (kill the worker mid-job, or point research at a dead URL) and show the failure surfaced in the UI in plain language, plus where it shows up in the underlying log table.

---

## 6. "Does this actually save my team time, or does it just move the work from writing to babysitting the AI?"

The founder's real ROI question, not in the edge-cases doc explicitly but implied by the PRD's framing ("the process works, but it takes too much manual effort to scale"):

- How many manual touches does a content manager need per request — one (submit + approve) or several (submit, monitor, retry, fix formatting, re-approve)?
- If revision or adaptation fails, is there a clear one-click "retry" / "regenerate" path, or does the human have to start a whole new request? (EDGE_CASES #29, #40 — a dead-letter item with no next action is a place where the tool becomes a chore instead of a time-saver.)
- Is the publishing queue actually actionable (schedule/retry/cancel) or just a read-only status list? (EDGE_CASES #42.)

**What to show them:** the full time-to-publish for one request, including at least one point where something needed a human fix, and how many clicks that fix took.

---

## 7. "Is this going to embarrass us on the platform itself — literal asterisks in a LinkedIn post, a tweet that's too long, a newsletter that reads like a search-optimized blog post crammed into an email?"

Very concrete and very findable in a 5-minute demo (EDGE_CASES #31–#38, all Tier 1 or their neighbors).

- Does the LinkedIn/X output ever leak markdown syntax (`**bold**`, `## heading`) that renders as literal characters on the platform?
- Is there an actual character-limit check before a human can approve an over-limit X post, or is that only caught by the platform itself after publishing?
- Do the three channel outputs actually read differently from each other, or is it "one article, three fonts"? (EDGE_CASES #34 — this is explicitly the case most likely to slip past a human reviewer because all three look "fine" individually.)

**What to show them:** the same approved article's three channel outputs side by side, and point out where each deliberately differs in structure/hook/CTA.

---

## 8. "Who can submit requests, and can a stranger get into this and publish something under our name?"

Security & data responsibility is a graded skill, and any founder handling client/brand content will ask this before anything else if they're diligent:

- Is access allowlist-based, and is the allowlist non-enumerable (so a bad actor can't probe which emails have access)? (EDGE_CASES §"Auth" tier 3, and SUBMISSION_WORKBOOK's security checklist.)
- Are OTP codes single-use and sessions revocable?
- Are there any API keys, credentials, or real PII visible in the repo, the demo video, or the front-end network tab?

**What to show them:** log in as a non-allowlisted email and show the identical "check your email" response either way (no enumeration signal), plus a diff/grep proving no secrets are committed.

---

## 9. "What does 'published' actually mean right now — is this really going to LinkedIn, or just into a queue?"

The founder will ask this because the gap between "looks published" and "actually published" is a trust-breaking surprise if discovered later, not caught early (EDGE_CASES #39, explicitly flagged as "by design for v1, but must be honestly stated").

- Is it clearly stated, in the UI and the one-pager, that v1 writes to a mock/queue and does not call real platform APIs?
- Is there a visible, obvious distinction between "queued/scheduled" and "actually posted," so nobody assumes content went out live when it didn't?

**What to show them:** the one-pager's explicit statement of this limitation, plus the queue UI showing queue-state, not a fake "posted" badge.

---

## 10. "What happens with a genuinely bad or garbage input — can someone waste a whole pipeline run by typo-ing 'asdfasdf' into the idea field?"

Cost + UX question in one. (EDGE_CASES #1–#5.)

- Is there instant, no-Claude-call validation that rejects empty/gibberish/too-vague input before any research/generation cost is incurred?
- Does a vague-but-technically-valid idea ("productivity") get flagged, or does it silently produce generic filler that looks like a finished article? (EDGE_CASES #2, #3 — this is the hardest one because it's not a validation-schema problem, it's a judgment call the system may not be equipped to make.)

**What to show them:** one intake rejected instantly (no pipeline run, no cost) and one intake that's vague-but-valid, with an honest answer about whether/how the system flags weak input rather than just running with it.

---

## Quick reference: the "don't let this bite you in the demo" list

These are the specific things a sharp business reviewer finds fastest, in order of how fast they'd find them:

1. Approve a flawed draft and see if the flaw was visible before you clicked (30 seconds into the review screen).
2. Compare the LinkedIn/X/newsletter outputs side by side for "is this actually different content or the same text three times" (1 minute).
3. Click a claim in the article and ask "which source says this" (1 minute).
4. Ask "what happens if I submit garbage" and watch whether it costs a Claude call (immediate).
5. Ask "what happens if this fails halfway through" and watch for a real error message vs. a spinner that never resolves (needs a staged failure demo).
6. Ask "is this really posting to LinkedIn or a mock" — and check whether the honest answer was already written down before they asked.
