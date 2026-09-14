# Week 4 Submission Workbook — AI Content Research and Publishing Agent

> **Purpose:** This file is the single reference for everything required to submit Week 4. It combines the submission template (deliverables, testing evidence table, reflection sheet), the Instructor / Participant Guide for production-ready systems (grading criteria, the 5 core production skills, how work is graded, submission requirements), and a working space to fill in as you build. Use it as your running checklist — if the session breaks, the reference is here.

---

# PART 1 — SUBMISSION TEMPLATE (what you hand in)

## Deliverables

**1. Front-end or application link**

<aside>

*Paste here*

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
| Raw idea request |  |  |  |  |
| URL-based request |  |  |  |  |
| Research and source grounding |  |  |  |  |
| Evaluation and revision loop |  |  |  |  |
| Human approval before publishing |  |  |  |  |
| Channel formatting |  |  |  |  |
| Publishing or scheduling |  |  |  |  |
| Failure handling |  |  |  |  |

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

1. 
2. 
3. 
4. 
5. 
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

## Session start: date/time

## What exists so far

-

## What is built

-

## What is tested (which of the 8 scenarios, and the result)

-

## What is not yet built

-

## Open decisions

-

## Errors encountered and how they were resolved

-

## Model used and why (for reflections)

-

## Edge cases handled (for reflections)

-

## One thing to do differently next time (for reflections)

-

## Clarifying questions (for reflections)

-

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
