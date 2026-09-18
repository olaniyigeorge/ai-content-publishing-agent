# Week 4 Submission Workbook — AI Content Research and Publishing Agent

> **Purpose:** This file is the single reference for everything required to submit Week 4. It combines the submission template (deliverables, testing evidence table, reflection sheet), the Instructor / Participant Guide for production-ready systems (grading criteria, the 5 core production skills, how work is graded, submission requirements), and a working space to fill in as you build. Use it as your running checklist — if the session breaks, the reference is here.

---

# PART 1 — SUBMISSION TEMPLATE (what you hand in)

## Deliverables

**1. Front-end or application link**

<aside>

https://ai-content-publishing-agent.vercel.app/ (backend API: https://ai-content-publishing-agent.onrender.com — confirmed live and healthy 2026-09-17, `/health/ready` returns 200)

</aside>

---

**2. Content sample pack**

<aside>

*Show the input you gave the system and everything it produced: the article, the LinkedIn post, the X post, the email newsletter, and the source list. Link it here*

</aside>

---

**3. Testing evidence**

<aside>

Fill in the table below. If a test failed at first, say what you changed — that's the part we're most interested in.

</aside>

| Test case | Expected result | Actual result | Passed? | Notes or fix made |
| --- | --- | --- | --- | --- |
| Raw idea request | Idea-only request (no URL) produces article option(s), with no fabricated source list. | **Live-verified 2026-09-18** (`LIVE_TEST_SESSION.md` §1): a zero-attachment request triggered `retrieval_method: web_search`, found two real live sources it wasn't given, cited them inline with an honest `confidence: thin/strong` split, and the article's claims traced to them — never fabricated. | **Pass** — on the real requirement (never fabricate sources), though the scenario's original written expectation ("no source list at all") was itself stale against this capability; recommend updating that wording. | Prior local finding (Session 1 #7, zero-source case scoring 1/5 and escalating) still holds as the negative-space confirmation that the evaluator discriminates rather than rubber-stamping. |
| URL-based request | One real, scrapeable URL is extracted and used; the article's claims trace to it. | **Live-verified 2026-09-18** (`LIVE_TEST_SESSION.md` §2): `stateof.ai` scraped and `selected` with a specific relevance note; draft went through a real, visible revision cycle (v1 3.5/5 → v3 3.9/5) with `parent_draft_id` lineage intact. | **Pass.** | None needed today. |
| Research and source grounding | Mixed good/dead sources: failed source shown as failed with a reason; article traces only to usable sources. | **Live-verified 2026-09-18** (`LIVE_TEST_SESSION.md` §3): today's "good" URLs (`linkedin.com`, `nytimes.com`) were both blocked 403 by Firecrawl's own anti-bot handling — a real-world fixture staleness issue, not a bug — recorded verbatim as `status=failed`; the dead `example.com` link correctly landed `discarded` (not `failed`) with a specific reason. The resulting zero-usable-sources case then correctly triggered `is_ungroundable()` after exactly one generate/evaluate attempt (confirmed on two separate requests today), not the full revision cap. | **Pass** on error handling and the ungroundable guard; the specific "one good, one bad" fixture needs a URL swap for future runs. | Recommend swapping payload #3's URL in `TEST_INTAKE_REQUESTS.md` to a scraper-friendly page. |
| Evaluation and revision loop | Evaluation returns pass/revise/reject + per-criterion notes; revision history preserved. | **Live-verified 2026-09-18** (`LIVE_TEST_SESSION.md` §4): `evaluations` rows carry `overall_score`, `passed_threshold`, per-criterion `rubric_scores`, and specific `unsupported_claims` with individual reasons; draft lineage (v1→v2→v3) is real and queryable via `parent_draft_id`, each with its own evaluation. | **Pass.** | Malformed-Claude-response `KeyError`s (Session 3 #5) were turned into typed, human-readable errors via `claude/outputs.py::require_fields()` — still holding, no recurrence today. |
| Human approval before publishing | Cannot reach queued/published state without an explicit approve; a "selected" option is never treated as "approved." | **Live-verified 2026-09-18** (`LIVE_TEST_SESSION.md` §5): posted `option_selected` directly via the API — draft/request state didn't move, no adaptation/queue rows created. Only `approved` flipped draft to `selected` and request to `adapting`. The evaluation's score + 11 specific flagged claims were confirmed available to the reviewer before that decision, not summarized into a bare checkmark. | **Pass.** | Verified via direct API call, not the browser — the frontend's own rendering of this data was confirmed in the 2026-09-17 UI session, not re-walked today. |
| Channel formatting | LinkedIn/X/newsletter genuinely differ (not one article, three fonts); no leaked markdown; over-limit output is caught, not silently approved. | **Live-verified 2026-09-18** (`LIVE_TEST_SESSION.md` §6): all three channels came back structurally distinct (LinkedIn 338 words hook→CTA, X 30 words/1 hashtag, newsletter HTML with subject line + sign-off), no literal markdown leaking. Then deliberately forced a 3-hashtag X rewrite (over the 2-hashtag limit) — it came back `status: failed` with the exact violation recorded, never silently approved. | **Pass, including the deliberately-forced failure case.** | `claude/quality_guards.py`'s deterministic recompute caught the forced violation live — good, reusable video demo moment. |
| Publishing or scheduling | Approved content lands in a visibly-labeled queue state, honestly distinguished from "actually posted." | **Live-verified 2026-09-18** (`LIVE_TEST_SESSION.md` §7): all three adaptations auto-queued and settled at `ready_to_publish` (never self-promoted to `published`). Manually exercised `/cancel` (→ `cancelled`) and the manual `/status {published}` override (→ `published`, cascading to the parent adaptation) — both worked as designed. | **Pass.** | v1 publishing is a real queue with honest states, not a disguised "published" — confirmed end-to-end today, not just designed. |
| Failure handling | A broken step surfaces a human-readable error in the UI and a matching `stage_events` log entry. | **Live-verified 2026-09-18** (`LIVE_TEST_SESSION.md` §8, request `c0b5e371`): an all-dead-URL request produced the exact `stage_events` message ("this draft has no source material to ground claims in...") on v1 — no stack trace — and the ungroundable guard correctly stopped the *automatic* revision loop there. That guard doesn't cover a later manual retry, though: requesting another rewrite from the review screen ran the pipeline again anyway, and v2 fabricated two source URLs outright (`developer.x.com`, `help.x.com`), caught by the fabricated-URL check; v3 then hit the revision cap still ungrounded (13 flagged claims, same 2.1/5). Three drafts and 7 Claude calls ($0.35) total on a request that had nothing real from the start. Separately, race-tested two rewrite paths: article-draft double-rewrite was correctly rejected ("already has a revision in progress"); channel-adaptation double-rewrite was **not** rejected — new finding, not a crash, but wasted Claude spend on a silently-discarded concurrent call. | **Pass on the core error-visibility scenario; two gaps found and documented, one still open.** | New 2026-09-18 findings: (1) the ungroundable guard stops the *automatic* loop but not a human-triggered retry on the same unfixable draft — worth a second guard. (2) `app/services/adaptation_service.py::rewrite_channel_adaptation` needs the same `has_pending_revision` guard `draft_service.py::rewrite_draft` already has. Also fixed today: the grounding checker could catch a wrong number in a citation but not a wrong publisher — added a check that verifies proper nouns in a citation against the source's recorded title/excerpt (`backend/claude/grounding_validator.py`), tested. Full backend suite: **158/158 passing today**. Total live-verification spend today: $2.10 / 77 real Claude calls. |

---

**4. Video walkthrough**

<aside>

*Paste the link.*

</aside>

---

**5. Reflection sheet**

<aside>

Answer the following questions:

- **In a business setting, what clarifying questions would you ask when assigned this project?**
- **What was the most significant challenge you faced while building this, and what was its root cause?**
- **If you were to start this project again with your current knowledge, what is the one thing you would do differently to make the solution more robust or efficient?**
- **What edge cases did you account for, and how did you account for them?**
- **Which Claude model did you use and why?** Name the alternative you considered, and explain how you weighed quality, cost, latency and task complexity.

Answers:

1. **Clarifying questions I'd ask in a business setting:** What does "publish" actually mean for this team today — do they already have real LinkedIn/X/newsletter integrations, or is a reviewed, ready-to-send queue the real v1 deliverable? Who is the content-manager audience — one person or a small team, which affects whether access control needs to be more than a shared allowlist? What's the expected volume, since that changes whether cost-per-run and caching are worth investing in versus premature? Are there brand-voice guidelines beyond "match the brand" — a style guide or example posts — since the prompts currently have nothing more specific than that? And when a human rejects or asks for a revision today, do they rewrite it themselves or hand back written notes — this decides whether reviewer feedback should ever automatically drive another AI revision pass, or just sit as a record.
2. **Most significant challenge and its root cause:** Getting the system to be honest about source grounding rather than just "looking" grounded. The concrete case: a request with two dead-end source URLs still ran the full research → plan → generate → evaluate cycle three times before escalating, at $0.1651 in Claude calls, because nothing distinguished "zero sources were given" (a supported, required input shape per Scenario 1) from "sources were given but none turned out usable" (should fail fast and cheap). The root cause wasn't a missing check — the checks that existed only fired on model self-reports, not independently verified facts, so a model that scored its own weak draft correctly still let the *loop* keep spending money on drafts that could never pass. The fix was a deterministic guard (`is_ungroundable()`) that looks at the actual data (zero `source_ids_used`) rather than trusting the model's judgment about its own output.
3. **What I'd do differently starting over:** Give the revision loop a reason code before deciding whether to retry, instead of always spending up to the same fixed number of attempts regardless of *why* a draft failed. Right now a source-grounding failure and a genuinely fixable wording issue both consume the same revision budget — the ungroundable-draft guard added this session only catches the zero-sources case; a source that's real but too thin to support the whole article (observed in `TESTING_FINDINGS.md` Session 3 #7, one source stretched across a much bigger argument) still burns the full loop today. Classifying *why* an evaluation failed before deciding whether another attempt can plausibly fix it would be more robust and cheaper.
4. **Edge cases accounted for, and how:** (a) All-sources-unusable — a deterministic guard skips remaining revision attempts once a draft has zero real sources and a low grounding score, escalating to human review instead of burning the cap (`claude/quality_guards.py`). (b) Malformed/incomplete structured responses from Claude — `require_fields()` turns a bare `KeyError` into a typed, readable error instead of surfacing raw Python exceptions to a human reviewer. (c) Concurrent revision requests on the same draft — a pending-job check now rejects a second "rewrite" request with a clear message instead of racing into a database constraint violation. (d) Adversarial/gibberish intake — a free, deterministic filter catches the obvious cases before any AI cost is spent; it's known to be beatable by a single character, so the real backstop is generation refusing to fabricate content from nothing rather than inventing a confident-sounding article (documented explicitly as a limitation, not discovered by an outside reviewer). (e) Model self-reports being wrong — real word/char counts and link counts are recomputed server-side for both articles and channel adaptations, and a model's own "pass" is downgraded if the hard, computed check fails. (f) An allowlist filter-injection risk found during a security pass — fixed this session by replacing a string-interpolated PostgREST `.or_()` filter with two parameterized `.eq()` queries, with a regression test proving a crafted email can no longer widen the match.
5. **Model choice:** Sonnet 5 for `generate` and `evaluate` — these are the two quality-sensitive steps; `generate` is the actual writing the audience reads and has to satisfy SEO rules and source grounding, and `evaluate` drives the entire revision loop, so a weak evaluator model is the single biggest risk to the self-review mechanism ever catching a bad draft. Haiku 4.5 for `research`, `plan`, and `adapt` — these are closer to structured extraction (summarizing scraped text, outlining from a fixed source set, applying channel formatting rules to an already-approved article) than original creative writing, and Haiku is roughly 2x cheaper per token. The alternative considered was running everything on Sonnet for simplicity; rejected because `plan` and `research` run on every single request regardless of outcome, so a cheaper model there compounds savings across every run, while `generate`/`evaluate` are exactly the steps where a cheaper model's mistakes are most expensive to catch later. This is a real, priced trade-off, not a default — though it's honestly calibrated on reasoning-plus-one-session-of-testing (`TESTING_FINDINGS.md` Session 3), not a controlled A/B; the stated trigger to revisit it is if cost data ever shows repeated Sonnet (`generate`) revisions whose root cause traces back to a bad `plan` outline rather than source-grounding thinness.
</aside>

---

**6. One-page documentation**

<aside>

*Paste the link.*

</aside>

---

## Submission Form

<aside>

https://docs.google.com/forms/d/e/1FAIpQLSfnFXF2X4L8T4D8BBAX3GoJcV_XaPYv8Ejrq7bZQjtPAjWDtA/viewform

</aside>

---

# PART 2 — PRODUCTION-READY SYSTEMS GUIDE (how you are graded)

## What This Guide Is For

This guide explains **how your work is evaluated in this program** and what we mean by building *production-ready* automation systems.

You are not being graded on how many tools you use or how clever your solution looks. You are being graded on whether the system you built could realistically be used by a business.

Many automations work once, in perfect conditions. Real systems run repeatedly, fail in unexpected ways, and are relied on by other people.

This guide exists to help you build for that reality — and to communicate your thinking clearly through your submissions.

## What "Production-Ready" Means in This Program

In this program, *production-ready* does not mean complex or feature-heavy.

A production-ready system is one that can run **reliably over time**, even when things go wrong.

That means assuming:

- inputs will be messy or incomplete
- external services may fail
- automations may run more than once
- someone else depends on the outcome

Your job is not to prevent every failure, but to **design for failure**.

If your automation only works on the happy path, it is a demo.

If it can handle errors, edge cases, and repeated runs without breaking, it is production-ready.

Everything else in this guide builds on this idea.

## The Core Production Skills We Grade For

When we evaluate your projects we are not just looking at whether the automation works. We are looking at **how it behaves when reality doesn't cooperate**.

These are the five production skills we explicitly grade for.

### 1. Error Handling & Failure Visibility

Systems fail. What matters is whether the failure is **visible and understandable**.

Your solutions must:

- Detect when something goes wrong
- Surface errors clearly instead of failing silently
- Make it possible to tell *what failed and why*

If an automation breaks and no one can tell, it is not production-ready.

### 2. Handling Edge Cases

Real inputs are rarely perfect.

Your solutions must reflect that you have thought about:

- Missing or incomplete data
- Unexpected formats or values
- Situations that break assumptions

You do not need to handle every possible edge case, but you should show that you have **identified the important ones** and designed around them.

### 3. Cost Awareness & Resource Usage

Production-ready systems run often. Small inefficiencies add up quickly.

Your work must show signs that you have thought about:

- When an automation should *not* run
- Avoiding unnecessary API or AI calls
- Reusing results instead of recomputing them

You do not need exact cost calculations, but you should demonstrate **intentional use of resources**, not wasteful execution.

> **Model selection is part of this.** From Week 2 onward, every set of reflections asks which model you used and what you traded off. Picking the largest available model for a task that a smaller one handles is a cost decision, and it is graded under Critical Thinking. "It was the default" is not an answer.

### 4. Building Unbreakable Workflows

A production-ready workflow should be safe to run repeatedly.

Build systems that handle retries, avoid duplicates, and do not corrupt data when run more than once.

### 5. Security & Data Responsibility

Production systems do not expose secrets or sensitive data.

We look for evidence that you understand basic operational security:

- No hardcoded API keys or credentials in nodes
- Proper use of environment variables or credential managers
- No secrets committed to your GitHub repo — including in the history, not just the current file
- No sensitive data exposed in screenshots or demo videos
- No real user data shown unnecessarily
- Thoughtful handling of access and permissions

A system that works but exposes secrets is not production-ready.

## How Your Work Is Graded

Your work is graded across three dimensions:

- **Technical Execution**
- **Communication**
- **Critical Thinking**

These are closely related. Strong submissions tend to score well across all three, because they reflect clear thinking about the system, the business problem it solves, and how it behaves in real conditions.

### Grading Overview

| Grade Level | What This Level Represents | **Technical Execution** | **Communication (Video)** | **Critical Thinking (Reflections)** |
| --- | --- | --- | --- | --- |
| **1 — Incomplete** | A demo that only works in ideal conditions | Automation works only on a narrow happy path and breaks easily. No meaningful error handling or safeguards. | Video is confusing, disorganised, or skips explaining how the system behaves. | Reflections are missing or show no engagement with the problem. |
| **2 — Beginning** | A working solution that lacks robustness | Automation achieves the core objective but is fragile (little to no error handling, no edge case consideration). | Video explains basic functionality but lacks a clear narrative or focus on outcomes. | Reflections describe what was built, not why decisions were made. |
| **3 — Functional** | A system that works as expected | Automation is fully functional, efficient, and handles common edge cases. | Video is clear and concise, and explains the approach effectively. | Reflections identify challenges but stop short of deeper analysis or lessons learned. |
| **4 — Proficient** | A production-ready system | Automation is reliable, safe to run repeatedly, handles multiple edge cases, and follows basic security best practices. | Video clearly demos the system, focusing on behaviour, outcomes, and reliability. | Reflections analyse problems, explain trade-offs, and extract meaningful lessons. |
| **5 — Excellent** | A system built with ownership and judgment | Automation goes beyond the PRD to improve reliability, clarity, or robustness. Failure modes are well handled. | Video is compelling, well-structured, and includes reflection and improvement ideas. | Reflections demonstrate self-mentoring: clear critique of the work and thoughtful future improvements. |

Each dimension is scored out of 5, so each project is out of 15. **You pass on an 11/15 average across the six weeks**, not week by week.

## Submissions & Deliverables

Your submission has **four parts**: your workflow, a one-pager, a demo video, and written reflections. From Week 3 there is a fifth — a shareable link.

Together they should clearly communicate **what you built, why it exists, and whether it can be trusted**.

### Workflow

You must submit the **actual n8n workflow** you built.

It should:

- Reflect the system shown in your video
- Be runnable and not broken
- Include error handling and safeguards where relevant
- Be safe to run more than once

The workflow is evaluated for **structure, robustness, and production readiness**, not just correctness.

From Week 3 you are building with Claude Code on top of n8n. Everything above still applies — the substrate has not changed, only how fast you can move on it. Code you did not write is still code you own and still code you have to be able to explain.

### Shareable link — Week 3 onward

Every project from Week 3 ships a **working front-end with a link somebody else can open**.

It must:

- Actually load, from a machine that is not yours, without you present
- Still be live when your project is graded — a link that has gone down is a submission that cannot be marked
- Not expose keys or credentials to the browser

This is the single most common way a strong project loses points: the build was good and the link was dead.

### One-Pager

Your one-pager should read like a short internal document someone else could rely on. It should not be overly technical.

**Include:**

- **Header:** title, owner, key links, last updated date
- **Purpose & Success Criteria:** who it is for, what problem existed, what it does, what changes if it works, how success is measured
- **How it Works:** high-level system behaviour
- **How to Use It:** step by step
- **Appendix (optional):** assumptions, limitations, troubleshooting, artefacts

### Demo Video

Your video should be understandable to anyone. **58 minutes maximum.**

**Flow:**

1. Who you are and what you built
2. The business problem
3. How the system solves it, and what success looks like
4. Demo:
    - the happy path
    - at least one failure or edge case
5. Key artefacts
6. Brief reflections on trade-offs and improvements

Focus on **behaviour and outcomes**, not nodes.

### Reflections

Your reflections should demonstrate **judgment and learning**, not just completion.

Strong reflections show:

- awareness of challenges and their root causes
- understanding of trade-offs — including **which model you chose and why**, from Week 2 on
- consideration of robustness and edge cases
- how your approach evolved

This is where Critical Thinking is scored. It is the cheapest five points in the program to earn and the most commonly thrown away.

### Final Check Before Submitting

Before you submit, ask yourself:

- Is the business purpose clear?
- Would someone trust this to run more than once?
- Are failures visible and handled?
- Does the link still open on someone else's machine?
- Are there any keys in the repo, the video, or the front-end?
- Do the submissions focus on outcomes, not just execution?

If yes, you are aligned with what this program is looking for.

---

# PART 3 — WEEK 4 PROJECT CONTEXT (what you are building)

## Introduction

The content team at a Koya Talent marketing agency creates and publishes content across LinkedIn, X, and an email newsletter.

The current workflow includes brainstorming content ideas, researching source material, creating SEO articles, adapting the selected article for each channel, reviewing the final content internally, and publishing or scheduling it for release.

The process works, but it takes too much manual effort to scale while keeping quality, tone, and factual accuracy consistent.

Your task is to build an AI content research and publishing agent that helps the team move from a raw idea or source URL to reviewed, channel-ready content.

The automation should begin when a content manager submits a content request. At minimum, the request should include a raw content idea, the target audience, and any supporting material or source URL. You may decide what other inputs to collect and how the content manager should submit them.

The system should research the topic, retrieve relevant source material, choose the sources or excerpts that matter, plan the content, generate article options, evaluate its own output, revise weak drafts, and prepare the selected content for LinkedIn, X, and an email newsletter.

Generated articles should follow the SEO best practices. Channel-specific outputs should follow the platform formatting rules.

The system should include a review step where a human can approve, reject, revise, or select content before publishing or scheduling. The final content should stay grounded in reviewed source material, and the system should make it clear which sources informed the output.

You may use n8n, custom code, Claude API, Claude through n8n, a backend application, a simple front-end, search or scraping tools, a retrieval system, a database, a publishing queue, or any other tools that fit your implementation.

## Testing Scenarios (8 required)

1. **Raw Idea Request**: A content request with only a topic or idea should produce relevant article options.
2. **URL-Based Request**: A content request with a source URL should extract useful source material and use it in the generated content.
3. **Research and Source Grounding**: The system should show which sources informed the output and avoid claims that are not supported by the available material.
4. **Evaluation and Revision Loop**: The system should evaluate draft quality using the content evaluation rubric, revise weak sections, and preserve the review history.
5. **Human Approval**: The system should not publish or schedule content until a human approves it.
6. **Channel Formatting**: The selected article should be adapted into LinkedIn, X, and newsletter formats that follow the formatting rules.
7. **Publishing or Scheduling**: Approved content should be published, scheduled, or saved into a clear publishing queue.
8. **Failure Handling**: If research, retrieval, generation, evaluation, approval, publishing, or logging fails, the system should make the failure clear enough to debug.

Submit the completed testing evidence table from the project page with your project.

## Deliverables (repeat, for clarity)

- A working **front-end or application link**
- A generated **content sample pack** that shows the input given to the system and the outputs it produced, including the article, LinkedIn post, X post, email newsletter, and source list
- Completed **testing evidence**
- A short **Loom video** showing how the automation works
- Answer the questions in your **reflection sheet** for this project
- A **one-page document** explaining how your automation works and how to use it

## Local Assets You Must Follow

**SEO best practices:**
- Get the primary keyword from the content idea.
- Include the primary keyword in the article title.
- Include the primary keyword in the first 100 words.
- Analyze strong competing or reference articles to identify long-tail and short-tail keywords.
- Use relevant secondary keywords in the body and section headers.
- Use one H1 title.
- Use H2 section headers.
- Use H3 subheaders where needed.
- Use short paragraphs of 2 to 3 sentences.
- Let the depth of each main section reflect the strength and complexity of the source material.
- Include 2 to 3 relevant internal or external links.
- Keep the writing readable for a broad audience.
- Include one contextually relevant image if the content needs one.
- Keep claims grounded in reviewed source material.

**Channel formatting rules:**

*LinkedIn Post:*
- Use the PAS copywriting structure: problem, agitation, solution.
- Keep paragraphs short.
- Use bullets or simple symbols when they improve clarity.
- Use a small number of relevant emojis only when they fit the brand voice.
- End with a clear call to action.
- Include a relevant image or carousel if useful.

*X Post:*
- Lead with the main benefit, insight, or hook.
- Keep the post focused on one core idea.
- Use line breaks for readability.
- Use no more than 1 to 2 relevant hashtags.
- Tag another account only if the tag adds value.

*Email Newsletter:*
- Use a strong subject line with a clear benefit or point of intrigue.
- Start with a short intro of 1 to 3 sentences.
- Make the main value section easy to skim with subheadings or bullets.
- Add an optional secondary item, such as a quick tip, link, or update.
- Include a clear call to action.
- Use a friendly sign-off.
- Write like you are speaking to a smart, busy reader who trusts you to send something useful.
- Keep the newsletter between 250 and 600 words.

**Content evaluation rubric:**

For each draft, evaluate against these criteria:

| Criterion | What to check |
| --- | --- |
| Topic Relevance | The content answers the request and stays focused on the intended topic. |
| Source Grounding | Claims, examples, and recommendations connect back to reviewed source material. |
| Factual Consistency | The content avoids contradictions, unsupported claims, and invented details. |
| Audience Fit | The content speaks to the target audience at the right level of depth. |
| Tone | The style matches the brand and channel. |
| SEO Fit | The article uses the primary keyword, relevant secondary keywords, clear headings, and useful links. |
| Channel Fit | Each adapted output follows the platform formatting rules. |
| Clarity | The content is easy to read, skimmable, and direct. |
| Completeness | The output includes every required section or channel asset. |

The evaluation output for each draft must include:
- Overall status: pass, revise, or reject
- Scores or short notes for the criteria above
- Unsupported or weak claims to remove or rewrite
- Sections that need revision
- Specific recommended changes
- Final approval status

---

# PART 4 — HOW TO HIT 5/5 ON EVERY CRITERION (working notes)

This section is the active workspace. Fill it in as you build. The goal is a 5/5 on Technical Execution, Communication, and Critical Thinking — which means a 15/15 project.

## 4.1 Technical Execution — 5/5 target

A 5/5 Technical Execution means: *Automation goes beyond the PRD to improve reliability, clarity, or robustness. Failure modes are well handled.*

Checklist (tick as you build):

- [ ] The workflow works on the happy path end to end.
- [ ] Every major step (research, retrieval, generation, evaluation, approval, publishing, logging) has explicit error detection and a clear error message that says *what failed and why*.
- [ ] The system does not silently swallow failures — if something fails, a human or the log can see it.
- [ ] Edge cases identified and handled (list them below):
    -
    -
    -
- [ ] The workflow is safe to run more than once (idempotency: no duplicate content, no corrupted state on re-run).
- [ ] Retries where appropriate (e.g. transient network/API failures).
- [ ] No hardcoded API keys or credentials in nodes — use environment variables or credential managers.
- [ ] No secrets committed to the repo (check git history, not just the current file).
- [ ] No sensitive data exposed in screenshots or the demo video.
- [ ] No real user data shown unnecessarily.
- [ ] The front-end does not expose keys or credentials to the browser.
- [ ] The system shows which sources informed the output (source attribution is visible, not implied).
- [ ] The evaluation rubric is actually applied to drafts — the output includes pass/revise/reject, scores or notes per criterion, unsupported claims flagged, sections to revise, specific recommended changes, and final approval status.
- [ ] The revision loop preserves review history (you can see what was evaluated, what was changed, and why).
- [ ] Human approval is a real gate — the system does not publish or schedule before a human approves.
- [ ] The publishing queue is clear — approved content has a visible next state (published, scheduled, or queued).
- [ ] Something beyond the PRD was added to improve reliability, clarity, or robustness (list it below):
    -

## 4.2 Communication (Video) — 5/5 target

A 5/5 Communication means: *Video is compelling, well-structured, and includes reflection and improvement ideas.*

Checklist:

- [ ] Video is 58 minutes or less.
- [ ] Flow followed:
    1. Who you are and what you built
    2. The business problem
    3. How the system solves it, and what success looks like
    4. Demo: the happy path
    5. Demo: at least one failure or edge case
    6. Key artefacts
    7. Brief reflections on trade-offs and improvements
- [ ] The video focuses on **behaviour and outcomes**, not on walking through nodes.
- [ ] The failure/edge case demo is real and shows how the system behaves, not just that it exists.
- [ ] The video would make sense to someone who has never seen the project.
- [ ] You include reflection and improvement ideas in the video (not just a demo).

## 4.3 Critical Thinking (Reflections) — 5/5 target

A 5/5 Critical Thinking means: *Reflections demonstrate self-mentoring: clear critique of the work and thoughtful future improvements.*

Checklist:

- [ ] You answer every reflection question from the submission template (see Part 1, section 5).
- [ ] You name the Claude model you used and **why**, and name the alternative you considered, and explain how you weighed quality, cost, latency, and task complexity. "It was the default" is not an answer.
- [ ] You identify the most significant challenge and its **root cause**, not just the symptom.
- [ ] You say what you would do differently with your current knowledge — one concrete thing that would make the solution more robust or efficient.
- [ ] You list the edge cases you accounted for and **how** you accounted for them.
- [ ] You list the clarifying questions you would ask in a business setting before building — this shows you understand the gap between a vague brief and a buildable system.
- [ ] Your reflections show how your approach evolved, not just what you ended up with.
- [ ] You critique your own work honestly — where it is weak, what you would improve, what you would not ship as-is.

---

# PART 5 — RUNNING BUILD LOG (fill in as you work)

Use this section to track progress so a broken session can be resumed without re-reading everything.

## Session start: 2026-09-14 (first build session)

## What exists so far

- `docs/provided/` — PRD + 3 asset files, untouched from the project (PRD.md, seo-best-practices.md, channel-formatting-rules.md, content-evaluation-rubric.md)
- `docs/work/architecture.md` — full architecture doc, 9 sections: design principles, enum types, 10 tables (content_requests, intake_attachments, sources, content_plans, article_drafts, evaluations, human_reviews, channel_adaptations, publishing_queue, jobs, stage_events), indexes, retry/dead-letter logic, minimal auth (§6: access_rules, users, login_attempts, sessions + 3 refinements + RLS decision), what's deferred, full example data trace (§8), project structure for backend + frontend (§9 — FastAPI + polling worker + Claude service + Next.js, no n8n)
- `docs/work/PROJECT_SUMMARY.md` — verbatim dump of everything in the project (PRD, workflow, SEO rules, channel rules, rubric, 8 test scenarios, 6 deliverables, resource links, decision checklist)
- `docs/work/SUBMISSION_WORKBOOK.md` — combined submission template (Part 1) + production-ready systems grading guide (Part 2) + Week 4 project context (Part 3) + 5/5 checklists for Technical Execution / Communication / Critical Thinking (Part 4) + running build log (Part 5)
- `README.md` at repo root — updated to point at `provided/` layout

## What is built

**Docs only — no code yet.** Everything above is design documentation:
- Architecture fully specified (schema + auth + project structure)
- Submission workbook assembled (what to hand in + how it's graded + how to hit 5/5)
- Directory organized (provided/ vs work/)
- All internal references in docs pointing at the right places

## What is tested (which of the 8 scenarios, and the result)

None yet — no running system. The test plan is written into `backend/tests/` in the architecture doc (§9.2): test_intake, test_source_grounding, test_evaluation_loop, test_human_approval_gate, test_channel_formatting, test_publishing_queue, test_failure_handling, test_auth — each mapped 1:1 to the 8 required scenarios.

## What is not yet built

- Backend code (FastAPI app, worker, Claude service, auth module)
- Supabase schema (migrations from §3 of architecture.md)
- Frontend code (Next.js app + components)
- Any running system, any sample output, any Loom video

## Open decisions

- Claude model selection for v1 (which model for which step) — to be recorded in `backend/claude/models.py` as the model router, and used later in the reflection sheet's model-choice question
- Which scraping/retrieval tool the `research` handler uses (Firecrawl, Crawl4AI, direct HTTP) — the handler owns this, §3.2's `retrieval_method` records it
- Whether frontend uses Supabase Storage for intake image uploads (lib/supabase.ts with anon key) or handles media another way — only affects one frontend lib, no architecture impact
- Whether to generate frontend types from FastAPI OpenAPI spec or hand-write them (§9.4) — hand-write is fine for v1 if backed by a shape-matching assertion in tests

## Errors encountered and how they were resolved

None at the code level — no code written yet. Doc-level: the original `docs/` had everything flat (PRD, assets/, architecture.md, SUBMISSION_WORKBOOK.md mixed together). Resolved by splitting into `provided/` (project-owned, never edited) and `work/` (ours), and moving PROJECT_SUMMARY.md from repo root into `docs/work/`. Updated all `assets/` references in README.md and PROJECT_SUMMARY.md to `../provided/assets/`.

## Model used and why (for reflections)

Not yet decided / not yet used. To be filled in once the Claude service is wired and we've made the actual model choice. The architecture document leaves this open deliberately (§9.2, `claude/models.py` is the model router) so the choice is explicit and recorded in code, not implicit in each call.

## Edge cases handled (for reflections)

Not yet built, so none handled at runtime. The design accounts for these at the schema/structure level (to be reflected on later):
- Multiple source URLs + image attachments per request (intake_attachments table, not a single source_url column)
- Revision history preserved structurally (article_drafts append-only + parent_draft_id lineage, not overwrite)
- Failure visibility structural (stage_events append-only log, not app logs)
- Publishing as a queue by default, not a live integration (publishing_queue + mock adapter)
- Source traceability as a first-class relationship (source_ids_used array + sources table, not a text blob)
- Allowlist not enumerable (request-code returns same response either way)
- OTP invalidated after use (consumed_at field)
- Session is opaque + server-side + immediate revocation on logout (delete row, no revoked_at needed)

## Known limitations (for the one-pager appendix + video script)

**Intake's gibberish filter is a deterministic heuristic, not a semantic check — it can be beaten by a single character.** Found during testing (`TESTING_FINDINGS.md`, Session 3, test #8): the string `"xkcd zzzz qwrty tbh"` was correctly rejected at intake ("doesn't look like real words — no vowels"), but appending a single vowel (`"xkcd zzzz qwrty tbha"`) passed the same filter — the check only looks for *the presence of a vowel*, not whether the text is actually meaningful. That's a deliberate tradeoff, not an oversight: catching this reliably would require a Claude call on every single intake submission, which defeats the point of having a free, instant, deterministic filter at all. A semantic check that costs money on every request (including the vast majority of genuinely fine ones) isn't worth it just to catch a rare adversarial edge case.

The system still didn't produce bad output from it. When the nonsense idea reached the generation step, Claude refused to write the article rather than inventing a fake xkcd comic and writing confidently about it — the draft was an honest explanation of why it couldn't proceed, the evaluator scored it 1.40/5, and the loop stopped after one attempt instead of spending the full revision cap. Total cost: 3 Claude calls, $0.0286.

**For the one-pager's Appendix (Assumptions/Limitations):**
> Intake validation catches obviously-empty, too-short, or clearly-nonsense input for free, before any AI cost is spent — but it's a deterministic heuristic, not a semantic judgment, so it can be beaten by adversarial input (e.g. a single added character). This is a known, accepted tradeoff: the generation step is the real backstop — it's instructed to refuse rather than fabricate when it has nothing real to work with, so bad input costs a small amount (a few cents) rather than producing confident-looking fabricated content.

**For the video script** (pairs well with the failure/edge-case demo beat):
> "Our intake filter catches most junk for free, before we spend anything on it — but it's not perfect. Watch what happens if I sneak something past it..." *[submit the near-miss gibberish case]* "...it got through intake, but the writer itself refused to make something up — it told us honestly it didn't have anything real to write about, instead of inventing a fake article. That's the layer we actually rely on to stop bad content from reaching a human looking finished."

## One thing to do differently next time (for reflections)

To be filled in after building. Likely candidate: the architecture doc §9.7 lists what's deferred (RLS, real publishing, pgvector, configurable backoff) — once we've built v1 and seen where the actual friction was, this field gets the honest answer.

## Clarifying questions (for reflections)

To be filled in after building, but the project brief already implies these (to be sharpened):
- What does "publish" actually mean for this team — do they have real LinkedIn/X/newsletter integrations today, or is "saved into a publishing queue" the real deliverable for v1?
- Who is the content manager audience for the front-end — one person, a small team, external reviewers? (Drives whether auth is domain-wide allowlist vs. individual emails, and whether the one-pager should address multiple user roles.)
- What's the expected volume — a few requests per week, or enough that cost-per-run and retry behavior matter materially? (Drives model selection and whether to invest in caching/reuse.)
- Are there brand voice / tone guidelines beyond what the rubric and channel-formatting-rules capture — a style guide document, example posts, a brandbook? (Drives whether the Claude prompts need a voice section beyond "match the brand.")
- What does the human reviewer do today when they reject or ask for a revision — do they rewrite themselves, or do they give written feedback the author acts on? (Drives whether `human_reviews.notes` should feed back into a revision job automatically or just sit as a record.)

## Things to verify before submitting

- [ ] Front-end link loads from another machine and is still live
- [ ] No keys in repo, video, or front-end
- [ ] Content sample pack has: input, article, LinkedIn post, X post, email newsletter, source list
- [ ] Testing evidence table is filled in for all 8 scenarios
- [ ] One-pager exists and covers: header, purpose & success criteria, how it works, how to use it, appendix
- [ ] Video covers: who you are, business problem, solution, happy path demo, failure/edge case demo, key artefacts, reflections
- [ ] Reflection sheet answers all 5 questions, including model choice with alternative and trade-offs
- [ ] Workflow is runnable, not broken, includes error handling, safe to run more than once
- [ ] Submission form URL is the correct one: https://docs.google.com/forms/d/e/1FAIpQLSfnFXF2X4L8T4D8BBAX3GoJcV_XaPYv8Ejrq7bZQjtPAjWDtA/viewform

---

*End of workbook.*

> **Build log:** The running build log was split out into its own file — `docs/work/BUILD_LOG.md` — so it can grow session by session without bloating the submission workbook. Update that file every session; this workbook stays focused on what you hand in and how it's graded.
