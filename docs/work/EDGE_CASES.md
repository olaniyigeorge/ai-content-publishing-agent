# Edge Cases — Koya Content Agent

> Input and output edge cases for the system. Organized by which boundary they hit (intake, research, generation, evaluation, revision, human review, adaptation, publishing, attribution, sample pack, API/frontend contract, worker/async, revision history), and ranked by how much they could hurt the business or make the system unhelpful — so the ones that matter most are at the top of each section.

> Ranking is qualitative: **high** = could produce bad-publishable content, leak a failure the human doesn't see, or break the workflow entirely; **medium** = produces poor output, wastes a run, or is confusing but recoverable; **low** = handled by schema/validation, minor UX issue, or edge case that's unlikely in normal use. The ranking is a starting point for test and submission decisions, not a claim that any specific case won't bite in production.

---

## Tier 1 — High impact: bad content reaches a human or platform, or a failure is invisible

These are the cases where the system produces something wrong and **the human never gets a clear signal**, or where a single run produces unusable output that looks fine. They map most directly to test scenarios 3, 4, 5, 6, 8 and to the error-handling and edge-case production skills.

### Intake — invalid or unusable input slipping through
1. **[HIGH] Empty raw_idea + zero attachments** — intake should reject; if it doesn't, the pipeline runs on nothing. (Scenario 1 / intake validation.)
2. **[HIGH] Raw idea is so vague ("productivity") that every downstream step produces generic filler** — the system "works" but the output is useless. The human sees a finished article that says nothing. This is the gap between "the system ran successfully" and "the output is good."
3. **[HIGH] Target audience empty or too vague ("everyone")** — the article is written for no one in particular; tone, depth, and framing are off. Same failure mode as #2.
4. **[MEDIUM] Raw idea is a single word, a question, or raw HTML/special characters** — the system accepts it but the output is odd; should be caught at intake or warned.
5. **[MEDIUM] Duplicate or near-duplicate request** — wastes a Claude run; not harmful but noisy if volume grows.

### Research — sources fail silently or produce garbage
6. **[HIGH] All sources fail to retrieve (404/403/blocked/paywall/empty) and the pipeline proceeds anyway** — planning + generation + evaluation run on zero evidence. The article looks complete but has no source grounding. This violates the PRD's "stay grounded in reviewed source material" and "show which sources informed the output" requirements, and the human may never see that the sources are empty unless the UI explicitly shows it. (Scenario 3 / source grounding.)
7. **[HIGH] Scrape returns a page but no article text (nav, ads, footer, JS shell)** — a `sources` row exists with `raw_content` but it's not usable. The system treats it as a real source. The human sees a source listed but the article's claims don't actually trace to it.
8. **[MEDIUM] URL is a PDF / video / API endpoint / social post / dead redirect** — the scraper returns nothing usable or the wrong thing; the source is listed but contributes nothing.
9. **[MEDIUM] Multiple URLs return identical content / one URL is a duplicate** — wastes context; not harmful but inefficient and the human sees redundancy.
10. **[MEDIUM] Source content is in the wrong language** — Claude processes it but the output may be off; the human has to notice.

### Generation — article is bad but looks finished
11. **[HIGH] Generated article contains claims not supported by any source (hallucination)** — the article looks real, the source list looks real, but a claim in the body has no source behind it. If evaluation doesn't catch it, it reaches human review and can be approved. This is the worst-case failure mode for a content system that's supposed to be source-grounded. (Scenario 3 + Scenario 4.)
12. **[HIGH] Generated article is empty, near-empty, or pure restatement of the prompt** — Claude returned almost nothing or generic filler. The system writes a `draft` row that's technically a draft but has no substance. Without an evaluation that flags this, it progresses.
13. **[HIGH] Generated article violates SEO best practices silently** — primary keyword missing from title/first 100 words, no H2/H3 structure, no links, wrong heading depth. The article is "an article" but fails the SEO requirement. The human may not notice if the UI doesn't surface it.
14. **[MEDIUM] Article is too short / too long / incoherent / off-topic / wrong tone** — the system produced something, just not good. Evaluation should catch this; if it doesn't, it's a missed failure.
15. **[MEDIUM] Article includes hallucinated links (not real URLs)** — the "2 to 3 relevant links" requirement is met on paper but the links are fake.
16. **[MEDIUM] Claude API fails mid-generation** — no draft written; the `jobs` row must show `failed` + clear `last_error`, and the request status must reflect it. if it doesn't, the request is stuck in `drafting` with no draft. (Scenario 8.)

### Evaluation — passes bad content or misses real problems
17. **[HIGH] Evaluation says "pass" on an article that has unsupported claims, missing keyword, or hallucinated links** — the rubric scores are inflated; bad content reaches human review with a green light. This is the evaluation's most dangerous failure: a false positive that defeats the whole revision loop. (Scenario 4.)
18. **[HIGH] Evaluation fails to produce parseable structured output** — the JSON schema isn't matched; the worker can't write the `evaluations` row and the revision loop breaks. The failure must be surfaced in `stage_events` + `jobs.last_error`, not swallowed. (Scenario 8.)
19. **[MEDIUM] Evaluation is a false negative** — it says "revise" on a fine article; wastes a revision cycle and a Claude call; the human eventually sees a good article, so the harm is cost + time, not bad content.
20. **[MEDIUM] Revision instructions are vague ("make it better")** — the next generate step has nothing concrete to act on; the revision may not actually fix anything.
21. **[MEDIUM] Evaluation is inconsistent / too generous / all-maxed-out scores** — the threshold isn't discriminating; bad articles pass and good articles don't get credit. Hard to detect without a human comparing.

### Revision — the loop doesn't converge or makes things worse
22. **[HIGH] Revision introduces new unsupported claims or makes the article worse** — the revised draft is technically a newer version but poorer than the original. If evaluation passes it, the worse version moves forward. (Scenario 4.)
23. **[HIGH] Revision doesn't address the feedback** — the evaluation said "lead with the stat" and the revision still doesn't; the loop spins. Without a limit, this can repeat.
24. **[HIGH] Revision loop cycles forever** — draft fails evaluation, gets revised, fails again, repeats indefinitely. There must be a max-revision cap, or the system runs forever burning Claude calls and never reaching human review. This is a real production-readiness failure: an unbounded loop. (Scenario 4 + "unbreakable workflows".)
25. **[MEDIUM] Revision exceeds the cap with no fallback** — what happens? The request is stuck? The last version is presented with a warning? The human must be able to see and act on it.

### Human review — bad approval or invalid decision
26. **[HIGH] Human approves a draft that has known problems (unsupported claims, failed evaluation, flagged issues) and the UI doesn't make those visible at approval time** — the approval gate passes bad content because the human couldn't see the problems. The system should still let the human approve (they're the final authority) but the known issues must be visible at the moment of decision.
27. **[HIGH] Human selects option A (or B) but selection is treated as approval** — `option_selected` is not `approved`; the system must not green-light a selected-but-unapproved draft for publishing. (Scenario 5.)
28. **[MEDIUM] Human approves a draft that's not in a reviewable state (still being revised, not yet evaluated)** — the endpoint must reject the decision as invalid for the current state, not accept it out of order.
29. **[MEDIUM] Human rejects everything with no path back** — the request is dead; is that the right outcome, or should there be a "request regeneration" path?
30. **[LOW] Two humans try to review the same request simultaneously** — the first wins; the second must be rejected with a clear message, not a silent overwrite. Usually rare in an internal tool; schema + endpoint validation handles it.

### Adaptation — channel output is wrong or not channel-adapted
31. **[HIGH] LinkedIn/X post contains markdown syntax (`**bold**`, `## heading`) that renders as literal asterisks on the platform** — violates the channel formatting rule and the output looks broken to a human reader on the platform. The adaptation must emit plain text, and the formatting check must verify it. (Scenario 6.)
32. **[HIGH] LinkedIn/X post exceeds the platform character limit** — truncated or rejected by the platform. The formatting check must catch this before the human approves or the queue publishes. (Scenario 6.)
33. **[HIGH] Newsletter is under 250 or over 600 words, or is missing a strong subject line / CTA / friendly sign-off** — violates the newsletter rules; the output is not a valid newsletter. Formatting check must catch it. (Scenario 6.)
34. **[HIGH] All three channels produce essentially the same content** — not actually adapted; the LinkedIn post, X post, and newsletter are the same text in the same voice. The system "adapted" but didn't differentiate. The human sees three outputs that look identical and may approve them without noticing. (Scenario 6.)
35. **[HIGH] Adapted content introduces new claims not in the approved article, or loses source grounding** — the channel posts say things the article didn't, or drop the source attribution. The output diverges from the approved, grounded article. (Scenario 6 + Scenario 3.)
36. **[MEDIUM] Formatting check says `within_limit: true` but is actually wrong** — the check itself has a bug; the human sees a green check on a post that's too long. The check is the last line of defense before approval/queue; if it's wrong, the defense is fake.
37. **[MEDIUM] Adaptation fails entirely for one or more channels (Claude error / empty output)** — the channel adaptation row must show `failed` with an error, not a partial or empty output that the human approves. (Scenario 8.)
38. **[LOW] LinkedIn post has too many emojis/hashtags or doesn't follow PAS** — the rule exists; the output may not reflect it. The formatting check should note the deviation, but this is lower harm than a broken or over-limit post.

### Publishing queue — publish state is wrong or unactionable
39. **[HIGH] Queue says "published" but nothing actually went out** — the mock writes `published` deterministically; in a real integration this gap (queue says yes, platform says no) is a real failure. For v1 with the mock this is by design, but the one-pager must be honest about it, and the system must not claim real publishing until real credentials are wired. (Scenario 7.)
40. **[HIGH] Dead-letter item has no clear next action for the human** — the UI shows "dead_letter" but doesn't say what to do (retry? rewrite the adaptation? abandon the request?). The human can see the failure but not the path out. (Scenario 8.)
41. **[MEDIUM] Scheduled time is in the past or absurdly far in the future** — past-scheduled items should be processed now; far-future items may be a data-entry error. The queue should handle both sensibly.
42. **[MEDIUM] Queue is read-only in the UI** — items are visible but schedule/retry/cancel aren't exposed; the human can see the queue but not act on it. The endpoints exist; the UI must surface them. (Scenario 7.)

### Source attribution — attribution is present but empty or misleading
43. **[HIGH] Article lists sources but `source_ids_used` is empty** — the attribution is implied, not real; the "which sources informed the output" requirement is met in prose only. (Scenario 3.)
44. **[HIGH] `relevance_notes` are generic ("this source is relevant")** — the human can see the source but not why it mattered; the attribution is technically present but not useful. (Scenario 3.)
45. **[MEDIUM] Source is listed but no excerpt selected** — the source exists in the DB but the article doesn't actually use a passage from it; the source may be decoration.
46. **[MEDIUM] Source URL has link rot / content changed** — the source was right at retrieval time but is different now; the attribution is stale.
47. **[LOW] Source attribution is misleading** — the article implies a source supports a claim it doesn't; harder to detect automatically, mostly a human-review concern.

### Content sample pack (the deliverable) — submission is incomplete or unsafe
48. **[HIGH] Sample pack includes real credentials, PII, or secrets** — violates the security requirement and the submission checklist ("no keys in repo, video, or front-end"). This can lose points on Technical Execution even if the system works.
49. **[HIGH] Sample pack shows only the happy path** — the submission evidence is missing the failure/edge case demo, which is the part the grading is most interested in (the testing table explicitly asks "if a test failed at first, say what you changed"). (All scenarios / submission evidence.)
50. **[MEDIUM] Sample pack shows input but no output, or truncated output** — incomplete submission; the reviewer can't see what the system produced.
51. **[LOW] Sample pack uses example data that doesn't look realistic** — the reviewer can't tell if the system works on real inputs; the sample should look like a real content request.

### API / frontend contract — the UI can't show what the backend knows
52. **[HIGH] API returns a failure but the frontend shows a generic "something went wrong" with no detail** — the failure visibility exists in the backend (`stage_events`, `jobs.last_error`, `publishing_queue.last_error`) but the UI doesn't surface it. The human sees a blank error and can't act. (Scenario 8.)
53. **[HIGH] Frontend crashes or shows a broken state on malformed/partial API responses** — the backend returns something the frontend doesn't handle; the UI is unusable for that request. (Scenario 8 / unbreakable workflows.)
54. **[MEDIUM] Frontend asks for a request that doesn't exist and gets a 404 with no graceful empty state** — the UI must handle "not found" without crashing or showing a raw error.
55. **[MEDIUM] Contract drift — backend adds/removes a field and the frontend ignores it or breaks on it** — the API contract and the frontend types diverge; the UI shows wrong or missing data without the human knowing. (Scenario 8 / "unbreakable" if a repeated run changes the schema.)
56. **[MEDIUM] Large request with many drafts / sources / events returns a huge payload** — the detail endpoint or the frontend chokes; the human can't load the page. Pagination or a bounded response is needed if volume grows.
57. **[LOW] No pagination on list views** — fine for a demo with a few requests; becomes slow if the team runs many requests. Cost-awareness concern at volume, not a v1 bug.

### Worker / async — the pipeline stalls or runs wrong
58. **[HIGH] Worker runs but Supabase is unreachable and every job fails silently** — the error must be surfaced per-job in `jobs.last_error` + `stage_events`, not swallowed. If it isn't, the whole pipeline is stalled and no one knows why. (Scenario 8.)
59. **[HIGH] Worker picks up a job whose referenced row was deleted (ghost reference)** — the handler must detect this and fail with a clear error, not crash or process against nothing. (Scenario 8.)
60. **[HIGH] Two workers pick up the same job** — the job runs twice; duplicates can be created (two drafts, two evaluations, two adaptations). The claim query (`FOR UPDATE SKIP LOCKED`) must prevent this; if it doesn't, the data is corrupted. (Unbreakable workflows.)
61. **[HIGH] Worker crashes mid-job and the row is left in `processing` forever** — the next poll cycle can't recover; the job is stuck. There must be a way to reclaim or timeout a `processing` row, or the pipeline stalls. (Scenario 8 / unbreakable workflows.)
62. **[MEDIUM] Job retries a permanent failure (404, bad URL, bad prompt) as if it were transient** — retrying won't help; the item should go to dead_letter faster, or the handler should distinguish. Wastes Claude calls and delays the human. (Cost awareness + Scenario 8.)
63. **[MEDIUM] Job payload is malformed / corrupted** — the handler can't parse it; must fail cleanly with an error, not crash. (Scenario 8.)
64. **[MEDIUM] Worker runs a job for a request that's been cancelled or wiped** — the request is gone; the job should be skipped or failed, not processed against ghost data. (Unbreakable workflows.)

### Revision history — lineage is broken or confusing
65. **[HIGH] Version numbers get out of sync — two `v2` drafts for the same option** — the `unique (content_request_id, option_label, version)` constraint should prevent this; if it doesn't, the revision lineage is corrupted and the human can't tell which version is current. (Scenario 4 / unbreakable workflows.)
66. **[MEDIUM] `parent_draft_id` points to a draft that was discarded** — the lineage references a dead version; the history is misleading.
67. **[MEDIUM] Evaluation references a draft version that no longer exists** — orphaned evaluation; the history has a gap.
68. **[LOW] Both option A and option B have revisions, human picks A, B's revisions clutter the view** — cosmetic; the data is fine but the UI may show confusing extra versions.

---

## Tier 2 — Medium impact: poor output, wasted run, confusing but recoverable

These are the cases that degrade quality, waste a Claude call, or create a confusing UX, but don't typically result in bad-publishable content or an invisible failure. They're still worth handling because they're what the human notices on repeated runs, and they're what the cost-awareness and edge-case production skills look for.

### Intake
- Raw idea is a single word, a question, or contains raw HTML/special characters (the system accepts it but the output is odd)
- Duplicate or near-duplicate request (wastes a run)
- URL has no scheme / is malformed / is a non-HTTP scheme (rejected or normalized at intake)
- Image is too large / isn't a valid image / is an irrelevant screenshot (handled by validation or ignored)
- File attachment is unsupported / too large / binary / password-protected (rejected or ignored)

### Research
- Source content is in the wrong language
- Scrape returns partial / truncated content
- Claude can't extract a meaningful excerpt from a source
- Rate limiting on code requests is done off the `login_attempts` table (affects auth, not research, but is a medium-cost decision)

### Generation
- Article is too short / too long / incoherent / off-topic / wrong tone (evaluation should catch)
- Article includes broken markdown or formatting that doesn't render as intended

### Evaluation
- Evaluation is a false negative (wastes a revision cycle + a Claude call)
- Evaluation is inconsistent or too generous (hard to detect without human comparison)

### Revision
- Revision is a marginal improvement but still fails evaluation (costs another cycle)
- Human rejects everything with no regeneration path (the request is dead; may or may not be the right outcome)

### Adaptation
- LinkedIn post has too many emojis/hashtags or doesn't follow PAS (lower harm than broken/over-limit post)
- X post doesn't lead with the hook or has 3+ hashtags
- Newsletter subject line is weak or missing a CTA/sign-off
- Adapted content is good but the formatting check metadata is sparse

### Publishing queue
- Scheduled time is in the past or far future (data-entry edge case)
- Queue item has no scheduling granularity (e.g., "publish at this exact minute" with no timezone clarity)

### API / frontend
- Pagination not implemented (fine for demo, cost concern at volume)
- Frontend doesn't refresh automatically / the human has to poll to see progress (UX friction, not a bug)

### Worker
- Worker poll interval is too slow (pipeline feels sluggish but works)
- Worker runs one job at a time (fine for v1; scales poorly but not a v1 bug)

---

## Tier 3 — Low impact: handled by schema/validation, minor UX, or unlikely in normal use

These are cases the schema, validation, or basic UX handles, or that are unlikely to occur in a normal internal-tool run. They're listed for completeness so the test plan and one-pager can say "we considered these" without spending build time on them.

### Intake (schema/validation handled)
- URL is a non-HTTP scheme — rejected at intake
- Check constraint on `intake_attachments` (URL must have a URL, media must have a storage path)
- Duplicate URL in the same request — stored, not a crash; minor noise
- Image/file too large — validation rejects or caps

### Research
- URL redirects in a loop — scraper returns an error; source status = `failed`
- Malicious/phishing URL — fetched and processed; v1 doesn't filter content safety (a known gap, not a v1 build item)

### Auth
- Session cookie tampered with — opaque 122-bit token; validation rejects invalid tokens
- Two sessions for the same user — both valid; no conflict unless they both review the same request simultaneously (rare; endpoint handles it)

### Revision history
- Option A and B both have revisions, B's revisions clutter the view (cosmetic)
- `parent_draft_id` points to a discarded draft (data is odd but not corrupt)

### API / frontend
- Frontend sends malformed JSON — clear 4xx, not a 500
- API returns a field the frontend doesn't know about — frontend ignores it (graceful)

---

## How to use this list for the build and submission

### For the 8 test scenarios

| Scenario | Edge cases to test (from this list) |
| --- | --- |
| 1. Raw idea request | #2, #3, #5 (vague/empty idea, vague audience) — the system should produce something, but the test should also show what "too vague" looks like and whether the system warns |
| 2. URL-based request | #12–#25 (malformed, 404, paywall, JS-heavy, PDF, video, duplicate, empty scrape) — at least one URL that fails and one that succeeds, plus a URL that returns garbage |
| 3. Research and source grounding | #6, #7, #43, #44, #45 (all sources fail, no article text, empty source_ids_used, generic relevance_notes, source without excerpt) — show the source list is real and traceable, and show what happens when it isn't |
| 4. Evaluation and revision loop | #11, #17, #22, #23, #24, #65 (hallucinated claims, false-pass evaluation, revision makes it worse, revision ignores feedback, infinite loop risk, version sync) — show the loop catching a bad draft, revising, and preserving history; show the cap that prevents an infinite loop |
| 5. Human approval before publishing | #26, #27, #28 (approve bad content with invisible issues, selection treated as approval, approve out of state) — show the gate blocking an out-of-state approval and the UI showing issues at approval time |
| 6. Channel formatting | #31, #32, #33, #34, #35, #36 (markdown in LinkedIn/X, over-limit post, newsletter out of word count, identical channel outputs, new claims in adaptations, wrong formatting check) — show each channel output follows the rules, and show the formatting check catching a violation |
| 7. Publishing or scheduling | #39, #40, #41, #42 (queue says published but nothing went out, dead-letter has no action, scheduled time edge case, read-only queue) — show the queue with a published, scheduled, and dead-letter item, and show the human can act on it |
| 8. Failure handling | #16, #37, #52, #53, #58, #59, #60, #61, #63, #64 (scrape fails, adaptation fails, API failure not surfaced, frontend crashes, worker can't reach DB, ghost reference, duplicate job pickup, stuck processing row, malformed payload, wiped request) — show at least one failure per stage with a clear error visible in the UI and in `stage_events`/`jobs`/`publishing_queue` |

### For the 5 production skills

- **Error handling & failure visibility:** #6, #7, #16, #18, #37, #52, #53, #58, #59, #61, #63 — every one of these must surface a clear error in `stage_events` + the relevant `jobs`/`publishing_queue` row + the UI. If any of these is silent, the system fails this skill.
- **Handling edge cases:** this whole list is the evidence. Pick the high-impact ones as the cases you actually handle in v1, and list the rest as "considered, documented as known gaps" in the one-pager.
- **Cost awareness & resource usage:** #9, #19, #25 (duplicate content, wasted revision cycle, infinite loop burning Claude calls), #56, #57 (large payloads, no pagination), #62 (retrying permanent failures). The model-choice question in the reflection sheet also lives here — which model for which step, and why.
- **Building unbreakable workflows:** #24 (infinite loop), #60 (duplicate job pickup), #61 (stuck processing row), #64 (job for wiped request), #65 (version sync via unique constraint), #66/#67 (orphaned lineage). These are the "run it twice and it shouldn't corrupt data" cases.
- **Security & data responsibility:** #48 (sample pack with credentials/PII), #37/#40/#41 (auth edge cases — non-enumerable allowlist, OTP consumption, session revocation), and the general "no keys in repo/video/frontend" rule. The auth design (§6 of the architecture doc) is the main evidence here.

### For the one-pager

The one-pager's appendix (assumptions, limitations, troubleshooting) is where the Tier 2 and Tier 3 cases go — "here's what we handle, here's what we don't handle yet, here's how to tell what went wrong." The high-impact cases should be in the "how it works" or "how to use it" sections because they're the ones a human needs to know about when using the system: "if all sources fail, the request won't proceed," "if the evaluation passes a bad draft, the human can still see the flagged issues at review time," "if a channel post is over the limit, the formatting check flags it before approval."

### For the reflection sheet

The reflection sheet's edge-cases question should point at this list and say which ones you actually handled in v1 vs. which ones you deferred. The "most significant challenge" question will likely be one of the high-impact cases that was harder to handle than it looked (my guess: #6 — all sources failing silently — or #24 — the infinite-loop cap, or #34 — detecting that three channels produced the same content). The "one thing to do differently" question will probably be about which of these you discovered too late.

---

*This file is a living document. As you build, move cases from "considered" to "handled" or "deferred," and record the actual failure modes you hit in the BUILD_LOG.md. The ranking here is a starting point — update it as you learn which cases actually bite.*
