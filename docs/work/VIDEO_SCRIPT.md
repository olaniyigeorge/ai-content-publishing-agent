# Demo Video Script — Week 4 Submission

> Target: **5–8 minutes** (the actual program limit — Week 3's 9-minute video was flagged; do not repeat it). Time yourself against this script before recording; if a section runs long, cut narration, not the demo itself. One take, one file — Week 3 also lost points for submitting two different demo videos.
>
> Flow required by `SUBMISSION_WORKBOOK.md`: who you are + what you built → the business problem → how the system solves it → happy path demo → failure/edge case demo → key artefacts → brief reflection on trade-offs. This script hits every one of those beats — it just tells them as one story instead of six separate slides, so pick one throughline (a content manager, one request, one real source) and stay with it start to finish instead of narrating features in the abstract.

---

## 0:00–0:30 — Who you are, and the story you're about to tell

> "I'm Olaniyi George. Picture a content manager at an agency like Koya Talent, staring at a blank brief that needs to become a full article and three social posts by end of day. That's the story I'm going to walk through — one real idea, one real source, watch what happens to it — and this is the system I built to carry it."

Show: the live app URL in the browser bar (`ai-content-publishing-agent.vercel.app`), logged in.

---

## 0:30–1:30 — The problem, before this system existed

> "Before this, that content manager's day looked like: brainstorm an idea, research it by hand, write a full SEO article, then manually rewrite it three different ways for LinkedIn, X, and a newsletter, then get someone to check it before it goes anywhere. It works. It just doesn't scale — every piece costs the same manual effort as the last one, and how good it turns out depends on who happened to write it that day."

> "So the story isn't 'remove the person.' It's: move where they spend their time — from writing everything by hand, to reviewing what the system already drafted. And make sure nothing reaches them looking finished unless it can actually back itself up with a real source."

Show: nothing yet, or a quick cut to the PRD/one-pager purpose section.

---

## 1:30–2:15 — How the story plays out, and what "it worked" means

> "Here's what happens to that content manager's idea once it enters the system: it gets researched, the sources that actually have usable content get picked out from the ones that don't, a draft gets written and planned around them, the draft grades itself against a rubric, weak drafts get one more pass — up to a cap — and only then does a human see it. Approve it, and it gets rewritten for all three channels and dropped into a queue."

> "For this story to have a good ending, three things have to be true: every claim in the final piece can be traced back to a real source, every channel's version actually follows that channel's own rules, and nobody's post goes out without a human having looked at it first."

Show: a quick screen of the pipeline timeline / architecture diagram if you have one handy — keep this under 45 seconds, don't narrate every table.

---

## 2:15–4:30 — Watching it happen: the happy path

Use a request submitted **before** recording (or submit live if it's fast enough) with one real source URL — this is the same idea from the opening, now actually going through the system.

1. Show the intake form — point out the required fields (idea, target audience, optional source URL/attachments). "This is the moment our content manager hands the idea off."
2. Jump to the request detail page. Show the pipeline timeline moving through research → planning → generation → evaluation. "It's working through the same steps she'd do by hand — just not by hand."
3. Open the sources list — show the source marked `selected` with its specific relevance note (not boilerplate). "It didn't just grab a link, it explains why this one earned a place in the draft."
4. Open the draft — point to one sentence and the source it's attributed to. "Every claim like this one traces back to something real — that's the part I care about most."
5. Show the evaluation output — pass/revise/reject status and per-criterion notes, not just a score. "Before a human even sees it, the system already graded its own work."
6. Approve the draft. "This is the one moment a person has to step in — and it's a decision, not a rewrite."
7. Show the three channel adaptations side by side — LinkedIn (PAS structure), X (short, ≤280 chars), newsletter (subject line + CTA). Read one line from each out loud so it's obvious they're genuinely different, not the same text three times.
8. Move it to the publishing queue — and say out loud that this is a queue, not a live post to LinkedIn/X yet.

> "That's the whole story, start to finish — one idea in, three approved, channel-correct, source-attributed pieces out, with exactly one human decision in the middle."

---

## 4:30–6:00 — The same story, but something goes wrong

Pick **one** of these (whichever you actually verified live in `LIVE_TEST_SESSION.md` — don't demo something you haven't confirmed works). Frame it as "what if the content manager's idea didn't have good sources to begin with" rather than a separate demo.

**Option A — all sources unusable:**
> "Now imagine she hands over an idea, but every source she gives it is dead. Watch — [submit the all-dead-URL request]. The sources list shows both as failed, with the actual reason, not just a red X. And instead of burning the full revision budget writing three drafts from nothing, the system notices after one attempt that it has zero usable sources and sends it straight to human review with an explicit note — that's the ungroundable-draft guard catching the story before it goes anywhere bad."

**Option B — the intake filter near-miss:**
> "Our intake filter catches most junk for free, before we spend anything on it — but it's not perfect. Watch what happens if I sneak something past it..." [submit the near-miss gibberish case] "...it got through intake, but the writer itself refused to make something up — it told us honestly it didn't have anything real to write about, instead of inventing a fake article. That's the layer we actually rely on to stop bad content from reaching a human looking finished."

> Either way, close with: "The point of this second story isn't that the system never fails — it's that when it does, you can see exactly where and why, and it doesn't cost a runaway bill or a fabricated article to find out."

---

## 6:00–7:00 — Key artefacts

Quick screen-share, no narration needed beyond naming each:
- The content sample pack (input → article → LinkedIn → X → newsletter → source list).
- The testing evidence table.
- The one-pager.
- (If time) the model router file (`claude/models.py`) — "Sonnet for generation and evaluation, Haiku for research and adaptation, because those are structured/extraction tasks, not creative writing."

---

## 7:00–8:00 — How I'd change the next chapter

> "The biggest trade-off in this build: the intake filter is a fast, free, deterministic check — it can be beaten by a single character, and it will be beaten sometimes. We accepted that because the real backstop is the generation step refusing to fabricate content, not a perfect filter at the front door."

> "If I rebuilt this today, the one thing I'd change is [insert your actual answer from the reflection sheet — e.g. giving the revision loop a reason code before deciding whether to retry, instead of always spending the same number of attempts regardless of why the draft failed]."

> "And to be honest about where this story ends today: it queues content — it doesn't post to real LinkedIn, X, or email platforms yet. That's a deliberate v1 scope decision, stated here and in the one-pager, not a hidden gap."

**End.** Do not add a closing "thanks for watching" beat if you're tight on time — the reflections line is the actual close.

---

## Recording checklist (do this before you hit record)

- [ ] Re-read `LIVE_TEST_SESSION.md` and confirm you know exactly which scenario you'll show for the failure/edge case demo, and that it's already been verified live once.
- [ ] Close any browser tabs/extensions that might leak something (email inbox, other client data).
- [ ] Confirm no API keys are visible in the network tab if you show it.
- [ ] Time a dry run — cut ruthlessly if over 8 minutes. A tight 6-minute video beats a thorough 9-minute one (this is graded, and 9 minutes cost marks last time).
- [ ] Export/upload once. One link, one file, in the submission form — not two versions like last time.
