# Demo Video Script — Week 4 Submission

> Target: **5–8 minutes** (the actual program limit — Week 3's 9-minute video was flagged; do not repeat it). Time yourself against this script before recording; if a section runs long, cut narration, not the demo itself. One take, one file — Week 3 also lost points for submitting two different demo videos.
>
> Flow required by `SUBMISSION_WORKBOOK.md`: who you are + what you built → the business problem → how the system solves it → happy path demo → failure/edge case demo → key artefacts → brief reflection on trade-offs.

---

## 0:00–0:30 — Who you are and what you built

> "I'm Olaniyi George. This is an AI content research and publishing agent — it takes a raw idea or a source URL from a content manager and turns it into a researched, source-grounded article, adapted for LinkedIn, X, and an email newsletter, with a human approval step before anything gets queued to publish."

Show: the live app URL in the browser bar (`ai-content-publishing-agent.vercel.app`), logged in.

---

## 0:30–1:30 — The business problem

> "A content team at an agency like Koya Talent does this by hand today: brainstorm, research, write an SEO article, manually rewrite it three different ways per channel, review it, then publish. It works, but it doesn't scale — every new piece of content is the same amount of manual effort, and quality depends on who happened to write it that day."

> "The goal isn't to remove the human. It's to move the bottleneck from *writing* to *reviewing* — and to make sure nothing gets approved that the system can't actually back up with a real source."

Show: nothing yet, or a quick cut to the PRD/one-pager purpose section.

---

## 1:30–2:15 — How the system solves it, what success looks like

> "The pipeline is: submit a request → research and source retrieval → the system picks which sources actually have usable content → plans and drafts the article → evaluates its own draft against a rubric → revises weak drafts automatically, up to a cap → a human approves, rejects, or edits → approved content gets adapted for all three channels → queued for publishing."

> "Success isn't 'it produced something.' Success is: every claim in the final piece traces to a real source, every channel output actually follows that channel's formatting rules, and nothing gets published without a human looking at it first."

Show: a quick screen of the pipeline timeline / architecture diagram if you have one handy — keep this under 45 seconds, don't narrate every table.

---

## 2:15–4:30 — Demo: happy path

Use a request submitted **before** recording (or submit live if it's fast enough) with one real source URL.

1. Show the intake form — point out the required fields (idea, target audience, optional source URL/attachments).
2. Jump to the request detail page. Show the pipeline timeline moving through research → planning → generation → evaluation.
3. Open the sources list — show the source marked `selected` with its specific relevance note (not boilerplate).
4. Open the draft — point to one sentence and the source it's attributed to.
5. Show the evaluation output — pass/revise/reject status and per-criterion notes, not just a score.
6. Approve the draft.
7. Show the three channel adaptations side by side — LinkedIn (PAS structure), X (short, ≤280 chars), newsletter (subject line + CTA). Read one line from each out loud so it's obvious they're genuinely different, not the same text three times.
8. Move it to the publishing queue — and say out loud that this is a queue, not a live post to LinkedIn/X yet.

> "That's the happy path — idea to three approved, channel-correct, source-attributed pieces, with a human decision in the middle."

---

## 4:30–6:00 — Demo: failure / edge case

Pick **one** of these (whichever you actually verified live in `LIVE_TEST_SESSION.md` — don't demo something you haven't confirmed works):

**Option A — all sources unusable:**
> "What happens if every source I give it is dead? Watch — [submit the all-dead-URL request]. The sources list shows both as failed, with the actual reason, not just a red X. And instead of burning the full revision budget writing three drafts from nothing, the system catches that it has zero usable sources after one attempt and sends it straight to human review with an explicit note — that's the ungroundable-draft guard."

**Option B — the intake filter near-miss:**
> "Our intake filter catches most junk for free, before we spend anything on it — but it's not perfect. Watch what happens if I sneak something past it..." [submit the near-miss gibberish case] "...it got through intake, but the writer itself refused to make something up — it told us honestly it didn't have anything real to write about, instead of inventing a fake article. That's the layer we actually rely on to stop bad content from reaching a human looking finished."

> Either way, close with: "The point isn't that this never fails — it's that when it fails, you can see it, and it doesn't cost you a runaway bill or a fabricated article to find out."

---

## 6:00–7:00 — Key artefacts

Quick screen-share, no narration needed beyond naming each:
- The content sample pack (input → article → LinkedIn → X → newsletter → source list).
- The testing evidence table.
- The one-pager.
- (If time) the model router file (`claude/models.py`) — "Sonnet for generation and evaluation, Haiku for research and adaptation, because those are structured/extraction tasks, not creative writing."

---

## 7:00–8:00 — Brief reflections on trade-offs and improvements

> "The biggest trade-off in this build: the intake filter is a fast, free, deterministic check — it can be beaten by a single character, and it will be beaten sometimes. We accepted that because the real backstop is the generation step refusing to fabricate content, not a perfect filter at the front door."

> "If I rebuilt this today, the one thing I'd change is [insert your actual answer from the reflection sheet — e.g. giving the revision loop a reason code before deciding whether to retry, instead of always spending the same number of attempts regardless of why the draft failed]."

> "Right now this queues content — it doesn't post to real LinkedIn, X, or email platforms. That's a deliberate v1 scope decision, stated honestly here and in the one-pager, not a hidden gap."

**End.** Do not add a closing "thanks for watching" beat if you're tight on time — the reflections line is the actual close.

---

## Recording checklist (do this before you hit record)

- [ ] Re-read `LIVE_TEST_SESSION.md` and confirm you know exactly which scenario you'll show for the failure/edge case demo, and that it's already been verified live once.
- [ ] Close any browser tabs/extensions that might leak something (email inbox, other client data).
- [ ] Confirm no API keys are visible in the network tab if you show it.
- [ ] Time a dry run — cut ruthlessly if over 8 minutes. A tight 6-minute video beats a thorough 9-minute one (this is graded, and 9 minutes cost marks last time).
- [ ] Export/upload once. One link, one file, in the submission form — not two versions like last time.
