# AI Content Research and Publishing Agent — Handover Guide

**Owner:** Olaniyi George (olaniyigeorge77@gmail.com)
**Live app:** https://ai-content-publishing-agent.vercel.app/
**Repo:** https://github.com/olaniyigeorge/ai-content-publishing-agent
**Last updated:** 2026-09-18

---

## What this is for

If you manage content for LinkedIn, X, and a newsletter, you know the drill: get an idea, research it, write a full article, rewrite it three different ways for three platforms, check your own work, then publish. Every piece takes the same amount of manual effort, and quality depends on who happened to write it that day.

This tool takes that idea off your desk and hands you back a finished, checked, ready-to-post set of content — while keeping you as the person who makes the final call.

**Your starting point:** a rough idea, or a link to an article you want to base something on.
**Your end point:** a reviewed article plus a LinkedIn post, an X post, and a newsletter draft, all sitting in a queue waiting for you to say "go."
**What you're trading:** you stop writing from a blank page and start reviewing finished-looking drafts. Nothing reaches your queue without you personally approving it.

---

## How it gets you there

Think of it as five people doing one job in sequence, each checking the last one's work:

1. **You submit a request.** A topic, or a link, plus who it's for (e.g. "heads of content at agencies"). You can attach files or extra links too.

2. **It researches.** If you gave it a link, it reads that page. If you didn't, it goes and finds real, current sources on its own — and tells you honestly how confident it is in each one. It never pretends to have a source it doesn't.

3. **It plans, then writes.** It outlines the article from what it found, then writes a full draft — following SEO rules (right keywords, proper headings) and tying every claim back to something it actually read.

4. **It checks its own work.** A second AI pass grades the draft against a real rubric — is it accurate, on-topic, well-sourced, readable — and scores it. If the draft is weak, the system rewrites it automatically, up to a few tries. You can see exactly what changed and why between versions, not just the final result.

5. **You decide.** You read the draft, see which sources back it up and what the AI flagged as weak, and you approve it, reject it, ask for a revision, or edit it yourself by hand. **Nothing moves forward without your explicit approval** — the system cannot publish or queue anything on its own.

6. **It adapts the approved piece for each channel.** Once you approve, it automatically rewrites the article into a LinkedIn post, an X post, and a newsletter — each one actually following that platform's own rules (character limits, hashtag limits, tone), not just the same text pasted three times. If a rewrite breaks a platform's rules, it's caught and marked failed instead of slipping through.

7. **It lands in your publishing queue.** Approved, correctly-formatted content sits in a clearly labeled queue — ready to publish, not yet posted. **Important:** this version doesn't actually post to LinkedIn, X, or your email platform for you yet — it prepares everything and hands you a queue you can act on, or plug into your real posting tools later.

Every step along the way is logged, so if anything goes wrong — a source can't be reached, a draft can't clear review — you'll see exactly what happened and why, in plain language, not a technical error message.

---

## How to use it, step by step

1. Go to the live app link above and log in with your email — you'll get a one-time code by email, no password needed.
2. Click **"New Request."** Type your idea and/or paste a source link, add your target audience, and attach any files if you have them.
3. Submit, and watch the page update live as it researches, plans, and drafts.
4. Once a draft is ready, open it. Read the article, check which sources it used and why, and read the AI's own notes on where it's weak.
5. Approve it, reject it, ask for a rewrite, or edit it directly yourself.
6. Once approved, open the channel tab to see your LinkedIn, X, and newsletter versions.
7. Move the approved content into your publishing queue from the same page.

---

## Good to know before you rely on this

- **"Publish" means queued and ready, not posted.** This version stops one step short of actually pushing to LinkedIn/X/email — it hands you a finished, approved queue instead.
- **If you give it a weak or vague idea, it will say so rather than guess.** A one-line, unclear idea gets flagged and, if there's truly nothing to work from, the system refuses to invent a confident-sounding article out of nothing.
- **Model choice is deliberately mixed, not one-size-fits-all.** The two steps where quality matters most — writing the article and grading it — use the strongest available AI model, since the grading step is the one thing standing between a bad draft and your desk. Research, planning, and reformatting use a faster, cheaper model, since those are closer to organizing information than original judgment.
- **A known gap:** if you ask for a rewrite on a channel post (say, X) twice in quick succession, both requests currently run instead of the system catching the duplicate — it won't create a mess, but it will cost a bit of wasted AI usage. Rewriting a full article already has this protection; the channel-level version doesn't yet.
- **Cost stays visible.** Each request typically costs a few cents to a bit over a dollar in AI usage, depending on how many revision rounds it needs — you can always see what a request has cost before deciding whether to push it further.
