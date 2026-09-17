# AI Content Research and Publishing Agent

**Owner:** Olaniyi George (olaniyigeorge77@gmail.com)
**Live app:** https://ai-content-publishing-agent.vercel.app/
**API:** https://ai-content-publishing-agent.onrender.com
**Repo:** https://github.com/olaniyigeorge/ai-content-publishing-agent
**Last updated:** 2026-09-17

---

## Purpose & Success Criteria

**Who it's for:** a content manager at a marketing agency (modeled on Koya Talent's content team) who publishes across LinkedIn, X, and an email newsletter.

**What problem existed:** producing one piece of content meant brainstorming, researching, writing a full SEO article by hand, manually rewriting it three different ways per channel, self-reviewing, then publishing — all manual effort, repeated identically for every new piece, with quality and tone depending on who happened to write it that day.

**What it does:** takes a raw idea or a source URL from a content manager and runs it through research and source retrieval, source selection, planning, drafting, self-evaluation against a rubric, automatic revision of weak drafts (up to a cap), then adapts the approved article into LinkedIn, X, and newsletter formats. Nothing reaches the publishing queue without an explicit human approval.

**What changes if it works:** the bottleneck moves from *writing* to *reviewing*. A content manager spends their time judging and approving finished-looking drafts instead of producing them from scratch, and every piece goes through the same grounded, rubric-checked process regardless of who submitted the request.

**How success is measured:** every claim in an approved piece traces to a real, reviewed source; every channel output actually follows that channel's formatting rules (not the same text reformatted three times); nothing is approved or queued without a human decision; and cost per request stays visible and bounded (typically $0.03–$0.25 depending on how many revision cycles a request needs).

---

## How It Works

1. A content manager submits a request: a raw idea and/or a source URL, plus a target audience.
2. **Research:** the system scrapes any provided URLs (via Firecrawl) and records each one's usable/unusable status with a specific reason — a failed or unusable source is never silently treated as real grounding material.
3. **Source selection:** Claude (Haiku) picks which retrieved content is actually usable and why.
4. **Planning:** Claude (Haiku) outlines the article from the selected sources.
5. **Generation:** Claude (Sonnet) writes the article, following SEO rules (primary keyword in title/first 100 words, H1/H2/H3 structure, source-grounded claims).
6. **Evaluation:** Claude (Sonnet) scores the draft against the content rubric (topic relevance, source grounding, factual consistency, audience fit, tone, SEO fit, clarity, completeness) and returns pass/revise/reject plus specific flagged claims and recommended changes.
7. **Revision loop:** weak drafts are automatically revised, up to a fixed attempt cap. A deterministic guard stops the loop early and escalates to a human if a draft has no real source material behind it — revising the wording can't fix a grounding problem.
8. **Human review:** a person approves, rejects, requests revision, or hand-edits the draft. This is a real gate — the system cannot reach a publishable/queued state without it.
9. **Channel adaptation:** the approved article is adapted into LinkedIn (PAS structure), X (short, hook-first, ≤280 chars), and newsletter (250–600 words, subject line, CTA) formats. Real character/word counts are recomputed server-side — a model's own "this passes" claim is overridden if the computed check fails.
10. **Publishing queue:** approved, correctly-formatted content moves into a queue with a clearly labeled state (queued/ready-to-publish). **v1 does not post to real LinkedIn, X, or email platforms** — this is an internal queue, stated here explicitly rather than left to be discovered later.

Every stage writes to an append-only event log, so a failure at any step is visible (what failed, why) rather than silent.

---

## How to Use It

1. Go to https://ai-content-publishing-agent.vercel.app/ and log in with an allowlisted email (passwordless — a one-time code is emailed to you).
2. Click "New Request." Enter a content idea and/or one or more source URLs, and a target audience. Optionally attach supporting files/images.
3. Submit. The request page shows live pipeline progress (researching → planning → drafting → evaluating).
4. Once a draft is ready, open the request to review: read the draft, check which sources it's attributed to, and read the evaluation notes.
5. Approve, reject, request a revision, or hand-edit the draft.
6. Once approved, open the channel adaptations tab to see the LinkedIn, X, and newsletter versions.
7. Move approved content to the publishing queue from the request page.

---

## Appendix — Assumptions, Limitations, Known Trade-offs

- **"Publish" means queued, not posted.** v1 has no real LinkedIn/X/email integration. This is a deliberate scope decision for this build, not a hidden gap.
- **Intake validation is a deterministic heuristic, not a semantic judgment.** It catches empty, too-short, and obviously-gibberish input for free, before any AI cost is spent — but it can be beaten by adversarial input (e.g. one added character defeats a no-vowel check). The real backstop is the generation step itself, which is instructed to refuse rather than fabricate when it has nothing real to work with, so the worst case for bad input is a few cents spent on an honest refusal, not a confident-looking fabricated article.
- **Model routing is cost-aware, not uniform.** Sonnet 5 for the two quality-sensitive steps (drafting, evaluation); Haiku 4.5 for research, planning, and channel adaptation (closer to structured extraction than original writing). Full reasoning is in `backend/claude/models.py`.
- **Single-process worker.** One slow job can delay the rest of the queue. Acceptable at this scale; would need horizontal workers at real production volume.
- **No admin UI for the access allowlist yet** — managed directly via the backend's `/auth/access-rules` endpoints or direct database inserts. Fine for a small reviewer team; would need a real admin role for a larger one.
- **Known, not-yet-implemented improvement:** the revision loop doesn't yet classify *why* an evaluation failed before deciding whether another attempt can plausibly fix it — a source-grounding failure and a fixable wording issue currently consume the same revision budget, except for the one specific case (zero usable sources) that already has a dedicated early-exit guard.
